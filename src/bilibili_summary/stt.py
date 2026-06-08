from __future__ import annotations

from pathlib import Path
import httpx


class STTClient:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def transcribe(self, audio_path: Path) -> str:
        with audio_path.open("rb") as file:
            resp = httpx.post(
                f"{self.base_url}/audio/transcriptions",
                files={"file": (audio_path.name, file, "application/octet-stream")},
                data={"model": self.model},
                timeout=1800,
            )
        resp.raise_for_status()
        payload = resp.json()
        text = payload.get("text")
        if not text:
            raise RuntimeError("STT response did not contain text")
        return text
