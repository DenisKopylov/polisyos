# Acquisition N13b Boundary Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent fixture-injected acquisition dependencies from projecting production readiness or creating a production execution reservation, while delivering reproducible measurements and a seven-row closure dossier without widening any production definition.

**Architecture:** Keep the published `behavioral_fixture_not_production` const and the existing API schema unchanged. Change only the acquisition service's internal derivation: while its only owner-result contract is fixture-badged, both variable capability fields remain `producer_missing`, and `execute()` fails closed before authority-provider invocation, reservation persistence, or job creation. Treat INT-R2, GY admission, numeric VoI, production N13b, and deterministic bundle deficits as measured non-closures rather than filling them with test-shaped substitutes.

**Tech Stack:** Python 3.12, Pydantic v2, pytest/pytest-asyncio, Ruff, PolicyOS runtime control/CAS services, `uv run`.

**Spec:** `docs/superpowers/journals/2026-08-30-debt-e-acquisition-n13b.md#approved-scope-and-corrections`

## Global Constraints

- Work only on branch `codex/debt-e-acquisition-n13b` in `.worktrees/debt-e-acquisition-n13b`; never rebase, force-push, or use stash as storage.
- Preserve the exact token `behavioral_fixture_not_production`; create no synonym and change no public field or enum.
- Do not edit or regenerate `schemas/runtime_api_v1.openapi.json`, `packages/runtime-api-client/**`, `apps/runtime-dashboard/**`, or `src/polisyos/runtime/http/openapi_contract.py`.
- Do not edit `docs/plans/active/DEBT-REGISTER.md`, `docs/plans/active/LEDGER.md`, `docs/plans/active/layer3-slices/GY-engine-subordination.md`, `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`, or `tools/quality/validation/check_debt_ledger.py`.
- Do not edit `src/polisyos/runtime/quality/**`, `src/polisyos/runtime/http/dependencies.py`, `promotion_sequence.py`, or another lane's files.
- Never reinterpret a badged port, fixture-shaped run, row count, signature marker, or same-stream observation as a production port, non-data object, admission, authority, or positive route (`W5-K01`, `P31`, `P32`, `P37`, `P38`).
- Preserve the 15 typed `metric_residual_granularity_not_supported` refusals; create no numeric VoI without measure, population, horizon, assumptions, and authority source.
- Use only exact test nodes and narrow blast-radius files. Directory-wide and full-suite runs are forbidden.
- Run every Python verifier through the worktree-bound `uv run` interpreter.
- Commit at the planning boundary, the coherent behavior boundary, and closeout; verify branch attachment before every commit.

## Pattern Pass

- Relevant failure patterns: `P04` status-lattice contradiction; `P05` authority leak; `P10` semantic adequacy; `P15` projection laundering; `P31` instance patching; `P32` trust by form; `P35` sampled-denominator generalization; `P37` declared gate predicate; `P38` proxy gate; `P41` red provenance.
- Existing anti-pattern: `AcquisitionActionService._projection()` derives `ready` from the mere presence of duck-typed injected collaborators while the same response and result contract are permanently `behavioral_fixture_not_production`.
- Target correct pattern: fixture injection may support behavioral tests, but the production-readiness projection remains fail-closed and the production execute boundary stops before reservation or effect orchestration.
- Capability labels after this task: production N13b remains `producer_missing`; deterministic admission bundle remains `producer_missing + artifact_missing + bridge_missing`; INT-R2 remains `absent/unallocated`; GY admission remains `artifact_missing + bridge_missing`; semantic-epoch and mandate authority slots remain typed empty.
- Acceptance signal: the new test is red because injected dependencies currently yield `ready` and reach the provider, then green after both capability values stay `producer_missing` and execution raises `acquisition_execution_bridge_missing` before provider invocation or job creation.

---

### Task 1: Freeze the approved scope and baseline

**Files:**
- Create: `docs/superpowers/plans/2026-08-30-debt-e-acquisition-n13b.md`
- Create: `docs/superpowers/journals/2026-08-30-debt-e-acquisition-n13b.md`

