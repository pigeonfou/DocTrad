import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from .config import MODELS


def _signature(path):
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


@lru_cache(maxsize=256)
def _file_checksum(path, signature):
    # Keep only digests in memory; changed/replaced files get a new cache key.
    if _signature(path) != signature:
        raise OSError("Model file changed before verification")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if _signature(path) != signature:
        raise OSError("Model file changed during verification")
    return digest


class Registry:
    def __init__(self, root=MODELS): self.root = Path(root)
    def list(self):
        result = []
        for path in sorted(self.root.glob("*/manifest.json")):
            try:
                item = json.loads(path.read_text())
                item["path"] = str(path.parent)
                item["status"] = "ready" if self.verify(item) else "invalid"
                result.append(item)
            except (ValueError, OSError, KeyError): continue
        from .remote_ai import manifest
        try:
            remote = manifest()
            if remote: result.append(remote)
        except (ValueError, OSError, KeyError): pass
        return result
    def verify(self, item):
        path = Path(item["path"]).resolve()
        if not path.is_relative_to(self.root.resolve()): return False
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", item.get("id", "")): return False
        if not re.fullmatch(r"[0-9a-f]{40}", item.get("revision", "")): return False
        if item.get("family") not in {"opus", "m2m100", "madlad"}: return False
        files = item.get("sha256", {})
        if not files or "config.json" not in files: return False
        if not any(name.endswith((".safetensors", ".bin")) for name in files): return False
        for name, digest in files.items():
            f = (path / name).resolve()
            if not f.is_relative_to(path) or not f.is_file(): return False
            actual = _file_checksum(f, _signature(f))
            if actual != digest: return False
        return True
    def choose(self, requested="auto"):
        candidates = [m for m in self.list() if m["status"] == "ready" and m.get("enabled", True)]
        if requested not in {"auto", "light", "balanced", "quality"}:
            candidates = [m for m in candidates if m["id"] == requested]
        elif requested != "auto":
            candidates = [m for m in candidates if m.get("profile") == requested]
        # Resource ceiling applies only when the manifest declares a requirement.
        try:
            memory = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
            available = int(memory["MemAvailable"].split()[0]) / 1024
            candidates = [m for m in candidates if m.get("ram_mb", 0) < available * 0.85]
        except (OSError, KeyError, ValueError): pass
        if not candidates: raise ValueError("Aucun modèle local vérifié et compatible disponible pour ce choix.")
        # Quality recommendations require actual benchmark results, never parameter count.
        candidates.sort(key=lambda m: (not (m.get("remote") and m.get("default", False)), not m.get("default", False), -m.get("benchmark", {}).get("technical_score", 0), m.get("ram_mb", 999999)))
        return candidates[0]

