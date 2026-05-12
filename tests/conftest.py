from pathlib import Path

import pandas as pd
import pytest

from ruleframe import RuleBundle

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "data" / "sample_data.csv")


@pytest.fixture
def sample_bundle() -> RuleBundle:
    text = (FIXTURES / "rules" / "sample_rules.yaml").read_text(encoding="utf-8")
    return RuleBundle.from_yaml(text)
