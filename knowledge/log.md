# Change log

## 2026-11-10

- **Creation**: bundle scaffold (OKF 0.2), [conventions](conventions.md) and the
  `scripts/okf_bundle.py` lint and index tool.
- **Creation**: [system context](system/context.md), 36 functional and 32 non-functional
  requirements, drafted from `docs/FEATURE_INVENTORY.md`, `docs/ARCHITECTURE.md`, `CLAUDE.md` and
  `docs/plans/version-03.md`.
- **Update**: all 68 requirements reviewed and accepted; they are now `stable`.
- **Creation**: component register (22 components, accepted as a first version: `stable`) with `satisfies` and
  `verified_by` trace keys, and the generated [traceability matrix](traceability.md).
- **Update**: CI job `knowledge` runs the bundle lint; pull requests get a drift hint.
