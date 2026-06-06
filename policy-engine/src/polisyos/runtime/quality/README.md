# Runtime Quality

`polisyos.runtime.quality` owns Policy Design Case runtime-quality artifacts:
authority/status composition, evidence and claim binding, replay, closeout
checks, and audit-oriented exports.

This package may orchestrate producer-backed signals, but it does not make LLM
output, corpus stubs, simulations, or historical priors into current evidence
authority by itself. Those paths remain candidates, caps, context, or replay
inputs until a producer-owned capability admits them.

Rule replay lives in `rule_replay_engine.py`. Closed cases should replay through
their stored rule, capability, and data references, and C33 rule-change classes
must produce explicit revalidation triggers rather than silently changing old
closeout meaning.

Boundary notes:

- Prefer neutral contracts from `polisyos.core.contracts` when lower-level
  packages need DTOs or protocols.
- Keep runtime-only persistence, ledger, replay, and validation wiring in this
  package.
- `layer3_grounding_inventory.py` is the internal G0 pre-adapter inventory and
  firewall producer. It reads repository architecture/data artifacts, registers
  source touchpoints in shadow form, and enforces quarantine/status/import
  checks without admitting adapters or exporting a stable public facade.
- Public experimental exports must be reflected in the public-surface
  inventory and release fragments before release promotion.
