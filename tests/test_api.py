from pathlib import Path

from fastapi.testclient import TestClient

from bilibili_summary.api import create_app
from bilibili_summary.config import Settings


def make_settings(tmp_path: Path, token: str | None = "secret-token") -> Settings:
    return Settings(
        rss_feed_url="https://rss.example/feed",
        db_path=tmp_path / "data" / "db.sqlite3",
        download_dir=tmp_path / "data" / "downloads",
        bilibili_user_agent="TestAgent",
        bilibili_referer="https://www.bilibili.com",
        stt_base_url="https://stt.example/v1",
        stt_model="stt",
        llm_base_url="",
        llm_api_key="",
        llm_model="llm",
        wallabag_base_url="",
        wallabag_client_id="",
        wallabag_client_secret="",
        wallabag_username="",
        wallabag_password="",
        watch_later_url=None,
        watch_later_token=None,
        keep_audio_files=False,
        log_level="INFO",
        api_token=token,
    )


def test_health_does_not_require_token(tmp_path):
    client = TestClient(create_app(make_settings(tmp_path)))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_process_requires_bearer_token(tmp_path):
    client = TestClient(create_app(make_settings(tmp_path)))

    response = client.post("/api/videos/process", json={"video": "BV1xx411c7mD"})
    assert response.status_code == 401

    response = client.post(
        "/api/videos/process",
        headers={"Authorization": "Bearer wrong"},
        json={"video": "BV1xx411c7mD"},
    )
    assert response.status_code == 401


def test_process_enqueues_video(tmp_path):
    client = TestClient(create_app(make_settings(tmp_path)))

    response = client.post(
        "/api/videos/process",
        headers={"Authorization": "Bearer secret-token"},
        json={"video": "https://www.bilibili.com/video/BV1xx411c7mD"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == 1
    assert payload["bvid"] == "BV1xx411c7mD"
    assert payload["created"] is True
    assert payload["status"] == "discovered"


def test_process_rejects_invalid_video(tmp_path):
    client = TestClient(create_app(make_settings(tmp_path)))

    response = client.post(
        "/api/videos/process",
        headers={"Authorization": "Bearer secret-token"},
        json={"video": "not a bvid"},
    )

    assert response.status_code == 400


def test_process_requires_configured_token(tmp_path):
    client = TestClient(create_app(make_settings(tmp_path, token=None)))

    response = client.post(
        "/api/videos/process",
        headers={"Authorization": "Bearer secret-token"},
        json={"video": "BV1xx411c7mD"},
    )

    assert response.status_code == 503
