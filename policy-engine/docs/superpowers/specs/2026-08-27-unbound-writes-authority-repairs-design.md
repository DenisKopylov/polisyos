# Unbound Writes Authority Repairs — Revised Design for Approval

## Authority and source freeze

This spec records the 2026-08-27 corrected design for branch
`codex/unbound-writes`, attached in its own worktree at source freeze
`2525da7306d329ae28fa394690e1c39133eb0d55`. Fabric authority and the timing
repair retain their approval. The case-record mechanism remains frozen until
this revision's WorkspaceLoop seam is accepted; no case-record implementation
was started while re-establishing it.

The lane is local-only: no push, merge, or rebase. It must not modify
`apps/runtime-dashboard/`, `architecture/atlas_surfaces/`,
`docs/plans/active/DEBT-REGISTER.md`, or
`tools/quality/validation/check_debt_ledger.py`. Architecture synchronization,
if needed, uses `guardrails sync --skip-deep-import-baseline`; the deep-import
baseline may change only by explicit enumeration.

The widening ledger remains at 2 of 4 rounds. The Fabric write API is the
already-approved new owner surface (round 1). The governed WorkspaceLoop S2
operation plus run/case/tenant binding is the already-approved case mechanism
(round 2); the correction replaces its invalid Scientist supplier without
buying another round. Exporting `WorldMaterializationPolicy`, completing the
conditional facade behavior, wiring the existing HTTP route to the governed
operation, adding the timing-catalog row, and removing forbidden edges consume
no further round. At every commit boundary the ledger records what each
standing round bought, which row it cleared, and whether any round was
withdrawn.

## Pattern pass

The load-bearing failures are `P05` (owner bypass and authority leak), `P01`
and `P02` (a writer with no production bridge), `P07` (unreplayable identity),
`P29` (marker-only proof), `P31`/`P33` (instance repair or teaching to one
probe), `P32` (trust by shaped bytes), `P35` (sampled denominator), and
`P37`/`P38` (declared or proxy gate predicates). The correct pattern is:

1. one Fabric-owned transactional write waist with a generic owner-bypass
   guard;
2. one production run closure that emits a content-bound case identity and one
   direct run-id resolver, while institutional authority remains explicitly
   absent;
3. one admitted wall-clock observation in the wall-clock timing catalog, with
   the distinct CPU-ceiling finding retained in the execution receipt.

The capability chain at close is producer + strict artifact/binding + run
manifest bridge + direct resolver + run-paper consumer + behavioral negatives.
No builder or global index participates in resolution.

## Fabric world-store authority

### Owner API

Fabric adds an unconditionally importable public `write_world_snapshot` facade
operation with frozen, strict request types for nodes, facts, and snapshot
metadata. The contracts live in a dependency-light Fabric owner module. The
function acquires `SimulationDB`, materialization helpers, and the private
`create_world_snapshot` implementation only when called. If the backend is not
installed, a Fabric-owned typed availability error is raised before a database
or transaction is opened; unexpected `ModuleNotFoundError` exceptions are not
laundered into that expected state.

Unconditional import availability is deliberate. The authority waist must not
disappear in a minimal environment and invite a caller to recover by importing
`SimulationDB` or a deep store module. Runtime supplies only typed values and
paths; Fabric alone opens the database, creates the schema, executes world-table
SQL, verifies consistency, and calls the private snapshot implementation.

The owner transaction performs a deterministic replace of the explicitly
named node/fact identities:

- validate non-empty and unique identities before opening the transaction;
- reject a fact whose subject or non-null target cannot resolve to a node;
- reject a requested node that would have no fact after the replace;
- delete the named facts before the named nodes, insert nodes before facts,
  and never issue an unscoped table delete;
- query the written identities and both orphan directions as postconditions;
- roll back on any failed postcondition;
- invoke `create_world_snapshot` only after the store is committed and proven
  consistent.

