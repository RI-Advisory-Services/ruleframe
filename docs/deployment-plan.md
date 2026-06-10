# RuleFrame: PyPI Deployment Plan

> Design doc for first public release of `ruleframe` to PyPI.
> Created: 2026-06-10 | Status: Draft

---

## Current State Assessment

| Dimension | Status | Notes |
|-----------|--------|-------|
| Package name `ruleframe` on PyPI | ✅ Available | Not yet registered |
| Tests (393 total) | ✅ All passing | 0.67s, 6 warnings (dateutil fallback, expected) |
| Ruff lint | ✅ Clean | 0 violations |
| Mypy strict | ✅ Clean | 0 errors in 11 source files |
| Package build | ✅ Works | sdist + wheel build clean |
| `twine check` | ✅ Passes | Requires twine ≥6.0 for Metadata-Version 2.4 |
| GitHub Actions CI | ✅ Exists | lint.yml, tests.yml (Python 3.10–3.14), publish.yml |
| GitHub repo | ⚠️ Private | `RI-Advisory-Services/ruleframe` — needs to go public |
| README | ⚠️ Dev-focused | Needs user-facing quickstart for PyPI landing page |
| CHANGELOG | ❌ Missing | Needed before first release |
| PyPI account/token | ❌ Not configured | Trusted Publisher or API token needed |
| openpyxl dependency | ⚠️ Not in core deps | Hand-installed; decide if it's a core or optional dep |

---

## Step-by-Step Deployment Checklist

### Phase 1: Pre-Release Housekeeping

These are tasks that should be done before any publish attempt.

#### 1.1 Fix `pyproject.toml` URLs

```toml
[project.urls]
Homepage = "https://github.com/RI-Advisory-Services/ruleframe"
Documentation = "https://github.com/RI-Advisory-Services/ruleframe/tree/main/docs"
Repository = "https://github.com/RI-Advisory-Services/ruleframe"
Issues = "https://github.com/RI-Advisory-Services/ruleframe/issues"
```

**Decision needed**: Will the repo stay under `RI-Advisory-Services` or move to a personal/org account more suited for open-source?

#### 1.2 Decide on `openpyxl`

Options:
- **A) Optional dependency** (recommended): Add `[excel]` extra in pyproject.toml. Users who need Excel I/O install `pip install ruleframe[excel]`. This keeps the core dependency footprint minimal.
- **B) Core dependency**: Add to `dependencies` list. Simpler for users but heavier.
- **C) Dev-only**: If it's only used in tests/scratch, leave it in `[dev]` extras only.

Current evidence: `openpyxl` is in `[dev]` extras already. If it's not imported anywhere in `src/ruleframe/`, keep it dev-only.

#### 1.3 Add `CHANGELOG.md`

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-XX

### Added
- Core validation pipeline: load → validate → compile → coerce → evaluate
- YAML and JSON rule bundle loading (`RuleBundle.from_yaml()`, `.from_json()`, etc.)
- 30+ predicates (equality, comparison, date, membership, blank-checking)
- 12 computed column types (arithmetic, group aggregates, date operations)
- Type inference and numeric coercion with conflict detection
- Null-safe comparison operators
- Date normalization (flexible and strict parsing modes)
- `ValidationResult` with annotated DataFrame, findings DataFrame, and summary
- Custom JsonLogic operator registry
- Full test suite (393 tests)
- GitHub Actions CI (lint, test matrix 3.10–3.14, publish)
```

#### 1.4 Polish README for PyPI

The README renders as the PyPI project page. It needs:
- One-line tagline
- Badges (CI status, PyPI version, Python versions, license)
- Install command (`pip install ruleframe`)
- Minimal working example (5-10 lines of Python + a small YAML rule)
- Link to full docs

#### 1.5 Author / Maintainer Metadata

Update `pyproject.toml`:
```toml
authors = [
  { name = "Your Name", email = "you@example.com" }
]
maintainers = [
  { name = "Your Name", email = "you@example.com" }
]
```

PyPI shows this publicly. Use a real maintainer identity.

#### 1.6 Verify `py.typed` Marker

Already present at `src/ruleframe/py.typed` — this tells tools (mypy, pyright) that the package ships inline type hints. ✅

---

### Phase 2: TestPyPI Dry Run

**Do this before touching real PyPI.** TestPyPI is a sandbox.

#### 2.1 Create Accounts

1. Create account at https://test.pypi.org/account/register/
2. Create account at https://pypi.org/account/register/
3. Enable 2FA on both (required for new projects)

#### 2.2 Configure Trusted Publisher (Recommended)

This is the modern approach — no API tokens to manage.

On **TestPyPI** → Your Account → Publishing → Add a new pending publisher:
- PyPI project name: `ruleframe`
- Owner: `RI-Advisory-Services`
- Repository: `ruleframe`
- Workflow name: `publish.yml`
- Environment name: (leave blank or use `release`)

Repeat on **PyPI** when ready for production.

The existing `publish.yml` already has `id-token: write` permission — it's set up for trusted publishing.

#### 2.3 Test Build & Upload to TestPyPI

```bash
# Clean and rebuild
rm -rf dist/ build/
python -m build

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Test install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ ruleframe
```

**Or via GitHub Actions**: Temporarily modify `publish.yml` to target TestPyPI:
```yaml
- name: Publish to TestPyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  with:
    repository-url: https://test.pypi.org/legacy/
