from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

from .models import FeedVideo, JobStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bvid TEXT NOT NULL UNIQUE,
  source_url TEXT NOT NULL,
  feed_guid TEXT,
  feed_title TEXT,
  published_at TEXT,
  status TEXT NOT NULL,
  retry_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  cid INTEGER,
  video_title TEXT,
  cover_url TEXT,
  owner_name TEXT,
  category_name TEXT,
  is_food INTEGER,
  audio_path TEXT,
  stt_text TEXT,
  ai_title TEXT,
  ai_html_content TEXT,
  tags_json TEXT,
  wallabag_entry_id TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
"""


class JobStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def upsert_discovered(self, video: FeedVideo) -> bool:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO jobs (bvid, source_url, feed_guid, feed_title, published_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (video.bvid, video.url, video.guid, video.title, video.published, JobStatus.DISCOVERED.value),
            )
            return cur.rowcount > 0

    def list_by_status(self, *statuses: JobStatus, limit: int = 20) -> list[sqlite3.Row]:
        values = [s.value for s in statuses]
        placeholders = ",".join("?" for _ in values)
        with self.connect() as conn:
            return list(conn.execute(
                f"SELECT * FROM jobs WHERE status IN ({placeholders}) ORDER BY id LIMIT ?",
                (*values, limit),
            ))

    def update(self, job_id: int, status: JobStatus | None = None, **fields: object) -> None:
        assignments = []
        values: list[object] = []
        if status is not None:
            assignments.append("status = ?")
            values.append(status.value)
        for key, value in fields.items():
            assignments.append(f"{key} = ?")
            values.append(value)
        assignments.append("updated_at = CURRENT_TIMESTAMP")
        values.append(job_id)
        with self.connect() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(assignments)} WHERE id = ?", values)

    def fail(self, job_id: int, message: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, retry_count = retry_count + 1, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (JobStatus.FAILED.value, message[:2000], job_id),
            )
