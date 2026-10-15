# E1.5 (Phase 5) — Foundry: dependency cleanup + compiler split (`surface_compiler` vs `trinity_compiler`)

**Repo snapshot date**: 2026-02-03  
**Scope**: `policy-engine/src/polisyos/foundry/*` + touchpoints in `core/contracts/*`, `core/compiler/*`, `ir/linker/*`, `scientist/*`, and `tests/*`\
**Primary goal**: make Foundry a **pure-compute** core (CAS-in/CAS-out), remove upper-layer leaks, and physically split compilation into:

- **Legacy**: `PolicySurfaceIR → ExecPlan` (surface compiler, frozen compatibility)
- **Canonical**: `TrinityBundle → ExecPlan` (`trinity_compiler`, the primary path forward)

From the outside, Foundry still exposes **one facade**, `compile()/execute()`, which selects a compiler by input type (or flag) without mixing the models.

> Historical snapshot note: Repository-state statements describe the dated snapshot above; phase labels and completion criteria belong to that historical plan. They do not establish current E02 status or end-to-end functionality.

---

## 0) Phase goal (what should change in practice)

After E1.5:

1. **Foundry = pure compute**:
   - inputs: only **IR/Core contracts** and/or **CAS refs** (`ArtifactRef`, typed refs from `core.contracts.*`)
   - outputs: only **CAS artifacts** (through `FileSystemCAS.put_*`) + typed refs
   - Foundry does **not know** about Scientist (not through types, imports, or governance profiles).

2. **Policy compilation is split**:
   - `surface_compiler` serves legacy `PolicySurfaceIR` (frozen: compatibility and bug fixes only)
   - `trinity_compiler` serves Trinity (`ProblemFrame/PolicySpec/ModelSpec`) and builds on `ir.linker.link_trinity()`.

3. **One public entry API**:
   - `polisyos.foundry.compile.api.compile(request) -> CompileResult`
   - `polisyos.foundry.execute.api.execute(request) -> ExecuteResult`
   - select a compiler **by the input ref kind** (`ir.policy_surface` vs `ir.trinity_bundle`) or explicit `input_kind`.

4. **Dependencies must be clean**:
   - the import gate (`tools/quality/lint/lint_imports.py` + `architecture/imports/policy.toml`) passes
   - Foundry contains no imports of `polisyos.scientist.*` or `polisyos.fabric.*` implementations (the `core.contracts.fabric` contracts are allowed).

---

## 1) Preconditions (what already exists after E1.1–E1.4)

### 1.1 Import gate / Dependency-guard

Source of truth: `policy-engine/docs/adr/0004-architecture-boundaries-import-gate.md`, `policy-engine/architecture/imports/policy.toml`, `policy-engine/tools/quality/lint/lint_imports.py`, and test `policy-engine/tests/repo_quality/architecture/test_arch_import_gate.py`.

Current rule: `foundry` may import only `foundry|core|ir|common` (see `architecture/imports/policy.toml`).

### 1.2 Trinity and the Linker already exist

- `polisyos.ir.trinity.TrinityBundle` (payload contract)
- `polisyos.ir.linker.link_trinity()` + `LinkedTrinityBundle` + `LinkReport` (deterministic, no I/O)
- the legacy surface linker lives in `polisyos.ir.linker.legacy_surface.link_policy()`

### 1.3 Core ports already exist

Key artifact ports and refs used in E1.5:

- `polisyos.core.contracts.foundry`:
  - `ProgramGraphRef`, `ExecPlanRef`, `StateSnapshotRef`, `MetricsRef`, `ConstraintReportRef`
  - `SimulationResultRef` + `SimulationResult` envelope (introduced in E1.4, but not yet used everywhere)
- `polisyos.core.contracts.trinity`:
  - `TrinityBundleRef` (kind=`ir.trinity_bundle`)
- `polisyos.core.contracts.compiler`:
  - `LinkReportRef` (kind=`compiler.link_report`)
  - `CompileReportRef` (kind=`compiler.compile_report`)
- Core registry plumbing:
  - `polisyos.core.registry.build_default_registry_bundle()` creates `core.registry_bundle`
  - `polisyos.core.registry.load_registry_bundle_content()` loads typed registries from the bundle

---

## 2) Current repository state (important for E1.5)

### 2.1 Legacy compilation (surface)

File: `policy-engine/src/polisyos/foundry/compiler.py`

- `put_policy_surface(store, policy) -> PolicySurfaceIRRef` stores `ir.policy_surface` in CAS.
- `compile_surface_policy(store, policy, mechanism_registry, slot_registry, merge_registry, ...) -> CompileArtifacts`
  - builds a `ProgramGraph` (`foundry.program_graph`)
  - builds an `ExecPlan` (`foundry.exec_plan`)
  - stores supporting artifacts: `foundry.slot_layout`, `foundry.treasury_plan`

