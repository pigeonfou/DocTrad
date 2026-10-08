import secrets
import os
import uuid
import time
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import select, text
from .config import DATA, MODELS, SECRET, MAX_UPLOAD, RUNTIME_URL
from .db import Session, Job, User, Segment, Correction, Memory, Glossary
from .auth import csrf, authenticated, verify, rate_limit
from .registry import Registry
from .documents import validate
from .quality import check
from .translation_audit import audit_translation

@asynccontextmanager
async def lifespan(app):
    if len(SECRET) < 32: raise RuntimeError("SESSION_SECRET doit contenir au moins 32 caractères")
    for directory in ("uploads", "outputs", "temp"): (DATA / directory).mkdir(parents=True, exist_ok=True)
    yield

BASE_PATH = os.environ.get("DOCTRAD_BASE_PATH", "").rstrip("/")
if BASE_PATH and (not BASE_PATH.startswith("/") or any(c not in "/abcdefghijklmnopqrstuvwxyz0123456789_-" for c in BASE_PATH)):
    raise ValueError("DOCTRAD_BASE_PATH invalide")

app = FastAPI(root_path=BASE_PATH, title="DocTrad", docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET or "unconfigured", session_cookie="doctrad_session", path=BASE_PATH + "/", https_only=os.environ.get("COOKIE_SECURE", "true") == "true", same_site="strict", max_age=28800)
root = Path(__file__).parent
app.mount("/static", StaticFiles(directory=root / "static"), name="static")
templates = Jinja2Templates(directory=root / "templates")
templates.env.globals["base_path"] = BASE_PATH

@app.middleware("http")
async def headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
    response.headers["Cache-Control"] = "no-store"
    return response

@app.exception_handler(HTTPException)
async def error(request, exc):
    if exc.status_code == 401: return RedirectResponse(BASE_PATH + "/login", status_code=303)
    return templates.TemplateResponse(request=request, name="error.html", context={"message":exc.detail}, status_code=exc.status_code)

@app.exception_handler(Exception)
async def unexpected(request, exc):
    return templates.TemplateResponse(request=request, name="error.html", context={"message":"Service indisponible ; consultez le diagnostic local."}, status_code=503)

@app.get("/health")
def health():
    try:
        with Session() as db: db.execute(text("SELECT 1"))
        storage = DATA.exists() and os.access(DATA, os.W_OK)
        heartbeat = DATA / "worker-heartbeat"
        worker = heartbeat.exists() and time.time() - heartbeat.stat().st_mtime < 600
        try:
            import httpx
            runtime = httpx.get(RUNTIME_URL + "/health", timeout=2, trust_env=False).json()
        except Exception: runtime = {"available":False,"loaded":False}
        models = [m for m in Registry().list() if m["status"] == "ready" and m.get("enabled",True)]
        return JSONResponse({"web":True,"database":True,"storage":storage,"offline":True,"worker":worker,"translation_runtime":runtime,"local_models":len(models),"ocr":bool(__import__('shutil').which("tesseract")),"ready":storage and worker and bool(models) and runtime.get("available",True)}, status_code=200 if storage else 503)
    except Exception: return JSONResponse({"web":True,"database":False,"offline":True}, status_code=503)

@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    request.session.setdefault("csrf", secrets.token_urlsafe(32))
    return templates.TemplateResponse(request=request, name="login.html", context={"csrf":request.session["csrf"]})

@app.post("/login")
def login_post(request: Request, username: str = Form(), password: str = Form(), token: str = Form()):
    csrf(request, token)
    rate_limit(request.client.host if request.client else "unknown")
    with Session() as db:
        user = db.scalar(select(User).where(User.username == username))
        if not user or not verify(user.password, password): raise HTTPException(403, "Identifiants invalides")
        request.session.clear(); request.session.update(uid=user.id, csrf=secrets.token_urlsafe(32))
    return RedirectResponse(BASE_PATH + "/", status_code=303)

@app.post("/logout")
def logout(request: Request, token: str = Form()):
    csrf(request, token); request.session.clear()
    return RedirectResponse(BASE_PATH + "/login", status_code=303)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    with Session() as db:
        user = authenticated(request, db)
        jobs = list(db.scalars(select(Job).where(Job.owner_id == user.id).order_by(Job.created.desc()).limit(100)))
        models = [m for m in Registry().list() if m["status"] == "ready" and m.get("enabled", True)]
        return templates.TemplateResponse(request=request, name="home.html", context={"user":user,"jobs":jobs,"models":models,"csrf":request.session["csrf"]})

@app.post("/jobs")
async def upload(request: Request, document: UploadFile = File(), model: str = Form("auto"), token: str = Form()):
    csrf(request, token)
    with Session() as db:
        user = authenticated(request, db)
        try: selected = Registry().choose(model)
        except ValueError as exc: raise HTTPException(400, str(exc))
        suffix = Path(document.filename or "").suffix.lower()
        job_id = str(uuid.uuid4()); path = DATA / "uploads" / (job_id + suffix)
        # Filename is display-only; never use it for storage.
        total = 0
        try:
            with path.open("xb") as f:
                while chunk := await document.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_UPLOAD: raise ValueError("Document trop volumineux")
                    f.write(chunk)
            validate(path, suffix)
            job = Job(id=job_id, owner_id=user.id, filename=Path(document.filename or "document").name[:255], suffix=suffix, model_id=selected["id"], model_version=selected["revision"])
            db.add(job); db.commit()
        except (ValueError, OSError, __import__('zipfile').BadZipFile) as exc:
            path.unlink(missing_ok=True); raise HTTPException(400, "Document refusé : " + type(exc).__name__) from exc
        except Exception:
            path.unlink(missing_ok=True); raise
    return RedirectResponse(BASE_PATH + "/jobs/" + job_id, status_code=303)

