# GY-O0 Attempted-Evaluation Safety Gate Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` to execute this plan cluster by cluster. Use `superpowers:test-driven-development` for every behavior change and `superpowers:verification-before-completion` before each handoff.

**Goal:** Build the independent, fail-closed `EvalSafety` gate that every non-simulation evaluation attempt must pass before any evaluation computation or external handoff can begin.

**Architecture:** Consolidate the existing six-mode vocabulary into one strict runtime owner; add a content-addressed, domain-pack-driven safety requirement and certificate chain; persist decisions through the existing runtime authority/event infrastructure; project only an informational audit artifact through existing run/artifact surfaces; and strangle the two live non-N8 evaluator chokepoints. Promotion evidence is never an input to the safety-pass predicate. It may be verified only after a block to classify a near miss.

**Tech stack:** Python 3.14, strict Pydantic v2 DTOs, existing `ArtifactStore`/CAS and runtime diagnostic-event owners, FastAPI's existing artifact/run surfaces, pytest, Ruff, and repository architecture guardrails.

> **Execution standing: executable; C00 is a census and structural-witness
> cluster, not a blanket stop.** The current canonical N9 producer cannot emit
> a production-lane `consumer_promotable=True` receipt. That leaves the named
> empirical cross-gate non-closure `GY-O0-NC-01`; it does not block C01-C05 or
> O0 closure. No constructed, contract-testing, forged, or verification-only
> receipt may be represented as an admitted N9 receipt. Promotion independence
> is instead proved for every input by the pure safety-core signature and the
> per-cluster injection falsifiers below.

**Binding specifications:**

- `docs/plans/active/layer3-slices/GY-engine-subordination.md:927-958` (`U1`-`U4`)
- `docs/plans/active/layer3-slices/GY-engine-subordination.md:5034-5049` (`GY-O0`)
- `docs/reference/policy-design-search-RACE-HOG-PODS-v3.2-spec.md:410-420` and `:993-1008`
- `docs/system-design-decisions/policyos-identity-and-custody-boundary.md:72-123`
- `docs/system-design-decisions/stage0-custody-kernel-ratification.md:42-110`
- `docs/system-design-decisions/int-wave-claim-semantics-ratification.md:190-208`
  (ratified finding `INT-K06`)
- `docs/reference/policy-design-case-failure-patterns.md`

---

## 1. Plan standing and non-negotiable outcome

Planning was performed in the dedicated attached worktree
`/Users/deniskopylov/polisyos/.worktrees/gy-o0-attempted-evaluation-safety-plan`
on `refs/heads/codex/gy-o0-attempted-evaluation-safety-plan`, based on local
`main` at `2525da7306d329ae28fa394690e1c39133eb0d55`. The Phase-5 closure commit
`c6fbfa388` is an ancestor of that base. This planning task writes only this
file; it does not change source, a register, a generated artifact, the
deep-import baseline, or a timing budget.

Execution starts from local `main` at
`f3e3d996bd6710e26f24fd913d4fe0547f1d1a0d` on the attached branch
`codex/gy-o0-attempted-evaluation-safety-execution`. The plan commit
`39d8f0293d24d55f9be66b506d227d9270e7eddf` was brought forward by the
append-only merge `2eca093151adedffb7dd937d61095bfcb2eec0bb`; no rebase was
used. Execution re-derives C00 on that new base rather than treating planning
receipts as current repository evidence.

Two independent parsers over the complete task table in
`docs/plans/active/layer3-slices/GY-engine-subordination.md` agree on the live
ladder denominator: **37 tasks = 25 `executed` + 1 `not_executable` + 11
`not_started`; 0 Phase-5 rows remain open and 0 rows are `in_flight`.** A first,
narrow regex assumed every status cell was code-formatted and returned 36; it
missed the bold-only `GY-PA1` `not_executable` cell. That disagreement is not
discarded: it is the reason the admitted derivations use a generic five-cell
regex and an independent cell split, which return identical 37-row sets.

Pre-implementation O0 capability standing is **`contract_only`,
`producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`,
`verification_missing`, `surface_missing`, and `semantic_test_missing`**. It is
not `absent/unallocated`: `FoundryValuePort`, the six-mode contract, the
fail-closed O0 placeholder, N8, and the two evaluator chokepoints are named
candidate owners. What is absent is the admitted EvalSafety chain: no
requirement-pack producer, persisted attempt decision, mode-matched
certificate, execution bridge, success-path consumer, honest counter
projection, inspectable audit artifact, or negative end-to-end semantic test.

Planning found a separate inherited premise failure behind the decisive
near-miss test. Owner code at `promotion_sequence.py:3328-3348` always emits
`scope_insufficient` for the GY-K `EFFECT` obligation, while
`:3436-3446` always emits `scope_insufficient` for `MEASUREMENT`;
`_compile_obligations` at `:2973-3010` includes both, and `_refusal_reasons` at
`:3715-3734` makes those production-scope outcomes non-promotable. The
independent owner test at
`tests/unit/runtime/quality/test_promotion_sequence.py:124-129` pins both
outcomes. Thus the current canonical N9 producer cannot emit a production-lane
`consumer_promotable=True` receipt.

That does not reopen the ladder count: Phase 5 is closed as a task-table fact.
It does mean N9's positive production capability is incomplete. For its effect
dependency the exact state is `contract_only`, `producer_missing`,
`artifact_missing`, `bridge_missing`, `consumer_missing`,
`verification_missing`, and `semantic_test_missing`. The measurement-root
chain exists upstream but is `implemented_but_not_orchestrated` relative to
N8/N9 and `bridge_missing`. The authority-grade N8 measurement-obligation
chain's first failures are **`producer_missing + bridge_missing` with a named
candidate owner**; its complete typed standing is `producer_missing`,
`artifact_missing`, `bridge_missing`, `consumer_missing`,
`verification_missing`, and `semantic_test_missing`, not
`absent/unallocated`. The canonical candidate `owner_ref` values are `GY-K
entailment witness owner` and `measurement-rooted producer owner`; their
refusal details state exactly **"GY-K entailment witness owner is unwired"** at
`promotion_sequence.py:3345` and **"Measurement-rooted producer owner is
unwired"** at `:3443`. Completing either chain is not attempted-evaluation
safety, cannot be priced from O0's measured path set, and is not silently
absorbed here. C00 preserves this evidence and C01-C05 proceed without claiming
that either positive production capability exists.

**Standing unwired/unowned check:** before assigning any incomplete-capability
label, resolve candidate owners in contract, producer, refusal, and consumer
code. `absent/unallocated` is admissible only when that complete walk finds no
owner and no candidate. An existing root or code-named candidate routes the row
to its first missing chain link, such as `producer_missing` or
`bridge_missing`; "unwired" never means "unowned".

The outcome is load-bearing:

1. `simulate_only` may run only when explicitly declared; it never obtains an
   `EvalSafety` certificate.
2. Every other canonical mode must resolve a mode-specific domain-pack profile
   and a passing, current, content-bound `EvalSafety` certificate before the
   relevant evaluator owner runs.
3. Missing/unknown mode, unresolved unknown-domain pack/facet basis, missing
   profile, missing appointment,
   stale evidence, wrong binding, or unverified evidence blocks with a typed
   reason. No fallback may convert any of them to simulation.
4. A valid promotion artifact cannot satisfy, weaken, or bypass `EvalSafety`.
5. The gate has no executor callback and acquires no ability to pilot or deploy.
6. Every EvalSafety intake decision is persisted. Counters are recomputed from
   the complete, reconciled event denominator rather than incremented from
   requests.

Two independent dependency derivations constrain the width of the N9 gap:

| Derivation over the six outcomes | Receipt-dependent | Promotion-related but structurally dischargeable | No promotion relation |
| --- | ---: | ---: | ---: |
| Outcome-text inventory | 0 | item 4 only (1) | items 1, 2, 3, 5, 6 (5) |
| Target dataflow/signature inventory | 0 | item 4 only (1) | items 1, 2, 3, 5, 6 (5) |

There is no disagreement: **zero of six outcomes requires a live positive N9
receipt**. Item 4 is the only outcome that mentions promotion, and it is a
negative separation property. `INT-K06` ratifies a binding, falsifiable claim
about procedure without a probabilistic or production-readiness claim; here
that procedure claim is stronger than one empirical pair because it forbids a
promotion-to-safety data path for every input. Items 1, 2, 3, 5, and 6 are
independent of N9 altogether.

`GY-O0-NC-01 — empirical cross-gate disagreement on a real promoted design` is
retained as a named non-closure. Its two candidate owners are the exact
code-named owners above. When they are wired, a real promoted design can add an
observed promotion-safe/pilot-unsafe example; until then no fabricated receipt
substitutes for it. **O0 closure does not wait on `GY-O0-NC-01`.**

---

## 2. Identity and custody boundary

Classify one plane at a time. These rulings apply the ratified `S0-K03` plane
decomposition and the `S0-K06` authority-band fail-closed rule.

| Plane | Ruling | O0 behavior |
| --- | --- | --- |
| Safety requirement grammar, evidence admission, attempt-safety decision, certificate, staleness, and revocation semantics | **OWN** | PolicyOS signs only the bounded claim that the named attempt satisfied the pinned safety basis at the stated time. |
| Ethical/legal approval, privacy/access authorization, containment verification, stop-rule readiness, rollback readiness, population-protection evidence | **INTEGRATE** | Receive typed evidence; resolve, content-bind, verify provenance and currentness; never perform or self-attest the institutional function. |
| Promotion receipt | **INTEGRATE for near-miss classification only** | Resolve after the safety decision; it cannot enter the safety-pass predicate. |
| Pilot/deployment execution, implementation status, appeal outcome, realized effects | **out_of_scope execution; INTEGRATE evidence on return** | The gate emits no command, callback, job, notification, payment, rollout, or case-management act. |
| Observation and later learning | **OWN-core in O1/O3, not O0** | O0 may bind the intended observation contract but does not attribute an effect or update the world model. |

An absent institutional verifier or approver is a declared absence and a typed
blocker, not an O0 defect and not an invitation to appoint one in code.

---

## 3. Binding research input: explicit non-blocker for O0

`INT-R4` (`DeploymentLearningSafetyCase`) is undelivered. Two independent
complete walks agree:

- Git-tree walk: **253 tracked files** under `docs/research`, zero filenames
  containing `int-r4` or `deployment-learning-safety`, and the sole file
  containing the exact artifact name is
  `docs/research/policy-operations-and-real-world-runtime-backlog.md`.
- Filesystem walk: **253 files across all file types**, the same zero report-name
  hits, and the same backlog-only artifact-name hit.

The backlog binds `INT-R4` with `OPS-R5` to O1/O3 at lines 206, 238, 266, 489,
527, and 676-680. Therefore:

> **`INT-R4` gates O1/O3 and the O-block's closure; it does not gate GY-O0.**

O0 decides whether an attempt may begin. It neither diagnoses realized versus
predicted change nor writes a deployed-effect posterior/world branch. O0's
completion must never be reported as Phase 6 or the O-block closing.

---

## 4. Census: what exists before O0

### 4.1 Six-mode census

Two executable derivations agree exactly:

| Derivation | Complete source | Result |
| --- | --- | --- |
| Python AST of the `Literal` alias | `src/polisyos/runtime/quality/generation_cycle.py:150-157` | `simulate_only`, `retrospective`, `measurement_audit`, `sandbox_pilot`, `field_pilot`, `deployment` |
| Parsed frozen N8 denominator | `architecture/policy_design_case/layer3_gy_value_gate_contract.json:1130-1137` | the same ordered six members |

The vocabulary is already typed. O0 extends/consolidates it; it does not create
a parallel string list.

There are two source disagreements that must remain visible:

