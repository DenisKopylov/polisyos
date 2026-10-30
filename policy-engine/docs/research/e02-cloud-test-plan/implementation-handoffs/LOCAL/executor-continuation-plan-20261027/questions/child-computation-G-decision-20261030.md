# G decision: admitted child computation with an intact parent grant

Date: 2026-10-30. Architecture decision for implementation; not code acceptance,
integration, an E02 closeout, or a new scientific/production authorization.
`code_acceptance=false`; `closure_ids=[]`; runtime verification in this review: UNRUN.

Reviewed delivery: `e151479e1349639c89daf026a1b8282772194f80`, tree
`0900a3b53321a1b6bbd793ec86736261ede6b283`. The two question documents are under
`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/executor-continuation-plan-20261027/questions/`.
The author analysis is pinned to `f44a6455be0313dc1b6258e7fca2518f232c4e43`.
I independently hashed every member of the manifest's complete named denominator:
24 source/document files, zero mismatches at the reviewed delivery. This is not a
repository-wide dependency census. Manifest SHA-256:
`378724db8e5c3da7a5423823384ad8fcb330fbbd627fe19d621b73098b114fd7`.

## 1. Ruling and binding invariants

Select option 1: an **engine-owned, separately admitted child-computation
capability**, with the existing parent producer grant unchanged. Extend the
existing sub-workflow, invocation, registry, retry, journal/merge and run-custody
owners. Do not create another executor, scheduler, policy-authority service or
simulation ledger.

The grant addresses a different child workspace, not a widened view of the parent.
The parent cannot manufacture it by constructing an issuer, submitting a NodeSpec,
unioning child paths or copying state without its journal. An independently
appointed engine admission owner authorizes the invocation from its own policy.

The original four parent paths remain:

- `params.policy_candidate_schema`
- `params.policy_search_result`
- `inputs.trinity_bundle_ref`
- `artifacts_index.policy_frontier_report_ref`

`branch_state` narrowing remains binding everywhere it currently applies.
Neither those paths nor `NodeSpec.state_writes` are reinterpreted as merely a
publication hint. Child execution and parent publication are separately admitted.

Binding existing rules: **S0-K03** (separate planes), **S0-K05/K07** (transport and
projection cannot mint authority), **S0-K06**, especially its application note at
`docs/system-design-decisions/stage0-custody-kernel-ratification.md:155-176`, and
P05/P27/P29/P31/P32/P37/P38/P40 in the failure-pattern register. These rules constrain
the choice; they do not already appoint a workspace issuer. This decision appoints
the logical engine execution-admission role described below. Its implementation
and authenticated configuration are still required.

Option 2 is not selected for this slice. A separate composition owner could
legitimately hold a newly authorized union grant, but giving that union to the
current parent producer would enlarge its mutation authority. Keeping the union
inside a mediator largely reconstructs the selected child-invocation mechanism.
No inspected ratified finding supplies a ready-made alternative issuer for option 3.

## 2. Trust model and candidate plane

The first supported profile is **trusted builtin, same-principal local candidate
computation**. It is not a Python sandbox. Candidate work may retain declared
unknown scientific, jurisdictional or evidential scope under S0-K06. It may not
use that uncertainty to obtain data, filesystem, network, tenant or publication
permissions that its executing principal does not possess.

Require managed state/input/store/port operations to pass their actual owners.
Passing only the admitted input projection and restricted handles is real
interface enforcement. It does not prevent trusted Python from using a captured
object, ambient credentials, an import or direct OS I/O. Such bypasses are outside
and prohibited by this trusted-code profile, not claimed mechanically impossible.

Consequently:

- A candidate result and verified application of a particular managed journal may
  be returned when their actual predicates are established.
- Do not issue a successful **fully confined workspace/no-effects/privacy** receipt
  while those predicates are unestablished. Record managed journal verification,
  execution outcome, release decision and isolation coverage separately.
- A consumer requiring secret segregation, hostile/plugin-code containment,
  arbitrary external-effect exclusion or stronger deployment authenticity must
  select a proven isolation/backend profile or receive a typed refusal. No silent
  fallback to this trusted local profile.
- If a required actual port/data operation lacks authorization or a compatible
  effect adapter, refuse that operation; independently executable candidate work
  may continue with its precise limitation. Do not fabricate an empty successful
  child or a scientific positive.

