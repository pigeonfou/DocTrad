"""Explicit model preparation process. Never sends documents or database settings."""
import argparse
import fcntl
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import threading
import uuid
from pathlib import Path, PurePosixPath

STATUS_LOCK = threading.RLock()

CATALOG = {
    'opus-mt-en-fr': {'safetensors_revision': 'c96fcd7f38a4c0d1ac9b61e255b47f3f7ff55e5e', 'name': 'OPUS anglais → français', 'repo': 'Helsinki-NLP/opus-mt-en-fr', 'family': 'opus', 'profile': 'light', 'license': 'apache-2.0', 'ram_mb': 1024, 'disk_gb': 1, 'description': 'Modèle léger pour commencer, sur CPU.'},
    'opus-mt-tc-big-en-fr': {'name': 'OPUS Big anglais → français', 'repo': 'Helsinki-NLP/opus-mt-tc-big-en-fr', 'family': 'opus', 'profile': 'balanced', 'license': 'cc-by-4.0', 'ram_mb': 2048, 'disk_gb': 2, 'description': 'Variante anglaise → française plus volumineuse, à comparer sur vos documents ; mémoire indicative 2 Go.'},
    'm2m100-418m': {'safetensors_revision': 'ae6407352f7f86e328c0f0678d466fc4246e78b3', 'name': 'M2M100 418M', 'repo': 'facebook/m2m100_418M', 'family': 'm2m100', 'profile': 'balanced', 'license': 'mit', 'ram_mb': 4096, 'disk_gb': 3, 'description': 'Modèle multilingue ; prévoir davantage de mémoire.'},
    'madlad400-3b': {'name': 'MADLAD400 3B', 'repo': 'google/madlad400-3b-mt', 'family': 'madlad', 'profile': 'quality', 'license': 'apache-2.0', 'ram_mb': 16000, 'disk_gb': 13, 'description': 'Modèle volumineux ; vérifier les ressources avant installation.'},
}


def write_status(path, **values):
    with STATUS_LOCK:
        _write_status(path, **values)


def _write_status(path, **values):
    path = Path(path)
    current = json.loads(path.read_text()) if path.exists() else {}
    current.update(values, updated_at=time.time())
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(current, ensure_ascii=False))
    tmp.chmod(0o600)
    os.replace(tmp, path)


