#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ $EUID -eq 0 ]] || exit 1
SOURCE=${1:?Path to unpacked release source required}
VERSION=${2:?New version required}
[[ $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || exit 1
RELEASE=/opt/docutranslate/releases/$VERSION
[[ ! -e $RELEASE ]] || { echo "Release already exists" >&2; exit 1; }
"$(dirname "$0")/backup.sh" "/var/backups/docutranslate/$(date -u +%Y%m%dT%H%M%SZ)" --include-documents
OLD=$(readlink -f /opt/docutranslate/current)
mkdir "$RELEASE"
tar -C "$SOURCE" --exclude=.git --exclude=.venv --exclude=models --exclude=data --exclude=offline -cf - . | tar -C "$RELEASE" -xf -
install -d -m 700 /var/tmp/docutranslate-offline-install
export TMPDIR=/var/tmp/docutranslate-offline-install
python3 -m venv "$RELEASE/.venv"
"$RELEASE/.venv/bin/pip" install --no-index --find-links="${3:?Wheelhouse required}" -r "$RELEASE/requirements.lock"
"$RELEASE/.venv/bin/pip" install --no-deps --no-build-isolation "$RELEASE"
"$RELEASE/.venv/bin/pip" check
"$RELEASE/.venv/bin/python" -m compileall -q "$RELEASE/app"
chmod -R g+rX,o-rwx "$RELEASE"
chown -R root:docutranslate "$RELEASE"
systemctl stop docutranslate-web docutranslate-worker docutranslate-translation
# Version 0.1 schema has no destructive migration. Future releases need explicit
# compatibility metadata and versioned migrations before this command is reused.
set -a
source /etc/docutranslate/docutranslate.env
set +a
runuser -u docutranslate -- "$RELEASE/.venv/bin/docutranslate" migrate
ln -s "$RELEASE" /opt/docutranslate/current.next
mv -Tf /opt/docutranslate/current.next /opt/docutranslate/current
systemctl daemon-reload
systemctl start docutranslate-translation docutranslate-worker docutranslate-web
if ! curl --fail --retry 5 --retry-delay 2 --retry-connrefused http://127.0.0.1:8090/health; then
  systemctl stop docutranslate-web docutranslate-worker docutranslate-translation
  ln -s "$OLD" /opt/docutranslate/current.next
  mv -Tf /opt/docutranslate/current.next /opt/docutranslate/current
  systemctl start docutranslate-translation docutranslate-worker docutranslate-web
  exit 1
fi