```

#### 2.4 Validate the TestPyPI Install

```python
# In a fresh venv:
from ruleframe import RuleBundle, validate_dataframe, __version__
print(__version__)  # Should print "0.1.0"
```

---

### Phase 3: First Real Release

#### 3.1 Make Repo Public

GitHub → Settings → Danger Zone → Change visibility → Public

**Before doing this, audit for:**
- ❌ No secrets/credentials in git history
- ❌ No internal company data in fixtures or scratch/
- ✅ LICENSE file present (MIT)
- ✅ .gitignore covers scratch/

#### 3.2 Create GitHub Release

```bash
git tag v0.1.0
git push origin v0.1.0
```

Then on GitHub → Releases → Create release from tag `v0.1.0`:
- Title: `v0.1.0 — Initial Release`
- Body: Copy from CHANGELOG.md
- Mark as pre-release (since it's alpha)

This triggers `publish.yml` → package goes to PyPI automatically.

#### 3.3 Verify on PyPI

- Visit https://pypi.org/project/ruleframe/
- Confirm README renders correctly
- Confirm metadata (license, classifiers, URLs) look right
- Test `pip install ruleframe` from real PyPI in a clean venv

---

### Phase 4: Post-Release

#### 4.1 Add PyPI Badge to README

```markdown
[![PyPI](https://img.shields.io/pypi/v/ruleframe)](https://pypi.org/project/ruleframe/)
[![Python](https://img.shields.io/pypi/pyversions/ruleframe)](https://pypi.org/project/ruleframe/)
[![License](https://img.shields.io/pypi/l/ruleframe)](https://github.com/RI-Advisory-Services/ruleframe/blob/main/LICENSE)
[![Tests](https://github.com/RI-Advisory-Services/ruleframe/actions/workflows/tests.yml/badge.svg)](https://github.com/RI-Advisory-Services/ruleframe/actions/workflows/tests.yml)
```

#### 4.2 Register on GitHub Topics

Add topics to the repo: `python`, `validation`, `dataframe`, `pandas`, `jsonlogic`, `yaml`, `rules-engine`

---

## Design Decisions

| # | Decision | Resolution |
|---|----------|------------|
| 1 | GitHub org for public repo | Stay under `RI-Advisory-Services` — it's a work product |
| 2 | `openpyxl` placement | Dev-only (already in `[dev]` extras at `>=3.1,<4.0`; not imported in `src/`) |
| 3 | Version scheme | SemVer (already using 0.1.0) |
| 4 | Pre-release label | Ship as `0.1.0` with Alpha classifier; promote to `1.0.0` when API stabilizes |
| 5 | Authentication method | Trusted Publisher (already scaffolded in `publish.yml`) |
| 6 | README rewrite | Owner will rewrite with real quickstart + examples before publish |
| 7 | Documentation hosting | GitHub `docs/` folder for now; mkdocs later when needed |
| 8 | Python 3.14 support | Keep — tests pass in CI matrix |

---

## Known Gaps / Minor Issues Found During Review

| Issue | Severity | Status | Action |
|-------|----------|--------|--------|
| `computed.py` uses bare `ValueError` instead of `BundleValidationError` in ~6 places (`_compute_group_sum`, `_compute_group_count`, `_compute_date_diff`, `_compute_days_since_today`, `_compute_years_since_year`, `compute_column` divide case, `computed_column_name`, `computed_source_columns`) | Low | ⏳ Backlog | Owner to fix in follow-up PR; not blocking for release |
| `operators.py` bare `ValueError` in `from_expression()` methods | Low | ⏳ Backlog | Same — internal validation, not user-facing |
| `dates.py` emits `UserWarning` about format inference during flexible date parsing | Info | ✅ Expected | Document in user-facing docs; suppress in tests with `pytest.warns` if desired |
| `examples/` folder is empty | Medium | ⏳ Backlog | Owner will add minimal example before or shortly after first release |
| `twine` pin updated from `>=5.1,<6.0` → `>=6.0,<7.0` | Low | ✅ Fixed | Metadata-Version 2.4 requires twine ≥6.0 |
| `project.urls` still has `your-org` placeholder | **Blocking** | ⏳ Todo | Must fix before publish |
| `authors` field has no real name/email | **Blocking** | ⏳ Todo | Must fix before publish |
| No `description-content-type` explicit field | Info | ✅ OK | setuptools infers from `readme = "README.md"` |

---

## Minimal Viable Release Checklist (Do These, Ship It)

**pyproject.toml fixes:**
- [ ] Fix `project.urls` (replace `your-org` → `RI-Advisory-Services`)
- [ ] Update `authors` with real name and email

**Code quality (before release):**
- [ ] Fix bare `ValueError` → `BundleValidationError` in `computed.py` (~6 places)
- [ ] Fix bare `ValueError` in `operators.py` `from_expression()` methods

**Docs & changelog:**
- [ ] Add `CHANGELOG.md`
- [ ] Rewrite `README.md` with install command and minimal working example
- [ ] Add at least one example to `examples/`

**PyPI setup:**
- [ ] Create PyPI + TestPyPI accounts, enable 2FA
- [ ] Configure Trusted Publisher on TestPyPI
- [ ] Test publish to TestPyPI
- [ ] Validate install from TestPyPI in a clean venv

**Go live:**
- [ ] Make repo public (audit git history for secrets/internal data first)
- [ ] Configure Trusted Publisher on real PyPI
- [ ] Create GitHub release with tag `v0.1.0`
- [ ] Verify on PyPI — confirm README renders, metadata looks right
- [ ] Add PyPI/CI badges to README

---

## Appendix: Files Modified for Release

| File | Change |
|------|--------|
| `pyproject.toml` | Fix URLs, update authors, bump twine pin |
| `README.md` | Add badges, install command, quick example |
| `CHANGELOG.md` | New file |
| `examples/basic_validation.py` | New file (minimal example) |
| `.github/workflows/publish.yml` | Potentially add TestPyPI step |
