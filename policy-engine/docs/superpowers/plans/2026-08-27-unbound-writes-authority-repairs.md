# Unbound Writes Authority Repairs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the Fabric world-store owner bypass, make the existing production S2 design-search producer persist a directly run-resolvable case record, and register one honestly measured wall-clock timing lane.

**Architecture:** Fabric gains one dependency-light public write waist whose backend is acquired lazily and whose transaction owns world-table replacement and consistency. The governed WorkspaceLoop adds a distinct Phase-2 S2 REFINE operation, persists one PDC-owned binding into the Core run manifest, and resolves the packet only through the run's terminal trace and verified CAS chain. Timing remains a separate wall-clock catalog repair backed by one serialized, once-only run and a byte-preserved evidence record.

**Tech Stack:** Python 3.14, Pydantic v2, DuckDB, `FileSystemCAS`, Core `RunContext`, FastAPI, pytest, Ruff, PolicyOS architecture and timing validators.

**Spec:** `docs/superpowers/specs/2026-08-27-unbound-writes-authority-repairs-design.md`

## Global Constraints

- Work only in the attached `codex/unbound-writes` worktree. Do not push, open a PR, rebase, force-push, reset, or stash.
- Preserve `slice0.refine.stub` byte-for-byte: it remains registered, `executable=False`, with `fail_closed_reason="GY-C2 owns REFINE after spine-rot repair."`.
- Add only `phase2.refine.layer2_s2_design_search`; never route the Slice-0 missing-bounds deviation through it.
- Do not edit `src/polisyos/core/contracts/control.py`, `run_lifecycle.py`, Scientist, the run-index implementation, `docs/plans/active/DEBT-REGISTER.md`, `docs/plans/active/LEDGER.md`, `tools/quality/validation/check_debt_ledger.py`, the deep-import baseline, or another slice's evidence/snapshots/visual specs.
- Continue the widening ledger at 2/4: round 1 is the Fabric write owner surface; round 2 is the governed S2 bridge and run binding. These rounds stand. A correction, an owner-edge removal, an already-published export, a consumer wire, a test, or a mandatory P39 record consumes no new round.
- At every commit boundary print: rounds consumed; what each bought; which row the boundary clears; whether each round stands or was withdrawn. Stop before a fifth round; if the count reaches 4/4, classify any remainder.
- Before every path coordinate, run `git rev-parse --show-prefix` and interpret repository-root paths relative to that prefix exactly once.
- Use red-first behavioral tests and record the intended missing property. Use targeted tests only; never run full pytest.
- Read process exit codes directly before parsing or piping output. Derive every set-level count twice and report disagreements without averaging or silently reconciling them.
- Run the epoch corrupt-field validator exactly once. Before launch record a 600 core-second (`user + sys`) ceiling and an uptime pair. Only a completed exit 0/pass run is an admissible wall-clock sample.
- Commit each clean cluster with its red/green receipts in the commit message and verify branch attachment immediately before committing.

---

### Task 1: Fabric-owned world snapshot write waist

**Files:**
- Create: `src/polisyos/fabric/world/write.py`
- Modify: `src/polisyos/fabric/world/__init__.py`
- Modify: `src/polisyos/fabric/world/store/__init__.py`
- Modify: `src/polisyos/fabric/data_plane/benchmarks.py`
- Modify: `src/polisyos/runtime/quality/data_state_substrate.py`
- Create: `tests/unit/fabric/test_world_write.py`
- Create: `tests/repo_quality/architecture/test_fabric_world_write_waist.py`
- Modify: `tests/unit/fabric/test_world_store.py`
- Modify: `tests/unit/runtime/quality/test_world_model_record.py`

**Interfaces:**
- Produces unconditional strict DTOs `WorldSnapshotNodeWrite`, `WorldSnapshotFactWrite`, and `WorldSnapshotWriteRequest`, the typed `WorldSnapshotBackendUnavailable`, and `write_world_snapshot(db_path: Path, request: WorldSnapshotWriteRequest) -> WorldSnapshotRecord` from `polisyos.fabric.world`.
- Preserves the 36 source-derived legacy base exports and adds the new unconditional write exports as a separately reported base delta. The materialization delta remains source-derived and conditional; it gains `WorldMaterializationPolicy` beside `ensure_world_materialized`.
- Acquires `duckdb`, `SimulationDB`, `ensure_world_schema`, and private `create_world_snapshot` only inside `write_world_snapshot`. Only absence of the exact `duckdb` backend is translated into `WorldSnapshotBackendUnavailable`; an internal import defect propagates.
- Consumes the existing Fabric schema in `src/polisyos/fabric/world/ddl/duckdb_world.sql` as the SQL-target source of truth. The forbidden import set is the union of `write.py`'s actual private `fabric.world` imports, their on-disk parents below the public world facade and descendants, with every Fabric module whose AST contains a mutating statement against a derived owned table. Generic `SimulationDB` acquisition remains admitted unless the same consumer mutates an owned world table; read/event modules are not forbidden merely because they are beneath `fabric.world`.

