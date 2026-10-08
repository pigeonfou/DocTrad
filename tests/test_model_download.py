import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from app import model_download as download

class Hub:
    def __init__(self,license='apache-2.0',weights=True):
        self.license=license;self.calls=[];self.weights=weights
    def model_info(self,repo,**kwargs):
        self.calls.append(('info',repo,kwargs))
        names=['config.json','source.spm']+(['model.safetensors'] if self.weights else ['pytorch_model.bin'])+['../escape.json','remote_code.py']
        return SimpleNamespace(sha='a'*40,card_data={'license':self.license},siblings=[SimpleNamespace(rfilename=n,size=7,lfs=SimpleNamespace(sha256=hashlib.sha256(b'fixture').hexdigest())) for n in names])
    def hf_hub_download(self,repo,name,**kwargs):
        self.calls.append(('file',name,kwargs));path=Path(kwargs['local_dir'])/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture');return str(path)


def test_verified_atomic_install_and_idempotence(tmp_path):
    hub=Hub();root=tmp_path/'models';status=tmp_path/'status.json'
    download.download_model('opus-mt-en-fr',root,status,hub=hub)
    assert download.verify_existing(root/'opus-mt-en-fr','opus-mt-en-fr')
    manifest=json.loads((root/'opus-mt-en-fr/manifest.json').read_text())
    assert manifest['default'] and manifest['revision']=='a'*40
    assert set(manifest['sha256'])=={'config.json','source.spm','model.safetensors'}
    assert json.loads(status.read_text())['status']=='ready'
    assert all(c[2]['revision']=='a'*40 and c[2]['token'] is False for c in hub.calls if c[0]=='file')
    count=len(hub.calls);download.download_model('opus-mt-en-fr',root,status,hub=hub);assert len(hub.calls)==count

def test_refuses_pickle_only(tmp_path):
    hub=Hub(weights=False)
    with pytest.raises(ValueError):download.download_model('opus-mt-en-fr',tmp_path/'models',tmp_path/'status.json',hub=hub)
    assert not any(c[0]=='file' for c in hub.calls)
    assert not (tmp_path/'models/opus-mt-en-fr').exists()


def test_no_overwrite_tampered_install(tmp_path):
    root=tmp_path/'models';status=tmp_path/'status.json';download.download_model('opus-mt-en-fr',root,status,hub=Hub())
    (root/'opus-mt-en-fr/model.safetensors').write_text('tampered')
    with pytest.raises(ValueError):download.download_model('opus-mt-en-fr',root,status,hub=Hub())
    assert (root/'opus-mt-en-fr/model.safetensors').read_text()=='tampered'


