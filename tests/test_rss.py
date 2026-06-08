from bilibili_summary.rss import extract_bvid, parse_feed
from bilibili_summary.pipeline import Pipeline


class DummySettings:
    rss_feed_url = "https://rss.example/feed"
    bilibili_user_agent = "TestAgent"
    bilibili_referer = "https://www.bilibili.com"


def test_extract_bvid():
    assert extract_bvid("https://www.bilibili.com/video/BV1xx411c7mD") == "BV1xx411c7mD"
    assert extract_bvid("nothing") is None


def test_parse_feed_extracts_bvid():
    xml = """<?xml version='1.0'?><rss><channel><item><title>Video</title><link>https://www.bilibili.com/video/BV1xx411c7mD</link><guid>g1</guid></item></channel></rss>"""
    videos = parse_feed(xml)
    assert len(videos) == 1
    assert videos[0].bvid == "BV1xx411c7mD"


def test_fetch_rss_retries_transient_503(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, status_code, text=""):
            self.status_code = status_code
            self.text = text

        def raise_for_status(self):
            if self.status_code >= 400:
                import httpx

                raise httpx.HTTPStatusError("bad", request=httpx.Request("GET", DummySettings.rss_feed_url), response=httpx.Response(self.status_code))

    def fake_get(url, headers, timeout):
        calls.append((url, headers, timeout))
        if len(calls) == 1:
            return FakeResponse(503)
        return FakeResponse(200, "<rss />")

    monkeypatch.setattr("bilibili_summary.pipeline.httpx.get", fake_get)
    monkeypatch.setattr("bilibili_summary.pipeline.time.sleep", lambda _: None)

    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = DummySettings()

    assert pipeline._fetch_rss() == "<rss />"
    assert len(calls) == 2
    assert calls[0][1]["User-Agent"] == "TestAgent"
