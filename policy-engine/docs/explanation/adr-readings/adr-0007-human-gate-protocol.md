# English reader translation of ADR-0007: Human Gate protocol in IR

Document type: English reader translation (informational derivative)  
Source pin: `af387828fbf27dce6dec8665286180df0dd10d1c`  
Source of truth: `docs/adr/0007-human-gate-protocol.md`

This page translates the decision text in the [source ADR](../../adr/0007-human-gate-protocol.md), whose SHA-256 is
`1fddfd8209db9a02b28ff492f7fa5c91420f8918827bddd7b87d8711bdf27cec`.
The generated ADR index reports the source status as `accepted` at the source
pin. This derivative does not ratify or revise the decision and does not
establish that the decision was implemented.

- **Date:** 2026-02-06
- **Status in source:** Accepted
- **Decision:** Move Human Gate contracts to
  `polisyos.ir.governance.gate` and centralize the lifecycle in
  `HumanGateProtocol`.

## Context

Human Gate was previously spread across:

- `ExperimentState.params["require_human_gate"]`
- `ExperimentState.params["gate_decision"]` (string / dictionary)
- `scientist.kernel.human_gate` (legacy models)

There was no formal CAS audit trail or stable request identity for retries.

## Decision

Introduce typed contracts:

- `GateContext`
- `GateRequest`
- `GateDecision`
- `GateEvent`

and an orchestration service:

- `HumanGateProtocol`
  (`src/polisyos/scientist/kernel/gate_protocol.py`)

Key properties:

- Deterministic `request_id`:
  `sha256("{run_id}:{phase}:{node_alias}:{iteration}")`

- Persist `GateRequest` / `GateDecision` in CAS
  (`ir.gate_request`, `ir.gate_decision`).
- Record `GATE_REQUESTED` / `GATE_DECIDED` in `trace.jsonl`.
- Correlate with OTel trace / span ID.
- Escalate without an infinite loop:
  `iteration += 1`, `is_escalated=true`, `priority=critical`.

## Migration and compatibility

- Migrate `RunGovernanceNode` to `HumanGateProtocol`.
- Support legacy decision formats (`"approve"`, `"reject"`,
  `{approved: bool}`) in the parser.
- Keep `scientist.kernel.human_gate` as a compatibility shim and mark it
  deprecated.
- Extend `ExperimentState.params` to a JSON-like structure for typed payloads.

## Consequences

### Advantages

- A formal, reproducible audit trail for gate decisions.
- Idempotent request identity for retry scenarios.
- One protocol layer for Scientist / UI / API.

### Disadvantages

- More state in `params` and more CAS artifacts.

### Risks

- Legacy consumers may rely on old fields.

### Mitigations

- Retain fallback parsing and the compatibility shim.