Key current fact for the split:

- `ProgramGraph.ir_ref` in `core.contracts` is typed as `PolicySurfaceIRRef`, so the Trinity path is currently impossible without changing the port.

### 2.2 Execution (`execute`)

File: `policy-engine/src/polisyos/foundry/executor.py`

- `execute_program_graph(...) -> ExecuteArtifacts`:
  - reads `ProgramGraph`/`ExecPlan` from CAS
  - executes steps and returns:
    - `foundry.state_delta` + `foundry.metrics`
    - optionally, `foundry.constraint_report`
    - optionally, `foundry.environment_manifest` (`capture_env=True` by default at this time)

Key current fact for Trinity:

- the executor extracts constraint values by loading `PolicySurfaceIR` through `program_graph.ir_ref`.
  - for Trinity, this location must be extended to recognize `ir.trinity_bundle` and extract constraints from `ProblemFrame`.

### 2.3 Scientist currently calls the legacy compiler directly

File: `policy-engine/src/polisyos/scientist/orchestrator/flow_nodes.py`

- calls `link_policy(...)` (legacy linker) + stores `compiler.link_report`
- then calls `compile_surface_policy(...)` directly

This is the migration point: in E1.5, Scientist must call the **Foundry facade** (see §8).

---

## 3) Non-goals (out of scope for E1.5)

E1.5 does **not**:

- implement Fabric World Graph / Doc/Claim pipelines / Lex/Scholar (those are E2+).
- unify “component-based” extensibility across all plugins (that is E3; the skeleton already exists in E1.4).
- rewrite the `polisyos.foundry.plugins` system (it is not the target ExecPlan compiler).

E1.5 does only what is necessary for:

- a clean Foundry compute core,
- two compilers,
- one stable `compile`/`execute` facade,
- migration of Scientist calls and the test setup.

---

## 4) 5.2 Audit: find and classify dependency/I/O leaks

### 4.1 Dependency scan results (imports)

In the 2026-02-03 snapshot, `polisyos.foundry.*` has **no**:

- `import polisyos.scientist.*`
- `import polisyos.fabric.*`

This matches the import gate and is an E1.5 **invariant**: any new `foundry.compile/*` and `foundry.execute/*` modules must preserve it.

### 4.2 Direct I/O inside Foundry (violates “pure compute” if the package boundary is used)

The following are locations where code under `polisyos.foundry.*` works with files, subprocesses, or the outside world beyond CAS.

> Important: some of these locations are tooling/dev-only. E1.5 fixes the rule that the **Foundry compute kernel** (`compile`/`execute`) performs none of these operations; tooling is moved out or isolated (see §9).

#### 4.2.1 Leak table and replacement classification

| Location                                                                         | Symptom                                                                   | I/O leak type          | Replacement classification                      | E1.5 normative decision                                                                                                                                            |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | ---------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `polisyos.foundry.calibration.preflight.fetch_targets()`                         | calls `udf_engine.query()` / `fetcher(...)`                               | I/O (world/data plane) | **Orchestration** (belongs in Scientist/Fabric) | Move fetching to Scientist. Foundry receives `raw_targets` as an input artifact/parameter.                                                                         |
| `polisyos.foundry.execute.executor.execute_program_graph(..., capture_env=True)` | calls `capture_environment()` by default (FS, git, deps)                  | I/O (host env)         | **Orchestration/observability** (control plane) | Set `capture_env=False` by default in the kernel API; Scientist/RunContext captures the environment and passes refs.                                               |
| `polisyos.foundry.methods.artifacts`                                             | reads source files (`Path.open`) and calls `git` through `subprocess.run` | I/O + subprocess       | **Needed as a contract/metadata**               | Move source-fingerprint computation to Core (env manifest) or build time. A method artifact must refer to an already pinned artifact/ref, not read the filesystem. |
| `polisyos.foundry.plugins.cli`                                                   | reads/writes result files and creates directories                         | FS I/O                 | **Tooling**                                     | Move the CLI to `policy-engine/tools/` or `polisyos.runtime` (outside the compute kernel).                                                                         |
| `polisyos.foundry.agent_sim.*`                                                   | writes configs/metrics/artifacts to the run directory                     | FS I/O                 | **Tooling / demo**                              | Move to `polisyos.runtime`/`tools` or mark as a separate package (not part of the compute kernel).                                                                 |
| `polisyos.foundry.methods.testing.golden`                                        | stores “golden records” on the filesystem                                 | FS I/O                 | **Test infrastructure**                         | Move to `tests/` or `policy-engine/tools/` (do not keep under `polisyos.foundry.*`).                                                                               |

