# Group A / 05 — Scope adjudication: carrying a rule and admitting its application

Research for the architect; no decision, owner allocation, implementation grant, debt
status change, or closure determination. Source pin: `63bdb9640`. Paths below are
repository-relative and source citations explicitly retain that pin. The Task D and
Task Q corrections supplied by the principal are accepted premises, not reopened
historical investigations.

## 1. Discrepancy between the row, the measurement, and the agreed history

The baseline row says the ratified document owns the rule but “no typed
scope-adjudication artifact, producer, or bridge exists.” That sentence conflates
the missing authority application with the candidate artifact already delivered.
The current artifact is `ScopeAdjudicationCandidate`, with a deterministic builder,
content-integrity verifier, plane constraints and typed limitations. It fixes
`authority_effect="none"`, `closure_effect="none"`, prohibits scope rulings and
claim-head advancement, and always retains resolver/consumer limitations.
Evidence: `policy-engine/src/polisyos/core/contracts/scope_adjudication.py@63bdb9640`,
`ScopeAdjudicationCandidate`, `build_scope_adjudication_candidate`,
`verify_scope_adjudication_candidate`, `_derive_limitations`.

The baseline claim is quoted only from
`policy-engine/docs/plans/active/DEBT-REGISTER.md@63bdb9640`, row
`DS11-SCOPE-ADJUDICATION-RECORD`; it is not evidence of the tree. The row itself also
records the principal's correction: Task D built the candidate artifact, its
historical test/census receipts established a bounded candidate result, and the
named lifecycle test was intentionally absent. D's proposed institutional/inaccessible
blocker was rejected because the relevant files were in D's scope. Task Q accepted
the candidate as correct but nonterminal and preserved the authority-band work owed.
Declaring the candidate terminal and changing the requested signal is an already
rejected alternative. This report does not re-propose it.

The measured distinction is between **the authority of the general rule** and
**authority for a particular application and lifecycle act**. The document already
ratifies the ordered test. The candidate code does not establish the truth of its
supplied observations or admit the resulting proposal into a claim head. A
transport-only Runtime wrapper and a stateful claim owner are different planes;
the question cannot be settled by giving the whole chain one label.

The historical Atlas/GY allocation is accepted as an architect-created work split,
not an intrinsic inability. A source-path correction matters for the actual trace:
the current supersession producer/resolver lives in
`policy-engine/src/polisyos/scientist/evidence/claims/owner_events.py@63bdb9640`,
not the historical `scientist/governance/continuous/owner_events.py` spelling.

## 2. Measured commands, complete denominators, and the actual admission path

The reproducible instrument is
`policy-engine/docs/superpowers/journals/group-a/05-scope/measure_scope.py`.
Run from the analysis worktree:

```sh
python3 policy-engine/docs/superpowers/journals/group-a/05-scope/measure_scope.py
```

It reads pinned Git objects without importing or editing product code. Independent
`git ls-tree -r --name-only -z` and `git archive --format=tar` member enumeration
agree on the complete denominators. Both derive from the same Git commit; they
are independent enumeration mechanisms, not independent witnesses of runtime truth.

| Path denominator at the pin | File-type denominator | ls-tree | archive |
| --- | --- | ---: | ---: |
| `policy-engine/**` | tracked `.py` blobs | 6,176 | 6,176 |
| `policy-engine/src/polisyos/**` | tracked `.py` blobs | 2,653 | 2,653 |
| `policy-engine/tests/**` | tracked `.py` blobs | 2,578 | 2,578 |

The whole-project Python denominator contains zero AST parse errors. On that
complete denominator, there are zero definitions named
`ScopePredicateEvidenceResolver`, `ScopeAdjudicationRecord`,
`ScopeAdjudicationClaimLifecycleConsumer`, or
`test_four_way_ruling_is_produced_consumed_and_plane_specific`.
The candidate builder and verifier definitions resolve to the source file above;
their direct syntactic callsites are confined to the exact scope unit file in
the receipt. The exact file's complete AST definition enumeration contains five
test functions; this is not a pytest collected-case count and does not replace
the accepted historical Task D receipt.

Complete deciding output: `policy-engine/docs/superpowers/journals/group-a/05-scope/census-receipt.json`.
The receipt lists definition, import, and direct call hits, the exact test identities,
and the content hash of `raw/ast-trace.json`; the latter retains complete instrument
output for the traced definitions. `raw/census-command.log` retains stdout from
the replay. Direct AST syntax does not prove the absence of reflection or of a
semantically similar differently named mechanism. No product tests or live
signature probe were executed for this report.

The actual paths are distinct:

| Plane/path | Observed call chain and its consequence | Pinned source |
| --- | --- | --- |
| Ordinary workflow admission | `launch_workflow_run` resolves execution policy and input refs, then `_enqueue_job` persists the payload and capability manifest and creates a durable job. `_process_control_job` hydrates inputs, conditionally invokes `_admit_evaluation_safety_attempt`, then `_execute_workflow_control_transition`. This is job/evaluation admission, not four-way scope adjudication. | `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py@63bdb9640`, lines 2094, 2670, 2967, 3289 |
| Workflow execution | `_execute_workflow_control_transition` selects the workspace path or legacy-shadow path; `_execute_workspace_loop_workflow` further dispatches S2, production-case intake, or fixture. A queued/accepted job is not itself a scope ruling or claim-head advance. | `policy-engine/src/polisyos/runtime/http/services/control/workspace_loop_transition.py@63bdb9640`, lines 59, 137 |
| Monitor receipt and claim reaction | `_publish_monitor_decision_validity_event` resolves exact monitor content, checks the applicable perturbation/epoch or advisory-custody conditions, delegates to `bridge_monitor_event`, and checks that the returned monitor agrees. The bridge reloads the packet/ledger, persists lifecycle output, and passes an eligible owner-event candidate to `claim_owner.append_verified_owner_event`. | `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py@63bdb9640`, line 3428; `policy-engine/src/polisyos/scientist/governance/continuous/lifecycle_bridge.py@63bdb9640`, line 114 |
| Epoch admission and claim reaction | `admit_epoch_validity_batch` invokes the Decision Validity owner, resolves completed batch evidence, and calls `bridge_completed_batch`. The bridge reparses and hashes receipt bytes, binds the query and packet denominator, resolves dependency mapping, then calls `advance_verified_batch`. | `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py@63bdb9640`, line 3594; `policy-engine/src/polisyos/scientist/governance/continuous/lifecycle_bridge.py@63bdb9640`, line 215 |
| Owner and store composition | Container construction binds the claim owner, Decision Validity owner, bridge and artifact store by identity; startup injects that bridge into `ControlPlaneService`. The default claim owner factory currently returns `UnappointedClaimLedgerOwner`. That is runtime configuration evidence, not a finding that a new institution must be appointed for scope work. | `policy-engine/src/polisyos/runtime/http/container.py@63bdb9640`, lines 203–235, 310–325; `policy-engine/src/polisyos/scientist/evidence/claims/head_index.py@63bdb9640`, `build_default_claim_ledger_owner`, line 4150 |
| Authoritative head admission and replay | Repository owner `append_verified_owner_event` resolves current head, resolves the signed supersession event, binds the exact prior head, derives the next ledger, persists a bridge and advances through the owner CAS. `_verify_closed_head` re-resolves and replays owner events when validating the complete head. The admitted owner-event model and appointment have `authority_purpose: Literal["claim_supersession"]`; they are not a scope-purpose admission contract. | `policy-engine/src/polisyos/scientist/evidence/claims/head_index.py@63bdb9640`, lines 2800 onward, 3890 onward; `policy-engine/src/polisyos/scientist/evidence/claims/owner_events.py@63bdb9640`, lines 55, 93, 296, 337 |

The last row explains why placing a consumer call in `run_lifecycle` would not by
itself settle the missing semantics. Existing head admission and complete-head
replay both interpret the event's purpose. A new transport wrapper cannot confer
that purpose on a candidate. Conversely, a purpose-specific refusal in the
current owner contract does not establish that a new external sovereign function
is required. It establishes the current mechanism's accepted purpose.

## 3. Competing readings: what each licenses and what it costs

| Reading, separated by plane | What the existing rulings license under that reading | Cost and boundary | Specific fact that would distinguish it |
| --- | --- | --- | --- |
| Carry an already-ratified rule/application | A consumer may carry an admitted, purpose-bound record, or a pure verifier may check supplied objects without adding authority. Implementing the ratified ordered rule does not require re-ratifying that rule. | The chain still needs evidence resolution, content binding, competence/time/use checks, persistence and owner-consumed lifecycle semantics. Calling these operations “carrying” does not waive their authority conditions. | An existing admitted application must resolve to the exact subject, plane, predicate evidence, permitted use and owner-issued provenance that the proposed consumer uses; the consumer must add no new authoritative proposition. The current candidate record does not provide that evidence. |
| Produce/admit a new authoritative application | The fixed general rule can supply normative authority while an owner computes a new conclusion about a particular function and claim. Producing that receipt or admitting it into a current claim head is an authority act even if the decision algorithm is deterministic. | The authority act needs an authorized producer and established predicates. Under §9.5, absent institutional authority constrains the signed result, not whether the whole demonstrable mechanism can be built. | Identify the exact new proposition or protected effect that did not already exist in an admitted artifact, plus which owner-state reads/writes establish it. Current head admission reads CAS, signatures and time, and changes owner head state; it is not a pure object-only verifier. Whether an existing appointment covers the proposed scope act remains a separate question. |

