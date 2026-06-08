from bilibili_summary.models import SummaryResult, VideoMetadata
from bilibili_summary.wallabag import WallabagClient


def test_wallabag_dry_run_returns_marker():
    client = WallabagClient("http://wallabag", "id", "secret", "user", "pass")
    meta = VideoMetadata("BV1xx411c7mD", 1, "title", "pic", "owner", "cat", "desc", "dyn")
    summary = SummaryResult("ai", "<p>body</p>", ["AI-Summary"])
    assert client.create_entry(meta, summary, dry_run=True) == "dry-run"
