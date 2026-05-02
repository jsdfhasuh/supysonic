# Mainline Logging Gap Closure Design

**Goal:** Close the remaining mainline runtime logging gaps so Web, daemon, and foreground scan flows consistently use the managed logging system instead of ad-hoc output.

**Scope**
- Add persistent Web debug logging.
- Initialize managed logging for CLI foreground scanning.
- Replace runtime-path `print()` calls with logger-based output in mainline modules.
- Keep existing category files and summary log behavior intact.

**Out of Scope**
- No repository-wide print cleanup.
- No new `frontend.log` or broad category expansion.
- No logging overhaul for edge integrations like `MusicBrainz.py` or `spotify.py`.
- No large-scale rewrite of existing free-form text logs into structured events.

**Mainline Gaps Being Closed**
- Web file logging currently drops `DEBUG` records because all Web file handlers are `INFO+` only.
- Foreground CLI scanning does not initialize the managed logging system.
- Several runtime-path modules still emit `print()` directly, bypassing all managed handlers.

**Architecture**
- Extend `supysonic/logging_manager.py` so Web logging mirrors daemon behavior for debug persistence via `web.debug.log`.
- Add a minimal CLI logging setup path that reuses the existing managed logging config and routes foreground scan logs through the Web logging manager.
- Replace `print()` with module loggers in runtime-path code, preserving user-facing `click.echo()` scan summaries.

**Implementation Boundaries**
- Replace `print()` only in these mainline runtime files:
  - `supysonic/api/media.py`
  - `supysonic/frontend/__init__.py`
  - `supysonic/scanner_func/scanner_enrich.py`
  - `supysonic/api/search.py`
- Leave edge modules such as `MusicBrainz.py` and `spotify.py` untouched for now.
- Keep existing Web category routing unchanged except for adding a Web debug file.

**Verification Strategy**
- Extend logging manager tests to verify Web debug file creation and persistence.
- Add/extend CLI-focused tests to verify foreground scan logging initialization and log file creation.
- Add targeted regression tests for the converted runtime `print()` paths where practical.

**Risk Notes**
- Foreground scan logging must not break existing CLI output expectations.
- Web debug persistence should not change existing `INFO+` category routing semantics.
