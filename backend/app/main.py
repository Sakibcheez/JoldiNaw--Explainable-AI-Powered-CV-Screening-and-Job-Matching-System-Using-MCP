import csv
import io
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from redis import Redis
from sqlalchemy import select, text
from sqlalchemy.orm import Session as DBSession
from app.auth import Identity, demo_token, identity, workspace_reader, writer
from app.config import settings
from app.db import Batch, Job, Membership, Processing, Result, Resume, Review, get_db, uid
from app.documents import validate_file
from app.schemas import Correction, JobInput, Login, OidcExchange, Requirement, ReviewInput, ScreeningInput
from app.services import (
    audit,
    delete_resume,
    job_data,
    listing,
    owned,
    replace_text,
    requirements_data,
    result_data,
    resume_data,
)
from app.tasks import enqueue


@asynccontextmanager
async def lifespan(_):
    settings.validate_runtime()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="JoldiNaw", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Organization-ID"],
)
requests_by_ip = defaultdict(deque)


@app.middleware("http")
async def boundaries(request: Request, call_next):
    if int(request.headers.get("content-length", "0")) > 11 * 1024 * 1024:
        return JSONResponse({"detail": "Request exceeds limit"}, 413)
    if request.url.path.startswith("/api/"):
        key = request.client.host if request.client else "unknown"
        queue = requests_by_ip[key]
        now = time.monotonic()
        while queue and queue[0] < now - 60:
            queue.popleft()
        if len(queue) >= 180:
            return JSONResponse({"detail": "Rate limit exceeded"}, 429)
        queue.append(now)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready(db: DBSession = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        if settings.task_mode == "rq":
            Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping()
        return {"status": "ready"}
    except Exception:
        raise HTTPException(503, "Dependencies unavailable") from None


@app.post("/api/v1/auth/demo")
def login(body: Login):
    return {"access_token": demo_token(body.password), "token_type": "bearer"}


def oidc_document():
    if not settings.oidc_client_id or not settings.oidc_redirect_uri:
        raise HTTPException(503, "OIDC browser sign-in is not configured")
    issuer = settings.oidc_issuer.rstrip("/")
    try:
        response = httpx.get(f"{issuer}/.well-known/openid-configuration", timeout=5)
        response.raise_for_status()
        document = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Identity provider discovery failed") from exc
    if not isinstance(document, dict) or str(document.get("issuer", "")).rstrip("/") != issuer:
        raise HTTPException(502, "Identity provider discovery returned invalid endpoints")
    endpoints = [document.get(name) for name in ("authorization_endpoint", "token_endpoint")]
    if any(not isinstance(endpoint, str) or not endpoint for endpoint in endpoints):
        raise HTTPException(502, "Identity provider discovery returned invalid endpoints")
    try:
        endpoint_urls = [urlsplit(endpoint) for endpoint in endpoints]
        callback = urlsplit(settings.oidc_redirect_uri)
    except ValueError as exc:
        raise HTTPException(502, "Identity provider discovery returned invalid endpoints") from exc
    if any(not url.netloc or url.scheme not in {"http", "https"} for url in endpoint_urls):
        raise HTTPException(502, "Identity provider discovery returned invalid endpoints")
    if settings.app_env == "production" and any(
        url.scheme != "https" for url in endpoint_urls
    ):
        raise HTTPException(502, "Production identity provider endpoints must use HTTPS")
    allowed_origins = {origin.strip().rstrip("/") for origin in settings.cors_origins.split(",")}
    callback_origin = f"{callback.scheme}://{callback.netloc}"
    if (
        not callback.netloc
        or callback.path != "/auth/callback"
        or callback.query
        or callback.fragment
        or callback_origin not in allowed_origins
    ):
        raise HTTPException(503, "OIDC callback must be an allowed frontend origin ending in /auth/callback")
    if settings.app_env == "production" and callback.scheme != "https":
        raise HTTPException(503, "Production OIDC callback must use HTTPS")
    if not {"openid", "read", "write"}.issubset(settings.oidc_scopes.split()):
        raise HTTPException(503, "OIDC_SCOPES must include openid, read and write")
    return document


@app.get("/api/v1/auth/oidc/config")
def oidc_config():
    document = oidc_document()
    return {
        "authorization_endpoint": document["authorization_endpoint"],
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scopes": settings.oidc_scopes,
        "audience": settings.oidc_audience,
    }


@app.post("/api/v1/auth/oidc/token")
def oidc_token(body: OidcExchange):
    document = oidc_document()
    try:
        response = httpx.post(
            document["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "client_id": settings.oidc_client_id,
                "code": body.code,
                "redirect_uri": settings.oidc_redirect_uri,
                "code_verifier": body.code_verifier,
            },
            timeout=10,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Identity provider token exchange failed") from exc
    if response.is_error:
        raise HTTPException(401, "Identity provider rejected the authorization code")
    try:
        token_response = response.json()
    except ValueError as exc:
        raise HTTPException(502, "Identity provider returned an invalid token response") from exc
    if (
        not isinstance(token_response, dict)
        or not isinstance(token_response.get("access_token"), str)
        or not token_response["access_token"].strip()
    ):
        raise HTTPException(502, "Identity provider response did not include an access token")
    return {"access_token": token_response["access_token"], "token_type": "bearer"}


@app.get("/api/v1/me")
def me(who: Identity = Depends(identity), db: DBSession = Depends(get_db)):
    return {
        "user_id": who.user_id,
        "organization_id": who.organization_id,
        "role": who.role,
        "memberships": [
            {"organization_id": m.organization_id, "role": m.role}
            for m in db.scalars(select(Membership).where(Membership.user_id == who.user_id))
        ],
    }


@app.get("/api/v1/jobs")
def jobs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    who: Identity = Depends(workspace_reader),
    db: DBSession = Depends(get_db),
):
    return [job_data(j) for j in listing(db, Job, who.organization_id, limit, offset)]


@app.post("/api/v1/jobs", status_code=201)
def create_job(body: JobInput, who: Identity = Depends(writer), db: DBSession = Depends(get_db)):
    job = Job(
        id=uid(),
        organization_id=who.organization_id,
        title=body.title,
        description=body.description,
        status=body.status,
        requirements=requirements_data(body.requirements),
    )
    db.add(job)
    audit(db, who, "job.create", job.id)
    db.commit()
    return job_data(job)


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str, who: Identity = Depends(workspace_reader), db: DBSession = Depends(get_db)):
    return job_data(owned(db, Job, job_id, who.organization_id))


