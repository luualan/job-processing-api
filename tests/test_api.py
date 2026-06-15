import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app import models, db
from app.queue import queue as job_queue

# Use an in-memory SQLite database for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
# Use StaticPool so the in-memory SQLite database persists across connections used by SQLAlchemy
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
models.Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def reset_db():
    """Drop and recreate tables before each test to guarantee isolation."""
    # Reset DB and in-memory queue between tests
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    job_queue.clear()
    yield
    models.Base.metadata.drop_all(bind=engine)


def override_get_db():
    db_session = TestingSessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()


app.dependency_overrides[db.get_db] = override_get_db
client = TestClient(app)


def _get_type_field(obj):
    return obj.get("type") or obj.get("job_type")


def test_create_and_get_job():
    resp = client.post("/jobs", json={"type": "import", "payload": {"x": 1}, "priority": 2})
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert _get_type_field(data) == "import"

    job_id = data["id"]
    r2 = client.get(f"/jobs/{job_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == job_id


def test_list_jobs_and_filter():
    # create two jobs
    client.post("/jobs", json={"type": "t1", "payload": {}, "priority": 0})
    client.post("/jobs", json={"type": "t2", "payload": {}, "priority": 0})

    r = client.get("/jobs")
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list)
    assert len(arr) >= 2

    # filter by status
    r2 = client.get("/jobs", params={"status": "PENDING"})
    assert r2.status_code == 200
    for j in r2.json():
        assert j["status"] == "PENDING"


def test_process_job_and_prevent_reprocess():
    resp = client.post("/jobs", json={"type": "proc", "payload": {}, "priority": 0})
    job = resp.json()
    job_id = job["id"]

    p = client.post(f"/jobs/{job_id}/process")
    assert p.status_code == 200
    data = p.json()
    # now the job should be claimed and be RUNNING
    assert data["status"] == "RUNNING"

    # attempting to process again should fail with 400 (only pending can be claimed)
    p2 = client.post(f"/jobs/{job_id}/process")
    assert p2.status_code == 400


def test_fail_job():
    resp = client.post("/jobs", json={"type": "tofail", "payload": {}, "priority": 0})
    job = resp.json()
    job_id = job["id"]

    f = client.post(f"/jobs/{job_id}/fail", params={"reason": "broken"})
    assert f.status_code == 200
    data = f.json()
    assert data["status"] == "FAILED"
    # result may contain reason
    assert data.get("result") is not None

    # failing again should return 400
    f2 = client.post(f"/jobs/{job_id}/fail")
    assert f2.status_code == 400


def test_summary_route():
    # create a predictable set
    client.post("/jobs", json={"type": "s1", "payload": {}, "priority": 0})
    client.post("/jobs", json={"type": "s2", "payload": {}, "priority": 0})
    r = client.get("/jobs/summary")
    assert r.status_code == 200
    data = r.json()
    # ensure keys exist
    assert "pending" in data or "PENDING" in data


def test_not_found_returns_404():
    r = client.get("/jobs/nonexistent-id")
    assert r.status_code == 404


def test_complete_job_success():
    resp = client.post("/jobs", json={"type": "to_complete", "payload": {}, "priority": 0})
    job = resp.json()
    job_id = job["id"]

    p = client.post(f"/jobs/{job_id}/process")
    assert p.status_code == 200

    c = client.post(f"/jobs/{job_id}/complete", json={"result": {"message": "ok"}})
    assert c.status_code == 200
    data = c.json()
    assert data["status"] == "COMPLETED"
    assert data.get("result") is not None
    assert data["result"].get("message") == "ok"


def test_complete_job_requires_running():
    resp = client.post("/jobs", json={"type": "not_running", "payload": {}, "priority": 0})
    job = resp.json()
    job_id = job["id"]

    # attempting to complete a PENDING job should return 400
    c = client.post(f"/jobs/{job_id}/complete", json={"result": {"x": 1}})
    assert c.status_code == 400


def test_complete_job_cannot_complete_failed():
    resp = client.post("/jobs", json={"type": "will_fail", "payload": {}, "priority": 0})
    job = resp.json()
    job_id = job["id"]

    f = client.post(f"/jobs/{job_id}/fail", params={"reason": "err"})
    assert f.status_code == 200

    c = client.post(f"/jobs/{job_id}/complete", json={"result": {}})
    assert c.status_code == 400
