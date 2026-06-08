from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class JobStatus(StrEnum):
    DISCOVERED = "discovered"
    METADATA_FETCHED = "metadata_fetched"
    CLASSIFIED = "classified"
    SKIPPED = "skipped"
    AUDIO_DOWNLOADED = "audio_downloaded"
    TRANSCRIBED = "transcribed"
    SUMMARIZED = "summarized"
    ARCHIVED = "archived"
    FAILED = "failed"


@dataclass(frozen=True)
class FeedVideo:
    bvid: str
    url: str
    title: str | None = None
    guid: str | None = None
    published: str | None = None


@dataclass(frozen=True)
class VideoMetadata:
    bvid: str
    cid: int
    title: str
    cover_url: str | None
    owner_name: str | None
    category_name: str | None
    description: str | None
    dynamic: str | None


@dataclass(frozen=True)
class SummaryResult:
    ai_title: str
    ai_html_content: str
    tags: list[str]
