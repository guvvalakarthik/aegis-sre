# Developer bootstrap

Issue #5 defines the supported local toolchain and a repeatable, least-privilege setup.

## Supported versions

| Tool | Minimum |
| --- | --- |
| Python | 3.12 |
| Git | 2.40 |
| Docker Engine or Docker Desktop | 24 |
| kubectl | 1.28 |
| Helm | 3.14 |
| Node.js | 20 |

The check is intentionally a minimum-version check. Project dependencies remain pinned by
the version ranges in pyproject.toml; no system package manager or elevated installer is
invoked by the bootstrap scripts.

## Windows

From PowerShell:

~~~powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\bootstrap.ps1
~~~

The execution-policy change is process-scoped and does not modify the machine policy. The
script creates .venv if needed, checks Docker and Kubernetes safety, upgrades pip inside
the virtual environment, and installs the project with development dependencies.

## Linux and macOS

From a shell:

~~~bash
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh
~~~

The script is idempotent: rerunning it reuses the virtual environment and reconciles the
editable development install.

## Safety checks

scripts/check-toolchain.py verifies:

- every required executable is available and meets the minimum version
- Docker is running with at least 2 CPUs and 4 GiB memory by default
- the current Kubernetes context exists
- contexts containing prod or production are rejected unless explicitly reviewed

To use a different Docker memory threshold:

~~~text
AEGIS_MIN_DOCKER_MEMORY_GIB=8
~~~

To override the production-context guard for a deliberate, reviewed operation:

~~~text
AEGIS_ALLOW_PRODUCTION_CONTEXT=1
~~~

Never place credentials in these variables or in .env.example. Keep real secrets in the
local environment or an approved secret manager.

## Quality gates

After bootstrap, run:

~~~bash
ruff format --check .
ruff check .
mypy src
pytest
docker build --tag aegis-sre:local .
~~~

The CI workflow runs the same quality checks. Attach the command output and the tool
versions to the Issue #5 validation evidence when verifying a clean machine.
