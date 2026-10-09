#!/usr/bin/env python3
"""Configure the optional BC-250 engine without putting credentials in shell history."""
import argparse
import getpass
import json
import os
import pwd
import tempfile
import sys
import urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.remote_ai import translation_payload, clean_translation

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
    parser.add_argument("--translategemma", action="store_true",
        help="Détecter et tester TranslateGemma 12B Q4_K_M déjà chargé dans Unsloth")
    parser.add_argument("--reuse-key", action="store_true", help="Conserver la clé existante")
    args = parser.parse_args()
    if os.geteuid() != 0: parser.error("Exécuter avec sudo")
    root = Path(args.data_root)
    if not root.is_dir(): parser.error("Dossier de données absent")
    account = pwd.getpwnam(args.user)
    config_file = root / "remote-ai.json"
    previous = json.loads(config_file.read_text()) if config_file.exists() else {}
    key_file = root / "remote-ai.key"
    old_key = Path(previous.get("key_file", str(key_file)))
    if args.reuse_key:
        if not old_key.is_file() or old_key.stat().st_mode & 0o077:
            parser.error("Clé existante absente ou permissions non privées")
        key = old_key.read_text().strip()
    else:
        key = getpass.getpass("Clé API Unsloth (saisie masquée) : ").strip()
    if not key or len(key) > 512 or any(c.isspace() for c in key): parser.error("Clé invalide")
    config = dict(previous, enabled=True, base_url="http://192.168.6.22:8888/v1",
        model="mradermacher/translategemma-12b-it-GGUF", key_file=str(key_file))
    config.setdefault("default", False)
    if args.translategemma:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs): return None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        def request(path, payload=None):
            req = urllib.request.Request(config["base_url"] + path,
                data=None if payload is None else json.dumps(payload).encode(),
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            with opener.open(req, timeout=180) as response:
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024: raise ValueError("Réponse trop grande")
                return json.loads(raw)
        try:
            models = request("/models")["data"]
            candidates = [m for m in models if m.get("loaded") is True
                and "translategemma" in m.get("id", "").lower()
                and "12b" in m["id"].lower()
                and (str(m.get("quant", "")).upper() == "Q4_K_M" or ".q4_k_m.gguf" in m["id"].lower())]
            if len(candidates) != 1:
                parser.error("Charger uniquement TranslateGemma 12B Q4_K_M dans Unsloth, puis relancer")
            config["model"] = candidates[0]["id"]
            source = "Disconnect the power supply before servicing."
            choice = request("/chat/completions", translation_payload(config["model"], source))["choices"][0]
            result = clean_translation(choice["message"]["content"])
            if choice.get("finish_reason") != "stop" or not isinstance(result, str) or not result.strip() or result.strip() == source:
                parser.error("Test de traduction invalide ; configuration conservée")
        except Exception:
            parser.error("Test Unsloth échoué ; configuration conservée. Vérifier le modèle et son template TranslateGemma")
        # A probe-specific language check, not a general language detector.
        normalized = result.lower()
        if "alimentation" not in normalized or not any(word in normalized for word in ("débranch", "déconnect", "coupez", "couper")):
            parser.error("Le test ne produit pas la traduction française attendue ; configuration conservée")
        config["default"] = True
        print("Test de traduction :", result.strip())
    atomic(key_file, key + "\n", account)
    atomic(root / "remote-ai.json", json.dumps(config, indent=2) + "\n", account)
    print("BC-250 configuré. Sélectionnez-le dans DocTrad pour une traduction sur votre réseau privé.")

if __name__ == "__main__": main()
