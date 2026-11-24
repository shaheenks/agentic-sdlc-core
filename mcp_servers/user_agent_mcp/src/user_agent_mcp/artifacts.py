"""The user's own artifacts under `artifacts/users/<user ID>/` of the mounted artifact bucket (FR-ART-001,
FR-ART-002, FR-AUTHZ-008, DEC-0006).

Every path is built here from the verified user ID; a tool argument only names an artifact. Each version is
two objects, `<name>/<NNNN>.json` (metadata) and `<name>/<NNNN>.content`, so the bucket's lifecycle rule
deletes each version 7 days after it was written and earlier versions stay readable meanwhile.
"""

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from user_agent_mcp.errors import ToolError

NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
USER_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
LABEL = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")


def _check_name(name: object) -> str:
    if not isinstance(name, str) or not NAME.match(name) or ".." in name:
        raise ToolError("invalid_name", "an artifact name is 1-100 letters, digits, '.', '_' or '-'")
    return name


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _user_dir(self, user_id: str) -> Path:
        if not USER_ID.match(user_id):
            raise ToolError("invalid_user", "unexpected user ID")
        return self.root / "artifacts" / "users" / user_id

    def _artifact_dir(self, user_id: str, name: str) -> Path:
        base = self._user_dir(user_id)
        path = base / _check_name(name)
        if path.resolve().parent != base.resolve():  # defence in depth: never leave the user's prefix
            raise ToolError("invalid_name", "name leaves the user's artifacts")
        return path

    @staticmethod
    def _versions(path: Path) -> list[int]:
        if not path.is_dir():
            return []
        return sorted(int(p.stem) for p in path.glob("*.json") if p.stem.isdigit())

    def save(
        self,
        user_id: str,
        name: str,
        content: str,
        content_type: str,
        *,
        allowed_types: list[str],
        max_bytes: int,
        lineage: dict[str, str | None],
        classification: str,
    ) -> dict:
        if content_type not in allowed_types:
            raise ToolError("invalid_type", f"content type must be one of {', '.join(allowed_types)}")
        data = content.encode("utf-8")
        if len(data) > max_bytes:
            raise ToolError("too_large", f"an artifact holds at most {max_bytes} bytes")
        for key, value in lineage.items():
            if value is not None and not LABEL.match(value):
                raise ToolError("invalid_lineage", f"{key} has unexpected characters")
        if not LABEL.match(classification):
            raise ToolError("invalid_classification", "classification has unexpected characters")
        path = self._artifact_dir(user_id, name)
        path.mkdir(parents=True, exist_ok=True)
        version = (self._versions(path) or [0])[-1] + 1
        while True:
            try:
                with open(path / f"{version:04d}.content", "xb") as handle:  # exclusive: no overwrite
                    handle.write(data)
                break
            except FileExistsError:
                version += 1
        meta = {
            "name": name,
            "version": version,
            "owner": user_id,
            "content_type": content_type,
            "size": len(data),
            "classification": classification,
            "created_at": datetime.now(UTC).isoformat(),
            **{k: v for k, v in lineage.items() if v is not None},
        }
        (path / f"{version:04d}.json").write_text(json.dumps(meta), encoding="utf-8")
        return meta

    def _meta(self, path: Path, version: int) -> dict:
        return json.loads((path / f"{version:04d}.json").read_text(encoding="utf-8"))

    def list(self, user_id: str) -> list[dict]:
        base = self._user_dir(user_id)
        if not base.is_dir():
            return []
        found = []
        for path in sorted(p for p in base.iterdir() if p.is_dir()):
            versions = self._versions(path)
            if versions:
                found.append({**self._meta(path, versions[-1]), "versions": versions})
        return found

    def read(self, user_id: str, name: str, version: int | None = None) -> dict:
        path = self._artifact_dir(user_id, name)
        versions = self._versions(path)
        if not versions or (version is not None and version not in versions):
            raise ToolError("not_found", "no such artifact")
        version = version or versions[-1]
        content = (path / f"{version:04d}.content").read_text(encoding="utf-8")
        return {**self._meta(path, version), "versions": versions, "content": content}

    def delete(self, user_id: str, name: str) -> dict:
        path = self._artifact_dir(user_id, name)
        if not self._versions(path):
            raise ToolError("not_found", "no such artifact")
        shutil.rmtree(path)
        return {"name": name, "deleted": True}
