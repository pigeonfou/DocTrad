"""Bounded, content-free per-job diagnostic history."""
import json
import os
import re
import uuid
from datetime import datetime, timezone
from .config import DATA

class InferenceError(ValueError):
    def __init__(self, code, diagnostic):
        messages = {
            'remote_control_auth': 'Unsloth refuse le contrôle des modèles : vérifier les droits de la clé API.',
            'remote_model_load': 'Chargement du modèle distant échoué : vérifier Unsloth et la mémoire de la BC-250.',
            'remote_model_settings': 'Unsloth ne confirme pas TranslateGemma Q4_K_M avec le contexte demandé.',
        }
        super().__init__(messages.get(code, "IA distante indisponible ou réponse incomplète : " + code))
        self.diagnostic = safe_details(dict(diagnostic, code=code))

def safe_details(value):
    result = {}
    for key in ("segment", "characters", "response_characters", "http_status", "seconds", "attempt"):
        item = value.get(key)
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            result[key] = item
    for key in ("code", "exception", "finish_reason", "transport_reason"):
        item = value.get(key)
        if isinstance(item, str) and re.fullmatch(r"[A-Za-z0-9_]{1,64}", item):
            result[key] = item
    known = {"<|file_separator|>", "<|im_start|>", "<|im_end|>", "<end_of_turn>", "<eos>"}
    if isinstance(value.get("markers"), list):
        result["markers"] = [m if isinstance(m, str) and m in known else "unknown" for m in value["markers"][:20]]
    return result

def path_for(job_id):
    return DATA / "diagnostics" / (str(uuid.UUID(str(job_id))) + ".jsonl")

def record(job_id, event, **details):
    try:
        path = path_for(job_id)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        entry = dict(time=datetime.now(timezone.utc).isoformat(),
                     event=event if event in ("started", "segment_started", "segment_done", "failed", "done", "remote_model_loading", "remote_model_ready") else "unknown",
                     **safe_details(details))
        # Keep a rolling window rather than accumulating unlimited logs.
        lines = path.read_text().splitlines()[-199:] if path.exists() else []
        import tempfile
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".diagnostic-")
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write("\n".join(lines + [json.dumps(entry, ensure_ascii=False)]) + "\n")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
    except (OSError, ValueError):
        # A diagnostic write must not stop a translation (e.g. disk full).
        pass

def history(job_id):
    try:
        return [json.loads(line) for line in path_for(job_id).read_text().splitlines()[-200:]]
    except (OSError, ValueError):
        return []
