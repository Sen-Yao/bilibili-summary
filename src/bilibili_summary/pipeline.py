from __future__ import annotations

import json
import httpx

from .bilibili import BilibiliClient
from .config import Settings
from .llm import LLMClient
from .models import JobStatus, VideoMetadata
from .rss import parse_feed
from .store import JobStore
from .stt import STTClient
from .wallabag import WallabagClient
from .watch_later import WatchLaterClient


class Pipeline:
    def __init__(self, settings: Settings, store: JobStore):
        self.settings = settings
        self.store = store
        self.bilibili = BilibiliClient(settings.bilibili_user_agent, settings.bilibili_referer)
        self.llm = LLMClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
        self.stt = STTClient(settings.stt_base_url, settings.stt_model)
        self.wallabag = WallabagClient(
            settings.wallabag_base_url,
            settings.wallabag_client_id,
            settings.wallabag_client_secret,
            settings.wallabag_username,
            settings.wallabag_password,
        )
        self.watch_later = WatchLaterClient(settings.watch_later_url, settings.watch_later_token)

    def poll_once(self, dry_run: bool = True) -> int:
        resp = httpx.get(self.settings.rss_feed_url, timeout=30)
        resp.raise_for_status()
        videos = parse_feed(resp.text)
        inserted = 0
        if dry_run:
            return len(videos)
        for video in videos:
            if self.store.upsert_discovered(video):
                inserted += 1
        return inserted

    def run_pending(self, limit: int = 5, dry_run: bool = True) -> int:
        jobs = self.store.list_by_status(JobStatus.DISCOVERED, limit=limit)
        return self._run_rows(jobs, dry_run=dry_run)

    def retry_failed(self, limit: int = 5, dry_run: bool = True) -> int:
        jobs = self.store.list_by_status(JobStatus.FAILED, limit=limit)
        return self._run_rows(jobs, dry_run=dry_run)

    def _run_rows(self, jobs: list[object], dry_run: bool = True) -> int:
        processed = 0
        for job in jobs:
            self.run_job(job["id"], job["bvid"], dry_run=dry_run)
            processed += 1
        return processed

    def run_job(self, job_id: int, bvid: str, dry_run: bool = True) -> None:
        try:
            metadata = self.bilibili.get_metadata(bvid)
            self.store.update(
                job_id,
                JobStatus.METADATA_FETCHED,
                cid=metadata.cid,
                video_title=metadata.title,
                cover_url=metadata.cover_url,
                owner_name=metadata.owner_name,
                category_name=metadata.category_name,
            )
            classification = self.llm.classify_food(metadata)
            self.store.update(job_id, JobStatus.CLASSIFIED, is_food=1 if classification.is_food else 0)
            if classification.is_food:
                result = self.watch_later.add(bvid, dry_run=dry_run)
                self.store.update(job_id, JobStatus.SKIPPED, error_message=f"watch_later={result}; reason={classification.reason}")
                return

            audio_url = self.bilibili.get_audio_url(bvid, metadata.cid)
            audio_path = self.settings.download_dir / f"{bvid}.m4a"
            if dry_run:
                self.store.update(job_id, JobStatus.AUDIO_DOWNLOADED, audio_path=str(audio_path), error_message="dry-run: audio not downloaded")
                return
            self.bilibili.download_audio(audio_url, audio_path)
            self.store.update(job_id, JobStatus.AUDIO_DOWNLOADED, audio_path=str(audio_path))

            stt_text = self.stt.transcribe(audio_path)
            self.store.update(job_id, JobStatus.TRANSCRIBED, stt_text=stt_text)

            summary = self.llm.summarize(metadata, stt_text)
            self.store.update(
                job_id,
                JobStatus.SUMMARIZED,
                ai_title=summary.ai_title,
                ai_html_content=summary.ai_html_content,
                tags_json=json.dumps(summary.tags, ensure_ascii=False),
            )

            entry_id = self.wallabag.create_entry(metadata, summary, dry_run=dry_run)
            self.store.update(job_id, JobStatus.ARCHIVED, wallabag_entry_id=entry_id)
        except Exception as exc:
            self.store.fail(job_id, f"{type(exc).__name__}: {exc}")
