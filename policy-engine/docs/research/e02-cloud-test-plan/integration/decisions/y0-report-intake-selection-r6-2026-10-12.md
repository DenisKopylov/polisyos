# Y0 transportability whole-pass admission (open decision)

**Status:** open. This packet documents an engineering candidate for the existing pass boundary; it ratifies no new evidence, source-authenticity, or authority rule. `closure_ids=[]`.

## Question and pattern pass

R5 repaired report/result alias reconciliation but the independent R5 review found that cross-graph profile refs still mapped null, missing-store, malformed, and unresolved inputs to absence. It also found that mutable typed `CausalEffectReport` objects bypassed intake validation, and that partial/bounds-only or missing/proxy profile predicates remained warnings in STRICT. This is P32/P38/P40: the same pass-intake class one level deeper. The R6 candidate widens the whole owner intake instead of adding one more key-specific branch. It also addresses P29/P37: actual model resolution and the existing recomputed proof-review grade are used before the strict semantic disposition; key presence and asserted profile/result labels do not clear the gate.

## Candidate property

Before this pass evaluates transportability, each effective report, result, profile, and explicit requirement input is admitted once. Absence is distinct from a supplied null, malformed value, unresolved ref, missing store, invalid typed instance, or conflicting alias. CAS refs go through the existing loader and their loaded models are revalidated. Typed mutable report inputs and nested result/profile values are serialized and revalidated at this boundary. Content-equivalent aliases are counted once; disagreements surface as typed pass issues.

The set covered is derived from this pass's actual selectors and current caller/schema boundary: `causal_effect_reports`, `causal_report`, `artifacts_index.causal_report_ref`, canonical `CausalEffectReport.transport_result`, legacy `method_params.transport_result`, `artifacts_index.transportability_result_ref`, direct `cross_graph_evidence_profile`, `artifacts_index.cross_graph_evidence_profile_ref`, and `params.transport_required`. The R6 candidate retains the R5 report/result selector and reconciles direct/CAS profile aliases in the same admission function. It does not extend source authenticity beyond the existing free-form external-source routing hint.

After admission, the existing proof-review grade is frozen with each validated transport result. A source-verified `NO_ADDITIONAL_REVIEW` grade remains the only identified result that can clear the identified-result branch; the existing R4 classifier currently returns `review_required` for scoped Y0 candidates and `unknown` for other identified results because no source-bound native verifier is present. Profile `IDENTIFIED` status has no independent proof verifier and remains unknown unless it explicitly requires review, which remains review-required. STRICT blocks unknown, review-required, partial, bounds-only, unsupported, insufficient, or non-direct transport premises. MVP retains warnings; a valid explicit `transport_required=true` promotes missing or malformed admission inputs to blockers in every non-FAST profile. A malformed requirement value is itself reported, never defaulted to false.

## Alternatives

1. **One complete pass-owned intake (candidate).** Reuse existing report/result/profile contracts, typed ref models, CAS loaders, and result-grade classifier. Normalize all current inputs at the same owner boundary; reject supplied invalid states; compare aliases by validated content; freeze the gate disposition inputs. This closes the property without adding a producer or changing persisted schemas.
2. **Keep the R5 report selector and separately add a profile helper.** This repairs the reported examples, but preserves split admission semantics and invites another deeper source to collapse into absence. It repeats P40's narrow repair ladder.
3. **Reuse the generic optional artifact resolver unchanged.** That helper treats null, malformed or missing-store refs as absence and trusts typed mutable model instances. Reusing it without fixing those properties would preserve the exact divergence.
4. **Replace state inputs with one versioned selection artifact.** This could make source choice explicit, but it requires a producer, persistence, migration, invalidation, and reissue contract with no established owner in this bounded change. It remains an architectural option, not an implementation assumption.

The candidate chooses option 1. It introduces no DTO, enum, export, public surface, persisted schema, or authority rule.

## Compatibility and limits

Existing state keys, typed report/result/profile models, and CAS reference schemas remain unchanged. Empty report lists still do not shadow single/CAS aliases. Matching sources evaluate once; conflicts now produce issues. Existing boolean and recognized boolean-string values for `params.transport_required` remain accepted; a malformed present value is now reported. An explicit requirement with no admitted result or need now blocks instead of silently passing. STRICT profile partial/bounds-only and unknown-observability outcomes now block consistently with direct result outcomes; lower-authority profiles continue warning when no explicit requirement is set.

This pass still routes external reports through the current free-form source-type markers. It does not prove that a report is actually external or internal. A cross-graph profile's evidence/observability/transport statuses remain producer-supplied fields; no independent content verifier binds their meaning to underlying data here. Source authenticity, graph truth, data existence/currentness/authority, empirical grounding, publication eligibility, and institutional authority remain `not_established`. Unknown proof premises fail closed for this protected consumer; this candidate does not convert unknowns into negative identification conclusions.

## Acceptance evidence and remaining work

The virtual test delta adds strict direct-profile/ref invalid, null, unresolved and missing-store cases; profile alias agreement/conflict; whole status-composition controls; typed mutable profile/report revalidation; malformed requirement and parameter-container controls; explicit-required/no-evidence and explicit-false cases. Existing R5 report/result tests remain in the candidate. The candidate test file has **not been run** because the root's shared CPU/import lease is held. Both changed Python files parse with the standard-library AST parser. Canonical-path Ruff passes for the candidate mechanism and test modules. These checks do not establish runtime behavior; root must run the registered existing pass module tests on the final composed source before adoption.

Pattern pass: P29, P32, P37, P38, P40. Capability status remains `verification_missing` until the full pass test suite and remove-intake-keep-markers falsifier run on the composed source; native source-bound proof verification remains `verification_missing`; profile/source authenticity remains `not_established`. No formal closure ID is assigned.
