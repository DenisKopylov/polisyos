# GY-PR1 stage-1 findings, 2026-09-08

This is read-only research at slice base `3d572c146` on attached branch
`codex/gy-phase5-execution`. No production source, tests, governed receipt, active debt
register or ledger was edited. Research scripts and command records are the only writes in
this directory. Each `*.json` command record contains the exact command, working directory,
actual subprocess return code, wall time, and complete untruncated stdout and stderr. The
runner puts the lane venv first in child `PATH`; the later version also sets lane `src` first
in `PYTHONPATH`. Initial environment nonreceipts are retained rather than overwritten.

## Done when and its conjuncts

Quoted verbatim from `docs/plans/active/layer3-slices/GY-engine-subordination.md:5519`
(the complete task text is also captured in `runtime-snapshot-ready.json`):

> Done when: `GY-O0-NC-01`'s closure signal is met exactly as written — a real canonical
> `consumer_promotable=True` receipt in the production lane, a field-pilot request lacking a required
> protection persisting `EvalSafety=blocked` with `near_miss=true`, both reconciled counters
> incrementing exactly once, and the safety core and its hash unchanged. Plus, red-first: a design
> that is in fact inadmissible or dependent must refuse **against a caller supplying `True`**, and a
> design with an unresolved joint coupling must make COUPLING refuse. A constructed or forged receipt
> cannot close it.

| ID | Conjunct | Current measurement | Discharged? / missing state |
| --- | --- | --- | --- |
| PR1-C1 | Real canonical production `consumer_promotable=True` receipt | `source-census.json`: complete source set has no `ValueGateReceipt(...)` constructor; the two model-validation calls are exact legacy-history readers. `runtime-snapshot-ready.json`: executing the default controller constructs `CanonicalN9PromotionPort` with `_context_provider is None`. `n8-owner-assignment.json`: real owner-data/method selection reaches `treatment_assignment_not_owner_derived`, no value receipt, typed unsatisfied acquisition request; shaped rollout/SKG declarations cannot change that. | Not discharged: N8 `producer_missing` / `artifact_missing`; production N9 `bridge_missing`. The actual complete promoted candidate and its custody record remain unproduced. Root owns the independent SKG/CG2 scientific-input measurements. |
| PR1-C2 | Field-pilot request lacking a required protection persists `EvalSafety=blocked` | Existing O0 persistence and control retry nodes are being measured separately in `o0-persistence.json`; they exercise genuine persisted blocked attempts without requiring a forged promoted receipt. | Subconjunct measurement recorded below; cannot credit the combined C2+C3 signal from an isolated negative. |
| PR1-C3 | The same blocked request has `near_miss=true` | `runtime-snapshot-ready.json`: actual N9 field-pilot evaluator returns `scope_insufficient`, `owner_ref=absent/unallocated`, explaining that the attempted-evaluation certificate forbids promotion. Existing `verify_near_miss_classification` in `runtime/quality/evaluation_safety.py:1664` requires canonical N9 replay and binds candidate/problem/value/world/epoch/open-world identities after the safety core. No real promoted premise was produced. | `not_established` for the requested event; missing promotion-purpose authority mechanism and signed artifact. Never substitute the counter unit tests' deliberately mocked classifications. |
| PR1-C4 | Both reconciled counters increment exactly once for that event | Existing reducer `runtime/http/services/control/evaluation_safety.py:730-785` deduplicates by decision identity and recomputes the two counts over reconciled events. Control-retry test measures blocked count=1 and near-miss count=0, not the missing positive near miss. | `not_established` for the exact joint near-miss signal; same C1/C3 prerequisite. |
| PR1-C5 | Safety core and its hash unchanged | `runtime-snapshot-ready.json`: entire `runtime/quality/evaluation_safety.py` is byte-identical to slice base, SHA-256 `22edd5916472bbe5e186c2a0091ab2e65c40d3b06d94c72cbefaaafdb4d6537c`. Promotion injection safety-core test is in O0 command. | Source integrity discharged; preservation under the eventual C1/C3 positive is `not_established`. |
| PR1-C6 | Inadmissible design refuses despite caller `True` | `gate-core-ready.json`: current-input and production-context legacy predicate rejection nodes pass; CG2 open `admissibility_closed` obligation yields `abstain`, IDENTIFICATION failed and `not_bind_decision`. `runtime-snapshot-ready.json` executes current model field inspection: neither caller field exists in v6 input. | Existing repair, discharged at the measured input/context and real CG2 gate paths; do not reimplement the retired caller predicate. |
| PR1-C7 | Dependent design refuses despite caller `True` | `gate-core-ready.json`: `test_real_dependent_independence_graph_refuses_legacy_true` rejects the caller field, produces/persists a real dependent evidence graph, resolves it through N9, and requires `dependent_evidence_collapsed` plus DATA refusal. Empty graph and context smuggling controls also pass. | Existing repair, discharged at the measured owner producer/bridge/evaluator paths. |
| PR1-C8 | Unresolved joint coupling makes COUPLING refuse | `coupling-bridge.json`: real N5 feedback-coupling run yields `unsupported_coupling_gated`, `simulation_blocked`, `n5_coupling_blocked`; summary bridge preserves the blocker. `gate-core-ready.json`: N9 COUPLING fails on it; supported path satisfies. `coupling-removal.json`: removing refusal behavior in memory leaves the supported happy-path result byte-equivalent and function markers present, but the existing real-owner test exits 1 at `unsupported_n5_result_must_block`. | Existing repair, discharged for the actual unsupported owner class with a decisive behavior-removal falsifier. |
| PR1-C9 | C1 is owner-produced rather than constructed/forged | No production receipt was constructed or forged by this research. Existing test-helper receipts were used only inside preexisting mechanism tests, and are not a canonical production denominator. | C1 remains unmet; no fixture is credited as closure. |

