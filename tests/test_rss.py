from bilibili_summary.rss import extract_bvid, parse_feed


def test_extract_bvid():
    assert extract_bvid("https://www.bilibili.com/video/BV1xx411c7mD") == "BV1xx411c7mD"
    assert extract_bvid("nothing") is None


def test_parse_feed_extracts_bvid():
    xml = """<?xml version='1.0'?><rss><channel><item><title>Video</title><link>https://www.bilibili.com/video/BV1xx411c7mD</link><guid>g1</guid></item></channel></rss>"""
    videos = parse_feed(xml)
    assert len(videos) == 1
    assert videos[0].bvid == "BV1xx411c7mD"