#### 4.2.2 Minimal E1.5 cut (to keep the phase bounded)

For E1.5, it is sufficient to:

1. **Make the new `compile`/`execute` facades strictly CAS-only** (see §6–§8).
2. Fix the **policy**: no I/O tooling modules are imported from `polisyos.foundry.__init__` or pulled transitively into `compile`/`execute`.
3. (Recommended) add a “no I/O in kernel” unit test for `polisyos/foundry/compile/*` and `polisyos/foundry/execute/*` (see §11.7).

Tooling can be moved entirely out of the Foundry package in a separate PR/sub-phase without blocking the compiler split.

---

## 5) 5.3 Foundry API design (a minimally stable “port”)

### 5.3.1 Principle: “refs and contracts only”

The Foundry facade does **not accept**:

- live Scientist objects (state machine, governance profile, UDF engine, DB handle, etc.)

The Foundry facade **accepts only**:

- Pydantic models from IR/Core (`polisyos.ir.*`, `polisyos.core.contracts.*`)
- CAS refs (`ArtifactRef` and typed refs)

### 5.3.2 Changes required in `polisyos.core.contracts.foundry` for E1.5

File: `policy-engine/src/polisyos/core/contracts/foundry.py`

#### A) Generalize `ProgramGraph.ir_ref`

**Problem:** `ProgramGraph.ir_ref: PolicySurfaceIRRef` currently blocks the Trinity path.

**E1.5 decision:** replace the field type with the base `ArtifactRef`:

- was: `ir_ref: PolicySurfaceIRRef`
- becomes: `ir_ref: ArtifactRef`

Invariants:

- `ir_ref.kind` MUST be one of:
  - `"ir.policy_surface"` (legacy)
  - `"ir.trinity_bundle"` (canonical)
- `ir_ref.media_type` SHOULD be `"application/json"`

> This change is backward-compatible with existing artifacts (payloads without the new fields remain valid).

#### B) Add compile/execute request/result envelopes

Add (or extend) these models:

1. `CompileRequest`
2. `CompileResult`
3. `ExecuteRequest`
4. `ExecuteResult`

##### `CompileRequest` (normative minimum)

```python
class FoundryValidationFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strict_schema: bool = True
    strict_link: bool = True
    allow_extra_params: bool = False
    strict_conflict_check: bool = True
    # reserved for future:
    allow_legacy_units: bool = False


class FoundryCompileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")

    # exec-plan knobs (must be serializable)
    mode: Literal["dev", "perf", "audit"] = "dev"
    jit: bool = True
    max_steps: int | None = None
    nan_guard_enabled: bool = False

    # determinism (no env capture here)
    determinism_tier: str | None = None  # "strict_cpu"|"best_effort_gpu"|"nondeterministic"
    random_seed: int | None = None

    # optional compile-time budgeting (no floats)
    cost_budget_max_total_ms: int | None = None
    cost_budget_max_memory_mb: int | None = None
    cost_budget_max_compile_ms: int | None = None
    cost_budget_max_per_mechanism_ms: int | None = None

    # parameters for cost estimate (if budget enabled)
    estimate_n_agents: int | None = None
    estimate_time_steps: int | None = None


class CompileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")

    input_kind: Literal["auto", "surface", "trinity"] = "auto"
    policy_ref: ArtifactRef  # MUST be ir.policy_surface or ir.trinity_bundle

    registry_bundle_ref: ArtifactRef | None = None  # kind="core.registry_bundle"
    compile_config: FoundryCompileConfig = Field(default_factory=FoundryCompileConfig)
    validation_flags: FoundryValidationFlags = Field(default_factory=FoundryValidationFlags)

    notes: list[str] = Field(default_factory=list)
```

Normative rules:

- `CompileRequest` MUST be serializable as canonical JSON (`polisyos.core.canon.to_canonical_bytes`) without floats.
- `input_kind="auto"` ⇒ select the compiler from `policy_ref.kind`.
- `input_kind!="auto"` ⇒ `policy_ref.kind` MUST match `input_kind` (otherwise validation fails).
- `registry_bundle_ref`:
  - if provided ⇒ use it
  - if not provided ⇒ the compiler tries to extract a ref from the input IR:
    - surface: `PolicySurfaceIR.semantic.registry_bundle_ref`
    - trinity: `TrinityBundle.model_spec.registry_bundle_ref`

##### `CompileResult` (normative minimum)

```python
class DerivedArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    ref: ArtifactRef


class CompileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")
    ok: bool

    exec_plan_ref: ExecPlanRef | None = None
    compile_report_ref: ArtifactRef  # kind="compiler.compile_report"

    derived_refs: list[DerivedArtifact] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
```

