# Y0 transport report-intake selection semantics (open decision)

**Status:** open; this packet describes a candidate engineering behavior and does not ratify an evidence or authority rule.

## Question

What should the transportability governance pass do when multiple existing report/result inputs are present, malformed, unresolved, empty, or contradictory? The pass already accepts `causal_effect_reports`, `causal_report`, `artifacts_index.causal_report_ref`, embedded canonical and legacy transport results, and `artifacts_index.transportability_result_ref`. Earlier R4 repairs established a recomputed proof-review grade for actual Y0 results, while independent R4 review found two same-class escapes: an empty report list suppresses aliases, and any non-null legacy value could bypass typed proof grading.

## Candidate property and observed divergence

The candidate property is: every supplied effective report/result source is resolved, validated and content-compared under one intake; empty containers cannot hide another source; malformed or conflicting values remain explicit; aliases with identical validated content are evaluated once. The current R5 implementation applies this rule to the complete in-scope source family and routes canonical and legacy results through `TransportabilityResult` validation and the existing R4 grade function.

The R4 implementation returned from `_resolve_reports_with_paths()` whenever `causal_effect_reports` was present, including `[]`, so it skipped `causal_report` and CAS aliases. Its legacy-result check treated non-`None` `method_params["transport_result"]` as enough to enter the success path. Its reference resolver could also turn malformed/unresolved source inputs into absence. Those are consumer-side P38 divergences: list presence and value presence were tested instead of resolved selected content and grade. R5 closes this same class at the whole selector/intake level (P40), rather than patching the two examples.

## Alternatives

1. **Collect and reconcile current sources (R5 candidate).** Resolve the list, single compatibility alias and CAS report reference when present. Validate each at its own boundary, deduplicate exact report content and refuse conflicting sources. Normalize canonical, legacy and direct CAS transport-result inputs through the typed result and existing grade path. This preserves current input names and exposes mismatches instead of letting ordering decide.
2. **Keep first-source precedence.** This is smaller but permits empty lists, malformed values or stale aliases to suppress a more complete source. It reproduces P38 and is not a safe protected-intake rule.
3. **Replace current inputs with one versioned selector artifact.** A typed selection record could identify one report and transport-result ref, but it would add a producer, persistence, migration and reissue contract. There is no established owner for those lifecycle decisions in this change.
4. **Resolve conflicts by source priority or recency.** No independently verified freshness/authority ordering exists among these sources. Choosing one would make a declared priority act as gate authority.
5. **Preserve explicit-null origin through CAS.** `persist_causal_effect_report()` currently writes `report.model_dump(mode="json")`, which materializes nullable defaults. After reload, explicit null and an omitted default are indistinguishable. A versioned presence/provenance field or an intentionally omission-preserving write contract could settle this; silently inventing the missing origin cannot.

The candidate chooses option 1 for source resolution while leaving the artifact-presence question in option 5 open. It does not choose an institutional rule about which sources deserve authority.

## Typed inputs, statuses, and authority boundary

The report selector accepts the existing typed `CausalEffectReport`, valid raw mappings, typed `CausalEffectReportRef`, and valid mapping refs. Refs require the configured artifact store and successful typed CAS read. An explicit null at an in-memory/raw input boundary, an invalid legacy value, unresolved reference, malformed index, or conflicting report/result source produces an input issue. A valid `TransportabilityResult` is graded by the existing `transportability_proof_review_grade()` path. Schema-valid but ungraded `{}` remains `unknown`, never an absence or green result. STRICT mode blocks unknown/review-required results. Existing MVP warning behavior remains profile scoped.

If identical report aliases appear in both the list and a single/CAS slot, the report is evaluated once. If they differ, selection returns a blocker rather than selecting by key order. Direct result CAS is compared with report-embedded results; identical result content is not counted twice, and disagreement blocks. A direct result without a selected report is still evaluated as a direct candidate and does not retroactively prove that it belongs to an external report that lacks a result.

Input resolution and content equality are recomputed from admitted values. Source authenticity, source-data existence/currentness/authority, graph truth and empirical grounding remain `not_established`; an engine string, review Boolean, list/ref presence or this decision packet cannot change that. A Y0 expression remains a mathematical candidate under its declared assumptions. No claim becomes publishable, gate-eligible, institutionally authoritative or current through this intake.

## Compatibility, migration and impact

The state keys, typed references, `CausalEffectReport` and `TransportabilityResult` schemas, method registry, and public HTTP/API surfaces are unchanged. Existing callers may continue supplying any supported existing input. Conflicting inputs that previously depended on incidental precedence will now be reported. Legacy raw dictionaries still pass through the existing typed result model; malformed values produce an input issue, while schema-valid results with unknown proof grade remain unknown. The existing FAST/MVP/STRICT severity policy remains in place.

The existing CAS serializer emits `transport_result: null` even when a default was omitted. For a report loaded only from that CAS artifact, the candidate treats this nullable default as missing evidence; explicit-null origin at that persistence boundary is `not_established`. The raw/direct typed path does preserve an explicit null and reports it as invalid. Changing CAS presence semantics requires a separate schema or serializer migration decision.

## Pattern pass and capability state

Relevant patterns: P29, P32, P37, P38 and P40. R4's independent review classified the new findings as the same report-source/input gate class at a deeper boundary. The candidate widens to the whole report/result input quantity, uses typed resolution and content comparison, and exercises actual report/CAS/pass behavior. Existing evidence grading remains the R4 path; no authority verifier is added here. The semantic test for selection behavior is present in the candidate. Protected native proof remains `verification_missing`; no formal closure ID is assigned (`closure_ids = []`). The governance pass remains the existing consumer surface; no new public surface is claimed.

## Candidate falsifiers and acceptance evidence

The focused candidate tests cover empty-list fallback, single/list/CAS combinations, identical and conflicting aliases, missing stores, unresolved and malformed refs, explicit null versus absence on inputs that retain origin, valid typed/raw legacy values, malformed legacy values, direct/report result equality or conflict, multiple reports and the existing Y0 review-required/unknown grade controls. Running the same 40 tests against the immutable R4 implementation leaves 25 failing and 15 passing; the R5 candidate passes all 40. Exact outputs are `pytest-r5-red-final-output.txt` and `pytest-r5-green-output.txt`; canonical module origins are in `r5-module-origins-red-final.json` and `r5-module-origins-green.json`; strict canonical-path Ruff output is `ruff-r5-canonical-output.txt`. No numerical Y0 call, backend fitting, data acquisition or production source write was part of this bounded candidate check.

Before any adoption, verify the candidate against the exact current physical source composition, review the CAS-origin limitation, and decide whether a presence-preserving report schema/write is required for the intended policy. This packet does not close that decision.
