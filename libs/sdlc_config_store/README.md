# sdlc_config_store

The bundle format, the active-version pointer, and `ConfigStore`, which services use to read the active bundle
from a folder or the configuration bucket ([Configuration Registry](../../spec/components/configuration-registry.md);
FR-CFG-001, FR-CFG-003, FR-CFG-005). Without a verified bundle, `ConfigStore` raises `ConfigUnavailable` and the
service refuses the request. Test from this folder: `uv run pytest`.
