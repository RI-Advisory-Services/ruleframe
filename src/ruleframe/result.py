from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


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
