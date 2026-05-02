# Log Directory Unification Design

**Goal:** Align runtime config, sample config, Docker image defaults, and setup docs so container deployments can persist logs from a single `/log` mount while keeping Web and daemon logs separated.

## Scope

- Update the active runtime config in `supysonic.conf` to use `WEBAPP.log_dir = /log/web` and `DAEMON.log_dir = /log/daemon`.
- Update `config.sample` to demonstrate the same `/log` layout.
- Update `docs/setup/configuration.rst` sample config paths to match `/log/web` and `/log/daemon`.
- Update container startup so `/log/web` and `/log/daemon` exist even when `/log` is a bind mount.

## Non-Goals

- Do not remove code-level legacy support for `log_file`.
- Do not change log file names or routing behavior.
- Do not introduce Docker volume declarations or compose changes.

## Design

### Log Layout

- Web logs live under `/log/web`.
- Daemon logs live under `/log/daemon`.
- This avoids collisions because both sides write files such as `supysonic.log`.

### Runtime Behavior

- `supysonic.conf` stops using legacy `log_file` entries.
- The container image creates `/log/web` and `/log/daemon` for non-mounted runs.
- `setup.sh` also creates those directories on startup so bind-mounted `/log` works without precreating subdirectories on the host.

### Documentation Strategy

- Sample configuration should only show `log_dir` for the recommended path.
- Documentation can still describe legacy compatibility where accurate, but examples should prefer the `/log` layout.

## Verification

- Run `sh -n setup.sh` to verify shell syntax after startup-script changes.
- Run `git diff --check` on touched files to catch patch formatting issues.
- Docker build verification is optional and can be skipped if Docker is unavailable in the environment.
