import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from app.config import settings
from app.db import Membership, Session, User


@dataclass
class Identity:
    user_id: str
    organization_id: str
    role: str
    scopes: set[str]


def verify_token(token: str, org: str | None = None) -> Identity:
    try:
        if settings.app_env == "production":
            key = jwt.PyJWKClient(settings.oidc_jwks_url).get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=settings.oidc_issuer,
                audience=settings.oidc_audience,
                options={"require": ["exp", "sub", "iss", "aud"]},
            )
        else:
            claims = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=["HS256"],
                audience="joldinaw",
                issuer="joldinaw-dev",
                options={"require": ["exp", "sub", "iss", "aud"]},
            )
        with Session() as db:
            user = db.scalar(select(User).where(User.subject == claims["sub"]))
            if not user:
                raise ValueError("Unknown subject")
            memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
            member = (
                next((m for m in memberships if m.organization_id == org), None)
                if org
                else (memberships[0] if len(memberships) == 1 else None)
            )
            if not member:
                raise ValueError("Organization membership required")
            return Identity(user.id, member.organization_id, member.role, set(claims.get("scope", "").split()))
    except Exception as exc:
        raise HTTPException(401, "Invalid session or organization membership") from exc


def identity(authorization: str = Header(default=""), x_organization_id: str | None = Header(default=None)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in required")
    who = verify_token(authorization[7:], x_organization_id)
    if "read" not in who.scopes:
        raise HTTPException(403, "Read permission required")
    return who


def workspace_reader(who: Identity = Depends(identity)):
    if who.role not in {"admin", "recruiter", "viewer"}:
        raise HTTPException(403, "Recruiting workspace access required")
    return who


def writer(who: Identity = Depends(identity)):
    if who.role not in {"admin", "recruiter"} or "write" not in who.scopes:
        raise HTTPException(403, "Write permission required")
    return who


def demo_token(password: str):
    if settings.app_env != "development" or not settings.demo_password:
        raise HTTPException(404, "Demo login disabled")
    if not secrets.compare_digest(password, settings.demo_password):
        raise HTTPException(401, "Invalid credentials")
    return jwt.encode(
        {
            "sub": "demo-recruiter",
            "iss": "joldinaw-dev",
            "aud": "joldinaw",
            "scope": "read write mcp:read",
            "exp": datetime.now(timezone.utc) + timedelta(hours=2),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
