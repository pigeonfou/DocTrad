#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ $EUID -eq 0 ]] || exit 1
DEST=${1:?Specify new backup directory}
[[ ! -e $DEST ]] || { echo "Destination exists" >&2; exit 1; }
mkdir -p "$DEST"
# Quiesce writes for a coherent DB/files snapshot. Always restart on exit.
trap 'systemctl start docutranslate-translation docutranslate-worker docutranslate-web' EXIT
systemctl stop docutranslate-web docutranslate-worker docutranslate-translation
runuser -u postgres -- pg_dump -Fc docutranslate > "$DEST/database.dump"
cp -a /etc/docutranslate "$DEST/config"
printf '%s\n' "$(readlink -f /opt/docutranslate/current)" > "$DEST/release.txt"
if [[ ${2:-} == --include-documents ]]; then tar -C /var/lib -cf "$DEST/documents.tar" docutranslate; fi
if [[ ${3:-} == --include-models ]]; then tar -C /opt/docutranslate -cf "$DEST/models.tar" models; fi
(cd "$DEST" && sha256sum database.dump release.txt > SHA256SUMS)
