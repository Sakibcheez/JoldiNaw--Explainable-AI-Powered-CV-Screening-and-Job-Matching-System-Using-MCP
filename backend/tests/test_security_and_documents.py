import io
import zipfile
import jwt
import pytest
import httpx
from datetime import datetime, timedelta, timezone
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import select
from app.config import settings
from app.db import Membership, Resume, Session, User
from app.documents import parse, validate_file
from app.tasks import execute


def test_extract_known_synthetic_pdf():
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 40 700 Td (SYNTHETIC Python API project) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    result = parse(output.getvalue(), "synthetic.pdf")
    assert "SYNTHETIC Python API project" in result[0]["text"]
    assert result[0]["page"] == 1 and result[0]["start"] == 0


def test_docx_zip_expansion_is_bounded():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"x" * (31 * 1024 * 1024))
    with pytest.raises(ValueError, match="Expanded"):
        validate_file(output.getvalue(), "bomb.docx")


def test_expired_and_wrong_audience_tokens_fail(client):
    for expired, audience in [(True, "joldinaw"), (False, "other-app")]:
        token = jwt.encode(
            {
                "sub": "demo-recruiter",
                "iss": "joldinaw-dev",
                "aud": audience,
                "exp": datetime.now(timezone.utc) + timedelta(hours=-1 if expired else 1),
                "scope": "read write",
            },
            settings.jwt_secret,
            algorithm="HS256",
        )
        assert client.get("/api/v1/jobs", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_viewer_role_cannot_mutate_even_with_write_scope(client, headers):
    with Session() as db:
        user = db.scalar(select(User).where(User.subject == "demo-recruiter"))
        member = db.scalar(select(Membership).where(Membership.user_id == user.id))
        member.role = "viewer"
        db.commit()
    assert (
        client.post(
            "/api/v1/jobs",
            headers=headers,
            json={"title": "Forbidden", "description": "test", "requirements": [{"text": "Python"}]},
        ).status_code
        == 403
    )


def test_user_role_cannot_read_recruiting_records(client, headers):
    with Session() as db:
        user = db.scalar(select(User).where(User.subject == "demo-recruiter"))
        member = db.scalar(select(Membership).where(Membership.user_id == user.id))
        member.role = "user"
        db.commit()
    assert client.get("/api/v1/me", headers=headers).status_code == 200
    assert client.get("/api/v1/jobs", headers=headers).status_code == 403
    assert client.get("/api/v1/resumes", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/jobs",
        headers=headers,
        json={"title": "Forbidden", "description": "test", "requirements": [{"text": "Python"}]},
    ).status_code == 403


def test_oidc_config_and_pkce_exchange_use_server_discovery(client, monkeypatch):
    monkeypatch.setattr(settings, "oidc_issuer", "https://identity.example/tenant")
    monkeypatch.setattr(settings, "oidc_client_id", "spa-client")
    monkeypatch.setattr(settings, "oidc_redirect_uri", "http://localhost:5173/auth/callback")
    monkeypatch.setattr(settings, "oidc_scopes", "openid read write")
    document = {
        "issuer": settings.oidc_issuer,
        "authorization_endpoint": "https://identity.example/authorize",
        "token_endpoint": "https://identity.example/token",
    }
    monkeypatch.setattr(
        "app.main.httpx.get",
        lambda *args, **kwargs: httpx.Response(200, json=document, request=httpx.Request("GET", args[0])),
    )
    config = client.get("/api/v1/auth/oidc/config")
    assert config.status_code == 200
    assert config.json()["client_id"] == "spa-client"
    assert config.json()["redirect_uri"] == settings.oidc_redirect_uri

    request_data = {}

    def exchange(url, *, data, **kwargs):
        request_data.update(data)
        return httpx.Response(200, json={"access_token": "signed-by-provider"}, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.main.httpx.post", exchange)
    response = client.post(
        "/api/v1/auth/oidc/token",
        json={"code": "authorization-code", "code_verifier": "a" * 43},
    )
    assert response.status_code == 200
    assert response.json() == {"access_token": "signed-by-provider", "token_type": "bearer"}
    assert request_data == {
        "grant_type": "authorization_code",
        "client_id": "spa-client",
        "code": "authorization-code",
        "redirect_uri": settings.oidc_redirect_uri,
        "code_verifier": "a" * 43,
    }


def test_oidc_exchange_rejects_invalid_pkce_verifier(client):
    response = client.post("/api/v1/auth/oidc/token", json={"code": "code", "code_verifier": "short"})
    assert response.status_code == 422


def test_background_task_rechecks_tenant_and_is_idempotent():
    with Session() as db:
        resume = db.scalar(select(Resume))
        rid, org = resume.id, resume.organization_id
    execute("parse", rid, "wrong-org")
    execute("parse", rid, org)
    with Session() as db:
        assert db.get(Resume, rid).status == "ready"


def test_read_scope_required(client):
    token = jwt.encode(
        {
            "sub": "demo-recruiter",
            "iss": "joldinaw-dev",
            "aud": "joldinaw",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "scope": "mcp:read",
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    assert client.get("/api/v1/resumes", headers={"Authorization": "Bearer " + token}).status_code == 403
