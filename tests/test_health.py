from fastapi.testclient import TestClient

from app.api.routes import create_app
from app.database.db import Database


def test_health_reports_database_failure_without_leaking_details(tmp_path, monkeypatch):
    database = Database(tmp_path / "health.sqlite3")
    database.initialize()
    client = TestClient(create_app(database))

    def fail_connect():
        raise RuntimeError("private connection details")

    monkeypatch.setattr(database, "connect", fail_connect)
    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert response.json()["database"] == "unavailable"
    assert "private connection details" not in response.text