**Interfaces:**
- Consumes: the user-approved Task E continuation, the seven debt rows, W5-K01, predecessor journal, and repository instructions.
- Produces: an executable TDD sequence and an append-only evidence journal for later dossier transcription.

- [x] **Step 1: Record branch and baseline identity**

Run:

```bash
git status -sb
git symbolic-ref -q HEAD
git rev-parse HEAD
git rev-list --left-right --count main...HEAD
```

Expected: attached `codex/debt-e-acquisition-n13b`, clean tree, HEAD `784d020148c56e9bfb3a3631909ba11232210a9f`, and `0 0` divergence before edits.

- [x] **Step 2: Install the bound test/lint environment**

Run:

```bash
uv sync --frozen --extra test --extra lint
uv run python -c "import pathlib, polisyos, pytest; print(pathlib.Path(polisyos.__file__).resolve()); print(pytest.__version__)"
```

Expected: exit `0`; `polisyos` resolves under this worktree and pytest imports under `uv run`.

- [x] **Step 3: Commit the planning boundary**

Run:

```bash
git status -sb
git add docs/superpowers/plans/2026-08-30-debt-e-acquisition-n13b.md docs/superpowers/journals/2026-08-30-debt-e-acquisition-n13b.md
git commit -m "docs: plan acquisition boundary hardening"
```

Expected: commit succeeds on `codex/debt-e-acquisition-n13b` with only the two mandated documents.

### Task 2: Reproduce the fixture-readiness contradiction

**Files:**
- Create: `tests/integration/core_runtime/test_acquisition_production_boundary.py`

**Interfaces:**
- Consumes: `AcquisitionActionService._projection`, `AcquisitionActionService.execute`, and the existing real control-service/route-closure test harness.
- Produces: two regression witnesses over the service's consumer-visible projection and durable job boundary.

- [x] **Step 1: Write the projection regression test**

Add an async test that obtains the existing injected `_Provider` and `_Port` harness, projects its verified closure, and independently asserts these literals:

```python
assert projection.authority_badge == "behavioral_fixture_not_production"
assert projection.authority_capability == "producer_missing"
assert projection.execution_capability == "producer_missing"
```

The production mutation this catches is deriving either capability's `ready` value from collaborator presence while the path remains fixture-badged.

- [x] **Step 2: Run the exact projection test and verify RED**

Run:

```bash
uv run pytest tests/integration/core_runtime/test_acquisition_production_boundary.py::test_badged_dependencies_cannot_project_ready -q
```

Expected before implementation: exit `1`; assertion reports actual `ready` versus expected `producer_missing`.

- [x] **Step 3: Write the pre-reservation regression test**

Add an async test using a second idempotency key. Compute the would-be job ID before calling `execute()`, assert it is absent, then assert:

```python
with pytest.raises(
    AcquisitionActionServiceError,
    match="acquisition_execution_bridge_missing",
):
    service.execute(...)
assert calls == []
assert control._control_store.get_job(job_id) is None
```

The production mutation this catches is removing the fixture/production boundary and allowing provider invocation, reservation persistence, or enqueueing.

- [x] **Step 4: Run the exact execution test and verify RED**

Run:

```bash
uv run pytest tests/integration/core_runtime/test_acquisition_production_boundary.py::test_badged_dependencies_fail_before_reservation_or_job_creation -q
```

Expected before implementation: exit `1`; the injected provider is reached instead of the typed production-bridge refusal.

### Task 3: Make the smallest behavior-only repair

**Files:**
- Modify: `src/polisyos/runtime/http/services/acquisition_action_service.py`
- Test: `tests/integration/core_runtime/test_acquisition_production_boundary.py`

**Interfaces:**
- Consumes: the unchanged `AcquisitionRouteProjection` schema and fixture-badged `AcquisitionOwnerExecutionResult` contract.
- Produces: fail-closed capability derivation and a pre-reservation production gate using the existing `acquisition_execution_bridge_missing` error vocabulary.

- [x] **Step 1: Change only the projection derivation**

In `_projection()`, keep both public fields and their existing `Literal["ready", "producer_missing"]` types, but emit the hand-derived current truth:

```python
authority_capability="producer_missing",
execution_capability="producer_missing",
```

