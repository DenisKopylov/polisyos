# ADR-0175: Layer 3 Grounding Subordination Discipline

## Status

Accepted

accepted_by: Denis Kopylov
accepted_at: 2026-06-06T15:35:57+03:00
acceptance_ref: Codex thread human-principal message, 2026-06-06, "Я принимаю. Можешь обновить адр и пересобрать индекс"

## Context

Layer 3 G0 freezes the pre-adapter grounding discipline for the Policy Design
Case. It persists the capability/data inventory, triage registry, port map,
source-touchpoint registration, conformance harness, health ledgers, import
firewall lint, empty-port map, adapter-cost map, and first vertical case refs
before any adapter may claim authority.

Related: ADR-0174, ADR-0173, ADR-0156.

## Decision

G0 artifacts are deterministic readiness and audit evidence only. They are
authoritative for `layer3_g0_pre_adapter_inventory`,
`layer3_g0_triage_projection`, `layer3_g0_import_firewall_audit`,
`layer3_g0_manifest_drift_detection`, and
`layer3_g0_zero_adapter_admission_gate`. They may not be used for adapter
admission, publication authority, claim authority, production recommendation,
closeout authority, grounded conversion, useful design outcome, LLM authority,
or source-truth adapter path creation.

LLM output remains candidate material and never authority. Adapter discipline
is fail-closed: no adapter admission before G0, zero admitted adapters, and any
quarantined source must block adapter admission. The preservation registry for
source truth is distinct from the adapter admission registry; preserving legacy
paths is not the same as admitting a Layer 3 adapter.

The current import policy has a recorded conflict: `architecture/imports/policy.toml:112`
allows broader `pdc` imports than the constitution's narrow-waist posture for
Layer 3. A follow-up architecture ADR must narrow `policy.toml`'s `pdc`
allowlist after this freeze so `runtime`, `scientist`, and `ir` cannot become
implicit source-authority lanes for Policy Design Case code.

Constitution section 8.4 open questions remain `tracked_empirically_open`.
They are not resolved by this ADR; they are governed as empirical follow-up
questions with explicit evidence refs.

## Consequences

G0 can persist and replay the grounding inventory while blocking authority
laundering. Portless capability gaps remain governed waist-change questions,
health ledgers stay frozen until the next slice, and the readiness manifest
must match the runtime builder counts.

Layer 3 G0 acceptance is valid only with the human-principal fields in the
Status section. An agent-written status string is not sufficient evidence of
acceptance.
