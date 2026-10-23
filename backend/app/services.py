from fastapi import HTTPException
from sqlalchemy import delete, select
from app.db import Audit, Batch, Job, Processing, Result, Resume, Review, Section, uid
from app.config import settings
from app.documents import passages, skills


def owned(db, model, resource_id, org):
    row = db.scalar(select(model).where(model.id == resource_id, model.organization_id == org))
    if row is None:
        raise HTTPException(404, "Record not found")
    return row


def listing(db, model, org, limit=50, offset=0):
    return db.scalars(
        select(model)
        .where(model.organization_id == org)
        .order_by(model.created_at.desc(), model.id)
        .limit(limit)
        .offset(offset)
    ).all()


def audit(db, who, action, resource_id):
    db.add(Audit(organization_id=who.organization_id, actor=who.user_id, action=action, resource_id=resource_id))


def job_data(job):
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "status": job.status,
        "requirements": job.requirements,
        "created_at": job.created_at,
    }


def resume_data(db, resume, detail=False):
    data = {
        "id": resume.id,
        "filename": resume.filename,
        "status": resume.status,
        "error": resume.error,
        "skills": resume.skills,
        "revision": resume.revision,
        "created_at": resume.created_at,
    }
    if detail:
        data["sections"] = [
            {"id": s.id, "text": s.text, "page": s.page, "start": s.start, "end": s.end}
            for s in db.scalars(
                select(Section).where(Section.resume_id == resume.id).order_by(Section.page, Section.start)
            )
        ]
    return data


def requirements_data(requirements):
    return [{**r.model_dump(), "id": uid(), "position": i} for i, r in enumerate(requirements)]


def replace_text(db, resume, text):
    # Invalidate outputs before replacing passage IDs so all surviving citations remain resolvable.
    results = db.scalars(select(Result).where(Result.resume_id == resume.id)).all()
    for result in results:
        db.execute(delete(Review).where(Review.result_id == result.id))
        db.delete(result)
    db.execute(delete(Section).where(Section.resume_id == resume.id))
    output = list(passages(text))
    for passage in output:
        db.add(Section(resume_id=resume.id, **passage))
    resume.skills = skills(text)
    resume.revision += 1
    resume.status = "ready"


def delete_resume(db, resume):
    key = resume.object_key
    # Remove references from batch input lists as well as cascading results and reviews.
    for batch in db.scalars(select(Batch).where(Batch.organization_id == resume.organization_id)):
        batch.resume_ids = [rid for rid in batch.resume_ids if rid != resume.id]
    db.execute(
        delete(Processing).where(
            Processing.resource_id == resume.id, Processing.organization_id == resume.organization_id
        )
    )
    db.delete(resume)
    db.commit()
    (settings.storage_dir / key).unlink(missing_ok=True)


def result_data(db, result):
    return {
        **result.payload,
        "id": result.id,
        "resume_id": result.resume_id,
        "batch_id": result.batch_id,
        "reviews": [
            {"decision": r.decision, "notes": r.notes, "created_at": r.created_at}
            for r in db.scalars(select(Review).where(Review.result_id == result.id).order_by(Review.created_at))
        ],
    }


def existing_match(db, org, job_id, resume_id):
    owned(db, Job, job_id, org)
    owned(db, Resume, resume_id, org)
    result = db.scalar(
        select(Result)
        .join(Batch)
        .where(Result.organization_id == org, Batch.job_id == job_id, Result.resume_id == resume_id)
        .order_by(Result.created_at.desc())
    )
    if result is None:
        raise HTTPException(404, "Run a screening in the recruiter application first")
    return result_data(db, result)
