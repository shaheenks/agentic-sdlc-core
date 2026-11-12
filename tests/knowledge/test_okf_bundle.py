"""scripts/okf_bundle.py on small bundles in tmp_path: each lint rule passes and fails (CH-0007).

The tests never read the real bundle (tests/knowledge/test_bundle.py does that).
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "okf_bundle.py"
REQ = "knowledge/requirements/functional/FR-TST-001.md"
COMPONENT = "knowledge/components/widget.md"
CHANGE = "knowledge/changes/CH-0001.md"
REQ_LINE = (
    "- [FR-TST-001: Widget works](../requirements/functional/FR-TST-001.md)"
    " - Provides the widget.\n"
)

FILES = {
    "pyproject.toml": '[tool.uv.workspace]\nmembers = ["libs/widget"]\n',
    "libs/widget/widget.py": "VALUE = 1\n",
    "tests/test_widget.py": "def test_value():\n    assert True\n",
    "knowledge/log.md": "# Change log\n\n## 2026-11-12\n\n- **Creation**: test bundle.\n",
    REQ: """---
type: Functional Requirement
title: Widget works
description: The widget does its job.
area: Testing
status: draft
priority: must
implementation: built
---

# Statement

The system shall provide a widget.

# Acceptance criteria

- The widget returns a value.
""",
    COMPONENT: """---
type: Component
title: widget
description: The widget library.
area: Libraries
status: draft
resource: ../../libs/widget
satisfies:
- /requirements/functional/FR-TST-001
verified_by:
- tests/test_widget.py
---

# Requirements

- [FR-TST-001: Widget works](../requirements/functional/FR-TST-001.md) - Provides the widget.
""",
    CHANGE: """---
type: Change
title: Tidy the widget
description: A refactor.
kind: refactor
state: open
status: draft
touches:
- /components/widget
---

# Design

