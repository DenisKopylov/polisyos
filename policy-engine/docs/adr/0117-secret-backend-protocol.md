# ADR-0117: Secret Backend Protocol

## Status
Proposed

## Date
2026-04-18

## Context

Environment variables are useful locally, but pipelines and runtime services
must support cloud and production secret managers without hardcoding env reads.
Secrets also need mandatory redaction in logs, manifests, and telemetry.

## Decision

Introduce a `SecretBackend` protocol:

```python
class SecretBackend(Protocol):
    def get(self, name: str) -> str | None: ...
```

Supported backends include env, dotenv, GCP Secret Manager, Vault, file-mounted
Kubernetes secrets, and future provider-specific implementations. Secret fields
are redacted or hashed before logging, telemetry, or manifest publication.

## Consequences

- Pipeline code stops depending directly on env layout.
- Cloud migration does not require rewiring domain pipelines.
- Secret scanning and redaction become enforceable gates.
