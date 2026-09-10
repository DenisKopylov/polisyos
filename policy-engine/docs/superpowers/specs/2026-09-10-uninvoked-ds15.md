# DS15 uninvoked mechanisms: decision before wiring

Date: 2026-09-10. Lane base: `c49449343`. Decision owner: uninvoked root;
implementation owner: DS15 workstream. No source changes preceded this document.

## Discrepancies first

**U15-F01 — the gateway names in the initial question are not the audited
mechanism.** Task Q's finding under
`2026-09-01-debt-q-remeasure-and-typing.md`, heading
`ds15-signed-v2-delegation-mandate-owner-authority`, names
`AgentActionAuthorityGateway`. The current source contains
`AcquisitionAuthorityGatewayProvider` (a Protocol) and
`HumanDecisionProductionGatewayAdapterInput` (a DTO), not implementations named
`AcquisitionAuthorityGateway` or `HumanDecisionProductionGateway`. Neither
`RealAcquisitionOwnerGateway` nor `RecordedAcquisitionOwnerGateway` replaces the
audited gateway: they obtain/replay data-owner artifacts; they do not resolve
signed delegation or current mandate authority. The root's complete tracked
`src/**/*.py` AST/token census is the quantitative owner; these are semantic
identifications, not counts inferred from a search result.

**U15-F02 — the signed-delegation record's engineering gap remains.**
`runtime/http/container.py:RuntimeContainer` passes its optional
`acquisition_authority_provider` override to `AcquisitionActionService`;
the ordinary default remains `None`. `AcquisitionActionService.request_decision`
and `execute` call `_require_authority_provider`, which raises
`acquisition_authority_producer_missing` before the gateway. The record's
construction assertion must be read against the root census for
`AgentActionAuthorityGateway`, not the differently named data-acquisition
gateways. `CurrentMandateOwnerEvidence` remains a signed evidence DTO;
the mapping accepted by the gateway is not an institutional appointment slot.

**U15-F03 — semantic qualification has a production query caller, but the
record's persisted acquisition producer remains uninvoked.**
`dependencies.build_runtime_api_context` now composes
`SemanticEpochService.for_unallocated_policy_query` into `TemporalService`.
The served `GET /api/v1/temporal/runs/{run_id}/epoch-staleness` calls
`build_epoch_staleness_projection` → `qualify_chronology_query` →
`QualificationConsumer.qualify`, which produces the real typed
`policy_admission_missing` result. The route audits projection status; it does
not persist `PersistedSemanticEpochProductionReceipt`. That live query path
does not settle the task-Q finding about
`admit_acquisition_with_production_semantic_epoch`. The old full acquisition
composition still requires its own durable invocation. Query composition and
acquisition admission are different mechanisms and neither substitutes for the
other.

Source anchors for U15-F01–F03 are
`src/polisyos/runtime/quality/agent_action_authority.py`,
`src/polisyos/runtime/quality/acquisition_planner.py`,
`src/polisyos/runtime/http/services/acquisition_action_service.py`,
`src/polisyos/runtime/http/container.py`,
`src/polisyos/runtime/http/dependencies.py`,
`src/polisyos/runtime/http/services/temporal.py`, and
`src/polisyos/runtime/quality/acquisition_executor.py`, all at the lane base.

## Production callers decided before implementation