- The formal v3.2 prose uses `simulation_only`; executable N8 code and its
  frozen contract use `simulate_only`. O0 keeps the executable spelling and
  rejects `simulation_only` as `evaluation_mode_unknown` unless a later,
  separately versioned migration is approved. There is no silent alias.
- The formal attempted-safety section names profiles for `retrospective`,
  `sandbox_pilot`, `field_pilot`, and deployment, but omits a
  `measurement_audit` profile. N8 says both `retrospective` and
  `measurement_audit` require `DataTrust`. O0 does not invent a fifth
  engine-coded profile: a domain pack must declare it, or the attempt blocks as
  `eval_safety_mode_profile_missing`. `DataTrust` is necessary evidence where
  declared, never a substitute certificate.

Current production facts:

- `ValueGateReceipt.evaluation_mode` is typed at
  `generation_cycle.py:430-486`.
- `FoundryValuePort` defaults to `simulate_only` at `:1624-1648`.
- Pilot/deployment modes are unconditionally blocked by the placeholder at
  `:1665-1673`; retrospective/measurement audit only test `DataTrust` presence
  at `:1675-1682`.
- `_value_evaluation_mode` at `:4265-4268` silently maps unknown or absent input
  to `simulate_only`. Although it has no current caller, it is a latent P38
  bypass and must be removed or made strict.
- `promotion_sequence.py:3521-3540` records `EVAL_SAFETY` as
  `scope_insufficient`; it is neither a certificate nor a consumer.

### 4.2 Semantic executor and workflow census

Membership rule: an executor owner directly evaluates a policy/design
candidate or observational evidence into value-, world-, or promotion-relevant
output. The candidate owner set is grounded in the complete GY-N0 owner
investigation. A Git-tree `ls-files` derivation and an independent filesystem
`rglob` agree on identical membership for the complete denominator: **2,600
Python files under `src`**. One AST walk and one token-stream walk over that
complete set find the identical set of **4 owner methods**:

| Owner | Location | Standing |
| --- | --- | --- |
| `FoundryValuePort.__call__` | `src/polisyos/runtime/quality/generation_cycle.py:1651` | live attempt port, currently blocks before a real non-simulation owner call |
| `RunCausalEvaluationNode.execute` | `src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py:374` | live; loads observational data and invokes `run_job` before any mode/safety admission |
| `ProductionPolicyEvaluationBackend.evaluate` | `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:165` | live; computes evaluation/promotion input without explicit mode/safety admission |
| `SyntheticPolicyEvaluationBackend.evaluate` | `policy_runtime_support.py:244` | quality/validator-only; not a live production executor |

After the independently identical quality-only classification, **3 of the 4
are live/attempt-capable**.

Workflow membership rule: count a `NodeInvocation` whose `node_id` names the
causal evaluator, hierarchical Stage-B evaluator, or policy-blueprint runtime.
A Git-tree `ls-files` derivation and an independent filesystem `rglob` agree on
identical membership for the complete denominator: **11 Python files** under
`src/polisyos/scientist/orchestration/workflows`. A text walk and an AST walk
over that complete set agree on **6 registrations**: four causal-evaluation
registrations and one each for Stage-B and blueprint.
The two methods disagree only on line coordinates because text reports the
literal's line while AST reports the enclosing `NodeInvocation` start; member
files, node IDs, and counts agree.

The six registrations are in:

- `workflows/default.py:109`
- `workflows/causal_full.py:126`
- `workflows/policy_verified.py:149`
- `workflows/policy_design.py:109`, `:190`, and `:231`

The causal node is also reached by `WorkspaceLoop.run_intent` through
`runtime/quality/workspace/loop.py:1251` and `:1325-1421`. The Stage-B and
blueprint paths converge on `ProductionPolicyEvaluationBackend`, so the repair
belongs at two executor owners, not six workflow fixtures.

Two independent syntax walks over the causal node, backend, Stage-B caller,
blueprint caller, and workspace loop find **zero** occurrences of
`evaluation_mode`, `EvalSafety`/`eval_safety`, or `DataTrust`/`data_trust`.
Behavioral inspection proves the consequence rather than treating the zero as
the property:

- a merely loadable `observational_data_ref` reaches `run_job`;
- `fidelity == "full"` plus supplied component presence may mark backend output
  promotable.

Therefore O0 is **a lock on an open room**, not merely a replacement for N8's
placeholder.

### 4.3 Bounded census caveat

The two executor derivations are complete over the named GY-N0 owner predicate;
they cannot infer an owner omitted from that authoritative census. C05 repeats
a global symbol/caller scan and the behavioral sibling-bypass test. A newly
found owner is a widening-class finding, not silently folded into a count.

### 4.4 Domain-pack, facet, and appointment census

There is no existing EvalSafety pack/admission/verifier owner to wire as a
whole:

- `runtime/quality/cycle_substrate.py:1-5,101-151` owns a content-bound cycle
  intake and explicitly says it does not load a domain pack. Reuse its
  candidate/domain/WMR bindings only.
- `runtime/quality/semantic_epoch.py:415-531` already owns the data-extensible,
  hash-bound `SemanticFacetRegistry`, `SemanticFacetValue`, and complete
  `SemanticFacetDenominatorReceipt`. Reuse those as applicability evidence;
  do not invent `dict[str, object]` scope metadata.
- `core/components/discovery.py:219-258,406-486` supplies a content-bound
  `ComponentDiscoveryManifest`, and `ComponentId` is an open validated
  dotted+semver identity. Discovery proves implementation identity only.
  `Component.create() -> Any` and `DataForgeDomainPlugin.create() -> object`
  do not type a safety profile, appoint a verifier, or grant authority.
- Existing appointment resolvers are purpose-specific. None appoints an
  EvalSafety evidence verifier.

Therefore O0 **reuses** cycle bindings, semantic-facet denominators, component
identity discovery, and CAS. It **builds** strict mode-basis/domain-pack
admission plus a narrow appointed-verifier registry/resolver in the canonical
EvalSafety owner. An external pack or appointment remains integrate-evidence;
PolicyOS produces the typed admitted/refused receipt. Production absence is
`eval_safety_verifier_unresolved`, never a fixture fallback.

---

## 5. Reuse/build disposition by component

| Component | Existing owner | Disposition | Target state |
| --- | --- | --- | --- |
| Six-mode taxonomy | `generation_cycle.py:150-157`; frozen N8 contract | **consolidate/extend-existing** | One strict `evaluation_modes.py` owner; compatibility import only, no fallback parser. |
| N8 value receipt | `generation_cycle.py:430-486` | **wire-existing** | Binds the selected mode and resulting safety refs; never becomes the certificate. |
| N9 promotion classifier | private decision-front predicate in `generation_cycle.py:5475-5510`; canonical receipt/validator in `promotion_sequence.py` | **consolidate-existing** | Move/expose the canonical predicate on the promotion owner; invoke only after safety is frozen and only for near-miss classification. |
| N9 positive production premise | GY-K has a shadow-only contract and a named but unwired witness owner; measurement roots exist but their named producer owner does not reach an authority-grade N8/N9 obligation | **separate named non-closure; not O0 mechanism or closure prerequisite** | Route `GY-O0-NC-01` to the GY-K entailment-witness and measurement-rooted producer candidates. O0 proves separation structurally and does not absorb or wait on either owner. |
| Requirement algebra, intake/request, decision, certificate/revision, typed blockers | none | **build-new** | Strict, frozen Pydantic artifacts and verification-only port in `evaluation_safety.py`. |
| Domain-pack admission producer | no EvalSafety owner; discovery components return untyped objects | **build-new over reused discovery/CAS** | Admit/refuse strict pack, mode-basis, and appointment artifacts; raw domain hints never select a pass. |
| Applicability facets | `SemanticFacetRegistry` and `SemanticFacetDenominatorReceipt` | **wire-existing** | Exact hash-bound facet requirements; open namespaced facet IDs, no metadata bag or domain enum. |
| Verifier appointment/resolution | no generic EvalSafety appointment owner | **build-new integration port** | Component discovery proves identity only; verified appointment plus independent resolver is required, otherwise typed block. |
| Authority/provenance/time semantics | `runtime/quality/authority.py`; CAS manifests | **wire/extend-existing** | Purpose, producer/verifier, schema/rule version, valid/as-of times, population/candidate/world bindings. |
| Artifact persistence and durable event | `control/artifacts.py`, `event_log.py`, `control_plane_store.py`, `authority_reconciliation.py` | **wire-existing** | One authority artifact/event chain plus a distinct informational projection. |
| Authority reconciliation/counter denominator | `ArtifactStore.iter_artifact_ids`; `authority_reconciliation.py` currently post-filters a 1,000-event page | **extend-existing** | Exact manifest-linked event-ID reconciliation plus complete CAS decision census; page position is irrelevant. |
| N8 admission bridge | `FoundryValuePort` + recursive controller composition | **extend-existing** | Explicit execution context; non-simulation calls resolve a certificate before owner evaluation. |
| Legacy evaluator bridge | causal node and production backend | **extend/strangle-existing** | Two chokepoints cover the six registered workflows, workspace loop, and direct backend calls. |
| Scientist verifier DI | `ExecutionContext`/workflow builder/API facade have no EvalSafety port | **extend-existing** | Inject one verification-only port through the control-to-Scientist facade; absent port blocks non-simulation and cannot execute anything. |
| Audit/API surface | artifact manifest/content/lineage/schema routes, job progress, run paper | **wire-existing** | Publish a projection ref; do not add a route or governed/static projection family. |
| Actual pilot/deployment execution | external institution | **surface_out_of_scope** | Certificate only; no executor capability. Returned status/effects/appeals remain typed integrate-evidence for later tasks. |

Target capability state after C01-C05 is complete for attempted-evaluation
admission without an N9-positive prerequisite: typed artifact + producer +
persisted artifact/event + orchestration bridge + consumers + verification +
existing audit/API surface + negative/e2e semantic tests. Institutional
approvals may remain absent without making the mechanism incomplete; their
attempts block honestly. `GY-O0-NC-01` remains an explicitly non-closing
empirical demonstration, not a missing EvalSafety chain link.

---

## 6. Target contracts and semantics

All public models are strict (`extra="forbid"`) and frozen. Names below are
binding; implementation may split private helpers but may not weaken fields or
purpose bounds.

