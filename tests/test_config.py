from pathlib import Path

import pytest

from bilibili_summary.config import Settings


def test_settings_requires_stt_base_url(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("RSS_FEED_URL=https://rss.example/feed\n", encoding="utf-8")
    monkeypatch.delenv("STT_BASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="STT_BASE_URL"):
        Settings.from_env(env_file)


def test_settings_loads_required_public_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "RSS_FEED_URL=https://rss.example/feed",
                "STT_BASE_URL=https://stt.example/v1",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("RSS_FEED_URL", raising=False)
    monkeypatch.delenv("STT_BASE_URL", raising=False)

    settings = Settings.from_env(env_file)

    assert settings.rss_feed_url == "https://rss.example/feed"
    assert settings.stt_base_url == "https://stt.example/v1"
    assert settings.db_path == Path("data/bilibili_summary.sqlite3")
