# Promotion conjunction: row and ownership research

Read-only source research at `28b8a1a42`, attached branch
`codex/promotion-conjunction`. This note does not update the register or ledger,
appoint an authority, or certify a canonical promotion. Paths below are relative
to `policy-engine/` and refer to their bytes at `@28b8a1a42` unless explicitly
identified as historical evidence. No current test result is claimed here.

## Deciding predicates, before adjudication

For row classification, the deciding variable is the property in its operative
closure signal, traced through its current source producer and consumers. A
historical opening description does not override later source or the operative
signal. A reviewer/fallback path owner is not automatically the owner of a new
scientific admission semantic. A positive mechanism control with explicit test
keys proves a gate is not vacuous; it is not an empirical policy candidate.

For ownership, distinguish (a) source maintenance/refusal custody, (b) the
source-to-original-construct scientific acceptance decision, and (c) the actor
authorized to supply evidence under that decision. This avoids using a broad
Runtime owner label to appoint a scientific decider by adjacency (P36).

## PC-R1: classify each requested row by its actual remaining condition

| Register identity | Current deciding variable | Classification and smallest remaining link |
| --- | --- | --- |
| `gy-promotion-obligations-scope-insufficient` | Its recorded closure signal is the complete `GY-O0-NC-01` field-pilot event, not the count of helper returns. The current EFFECT/MEASUREMENT/INDEPENDENCE paths consume genuine owner evidence; protected EvalSafety still has no promotion-purpose decision input. | The head description is stale. Its remainder combines an authentic complete candidate, protected-purpose authority semantics/evidence, and observed near-miss/counter reconciliation. Scope refusal count alone cannot close it. Do not type the whole row as an appointment. |
| `GY-O0-NC-01` | A *single real production* field-pilot request must be consumer-promotable while independently missing a required attempted-evaluation protection; its durable O0 decision must be blocked, near-miss true, counters reconciled once, core/hash unchanged. | An unproduced deciding event with multiple conjuncts. A supplied signer cannot manufacture the candidate, and a good data-only candidate cannot satisfy this field-pilot scope. The protected-purpose intake is buildable up to a typed-empty slot; scientific rules and authentic evidence remain separate. |
| `eval-safety-promotion-authority-producer-missing` | `_eval_safety_obligation` has no promotion-purpose input and returns scope-insufficient for the protected modes; the O0 certificate explicitly denies promotion authority. | A real absent capability ahead of any appointment: contract, empty trust/authority slot, persistence/resolution, invocation bridge, and N9 consumer. The deciding protected-purpose policy and authorized minting actor are not supplied. Institutional absence does not prevent building neutral custody/intake and fail-closed consumption. |
| `first-promotion-candidate-with-complete-evidence` | Authentic complete candidate evidence must jointly survive current N7/N8/N9 authority checks and reach the production consumer. | Historical claims of missing source-preservation/context wiring are superseded by current `GenerationCycleController` and `generation_source`. The live upstream acceptance slot remains empty, but the correspondence standard, risk composition, allocation and stratum policy are already decided (PC-R1-CORRECTION below). Purpose-qualified appointment, scoped genuine labels and application remain distinct from source identity; an all-green receipt cannot be constructed for this row. |
| `GY-PA1` (with `GY-GAP7`) | Authority to select from the exact source frontier, under the right purpose/decision role/case/scope/time, with persisted refusal and current consumers. | `producer_missing` is refuted for its S8/GAP7 mechanism by current source. The producer, persisted admission, resolver, typed request, ranked consumer, actual worker bridge, later signed HTTP intake and current readers exist. Empty deployment trust is an intentionally unfilled slot, not producer absence. Its separate N8/CG2 scientific gap does not retag the S8 permission mechanism as missing. |
| `gy-j-positive-evidence-admission-producer-has-no-owner` | Admission of truthful evidence supporting an original requested construct in its actual scope, followed by the existing S1/production-population consumer. | Missing scientific admission capability/acceptance basis in the measured live chain; `absent/unallocated` for that semantic. Refusal custody and generic path maintenance already have owners. Architect allocation and acceptance decision are needed; copying their owner label is not sufficient. |

The row source is `docs/plans/active/DEBT-REGISTER.md` (exact named rows in sections
A/B; read-only). The later authoritative task-standing rows in
`docs/plans/active/layer3-slices/GY-engine-subordination.md` matter particularly:
`GY-PA1` is `executed` in §8.5, while the register still starts with
`producer_missing`. Neither the August absence census nor the September journal's
earlier intermediate blocker is treated as today's source state.

## PC-R5: GAP7/S8 is built and orchestrated

Current source, read through its operative boundaries:

