# Acquisition positive admission and epoch qualification — Stage 1

Holder/executor: `positive_research`. Read-only source basis: attached
`codex/acquisition-movement`, `28b8a1a42` (full identity in the census receipt).
Scope: `ds15-fresh-positive-production-route` and
`ds15-semantic-epoch-qualification-authority` only. Source, tests, configuration,
register, ledger and generated surfaces are unchanged by this workstream.

## P-F01 — grouping holds, but there are distinct admission objects

The two rows belong to the acquisition lifecycle. They share the chain between
quarantined acquisition evidence, qualified semantic epoch, visible owner
overlay and exact case re-entry. Neither is decided by a transition signature.
This re-establishes **EP-F08** in
`docs/superpowers/specs/2026-09-12-epoch-positive-path-stage1.md:205`, rather than
inheriting its conclusion. The epoch journal
`docs/superpowers/journals/2026-09-12-epoch-positive-path.md:66` explicitly leaves
these acquisition sources outside its transition repair. Later shared deployment
hooks do not change the acquisition composition (P-F03 below).

This is not one interchangeable admission type. The data passport admits
observations to a hidden owner overlay; native chronology qualification authorizes
epoch-history append; activation exposes the overlay; same-case re-entry consumes
that exposed state. A movement-family chronology/row-admission record is another
downstream object. The Task E **GY-GAP6 routable specification at freeze**, in
`docs/superpowers/journals/2026-08-30-debt-e-acquisition-n13b.md:1061`, names that
movement-family producer and its GY row/date/head bindings. An epoch-family
qualification cannot be silently promoted into movement-family authority.

## P-F02 — exact production-port stop and consumer effect

`WorldBankWDIAcquisitionExecutionPort.execute` invokes the actual N13b executor
at `src/polisyos/runtime/http/services/acquisition_surface_execution.py:391`, or
the explicitly injected test transport at :400. It then reduces the resulting
`LiveSourceExecutionEvidence` to four artifact references at :408–416 and returns
`AcquisitionOwnerExecutionResult(disposition="quarantined_no_growth",
admitted_observation_delta=0)` at :422–426. No data-quality result, appointment,
epoch result or transport result selects another return arm here.

`reenter` (:428–436) and `resume_reentry` (:438–446) discard their arguments and
call `_raise_reentry_not_admitted`; :558–563 raises
`acquisition_live_evidence_not_admitted`. Even a shape-valid positive result
cannot change those methods. This is an executable property, not a missing
institution being inferred from a string.

The real non-test composition is
`AcquisitionActionService.__init__` at
`src/polisyos/runtime/http/services/acquisition_action_service.py:250–258`, which
calls `build_production_world_bank_wdi_execution_port`. The factory at
`acquisition_surface_execution.py:566–612` requires production profile, canonical
provision/registry/baseline/L5 owner files and control-owned storage. It installs
the handler at `acquisition_action_service.py:274`. The served terminus is
`POST /api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute`,
`src/polisyos/runtime/http/routes/acquisitions.py:199–228`.
The deferred job handler invokes `port.execute` at
`acquisition_action_service.py:513`, then its :533–541 quarantine arm persists
`AcquisitionRouteLoopReceipt` through `sink.persist_terminal`. The positive
world-commit/re-entry branch already exists at :542–554. Recovering a committed
pending action uses `resume_world_committed_reentry` at :493–498.

Reachability qualification: the real HTTP/worker call chain exists, but absent
mandate/authority-provider evidence may refuse before reaching this port. The
port probe isolates the later forced stop; it does not claim a current admitted
production request, live provider call or new observations.

## P-F03 — qualification has a durable negative, not a positive acquisition composition

