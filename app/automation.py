"""Bounded reference-document operations for the authorized server runner.

Only the two public, byte-identified reference PDFs may leave the application.
No account credentials, configuration files or arbitrary uploads are exported.
"""
import argparse
import fcntl
import hashlib
import json
import os
import secrets
import shutil
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import select
from .config import DATA, RUNTIME_URL
from .db import Session, Job, Segment, User, Memory

REFERENCES = {
    'cc6a5ca2bd9fad41fce19136afd7aaca3315a783a52348a4984bf11d8b8e41f6': 'L3Harris AN/PRC-167',
    '9bc58a21ffa56f89dcec9e201f17d77b606135462a9c23b8e23fc274467b9e4b': 'TrellisWare TSM waveform',
}
FILES = ('manifest.json','source.pdf','translation.pdf','segments.json','diagnostics.json','layout-report.json')
QA_USER = '__doctrad_public_reference_qa__'
CURRENT_RELEASE = Path('/opt/oneforall/apps/doctrad/current')


def root():
    directory=DATA/'automation'
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    return directory


def source_for(job):
    identifier=str(uuid.UUID(job.id))
    if identifier != job.id or job.suffix != '.pdf':
        return None
    path=DATA/'uploads'/(identifier+'.pdf')
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 30*1024**2:
        return None
    if not path.resolve().is_relative_to((DATA/'uploads').resolve()):
        return None
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    checksum=digest.hexdigest()
    return (path,checksum) if checksum in REFERENCES else None


def latest(db,completed=False):
    query=select(Job).where(Job.suffix=='.pdf')
    if completed: query=query.where(Job.status=='done')
    for job in db.scalars(query.order_by(Job.created.desc()).limit(500)):
        source=source_for(job)
        if source:
            return job,source
    raise ValueError('Aucun document de référence public reconnu dans les 500 derniers PDF.')


def write_json(path,value):
    temporary=path.with_suffix(path.suffix+'.new')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    os.replace(temporary,path)


def release_revision():
    """Report the installed release, independently of remote model settings."""
    import re
    current = CURRENT_RELEASE.resolve().name
    if CURRENT_RELEASE.is_symlink() and re.fullmatch(r'[a-f0-9]{40}', current):
        return current
    return next((path.name for path in Path(__file__).resolve().parents
                 if re.fullmatch(r'[a-f0-9]{40}',path.name)), None)

def snapshot(db,job,source):
    path,digest=source
    from .diagnostics import history
    rows=list(db.scalars(select(Segment).where(Segment.job_id==job.id).order_by(Segment.position)))
    summary=dict(job_id=job.id,status=job.status,progress=job.progress,model_id=job.model_id,
        model_revision=job.model_version,application_revision=release_revision(),reference=REFERENCES[digest],source_sha256=digest,
        segments=len(rows),warning_count=sum(len(row.warnings or []) for row in rows),
        elapsed_seconds=job.elapsed,human_review_required=True)
    # Publish a complete bundle atomically; failed/unfinished jobs cannot leave
    # a previous successful PDF behind for an artifact consumer to mistake.
    stage=Path(tempfile.mkdtemp(prefix='.bundle-',dir=root()))
    try:
        shutil.copyfile(path,stage/'source.pdf')
        write_json(stage/'segments.json',[dict(position=row.position,source=row.source,
            target=row.target,warnings=row.warnings,layout=row.metadata_json) for row in rows])
        write_json(stage/'diagnostics.json',history(job.id))
        outputs=(DATA/'outputs'/job.id).resolve()
        if not outputs.is_relative_to((DATA/'outputs').resolve()):
            raise ValueError('Répertoire de résultat hors de l’application.')
        for name in ('translation.pdf','layout-report.json'):
            item=outputs/name
            if job.status=='done' and item.is_file() and not item.is_symlink() and item.resolve().parent==outputs:
                shutil.copyfile(item,stage/name)
        if job.status=='done' and not (stage/'translation.pdf').is_file():
            summary['status']='missing_output'
        summary['files']=[name for name in FILES if (stage/name).is_file() or name=='manifest.json']
        write_json(stage/'manifest.json',summary)
        target=root()/'bundle'
        if target.exists():shutil.rmtree(target)
        os.replace(stage,target)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return summary