Runtime's `_write_fabric_world_snapshot` becomes a request constructor and one
facade call. It imports neither `SimulationDB` nor a deep `fabric.world.*`
module and contains no SQL against `world.*`.

### Conditional facade completion and generic guard

`WorldMaterializationPolicy` is exported from `polisyos.fabric.world` because
the already-exported `ensure_world_materialized` accepts it. The benchmark
imports the policy from that facade, closing the second ARCH004 diagnostic by
completing the published signature rather than broadening the package.

The policy remains conditional while its owner is
`materialize/duckdb.py`: it is present exactly on the same dependency-enabled
branch as `ensure_world_materialized`. It is not duplicated into an
unconditional contracts module. `fabric.data_plane.benchmarks` already needs
that materialization capability and therefore inherits the same declared
condition.

The conditional loader does not retain the facade's current broad
`except ModuleNotFoundError`. It probes the owner-declared backend dependency
identity before importing the materialization surface. An absent expected
backend selects the base branch; once the backend is present, any
`ModuleNotFoundError` raised while importing owner code is re-raised as an
import defect. The write API applies the same rule at lazy acquisition: only
the exact expected backend absence becomes the typed availability error.

The base facade count is environment-conditional and has been independently
re-derived rather than inherited. AST branch analysis finds 36 unique literal
base names and a disjoint 17-name guarded materialization delta. A normal
dependency-present import returns the 53-name union. A forced exception exactly
at the guarded import returns the 36-name base.

That arithmetic exposes a P38 divergence rather than proving a real minimal
surface. A genuine missing dependency currently fails before the guard:
`world.__init__ -> world.store -> store.snapshots -> materialize.sql` and
`SimulationDB`. Blocking either the materialize package or DuckDB exits during
the eager store import; it does not return a 36-symbol facade. The mechanism
must decouple or lazily acquire those snapshot imports so the declared
conditional surface becomes executable rather than syntactic.

No test pins 53 or any post-change total. Let `B` be the source-derived
unconditional names and `M` the source-derived guarded names. The census reports
`|B|`, `|M - B|`, and `|B union M|`, proves uniqueness/disjointness as
applicable, and uses two isolated subprocesses:

- dependency-enabled import must expose exactly `B union M`;
- an actual earliest-dependency block must still import the facade and expose
  exactly `B`.

Both branches require attribute/`__all__` equality. `write_world_snapshot` and
its public request/error types must be in `B`; `WorldMaterializationPolicy`
must be in `M`. The implementation hand-back reports both branches and methods,
not one fixed facade count.

The owner-bypass guard derives its forbidden deep-module set by walking the
actual `polisyos.fabric.world` package tree. It derives owned SQL targets from
the Fabric schema's `CREATE TABLE` statements, then AST-scans every production
module outside the owner package. It therefore fails on any external deep
world import or mutating SQL statement against a Fabric-owned world table
without enumerating today's module or table names. Its source analysis does not
import the optional facade branch. A separate complete census proves zero
Runtime SQL against `world.*`.

Behavioral falsifiers prove that an external caller reaching the store without
the facade fails the guard, and that a write leaving either a fact or a node
orphaned rolls back and emits no snapshot.

## Run-bound S2 DesignRecord

### Current entry-point census and ruling

`WorkflowRunRequest` is strict and has no top-level `workflow_id`. Its `params`
member is intentionally arbitrary, so a nested `params["workflow_id"]` is
accepted, but the control service does not dispatch on it. Filesystem and
Git-tracked walks agree on 14 Python files below
`runtime/http/services/control`; both literal and AST-name censuses find zero
`workflow_id` occurrences in that denominator.

There is a technical distinction that the repaired design keeps visible.
`control_plane_transition="legacy_shadow"` forwards the complete params object
to Scientist, and Scientist's selector does read `params["workflow_id"]`.
A real-route probe selected `scientist_policy_design`. That proves legacy
reachability, not governed admission: the path is explicitly stamped
`legacy_shadow` and goes around the WorkspaceLoop authority waist. It cannot
close this row.

