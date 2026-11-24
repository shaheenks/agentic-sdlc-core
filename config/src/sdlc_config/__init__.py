"""Validation, compilation and publishing of the platform's declared configuration (FR-CFG-001 to FR-CFG-005).

Shared files in `config/` declare the access model; `config/env/<env>/` holds what differs per environment
(OAuth client IDs, allowed domains, group emails, the static user list, the block list) and is git-ignored
except for `env/example/`. `compile_config` validates every file against its schema in `config/schemas/`,
checks the cross-references and returns the compiled bundle content that services read.
"""

from pathlib import Path

from sdlc_config.compile import ENV_KINDS, SHARED_KINDS, Compiled, compile_config

CONFIG_DIR = Path(__file__).resolve().parents[2]

__all__ = ["CONFIG_DIR", "ENV_KINDS", "SHARED_KINDS", "Compiled", "compile_config"]
