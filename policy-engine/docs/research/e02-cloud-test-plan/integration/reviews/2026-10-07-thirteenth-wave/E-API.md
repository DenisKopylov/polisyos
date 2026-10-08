# E IR API, ABI and generated-surface review

Read-only review of E root `b2f2f65ea8884a6e2ffa3fc444cdf4bbb9157641` (tree `4cbbed1d9392832729cab92c6615f9a1d03a41c7`) against G `9806442ddb47d624a2940bac75d9d6248e934c48`. The reviewed API-relevant source paths at latest PR head `df5258b7ddfade5b952e3b21ef28116ced40fa68` match the E root; the docs-only PR delta does not change the reviewed source. No tests or generators were run.

**Decision:** bounded Profile2 implementation/API source review is GO to integrate as a candidate. Public ABI/release readiness is HOLD (`surface_missing`) until canonical ABI snapshots and public inventory/reference are regenerated and reconciled from one frozen G source. This is a missing generated companion, not a reason to demand more E math runs or new authority inputs. It does not close B201/B202 or imply G acceptance.

## Public contract and actual delta

`architecture/public_surface/contract.toml` keeps `polisyos.ir` `public_stable`; no contract edit is needed to admit an additive type under this existing facade. E root exports four new names via `src/polisyos/ir/__init__.py` `__all__` and its lazy map:

- `polisyos.ir.PosteriorParameterBinding`
- `polisyos.ir.PosteriorSummaryContext`
- `polisyos.ir.PosteriorSummaryProfile`
- `polisyos.ir.PosteriorSummaryProfileV2`

The candidate facade has 288 literal `__all__` names, but candidate `architecture/public_surface/inventory.json` and its rendered `docs/reference/public-surface.md` still record 284 and omit all four names. The same 284 baseline count is at G. This is a concrete source-to-inventory gap; the changed inventory/doc files in the E tree do not establish freshness for this IR row. Candidate `src/polisyos/schemas/abi_models.py` registers `posterior_summary_profile` and `posterior_summary_profile_v2` with `profile_version` version fields and target files `posterior_summary_profile.schema.json` and `posterior_summary_profile_v2.schema.json`. Neither snapshot file is present under `schemas/snapshots/ir/`, its `_manifest.json` has no posterior-profile entries, and G→E has no changes under that snapshot directory. Thus `abi_models.py` is updated source while its committed generated ABI outputs are missing.

The two release fragments already describe the scope but leave the inventory review flag false: `2026-10-07-posterior-summary-profile.toml` marks the initial Python public API; `2026-10-07-posterior-ratio-law-v2.toml` marks the additive persisted profile version. The latter states that E did not write generated files and names the canonical generator owner. Keep their distinction: Profile1 remains a separately typed, unchanged profile; Profile2 is a new public model/schema version.

## Compatibility boundary and typecheck receipt

The new profile does not replace or reinterpret the existing `UncertaintyEnvelope` v1.1 wire. Profile1 remains ID `urn:policyos:ir:bayesian-posterior-summary-profile:1`, version `1.0`, with its existing normalized-probability contract; the indexed fixture set contains seven literal historical Profile1 records. Profile2 is ID `urn:policyos:ir:bayesian-posterior-summary-profile:2`, version `2.0`, and uses canonical binary ratio weights that deliberately need not sum to one. Its schema must preserve `probability_convention = exact_binary_weight_ratios`, `sampling_approximation = finite_uniform_mesh_discretization`, and `gate_eligible = false`; do not normalize the stored ratio values or call this a new Envelope wire version. Multidimensional Profile2 requires supplied aligned unique draw IDs. This review does not elevate those IDs, source/model fit, or the finite sample law into provenance or authority.

The recorded typecheck failure belongs to older typed source `3932cded22a29254a7dfced99723e147d6fea7cb`, tree `8d19c30199666cf97dd3934f60d772baa3071f7e`, from base `64d7444a18c55df7b88b71b7699a2f1b25ca24bd`. Its Pyright 1.39.0 output has one `reportOptionalMemberAccess` at old `posterior_summary.py:461`: `envelopes[name].distribution_payload.model_dump(...)` where the payload can be `None`. That source blob is `3830f8f65cc4ea4428b1ca7b145f2867b5bc7d92`. The current E-root and reviewed composition source both have blob `48eb8c09bd2470977fb7f86258d739a80738362c`; there the code first checks `isinstance(carrier, PosteriorSamplesCarrier)` and calls `carrier.model_dump`. The precise old failing expression is therefore not carried into the current source. No typecheck was run on current E root; current status is **UNRUN**, and P41 attribution to current E/G is **not established**. Do not report the old red as a current code failure or convert the changed expression into a current typecheck pass.

## Canonical companion owners and minimal frozen-G action

The ABI artifact family in `architecture/generated_artifacts.toml` names `team-polisyos` as owner, source of truth `src/polisyos/schemas/abi_models.py` plus Pydantic/Enum contracts, and generator `uv run --extra ml polisyos-tools diagnostics gen-schema` (check form adds `--check`). It registers `schemas/snapshots/ir/` as generated committed output. The public-surface contract names `team-architecture` as inventory review owner and records `uv run python tools/devx/architecture/guardrails.py sync --skip-deep-import-baseline`; this produces the inventory/reference from source. These are canonical generated writers; E should not hand-edit generated snapshots or use a side checkout as their source.

Smallest safe order after G admits all intended E product-source commits and freezes an integration SHA:

1. In the canonical G checkout at that frozen SHA, run from `policy-engine/` `uv run --extra ml polisyos-tools diagnostics gen-schema` once. It should emit both registered profile snapshots and refresh the ABI manifest from the source declarations.
2. Run `uv run python tools/devx/architecture/guardrails.py sync --skip-deep-import-baseline` to reconcile the full literal root facade and update the public inventory/reference. Confirm the result enumerates 288 candidate root names, including all four above; if generation still reports 284, route that source-to-inventory issue to the canonical facade/inventory owner rather than manually editing the inventory.
3. Validate the frozen outputs with `uv run --extra ml polisyos-tools diagnostics gen-schema --check` and `uv run polisyos-tools architecture guardrails check`. Only then mark the relevant release fragments' `public_surface_inventory_reviewed` true. No HTTP OpenAPI/generated-client regeneration is indicated; this is Python facade plus the repository's IR ABI snapshots.

The API work does not require a World Model authority input or production dataset: `gate_eligible` remains false and the accepted scope is finite, supplied sample rows. Keep generated-surface completion separate from source acceptance and E finding closure.

## Separate configured-fit input owner handoff

The E handoff also records an unapplied protected-float materializer packet. The canonical writer is the **Scientist compute/input-materializer owner**, routed by G; protected source is `policy-engine/src/polisyos/scientist/compute/runner.py` (source candidate `6638e18a3295e43a89b0ae6adba32e62952154bb`, protected source SHA-256 `75cce3ced29ecec057fb56f2b1d927741821e7ecc777c63aa2cc21e3bdbe27fd`). The minimal owner fix uses the existing Core canonical decoder at `_load_input_refs`; the packet records `source_mutated=false` and `backend_rerun=false`. Its scoped witness is the existing configured `run_job` HMC/NUTS path with finite float CAS refs, plus malformed-tag and mismatched source-kind/view refusal controls. It does not require WMR authority or production data and is separate from the API snapshot gap. No patch was applied here.
