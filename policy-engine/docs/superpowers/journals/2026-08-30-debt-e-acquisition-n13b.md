# Task E — acquisition and N13b handshake journal

Date opened: 2026-08-30  
Continuation approved: 2026-08-31  
Branch: `codex/debt-e-acquisition-n13b`  
Base: `784d020148c56e9bfb3a3631909ba11232210a9f`

## Approved scope and corrections

The approved implementation is a boundary hardening, not a production-port substitution. The published vocabulary remains unchanged: `authority_badge` and `AcquisitionOwnerExecutionResult.authority_badge` stay the exact const `behavioral_fixture_not_production`. No second badge, enum member, field, schema regeneration, client regeneration, or dashboard edit is permitted.

The defect is the variable capability derivation beside that const. At baseline, `AcquisitionActionService._projection()` returns `ready` when any duck-typed authority provider or execution port is injected, even though the route and result contracts remain permanently fixture-badged. The repair must keep both capability fields `producer_missing` on this badged path and stop production execution before authority reservation or job creation. Direct behavioral worker tests remain fixtures and establish no production capability.

The seven-row denominator remains the original four core plus three adjacent rows for reporting. `GY-GAP6` is re-scoped out of Task E implementation and will receive a routable specification rather than a Task E closure verdict; its existing `blocked` standing contributes only to the required seven-row arithmetic.

## Baseline receipts

| measurement | result | disposition |
| --- | --- | --- |
| `git status -sb` | `## codex/debt-e-acquisition-n13b` | branch attached, tree clean before edits |
| `git symbolic-ref -q HEAD` | `refs/heads/codex/debt-e-acquisition-n13b` | correct branch attachment |
| `git rev-parse HEAD` | `784d020148c56e9bfb3a3631909ba11232210a9f` | requested base |
| `git rev-list --left-right --count main...HEAD` | `0 0` | requested ahead/behind baseline |
| mandated plan path | absent before Task E | created by this planning boundary |
| mandated journal path | absent before Task E | created by this planning boundary |
| `uv sync --frozen --extra test --extra lint` | exit `0`; 49 test/lint packages installed | worktree-bound dependency receipt |
| `uv run python -c "import pathlib, polisyos, pytest; ..."` | exit `0`; `polisyos` resolved to this worktree; pytest `9.0.2` | bound-interpreter receipt |

## Opening pattern pass

- `P04` / `P15`: the response can currently pair `ready` with a const that says not production.
- `P31` / `P32`: a duck-typed injected collaborator cannot establish production provenance by presence or shape.
- `P35`: readiness construction sites, N13b implementations, INT-R2 symbols, and VoI residuals require complete enumerations with denominators.
- `P37` / `P38`: the intended property is production capability; current code tests collaborator presence, which diverges for the badged test provider/port.
- `W5-K01`: additional fixture rows or successful test invocations cannot establish the missing production port, admission, authority, or INT-R2 union.

Target pattern: preserve the fixture path for semantic testing while making its production capability and production execution effect exactly fail closed. Capability reality remains explicit: production port `producer_missing`; deterministic bundle `producer_missing + artifact_missing + bridge_missing`; INT-R2 `absent/unallocated`; GY admission `artifact_missing + bridge_missing`; positive route `absent/unallocated`; numeric VoI `producer_missing`.

## Protected paths

The following remain read-only throughout this lane:

- `schemas/runtime_api_v1.openapi.json`
- `packages/runtime-api-client/**`
- `apps/runtime-dashboard/**`
- `src/polisyos/runtime/http/openapi_contract.py`
- `src/polisyos/runtime/quality/**`
- `docs/plans/active/DEBT-REGISTER.md`
- `docs/plans/active/LEDGER.md`
- `docs/plans/active/layer3-slices/GY-engine-subordination.md`
- `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`
- `tools/quality/validation/check_debt_ledger.py`

## Evidence log

### Red-first boundary witnesses

The two new exact tests were run before the source repair.

```bash
uv run pytest tests/integration/core_runtime/test_acquisition_production_boundary.py::test_badged_dependencies_cannot_project_ready -q
```

