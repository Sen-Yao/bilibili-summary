from pathlib import Path

from bilibili_summary.models import FeedVideo, JobStatus, VideoMetadata
from bilibili_summary.pipeline import Pipeline
from bilibili_summary.store import JobStore


class DummySettings:
    def __init__(self, tmp_path: Path):
        self.db_path = tmp_path / "data" / "db.sqlite3"
        self.download_dir = tmp_path / "data" / "downloads"
        self.keep_audio_files = False


class Classification:
    def __init__(self, is_food: bool):
        self.is_food = is_food
        self.reason = "test"


class DummyBilibili:
    def __init__(self):
        self.audio_requests = 0

    def get_metadata(self, bvid: str) -> VideoMetadata:
        return VideoMetadata(bvid, 123, "title", None, "owner", "category", "desc", None)

    def get_audio_url(self, bvid: str, cid: int) -> str:
        self.audio_requests += 1
        return "https://audio.example/file.m4a"

    def download_audio(self, url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"audio")
        return destination


class DummyLLM:
    def __init__(self, is_food: bool):
        self.is_food = is_food

    def classify_food(self, metadata: VideoMetadata) -> Classification:
        return Classification(self.is_food)


class DummyWatchLater:
    def __init__(self):
        self.added = []

    def add(self, bvid: str, dry_run: bool = True) -> str:
        self.added.append((bvid, dry_run))
        return "dry-run" if dry_run else "ok"


def make_pipeline(tmp_path, is_food=False):
    store = JobStore(tmp_path / "data" / "db.sqlite3")
    store.init_db()
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = DummySettings(tmp_path)
    pipeline.store = store
    pipeline.bilibili = DummyBilibili()
    pipeline.llm = DummyLLM(is_food)
    pipeline.watch_later = DummyWatchLater()
    return pipeline, store


def test_process_video_enqueues_and_deduplicates(tmp_path):
    pipeline, _ = make_pipeline(tmp_path)

    first = pipeline.process_video("https://www.bilibili.com/video/BV1xx411c7mD", dry_run=True)
    second = pipeline.process_video("BV1xx411c7mD", dry_run=True)

    assert first["created"] is True
    assert second["created"] is False
    assert first["job_id"] == second["job_id"]
    assert first["bvid"] == "BV1xx411c7mD"


def test_process_video_run_now_dry_run_checks_audio(tmp_path):
    pipeline, store = make_pipeline(tmp_path, is_food=False)

    result = pipeline.process_video("BV1xx411c7mD", dry_run=True, run_now=True)

    assert result["status"] == JobStatus.DISCOVERED.value
    assert pipeline.bilibili.audio_requests == 1
    assert store.get(result["job_id"])["status"] == JobStatus.DISCOVERED.value


def test_process_video_food_uses_watch_later_unless_forced(tmp_path):
    pipeline, store = make_pipeline(tmp_path, is_food=True)

    skipped = pipeline.process_video("BV1xx411c7mD", dry_run=False, run_now=True)
    assert skipped["status"] == JobStatus.SKIPPED.value
    assert pipeline.watch_later.added == [("BV1xx411c7mD", False)]

    store.upsert_discovered(FeedVideo("BV1yy411c7mD", "https://example/BV1yy411c7mD"))
    forced = pipeline.process_video("BV1yy411c7mD", dry_run=True, run_now=True, force=True)
    assert forced["status"] == JobStatus.DISCOVERED.value
    assert pipeline.bilibili.audio_requests == 1


def test_process_video_rejects_missing_bvid(tmp_path):
    pipeline, _ = make_pipeline(tmp_path)

    try:
        pipeline.process_video("not a video", dry_run=True)
    except ValueError as exc:
        assert "Could not find" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_process_video_does_not_rerun_terminal_status_without_force(tmp_path):
    pipeline, store = make_pipeline(tmp_path, is_food=False)
    created = pipeline.process_video("BV1xx411c7mD", dry_run=True)
    store.update(created["job_id"], JobStatus.ARCHIVED)

    existing = pipeline.process_video("BV1xx411c7mD", dry_run=True, run_now=True)

    assert existing["status"] == JobStatus.ARCHIVED.value
    assert pipeline.bilibili.audio_requests == 0

    forced = pipeline.process_video("BV1xx411c7mD", dry_run=True, run_now=True, force=True)

    assert forced["status"] == JobStatus.ARCHIVED.value
    assert pipeline.bilibili.audio_requests == 1
