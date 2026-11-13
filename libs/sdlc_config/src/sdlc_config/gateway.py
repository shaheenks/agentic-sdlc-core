"""The Agent Gateway's MCP tool allowlist, generated from config (CH-0015, NFR-SEC-015).

Access is declared in `config/`, so the gateway's view of an MCP server comes from `tools.yaml`
too: the tools a server serves are the most any agent may call through the gateway. The
gateway never allows a tool that config does not have; who may call which tool, with which
arguments, is still decided per user by the MCP server.

The output is a small JSON document, checked in at `infra/gcp/generated/gateway_policy.json` and
read by Terraform:
- `tools`: the allowed tool names (sorted), for the IAP condition on the agent's grant;
- `toolspec`: the Agent Registry tool spec (`{"tools": [{name, description, inputSchema}]}`), which
  the gateway uses to recognise the server's tools.
"""

import json

from sdlc_config.model import Snapshot

SPEC_LIMIT_BYTES = 10 * 1024  # Agent Registry's limit for a tool spec


def gateway_policy(snapshot: Snapshot, server: str = "core-mcp") -> dict:
    tools = sorted(name for name, tool in snapshot.tools.items() if tool.server == server)
    if not tools:
        raise ValueError(f"tools.yaml: no tools for server '{server}'")
    spec = {
        "tools": [
            {
                "name": name,
                "description": f"{name} (risk {snapshot.tools[name].risk}; "
                "access per user is decided by the MCP server)",
                # The server validates arguments; the gateway only needs the names.
                "inputSchema": {"type": "object"},
            }
            for name in tools
        ]
    }
    size = len(json.dumps(spec, separators=(",", ":")).encode("utf-8"))
    if size > SPEC_LIMIT_BYTES:
        raise ValueError(f"tool spec is {size} bytes, over Agent Registry's {SPEC_LIMIT_BYTES}")
    return {"server": server, "tools": tools, "toolspec": spec}


def render(policy: dict) -> str:
    """Stable text for the checked-in file (sorted keys, two-space indent, final newline)."""
    return json.dumps(policy, indent=2, sort_keys=True) + "\n"