Exit `1`: the badged injected harness projected actual `ready` where the test required
`producer_missing`.

```bash
uv run pytest tests/integration/core_runtime/test_acquisition_production_boundary.py::test_badged_dependencies_fail_before_reservation_or_job_creation -q
```

Exit `1`: execution reached `_Provider.for_request`; the provider's deliberate
`worker cannot recreate HTTP authority` assertion fired. That establishes that the
baseline crossed the production boundary rather than refusing before authority use.

After the behavior-only repair, the combined exact command exited `0` with two test
nodes passing:

```bash
uv run pytest \
  tests/integration/core_runtime/test_acquisition_production_boundary.py::test_badged_dependencies_cannot_project_ready \
  tests/integration/core_runtime/test_acquisition_production_boundary.py::test_badged_dependencies_fail_before_reservation_or_job_creation \
  -q
```

The repair changes no DTO, `Literal`, badge, error token, schema, generated client, or
dashboard consumer. `_projection()` now emits `producer_missing` for both variable
capability fields, and `execute()` raises the existing
`acquisition_execution_bridge_missing` immediately after read-only route revalidation
and before provider lookup, port lookup, action tuple construction, job-id construction,
reservation persistence, phase persistence, or enqueue.

The first narrow blast-radius command exited `0` over 11 collected acquisition nodes;
the exact Ruff command also exited `0`:

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

### `ready` construction-site census

The complete executable Python census walked 5,092 `.py` files under `src/`, `tests/`,
`schemas/`, and `architecture/` with zero parse errors. It found two executable sites
that set either capability field:

1. `AcquisitionActionService._projection()` in
   `src/polisyos/runtime/http/services/acquisition_action_service.py`, the sole backend
   response constructor, sets both fields to `producer_missing`.
2. The example dictionary in `src/polisyos/runtime/http/openapi_contract.py` sets both
   fields to `producer_missing`; it is documentation/example construction, not a port.

The source schema declaration remains
`Literal["ready", "producer_missing"]`. Generated schema/client mirrors and dashboard
test fixtures contain the public vocabulary, including fixture objects with `ready`,
but none is a backend response producer or strict-port binding. The complete reference
denominator was 7,740 `.py`/`.json`/`.ts`/`.tsx`/`.md` files under `src/`, `tests/`,
`schemas/`, `architecture/`, `packages/`, and `apps/`: 5,095 Python, 1,097 JSON,
492 TypeScript, 716 TSX, and 340 Markdown files; 17 files referenced at least one of the
two fields.

Rerunnable executable-site predicate (exit `0`, two sites):

```bash
uv run python - <<'PY'
import ast
from pathlib import Path

paths = sorted({
    path
    for root in map(Path, ("src", "tests", "schemas", "architecture"))
    for path in root.rglob("*.py")
})
fields = {"authority_capability", "execution_capability"}
rows = []
for path in paths:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            found = tuple(keyword.arg for keyword in node.keywords if keyword.arg in fields)
        elif isinstance(node, ast.Dict):
            found = tuple(
                key.value
                for key in node.keys
                if isinstance(key, ast.Constant) and key.value in fields
            )
        else:
            continue
        if found:
            rows.append((path, node.lineno, type(node).__name__, found))
print(f"python_file_denominator={len(paths)}")
print(f"executable_capability_construction_site_denominator={len(rows)}")
for row in rows:
    print(*row, sep="\t")
PY
```

Answer to the corrected narrow question: **no**. After this change, an injected test
port, provider, or fixture-badged result cannot make either backend capability field
report `ready`; the sole backend constructor has no collaborator-dependent branch.

### Strict N13b port implementation census

The complete structural census below parsed 5,092 Python files and all 12,005 class
definitions under the four roots, with zero parse errors. It found two classes defining
the full `execute` + `reenter` + `resume_reentry` shape:

- `AcquisitionExecutionPort` at
  `src/polisyos/runtime/http/services/acquisition_action_service.py:190` is the strict
  `Protocol`, not an implementation.