Invariants:

- `compile_report_ref` MUST always be present (even when `ok=False`).
- `derived_refs` MUST contain (when `ok=True`):
  - `role="program_graph"` → `foundry.program_graph`
  - `role="exec_plan"` → `foundry.exec_plan` (duplicating `exec_plan_ref` is allowed)
  - optionally: `slot_layout`, `treasury_plan`, `link_report`, `linked_trinity_bundle`

##### `ExecuteRequest` (normative minimum)

```python
class FoundryExecConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")
    seed: int = 0
    mode: Literal["dev", "perf", "audit"] = "dev"
    max_steps: int | None = None
    deterministic: bool = True
    capture_env: bool = False  # explicit, default off


class ExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")

    exec_plan_ref: ExecPlanRef

    # input data: prefer Fabric DataSnapshotRef long-term; support StateSnapshotRef short-term
    data_snapshot_ref: ArtifactRef | None = None  # kind="fabric.data_snapshot" (preferred)
    state_snapshot_ref: StateSnapshotRef | None = None  # compat path

    registry_bundle_ref: ArtifactRef | None = None  # kind="core.registry_bundle"
    exec_config: FoundryExecConfig = Field(default_factory=FoundryExecConfig)
    notes: list[str] = Field(default_factory=list)
```

Normative rules:

- `execute()` MUST be CAS-only (no DB/network).
- exactly one state source must be defined:
  - if `state_snapshot_ref` is set ⇒ use it
  - otherwise, if `data_snapshot_ref` is set ⇒ Foundry reads `core.contracts.fabric.DataSnapshot` and requires `data_ref.kind == "foundry.state_snapshot"` (temporary, until E2)
  - otherwise, return an error.

##### `ExecuteResult` (normative minimum)

```python
class ExecuteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")
    ok: bool

    simulation_result_ref: SimulationResultRef | None = None
    derived_refs: list[DerivedArtifact] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
```

Invariants:

- when `ok=True`, `simulation_result_ref` MUST be returned (kind=`foundry.simulation_result`)
- `derived_refs` SHOULD include:
  - `metrics`, `state_delta`, and optionally `constraint_report`, `environment_manifest`

### 5.3.3 Changes in `polisyos.core.contracts.compiler` (optional, but recommended)

File: `policy-engine/src/polisyos/core/contracts/compiler.py`

For stricter types:

- add a typed `RegistryBundleRef` (kind=`core.registry_bundle`) **or** keep `ArtifactRef`.

Not a blocker for E1.5, but it reduces boundary errors.

---

## 6) 5.4 Split the compilers: physical code decomposition

### 6.1 Structural goal

- Legacy and Canonical compilers are physically separated (different files/modules).
- The shared entry point (`compile.api`) selects the implementation.
- Old entry points remain as thin wrappers and are marked deprecated.

### 6.2 Recommended Foundry module structure

Target (E1.5):

```text
polisyos/foundry/
  compile/
    __init__.py
    api.py                 # facade compile(request) -> CompileResult
    surface_compiler.py    # legacy path
    trinity_compiler.py    # canonical path
    types.py               # internal types/helpers (not core.contracts)
    _io.py                 # internal CAS load/store helpers (optional)
    _graph.py              # internal graph builder shared by compilers (optional)

  execute/
    __init__.py
    api.py                 # facade execute(request) -> ExecuteResult

  legacy/
    __init__.py
    compiler.py            # deprecated wrappers around new facade
```

Transition state (backward compatibility):

- `polisyos.foundry.compiler` remains, but becomes a thin wrapper:
  - `compile_surface_policy(...)` → builds a `CompileRequest` and calls `foundry.compile.api.compile`
  - `put_policy_surface(...)` remains as a helper but is marked as a legacy convenience

### 6.3 “Gateway” between compilers (required invariant)

Both compilers must emit the same set of CAS artifacts:

- `foundry.program_graph`
- `foundry.exec_plan`
- optionally, `foundry.slot_layout`
- optionally, `foundry.treasury_plan`
- `compiler.link_report` (if linking happens inside `compile`)
- `compiler.compile_report` (always)

And use the same base runtime IR: `ExecPlan` + `ProgramGraph` from `polisyos.core.contracts.foundry`.

**Critical:** runtime execution by `ExecPlanRef` must not require Scientist objects (CAS + registries bundle ref only).

---

## 7) 5.5 `surface_compiler`: stabilize legacy without expanding its surface

### 7.1 Goal

- Preserve support for existing policies/tests using `PolicySurfaceIR`.
- Freeze the legacy “surface”: add no new features to the format.
- Move external calls to `CompileRequest`/`CompileResult`.