The governed path currently reads `control_plane_transition`, then only
`slice0_fixture_id`, and invokes `WorkspaceLoop.run_control_plane_fixture`.
Static declaration enumeration and runtime registry materialization agree on
a 15-class GY operation vocabulary and nine WorkspaceLoop registrations: five
executable registrations and four non-executable stubs.
Only `BIND`, `ESTIMATE`, and `VERIFY` are active in the fixed Slice-0
trajectory; `DECOMPOSE` and `COMPOSE` are executable outside that trajectory;
`DISCOVER`, `ACQUIRE`, `REFINE`, and `LOWER` remain fail-closed stubs. No S2
operation is admitted.

`WorkspaceLoop.run_intent(DesignProblem)` is a separate Phase-2 method. A text
call census and a complete AST call census over identical Git/filesystem sets
of 2,600 `src/**/*.py` files agree that it has zero production callers; the
same census finds one `WorkspaceLoop` construction, one
`run_control_plane_fixture` call, and zero `persist_s2_design_search_run`
calls. Its current executor admits causal evaluation and normative
arbitration aliases, not S2 design search. The production-module occurrence of
`run_s2_shadow_design_loop` in `design_generation.py` constructs unseen-shape
strangle probes, discards their outputs, and carries no request case, run,
tenant, or persistence. It is verification, not the missing producer bridge.

Therefore the pinned tree has no governed production supplier for
`layer2_s2_design_search_input`; the honest current state is `bridge_missing`.
The Scientist terminal-node design is withdrawn. The original row is not
closed by this census. It can close only if the mechanism below makes the
existing HTTP route an actual WorkspaceLoop caller and the HTTP-level populated
path passes; otherwise the hand-back re-types the residual caller gap rather
than claiming closure.

### Governed WorkspaceLoop S2 operation and supplier

The existing `POST /api/v1/control/runs` route is the transport supplier, but
only after a new explicit governed dispatch lands. A populated request remains
within the existing arbitrary `WorkflowRunRequest.params` member and carries:

- `params["control_plane_transition"]="workspace_loop"`;
- `params["workspace_operation_id"]="phase2.refine.layer2_s2_design_search"`;
- a strict `params["layer2_s2_design_search_input"]` object.

The transition recognizes that exact operation identity, validates the S2
object with the existing strict PDC model, and calls a WorkspaceLoop method. It
does not inspect `workflow_id`, build an `ExperimentState`, construct a
Scientist node, or use `legacy_shadow`.

The WorkspaceLoop registry replaces the existing non-executable REFINE stub
with one concrete executable Phase-2 S2 `REFINE` registration whose discovery
evidence points to the existing PDC producer and persistence owner. It does not
add a competing REFINE. The registry therefore remains nine entries, moves
from five to six executable registrations, and keeps the active seed set at
three. REFINE remains excluded from `ACTIVE_WORKSPACE_OPERATIONS` and cannot
enter the fixed Slice-0 trajectory. The operation records its applicability,
invocation, ledger event, artifact envelope, and candidate-only authority
transform before it may emit outputs. This is the correct place for the S2
step: inside the owner waist and outside the three-operation Slice-0 seed path.

Input ownership is split without ambiguity. The request supplies the strict
design-search facts. The server supplies the control job's run ID. The
authenticated principal supplies tenant/cell identity through the ambient job
scope. No identity field from request params is admitted as run or tenant
authority.

### Tenant fail-close

The populated tenant branch is real but conditional. `_attach_job_actor_scope`
copies a non-empty tenant/cell from the server-resolved execution policy into
the durable job; `_job_tenant_scope` restores it before dispatch. When tenant
is absent, however, `_job_tenant_scope` currently yields `nullcontext()` and the
worker proceeds unscoped. A real-route probe with an authenticated principal
whose tenant was `None` returned `200/accepted` and reached worker execution
with ambient tenant and cell both absent.

