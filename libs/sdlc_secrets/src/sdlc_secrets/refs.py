"""Secret references (what config says) and secret values (what a resolver returns)."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

# Same patterns as config/schemas/source.schema.json (credentials).
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
SECRET_NAME = re.compile(r"^[a-z][a-z0-9-]*$")  # also a valid Secret Manager secret id


@dataclass(frozen=True)
class SecretRef:
    kind: str  # "env" | "secret"
    name: str

    def __post_init__(self) -> None:
        pattern = {"env": ENV_NAME, "secret": SECRET_NAME}.get(self.kind)
        if pattern is None:
            raise ValueError(f"unknown secret reference kind '{self.kind}' (env or secret)")
        if not pattern.fullmatch(self.name):
            raise ValueError(f"invalid {self.kind} secret name '{self.name}'")

    @classmethod
    def parse(cls, value: "Mapping[str, str] | tuple[str, str] | SecretRef") -> "SecretRef":
        """From config (`{env: NAME}` / `{secret: name}`) or a (kind, name) pair."""
        if isinstance(value, SecretRef):
            return value
        if isinstance(value, Mapping):
            if len(value) != 1:
                raise ValueError("a secret reference has exactly one of: env, secret")
            ((kind, name),) = value.items()
            return cls(kind, name)
        kind, name = value
        return cls(kind, name)

    def __str__(self) -> str:  # safe to log: names only
        return f"{self.kind}:{self.name}"


class SecretValue:
    """A secret string that does not print itself. Use `reveal()` at the point of use only."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError("empty secret value")
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "SecretValue(***)"

    __str__ = __repr__

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SecretValue) and other._value == self._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __reduce__(self):  # never pickled into caches, bundles or task payloads
        raise TypeError("SecretValue cannot be pickled")
