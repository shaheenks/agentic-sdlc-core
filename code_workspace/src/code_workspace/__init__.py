"""Cloud Run job where ci_workflow_agent's changes are applied, built, tested and pushed (DEC-0015, FR-SDLC-006).

Started only by event_agent_mcp, one execution per request; see run.py.
"""

NAME = "code_workspace"
