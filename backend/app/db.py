import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from pgvector.sqlalchemy import Vector
from app.config import settings


class Base(DeclarativeBase):
    pass


def uid():
    return str(uuid.uuid4())


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Organization(Record, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(200))


class User(Record, Base):
    __tablename__ = "users"
    subject: Mapped[str] = mapped_column(String(300), unique=True)


class Membership(Base):
    __tablename__ = "memberships"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(30), default="recruiter")


class Owned(Record):
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)


class Job(Owned, Base):
    __tablename__ = "jobs"
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="open")
    requirements: Mapped[list] = mapped_column(JSON, default=list)


class Resume(Owned, Base):
    __tablename__ = "resumes"
    filename: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    revision: Mapped[int] = mapped_column(default=1)


class Section(Record, Base):
    __tablename__ = "resume_sections"
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    page: Mapped[int] = mapped_column(default=1)
    start: Mapped[int] = mapped_column(default=0)
    end: Mapped[int] = mapped_column(default=0)
    embedding: Mapped[list | None] = mapped_column(Vector(384).with_variant(JSON, "sqlite"), nullable=True)


class Processing(Owned, Base):
    __tablename__ = "processing_jobs"
    resource_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Batch(Owned, Base):
    __tablename__ = "screening_batches"
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    resume_ids: Mapped[list] = mapped_column(JSON)
    requirement_snapshot: Mapped[list] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Result(Owned, Base):
    __tablename__ = "screening_results"
    batch_id: Mapped[str] = mapped_column(ForeignKey("screening_batches.id", ondelete="CASCADE"), index=True)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class Review(Owned, Base):
    __tablename__ = "human_reviews"
    result_id: Mapped[str] = mapped_column(ForeignKey("screening_results.id", ondelete="CASCADE"))
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(30))
    notes: Mapped[str] = mapped_column(Text)


class Audit(Owned, Base):
    __tablename__ = "audit_events"
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(36))


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    **({"connect_args": {"check_same_thread": False}} if settings.database_url.startswith("sqlite") else {}),
)
if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def sqlite_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")


Session = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with Session() as db:
        yield db
