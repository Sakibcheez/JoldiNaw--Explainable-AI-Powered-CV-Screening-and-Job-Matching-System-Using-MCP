"""Explicit synthetic demo seed. Run after migrations; safe to repeat."""

import io
from docx import Document
from sqlalchemy import select
from app.config import settings
from app.db import Job, Membership, Organization, Resume, Session, User, uid
from app.schemas import Requirement
from app.services import requirements_data
from app.tasks import execute


def seed():
    if settings.app_env != "development":
        raise RuntimeError("Demo seeding is development-only")
    with Session() as db:
        user = db.scalar(select(User).where(User.subject == "demo-recruiter"))
        if user:
            return
        org, user = Organization(id=uid(), name="Northstar Demo"), User(id=uid(), subject="demo-recruiter")
        db.add_all([org, user])
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=org.id, role="admin"))
        db.add(
            Job(
                organization_id=org.id,
                title="Backend Engineer",
                description="Build reliable Python APIs and data services.",
                requirements=requirements_data(
                    [
                        Requirement(text="Python", weight=3),
                        Requirement(text="SQL", weight=2),
                        Requirement(text="Docker", required=False),
                    ]
                ),
            )
        )
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        ids = []
        for name, text in [
            (
                "synthetic-backend",
                "SYNTHETIC SAMPLE\nProjects\nBuilt Python and FastAPI services using SQL and Docker.\nTested REST APIs with pytest.",
            ),
            (
                "synthetic-frontend",
                "SYNTHETIC SAMPLE\nProjects\nDeveloped accessible React and TypeScript interfaces.\nCollaborated using Git.",
            ),
        ]:
            doc = Document()
            for line in text.splitlines():
                doc.add_paragraph(line)
            out = io.BytesIO()
            doc.save(out)
            resume = Resume(id=uid(), organization_id=org.id, filename=name + ".docx", object_key=uid() + ".docx")
            (settings.storage_dir / resume.object_key).write_bytes(out.getvalue())
            db.add(resume)
            ids.append(resume.id)
        db.commit()
        for rid in ids:
            execute("parse", rid, org.id)


if __name__ == "__main__":
    seed()