def start(db):
    source_job,source=latest(db)
    owner=db.scalar(select(User).where(User.username==QA_USER))
    if owner is not None:
        if owner.admin or db.scalar(select(Memory.id).where(Memory.owner_id==owner.id).limit(1)):
            raise ValueError('Compte de test non isolé ; aucune mémoire utilisateur ne sera supprimée.')
        active=db.scalar(select(Job).where(Job.owner_id==owner.id,Job.status.in_(
            ['queued','running','export_queued','exporting'])).order_by(Job.created.desc()).limit(1))
        if active:
            active_source=source_for(active)
            if not active_source:raise ValueError('Test actif non reconnu.')
            write_json(root()/'active.json',{'job_id':active.id})
            return snapshot(db,active,active_source)
    else:
        from .auth import password_hash
        # No usable interactive credential is emitted or retained externally.
        owner=User(username=QA_USER,password=password_hash(secrets.token_urlsafe(48)),admin=False)
        db.add(owner);db.flush()
    from .registry import Registry
    model=Registry().choose('auto')
    identifier=str(uuid.uuid4())
    destination=DATA/'uploads'/(identifier+'.pdf')
    shutil.copyfile(source[0],destination)
    job=Job(id=identifier,owner_id=owner.id,filename='Public reference automation.pdf',
        suffix='.pdf',model_id=model['id'],model_version=model['revision'])
    try:
        db.add(job);db.commit()
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    write_json(root()/'active.json',{'job_id':identifier})
    return snapshot(db,job,(destination,source[1]))


def execute(action):
    if action not in ('probe','latest','start','status'):
        raise ValueError('Opération de référence inconnue.')
    with (root()/'operations.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with Session() as db:
            if action=='probe':
                reference=None
                try:
                    _,source=latest(db);reference=REFERENCES[source[1]]
                except ValueError:pass
                runtime=False
                try:
                    import httpx
                    runtime=httpx.get(RUNTIME_URL+'/health',timeout=5,trust_env=False).status_code==200
                except Exception:pass
                result=dict(automation_version=1,operations=['probe','latest','start','status'],
                    reference_available=reference is not None,reference=reference,runtime_reachable=runtime,
                    export_policy='known_public_reference_hashes_only')
                try:
                    from .remote_ai import settings
                    remote=settings()
                    result['remote_translation']={'enabled':bool(remote)}
                    if remote:
                        result['remote_translation'].update(model=remote['model'],
                            context_length=remote['context_length'],auto_load=remote['auto_load'])
                except (ValueError,OSError,KeyError):
                    result['remote_translation']={'configuration_valid':False}
                target=root()/'bundle'
                if target.exists():shutil.rmtree(target)
                target.mkdir();write_json(target/'manifest.json',result)
                return result
            if action=='latest':
                job,source=latest(db,completed=True)
                return snapshot(db,job,source)
            if action=='start':return start(db)
            state=json.loads((root()/'active.json').read_text())
            job=db.get(Job,str(uuid.UUID(state['job_id'])))
            source=source_for(job) if job else None
            if not source:raise ValueError('Aucun test autonome reconnu à suivre.')
            return snapshot(db,job,source)


def main():
    parser=argparse.ArgumentParser(description='Public reference automation only')
    parser.add_argument('action',choices=['probe','latest','start','status'])
    args=parser.parse_args()
    try:
        print(json.dumps(execute(args.action),ensure_ascii=False))
    except Exception as error:
        # No DSN, credentials or confidential paths in Actions logs.
        print(json.dumps({'error':'reference_operation_failed','exception':type(error).__name__}))
        raise SystemExit(1)


if __name__=='__main__':main()
