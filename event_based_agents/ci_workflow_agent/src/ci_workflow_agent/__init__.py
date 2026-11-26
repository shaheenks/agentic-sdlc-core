"""ci_workflow_agent: plans and implements approved designs, one run per event (DEC-0007, DEC-0015).

Runs on the event agents' own Agent Runtime deployment as the system identity, and calls tools only through
event_agent_mcp. The security and quality review workflows come in phase 5b."""

NAME = "ci_workflow_agent"
