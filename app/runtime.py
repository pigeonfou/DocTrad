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
    contextual: bool = False
    glossary: dict[str, str] = Field(default_factory=dict, max_length=10000)
    texts: list[str] = Field(min_length=1, max_length=32)
    contexts: list[dict[str, str]] = Field(default_factory=list, max_length=32)

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
        if body.contexts and len(body.contexts) != len(body.texts): raise ValueError("Contextes incohérents")
        if any(sum(len(k)+len(v) for k,v in context.items()) > 1600 for context in body.contexts):
            raise ValueError("Contexte trop long")
        import time, resource
        started = time.monotonic()
        texts = runtime.translate(manifest, body.texts, contextual=body.contextual, glossary=body.glossary, contexts=body.contexts)
        return {"texts": texts, "seconds": time.monotonic() - started, "runtime_peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    except Exception as exc:
        from .diagnostics import safe_details
        diagnostic = getattr(exc, "diagnostic", {"code": "runtime_error", "exception": type(exc).__name__})
        raise HTTPException(503, {"message": "Moteur indisponible ou segment refusé", "diagnostic": safe_details(diagnostic)}) from exc


