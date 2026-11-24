from starlette.testclient import TestClient

from event_gateway import SERVICE, create_app


def test_healthz():
    response = TestClient(create_app()).get("/healthz")
    assert response.status_code == 200
    assert response.json()["service"] == SERVICE
