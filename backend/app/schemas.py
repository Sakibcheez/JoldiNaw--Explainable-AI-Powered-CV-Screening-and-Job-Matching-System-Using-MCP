from typing import Literal
from pydantic import BaseModel, Field


class Requirement(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    kind: Literal["skill", "experience", "education", "license", "other"] = "skill"
    canonical_skill: str | None = Field(default=None, max_length=100)
    required: bool = True
    weight: float = Field(default=1, gt=0, le=100)


class JobInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=30000)
    status: Literal["open", "closed"] = "open"
    requirements: list[Requirement] = Field(min_length=1, max_length=100)


class Correction(BaseModel):
    text: str = Field(min_length=1, max_length=100000)


class ScreeningInput(BaseModel):
    resume_ids: list[str] = Field(min_length=1, max_length=50)


class ReviewInput(BaseModel):
    decision: Literal["reviewed", "follow_up", "shortlist", "hold"]
    notes: str = Field(default="", max_length=10000)


class Login(BaseModel):
    password: str = Field(max_length=200)


class OidcExchange(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    code_verifier: str = Field(pattern=r"^[A-Za-z0-9._~-]{43,128}$")