These readings can coexist within one implementation: Runtime can carry a rule's
application while its delegated owner mints the purpose-scoped receipt or lifecycle
fact. They do not yield a whole-row answer until the architect specifies the
protected act and identifies its authority source. Neither reading licenses
candidate-band terminality or promotion based merely on the text `recomputed`.

## 4. Facts and rulings on which the architect's decision rests

**Rule source.** Identity decision §5 supplies the ordered OWN/INTEGRATE/OBSERVE/
OUT_OF_SCOPE rule, §6 supplies ratified zone applications, and §9.3 requires
adjudication against that document. Its authority scope includes
`scope_adjudication`; its exclusions include `task_execution_contract` and
`jurisdiction_specific_legal_conclusion`. Citation:
`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md@63bdb9640`,
§5, §6, §9.3 and frontmatter. A ratified rule is not evidence that the premises of
every future application are true.

**Capability versus signature.** The principal's §9.5 ruling explicitly places an
institutional refusal on the signed claim/promotion/custody fact and requires a
fully built, demonstrable mechanism with a typed-empty signature slot where needed.
Its §9.6 ruling distinguishes production/admission from vocabulary and pure checking:
object-only checks can move; predicates reaching owner-controlled registry/store/
clock/I/O stay with the owner. The falsifier requires rejection of a consumer-made
artifact without the producer-owned marker. Citation: the same pinned identity
decision, **§9 item 5** and **§9 item 6**. Nothing in this reading assigns a new owner
or presumes a missing institution.

**Plane and action.** **S0-K03** requires separating the external act, evidence
emission, PolicyOS admission, scoped claim reaction and public projection.
**S0-K06**, including its ratified §4.3 application note, closes scope for the
affected protected action while permitting declared unknowns in the candidate
band. K06's underlying wording includes subject, purpose, tenant, jurisdiction,
competent producer, relevant time and permitted/prohibited use, and explicitly does
not prescribe one gate sequence. Citations:
`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md@63bdb9640`,
**S0-K03**, **S0-K06**, §4.3; ratified wording at
`policy-engine/docs/research/policy-operations/consolidation/stage0/stage0-consensus-kernel.md@63bdb9640`,
**S0-K03**, **S0-K06**. The ratification's own exclusions include
`canonical_owner_assignment` and `authority_grant`; it cannot supply a missing
instance-specific authority grant by adjacency.

**Predicate provenance in the actual artifact.** `_validate_evidence_and_establishment`
checks paired refs/digests and declared classes; `_derive_proposed_ruling` uses the
supplied boolean observations; `verify_scope_adjudication_candidate` reparses and
recomputes the payload digest. None of those operations reads the referenced evidence
or recomputes the premise “absence makes our published claim silently false.”
An observation declared `recomputed` is therefore a producer-supplied classification
at this boundary, not a measured provenance finding of this report. Source:
`policy-engine/src/polisyos/core/contracts/scope_adjudication.py@63bdb9640`, named
definitions above. The potential divergent case is a false factual observation with
self-consistent ref/digest and recomputed candidate digest. Integrity checking and
factual adjudication ask different questions. This is source-level reasoning, not a
reported executed adversarial probe.

Pattern pass, using the register as the diagnostic lens rather than tree evidence:
**P01/P02** distinguish existing candidate machinery from the missing admitted
producer/consumer chain; **P05/P32/P37/P38** distinguish rule authority, content
integrity and predicate truth; **P35/P36** constrain denominator and ruling citations;
**P31** requires considering owner intake and full-head replay together. Component
gap vocabulary relevant to a future architect allocation is `bridge_missing`,
`consumer_missing`, `verification_missing`, `semantic_test_missing`, with no row
status assigned here. The acceptance property under discussion remains a produced,
persisted, plane-specific, purpose-bound ruling whose premises are established and
whose lifecycle consequence is consumed and inspectable, including refusal for false
premises or mismatched purposes. This names the property, not a new implementation
contract or a declaration that it has passed.

## 5. What remains unknown

- The exact instance-level proposition and lifecycle action a scope ruling is meant
  to authorize: owning a capability, limiting an existing claim, changing a claim
  head, or another precisely scoped act. They cannot be substituted for one another.
- Which controlled sources can establish each four-way premise for the relevant
  subject/plane, rather than accepting an authored boolean and provenance label.
- Whether an existing admitted application or purpose-specific owner authorization
  already covers that act. The named AST absence and present supersession purpose do
  not prove that no differently named reusable authority mechanism exists.
- The architect's allocation across the current owner intake, complete-head replay,
  evidence resolver, Runtime bridge and governed surface. The earlier Atlas/GY split
  supplies no intrinsic technical answer.
- A live purpose-scoped end-to-end witness for this pin. This report traced source
  and AST; it does not claim to replay the historical signed-event probe or to prove
  a new applied ruling by execution.