The existing non-test caller is
`src/polisyos/runtime/quality/acquisition_epoch_admission.py:run_admission`,
:78–96. Runnable terminus:
`python -m polisyos.runtime.quality.acquisition_epoch_admission --request REQUEST`.
It invokes the existing acquisition producer, then resolves and compares its
exact CAS statement at :99–124 before printing it. Typed negative exit is 1;
invalid or unresolved evidence exits 2. Its :97–98 guard refuses an
`ActivatedSemanticEpochAdmissionReceipt` with
`acquisition_epoch_activation_consumer_not_established`.

The producer
`admit_acquisition_with_production_semantic_epoch` at
`src/polisyos/runtime/quality/acquisition_executor.py:1849` composes a real local
catalog overlay, native history and boundary/facet owners. It **unconditionally**
constructs `SemanticEpochQualificationAdapter.from_unallocated_policy_authority`
at :1940–1945 and
`QualificationConsumer.from_unallocated_policy_authority` at :1971–1973.
Neither its signature nor the CLI request accepts an admitted deployment or a
purpose-specific policy owner. Installing an institution elsewhere leaves these
exact constructors unchanged.

The actual typed empty slot is
`SemanticEpochQualificationAdapter._policy_owner: EpochChronologyPolicyOwner | None`
at `src/polisyos/runtime/quality/semantic_epoch.py:1036`; the factory sets `None`
at :1068. The policy-owner protocol at :978–996 supplies native profile,
projection verifier provenance and member/query predicate dispositions. Separately,
`QualificationConsumer` carries an empty private owner and a true unallocated flag
at `src/polisyos/runtime/quality/chronology_qualification.py:216–220`. Its
:251–260 branch returns `PolicyAdmissionMissingFailure` before calling the native
adapter. `_append_and_qualify` at `semantic_epoch.py:2313–2338` persists that
typed negative before the history append at :2339.

The shared epoch lane supplied reusable deployment mechanisms:
`EpochDeploymentConfig.predicate_policy_admission_refs` /
`predicate_owner_verification_refs` / `native_candidate_refs`
(`epoch_deployment.py:104–106`), privileged
`PredicatePolicyOwnerProvenanceVerifier | None` at :383 and
`QualificationConsumer.from_deployment` at `chronology_qualification.py:224`.
`EpochEvidenceExchange.enumerate_admission_refs` resolves exact signed policy
admissions by selection key (`epoch_evidence_exchange.py:31–47`). However generic
signed transport and declared verifier receipts deliberately return
`policy_owner_relation_not_established` without the native verifier operation
(:87–104, :165–170). Those existing hooks are reuse candidates, not evidence that
the acquisition-native predicate producer/verifier is installed.

Thus the register's **BRIDGE HALF DISCHARGED 2026-09-10** at
`docs/plans/active/DEBT-REGISTER.md:436` remains true for its durable-negative
composition. Its **TASK EPOCH-POSITIVE-PATH 2026-09-13** qualification/activation
distinction also holds. Appointment-only is not a description of the broader
positive acquisition capability: positive configuration/consumption still needs
engineering. The row's original signal may treat its negative bridge as discharged;
this report does not retroactively change that accepted signal.

## P-F04 — positive requirements derived from the existing refusals

The smallest data-admission producer to reuse is
`admit_acquisition_with_semantic_epoch`,
`src/polisyos/runtime/quality/acquisition_executor.py:1703–1844`. Its output union
is `ActivatedSemanticEpochAdmissionReceipt | PersistedSemanticEpochProductionReceipt`.
The positive DTO is defined at :387–401. It binds the passport, prepared epoch,
pending overlay, production receipt, activated overlay, native membership,
semantic denominator, projection verification and exact stamp.

