"""The tools served in code and the tools named in `config/tool_groups.yaml` agree (FR-AUTHZ-006).

Access is matched by tool name only, so a name in configuration with no tool behind it, or a tool that no
group lists, would go unnoticed: neither is an error at runtime, the tool is simply available to no one.

The configuration is read from the repository, so this runs in the workspace and skips when the component
is built and tested on its own."""

from pathlib import Path

import pytest
from user_agent_mcp.tools import TOOLS

TOOL_GROUPS = Path(__file__).resolve().parents[3] / "config" / "tool_groups.yaml"


def configured_tools() -> dict[str, str]:
    """Tool name -> the tool group that lists it."""
    yaml = pytest.importorskip("yaml")
    if not TOOL_GROUPS.is_file():
        pytest.skip(f"{TOOL_GROUPS} not found: not running in the workspace")
    groups = yaml.safe_load(TOOL_GROUPS.read_text(encoding="utf-8"))["tool_groups"]
    return {tool: group for group, declared in groups.items() for tool in declared["tools"]}


def test_every_configured_tool_exists():
    unknown = {tool: group for tool, group in configured_tools().items() if tool not in TOOLS}
    assert not unknown, f"tool_groups.yaml names tools user_agent_mcp does not serve: {unknown}"


def test_every_tool_is_in_a_group():
    ungrouped = sorted(set(TOOLS) - set(configured_tools()))
    assert not ungrouped, f"tools in no tool group of tool_groups.yaml, so available to no one: {ungrouped}"