- `_Port` at `tests/unit/runtime/http/test_acquisition_control_worker.py:21` is the sole
  structural implementation. `_worker_harness` manually assigns it to an
  `object.__new__` test service, binds it to `tenant-a/cell-a/run-ds15`, a mutable call
  recorder, and a test CAS receipt, and invokes the worker directly. Its result type is
  permanently `behavioral_fixture_not_production`.

There is no structural implementation under `src/` and no tenant-bound production
binding. Rerunnable predicate (exit `0`, two structural rows including the protocol):

```bash
uv run python - <<'PY'
import ast
from pathlib import Path

paths = sorted({
    path
    for root in map(Path, ("src", "tests", "schemas", "architecture"))
    for path in root.rglob("*.py")
})
rows = []
classes = 0
errors = []
for path in paths:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception as exc:
        errors.append((path, exc))
        continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        classes += 1
        methods = {
            child.name
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if {"execute", "reenter", "resume_reentry"} <= methods:
            rows.append((path, node.lineno, node.name, tuple(ast.unparse(b) for b in node.bases)))
print(f"python_file_denominator={len(paths)}")
print(f"class_denominator={classes}")
print(f"parse_error_denominator={len(errors)}")
print(f"structural_match_denominator={len(rows)}")
for row in rows:
    print(*row, sep="\t")
PY
```

### P40 review bucket and bounded fixture residual

Final review found the same boundary class one level deeper: `handle_job()` can process a
pre-existing durable job when a test embedding manually injects the badged provider and
`_Port`. That is the existing behavioral worker receipt path, not a production binding.

**Ruling:** retain this direct fixture witness and do not call it production-safe. The
public production `execute()` route cannot create its reservation or job, the complete
port census finds no production implementation, and the worker result remains fixture
badged. The bounded residual is explicit: a pre-existing job plus manual injection of
both test collaborators can still exercise `handle_job()`; that is why the production
N13b row stays open. The cost if this ruling is wrong is a stale queued job becoming
effect-capable under a future embedding that injects the fixture collaborators. The
smallest future closure is the missing tenant-bound production port and an owner-derived
production/fixture discriminator, not suppression or relabeling of the fixture receipt.
The scoped re-review accepted that classification and withdrew the provisional Important
finding: retaining the direct fixture is required for the DS15 receipt, while the public
route cannot enqueue it and the complete census establishes zero production bindings.

### INT-R2 producer and artifact measurement

```bash
rg -n 'GapAcquisitionCase|gap_acquisition_case' src tests schemas architecture
```

Exit `1`, zero matches. The searched denominator is 5,092 Python plus 1,036 JSON files:
`src` 2,611 `.py` / 10 `.json`; `tests` 2,471 `.py` / 381 `.json`; `schemas`
0 `.py` / 143 `.json`; `architecture` 10 `.py` / 502 `.json`. Therefore neither the
ratified producer nor its typed persisted artifact exists in the tree. The verdict names
both absences; it is not the generic phrase “waiting on INT-R2.”

### Numeric VoI residual denominator

The canonical N13a artifact census read all 15 `growth_backlog` rows. The distribution is
15 of 15 `metric_residual_granularity_not_supported`, across these 15 row IDs:
`avg_hh_income_uah`, `particulate_emissions`, `residential_peak_demand`,
`avg_household_income`, `cells.distress_score`,
`combined_demand_emissions_burden`, `global.tax_rate`, `government.balance`,
`heat_wave_environmental_equity_burden`, `learning`,
`low_income_renter_energy_costs`, `msme_credit_access`, `msme_survival_rate`,
`teaching`, and `watershed_slope`. No numeric granularity was inferred.

```bash
uv run pytest tests/repo_quality/tools/test_layer3_gy_n13a_acquisition_census.py::test_growth_backlog_ranks_full_residual_denominator_without_claiming_voi -q
```

Exit `0`, one test node passing.

### Fresh-positive production route measurement

```bash
uv run pytest \
  tests/unit/runtime/http/test_acquisition_surface_projection.py::test_acquisition_growth_keeps_qualification_and_n13b_history_negative \
  tests/unit/runtime/quality/test_semantic_epoch.py::test_production_acquisition_invokes_epoch_adapter_and_returns_policy_admission_missing \
  -q
```

