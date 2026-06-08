from bilibili_summary.llm import _json_from_text


def test_json_from_plain_text():
    assert _json_from_text('{"is_food": false, "reason": "x"}') == {"is_food": False, "reason": "x"}


def test_json_from_markdown_fence():
    assert _json_from_text('```json\n{"ai_title":"t","ai_html_content":"c","tags":[]}\n```')["ai_title"] == "t"
