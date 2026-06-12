from pathlib import Path

from bilibili_summary.bilibili import BilibiliClient
from bilibili_summary.models import FeedVideo, JobStatus
from bilibili_summary.pipeline import Pipeline
from bilibili_summary.store import JobStore


class DummySettings:
    def __init__(self, tmp_path: Path, keep_audio_files: bool = False):
        self.db_path = tmp_path / "data" / "db.sqlite3"
        self.download_dir = tmp_path / "data" / "downloads"
        self.keep_audio_files = keep_audio_files


class DummySTT:
    def transcribe(self, audio_path: Path) -> str:
        assert audio_path.exists()
        return "transcript"


class DummyLLM:
    def summarize(self, metadata, stt_text):
        raise AssertionError("summary should not run in this test")


def test_download_audio_uses_partial_then_renames(tmp_path, monkeypatch):
    destination = tmp_path / "BV1.m4a"
    chunks = [b"hello", b"world"]

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield from chunks

    monkeypatch.setattr("bilibili_summary.bilibili.httpx.stream", lambda *args, **kwargs: Response())

    BilibiliClient("ua", "ref").download_audio("https://audio.example", destination)

    assert destination.read_bytes() == b"helloworld"
    assert not destination.with_name("BV1.m4a.part").exists()


def test_download_audio_removes_stale_partial(tmp_path, monkeypatch):
    destination = tmp_path / "BV1.m4a"
    partial = destination.with_name("BV1.m4a.part")
    partial.write_bytes(b"stale")

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield b"fresh"

    monkeypatch.setattr("bilibili_summary.bilibili.httpx.stream", lambda *args, **kwargs: Response())

    BilibiliClient("ua", "ref").download_audio("https://audio.example", destination)

    assert destination.read_bytes() == b"fresh"
    assert not partial.exists()


def test_download_audio_removes_partial_on_failure(tmp_path, monkeypatch):
    destination = tmp_path / "BV1.m4a"

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield b"partial"
            raise RuntimeError("network failed")

    monkeypatch.setattr("bilibili_summary.bilibili.httpx.stream", lambda *args, **kwargs: Response())

    try:
        BilibiliClient("ua", "ref").download_audio("https://audio.example", destination)
    except RuntimeError:
        pass

    assert not destination.exists()
    assert not destination.with_name("BV1.m4a.part").exists()


def test_transcribe_deletes_audio_by_default(tmp_path):
    store = JobStore(tmp_path / "data" / "db.sqlite3")
    store.init_db()
    store.upsert_discovered(FeedVideo("BV1xx411c7mD", "https://example/video"))
    row = store.list_by_status(JobStatus.DISCOVERED, limit=1)[0]
    audio = tmp_path / "data" / "downloads" / "BV1xx411c7mD.m4a"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"audio")
    store.update(row["id"], JobStatus.AUDIO_DOWNLOADED, audio_path=str(audio), cid=1, video_title="title")

    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = DummySettings(tmp_path)
    pipeline.store = store
    pipeline.stt = DummySTT()
    pipeline.llm = DummyLLM()

    try:
        pipeline._transcribe_and_archive(store.get(row["id"]), dry_run=False)
    except AssertionError:
        pass

    assert not audio.exists()
    assert store.get(row["id"])["stt_text"] == "transcript"


def test_transcribe_keeps_audio_when_configured(tmp_path):
    store = JobStore(tmp_path / "data" / "db.sqlite3")
    store.init_db()
    store.upsert_discovered(FeedVideo("BV1xx411c7mD", "https://example/video"))
    row = store.list_by_status(JobStatus.DISCOVERED, limit=1)[0]
    audio = tmp_path / "data" / "downloads" / "BV1xx411c7mD.m4a"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"audio")
    store.update(row["id"], JobStatus.AUDIO_DOWNLOADED, audio_path=str(audio), cid=1, video_title="title")

    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = DummySettings(tmp_path, keep_audio_files=True)
    pipeline.store = store
    pipeline.stt = DummySTT()
    pipeline.llm = DummyLLM()

    try:
        pipeline._transcribe_and_archive(store.get(row["id"]), dry_run=False)
    except AssertionError:
        pass

    assert audio.exists()


def test_cleanup_downloads_dry_run_and_delete(tmp_path):
    store = JobStore(tmp_path / "data" / "db.sqlite3")
    store.init_db()
    protected = tmp_path / "data" / "downloads" / "protected.m4a"
    orphan = tmp_path / "data" / "downloads" / "orphan.m4a"
    partial = tmp_path / "data" / "downloads" / "old.m4a.part"
    protected.parent.mkdir(parents=True)
    protected.write_bytes(b"keep")
    orphan.write_bytes(b"delete")
    partial.write_bytes(b"partial")
    store.upsert_discovered(FeedVideo("BV1xx411c7mD", "https://example/video"))
    row = store.list_by_status(JobStatus.DISCOVERED, limit=1)[0]
    store.update(row["id"], JobStatus.AUDIO_DOWNLOADED, audio_path=str(protected))

    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = DummySettings(tmp_path)
    pipeline.store = store

    candidates = pipeline.cleanup_downloads(dry_run=True)
    assert sorted(p.name for p in candidates) == ["old.m4a.part", "orphan.m4a"]
    assert orphan.exists()
    assert partial.exists()

    pipeline.cleanup_downloads(dry_run=False)
    assert protected.exists()
    assert not orphan.exists()
    assert not partial.exists()
