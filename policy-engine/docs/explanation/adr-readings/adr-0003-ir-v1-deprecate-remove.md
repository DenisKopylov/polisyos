# English reader translation of ADR-0003: Deprecate and remove IR v1

Document type: English reader translation (informational derivative)  
Source pin: `af387828fbf27dce6dec8665286180df0dd10d1c`  
Source of truth: `docs/adr/0003-ir-v1-deprecate-remove.md`

This page translates the decision text in the [source ADR](../../adr/0003-ir-v1-deprecate-remove.md), whose SHA-256 is
`abfbfec2979fa03dbc514203289194d1cb1f1cbe43674494a62c9b0f864745b8`.
The generated ADR index reports the source status as `unknown` at the source pin.
This derivative does not ratify or revise the decision and does not establish
that the decision was implemented.

- **Date:** 2026-01-12
- **Decision:** Accept only `PolicySurfaceIR` (v2) everywhere. Use one
  compatibility loader / migration for v1 inputs. Mark `PolicyRequestIR`
  deprecated and remove it after the compatibility window closes.
- **Context:** The system contains both v2 Surface IR (the current path) and
  v1 PolicyRequestIR (legacy compatibility). Duplicated migration logic and
  separate APIs increase the risk of divergence.
- **Consequences:**
  - Route incoming v1 payloads through one compatibility loader and migrate
    them to v2.
  - The API, orchestrator, and tools do not accept v1 directly.
  - Convert tests and demos that rely on v1 into migration tests or remove
    them.
- **Removal point:** 60 days or two minor releases after deployment of the ADR,
  whichever comes first. After date T, remove `PolicyRequestIR` and related
  paths, leaving only v2.
