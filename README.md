# AegisSRE

AegisSRE is an evidence-grounded, safety-gated reliability engineering platform for
detecting, diagnosing, and remediating incidents in Kubernetes workloads.

The system is being built as a sequence of independently reviewable milestones. It does
not claim capabilities before they are implemented and evaluated.

## Current status

Milestone 1 establishes the production repository, typed configuration, structured
logging, health contracts, Prometheus instrumentation, container build, and CI quality
gates. Incident detection and remediation are intentionally not part of this milestone.

## Target capabilities

- Correlate OpenTelemetry logs, metrics, traces, and deployment events.
- Detect anomalies using statistical, classical ML, deep learning, and transformer models.
- Build evidence-linked root-cause hypotheses from topology, code, and operational data.
- Execute diagnostics through typed, least-privilege tools.
- Validate remediations in a sandbox and require approval for risky changes.
- Measure detection, diagnosis, recovery, safety, latency, and cost on reproducible incidents.

## Repository layout

```text
src/aegis_sre/        Python control-plane package
tests/                Executable unit and integration contracts
docs/architecture/    System boundaries and architecture
docs/adr/             Architecture decision records
.github/workflows/    Continuous integration
```

The repository will expand by bounded context as each milestone is implemented. Empty
placeholder packages are not committed.

## Local development

Requirements:

- Python 3.12
- Docker 24 or newer

Create an isolated environment and install the development dependencies:

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run the control plane:

```bash
aegis-api
```

Validate the service:

```bash
curl http://localhost:8080/health/live
curl http://localhost:8080/health/ready
curl http://localhost:8080/metrics
```

Run all quality gates:

```bash
ruff format --check .
ruff check .
mypy src
pytest
```

Alternatively, build and run the hardened container:

```bash
docker compose up --build
```

## Delivery rules

- Each milestone is developed on a dedicated branch and reviewed through a pull request.
- A capability is documented only after an executable implementation exists.
- Synthetic incidents include ground truth and deterministic reproduction metadata.
- Model results are reported from versioned evaluation runs, never manually invented.
- Remediation tools are typed and allowlisted; the language model never receives a raw shell.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and
[system-context.md](docs/architecture/system-context.md) for the system boundary.

## Team collaboration

The project uses one task per branch, reciprocal pull-request reviews, and an equal
100-point ownership split between Karthik and Trivedi. The canonical upstream remains in
Karthik's account and Trivedi works through a personal fork so the project is visible from
both GitHub profiles.

Read the [collaboration charter](docs/team-collaboration-plan.md) or download the
[print-ready PDF](docs/AegisSRE-Team-Collaboration-Plan.pdf).

## License

MIT
