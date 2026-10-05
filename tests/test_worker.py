from app.config import DATA
from app.db import Session,User,Job,Segment,Memory
from app.worker import claim,run_job
from sqlalchemy import select

def test_queue_to_export_using_validated_memory():
    from docx import Document
    DATA.joinpath('uploads').mkdir(parents=True,exist_ok=True)
    source='Power supply voltage: 12 VDC.';target='Tension alimentation : 12 VDC.'
    with Session.begin() as db:
        user=User(username='alice',password='not-used');db.add(user);db.flush()
        db.add(Job(id='memory-job',owner_id=user.id,filename='a.docx',suffix='.docx',model_id='opus',model_version='a'*40))
        db.add(Memory(owner_id=user.id,source=source,target=target))
    doc=Document();doc.add_paragraph(source);doc.save(DATA/'uploads/memory-job.docx')
    assert claim()=='memory-job'
    assert claim() is None
    run_job('memory-job')
    with Session() as db:
        assert db.get(Job,'memory-job').status=='done'
        assert db.scalar(select(Segment)).target==target
    assert (DATA/'outputs/memory-job/translation.pdf').is_file()

def test_export_after_correction():
    test_queue_to_export_using_validated_memory()
    with Session.begin() as db:
        db.get(Job,'memory-job').status='export_queued'
        db.scalar(select(Segment)).target='Alimentation nominale : 12 VDC.'
    assert claim()=='memory-job';run_job('memory-job')
    from docx import Document
    assert Document(DATA/'outputs/memory-job/translation.docx').paragraphs[0].text=='Alimentation nominale : 12 VDC.'


def test_postgres_claim_is_atomic():
    import pytest
    from app.db import engine
    if engine.dialect.name != "postgresql":pytest.skip("Native PostgreSQL CI test")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    with Session.begin() as db:
        user=User(username="queue-test",password="unused");db.add(user);db.flush()
        for i in range(4):db.add(Job(id=f"concurrent-{i}",owner_id=user.id,filename="test.docx",suffix=".docx",model_id="opus",model_version="a"*40))
    gate=Barrier(4)
    def reserve():gate.wait();return claim()
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:reserve(),range(4)))
    assert len(set(results))==4 and None not in results
    assert claim() is None