Exit `0`, two test nodes passing. The current projection remains no-growth/history
negative, and production qualification returns `policy_admission_missing`. The new
boundary test independently establishes that injected collaborators cannot turn those
facts into `ready` or a production reservation. This is negative evidence only; it does
not manufacture the positive route the row requires.

### Deterministic admission bundle census

The complete 5,092-Python-file AST census found exactly two constructor calls across the
four roots: `AgentActionAdmissionBundle(...)` at
`tests/unit/runtime/quality/test_agent_action_authority.py:484` and
`AgentActionAuthorityGateway(...)` at line 586 of that same test file. There is no source
constructor for the bundle, no source writer for
`runtime_quality.agent_action_admission`, and no production invocation-to-artifact
mapping. Source only defines and validates the contract, consumes a caller-supplied
`admission_refs_by_invocation_hash`, reads and verifies the signed artifact, and fails
closed when the mapping is absent.

```bash
uv run pytest tests/unit/runtime/quality/test_agent_action_authority.py::test_missing_governed_admission_bundle_never_fires_effect -q
```

Exit `0`, one test node passing with zero external effect. This measures the three
engineering absences separately: producer, persisted signed artifact, and invocation
bridge. The signature slot is present and empty; Task E appoints no signer.

### DS15 receipt production and separate GY non-admission

Supply-side receipt production:

```bash
uv run pytest \
  tests/unit/runtime/http/test_acquisition_route_authority_sink.py::test_active_owner_receipt_persists_reentry_pending_before_callback \
  tests/unit/runtime/http/test_acquisition_control_worker.py::test_worker_loads_durable_decision_before_sealed_effect_and_terminal \
  -q
```

Exit `0`, two test nodes passing. The first node persists requested → executing →
world-committed/re-entry-pending → terminal receipts, reads the durable head back, checks
the CAS manifest kind `runtime_quality.acquisition_route_loop_receipt`, schema
`polisyos.runtime.AcquisitionRouteLoopReceipt`, terminal payload and predecessor, and a
distinct durable terminal event. The second node demonstrates the explicitly badged
worker fixture loading a durable decision before the sealed effect and terminal head.
This is the DS15 runtime receipt measurement; it is not GY admission and is not a
production-port measurement.

The admission-side predicate is separate:

```bash
uv run pytest \
  tests/unit/runtime/quality/test_generation_cycle.py::test_active_overlay_reentry_rejects_binding_and_trace_mutations \
  tests/integration/runtime_quality/test_chronology_protocol_conformance.py::test_adapter_cannot_admit_source_or_accept_anchor \
  tests/integration/runtime_quality/test_chronology_protocol_conformance.py::test_novel_member_unknown_relation_or_provenance_fails \
  tests/repo_quality/test_chronology_terminal_state.py::test_cluster4_terminal_labels_match_source_derived_chain \
  -q
```

Exit `0`, four test nodes passing. These preserve exact same-case N13b binding and the
generic chronology authority boundary; they do not produce a movement-family admission.
`CycleBoardProjectionService` still constructs `CycleBoardMovementGap()` unconditionally,
whose `execution_status` is `not_established` and whose movement-record denominator is
zero records. Thus DS15 receipt production and GY admission are two separately measured
facts, and only the supply side moved.

### `external_nonclosures` bidirectional reconciliation

Source-to-register, over the tuple's four entries:

| contract tuple entry | register mapping | reconciliation |
| --- | --- | --- |
| `fresh_positive_production_route:absent/unallocated` | `ds15-fresh-positive-production-route` | exact semantic name and capability label; the only exact match |
| `current_mandate_owner:producer_missing` | sibling `ds15-signed-v2-delegation-mandate-owner-authority`, outside the seven-row denominator | shortened composite and weaker label: the row records `producer_missing + artifact_missing`, primary `absent/unallocated` |
| `deterministic_admission_bundle:producer_missing` | `ds15-deterministic-admission-bundle-producer` | partial/stale name and partial label: the row records producer + artifact + bridge missing, primary `absent/unallocated` |
| `non_fixture_n13b_owner_port:bridge_missing` | `ds15-production-n13b-execution-handshake` | noncanonical name and label disagreement: the row's production implementation is `producer_missing`, not merely `bridge_missing` |

