import json

from app import model_download as download
from app.registry import Registry
from test_model_download import Hub
from test_web import signin


def test_big_opus_install_keeps_existing_default_and_verifies_weights(tmp_path):
    root = tmp_path/'models'; status = tmp_path/'status.json'
    download.download_model('opus-mt-en-fr', root, status, hub=Hub())
    download.download_model('opus-mt-tc-big-en-fr', root, status, hub=Hub(license='cc-by-4.0'))
    big = json.loads((root/'opus-mt-tc-big-en-fr/manifest.json').read_text())
    assert big['family'] == 'opus' and big['profile'] == 'balanced'
    assert not big['default'] and big['ram_mb'] == 2048
    assert download.verify_existing(root/'opus-mt-tc-big-en-fr', 'opus-mt-tc-big-en-fr')
    assert json.loads((root/'opus-mt-en-fr/manifest.json').read_text())['default']


def test_default_switch_requires_admin_csrf_and_verified_installed_model(client, tmp_path, monkeypatch):
    root = tmp_path/'models'; status = tmp_path/'status.json'
    for name in ('opus-mt-en-fr', 'opus-mt-tc-big-en-fr'):
        download.download_model(name, root, status, hub=Hub())
        path = root/name/'manifest.json'
        manifest = json.loads(path.read_text()); manifest['ram_mb'] = 0
        path.write_text(json.dumps(manifest))
    monkeypatch.setattr(Registry, '__init__', lambda self, *args, **kwargs: setattr(self, 'root', root))
    token = signin(client)
    body = {'model_id':'opus-mt-tc-big-en-fr', 'token':token}
    assert client.post('/admin/models/default', data=body).status_code == 403
    client.cookies.clear()
    token = signin(client, name='admin', admin=True); body['token'] = token
    assert client.post('/admin/models/default', data={**body, 'token':'invalid'}).status_code == 403
    assert client.post('/admin/models/default', data={**body, 'model_id':'missing'}).status_code == 400
    result = client.post('/admin/models/default', data=body, follow_redirects=False)
    assert result.status_code == 303 and result.headers['location'] == '/admin'
    assert Registry().choose()['id'] == 'opus-mt-tc-big-en-fr'
    assert not json.loads((root/'opus-mt-en-fr/manifest.json').read_text())['default']
    (root/'opus-mt-en-fr/model.safetensors').write_text('tampered')
    assert client.post('/admin/models/default', data={**body, 'model_id':'opus-mt-en-fr'}).status_code == 400
    assert Registry().choose()['id'] == 'opus-mt-tc-big-en-fr'
