#!/usr/bin/env bash
set -euo pipefail
# Run on Ubuntu 24.04 amd64 with Python 3.12, apt-rdepends and dpkg-dev installed.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEST=${1:?New bundle destination required}
MODEL_SOURCE=${2:?Verified model root required}
[[ ! -e $DEST ]] || { echo "Destination exists" >&2; exit 1; }
command -v apt-rdepends >/dev/null
command -v dpkg-scanpackages >/dev/null
mkdir -p "$DEST"/{app,wheels,apt,models}
tar -C "$ROOT" --exclude=.git --exclude=.venv --exclude=models --exclude=data --exclude=offline -cf - . | tar -C "$DEST/app" -xf -
python3 -m pip download --only-binary=:all: -r "$ROOT/requirements.lock" -d "$DEST/wheels"
cp -a "$MODEL_SOURCE/." "$DEST/models/"
# Recursive dependencies, including packages already installed on builder.
apt-rdepends python3-venv postgresql nginx openssl fonts-dejavu-core tesseract-ocr tesseract-ocr-eng poppler-utils curl 2>/dev/null | awk '/^[a-zA-Z0-9][^ ]*$/ {print}' | sort -u > "$DEST/apt/packages.txt"
while IFS= read -r package; do
  # Virtual dependencies must be resolved explicitly; stop instead of ignoring.
  (cd "$DEST/apt" && apt-get download "$package")
done < "$DEST/apt/packages.txt"
(cd "$DEST/apt" && dpkg-scanpackages . /dev/null > Packages)
python3 - "$DEST" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
files={}
for path in sorted(root.rglob('*')):
    if path.is_file():
        with path.open('rb') as f:files[str(path.relative_to(root))]=hashlib.file_digest(f,'sha256').hexdigest()
(root/'MANIFEST.json').write_text(json.dumps({'platform':'Ubuntu 24.04 amd64 Python 3.12','sha256':files},indent=2))
PY
printf '%s\n' 'Authenticate MANIFEST.json, transfer the directory, then sudo app/install.sh --offline /absolute/bundle/path' > "$DEST/README-OFFLINE.txt"
