# Task E — acquisition and N13b handshake journal

Date opened: 2026-08-30  
Continuation approved: 2026-08-31  
Branch: `codex/debt-e-acquisition-n13b`  
Base: `784d020148c56e9bfb3a3631909ba11232210a9f`

## Approved scope and corrections

The approved implementation is a boundary hardening, not a production-port substitution. The published vocabulary remains unchanged: `authority_badge` and `AcquisitionOwnerExecutionResult.authority_badge` stay the exact const `behavioral_fixture_not_production`. No second badge, enum member, field, schema regeneration, client regeneration, or dashboard edit is permitted.

The defect is the variable capability derivation beside that const. At baseline, `AcquisitionActionService._projection()` returns `ready` when any duck-typed authority provider or execution port is injected, even though the route and result contracts remain permanently fixture-badged. The repair must keep both capability fields `producer_missing` on this badged path and stop production execution before authority reservation or job creation. Direct behavioral worker tests remain fixtures and establish no production capability.

The seven-row denominator remains the original four core plus three adjacent rows for reporting. `GY-GAP6` is re-scoped out of Task E implementation and will receive a routable specification rather than a Task E closure verdict; its existing `blocked` standing contributes only to the required seven-row arithmetic.

## Baseline receipts

| measurement | result | disposition |
| --- | --- | --- |
| `git status -sb` | `## codex/debt-e-acquisition-n13b` | branch attached, tree clean before edits |
| `git symbolic-ref -q HEAD` | `refs/heads/codex/debt-e-acquisition-n13b` | correct branch attachment |
| `git rev-parse HEAD` | `784d020148c56e9bfb3a3631909ba11232210a9f` | requested base |
| `git rev-list --left-right --count main...HEAD` | `0 0` | requested ahead/behind baseline |
| mandated plan path | absent before Task E | created by this planning boundary |
| mandated journal path | absent before Task E | created by this planning boundary |
| `uv sync --frozen --extra test --extra lint` | exit `0`; 49 test/lint packages installed | worktree-bound dependency receipt |
| `uv run python -c "import pathlib, polisyos, pytest; ..."` | exit `0`; `polisyos` resolved to this worktree; pytest `9.0.2` | bound-interpreter receipt |

## Opening pattern pass

- `P04` / `P15`: the response can currently pair `ready` with a const that says not production.
- `P31` / `P32`: a duck-typed injected collaborator cannot establish production provenance by presence or shape.
- `P35`: readiness construction sites, N13b implementations, INT-R2 symbols, and VoI residuals require complete enumerations with denominators.
- `P37` / `P38`: the intended property is production capability; current code tests collaborator presence, which diverges for the badged test provider/port.
- `W5-K01`: additional fixture rows or successful test invocations cannot establish the missing production port, admission, authority, or INT-R2 union.

Target pattern: preserve the fixture path for semantic testing while making its production capability and production execution effect exactly fail closed. Capability reality remains explicit: production port `producer_missing`; deterministic bundle `producer_missing + artifact_missing + bridge_missing`; INT-R2 `absent/unallocated`; GY admission `artifact_missing + bridge_missing`; positive route `absent/unallocated`; numeric VoI `producer_missing`.

## Protected paths

The following remain read-only throughout this lane:

- `schemas/runtime_api_v1.openapi.json`
- `packages/runtime-api-client/**`
- `apps/runtime-dashboard/**`
- `src/polisyos/runtime/http/openapi_contract.py`
- `src/polisyos/runtime/quality/**`
- `docs/plans/active/DEBT-REGISTER.md`
- `docs/plans/active/LEDGER.md`
- `docs/plans/active/layer3-slices/GY-engine-subordination.md`
- `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`
- `tools/quality/validation/check_debt_ledger.py`

## Evidence log

Receipts are appended here after each red/green cycle and complete-set measurement. Failed or superseded commands remain visible rather than being rewritten.

## Register closure dossier

Pending targeted implementation and fresh verification. The final journal will contain all seven blocks, the measured arithmetic, the N13b implementation census, the bidirectional `external_nonclosures` reconciliation, and the routable GY-GAP6 specification.
