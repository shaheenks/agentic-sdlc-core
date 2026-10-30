"""Shared store for the AG-UI probe agent: AgentLoader imports the agent as a top-level module, so
its own globals are not the ones a test imports."""

RECORDS: list[dict] = []
