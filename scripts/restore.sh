#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || exit 1
BACKUP=${1:?Specify backup directory}
[[ ${2:-} == --replace-existing ]] || { echo "Restore replaces database/configuration. Use --replace-existing after reviewing backup." >&2; exit 1; }
(cd "$BACKUP" && sha256sum -c SHA256SUMS)
systemctl stop docutranslate-web docutranslate-worker docutranslate-translation
runuser -u postgres -- pg_restore --clean --if-exists --exit-on-error -d docutranslate < "$BACKUP/database.dump"
cp -a "$BACKUP/config/." /etc/docutranslate/
if [[ -e $BACKUP/documents.tar ]]; then tar -C /var/lib -xf "$BACKUP/documents.tar"; fi
if [[ -e $BACKUP/models.tar ]]; then tar -C /opt/docutranslate -xf "$BACKUP/models.tar"; fi
systemctl start docutranslate-translation docutranslate-worker docutranslate-web
curl --fail http://127.0.0.1:8090/health
