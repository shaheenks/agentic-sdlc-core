"""Errors shared by everything that talks to external systems (ingest loaders, MCP tools)."""


class ConnectorError(RuntimeError):
    """An external system cannot be reached or refused the request. Messages name the host and
    status, never credentials or response bodies."""
