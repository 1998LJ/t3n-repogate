# Contributing to RepoGate

Thank you for contributing to RepoGate! We welcome contributions that improve code quality, strengthen security boundaries, and expand automated audit capabilities.

---

## 1. Development Setup

Requirements:
- **Python >= 3.10** (tested through Python 3.14)
- **Node.js >= 24** (only required for cross-language compatibility oracle tests)

```bash
# Clone the repository
git clone https://github.com/1998LJ/t3n-repogate.git
cd t3n-repogate

# Create and activate a clean virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with development dependencies
pip install -e ".[dev]"

# (Optional) Install Node dependencies if testing cryptographic reference oracle
npm ci
```

---

## 2. Required Quality Gates

Before submitting a Pull Request, all local checks must pass:

```bash
# 1. Linting and formatting
ruff check .
ruff format --check .

# 2. Python test suite (includes CLI, 6-Gate, and adversarial tests)
python3 -m unittest discover -s tests -v

# 3. Node reference oracle verification
npm test

# 4. Isolated package build
python3 -m build
```

---

## 3. Contribution Guidelines

- **Scoped Changes**: Keep PRs focused on a single responsibility. Large architectural overhauls should be preceded by an issue discussion.
- **Test Coverage**: All bug fixes must include regression tests. All new features must include unit tests.
- **Protocol Stability**: Do not modify the `T3N-REPOGATE-v1-ECDSA` cryptographic standard, report JSON schemas, or canonical DID bindings without prior architectural consensus.
- **Supply Chain & Hygiene**:
  - Never commit credentials, private keys, `.secret` files, or production tokens.
  - Never commit build artifacts (`dist/`, `build/`, `*.egg-info`), virtual environments, or `node_modules/`.
- **Legacy Compatibility**: Keep legacy compatibility shims intact (e.g. `repogate_engine.py`) to prevent breaking external integrations.

---

## 4. Pull Request Review & CI Acceptance

All Pull Requests trigger an automated GitHub Actions matrix testing:
- Code style & format (`ruff`)
- Python matrix (`3.10`, `3.11`, `3.12`, `3.13`, `3.14`)
- Node 24 compatibility oracle (`node-reference`)
- Clean wheel build, artifact audit, and outside-repo smoke test (`build-and-smoke`)

PRs must achieve a 100% green build before merge.
