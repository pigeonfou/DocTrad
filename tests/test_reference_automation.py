import hashlib
import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import select
from app import automation
from app.db import Session,User,Job,Memory


@pytest.fixture
def reference(tmp_path,monkeypatch):
    monkeypatch.setattr(automation,'DATA',tmp_path)
    (tmp_path/'uploads').mkdir();(tmp_path/'outputs').mkdir()
    public=b'%PDF-1.4 public reference test\n'
    digest=hashlib.sha256(public).hexdigest()
    monkeypatch.setattr(automation,'REFERENCES',{digest:'Public fixture'})
    with Session.begin() as db:
        owner=User(username='private-owner-name',password='unused',admin=False)
        db.add(owner);db.flush()
        identifier=str(uuid.uuid4())
        job=Job(id=identifier,owner_id=owner.id,filename='private-filename.pdf',suffix='.pdf',
            model_id='test-model',model_version='a'*40,status='done',progress=100)
        db.add(job)
    (tmp_path/'uploads'/(identifier+'.pdf')).write_bytes(public)
    output=tmp_path/'outputs'/identifier;output.mkdir()
    (output/'translation.pdf').write_bytes(b'%PDF-1.4 translated public fixture\n')
    return tmp_path,identifier,public


def test_only_recognized_reference_is_exported_and_no_account_metadata(reference):
    root,identifier,public=reference
    with Session.begin() as db:
        owner=db.scalar(select(User))
        private_id=str(uuid.uuid4())
        db.add(Job(id=private_id,owner_id=owner.id,filename='private.pdf',suffix='.pdf',
            model_id='test-model',model_version='a'*40,status='done'))
    (root/'uploads'/(private_id+'.pdf')).write_bytes(b'%PDF confidential customer document')
    result=automation.execute('latest')
    assert result['job_id']==identifier
    assert (root/'automation/bundle/source.pdf').read_bytes()==public
    manifest=(root/'automation/bundle/manifest.json').read_text()
    assert 'private-owner-name' not in manifest
    assert 'private-filename' not in manifest
    assert str(root) not in manifest


def test_start_uses_fresh_isolated_owner_and_reuses_an_active_test(reference,monkeypatch):
    root,identifier,public=reference
    monkeypatch.setattr('app.registry.Registry.choose',lambda self,requested:
        {'id':'test-model','revision':'b'*40})
    first=automation.execute('start')
    second=automation.execute('start')
    assert first['job_id']==second['job_id']!=identifier
    with Session() as db:
        job=db.get(Job,first['job_id']);owner=db.get(User,job.owner_id)
        assert owner.username==automation.QA_USER and not owner.admin
        assert not list(db.scalars(select(Memory).where(Memory.owner_id==owner.id)))
    assert (root/'uploads'/(first['job_id']+'.pdf')).read_bytes()==public


def test_failed_snapshot_never_retains_a_previous_successful_pdf(reference):
    root,identifier,_=reference
    automation.execute('latest')
    assert (root/'automation/bundle/translation.pdf').exists()
    with Session.begin() as db:db.get(Job,identifier).status='failed'
    automation.root().joinpath('active.json').write_text(json.dumps({'job_id':identifier}))
    result=automation.execute('status')
    assert result['status']=='failed'
    assert not (root/'automation/bundle/translation.pdf').exists()


def test_output_symlink_cannot_export_another_document(reference,tmp_path):
    root,identifier,_=reference
    output=root/'outputs'/identifier
    (output/'translation.pdf').unlink();output.rmdir()
    private=root/'private';private.mkdir();(private/'translation.pdf').write_text('private secret')
    output.symlink_to(private,target_is_directory=True)
    with pytest.raises(ValueError,match='hors'):automation.execute('latest')


def test_reference_input_symlink_is_rejected(reference):
    root,identifier,public=reference
    source=root/'uploads'/(identifier+'.pdf');source.unlink()
    other=root/'other.pdf';other.write_bytes(public);source.symlink_to(other)
    with pytest.raises(ValueError,match='Aucun'):automation.execute('latest')


def test_test_memory_is_never_deleted_to_force_a_fresh_translation(reference):
    with Session.begin() as db:
        owner=User(username=automation.QA_USER,password='unused',admin=False);db.add(owner);db.flush()
        db.add(Memory(owner_id=owner.id,source='approved correction',target='validated'))
    with pytest.raises(ValueError,match='isolé'):automation.execute('start')
    with Session() as db:assert db.scalar(select(Memory)).target=='validated'


