# Log Directory Unification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move recommended container log configuration to `/log/web` and `/log/daemon` while ensuring the directories exist at runtime.

**Architecture:** Keep the existing logging implementation unchanged and only update configuration, documentation, and container startup defaults. Use startup-time directory creation so bind-mounted `/log` works without relying on image-layer directories.

**Tech Stack:** INI config, Dockerfile, POSIX shell, reStructuredText

---

### Task 1: Update runtime config

**Files:**
- Modify: `supysonic.conf`

**Step 1: Replace legacy web log path**

- Remove the old `WEBAPP.log_file` entry.
- Add `WEBAPP.log_dir = /log/web`.
- Keep existing log level and rotation settings.

**Step 2: Replace legacy daemon log path**

- Remove the old `DAEMON.log_file` entry.
- Add `DAEMON.log_dir = /log/daemon`.
- Add `DAEMON.log_backup_count = 7` if missing so the runtime config matches the current managed logging options.

### Task 2: Update recommended sample config

**Files:**
- Modify: `config.sample`

**Step 1: Point web sample logs to `/log/web`**

- Change the sample `WEBAPP.log_dir` path from `/var/supysonic/logs/web` to `/log/web`.
- Remove the commented legacy `log_file` example from the sample block.

**Step 2: Point daemon sample logs to `/log/daemon`**

- Change the sample `DAEMON.log_dir` path from `/var/supysonic/logs/daemon` to `/log/daemon`.
- Remove the commented legacy `log_file` example from the sample block.

### Task 3: Update configuration docs

**Files:**
- Modify: `docs/setup/configuration.rst`

**Step 1: Align web examples**

- Change web sample config paths to `/log/web`.
- Remove the sample `log_file` lines from the web config example.

**Step 2: Align daemon examples**

- Change daemon sample config paths to `/log/daemon`.
- Remove the sample `log_file` lines from the daemon config example.

### Task 4: Ensure runtime directories exist in containers

**Files:**
- Modify: `Dockerfile`
- Modify: `setup.sh`

**Step 1: Create image-level defaults**

- Add a Dockerfile step that creates `/log/web` and `/log/daemon`.

**Step 2: Create startup-time directories**

- Add `mkdir -p /log/web /log/daemon` near the top of `setup.sh`.
- Keep the rest of the startup flow unchanged.

### Task 5: Verify text and shell changes

**Files:**
- Verify: `supysonic.conf`
- Verify: `config.sample`
- Verify: `docs/setup/configuration.rst`
- Verify: `Dockerfile`
- Verify: `setup.sh`

**Step 1: Check shell syntax**

Run: `sh -n setup.sh`
Expected: no output, exit code 0

**Step 2: Check patch formatting**

Run: `git diff --check -- supysonic.conf config.sample docs/setup/configuration.rst Dockerfile setup.sh docs/plans/2026-05-01-log-directory-unification-design.md docs/plans/2026-05-01-log-directory-unification.md`
Expected: no output, exit code 0
