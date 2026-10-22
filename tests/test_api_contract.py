from fastapi.testclient import TestClient

from app.api.routes import create_app
from app.database.db import Database


def test_openapi_lists_core_routes_and_request_schemas(tmp_path):
    database = Database(tmp_path / "api-contract.sqlite3")
    client = TestClient(create_app(database))

    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]

    assert "get" in paths["/api/health"]
    assert "get" in paths["/api/tasks"]
    assert "post" in paths["/api/tasks"]
    assert "post" in paths["/api/imports/backup"]
    assert "post" in paths["/api/doubts/solve"]
    assert "get" in paths["/api/calendar"]

    create_task_operation = paths["/api/tasks"]["post"]
    request_schema_ref = create_task_operation["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"]
    request_schema_name = request_schema_ref.rsplit("/", maxsplit=1)[1]
    request_schema = schema["components"]["schemas"][request_schema_name]
    assert {"title"}.issubset(request_schema["required"])
