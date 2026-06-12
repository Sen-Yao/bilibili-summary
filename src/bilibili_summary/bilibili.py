from __future__ import annotations

from pathlib import Path
import httpx

from .models import VideoMetadata


class BilibiliClient:
    def __init__(self, user_agent: str, referer: str):
        self.headers = {"User-Agent": user_agent, "Referer": referer}

    def get_metadata(self, bvid: str) -> VideoMetadata:
        resp = httpx.get(
            "https://api.bilibili.com/x/web-interface/view",
            params={"bvid": bvid},
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"Bilibili metadata error: {payload.get('message')}")
        data = payload["data"]
        return VideoMetadata(
            bvid=bvid,
            cid=int(data["cid"]),
            title=data.get("title") or bvid,
            cover_url=data.get("pic"),
            owner_name=(data.get("owner") or {}).get("name"),
            category_name=data.get("tname"),
            description=data.get("desc"),
            dynamic=data.get("dynamic"),
        )

    def get_audio_url(self, bvid: str, cid: int) -> str:
        resp = httpx.get(
            "https://api.bilibili.com/x/player/playurl",
            params={"bvid": bvid, "cid": cid, "fnval": 16},
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"Bilibili playurl error: {payload.get('message')}")
        audio = payload.get("data", {}).get("dash", {}).get("audio", [])
        if not audio:
            raise RuntimeError("Bilibili playurl returned no audio streams")
        return audio[0].get("baseUrl") or audio[0]["base_url"]

    def download_audio(self, url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(f"{destination.name}.part")
        if partial.exists():
            partial.unlink()
        try:
            with httpx.stream("GET", url, headers=self.headers, timeout=120) as resp:
                resp.raise_for_status()
                with partial.open("wb") as file:
                    for chunk in resp.iter_bytes():
                        file.write(chunk)
        except Exception:
            if partial.exists():
                partial.unlink()
            raise
        partial.replace(destination)
        return destination
