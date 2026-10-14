import time
import logging
from datetime import timedelta
from sqlalchemy import select
import httpx
from .config import DATA, RUNTIME_URL, RUNTIME_SECRET
from .db import Session, Job, Segment, Glossary, Memory, now
from .documents import analyze, exports
from .quality import check
from .terminology import terminology
from .translation_audit import audit_translation
from .diagnostics import record, InferenceError, safe_details
from .document_context import translation_context

log = logging.getLogger(__name__)

def reusable_translation(source, target, terms):
    from .quality import inference_defects
    from .terminology import missing_names
    return (isinstance(target, str) and bool(target.strip())
            and not missing_names(source, target, terms)
            and not inference_defects(source, target))

def export_job(s, job):
    segments = list(s.scalars(select(Segment).where(Segment.job_id == job.id).order_by(Segment.position)))
    report = exports(DATA / 'uploads' / (job.id + job.suffix), job.suffix,
                     [segment.target for segment in segments], DATA / 'outputs' / job.id,
                     segments=[dict(segment.metadata_json, text=segment.source) for segment in segments])
    if report:
        for warning in report['warnings']:
            segment = segments[warning['segment']]
            message = 'Mise en page : ' + warning['reason']
            if message not in segment.warnings:
                segment.warnings = [*segment.warnings, message]

def claim():
    with Session.begin() as s:
        job = s.scalar(select(Job).where(Job.status.in_(["queued", "export_queued"])).order_by(Job.created).with_for_update(skip_locked=True).limit(1))
        if not job: return None
        job.status = "exporting" if job.status == "export_queued" else "running"; job.heartbeat = now()
        return job.id

def _run_job(job_id):
    start = time.monotonic()
    record(job_id, "started")
    try:
        with Session() as s:
            job = s.get(Job, job_id)
            if job.status == "exporting":
                export_job(s, job)
                job.status = "done"; job.progress = 100; s.commit()
                return
            if job.model_id == 'remote-bc250':
                from .remote_ai import settings, manifest as remote_manifest, ensure_model
                current = remote_manifest()
                if not current or current['revision'] != job.model_version:
                    raise ValueError('Configuration IA distante modifiée ; créer une nouvelle traduction')
                record(job_id, 'remote_model_loading')
                s.commit()
                ensure_model(settings())
                record(job_id, 'remote_model_ready')
                job.heartbeat = now(); s.commit()
            terms = {g.source:g.target for g in s.scalars(select(Glossary).where(Glossary.active == True).order_by(Glossary.priority.desc()))}
            terms = terminology(terms)
            items = analyze(DATA / "uploads" / (job.id + job.suffix), job.suffix)
            texts = [item["text"] for item in items]
            if not texts: raise ValueError("Aucun texte exploitable")
            if len(texts) > 20000: raise ValueError("Trop de segments")
            targets = []
            for i, text in enumerate(texts):
                segment_started = time.monotonic()
                record(job_id, "segment_started", segment=i + 1, characters=len(text))
                memory = s.scalar(select(Memory).where(Memory.owner_id == job.owner_id, Memory.source == text).order_by(Memory.id.desc()).limit(1))
                from .terminology import correct_network_terms, missing_names
                cached = correct_network_terms(text,memory.target) if memory else None
                if cached is not None and reusable_translation(text,cached,terms): translated = cached
                else:
                    with httpx.Client(timeout=300, trust_env=False) as client:
                        response = client.post(RUNTIME_URL + "/translate", headers={"X-Runtime-Secret":RUNTIME_SECRET}, json={"model_id":job.model_id, "revision":job.model_version, "texts":[text], "contextual":True, "glossary":terms, "contexts":[translation_context(items, i)]})
                        if response.status_code != 200:
                            diagnostic = {"code": "runtime_http_error", "http_status": response.status_code}
                            try:
                                detail = response.json().get("detail")
                                if isinstance(detail, dict) and isinstance(detail.get("diagnostic"), dict):
                                    diagnostic.update(safe_details(detail["diagnostic"]))
                            except (ValueError, AttributeError): pass
                            diagnostic["segment"] = i + 1
                            raise InferenceError(diagnostic["code"], diagnostic)
                        translated = response.json()["texts"][0]
                # Apply deterministic repairs to cached translations as well.
                translated = correct_network_terms(text, translated)
                warnings = list(dict.fromkeys(check(text, translated) + audit_translation(text, translated)))
                if items[i]["confidence"] < 0.85: warnings.append("OCR incertain : vérification nécessaire")
                if items[i].get("minimum_confidence", 1) < .50:
                    warnings.append("Mot OCR incertain : vérifier le texte source")
                s.add(Segment(job_id=job.id, position=i, source=text, machine=translated, target=translated, warnings=warnings, metadata_json={k:v for k,v in items[i].items() if k != "text"}))
                targets.append(translated)
                record(job_id, "segment_done", segment=i + 1, seconds=round(time.monotonic() - segment_started, 2))
                job.progress = int((i + 1) / len(texts) * 90); job.heartbeat = now(); s.commit()
                (DATA / "worker-heartbeat").write_text(str(time.time()))
            export_job(s, job)
            record(job_id, "done", seconds=round(time.monotonic() - start, 2))
            job.status = "done"; job.progress = 100; job.elapsed = int(time.monotonic() - start); s.commit()
    except Exception as exc:
        record(job_id, "failed", **getattr(exc, "diagnostic", {"code": "processing_error", "exception": type(exc).__name__}))
        # No confidential document text or model response in logs.
        log.error("job=%s error=%s", job_id, type(exc).__name__)
        with Session.begin() as s:
            job = s.get(Job, job_id); job.status = "failed"
            job.error = str(exc) if isinstance(exc, ValueError) else "Échec du traitement : " + type(exc).__name__

def main():
    logging.basicConfig(level=logging.INFO)
    DATA.mkdir(parents=True, exist_ok=True)
    recover_layout_failures()
    while True:
        (DATA / "worker-heartbeat").write_text(str(time.time()))
        job_id = claim()
        if job_id: run_job(job_id)
        else: time.sleep(2)

def recover_layout_failures():
    # Retry only this known export regression, preserving every saved correction.
    with Session.begin() as s:
        jobs = s.scalars(select(Job).where(Job.status == 'failed', Job.suffix == '.pdf',
                                          Job.error == 'Coordonnées OCR hors de la page'))
        for job in jobs:
            if s.scalar(select(Segment.id).where(Segment.job_id == job.id).limit(1)) is not None:
                job.status = 'export_queued'
                job.error = ''


def run_job(job_id):
    # Hold the remote job slot for the entire document, not only the switch.
    import fcntl
    with Session() as session:
        job=session.get(Job,job_id)
        remote=job.model_id == 'remote-bc250' and job.status != 'exporting'
    if not remote: return _run_job(job_id)
    with open(DATA / 'remote-job.lock','a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            with Session.begin() as session:
                job=session.get(Job,job_id);job.status='queued';job.heartbeat=now()
            time.sleep(1)
            return
        return _run_job(job_id)


if __name__ == "__main__": main()



