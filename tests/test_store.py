from bilibili_summary.models import FeedVideo, JobStatus
from bilibili_summary.store import JobStore


def test_upsert_discovered_deduplicates(tmp_path):
    store = JobStore(tmp_path / "db.sqlite3")
    store.init_db()
    video = FeedVideo(bvid="BV1xx411c7mD", url="https://example/BV1xx411c7mD")
    assert store.upsert_discovered(video) is True
    assert store.upsert_discovered(video) is False
    rows = store.list_by_status(JobStatus.DISCOVERED)
    assert len(rows) == 1


def test_update_can_restore_discovered(tmp_path):
    store = JobStore(tmp_path / "db.sqlite3")
    store.init_db()
    video = FeedVideo(bvid="BV1xx411c7mD", url="https://example/BV1xx411c7mD")
    assert store.upsert_discovered(video) is True
    row = store.list_by_status(JobStatus.DISCOVERED, limit=1)[0]
    store.update(row["id"], JobStatus.AUDIO_DOWNLOADED, error_message="dry-run: audio not downloaded")
    store.update(row["id"], JobStatus.DISCOVERED, error_message=None, audio_path=None)
    rows = store.list_by_status(JobStatus.DISCOVERED, limit=1)
    assert rows[0]["error_message"] is None
