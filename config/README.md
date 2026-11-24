# config

The platform's declared access model: YAML in this folder, validated by `sdlc-config` and published as a
bundle to the configuration bucket ([FR-CFG-004](../spec/requirements/functional/FR-CFG-004.md),
[FR-CFG-005](../spec/requirements/functional/FR-CFG-005.md)). A person activates a bundle per environment.

**Phase 0 skeleton:** `sdlc-config validate --env local` parses every YAML file and fails on syntax errors.
Schemas, the permission diff and publishing come in phase 1.

Environment-specific files go under `env/<env>/`; files with user or group identities there are git-ignored.