def owned(request, db, job_id):
    user = authenticated(request, db)
    job = db.get(Job, job_id)
    if not job or job.owner_id != user.id: raise HTTPException(404, "Document introuvable")
    return job

@app.get("/jobs/{job_id}")
def detail(request: Request, job_id: str):
    with Session() as db:
        job = owned(request, db, job_id)
        segments = list(db.scalars(select(Segment).where(Segment.job_id == job_id).order_by(Segment.position)))
        return templates.TemplateResponse(request=request, name="job.html", context={"job":job,"segments":segments,"csrf":request.session["csrf"]})

@app.get("/jobs/{job_id}/status")
def status(request: Request, job_id: str):
    with Session() as db:
        job = owned(request, db, job_id)
        return {"status":job.status,"progress":job.progress}

@app.get("/jobs/{job_id}/download/{format}")
def download(request: Request, job_id: str, format: str):
    with Session() as db:
        job = owned(request, db, job_id)
        if job.status != "done" or format not in {"pdf", "docx", "pptx"}: raise HTTPException(404)
        file = DATA / "outputs" / job.id / ("translation." + format)
        if not file.is_file(): raise HTTPException(404)
        return FileResponse(file, filename="traduction." + format)

@app.post("/jobs/{job_id}/segments/{segment_id}")
def correct(request: Request, job_id: str, segment_id: int, target: str = Form(), token: str = Form()):
    csrf(request, token)
    if len(target) > 20000: raise HTTPException(400)
    with Session.begin() as db:
        job = owned(request, db, job_id)
        if job.status != "done": raise HTTPException(409, "Document non terminé")
        seg = db.get(Segment, segment_id)
        if not seg or seg.job_id != job.id: raise HTTPException(404)
        db.add(Correction(segment_id=seg.id, user_id=job.owner_id, previous=seg.target, target=target))
        seg.target = target; seg.warnings = list(dict.fromkeys(check(seg.source, target) + audit_translation(seg.source, target)))
        if seg.metadata_json.get("confidence", 1) < 0.85: seg.warnings.append("OCR incertain : vérification nécessaire")
        if not seg.warnings: db.add(Memory(owner_id=job.owner_id, source=seg.source, target=target))
        # Export via queue after correction; a separate state avoids retranslating.
        job.status = "export_queued"
    return RedirectResponse(BASE_PATH + "/jobs/" + job_id, status_code=303)

@app.get("/glossary")
def glossary(request: Request):
    with Session() as db:
        user = authenticated(request, db)
        return templates.TemplateResponse(request=request, name="glossary.html", context={"user":user,"entries":list(db.scalars(select(Glossary))),"csrf":request.session["csrf"]})

@app.post("/glossary")
def glossary_save(request: Request, source: str = Form(), target: str = Form(), token: str = Form()):
    csrf(request, token)
    if not source.strip() or len(source) > 200 or len(target) > 500: raise HTTPException(400)
    with Session.begin() as db:
        user = authenticated(request, db)
        if not user.admin: raise HTTPException(403)
        entry = db.scalar(select(Glossary).where(Glossary.source == source))
        if entry: entry.target = target
        else: db.add(Glossary(source=source,target=target))
    return RedirectResponse(BASE_PATH + "/glossary", status_code=303)

@app.get("/admin")
def admin(request: Request):
    with Session() as db:
        user = authenticated(request, db)
        if not user.admin: raise HTTPException(403)
    from .cli import diagnostic
    from .model_download import CATALOG, latest_status
    return templates.TemplateResponse(request=request, name="admin.html", context={"system":diagnostic(),"models":Registry().list(),"csrf":request.session["csrf"],"catalog":CATALOG,"download":latest_status(DATA / "model-downloads", MODELS)})


@app.post("/admin/models/download")
def model_download(request: Request, model_id: str = Form(), token: str = Form(), confirm_network: str = Form("")):
    csrf(request, token)
    with Session() as db:
        if not authenticated(request, db).admin: raise HTTPException(403)
    if confirm_network != "yes": raise HTTPException(400, "Confirmez le téléchargement initial depuis Hugging Face.")
    from .model_download import start_download
    try: start_download(model_id, MODELS, DATA / "model-downloads")
    except ValueError as exc: raise HTTPException(409, str(exc)) from exc
    except OSError as exc: raise HTTPException(503, "Téléchargement indisponible : vérifiez les permissions du dossier des modèles.") from exc
    return RedirectResponse(BASE_PATH + "/admin", status_code=303)

@app.get("/admin/models/download/status")
def model_download_status(request: Request):
    with Session() as db:
        if not authenticated(request, db).admin: raise HTTPException(403)
    from .model_download import latest_status
    return latest_status(DATA / "model-downloads", MODELS) or {"status":"idle"}

