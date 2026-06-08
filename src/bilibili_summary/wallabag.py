from __future__ import annotations

import httpx

from .models import SummaryResult, VideoMetadata


class WallabagClient:
    def __init__(self, base_url: str, client_id: str, client_secret: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self._token: str | None = None

    def token(self) -> str:
        if not all([self.base_url, self.client_id, self.client_secret, self.username, self.password]):
            raise RuntimeError("Wallabag credentials are required for real archive operations")
        if self._token:
            return self._token
        resp = httpx.post(
            f"{self.base_url}/oauth/v2/token",
            data={
                "grant_type": "password",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "username": self.username,
                "password": self.password,
            },
            timeout=30,
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        return self._token

    def create_entry(self, metadata: VideoMetadata, summary: SummaryResult, dry_run: bool = True) -> str:
        content = (
            f'<img src="{metadata.cover_url or ""}" referrerpolicy="no-referrer" style="max-width: 100%; height: auto;" />'
            "<br>"
            f'视频原地址：<a href="https://www.bilibili.com/video/{metadata.bvid}">https://www.bilibili.com/video/{metadata.bvid}</a>'
            "<br><br>"
            f"{summary.ai_html_content}"
        )
        payload = {
            "url": f"https://www.bilibili.com/video/{metadata.bvid}",
            "title": summary.ai_title,
            "content": content,
            "tags": summary.tags,
            "authors": metadata.owner_name or "",
        }
        if dry_run:
            return "dry-run"
        resp = httpx.post(
            f"{self.base_url}/api/entries",
            headers={"Authorization": f"Bearer {self.token()}", "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        return str(resp.json().get("id", "created"))
