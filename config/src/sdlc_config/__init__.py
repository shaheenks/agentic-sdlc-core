"""Validation and publishing of the platform's declared configuration."""

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2]


def load_all(config_dir: Path, env: str) -> dict[str, object]:
    """Parse every YAML file of the shared configuration and of the environment."""
    files = sorted(p for p in config_dir.glob("*.yaml"))
    env_dir = config_dir / "env" / env
    if env_dir.is_dir():
        files += sorted(env_dir.rglob("*.yaml"))
    return {p.relative_to(config_dir).as_posix(): yaml.safe_load(p.read_text(encoding="utf-8")) for p in files}
