import argparse
import getpass
import json
import os
import platform
import shutil
import time
from pathlib import Path
from sqlalchemy import select, text
from .config import DATA, MODELS, RUNTIME_URL, RUNTIME_SECRET
from .db import Base, engine, Session, User, Job, Benchmark
from .auth import password_hash
from .registry import Registry

CORPUS = [
    "Power supply voltage: 12 VDC.",
    "Connect J3 to the STM32F407 control board.",
    "Maximum torque is 4.5 Nm.",
    "Use the M4x20 screws.",
    "Communication uses CAN and RS-485.",
]

def diagnostic():
    system = {"OS":platform.platform(),"Python":platform.python_version(),"CPU":platform.processor() or platform.machine(),"cores":os.cpu_count(),"offline":True,"model_root":str(MODELS)}
    try:
        memory = dict(line.split(":",1) for line in Path("/proc/meminfo").read_text().splitlines())
        system["RAM"] = memory["MemTotal"].strip(); system["RAM available"] = memory["MemAvailable"].strip()
    except OSError: pass
    system["storage_free_GB"] = round(shutil.disk_usage(DATA if DATA.exists() else ".").free / 1024**3, 1)
    try:
        with Session() as db:
            db.execute(text("SELECT 1")); system["database"] = "OK"
            system["queue"] = len(list(db.scalars(select(Job).where(Job.status == "queued"))))
    except Exception: system["database"] = "UNAVAILABLE"
    heartbeat = DATA / "worker-heartbeat"
    system["worker"] = "OK" if heartbeat.exists() and time.time() - heartbeat.stat().st_mtime < 600 else "UNAVAILABLE"
    system["models_ready"] = len([m for m in Registry().list() if m["status"] == "ready" and m.get("enabled",True)])
    system["OCR"] = "Tesseract local" if shutil.which("tesseract") else "UNAVAILABLE"
    try:
        import httpx
        system["translation_runtime"] = httpx.get(RUNTIME_URL + "/health", timeout=3, trust_env=False).json()
    except Exception: system["translation_runtime"] = "UNAVAILABLE"
    try:
        import torch
        system["GPU"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU only"
    except ImportError: system["GPU"] = "PyTorch absent"
    return system

def model_action(action, model_id):
    registry = Registry()
    models = registry.list()
    if action == "list": print(json.dumps(models, indent=2, ensure_ascii=False)); return
    item = next((m for m in models if m["id"] == model_id), None)
    if not item:
        # Keep filesystem errors visible instead of silently treating them as absent models.
        target = MODELS / str(model_id)
        details = []
        for path in [MODELS.parent, MODELS, target, target / "manifest.json"]:
            try:
                stat = path.stat()
                details.append(f"{path}: uid={stat.st_uid} gid={stat.st_gid} mode={oct(stat.st_mode & 0o777)}")
            except OSError as exc:
                details.append(f"{path}: {type(exc).__name__}")
        try:
            manifest = json.loads((target / "manifest.json").read_text())
            manifest["path"] = str(target)
            registry.verify(manifest)
        except (OSError, ValueError, KeyError) as exc:
            details.append(f"Manifest verification: {type(exc).__name__}: {exc}")
        raise SystemExit("Modèle non installé\n" + "\n".join(details))
    if action == "verify":
        if not registry.verify(item): raise SystemExit("Intégrité invalide")
        print("OK"); return
    if action == "info": print(json.dumps(item, indent=2)); return
    if action == "benchmark":
        import httpx
        from .quality import protect, restore, check
        import resource
        started = time.monotonic(); results = []; technical = 0; peak_rss = None
        for source in CORPUS:
            protected, mapping = protect(source)
            try:
                response = httpx.post(RUNTIME_URL + "/translate", headers={"X-Runtime-Secret":RUNTIME_SECRET}, json={"model_id":item["id"],"revision":item["revision"],"texts":[protected]}, timeout=300, trust_env=False)
                if response.status_code != 200: raise SystemExit(f"Runtime indisponible (HTTP {response.status_code}) : {response.text}")
                result = response.json(); peak_rss = result.get("runtime_peak_rss_kb")
                target = restore(result["texts"][0], mapping)
                ok = not check(source, target)
            except ValueError: target = "PROTECTED DATA FAILURE"; ok = False
            technical += int(ok); results.append({"source":source,"target":target,"technical_ok":ok})
        score = {"seconds":time.monotonic()-started,"runtime_peak_rss_kb":peak_rss,"technical_score":technical/len(CORPUS),"quality_score":None,"human_review_required":True,"hardware":platform.platform(),"segments":results}
        with Session.begin() as db: db.add(Benchmark(model_id=item["id"],revision=item["revision"],results=score))
        print(json.dumps(score, indent=2, ensure_ascii=False))
        item["benchmark"] = score
    elif action == "enable":
        if not registry.verify(item): raise SystemExit("Modèle invalide")
        item["enabled"] = True
    elif action == "disable": item["enabled"] = False
    elif action == "set-default":
        if not registry.verify(item) or not item.get("enabled",True): raise SystemExit("Modèle indisponible")
        for other in models:
            if other["id"] != item["id"]:
                other["default"] = False; save_manifest(other)
        item["default"] = True
    save_manifest(item)
    if action == "benchmark" and item["benchmark"]["technical_score"] < 1.0:
        raise SystemExit("Benchmark technique échoué : données protégées altérées ; modèle à corriger.")

def save_manifest(item):
    target = Path(item["path"]) / "manifest.json"
    content = {k:v for k,v in item.items() if k not in {"path","status"}}
    temp = target.with_suffix(".tmp"); temp.write_text(json.dumps(content, indent=2)); os.replace(temp, target)

def main():
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("migrate")
    user = subs.add_parser("create-user"); user.add_argument("username"); user.add_argument("--admin",action="store_true")
    subs.add_parser("diagnose"); subs.add_parser("health"); subs.add_parser("benchmark-all")
    recover = subs.add_parser("recover"); recover.add_argument("job_id")
    model = subs.add_parser("model"); model.add_argument("action",choices=["list","info","verify","enable","disable","set-default","benchmark"]); model.add_argument("model_id",nargs="?")
    args = parser.parse_args()
    if args.command == "migrate": Base.metadata.create_all(engine)
    elif args.command == "create-user":
        password = getpass.getpass("Mot de passe (12 caractères minimum) : ")
        if password != getpass.getpass("Confirmer : "): raise SystemExit("Les mots de passe diffèrent")
        with Session.begin() as db: db.add(User(username=args.username,password=password_hash(password),admin=args.admin))
    elif args.command in {"diagnose","health"}:
        report = diagnostic(); print(json.dumps(report, indent=2, ensure_ascii=False))
        if args.command == "health" and (report["database"] != "OK" or report["worker"] != "OK" or report["translation_runtime"] == "UNAVAILABLE" or not report["models_ready"] or report["OCR"] == "UNAVAILABLE"): raise SystemExit(1)
    elif args.command == "recover":
        # Operator explicitly confirms old worker is stopped before invoking.
        from .db import Segment
        from sqlalchemy import delete
        with Session.begin() as db:
            job = db.get(Job,args.job_id)
            if not job or job.status not in {"running","failed","exporting"}: raise SystemExit("État incompatible")
            db.execute(delete(Segment).where(Segment.job_id==job.id)); job.status="queued"; job.progress=0; job.error=""
    elif args.command == "model": model_action(args.action,args.model_id)
    elif args.command == "benchmark-all":
        models = [m for m in Registry().list() if m["status"] == "ready" and m.get("enabled", True)]
        if not models: raise SystemExit("Aucun modèle local vérifié à benchmarker")
        for model in models: model_action("benchmark", model["id"])

if __name__ == "__main__": main()
