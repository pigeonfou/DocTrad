"""Deployment inputs stay fixed even when the runner controls its environment."""
import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import os
import json
import sys

import pytest

spec=importlib.util.spec_from_file_location('doctrad_deploy_helper',
    Path(__file__).parents[1]/'scripts/oneforall-doctrad-deploy.py')
helper=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


@pytest.fixture(autouse=True)
def preserve_process_environment():
    with patch.dict(os.environ,dict(os.environ),clear=True):
        yield


def test_helper_accepts_only_exact_sha_or_fixed_diagnostics():
    assert helper.command('a'*40)[-4:] == ['--apps','doctrad','--sha','a'*40]
    assert helper.command('--status')[-3:] == ['status','--apps','doctrad']
    assert helper.command('--logs')[-3:] == ['logs','--apps','doctrad']
    for bad in ('main','A'*40,'a'*39,'--config','doctrad','a'*40+';id','../script.py'):
        with pytest.raises(ValueError):helper.command(bad)
    for mode in ('--automation-probe','--test-latest','--test-start','--test-status'):
        assert helper.command(mode) is None


def test_superseded_sha_never_reaches_privileged_update():
    info=SimpleNamespace(st_uid=0,st_mode=0o755)
    with patch.object(helper.os,'geteuid',return_value=0),patch.object(Path,'stat',return_value=info),patch.object(helper.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'b'*40+'\trefs/heads/main\n')) as run:
        with pytest.raises(ValueError,match='dépassée'):helper.main(['a'*40])
        assert run.call_count == 1
        assert run.call_args.args[0][1] == 'ls-remote'


def test_update_uses_fixed_manager_and_clean_environment():
    info=SimpleNamespace(st_uid=0,st_mode=0o755)
    responses=[subprocess.CompletedProcess([],0,'a'*40+'\trefs/heads/main\n'),subprocess.CompletedProcess([],7)]
    with patch.object(helper.os,'geteuid',return_value=0),patch.object(Path,'stat',return_value=info),patch.object(helper.subprocess,'run',side_effect=responses) as run:
        assert helper.main(['a'*40]) == 7
        assert run.call_args.args[0] == helper.command('a'*40)
        assert run.call_args.kwargs['env'] == helper.ENV
        assert run.call_args.kwargs['cwd'] == '/'


def test_manager_writable_by_runner_is_rejected():
    with patch.object(helper.os,'geteuid',return_value=0),patch.object(Path,'stat',return_value=SimpleNamespace(st_uid=0,st_mode=0o775)),patch.object(helper.subprocess,'run') as run:
        with pytest.raises(ValueError,match='root'):helper.main(['--status'])
        run.assert_not_called()


def test_successful_deployment_can_refresh_only_the_activated_root_owned_helper(tmp_path,monkeypatch):
    installed=tmp_path/'installed-helper';installed.write_text('old')
    current=tmp_path/('a'*40);(current/'scripts').mkdir(parents=True)
    source=current/'scripts/oneforall-doctrad-deploy.py';source.write_text('new trusted helper')
    monkeypatch.setattr(helper,'HELPER',installed)
    monkeypatch.setattr(helper,'CURRENT',current)
    monkeypatch.setattr(helper,'__file__',str(installed))
    original=Path.stat
    def stat(path,*args,**kwargs):
        result=original(path,*args,**kwargs)
        return SimpleNamespace(st_uid=0,st_mode=0o444) if path==source else result
    with patch.object(Path,'stat',stat):
        helper.refresh_helper('a'*40)
        assert installed.read_text()=='new trusted helper'
        with pytest.raises(ValueError,match='validée'):helper.refresh_helper('b'*40)


def test_automation_does_not_export_an_unrecognized_source_or_echo_credentials(tmp_path,monkeypatch):
    bundle=tmp_path/'automation/bundle';bundle.mkdir(parents=True)
    (bundle/'source.pdf').write_text('private document')
    summary={'source_sha256':'a'*64}
    fake_common=SimpleNamespace(app_env=lambda app:{'DATA_ROOT':str(tmp_path),'DATABASE_URL':'secret-db-password'},user=lambda app:'ofa-doctrad')
    monkeypatch.setattr(helper,'EXPORT',tmp_path/'published')
    with patch.dict(sys.modules,{'common':fake_common}),patch.object(helper.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(summary))) as run:
        with pytest.raises(ValueError,match='publics'):helper.automation('--test-latest')
        assert 'secret-db-password' not in ' '.join(run.call_args.args[0])
        assert run.call_args.kwargs['env']['DATABASE_URL']=='secret-db-password'
        assert not helper.EXPORT.exists()


def test_only_named_candidate_branch_head_can_reach_privileged_update():
    info=SimpleNamespace(st_uid=0,st_mode=0o755)
    heads='b'*40+'\trefs/heads/main\n'+'a'*40+'\trefs/heads/refonte-contexte-mise-en-page\n'
    responses=[subprocess.CompletedProcess([],0,heads),subprocess.CompletedProcess([],7)]
    with patch.object(helper.os,'geteuid',return_value=0),patch.object(Path,'stat',return_value=info),patch.object(helper.subprocess,'run',side_effect=responses) as run:
        assert helper.main(['a'*40]) == 7
        assert run.call_args.args[0] == helper.command('a'*40)


def test_unapproved_reference_is_rejected_even_with_matching_sha():
    info=SimpleNamespace(st_uid=0,st_mode=0o755)
    with patch.object(helper.os,'geteuid',return_value=0),patch.object(Path,'stat',return_value=info),patch.object(helper.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'a'*40+'\trefs/heads/untrusted\n')) as run:
        with pytest.raises(ValueError,match='dépassée'):helper.main(['a'*40])
        assert run.call_count==1
