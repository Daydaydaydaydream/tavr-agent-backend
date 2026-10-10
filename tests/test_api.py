from itertools import product

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("ct", "annulus", "measurement"), list(product([False, True], repeat=3))
)
def test_guidance_priority_for_all_states(client, ct, annulus, measurement):
    response = client.post(
        "/agent/guide",
        json={"state": {
            "current_page": "ct_viewer", "ct_loaded": ct,
            "annulus_plane_confirmed": annulus, "measurement_completed": measurement,
        }},
    )
    expected = {
        (False, False, False): ("请先导入 CT 影像。", "open_ct_import"),
        (False, False, True): ("请先导入 CT 影像。", "open_ct_import"),
        (False, True, False): ("请先导入 CT 影像。", "open_ct_import"),
        (False, True, True): ("请先导入 CT 影像。", "open_ct_import"),
        (True, False, False): ("请进入瓣环定位模块。", "open_annulus_plane"),
        (True, False, True): ("请进入瓣环定位模块。", "open_annulus_plane"),
        (True, True, False): ("请进入瓣环测量模块。", "open_measurement"),
        (True, True, True): ("示例规划步骤已完成。", None),
    }[(ct, annulus, measurement)]
    assert response.status_code == 200
    assert response.json() == {"message": expected[0], "next_action": expected[1]}


def test_defaults(client):
    response = client.post("/agent/guide", json={"state": {}})
    assert response.status_code == 200
    assert response.json()["next_action"] == "open_ct_import"


@pytest.mark.parametrize("payload", [
    {}, {"state": None}, {"state": []},
    {"state": {"ct_loaded": "true"}}, {"state": {"ct_loaded": 1}},
    {"state": {"annulus_plane_confirmed": "false"}},
    {"state": {"measurement_completed": None}},
    {"state": {"ct_loadedd": True}}, {"state": {}, "unexpected": True},
    {"state": {"current_page": 12}}, {"state": {"current_page": ""}},
    {"state": {"current_page": "x" * 129}},
])
def test_invalid_payload_returns_422(client, payload):
    response = client.post("/agent/guide", json=payload)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_malformed_json(client):
    response = client.post("/agent/guide", content='{', headers={"Content-Type": "application/json"})
    assert response.status_code == 422


def test_page_is_context_only(client):
    response = client.post("/agent/guide", json={"state": {"current_page": "future_module"}})
    assert response.status_code == 200
    assert response.json()["next_action"] == "open_ct_import"


def test_requests_do_not_share_state(client):
    completed = client.post("/agent/guide", json={"state": {
        "ct_loaded": True, "annulus_plane_confirmed": True, "measurement_completed": True,
    }})
    assert completed.json()["next_action"] is None
    assert client.post("/agent/guide", json={"state": {}}).json()["next_action"] == "open_ct_import"


def test_openapi_contract(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "get" in schema["paths"]["/health"]
    assert "post" in schema["paths"]["/agent/guide"]
    assert schema["components"]["schemas"]["GuideRequest"]["required"] == ["state"]
    assert client.get("/docs").status_code == 200
