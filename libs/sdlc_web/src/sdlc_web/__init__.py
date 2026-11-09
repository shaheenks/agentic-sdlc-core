"""Serve ADK agents to signed-in Entra users. See libs/sdlc_web/README.md."""

import os

# Spans never carry prompts, model responses or tool results (retrieved content can be
# confidential). ADK records them by default and reads these once, when its telemetry context is
# built, so they are forced here, before any submodule imports ADK. Not left to the deployment:
# Cloud Run once ran without them and exported prompt text to Cloud Trace (version-02 H5).
CONTENT_CAPTURE_OFF = {
    "ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS": "false",
    "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "false",
}
os.environ.update(CONTENT_CAPTURE_OFF)

from sdlc_web.middleware import EntraUserBindingMiddleware  # noqa: E402

__all__ = ["CONTENT_CAPTURE_OFF", "EntraUserBindingMiddleware"]