### 7.2 Surface compiler behavior (normative)

`polisyos.foundry.compile.surface_compiler.compile_surface(request, store) -> CompileResult`

Pipeline:

1. **Load policy**:
   - `policy = PolicySurfaceIR.model_validate(from_canonical_bytes(store.get_bytes(policy_ref)))`

2. **Resolve the registry bundle** (see §5.3.2):
   - `registry_bundle_ref = request.registry_bundle_ref or policy.semantic.registry_bundle_ref`
   - if missing ⇒ `ok=False`, `compile_report` with error `missing_registry_bundle`

3. **Load registries**:
   - `registry_content = load_registry_bundle_content(store, registry_bundle_ref)`

4. **Link legacy surface**:
   - `link_report = link_policy(policy, registry_content.mechanism_registry, slot_registry=..., units_registry=..., allow_extra_params=request.validation_flags.allow_extra_params, ...)`
   - save `compiler.link_report` (through `core.compiler.report.put_link_report`)
   - if `strict_link=True` and `not link_report.ok` ⇒ `ok=False`; emit `compile_report` and exit without compiling

5. **Compile the graph** (without Scientist references):
   - reuse the current implementation from `polisyos.foundry.compiler`:
     - build ProgramGraph nodes/edges
     - conflict check (CompileTimeConflictChecker)
     - cost-estimate gating (if a budget is enabled)

6. **Emit compile artifacts**:
   - `foundry.program_graph`
   - `foundry.exec_plan` (fields come from `request.compile_config`; `environment_*` remains `None`)

7. `foundry.slot_layout`, `foundry.treasury_plan` (if current logic is retained)
8. **Emit `compile_report`** (`compiler.compile_report`, always):
   - `ok`, `policy_ref`, `registry_bundle_ref`, `link_report_ref`, `program_graph_ref`, `exec_plan_ref`, `slot_layout_ref`, `treasury_plan_ref`

### 7.3 Prohibitions and compatibility

- `surface_compiler` must NOT import Trinity models.
- Any new domain-compilation logic must go into `trinity_compiler`, not `surface`.
- If the legacy code hard-codes registries/mechanisms:
  - either move to `registry_bundle_ref`
  - or move to `polisyos.foundry.legacy/*` and mark it explicitly as deprecated.

### 7.4 Backward-compat wrappers

Preserve existing public functions as thin wrappers:

- `polisyos.foundry.compiler.compile_surface_policy(...)`:
  - retaining the old signature is allowed (for tests/temporary compatibility)
  - internally:
    - optionally build `core.registry_bundle` from the supplied registries (if `bundle_ref` is not supplied)
    - set `policy_ref = put_policy_surface(...)` if needed
    - construct `CompileRequest(input_kind="surface", policy_ref=..., registry_bundle_ref=...)`
    - call `foundry.compile.api.compile(request)`
    - return legacy `CompileArtifacts` or move to `CompileResult` (the latter is preferable, gradually)

Deprecation:

- add `warnings.warn(..., DeprecationWarning)` on import/call of legacy entry points, without breaking all tests at once.

---

## 8) 5.6 `trinity_compiler`: canonical Trinity → ExecPlan path

### 8.1 Goal

- Make Trinity compilation first-class: `TrinityBundleRef` → `ProgramGraph/ExecPlan`.
- Use the IR linker `link_trinity()` as the single source for matching against registries.
- Do not add Scientist dependencies or use the legacy surface as an intermediate boundary format.

### 8.2 Inputs

`CompileRequest` with:

- `policy_ref.kind == "ir.trinity_bundle"` (payload = `polisyos.ir.trinity.TrinityBundle`)
- `registry_bundle_ref`:
  - from the request **or** from `bundle.model_spec.registry_bundle_ref`

Optional (not an E1.5 blocker, but useful):

- save `LinkedTrinityBundle` as a derived artifact (kind `compiler.linked_trinity_bundle`)

### 8.3 Pipeline inside the Trinity compiler (normative)

`polisyos.foundry.compile.trinity_compiler.compile_trinity(request, store) -> CompileResult`

#### Step 0: load inputs

1. `bundle = TrinityBundle.model_validate(from_canonical_bytes(store.get_bytes(policy_ref)))`
2. `registry_bundle_ref = resolve_registry_bundle_ref(bundle, request)`
3. `registry_content = load_registry_bundle_content(store, registry_bundle_ref)`

#### Step 1: validate_structural (schema-level)

Minimum checks:

- Pydantic validation (already occurs in `.model_validate`)
- additional checks that require no “world” context, only contracts:
  - `bundle.policy_spec.interventions` IDs are unique (already validated by `PolicySpec`)
  - `bundle.problem_frame.hard_constraints/soft_constraints` IDs are unique (already validated)

