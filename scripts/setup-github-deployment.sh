#!/usr/bin/env bash
# Run once after native installation and registering the read-only deploy SSH key.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo' >&2; exit 1; }
ROOT=$(cd "$(dirname "$0")/.." && pwd)
[[ -f /etc/docutranslate/docutranslate.env ]] || { echo 'Install DocTrad first' >&2; exit 1; }
[[ -f /root/.ssh/doctrad-deploy-ed25519 ]] || { echo 'Create/register the read-only SSH deploy key first' >&2; exit 1; }
id docutranslate-runner &>/dev/null || useradd --create-home --shell /bin/bash docutranslate-runner
install -d -m 750 -o root -g docutranslate /opt/docutranslate/models /opt/docutranslate/releases
install -d -m 700 /var/lib/docutranslate-deploy
if [[ ! -d /var/lib/docutranslate-deploy/repository.git ]]; then
  git -c core.sshCommand='ssh -p 443 -o HostName=ssh.github.com -i /root/.ssh/doctrad-deploy-ed25519 -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes' clone --bare git@github.com:pigeonfou/DocTrad.git /var/lib/docutranslate-deploy/repository.git
fi
install -m 755 -o root -g root "$ROOT/packaging/deploy/docutranslate-deploy" /usr/local/sbin/docutranslate-deploy
install -m 755 -o root -g root "$ROOT/packaging/deploy/docutranslate-model-install" /usr/local/sbin/docutranslate-model-install
SUDO_RULE=$(mktemp)
trap 'rm -f "$SUDO_RULE"' EXIT
printf '%s\n' 'docutranslate-runner ALL=(root) NOPASSWD: /usr/local/sbin/docutranslate-deploy, /usr/local/sbin/docutranslate-model-install' > "$SUDO_RULE"
visudo -cf "$SUDO_RULE"
install -m 440 -o root -g root "$SUDO_RULE" /etc/sudoers.d/docutranslate-deploy
printf '%s\n' 'Wrapper installed. Register the runner with label doctrad-deploy; see docs/GITHUB_CLOUDFLARE_SETUP.md.'