- [ ] **Step 1: Write strict-contract and rollback falsifiers**

Add tests with the following contract shape and cases:

```python
request = WorldSnapshotWriteRequest(
    snapshot_root=tmp_path / "snapshots",
    snapshot_id="snapshot-1",
    branch_name="observed",
    as_of_valid_time="2026-05-01T00:00:00+00:00",
    as_of_tx_time="2026-05-01T00:00:00+00:00",
    provenance={"producer": "test"},
    nodes=(
        WorldSnapshotNodeWrite(
            node_id="node-1",
            kind="data_state",
            label="node one",
            artifact_id="sha256:" + "1" * 64,
            props_ref=None,
        ),
    ),
    facts=(
        WorldSnapshotFactWrite(
            fact_id="fact-1",
            schema_version="1.0",
            subject_id="node-1",
            predicate_id="data_state.payload_hash",
            object_value="sha256:" + "1" * 64,
            target_id=None,
            valid_time="2026-05-01T00:00:00Z",
            tx_time="2026-05-01T00:00:00Z",
            provenance_json={"producer": "test"},
            trust_json=None,
            legal_json=None,
            segment_id="seg-1",
        ),
    ),
)
```

Require `extra="forbid"`, frozen instances, non-empty/unique node and fact IDs, subject and target resolution, and at least one fact per requested node. Monkeypatch the postcondition query separately so a fact is orphaned and so a node is orphaned; both calls must raise, roll back all managed-row changes, and make the snapshot spy remain at zero calls. Add a positive replacement test proving unrelated rows survive and the private snapshot spy runs exactly once after `COMMIT`.

- [ ] **Step 2: Write the generic owner-bypass guard RED**

In the repository-quality test, implement source-derived helpers with these exact responsibilities:

```python
def world_write_private_modules(src_root: Path, owner_path: Path) -> frozenset[str]:
    """Derive private backend imports, descendants, and owned-table writers."""


def world_owned_tables(ddl_path: Path) -> frozenset[str]:
    """Derive qualified table names from every CREATE TABLE statement."""


def external_world_write_violations(src_root: Path) -> tuple[str, ...]:
    """Return sorted deep-import and mutating-owned-table AST findings."""
```

`world_write_private_modules` parses the real owner module's private `fabric.world` imports, walks their actual parents below the public world facade and package descendants, then unions every Fabric module whose AST contains a mutating statement against a DDL-derived owned table. `world_owned_tables` parses every `CREATE TABLE` target in the actual DuckDB DDL. The AST scan visits every production Python module outside the owner package and rejects an import from any derived world-store-private module and any mutating SQL literal (`INSERT`, `UPDATE`, `DELETE`, `MERGE`, `CREATE`, `ALTER`, `DROP`, or `TRUNCATE`) whose qualified target is in the derived table set. Mutant tests add a fourth owner package descendant, a lazy parent-package export, a generic backend plus owned-table mutation, and a fourth DDL table without modifying an enumerated string list and require all to be detected. The live-tree assertion is red on Runtime's current store imports and SQL while legitimate `fabric.world.events` readers and generic database acquisition remain admitted.

- [ ] **Step 3: Run the Fabric reds and record the intended failures**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/fabric/test_world_write.py \
  tests/repo_quality/architecture/test_fabric_world_write_waist.py \
  tests/unit/runtime/quality/test_world_model_record.py -q
