from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .config import RUNTIME_SECRET
from .registry import Registry
from .translation import Runtime

app = FastAPI(docs_url=None, redoc_url=None)
runtime = Runtime()
class Request(BaseModel):
    model_id: str
    revision: str
    texts: list[str] = Field(min_length=1, max_length=32)

@app.get("/health")
def health(): return runtime.engine.health()

@app.post("/translate")
def translate(body: Request, x_runtime_secret: str = Header(default="")):
    import secrets
    if not RUNTIME_SECRET or not secrets.compare_digest(x_runtime_secret, RUNTIME_SECRET): raise HTTPException(403)
    try:
        manifest = Registry().choose(body.model_id)
        if manifest["revision"] != body.revision: raise ValueError("Révision du job indisponible")
        if any(len(t) > 5000 for t in body.texts): raise ValueError("Segment trop long")
        return {"texts": runtime.translate(manifest, body.texts)}
    except Exception as exc:
        raise HTTPException(503, "Moteur local indisponible : " + type(exc).__name__) from exc
