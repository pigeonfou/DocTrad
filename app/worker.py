import time
import logging
from datetime import timedelta
from sqlalchemy import select
import httpx
from .config import DATA, RUNTIME_URL, RUNTIME_SECRET
from .db import Session, Job, Segment, Glossary, Memory, now
from .documents import analyze, exports
from .quality import protect, restore, check

log = logging.getLogger(__name__)

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

def run_job(job_id):
    start = time.monotonic()
    try:
        with Session() as s:
            job = s.get(Job, job_id)
            if job.status == "exporting":
                export_job(s, job)
                job.status = "done"; job.progress = 100; s.commit()
                return
            terms = {g.source:g.target for g in s.scalars(select(Glossary).where(Glossary.active == True).order_by(Glossary.priority.desc()))}
            items = analyze(DATA / "uploads" / (job.id + job.suffix), job.suffix)
            texts = [item["text"] for item in items]
            if not texts: raise ValueError("Aucun texte exploitable")
            if len(texts) > 20000: raise ValueError("Trop de segments")
            targets = []
            for i, text in enumerate(texts):
                memory = s.scalar(select(Memory).where(Memory.owner_id == job.owner_id, Memory.source == text).order_by(Memory.id.desc()).limit(1))
                if memory: translated = memory.target
                else:
                    protected, mapping = protect(text, terms)
                    with httpx.Client(timeout=300, trust_env=False) as client:
                        response = client.post(RUNTIME_URL + "/translate", headers={"X-Runtime-Secret":RUNTIME_SECRET}, json={"model_id":job.model_id, "revision":job.model_version, "texts":[protected]})
                        if response.status_code != 200: raise ValueError("Moteur local indisponible ou segment refusé ; consulter le diagnostic")
                        translated = restore(response.json()["texts"][0], mapping)
                warnings = check(text, translated)
                if items[i]["confidence"] < 0.85: warnings.append("OCR incertain : vérification nécessaire")
                s.add(Segment(job_id=job.id, position=i, source=text, machine=translated, target=translated, warnings=warnings, metadata_json={k:v for k,v in items[i].items() if k != "text"}))
                targets.append(translated)
                job.progress = int((i + 1) / len(texts) * 90); job.heartbeat = now(); s.commit()
                (DATA / "worker-heartbeat").write_text(str(time.time()))
            export_job(s, job)
            job.status = "done"; job.progress = 100; job.elapsed = int(time.monotonic() - start); s.commit()
    except Exception as exc:
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

if __name__ == "__main__": main()