## The stale premises, remeasured

**PR1-F01 — the three old vacuous passes are repaired.** Current
`CanonicalPromotionInput` is `n9_promotion.v6`; caller fields `admissibility` and
`effective_independence` are absent and rejected. Historical owner projection v1 retains its
historical booleans for exact reads, which is not a current authority input. Current production
context explicitly rejects either legacy predicate. Admissibility is consumed through CG2;
independence is recomputed by `build_effective_independence_graph`, content-bound in the CAS bridge,
and consumed as a decisive DATA obligation. N5 now emits the coupling blocker at
`generation_cycle.py:264`, the selected-summary bridge carries it at `:5718`, and N9 consumes it
at `promotion_sequence.py:4943`. The old `joint_obligation_inconsistency` text remains the PDC
fail-closed enum value, not a second required producer.

**PR1-F02 — the honest scope-gap test vehicle landed.**
`test_scope_insufficient_obligation_does_not_vacuously_pass` now removes the G4 governed record
and inspects PARAM. It changes a PARAM scope-insufficient record to SATISFIED while retaining
its scope tag, recomputes the gate hash, and requires the real validator to report exactly
`obligation_class_vacuously_passed`. It passes in `gate-core-ready.json`. The general scope
property no longer depends on permanent EFFECT/MEASUREMENT failure.

**PR1-F03 — EFFECT and MEASUREMENT are genuine evidence consumers.**
`runtime-snapshot-ready.json` records their current executed owner definitions. EFFECT receives
an independently resolved status with real semantics, and no longer reads the timeout knob;
MEASUREMENT satisfies only on the bound producer resolution. The negative EFFECT conjuncts,
real CAS-backed `MeasurementRootProducer` positive, unresolved resolver negative, and production
N9 measurement/independence writer bridge tests pass in `gate-core-ready.json`. Positive EFFECT
and its production-port test initially skipped for missing CP-SAT; after parent provisioned
OR-Tools they reached an unrelated environment incompatibility (pandas 3 string dtype vs station
DuckDB) before EFFECT. Both nonreceipts are retained. After restoring the lockfile dependency
versions, `effect-positive-locked.json` exited 0 in 59.678 seconds: exact and bounded positive
entailment satisfy EFFECT, and the production N9 port persists/consumes EFFECT while honestly
refusing contract-only CG2. These positives are now established as mechanism evidence; none
is a production complete-candidate receipt.

**PR1-F04 — no production complete-candidate chain has appeared.** The denominator of
`source-census.json` is every tracked `src/**/*.py` file: 2,630, independently equalling the
filesystem walk by identity set (no differences, unreadable cases or syntax failures). Each
literal occurrence identity was independently obtained by Python regex and `rg --json`, with
exact equality of all `path:line:column` sets. The alias-aware AST captures complete constructor
call expressions. Findings:

- `ValueGateReceipt`: no constructor, two `model_validate` calls at
  `promotion_sequence.py:1530,1590`, both legacy-history readers.
- `value_ready`: four occurrences, all contract/type/check positions in `generation_cycle.py`;
  no producer emission.
- `CanonicalN9PromotionPort`: its sole production constructor is at
  `generation_cycle.py:2452` and supplies no `context_provider`; actual default-controller
  construction independently confirms `_context_provider=None`.
