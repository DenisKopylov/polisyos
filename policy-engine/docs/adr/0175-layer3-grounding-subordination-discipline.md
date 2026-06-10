# ADR-0175: Layer 3 Grounding Subordination Discipline

## Status

Accepted

accepted_by: Denis Kopylov
accepted_at: 2026-06-06T15:35:57+03:00
acceptance_ref: Codex thread human-principal message, 2026-06-06, "Я принимаю. Можешь обновить адр и пересобрать индекс"
v2_amendment_status: Accepted
v2_amendment_accepted_by: Denis Kopylov
v2_amendment_accepted_at: 2026-06-07T11:03:19+03:00
v2_amendment_acceptance_ref: Codex thread human-principal instruction, 2026-06-07, "Продолжаем исполненние плана ... бери в работу полностью Task 5 - Audit Surface, ADR, and Corpus Route"

## Context

Layer 3 G0 freezes the pre-adapter grounding discipline for the Policy Design
Case. It persists the capability/data inventory, triage registry, port map,
source-touchpoint registration, conformance harness, health ledgers, import
firewall lint, empty-port map, adapter-cost map, first vertical case refs,
discovery/search discipline, hardcode enumeration backlog, engineering-quality
check, and readiness manifest before any adapter may claim authority.

ADR-0175 is the accepted v1 pre-adapter discipline. This document also records
the v2 discovery/search amendment as a supplemental acceptance with its own
human-principal acceptance ref. The v2 replay contract is:

- schema version: `policyos.policy_design_case.layer3_g0_discovery_search.v2`;
- rule version: `policyos.layer3.g0.discovery_search_free_growth.v2`.

Related: ADR-0174, ADR-0173, ADR-0156.

## Decision

G0 artifacts are deterministic readiness and audit evidence only. They are
authoritative for `layer3_g0_pre_adapter_inventory`,
`layer3_g0_triage_projection`, `layer3_g0_import_firewall_audit`,
`layer3_g0_manifest_drift_detection`, and
`layer3_g0_zero_adapter_admission_gate`. They may not be used for adapter
admission, publication authority, claim authority, production recommendation,
closeout authority, grounded conversion, useful design outcome, LLM authority,
no-hit/domain-ceiling summary, or source-truth adapter path creation.

LLM output remains candidate material and never authority. Adapter discipline
is fail-closed: no adapter admission before G0, zero admitted adapters, and any
quarantined source must block adapter admission. The preservation registry for
source truth is distinct from the adapter admission registry and from the raw
discovery/source registry. `AdapterContractRegistry` is semantic-preservation
substrate: it records how an already identified source truth surface is
preserved through an adapter contract. It is not the raw discovery registry, it
does not discover sources, and preserving a legacy path is not the same as
admitting a Layer 3 adapter.

The governed Layer 3 discipline is the constitution's §5 organizing rules plus
§7 ports/adapters/registry/conformance. The amended Rule 12/T7 discovery-search
discipline is accepted at G0 scope:

- capability/data/method/tool growth is discovered by replayable search, not
  hardcoded enumeration;
- hardcoded enumerations remain only as registered strangle-backlog debt with
  owner, replacement path, deletion condition, and no fallback;
- search frontier, selected/rejected candidates, cutoffs, index/rule versions,
  incompleteness, and absence reasons are persisted before no-hit or selected
  results can influence a port;
- no-hit is candidate/control-plane information with `authoritative_for=[]`;
- `search-recall@known-seeds + index-staleness` gates distinguish search
  ceiling from domain ceiling;
- G0 recall/freshness readiness is necessary but not sufficient for
  no-hit/domain-ceiling summaries, which still require G1+ search adapter
  execution.

The current import policy has a recorded conflict: `architecture/imports/policy.toml:112`
allows broader `pdc` imports than the constitution's narrow-waist posture for
Layer 3. A follow-up architecture ADR must narrow `policy.toml`'s `pdc`
allowlist after this freeze so `runtime`, `scientist`, and `ir` cannot become
implicit source-authority lanes for Policy Design Case code.

Constitution section 8.4 open questions remain `tracked_empirically_open`.
They are not resolved by this ADR; they are governed as empirical follow-up
questions with explicit evidence refs.

Impact note required by the constitution:

- status lattice: `discoverable`, `executable`, and `admitted_authority` remain
  composed with adapter maturity, grounding disposition, promotion state, and
  capability reality labels;
- authority boundaries: search, LLM, tool, corpus-stub, and projection outputs
  cannot grant authority without adapter admission and purpose-scoped A-gate
  validation;
- replay behavior: persisted ledgers, index freshness receipts, rule/schema
  versions, and runtime/persisted content hashes are the replay anchors;
- affected slice plans: G1+ slices must consume the G0 discovery/search
  discipline and cannot bypass hardcode, recall, freshness, no-hit, or
  domain-ceiling gates;
- health signals: five ledgers are frozen, including
  `search-recall@known-seeds + index-staleness`;
- enforcement surfaces: runtime validator, persisted JSON/TOML artifacts,
  reference docs, architecture inventory, W12D corpus route, CLI report, and
  repo-quality tests must all preserve the same boundaries.

## Consequences

G0 can persist and replay the grounding inventory while blocking authority
laundering. Portless capability gaps remain governed waist-change questions,
health ledgers stay frozen until the next slice, and the readiness manifest
must match the runtime builder counts.

W12D useful-design semantics are unchanged. G0 is not a grounded conversion
slice, so W12D reports `not_attempted_g0_pre_adapter` and
`grounded_conversion_count=0`. A no-hit/domain-ceiling summary cannot appear
before G1+ search adapter execution and G0 recall/freshness readiness.

Layer 3 G0 acceptance is valid only with the human-principal fields in the
Status section, including the v2 supplemental acceptance fields. An
agent-written status string is not sufficient evidence of acceptance.
