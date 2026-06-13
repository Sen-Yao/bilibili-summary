from __future__ import annotations

import json
import logging
import time
from pathlib import Path
import httpx

from .bilibili import BilibiliClient
from .config import Settings
from .llm import LLMClient
from .models import FeedVideo, JobStatus, VideoMetadata
from .rss import extract_bvid, parse_feed
from .store import JobStore
from .stt import STTClient
from .wallabag import WallabagClient
from .watch_later import WatchLaterClient

logger = logging.getLogger(__name__)


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
        videos = parse_feed(self._fetch_rss())
        logger.info("rss poll completed videos=%s dry_run=%s", len(videos), dry_run)
        inserted = 0
        if dry_run:
            return len(videos)
        for video in videos:
            if self.store.upsert_discovered(video):
                inserted += 1
        logger.info("rss poll inserted=%s", inserted)
        return inserted

    def enqueue_video(self, video: str) -> dict[str, object]:
        bvid = extract_bvid(video)
        if not bvid:
            raise ValueError(f"Could not find a BVID in: {video}")
        source_url = video if video.startswith(("http://", "https://")) else f"https://www.bilibili.com/video/{bvid}"
        job_id, created = self.store.enqueue_video(FeedVideo(bvid=bvid, url=source_url, guid=f"manual:{bvid}"))
        row = self.store.get(job_id)
        status = row["status"] if row else JobStatus.DISCOVERED.value
        logger.info("manual video enqueued id=%s bvid=%s created=%s status=%s", job_id, bvid, created, status)
        return {"job_id": job_id, "bvid": bvid, "created": created, "status": status}

    def process_video(self, video: str, dry_run: bool = True, run_now: bool = False, force: bool = False) -> dict[str, object]:
        result = self.enqueue_video(video)
        if run_now and self._should_run_manual_status(str(result["status"]), force=force):
            self.run_job(int(result["job_id"]), str(result["bvid"]), dry_run=dry_run, force=force)
            row = self.store.get(int(result["job_id"]))
            result["status"] = row["status"] if row else result["status"]
        logger.info(
            "manual video processed id=%s bvid=%s run_now=%s dry_run=%s force=%s status=%s",
            result["job_id"],
            result["bvid"],
            run_now,
            dry_run,
            force,
            result["status"],
        )
        return result

    @staticmethod
    def _should_run_manual_status(status: str, force: bool = False) -> bool:
        if force:
            return True
        return status in {
            JobStatus.DISCOVERED.value,
            JobStatus.AUDIO_DOWNLOADED.value,
            JobStatus.TRANSCRIBED.value,
            JobStatus.SUMMARIZED.value,
            JobStatus.FAILED.value,
        }

    def _fetch_rss(self, attempts: int = 3) -> str:
        last_error: Exception | None = None
        headers = {
            "User-Agent": self.settings.bilibili_user_agent,
            "Referer": self.settings.bilibili_referer,
        }
        for attempt in range(1, attempts + 1):
            try:
                resp = httpx.get(self.settings.rss_feed_url, headers=headers, timeout=30)
                resp.raise_for_status()
                return resp.text
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code not in {429, 500, 502, 503, 504} or attempt == attempts:
                    break
            except httpx.TransportError as exc:
                last_error = exc
                if attempt == attempts:
                    break
            time.sleep(2 ** (attempt - 1))
        if last_error:
            raise last_error
        raise RuntimeError("RSS fetch failed without an error")

    def run_pending(self, limit: int = 5, dry_run: bool = True) -> int:
        jobs = self.store.list_by_status(JobStatus.DISCOVERED, limit=limit)
        return self._run_rows(jobs, dry_run=dry_run)

    def retry_failed(self, limit: int = 5, dry_run: bool = True) -> int:
        jobs = self.store.list_by_status(JobStatus.FAILED, limit=limit)
        return self._run_rows(jobs, dry_run=dry_run)

    def run_resumable(self, limit: int = 5, dry_run: bool = True) -> int:
        jobs = self.store.list_by_status(
            JobStatus.DISCOVERED,
            JobStatus.AUDIO_DOWNLOADED,
            JobStatus.TRANSCRIBED,
            JobStatus.SUMMARIZED,
            limit=limit,
        )
        return self._run_rows(jobs, dry_run=dry_run)

    def _run_rows(self, jobs: list[object], dry_run: bool = True) -> int:
        processed = 0
        for job in jobs:
            self.run_job(job["id"], job["bvid"], dry_run=dry_run)
            processed += 1
        logger.info("job batch completed processed=%s dry_run=%s", processed, dry_run)
        return processed

    def run_job(self, job_id: int, bvid: str, dry_run: bool = True, force: bool = False) -> None:
        logger.info("job start id=%s bvid=%s dry_run=%s force=%s", job_id, bvid, dry_run, force)
        try:
            existing = self.store.get(job_id)
            if existing and existing["status"] == JobStatus.AUDIO_DOWNLOADED.value:
                self._transcribe_and_archive(existing, dry_run=dry_run)
                return
            if existing and existing["status"] == JobStatus.TRANSCRIBED.value:
                self._summarize_and_archive(existing, dry_run=dry_run)
                return
            if existing and existing["status"] == JobStatus.SUMMARIZED.value:
                self._archive_existing(existing, dry_run=dry_run)
                return
            metadata = self.bilibili.get_metadata(bvid)
            logger.info("metadata fetched id=%s bvid=%s title=%s", job_id, bvid, metadata.title)
            if dry_run:
                classification = self.llm.classify_food(metadata)
                if classification.is_food and not force:
                    self.watch_later.add(bvid, dry_run=True)
                    return
                self.bilibili.get_audio_url(bvid, metadata.cid)
                return
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
            logger.info("classification completed id=%s bvid=%s is_food=%s", job_id, bvid, classification.is_food)
            if classification.is_food and not force:
                result = self.watch_later.add(bvid, dry_run=dry_run)
                self.store.update(job_id, JobStatus.SKIPPED, error_message=f"watch_later={result}; reason={classification.reason}")
                logger.info("job skipped id=%s bvid=%s watch_later=%s", job_id, bvid, result)
                return
            if classification.is_food and force:
                logger.info("food classification overridden id=%s bvid=%s reason=%s", job_id, bvid, classification.reason)


            audio_url = self.bilibili.get_audio_url(bvid, metadata.cid)
            audio_path = self.settings.download_dir / f"{bvid}.m4a"
            logger.info("audio download start id=%s bvid=%s path=%s", job_id, bvid, audio_path)
            self.bilibili.download_audio(audio_url, audio_path)
            self.store.update(job_id, JobStatus.AUDIO_DOWNLOADED, audio_path=str(audio_path))
            logger.info("audio download completed id=%s bvid=%s path=%s", job_id, bvid, audio_path)
            self._transcribe_and_archive(self.store.get(job_id), dry_run=dry_run)
        except Exception as exc:
            logger.exception("job failed id=%s bvid=%s", job_id, bvid)
            self.store.fail(job_id, f"{type(exc).__name__}: {exc}")

    def _metadata_from_row(self, row: object) -> VideoMetadata:
        return VideoMetadata(
            bvid=row["bvid"],
            cid=row["cid"],
            title=row["video_title"] or row["feed_title"] or row["bvid"],
            cover_url=row["cover_url"],
            owner_name=row["owner_name"],
            category_name=row["category_name"],
            description=None,
            dynamic=None,
        )

    def _transcribe_and_archive(self, row: object | None, dry_run: bool = True) -> None:
        if row is None:
            raise RuntimeError("Cannot transcribe missing job row")
        if not row["audio_path"]:
            raise RuntimeError("Cannot transcribe job without audio_path")
        audio_path = Path(row["audio_path"])
        if not audio_path.is_absolute():
            audio_path = self.settings.db_path.parent.parent / audio_path
        logger.info("stt start id=%s bvid=%s path=%s", row["id"], row["bvid"], audio_path)
        stt_text = self.stt.transcribe(audio_path)
        self.store.update(row["id"], JobStatus.TRANSCRIBED, stt_text=stt_text)
        logger.info("stt completed id=%s bvid=%s chars=%s", row["id"], row["bvid"], len(stt_text))
        if not self.settings.keep_audio_files:
            self._delete_file(audio_path)
            logger.info("audio deleted id=%s bvid=%s path=%s", row["id"], row["bvid"], audio_path)
        self._summarize_and_archive(self.store.get(row["id"]), dry_run=dry_run)

    def _summarize_and_archive(self, row: object | None, dry_run: bool = True) -> None:
        if row is None:
            raise RuntimeError("Cannot resume missing job row")
        metadata = self._metadata_from_row(row)
        logger.info("summary start id=%s bvid=%s", row["id"], row["bvid"])
        summary = self.llm.summarize(metadata, row["stt_text"] or "")
        self.store.update(
            row["id"],
            JobStatus.SUMMARIZED,
            ai_title=summary.ai_title,
            ai_html_content=summary.ai_html_content,
            tags_json=json.dumps(summary.tags, ensure_ascii=False),
        )
        logger.info("summary completed id=%s bvid=%s title=%s", row["id"], row["bvid"], summary.ai_title)
        self._archive_existing(self.store.get(row["id"]), dry_run=dry_run)

    def _archive_existing(self, row: object | None, dry_run: bool = True) -> None:
        if row is None:
            raise RuntimeError("Cannot archive missing job row")
        metadata = self._metadata_from_row(row)
        from .models import SummaryResult

        summary = SummaryResult(row["ai_title"] or metadata.title, row["ai_html_content"] or "暂无总结", json.loads(row["tags_json"] or "[]"))
        logger.info("archive start id=%s bvid=%s dry_run=%s", row["id"], row["bvid"], dry_run)
        entry_id = self.wallabag.create_entry(metadata, summary, dry_run=dry_run)
        self.store.update(row["id"], JobStatus.ARCHIVED, wallabag_entry_id=entry_id, error_message=None)
        logger.info("archive completed id=%s bvid=%s entry_id=%s", row["id"], row["bvid"], entry_id)

    def cleanup_downloads(self, dry_run: bool = True) -> list[Path]:
        candidates: list[Path] = []
        download_dir = self.settings.download_dir
        if not download_dir.exists():
            logger.info("cleanup skipped missing_download_dir=%s", download_dir)
            return candidates

        candidates.extend(sorted(download_dir.glob("*.part")))
        protected = {
            self._resolve_audio_path(row["audio_path"])
            for row in self.store.list_by_status(JobStatus.AUDIO_DOWNLOADED, limit=100000)
            if row["audio_path"]
        }
        for audio in sorted(download_dir.glob("*.m4a")):
            if audio.resolve() not in protected:
                candidates.append(audio)

        if not dry_run:
            for path in candidates:
                self._delete_file(path)
        logger.info("cleanup completed dry_run=%s candidates=%s", dry_run, len(candidates))
        return candidates

    def _resolve_audio_path(self, audio_path: str) -> Path:
        path = Path(audio_path)
        if not path.is_absolute():
            path = self.settings.db_path.parent.parent / path
        return path.resolve()

    @staticmethod
    def _delete_file(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            return