| Mechanism | Outcome and production caller / named deferred task | Runnable terminus and material boundary |
| --- | --- | --- |
| `admit_acquisition_with_production_semantic_epoch` | Wire through new `src/polisyos/runtime/quality/acquisition_epoch_admission.py:main` | `python -m polisyos.runtime.quality.acquisition_epoch_admission --request REQUEST.json`; consumes real persisted input refs, invokes the existing complete producer and prints an exact-read persisted owner receipt. |
| `CanonicalAcquisitionAuthority.from_provision` | Same new module resolves the provision from its configured authority repository and baseline file | Same CLI; no caller-supplied authority object or trust-anchor digest. Existing provision validation remains authoritative. |
| `SemanticEpochService`, `SemanticEpochQualificationAdapter`, `QualificationConsumer.qualify`, `persist_semantic_epoch_production_receipt` | Existing `admit_acquisition_with_production_semantic_epoch` remains their composition caller; the new CLI makes that caller reachable | Same CLI; negative qualification is persisted by the existing producer. No new predicate signer, policy admission, positive history or activation route. |
| `AgentActionAuthorityGateway` and `CurrentMandateOwnerEvidence` intake | **Deferred with a name: `DS15-MANDATE-INTAKE`**, owned by `team-runtime` with the external mandate institution supplying signed currentness/delegation evidence | Future production provider is `runtime/http/services/acquisition_authority_provider.py:ProductionAcquisitionAuthorityProvider`, composed through a governed deployment-factory extension owned by that task. `RuntimeContainerOverrides` is forbidden by ordinary non-dev app creation and is not the production route. Terminus must be the existing served acquisition decision-request and execute routes, including worker replay. |
| `AcquisitionAuthorityGatewayProvider` | Same `DS15-MANDATE-INTAKE` task; the Protocol is not a caller | Must use both `for_request` and `for_job`, return the actual gateway and consume its persisted decision; a provider constructed only by tests will not close the task. |
| `RealAcquisitionOwnerGateway`, `RecordedAcquisitionOwnerGateway`, temporal query composition | Existing callers; no source modification in this lane | Separate data-production / served temporal paths, measured by the root census; no DS15 mandate-authority claim is made from them. |

### Why the mandate caller is deferred

**U15-F04 — a standalone refusal checker cannot lawfully construct this
gateway from empty dependencies.** Its constructor requires the exact
`BoundActionPermissionVerification`; that type's `__post_init__` checks the
private route-dependency seal (`runtime/http/authorization.py`). The gateway
also binds signed CAS, runtime event log, idempotency owner, verifier, producer
identity and exact run/resource context. Copying the test helper's private seal
or writing a synthetic DS20 proof in a CLI would manufacture the floor the
gateway exists to enforce. A gateway-independent missing-provider receipt
would still leave the gateway uninvoked.

**U15-F06 — the apparent alternate-embedding seam is explicitly forbidden in
production.** A follow-up read of `runtime/http/app.py:create_runtime_api_app`
establishes that any non-`None` `container_overrides` is placed in
`direct_non_development_authority` and rejected when the default profile is
not `dev`. The admitted `RuntimeDeploymentSecurity` class in
`runtime/http/deployment_security.py` carries identity, cells, OPA, step-up,
principal grants and human-decision custody; it carries no acquisition
authority provider. Therefore simply writing an alternate app factory with the
existing override is a development caller, and bypassing the guarded factory
would cross the closed bootstrap authority boundary. This corrects the initial
future-route inference in this decision; no signed-gateway source was written
under that inference. `DS15-MANDATE-INTAKE` must first create the sanctioned
governed deployment composition, with its owner revisiting the closed bootstrap
surface explicitly. The absence is engineering as well as institutional.

The missing task is not merely “appoint an owner.” `DS15-MANDATE-INTAKE` must
build the purpose-specific typed-empty intake, independently verify and
content-bind institutional currentness/revocation and signed v2 delegation,
select their refs for the exact route resource, and compose the gateway with
the real DS20 proof and durable runtime owners. It must preserve a named empty
arm, persist the gateway's refusal through `persist_decision`, and expose the
decision on the existing API. Its negative test must remove that provider
invocation while leaving the same unappointed institution and route request
unchanged; no decision receipt may survive the removal. Its positive authority
test waits for real institutional inputs, not fixture keys. Present capability
labels remain `absent/unallocated` for institutional authority,
`producer_missing` for intake/selection, and `implemented_but_not_orchestrated`
for the gateway. This named deferral claims no appointment-only closure.

## Operational admission CLI design

The CLI is a local operational entry point over the existing producer. A
strict Pydantic request contains the repository root for epoch-owned registries,
the authority repository and baseline path for canonical provision resolution,
CAS/overlay/history paths, epoch ordinal, journal evidence ref, epoch scope,
authority purpose, three role-distinct coordinate evidence refs, complete facet
source-ref mapping and optional existing live-execution evidence. It accepts
neither a constructed authority nor a qualification status, policy signer or
verifier. Local paths select existing owned artifacts; canonical owner code
reopens and content-binds the decisive files and CAS evidence.

