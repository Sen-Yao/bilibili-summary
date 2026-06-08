from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Iterable

try:
    import feedparser
except ModuleNotFoundError:  # pragma: no cover - exercised when dependency absent
    feedparser = None

from .models import FeedVideo

BV_PATTERN = re.compile(r"BV[a-zA-Z0-9]{10}")


def extract_bvid(text: str | None) -> str | None:
    if not text:
        return None
    match = BV_PATTERN.search(text)
    return match.group(0) if match else None


def parse_feed(content: str) -> list[FeedVideo]:
    if feedparser is None:
        return _parse_feed_stdlib(content)
    parsed = feedparser.parse(content)
    videos: list[FeedVideo] = []
    for entry in parsed.entries:
        candidates: Iterable[str | None] = (
            getattr(entry, "link", None),
            getattr(entry, "id", None),
            getattr(entry, "guid", None),
            getattr(entry, "title", None),
            getattr(entry, "summary", None),
        )
        bvid = next((value for value in (extract_bvid(c) for c in candidates) if value), None)
        if not bvid:
            continue
        url = getattr(entry, "link", None) or f"https://www.bilibili.com/video/{bvid}"
        videos.append(
            FeedVideo(
                bvid=bvid,
                url=url,
                title=getattr(entry, "title", None),
                guid=getattr(entry, "id", None) or getattr(entry, "guid", None),
                published=getattr(entry, "published", None),
            )
        )
    return videos


def _parse_feed_stdlib(content: str) -> list[FeedVideo]:
    root = ET.fromstring(content)
    videos: list[FeedVideo] = []
    for item in root.findall(".//item"):
        values = {child.tag.rsplit("}", 1)[-1]: child.text for child in list(item)}
        candidates: Iterable[str | None] = (
            values.get("link"),
            values.get("guid"),
            values.get("id"),
            values.get("title"),
            values.get("description"),
            values.get("summary"),
        )
        bvid = next((value for value in (extract_bvid(c) for c in candidates) if value), None)
        if not bvid:
            continue
        videos.append(
            FeedVideo(
                bvid=bvid,
                url=values.get("link") or f"https://www.bilibili.com/video/{bvid}",
                title=values.get("title"),
                guid=values.get("guid") or values.get("id"),
                published=values.get("pubDate") or values.get("published"),
            )
        )
    return videos