```

Expected red: the public DTO/API names do not exist, Runtime is reported as a deep-import/owned-table writer, and neither orphan rollback guarantee exists.

- [ ] **Step 4: Implement the dependency-light owner contracts and transaction**

Define strict frozen Pydantic DTOs and the public error in `write.py`. `write_world_snapshot` must validate the request before backend acquisition, probe `importlib.util.find_spec("duckdb")`, and then lazily import the exact Fabric backend helpers. Within one explicit `BEGIN`/`ROLLBACK`/`COMMIT` transaction it must:

```python
managed_fact_ids = tuple(fact.fact_id for fact in request.facts)
managed_node_ids = tuple(node.node_id for node in request.nodes)
# parameterized DELETE only for managed IDs
# insert nodes before facts
# compare exact fetched managed rows to the request
# query facts with missing subjects or non-null missing targets
# query requested nodes having no fact
```

Any mismatch raises a Fabric-owned validation error and rolls back. Commit precedes the lazy private `create_world_snapshot` call. The snapshot call receives exactly the request's root/id/branch/times/provenance and returns its `WorldSnapshotRecord`.

- [ ] **Step 5: Make both facade availability branches executable**

Remove the eager snapshot-module import from `world.store` and expose its existing snapshot names lazily through module `__getattr__`, preserving its declared store surface when the backend exists. In the world facade:

```python
_DUCKDB_AVAILABLE = importlib.util.find_spec("duckdb") is not None
if _DUCKDB_AVAILABLE:
    from polisyos.fabric.world.materialize import (
        MergeStrategy,
        WorldMaterializationPolicy,
        ensure_world_materialized,
    )
```

Do not catch a broad `ModuleNotFoundError` after a successful backend probe. Export the write contracts unconditionally. Export `WorldMaterializationPolicy` only in the materialization delta. Add subprocess tests that derive `B` and `M` from the facade AST, then prove attribute/`__all__` equality for a normal import and an earliest real `duckdb` block. Report `|legacy B|=36`, the new unconditional write delta, `|M-B|`, and the union rather than pinning one post-change total.

- [ ] **Step 6: Rewire Runtime and the benchmark through the facade**

Build the existing data-state node and two facts as the strict DTOs and replace all database/schema/SQL/private snapshot work with:

```python
write_world_snapshot(
    db_path,
    WorldSnapshotWriteRequest(
        snapshot_root=snapshot_root,
        snapshot_id=snapshot_id,
        branch_name="observed",
        as_of_valid_time="2026-05-01T00:00:00+00:00",
        as_of_tx_time="2026-05-01T00:00:00+00:00",
        provenance={"producer": "polisyos.runtime.quality.data_state_substrate"},
        nodes=(world_node,),
        facts=(bound_agent_count_fact, payload_hash_fact),
    ),
)
```

Import `WorldMaterializationPolicy` in `fabric/data_plane/benchmarks.py` from `polisyos.fabric.world`. Do not export or directly consume private `create_world_snapshot` outside the owner.

- [ ] **Step 7: Run focused Fabric green checks and the two independent censuses**

Run the Task 1 pytest command again, then run the normal/blocked facade subprocess census and both a filesystem-AST and Git-object census for Runtime SQL against `world.*`. Both Runtime censuses must report zero. Run Ruff on the changed Python files.

- [ ] **Step 8: Commit the Fabric cluster**

Immediately before commit, verify `git status -sb`, `git symbolic-ref -q HEAD`, and `git rev-parse --show-prefix`; print the 2/4 ledger with round 1 standing and clearing `fabric-world-store-write-authority`, round 2 standing but not yet clearing its row, and no withdrawal. Commit as:

```bash
git commit -m "fix(fabric): own world snapshot replacement" \
  -m "Receipts: Fabric rollback/waist/facade tests green; Runtime world-write census zero. Ledger: 2/4, rounds 1-2 stand."
