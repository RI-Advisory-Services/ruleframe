from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .exceptions import BundleValidationError


@dataclass(frozen=True)
class RuleBundle:
    """Container for loaded and structurally validated rule bundle configuration."""

    raw: dict[str, Any]

    def __post_init__(self) -> None:
        _validate_structure(self.raw)

    @classmethod
    def from_yaml(cls, path: str | Path) -> RuleBundle:
        content = Path(path).read_text(encoding="utf-8")
        return cls.from_yaml_string(content)

    @classmethod
    def from_json(cls, path: str | Path) -> RuleBundle:
        content = Path(path).read_text(encoding="utf-8")
        return cls.from_json_string(content)

    @classmethod
    def from_yaml_string(cls, content: str) -> RuleBundle:
        parsed = yaml.safe_load(content)
        if not isinstance(parsed, dict):
            raise BundleValidationError("Rule bundle YAML must deserialize to a dictionary")
        return cls(raw=parsed)

    @classmethod
    def from_json_string(cls, content: str) -> RuleBundle:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise BundleValidationError(f"Rule bundle JSON is invalid: {exc}") from exc
        if not isinstance(parsed, dict):
            raise BundleValidationError("Rule bundle JSON must deserialize to a dictionary")
        return cls(raw=parsed)

    @classmethod
    def from_json_dict(cls, value: dict[str, Any]) -> RuleBundle:
        if not isinstance(value, dict):
            raise BundleValidationError("Rule bundle must be a dictionary")
        return cls(raw=value)

    @property
    def version(self) -> int | None:
        value = self.raw.get("version")
        return int(value) if isinstance(value, int) else None

    @property
    def rules(self) -> list[dict[str, Any]]:
        value = self.raw.get("rules", [])
        if not isinstance(value, list):
            raise BundleValidationError("rules must be a list")
        return value

    @property
    def computed_columns(self) -> list[dict[str, Any]]:
        value = self.raw.get("computed_columns", [])
        if not isinstance(value, list):
            raise BundleValidationError("computed_columns must be a list")
        return value


def _validate_structure(raw: dict[str, Any]) -> None:
    """Validate bundle structure at construction time.

    Checks structural requirements (keys exist, correct types) but NOT
    semantic requirements (whether referenced columns exist in a DataFrame).
    """
    if "rules" in raw and not isinstance(raw["rules"], list):
        raise BundleValidationError("rules must be a list")

    if "computed_columns" in raw and not isinstance(raw["computed_columns"], list):
        raise BundleValidationError("computed_columns must be a list")

    for i, rule in enumerate(raw.get("rules", [])):
        if not isinstance(rule, dict):
            raise BundleValidationError(f"Rule at index {i} must be a dictionary")
        if "id" not in rule:
            raise BundleValidationError(f"Rule at index {i} is missing required field 'id'")
        if "fail_when" not in rule:
            raise BundleValidationError(
                f"Rule {rule['id']!r} is missing required field 'fail_when'"
            )
        if not isinstance(rule["fail_when"], dict):
            raise BundleValidationError(f"Rule {rule['id']!r} 'fail_when' must be a dictionary")
