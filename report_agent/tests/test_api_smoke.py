"""接口冒烟：装了 fastapi/httpx 才跑，没装自动跳过。"""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from ra import api  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    api._state.clear()
    return TestClient(api.app)


def test_health_before_bootstrap(client: TestClient):
    body = client.get("/health").json()
    assert body["ok"] is True
    assert body["ready"] is False


def test_stream_auto_bootstraps_and_answers(client: TestClient):
    with client.stream(
        "POST", "/chat/stream", json={"question": "逾期账龄怎么统计", "user_id": "smoke"}
    ) as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())

    assert "event: state" in text or "event: cache" in text
    assert "event: done" in text
    assert "data:" in text
    assert client.get("/health").json()["ready"] is True


def test_empty_question_still_returns_stream(client: TestClient):
    with client.stream("POST", "/chat/stream", json={"question": ""}) as response:
        assert response.status_code == 200