Do not alter `authority_badge`, `external_nonclosures`, public models, schemas, or generated consumers.

- [x] **Step 2: Add the current production execution gate**

Immediately after mutation revalidation and before resolving the provider, call a private helper whose complete current behavior is:

```python
raise AcquisitionActionServiceError("acquisition_execution_bridge_missing")
```

Name and document the helper so it states the property: the injection-only port returns the fixture-badged result contract and therefore cannot establish a production execution bridge. Keep decision-request behavior and the direct behavioral worker harness unchanged.

- [x] **Step 3: Run both regression nodes and verify GREEN**

Run:

```bash
uv run pytest \
  tests/integration/core_runtime/test_acquisition_production_boundary.py::test_badged_dependencies_cannot_project_ready \
  tests/integration/core_runtime/test_acquisition_production_boundary.py::test_badged_dependencies_fail_before_reservation_or_job_creation \
  -q
```

Expected: exit `0`, `2 passed`.

- [x] **Step 4: Run the narrow acquisition blast radius**

Run:

```bash
uv run pytest \
  tests/unit/runtime/http/test_acquisition_control_worker.py \
  tests/integration/runtime_frontend/test_ds15_acquisition_route_contract_bridge.py \
  tests/integration/core_runtime/test_acquisition_production_boundary.py \
  -q
uv run python -m ruff check \
  src/polisyos/runtime/http/services/acquisition_action_service.py \
  tests/integration/core_runtime/test_acquisition_production_boundary.py
```

Expected: both commands exit `0`; the behavioral worker remains usable for its explicitly non-production semantic tests and the published API bridge remains unchanged.

- [x] **Step 5: Inspect and commit the coherent behavior slice**

Run:

```bash
git diff --check
git diff -- src/polisyos/runtime/http/services/acquisition_action_service.py tests/integration/core_runtime/test_acquisition_production_boundary.py
git status -sb
git add src/polisyos/runtime/http/services/acquisition_action_service.py tests/integration/core_runtime/test_acquisition_production_boundary.py
git commit -m "fix: keep fixture acquisition paths non-production"
```

Expected: only the acquisition service and one acquisition integration test enter the commit.

### Task 4: Measure the seven rows and reconcile the two inventories

**Files:**
- Modify: `docs/superpowers/journals/2026-08-30-debt-e-acquisition-n13b.md`

**Interfaces:**
- Consumes: complete source/test/schema/architecture censuses and executable targeted checks.
- Produces: replayable commands, exit codes, denominators, port implementation enumeration, field construction-site enumeration, bidirectional `external_nonclosures` mapping, and the GY handoff specification.

- [x] **Step 1: Measure INT-R2's complete executable denominator**

Run:

```bash
rg -n 'GapAcquisitionCase|gap_acquisition_case' src tests schemas architecture
```

Expected: exit `1`, zero occurrences across the four named roots; record both missing predicates: ratified producer and typed persisted artifact.

- [x] **Step 2: Enumerate capability construction sites**

Run complete `.py`/`.json`/`.ts`/`.tsx` searches for `AcquisitionRouteProjection(`, `authority_capability`, and `execution_capability`, recording file-type denominators and classifying definitions, the sole backend constructor, generated schema/client mirrors, and consumers. The acceptance finding is based on the sole executable backend constructor, not on sampled references.

- [x] **Step 3: Enumerate every structural strict-port implementation**

Run an AST census over every Python file under `src/`, `tests/`, `schemas/`, and `architecture/`. Report every class defining all three methods `execute`, `reenter`, and `resume_reentry`, distinguish the `AcquisitionExecutionPort` protocol from implementations, and state each implementation's binding.

- [x] **Step 4: Reconcile `external_nonclosures` in both directions**

Map each of the tuple's four entries to a register row and compare its exact capability label. Then map all seven Task E rows back to the tuple, explicitly naming omissions and the mandate sibling that appears in the tuple but not the seven-row denominator. Do not edit either source of truth.

- [x] **Step 5: Measure the complete numeric-VoI denominator**

Use the canonical N13a acquisition census/checker to enumerate all 15 growth-backlog rows and assert each reports `metric_residual_granularity_not_supported`; record the command, row measure, and exit code without producing a number.

