# Policy Design Case Layer 3 Legal Mandate Search

Owner: `team-runtime-quality`
Source of truth: `src/polisyos/runtime/quality/proving_ground/legal_mandate_search.py`, `tools/quality/validation/check_policy_design_case_layer3_gl_readiness.py`, and `architecture/policy_design_case/layer3_gl_readiness_manifest.json`

Layer 3 GL is the legal mandate search and consumer-gate readiness surface for
Policy Design Case. It turns canonical L3 Legal KG search, replayable query
traces, false-abstention recall checks, claim-level Lex legal authority records,
threshold records, mandate records, temporal competence, amendment lineage,
reference resolution, and downstream consumer handoffs into persisted audit
artifacts.

GL is not recommendation, claim, publication, closeout, S6, S7, S8, G4, or
legal advice authority. It exposes refs and fail-closed readiness evidence so
runtime consumers can decide what may be used.

## Search Vs Authority

The search vs authority boundary is load-bearing:

- search ledgers and query traces are replay/control-plane evidence;
- KG rows, threshold hits, retrieved legal text, query summaries, and LLM
  summaries do not create legal authority;
- claim-level `legal_authority_record_refs` from the Lex legal authority adapter
  are the legal authority handoff consumed by GL gates;
- claim registry and semantic binding preserve the refs, but cannot prove legal
  authority alone.

Every GL artifact carries `may_not_use_for` denials including recommendation
substance, closeout authority, publication authority, agent authority, legal
authority without a claim-level adapter, S6 pass without S6 evaluation, and
ranked value choice without S8 authorization.

## False-Abstention Recall Guard

`layer3_gl_search_recall_freshness.json` records known-seed recall,
index-freshness, frontier completeness, and whether a domain ceiling is allowed.
If known legal seeds are missed or the canonical Legal KG is stale, GL must not
treat a no-hit search as evidence that no legal mandate exists.

## Legal Time Roles

GL keeps legal time roles distinct:

- `legal_as_of` describes the legal snapshot used for authority evaluation;
- legal effective windows describe when the norm or threshold is legally in
  force;
- policy effective windows and implementation periods describe the policy
  design interval;
- replay and publication times are not substitutes for legal competence time.

Partial or unresolved temporal rows are limitations or blockers, never authority.

## Amendment Lineage

`layer3_gl_amendment_lineage_records.json` records whether a provision is
current, stale, reissue-required, or missing lineage. Amendment records are used
to audit whether selected norms and threshold rows still point at the operative
legal version. Stale lineage prevents authority promotion until the legal window
is reissued or explicitly limited.

## Mandate S6/S7 Handoff

GL mandate records are S6-compatible source handoffs. They can populate
`MandateSourceRecord`-compatible rows and refs for
`Layer2S6BlindSpotPostureInput`, but they do not assert S6 overall posture or
S6 pass unless S6 producer semantics are present.

For S7, GL feeds mandate refs into delegation surfaces only as inputs. Human
decision integrity, responsibility routing, active choice, and P26 checks remain
S7 authority, not GL authority.

## Mandate S8 Value-Choice Handoff

GL exposes mandate refs and dispositions compatible with
`AuthorizedValueSchedule` and `Layer2S8ValuePostureInput`. Non-ranking GL
closure declares S8 value-choice ranking out of scope. If GL is used for ranked
value choices, S8 must fail closed unless S6 mandate pass exists and mandate
source dispositions are not candidate or limited.

## Lex Intervention Map Boundary

`lex_intervention_map` binding maps legally admitted provisions to intervention
knobs, target populations, sectors, regions, channels, and measurement
expectations. It is executable context and design input only. It cannot be used
as legal authority, recommendation substance, publication authority, promotion
authority, or closeout authority.

## Persisted Artifacts

The GL readiness CLI writes the Task 6 consumer and surface artifacts:

- `architecture/policy_design_case/layer3_gl_claim_registry_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_semantic_binding_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_argument_graph_readiness_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_s6_mandate_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_s7_delegation_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_s8_value_choice_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_pdc_compiler_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_design_constraint_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_g4_promotion_gate_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_legal_mandate_audit_surface.json`
- `architecture/policy_design_case/layer3_gl_public_export_projection_refs.json`

`layer3_gl_public_export_projection_refs.json` is reference-only. It exposes
projection refs and safe disclosure status, not raw legal rows, source quotes,
provision text, query ledgers, or unredacted authority payloads.

## Validator

Run the readiness validator from the product root:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer3_gl_readiness.py --repo-root . --write --output-format json
```

Without `--write`, the validator checks runtime validation, persisted artifacts,
manifest/runtime drift, generated-artifact registration, inventory and docs
sync, public raw-payload redaction, and GL authority boundary enforcement.