def test_child_does_not_inherit_database_or_auth_secrets(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_URL','private-db');monkeypatch.setenv('SESSION_SECRET','secret');monkeypatch.setenv('HF_TOKEN','private-token');monkeypatch.setenv('HF_HUB_OFFLINE','1')
    with patch.object(download.subprocess,'Popen') as spawn:
        download.start_download('opus-mt-en-fr',tmp_path/'models',tmp_path/'state')
        env=spawn.call_args.kwargs['env']
        assert not {'DATABASE_URL','SESSION_SECRET','HF_TOKEN'} & env.keys()
        assert env['HF_HUB_OFFLINE']=='0' and env['HF_HUB_DISABLE_TELEMETRY']=='1'
        assert '--allow-network' in spawn.call_args.args[0]
        assert os.environ['HF_HUB_OFFLINE']=='1'


def test_lock_and_interrupted_state(tmp_path):
    models=tmp_path/'models';state=tmp_path/'state';state.mkdir();status=state/'job.json'
    download.write_status(status,status='downloading',model_id='opus-mt-en-fr')
    fd=download.lock_download(models)
    try:
        with pytest.raises(ValueError):download.start_download('opus-mt-en-fr',models,state)
        assert download.latest_status(state,models)['status']=='downloading'
    finally:os.close(fd)
    assert download.latest_status(state,models)['status']=='failed'


def test_disk_preflight_and_upstream_hash(tmp_path):
    with patch.object(download.shutil,'disk_usage',return_value=SimpleNamespace(free=10)):
        with pytest.raises(ValueError,match='Espace'):download.download_model('opus-mt-en-fr',tmp_path/'models',tmp_path/'status.json',hub=Hub())
    class Corrupt(Hub):
        def hf_hub_download(self,*args,**kwargs):
            path=super().hf_hub_download(*args,**kwargs);Path(path).write_text('wrong');return path
    with pytest.raises(ValueError,match='SHA-256'):download.download_model('opus-mt-en-fr',tmp_path/'models',tmp_path/'status.json',hub=Corrupt())
    assert not (tmp_path/'models/opus-mt-en-fr').exists()


def test_admin_only_confirmation_csrf_and_status(client,monkeypatch):
    from test_web import signin
    token=signin(client)
    response=client.post('/admin/models/download',data={'model_id':'opus-mt-en-fr','token':token,'confirm_network':'yes'})
    assert response.status_code==403
    client.cookies.clear()
    token=signin(client,name='admin',admin=True)
    assert 'Télécharger et installer le modèle' in client.get('/admin').text
    with patch.object(download,'start_download',return_value='job') as start:
        assert client.post('/admin/models/download',data={'model_id':'opus-mt-en-fr','token':token}).status_code==400
        assert client.post('/admin/models/download',data={'model_id':'opus-mt-en-fr','token':'invalid','confirm_network':'yes'}).status_code==403
        start.assert_not_called()
        response=client.post('/admin/models/download',data={'model_id':'opus-mt-en-fr','token':token,'confirm_network':'yes'},follow_redirects=False)
        assert response.status_code==303 and response.headers['location']=='/admin'
        start.assert_called_once()
    assert client.get('/admin/models/download/status').status_code==200


def test_interrupted_download_resumes_the_same_revision(tmp_path):
    class Interrupted(Hub):
        def hf_hub_download(self,repo,name,**kwargs):
            if name=='model.safetensors':raise ConnectionError('interrupted')
            return super().hf_hub_download(repo,name,**kwargs)
    root=tmp_path/'models';status=tmp_path/'status.json'
    with pytest.raises(ConnectionError):download.download_model('opus-mt-en-fr',root,status,hub=Interrupted())
    assert not (root/'opus-mt-en-fr').exists()
    assert (root/'.downloads/opus-mt-en-fr/config.json').exists()
    resumed=Hub();download.download_model('opus-mt-en-fr',root,status,hub=resumed)
    assert resumed.calls[0][2]['revision']=='a'*40
    assert download.verify_existing(root/'opus-mt-en-fr','opus-mt-en-fr')


def test_cli_requires_explicit_network_authorization(monkeypatch,tmp_path):
    root=tmp_path/'models'
    monkeypatch.setattr(download.sys,'argv',['download','opus-mt-en-fr','--model-root',str(root)])
    with pytest.raises(SystemExit) as error:download.main()
    assert error.value.code==2 and not root.exists()

@pytest.mark.parametrize('license_name',['cc-by-nc-4.0',None])
def test_license_does_not_block_download_or_reuse(tmp_path,license_name):
    root=tmp_path/'models';status=tmp_path/'status.json';hub=Hub(license=license_name)
    download.download_model('opus-mt-en-fr',root,status,hub=hub)
    target=root/'opus-mt-en-fr'
    assert download.verify_existing(target,'opus-mt-en-fr')
    manifest=json.loads((target/'manifest.json').read_text())
    assert manifest['license']==(license_name or 'unknown')
    assert manifest['usage_policy']=='upstream'
    count=len(hub.calls)
    download.download_model('opus-mt-en-fr',root,status,hub=hub)
    assert len(hub.calls)==count



def test_pickle_main_uses_pinned_safetensors_variant_without_conversion(tmp_path):
    pinned = download.CATALOG['opus-mt-en-fr']['safetensors_revision']
    class ConvertedHub(Hub):
        def model_info(self, repo, **kwargs):
            self.weights = kwargs['revision'] == pinned
            result = super().model_info(repo, **kwargs)
            if self.weights: result.sha = pinned
            return result
    hub = ConvertedHub(weights=False)
    root = tmp_path/'models'; status = tmp_path/'status.json'
    download.download_model('opus-mt-en-fr', root, status, hub=hub)
    manifest = json.loads((root/'opus-mt-en-fr/manifest.json').read_text())
    assert manifest['revision'] == pinned
    assert download.verify_existing(root/'opus-mt-en-fr', 'opus-mt-en-fr')
    assert [c[2]['revision'] for c in hub.calls if c[0] == 'info'] == ['main', pinned]
    assert all(c[1] != 'pytorch_model.bin' and c[2]['revision'] == pinned for c in hub.calls if c[0] == 'file')


def test_explicit_pickle_revision_never_switches_to_another_revision(tmp_path):
    hub = Hub(weights=False)
    with pytest.raises(ValueError, match='Safetensors'):
        download.download_model('opus-mt-en-fr', tmp_path/'models', tmp_path/'status.json', revision='a'*40, hub=hub)
    assert [c[2]['revision'] for c in hub.calls if c[0] == 'info'] == ['a'*40]
    assert not any(c[0] == 'file' for c in hub.calls)
