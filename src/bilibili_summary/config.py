from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


@dataclass(frozen=True)
class Settings:
    rss_feed_url: str
    db_path: Path
    download_dir: Path
    bilibili_user_agent: str
    bilibili_referer: str
    stt_base_url: str
    stt_model: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    wallabag_base_url: str
    wallabag_client_id: str
    wallabag_client_secret: str
    wallabag_username: str
    wallabag_password: str
    watch_later_url: str | None
    watch_later_token: str | None
    keep_audio_files: bool
    log_level: str

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "Settings":
        if load_dotenv:
            load_dotenv(env_file or ".env")
        return cls(
            rss_feed_url=_required("RSS_FEED_URL"),
            db_path=Path(os.getenv("DB_PATH", "data/bilibili_summary.sqlite3")),
            download_dir=Path(os.getenv("DOWNLOAD_DIR", "data/downloads")),
            bilibili_user_agent=os.getenv("BILIBILI_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"),
            bilibili_referer=os.getenv("BILIBILI_REFERER", "https://www.bilibili.com"),
            stt_base_url=_required("STT_BASE_URL"),
            stt_model=os.getenv("STT_MODEL", "deepdml/faster-whisper-large-v3-turbo-ct2"),
            llm_base_url=os.getenv("LLM_BASE_URL", ""),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", "glm-5"),
            wallabag_base_url=os.getenv("WALLABAG_BASE_URL", ""),
            wallabag_client_id=os.getenv("WALLABAG_CLIENT_ID", ""),
            wallabag_client_secret=os.getenv("WALLABAG_CLIENT_SECRET", ""),
            wallabag_username=os.getenv("WALLABAG_USERNAME", ""),
            wallabag_password=os.getenv("WALLABAG_PASSWORD", ""),
            watch_later_url=os.getenv("WATCH_LATER_URL"),
            watch_later_token=os.getenv("WATCH_LATER_TOKEN"),
            keep_audio_files=_bool_env("KEEP_AUDIO_FILES", default=False),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
