#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || exit 1
VERSION=${1:?Version required}
[[ $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || exit 1
RELEASE=/opt/docutranslate/releases/$VERSION
[[ -x $RELEASE/.venv/bin/docutranslate ]] || { echo "Release not available" >&2; exit 1; }
[[ ${2:-} == --schema-compatible ]] || { echo "Confirm database compatibility first; otherwise restore backup." >&2; exit 1; }
systemctl stop docutranslate-web docutranslate-worker docutranslate-translation
ln -s "$RELEASE" /opt/docutranslate/current.next
mv -Tf /opt/docutranslate/current.next /opt/docutranslate/current
systemctl start docutranslate-translation docutranslate-worker docutranslate-web
curl --fail --retry 5 --retry-delay 2 --retry-connrefused http://127.0.0.1:8090/health
