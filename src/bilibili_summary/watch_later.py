from __future__ import annotations

import httpx


class WatchLaterClient:
    def __init__(self, url: str | None, token: str | None):
        self.url = url
        self.token = token

    def add(self, bvid: str, dry_run: bool = True) -> str:
        if not self.url:
            return "not-configured"
        if dry_run:
            return "dry-run"
        headers = {"X-Api-Token": self.token} if self.token else {}
        resp = httpx.get(self.url, params={"bvid": bvid}, headers=headers, timeout=30)
        resp.raise_for_status()
        return "added"