```

### Task 2: Governed S2 persistence, terminal-trace resolution, and typed abstention

**Files:**
- Modify: `src/polisyos/pdc/_impl/layer2_design_search.py`
- Modify: `src/polisyos/pdc/__init__.py`
- Create: `src/polisyos/runtime/quality/workspace/s2_design_search_operation.py`
- Modify: `src/polisyos/runtime/quality/workspace/loop.py`
- Modify: `src/polisyos/runtime/http/services/control/workspace_loop_transition.py`
- Modify: `src/polisyos/runtime/http/services/adapters/core_run.py`
- Create: `src/polisyos/runtime/http/services/run_paper_case_record.py`
- Modify: `src/polisyos/runtime/http/services/run_paper_contracts.py`
- Modify: `src/polisyos/runtime/http/services/run_paper_projection.py`
- Modify: `src/polisyos/runtime/http/routes/runs.py`
- Modify: `src/polisyos/runtime/http/routes/governed_projections.py`
- Modify: `tests/unit/pdc/test_layer2_s2_design_search.py`
- Modify: `tests/unit/runtime/quality/test_workspace_loop.py`
- Modify: `tests/unit/runtime/quality/test_workspace_workflow_playbook_projection.py`
- Modify: `tests/unit/runtime/http/test_workspace_loop_transition.py`
- Modify: `tests/unit/runtime/http/test_run_paper_api.py`
- Modify: `tests/unit/runtime/http/test_runs_api.py`

**Interfaces:**
- Produces PDC-owned `RunBoundDesignRecordBinding` and `PersistedS2DesignSearchRun`; Runtime's `RunPaperDesignRecordBinding` is an exact alias, not a second model.
- Changes `persist_s2_design_search_run(run, *, store, run_id: str, tenant_id: str, cell_id: str | None) -> PersistedS2DesignSearchRun`. It writes DesignRecord, SearchLedger, then the binding, and returns all three exact refs.
- Produces `derive_core_run_dir(core_runs_root: Path, run_id: str) -> Path` and `load_terminal_core_run_source(*, store, core_runs_root: Path, run_id: str) -> TerminalCoreRunSource` from the Core adapter.
- Produces `RunBoundDesignRecordResolver(store, core_runs_root).resolve(run_id) -> ResolvedRunBoundDesignRecord` without a builder, run index, by-kind lookup, caller-supplied directory, or CAS scan.
- Produces the distinct executable registry ID `phase2.refine.layer2_s2_design_search`; retains `slice0.refine.stub` and all three Slice-0 active operations unchanged.
- Produces strict `RunBoundDesignRecordTenantNonReceipt` at control-job progress and strict `AuthorityAbstainingRunPaperCase` in the run-paper discriminated union.

- [ ] **Step 1: Write PDC binding reds**

Add the strict contracts with these load-bearing fields:

```python
class RunBoundDesignRecordBinding(Layer2ReadinessModel):
    schema_version: Literal["policyos.pdc.run_bound_design_record_binding.v1"]
    binding_id: str
    run_id: str
    tenant_id: str
    cell_id: str | None
    case_id: str
    design_record_ref: artifacts.ArtifactRef
    design_record_record_id: str
    design_record_schema_name: Literal["policyos.layer2_s2.design_record_v0"]
    design_record_schema_version: str
    design_record_content_digest: str
    search_ledger_ref: artifacts.ArtifactRef
    search_ledger_id: str
    search_ledger_content_digest: str
    producer: artifacts.ProducerInfo

class PersistedS2DesignSearchRun(Layer2ReadinessModel):
    design_record_ref: artifacts.ArtifactRef
    search_ledger_ref: artifacts.ArtifactRef
    binding_ref: artifacts.ArtifactRef
    binding: RunBoundDesignRecordBinding
