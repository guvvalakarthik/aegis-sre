# Telemetry storage

Issue #8 defines a local, bounded telemetry stack for the aegis-lab Kubernetes environment.

## Components and retention

| Signal | Backend | Retention | Local storage |
| --- | --- | --- | --- |
| Metrics and alerts | Prometheus | 7 days / 8 GiB | 10 GiB PVC |
| Dashboards | Grafana | dashboard metadata | 2 GiB PVC |
| Logs | Loki | 7 days | 10 GiB PVC |
| Traces | Tempo | 7 days | 10 GiB PVC |
| Collection | OpenTelemetry Collector | bounded by backend retention | daemonset |

Chart versions are pinned in infra/telemetry/versions.env. The stack uses local PVCs suitable
for the disposable kind environment; it is not a production backup or disaster-recovery
configuration.

## Install and verify

Set a local Grafana password and run:

~~~bash
export GRAFANA_ADMIN_PASSWORD='use-a-local-secret'
bash scripts/telemetry-stack.sh install
bash scripts/telemetry-stack.sh verify
~~~

The password is passed through an environment variable and is never committed.

## Correlation contract

Every collector record must preserve:

- service.name, service.namespace, service.version
- deployment.environment
- pod, container, and node identity
- trace ID and span ID when available
- event timestamp and observed timestamp
- source backend and schema version

Grafana data sources should be configured as follows after install:

- Prometheus for metrics and exemplars
- Loki for logs with trace ID labels
- Tempo for traces with Loki and Prometheus derived-field links

A known checkout request must be followed by its trace ID across the three backends.

## Failure visibility

The collector and each backend expose health/readiness endpoints. The verification procedure
must record pod readiness, PVC binding, collector export errors, and dropped-signal counters.
A backend outage is a failed validation result; the stack must not silently claim ingestion.

## Cleanup

~~~bash
bash scripts/telemetry-stack.sh destroy
~~~

This uninstalls only the four named releases in the aegis-lab namespace. PVC deletion is
deliberately separate so evidence can be inspected before cleanup.