The S2 WorkspaceLoop operation therefore calls the existing strict
`get_current_tenant_id()` before executing the S2 loop or opening any
persistence path. `get_current_tenant_id()` raises the existing
`TenantContextNotSetError` with a message only; it does not own the public
control code. `workspace_loop_transition.py` must catch that exception before
the current broad WorkspaceLoop catch and translate it into a typed failed
progress packet. It must not fall through to
`workspace_loop_failed_non_authority` or generic `control_job_failed`.

The translated `ControlFailureEnvelope` is frozen as:

- `code="run_bound_design_record_tenant_scope_missing"`;
- `layer="pdc.gy"` and `phase="s2_design_search_persist"`;
- message `Run-bound DesignRecord persistence requires a verified ambient tenant scope.`;
- `retryable=false`;
- next action `Re-launch under an authenticated principal with a verified tenant scope; tenant_id is not caller-supplied.`;
- the exact server run/job identities and empty `artifact_refs`.

The job has `state="failed"`, `runtime_state="blocked"`, and
`authority_result="repair_required"`. A named strict
`RunBoundDesignRecordTenantNonReceipt` is owned by
`workspace_loop_transition.py` and carried at
`progress["run_bound_design_record_nonreceipt"]`; it uses
`ConfigDict(extra="forbid")`, and its complete frozen fields are:

- `kind="run_bound_design_record_nonreceipt"`;
- `status="not_established"`;
- `missing_authority="tenant_identity"`;
- `authority_state="absent/unallocated"`;
- `owner_route="runtime.authenticated_principal.tenant_id"`;
- `denied_uses=("s2_design_search_execution", "design_record_persistence",
  "search_ledger_persistence", "run_case_tenant_binding")` in that canonical
  order.

The operation never substitutes a tenant, and specifically never borrows
`tenant-unknown`, which remains diagnostic-event vocabulary only.

The no-tenant falsifier launches through the real HTTP route, dispatches the
real queued worker, and reads the job. Its arbitrary params deliberately carry
forged `tenant_id="tenant-unknown"` and `cell_id="forged-cell"` siblings while
the authenticated principal has no tenant. The test parses the returned member
through `RunBoundDesignRecordTenantNonReceipt`, requires the exact typed
refusal, and proves with a call spy that the S2 producer was never invoked. It
also proves that no new S2 DesignRecord, SearchLedger, or binding kind was
persisted, that no binding appears in job progress or a run manifest, and that
no authority-bearing S2 artifact contains `tenant-unknown` or the forged cell.

### Producer, binding, and direct resolver

On the populated tenant branch, WorkspaceLoop starts a Core `RunContext` with
the server control run ID and the exact ambient tenant/cell. It executes the
existing deterministic S2 producer and calls the extended PDC persistence
function. PDC owns one canonical strict `RunBoundDesignRecordBinding` artifact
containing the DesignRecord CAS reference and content digest, record and case
identity, schema and producer identity, and exact Core run/tenant/cell identity.
Its artifact identity is frozen as
`kind="policyos.pdc.run_bound_design_record_binding"`,
`media_type="application/json"`,
`schema.name="policyos.pdc.run_bound_design_record_binding"`, and
`schema.version="policyos.pdc.run_bound_design_record_binding.v1"`; the model
carries that literal schema version, and resolution requires exact sidecar
equality.
The binding also carries the exact SearchLedger CAS reference, content digest,
and ledger identity. The persistence call writes the DesignRecord and
SearchLedger first, content-binds both in the binding, writes the binding, and
returns all three references; the WorkspaceLoop operation adds all three as
outputs before that same `RunContext` finalizes. The binding's `case_id` is not
self-attestation: resolution verifies the bound ledger bytes and requires the
ledger's `case_id` and `ledger_id` to equal the binding.

Runtime does not define a second binding schema. The existing public
`RunPaperDesignRecordBinding` name becomes an exact alias of PDC's exported
`RunBoundDesignRecordBinding`, preserving the consumer name while keeping one
field set and one validator owner. Runtime's distinct
`RunPaperCaseSourceVerification` remains a projection-verifier receipt and
gains `bound_cell_id: str | None`.