@app.patch("/api/v1/jobs/{job_id}")
def edit_job(job_id: str, body: JobInput, who: Identity = Depends(writer), db: DBSession = Depends(get_db)):
    job = owned(db, Job, job_id, who.organization_id)
    job.title, job.description, job.status = body.title, body.description, body.status
    job.requirements = requirements_data(body.requirements)
    audit(db, who, "job.edit", job.id)
    db.commit()
    return job_data(job)


@app.put("/api/v1/jobs/{job_id}/requirements")
def edit_requirements(
    job_id: str, body: list[Requirement], who: Identity = Depends(writer), db: DBSession = Depends(get_db)
):
    if not 1 <= len(body) <= 100:
        raise HTTPException(422, "Provide 1–100 requirements")
    job = owned(db, Job, job_id, who.organization_id)
    job.requirements = requirements_data(body)
    audit(db, who, "requirements.approve", job.id)
    db.commit()
    return job_data(job)


@app.delete("/api/v1/jobs/{job_id}", status_code=204)
def remove_job(job_id: str, who: Identity = Depends(writer), db: DBSession = Depends(get_db)):
    db.delete(owned(db, Job, job_id, who.organization_id))
    audit(db, who, "job.delete", job_id)
    db.commit()


@app.post("/api/v1/resumes", status_code=202)
async def upload(file: UploadFile = File(), who: Identity = Depends(writer), db: DBSession = Depends(get_db)):
    content = await file.read(10 * 1024 * 1024 + 1)
    filename = Path((file.filename or "document").replace("\\", "/")).name[:255]
    try:
        suffix = validate_file(content, filename)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    resume = Resume(id=uid(), organization_id=who.organization_id, filename=filename, object_key=uid() + suffix)
    task = Processing(id=uid(), organization_id=who.organization_id, resource_id=resume.id, kind="parse")
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    path = settings.storage_dir / resume.object_key
    path.write_bytes(content)
    try:
        db.add_all([resume, task])
        audit(db, who, "resume.upload", resume.id)
        db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    dispatch(db, task, resume)
    return {"resume_id": resume.id, "processing_job_id": task.id, "status": "queued"}


def dispatch(db, task, resource):
    try:
        enqueue(task.kind, resource.id, task.organization_id)
    except Exception:
        task.status, resource.status = "failed", "failed"
        task.error = "Queue unavailable; retry when the worker service is ready"
        resource.error = task.error
        db.commit()
        raise HTTPException(503, "Queue unavailable; record saved with failed status") from None


@app.get("/api/v1/resumes")
def resumes(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    who: Identity = Depends(workspace_reader),
    db: DBSession = Depends(get_db),
):
    return [resume_data(db, r) for r in listing(db, Resume, who.organization_id, limit, offset)]


@app.get("/api/v1/resumes/{resume_id}")
def get_resume(resume_id: str, who: Identity = Depends(workspace_reader), db: DBSession = Depends(get_db)):
    return resume_data(db, owned(db, Resume, resume_id, who.organization_id), True)


