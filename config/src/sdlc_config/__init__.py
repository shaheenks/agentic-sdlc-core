"""Validation, compilation and publishing of the platform's declared configuration (FR-CFG-001 to FR-CFG-005).

Shared files in `config/` declare what is the same everywhere (tool groups, surfaces, limits, providers);
`config/env/<env>/` holds the environment's identity settings, users, block list, teams, user groups and knowledge
sources with what they are given, and is git-ignored except for `env/example/`. `compile_config` validates every
file against its schema in `config/schemas/`, checks the cross-references and returns the compiled bundle content
that services read.
"""

from pathlib import Path

from sdlc_config.compile import ENV_KINDS, SHARED_KINDS, Compiled, compile_config

CONFIG_DIR = Path(__file__).resolve().parents[2]

__all__ = ["CONFIG_DIR", "ENV_KINDS", "SHARED_KINDS", "Compiled", "compile_config"]