Resolution follows the run's own closure chain:

`run_id -> exact deterministic run directory under the trusted configured
core_runs_root -> owner-bound RUN_STARTED plus one unambiguous terminal
RUN_FINALIZED event -> core.run_manifest CAS reference -> verified manifest ->
exactly one binding output -> content-verified DesignRecord`.

`RunContext.finalize()` does not write a manifest file in the run directory: it
persists the manifest to CAS and makes that reference authoritative only through
the terminal trace event. One shared Runtime adapter helper derives a
normalized direct child from the trusted configured `core_runs_root` and a run
ID and rejects traversal. The transition uses that helper and passes the result
as the explicit `run_dir` to `RunContext.start`; this joins the producer to the
same root used by resolution even when `core_runs_root` differs from the CAS
default. The resolver receives that trusted root as constructor configuration
and derives the directory itself; a caller-supplied directory or a
run-service-resolved manifest is never discovery authority.

The Core-run adapter is factored so both its existing `load_core_run` path and
the direct resolver use one trace parser. The direct form requires an exact
run-ID match, an owner-bound `RUN_STARTED`, exactly one non-conflicted terminal
`RUN_FINALIZED`, and exactly one `core.run_manifest` reference on that event.
It then applies `load_bound_terminal_manifest` to that reference and verifies
its CAS bytes, sidecar metadata, schema, producer, lineage, and exact
run/tenant/cell identity. `load_bound_terminal_manifest` alone is not treated
as trace proof.

That strict trace resolution returns one terminal source object containing the
manifest reference, verified manifest, and trace-derived run facts. The
`RunPaperProjectionService` no longer accepts a run index: the same source
object feeds `RunPaperRun`, `RunPaperSourceBinding`, artifact links, replay
pins, and case-record resolution. Route-level authorization may still consult
the pre-existing run index, but an index record cannot contribute a path,
manifest reference, manifest bytes, or projection fact. If its same-owner
manifest differs from the trace-derived reference, the trace-derived source is
the only admissible projection source rather than a second manifest silently
entering the packet.

The manifest must contain exactly one binding output and the exact
DesignRecord and SearchLedger references named by that binding. The resolver
verifies all three sidecars and byte streams, requires both referenced digests
to match, parses the ledger, and compares run, tenant, cell, case, ledger,
record, schema, producer, and content identity. Record discovery may not query
a builder, a by-kind/global artifact index, the run index, or a CAS-wide scan.
Bytes that exist only through any of those decoys are rejected.

The canonical PDC binding carries `cell_id: str | None`, and
`RunPaperCaseSourceVerification` carries `bound_cell_id: str | None`, so
verification binds the same complete owner scope as the Core manifest. A
non-null cell cannot be erased, and a null cell cannot be replaced by a caller
value.

The run-paper projection renders the resolved DesignRecord and binding but
does not construct `AvailableRunPaperCase`. Instead it emits a strict
`AuthorityAbstainingRunPaperCase` with the unique discriminated-union tag
`availability="record_available_authority_abstaining"` and
`authority_projection="abstained"`. Its grounding, admission, and promotion
fields are three separately typed non-receipts, each naming its exact authority
role, `status="not_established"`, `authority_state="absent/unallocated"`, its
institutional owner route, and its complete denied-use tuple. The record remains
inspectable and demonstrable; only the authority-bearing projection abstains.
No shaped substitute, shared verifier, blank, or generic `unavailable` value
is accepted.

One shared bound-case validator applies to both the abstaining arm and the
future `AvailableRunPaperCase`. It binds case and record identity, and requires
the binding's run, tenant, and cell to equal `RunPaperRun` exactly, including
`None` versus non-null cell. The available arm's source-verification comparison
also includes `bound_cell_id`; the abstaining arm does not fabricate source
verification for absent authorities.