- `src/polisyos/runtime/quality/design_axes/value_choice_provenance.py`:
  `NormativeAuthorizationRecord` and `NormativeAuthorizationRecordV2` bind
  `value_schedule_for_ranking` to exact schedule/frontier/selection and, for
  generation, compiled/source/node coordinates. `NormativeDecisionRequest`
  exists as the persisted refusal output. `NormativeValueScheduleOwner` resolves
  content and manifests, independently verifies configured signatures, rejects
  self-grading and wrong decision role/purpose/case/scope/mandate/time, produces
  admission, and re-resolves it before ranked emission. Empty default trust raises
  `p20_normative_authority_slot_empty`; it does not erase the producer.
- `src/polisyos/runtime/http/services/control/generation_cycle.py`:
  `produce_normative_run_disposition` walks actual compiled leaves, calls
  `owner.produce_generation_disposition`, persists the composition, and calls
  `project_normative_run_disposition` for readback. The composition withholds
  rankings unless its leaves are authorized.
- Non-test production caller:
  `ControlPlaneService`'s natural-language worker in
  `src/polisyos/runtime/http/services/control/run_lifecycle.py` calls
  `resolve_generation_value_choices` after compilation, then publishes compiled
  and normative outputs through `_publish_generation_run` and completes the job.
  `submit_normative_evidence` separately admits evidence signed after source
  production and attaches the conditional current head through the existing
  control-store transaction.
- Runnable surface/terminus:
  `POST /api/v1/control/runs/{run_id}/normative-evidence` in
  `src/polisyos/runtime/http/routes/control.py` invokes that service. Both
  `get_job_status` and `get_latest_job_for_run` consume current owner replay;
  no fresh event means no invented current head.

The historical deciding findings are `GGA-PA1-S8-01/02` in
`docs/superpowers/journals/2026-09-07-gy-grade-authority.md`, followed by
`PA1-R01` / `PA1-D3b`–`PA1-D3e` in
`docs/superpowers/journals/2026-09-08-gy-phase5-completion.md`. Its final
“GY-PA1 conjunct closeout map” explicitly supersedes the absent-producer claim.
The intermediate `PA1-R01` temporal gap was real, then repaired; current route
and head-reader source independently confirm the repair exists at this base.

Focused executable controls, not claimed as run in this note:

```text
tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py::test_separate_signed_authorization_produces_persists_resolves_and_projects
tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py::test_invalid_authority_keeps_frontier_and_persists_typed_request
tests/unit/runtime/http/test_normative_evidence_intake.py::test_post_source_signature_advances_both_current_job_readers
```

Those controls test the selection-permission mechanism with explicit fixture
signers. The actual deployment's trusted keys, live PostgreSQL competing-head
execution, alternate CAS backend and empirical/promotion authority are not
established by them. They do not need a new producer build in this lane.

## PC-R4: the positive GY-J semantic is not an unwritten Runtime appointment

The owner is visible at the refusal plane:
`WorkspaceLoop.run_production_case` in
`src/polisyos/runtime/quality/workspace/loop.py` persists obligations with
`resolution_options` naming `team-runtime-quality` for
`original_construct_evidence_admission_owner_missing` and
`source-custody-or-appointed-adjudicator` for
`original_construct_and_scope_evidence_binding`. The `GradedOutcomeEvidenceInput`
also names `team-runtime-quality`. `.github/CODEOWNERS` at repository root and
`docs/reference/ownership.md` assign reviewers and fallback escalation to Runtime
paths. Therefore “nobody attached” is too broad if read as maintenance or refusal
routing ownership.

The missing scientific plane is equally explicit in current source:

- `ProductionCaseAdmission` constrains `positive_admission_state` to
  `original_construct_evidence_admission_owner_missing`, substantive support to
  `not_established`, and custody to catalog-attempt/graded-refusal recomputation.
- `_production_source_attempts` resolves original requested bindings through the
  actual catalog, data-requirement and connector admission owners. These outputs
  deliberately leave `scientific_original_construct_support=not_established`.
- `_compose_production_case_admission` passes each original construct to the real
  `compose_graded_outcome` with `unsupported`, `non_overridable`, no decision
  owner and no source-evidence refs, then requires the actual typed blocker.
- `resolve_production_case_admission` re-reads CAS bytes/manifests and recomputes
  that exact request/source/S1 result. A public metadata field or caller-supplied
  verifier cannot introduce a positive scientific relation.
- The real non-test caller is
  `WorkspaceLoopTransitionMixin._run_workspace_production_case` in
  `src/polisyos/runtime/http/services/control/workspace_loop_transition.py`;
  it invokes `WorkspaceLoop.run_production_case` with the production catalog and
  runtime CAS. The durable control worker and job response are the runtime
  terminus. The canonical measurement terminus is
  `tools/quality/validation/check_layer3_gy_loop_artifacts.py`; its
  `_classify_production_observation` additionally rejects a positive terminal
  until this missing owner is supplied. Positive source semantics must therefore
  be consumed both in runtime and in that canonical population instrument.