| Existing stop/property | Required evidence/behavior already imposed by its owner |
| --- | --- |
| Verified raw source and candidate (`acquisition_executor.py:1717–1742`) | Raw journal bytes exist in CAS; for live fetch, use the normalized data artifact and complete `LiveSourceExecutionEvidence`, with verified manifest/hash/content. Four reference strings alone do not carry the producer input. |
| Admission passport (`acquisition_executor.py:263–385`, :2213–2323) | Recompute live/raw/baseline bindings; source authority; measured nonempty schema; canonical field/distribution/unit transformation; calibrated alignment; admissible license; PII result; source watermark/version; L5 trust; observed/proxy provenance. Any rejection gives quarantine. A proxy may be admitted degraded and must not be relabeled observed. |
| Hidden owner admission (`overlay.py:1014–1115`) | Read back and bind prepared candidate/stamp; revalidate owner evidence immediately; require passport admitted/admitted_degraded; reject derived/model-output observations; require exact registered variable/field. |
| Nonempty actual observations (`overlay.py:1110–1119`, :1212–1228; :3001–3003) | Derive and validate canonical rows from verified source bytes. Persist `PendingOverlayAdmissionStatement` with owner-computed count and complete native membership denominator. Pending is not visible world growth. |
| Admitted semantic-boundary evidence (`acquisition_executor.py:1793–1806`; `semantic_epoch.py:2591–2838`) | Persist native member, passport, pending receipt, native membership, semantic denominator, projection verification and verifier provenance; recursively read/bind them; re-enumerate the real owner after admission; preserve exact query and epoch stamp. |
| Native qualification before append (`semantic_epoch.py:2313–2345`) | `NativeChronologyQualified`, produced by the native adapter plus exact admitted policy/owner verification, is required before append. Missing or failing evidence persists a negative; competing history head produces contested. |
| Activation (`overlay.py:1298–1372`, :1387–1500) | Resolve full persisted positive epoch receipt; match its raw bytes/semantic hash, epoch, prepared ref and query to the pending receipt; reconcile physical native members; atomically expose only that epoch; return `OverlayAdmissionReceipt`. |
| Fresh delta versus replay (`overlay.py:1451–1480`, :1496–1500) | Owner receipt reports `replayed`. The same positive row count on replay is not fresh growth. A producer must distinguish newly activated members from an already-active receipt; copying a caller's positive integer into `admitted_observation_delta` is insufficient. |
| Worker positive result (`acquisition_action_service.py:170–187`) | `world_committed` requires positive delta, activated overlay receipt and post-epoch evidence. The present DTO checks shape and numbers; the wiring must derive/resolve them from the previous owners, not self-attest them. |

No new license class, alignment threshold, epoch scope, institutional appointment
or policy decision is proposed. The table is a dependency slice through runtime
rejection paths, not a replacement admission specification.

## P-F05 — exact same-case re-entry exists and requires wiring

Reuse `GenerationCycleController.reenter_after_active_acquisition_overlay`
(`src/polisyos/runtime/quality/generation_cycle.py:2939–3138`). The method consumes
`OverlayAdmissionReceipt`, not a generic artifact reference or transition signature.
It requires the exact original run/source cycle/`DesignProblem` match (:2957–2967),
an `acquisition_required` source terminal and its requirement/routing report
(:2968–2975), exact unchanged baseline and active overlay (:2983–2999), and
independent activated receipt validation (:3001–3016). It then requires one
matching epoch/passport, admitted status, positive owner count and exactly the
demanded canonical variable (:3018–3042), cost basis agreement (:3043–3049), and
one exact activation and one epoch-production event (:3051–3068).

It constructs a new N6 value port over that active owner overlay and runs exactly
the next cycle (:3093–3111). The return is `AcquisitionOverlayReentryReceipt`
(:912–945, :3113–3138), binding source run/cycle/case/candidate, receipt/hash,
baseline, epoch/passport/variable/count, semantic production receipt and new cycle.
The `VerifiedAcquisitionRouteClosure` already carries the original problem, run
and source cycle (`acquisition_route_loop.py:182–205`), so these are existing
inputs to wire, not missing world-model abstractions.

