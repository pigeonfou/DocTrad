#!/usr/bin/env python3
"""Explicit online preparation only; never imported by production services."""
import argparse
import hashlib
import json
import os
from pathlib import Path

CANDIDATES = {
    "opus-mt-en-fr": ("Helsinki-NLP/opus-mt-en-fr","opus","light","apache-2.0",1024),
    "m2m100-418m": ("facebook/m2m100_418M","m2m100","balanced","mit",4096),
    "madlad400-3b": ("google/madlad400-3b-mt","madlad","quality","apache-2.0",16000),
}

def main():
    parser = argparse.ArgumentParser(description="Download weights explicitly on the connected preparation machine")
    parser.add_argument("model_id", choices=CANDIDATES)
    parser.add_argument("--revision",required=True,help="Exact 40-character upstream commit SHA")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    import re
    if not re.fullmatch(r'[0-9a-f]{40}',args.revision): parser.error("Exact commit SHA required")
    for key in ("HF_HUB_OFFLINE","TRANSFORMERS_OFFLINE"):os.environ.pop(key,None)
    from huggingface_hub import snapshot_download, model_info
    source,family,profile,expected_license,ram=CANDIDATES[args.model_id]
    info=model_info(source,revision=args.revision)
    license_name=info.card_data.get('license') if info.card_data else None
    if license_name != expected_license: raise SystemExit("Upstream license differs or is unknown: manual review required")
    target=args.output/args.model_id
    if target.exists():raise SystemExit("Output already exists; do not overwrite an installed revision")
    print(f"Explicit download: {source}@{args.revision} -> {target}")
    snapshot_download(source,revision=args.revision,local_dir=target,allow_patterns=['*.json','*.safetensors','pytorch_model.bin','*.spm','*.model','*.txt','README.md','LICENSE*'])
    if not any(target.glob('*.safetensors')):
        # Only the explicitly selected official checkpoint is opened; PyTorch
        # weights_only=True prevents arbitrary pickle code execution. Production
        # loads only the converted Safetensors artifact.
        from transformers import AutoModelForSeq2SeqLM
        local_model=AutoModelForSeq2SeqLM.from_pretrained(target,local_files_only=True,trust_remote_code=False,use_safetensors=False,weights_only=True)
        local_model.save_pretrained(target,safe_serialization=True)
        (target/'pytorch_model.bin').unlink(missing_ok=True)
        del local_model
    files={}
    for p in sorted(target.rglob('*')):
        if p.is_file() and '.cache' not in p.parts:
            with p.open('rb') as f:files[str(p.relative_to(target))]=hashlib.file_digest(f,'sha256').hexdigest()
    if not any(n.endswith('.safetensors') for n in files):raise SystemExit("Safetensors weights unavailable; conversion must be reviewed separately")
    manifest=dict(id=args.model_id,name=source,family=family,profile=profile,revision=args.revision,version=args.revision,source='https://huggingface.co/'+source,license=license_name,usage_policy='permissive',ram_mb=ram,device='cpu',cpu_compatible=True,gpu_compatible=True,quantization='FP32',enabled=True,default=False,sha256=files,disk_bytes=sum((target/n).stat().st_size for n in files))
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('Preparation complete; transfer the entire model directory to the offline server.')

if __name__=='__main__':main()