The pointed historical evidence was opened:
`docs/superpowers/journals/2026-09-08-gy-eight-gaps-completion.md` (`GY-J` final
finding), and its `gy-eight-gaps-evidence/j/partial-scope-owner.json`. The latter's
bounded finding is that available macro credit/GDP context does not identify
individual MSME outcomes or establish an original MSME construct binding. It
explicitly disclaims absence of relevant data from every corpus. That bounded
scientific mismatch is not a claim of global data absence and is not repaired
by naming Runtime as author of a positive.

The smallest unresolved link is a scientifically specified, independently
verified source-to-original-construct/scope admission: what evidence admits
which original construct, from which source, with what verifier/acceptance rule
and authority limit. The architect must either assign that semantic/producer
with its acceptance basis or rule the requested claims outside the available
scope and amend the task's success condition. The existing catalog/source/S1/CAS/
worker/refusal chain is reusable and should not be duplicated. No positive
contract or scientific threshold is inferred here from the existing blanket
refusal; doing so would turn an unresolved research question into authority.

**Buildable-plumbing adjudication:** the existing `ProductionCaseIntake` is the
persisted original request; `ProductionCaseAdmission` is the typed-empty
scientific slot plus source-attempt custody; its CAS producer, manifest/content
resolver, actual S1 consumer, durable worker and terminal obligations are already
connected. Its `positive_admission_state` literal and `substantive_source_support`
literal prevent any caller from filling that slot with self-attestation. Adding
another owner-`None` DTO or another persisted refusal request would close no
missing link and would duplicate this apparatus. No *independent* new plumbing
is established as necessary before the scientific decision. Once an accepted
source-to-construct artifact and verifier are specified, the smallest extension
is its intake at `_compose_production_case_admission`, content/provenance replay
at `resolve_production_case_admission`, and consumption by the existing S1 and
canonical observation classifier. That positive semantic link is the exact
decision-dependent boundary; none of the surrounding refusal engineering is
being handed back unbuilt.

## PC-R1-UPSTREAM: current first-candidate evidence and acceptance boundaries

`GenerationCycleController.__init__` in
`src/polisyos/runtime/quality/generation_cycle.py` supplies
`context_provider=self._promotion_source_context` to the real canonical N9 port.
`src/polisyos/runtime/quality/generation_source.py` retains actual N4 source and
replays the typed EFFECT writer projection. The existing
`_bind_production_promotion_evidence` in `promotion_sequence.py` invokes real
independence, measurement and EFFECT writers from supplied owner inputs. This
refutes using the historical “zero context-provider production caller” statement
as a current blocker.

`src/polisyos/runtime/quality/production_grounding_calibration.py` is the current
source-discovery/refusal owner. Its `RelationAcceptanceSlot` is explicitly empty
for `cg1_proposal_reference_relation`: relation gold context, accepted relation
adjudicator and outcome-sensitive calibration rule are `None`; its source result
cannot grant N8 eligibility. `ProductionCG2CalibrationSource.produce/replay`
persists and recomputes exact request/source evidence through the existing CG2
owner. `SourceIdentityBundle` in
`src/polisyos/data_forge/domains/academic/knowledge/skg_identity_bridge.py` owns
source-reference identity only and explicitly leaves numeric semantics, causal
identification, world binding, transport and calibration unestablished. Those
owners already provide typed-empty engineering mechanisms. An empty source DTO does
not establish that the governing scientific rule is undecided. Their missing positive
admission cannot be replaced with publication eligibility or a signer; the precise
current rule and remaining inputs are corrected in PC-R1-CORRECTION below.

## Input and interpretation limits

This note's deciding inputs are the named register/task rows, the named source
definitions and complete enclosing functions, the named historical finding
sections, and the named test definitions. Search results were locators, not
proof of a repository-wide absence. No set-level count is derived here from a
search result. Current source paths were read from the attached worktree at the
pinned base. Relevant unread boundaries are:

- `unresolved_by_construction.external_scientific_appointment`: out-of-repository
  appointment and gold/adjudication agreements were not read.
- `unresolved_by_construction.unselected_authority_documents`: no claim that all
  possible differently named research decisions were semantically interpreted.
- `unresolved_by_construction.current_production_data`: historical data receipts
  were read, but their databases and remote providers were not replayed here.
- `unresolved_by_construction.runtime_execution`: tests named above are selected
  falsifiers, not fresh execution receipts until the coordinator runs them.