```python
EvaluationMode = Literal[
    "simulate_only",
    "retrospective",
    "measurement_audit",
    "sandbox_pilot",
    "field_pilot",
    "deployment",
]

NamespacedEvalSafetyId = Annotated[
    str,
    StringConstraints(pattern=NAMESPACE_AND_VERSION_PATTERN),
]

class EvalSafetyFacetValueRequirement(BaseModel):
    facet_id: NamespacedEvalSafetyId
    source_binding_ref: ArtifactRef
    expected_semantic_value_hash: Digest

class EvalSafetyAllApplicability(BaseModel):
    kind: Literal["all"] = "all"

class EvalSafetyFacetApplicability(BaseModel):
    kind: Literal["semantic_facet_all_of"] = "semantic_facet_all_of"
    semantic_facet_registry_ref: ArtifactRef
    semantic_facet_denominator_receipt_ref: ArtifactRef
    all_of: tuple[EvalSafetyFacetValueRequirement, ...]

EvalSafetyApplicabilityScope = Annotated[
    EvalSafetyAllApplicability | EvalSafetyFacetApplicability,
    Field(discriminator="kind"),
]

class EvalSafetyRequirement(BaseModel):
    requirement_id: NamespacedEvalSafetyId
    evidence_contract_id: NamespacedEvalSafetyId
    authority_purpose: Literal["attempted_evaluation_safety"]
    applicability_scope: EvalSafetyApplicabilityScope
    warning_expires_after: timedelta | None

class EvalSafetyModeProfile(BaseModel):
    mode: EvaluationMode
    all_of: tuple[EvalSafetyRequirement, ...]

class EvalSafetyModeBasis(BaseModel):
    schema_version: str
    rule_version: str
    profiles: tuple[EvalSafetyModeProfile, ...]
    producer_authority_ref: ArtifactRef
    verifier_receipt_ref: ArtifactRef
    valid_from: datetime
    valid_until: datetime | None
    content_hash: str

class EvalSafetyVerifierAppointment(BaseModel):
    appointment_id: NamespacedEvalSafetyId
    evidence_contract_id: NamespacedEvalSafetyId
    verifier_component_id: ComponentId
    component_discovery_manifest_ref: ArtifactRef  # identity, not authority
    appointing_authority_ref: ArtifactRef
    appointment_verification_receipt_ref: ArtifactRef
    valid_from: datetime
    valid_until: datetime | None

class DomainEvalSafetyPack(BaseModel):
    schema_version: str
    rule_version: str
    pack_component_id: ComponentId
    source_pack_ref: ArtifactRef
    mode_basis_ref: ArtifactRef
    semantic_facet_registry_ref: ArtifactRef
    semantic_facet_denominator_receipt_ref: ArtifactRef
    verifier_appointment_refs: tuple[ArtifactRef, ...]
    profiles: tuple[EvalSafetyModeProfile, ...]
    valid_from: datetime
    valid_until: datetime | None
    content_hash: str

class EvalSafetyPackAdmissionReceipt(BaseModel):
    pack_ref: ArtifactRef
    mode_basis_ref: ArtifactRef
    status: Literal["admitted", "refused"]
    blocker_codes: tuple[NamespacedEvalSafetyId, ...]
    resolved_appointment_refs: tuple[ArtifactRef, ...]
    admitted_at: datetime
    content_hash: str

class EvaluationModeResolution(BaseModel):
    status: Literal["accepted", "missing", "invalid"]
    canonical_mode: EvaluationMode | None
    blocker_code: NamespacedEvalSafetyId | None
    source_token_hash: Digest

class EvaluationAttemptIntake(BaseModel):
    # Audit-safe envelope retained even when canonical mode parsing fails.
    attempt_id: str
    candidate_ref: ArtifactRef
    world_model_record_ref: ArtifactRef
    requested_mode_token: str | None
    mode_resolution: EvaluationModeResolution
    domain_hint: str | None             # audit provenance; never pack selection
    domain_pack_ref: ArtifactRef | None
    target_population_scope_ref: ArtifactRef
    evaluation_input_refs: tuple[ArtifactRef, ...]
    evidence_refs: tuple[ArtifactRef, ...]
    requested_at: datetime
    intended_start_at: datetime
    requested_rule_version: str | None
    external_executor_identity_ref: ArtifactRef | None

class EvaluationAttemptRequest(BaseModel):
    intake_ref: ArtifactRef
    attempt_id: str
    candidate_ref: ArtifactRef
    world_model_record_ref: ArtifactRef
    evaluation_mode: EvaluationMode
    domain_pack_ref: ArtifactRef
    semantic_facet_denominator_receipt_ref: ArtifactRef
    target_population_scope_ref: ArtifactRef
    evidence_refs: tuple[ArtifactRef, ...]
    requested_at: datetime
    intended_start_at: datetime
    rule_version: str
    external_executor_identity_ref: ArtifactRef | None

class EvaluationExecutionContext(BaseModel):
    intake_ref: ArtifactRef
    evaluator_owner_id: ComponentId
    evaluation_input_refs: tuple[ArtifactRef, ...]
    eval_safety_certificate_ref: ArtifactRef | None

class EvalSafetyRequirementResult(BaseModel):
    requirement_id: NamespacedEvalSafetyId
    evidence_contract_id: NamespacedEvalSafetyId
    request_ref: ArtifactRef
    candidate_ref: ArtifactRef
    world_model_record_ref: ArtifactRef
    evaluation_mode: EvaluationMode
    target_population_scope_ref: ArtifactRef
    rule_version: str
    intended_start_at: datetime
    evidence_ref: ArtifactRef
    evidence_producer_component_id: ComponentId
    verifier_component_id: ComponentId
    verification_receipt_ref: ArtifactRef
    status: Literal["passed", "blocked"]
    blocker_codes: tuple[NamespacedEvalSafetyId, ...]
    predicate_provenance: tuple[PredicateProvenance, ...]
    evaluated_at: datetime
    valid_until: datetime | None
    content_hash: str

class EvaluationSafetyDecisionCore(BaseModel):
    intake_ref: ArtifactRef
    request_ref: ArtifactRef | None     # absent when canonical parsing failed
    requested_mode_token: str | None
    evaluation_mode: EvaluationMode | None
    attempt_class: Literal["simulation", "non_simulation", "not_established"]
    attempt_class_provenance: PredicateProvenance
    status: Literal["passed", "blocked"]
    blocker_codes: tuple[NamespacedEvalSafetyId, ...]
    requirement_results: tuple[EvalSafetyRequirementResult, ...]
    predicate_provenance: tuple[PredicateProvenance, ...]
    evaluated_at: datetime
    valid_until: datetime | None
    safety_semantic_hash: str

def decide_evaluation_safety_core(
    *,
    intake: EvaluationAttemptIntake,
    request: EvaluationAttemptRequest | None,
    admitted_pack: EvalSafetyPackAdmissionReceipt | None,
    mode_basis: EvalSafetyModeBasis | None,
    requirement_results: tuple[EvalSafetyRequirementResult, ...],
    evaluated_at: datetime,
) -> EvaluationSafetyDecisionCore: ...

class EvalSafetyNearMissClassificationOffer(BaseModel):
    promotion_receipt_ref: ArtifactRef
    canonical_promotion_input_ref: ArtifactRef
    design_problem_binding_ref: ArtifactRef
    value_receipt_ref: ArtifactRef
    candidate_ref: ArtifactRef
    world_model_record_ref: ArtifactRef
    promotion_rule_version: str
    open_world_resolver_basis_ref: ArtifactRef
    epoch_resolver_basis_ref: ArtifactRef
    offered_at: datetime
    content_hash: str

class EvaluationSafetyDecisionEvent(BaseModel):
    decision_id: str  # deterministic from safety core/basis/rule, never promotion
    safety: EvaluationSafetyDecisionCore
    classification_offer_ref: ArtifactRef | None
    promotion_validation_basis_ref: ArtifactRef | None
    promotion_safe_facet: bool | None   # computed after safety; never gates pass
    near_miss: bool
    content_hash: str

class EvalSafetyCertificate(BaseModel):
    decision_ref: ArtifactRef
    request_ref: ArtifactRef
    evaluation_mode: EvaluationMode
    candidate_ref: ArtifactRef
    world_model_record_ref: ArtifactRef
    domain_pack_ref: ArtifactRef
    target_population_scope_ref: ArtifactRef
    rule_version: str
    revision_lineage_id: str
    valid_from: datetime
    valid_until: datetime
    authoritative_for: Literal["attempted_evaluation_admission"]
    may_not_use_for: tuple[Literal[
        "promotion",
        "simulation_safety",
        "attempted_evaluation_occurred",
        "deployment_execution",
        "realized_effect",
        "implementation_status",
        "appeal_outcome",
    ], ...]
    content_hash: str

class EvalSafetyCertificateRevision(BaseModel):
    revision_id: str
    revision_lineage_id: str
    predecessor_ref: ArtifactRef | None
    action: Literal["issue", "supersede", "revoke"]
    certificate_ref: ArtifactRef
    verified_cause_ref: ArtifactRef
    effective_at: datetime
    predicate_provenance: PredicateProvenance
    content_hash: str

class EvalSafetyConsumerAdmissionReceipt(BaseModel):
    status: Literal["verified", "blocked"]
    intake_ref: ArtifactRef
    certificate_ref: ArtifactRef | None
    current_revision_head_ref: ArtifactRef | None
    blocker_codes: tuple[NamespacedEvalSafetyId, ...]
    verified_at: datetime

class EvalSafetyAppointmentResolution(BaseModel):
    status: Literal["verified", "blocked"]
    appointment_ref: ArtifactRef
    appointment: EvalSafetyVerifierAppointment | None
    blocker_codes: tuple[NamespacedEvalSafetyId, ...]
    predicate_provenance: tuple[PredicateProvenance, ...]
    verified_at: datetime

class EvalSafetyVerifierAppointmentResolver(Protocol):
    def resolve(
        self, appointment_ref: ArtifactRef
    ) -> EvalSafetyAppointmentResolution: ...

class EvidenceVerifier(Protocol):
    @property
    def component_id(self) -> ComponentId: ...

    def verify(
        self,
        *,
        requirement: EvalSafetyRequirement,
        request: EvaluationAttemptRequest,
        evidence_ref: ArtifactRef,
        appointment: EvalSafetyVerifierAppointment,
        evaluated_at: datetime,
    ) -> EvalSafetyRequirementResult: ...

class EvalSafetyVerifierRegistry(Protocol):
    def resolve(
        self, evidence_contract_id: NamespacedEvalSafetyId
    ) -> EvidenceVerifier | None: ...

class EvalSafetyVerifierPort(Protocol):
    def require_admission(
        self, context: EvaluationExecutionContext
    ) -> EvalSafetyConsumerAdmissionReceipt: ...

class EvalSafetySurfaceDisposition(BaseModel):
    surface: Literal["run", "artifact", "lineage", "dashboard"]
    purpose: Literal["runtime_closeout_authority", "dashboard_display"]
    status: Literal["allow"]
    authority_result: Literal["informational_projection_only"]
    consumed_boundary_id: str
    projection_scope: Literal["faithful_eval_safety_projection"]
    may_not_use_for: tuple[Literal[
        "attempted_evaluation_admission", "promotion", "evaluation_execution"
    ], ...]

class EvalSafetyAuthoritySurfacePacket(BaseModel):
    schema_version: Literal["policyos.runtime.eval_safety_surface_packet.v1"]
    boundary: AuthorityBoundary
    surfaces: dict[
        Literal["run", "artifact", "lineage", "dashboard"],
        EvalSafetySurfaceDisposition,
    ]

class EvalSafetyMetricsProjection(BaseModel):
    attempt_disposition: Literal["passed", "blocked"]
    denominator_decision_ids: tuple[str, ...]
    unsafe_attempt_blocked_count: int
    near_miss_count: int
    near_miss_classification_status: Literal[
        "complete", "partial", "not_established"
    ]
    unclassified_blocked_decision_ids: tuple[str, ...]
    reconciliation_status: Literal["complete", "not_established"]
    generated_at: datetime
    source_event_refs: tuple[ArtifactRef, ...]
    authority_boundary: AuthorityBoundary
    authority_surface_packet: EvalSafetyAuthoritySurfacePacket
```

`EvalSafetyRequirementResult` binds the requirement ID, request/candidate/world/mode/
population/rule/time basis, evidence artifact, producer, independent verifier,
verification receipt, and outcome. Free text may explain a blocker but cannot
select pass.

Mnemonic blocker suffixes such as `eval_safety_verifier_unresolved` below are
readability shorthands. Persisted blocker IDs use the same namespaced,
versioned syntax as `NamespacedEvalSafetyId`; a bare suffix is not admitted on
the wire.

