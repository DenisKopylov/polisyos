# Promotion conjunction: Stage 1 source reading

Stage 1 source references are relative to `policy-engine/` at `28b8a1a42`.
The explicitly marked Stage 2 section instead uses the implementation commit
recorded in `execution.md`.
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
resolvers but omits the promotion-evidence resolver at the slice base. The actual
control lifecycle persists `classification=None` rather than invoking it (PC-R04
in `reduction-research.md`). That inspected caller state establishes the buildable
bridge gap; it makes no whole-repository absence claim. Destination: PC-B2
post-core production invocation and evidence replay.

Pattern pass: P01/P02 (real invocation and bridge), P04/P05 (scope and authority),
P29/P32/P33 (behavioral replay and removal probes), P35/P38 (instance versus
function/return-site denominator and no proxy admission). No evidence here grants
an institutional appointment or promotion authority.


## Stage 2 stop-rule audit: completed source bridge and bounded posture mapping

This section references delivered source at the implementation commit named in
`execution.md`, overriding this note's Stage 1 base convention.

PC-B1 includes the independently buildable source-selection link missed in the
initial finite paragraph. `PromotionRuntime.promotion_evidence_source` defaults to a
concrete typed empty selection. The default `GenerationCycleController` and standalone
`CanonicalN9PromotionPort` consume it. The source snapshots each exact typed selection,
including original candidate identity/hash, whole-summary content hash and complete
problem binding; missing, ambiguous and mismatched selections persist named refusal
receipts. Existing independence/measurement writer inputs reach their actual producers,
and the same measurement catalog/providers reach replay. Candidate safety-source refs
reach the protected-purpose custody request; optional G4 refs reach the existing owner
resolver. No selector result grants authority. Every result records the actual candidate,
problem and configured rows read, with external evidence, promotion authority and verified
S6/S7/S8 admission named `unresolved_by_construction` boundaries. The independent source
configuration is frozen to serialized bytes, so post-assembly nested mutation cannot
change the runtime selection snapshot. Actual-read receipts remain candidate-grade.

Posture census predicate, stated before execution: walk every `src/**/*.py` file and
count direct constructor or class `model_validate`, `model_validate_json`, or
`model_construct` calls to `Layer2S6BlindSpotPostureInput`,
`Layer2S7DelegationPostureInput`, and `Layer2S8ValuePostureInput`, resolving import aliases.
The reproducible script is `posture_census.py`. The census found **0 such explicit producer call sites across the full denominator of
2,664 on-disk Python files under `src/`**, independently reconciled against **2,663
tracked Python files under `src/` plus the single new `promotion_safety.py` Python file**;
no tracked member was missing or unreadable. This is a syntactic producer-call count,
not a claim of absent institutions or a proof against dynamic deserialization. Complete
actual file hashes and named dynamic-dispatch boundary are retained in
`raw/posture-producer-census.json` (SHA-256
`cb3b215e21827050e9b67ea512c2dbb58843caf91b1d04995ce99d0b399af337`).
The tracked-script replay returned actual process code 0 in 89.103 seconds;
`raw/posture-census-replay.json` SHA-256 is
`811c56ae6efccc185f2d8bb8fd35e9697c77d011a79b20843e4a46da66701093` and its process receipt
is `raw/posture-census-replay-receipt.json`. Its complete result equals the original
except the read hash of `evaluation_safety.py`, which changed from
`dce13781f5a09a8af3356d47d58974992daf83dc32e44f2f65b263144c721953` to
`dde45bf91a6cd06f728d734c3fc5becdcd5cede8bacb6100ec80813024ad5a73` as PC-B2 source work
finished. The call set, input file set and unread-boundary results are identical.
This source-wave timing difference is routed to the lane freeze receipt, with no
product finding or borrowed absence claim.
The independent call-boundary inspection read every class and its evaluator, then the
real source owners below. Source inputs unchanged from the base are:
`src/polisyos/pdc/_impl/layer2_design_search.py@28b8a1a420e746b54fbd0b87f73fad1fc4821ba5`,
`src/polisyos/runtime/quality/proving_ground/legal_mandate_search.py@28b8a1a420e746b54fbd0b87f73fad1fc4821ba5`,
`src/polisyos/runtime/http/services/human_decisions.py@28b8a1a420e746b54fbd0b87f73fad1fc4821ba5`,
and `src/polisyos/runtime/quality/design_axes/value_choice_provenance.py@28b8a1a420e746b54fbd0b87f73fad1fc4821ba5`.

- S6's DTO explicitly describes injected shadow-loop posture. Its N9 evaluator accepts
  any nonblocked `overall_posture` and records refs without resolving their contents.
  `build_gl_s6_mandate_consumer_gate` already produces a compatible legal-mandate source,
  but deliberately sets `does_not_assert_s6_pass=True`, `s6_evaluation_ref=None` and
  `s6_gate_disposition="compatibility_only"`. The missing deciding semantics are the
  protected-purpose acceptance of measurability, aggregation, capacity, mandate and
  strategic-response evidence into the whole S6 posture. A compatible source handoff
  cannot settle those scientific predicates.
- S7's N9 evaluator calls `_s7_governed_pilot_eligible`, whose deciding variables are
  supplied posture/approval/firewall flags and reference presence. The real
  `HumanDecisionService` has signed source reading, actor/role/scope/time checks and
  live production-approval joins; HTTP human-decision routes invoke that service.
  Its `agent_action_authority` and `production_approval` purposes do not specify the
  mapping to N9 governed-pilot eligibility together with the S6 mandate conjunct.
  The remaining act is protected-purpose semantic admission/appointment for that
  mapping, not building another human-decision owner.
- S8's N9 evaluator tests injected ranking/disposition/P20/P22 statuses. The existing
  `NormativeValueScheduleOwner` verifies configured separate signers, exact authorization,
  scope/frontier/generation binding and persisted re-resolution before ranked emission.
  That PA1 source capability is real. It does not produce the complete injected S8
  posture or establish its objective, tradeoff, mandate and whole-posture admission
  semantics. Translating a signed schedule directly into pass flags would invent them.

The canonical promotion input and persisted owner projection already carry nullable,
typed S6/S7/S8 slots, and the real evaluators produce scope refusals for absence. No
new empty posture DTO or duplicate request is needed. Adding raw flags to deployment
selection would widen P37 authority risk rather than close an independent bridge.
`test_injected_posture_flags_are_a_bounded_predicate_not_evidence_admission` is the
bounded falsifier: direct actual evaluators receive fictional `s6://`, `s7://`, and
`s8://` refs with green flags, and accept them; a real production N9 receipt still
refuses promotion. The combined-wave receipt retains the full inputs, actual evaluator
outputs and global refusal. `epoch_removal_probe.py` repeats this final frozen witness
before mutating each epoch forwarding seam; its per-case receipts require the intended
call-phase failure, not merely pytest exit code 1. Complete output stays under `raw/`. This historical injected-predicate issue is explicitly
routed to architect register row **promotion-s6-s7-s8-injected-posture-admission-mapping**,
with P37/P38 semantics and the existing source owners named above. The smallest missing
capability is protected-purpose evidence-to-posture admission for each named axis;
source authenticity alone is not the deciding property. This lane neither appoints
that authority nor manufactures scientific acceptance rules.
