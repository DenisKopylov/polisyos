# Promotion conjunction: Stage 1 source reading

All source references below are relative to `policy-engine/` at `28b8a1a42`.
This is read-only architectural research, not a claim that a positive production
promotion has run. The task-zero census is maintained by the lane's primary report.

## Counting and scope

For this analysis an obligation means a declared obligation **instance** consumed
by `_refusal_reasons`, distinguished by `obligation_role`, class, gate, source
identity and invocation scope. A class gate, a decisive predicate, a Python
function and a return site are different denominators. The compiler's class
denominator is `PromotionObligationClass`; `_finalize_obligations` additionally
appends effective independence and the receipt owner's internal consistency
predicates. Do not quote the class denominator as the whole runtime conjunction.

## The operative conjunction

The authority-bearing path requires the following conjunction, derived from the
actual refusal and admission paths rather than desired labels.

| Conjunct | Deciding code | What can satisfy it at this base |
| --- | --- | --- |
| Owner runtime and pre-N9 admission | `promotion_sequence.py:2801` `CanonicalN9PromotionPort.__call__`; `_resolve_pre_n9_batch_owner_binding`; `_run_n9_promotion_port_batch` | Container-owned `PromotionRuntime`, persisted admitted batch, exact aggregate/member/occurrence bindings, runtime-derived epoch resolver. Mechanisms exist; missing owners produce typed nonreceipts. |
| Current epoch | Port independently resolves each pre-N9 admission; receipt replay independently resolves the projection | Matching current owner evidence. A caller-provided projection alone cannot establish it. |
| Open-world risk | Batch `prepare_verified_projection`; owner gate; receipt replay `resolve_verified` | Owner-established vector bound to the same aggregate, member, candidate occurrence and summary. |
| Canonical durable confidence session | Port `_open_confidence_ledger_session`; `_run_promotion_sequence_with_bound_session` | Actual authority session with exact design-problem risk scope. Verification namespace is intrinsically non-consumer. |
| SYNTAX | `_syntax_obligation` | Strict typed input and no declared producer root among LLM/candidate/surrogate/evidence-count self-promotion roots. |
| TYPE | `_type_obligation` | N8 `ValueGateReceipt` with a method family; absent receipt fails. |
| SLOT | `_slot_obligation` | N8 receipt exists; if a world record is supplied its hash matches; transport is not blocked. |
| PARAM | `_param_obligation` | No `force_promote`; a G4 reference resolves to an existing persisted record. This does not make the G4 record authoritative for N9. |
| COUPLING | `_coupling_obligation` | Candidate's production N5 projection has no `n5_coupling_blocked`. This is the actual bounded predicate, not a new claim of complete world-model adequacy. |
| EFFECT | `_effect_obligation`; repository `persist_effect_obligation`/`resolve`; `_effect_obligation_disposition` | Candidate/problem-bound producer artifact passes owner replay: grounded direct atom/L6 binding; estimand mapping; causal path or mechanism; grounded relation axes and CG2 binding. Missing evidence returns UNKNOWN, not scope-insufficient. |
| IDENTIFICATION | `_identification_obligation`; `grounding_bind.resolve_grounding_decision_promotability` | Candidate current-valid AND owner-resolved CG2 grant. Contract-testing bind may satisfy this class but never consumer promotion. |
| CALIBRATION | `_calibration_obligation` and confidence ledger binding | N8 calibration status pass plus executed eligible owner-bound promotion check. |
| MEASUREMENT | `_measurement_obligation`; evidence bridge repository | Independently resolved, candidate/problem-bound CAS MeasurementRoot from real Fabric fetch. Existing producer and bridge can satisfy it. |
| DATA | `_data_obligation` and confidence ledger binding | `DataTrust.effective_score >= resolved_promotion_floor` plus eligible executed owner check. |
| IMPLEMENTATION | `layer2_design_search.evaluate_s6_blind_spot_promotion_gate` | S6 posture exists and is not blocked. |
| EQUILIBRIUM | `_equilibrium_obligation` | No violated ValueOuterSet assumptions. TYPE separately refuses an absent receipt. |
| NORMATIVE | `layer2_design_search.evaluate_s7_mandate_delegation_promotion_gate`, `_s7_governed_pilot_eligible` | S7 exists, is governed-pilot eligible, recorded-valid decision, has human decision ref, responsibility and mandate firewalls pass, and S6 is `clear_fail_closed`. |
| EVAL_SAFETY | `_eval_safety_obligation` | Data-only attempt is `NOT_APPLICABLE_DATA_ONLY`. Pilot/deployment remains scope-insufficient: attempted-evaluation safety expressly lacks promotion authority. |
| VALUE | `_value_obligation`; `ValueOuterSet.promotion_decision`; S8 owner | N8 value decision promotable AND S8 posture present with no blocked disposition, P20/P22 block, or ranked use of shadow-only value scenarios. |
| Effective-independence decisive predicate | `_decisive_predicate_obligations`, `_effective_independence_obligation` | Recomputed persisted graph, correct candidate/problem bridge and acceptable owner disposition. It is additional to the DATA class gate. |
| Receipt consistency decisive predicates | `ValueGateReceipt.decisive_consistency_predicates` | Transport WMR hash equals receipt WMR hash; outer-set WMR ref equals receipt WMR hash. These establish internal consistency only. |
| All identity/scope evidence survives replay | `_finalize_obligations`; `_obligation_instance_issues`; `_validate_promotion_receipt_with_bound_session` | Exact class denominator; no duplicate, omitted, unexpected or substituted decisive instance; all instance hashes bind invocation/problem/candidate/source. |
| Predictable owner checks and risk budget | `_promotion_certificate_offers`; `_execute_promotion_certificate_offers`; `_bind_certificate_checks_to_obligations`; `_risk_spend_summary` | Registry routes reconcile against code-owned producers; supplied offers match owner recomputation; checks bind evidence; executed eligible support; aggregate ledger spend within budget. |
| No refused obligation | `_refusal_reasons` | No FAILED, UNKNOWN or SCOPE_INSUFFICIENT anywhere in the finalized instance set. Only contract-testing receipts may retain scope gaps, with no consumer authority. |
| Narrow derived authority and trace | `_computed_authority_boundary`; `_authority_derivation_trace`; receipt validators | Boundary is met with S7/S8 authority, optimistic caller grade is downgraded, trace binds gate and confidence ledger. It forbids production deployment and unguarded champion promotion. |
| Production consumer admission | `promotion_receipt_allows_decision_front` | Replay succeeds; promoted and consumer-promotable; production lane; no non-promotable reason. Verification and contract receipts cannot pass. |
| N6 decision-front conditions | `generation_cycle._apply_promotion_to_summaries` | Certified candidate ID, certified-current-valid port status, canonical replay, current validity, no blocked/low value, and completed adversarial shadow validation if high-proxy. |