```

The binding validator requires each digest to equal its ref artifact ID, both refs to carry exact kind/media/schema/producer metadata, and non-empty run/case/tenant identity. Tests must hold the DesignRecord bytes/hash constant while changing `run_id`, `tenant_id`, or `cell_id` and show the binding or resolver rejects the substitution. A ledger with a different `case_id` or `ledger_id` must fail even when its bytes and sidecar verify.

- [ ] **Step 2: Write terminal-trace and CAS-matrix reds**

Add tests for the exact chain:

```text
trusted root child -> RUN_STARTED -> one RUN_FINALIZED -> core.run_manifest ref
-> verified manifest -> one binding output -> DesignRecord + SearchLedger
```

Reject traversal run IDs, missing or owner-mismatched `RUN_STARTED`, event-before-start, no terminal, duplicate/conflicting terminal manifest refs, manifest/run/tenant/cell mismatch, zero or multiple binding outputs, and a correct binding discoverable only through a builder/global-index/CAS-scan decoy. Parameterize the four resolved roles—manifest, binding, DesignRecord, SearchLedger—and for each make `store.verify()` fail, corrupt bytes, and substitute sidecar kind/media/schema/producer while keeping the other three roles correct. Every case must raise `RunPaperSourceError`.

- [ ] **Step 3: Write governed-operation and GY-C2 ownership reds**

Assert the registry moves from 9 to 10 registrations and 5 to 6 executable registrations while the exact serialized `slice0.refine.stub` member remains unchanged. Spy on the new operation and drive:

```python
result = WorkspaceLoop().run_intent(
    stable_design_problem.model_copy(update={"force_counterexample": "missing_bounds"})
)
```

Require terminal kind `SEARCH_CEILING_REPAIR_REQUIRED`, the same blocker IDs and playbook trace as the pre-addition fixture, and zero spy calls. Separately require only the exact new ID, an executable REFINE registration, and a valid `Layer2S2DesignSearchInput` to enter the new adapter.

- [ ] **Step 4: Write real-route positive and no-tenant reds**

Use the existing runtime HTTP fixture to post `/api/v1/control/runs` with:

```python
params = {
    "control_plane_transition": "workspace_loop",
    "workspace_operation_id": "phase2.refine.layer2_s2_design_search",
    "layer2_s2_design_search_input": valid_input.model_dump(mode="json"),
}
```

Dispatch the real queued worker, read the job, then GET the run paper using only the returned run ID. The positive principal has a server-authenticated tenant/cell; require the terminal manifest, binding, record, and ledger to carry that exact identity and the requested case.

The negative traverses the same real HTTP route, queue, worker, and job readback, but monkeypatches only `runtime.http.routes.control._get_principal` to return `RuntimePrincipal(subject="tenantless-falsifier", authenticated=True, tenant_id=None, cell_id=None)`. This isolated seam is necessary because the production identity DTO requires a non-empty tenant and fail-closed middleware rejects absent identity before routing; do not weaken either owner. Params additionally forge `tenant_id="tenant-unknown"` and `cell_id="forged-cell"`. Parse `progress["run_bound_design_record_nonreceipt"]` as:

```python
RunBoundDesignRecordTenantNonReceipt(
    kind="run_bound_design_record_nonreceipt",
    status="not_established",
    missing_authority="tenant_identity",
    authority_state="absent/unallocated",
    owner_route="runtime.authenticated_principal.tenant_id",
    denied_uses=(
        "s2_design_search_execution",
        "design_record_persistence",
        "search_ledger_persistence",
        "run_case_tenant_binding",
    ),
)
```

Require failure code `run_bound_design_record_tenant_scope_missing`, job `failed`, runtime `blocked`, authority `repair_required`, zero producer calls, and zero DesignRecord/SearchLedger/binding persistence. No authority artifact or progress member may bind either forged value.

- [ ] **Step 5: Run the case-record reds and record the missing properties**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/pdc/test_layer2_s2_design_search.py \
  tests/unit/runtime/quality/test_workspace_loop.py \
  tests/unit/runtime/quality/test_workspace_workflow_playbook_projection.py \
  tests/unit/runtime/http/test_workspace_loop_transition.py \
  tests/unit/runtime/http/test_run_paper_api.py -q
```

Expected red: no binding artifact, no exact operation registration/dispatch, no typed tenant non-receipt, and run-paper discovery still depends on the run index rather than terminal trace.

- [ ] **Step 6: Implement the PDC binding and direct Core-run source**

Persist canonical DesignRecord and SearchLedger bytes first, build the binding from their returned refs and the server/ambient identity, then persist it with:

```python
PutOptions(
    kind="policyos.pdc.run_bound_design_record_binding",
    media_type="application/json",
    schema=SchemaInfo(
        name="policyos.pdc.run_bound_design_record_binding",
        version="policyos.pdc.run_bound_design_record_binding.v1",
    ),
    producer=producer,
)
```

Factor Core trace parsing so `load_core_run` and the strict source loader share record validation. `derive_core_run_dir` rejects empty, absolute, separator-bearing, dot-segment, or normalized-escape run IDs and returns exactly one direct child of `core_runs_root.resolve()`. The strict loader does not call `recover_pending_run_finalize`; incomplete closure is a non-receipt, not permission to mutate the trace during projection.

- [ ] **Step 7: Implement the governed operation without taking the Slice-0 REFINE slot**

Add the new registration without editing the existing stub literal. The adapter must:

```python
tenant_id = get_current_tenant_id()  # raises; never substitutes
cell_id = get_current_cell_id()
run_dir = derive_core_run_dir(core_runs_root, run_id)
run_context = RunContext.start(
    store,
    registry_bundle_ref,
    run_dir=run_dir,
    run_id=run_id,
    tenant_id=tenant_id,
    cell_id=cell_id,
)
search_run = run_s2_shadow_design_loop(search_input)
persisted = persist_s2_design_search_run(
    search_run,
    store=store,
    run_id=run_id,
    tenant_id=tenant_id,
    cell_id=cell_id,
)
for ref in (persisted.design_record_ref, persisted.search_ledger_ref, persisted.binding_ref):
    run_context.add_output(ref)
manifest_ref = run_context.finalize()
```

Before outputs, emit applicability/invocation/ledger/envelope events with candidate-only authority. Return one typed operation result carrying the three refs and trace-derived manifest ref. Dispatch this only when both the exact operation ID and strict input are present; all other WorkspaceLoop requests retain the existing fixture path.

