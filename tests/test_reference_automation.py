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
