"""Agent spans never carry prompts, model responses or tool results, whatever the deployment sets
(version-02 H5: Cloud Run lacked the compose env vars and exported prompt text to Cloud Trace)."""

import json
import os
import subprocess
import sys

PROBE = """
import json
import sdlc_web  # must switch content capture off before ADK reads it
from google.adk.telemetry.context import TelemetryConfig
c = TelemetryConfig()
print(json.dumps({
    "legacy_spans": c.should_add_content_to_legacy_spans,
    "spans": c.should_add_content_to_experimental_spans,
    "logs": c.should_add_content_to_logs,
}))
"""


def test_importing_sdlc_web_turns_span_content_off_even_if_env_enables_it():
    env = {
        **os.environ,
        "ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS": "true",
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "SPAN_AND_EVENT",
    }
    out = subprocess.run(
        [sys.executable, "-c", PROBE], env=env, capture_output=True, text=True, check=True
    ).stdout
    assert json.loads(out.strip().splitlines()[-1]) == {
        "legacy_spans": False,
        "spans": False,
        "logs": False,
    }