Here, independently executable means authorized through its own existing path.
It never permits entry into the new child workspace without its issuer/admission.
Unknown scientific scope and missing permission are different conditions.

An all-purpose sandbox is not a prerequisite for the narrow comparison computation.
This does not establish that today's Stage-B context already meets the narrow profile.

## 3. Concrete existing owners and corrections to the source analysis

All paths in this section are relative to `policy-engine/src/polisyos/` at the
reviewed commit.

| Owner | Reuse and required extension |
|---|---|
| `scientist/orchestration/engine/sub_workflow.py:151-224,309-336` | Existing mapped child workflow, normal executor and guarded parent projection. Extend this composition seam or factor its common engine service; do not introduce a parallel nested runner. Its current shallow input mapping, copied context and all-child-artifacts return are not the new capability. |
| `scientist/orchestration/engine/context.py:293-370` | Resolve actual invocation, selected workflow/input artifacts and run-owned attempts. Add distinct child binding rather than copying the parent's `_engine_invocation`. |
| `scientist/orchestration/engine/registry.py` and `component_identity.py:1-5,222-285` | Registry resolution plus actual selected implementation/spec/bound-parameter identity. Mutable registration is evidence, not issuer appointment. Current identity is in-process and covers three selected builtin types; extend its mechanism to the admitted composition without claiming transitive/deployment attestation. |
| `scientist/orchestration/engine/state_branching.py:303-338`, `state_merge.py` | Preserve narrowing, alias protections and verified journal application. A newly admitted child gets its own workspace grant, never the parent's detached unguarded model. |
| `scientist/orchestration/engine/retry.py:619-654,1399-1413,1486-1506` | Existing attempt revocation and restricted `_EngineNodeRunView`. Normal engine callbacks already receive a manifest snapshot and restricted run API. Preserve/extend this boundary; Stage-B save/restore is not proof of raw parent-manifest access during normal execution. |
| `core/run/context.py`, existing worker/control-store fencing and budget middleware | Bind root lineage, attempts, effect receipts, actual lease/current owner and accounting. Use the existing transaction mechanism for the selected profile. |
| `scientist/nodes/builtins/planning/run_hierarchical_policy_search.py:1140-1284` | Replace the direct five-node calls with admitted composition. Include the counterfactual helper and candidate/evaluation persistence in the declared effect/identity boundary. Preserve their existing scientific owners. |

`state_reads` currently supports availability/scheduling/idempotency reasoning; it
is not an enforced privacy firewall. The existing timed store/run gates also do not
automatically constrain every Fabric/Foundry/Lex/Scholar/memory port.

## 4. Appointment, grant and implementation binding

The **engine execution-admission owner** is configured by trusted runtime bootstrap
under existing tenant/cell/run authority. The owner-controlled composition policy
is selected independently of the parent's mutable registry and request payload.
Only that configured role can issue/revoke this capability. Do not add a caller
HTTP field or let the parent pass its own Protocol-shaped issuer as appointment.

For the local trusted profile, opaque owner-held handles and an owner-owned active
record suffice; this ruling does not require a new cryptographic token service.
Their guarantee is managed-interface admission in a trusted process, not resistance
to hostile code running in that same interpreter.

The versioned admission record binds:

- tenant/cell, root run/job/attempt and current fence; parent invocation identity;
- composition-policy ref/version and admission generation/expiry/revocation;
- actual immutable composition template: membership, dependencies, bind parameters,
  input/output mappings, allowed conditionals/repetition and selected entry profile;
- actual resolved implementation identities and their stated proof coverage;
- child workspace/attempt identities, input refs with complete selected profiles,
  managed read/port/effect rights and publication mapping;
- inherited deadline, cancellation lineage, resource permit and budget authority.

The effective rights are bounded by both the engine policy and the executing
principal's existing data/effect/resource authority. A child contract supplies no
extra authority by itself. Child paths are relative to its child workspace; they
need not be subsets of the parent's four paths because they cannot mutate that
parent object. Parent publication remains a subset of the original parent grant.

Resolve the actual implementation at dispatch; matching component names alone is
insufficient. Capture registered type/function/spec/bind identity through the
existing identity owner. Hold the selected resolved registration for the invocation
or refuse a substitution. In-process proof does not survive a process change as a
fresh authority fact. An exact trusted deployment/package boundary can be a
separate input; do not build an endless recursive transitive-hashing ladder.

