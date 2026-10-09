#!/usr/bin/env python3
"""Configure the optional BC-250 engine without putting credentials in shell history."""
import argparse
import getpass
import json
import os
import pwd
import tempfile
from pathlib import Path

def atomic(path, content, account):
    fd, temporary = tempfile.mkstemp(prefix=".remote-ai-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
        os.chmod(temporary, 0o600)
        os.chown(temporary, account.pw_uid, account.pw_gid)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="/var/lib/oneforall/doctrad")
    parser.add_argument("--user", default="ofa-doctrad")
    args = parser.parse_args()
    if os.geteuid() != 0: parser.error("Exécuter avec sudo")
    root = Path(args.data_root)
    if not root.is_dir(): parser.error("Dossier de données absent")
    account = pwd.getpwnam(args.user)
    key = getpass.getpass("Clé API Unsloth (saisie masquée) : ").strip()
    if not key or any(c.isspace() for c in key): parser.error("Clé invalide")
    key_file = root / "remote-ai.key"
    config = dict(enabled=True, default=False, base_url="http://192.168.6.22:8888/v1",
        model="unsloth/Qwen3.8-27B-GGUF", key_file=str(key_file))
    atomic(key_file, key + "\n", account)
    atomic(root / "remote-ai.json", json.dumps(config, indent=2) + "\n", account)
    print("BC-250 configuré. Sélectionnez-le dans DocTrad pour une traduction sur votre réseau privé.")

if __name__ == "__main__": main()