The command calls the existing full producer once. The audit consumer resolves
its returned `epoch.production_receipt` through the canonical epoch statement
reader and compares the full statement with the returned receipt before
printing the existing persisted DTO as JSON. A positive activation return is
not reinterpreted as a negative production receipt. The command reports typed
negative admission with a nonzero exit status, making absence operationally
visible while retaining the durable receipt. Parser/config/owner-resolution
errors fail before any successful output. No new receipt schema, authority
vocabulary or parallel qualification mechanism is introduced.

### Red-first sequence and acceptance

1. Add a targeted test file
   `tests/unit/runtime/quality/test_acquisition_epoch_admission.py` that drives
   the CLI `main` from a strict JSON request against real local CAS, journal,
   catalog provision, L5 registry, Lex store and overlay/history. Use fixture
   bytes only as test inputs; the executable source imports no test helper.
   The initial run must fail because the CLI module does not exist.
2. Add the new module without editing closed producers. The baseline negative
   must execute the real producer, persist `status=not_established` and
   `failure_codes=[policy_admission_missing]`, and return that exact persisted
   statement through CLI output. Read the CAS bytes independently in the test.
3. Removal probe: disable only the CLI-to-producer call while preserving the
   identical unappointed policy and request; the unchanged receipt assertions
   must fail. A call counter alone is insufficient. Also reject fabricated or
   mutated returned receipt evidence, malformed/extra request fields and
   missing owner input.
4. Run only that targeted file plus the exact original production-composition
   regression node and lint for changed Python files. Root serializes the
   shared README documentation and architecture gate.

The local worktree has a Python 3.14 venv whose installed dependencies are
borrowed by a `.pth` from the main checkout, with this worktree `src` first.
DuckDB and the existing test substrate are required. Missing fixture/data or
tool dependencies are harness limitations and cannot count as a semantic red.
All deciding full outputs and removal outputs go to gitignored
`docs/superpowers/journals/uninvoked/ds15/raw/`; only concise evidence is retained
in the root completion journal.

## Boundaries, transition and pattern pass

DS15's original acquisition source is declared `execution_closed` by
`docs/plans/active/atlas-slices/DS15-acquisition-routes.md`; Task J closed
`acquisition_surface_execution.py` and its route binding; Tasks B/R own closed
temporal/epoch projection work. This lane routes those mechanisms and changes
none of their source. The new CLI module and mirrored test are its mechanism
paths. Parent README updates and decision/journal documents are mandatory
companions, outside that mechanism count and serialized by root.

No governed rule, registry, policy schema, existing producer source or artifact
is to be changed. The baseline for any subsequently discovered required epoch
transition is this lane's merge base `c49449343`; root must coordinate such a
transition before governed writes. The CLI addition itself asserts no artifact
reissue or epoch bump.

**U15-F05 — positive transition remains blocked on the same missing chain.**
The `ds18-positive-transition-production-unorchestrated` finding names a real
pre-N9 trigger, complete `EpochDependencyDenominatorProvider`, complete
`EpochPerturbationAdjudicationProvider`, purpose-scoped signer/owner appointment
and the later denominator-reader wiring. This CLI builds none of those. A
negative acquisition production receipt does not produce a signed positive
transition, and it changes none of that row's blockers. The out-of-scope
`ds18-epoch-predicate-policy-signer-unappointed` mechanism is unchanged.

Pattern pass: P01/P02 identify the unreachable producer; P03 requires the
persisted receipt's audit consumer; P05/P32/P37 prohibit a fabricated DS20 floor
or mandate authority; P29/P33 require content readback and an unchanged-negative
removal witness; P35/P36 put set claims in the full root census and identify
findings separately; P38 separates typed query projection from persisted
acquisition production. The repaired property is real invocation and exact
receipt consumption, not a constructor string or successful exit marker. The
smallest divergent case is a CLI printing an unchanged `policy_admission_missing`
literal after its producer call is deleted; the removal witness must reject it.