Factories/model validators recompute namespace syntax, mode resolution,
content hashes, unique/non-empty profiles, immutable basis extension, semantic
facet denominator membership, appointment independence, the exact declared
surface map, per-entry surface/key/purpose match, the boundary's exact current
egress purposes (`runtime_closeout_authority` for run/artifact/lineage and
`dashboard_display` for dashboard), its projection-only exclusion set, and
status/blocker coherence.
`EvalSafetyAllApplicability(kind="all")` is admitted only on the
independently verified universal `EvalSafetyModeBasis`; every requirement in a
`DomainEvalSafetyPack` must instead carry a non-empty
`semantic_facet_all_of` scope. A governance pack therefore cannot declare
itself universally applicable. A raw `domain_hint`,
`ComponentMetadata.domains`, or a bound
component-discovery manifest cannot select or pass a pack. The pure pack
admission producer emits `EvalSafetyPackAdmissionReceipt`; the control adapter
persists it. Production resolver/registry absence is an established typed
refusal, while independently verified test appointments exercise the generic
positive path without appointing an institution in O0.

`EvaluationAttemptIntake` is an audit envelope, never positive authority. It is
persisted before canonical parsing so a missing or unknown mode still produces
a typed blocked decision. The owner recomputes `attempt_class` from the bound
evaluator and input provenance; caller declaration cannot make real-world or
unestablished inputs simulation. `not_established` always blocks and is not
silently included in a counter whose predicate is specifically non-simulation.
`EvaluationExecutionContext` carries references only: each chokepoint compares
its own fixed owner identity and resolved input refs. It has no callable,
command, transport, or execution status field.

Promotion is absent from `EvaluationAttemptIntake`,
`EvaluationAttemptRequest`, every `EvalSafetyRequirementResult`, and
`EvaluationSafetyDecisionCore`. The core's `safety_semantic_hash` is recomputed
only from those safety fields. The pure function signature is itself a
load-bearing structural constraint: it has no promotion receipt, promotion
status, classification offer, or generic metadata/kwargs input through which
promotion state can enter. A separate
`EvalSafetyNearMissClassificationOffer` arrives after the core is frozen and
binds the canonical N9 replay input, design problem, value receipt, candidate,
WMR, promotion rule, and current open-world/epoch resolver bases. The final
event may record that offer and classification, but neither its receipt nor its
full-event hash can alter the core, its identity, or its semantic hash.

The injection falsifier invokes the enclosing composition with three promotion
states while holding every safety input fixed: omitted; maximally favorable;
and a forged passing certificate/receipt. All three must produce the same
pilot safety status, blockers, certificate eligibility, evaluator-spy count,
`EvaluationSafetyDecisionCore` bytes, `decision_id`, and
`safety_semantic_hash`. The forged state must additionally fail canonical
resolve-bind-verify and yield no admitted promotion facet. A future real N9
receipt may change only the containing event's post-core classification fields.
No positive promotion artifact is needed to falsify this universal separation.

The concrete `EvalSafetyVerifierPort` is container-owned. Its interface can
only resolve and require admission; it cannot run, schedule, callback, or
transport an evaluation. It recomputes the complete certificate-revision graph
from CAS, rejects absent/forked/cyclic/revoked heads, reconciles authority
events, and re-runs current appointed evidence verifiers immediately before
work. A post-issuance evidence invalidation is therefore a typed block even
while certificate bytes and markers remain unchanged.

### 6.1 Generic requirement composition

- `simulate_only` is explicit and certificate-free.
- Every other mode requires exactly one resolved pack profile. Duplicate
  profiles, empty profiles, missing profiles, or a profile for another mode
  block.
- A profile is generic `all_of`. O0 adds no special case for containment,
  approvals, privacy, rollback, or any domain.
- Every requirement must resolve one current evidence artifact satisfying its
  declared evidence contract and all attempt bindings.
- `warning`, `partial`, `contested`, `review_required`, expired, or unknown
  evidence is non-passing. Warning/review deadlines are explicit; aging changes
  the typed blocker, never silently upgrades it.
- An unrecognized evidence contract or absent verifier is
  `eval_safety_verifier_unresolved`, not a permissive plugin hook.
- A rule-versioned, content-addressed mode-basis artifact supplies the minimum
  profile below; a domain pack can refine or extend it but cannot delete a
  minimum. The engine performs one generic profile lookup and `all_of` union —
  it contains no mode-specific requirement branch.

| Mode key in mode-basis/domain-pack data | Minimum semantic obligation families |
| --- | --- |
| `retrospective` | data trust; privacy and access; measurement validity |
| `sandbox_pilot` | containment; stop rules; harm bound |
| `field_pilot` | ethical/legal approval; monitoring readiness; rollback readiness; population protections |
| `deployment` | full deployment safety; governance; accountability |
| `measurement_audit` | no ratified O0 minimum is present in v3.2; a non-empty domain-pack profile is mandatory, while N8's independent DataTrust check still applies |
| `simulate_only` | no EvalSafety certificate; recomputed simulation-only provenance is still mandatory |

The obligation-family labels are semantics references in data, not a closed
Python enum or governance-fixture switch. Namespaced requirement IDs and
evidence-contract IDs remain domain-pack-extensible. Missing basis, attempted
minimum deletion, or a profile that resolves only for another fixture blocks
as `eval_safety_profile_basis_invalid`/`eval_safety_mode_profile_missing`.

### 6.2 Admission algorithm

The single owner executes this order:

1. Persist and resolve the strict intake envelope; recompute the attempted
   action class from bound evaluator/input provenance.
2. Strictly parse the canonical request and mode; never normalize an unknown
   value. Parse failure emits a blocked decision against the intake, not an
   exception-only or invisible refusal.
3. Resolve and verify the request, candidate, WMR, population scope, domain
   pack, semantic-facet denominator, mode-basis artifact, and every evidence
   artifact from CAS.
4. Recompute pack/facet/mode applicability, immutable basis composition, and
   currentness.
5. Resolve every requirement using its typed evidence contract; verify content
   binding, producer/verifier provenance, independence, rule/schema version,
   authority purpose, and time window.
6. Compose `all_of` and freeze the pure safety status/blockers in memory.
   Recompute `safety_semantic_hash`; no decision is persisted yet, and promotion
   is absent from this computation.
7. Only when that frozen status is blocked and a separate classification offer
   was supplied, resolve the offer and any available real N9 receipt from CAS.
   Require exact
   receipt/replay-input/design-problem/value-receipt/candidate/WMR/rule and
   current open-world/epoch-resolver bindings before invoking the canonical
   decision-front predicate. Invalid, stale, or unavailable classification
   input yields `None`; it never adds a safety blocker or changes the core.
8. Compute `near_miss = (safety.status == "blocked" and
   promotion_safe_facet is True)`, construct one immutable event containing the
   already-frozen core plus the classification refs/facet, and persist it once.
9. Issue a certificate and its `issue` revision only for a non-simulation
   persisted `passed` decision.
10. Recompute counters from the complete reconciled decision-event denominator
   and persist the informational projection.
11. Return artifact refs. There is no executor argument, callback, command, or
   side effect beyond custody artifacts/events/projection.

`promotion_safe_facet=True` means the existing N9 validator returns no issues
and the receipt is `promoted`, `consumer_promotable`, on the `production` lane,
with no non-promotable reason. The helper currently lives privately at
`generation_cycle.py:5475-5510`; C01 moves/exposes it on its canonical
`promotion_sequence.py` owner and makes generation-cycle delegate. The pilot
attempt's mode need not equal the N9 receipt's earlier data/simulation mode:
the classification offer and resolved replay input must bind the exact design
problem, value receipt, candidate, WMR, promotion rule, and current
open-world/epoch bases, while pilot safety is judged independently. Requiring
pilot mode on both would make the classifier circular because N9 currently
marks pilot EvalSafety `scope_insufficient`.

The production classification path accepts a positive N9 receipt only through
the real canonical producer and validator. On the current base that producer
gap is `GY-O0-NC-01`, whose first missing links are `producer_missing` and
`bridge_missing`; it is not generically relabelled `verification_missing` and
does not stop implementation. A constructed dictionary, contract-testing
receipt, forged passing certificate, or verification-only receipt cannot mint
`promotion_safe_facet=True`. The structural injection falsifier closes O0's
independence property now; a future real receipt adds the separately named
empirical cross-gate observation.

The injected verifier port resolves the certificate again immediately before
evaluator work and checks exact owner/input refs, mode, candidate, WMR,
population, pack/basis/rule, complete current revision head, current appointed
evidence, and decision status. A certificate is neither a bearer token for
another attempt nor proof that its pinned evidence remains current.

### 6.3 Honest counter definitions

Let `D` be the set of unique, reconciled decision IDs selected by exact
EvalSafety artifact kind/schema from `ArtifactStore.iter_artifact_ids`.

```text
unsafe_attempt_blocked_count =
  |{d in D : d.safety.attempt_class == non_simulation
             and d.safety.status == blocked}|

near_miss_count =
  |{d in D : d.safety.status == blocked
             and d.promotion_safe_facet == true
             and d.near_miss == true}|
```

`near_miss_count` is a count of independently reconciled positive
classifications, never an assertion that every blocked design was classified.
The projection therefore carries `near_miss_classification_status` and the
exact `unclassified_blocked_decision_ids`. With no real positive N9 receipt,
`near_miss_count = 0` can be honest only alongside `partial` or
`not_established` classification status when such blocked decisions exist.
`unsafe_attempt_blocked_count` remains complete because its predicate depends
only on the reconciled safety core. A pure reducer test may exercise a
pre-classified decision event to prove the arithmetic; that contract-testing
event is not an admitted promotion receipt and cannot discharge
`GY-O0-NC-01`.

The existing `reconcile_authority_ref` cannot establish `D`: it asks for the
first 1,000 run/job events and filters afterward. C02 repairs that owner-level
property without widening two already-sufficient owners: authority
reconciliation resolves the manifest-linked diagnostic-event CAS artifact,
extracts its `event_id`, and calls the existing event-log `event_id` filter
with `limit=2`. The backing store applies that exact predicate before `LIMIT`.
It verifies the linked CAS artifact's integrity and expected event kind/schema,
requires cardinality one, requires `record.event == linked_event` over the full
canonical diagnostic-event model, and requires the record-column
`payload_ref` to equal both event payload refs and the authority artifact ref.
Zero/multiple rows or any changed producer, event type, phase, trace/span,
execution profile, event time, blocking status, identity field, or payload
binding fail. The red places more than 1,000 unrelated same-run events before
the target, separately injects a duplicate event identity, and substitutes a
same-ID event with one non-subset field changed. Page position and subset
agreement then cannot change the answer.

Duplicate retries with the same deterministic decision ID count once. Two
different payloads claiming the same attempt/decision identity make projection
reconciliation `not_established`; they are never arbitrarily deduplicated.
Page-capped `list_diagnostic_events` and in-memory metric increments are
forbidden denominators.

### 6.4 Projection versus authority

Persist two distinct surfaces:

- the decision/certificate authority artifact, purpose-bound to attempted
  evaluation admission and consumed only through resolve-bind-verify;
- an informational projection artifact containing typed reasons, refs, and
  recomputed counters, explicitly excluded from admission, promotion, or
  execution. It carries a deterministic `AuthorityBoundary` and typed allowed
  surface packet. The boundary authorizes exactly the existing egress-purpose
  tokens `runtime_closeout_authority` and `dashboard_display`; each disposition
  narrows that transport permission to `faithful_eval_safety_projection`, and
  the boundary/packet exclude admission, promotion, and execution. The
  attempt's passed/blocked disposition remains separate and never turns
  surface visibility into safety authority.

Two independent current-owner derivations agree on those purpose tokens:
`runtime/quality/authority.py:1746-1751` maps the named surfaces to their
default purposes, while the artifact/run consumers at
`routes/artifacts.py:769`, `services/artifact_inspector.py:579`, and
`services/control/response_shapes.py:394` invoke that same fail-closed egress
decision. The implementation test exercises both the function and the route;
the plan does not infer visibility from packet shape.