Re-entry does not guarantee a successful recommendation or a deeper terminal.
Its genuine next-cycle result may still refuse or request more acquisition.
GY-GAP6's distinct deeper-terminal / admitted movement-head criterion must be
checked by that row's own consumer, not inferred from nonzero observations.

## P-F06 — buildable work and irreducible residuals

1. Extend the existing production port/owner bridge to retain complete typed live
   execution evidence and route-derived governed admission inputs. Invoke the
   existing two-phase producer; persist/consume its negative through existing
   route lifecycle when no policy is admitted. Empty slots do not block this work.
2. Reuse `EpochDeployment` evidence intake and `QualificationConsumer.from_deployment`
   for an admitted acquisition composition, preserving explicit unallocated owner
   and native-verifier arms. Use the canonical acquisition-native boundary and
   predicate adapter; do not treat a transition signer as policy authority.
3. Extend the activated-result consumer and port result derivation to resolve
   exact owner receipts, calculate fresh growth with replay distinction, and invoke
   the existing same-case re-entry method with the closure's existing source objects.
   Persist/recover the returned re-entry receipt through the current route sink.
4. Leave movement-family GY-row/policy/head admission to the separate movement
   producer/consumer chain described by Task E. It can consume this acquisition
   result; acquisition cannot sign for it.

Wait classification: unappointed predicate-policy authority is an **appointment**
residual; unavailable native predicate evidence/verifier or missing port activation
and re-entry connections are **capability** residuals (`producer_missing` or
`bridge_missing`, depending on the concrete seam), not appointment waits. A
non-current/mismatched case, variable, query or receipt is a **scope** refusal.
Transition signing and movement-family policy are **different variables**, with
different consumers. Non-WDI connector execution remains the named
`surface_out_of_scope` boundary already projected by DS15.

No new architectural yes/no decision was found necessary for the surrounding
wiring in this two-row scope. The exact positive-evidence question remains:
**which independently admitted epoch-native member/query predicates and verifier
provenance cover this acquisition-finalization scope/purpose, and which institution
may issue their policy/admission/owner-relation evidence?** Existing protocols and
fail-closed slots carry that absence. This question does not authorize invented
predicate truth, self-appointment, or use of movement-family/transition evidence
as a substitute; it also does not prevent building and demonstrating the empty arm.

## Verification and measurement boundary

Predeclared counterexample: another production caller could bypass the World Bank
port, invoke the positive owner/re-entry under an alias, or install acquisition
qualification via a shared deployment. The full source AST census and independent
token call parser run in `census.py`; a case-insensitive whole-source lexical pass
provides the requested insensitive variant. Actual caller tracing above resolves
the specific production callback; arbitrary reflection/receiver dispatch remains
`unresolved_by_construction`, never a proved global zero.

The instrument reuses `docs/superpowers/journals/uninvoked/census.py`; every
successful source read has a content hash in `raw/census-complete.json`, and
`git ls-files` is independently reconciled with `git ls-tree` at HEAD. Source
file types are `.py` under tracked `policy-engine/src/` only; tests/tools/docs,
external deployed data and unselected authority documents are excluded. Failed
reads or parse disagreement abort rather than becoming empty input. The source
census is not a census of current production instances. In particular the old
“zero of five conjuncts” is not reissued from a source scan.

Focused checks and in-memory removal probe outputs are retained under `raw/`.
`port_probe.py` exercises the actual port after an isolated test transport and
both re-entry methods; its shape-valid-positive counterexample still refuses.
Its removal switch replaces only the in-memory re-entry enforcement helper while
retaining the source/DTO/refusal strings; the unchanged behavioral assertion must
fail. These witnesses carry `behavioral_fixture_not_production`, not institution
or live-source authority. Final receipts/counts are appended after completion.

