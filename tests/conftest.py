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


@pytest.fixture
def arithmetic_df() -> pd.DataFrame:
    return pd.read_csv(DATA / "arithmetic_rows.csv")


@pytest.fixture
def arithmetic_bundle() -> RuleBundle:
    return RuleBundle.from_yaml(RULES / "arithmetic_rules.yaml")


@pytest.fixture
def group_aggregate_df() -> pd.DataFrame:
    return pd.read_csv(DATA / "group_aggregate_rows.csv")


@pytest.fixture
def group_aggregate_bundle() -> RuleBundle:
    return RuleBundle.from_yaml(RULES / "group_aggregate_rules.yaml")


@pytest.fixture
def date_df() -> pd.DataFrame:
    return pd.read_csv(DATA / "date_rows.csv")


@pytest.fixture
def date_bundle() -> RuleBundle:
    return RuleBundle.from_yaml(RULES / "date_rules.yaml")


@pytest.fixture
def savings_flag_df() -> pd.DataFrame:
    return pd.read_csv(DATA / "savings_flag_rows.csv")


@pytest.fixture
def savings_flag_bundle() -> RuleBundle:
    return RuleBundle.from_yaml(RULES / "savings_flag_rules.yaml")