- [ ] **Step 8: Translate absent tenant to the exact typed refusal**

Catch `TenantContextNotSetError` before the broad WorkspaceLoop exception. Produce the exact non-receipt above plus a `ControlFailureEnvelope` with code `run_bound_design_record_tenant_scope_missing`, layer `pdc.gy`, phase `s2_design_search_persist`, the frozen message/next-action from the spec, `retryable=False`, exact job/run IDs, and empty artifact refs. Do not persist the normal failed-workspace proof artifacts on this branch because the falsifier requires zero DesignRecord, SearchLedger, or binding persistence and no fabricated scope.

- [ ] **Step 9: Implement direct resolution and the authority-abstaining paper arm**

The resolver takes only store and trusted root configuration. It resolves `TerminalCoreRunSource`, verifies the manifest, locates exactly one binding output by exact sidecar identity, verifies binding bytes, then verifies and parses its exact DesignRecord and SearchLedger refs. It compares every bound identity, schema, producer, content digest, case, record, ledger, run, tenant, and cell field.

Change `RunPaperProjectionService` to:

```python
RunPaperProjectionService(
    store=ctx.store,
    core_runs_root=ctx.core_runs_root,
    tenant_id=authorized_tenant_id,
)
```

The route may query the run index before construction for authorization/listing only. The service and resolver receive no run-index object. Feed the one trace-derived source into `RunPaperRun`, `RunPaperSourceBinding`, links, replay pins, and the case record.

Alias `RunPaperDesignRecordBinding = RunBoundDesignRecordBinding`. Add `bound_cell_id` to source verification. Define three separate strict `RunPaperAuthorityNonReceipt` values for grounding, admission, and promotion, each with its own `missing_authority`, institutional `owner_route`, `status="not_established"`, `authority_state="absent/unallocated"`, and role-specific denied uses. `AuthorityAbstainingRunPaperCase` uses discriminator `availability="record_available_authority_abstaining"`, renders the verified record and binding, and carries `authority_projection="abstained"`. Apply one shared case/run/tenant/cell validator to it and the future available arm; never construct the available arm here.

- [ ] **Step 10: Run focused case-record green checks and falsifier matrix**

Run the Task 2 command plus `tests/unit/runtime/http/test_runs_api.py`. Require the real-route positive, no-tenant negative, constant-hash binding mutation, builder/global-index decoy, trace conflict set, four-role CAS matrix, and Slice-0 zero-invocation test all green. Run Ruff over every changed Task 2 Python file.

- [ ] **Step 11: Re-derive the operation and caller counts twice**

Use one filesystem AST walk and one Git-object AST walk over the complete `src/**/*.py` denominator. Report the registry as 10 total / 6 executable / 4 retained stubs / 3 active Slice-0 operations; report one production call into `persist_s2_design_search_run` through the governed adapter and one reachable route dispatch for the exact operation ID. Preserve any disagreement as a finding.

- [ ] **Step 12: Commit the case-record cluster**

Immediately before commit, verify attachment and prefix; print the 2/4 ledger with round 1 standing/row cleared and round 2 standing/clearing `case-record-not-run-bound`, with no withdrawal. Confirm `git diff -- src/polisyos/core/contracts/control.py` is empty. Commit as:

```bash
git commit -m "fix(runtime): bind S2 case records to terminal runs" \
  -m "Receipts: real HTTP+worker success; typed no-tenant refusal; trace/CAS and Slice-0 ownership falsifiers green. Ledger: 2/4, rounds 1-2 stand."
```

### Task 3: Once-only epoch timing evidence and wall-clock catalog lane

**Files:**
- Create: `docs/superpowers/journals/2026-08-27-unbound-writes-authority-repairs.md`
- Create after the run: `docs/superpowers/timing-evidence/2026-08-27-gy-n12-epoch-corrupt-field-drift.jsonl`
- Modify after the run: `tools/quality/timing_budgets.json`
- Modify: `tests/repo_quality/tools/test_timing.py`

**Interfaces:**
- Consumes exactly one `ToolRunRecord` emitted by `quality.validation.check_layer3_gy_epoch_chronology_contract` in `corrupt-field-drift-check` mode and `serialized` regime.
- Produces timing key `quality.validation.check_layer3_gy_epoch_chronology_contract:corrupt-field-drift-check` with one wall-clock `samples_ms` value, identical `measured_p95_ms`, doubled `recommended_timeout_ms`, `sample_admission_predicate="declared_healthy_terminal:v1"`, `budget_basis="max_observed"`, and `ceiling_is_declared=False` after loading.
- Keeps the 600 core-second execution ceiling and historical 180 -> 264.30 core-second correction in the journal; neither CPU number enters `samples_ms`.

