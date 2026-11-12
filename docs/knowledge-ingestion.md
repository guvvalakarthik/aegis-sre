# Versioned knowledge ingestion protocol

All indexed chunks retain an exact source URI, version, commit, environment, timestamp, ACL,
content hash, parent relationship, and canonical chunk ID. Re-indexing identical content is
idempotent. A newer version revokes the prior active version, and explicit deletion/revocation
removes chunks from retrieval.

Ingestion rejects binary and unsupported formats and scans for secret-like values before chunking
or embedding. Retrieval is deny-by-default: a caller must share an ACL role with the chunk.
The index contract does not expose raw shell access or silently bypass authorization.

The in-memory implementation is an adapter contract for repository, incident, and document
connectors. Connector contract tests against real sources must publish counts, rejected files,
stale/deleted content, ACL failures, and freshness before Issue #26 is complete.
