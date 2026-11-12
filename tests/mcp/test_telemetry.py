"""H8.3: tracing hooks. Audit records carry the trace id; spans carry identifiers only."""

import json

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sdlc_core_mcp import telemetry
from sdlc_core_mcp.audit import emit


def test_tracing_is_off_without_an_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("SDLC_TRACE_TO_CLOUD", raising=False)
    assert telemetry.setup_tracing() is False
    assert telemetry.current_trace_id() is None


def test_cloud_trace_exporter_selection(monkeypatch):
    """version-02 N4: SDLC_TRACE_TO_CLOUD picks Cloud Trace (over OTLP) and needs the project."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318")
    monkeypatch.setenv("SDLC_TRACE_TO_CLOUD", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj-123")
    created = {}

    class FakeCloudTrace:
        def __init__(self, project_id):
            created["project"] = project_id

    import opentelemetry.exporter.cloud_trace as cloud_trace

    monkeypatch.setattr(cloud_trace, "CloudTraceSpanExporter", FakeCloudTrace)
    exporter, label = telemetry._exporter()
    assert isinstance(exporter, FakeCloudTrace) and created == {"project": "proj-123"}
    assert label == "Cloud Trace (proj-123)" and telemetry.enabled()

    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT")
    import pytest

    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
        telemetry._exporter()

    monkeypatch.setenv("SDLC_TRACE_TO_CLOUD", "false")
    _, label = telemetry._exporter()
    assert label == "OTLP/HTTP"


def test_audit_record_and_span_reference_each_other(caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    with provider.get_tracer("test").start_as_current_span("tools/call") as span:
        emit(
            {
                "event": "tool_call",
                "request_id": "req-1",
                "agent_session_id": "conv-1",
                "oid": "aaaaaaaa-0000-0000-0000-00000000000a",
                "tool": "fixture_review",
                "args_hash": "sha256:abc",
                "decision": "allow",
                "outcome": "ok",
                "config_version": "local-x",
            }
        )
        trace_id = format(span.get_span_context().trace_id, "032x")
    [record] = [json.loads(r.getMessage()) for r in caplog.records if r.name == "sdlc.audit"]
    assert record["trace_id"] == trace_id
    [finished] = exporter.get_finished_spans()
    attrs = dict(finished.attributes)
    assert attrs["sdlc.request_id"] == "req-1" and attrs["sdlc.agent_session_id"] == "conv-1"
    assert attrs["enduser.id"] == record["oid"] and attrs["sdlc.tool"] == "fixture_review"
    assert attrs["sdlc.decision"] == "allow" and attrs["sdlc.outcome"] == "ok"
    assert not any("arg" in key for key in attrs)  # no argument values or hashes on spans


def test_no_trace_id_without_an_active_span(caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    emit({"event": "tools_list", "request_id": "req-2"})
    [record] = [json.loads(r.getMessage()) for r in caplog.records if r.name == "sdlc.audit"]
    assert "trace_id" not in record