- [widget](../components/widget.md): tidy it.
""",
}


@pytest.fixture
def okf():
    spec = importlib.util.spec_from_file_location("okf_bundle_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def bundle(tmp_path, okf):
    """A valid bundle with generated files; returns a helper to edit files."""
    for rel, text in FILES.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    okf.configure(tmp_path)
    okf.build()

    class Bundle:
        root = tmp_path

        @staticmethod
        def edit(rel: str, old: str, new: str) -> None:
            path = tmp_path / rel
            text = path.read_text(encoding="utf-8")
            assert old in text, (rel, old)
            path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

        @staticmethod
        def problems(rebuild: bool = True) -> list[str]:
            if rebuild:
                okf.build()  # generated files follow the edit, so only the rule under test fails
            return okf.lint()

    return Bundle


def has(problems: list[str], text: str) -> bool:
    return any(text in p for p in problems)


def test_valid_bundle_passes(bundle):
    assert bundle.problems() == []


# --- frontmatter -----------------------------------------------------------------------------


def test_concept_needs_a_type(bundle):
    bundle.edit(COMPONENT, "type: Component\n", "")
    assert has(bundle.problems(), "needs frontmatter with a non-empty `type`")


def test_stable_needs_a_human_review(bundle):
    bundle.edit(REQ, "status: draft", "status: stable")
    assert has(bundle.problems(), "status `stable` needs a `verified` entry")
    bundle.edit(
        REQ,
        "status: stable",
        "status: stable\nverified:\n- by: human:someone\n  at: '2026-11-12T10:00:00+05:30'",
    )
    assert bundle.problems() == []


def test_timestamps_need_an_offset(bundle):
    bundle.edit(
        REQ,
        "status: draft",
        "status: stable\nverified:\n- by: human:someone\n  at: '2026-11-12T10:00:00'",
    )
    assert has(bundle.problems(), "UTC offset")


# --- requirements ----------------------------------------------------------------------------


def test_requirement_priority_and_sections(bundle):
    bundle.edit(REQ, "priority: must", "priority: urgent")
    bundle.edit(REQ, "# Statement", "# Summary")
    problems = bundle.problems()
    assert has(problems, "priority must be one of")
    assert has(problems, "missing section `# Statement`")


def test_requirement_file_name(bundle):
    (bundle.root / "knowledge/requirements/functional/thing.md").write_text(
        "---\ntype: Functional Requirement\ntitle: x\n---\n", encoding="utf-8"
    )
    assert has(bundle.problems(), "requirement file names look like")


# --- components ------------------------------------------------------------------------------


def test_component_resource_must_exist(bundle):
    bundle.edit(COMPONENT, "resource: ../../libs/widget", "resource: ../../libs/gone")
    assert has(bundle.problems(), "resource not found")


def test_component_satisfies_must_match_body_links(bundle):
    bundle.edit(
        COMPONENT,
        REQ_LINE,
        "",
    )
    assert has(bundle.problems(), "`satisfies` and the body's requirement links differ")


def test_verified_by_must_exist(bundle):
    bundle.edit(COMPONENT, "- tests/test_widget.py", "- tests/test_gone.py")
    assert has(bundle.problems(), "verified_by: not found")


@pytest.mark.parametrize(
    "ref", [".github/workflows/ci.yml", "libs/widget/widget.py", "docs/checks.md"]
)
def test_verified_by_must_be_a_test(bundle, ref):
    """CH-0007: a workflow file or source file does not count as verification."""
    path = bundle.root / ref
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    bundle.edit(COMPONENT, "- tests/test_widget.py", f"- {ref}")
    assert has(
        bundle.problems(), f"verified_by: not a test (no `tests` folder or test file name): {ref}"
    )


@pytest.mark.parametrize(
    "ref",
    [
        "tests/test_widget.py",
        "tests",
        "ui/app/tests",
        "ui/app/lib/widget.test.ts",
        "web/widget.spec.ts",
        "checks/test_x.py",
    ],
)
def test_test_shaped_verified_by_passes(bundle, ref):
    path = bundle.root / ref
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch() if path.suffix else path.mkdir()
    bundle.edit(COMPONENT, "- tests/test_widget.py", f"- {ref}")
    assert not has(bundle.problems(), "verified_by")


# --- coverage --------------------------------------------------------------------------------


def test_built_requirement_needs_a_component(bundle):
    bundle.edit(COMPONENT, "satisfies:\n- /requirements/functional/FR-TST-001\n", "satisfies: []\n")
    bundle.edit(
        COMPONENT,
        REQ_LINE,
        "",
    )
    problems = bundle.problems()
    assert has(problems, "implementation `built` but no component satisfies it")


def test_planned_requirement_may_have_no_component(bundle):
    bundle.edit(
        COMPONENT,
        "satisfies:\n- /requirements/functional/FR-TST-001\n",
        "satisfies: [/requirements/functional/FR-TST-001]\n",
    )
    bundle.edit(REQ, "implementation: built", "implementation: planned")
    assert bundle.problems() == []


def test_workspace_member_needs_a_component(bundle):
    bundle.edit("pyproject.toml", '["libs/widget"]', '["libs/widget", "libs/other"]')
    (bundle.root / "libs/other").mkdir()
    assert has(bundle.problems(), "workspace member `libs/other` has no component concept")


# --- change records --------------------------------------------------------------------------


def test_refactor_has_no_requirement_delta(bundle):
    bundle.edit(CHANGE, "touches:", "modifies:\n- /requirements/functional/FR-TST-001\ntouches:")
    bundle.edit(
        CHANGE, "- [widget]", "- [FR-TST-001](../requirements/functional/FR-TST-001.md)\n- [widget]"
    )
    assert has(bundle.problems(), "a refactor leaves requirements untouched")


def test_feature_names_its_requirements(bundle):
    bundle.edit(CHANGE, "kind: refactor", "kind: feature")
    assert has(bundle.problems(), "a feature names the requirements it adds")


def test_done_needs_approval(bundle):
    bundle.edit(CHANGE, "state: open", "state: done")
    assert has(bundle.problems(), "is approved (`status: stable`, verified) before it is done")


def test_change_body_links_match_frontmatter(bundle):
    bundle.edit(CHANGE, "- [widget](../components/widget.md): tidy it.", "- widget: tidy it.")
    assert has(bundle.problems(), "frontmatter and body links differ")


def test_change_touches_known_components(bundle):
    bundle.edit(CHANGE, "- /components/widget", "- /components/widget\n- /components/ghost")
    assert has(bundle.problems(), "touches: no such component /components/ghost")


# --- reserved files and links ----------------------------------------------------------------


def test_log_is_newest_first(bundle):
    bundle.edit("knowledge/log.md", "## 2026-11-12\n", "## 2026-11-10\n\n- a\n\n## 2026-11-12\n")
    assert has(bundle.problems(), "log.md entries must be newest first")


def test_root_index_declares_okf_version(bundle):
    bundle.edit("knowledge/index.md", 'okf_version: "0.2"', 'okf_version: "0.1"')
    assert has(bundle.problems(rebuild=False), "root index.md must declare okf_version")


def test_broken_link(bundle):
    bundle.edit(
        REQ, "- The widget returns a value.", "- The widget returns a value ([see](../nowhere.md))."
    )
    assert has(bundle.problems(), "broken link: ../nowhere.md")


# --- placeholder criteria (CH-0007) ----------------------------------------------------------


@pytest.mark.parametrize("implementation", ["live", "built", "stub"])
def test_code_backed_requirement_cannot_be_to_be_defined(bundle, implementation):
    bundle.edit(REQ, "implementation: built", f"implementation: {implementation}")
    bundle.edit(REQ, "- The widget returns a value.", "- Real behaviour is To Be Defined.")
    assert has(bundle.problems(), "acceptance criteria say `to be defined`")


def test_to_be_defined_is_allowed_when_planned_deprecated_or_quoted(bundle):
    bundle.edit(REQ, "- The widget returns a value.", "- Real behaviour is to be defined.")
    bundle.edit(REQ, "implementation: built", "implementation: planned")
    bundle.edit(
        COMPONENT,
        "satisfies:\n- /requirements/functional/FR-TST-001\n",
        "satisfies: [/requirements/functional/FR-TST-001]\n",
    )
    assert bundle.problems() == []
    bundle.edit(REQ, "implementation: planned", "implementation: built")
    bundle.edit(REQ, "status: draft", "status: deprecated")
    assert bundle.problems() == []
    bundle.edit(REQ, "status: deprecated", "status: draft")
    bundle.edit(
        REQ, "- Real behaviour is to be defined.", "- The lint rejects `to be defined` here."
    )
    assert bundle.problems() == []


def test_to_be_defined_outside_the_criteria_is_fine(bundle):
    bundle.edit(
        REQ,
        "The system shall provide a widget.",
        "The system shall provide a widget (colour to be defined).",
    )
    assert bundle.problems() == []


# --- generated files -------------------------------------------------------------------------


def test_build_is_deterministic(bundle, okf):
    generated = sorted((bundle.root / "knowledge").rglob("index.md")) + [
        bundle.root / "knowledge/traceability.md"
    ]
    before = {p: p.read_bytes() for p in generated}
    okf.build()
    assert {p: p.read_bytes() for p in generated} == before
    assert okf.stale() == []


def test_stale_detects_hand_edits(bundle, okf):
    trace = bundle.root / "knowledge/traceability.md"
    trace.write_text(trace.read_text(encoding="utf-8") + "\nhand edit\n", encoding="utf-8")
    assert has(okf.stale(), "traceability.md: out of date")
    assert has(okf.lint(), "traceability.md: out of date")
