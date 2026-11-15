"""The MCP server body is a library behind an identity adapter (CH-0020).

`libs/sdlc_mcp` must not know the identity provider: a second server component (core_mcp_gcp)
reuses it with its own adapter. core_mcp supplies the Entra adapter and verifier.
"""

import ast
from pathlib import Path

from sdlc_core_mcp.entra import ENTRA
from sdlc_mcp.identity import IdentityAdapter

from tests.support.config import REPO_ROOT

LIB = REPO_ROOT / "libs" / "sdlc_mcp" / "src" / "sdlc_mcp"
COMPONENT = REPO_ROOT / "mcp_servers" / "core_mcp" / "src" / "sdlc_core_mcp"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_the_library_imports_no_identity_provider():
    for path in sorted(LIB.glob("*.py")):
        modules = imported_modules(path)
        assert not [m for m in modules if m.startswith("sdlc_auth.entra")], path.name
        assert not [m for m in modules if m.startswith("sdlc_core_mcp")], path.name


def test_core_mcp_is_only_the_entra_parts():
    """No server code is copied into the component: just the adapter and the entry point."""
    files = sorted(p.name for p in COMPONENT.glob("*.py"))
    assert files == ["__init__.py", "entra.py", "server.py"]


def test_entra_adapter_fits_the_port():
    port = {n for n in vars(IdentityAdapter) if not n.startswith("_")} - {"name"}
    assert port == {"principal", "memberships", "user_key", "describe", "rejection"}
    assert all(callable(getattr(ENTRA, m)) for m in port)
    assert ENTRA.name == "entra"
    claims = {
        "oid": "aaaaaaaa-0000-0000-0000-00000000000a",
        "tid": "t",
        "preferred_username": "alice@example.test",
        "roles": ["SDLC.User"],
        "scp": "access_as_user",
    }
    p = ENTRA.principal(claims)
    assert p.user_id == p.oid == claims["oid"]
    assert ENTRA.memberships(p) == frozenset({"SDLC.User"})
    assert ENTRA.user_key(p) == claims["oid"]
    assert ENTRA.describe(p)["app_roles"] == ["SDLC.User"]
