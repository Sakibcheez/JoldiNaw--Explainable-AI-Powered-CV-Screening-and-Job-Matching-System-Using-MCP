"""CI-only check against configured PostgreSQL and Redis services."""

from redis import Redis
from sqlalchemy import text
from app.db import engine
from app.config import settings
import io
from docx import Document
from rq import Queue, SimpleWorker
from sqlalchemy import select
from app.db import Batch, Job, Result, Resume, Session, User, Membership, uid
from app.tasks import execute
from scripts.seed_demo import seed

with engine.connect() as connection:
    assert connection.scalar(text("SELECT count(*) FROM pg_extension WHERE extname='vector'")) == 1
assert Redis.from_url(settings.redis_url).ping()
seed()
connection = Redis.from_url(settings.redis_url)
queue = Queue("ci-" + uid(), connection=connection)
with Session() as db:
    user = db.scalar(select(User).where(User.subject == "demo-recruiter"))
    org = db.scalar(select(Membership.organization_id).where(Membership.user_id == user.id))
    job = db.scalar(select(Job).where(Job.organization_id == org))
    document = Document()
    document.add_paragraph("SYNTHETIC: Developed Python and SQL services with Docker.")
    data = io.BytesIO()
    document.save(data)
    resume = Resume(id=uid(), organization_id=org, filename="synthetic-ci.docx", object_key=uid() + ".docx")
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    (settings.storage_dir / resume.object_key).write_bytes(data.getvalue())
    db.add(resume)
    db.commit()
    rid = resume.id
queue.enqueue(execute, "parse", rid, org)
SimpleWorker([queue], connection=connection).work(burst=True)
with Session() as db:
    assert db.get(Resume, rid).status == "ready"
    batch = Batch(id=uid(), organization_id=org, job_id=job.id, resume_ids=[rid], requirement_snapshot=job.requirements)
    db.add(batch)
    db.commit()
    bid = batch.id
queue.enqueue(execute, "screen", bid, org)
SimpleWorker([queue], connection=connection).work(burst=True)
with Session() as db:
    assert db.get(Batch, bid).status == "completed"
    result = db.scalar(select(Result).where(Result.batch_id == bid))
    assert result.payload["requirement_evidence_coverage"] == 100
queue.delete()
print("PostgreSQL vector extension, Redis/RQ queued parsing and screening verified")