The positive closure test posts the populated request through the authenticated
route, dispatches the worker, resolves only from the returned run ID, and
asserts the request case plus authenticated tenant/cell on the binding and
manifest. Negatives hold the DesignRecord hash constant while substituting the
run binding; hold the same run, tenant, and bytes while substituting the cell
binding; introduce correct bytes discoverable only through a builder/global
index decoy; supply a caller-selected run directory; remove the terminal event;
owner-mismatch its `RUN_STARTED`; add conflicting terminal manifest references;
inject a same-owner but different run-index manifest; remove the run's binding
output; or keep the DesignRecord bytes while substituting a ledger whose case
differs. The packet source, replay pins, links, run projection, and case binding
must all name the one trace-derived manifest.

A parameterized CAS falsifier derives the four resolved roles from the
resolver contract—terminal manifest, binding, DesignRecord, and SearchLedger—
and, one role at a time, makes `store.verify()` fail, corrupts the referenced
bytes, or substitutes sidecar kind/media/schema/producer metadata while keeping
the other roles correct. Every matrix member fails closed. Together these
negatives prove resolution checks authority and content, not merely addresses
or parseable bytes.

### Re-derived source scope

The governed seam removes every proposed Scientist source edit. Honest closure
uses these mechanism paths:

- `src/polisyos/fabric/world/__init__.py`, a dependency-light
  `src/polisyos/fabric/world/write.py` owner, and
  `src/polisyos/fabric/world/store/__init__.py` to make snapshot imports lazy
  enough that the base facade branch is actually importable;
- `src/polisyos/runtime/quality/data_state_substrate.py` for the single typed
  facade call, with its current deep import and SQL removed;
- `src/polisyos/pdc/_impl/layer2_design_search.py` and
  `src/polisyos/pdc/__init__.py` for the canonical binding contract and extended
  persistence facade;
- `src/polisyos/runtime/quality/workspace/loop.py` plus the focused
  `src/polisyos/runtime/quality/workspace/s2_design_search_operation.py`
  adapter that implements the governed REFINE operation;
- `src/polisyos/runtime/http/services/control/workspace_loop_transition.py` for
  strict governed dispatch and typed job projection;
- `src/polisyos/runtime/http/services/run_paper_contracts.py`,
  `src/polisyos/runtime/http/services/run_paper_projection.py`, and the focused
  `src/polisyos/runtime/http/services/run_paper_case_record.py` resolver;
- `src/polisyos/runtime/http/services/adapters/core_run.py` to own the shared
  safe run-directory derivation and exact terminal-trace proof used by producer
  and resolver;
- `src/polisyos/runtime/http/routes/runs.py` and
  `src/polisyos/runtime/http/routes/governed_projections.py` to pass the
  already-configured trusted `core_runs_root` into every
  `RunPaperProjectionService` construction;
- `src/polisyos/fabric/data_plane/benchmarks.py` for the required facade import;
- `tools/quality/timing_budgets.json` for the one wall-clock lane.

No change is planned to `run_lifecycle.py`: its existing actor-scope transport
and configured `_core_runs_root` are consumed and its absent branch is fenced
at the S2 owner. No Scientist node, workflow spec, builder, selection,
executor, or run-index implementation is in the write set. The existing
run index continues to serve its pre-existing listing and route-authorization
functions, but it is not passed to `RunPaperProjectionService` and cannot
supply the packet's directory, manifest, binding, or projection facts.

The generic Fabric authority check may add one focused repository-quality
validator/test companion outside production source; that verification path is
declared before implementation and is not a widening mechanism. The
design/spec, implementation plan, execution journal, timing evidence, and tests
are mandatory P39 companions rather than mechanism paths. Before each edit,
current Git state will be checked for unexpected changes; any overlap with a
live lane stops the work.

## Corrected timing repair

