"""SDLC tools. Stage 3: STUBS that only echo their inputs, to demonstrate RBAC and argument
limits end to end. Real implementations replace them in later stages; access to them is
decided by config (tools.yaml, roles.yaml, teams/*.yaml), never here.
"""

from collections.abc import Callable

STUB_NOTE = "Stub: no work was performed. The real tool arrives in a later stage."


def _stub(tool: str, **inputs) -> dict:
    return {"stub": True, "tool": tool, "inputs": inputs, "message": STUB_NOTE}


def review_code(repo: str, ref: str = "main") -> dict:
    """(Stub) Review the code of a repository at a branch or commit."""
    return _stub("review_code", repo=repo, ref=ref)


def generate_tests(repo: str, target: str) -> dict:
    """(Stub) Generate test cases for a module or function in a repository."""
    return _stub("generate_tests", repo=repo, target=target)


def approve_design(repo: str, design_id: str) -> dict:
    """(Stub) Record approval of a design document for a repository."""
    return _stub("approve_design", repo=repo, design_id=design_id)


SDLC_TOOLS: list[Callable] = [review_code, generate_tests, approve_design]
