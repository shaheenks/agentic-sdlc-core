import io
import json
import logging

from sdlc_logging import AUDIT_TAG, JsonFormatter, audit


def _capture(service: str) -> io.StringIO:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    return stream


def test_log_line_is_json_with_service_and_severity():
    stream = _capture("svc")
    logging.getLogger("x").warning("hello %s", "world", extra={"run_id": "r1"})
    entry = json.loads(stream.getvalue())
    assert entry["severity"] == "WARNING"
    assert entry["message"] == "hello world"
    assert entry["service"] == "svc"
    assert entry["run_id"] == "r1"


def test_audit_record_carries_the_tag():
    stream = _capture("svc")
    audit("tool_call", tool="search", decision="allow")
    entry = json.loads(stream.getvalue())
    assert entry["log_type"] == AUDIT_TAG
    assert entry["event"] == "tool_call"
    assert entry["decision"] == "allow"
