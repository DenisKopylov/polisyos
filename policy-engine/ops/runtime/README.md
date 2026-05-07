# Runtime Operations

- Owner: `team-runtime`
- Artifact type: `runtime-operations-contracts`

`ops/runtime/` records deployment-facing runtime contracts that are not Python
source code: health/readiness, rollback, telemetry, and compatibility
expectations for operators.

The runtime implementation remains under `src/polisyos/runtime/`; this
directory is the operations baseline used by release, observability, and
migration reviews.