Seven-row-register-to-source:

- exact: `ds15-fresh-positive-production-route`;
- present but narrowed/stale: `ds15-production-n13b-execution-handshake` and
  `ds15-deterministic-admission-bundle-producer`;
- omitted from the tuple: `ds15-numeric-voi-metric-residual-granularity`,
  `ds15-int-r2-gap-acquisition-case-union`,
  `ds15-gy-gap6-evidence-register-closure`, and `GY-GAP6`;
- tuple-only relative to the seven rows: the signed-delegation/current-mandate sibling.

This is a finding, not a repair: changing that public default would enter the contract
generation/dashboard corridor. No tuple or generated mirror was edited.

### GY-GAP6 routable specification

The specification is routed to the owners already named by GY, not to Task E:

1. **Movement-family owner.** In
   `architecture/production_quality/chronology_capability_allocation.toml`, ordinal 5 is
   `subject_key = "movement_family_producer"`, `status = "absent/unallocated"`,
   `canonical_owner_ref = "movement"`, `routing_ref = "GY-GAP6"`, and activation
   `deferred_gy_gap6`. The missing GY-N13b artifact must bind the exact GY row identity,
   requirement-gap identity, admitted DS15 acquisition receipt and acquisition date,
   active overlay/semantic-epoch receipts, the same `DesignProblem` and source cycle,
   `AcquisitionOverlayReentryReceipt`, and a distinct deeper producer-owned terminal.
   Deletion, substitution, or cross-case replay of any member must fail.
2. **Policy and admission index.** Reuse
   `src/polisyos/core/contracts/chronology.py`:
   `PredicateAdmissionPolicyStatement`, `PredicatePolicyAdmissionStatement`,
   `PredicatePolicyAdmissionIndex`, and `PredicatePolicyOwnerProvenanceVerifier`.
   `src/polisyos/runtime/quality/chronology_qualification.py` already provides
   `NativeChronologyAuthorityAdapter` and `QualificationConsumer.qualify()`, which
   resolves the admission index, content-binds policy, owner relation and owner
   provenance, reconciles the native candidate, and requires a verified owner receipt.
   Missing predicates are a movement-native adapter, a persisted movement policy and
   admission statement, a movement admission-index implementation, independently
   verified owner relation/provenance, and an owner-container bridge. The gate's basis
   must be `recomputed` or `independently_reconciled`; `consumer_asserted`,
   `institutionally_supplied`, and `not_established` fail closed.
3. **N13b re-entry producer.** Reuse
   `GenerationCycleController.reenter_after_active_acquisition_overlay()` and
   `AcquisitionOverlayReentryReceipt` in
   `src/polisyos/runtime/quality/generation_cycle.py`. They already bind the design
   problem, source cycle, active owner overlay, passport, semantic epoch, production
   receipt, new cycle, and content hash. They do not bind a GY row, acquisition date, or
   movement-family chronology head, and therefore cannot be projected as GY movement
   without the owner artifact above.
4. **Cycle Board consumer.** In `cycle_board_sources.py`,
   `N13BGlobalMovementSignal` is explicitly denied for `N13B_DENIED_ROW_USES` = per-row
   movement, row enumeration and exhaustiveness. In `cycle_board_projection.py`,
   `CycleBoardProjectionService.project()` reads that global signal but constructs
   `CycleBoardMovementGap()` unconditionally. In `cycle_board_contracts.py`,
   `CycleBoardMovementGap` fixes `not_established` and an empty movement-record tuple,
   while `CycleBoardRow.movement_records` remains an unowned tuple of dictionaries. The
   missing consumer predicate is a typed, owner-qualified per-row movement projection
   carrying policy/admission/head identities; raw dicts or the global N13b status cannot
   satisfy it.