- [ ] **Step 1: Write the timing-catalog red before the expensive run**

Add a focused loader test that expects exactly one row for the new key, parses `source_refs[0]` as the promoted JSONL evidence line, decodes `entry["raw"]`, and requires:

```python
assert raw["tool"] == "quality.validation.check_layer3_gy_epoch_chronology_contract"
assert raw["mode"] == "corrupt-field-drift-check"
assert raw["regime"] == "serialized"
assert raw["exit_code"] == 0
assert raw["status"] == "ok"
assert raw["preflight_status"] == "ok"
assert lane.samples_ms == (raw["duration_ms"],)
assert lane.measured_p95_ms == raw["duration_ms"]
assert lane.recommended_timeout_ms == 2 * raw["duration_ms"]
assert lane.budget_basis == "max_observed"
assert lane.ceiling_is_declared is False
```

It must also reject a source record containing `user`, `sys`, or `cpu_seconds` as the catalog sample field. Run only this node and record red because the lane/evidence do not yet exist.

- [ ] **Step 2: Commit the pre-launch CPU ceiling and source freeze declaration**

Create the execution journal with: the exact upcoming source-freeze relationship, the code derivation that issues are rows with `rejected=False`, issue-free means pass, and pass maps to exit 0; the warning that the sibling's exit-1 polarity would make absence of an override inadmissible; the 600 core-second (`user + sys`) ceiling; the historical valid 264.30 core-second observation and invalid 180 core-second declaration; the once-only rule; and an empty receipt table explicitly marked `not launched`.

Verify attachment and print the unchanged 2/4 ledger. Commit the journal and red timing test as:

```bash
git commit -m "test(timing): declare epoch measurement admission" \
  -m "Preflight: 600 core-second ceiling; healthy terminal derived as exit 0; once-only run not launched. Ledger: 2/4, rounds 1-2 stand."
```

After the commit, record `SOURCE_FREEZE=$(git rev-parse HEAD)` in the journal scratch receipt; this exact commit is passed to the validator.

- [ ] **Step 3: Launch the expensive validator exactly once**

Use a new ignored scratch directory and no pipe:

```bash
SOURCE_FREEZE="$(git rev-parse HEAD)"
RUN_DIR=".polisyos-tools/unbound-writes-epoch-timing"
mkdir -p "$RUN_DIR"
uptime > "$RUN_DIR/uptime-before.txt"
set +e
POLISYOS_TOOLS_TIMING_LOG="$RUN_DIR/gy-n12-epoch-corrupt-field-drift.jsonl" \
POLISYOS_TOOLS_TIMING_REGIME=serialized \
PYTHONPATH="$PWD/src:$PWD" \
/usr/bin/time -p .venv/bin/python \
  tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py \
  --corrupt-field-drift-check \
  --expected-source-freeze "$SOURCE_FREEZE" \
  --output-format json \
  > "$RUN_DIR/report.json" \
  2> "$RUN_DIR/time.stderr"
EXIT_CODE=$?
set -e
printf '%s\n' "$EXIT_CODE" > "$RUN_DIR/exit-code.txt"
uptime > "$RUN_DIR/uptime-after.txt"
```

Read `exit-code.txt` before parsing anything else. If it is nonzero, if the JSON report is not pass, if `/usr/bin/time` reports a signal/killed run, or if the timing record is not exactly one well-formed exit-0/ok/serialized record, mark a non-receipt and do not rerun. A healthy completed run supplies wall `real`, CPU `user + sys`, the uptime pair, and the tool's `duration_ms` wall sample.

- [ ] **Step 4: Promote the exact raw record and add the wall-clock lane**

Construct one JSONL wrapper from the actual completed run values:

```python
source_path = ".polisyos-tools/unbound-writes-epoch-timing/gy-n12-epoch-corrupt-field-drift.jsonl"
raw = Path(source_path).read_bytes().removesuffix(b"\n").decode("utf-8")
entry = {
    "salvaged_at": datetime.now(UTC).isoformat(),
    "source_path": source_path,
    "source_line": 1,
    "raw": raw,
}
```

