# RuleFrame: Maintenance & Release Operations

> How to maintain `ruleframe` as a public PyPI package after initial release.
> Created: 2026-06-10 | Status: Draft

---

## Versioning Strategy

Use **Semantic Versioning** (`MAJOR.MINOR.PATCH`):

| Bump | When | Example |
|------|------|---------|
| PATCH (0.1.x) | Bug fixes, docs, internal refactors | Fix null handling edge case |
| MINOR (0.x.0) | New features, new predicates, new computed types | Add `starts_with` predicate |
| MAJOR (x.0.0) | Breaking API changes | Change `validate_dataframe()` signature |

**While at 0.x.y**: Minor bumps may include breaking changes (standard SemVer convention for pre-1.0). Document them clearly in CHANGELOG.

**Promote to 1.0.0** when:
- Public API is stable and you're confident in the surface
- At least one real downstream consumer relies on it in production
- You've had a few releases without needing breaking changes

---

## Release Workflow

### Standard Release Process

```
1. Work on feature branch → merge to main via PR
2. Update CHANGELOG.md (move items from Unreleased → new version section)
3. Bump version in pyproject.toml
4. Commit: "release: v0.2.0"
5. Push to main
6. Create GitHub Release with tag v0.2.0
7. publish.yml fires automatically → package on PyPI
```

### Single-Source Version

The version lives in **one place**: `pyproject.toml` → `version = "0.1.0"`.  
`__init__.py` reads it dynamically via `importlib.metadata.version("ruleframe")`. ✅ Already set up correctly.

### Detailed Steps for a Release

```bash
# 1. Ensure main is clean and CI passes
git checkout main && git pull

# 2. Update CHANGELOG.md
#    Move "Unreleased" items into a dated version section

# 3. Bump version
#    Edit pyproject.toml: version = "0.2.0"

# 4. Commit and push
git add pyproject.toml CHANGELOG.md
git commit -m "release: v0.2.0"
git push origin main

# 5. Create tag and release on GitHub
git tag v0.2.0
git push origin v0.2.0
# Then go to GitHub Releases → Create from tag → paste CHANGELOG section

# 6. Verify
#    - Check GitHub Actions publish workflow succeeded
#    - pip install --upgrade ruleframe in a test venv
#    - python -c "import ruleframe; print(ruleframe.__version__)"
```

---

## GitHub Actions CI/CD

### Current Workflows

| Workflow | Trigger | What It Does |
|----------|---------|--------------|
| `tests.yml` | Push to any branch, PRs | Run pytest across Python 3.10–3.14 matrix |
| `lint.yml` | Push to any branch, PRs | Ruff check + format + mypy |
| `publish.yml` | GitHub Release published | Build + publish to PyPI via Trusted Publisher |

### Recommended Additions

#### 1. Coverage Reporting (Enhancement)

Add to `tests.yml`:
```yaml
      - name: Upload coverage
        if: matrix.python-version == '3.12'
        uses: codecov/codecov-action@v5
        with:
          files: coverage.xml
```

And modify the pytest step:
```yaml
      - name: Run tests
        run: pytest --cov=ruleframe --cov-report=xml --cov-report=term-missing
```

Then add a Codecov badge to README. This gives visibility into test coverage over time.

#### 2. Dependency Review (Security)

Add `.github/workflows/dependency-review.yml`:
```yaml
name: Dependency Review
on: [pull_request]
jobs:
  dependency-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/dependency-review-action@v4
```

This flags new dependencies with known vulnerabilities on PRs.

#### 3. Release Drafter (Convenience, Optional)

Auto-generates release notes from PR titles. Useful once you have regular contributors.

---

## Branch & PR Strategy

### Recommended Branching Model

```
main (protected)
  ├── feature/add-starts-with-predicate
  ├── fix/null-handling-in-coercion
  └── release/v0.2.0  (optional, for coordinated releases)
```

**Rules for `main`:**
- Protected branch: require PR + passing CI
- No force pushes
- Squash merge PRs (clean history)

**Branch naming convention:**
- `feature/<short-description>`
- `fix/<short-description>`
- `docs/<short-description>`
- `chore/<short-description>` (deps, CI, tooling)

### PR Checklist (for your own reference or future contributors)

- [ ] Tests pass locally (`pytest`)
- [ ] Lint passes (`ruff check . && ruff format --check .`)
- [ ] Types pass (`mypy src/ruleframe/`)
- [ ] CHANGELOG.md updated (under "Unreleased")
- [ ] No breaking changes without version bump discussion

---

## Dependency Management

### Core Dependencies (keep minimal)

| Package | Why | Pin Strategy |
|---------|-----|--------------|
| `pandas >=2.0,<3.0` | Core data structure | Wide range for compatibility |
| `PyYAML >=6.0,<7.0` | Rule bundle parsing | Stable, rarely breaks |
| `python-dateutil >=2.8,<3.0` | Date parsing fallback | Very stable |
| `python-jsonlogic >=0.1.0,<1.0.0` | Evaluation engine | Pin tightly — this is your core engine |

### Updating Dependencies

```bash
# Check for outdated
pip list --outdated

# Test with latest
pip install --upgrade pandas PyYAML python-dateutil python-jsonlogic
pytest

# If tests pass, widen pins if needed
```

**When a dependency releases a major version (e.g., pandas 3.0):**
1. Create a branch
2. Update the pin in pyproject.toml
3. Run full test suite
4. Fix any breakages
5. Release a new minor/major version of ruleframe

### `python-jsonlogic` — Special Consideration

This is your most critical dependency and it's at `0.1.0`. Monitor it closely:
- Watch for breaking changes in their releases
- Consider vendoring or pinning very tightly if it becomes unstable
- If it goes unmaintained, you may need to fork or replace

