import io
from docx import Document
from pypdf import PdfWriter
from sqlalchemy import select
from app.db import Membership, Organization, Resume, Review, Section, Session, uid
from app.documents import parse, skills, validate_file
from app.matching import match


def docx(text):
    doc = Document()
    doc.add_paragraph(text)
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()


def screen(client, headers):
    job = client.get("/api/v1/jobs", headers=headers).json()[0]
    resumes = client.get("/api/v1/resumes", headers=headers).json()
    response = client.post(
        f"/api/v1/jobs/{job['id']}/screenings", headers=headers, json={"resume_ids": [r["id"] for r in resumes]}
    )
    assert response.status_code == 202
    batch_id = response.json()["batch_id"]
    results = client.get(f"/api/v1/screening-batches/{batch_id}/results", headers=headers).json()
    return job, resumes, batch_id, results


def test_auth_and_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").status_code == 200
    assert client.get("/api/v1/jobs").status_code == 401
    assert client.post("/api/v1/auth/demo", json={"password": "wrong"}).status_code == 401
    assert client.get("/api/v1/jobs", headers={"Authorization": "Bearer forged"}).status_code == 401


def test_upload_screen_ground_review_export_delete(client, headers):
    response = client.post(
        "/api/v1/resumes",
        headers=headers,
        files={"file": ("synthetic.docx", docx("Built Python services using SQL and Docker."))},
    )
    assert response.status_code == 202
    rid = response.json()["resume_id"]
    task = client.get("/api/v1/processing/" + response.json()["processing_job_id"], headers=headers).json()
    assert task["status"] == "completed"
    resume = client.get(f"/api/v1/resumes/{rid}", headers=headers).json()
    assert resume["status"] == "ready" and "Python" in resume["skills"]
    _, _, bid, results = screen(client, headers)
    assert len(results) == 3
    result = next(r for r in results if r["resume_id"] == rid)
    assert result["requirement_evidence_coverage"] == 100
    assert result["semantic_similarity"] is None and result["dataset_fit_prediction"] is None
    sections = {s["id"]: s["text"] for s in resume["sections"]}
    for requirement in result["requirements"]:
        for e in requirement["supporting_evidence"]:
            assert sections[e["section_id"]] == e["excerpt"]
    review = client.post(
        f"/api/v1/screening-results/{result['id']}/reviews",
        headers=headers,
        json={"decision": "follow_up", "notes": "Ask about API testing"},
    )
    assert review.status_code == 201
    assert "evidence_coverage" in client.get(f"/api/v1/screening-batches/{bid}/export", headers=headers).text
    with Session() as db:
        from app.config import settings

        path = settings.storage_dir / db.get(Resume, rid).object_key
    assert path.exists()
    assert client.delete(f"/api/v1/resumes/{rid}", headers=headers).status_code == 204
    assert not path.exists()
    assert client.get(f"/api/v1/screening-results/{result['id']}", headers=headers).status_code == 404
    with Session() as db:
        assert not db.scalars(select(Section).where(Section.resume_id == rid)).all()
        assert not db.scalars(select(Review).where(Review.result_id == result["id"])).all()


def test_cross_tenant_access_blocks_all_resource_types(client, headers):
    job, resumes, bid, results = screen(client, headers)
    with Session() as db:
        other = Organization(id=uid(), name="Other tenant")
        db.add(other)
        db.commit()
    hostile = {**headers, "X-Organization-ID": other.id}
    assert client.get("/api/v1/jobs", headers=hostile).status_code == 401
    # Give the demo user a legitimate second membership; known IDs still cannot cross tenants.
    user_id = client.get("/api/v1/me", headers=headers).json()["user_id"]
    org_id = client.get("/api/v1/me", headers=headers).json()["organization_id"]
    with Session() as db:
        db.add(Membership(user_id=user_id, organization_id=other.id, role="admin"))
        db.commit()
    for path in [
        f"/jobs/{job['id']}",
        f"/resumes/{resumes[0]['id']}",
        f"/screening-batches/{bid}",
        f"/screening-results/{results[0]['id']}",
        f"/screening-batches/{bid}/export",
    ]:
        assert client.get("/api/v1" + path, headers=hostile).status_code == 404
    assert (
        client.post(
            f"/api/v1/jobs/{job['id']}/screenings", headers=hostile, json={"resume_ids": [resumes[0]["id"]]}
        ).status_code
        == 404
    )
    assert client.get("/api/v1/jobs", headers={**headers, "X-Organization-ID": org_id}).status_code == 200


def test_correction_invalidates_old_evidence(client, headers):
    _, resumes, bid, results = screen(client, headers)
    rid = resumes[0]["id"]
    response = client.patch(
        f"/api/v1/resumes/{rid}/corrections", headers=headers, json={"text": "Corrected React experience"}
    )
    assert response.status_code == 200 and response.json()["revision"] == 2
    assert all(
        r["resume_id"] != rid for r in client.get(f"/api/v1/screening-batches/{bid}/results", headers=headers).json()
    )


def test_job_crud_and_weight_validation(client, headers):
    body = {
        "title": "Test opportunity",
        "description": "Synthetic role",
        "requirements": [{"text": "C++", "weight": 2}],
    }
    response = client.post("/api/v1/jobs", headers=headers, json=body)
    assert response.status_code == 201
    jid = response.json()["id"]
    body["title"] = "Updated opportunity"
    assert client.patch(f"/api/v1/jobs/{jid}", headers=headers, json=body).json()["title"] == "Updated opportunity"
    body["requirements"][0]["weight"] = 0
    assert client.post("/api/v1/jobs", headers=headers, json=body).status_code == 422
    assert client.delete(f"/api/v1/jobs/{jid}", headers=headers).status_code == 204


def test_parser_boundaries_and_skill_distinctions(client, headers):
    assert skills("C++ C# NoSQL Node.js") == ["NoSQL", "C++", "C#", "Node.js"]
    assert skills("C SQL .NET") == ["SQL", "C", ".NET"]
    assert parse(docx("SYNTHETIC Python evidence"), "test.docx")[0]["text"] == "SYNTHETIC Python evidence"
    assert client.post("/api/v1/resumes", headers=headers, files={"file": ("evil.pdf", b"fake")}).status_code == 422
    import pytest

    with pytest.raises(ValueError):
        validate_file(b"x" * (10 * 1024 * 1024 + 1), "huge.pdf")
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(output)
    with pytest.raises(ValueError, match="OCR"):
        parse(output.getvalue(), "scan.pdf")


def test_conservative_matching():
    reqs = [{"id": "r", "text": "5 years Python experience", "kind": "experience", "weight": 1, "required": True}]
    section = Section(id="s", resume_id="c", text="Used Python in one class", page=1, start=0, end=24)
    result = match(reqs, [section])
    assert result["requirements"][0]["decision"] != "supported"
    assert match([], [section])["requirement_evidence_coverage"] == 0
    reqs[0].update(kind="skill", text="Python")
    section.text = "No Python experience"
    assert match(reqs, [section])["requirements"][0]["decision"] != "supported"
    assert match(reqs, [section])["requirement_evidence_coverage"] == 0


def test_production_fails_closed(monkeypatch):
    from app.config import Settings
    import pytest

    with pytest.raises(RuntimeError, match="OIDC"):
        Settings(app_env="production", oidc_issuer="", oidc_audience="", oidc_jwks_url="").validate_runtime()
