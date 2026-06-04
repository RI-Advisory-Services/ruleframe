# RuleFrame

RuleFrame is a Python package for validating DataFrame and workbook data using declarative rule bundles.

## Project Status

This project is in early active development (alpha).

## Goals

- Validate tabular data with readable YAML or JSON rule bundles.
- Compile friendly rules to JsonLogic expressions.
- Evaluate all rules across all rows and return structured findings.
- Support computed columns in v1.

## Quick Start (Development)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Early API Shape

```python
from ruleframe import RuleBundle, validate_dataframe

# Load from a YAML or JSON file
bundle = RuleBundle.from_yaml("rules.yaml")
bundle = RuleBundle.from_json("rules.json")

# Load from raw string content (e.g. from S3, a database field, or an API response)
bundle = RuleBundle.from_yaml_string(yaml_text)
bundle = RuleBundle.from_json_string(json_text)

# Load from a pre-parsed dict (e.g. from a Django model or ORM)
bundle = RuleBundle.from_json_dict(data)

result = validate_dataframe(df, bundle)
```

## Documentation

- [Rule format](docs/rules-format.md)
- [Computed columns](docs/computed-columns.md)
- [Testing strategy](docs/testing-strategy.md)

## Scratch Notebooks

Use `scratch/` for local experimentation. This folder is gitignored by default.
