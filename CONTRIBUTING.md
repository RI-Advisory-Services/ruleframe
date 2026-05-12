# Contributing

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,jupyter]"
```

## Common Commands

```bash
pytest
pytest --cov=ruleframe --cov-report=term-missing
ruff check .
ruff format --check .
mypy src
python -m build
```

## Release Flow (Planned)

1. Ensure tests pass on CI.
2. Build package artifacts.
3. Publish to TestPyPI.
4. Validate install from TestPyPI.
5. Tag release and publish to PyPI.
