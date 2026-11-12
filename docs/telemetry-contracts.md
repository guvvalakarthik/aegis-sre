# Telemetry contracts

Issue #9 introduces versioned Pydantic contracts under src/aegis_sre/telemetry.

## Contract guarantees

Every record has:

- explicit schema version, signal kind, record ID, observed and received timestamps
- service identity and environment
- trace and span links when available
- source, source ID, collection timestamp, and redaction status
- strict unknown-field rejection

Supported v1 records are logs, metrics, traces, deployment changes, and Kubernetes events.

## Ingestion behavior

The reference InMemoryIngestStore demonstrates the adapter contract:

1. Redact secret-like keys and credential-shaped values before validation.
2. Validate against the signal-specific Pydantic model.
3. Quarantine invalid records with the original safe payload and error.
4. Deduplicate by record ID.
5. Keep the deterministically newest received record.
6. Preserve late records in quarantine or downstream archival policy rather than silently
   rewriting history.
7. Generate a stable SHA-256 fingerprint from canonical JSON.

Adapters for Prometheus, Loki, Tempo, OpenTelemetry, deployment metadata, and Kubernetes
events must map source responses into these contracts without dropping diagnosis-relevant
unknown fields. Contract and redaction tests must run against captured testbed samples before
a backend adapter is promoted.