def latest_status(state_root, model_root=None):
    files = sorted(Path(state_root).glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files: return None
    try:
        status=json.loads(files[0].read_text())
        if model_root and status.get('status') in ('queued','metadata','downloading','verifying'):
            try: fd=lock_download(model_root)
            except ValueError: return status
            else:
                os.close(fd)
                write_status(files[0],status='failed',message='Téléchargement interrompu. Relancez pour reprendre les fichiers locaux.')
                return json.loads(files[0].read_text())
        return status
    except (ValueError, OSError): return None


def lock_download(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    fd = os.open(root / '.download.lock', os.O_CREAT | os.O_RDWR, 0o600)
    try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise ValueError('Un téléchargement de modèle est déjà en cours.')
    return fd


def start_download(model_id, model_root, state_root):
    if model_id not in CATALOG: raise ValueError('Modèle inconnu')
    fd = lock_download(model_root)
    status = Path(state_root) / (uuid.uuid4().hex + '.json')
    status.parent.mkdir(parents=True, exist_ok=True)
    write_status(status, model_id=model_id, name=CATALOG[model_id]['name'], status='queued', message='Préparation du téléchargement', completed_bytes=0, total_bytes=0)
    try:
        # Only this child is online. No DB password, session secret, token or user file is inherited.
        env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': str(Path(model_root).resolve()),
               'PYTHONUNBUFFERED': '1', 'HF_HUB_DISABLE_TELEMETRY': '1', 'DO_NOT_TRACK': '1',
               'HF_HUB_OFFLINE': '0', 'TRANSFORMERS_OFFLINE': '1', 'HF_HUB_DISABLE_IMPLICIT_TOKEN': '1',
               'TMPDIR': str(Path(model_root).resolve()), 'HF_HOME': str(Path(model_root).resolve() / '.hub-cache')}
        subprocess.Popen([sys.executable, '-m', 'app.model_download', model_id, '--model-root', str(Path(model_root).resolve()),
                          '--status-file', str(status.resolve()), '--allow-network', '--lock-fd', str(fd)],
                         env=env, pass_fds=(fd,), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception:
        write_status(status, status='failed', message='Impossible de démarrer le processus de téléchargement.')
        raise
    finally: os.close(fd)
    return status.stem


def verify_existing(path, model_id):
    try:
        manifest = json.loads((path / 'manifest.json').read_text())
        spec=CATALOG[model_id]
        if manifest.get('id') != model_id or manifest.get('family') != spec['family']: return False
        if not re.fullmatch('[a-f0-9]{40}', manifest.get('revision','')): return False
        files=manifest.get('sha256',{})
        if 'config.json' not in files or not any(n.endswith('.safetensors') for n in files): return False
        for name,digest in files.items():
            file=(path/name).resolve()
            if not file.is_relative_to(path.resolve()) or not file.is_file(): return False
            with file.open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=digest:return False
        return True
    except (OSError,ValueError,TypeError):return False


def download_model(model_id, root, status_file, revision=None, hub=None):
    if model_id not in CATALOG: raise ValueError('Modèle inconnu')
    if revision and not re.fullmatch('[a-f0-9]{40}',revision):raise ValueError('Révision exacte SHA-40 requise')
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    spec=CATALOG[model_id];target=root/model_id
    if target.exists():
        if not verify_existing(target,model_id):raise ValueError('Modèle existant invalide : importez ou restaurez une version vérifiée, sans écrasement automatique.')
        item=json.loads((target/'manifest.json').read_text())
        if revision and item['revision']!=revision:raise ValueError('Une autre révision est déjà installée ; aucune donnée écrasée.')
        write_status(status_file,status='ready',message='Modèle déjà installé et vérifié.',revision=item['revision'])
        return
    stage=root/'.downloads'/model_id
    partial_revision=stage/'.revision'
    if not revision and partial_revision.exists():
        revision=partial_revision.read_text().strip()
        if not re.fullmatch('[a-f0-9]{40}',revision):raise ValueError('Révision du téléchargement interrompu invalide')
    if hub is None:
        # Import after choosing online mode. app.config is deliberately not imported here.
        os.environ['HF_HUB_OFFLINE']='0';os.environ['HF_HUB_DISABLE_TELEMETRY']='1';os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN']='1'
        import huggingface_hub as hub
    write_status(status_file,status='metadata',message='Vérification de la source')
    info=hub.model_info(spec['repo'],revision=revision or 'main',files_metadata=True,token=False)
    # Some upstream main branches publish only pickle weights. Select a known,
    # immutable Safetensors variant in the same repository for a fresh install.
    # Explicit requests and interrupted downloads never change revision.
    if (not revision and spec.get('safetensors_revision')
            and not any(file.rfilename.endswith('.safetensors') for file in info.siblings)):
        revision = spec['safetensors_revision']
        info = hub.model_info(spec['repo'], revision=revision, files_metadata=True, token=False)
    commit=info.sha
    if not re.fullmatch('[a-f0-9]{40}',commit or ''):raise ValueError('Révision de la source invalide')
    if revision and commit!=revision:raise ValueError('La révision reçue diffère de la demande')
    card=info.card_data or {}
    selected=[]
    upstream_hashes={}
    for file in info.siblings:
        name=file.rfilename;parts=PurePosixPath(name).parts
        if len(parts) != 1 or name.startswith('/') or '..' in parts or any(p.startswith('.') for p in parts):continue
        if any(fnmatch.fnmatch(name,p) for p in ('*.json','*.safetensors','*.spm','*.model','*.txt','README.md','LICENSE*')):
            selected.append((name,file.size or 0))
            lfs=getattr(file,"lfs",None)
            digest=getattr(lfs,"sha256",None) if lfs else None
            if digest:upstream_hashes[name]=digest
    if not any(n.endswith('.safetensors') for n,_ in selected):raise ValueError('Cette révision ne fournit pas de poids Safetensors ; aucune conversion non vérifiée ne sera exécutée.')
    if not any(n=='config.json' for n,_ in selected):raise ValueError('Configuration du modèle absente')
    total=sum(size for _,size in selected)
    required = max(int(total*1.1) + 256*1024**2, spec['disk_gb']*1024**3)
    free = shutil.disk_usage(root).free
    if free < required:
        raise ValueError(f'Espace disque insuffisant : {required/1024**3:.1f} Go nécessaires, {free/1024**3:.1f} Go disponibles pour les poids et la vérification.')
    stage=root/'.downloads'/model_id
    stage.mkdir(parents=True,exist_ok=True)
    if not stage.resolve().is_relative_to(root):raise ValueError('Dossier temporaire invalide')
    revision_file=stage/'.revision'
    if revision_file.exists() and revision_file.read_text()!=commit:
        raise ValueError('Téléchargement interrompu sur une autre révision ; relancez avec sa révision exacte.')
    revision_file.write_text(commit)
    done=0
    write_status(status_file,status='downloading',message='Téléchargement des poids et du tokenizer',revision=commit,total_bytes=total,completed_bytes=0)
    for number,(name,size) in enumerate(selected,1):
        write_status(status_file,message='Fichier '+str(number)+'/'+str(len(selected))+' : '+name)
        stop = threading.Event()
        def monitor():
            while not stop.wait(1):
                try:
                    partial=sum(p.stat().st_size for p in (stage/'.cache').rglob('*.incomplete'))
                    existing=(stage/name).stat().st_size if (stage/name).is_file() else 0
                    write_status(status_file,completed_bytes=done+min(size,existing+partial))
                except OSError: pass
        thread=threading.Thread(target=monitor,daemon=True);thread.start()
        try: hub.hf_hub_download(spec['repo'],name,revision=commit,local_dir=stage,token=False)
        finally: stop.set();thread.join()
        done+=size
        write_status(status_file,completed_bytes=done)
    write_status(status_file,status='verifying',message='Vérification SHA-256 des fichiers locaux')
    files={}
    for name,_ in selected:
        file=stage/name
        if not file.resolve().is_relative_to(stage.resolve()) or not file.is_file():raise ValueError('Fichier téléchargé invalide')
        with file.open('rb') as stream:files[name]=hashlib.file_digest(stream,'sha256').hexdigest()
        if name in upstream_hashes and files[name]!=upstream_hashes[name]:raise ValueError('Empreinte SHA-256 différente de la source pour '+name)
    manifest=dict(id=model_id,name=spec['name'],family=spec['family'],profile=spec['profile'],revision=commit,version=commit,
                  source='https://huggingface.co/'+spec['repo'],license=card.get('license') or 'unknown',usage_policy='upstream',
                  ram_mb=spec['ram_mb'],device='cpu',cpu_compatible=True,gpu_compatible=True,quantization='FP32',
                  enabled=True,default=not any(root.glob('*/manifest.json')),sha256=files,disk_bytes=sum((stage/n).stat().st_size for n in files))
    (stage/'manifest.json').write_text(json.dumps(manifest,indent=2))
    if not verify_existing(stage,model_id):raise ValueError('Vérification locale échouée')
    # Single-directory atomic publication: inference never sees half a download.
    os.rename(stage,target)
    write_status(status_file,status='ready',message='Modèle local installé. Les traductions restent hors ligne.',revision=commit,completed_bytes=total)


def main():
    parser=argparse.ArgumentParser(description='Télécharger explicitement un modèle local DocTrad')
    parser.add_argument('model_id',choices=CATALOG)
    parser.add_argument('--model-root',type=Path,required=True)
    parser.add_argument('--status-file',type=Path)
    parser.add_argument('--revision')
    parser.add_argument('--allow-network',action='store_true',help='Autoriser uniquement le téléchargement initial des poids publics')
    parser.add_argument('--lock-fd',type=int)
    args=parser.parse_args()
    if not args.allow_network:parser.error('--allow-network est requis pour autoriser le téléchargement')
    fd=args.lock_fd if args.lock_fd is not None else lock_download(args.model_root)
    status=args.status_file or args.model_root/'.downloads/status.json'
    status.parent.mkdir(parents=True,exist_ok=True)
    try:
        download_model(args.model_id,args.model_root,status,args.revision)
        print(json.loads(status.read_text())['message'])
    except Exception as exc:
        message=str(exc) if isinstance(exc,ValueError) else 'Téléchargement interrompu ('+type(exc).__name__+'). Vérifiez la connexion ou relancez pour reprendre.'
        write_status(status,model_id=args.model_id,status='failed',message=message)
        print(message,file=sys.stderr)
        raise SystemExit(1)
    finally:os.close(fd)

if __name__=='__main__':main()