Use the actual timestamp and raw line from the completed run; do not reserialize the raw record. Add the lane surgically to `timing_budgets.json` without reformatting unrelated rows. `samples_ms` and `measured_p95_ms` equal the record's `duration_ms`; timeout is exactly twice it; basis derives as max-observed because there is one sample. Update the journal with the exact source-freeze commit, direct exit code, report status, wall `real`, tool wall milliseconds, `user`, `sys`, CPU sum, uptime pair, evidence path, and the explicit unit separation.

- [ ] **Step 5: Run timing loader/recomputation checks without rerunning the epoch validator**

Run the focused timing test from Step 1 and the catalog loader/recomputation nodes that cover p95, timeout, source evidence, single-sample basis, and duplicate keys. Do not invoke `check_layer3_gy_epoch_chronology_contract.py --corrupt-field-drift-check` again. Run Ruff only on changed Python tests.

- [ ] **Step 6: Execute the corrected closure command**

Run one no-pipe Python command that loads the catalog through `tools.lib.timing.load_timing_budget_catalog`, selects the sole exact key, reads its sole evidence line and `raw` record, and asserts every field from Step 1 plus `samples_ms[0] == raw["duration_ms"]`. Separately parse the journal receipt and assert the journal labels `real`/`duration_ms` as wall-clock and `user + sys` as core-seconds, with 264.30 absent from the catalog row. Record the command and exit 0 verbatim in the journal and final hand-back.

- [ ] **Step 7: Commit the timing closure**

Verify attachment and prefix; print the 2/4 ledger with both rounds still standing and the independent timing row cleared without a widening round. Commit as:

```bash
git commit -m "fix(timing): catalog measured epoch drift lane" \
  -m "Receipt: once-only serialized exit 0; wall sample promoted byte-for-byte; CPU ceiling kept separate. Ledger: 2/4, rounds 1-2 stand."
```

### Task 4: Freeze, review, and verify the handed-back branch

**Files:**
- Modify only if receipts require it: `docs/superpowers/journals/2026-08-27-unbound-writes-authority-repairs.md`
- Do not modify mechanism source during the expensive verification wave; blocking review findings are batched before the freeze.

**Interfaces:**
- Consumes all three committed closures.
- Produces separate receipts for the import linter, release guardrail, and package gate; row texts for the register owner; and the attached-branch readback.

- [ ] **Step 1: Run whole-branch specification and quality review**

Review the complete diff from merge commit `374b46aa08bf6f64e5b65a82cbfc798c83c1b616` through HEAD against the amended spec. Classify every finding as NEW class or the same class one level deeper. On the second finding in a class, widen to the property or declare a bounded residual with its falsifier; do not patch a third instance.

- [ ] **Step 2: Re-open the failure/repair register and run targeted verification**

Re-read the complete failure/repair register, then run all changed test files together, Ruff on changed Python, the timing catalog recomputation checks, and architecture guardrails. Do not run full pytest and do not synchronize the deep-import baseline.

- [ ] **Step 3: Run and report the three predicates separately**

Run the repository's literal import-linter, release-guardrail, and package-gate commands discovered from the debt rows/spec records. Capture each direct exit before parsing. The import linter must move only ARCH004 from 2 to 0; release guardrail must remain exit 0 with zero creep. Before interpreting the package-gate count, census ignored `tmp/`, `production_data/`, and `runs/` directories and run the second derivation that excludes their environmental effect. Any movement outside the requested ARCH004 delta is a finding.

- [ ] **Step 4: Perform final ownership and adjacency censuses**

Using both filesystem and Git-object AST walks, prove: zero Runtime mutating SQL against `world.*`; no production import of a source-derived write-private Fabric module outside the owner API; one governed production S2 persistence caller; resolver discovery has no builder/global-index/run-index/CAS-scan edge; `slice0.refine.stub` source bytes equal the merge-base bytes; and `src/polisyos/core/contracts/control.py` has no branch diff.

- [ ] **Step 5: Commit receipt-only amendments if needed**

If the journal needs final predicate receipts, verify attachment, print the unchanged 2/4 ledger, and commit only the journal. Do not amend an already reviewed mechanism commit.

- [ ] **Step 6: Read the branch back and prepare hand-back row text**

Read every reported file and commit from attached branch HEAD after all writes. The hand-back includes: three closure row texts without editing the register; the exact timing closure command; the conditional facade census; the once-only timing receipt; the GY-C2 unchanged/zero-invocation proof; the no-tenant receipt; three predicate receipts; `core/contracts/control.py` adjacency; and widening ledger 2/4 with both rounds standing.