The timing catalog is a wall-clock catalog. `tools/lib/timing.py` measures
`time.perf_counter()` duration in milliseconds. The historical 264.30 value
is aggregate CPU (`user + sys`) in core-seconds and cannot populate
`samples_ms`. The register's old literal closure command is therefore
defective: it requires a CPU total in a wall-clock field and cites the debt row
as if registration were measurement evidence. It will not be made green.

Healthy exit 0 is derived from the epoch validator's own behavior, not from its
missing `TIMING_HEALTHY_TERMINAL_EXIT_CODES` declaration. In
`corrupt-field-drift-check` mode, it creates an issue only for a row whose
`rejected` value is false, separately rejects a case-denominator mismatch,
sets `status="pass"` exactly when the issue set is empty, and maps pass to exit
0. Therefore all corruptions detected over the complete denominator yield
exit 0; exit 1 means a validator failure and is not a timing sample.

Two complete-set derivations agree that 8 of 429 Python modules under `tools/`
declare `TIMING_HEALTHY_TERMINAL_EXIT_CODES`; Git-object and filesystem-AST
path denominators are identical. All eight declare exit 1 healthy for the same
mode name. The Depth-N sibling demonstrates the opposite polarity in code: no
surviving corruption produces its local `status="fail"`, which maps to exit 1.
If the epoch tool followed that convention, its absent override and the shared
default 0 would admit defects and reject healthy runs. The absence is therefore
only a compatibility fact, never the admission proof.

After source freeze and local environment provisioning, the exact lane runs
once, serialized. Before launch the journal declares a 600 core-second CPU
ceiling, derived above the valid 264.30 core-second observation, and records an
`uptime` pair. `/usr/bin/time -p` records wall, user, and sys; the tool's own
timing log records `perf_counter` wall milliseconds and direct exit status.
A killed/signalled run is a non-receipt and is not re-run merely to obtain a
number.

At this revised-spec checkpoint the expensive sample has not been launched, so
its observed exit is explicitly `pending`, not inferred as 0. The once-only
implementation run is admissible only if the report is pass and the directly
captured process exit is 0. An observed exit 1 stops the timing repair as a
validator finding; its wall time and CPU total do not enter the catalog.

The exact raw `ToolRunRecord` is promoted under
`docs/superpowers/timing-evidence/` using the README's preserved-raw JSONL
shape. The execution journal records both measures and explicitly corrects the
old 180 -> 264.30 core-second under-derivation in the CPU-ceiling lane. The
catalog adds one new row using only the newly observed wall-clock sample,
`declared_healthy_terminal:v1`, and `serialized`. With one sample, the loader
must report `budget_basis=max_observed`, `ceiling_is_declared=False`,
`measured_p95_ms=sample`, and `recommended_timeout_ms=2*sample`.

The corrected closure command will resolve the sole timing row, parse its
source evidence's preserved raw record, assert tool/mode/regime/healthy exit,
bind `samples_ms` exactly to that record's wall-clock `duration_ms`, and assert
the derived p95/timeout/basis. It will also assert that the promoted evidence
distinguishes wall time from the separately recorded `user + sys` CPU total.

## Verification and hand-back

Use TDD: write each behavioral negative first, observe the intended red, then
make the smallest owner-bound repair. Run only blast-radius tests, the timing
catalog recomputation tests, the architecture validators, Ruff on changed
Python, and the three requested repository predicates. Do not run full pytest.

Final evidence reports separately:

1. import linter, with ARCH004 reduced from 2 to 0 and ARCH001/ARCH002/ARCH006
   unchanged;
2. release guardrail, exit 0 with zero creep;
3. package gate, independently red with its complete forbidden set unchanged,
   after checking ignored `tmp/`, `production_data/`, and `runs/` effects.

Every set-level count is derived twice. The hand-back includes the three row
texts for the register owner to apply, the corrected timing closure command,
the promoted evidence path, the entry-point census, the facade count methods,
the zero-Runtime-SQL census, the falsifiers, and the widening ledger. The debt
register itself is never edited.