Reuse `write_runtime_authority_artifact`, `RuntimeDiagnosticEventLog`,
`ControlPlaneStore.append_diagnostic_event`, and `reconcile_authority_ref`.
Place the projection ref and disposition in existing control-job progress and,
when terminal, the run manifest so existing artifact inspector and run-paper
surfaces can display it. Do not change `routes/artifacts.py`,
`governed_projections.py`, a dashboard, Atlas, or any generated surface.

---

## 7. Universality design and falsifier

The gate consumes a strict, content-addressed `DomainEvalSafetyPack`. Requirement
IDs and evidence-contract IDs are namespaced typed identifiers, not a closed
domain enum. Pack identity is an open validated `ComponentId`; applicability
comes from a complete `SemanticFacetDenominatorReceipt`, never raw
`domain_hint`. A pack can add a new requirement/facet without changing engine
code; it cannot grant itself authority, appoint its own verifier, or satisfy a
requirement by declaring it satisfied.

The binding unseen-domain falsifier creates a temporary domain pack whose
component ID, semantic facet ID/value hash, and requirement ID have never
appeared in engine source, for example
`transit_lab.platform_crowding_guard@1.0.0`. It runs two branches with the same
engine bytes:

1. With a content-bound pack, a registered independent verifier, and evidence
   bound to the request/candidate/WMR/mode/population/rule/time, the generic
   resolver passes and issues a mode-matched certificate.
2. Remove the pack, corrupt its content hash/facet denominator, remove its
   verifier appointment, or use the governance fixture's pack against the new
   facet values: the request blocks with the corresponding typed reason.

The same property test generates further unseen domain and requirement IDs and
changes only pack/verifier/evidence data; outcomes must track those data, not a
known name. A changed source digest while loading a pack is an immediate
failure, but digest equality alone is not the proof. A post-change AST/diff
census must also reject every comparison or `match` arm against a literal
domain/requirement ID, and code review must confirm that mode minima are loaded
from the content-addressed basis artifact. **Zero engine conditional is added**
for the unseen domain: no `if domain == ...`, requirement-name switch, or
fixture-specific mode branch is permitted. This is the U3/U4 acceptance
signal:

> A gate calibrated only for the governance fixture refuses an unseen domain;
> it never improvises.

---

## 8. Predicate provenance and P38 declarations

### 8.1 Load-bearing predicate provenance

| Predicate | Admission classification | Rule |
| --- | --- | --- |
| Attempt is simulation versus non-simulation | `recomputed` or `not_established` | derive from bound evaluator/input provenance; caller label cannot grant; unknown blocks |
| Mode token belongs to the canonical six-member vocabulary | `recomputed` | strict parser; unknown blocks and still emits an intake-bound decision |
| Request/candidate/WMR/population/pack/evidence bytes match refs | `recomputed` | CAS resolve + integrity/content hash |
| Pack applies to this attempt and mode | `recomputed` | resolve the complete semantic-facet denominator, exact value hashes, pack admission, and mode profile; raw domain hint is ignored for pass |
| Pack/verifier appointment exists | `independently_reconciled` or `not_established` | absence blocks; O0 does not appoint |
| External approval/privacy/containment/rollback fact | initially `institutionally_supplied` | cannot pass until an independent appointed verifier reconciles it |
| Requirement outcome and currentness | `independently_reconciled` + `recomputed` time | consumer assertion never passes |
| Certificate matches this attempted action | `recomputed` | exact bindings immediately before work |
| Certificate/revision is the unique current head | `recomputed` | complete CAS lineage traversal; absent, forked, cyclic, superseded, or revoked blocks |
| Authority artifact has its exact durable event | `independently_reconciled` | verify manifest-linked event CAS, exact event-ID query, cardinality one, full canonical event equality, and record/event/authority payload-ref equality |
| Promotion-safe facet | `independently_reconciled` or `not_established` | classification only, after safety status; absence cannot alter admission and is exposed in classification coverage |
| Near-miss classification coverage | `recomputed` | derive exact classified/unclassified blocked decision IDs from `D`; zero near misses with incomplete coverage is never projected as a complete zero |
| Pilot/deployment occurred; implementation/appeal/effect outcome | `not_established` in O0 | never inferred from the certificate |

### 8.2 Property versus current proxy

| Property | Current code actually tests | Divergent case | Repair/falsifier |
| --- | --- | --- | --- |
| Actual evaluator action has an explicit admissible mode | default mode or free `fidelity` string | real-world input labeled/defaulted as simulation | require `EvaluationExecutionContext`; hold label fixed and vary bound input provenance |
| Retrospective data is safe/admissible for this attempt | `DataTrust is not None` or data ref is loadable | well-formed, wrong-scope/unapproved dataset runs | independently verified requirement results; spy proves `run_job` not called |
| Pilot attempt is safe | pilot-mode membership currently returns generic unavailable | missing rollback/population protection under omitted, maximally favorable, or forged passing promotion state | typed pack requirement blocker; inject all three states and require identical safety core/hash/certificate eligibility/evaluator count |
| Certificate is valid | prospective marker fields are present | right-looking certificate with missing/corrupt decision event or wrong binding | resolve-bind-verify; keep markers and remove property |
| Counters describe actual blocked attempts | a mutable increment or page-capped event query | retry double-count or omitted older event | complete CAS event census + reconciliation |

P29 remove-the-property/keep-the-markers probes are mandatory in every cluster.

---

## 9. Pattern pass and repair target

Relevant register rows:

- `P01`/`P02`: do not stop at contracts or a thin N8 check; build and consume
  the persisted chain. The inherited N9 positive path is already an instance:
  GY-K is contract-only and measurement roots are not orchestrated into N8/N9,
  so C00 records `GY-O0-NC-01` and forbids laundering either into a
  promotion-safe receipt while the independent O0 chain proceeds.
- `P03`: expose the informational projection through existing run/artifact
  surfaces.
- `P04`/`P09`: `blocked`, warning/review, contested, stale, and unknown states
  compose fail-closed with explicit lifecycle.
- `P05`/`P15`: promotion, LLM output, pack declarations, and projections cannot
  mint safety authority.
- `P07`/`P08`: rule version and requested/evaluated/valid/as-of time roles are
  explicit and replayed.
- `P10`/`P32`: presence/shape/self-attestation is not evidence; use
  resolve-bind-verifier provenance.
- `P12`: no certificate emits until every required producer/verifier handshake
  is complete.
- `P27`/`P28`: one mode owner and two executor chokepoints; no per-workflow
  parallel gate.
- `P29`/`P31`/`P33`: behavioral owner test, single intake/emission, adversarial
  synonyms/malformed/present-but-fake/sibling consumers.
- `P35`/`P36`: counts use complete denominators and claims cite binding findings.
- `P37`/`P38`: freeze predicate provenance and test the property, not labels.
  Promotion independence is constructed by the safety-core signature and
  injection invariance, not proxied by the current absence of a positive N9
  receipt. Before any plan-level stop rests on an upstream gap, enumerate every
  stated outcome and mark which ones actually depend on the missing artifact;
  a stop may reach only that subset. For this plan the two derivations in §1
  return 0 receipt-dependent, 1 promotion-related-but-structural, and 5
  promotion-independent outcomes.
- `P39`: count mechanism paths only; mandatory records/tests/generated checks
  are companions.
- `P40`: second finding of one class widens the mechanism or becomes a declared
  bounded residual; it never consumes another instance patch.
- `P41`: inherited red requires exact-base replay and zero intersection with the
  complete input denominator.

Capability-label closeout repeats the standing unwired/unowned check from §1.
A code-named candidate or an implemented root forbids `absent/unallocated`;
route the gap to the first missing chain link and its candidate owner. This is a
standing planning check, not a one-off correction for N8.

Target correct pattern:

```text
typed request
  -> strict mode + domain-pack resolution
  -> resolve/content-bind/independent-verifier reconciliation
  -> persisted blocked/passed decision event
  -> purpose-bound certificate only on pass
  -> immediate consumer re-verification at two execution chokepoints
  -> informational projection + complete-denominator counters
  -> existing artifact/run audit surface
```

---

## 10. Exact mechanism path manifest and ceilings

### 10.1 Declared source mechanism paths

The base manifest is exactly **16 unique mechanism paths**:

**Runtime quality (6)**

- Add `src/polisyos/runtime/quality/evaluation_modes.py`
- Add `src/polisyos/runtime/quality/evaluation_safety.py`
- Modify `src/polisyos/runtime/quality/generation_cycle.py`
- Modify `src/polisyos/runtime/quality/recursive_generation_cycle.py`
- Modify `src/polisyos/runtime/quality/promotion_sequence.py`
- Modify `src/polisyos/runtime/quality/authority_reconciliation.py`

**Runtime HTTP services (3)**

- Add `src/polisyos/runtime/http/services/control/evaluation_safety.py`
- Modify `src/polisyos/runtime/http/services/control/generation_cycle.py`
- Modify `src/polisyos/runtime/http/services/control/run_lifecycle.py`

**Scientist consumers and DI (7)**

- Modify `src/polisyos/scientist/api.py`
- Modify `src/polisyos/scientist/orchestration/engine/context.py`
- Modify `src/polisyos/scientist/orchestration/workflows/builder.py`
- Modify `src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py`
- Modify `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py`
- Modify `src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py`
- Modify `src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py`

No other source path was pre-authorized in the base manifest.

**Execution amendment (2026-08-28): C03 spends its one widening round.** A
red-first ownership trace found that the three C03 paths can bridge the
projection into the terminal Core run manifest, but cannot make the binding
remove-packet/keep-boundary falsifier fail at both existing egress consumers.
The generic egress owner currently validates only the surviving top-level
boundary, and run paper bypasses that gate. Admit exactly these two mechanism
paths as one P31/P38 owner-plus-sibling-consumer class:

- Modify `src/polisyos/runtime/quality/authority.py`
- Modify `src/polisyos/runtime/http/services/run_paper_projection.py`

The execution manifest is therefore **18 unique mechanism paths**: the explicit
16-path base union plus this exact two-path set. C03 is now 5/5 and has no
widening round left; the overall hard ceiling remains 24.

### 10.2 Two independent ceiling derivations

| Derivation | Base | Widening slack | Hard ceiling |
| --- | ---: | ---: | ---: |
| Cluster arithmetic | `C01 4 + C02 2 + C03 3 + C04 7 = 16` | four implementation clusters × at most two paths in one new-class round = 8 | **24** |
| Subsystem set union | runtime quality 6 + runtime HTTP services 3 + Scientist 7 = 16 | four bounded widening classes × owner+consumer maximum of 2 = 8 | **24** |

There is no disagreement. Path 25 is a hard stop requiring a user-approved plan
amendment.

This amendment adds no mechanism path: the structural independence falsifiers
live in the already declared test companions; `GY-O0-NC-01`, capability labels,
and lane ceilings are plan record. Both independent derivations therefore
remain **16 base mechanism paths and 24 hard-ceiling mechanism paths**.

The 2026-08-28 execution widening changes neither of those original ceiling
derivations. It spends two of the eight slack paths: cluster arithmetic is
`C01 4 + C02 2 + C03 5 + C04 7 = 18`, and the explicit set union is the
16-path base plus two previously absent egress paths = 18. Both derivations
agree on **18 current / 24 hard ceiling**, leaving six paths of aggregate slack.

### 10.3 Per-cluster mechanism caps and widening rounds

| Cluster | Declared base | Hard cap | Widening budget |
| --- | ---: | ---: | --- |
| C00 census and structural red witnesses | 0 | 0 | 0 |
| C01 contracts, strict mode, pure gate, canonical N9 classifier, N8 local seam | 4 | 6 | 1 round, at most 2 paths |
| C02 persistence, exact reconciliation, counters, projection adapter | 2 | 4 | 1 round, at most 2 paths |
| C03 container/recursive composition and existing surface | 3 + 2 admitted | 5 | **spent**: authority egress owner + run-paper sibling consumer |
| C04 Scientist verifier DI and executor strangle | 7 | 9 | 1 round, at most 2 paths |
| C05 freeze/replay/handoff | 0 | 0 | 0 |