#### Step 2: resolve_symbols (linking)

1. Build an IR-level `RegistryBundle` from the loaded registries:

- `mechanisms = registry_content.mechanism_registry`
- `slots = registry_content.slot_registry`
- `merge_rules = registry_content.merge_registry`
- `constraints = registry_content.constraint_registry`
- `selector_fields = registry_content.selector_field_registry`
- `units = registry_content.units_registry`
- `metrics = registry_content.metric_registry` (if present)

1. Call:

`linked_bundle, link_report = link_trinity(bundle, registries, allow_extra_params=request.validation_flags.allow_extra_params, strict=request.validation_flags.strict_link)`

1. Persist link_report:

- `link_report_ref = put_link_report(store, link_report, inputs=[policy_ref, registry_bundle_ref])`

1. If `strict_link=True` and `not link_report.ok` ⇒ `ok=False`, emit `compile_report`, and return.

Optional:

- Persist `linked_bundle` as `compiler.linked_trinity_bundle` (schema `polisyos.ir.LinkedTrinityBundle`, version `linked_bundle.schema_version`) and add it to `derived_refs`.

#### Step 3: build_program_graph (deterministic)

Goal: use the same `ProgramGraph` contract as legacy, but:

- `ProgramGraph.ir_ref = policy_ref` (kind=`ir.trinity_bundle`)

Intervention mapping:

- for each `PolicySpec.interventions[i]`:
  - persist `ir.intervention_payload` (as in the current surface compiler): schedule/target/params/priority/notes
  - create `op.make_mask` (selector from `intervention.target`)
  - create `op.apply_mechanism`:
    - `mechanism_type = intervention.kind`
    - `params_ref = intervention_payload_ref`
    - take `inputs/outputs` from `linked_bundle.bindings.interventions[i].reads_slots/writes_slots`

Edges:

- `make_mask → apply_mechanism (depends_on)`
- slot dependency edges: writer → reader when `writer.outputs ∩ reader.inputs ≠ ∅`

Op nodes:

- `op.merge_state`
- `op.check_constraints`:
  - `constraint_ids`: collect from `bundle.problem_frame.hard_constraints + soft_constraints`
  - for E1.5, it is acceptable to store only IDs; “hard/soft” semantics remain in IR, with enforcement deferred

#### Step 4: build_exec_plan

For both compilers:

- `order = topological_sort(program_graph)`
- `exec_plan = ExecPlan(program_ref=..., order=..., mode=request.compile_config.mode, jit=request.compile_config.jit, max_steps=request.compile_config.max_steps, nan_guard_enabled=request.compile_config.nan_guard_enabled, determinism_tier=request.compile_config.determinism_tier, random_seed=request.compile_config.random_seed)`
- **do not** populate `environment_ref/environment_fingerprint` during compilation (environment capture moves to execute/control plane)

#### Step 5: emit artifacts

Persist:

- `foundry.program_graph` (inputs: policy_ref, registry_bundle_ref, intervention_payloads, link_report_ref)
- `foundry.exec_plan` (input: program_graph_ref)
- `foundry.slot_layout`, `foundry.treasury_plan` (if preserving parity with legacy)
- `compiler.compile_report` (always)

### 8.4 Trinity runtime changes (required for E1.5)

File: `policy-engine/src/polisyos/foundry/executor.py`

Task: make the location where the executor loads constraints from `PolicySurfaceIR` polymorphic:

- if `program_graph.ir_ref.kind == "ir.policy_surface"` ⇒ as now
- if `program_graph.ir_ref.kind == "ir.trinity_bundle"` ⇒
  - load `TrinityBundle`
  - build `constraint_values = {constraint.constraint_id: constraint.value}` from `ProblemFrame.hard_constraints/soft_constraints`

Invariant:

- the executor does not import Scientist
- the executor does not import Fabric implementations

---

## 9) 5.7 Pure-compute rules (strict)

### 9.1 Prohibitions inside the Foundry compute kernel (`compile`/`execute`)

Prohibited in these modules:

- `polisyos.foundry.compile.*`
- `polisyos.foundry.execute.*`
- and in modules they import transitively

**Prohibitions:**

1. `import polisyos.scientist.*`
2. `import polisyos.fabric.*` (except `polisyos.core.contracts.fabric`; contracts are allowed)
3. Any direct I/O outside CAS:
   - `open()` on arbitrary paths
   - reading/writing files with `Path.read_text/write_text/open`
   - `subprocess.run` (git, pip, etc)
   - network calls
   - direct DuckDB/GraphStore access

4. Any writes to FactLog/world state (that is the Fabric plane).