- [x] **Step 6: Write the GY-GAP6 routable specification**

Name the exact movement-family owner allocation, generic chronology protocol, qualification consumer, missing native adapter/policy/admission index, Cycle Board producer/consumer symbols, and the predicates that must resolve and content-bind. Rule on the owner from the measured plane: reject `GY-AQ1` because that row is explicitly non-data while GY-GAP6 is data-acquisition movement; retain `GY-GAP6` with its declared GY-N13b producer / GY-N12 chronology split and Cycle Board as consumer, without appointing a new institutional role.

### Task 5: Close the journal with fresh verification evidence

**Files:**
- Modify: `docs/superpowers/journals/2026-08-30-debt-e-acquisition-n13b.md`

**Interfaces:**
- Consumes: committed implementation, targeted test receipts, validators, censuses, and GY specification.
- Produces: a seven-block Register closure dossier and final handoff arithmetic.

- [x] **Step 1: Run required repository validators through `uv run`**

Run:

```bash
PYTHONPATH=. uv run python tools/quality/validation/check_debt_ledger.py --check
PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py
```

Expected: debt-ledger checker exit `0`; docs-lifecycle output contains exactly six findings. Record the actual second exit code rather than assuming it.

- [x] **Step 2: Run final targeted verification once on frozen source**

Run:

```bash
uv run pytest \
  tests/unit/runtime/http/test_acquisition_control_worker.py \
  tests/integration/runtime_frontend/test_ds15_acquisition_route_contract_bridge.py \
  tests/integration/core_runtime/test_acquisition_production_boundary.py \
  -q
uv run python -m ruff check \
  src/polisyos/runtime/http/services/acquisition_action_service.py \
  tests/integration/core_runtime/test_acquisition_production_boundary.py
uv run polisyos-tools architecture guardrails check
git diff --check
```

Expected: every command exits `0`; if not, record the actual failure and classify it before changing any claim.

- [x] **Step 3: Complete the Register closure dossier**

Write one block for each of the seven named rows. Each closure row block contains verdict, exact command/predicate and exit code, and exact supersession prose. `GY-GAP6` contains a routable specification and notes its registered `blocked` standing solely for the required arithmetic, not a Task E closure verdict.

- [x] **Step 4: State measured arithmetic and protected-path confirmation**

Record:

```text
7 measured rows = 0 closed + 4 open + 3 blocked + 0 ambiguous
4 core rows = 0 closed + 3 open + 1 blocked + 0 ambiguous
3 adjacent rows = 0 closed + 1 open + 2 blocked + 0 ambiguous
```

Also record `git diff --name-only` evidence that no schema, generated client, dashboard, OpenAPI contract, debt register, ledger, active plan, or checker pin changed.

- [x] **Step 5: Commit and read the branch back**

Run:

```bash
git status -sb
git add docs/superpowers/journals/2026-08-30-debt-e-acquisition-n13b.md
git commit -m "docs: record acquisition closure dossier"
git status -sb
git log --oneline --decorate -3
git diff --name-status 784d020148c56e9bfb3a3631909ba11232210a9f..HEAD
```

Expected: attached branch, clean tree, three Task E commits visible from the branch, and only the approved plan, journal, acquisition service, and acquisition integration test changed.

---

## Round 2 append-only execution plan — production port or exact landing blocker

**Round-2 goal:** Re-adjudicate every Task E row as `closed` or `blocked`, without
turning the fixture-badged owner contract into a production port. Build the
deterministic acquisition admission-bundle producer and exact invocation-hash
bridge around a typed-empty signing/mandate slot; preserve every external or
institutional absence as a fail-closed input.

**Round-2 architecture decision:** The complete strict-port census found an
existing raw N13b executor but no safe input bridge. Its callable requires an
authority entry, attempt identity, live constraints, a raw journal path and a
raw CAS root; the verified route closure carries none of the first three, and
the executor constructs its own unguarded filesystem CAS from the last two.
The strict port must also return `AcquisitionOwnerExecutionResult`, whose badge
is type-constrained to `behavioral_fixture_not_production`. A production
adapter would therefore require both a current typed route-to-N13b execution
binding and a production-capable result contract/guarded-store seam. Those
objects do not exist in Task E's files, and adding them changes protected
contracts or the N13b owner write path. The production-port row is blocked by
those concrete landing objects; Task E will not wrap the raw-path executor or
rename the test port.