Admissible widening classes are limited to: a newly proven canonical contract
owner, a persistence/reconciliation owner required by the real store, an
unlisted N8 composition root, or a newly proven semantic executor owner. Each
round records the new class, exact paths, owner evidence, red falsifier, and
recomputed union before editing. A second finding of the same class invokes
P40: widen the existing mechanism to the property or declare/test a bounded
residual. It does not consume another round.

### 10.4 P39 companions outside the mechanism cap

These are mandatory companions but not mechanism paths:

- this plan and the future cluster journal;
- unit/integration/repository-quality tests listed below;
- nearest-owner README updates required by `CONTRIBUTING.md`:
  `src/polisyos/runtime/quality/README.md`,
  `src/polisyos/runtime/http/services/README.md`,
  `src/polisyos/scientist/orchestration/engine/README.md`,
  `src/polisyos/scientist/orchestration/workflows/README.md`, and
  `src/polisyos/scientist/nodes/README.md`;
- scratch receipts, source-digest comparisons, and command logs;
- any automatically generated OpenAPI/public-surface comparison run in scratch
  only.

The debt register, deep-import baseline, committed generated artifacts,
`tools/quality/timing_budgets.json`, dashboard, and Atlas surfaces are not
companions and remain forbidden.

### 10.5 Declared test companions

- Add `tests/unit/runtime/quality/test_evaluation_safety.py`
- Add `tests/unit/runtime/http/services/test_evaluation_safety.py`
- Add `tests/integration/runtime_quality/test_evaluation_safety_admission.py`
- Modify `tests/unit/runtime/quality/test_value_gate.py`
- Modify `tests/unit/runtime/quality/test_generation_cycle.py`
- Modify `tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py`
- Modify `tests/unit/runtime/http/test_control_service_di.py`
- Modify `tests/unit/runtime/http/test_control_api.py`
- Modify `tests/unit/runtime/http/test_artifact_inspector_api.py`
- Modify `tests/unit/runtime/http/test_run_paper_api.py`
- Modify `tests/unit/runtime/quality/test_authority_reconciliation.py`
- Modify `tests/unit/runtime/quality/test_promotion_sequence.py`
- Modify `tests/unit/scientist/facade/test_api.py`
- Modify `tests/unit/scientist/orchestration/workflows/test_builder_pinning.py`
- Modify `tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py`
- Modify `tests/unit/scientist/nodes/builtins/decide/test_policy_runtime_support.py`
- Modify `tests/unit/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py`
- Modify `tests/unit/scientist/search/test_phase_b_policy_runtime.py`
- Modify `tests/unit/scientist/search/test_policy_blueprint_runtime_guards.py`

Before each cluster test wave, the executor compares actual Add/Modify paths
against the exact cluster set. Any undeclared source path stops before tests or
commit.

---

## 11. Parallel-lane safety and serialization

### 11.1 Disjoint lanes and two newly reserved collision paths

- DS11 owns `apps/runtime-dashboard/` and `architecture/atlas_surfaces/`. O0
  touches neither path family.
- DS15's current 37-path reservation is institutionally supplied as disjoint
  from the 36-path O0 source/test/plan denominator; no coordination is needed.
- The unbound-writes lane still owns `fabric/world/`,
  `runtime/quality/data_state_substrate.py`, `pdc/`, and
  `tools/quality/timing_budgets.json`. Its revised plan at
  `55d7f39305893e0670833cb382e3a2b0b91da9ca` explicitly withdraws the
  `run_lifecycle.py` source edit, while retaining
  `tests/unit/runtime/http/test_run_paper_api.py` in its test set. The live
  reservation is therefore one test collision, subject to the immediate
  pre-touch re-derivation below.
- Existing PDC slots `EVAL_SAFETY` and `GY_O0_EVAL_SAFETY` are reused without a
  PDC edit.

The earlier 36-path plan intersection and exact-member walk both returned the
two historical paths; the revised plan text independently removes the source
reservation and retains the test reservation. Current Git-object diff walks
from both HEAD and merge base return neither path because that lane remains
plan-only. This temporal disagreement is recorded, not averaged away. C03
still edits `run_lifecycle.py` last and runs/edits its run-paper companion last
in the surface-test slice. Immediately before either path is touched,
execution repeats both intersection derivations against the lane's then-current
branch and worktree. If changes have landed, merge local `main` forward, rerun
the cluster's red falsifier, and only then edit. Reuse the lane's planned
`runtime/http/services/adapters/core_run.py::derive_core_run_dir` if it has
landed; do not add a competing helper path.

`tools/quality/timing_budgets.json` remains forbidden. The unbound-writes
lane's chronology-catalog edit is not a reason for O0 to touch or regenerate
that governed file.

### 11.2 Relocation lane: explicit sequencing barrier

The relocation branch `codex/import-relocations-nine-seams` remains unmerged.
Two independent final-tree delta walks from its merge base to
`d5bb487246e986a8b86198fc67e0b0a3932dacc5` return 42 paths and the same exact
two-path intersection with O0's 36-path denominator:

- `src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py`
- `tests/unit/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py`

The C00 execution readback records the lane moving while O0 was still
read-only. At committed head
`cd14d2da148d5b6cb8bc3865d1bb81393ac7c5bf`, the same two final-tree methods
return 53 paths and the same two-path intersection. The dirty attached
relocation worktree has a 129-path base-to-worktree union by two complete
methods and adds a third live O0 collision:

- `src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py`

This dirty-worktree member is sequencing evidence, not a release or a claim
that it will land. The three clear Scientist chokepoint groups proceed on
schedule: Scientist API/context/builder transport, causal evaluation, and the
production policy backend. Blueprint and hierarchical-policy-search source/test
pairs wait for an explicit release readback. Immediately before either deferred
group, read back the relocation branch/worktree and local `main`. If the
relocation work has landed, merge local `main` forward and replay the C04 owner
falsifier before editing; otherwise continue waiting for its explicit release.
Do not parallel-edit or guess around the reservation.

All CAS/event tests use isolated temporary stores. No shared DuckDB, fixed port,
browser, dashboard, or production data writer is acquired.

---

## 12. Execution protocol for every cluster

1. Run `git rev-parse --show-prefix` immediately before every path coordinate.
2. Confirm `git status -sb` and `git symbolic-ref -q HEAD`; detached HEAD stops.
3. Record cluster base and exact Add/Modify sets before editing.
4. Run the named red behavioral falsifier before implementation. A marker-only
   or constructor-only red is insufficient.
5. Implement the smallest owner-level repair.
6. In the local lane, run exact red/green blast-radius selectors, recomputing
   validators, changed-path Ruff, and guardrails. Full owner files and full
   suites belong only to the replay/cloud lane after the plan lands.
7. Run Ruff on changed Python paths and importer tests for changed modules.
8. Re-run declared-set equality and branch attachment.
9. Commit at the clean semantic boundary. The plan-forward merge already
   recorded in §1 and a collision-triggered append-only merge of local `main`
   under §11 are the only authorized merges. Never stash as storage, rebase,
   reset, force-push, push, or merge this execution branch into another branch.
10. Re-read the committed paths from the attached branch before handoff.

Every shell command uses this shape; `task_status` is deliberately not a zsh
reserved name:

```zsh
uptime
/usr/bin/time -p <exact-command>
task_status=$?
uptime
exit "$task_status"
```

Do not pipe a producer before reading its exit. Where a consumer is required,
write producer output to harness scratch, check its exit, then read the file.
A completed nonzero process is a failure receipt. A kill/signal/timeout is a
non-receipt. No ceiling widens during a run.

Fixed numeric ceilings, derived from completed `user + sys` comparisons:

| Typed lane and command class | Evidence and derivation | Fixed ceiling |
| --- | --- | ---: |
| planning/local census and source-set scripts | planning executor census CPU `user 13.70 + sys 0.42 = 14.12s`; `2 × 14.12 = 28.24s`, rounded up | **30s, planning/local census lane** |
| ordinary local focused blast-radius command: at most two exact pytest node IDs, or one changed-path Ruff/recomputing-validator invocation | Two independent current-base runs of `test_fixed_time_n8_calibration_is_ledger_refused_and_stays_shadow` plus `test_scope_insufficient_cannot_mint_production_authority`: run A uptime 22:39→22:40, CPU `user 51.38 + sys 2.20 = 53.58s`; run B uptime 22:40→22:41, CPU `user 52.67 + sys 2.03 = 54.70s`. The measured disagreement is `1.12s`; use the slower basis: `2 × 54.70 = 109.40s`, rounded up. | **110s, local focused-selection lane** |
| one full backend owner-test file | current-base full `test_promotion_sequence.py` replay, uptime 22:01→22:22, CPU `user 1134.01 + sys 45.32 = 1179.33s`; `2 × 1179.33 = 2358.66s`, rounded up | **2360s, replay/cloud lane only** |
| architecture guardrails | DS11 CPU `user 40.04 + sys 40.61 = 80.65s`; `2 × 80.65 = 161.30s`, rounded up | **180s, local guardrail lane** |
| full `workspace ci-parity --skip-browser` | DS9/DS-INFRA completed CPU `user + sys = 754.20s`; `2 × 754.20 = 1508.40s`, rounded up | **1510s, replay/cloud parity lane** |

Every run still records its own `user`, `sys`, ordinary exit, and uptime pair.
The **110s** ceiling is the ordinary local cluster default; the **2360s**
ceiling is never permission to run a full owner file locally. Conversely, the
110s figure is not applied to a cloud/full-file replay. Full files run as
separate replay/cloud commands unless a combined cloud wave is first measured
and admitted; do not hide an unmeasured aggregate under either per-command
ceiling. The operational ceiling can bound only the harness, never a product
predicate.

---

## 13. Cluster plan

### C00 — Preserve the N9 census, constrain its consequence, and freeze structural reds

**Mechanism paths:** none.

On the current base, run and preserve both independent N9 derivations described
in §1. They establish that `EFFECT` and `MEASUREMENT` remain
`scope_insufficient` and that no real production-lane
`consumer_promotable=True` receipt exists. Record the first missing links and
the two exact code-named candidates under `GY-O0-NC-01`; do not relabel the
whole condition `verification_missing`, fabricate a receipt, absorb the GY-K/N8
work, or stop C01-C05.

Before freezing reds, repeat the two §1 outcome-dependency derivations. The
outcome-text walk and target dataflow/signature walk must each enumerate all six
outcomes and return the same partition: 0 live-receipt-dependent, item 4 as the
sole promotion-related structural property, and items 1, 2, 3, 5, and 6 with no
promotion dependency. A later disagreement is reported and requires a plan
amendment; it is never reconciled by widening the stop.

Red-first behavioral witnesses:

1. **`O0-PROMOTION-INDEPENDENCE-C00`** freezes the procedure claim before
   implementation: the pure safety-core function has no promotion argument,
   catch-all kwargs, metadata bag, or promotion-bearing nested input. For the
   same pilot-unsafe request, omitted, maximally favorable, and forged-passing
   promotion injections must leave safety status/blockers, certificate
   eligibility, evaluator/external spies, core bytes, decision ID, and safety
   hash invariant. Forged/unverified input yields no admitted classification.
2. A loadable but wrong-scope observational dataset reaches
   `RunCausalEvaluationNode`; the red asserts `run_job` is never called.
3. `ProductionPolicyEvaluationBackend(fidelity="full")` with well-formed but
   wrong-bound reports currently creates evaluation/promotability output; the
   red requires explicit admission context and no output.
4. Unknown/absent mode and the formal spelling `simulation_only` do not become
   `simulate_only`.