**Owner recommendation:** do **not** route this into `GY-AQ1`. That task is explicitly
the generic **non-data** acquisition plane and W5-K01 ceiling algebra; GY-GAP6 is the
data-acquisition movement/admission chain. Combining them would mix planes and create a
P38 proxy gate. Retain `GY-GAP6` as the routed task, with its already-declared split:
GY-N13b owns admitted acquisition plus same-cycle re-entry; GY-N12 owns append-only
chronology/policy admission; Cycle Board is the consumer. This appoints no new role.

### Institutional slots and out-of-scope findings

Task E added no appointment and wired no new institutional authority. It preserved these
typed empty slots:

- semantic-epoch policy authority:
  `QualificationConsumer.from_unallocated_policy_authority()` returns
  `policy_admission_missing` before native candidate reconciliation;
- signed v2 mandate/current-owner evidence:
  `AgentActionAuthorityGateway._resolve_current_mandate_authority()` returns
  `current_mandate_authority_not_established` unless an externally signed, current,
  independently reconciled artifact exists;
- deterministic-bundle signature slot: signed-CAS verification remains present, while
  the engineering producer, artifact, and invocation map remain absent.

The GY movement owner, policy, admission index, chronology container, and Cycle Board
consumer are out of this lane and were specified, not edited. The public OpenAPI source,
generated schema/client/dashboard corridor, runtime-quality sources, active GY plan,
chronology allocation, debt register, ledger, and checker pins were read-only. No need to
edit `runtime/http/dependencies.py`, `promotion_sequence.py`, or
`architecture/imports/*.toml` arose.

## Final verification receipts

Frozen-source acquisition verification:

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

Exit `0`: 11 targeted acquisition nodes passed and Ruff reported `All checks passed!`.

```bash
PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py
```

Exit `1` with exactly six findings, matching the supplied inherited denominator: two
`active_plan_metadata` findings on `docs/plans/active/LEDGER.md` and four
`removed_stub_reference` findings for the supplied legacy frontend alias.

```bash
PYTHONPATH=. uv run python tools/quality/validation/check_debt_ledger.py --check
```

Exit `1`, not the brief's predicted `0`. The bound checker reports 151 register IDs,
32 pytest closure selections, and 18 of 18 `closure_signal_identity_unresolvable`
findings, with zero collection-host-unknown degradations. This is the repository's
already-registered `debt-closure-signals-name-unwritten-tests` defect: the exact rows are
open and their future closure tests do not exist yet.

P41 attribution was replayed from a temporary detached clone at the exact slice base
`784d020148c56e9bfb3a3631909ba11232210a9f`, with import readback resolving
`polisyos` inside that base clone. The base command also exited `1` and reproduced the
same 32-selection / 18-unresolvable identity class and the same 18 row IDs. The clone
additionally reported history/ledger findings caused by evaluating an old detached base
against its newer local `main` ref; those are not used for attribution. The identical
18-row class predates Task E. None of Task E's four changed paths is the debt register,
generated ledger, checker, active GY/Atlas plan, or any of the 32 selected missing test
identities. Task E did not edit the architect-owned checker pin to manufacture exit `0`.

The first architecture-guardrail attempt exited `1` as a tooling non-receipt: its
fresh-generation scratch lacked pnpm links (`prettier` and `openapi-typescript` were not
resolvable), and the trust-posture probe saw the still-uncommitted plan. The required
frozen toolchain provision then succeeded:

```bash
corepack pnpm install --frozen-lockfile
```

Exit `0`, 1,215 workspace packages linked with no lockfile change. A clean-tree
architecture rerun then established both generated corridors as fresh:

```bash
uv run polisyos-tools architecture guardrails check
```

Exit `1`: `runtime-api-client` was clean over five generator-observed outputs and
`runtime-dashboard-api-types` was clean over one generator-observed output. The sole
remaining failure was the trust-claim-posture register's
`ratified identity basis differs from the admitted closed receipt` validation.