**Round-2 bundle decision:** `AgentActionAdmissionBundle` construction,
detached signing, persistence and `{invocation_hash: cas_ref}` mapping currently
exist only in a unit-test harness. The engineering mechanism is executable in
this lane. Add one acquisition-owned deterministic producer which binds the
exact operation, invocation, intent, permission proof, resource, delegation
contract and effect adapter; persists through the existing authority writer;
signs through a purpose-scoped typed slot; reads the artifact back; and returns
the exact mapping consumed by `AgentActionAuthorityGateway`. The default slot
stays empty. No human-decision custody, fake contract ref, signature marker or
mandate appointment may be substituted.

### Round-2 constraints and corrected baselines

- No Task E verdict ends `open`: an executable row is completed; a blocked row
  names the exact artifact, producer, contract, appointment or slice that must
  land first.
- A missing bridge is work, not a blocker. A missing producer is a blocker only
  after a complete denominator and zero are recorded.
- Preserve the public badge, all API models and generated clients unchanged.
  Do not edit the OpenAPI contract owner or any dashboard file.
- Preserve the 15 typed numeric-VoI refusals. No absent value, cost or authority
  input is replaced by a number or a form-valid reference.
- `GY-GAP6` remains a specification deliverable with its existing registered
  blocked standing; Task E does not issue its verdict.
- The bound debt-ledger checker is expected to exit `1` with exactly 18 blocking
  `closure_signal_identity_unresolvable` findings at the slice base. Task E may
  not grow that set. The docs-lifecycle checker is expected to exit `1` with
  exactly six findings.
- Run exact nodes only. A directory-wide or full-suite run remains forbidden.
- Verify `codex/debt-e-acquisition-n13b` attachment before each commit. Append
  evidence to the journal and never rewrite register history.

### Round-2 pattern pass

- `P01`/`P02`/`P12`: build the bundle's producer, persisted artifact and exact
  consumer mapping as one chain; do not stop at a model constructor.
- `P05`/`P15`: a bundle producer is deterministic engineering, while signing,
  delegation and current mandate are separate authority inputs. Reusing an
  unrelated custody role would dilute purpose-scoped authority.
- `P31`/`P32`: expose one exact invocation-hash bridge and require a real
  persisted delegation ref plus detached signature. A fake SHA-shaped ref or
  signature marker is not evidence.
- `P35`: every absence and every count is derived from the complete named roots
  with path and file-type denominators.
- `P37`: producer-derived hashes are `recomputed`; detached signature trust is
  `independently_reconciled`; institutional mandate/currentness remains
  `not_established` and can never make a positive.
- `P38`: the bundle property is exact content/signature admission by the real
  gateway, not construction success or field presence. The divergent probe is
  a correctly shaped bundle with a missing/wrong detached signer.
- `P40`: the accepted worker-harness escape is a declared residual, not another
  repair round. Freeze its exact reachability and do not change it here.
- `P41`: compare the final debt finding identities with the 18-finding slice
  baseline rather than treating exit code `1` as new failure.

### Task 6: Freeze the round-2 census and executability rulings

**Files:**
- Modify: `docs/superpowers/plans/2026-08-30-debt-e-acquisition-n13b.md`
- Modify: `docs/superpowers/journals/2026-08-30-debt-e-acquisition-n13b.md`

- [x] Re-read the round-1 dossier, failure register and Task E rows.
- [x] Re-run/read back branch attachment and slice base.
- [x] Enumerate the three strict-port methods, their production inputs, the
  complete structural implementation denominator and every composition seam.
- [x] Census the three numeric-VoI input families and the five fresh-route
  conjuncts.
- [x] Census the bundle constructor, persistence and invocation-mapping sites.
- [ ] Append the commands, exit codes, denominators and exact landing blockers
  to the round-2 journal.