Templates may support many candidate iterations without pre-enumerating numerical
candidates. Each iteration binds its actual candidate/input and fresh child attempt.
A new child kind, graph edge, implementation or effect requires new admission under
the same generic mechanism, not another hardcoded engine branch or an LLM waiver.

## 5. Workspace and execution protocol

1. Reconcile the root invocation, configured issuer/policy and current attempt.
   Authorize before child reconstruction, callbacks or producer work.
2. Construct a child input projection using admitted finite-data/Core serialization
   and the existing copy/alias rules. Share immutable CAS bytes where permitted;
   do not shallow-share mutable parent/sibling objects or copy the whole CAS/venv.
3. Issue a distinct child attempt basis linked to the root attempt/fence and
   composition generation. Preserve inherited resources and ports. A new logical
   child ID must not create a new global run authority or default empty budget.
4. Invoke each child through the normal engine invocation/retry/journal path with
   its own registered write scope. Use a separately admitted next child; do not
   widen the preceding child's narrowed view. Cover the helper as a bound step of
   its existing owner, rather than leaving an unaudited direct-call gap.
5. Verify genuine journal operations and merge into the private child composition
   state with the existing merge owner. A producer-returned receipt is not proof.
6. Independently resolve the selected output/ref closure and prepare the parent
   projection. Reconcile current admission and root fence at actual release.
7. Apply only the four permitted parent paths through the original guarded parent
   view. Close handles; retain exact partial/refused/failed outcomes and provenance.

Admit dependent steps against their predecessor's verified output. Admission may
be dynamic inside a preauthorized template, but caller state/graph assertions
cannot supply a missing producer fact. Preserve causal readiness, calibration,
counterfactual and evaluation-safety refusals.

## 6. Effect custody and the actual publication set

| Effect | Required owner behavior |
|---|---|
| Input/state reads | Materialized admitted projection plus restricted managed CAS/read handles. Record observed/covered basis separately from advisory read declarations and ambient-code limitations. |
| Child CAS writes | Use existing CAS machinery behind an attempt-scoped candidate staging adapter. No parent/public current-reference admission from the child. |
| Run manifest, events, audit | Existing restricted run/attempt owner; child-owned records linked to root. No shared mutable parent manifest or arbitrary append-output authority. Audit distinguishes attempted, committed and unknown. |
| External ports | Explicitly authorized operation-scoped adapters; deny unsupported effects. No inherited omnibus port merely because `dataclasses.replace(ctx)` copied it. An irreversible external write is not part of this first profile. |
| Parent/current output and export | Existing run/publication owner admits the exact mapped output and allowed referenced artifacts under a live fence. Existing authority/tenant/secret gates continue to apply. |

For the first slice, prefer an attempt-local staging store/namespace whose locator
is **not reachable through any served store or scan root**, with allowed inputs
read through an authorized adapter. Reuse the storage format and immutable objects;
do not clone the input store. A write-only wrapper over the served CAS is insufficient.
An existing canonical reader release gate may substitute only if its behavior is
demonstrated across all affected content/download/export entries.

Publication covers the **schema-resolved, selected-profile permitted output/ref
closure**, including references embedded in the frontier/candidate/evaluation
payloads. Four dictionary assignments are not that closure. Existing authorized
input refs need not be copied. An unselected sibling must not become visible, and
a selected permitted child ref must not be stranded in inaccessible staging.
Unsupported reference semantics remain a typed limitation/refusal for the consumer
requiring a complete closure; do not recursively treat every string as an ArtifactRef.

Persist immutable staged objects before publishing one owner-admitted release
record/head binding the selected parent projection and closure. Consumers resolve
that committed release, not a child-set `private` or `complete` flag. Either the
selected store keeps unreleased objects unreachable or readers enforce the release
predicate. Physical blob presence, a guessed digest or another manifest profile
must not bypass the selected visibility decision. Do not release a whole namespace.

Promotion is part of this boundary: copying staged bytes into an already-readable
served CAS before the release record would create an escape. For this first slice,
extend the canonical artifact-read admission for the new child-output class to
resolve owner-controlled release state; stage/copy before release only where that
gate actually withholds visibility. If that gate is unavailable, retain the bytes
outside served roots and refuse release until a gated resolver exists. A reference
marker supplied by the child cannot activate or satisfy this predicate. Identical
content already accessible through an independently authorized occurrence keeps
its prior rights; staging must neither revoke those rights nor borrow them as
proof that a different child occurrence/profile was released.

