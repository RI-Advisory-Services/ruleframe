from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from .coercion import CoercionEvent


@dataclass(frozen=True)
class Finding:
    row_index: int
    rule_id: str
    rule_name: str | None
    severity: str
    message: str


@dataclass
class ValidationResult:
    """Result container for dataframe validation runs."""

    annotated: pd.DataFrame
    findings: list[Finding]
    working_dataframe: pd.DataFrame | None = field(default=None, repr=False)
    coercion_log: list[CoercionEvent] = field(default_factory=list)

    def to_annotated_dataframe(self) -> pd.DataFrame:
        return self.annotated.copy()

    def to_findings_dataframe(self) -> pd.DataFrame:
        rows: list[dict[str, Any]] = [
            {
                "row_index": f.row_index,
                "rule_id": f.rule_id,
                "rule_name": f.rule_name,
                "severity": f.severity,
                "message": f.message,
            }
            for f in self.findings
        ]
        return pd.DataFrame(rows)

    def to_summary_dataframe(self) -> pd.DataFrame:
        if not self.findings:
            return pd.DataFrame(columns=["rule_id", "severity", "count"])
        df = self.to_findings_dataframe()
        summary = (
            df.groupby(["rule_id", "severity"], as_index=False)
            .size()
            .rename(columns={"size": "count"})
        )
        return summary
