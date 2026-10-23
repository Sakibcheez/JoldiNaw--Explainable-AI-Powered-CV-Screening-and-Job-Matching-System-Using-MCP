import os
import tempfile
from pathlib import Path

# Isolated test database; never point tests at application data.
root = Path(tempfile.mkdtemp(prefix="joldinaw-test-"))
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite:///" + str(root / "test.db"))
os.environ["APP_ENV"] = "development"
os.environ["JWT_SECRET"] = "test-secret-at-least-32-characters-long"
os.environ["DEMO_PASSWORD"] = "test-password"
os.environ["STORAGE_DIR"] = str(root / "files")
os.environ["TASK_MODE"] = "inline"

import pytest
from fastapi.testclient import TestClient
from app.db import Base, Session, engine
from app.main import app, requests_by_ip
from scripts.seed_demo import seed


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    requests_by_ip.clear()
    seed()
    yield
    with Session() as db:
        db.rollback()


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def headers(client):
    response = client.post("/api/v1/auth/demo", json={"password": "test-password"})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}