@app.patch("/api/v1/resumes/{resume_id}/corrections")
def correct(resume_id: str, body: Correction, who: Identity = Depends(writer), db: DBSession = Depends(get_db)):
    resume = owned(db, Resume, resume_id, who.organization_id)
    if resume.status not in {"ready", "failed"}:
        raise HTTPException(409, "Wait for parsing to finish")
    replace_text(db, resume, body.text)
    audit(db, who, "resume.correct", resume.id)
    db.commit()
    return resume_data(db, resume, True)


@app.delete("/api/v1/resumes/{resume_id}", status_code=204)
def remove_resume(resume_id: str, who: Identity = Depends(writer), db: DBSession = Depends(get_db)):
    resume = owned(db, Resume, resume_id, who.organization_id)
    audit(db, who, "resume.delete", resume_id)
    delete_resume(db, resume)


@app.get("/api/v1/processing/{task_id}")
def processing(task_id: str, who: Identity = Depends(workspace_reader), db: DBSession = Depends(get_db)):
    task = owned(db, Processing, task_id, who.organization_id)
    return {"id": task.id, "status": task.status, "error": task.error}


@app.post("/api/v1/jobs/{job_id}/screenings", status_code=202)
def screen(job_id: str, body: ScreeningInput, who: Identity = Depends(writer), db: DBSession = Depends(get_db)):
    job = owned(db, Job, job_id, who.organization_id)
    ids = list(dict.fromkeys(body.resume_ids))
    for rid in ids:
        if owned(db, Resume, rid, who.organization_id).status != "ready":
            raise HTTPException(409, "All selected resumes must be ready")
    batch = Batch(
        id=uid(),
        organization_id=who.organization_id,
        job_id=job.id,
        resume_ids=ids,
        requirement_snapshot=job.requirements,
    )
    task = Processing(id=uid(), organization_id=who.organization_id, resource_id=batch.id, kind="screen")
    db.add_all([batch, task])
    audit(db, who, "screening.create", batch.id)
    db.commit()
    dispatch(db, task, batch)
    return {"batch_id": batch.id, "processing_job_id": task.id, "status": "queued"}


@app.get("/api/v1/screening-batches")
def batches(who: Identity = Depends(workspace_reader), db: DBSession = Depends(get_db)):
    return [
        {"id": b.id, "job_id": b.job_id, "status": b.status, "created_at": b.created_at}
        for b in listing(db, Batch, who.organization_id)
    ]


@app.get("/api/v1/screening-batches/{batch_id}")
def get_batch(batch_id: str, who: Identity = Depends(workspace_reader), db: DBSession = Depends(get_db)):
    b = owned(db, Batch, batch_id, who.organization_id)
    return {"id": b.id, "job_id": b.job_id, "status": b.status, "error": b.error, "resume_ids": b.resume_ids}


@app.get("/api/v1/screening-batches/{batch_id}/results")
def results(
    batch_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    who: Identity = Depends(workspace_reader),
    db: DBSession = Depends(get_db),
):
    owned(db, Batch, batch_id, who.organization_id)
    rows = db.scalars(
        select(Result)
        .where(Result.batch_id == batch_id, Result.organization_id == who.organization_id)
        .order_by(Result.created_at, Result.id)
        .limit(limit)
        .offset(offset)
    )
    return [result_data(db, r) for r in rows]


@app.get("/api/v1/screening-results/{result_id}")
def get_result(result_id: str, who: Identity = Depends(workspace_reader), db: DBSession = Depends(get_db)):
    return result_data(db, owned(db, Result, result_id, who.organization_id))


@app.post("/api/v1/screening-results/{result_id}/reviews", status_code=201)
def review(result_id: str, body: ReviewInput, who: Identity = Depends(writer), db: DBSession = Depends(get_db)):
    owned(db, Result, result_id, who.organization_id)
    r = Review(organization_id=who.organization_id, result_id=result_id, reviewer_id=who.user_id, **body.model_dump())
    db.add(r)
    audit(db, who, "review.create", result_id)
    db.commit()
    return {"id": r.id, "decision": r.decision}


@app.get("/api/v1/screening-batches/{batch_id}/export")
def export(batch_id: str, who: Identity = Depends(workspace_reader), db: DBSession = Depends(get_db)):
    owned(db, Batch, batch_id, who.organization_id)
    output = io.StringIO()
    csv_writer = csv.writer(output)
    csv_writer.writerow(
        ["candidate_id", "evidence_coverage", "semantic_similarity", "model_version", "human_review_required"]
    )
    for r in db.scalars(
        select(Result).where(Result.batch_id == batch_id, Result.organization_id == who.organization_id)
    ):
        p = r.payload
        csv_writer.writerow(
            [r.resume_id, p["requirement_evidence_coverage"], p["semantic_similarity"], p["model_version"], True]
        )
    audit(db, who, "report.export", batch_id)
    db.commit()
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="screening.csv"'},
    )
