"""Regression tests for optional V1 segmentation observations."""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.mark.parametrize("status,available,fragment", [
    ("not_started", False, "尚未启动分割"),
    ("running", False, "分割正在进行"),
    ("succeeded", True, "分割已完成"),
    ("succeeded", False, "尚无可用结果"),
    ("failed", False, "尚无可用结果"),
    ("failed", True, "已有可用分割结果"),
])
def test_segmentation_observations(status, available, fragment):
    with TestClient(app) as client:
        response = client.post("/agent/guide", json={"state": {
            "ct_loaded": True, "segmentation_status": status,
            "segmentation_result_available": available,
        }})
    assert response.status_code == 200
    assert fragment in response.json()["message"]
    assert response.json()["next_action"] == "open_annulus_plane"


def test_missing_ct_has_priority():
    with TestClient(app) as client:
        response = client.post("/agent/guide", json={"state": {
            "segmentation_status": "succeeded", "segmentation_result_available": True,
        }})
    assert response.json() == {"message": "请先导入 CT 影像。", "next_action": "open_ct_import"}


@pytest.mark.parametrize("fields", [
    {"segmentation_status": "done"}, {"segmentation_status": 1},
    {"segmentation_result_available": "true"},
])
def test_invalid_segmentation_fields(fields):
    with TestClient(app) as client:
        assert client.post("/agent/guide", json={"state": fields}).status_code == 422


@pytest.mark.parametrize("status", [None, "not_started", "running", "succeeded", "failed"])
@pytest.mark.parametrize("available", [False, True])
@pytest.mark.parametrize("annulus,measurement,expected_action", [
    (False, False, "open_annulus_plane"),
    (False, True, "open_annulus_plane"),
    (True, False, "open_measurement"),
    (True, True, None),
])
def test_segmentation_keeps_navigation_priority(status, available, annulus, measurement, expected_action):
    with TestClient(app) as client:
        response = client.post("/agent/guide", json={"state": {
            "ct_loaded": True, "annulus_plane_confirmed": annulus,
            "measurement_completed": measurement, "segmentation_status": status,
            "segmentation_result_available": available,
        }})
    assert response.status_code == 200
    assert response.json()["next_action"] == expected_action
    assert set(response.json()) == {"message", "next_action"}


def test_sequence_has_no_stale_server_state():
    with TestClient(app) as client:
        for status, available, text in [
            ("running", False, "分割正在进行"),
            ("failed", False, "本次分割失败"),
            ("running", False, "分割正在进行"),
            ("succeeded", True, "分割已完成"),
        ]:
            response = client.post("/agent/guide", json={"state": {
                "ct_loaded": True, "segmentation_status": status,
                "segmentation_result_available": available,
            }})
            assert response.status_code == 200
            assert text in response.json()["message"]
