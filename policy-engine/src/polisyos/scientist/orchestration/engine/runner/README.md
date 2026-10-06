# Scientist workflow runners

Runner backends consume the engine's typed state, node outcomes and configuration.
Start with [`protocol.py`](protocol.py), [`local_runner.py`](local_runner.py),
[`config.py`](config.py) and [`serialization.py`](serialization.py).

## Unknown primary outcome

`PrimaryExecutionOutcomeUnknownError` means that the primary execution may have
produced an external effect before its response was lost. The fallback runner
preserves this error and does not replay the workflow on another backend.
Reconciliation needs the external owner's actual idempotency or status contract;
a local timeout, missing response or marker does not establish that nothing ran.

The real-effect consumer checks are in
`tests/unit/scientist/orchestration/engine/runner/test_fallback_runner.py`.

## Cross-process wire contract

Current writers emit `polisyos.scientist.state_wire.v2` and
`polisyos.scientist.outcome_wire.v2` envelopes. The decoder checks the exact
envelope and finite Decimal tags for budget values before model coercion.
Numeric, boolean, string and null substitutions for required tagged budget
values refuse in this profile. Journaled outcomes retain their nested
`polisyos.scientist.node_outcome.mutations.v1` schema.

Readers also support explicit legacy unversioned payloads and journal v1.
Legacy compatibility does not imply the v2 budget admission property. Safe
state framing has an independent version byte and SHA-256 integrity hash; the
frame is checked before decoding the payload schema.

`deserialize_outcome_batch(...)` returns `NativeNodeOutcomeBatch`. Consumers
admit success through the decoded native outcome status and exact batch member;
the presence of a completed alias alone does not establish successful execution.

Run the defining wire and compatibility checks from `policy-engine/`:

```bash
uv run pytest tests/unit/scientist/orchestration/engine/runner/test_serialization_e02.py tests/unit/scientist/orchestration/engine/runner/test_serialization.py
```