---

## Handling Breaking Changes

### In Your Package

1. **Deprecation cycle** (for post-1.0):
   - Release N: Add `DeprecationWarning` for old behavior
   - Release N+1 (next major): Remove old behavior
   
2. **Pre-1.0**: Breaking changes are allowed in minor bumps. Just document clearly.

3. **Migration guides**: For significant breaks, add a `docs/migration-0.x-to-0.y.md`

### In Upstream Dependencies

If `python-jsonlogic` or `pandas` introduces a break:
- Pin to exclude the breaking version: `pandas >=2.0,<2.3` temporarily
- Fix compatibility
- Release a patch with the fix and widen the pin back

---

## Security Maintenance

### Automated Vulnerability Scanning

Enable **Dependabot** on GitHub:

`.github/dependabot.yml`:
```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

This auto-creates PRs when dependencies have known CVEs.

### If a Vulnerability Is Found in Your Code

1. Fix immediately on a branch
2. Release a PATCH version ASAP
3. Add a [GitHub Security Advisory](https://docs.github.com/en/code-security/security-advisories)
4. Consider requesting a CVE if it's serious

---

## Yanking a Bad Release

If you publish a broken version:

```bash
# Don't delete — yank instead (hides from install but doesn't break existing pins)
# Go to PyPI → Your project → Release → Yank

# Or via CLI:
# (Not directly supported — use the web UI)
```

Then immediately publish a fixed PATCH version.

---

## Monitoring & Observability

### What to Watch

| Metric | How |
|--------|-----|
| Download stats | https://pypistats.org/packages/ruleframe |
| GitHub issues | Enable issue templates |
| CI status | GitHub Actions dashboard |
| Dependency health | Dependabot alerts |
| Security advisories | GitHub Security tab |

### Issue Templates (Recommended)

Create `.github/ISSUE_TEMPLATE/bug_report.md`:
```markdown
---
name: Bug Report
about: Report a bug in ruleframe
---

**Package version**: 
**Python version**: 
**pandas version**: 

**Minimal reproducible example**:
```python
# paste code here
```

**Expected behavior**:
**Actual behavior**:
```

---

## Documentation Maintenance

### Current State
- User-facing: `docs/rules-format.md`, `docs/computed-columns.md` — keep these updated with each feature
- Internal: design docs — update when architecture changes

### When to Update Docs

| Change Type | Docs Action |
|-------------|-------------|
| New predicate | Add to `docs/rules-format.md` predicates table |
| New computed type | Add to `docs/computed-columns.md` |
| New public API function | Add to README or create API reference |
| Breaking change | Migration guide + CHANGELOG |
| Bug fix | CHANGELOG only |

### Future: MkDocs Site

When the project grows, stand up a proper docs site:
```bash
pip install -e ".[docs]"
mkdocs serve  # local preview
mkdocs gh-deploy  # deploy to GitHub Pages
```

The `[docs]` extras are already in pyproject.toml.

---

## Automation Opportunities (Future)

| Tool | Purpose | Priority |
|------|---------|----------|
| `python-semantic-release` | Auto-bump version + CHANGELOG from conventional commits | Medium — nice once you have regular releases |
| `release-drafter` | Auto-draft release notes from PR titles | Low — nice for multi-contributor |
| `pre-commit` | Run ruff/mypy on commit locally | Medium — prevents CI failures |
| Codecov | Track coverage trends | Medium — good for confidence |
| `towncrier` | CHANGELOG fragments per PR | Low — overkill for solo maintainer |

---

## Known Code Issues Backlog

These are minor issues identified at first release. Track them as follow-up work.

| File | Issue | Priority |
|------|-------|----------|
| `computed.py` | `_compute_group_sum`, `_compute_group_count`, `_compute_date_diff`, `_compute_days_since_today`, `_compute_years_since_year`, `compute_column` (divide case), `computed_column_name`, `computed_source_columns` all raise bare `ValueError` instead of `BundleValidationError` | Low |
| `operators.py` | `from_expression()` methods raise bare `ValueError` instead of a `RuleFrameError` subclass | Low |
| `dates.py` | Emits `UserWarning: Could not infer format` during flexible date parsing — expected behavior, but worth documenting explicitly in user-facing docs | Info |

---

## Operational Runbook

### "Tests are failing on a new Python version"

```bash
# 1. Check which tests fail
pytest -x  # stop at first failure

# 2. Common causes:
#    - pandas/numpy dropped support for that Python version
#    - dateutil behavior changed
#    - New Python deprecation warnings → failures in strict mode

# 3. Fix or drop the Python version from the matrix
#    Update pyproject.toml classifiers AND tests.yml matrix
```

### "A user reports a bug"

```bash
# 1. Reproduce locally
# 2. Write a failing test
# 3. Fix
# 4. Push to branch, PR to main
# 5. Release patch version
```

### "I need to make a breaking change"

```
Pre-1.0:
  1. Document in CHANGELOG under "Breaking"
  2. Bump minor version
  3. Release

Post-1.0:
  1. Add deprecation warning in current release
  2. Document migration path
  3. Remove in next major version
```

### "Dependency has a CVE"

```
1. Check if we're actually affected (do we use the vulnerable code path?)
2. If yes: pin to safe version, release patch
3. If no: update at leisure, still good to bump
4. Dependabot will likely auto-PR this
```

---

## Summary: Weekly Maintenance Routine (5 minutes)

Once the package is live, a lightweight weekly check:

1. **Glance at GitHub Actions** — any red builds?
2. **Check Dependabot PRs** — merge trivial ones, investigate security ones
3. **Check Issues** — any new bug reports?
4. **Check PyPI stats** (optional) — is anyone using it?

That's it. The CI automation handles the heavy lifting.