- [ ] Commit the round-2 planning boundary after branch-attachment verification.

### Task 7: Prove the deterministic bundle mechanism red-first

**Files:**
- Create: `src/polisyos/runtime/http/services/acquisition_admission_bundle.py`
- Create: `tests/integration/core_runtime/test_acquisition_admission_bundle.py`
- Modify: `src/polisyos/runtime/http/services/README.md`

- [ ] Add an exact-node test which imports the source producer and fails because
  the source producer/bridge does not exist yet.
- [ ] Add the institutional-boundary test: an empty purpose-scoped signer slot
  fails before any artifact write and emits the exact typed blocker.
- [ ] Add the positive engineering-mechanism test with an ephemeral trusted
  deployment signer and a real persisted contract ref. Require one signed,
  tenant/run/job-bound bundle artifact, exact content hashes, exact
  `{invocation_hash: artifact_ref}` mapping, and successful resolution by the
  existing `AgentActionAuthorityGateway` consumer.
- [ ] Add a negative signer/binding variant proving a shaped but untrusted or
  mismatched artifact is not admitted and no effect executes.
- [ ] Run the exact new nodes and capture the pre-implementation red.

### Task 8: Implement the bundle producer and bridge

**Files:** same as Task R2-2.

- [ ] Implement a strict typed signing slot whose production default is empty
  and whose configured state requires signer, trusted verifier and
  purpose-scoped identity together.
- [ ] Implement the deterministic producer over the exact authority hashes and
  acquisition effect binding; reject non-acquisition tuples, missing real
  delegation refs and incomplete signer state before persistence.
- [ ] Persist through the existing runtime authority writer, attach the detached
  signature, reconcile tenant/cell/run/job identity, read back exact bytes and
  return an immutable invocation mapping for the existing gateway.
- [ ] Keep institutional delegation/current-mandate mappings empty. Demonstrate
  that their absence can only refuse an authority decision; it cannot erase the
  bundle receipt or allow an effect.
- [ ] Run exact green nodes, Ruff for changed Python files, inspect the diff,
  verify branch attachment and commit the coherent bundle slice.

### Task 9: Freeze every remaining row predicate

**Files:**
- Modify: `docs/superpowers/journals/2026-08-30-debt-e-acquisition-n13b.md`

- [ ] Re-run the strict-port AST census and raw-executor input census. Record the
  precise blocked-by artifacts/contracts rather than `port missing`.
- [ ] Re-run the 15-row numeric-VoI input census and name owner/ranking,
  expected-value and expected-cost inputs separately.
- [ ] Re-run the fresh-route negative witnesses; use exactly the N13b landing
  blocker and semantic-epoch policy-authority appointment as `blocked_by`, and
  state every conjunct's measured disposition.
- [ ] Re-run the confirmed INT-R2 zero and the two independent GY measurements:
  DS15 receipt production versus GY admission absence.
- [ ] Freeze the accepted worker residual: a pre-existing acquisition job plus
  future manual injection of both fixture collaborators can still reach
  `handle_job`; the public route cannot create the job.
- [ ] Preserve the delivered GY-GAP6 routing specification verbatim in
  substance: GY-N13b producer, GY-N12 policy/admission chronology and Cycle
  Board per-row consumer.

### Task 10: Verify, dossier and read back the branch

- [ ] Run only exact acquisition bundle, production-boundary, worker and receipt
  nodes selected by the changed-path importer census.
- [ ] Run Ruff over changed Python files and `git diff --check`.
- [ ] Run the bound debt checker; assert exit `1` and compare the complete
  blocking identity set with the 18-row baseline so it does not grow.
- [ ] Run docs lifecycle; assert exit `1` with exactly six findings.
- [ ] Confirm protected-path diff is empty.
- [ ] Append seven dossier blocks. Six Task E-owned rows receive `closed` or
  `blocked`; `GY-GAP6` carries its existing blocked standing plus specification.
- [ ] State `7 = closed + blocked`, split four core versus three adjacent, with
  the measure attached to every number.
- [ ] Verify branch attachment, commit closeout, and read the committed branch
  diff and log back before reporting delivery.