### 9.2 Allowed

1. CAS I/O through `polisyos.core.artifacts.store.FileSystemCAS`
2. Canonicalization through `polisyos.core.canon.*`
3. IR validation through `polisyos.ir.*` (linker, models)
4. Emitting traces/metrics as **CAS artifacts** (if done inside `execute` and without external I/O).

### 9.3 Practical strategy (E1.5)

To avoid moving the entire demo/tooling subsystem at once:

- keep the compute kernel in the new `foundry/compile` and `foundry/execute` packages and ensure they do not import tooling
- do not import existing I/O-heavy modules (`foundry.agent_sim`, `foundry.plugins`, `foundry.methods.testing`) from `compile`/`execute`
- (recommended) add a test scan confirming there is no `open(` / `subprocess.run` in `foundry/compile` and `foundry/execute` (see §11.7)

---

## 10) 5.8 Migrate external Foundry calls + facade API

### 10.1 Foundry facade: compile

File: `policy-engine/src/polisyos/foundry/compile/api.py`

Normative signature:

```python
def compile(store: FileSystemCAS, request: CompileRequest) -> CompileResult:
    ...
```

Behavior:

- validates the request (`schema_version`, `input_kind`/`policy_ref.kind`)
- selects the compiler:
  - `surface` if `policy_ref.kind == "ir.policy_surface"`
  - `trinity` if `policy_ref.kind == "ir.trinity_bundle"`
- always guarantees a `compiler.compile_report` is emitted

Critical:

- `compile()` does NOT accept `PolicySurfaceIR`/`TrinityBundle` directly as “live objects” in the public API;
  - tests may use an internal helper `compile_from_payload(...)`, but it does not count as a port.

### 10.2 Foundry facade: execute

File: `policy-engine/src/polisyos/foundry/execute/api.py`

Normative signature:

```python
def execute(store: FileSystemCAS, request: ExecuteRequest) -> ExecuteResult:
    ...
```

Behavior:

- loads `ExecPlan` and `ProgramGraph` from CAS
- resolves state:
  - `state_snapshot_ref` directly
  - or `data_snapshot_ref` → `DataSnapshot.data_ref` (requires `foundry.state_snapshot`)
- loads registries through `registry_bundle_ref` (or optionally from `program_graph` inputs, though explicit is preferred)
- calls the existing `execute_program_graph(...)`
- creates a `SimulationResult` envelope (`core.contracts.foundry.SimulationResult`) and saves it as `foundry.simulation_result`

Invariant: `capture_env=False` by default and is an **explicit** request flag.

### 10.3 Scientist migration: replace direct compiler calls

File: `policy-engine/src/polisyos/scientist/orchestrator/flow_nodes.py`

Current:

- `link_policy(...)`
- `compile_surface_policy(...)`

Target (E1.5):

- `compile_result = foundry.compile.api.compile(store, CompileRequest(...))`
- subsequent steps rely on refs from `compile_result`:
  - `compile_report_ref`
  - `exec_plan_ref` (if `ok`)
  - `derived_refs` (program_graph, slot_layout, treasury_plan)

Recommendation:

- keep the previous runtime logs (`log_artifact(...)`), but now log:
  - `compile_report_ref`
  - `link_report_ref` (if contained in `compile_report`)
  - `exec_plan_ref`

### 10.4 Scientist migration: execute through the execute facade (minimum)

`scientist/compute/runner.py` currently calls `execute_program_graph` directly.

For E1.5, choose and document one of these options:

**Option A (minimal changes):** leave the runner as it is, but add the “official” facade `foundry.execute.api.execute` and migrate calls gradually.

**Option B (port immediately):** the runner builds an `ExecuteRequest` and calls `foundry.execute.api.execute`, receives a `SimulationResultRef`, and then (if needed) loads the final state separately.

Option A + a smoke test for the execute facade is sufficient for E1.5.

---

## 11) 5.9 Testing and validation (required for the phase)

### 11.1 Dependency gate (already exists)

- `policy-engine/tests/repo_quality/architecture/test_arch_import_gate.py` must remain green.
- Add an E1.5 regression ensuring that new `foundry/compile/*` and `foundry/execute/*` modules do not violate `architecture/imports/policy.toml`.

### 11.2 Unit tests: surface_compiler

Add/update tests in `policy-engine/tests/unit/foundry/`:

- migrate existing compilation tests to the new facade (or retain a legacy wrapper until migration):
  - `test_program_graph_ops.py`
  - `test_constraints_executor.py`
  - `test_patch_executor.py`

Minimum new test:

- `compile(request)` with `input_kind="surface"`:
  - instantiates `FileSystemCAS(tmp_path)`
  - builds `core.registry_bundle` (`build_default_registry_bundle`)
  - stores `PolicySurfaceIR` in CAS (`put_policy_surface`)
  - calls the compile facade
  - checks:
    - `result.ok is True`
    - `result.exec_plan_ref.kind == "foundry.exec_plan"`
    - `program_graph` is present among `derived_refs`

### 11.3 Unit tests: trinity_compiler

New test (minimal Trinity fixture):

- build a `TrinityBundle`:
  - `ProblemFrame(domain=...)` without complex goals
  - `PolicySpec` with one intervention (`income_tax`/`tax_subsidy`)
  - `ModelSpec(data_snapshot_ref=<sha256 stub>, registry_bundle_ref=<bundle_ref.artifact_id>)`
- persist `ir.trinity_bundle` in CAS (kind=`ir.trinity_bundle`, schema=`polisyos.ir.TrinityBundle`)
- call the compile facade (`input_kind="trinity"` or `auto`)
- verify:
  - `ok=True`
  - `ProgramGraph.ir_ref.kind == "ir.trinity_bundle"` (the models were not mixed)
  - `ExecPlanRef` exists

### 11.4 Determinism test: same input → same `ArtifactID`

Normative test:

- call `compile` twice with the same `policy_ref`, `registry_bundle_ref`, `compile_config`, and `validation_flags`
- expect:
  - `exec_plan_ref.artifact_id` to match
  - `program_graph_ref.artifact_id` to match

For the test to be valid:

- `compile` must not include environment capture or timestamps in the payload.

### 11.5 Contract tests: canonical JSON (no floats)

Add to `policy-engine/tests/contract/`:

- `to_canonical_bytes(CompileRequest(...))` does not raise `CanonViolation`
- `to_canonical_bytes(CompileResult(...))` does not raise `CanonViolation`
- likewise for `ExecuteRequest/ExecuteResult`

### 11.6 Execute smoke test (minimal end-to-end)

Goal: prove that Foundry can create a `SimulationResultRef` without depending on Scientist/Fabric.

Smoke test:

1. compile a minimal policy (surface or Trinity) into an `ExecPlanRef`
2. create a `StateSnapshotRef`:
   - build a minimal `GlobalState` fixture (as in the current Foundry tests)
   - `put_state_snapshot(store, state=..., step=0)`

3. call `foundry.execute.api.execute` with `ExecuteRequest(state_snapshot_ref=..., exec_plan_ref=..., registry_bundle_ref=...)`
4. verify:
   - `ok=True`
   - a `SimulationResultRef` is returned (kind=`foundry.simulation_result`)

### 11.7 (Recommended) “no I/O in kernel” test

A simple test scan (as a safety net):

- iterate over `.py` files in `polisyos/foundry/compile/` and `polisyos/foundry/execute/`
- verify that these substrings are absent:
  - `"open("`
  - `"subprocess.run"`
  - `"requests."`

This does not replace architectural discipline, but it catches regressions.

---

## 12) 5.10 Definition of Done (E1.5)

The phase is complete when:

1. `polisyos.foundry` has no imports of `polisyos.scientist.*`.
2. Both compilers are implemented:
   - `polisyos.foundry.compile.surface_compiler`
   - `polisyos.foundry.compile.trinity_compiler`

3. One facade exists:
   - `polisyos.foundry.compile.api.compile(request) -> CompileResult`
   - `polisyos.foundry.execute.api.execute(request) -> ExecuteResult`

4. `ProgramGraph.ir_ref` supports `ir.policy_surface` and `ir.trinity_bundle` without mixing the models.
5. `compiler.compile_report` is always emitted; errors/warnings are recorded as artifacts.
6. Tests:
   - the import gate passes
   - surface and Trinity compiler unit tests pass
   - the determinism test passes
   - the execute smoke test passes

## D1-L4 Validation Links

| Link type           | Current anchor                                                                                                                                                                                                                  |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source plan phase   | D1-L4 Phase 0 Trinity/linker contract and Phase 2 compiler pipeline inputs                                                                                                                                                      |
| Contract tests      | `tests/contract/test_foundry_facade_contracts.py`, `tests/contract/test_foundry_input_bindings_contract.py`, `tests/unit/foundry/compile/test_trinity_compiler.py`, `tests/unit/foundry/compile/test_trinity_field_coverage.py` |
| Schema snapshots    | `schemas/snapshots/ir/trinity_bundle.schema.json`, `schemas/snapshots/ir/model_spec.schema.json`, `schemas/snapshots/ir/policy_spec.schema.json`                                                                                |
| Generated reference | [IR Schema Catalog](../reference/ir/schema-catalog.md), [JSON Schema Catalog](../reference/schemas.md)                                                                                                                          |
