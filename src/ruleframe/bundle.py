from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


@dataclass(frozen=True)
class RuleBundle:
    """Container for loaded rule bundle configuration."""

    raw: dict[str, Any]

    @classmethod
    def from_yaml(cls, content: str) -> RuleBundle:
        parsed = yaml.safe_load(content)
        if not isinstance(parsed, dict):
            raise ValueError("Rule bundle YAML must deserialize to a dictionary")
        return cls(raw=parsed)

    @classmethod
    def from_json_dict(cls, value: dict[str, Any]) -> RuleBundle:
        return cls(raw=value)

    @property
    def version(self) -> int | None:
        value = self.raw.get("version")
        return int(value) if isinstance(value, int) else None

    @property
    def rules(self) -> list[dict[str, Any]]:
        value = self.raw.get("rules", [])
        if not isinstance(value, list):
            raise ValueError("rules must be a list")
        return value
