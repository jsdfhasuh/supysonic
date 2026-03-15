# AGENTS.md
Practical guide for coding agents working in `supysonic`.

## Mission
- Keep changes minimal, safe, and reviewable.
- Base decisions on repository evidence.
- Verify modified behavior with reproducible commands.

## Verified Project Facts
- Language/runtime: Python.
- Build backend: `setuptools.build_meta` (`pyproject.toml`).
- Test framework: `unittest` (primary).
- CI tests: coverage + unittest.
- Docs build: Sphinx via `docs/Makefile`.
- Core stack includes Flask and Peewee.

Evidence files:
- `.github/workflows/tests.yaml`
- `README-en.md`
- `pyproject.toml`
- `docs/Makefile`
- `setup.cfg`

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

CI-like dependency set:
```bash
pip install -r ci-requirements.txt
```

## Build Commands
Package:
```bash
python -m build
```
Docker image:
```bash
docker build -t supysonic .
```
Docs (run inside `docs/`):
```bash
make help
make html
sphinx-build -M html . _build
```

## Test Commands
Full suite:
```bash
python -m unittest
```
Network-dependent suite:
```bash
python -m unittest tests.net.suite
```
CI-equivalent coverage flow:
```bash
coverage run -m unittest
coverage run -a -m unittest tests.net.suite
coverage report -m
```

## Single-Test Commands (Important)
Run one module:
```bash
python -m unittest tests.api.test_media
```
Run one class:
```bash
python -m unittest tests.api.test_media.MediaTestCase
```
Run one test method:
```bash
python -m unittest tests.api.test_media.MediaTestCase.test_stream
```
Run a subtree via discovery:
```bash
python -m unittest discover -s tests/api -p "test_*.py"
```

## Run / Dev Commands
Flask dev server (Linux/macOS):
```bash
export FLASK_APP="supysonic.web:create_application()"
export FLASK_ENV=development
flask run
```
Flask dev server (Windows PowerShell):
```bash
$env:FLASK_APP="supysonic.web:create_application()"
$env:FLASK_ENV="development"
flask run
```
Installed entry points:
```bash
supysonic-cli --help
supysonic-server
supysonic-daemon
```

## Lint / Formatting Status
- No official project config detected for `ruff`, `flake8`, `black`, `isort`, `mypy`.
- Do not introduce new lint tooling unless task explicitly asks for it.
- Keep formatting consistent with touched files.

## Code Style Guidelines
### Imports
- Order groups as: stdlib -> third-party -> local modules.
- Avoid wildcard imports.
- Keep imports explicit and stable.

### Formatting
- Follow PEP 8 baseline in edited files.
- Prefer focused functions and shallow nesting.
- Add comments only for non-obvious logic.

### Types
- Add type hints for new or modified signatures.
- Prefer concrete types over `Any`.
- Use `Optional[T]` for nullable values.

### Naming
- New modules/files: `snake_case.py`.
- Variables/functions: `snake_case`.
- Classes: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Preserve legacy names unless rename is required for correctness.

### Error Handling
- Catch specific exceptions where possible.
- Avoid bare `except:` and silent swallow.
- Log debugging context (IDs, paths, key params).
- Keep API error behavior compatible with existing callers.

### Logging
- Use module logger: `logger = logging.getLogger(__name__)`.
- Use parameterized log messages.
- Never log secrets (passwords, tokens, keys).

### Data / DB Changes
- Reuse existing manager/model patterns first.
- Consider race conditions around unique constraints.
- Validate DB-related edits with targeted tests.

## Verification Discipline
- Run at least affected tests after edits.
- If impact is uncertain, run `python -m unittest`.
- Report what was verified and what was not.

## Git Safety
- Avoid destructive git operations.
- Do not mix unrelated refactors in one change.
- Do not change CI or major dependency versions unless requested.

## Cursor / Copilot Rules Check
Checked and not found:
- `.cursor/rules/`
- `.cursorrules`
- `.github/copilot-instructions.md`
If these are added later, apply the more specific rule first,
then treat this AGENTS.md as fallback guidance.
