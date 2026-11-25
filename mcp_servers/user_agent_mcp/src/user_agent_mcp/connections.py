"""The user's connection secrets under `secrets/users/<user ID>/<provider>.json` (DEC-0006, FR-CONN-001,
FR-CONN-005).

The secret is encrypted with AES-256-GCM under the data-encryption key from Secret Manager, with the user ID
and provider as associated data, so an object copied to another user's path cannot be decrypted. The object
records the key version. No tool result contains a secret: `list` returns metadata and status only.
"""

import base64
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from user_agent_mcp.artifacts import USER_ID
from user_agent_mcp.errors import ToolError

ACCOUNT = re.compile(r"^[^\s/\\]{1,200}$")


class Cipher:
    def __init__(self, key: bytes, key_version: str) -> None:
        self._aead = AESGCM(key)
        self.key_version = key_version

    def seal(self, plaintext: bytes, aad: bytes) -> dict:
        nonce = os.urandom(12)
        return {
            "key_version": self.key_version,
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(self._aead.encrypt(nonce, plaintext, aad)).decode(),
        }

    def open(self, sealed: dict, aad: bytes) -> bytes:
        try:
            return self._aead.decrypt(base64.b64decode(sealed["nonce"]), base64.b64decode(sealed["ciphertext"]), aad)
        except (InvalidTag, KeyError, ValueError) as exc:
            raise ToolError("unreadable", "the stored secret cannot be decrypted") from exc


class ConnectionStore:
    def __init__(self, root: Path, cipher: Cipher | None) -> None:
        self.root = Path(root)
        self.cipher = cipher

    def _user_dir(self, user_id: str) -> Path:
        if not USER_ID.match(user_id):
            raise ToolError("invalid_user", "unexpected user ID")
        return self.root / "secrets" / "users" / user_id

    @staticmethod
    def _aad(user_id: str, provider: str) -> bytes:
        return f"{user_id}/{provider}".encode()

    def save(
        self, user_id: str, provider: str, provider_config: dict, secret: str, account: str | None, base_url: str | None
    ) -> dict:
        if self.cipher is None:
            raise ToolError("unavailable", "connection secrets cannot be stored: no encryption key is configured")
        if not isinstance(secret, str) or not secret.strip() or len(secret) > 4096:
            raise ToolError("invalid_secret", "the secret must be 1-4096 characters")
        if account is not None and not ACCOUNT.match(account):
            raise ToolError("invalid_account", "unexpected account name")
        if provider_config["edition"] == "data_center":
            if not base_url or not base_url.startswith("https://") or len(base_url) > 300:
                raise ToolError("invalid_base_url", "a Data Center connection needs its server's https:// URL")
        else:
            base_url = provider_config.get("base_url")
        metadata = {
            "provider": provider,
            "system": provider_config["system"],
            "edition": provider_config["edition"],
            "account": account,
            "base_url": base_url,
            "saved_at": datetime.now(UTC).isoformat(),
        }
        sealed = self.cipher.seal(json.dumps({"secret": secret}).encode(), self._aad(user_id, provider))
        path = self._user_dir(user_id) / f"{provider}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"format": 1, "metadata": metadata, **sealed}), encoding="utf-8")
        return {**metadata, "status": "untested"}

    def list(self, user_id: str, providers: dict) -> list[dict]:
        base = self._user_dir(user_id)
        found = []
        for provider_id in sorted(providers):
            path = base / f"{provider_id}.json"
            if path.is_file():
                metadata = json.loads(path.read_text(encoding="utf-8")).get("metadata", {})
                found.append({**metadata, "status": "untested"})
        return found

    def revoke(self, user_id: str, provider: str) -> dict:
        path = self._user_dir(user_id) / f"{provider}.json"
        if not path.is_file():
            raise ToolError("not_found", "no such connection")
        path.unlink()
        return {"provider": provider, "revoked": True}

    def metadata(self, user_id: str, provider: str) -> dict:
        path = self._user_dir(user_id) / f"{provider}.json"
        if not path.is_file():
            raise ToolError("not_found", "no such connection")
        return json.loads(path.read_text(encoding="utf-8")).get("metadata", {})

    def credential(self, user_id: str, provider: str) -> tuple[str, str | None]:
        """The secret and account name, for connectors acting as the user; never returned by a tool."""
        return self.secret(user_id, provider), self.metadata(user_id, provider).get("account")

    def secret(self, user_id: str, provider: str) -> str:
        """For connectors acting as the user; never returned by a tool."""
        if self.cipher is None:
            raise ToolError("unavailable", "no encryption key is configured")
        path = self._user_dir(user_id) / f"{provider}.json"
        if not path.is_file():
            raise ToolError("not_found", "no such connection")
        sealed = json.loads(path.read_text(encoding="utf-8"))
        return json.loads(self.cipher.open(sealed, self._aad(user_id, provider)))["secret"]