- Each of `effective_independence_writer_input`, `measurement_root_writer_input`,
  `effect_obligation_writer_input` appears only at its consumer (respectively
  `promotion_sequence.py:1435,1455,1467`). Each corresponding persistence method has an actual
  production call inside that bridge, but no production source supplies the consumed context.

**PR1-F05 — "no scope_insufficient in any lane" is overbroad.** Direct execution of the real
`_eval_safety_obligation` in `runtime-snapshot-ready.json` yields `not_applicable_data_only` for
`simulate_only` and `scope_insufficient`/`absent/unallocated` for each of the three protected
modes in its actual mode set (`sandbox_pilot`, `field_pilot`, `deployment`). The retained Task K
four-cell test in the current passing targeted batch also requires a field-pilot production
scope gap. Missing measurement/independence evidence conditionally remains a scope gap. What
landed was removal of fake permanent failures in the data-only evidence path; that is not a
claim that every possible obligation/lane is scope-complete. The Task K test is a declared
mechanism fixture, not a real complete-candidate production count.

`runtime-snapshot-complete-modes.json` closes the mode denominator explicitly: all six members
of the canonical `pdc._impl.evaluation_safety.EvaluationMode` Literal were enumerated both by
live `typing.get_args` and an independent AST extraction, with equal identity sets. The
`simulate_only`, `retrospective`, and `measurement_audit` modes yield data-only non-applicability;
the three protected modes yield the actual promotion-authority scope gap.

## Owner decisions proposed for stage 2 (not implemented)

1. **Keep the repaired refusal owners.** Wire existing N5 projection and CG2/independence
   evidence consumers; do not recreate booleans, add a duplicate ADMISSIBILITY gate, or modify
   executed GY-O0/N8 internals to turn their authority into a different purpose. Falsifier:
   removing the owner refusal while retaining its marker must turn the real owner test red;
   coupling-removal already demonstrates this on current source.
2. **N8 production/persistence belongs to the value owner; N9 bridging belongs to the promotion
   owner.** The missing seam is `RealValueOwnerGateway`/`FoundryValuePort` output to a bound
   persisted `ValueGateReceipt` and actual `value_ready`, then default production composition
   to N9's existing three writer keys. Extending the `N9PromotionEvidenceBridgeRepository`
   intake preserves its CAS resolve/content-bind/recompute owner; an alternate context-fed
   boolean/receipt shortcut would be P27/P32/P37. S3 owns its manifest-projection change in
   `generation_cycle.py` first; PR1 would own subsequent production composition wiring.
   Falsifier: remove writer context or substitute foreign-candidate bytes; authority must
   refuse while the candidate and typed evidence request remain available.
3. **Promotion EvalSafety is a distinct authority purpose.** RACE-HOG-PODS §12.3 already names
   its semantic requirements (bounded pilot/deployment risk, required consent/approval,
   containment, stop rules, harm monitoring). Existing `EvalSafetyCertificate` is fixed to
   `attempted_evaluation_admission` and explicitly denies `promotion`; `N9._eval_safety_obligation`
   has only the mode input and no promotion-purpose evidence resolver. The neutral vocabulary,
   typed empty signer slot, pure verifier shape, resolver/persistence bridge and fail-closed N9
   consumer are buildable per identity boundary §9 items 5–6. Minting an authority-grade predicate
   needs the appointed owner and cannot be supplied by a generic `True`, an O0 purpose relabel,
   or an invented risk bound. Prefer extending N9's existing evidence repository for this
   distinct evidence purpose, subject to the stage-2 owner ruling. Falsifier: missing signer,
   foreign purpose, stale/wrong-scope evidence, or consumer-constructed artifact cannot produce
   a satisfied obligation. A valid external signature establishes authentication only;
   satisfaction also needs the exact independently resolved semantic acceptance owner. Its
   missing slot remains typed-empty. No acceptance floor is invented here.
4. **Do not restamp current epochs to repeat a landed bump.** Source already uses promotion
   v6, obligation scope v3, bridge v2 and owner projection v3. Any substantive receipt-affecting
   stage-3 change needs a new governed epoch, history readability, and an emitted/recomputed
   proof; correcting historical prose alone warrants no code/version change.

Pattern pass: P05/P04/P09 protect fail-closed authority; P27/P28 reject parallel owners and
unstrangled defaults; P29/P32/P33 require behavior, real provenance and removal probes;
P35/P37/P38 forbid sampled denominators, caller-declared gate premises and proxy closure.
No new anti-pattern class is asserted; all findings route to existing rows below.

## Routing and unresolved questions