## 7. Lifetime, fencing, retries and accounting

Reconcile appointment/currentness before each new child and at output admission.
Use the root run/lease and existing attempt gate, extended with composition
generation. A periodic status check alone is not a publication fence. State the
actual linearization point shared by revocation and the selected publication
transaction; do not claim a local mutex serializes an independent remote owner.
Do not hold admission locks across child computation, network calls or waits for
child capacity. Use short admission/commit fences and the existing lifetime owners;
the selected protocol must establish ordering for the actual owner combination.

An operation ordered after revocation refuses. Already-entered backend I/O may
finish after cancellation; retain inaccessible staging and unknown/partial effect
status where appropriate. A release ordered before cancellation remains historical
fact; cancellation is not rollback. Lost acknowledgement requires reconciliation
against the actual committed release before retry or another success receipt.

No new child acceptance after parent closure; no unowned detached execution or
successful quiescence claim while owned work is unresolved. This does not promise
that Python threads or remote I/O can be forcibly terminated. New handles cannot
reuse settled/revoked attempt authority.

Use one existing resource and monetary-accounting owner. The first execution may
run children serially by borrowing/continuing the parent's permit, with one charge
for actual physical work. Do not hold the last permit while waiting for a child to
acquire a second permit from the same exhausted pool. Parallel fanout reserves from
the same owner when implemented; neither a new semaphore nor a monetary ledger is
a substitute for compute admission. Child retry cannot reset remaining deadline or
budget; reconcile unknown charge acknowledgements using existing settlement IDs.

## 8. Cache, recovery and supported entries

The ordinary idempotency key does not establish the new grant. For the first
implementation **disable reuse fastpaths for both the child composition and its
enclosing composition-bearing parent invocation**, including recovery shortcuts
that would emit an outcome before fresh admission. This is a scoped measure, not a
global cache shutdown. Later reuse must separate old computational evidence from
present permission, bind composition/implementation/input provenance and pass the
same current release gate. Never repeat an irreversible effect just to replay.

Implement the actual local entry used by the failing witness, including an async
host dispatching the synchronous node if that is the real route. One canonical
admission/settlement API must cover all supported routes. Async/remote/nested entries
that cannot enforce it explicitly refuse the new capability before child work;
they may keep their unrelated existing behavior. Do not claim parity from a shared
DTO, transported in-process identity, or an old child receipt. Remote support later
needs a verified worker/deployment boundary, explicit attempt/fence transport and
late/duplicate return admission, not a second permission policy.

## 9. Minimal engineering sequence and migration

1. Assign one engine/composition owner and map the actual entry, callback/helper,
   store/run/port/output consumers. Preserve the 104-file pattern census's stated
   boundary; expand indirect/dynamic entries only where needed for this mechanism.
2. Implement versioned owner configuration/admission and distinct child invocation
   using the existing sub-workflow/executor seam. Preserve old narrowing and exact
   implementation binding. Do not silently enable the capability for all plugins.
3. Add the selected managed input/effect/staging profile, inherited lifetime and
   output-release join. Wire the parent and child cache/refusal paths together.
4. Replace Stage-B direct calls and manifest save/restore assumptions with the
   admitted composition. Keep the same semantic producers and original guards.
5. Run cheap semantic tests and independent source review, then the three original
   R102 comparison cases on a frozen candidate with their full original assertions.
6. Migrate affected SubWorkflow consumers, sync/async/remote boundaries, package and
   public/schema/generated surfaces. Older serialized workflows keep old meaning;
   a new composition version is explicit. Unadmitted old direct calls cannot become
   privileged by fallback. Publish useful code/docs and compact deciding evidence.

Runtime/configuration/implementation choices inside this ruling need no further
architectural permission. A newly demonstrated incompatible requirement should be
reported with its exact owner/property and alternatives, while independent work
continues. Root remains sole canonical source/index/refs writer. The G checkout,
main/integration and historical B198/B59 are outside this work.

## 10. Required behavioral acceptance signals

These are future implementation checks, not tests performed by this review.

