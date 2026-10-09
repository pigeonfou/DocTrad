#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ $EUID -eq 0 ]] || { echo "Run with sudo" >&2; exit 1; }
source /etc/os-release
ALLOW_26=0
if [[ ${1:-} == --experimental-ubuntu26 ]]; then
  ALLOW_26=1
  shift
fi
[[ $ID == ubuntu && $(uname -m) == x86_64 ]] || { echo "Ubuntu x86_64 required; detected $ID $VERSION_ID $(uname -m)" >&2; exit 1; }
case $VERSION_ID in
  24.04) ;;
  26.04)
    (( ALLOW_26 )) || { echo "Ubuntu 26.04 detected. Support is experimental: use --experimental-ubuntu26. Validated target: Ubuntu 24.04." >&2; exit 1; }
    echo "Experimental Ubuntu 26.04 installation: dependencies and services need validation on this server." >&2
    ;;
  *) echo "Unsupported Ubuntu version: $VERSION_ID (validated: 24.04; experimental: 26.04)" >&2; exit 1 ;;
esac
ROOT=$(cd "$(dirname "$0")" && pwd)
VERSION=$(python3 -c 'import tomllib; print(tomllib.load(open("'"$ROOT"'/pyproject.toml","rb"))["project"]["version"])')
RELEASE=/opt/docutranslate/releases/$VERSION
[[ ! -e /etc/docutranslate/docutranslate.env ]] || { echo "Already installed; use the update procedure" >&2; exit 1; }
if [[ ${1:-} == --offline ]]; then
  BUNDLE=${2:?Bundle root required}
  python3 "$ROOT/scripts/verify-bundle.py" "$BUNDLE"
  LOCAL_LIST=$(mktemp)
  trap 'rm -f "$LOCAL_LIST"' EXIT
  printf 'deb [trusted=yes] file:%s/apt ./\n' "$BUNDLE" > "$LOCAL_LIST"
  apt-get -o Dir::Etc::sourcelist="$LOCAL_LIST" -o Dir::Etc::sourceparts=- -o APT::Get::List-Cleanup=0 update
  apt-get -o Dir::Etc::sourcelist="$LOCAL_LIST" -o Dir::Etc::sourceparts=- install -y python3-venv postgresql nginx openssl fonts-dejavu-core tesseract-ocr tesseract-ocr-eng poppler-utils curl
else
  apt-get update
  apt-get install -y python3-venv postgresql nginx openssl fonts-dejavu-core tesseract-ocr tesseract-ocr-eng poppler-utils curl
fi
id docutranslate &>/dev/null || useradd --system --home /var/lib/docutranslate --shell /usr/sbin/nologin docutranslate
install -d -m 750 -o root -g docutranslate /opt/docutranslate /opt/docutranslate/models /etc/docutranslate
install -d -m 750 -o docutranslate -g docutranslate /var/lib/docutranslate /var/lib/docutranslate/{uploads,outputs,temp} /var/cache/docutranslate /opt/docutranslate/models/translation
install -d -m 750 /etc/docutranslate/tls
install -d -m 750 -o root -g docutranslate /opt/docutranslate/releases
[[ ! -e $RELEASE ]] || { echo "Release exists" >&2; exit 1; }
mkdir "$RELEASE"
tar -C "$ROOT" --exclude=.git --exclude=.venv --exclude=.env --exclude=data --exclude=models --exclude=offline -cf - . | tar -C "$RELEASE" -xf -
install -d -m 700 /var/tmp/docutranslate-install
export TMPDIR=/var/tmp/docutranslate-install
python3 -m venv "$RELEASE/.venv"
if [[ ${1:-} == --offline ]]; then
  "$RELEASE/.venv/bin/pip" install --no-index --find-links="$BUNDLE/wheels" -r "$RELEASE/requirements.lock"
else
  "$RELEASE/.venv/bin/pip" install -r "$RELEASE/requirements.lock"
fi
if [[ ${1:-} == --offline ]]; then
  cp -a "$BUNDLE/models/." /opt/docutranslate/models/translation/
  chown -R docutranslate:docutranslate /opt/docutranslate/models/translation
fi
# Install local package without build isolation or dependency downloads.
"$RELEASE/.venv/bin/pip" install --no-deps --no-build-isolation "$RELEASE"
# The service must traverse/read the root-owned release and its venv.
chmod -R g+rX,o-rwx "$RELEASE"
chown -R root:docutranslate "$RELEASE"
DB_PASSWORD=$(openssl rand -hex 32)
SESSION_SECRET=$(openssl rand -hex 32)
RUNTIME_SECRET=$(openssl rand -hex 32)
systemctl enable --now postgresql
runuser -u postgres -- psql -v ON_ERROR_STOP=1 -c "CREATE USER docutranslate PASSWORD '$DB_PASSWORD';"
runuser -u postgres -- createdb -O docutranslate docutranslate
cat > /etc/docutranslate/docutranslate.env <<CONFIG
DATABASE_URL=postgresql+psycopg://docutranslate:$DB_PASSWORD@127.0.0.1/docutranslate
SESSION_SECRET=$SESSION_SECRET
RUNTIME_SECRET=$RUNTIME_SECRET
COOKIE_SECURE=true
OFFLINE_MODE=true
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
HF_DATASETS_OFFLINE=1
HF_HUB_DISABLE_TELEMETRY=1
DATA_ROOT=/var/lib/docutranslate
MODEL_ROOT=/opt/docutranslate/models/translation
UPLOAD_MAX_SIZE=104857600
CONFIG
chmod 640 /etc/docutranslate/docutranslate.env
chown root:docutranslate /etc/docutranslate /etc/docutranslate/docutranslate.env
install -d -m 755 /opt/docutranslate/bin
install -m 755 "$ROOT/bin/docutranslate-tool" /opt/docutranslate/bin/docutranslate-tool
for command in diagnose docutranslate-health docutranslate-model benchmark-models; do
  ln -s docutranslate-tool "/opt/docutranslate/bin/$command"
done
ln -s "$RELEASE" /opt/docutranslate/current
set -a
source /etc/docutranslate/docutranslate.env
set +a
runuser -u docutranslate -- "$RELEASE/.venv/bin/docutranslate" migrate
read -rp "Administrator username: " ADMIN_USER
runuser -u docutranslate -- "$RELEASE/.venv/bin/docutranslate" create-user "$ADMIN_USER" --admin
# Test-only certificate; replace with your internal PKI certificate before production.
openssl req -x509 -newkey rsa:3072 -nodes -days 365 -subj '/CN=doctrad.local' -addext 'subjectAltName=DNS:doctrad.local' -keyout /etc/docutranslate/tls/server.key -out /etc/docutranslate/tls/server.crt
install -m 644 "$ROOT"/packaging/systemd/*.service /etc/systemd/system/
install -m 644 "$ROOT/packaging/nginx/docutranslate.conf" /etc/nginx/sites-available/docutranslate
ln -s /etc/nginx/sites-available/docutranslate /etc/nginx/sites-enabled/docutranslate
nginx -t
systemctl daemon-reload
systemctl enable --now docutranslate-translation docutranslate-worker docutranslate-web
systemctl reload nginx
curl --fail --retry 5 --retry-delay 2 --retry-connrefused http://127.0.0.1:8090/health
printf '\nInstalled. Transfer a verified model before translation. See docs/INSTALL_UBUNTU_24_04.md\n'
