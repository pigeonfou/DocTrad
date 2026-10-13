#!/usr/bin/env bash
# Install from a trusted release, once, as root; no registration token is stored.
set -euo pipefail
[[ $(id -u) == 0 ]] || { echo 'Exécuter avec sudo.' >&2; exit 1; }
runner_user=${1:-oneforall-runner}
if [[ $# == 0 ]]; then
  mapfile -t runner_units < <(systemctl list-unit-files --type=service --no-pager --no-legend | awk '$1 ~ /^actions\.runner\.pigeonfou-DocTrad\./ {print $1}')
  if [[ ${#runner_units[@]} == 1 ]]; then
    runner_user=$(systemctl show "${runner_units[0]}" --property=User --value)
  elif [[ ${#runner_units[@]} -gt 1 ]]; then
    echo 'Plusieurs runners DocTrad : fournir explicitement le compte du runner à préparer.' >&2
    exit 1
  fi
fi
[[ $# -le 1 && "$runner_user" =~ ^[a-z_][a-z0-9_-]*$ && "$runner_user" != root && "$runner_user" != ofa-doctrad ]] || {
  echo 'Usage: setup-oneforall-runner.sh [compte-du-runner]' >&2; exit 1;
}
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
test -f /opt/oneforall/manager/oneforall/cli.py
command -v git >/dev/null
command -v visudo >/dev/null
if ! id "$runner_user" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$runner_user"
fi
install -o root -g root -m 0755 "$script_dir/oneforall-doctrad-deploy.py" /usr/local/sbin/oneforall-doctrad-deploy
sudoers_tmp=$(mktemp)
trap 'rm -f "$sudoers_tmp"' EXIT
printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/oneforall-doctrad-deploy\n' "$runner_user" > "$sudoers_tmp"
chmod 0440 "$sudoers_tmp"
visudo -cf "$sudoers_tmp"
install -o root -g root -m 0440 "$sudoers_tmp" /etc/sudoers.d/oneforall-doctrad-runner
sudo -u "$runner_user" sudo -n /usr/local/sbin/oneforall-doctrad-deploy --status
sudo -u "$runner_user" sudo -n /usr/local/sbin/oneforall-doctrad-deploy --automation-probe
echo "Compte préparé : $runner_user ; label GitHub requis : doctrad-deploy."
echo 'Runner à enregistrer dans pigeonfou/DocTrad, sous ce compte, si absent.'
systemctl list-unit-files --type=service --no-pager | grep -E 'actions\.runner\.' || true
