from pathlib import Path

import pandas as pd
import pytest

from ruleframe import RuleBundle

FIXTURES = Path(__file__).parent / "fixtures"
DATA = FIXTURES / "data"
RULES = FIXTURES / "rules"


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.read_csv(DATA / "sample_data.csv")


@pytest.fixture
def sample_bundle() -> RuleBundle:
    return RuleBundle.from_yaml(RULES / "sample_rules.yaml")


@pytest.fixture
def workflow_split_node_df() -> pd.DataFrame:
    return pd.read_csv(DATA / "workflow_split_node_rows.csv")


@pytest.fixture
def workflow_split_node_bundle() -> RuleBundle:
    return RuleBundle.from_yaml(RULES / "workflow_split_node_rules.yaml")


@pytest.fixture
def computed_savings_df() -> pd.DataFrame:
    return pd.read_csv(DATA / "computed_savings_rows.csv")


@pytest.fixture
def computed_savings_bundle() -> RuleBundle:
    return RuleBundle.from_yaml(RULES / "computed_savings_rules.yaml")