| Finding | Home |
| --- | --- |
| PR1-F01/F02/F03 stale plan claims | GY-PR1 architectural transcription; evidence above replaces August prose, no edits to active register/ledger here. |
| Missing complete production receipt and N9 context | `first-promotion-candidate-with-complete-evidence`, N8 owner production plus PR1 default composition. |
| Missing promotion-purpose EvalSafety bridge/appointment | `eval-safety-promotion-authority-producer-missing`; neutral mechanism in PR1; external mint appointment remains external. |
| Exact near-miss joint signal unmeasured | `GY-O0-NC-01` and `gy-promotion-obligations-scope-insufficient`; O0 itself remains executed. |
| Missing scientific SKG/CG2 material | Root's independently measured DataForge/CG2 finding; no fabricated certificate or positive calibration receipt. |
| CP-SAT/pandas station nonreceipts | Lane environment journal; not a production defect and not inherited product debt. |

### Follow-up O0 execution

`o0-persistence.json` exited 0 in 28.677 seconds. The actual HTTP service persisted a blocked
non-simulation request, the integration control retry reused the same terminal projection and
kept `unsafe_attempt_blocked_count=1` / `near_miss_count=0`, and the core promotion-injection
separation test passed. This discharges PR1-C2's blocked-persistence subconjunct and existing
idempotent blocked-counter mechanism. PR1-C3 and the joint C4 signal remain `not_established`.
No O0 production file was changed.

## Concrete neutral promotion-safety seam proposal, declined before ratification

This appendix records a considered design and its falsification, so a reviewer can assess why
it did not become a code contract. It deliberately proposes no numeric acceptance threshold
and no signature-generating capability. The semantic-owner measurement below ruled out its
positive premise: no independently meaningful promotion-safety semantic source exists here.
Adding another permanently-refusing envelope to the already-persisted scope-gap obligation
would add contracts and epochs without closing a new deciding property (P01/P13). The design
is therefore declined, not an approved stage-3 step. It remains a future input only when the
missing semantic source/acceptance mapping is supplied.

| Concern | Existing owner and exact proposed extension | Why / falsifier |
| --- | --- | --- |
| Neutral source artifact and installed trust | Internal strict `PromotionSafetyEvidence` and `PromotionSafetyTrust`/principal DTOs in `runtime/quality/promotion_sequence.py`, next to existing source records. Artifact binds candidate ID/content, `N9DesignProblemBinding`, WMR/value identities, one canonical protected evaluation mode, externally declared safety-basis ref, validity interval, issuer identity, and exact `authority_purpose="promotion_eval_safety"`. Trust has an empty principal tuple by default; contains only public keys and explicit purpose/scope grants supplied by deployment composition. No private key, arbitrary boolean verifier callback, implicit accepting principal, or risk threshold. | N9 owns its evidence purpose; do not duplicate O0's certificate or widen O0's denial list. A signed O0 admission-purpose certificate must fail as wrong purpose even with a trusted key. |
| Source intake / persisted refusal | Extend `N9PromotionEvidenceBridgeRepository` with a method accepting an artifact ref or typed-empty ref slot, not a caller `passed` predicate. Reuse `core.artifacts.FileSystemCAS` canonical bytes/manifest/signature APIs and `Ed25519Verifier` as already used by the normative owner. Resolve and content-bind external signed bytes; configured trust controls signer admission. Persist the admission/refusal result and the existing candidate/problem-bound bridge. Missing source/trust yields explicit unresolved reason and cannot establish authority. | Single intake and existing CAS repository prevent a second promotion owner. Falsifier: unsigned, tampered, foreign candidate, wrong purpose, wrong mode, expired/revoked/unappointed identity all remain non-authoritative even if payload says passed. |
| Replay consumer | Add one evidence-kind member to the existing bridge union and `_promotion_evidence_resolutions`; extend `_eval_safety_obligation` to consume a persisted typed nonreceipt for protected modes. Authentication and semantic acceptance are separate fields; no semantic verifier currently maps the exact promotion purpose, so the semantic slot is type-constrained empty and no satisfied branch may be introduced from signature validity. Data-only applicability remains derived from canonical mode. | P37: the gate tests semantic acceptance, not signed self-attestation. Falsifier: an authentic, properly scoped signed statement declaring every property passed must still refuse with semantic acceptance not established; removing authentication must separately turn the admission-integrity gate red. |
| Deployment trust placement | `PromotionRuntime` in `runtime/quality/open_world_risk.py` is the existing container shared by default, recursive and HTTP N9. Add an optional typed trust slot, empty by default, and have `CanonicalN9PromotionPort` pass only that slot to its repository. This is the one additional file that needs root coordination; never accept trust/key grants in candidate context. | Production's only port constructor is already container-derived. Direct tests may install a throwaway test key as explicitly synthetic evidence, never claim an appointed real principal. A candidate-context attempt to replace trust must reject. |
| Writer wiring | `_bind_production_promotion_evidence` accepts only the new source-reference writer input and delegates to the repository. Keep its producer-root-ref path; do not add owner-projection fields. If no production source ref exists, persist the typed negative from that same bridge and emit the unresolved EVAL_SAFETY disposition. | Real source → CAS admission → bridge → obligation → existing receipt/audit surfaces. Missing signature is an authority refusal, not a disabled code path. |
| Red-first semantic test | First add a targeted test showing the current protected-mode evaluator has no persisted evidence-ref outcome for an absent/unappointed signer; assert the planned typed refusal and persisted request/bridge, run it red before implementing. After wiring, authenticate a genuinely signed test statement and assert that N9 still refuses because its semantic acceptance owner is absent. Also exercise wrong purpose, candidate binding, stale validity and forgery. The only positive is successful authentication/candidate intake, never eligibility or promotion. | Proves newly built mechanism rather than re-testing old unconditional refusal. A permanent-failure test alone would repeat P29; a signed-payload `True` becoming satisfied would repeat P37. |
| History / strangle / proof | Current epochs are promotion v6, scope v3, evidence bridge v2, owner projection v3. New evidence member requires next epochs and exact historical parsers. Owner projection stays v3 by using `producer_root_refs`. Extend existing `LegacyPromotionStrangleReceipt`/N9 contract checker to prove the protected-mode default calls the new owner and the unconditional legacy producer-missing branch cannot be restored. Emit proof by actual checker runs; corruption and owner-removal probes must fail. | Existing history must remain readable under its own epoch; no re-stamped current authority. Merely naming the new owner is not proof. |

