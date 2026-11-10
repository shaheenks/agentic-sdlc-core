---
type: Convention
title: Bundle conventions
description: How this bundle is organised - concept types, requirement IDs, extension keys, review states and the change procedure.
tags: [meta]
status: draft
sources:
  - id: okf
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
    title: Open Knowledge Format 0.2
---

# Purpose

This directory is an [Open Knowledge Format 0.2](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
bundle. It holds what is true about the system - its requirements, and later its components,
interfaces, data and decisions - in a form both people and agents read. OKF fixes only the file
layout, the `type` key and a few optional key families; everything below is this project's own
convention on top of it.

# Layout

| Path | Holds | Added in |
|---|---|---|
| `system/` | System context and scope | step 2 |
| `requirements/functional/` | One concept per functional requirement | step 2 |
| `requirements/non-functional/` | One concept per non-functional requirement | step 2 |
| `components/` | One concept per component, tracing to requirements | step 3 |
| `traceability.md` | Generated matrix: requirement to components, component to tests, gaps | step 3 |
| `changes/` | One record per feature, behaviour change, fix or refactor | step 6 |
| `rules/` | Binding working rules per area, routed from `CLAUDE.md` | step 7 |
| `interfaces/`, `data/`, `decisions/` | MCP tools and APIs, data model, decision records | step 5 |

`index.md` files and `traceability.md` are generated (`scripts/okf_bundle.py build`); do not edit
them by hand.
`log.md` is written by hand, newest first, under `## YYYY-MM-DD` headings.

# Concept types

| `type` | Use |
|---|---|
| `System` | The system as a whole |
| `Functional Requirement` | Something the system does for a user or operator |
| `Non-Functional Requirement` | A quality or constraint the system must hold |
| `Component` | A deployable or importable part of the repository |
| `Traceability Matrix` | The generated trace report |
| `Change` | A proposed or completed change and the requirements and components it affects |
| `Rule Set` | Binding working rules for one area of the repository |
| `Convention` | Rules for the bundle itself |

New types are added to this table in the pull request that first uses them.

# Requirement IDs

- A requirement's file name is its ID: `FR-<AREA>-<nnn>.md` or `NFR-<AREA>-<nnn>.md`.
- The OKF concept ID is the path, for example `/requirements/functional/FR-AUTHZ-001`. Use that
  form in trace keys and the bare ID (`FR-AUTHZ-001`) in plans, commits, pull requests and tests.
- IDs are stable. Never rename or reuse one. Change the `title` freely.
- A requirement that no longer applies gets `status: deprecated` and a line in `log.md`; the file
  stays.
- Numbers are allocated in order within an area and gaps are not filled.

Areas in use - functional: `IDN` identity, `AUTHZ` authorization, `CFG` configuration, `KNOW`
knowledge, `SKILL` skills, `TEAM` teams, `DOC` documents, `ART` artifacts, `CONN` connections,
`SURF` surfaces, `CONV` conversations, `ACT` SDLC actions, `AUTO` autonomous agents, `WRITE`
write actions. Non-functional: `SEC` security, `PRIV` privacy, `AUD` auditability, `OBS`
observability, `REL` reliability, `PORT` portability, `MAINT` maintainability, `QUAL` quality,
`OPS` operability.

# Frontmatter

OKF keys used here: `type`, `title`, `description`, `tags`, `status`, `verified`,
`sources`, and `stale_after` where a concept is known to age.

Extension keys for requirements:

| Key | Values | Meaning |
|---|---|---|
| `area` | free text | Groups requirements in the index |
| `priority` | `must`, `should`, `could` | How much the system depends on it |
| `implementation` | `live`, `built`, `stub`, `planned`, `parked` | State of the code, as in the feature inventory |

`status` describes the *document* (is this text reviewed?); `implementation` describes the *code*
(is it built?). A planned feature can have a `stable` requirement.

# Components and traceability

A component concept is named after its code (`components/sdlc_policy.md`) and carries the trace:

| Key | Value | Meaning |
|---|---|---|
| `resource` | path relative to the concept file | Where the code lives |
| `area` | free text | Groups components in the index |
| `satisfies` | requirement concept IDs | The requirements this component helps to meet |
| `verified_by` | paths from the repository root | Tests (files or folders) that exercise the component |

The body's `# Requirements` section links each satisfied requirement and says in a few words *how*
the component contributes. The key and the links must list the same requirements; the lint checks.

Rules the lint enforces:

- A requirement whose `implementation` is `live`, `built` or `stub` is satisfied by at least one
  component. `planned` and `parked` requirements may have none.
- Every component satisfies at least one requirement, and its `resource` and `verified_by` paths
  exist.
- Every uv workspace member in `pyproject.toml` has a component concept.

CI runs the lint on every push and pull request (job `knowledge`). On pull requests it also lists,
as a hint for the reviewer, components whose code changed while their concept did not
(`okf_bundle.py drift --base <rev>`); that list never fails the build.

`verified_by` is per component, not per requirement: it says the component is tested, not which
test proves which acceptance criterion.

# Review states

| State | Frontmatter | Meaning |
|---|---|---|
| Draft | `status: draft` | Written, not yet reviewed. Do not build against it without checking. |
| Reviewed | `status: stable` + a `verified` entry by `human:<id>` | A person has confirmed the text. |
| Retired | `status: deprecated` | Kept for history. |

Reviewers are recorded as `human:<id>`. Concepts carry no `generated` (authoring tool) entry; git
history records who wrote what. Whoever edits a reviewed concept in substance sets it back to
`draft` and removes `verified`.

# Requirement body

```markdown
# Statement

One sentence: "The system shall ...".

# Acceptance criteria

- Observable, testable facts. Each should be checkable by a test or a command.

# Notes

Optional: known gaps, open decisions, links to related requirements.
```

Links inside the bundle are relative, so they also work in the repository browser and in editors.

# Change records

Work on the system starts from a change record, `changes/CH-<nnnn>.md`, numbered in order. It says
which requirements the work adds, modifies or retires and which components it touches, so every
code change traces back to the specification. Records are never deleted or renumbered.

| Key | Values | Meaning |
|---|---|---|
| `kind` | `feature`, `change`, `fix`, `refactor` | See below |
| `state` | `open`, `done`, `dropped` | Where the work is |
| `adds`, `modifies`, `retires` | requirement concept IDs | The requirement delta |
| `touches` | component concept IDs | Components whose code or design changes |

- `feature` and `change` name at least one requirement they add, modify or retire.
- `fix` and `refactor` leave requirements untouched: a fix restores specified behaviour and a
  refactor keeps it. If the work shows the specification was wrong, it is a `change`.
- Approval is the OKF review state: a record is `status: draft` while proposed and becomes
  `status: stable` with a `verified` entry by `human:<id>` when approved. Code work starts only on
  an approved record, and only an approved record can be `done`.

```markdown
---
type: Change
title: Share artifacts with a team
description: One line saying what changes for whom.
kind: feature
state: open
status: draft
modifies: [/requirements/functional/FR-ART-004]
touches: [/components/core_mcp, /components/sdlc_db]
---

# Why

The problem or goal, and where it comes from (plan section, issue, incident).

# Requirements

- Modifies [FR-ART-004](../requirements/functional/FR-ART-004.md): what changes in the statement
  or acceptance criteria. A new requirement is written as its own concept, `status: draft`.

# Design

How each touched component changes: [core_mcp](../components/core_mcp.md) ...,
[sdlc_db](../components/sdlc_db.md) ... Alternatives considered. For a refactor, the tests that
pin today's behaviour before the work starts.

# Tasks

- [ ] Ordered steps, each small enough to review.

# Verification

Which tests or commands show each acceptance criterion holds.
```

Every requirement and component named in the frontmatter is linked in the body, and the other way
round; the lint checks. The work is finished in one pull request that carries the code, the
updated requirement and component concepts, the record set to `state: done`, and a line in
`log.md`. Changes made before the bundle existed are not backfilled.

# Changing the bundle

1. Edit or add the concept. A new requirement takes the next number in its area. When code
   changes what a component does, update its `satisfies` list and `# Requirements` section.
2. Add a line to `log.md`.
3. Run `uv run python scripts/okf_bundle.py build` and then `... lint`.
4. Commit the bundle change together with the code change it describes.
