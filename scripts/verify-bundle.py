#!/usr/bin/env python3
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
manifest=json.loads((root/'MANIFEST.json').read_text())
for name,digest in manifest['sha256'].items():
    target=(root/name).resolve()
    if not target.is_relative_to(root) or not target.is_file():raise SystemExit('Invalid bundle path')
    with target.open('rb') as stream: actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if actual!=digest:raise SystemExit('Checksum failed: '+name)
print('Bundle checksums OK (integrity only; authenticate the manifest separately)')