All means conjunction, not interchangeable alternatives. `promoted` alone is weaker
than consumer admission. A satisfied class does not eliminate missing decisive
predicates. `force_proof_timeout` is preserved as an input but does not decide
EFFECT at this base; its dedicated test rejects that old shortcut.

## Conditional scope refusals

The direct scope helper returns in `promotion_sequence.py` are not globally
unconditional. Effective independence and MeasurementRoot have established and
refused alternatives; PARAM can resolve its G4 record; evaluation safety is
not-applicable on a data-only attempt. Within the pilot/deployment branch,
EVAL_SAFETY has no promotion-authoritative producer input that can change its
result. Separately, S6/S7/S8 owner wrappers outside this file emit scope gaps for
absent postures. A file-local helper count therefore cannot characterize all
refusal paths.

## Guard reproduction and required behavioral probes

The source anchors reproduce exactly at the pinned base:

* `promotion_sequence.py:1929`: receipt construction raises
  `scope_insufficient_cannot_mint_authoritative_promotion` when promoted with a
  scope gap outside a non-consumer contract lane.
* `promotion_sequence.py:4439-4453`: replay rejects SATISFIED with
  `semantic_scope=scope_insufficient` as `obligation_class_vacuously_passed`, and
  SCOPE_INSUFFICIENT with a different semantic scope as
  `scope_insufficient_semantic_scope_mismatch`.
* `promotion_sequence.py:4576`: replay independently emits
  `scope_insufficient_authority_laundering` for authoritative promotion with a
  retained scope gap, including receipt objects made by validation-bypassing copy.

Behavioral probe design: obtain a genuine negative receipt, preserve its typed
scope markers and identities, remove the actual evidence/authority needed by one
obligation, and attempt authority admission. Construction must raise the first
anchor; replay of a copied receipt must report the third; altering only the
semantic scope while retaining scope status must report the second. Also cover
the inverse vacuous-pass case. Retain the complete outputs. To test that these
tests exercise guards, an isolated source mutation can disable each predicate
while retaining its marker string; the corresponding behavioral test must fail.
Do not weaken the guards in the delivered source.

## Buildable production link discovered

`GenerationCycleController.run` at `generation_cycle.py:2907` calls
`_apply_promotion_to_summaries`, which calls its local
`_promotion_receipt_allows_decision_front` wrapper. These forward open-world and
promotion-evidence resolvers but omit the already-held
`self._epoch_n9_evidence_resolver`. The canonical predicate requires this resolver
whenever the receipt contains an epoch projection, which production receipts do.
Thus even an otherwise complete production candidate cannot reach the decision
front through this chain. This is `bridge_missing`, independent of an appointment.

Smallest closure: forward the runtime-owned epoch resolver through this existing
call chain, preserve the missing-resolver negative, and show both forwarding and
actual canonical replay behavior. No new authority producer is needed.

The non-test chain and runnable terminus are established: natural-language run
execution in `runtime/http/services/control/run_lifecycle.py:3117` calls
`compile_and_run_recursive_generation_cycle`; its production builder calls the
recursive controller, whose leaf route constructs `GenerationCycleController`
(`recursive_generation_cycle.py:672`) and awaits `run`. The resulting compiled
run is persisted with kind `runtime.compiled_recursive_generation_cycle`
(`run_lifecycle.py:3145`), with fronts and N9 receipts reachable through run state.
The HTTP endpoint is `/api/v1/control/runs`.

## Further boundaries for the primary lane's architecture decision

`GenerationSourceRepository.resolve` at `generation_source.py:352` reconstructs
world model, CG2 certificate/reference and effect-writer input from persisted N4
sources. It does not currently supply the effective-independence or measurement
writer inputs consumed by `_bind_production_promotion_evidence`, nor S6/S7/S8
postures. Their absence on this source adapter is not evidence that the owner
capability is absent repository-wide. Existing owned producers must be located
and wired before inventing replacements; institutional slots remain typed and
empty where their evidence is absent.

`evaluation_safety.verify_near_miss_classification` forwards epoch and open-world
resolvers but omits the promotion-evidence resolver. A source search found only
its definition in `src/**/*.py`; this lexical boundary cannot rule out reflective
invocation. It is therefore a separate unestablished production-caller boundary,
not a reason to add an uninvoked helper patch. Destination: primary lane's
positive-evidence ownership/bridge determination.

Pattern pass: P01/P02 (real invocation and bridge), P04/P05 (scope and authority),
P29/P32/P33 (behavioral replay and removal probes), P35/P38 (instance versus
function/return-site denominator and no proxy admission). No evidence here grants
an institutional appointment or promotion authority.