That remaining failure was separately replayed with
`PYTHONPATH=. uv run python tools/quality/validation/check_trust_claim_posture.py
--repo-root . --check` at Task E HEAD and with base-first imports in the detached
`784d02014` clone. Both exited `1` at the same identity-basis predicate. A complete diff
of its three inputs — `posture.py`, `check_trust_claim_posture.py`, and the ratified
identity document — exited `0` between the Task E base and HEAD. It is therefore an
inherited architecture non-receipt outside this lane, not a reason to edit the identity
constant, generated register, or another owner's source. Task E records it and leaves it
unchanged.

```bash
git diff --check
git diff --name-only 784d020148c56e9bfb3a3631909ba11232210a9f -- \
  schemas/runtime_api_v1.openapi.json packages/runtime-api-client apps/runtime-dashboard \
  src/polisyos/runtime/http/openapi_contract.py docs/plans/active/DEBT-REGISTER.md \
  docs/plans/active/LEDGER.md docs/plans/active/layer3-slices/GY-engine-subordination.md \
  docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md \
  tools/quality/validation/check_debt_ledger.py
```

Both predicates exited `0`; the protected-path diff printed zero paths. The complete Task
E path denominator is four paths: the mandated plan, mandated journal, acquisition action
service, and one acquisition integration test. In particular, Task E changed neither
`schemas/runtime_api_v1.openapi.json`, `packages/runtime-api-client/**`,
`apps/runtime-dashboard/**`, nor `src/polisyos/runtime/http/openapi_contract.py`.

## Register closure dossier

### `ds15-fresh-positive-production-route`

- **Verdict:** `open`.
- **Predicate / exit:** the two-node fresh-positive negative command above exited `0`;
  the two-node production-boundary command exited `0`. No command produced the required
  positive production object.
- **Exact prose to append beneath the row:**

  > **TASK E MEASUREMENT 2026-08-31 — open.** The current production projection remains
  > no-growth/history-negative and production epoch qualification remains
  > `policy_admission_missing`. The sole backend route projection now keeps both
  > capability fields `producer_missing` even when fixture collaborators are injected,
  > and production execution refuses before reservation or enqueue. These are honest
  > negative receipts, not the missing positive route; no current non-fixture
  > data-shaped route, qualified active epoch, positive admitted delta, and exact
  > same-case re-entry exist together.

### `ds15-production-n13b-execution-handshake`

- **Verdict:** `open`.
- **Predicate / exit:** the complete 5,092-file / 12,005-class AST census above exited
  `0`: two structural matches = one source `Protocol` + one test-only `_Port`; zero
  source implementations. The production-boundary regression exited `0` and proves
  no reservation/job can be created through the badged public route.
- **Exact prose to append beneath the row:**

  > **TASK E MEASUREMENT 2026-08-31 — open.** A complete AST census of 5,092 Python
  > files and 12,005 class definitions found exactly two strict-port-shaped classes:
  > the source `AcquisitionExecutionPort` protocol and the test-only `_Port` manually
  > bound by `_worker_harness` to `tenant-a/cell-a/run-ds15`. No source or tenant-bound
  > production implementation exists. The fixture worker can still produce its badged
  > receipt directly, while the production execute route now fails before provider,
  > reservation or job creation. The direct fixture is not the missing production port.

### `ds15-numeric-voi-metric-residual-granularity`

- **Verdict:** `open`.
- **Predicate / exit:** the exact canonical census test above exited `0`; the complete
  artifact denominator is 15 growth-backlog rows, and 15 of 15 carry
  `metric_residual_granularity_not_supported`.
- **Exact prose to append beneath the row:**

  > **TASK E MEASUREMENT 2026-08-31 — open.** The canonical N13a acquisition census
  > contains 15 growth-backlog rows and all 15 report
  > `metric_residual_granularity_not_supported`; the owner semantic test passes. No
  > measure, population, horizon, assumptions, authority source, content-bound owner
  > decision, expected-value inputs, or acquisition-cost inputs exist from which a
  > numeric granularity could honestly be produced. Task E preserved the typed refusal.

### `ds15-int-r2-gap-acquisition-case-union`

- **Verdict:** `blocked`.
- **Predicate / exit:**
  `rg -n 'GapAcquisitionCase|gap_acquisition_case' src tests schemas architecture`
  exited `1` with zero occurrences across 5,092 Python and 1,036 JSON files.
