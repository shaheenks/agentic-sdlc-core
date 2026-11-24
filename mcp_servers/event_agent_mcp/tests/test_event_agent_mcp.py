from event_agent_mcp import SERVICE, create_app
from starlette.testclient import TestClient


def test_healthz():
    response = TestClient(create_app()).get("/healthz")
    assert response.status_code == 200
    assert response.json()["service"] == SERVICE