Route the stale PA1/GAP7 typing and GY-J overly broad owner wording to their exact
existing register rows for architect transcription, without writing either
register or ledger. Route source-to-construct acceptance to
`gy-j-positive-evidence-admission-producer-has-no-owner`; route relation gold and
outcome-sensitive calibration application to `cg2-production-relation-gold-acceptance-unspecified`.
The HC-F11–HC-F14 re-extraction boundary instead routes to `claim-level-evidence-axis`
in `docs/reference/data-capability-requirements.md`. No new sovereign subsystem is proposed.


## PC-R1-CORRECTION: decisions must be read past their opening paragraphs

This correction supersedes any inference above that `RelationAcceptanceSlot`'s
`None` fields prove an undecided CG2 scientific standard. The original read stopped
at an implementation's empty slot and a historical report. That was P36 authority
by adjacency, and the exact deciding rows refute it.

`correspondence-acceptance-standing-rule` records the architect's decision and its
later application. The causal member's substantive purpose is
`CAUSAL_INSTANTIATION`; `CORR-R1` refutes interchangeability with
`LEGAL_GOVERNANCE_CORRESPONDENCE`. Its qualification contract (point vi,
`CORR-I1` ownable half) requires independence, competence for the named purpose,
wrong-making gold authority, declared scope with a staling handle, and no custody
substitution. `CORR-I2` is the causal appointment; a source signer does not become
that adjudicator. `W4-K01` still says signing establishes custody, never correctness.
The constructed-negative rule and custody-without-a-number outcome (`INT-K06`)
are already decided. Positive purpose-qualified appointment and scoped independent
labels remain absent in the measured source chain.

The linked CORR consolidation's `CORR-R2`/`CORR-R3` per-unit versus horizon question
is itself superseded by `delta-ground-composition-and-stratum-budget`. That row is
closed: CGF appendix E.3 specifies pre-admission risk spending and the union-bound
composition; CGF §E.4.1 records the adopted stratum and epoch-scope division, budget
allocation, and the dated frame/re-declaration/recollection rules. There is no
remaining architect decision on the estimand bridge to stop this lane on. The
current source artifact's empty `outcome_sensitive_calibration_rule` is an unfilled
application slot, not evidence that these decisions do not exist. The CG2 row's
latest defensive-suite correction also prevents claiming its complete engineering
verification is green from a historical selected test result; this note has not
freshly rerun that complete suite.

Exact authority inputs, read at `@28b8a1a42`: the named rows in
`docs/plans/active/DEBT-REGISTER.md`; `CORR-R1`, `CORR-R2`, `CORR-R3` in
`docs/research/policy-operations/corr-consolidation/corr-consolidation-report.md`;
and `docs/reference/policy-design-causal-grounding-firewall-CGF-spec.md` E.3/E.4.1.
The register is read as a versioned sequence of rulings, not only its first sentence.
No register edit is made here. Route misleading empty-slot prose to the existing CG2
row for the architect; no new rule is proposed.

## PC-R1-HC: current re-extraction is a callable campaign, not an appointment wait

The same standing-rule correction explicitly removes HC-F11–HC-F14 from the
correspondence member set. `knowledge/skg_versioning.py::require_forwardable_confidence`
continues to refuse the content-bound historical vintage. An adjudicator cannot
change that historical current-rule mismatch.

The current engineering chain exists in
`src/polisyos/data_forge/domains/academic/batch/reextraction_cli.py`:
`main` → `run_plan` → `reextraction_campaign.run_campaign`, with owner-bound
source frame, SDK transport, durable checkpoint and recovery. Its separate
`main` → `finalize_plan` → `pipeline.finalize_extraction_campaign_graph` path
consumes completed candidate records through `graph_builder.load_graph` and
`edge_synthesize.run_edge_synthesize`, persists the candidate graph packet, and
independently reads it via `resolve_extraction_campaign_graph`. The runnable
production terminus is
`python -m polisyos.data_forge.domains.academic.batch.reextraction_cli` with
`prepare`, `run`, `recover`, or `finalize`. This is not an uninvoked helper.

`docs/reference/data-capability-requirements.md`'s later acquisition-state section
names the outstanding campaign input: a dated operating declaration establishing
provider throughput/model choice before a full pass is authorized, plus the actual
completed data pass. It explicitly separates graph finalization's resource stage.
Those are operational selection/execution inputs to a built mechanism, not missing
scientific acceptance and not permission for this promotion lane to begin a paid
corpus campaign. No current production dataset or provider operating envelope was
read or executed here (`unresolved_by_construction.current_production_data`). Route
the data pass to the existing `claim-level-evidence-axis` requirement and its
campaign execution owner; retain its current data status rather than claiming a
fresh forwardable reference. All paths in this paragraph were read at `@28b8a1a42`.