- **Exact prose to append beneath the row:**

  > **TASK E MEASUREMENT 2026-08-31 — blocked.** The ratified INT-R2 research is in the
  > tree, but a complete four-root search finds zero `GapAcquisitionCase` or
  > `gap_acquisition_case` occurrences. The ratified producer is missing and the typed
  > persisted artifact is independently missing. This is not a generic wait on INT-R2;
  > those are the exact two absent closure predicates.

### `ds15-gy-gap6-evidence-register-closure`

- **Verdict:** `blocked`.
- **Predicate / exit:** the two-node DS15 receipt-production command exited `0`; the
  separate four-node GY boundary command exited `0`, while
  `CycleBoardMovementGap.execution_status` remains `not_established` with zero movement
  records.
- **Exact prose to append beneath the row:**

  > **TASK E MEASUREMENT 2026-08-31 — blocked after supply-side progress.** DS15's
  > acquisition-route sink now has a replayable runtime receipt measurement: requested,
  > executing, world-committed/re-entry-pending and terminal records persist to CAS,
  > read back through the durable head, and emit a distinct terminal event. A separate
  > GY measurement still renders `CycleBoardMovementGap` with
  > `execution_status=not_established` and zero movement records. DS15 supplied the
  > receipt witness; no GY movement owner has admitted it into GY evidence or registered
  > closure. One measurement was not used for both ends.

### `GY-GAP6`

- **Task E disposition:** specification only; Task E issues no closure verdict. Its
  existing registered standing is `blocked`, used only for the required seven-row
  arithmetic.
- **Predicate / exit:** the four-node GY boundary command above exited `0`; the exact
  current source predicate is the unconditional `CycleBoardMovementGap()` construction,
  with `not_established` and zero movement records. The routable files, symbols, missing
  predicates, and ownership split are specified in the preceding section.
- **Exact prose to append beneath the row:**

  > **TASK E ROUTING SPECIFICATION 2026-08-31 — existing blocked standing unchanged;
  > no Task E closure verdict.** Route implementation through GY-GAP6's declared owners:
  > GY-N13b must produce the movement-family artifact binding one row's admitted DS15
  > receipt/date, active overlay and semantic epoch, exact DesignProblem/source cycle,
  > AcquisitionOverlayReentryReceipt and a distinct deeper producer terminal; GY-N12
  > must persist and admit the movement policy, owner relation/provenance, native
  > adapter, admission-index entry and append-only head through the existing chronology
  > qualification path; Cycle Board must consume a typed owner-qualified per-row record.
  > The global N13b signal remains denied for per-row use. Do not route this data-movement
  > chain into non-data task GY-AQ1.

### `ds15-deterministic-admission-bundle-producer`

- **Verdict:** `open`.
- **Predicate / exit:** the complete 5,092-file AST census exited `0` with the only
  bundle and gateway constructors in one unit-test harness; the missing-bundle negative
  test exited `0` and produced zero external effect.
- **Exact prose to append beneath the row:**

  > **TASK E MEASUREMENT 2026-08-31 — open.** The governed
  > `AgentActionAdmissionBundle` contract, signed-artifact resolver and fail-closed
  > consumer exist, but the complete Python census finds bundle construction,
  > persistence and invocation mapping only in a unit-test harness. Production still
  > lacks three separate engineering objects: the deterministic producer, its persisted
  > signed artifact, and the invocation-to-artifact bridge. The signature slot remains
  > typed and empty; no signer was appointed.

### Dossier arithmetic

- Seven measured register rows = zero `closed` + four `open` + three `blocked` + zero
  `ambiguous`.
- Four core rows = zero `closed` + three `open` + one `blocked` + zero `ambiguous`.
- Three adjacent rows = zero `closed` + one `open` + two `blocked` + zero `ambiguous`.

For closure jurisdiction, Task E adjudicates six rows: four `open` and two `blocked`.
The seventh, `GY-GAP6`, contributes its pre-existing registered `blocked` standing only
to satisfy the requested seven-row equation; Task E supplies a specification and does
not claim authority to change its verdict.
