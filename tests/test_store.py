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