5. Hold certificate/projection marker fields constant and remove the resolved
   authority event; admission must fail while projection inspection remains
   informational.
6. Issue a certificate, then append a content-bound revoke/supersede revision
   or invalidate one appointed evidence current head; the unchanged certificate
   is rejected before evaluator work.

Re-run and save the dual six-mode, owner-method, workflow-registration, and
admission-marker censuses. Record the known workflow coordinate-method
disagreement without changing the admitted count.

Local focused baseline selection, under the 110s lane ceiling, is exactly:

```text
tests/unit/runtime/quality/test_promotion_sequence.py::test_fixed_time_n8_calibration_is_ledger_refused_and_stays_shadow
tests/unit/runtime/quality/test_promotion_sequence.py::test_scope_insufficient_cannot_mint_production_authority
```

**Stop conditions:** stop only if the pure safety-core design admits promotion
as an input, if one of the five N9-independent outcomes is newly proved to
depend on a live receipt, or if a fourth live semantic owner appears and cannot
fit C04's one declared widening round. The present N9 producer gap itself is a
named non-closure, not a plan-level stop. When its two owners later wire a real
receipt, close `GY-O0-NC-01` with the empirical cross-gate example in their
scope; O0 is not reopened merely to add it.

### C01 — Strict mode/pack owner, pure gate/head, canonical N9 classifier, N8 seam

**Add:**

- `src/polisyos/runtime/quality/evaluation_modes.py`
- `src/polisyos/runtime/quality/evaluation_safety.py`

**Modify:**

- `src/polisyos/runtime/quality/generation_cycle.py`
- `src/polisyos/runtime/quality/promotion_sequence.py`

Tasks:

1. Move the six-member type and strict parser into `evaluation_modes.py`;
   preserve a compatibility import from `generation_cycle.py`, remove implicit
   default/coercion, and make every internal construction explicit.
2. Implement strict mode-basis/domain-pack admission, semantic-facet
   applicability, appointed-verifier resolution, canonical content hashes,
   immutable minimum union, promotion-free safety-core hashing, separate typed
   near-miss classification, pure decision composition, certificate revision
   head/revalidation, verification-only port contract, and typed blockers in
   `evaluation_safety.py`.
3. Make `FoundryValuePort` require an explicit `EvaluationExecutionContext`.
   `simulate_only` proceeds without a certificate; all other modes call the
   single verifier before the value-owner gateway. A missing real service or
   certificate blocks before gateway work.
4. Move/expose N9's existing decision-front admission predicate on
   `promotion_sequence.py`; make generation-cycle delegate. Use it only after
   a blocked safety result is frozen.
5. Preserve existing independent N8 DataTrust/value/world checks after O0
   admission; an EvalSafety pass does not satisfy them.

Required blocker families include invalid/unknown mode, pack missing/invalid/
wrong facet applicability/wrong mode/stale, profile missing/duplicate/empty, evidence
missing/unresolvable/wrong binding/stale, verifier unappointed/unverified/
self-produced, certificate wrong binding/stale/revoked, and decision-event
unreconciled.

Red/green falsifiers:

- unseen-domain two-branch pack test with identical engine-source digest;
- governance-only pack refuses the unseen domain;
- deleting or overriding any named mode-basis minimum blocks, while adding a
  namespaced domain requirement requires no engine conditional;
- `measurement_audit` without an explicit pack profile blocks;
- present-but-fake evidence and self-verification block;
- right markers with wrong candidate/WMR/mode/population/rule/time block;
- **`O0-PROMOTION-INDEPENDENCE-C01`:** signature inspection rejects any
  promotion parameter, catch-all kwargs, or promotion-bearing nested safety
  input; omitted, maximally favorable, and forged-passing injections leave the
  complete `EvaluationSafetyDecisionCore`, decision ID, certificate eligibility,
  evaluator spy, and `safety_semantic_hash` byte-identical. A forged offer
  yields no admitted facet; only a future real canonical receipt may change the
  containing event's post-core classification fields;
- forked/cyclic/revoked certificate head and post-issuance evidence invalidation
  block while certificate markers remain unchanged;
- removing the actual verifier call while leaving fields makes the test red;
- owner gateway spy stays at zero for every non-passing context.

Run exact local red/green selectors, including:

```text
tests/unit/runtime/quality/test_evaluation_safety.py::test_promotion_state_injection_cannot_change_safety_core
tests/unit/runtime/quality/test_evaluation_safety.py::test_unseen_domain_pack_resolves_or_refuses_without_engine_conditional
tests/unit/runtime/quality/test_value_gate.py::test_non_simulation_blocks_before_value_gateway
```

Replay/cloud owner-file denominator after the plan lands:

```text
tests/unit/runtime/quality/test_evaluation_safety.py
tests/unit/runtime/quality/test_value_gate.py
tests/unit/runtime/quality/test_promotion_sequence.py
```

Commit only when the exact local selectors, recomputing mode
AST/frozen-contract census, changed-path Ruff, and guardrails are green. The
cloud replay must still return the same six members over all three owner files.

### C02 — Persisted authority/event chain, honest counters, informational projection

**Add:**

- `src/polisyos/runtime/http/services/control/evaluation_safety.py`

**Modify:**

- `src/polisyos/runtime/quality/authority_reconciliation.py`

Tasks:

1. Adapt the pure gate to `write_runtime_authority_artifact`, the existing
   diagnostic event log, and `reconcile_authority_ref`; do not create a second
   store or event table.
2. Repair authority reconciliation generically: load the manifest-linked event
   CAS payload with integrity/kind/schema checks, query the existing event log
   by its exact `event_id` with `limit=2`, require one row, compare the complete
   canonical event model, and require record/event/authority payload-ref
   equality.
3. Persist pack admission, promotion-free intake, canonical request when parsing
   succeeds, optional classification offer, one immutable decision with its
   independently recomputable safety core/hash, certificate/revision-on-pass,
   later verified lifecycle revisions, and projection with exact
   schema/kind/purpose/lineage.
4. Recompute counters by enumerating every CAS artifact ID, selecting the exact
   decision kind/schema, reconciling its durable event, validating content, and
   grouping deterministic IDs.
5. Treat divergent duplicate identities as `not_established`; never select the
   convenient copy.
6. Give the projection a deterministic informational `AuthorityBoundary` and
   typed allowed run/artifact/lineage/dashboard surface packet recognized by
   the existing egress gate. The boundary grants only the gate's current
   `runtime_closeout_authority`/`dashboard_display` transport purposes; the
   packet narrows them to faithful projection, and explicit `may_not_use_for`
   includes admission, promotion, and execution.

Red/green falsifiers:

- blocked attempt persists decision/event/projection but no certificate;
- retrying the same decision does not increment either count;
- **`O0-PROMOTION-INDEPENDENCE-C02`:** omitted, maximally favorable, and forged
  promotion injections leave the persisted safety core/decision identity,
  certificate eligibility, and `unsafe_attempt_blocked_count` invariant; the
  forged input cannot increment `near_miss_count` and appears in exact
  unclassified coverage;
- the pure counter reducer counts one already-classified blocked decision once
  in both counters without treating that contract-testing event as an admitted
  N9 receipt or an empirical cross-gate witness;
- older events beyond the diagnostic page size remain in the CAS-derived count;
- more than 1,000 unrelated same-run events cannot hide the exact target event,
  while duplicate exact identity or a same-ID full-event substitution fails
  reconciliation;
- corrupt/missing durable event makes reconciliation incomplete and admission
  fail-closed;
- projection remains readable while its authority artifact is unusable;
- removing only the projection boundary/surface packet makes existing routes
  refuse it while all content markers remain;
- keeping the packet but removing either required boundary-purpose token makes
  the actual `authority_surface_decision` and route refuse the affected
  surface;
- service API contains no executor/callback parameter and an injected action
  spy remains untouched.

Run exact local red/green selectors, including:

```text
tests/unit/runtime/http/services/test_evaluation_safety.py::test_promotion_state_injection_cannot_change_persisted_safety_or_unsafe_count
tests/unit/runtime/http/services/test_evaluation_safety.py::test_counter_reducer_reports_near_miss_and_unclassified_coverage_honestly
tests/unit/runtime/quality/test_authority_reconciliation.py::test_exact_event_identity_reconciliation_is_page_position_independent
```

Replay/cloud owner-file denominator after the plan lands:

```text
tests/unit/runtime/http/services/test_evaluation_safety.py
tests/unit/runtime/quality/test_authority_reconciliation.py
tests/unit/runtime/quality/test_evaluation_safety.py
```

### C03 — Container ownership, recursive/N8 bridge, and existing audit surface

**Modify:**

- `src/polisyos/runtime/http/services/control/run_lifecycle.py`
- `src/polisyos/runtime/http/services/control/generation_cycle.py`
- `src/polisyos/runtime/quality/recursive_generation_cycle.py`

**Admitted C03 widening (one round, now spent):**

- `src/polisyos/runtime/quality/authority.py`
- `src/polisyos/runtime/http/services/run_paper_projection.py`

**Collision order:** complete the two uncontended owners and their falsifiers
first. Re-derive the unbound-writes intersection immediately before touching
`run_lifecycle.py`; edit that mechanism path and
`tests/unit/runtime/http/test_run_paper_api.py` last within their respective
C03 source/test slices, following §11.1 if the other lane has landed.

Tasks:

1. Construct exactly one EvalSafety service/concrete verifier port over the
   container-owned artifact store/event log and appointed-verifier registry;
   reject a foreign store/service just as promotion/epoch owners are rejected.
2. Thread the service and explicit execution context through the default
   recursive controller to every leaf `FoundryValuePort`. The production
   default explicitly says `simulate_only`; no constructor silently supplies it.
3. For a control-backed real-world attempt, persist and expose only
   `eval_safety_projection_ref`, typed disposition/reasons, and counter snapshot
   in job progress/terminal manifest. Keep the authority artifact separate.
4. Reuse existing artifact-inspector and run-paper routes; no route, Core DTO,
   governed projection, generated artifact, or dashboard edit.
5. A valid EvalSafety certificate must not remove existing N8 owner/treatment,
   DataTrust, world, calibration, or promotion blockers.
6. Route exact EvalSafety projection kind/schema through one type-specific
   validation seam at the generic authority egress owner, then route run paper
   through the same gate. A fresh valid-CAS projection with the packet removed
   but the generic boundary and markers retained must fail both artifact and
   run surfaces; corrupt bytes are not an adequate proxy.

Red/green falsifiers:

- **`O0-PROMOTION-INDEPENDENCE-C03`:** one pilot-unsafe control attempt under
  omitted, maximally favorable, and forged-passing promotion injections
  persists the same blocked safety core and calls no value-owner/external spy;
  forged input remains unclassified rather than minting a near miss;
- foreign service/store, stale certificate, and cross-leaf certificate block;
- explicit simulation leaf runs without a certificate but cannot narrow
  real-world state through O0;
- deleting the admission call while retaining progress fields makes the e2e
  test red;
- artifact inspector/run paper show the projection, while feeding that
  projection ref back as a certificate fails;
- removing the projection's boundary/surface packet while keeping its payload
  markers makes the existing fail-closed artifact/run surface refuse it.

Run exact local red/green selectors, including:

```text
tests/integration/runtime_quality/test_evaluation_safety_admission.py::test_control_attempt_promotion_injection_cannot_change_admission_or_call_executor
tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py::test_non_simulation_leaf_requires_current_eval_safety_head
tests/unit/runtime/http/test_artifact_inspector_api.py::test_eval_safety_projection_is_informational_only
```

Replay/cloud owner-file denominator after the plan lands:

```text
tests/unit/runtime/quality/test_generation_cycle.py
tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py
tests/unit/runtime/quality/test_value_gate.py
tests/unit/runtime/http/test_control_service_di.py
tests/unit/runtime/http/test_control_api.py
tests/unit/runtime/http/test_artifact_inspector_api.py
tests/unit/runtime/http/test_run_paper_api.py
tests/integration/runtime_quality/test_evaluation_safety_admission.py
```

### C04 — Inject the verifier port and strangle open-room Scientist executors

**Split sequencing barrier:** execute and commit the three clear chokepoint
groups first: facade/context/builder transport, causal evaluator, and production
policy backend. Blueprint runtime plus `run_hierarchical_policy_search.py` and
its owner test wait for the explicit relocation-lane release/readback in
§11.2. The deferred groups are continuations of C04, not a reason to hold the
clear chokepoints.

**Modify:**

- `src/polisyos/scientist/api.py`
- `src/polisyos/scientist/orchestration/engine/context.py`
- `src/polisyos/scientist/orchestration/workflows/builder.py`
- `src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py`
- `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py`
- `src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py`
- `src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py`

Tasks:

1. Add `eval_safety_verifier: EvalSafetyVerifierPort | None` to Scientist's
   execution context using a `TYPE_CHECKING` import from the canonical runtime
   owner. Make `scientist.api.run_experiment` and the workflow builder
   accept/propagate the injected port, closing the real
   `run_lifecycle -> run_experiment -> builder -> ExecutionContext` bridge. It
   has no default positive implementation; missing port blocks non-simulation.
2. In `RunCausalEvaluationNode.execute`, resolve the explicit execution context
   and mode-matched certificate immediately before observational data load/job
   execution. Missing, simulation-laundered, or mismatched context returns a
   typed node failure; `run_job` is untouched.
3. Make `ProductionPolicyEvaluationBackend.evaluate` require the same context
   at the owner method, not only at `build_policy_runtime_evaluation`, so direct
   calls cannot bypass it.
4. The backend recomputes whether bound inputs are simulation-only or carry
   real-world evidence; `fidelity` and caller assertion are not mode or safety
   proof. Real-world/unestablished provenance requires a certificate or blocks.
5. Thread explicit simulation contexts from hierarchical Stage-B and blueprint
   simulation call sites. Do not patch the six workflows individually.
6. Keep Synthetic backend quality-only and unable to mint authority.

Red/green falsifiers:

- **`O0-PROMOTION-INDEPENDENCE-C04`:** at both Scientist owner chokepoints,
  omitted, maximally favorable, and forged-passing promotion injections leave
  the same pilot-unsafe admission block and keep data-load/job/evaluator spies
  at zero;
- loadable wrong-scope dataset: node fails before load/`run_job`;
- `simulate_only` label held fixed while real-world input provenance changes:
  backend/node blocks the divergent case;
- absent/unknown mode cannot run either owner;
- builder omission/remote-worker nonreceipt blocks non-simulation; no local
  default service is synthesized inside Scientist;
- certificate issued before a later revoke/supersede/current-head invalidation
  is refused by the injected port before work;
- `fidelity="full"` with wrong-bound reports cannot emit promotable output;
- direct backend call and a newly registered sibling workflow remain gated;
- all six existing workflow registrations plus `WorkspaceLoop.run_intent` are
  covered through the two owner chokepoints;
- a passing certificate cannot cause execution of a pilot/deployment because
  no such executor exists in PolicyOS.

Run exact local red/green selectors, including:

```text
tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py::test_promotion_state_injection_cannot_bypass_eval_safety
tests/unit/scientist/nodes/builtins/decide/test_policy_runtime_support.py::test_direct_backend_promotion_state_injection_cannot_bypass_eval_safety
tests/unit/scientist/orchestration/workflows/test_builder_pinning.py::test_non_simulation_worker_without_eval_safety_port_fails_closed
```

Replay/cloud owner-file denominator after the plan lands:

```text
tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py
tests/unit/scientist/nodes/builtins/decide/test_policy_runtime_support.py
tests/unit/scientist/facade/test_api.py
tests/unit/scientist/orchestration/workflows/test_builder_pinning.py
tests/unit/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py
tests/unit/scientist/search/test_phase_b_policy_runtime.py
tests/unit/scientist/search/test_policy_blueprint_runtime_guards.py
tests/integration/runtime_quality/test_workspace_foundry_consumption.py
tests/integration/runtime_quality/test_evaluation_safety_admission.py
```

Re-run both executor-owner and workflow-registration derivations. The expected
sets remain 4 owners/6 registrations; the property change is that every live
owner now consumes explicit mode/safety context.

### C05 — Freeze, reviews, focused local closure, cloud replay, and handoff

**Mechanism paths:** none.

1. Freeze source and record `git diff --name-status` against the slice base.
2. Prove exact equality with the 16-path base manifest or an admitted widening
   ledger not exceeding 24.
3. Run two independent reviews in parallel: authority/status/time/counter
   semantics; and executor/sibling-bypass/domain-universality semantics.
4. Bucket every finding under P40. Apply blocking findings as one batch; a
   blocking post-freeze edit invalidates the freeze and re-prices the wave.
5. Re-open `docs/reference/policy-design-case-failure-patterns.md` and repeat the
   pattern/capability pass.
6. Run the focused local closure wave once. Dispatch the full owner-file and
   CI-parity replay to the replay/cloud lane after the plan lands.

**`O0-PROMOTION-INDEPENDENCE-C05`** is the conjunction of the C00-C04
falsifiers: re-run every named exact selector with the same omitted/maximally
favorable/forged injection matrix and prove the safety-core signature still has
no promotion-bearing input. A byte or behavior difference in safety status,
blockers, certificate eligibility, decision ID/hash, or evaluator-spy count is
a blocking O0 failure. A difference confined to independently verified
post-core classification is permitted.

Local focused lane, independently where safe:

```text
.venv/bin/python -m pytest -q <exact red/green selectors named in C00-C04>
.venv/bin/python -m <each recomputing validator for a changed governed owner>
.venv/bin/python -m ruff check <all changed Python source and test paths>
uv run polisyos-tools architecture guardrails check
```

Replay/cloud lane after the plan lands: every owner file named in C01-C04 plus
the three new test files, one full file per command under the 2360s replay
ceiling, followed by:

```text
python3 -m tools.cli workspace ci-parity --skip-browser
```

Do not run a browser/dashboard suite; O0 has no frontend path. Do not modify the
timing catalog. Do not use the replay/cloud ceiling to justify a local full-file
run. Apply P41 to every pre-existing red using the exact slice base and complete
input denominator; without that proof its provenance is `not_established`, not
inherited.

---

## 14. Required semantic acceptance matrix

| Case | Required result | Side-effect/counter assertion |
| --- | --- | --- |
| current base cannot produce a real production-lane N9 receipt | record `GY-O0-NC-01` at `producer_missing + bridge_missing`; continue O0 | no fabricated near miss; classification coverage is explicit rather than a falsely complete zero |
| explicit `simulate_only` | no EvalSafety certificate required | simulation owner only; neither counter changes |
| absent/unknown/`simulation_only` mode | typed intake-bound block | evaluator spy zero; blocked count changes only when bound evaluator/input provenance recomputes `attempt_class=non_simulation` |
| retrospective, missing privacy/access evidence | typed requirement block | causal job zero; blocked count +1 |
| measurement audit, missing pack profile | `eval_safety_mode_profile_missing` | evaluator zero; blocked count +1 |
| sandbox pilot, missing stop rule/harm bound | typed requirement blockers | no external action; blocked count +1 |
| field pilot, rollback/population protection absent; promotion state omitted, maximally favorable, then forged-passing | identical typed safety block in all three branches | evaluator zero; core/decision ID/hash/certificate eligibility and blocked count identical; forged state yields no admitted facet and no near-miss increment |
| pure counter reducer receives one already-classified blocked decision event | count deterministically without resolving promotion | both counters +1 exactly once; fixture is contract-testing evidence only and does not close `GY-O0-NC-01` |
| future real canonical N9 decision-front receipt with exact replay/design-problem/value/candidate/WMR/rule/open-world/epoch binding, field-pilot rollback absent | block + `near_miss=true`; discharge empirical `GY-O0-NC-01` only | both counters +1 exactly once; receipt may change classification fields only, never safety core/hash |
| deployment, complete pack but verifier absent | `eval_safety_verifier_unresolved` | no certificate/execution |
| valid certificate for another candidate/WMR/mode/population/rule/time | typed binding block | evaluator zero |
| issued certificate whose unique current revision/evidence head is later revoked, superseded, forked, or invalidated | typed current-head block | evaluator zero; historical certificate remains inspectable, not usable |
| present-looking projection used as certificate | typed authority-purpose block | evaluator zero |
| unseen domain with valid data pack + independent evidence | pass generically | certificate emitted; zero engine-source change |
| unseen domain with only governance pack | typed pack/facet/profile refusal | evaluator zero |
| duplicate retry | same logical decision | counters unchanged |
| conflicting duplicate identity | reconciliation `not_established` | fail closed; no arbitrary count/pass |

The structural three-injection field-pilot row is the decisive O0 independence
test now. If any promotion state can make the safety predicate pass, alter its
blockers/hash/certificate eligibility, or reach an evaluator, O0 has failed.
The future real-receipt row is stronger only as an observed example and closes
`GY-O0-NC-01`; it is not an O0 closure prerequisite. Claiming that empirical row
green on the current base would itself be fabricated authority.

---

## 15. Explicit out of scope

- O1 confirmatory updater, O2 exploratory/FDR discovery, O3 world-model
  write-back, or any O-block closure claim.
- Completing GY-K's production effect-witness chain or N8's authority-grade
  measurement-obligation chain. They are separately scoped named candidate
  owners for `GY-O0-NC-01`, not O0 prerequisites and not work O0 may absorb to
  manufacture its empirical near-miss witness.
- Institutional appointments or pretending an unappointed verifier exists.
- Executing a pilot/deployment, monitoring it, rolling it back, notifying
  actors, administering cases/payments, or deciding appeals.
- `fabric/world/`, `runtime/quality/data_state_substrate.py`, `pdc/`,
  `tools/quality/timing_budgets.json`.
- Debt register, deep-import baseline, dashboard, Atlas surfaces, new governed
  projection definition, new HTTP route, or committed generated artifact.
- Turning unresolved `INT-R4` questions into O0 code contracts.

---

## 16. Implementation handoff contract

Each cluster handoff reports:

- attached branch/base and committed readback;
- exact Add/Modify paths and current mechanism-cap/widening balance;
- delivered capability-chain links and any retained typed incomplete label;
- red-first behavior, green behavior, complete selected-test denominator,
  ordinary exits, `user + sys`, ceilings, and uptime pairs;
- authority/predicate provenance table changes;
- decision/certificate/projection refs from the e2e test;
- exact recomputed counter denominator and duplicate handling;
- collision release evidence for C04;
- the immediate pre-touch two-path unbound-writes collision readback for C03;
- no-push/no-integration confirmation, plus the exact authorized append-only
  merge readback if §11 required one.

Final handoff must repeat verbatim:

> `INT-R4` gates O1/O3 and the O-block's closure, not GY-O0. GY-O0 certifies an
> attempted evaluation; it neither executes deployment nor closes the O-block.

It must also report the six-mode code location, the final reuse/build split,
the unseen-domain falsifier result, every named structural promotion-injection
falsifier, and honest `unsafe_attempt_blocked_count`, `near_miss_count`, and
near-miss classification coverage. It must carry `GY-O0-NC-01` with candidate
`owner_ref` values `GY-K entailment witness owner` and `measurement-rooted
producer owner`, plus their exact refusal details **"GY-K entailment witness
owner is unwired"** and **"Measurement-rooted producer owner is unwired"**,
until a real empirical cross-gate disagreement is observed. That non-closure
neither authorizes a fabricated receipt nor delays O0 closure.
