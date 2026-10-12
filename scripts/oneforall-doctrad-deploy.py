#!/usr/bin/python3 -I
"""Root-owned, fixed DocTrad deployment entry point for the Actions runner."""
import os
import re
import subprocess
import sys
from pathlib import Path

MANAGER = Path('/opt/oneforall/manager/oneforall')
ENV = {'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':'/root','LANG':'C.UTF-8',
       'PYTHONNOUSERSITE':'1'}


def command(argument):
    if argument in ('--status','--logs'):
        return ['/usr/bin/python3',str(MANAGER/'cli.py'),
                'status' if argument == '--status' else 'logs','--apps','doctrad']
    if not re.fullmatch(r'[a-f0-9]{40}',argument):
        raise ValueError('Usage: oneforall-doctrad-deploy SHA | --status | --logs')
    return ['/usr/bin/python3',str(MANAGER/'cli.py'),'update','--apps','doctrad','--sha',argument]


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
    if not args[0].startswith('--'):
        head=subprocess.run(['/usr/bin/git','ls-remote','--exit-code',
            'https://github.com/pigeonfou/DocTrad.git','refs/heads/main'],
            env=ENV,cwd='/',capture_output=True,text=True,check=True,timeout=60)
        if head.stdout.split()[0] != args[0]:
            raise ValueError('Version dépassée : déployer uniquement le SHA actuel de main après validation CI.')
    return subprocess.run(invocation,env=ENV,cwd='/',check=False).returncode


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print(str(exc),file=sys.stderr)
        raise SystemExit(1)