**Semantic-owner correction (P37), before stage-2 ratification.** The smallest existing
requirement semantics owner is `evaluation_safety.verify_evaluation_safety_requirements`,
which re-resolves every requirement's appointment and invokes its registered evidence verifier.
It operates in attempted-evaluation admission, not promotion. Production's
`run_lifecycle._ControlEvaluationSafetyVerifierRegistry.resolve` is the actual empty registry:
it discards every contract ID and returns `None`. Its authority and appointment resolvers also
emit typed `not_established`. Thus there is neither an existing positive promotion-purpose
semantic verifier to wire nor a legitimate rule for promoting a trusted signature into proof
that risk/consent/containment/stop/monitoring requirements are satisfied. The new intake must
keep that semantic slot type-constrained empty. Root's stage-2 acceptance decision must make
this stronger limit explicit; no positive-eligibility fixture belongs in this build.

The precise principal-grant fields need the root's stage-2 decision: they must describe an
externally appointed scope rather than invent the appointment. Likewise, this mechanism cannot
claim to recompute substantive risk boundedness from any declaration, even a signed one. It
can verify a scoped external signature whose purpose has been separately granted, while still
recording semantic acceptance as `not_established`. Any proposal that requires
new numeric limits or treats evidence-shaped strings as independently established should be
returned to its source owner, not turned into a default in code.

The exact real promoted candidate, the real positive near-miss event, and the joint two-counter
increment remain `not_established`. They are not credited from fixture observations or from
source presence. Overall GY-PR1 is not complete at this stage.

### Final stage-1 recommendation

`safety-semantic-owner.json` exited 0 in 27.506 seconds and `source-census-safety.json` exited
0 in 11.652 seconds. The latter repeats the complete source/path identity crosscheck and adds
the safety verifier/registry/certificate call vocabulary. No unreadable case was reported.
The exact source and live empty-registry results are retained without elevating synthetic
query strings into a canonical contract denominator.

Recommend **GY-PR1 `blocked` at the real governed promotion/near-miss conjunct**, after the root
finishes the other tasks. This is not an institutional appointment used to stop engineering:
the independently required semantic acceptance input is missing, current source supplies no
compatible evidence that a new positive consumer could honestly resolve, and all discovered
nonvacuity repairs already landed. An appointment or a trusted signed assertion alone is not
that input under P37. Required change: the responsible promotion-authority/scientific owner
supplies the exact authority-grade acceptance mapping and evidence; the first-promotion row's
N8 producer/persistence and production N9 writer-context chain then have a real source to wire.

The existing protected-mode scope-gap obligation is an honest persisted typed nonreceipt.
It is **not** a fully implemented signed-evidence intake or a literal typed signer slot; those
remain `producer_missing` / `bridge_missing` at the appropriate purpose. A second permanent
negative would not make that missing capability real. No new receipt epoch or production
change is justified solely to rename this same absence.
