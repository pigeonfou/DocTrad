#!/usr/bin/python3 -I
"""Root-owned, fixed DocTrad deployment entry point for the Actions runner."""
import os
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

MANAGER = Path('/opt/oneforall/manager/oneforall')
HELPER = Path('/usr/local/sbin/oneforall-doctrad-deploy')
EXPORT = Path('/var/lib/oneforall/doctrad-automation')
CURRENT = Path('/opt/oneforall/apps/doctrad/current')
DEPLOY_REFS = ('refs/heads/main', 'refs/heads/refonte-contexte-mise-en-page')
PUBLIC_HASHES = {'cc6a5ca2bd9fad41fce19136afd7aaca3315a783a52348a4984bf11d8b8e41f6',
                '9bc58a21ffa56f89dcec9e201f17d77b606135462a9c23b8e23fc274467b9e4b'}
AUTOMATION = {'--automation-probe':'probe','--test-latest':'latest',
              '--test-start':'start','--test-status':'status'}
ENV = {'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':'/root','LANG':'C.UTF-8',
       'PYTHONNOUSERSITE':'1'}


def command(argument):
    if argument in AUTOMATION:
        return None
    if argument in ('--status','--logs'):
        return ['/usr/bin/python3',str(MANAGER/'cli.py'),
                'status' if argument == '--status' else 'logs','--apps','doctrad']
    if not re.fullmatch(r'[a-f0-9]{40}',argument):
        raise ValueError('Usage: oneforall-doctrad-deploy SHA | --status | --logs')
    return ['/usr/bin/python3',str(MANAGER/'cli.py'),'update','--apps','doctrad','--sha',argument]


def candidate_command(argument):
    command(argument)
    if argument.startswith('--'):
        raise ValueError('Le déploiement de branche exige un SHA.')
    # The ref is a fixed trusted constant, never caller input. APPS is shared
    # by cli/deploy only in this child process; on-disk configuration is unchanged.
    source = ("import sys; sys.path.insert(0, '/opt/oneforall/manager/oneforall'); "
              "from common import APPS; APPS['doctrad']['ref']='refonte-contexte-mise-en-page'; "
              "import cli; cli.main(sys.argv[1:])")
    return ['/usr/bin/python3','-I','-c',source,'update','--apps','doctrad','--sha',argument]


def automation(argument):
    sys.path.insert(0,str(MANAGER))
    from common import app_env,user
    values=app_env('doctrad')
    current=CURRENT
    result=subprocess.run(['/usr/sbin/runuser','-u',user('doctrad'),'--',
        str(current/'.venv/bin/python'),'-I','-m','app.automation',AUTOMATION[argument]],
        env={**ENV,**values},cwd='/',capture_output=True,text=True,timeout=120,check=False)
    if result.returncode:
        # Never echo an environment-bearing command or application traceback.
        raise ValueError('Opération de référence échouée ; vérifier le probe et les services.')
    summary=json.loads(result.stdout)
    data=Path(values['DATA_ROOT'])
    bundle=data/'automation/bundle'
    if not bundle.resolve().is_relative_to(data.resolve()):
        raise ValueError('Bundle hors du répertoire applicatif.')
    if AUTOMATION[argument]!='probe':
        source=bundle/'source.pdf'
        if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() not in PUBLIC_HASHES:
            raise ValueError('Seuls les documents de référence publics reconnus peuvent être récupérés.')
        if summary.get('source_sha256') not in PUBLIC_HASHES:
            raise ValueError('Manifest de référence invalide.')
    EXPORT.mkdir(mode=0o755,parents=True,exist_ok=True)
    info=EXPORT.stat()
    if info.st_uid!=0 or info.st_mode & 0o022 or EXPORT.is_symlink():
        raise ValueError('Répertoire d’export non protégé.')
    for name in ('manifest.json','source.pdf','translation.pdf','segments.json','diagnostics.json','layout-report.json'):
        target=EXPORT/name
        if target.is_symlink():raise ValueError('Lien inattendu dans les artefacts.')
        target.unlink(missing_ok=True)
        source=bundle/name
        if source.is_file():
            if source.is_symlink() or source.resolve().parent!=bundle.resolve():
                raise ValueError('Artefact hors du bundle de référence.')
            shutil.copyfile(source,target);target.chmod(0o644)
    print(json.dumps(summary,ensure_ascii=False))
    return 0


def refresh_helper(sha):
    # Once activated, subsequent successful deployments keep this fixed helper
    # current. Its source must be in the exact root-owned activated release.
    if Path(__file__).resolve()!=HELPER:return
    current=CURRENT.resolve(strict=True)
    source=current/'scripts/oneforall-doctrad-deploy.py'
    info=source.stat()
    if current.name!=sha or info.st_uid!=0 or info.st_mode & 0o022:
        raise ValueError('Source du lanceur non validée.')
    temporary=HELPER.with_suffix('.new')
    if temporary.is_symlink():raise ValueError('Lien inattendu dans le lanceur.')
    shutil.copyfile(source,temporary);temporary.chmod(0o755);os.replace(temporary,HELPER)


def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        raise ValueError('Un seul SHA ou mode de diagnostic est accepté.')
    invocation=command(args[0])
    if os.geteuid() != 0:
        raise ValueError('Exécuter via sudo.')
    # Neither the manager nor its import directory may be runner-writable.
    for path in (MANAGER,MANAGER/'cli.py',MANAGER.parent,MANAGER.parent.parent):
        info=path.stat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Gestionnaire OneForAll non détenu exclusivement par root.')
    # Remove caller-controlled variables before manager imports or runuser.
    os.environ.clear();os.environ.update(ENV)
    if args[0] in AUTOMATION:
        return automation(args[0])
    if not args[0].startswith('--'):
        head=subprocess.run(['/usr/bin/git','ls-remote','--exit-code',
            'https://github.com/pigeonfou/DocTrad.git',*DEPLOY_REFS],
            env=ENV,cwd='/',capture_output=True,text=True,check=True,timeout=60)
        heads = {parts[1]: parts[0] for line in head.stdout.splitlines()
                 if len(parts := line.split()) == 2 and parts[1] in DEPLOY_REFS}
        if args[0] not in heads.values():
            raise ValueError('Version dépassée : déployer uniquement le SHA actuel d’une branche autorisée après validation CI.')
        if heads.get('refs/heads/refonte-contexte-mise-en-page') == args[0] and heads.get('refs/heads/main') != args[0]:
            invocation=candidate_command(args[0])
    result=subprocess.run(invocation,env=ENV,cwd='/',check=False).returncode
    if result==0 and not args[0].startswith('--'):refresh_helper(args[0])
    return result


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print(str(exc),file=sys.stderr)
        raise SystemExit(1)
