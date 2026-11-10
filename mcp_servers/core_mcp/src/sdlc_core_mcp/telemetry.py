"""OpenTelemetry tracing for the MCP server (H8.3). Off unless an exporter is configured.

Exporters:
- OTLP over HTTP (local, e.g. Jaeger): the standard OTEL_EXPORTER_OTLP_ENDPOINT or
  OTEL_EXPORTER_OTLP_TRACES_ENDPOINT (e.g. http://jaeger:4318).
- Cloud Trace (GCP, version-02 N4): SDLC_TRACE_TO_CLOUD=true, project from GOOGLE_CLOUD_PROJECT,
  the service identity's credentials (roles/cloudtrace.agent). Takes precedence over OTLP.
fastmcp already opens a span per MCP request; this adds the exporter and psycopg spans (SQL text
only: psycopg instrumentation records no parameter values). The span rules are the same for both.

Privacy: spans carry no tokens and no tool argument values. The policy middleware adds only
`sdlc.request_id`, `sdlc.agent_session_id`, `enduser.id` (oid), `sdlc.tool` and the decision, and
writes the `trace_id` into each audit record, so logs and traces join in both directions.
Agent -> server propagation works without HTTP headers: the MCP client puts the trace context in
the request's `_meta` and fastmcp continues it, so one agent turn is one trace (agent, MCP server,
Postgres). Never add a trace HTTP header instead: a per-call header would change the MCP session key
(one MCP session per conversation, see knowledge/rules/workspace.md). Clients without trace context
(e.g. Antigravity) get a server-rooted trace; `sdlc.agent_session_id` / `trace_id` in the audit log
still correlate.
"""

import logging
import os

from opentelemetry import trace

log = logging.getLogger("sdlc.mcp")

_configured = False


def to_cloud() -> bool:
    return os.environ.get("SDLC_TRACE_TO_CLOUD", "").lower() == "true"


def enabled() -> bool:
    return to_cloud() or bool(
        os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    )


def _exporter():
    """(exporter, label). Cloud Trace needs the project; without it, fail loudly at startup."""
    if to_cloud():
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        if not project:
            raise RuntimeError("SDLC_TRACE_TO_CLOUD=true needs GOOGLE_CLOUD_PROJECT")
        return CloudTraceSpanExporter(project_id=project), f"Cloud Trace ({project})"
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    return OTLPSpanExporter(), "OTLP/HTTP"


def setup_tracing(service_name: str = "sdlc-core-mcp") -> bool:
    """Install a tracer provider with the configured exporter and psycopg instrumentation.
    Returns False (and changes nothing) when no exporter is configured."""
    global _configured
    if _configured or not enabled():
        return _configured
    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", service_name)})
    provider = TracerProvider(resource=resource)
    exporter, label = _exporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    PsycopgInstrumentor().instrument(enable_commenter=False)
    _configured = True
    log.info("tracing enabled (%s)", label)
    return True


def current_trace_id() -> str | None:
    """Hex trace id of the active span, or None when not tracing."""
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else None


def annotate(**attributes: str | None) -> None:
    """Set attributes on the active span (no-op without tracing). None values are skipped."""
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attributes({k: v for k, v in attributes.items() if v is not None})
