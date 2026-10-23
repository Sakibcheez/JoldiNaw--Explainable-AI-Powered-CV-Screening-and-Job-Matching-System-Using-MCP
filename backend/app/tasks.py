from redis import Redis
from rq import Queue
from sqlalchemy import select
from app.config import settings
from app.db import Batch, Processing, Result, Resume, Section, Session, uid
from app.documents import parse, skills
from app.matching import match, passage_embeddings


def enqueue(kind, resource_id, org):
    if settings.task_mode == "inline" and settings.app_env != "production":
        execute(kind, resource_id, org)
    else:
        Queue("screening", connection=Redis.from_url(settings.redis_url)).enqueue(
            execute, kind, resource_id, org, job_timeout=180, result_ttl=0
        )


def execute(kind, resource_id, org):
    with Session() as db:
        model = Resume if kind == "parse" else Batch
        row = db.scalar(select(model).where(model.id == resource_id, model.organization_id == org).with_for_update())
        if row is None or row.status != "queued":
            return
        task = db.scalar(
            select(Processing).where(Processing.resource_id == resource_id, Processing.organization_id == org)
        )
        row.status = "processing"
        if task:
            task.status = "processing"
        db.commit()
        try:
            if kind == "parse":
                output = parse((settings.storage_dir / row.object_key).read_bytes(), row.filename)
                embeddings = passage_embeddings([p["text"] for p in output])
                for passage, vector in zip(output, embeddings):
                    db.add(Section(resume_id=row.id, embedding=vector, **passage))
                row.skills = skills("\n".join(p["text"] for p in output))
                row.status = "ready"
            else:
                for resume_id in row.resume_ids:
                    resume = db.scalar(
                        select(Resume)
                        .where(Resume.id == resume_id, Resume.organization_id == org, Resume.status == "ready")
                        .with_for_update()
                    )
                    if resume is None:
                        raise ValueError("A selected resume is no longer ready")
                    sections = db.scalars(
                        select(Section).where(Section.resume_id == resume.id).order_by(Section.page, Section.start)
                    ).all()
                    if settings.embedding_path and any(s.embedding is None for s in sections):
                        vectors = passage_embeddings([s.text for s in sections])
                        for section, vector in zip(sections, vectors):
                            section.embedding = vector
                    payload = match(row.requirement_snapshot, sections)
                    payload["resume_revision"] = resume.revision
                    payload["inference_id"] = uid()
                    db.add(Result(organization_id=org, batch_id=row.id, resume_id=resume.id, payload=payload))
                row.status = "completed"
            if task:
                task.status = "completed"
            db.commit()
        except Exception:
            db.rollback()
            row = db.get(model, resource_id)
            if row:
                row.status = "failed"
                row.error = "Processing failed. Check document format, ready inputs and installed model artifacts."
            if task:
                task.status = "failed"
                task.error = "Processing failed; retry after correcting inputs."
            db.commit()