def test_probe_exposes_capabilities_and_context_without_credentials(reference,monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr('app.remote_ai.settings',lambda:{'model':'TranslateGemma',
        'context_length':4096,'auto_load':True,'key_file':'/private/key',
        'base_url':'http://192.168.6.22:8888/v1','secret':'super-secret'})
    monkeypatch.setattr('httpx.get',lambda *args,**kwargs:SimpleNamespace(status_code=200))
    report=automation.execute('probe')
    assert report['runtime_reachable'] and report['reference_available']
    assert report['remote_translation']['context_length']==4096
    encoded=json.dumps(report)
    for private in ('/private/key','192.168.6.22','super-secret'):
        assert private not in encoded


def test_release_revision_is_independent_of_model_revision(monkeypatch):
    from app import automation
    sha='a'*40
    monkeypatch.setattr(automation,'__file__','/opt/oneforall/apps/doctrad/releases/'+sha+'/.venv/lib/python3/site-packages/app/automation.py')
    assert automation.release_revision()==sha
    monkeypatch.setattr(automation,'__file__','/workspace/app/automation.py')
    assert automation.release_revision() is None


def test_active_release_takes_priority_over_a_reused_venv(monkeypatch,tmp_path):
    from app import automation
    current=tmp_path/'current';active=tmp_path/('b'*40);active.mkdir()
    current.symlink_to(active,target_is_directory=True)
    monkeypatch.setattr(automation,'CURRENT_RELEASE',current)
    monkeypatch.setattr(automation,'__file__','/opt/oneforall/apps/doctrad/releases/'+('a'*40)+'/.venv/lib/python3/site-packages/app/automation.py')
    assert automation.release_revision()=='b'*40


def test_tsm_start_imports_only_hash_recognized_public_fixture(reference,monkeypatch,tmp_path):
    root,_,_=reference
    digest='9bc58a21ffa56f89dcec9e201f17d77b606135462a9c23b8e23fc274467b9e4b'
    fixture=Path(__file__).parent/'fixtures/tsm-waveform-reference.pdf'
    release=tmp_path/'release';(release/'tests/fixtures').mkdir(parents=True)
    (release/'tests/fixtures/tsm-waveform-reference.pdf').write_bytes(fixture.read_bytes())
    monkeypatch.setattr(automation,'CURRENT_RELEASE',release)
    monkeypatch.setitem(automation.REFERENCES,digest,'TrellisWare TSM waveform')
    monkeypatch.setattr('app.registry.Registry.choose',lambda self,requested:{'id':'test-model','revision':'b'*40})
    first=automation.execute('start-tsm')
    assert first['source_sha256']==digest
    assert automation.execute('start-tsm')['job_id']==first['job_id']


def test_tsm_start_rejects_altered_fixture_before_creating_a_job(reference,monkeypatch,tmp_path):
    release=tmp_path/'release';(release/'tests/fixtures').mkdir(parents=True)
    (release/'tests/fixtures/tsm-waveform-reference.pdf').write_bytes(b'private document')
    monkeypatch.setattr(automation,'CURRENT_RELEASE',release)
    with pytest.raises(ValueError,match='altérée'):automation.execute('start-tsm')
    with Session() as db:assert db.scalar(select(User).where(User.username==automation.QA_USER)) is None


def test_explicit_reference_does_not_reuse_an_active_job_for_another_document(reference,monkeypatch,tmp_path):
    digest='9bc58a21ffa56f89dcec9e201f17d77b606135462a9c23b8e23fc274467b9e4b'
    release=tmp_path/'release';(release/'tests/fixtures').mkdir(parents=True)
    (release/'tests/fixtures/tsm-waveform-reference.pdf').write_bytes((Path(__file__).parent/'fixtures/tsm-waveform-reference.pdf').read_bytes())
    monkeypatch.setattr(automation,'CURRENT_RELEASE',release)
    monkeypatch.setitem(automation.REFERENCES,digest,'TrellisWare TSM waveform')
    monkeypatch.setattr('app.registry.Registry.choose',lambda self,requested:{'id':'test-model','revision':'b'*40})
    automation.execute('start')
    with pytest.raises(ValueError,match='autre référence'):automation.execute('start-tsm')