Pattern pass: P01/P02/P12 (actual producer→consumer chain), P04/P05 (pending,
active, degraded and authority roles), P10/P29/P32/P37/P38 (real owner evidence
versus typed shape/positive integer), P27 (reuse canonical overlay/epoch/re-entry),
P35/P36 (complete denominators and finding IDs), P40 (the missing positive bridge
is the same class behind successive refusal layers, not multiple invitations to
instance-patch). No register update or source repair is made in Stage 1.

## Completed census receipt

`census.py` exited 0 at the exact base above. Complete selected denominator:
**2,663 tracked `policy-engine/src/**/*.py` files**; **10,001 classes**,
**37,192 function/method definitions**, **25,646 imports**, **368,837 AST calls**.
The independently tokenized simple-name/attribute intersection is
**368,706 calls = 368,706 AST calls**, with zero disagreements and zero parse
failures. Index/tree path-set equality is exact, not merely equal counts.
Holder classification is `recomputed` for this workstream. Other holders must
run their own check before promoting supplied counts to `recomputed`.

Selected source call records (definitions do not count as calls) are a projection
of the complete AST records in `raw/selected-caller-records.json`:

| Symbol | Source definitions | Named source calls | Exact caller |
| --- | ---: | ---: | --- |
| `WorldBankWDIAcquisitionExecutionPort` | 1 | 1 | production factory, `acquisition_surface_execution.py:606` |
| `build_production_world_bank_wdi_execution_port` | 1 | 1 | service constructor, `acquisition_action_service.py:255` |
| `AcquisitionOwnerExecutionResult` | 1 | 1 | unconditional quarantine, `acquisition_surface_execution.py:422` |
| `admit_acquisition_with_production_semantic_epoch` | 1 | 1 | CLI `run_admission`, `acquisition_epoch_admission.py:79` |
| `admit_acquisition_with_semantic_epoch` | 1 | 1 | unallocated production wrapper, `acquisition_executor.py:1977` |
| `activate_semantic_epoch` | 2 (protocol and owner) | 1 | two-phase generic owner, `acquisition_executor.py:1822` |
| `ActivatedSemanticEpochAdmissionReceipt` | 1 | 1 | two-phase generic owner, `acquisition_executor.py:1833` |
| `reenter_after_active_acquisition_overlay` | 1 | 0 | no named source call in the selected denominator |
| `member_predicates` / `query_predicates` | 1 each, both protocol-only | 1 each | adapter at `semantic_epoch.py:1182–1183` |

The re-entry method's absent named source invocation is `bridge_missing`; the
port/sink wiring is not already a consumer of its typed return. The native
member/query predicate declarations similarly do not constitute a concrete
predicate producer. Runtime reflection/external supplied implementations remain
the named unresolved dispatch class, not a repository-wide assertion that an
institution cannot provide an implementation.

## Fresh runtime verification receipts

Command (from `policy-engine`, complete output `raw/focused-tests.log`):

```sh
PYTHONPATH=src:tests:. .venv/bin/python -m pytest -o addopts= \
  --basetemp=docs/superpowers/journals/acquisition-movement/positive/raw/pytest-temp \
  tests/unit/runtime/quality/test_acquisition_epoch_admission.py::test_python_module_is_runnable_terminus \
  tests/integration/core_runtime/test_acquisition_route_execution_binding.py::test_concrete_port_binds_route_and_governed_storage_before_executor
```

Result: **1 passed, 1 harness timeout; exit 1; 501.40 seconds**. The production
port binding/transport test passed. The CLI subprocess hit the test's unchanged
120-second timeout before emitting stdout/stderr. Its semantic result is **UNRUN**,
not a negative receipt, product failure, green, or proved inherited red. The
prepared isolated request remains under
`raw/pytest-temp/test_python_module_is_runnable0/request.json`. P-F03's durable
negative behavior is supported here by exact source tracing and the explicitly
historical U15/EP-F08 receipts, pending a fresh completed operational replay.

No test source or timeout was changed. Further test processes were not launched
after the root's freeze instruction; already-running port witness/removal runs
are recorded separately when they finish.
