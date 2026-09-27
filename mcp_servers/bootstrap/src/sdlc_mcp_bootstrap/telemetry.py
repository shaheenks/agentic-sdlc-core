"""OpenTelemetry tracing for the MCP server (H8.3). Off unless an OTLP endpoint is configured.

Enabled by the standard variables OTEL_EXPORTER_OTLP_ENDPOINT or OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
(OTLP over HTTP, e.g. http://jaeger:4318). fastmcp already opens a span per MCP request; this adds
the exporter and psycopg spans (SQL text only: psycopg instrumentation records no parameter values).

Privacy: spans carry no tokens and no tool argument values. The policy middleware adds only
`sdlc.request_id`, `sdlc.agent_session_id`, `enduser.id` (oid), `sdlc.tool` and the decision, and
writes the `trace_id` into each audit record, so logs and traces join in both directions.
Agent -> server propagation works without HTTP headers: the MCP client puts the trace context in
the request's `_meta` and fastmcp continues it, so one agent turn is one trace (agent, MCP server,
Postgres). Never add a trace HTTP header instead: a per-call header would change the MCP session key
(one MCP session per conversation, see CLAUDE.md). Clients without trace context (e.g. Antigravity)
get a server-rooted trace; `sdlc.agent_session_id` / `trace_id` in the audit log still correlate.
"""

import logging
import os

from opentelemetry import trace

log = logging.getLogger("sdlc.mcp")

_configured = False


def enabled() -> bool:
    return bool(
        os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    )


def setup_tracing(service_name: str = "sdlc-mcp-bootstrap") -> bool:
    """Install a tracer provider with an OTLP/HTTP exporter and psycopg instrumentation.
    Returns False (and changes nothing) when no endpoint is configured."""
    global _configured
    if _configured or not enabled():
        return _configured
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", service_name)})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    PsycopgInstrumentor().instrument(enable_commenter=False)
    _configured = True
    log.info("tracing enabled (OTLP/HTTP)")
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
