"""Deployment inputs stay fixed even when the runner controls its environment."""
import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

spec=importlib.util.spec_from_file_location('doctrad_deploy_helper',
    Path(__file__).parents[1]/'scripts/oneforall-doctrad-deploy.py')
helper=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def test_helper_accepts_only_exact_sha_or_fixed_diagnostics():
    assert helper.command('a'*40)[-4:] == ['--apps','doctrad','--sha','a'*40]
    assert helper.command('--status')[-3:] == ['status','--apps','doctrad']
    assert helper.command('--logs')[-3:] == ['logs','--apps','doctrad']
    for bad in ('main','A'*40,'a'*39,'--config','doctrad','a'*40+';id','../script.py'):
        with pytest.raises(ValueError):helper.command(bad)


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
