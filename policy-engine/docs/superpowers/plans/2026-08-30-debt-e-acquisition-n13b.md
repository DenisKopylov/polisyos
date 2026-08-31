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
