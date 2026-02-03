from feedback_agent.json_utils import fix_json_string, parse_json_payload


def test_fix_json_string_removes_trailing_commas():
    raw = '{"a": 1, "b": [1, 2,],}'
    fixed = fix_json_string(raw)
    assert fixed == '{"a": 1, "b": [1, 2]}'


def test_parse_json_payload_handles_wrapped_text():
    raw = "prefix {\"a\": 1, \"b\": \"ok\",} suffix"
    parsed = parse_json_payload(raw, "wrapped")
    assert parsed == {"a": 1, "b": "ok"}


def test_parse_json_payload_returns_none_for_non_object():
    raw = "[1, 2, 3]"
    parsed = parse_json_payload(raw, "list")
    assert parsed is None