| Boundary | Positive and adversarial/removal signal |
|---|---|
| Grant | Two real registered children with disjoint private writes; original four parent paths unchanged. Missing/forged issuer, wrong run/tenant/attempt, wider child spec, expired/revoked policy and changed implementation refuse before work. Remove admission while retaining names/markers: unchanged negative fails. |
| Input/alias | Valid mapped input succeeds; managed undeclared/secret read and parent/sibling mutable alias mutation refuse. Captured ambient Python read is either prevented by a proven stronger profile or explicitly demonstrates why the trusted receipt is not isolation evidence. |
| Invocation | Child basis resolves to actual child and root lineage, not the parent's alias/basis. Registry replacement, bound-parameter substitution and wrong selected profile refuse. Transitive/deployment evidence retains its honest coverage. |
| Effects/release | Real child artifact with otherwise valid tenant/surface attributes is unreadable by generic content/download before release and after cancellation. Test a frontier referencing one permitted artifact and one unreleased sibling, and same blob under another profile. Remove the release gate: the unchanged test catches actual bytes escaping. |
| Lifecycle | Deterministic barriers around effect admission, revocation, write acknowledgement and publication; crash/restart and lost acknowledgement reconcile actual committed state. Late/duplicate return and handle reuse cannot issue a new success/release. Do not assert rollback of a pre-admitted operation. |
| Cache | Warm the enclosing parent cache, revoke the child grant without changing input/node bytes, invoke again. No cache/recovery path bypasses admission; removing the common check makes the negative fail. |
| Capacity/cost | Capacity one plus nested child completes or gives a bounded refusal without deadlock. Nearly exhausted budget, two racing reservations and retry after charge-ack loss do not renew budget or charge twice. |
| Entry parity | Exercise the actual sync/async-host route. Unsupported async/remote/nested entry refuses before work. Supported entries use the same owner semantics; transport identity alone does not grant parity. |
| Real comparison | Preserve all three exact R102 selectors: actual hierarchical planner/result, target-authorization, fresh/cold reader, audit, adversarial and removal assertions. Passing a toy child test is not this proof. Genuine causal/calibration/source refusals remain distinct from execution authorization and cannot be fabricated away. |

## 11. Review outcome, limitations and prior art

Two code reviewers inspected independent owner/trust/lifecycle aspects; a third
researched primary sources. A second red-team pass on the proposed ruling found
two acceptance-critical refinements now included: enclosing parent cache bypass
and the resolved artifact closure beyond the four fields. I independently read the
source seams and reviewed the resulting decision. This is architecture review, not
fresh runtime evidence or G code acceptance.

The packet's new issuer/read/effect capability remains unimplemented at the pin.
Existing restricted RunContext, attempt fencing and sub-workflow are real reuse
assets. The missing complete protected-isolation chain is `absent/unallocated` in
this proposed scope; invocation/release integration and its tests remain
`bridge_missing`/`verification_missing`/`semantic_test_missing`. This is not an
assertion that the whole repository lacks every isolation facility.

Pattern pass: same authority/effect class deeper at cache, alias and artifact
readers (P05/P31/P37/P38/P40); distinct resource-conservation concern (P13).
Target: one appointed invocation admission, existing child execution, verified
managed journal and one fenced release consumer, with honest profile limitations.

Primary-source comparisons support the design principles, not PolicyOS correctness:

- [Temporal child workflows](https://docs.temporal.io/child-workflows) distinguish
  child execution from parent lifetime and advise against a new child workflow
  solely for code organization. This supports extending the existing engine rather
  than installing another workflow system.
- [Temporal MCP activity semantics](https://docs.temporal.io/develop/python/integrations/mcp)
  document retries and cancellation/timeout limits. Our inference is to separate
  completion from present permission and fence output acceptance; cancellation is
  not an external-effect rollback guarantee.
- [WASI filesystem capabilities](https://github.com/WebAssembly/WASI/blob/main/proposals/filesystem/imports.md)
  illustrate host-enforced descriptor-relative access. They motivate explicit
  resource handles, but do not turn Python adapters into equivalent isolation or
  require a WASM rewrite of PolicyOS.

No product source, tests, configuration, index, refs, environments or production
data were modified by this review. This new decision document is the only output;
the executor owns its subsequent tracked preservation and implementation.
