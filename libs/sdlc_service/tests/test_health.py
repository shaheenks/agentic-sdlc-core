from sdlc_service import health_routes
from starlette.applications import Starlette
from starlette.testclient import TestClient


def test_healthz_names_the_service():
    client = TestClient(Starlette(routes=health_routes("svc")))
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"service": "svc", "status": "ok"}
