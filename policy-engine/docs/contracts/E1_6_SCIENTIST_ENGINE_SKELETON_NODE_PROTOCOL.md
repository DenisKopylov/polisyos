# E1.6 (Phase 6) — Scientist: engine skeleton + Node protocol (workflow engine v0 + node registry)

**Repo snapshot date**: 2026-02-03
**Scope**: `policy-engine/src/polisyos/scientist/engine/*` (+ minimal builtins), `policy-engine/tests/unit/scientist/*`, `policy-engine/tests/contract/*`
**Primary goal**: turn Scientist from a “set of hard-coded steps” into a **minimal workflow engine** that executes a DAG of nodes through a unified protocol and can orchestrate Foundry/Fabric/Scholar/Lex through ports.

> Historical snapshot note: Repository-state statements describe the dated snapshot above; phase labels and completion criteria belong to that historical plan. They do not establish current E02 status or end-to-end functionality.

---

## 0) Phase goal (what should change in practice)

After E1.6, Scientist gets a workflow-engine “skeleton”:

1. **Unified Node protocol**:
   - A Node is a “black box”: it receives `ExecutionContext` + `ExperimentState` and returns `NodeOutcome`.
   - A node does not need to know about the rest of the workflow (apart from its own parameters and state).

2. **Unified `WorkflowSpec` format (DAG)**:
   - a serializable contract (Pydantic v2), suitable for future declarative workflows (E2/E3),
   - with no hard-coded branching inside the engine.

3. **Unified executor v0**:
   - correct DAG construction, validation, and topological sorting,
   - execution (sequential first), with minimal “resume” support through `status=skip`.

4. **Node registry/discovery v0**:
   - an in-process registry + minimal discovery through `polisyos.core.components` (if feasible),
   - without the E3 package ecosystem (marketplace/package installation comes later).

5. **Minimal built-in nodes**:
   - 2–3 “empty” nodes for checking the engine (`noop`/`set_state`/`emit_artifact`),
   - no domain logic (`compile`/`simulate`/`legal` must not live inside the engine).

**Important:** E1.6 does **not** move all existing Scientist business logic into Nodes (that is E1.7). This phase builds the foundation and verifies that it can execute and be traced.

---

## 1) Preconditions (after phases 1–5)

### 1.1 Ports and ABI already exist

From E1.4:

- `polisyos.core.contracts.*` are “ports” (DTOs/refs/Protocol only, no implementations).
- `polisyos.core.components.*` — `ComponentId`, `ComponentMetadata`, `Capability`, `ComponentRegistry`, `Discovery`.
- `polisyos.core.run.context.RunContext` + `polisyos.core.trace.*` provide the base trace artifact (`core.trace.jsonl`).

From E1.5:

- Foundry supports clean `compile()/execute()` through `core.contracts.foundry` contracts (CAS-in/CAS-out) and does not depend on Scientist.

### 1.2 Current Scientist repository state (the symptoms E1.6 addresses)

In the 2026-02-03 snapshot:

- LangGraph-based hard-coded orchestration exists:
  - the pre-decomposition orchestrator workflow builder assembles a graph with conditional routing,
  - the pre-decomposition flow-nodes module contains a large amount of domain logic and direct integrations.
- The `polisyos.scientist.workflows` abstraction exists (`engine_simple` / `engine_langgraph`), but:
  - there is no unified Node protocol (`ctx` + `state` → `outcome`),
  - there is no unified serializable workflow spec (DAG as a contract),
  - there is no node registry/discovery using `ComponentId`.

E1.6 adds a new **canonical** layer: `polisyos.scientist.engine.*`.

---

## 2) Non-goals (explicitly out of scope for this phase)

E1.6 does **not**:

- move existing `flow_nodes.py` into Node plugins (that is E1.7),
- add planning/optimization/LLM agents/governor/reflection (these remain in the current Scientist until migration),
- add a scheduler or parallel execution (the executor remains sequential only),
- implement Fabric World Graph / Scholar / Lex as subsystems (those are E2+), although `ExecutionContext` must provide ports for them,
- implement “extension = install a package” (E3); E1.6 keeps registry/discovery minimal.

---

## 3) Deliverables (what must be introduced after E1.6)

### 3.1 New engine package (skeleton)

Add the package:

```text
policy-engine/src/polisyos/scientist/engine/
  __init__.py
  errors.py
  state.py
  context.py
  protocol.py
  workflow_spec.py
  executor.py
  registry.py
  telemetry.py
  builtins/
    __init__.py
    noop.py
    set_state.py
    emit_artifact.py
```

File responsibility (normative):

- `engine/errors.py` — exceptions only (taxonomy from §4.0).
- `engine/state.py` — `ExperimentState` (Pydantic), no I/O.
- `engine/context.py` — `ExecutionContext` + port Protocols, no port implementations.
- `engine/protocol.py` — `Node`, `NodeSpec`, `NodeOutcome`, `NodeEvent`, `NodeError`.
- `engine/workflow_spec.py` — `WorkflowSpec` + `NodeInvocation` + validation (alias uniqueness, etc.).
- `engine/registry.py` — `NodeRegistry` + discovery adapter (entry_points/dev scan).
- `engine/executor.py` — sequential executor v0 (DAG validation + execution + trace).
- `engine/telemetry.py` — span helpers + attributes (must not import heavy dependencies when observability is disabled).
- `engine/builtins/*` — minimal built-in Nodes only (`noop`/`set_state`/`emit_artifact`).

Package invariants for `polisyos.scientist.engine`:

- does not import `langgraph` (or orchestration-specific dependencies)
- does not import concrete Foundry/Fabric/Scholar/Lex implementations (contracts + Protocol only)
- import-time side effects are prohibited (especially in `__init__.py`).

### 3.2 Tests

- unit tests for engine/executor/registry:
  - `policy-engine/tests/unit/scientist/engine/test_engine_executor_v0.py`
  - `policy-engine/tests/unit/scientist/engine/test_engine_registry_v0.py`
- contract test for `WorkflowSpec` serialization/deserialization:
  - `policy-engine/tests/contract/test_scientist_workflow_spec_contract.py`

### 3.3 Artifact kinds (engine ABI)

To make the engine reproducible rather than “in-memory only,” E1.6 fixes this minimal set of kinds:

- `scientist.workflow_spec` — `WorkflowSpec` (DAG)
- `scientist.workflow_report` — `WorkflowReport` (execution summary; recommended)
- `scientist.experiment_state` — `ExperimentState` (reuse the existing kind from `core.contracts.scientist.ExperimentStateRef`)

Note:

- `core.trace.jsonl` (from `RunContext.finalize()`) remains the base trace artifact for node execution.

### 3.4 Public API surface (exports from `polisyos.scientist.engine`)

Normative: `polisyos.scientist.engine.__init__` exports only “ready” abstractions:

- `Node`, `NodeSpec`, `NodeOutcome`, `NodeStatus`, `NodeEvent`, `NodeError`
- `ExperimentState`
- `WorkflowSpec`, `NodeInvocation`
- `NodeRegistry` (+ a minimal discovery helper)
- `WorkflowExecutor` (sequential executor v0)
- errors from the `EngineError` family

Everything else (internal utilities, telemetry details, staging structures) is considered internal.

### 3.5 Documentation

- This document (E1.6) is the source of truth for the engine ABI.
- optionally, `policy-engine/src/polisyos/scientist/engine/README.md` — a short how-to + example.

---

## 4) Node protocol (the strict minimum that will not break migration)

### 4.0 Errors (engine error taxonomy)

Define a minimal error hierarchy in `polisyos.scientist.engine.errors`:

- `EngineError(Exception)` — base class
- `WorkflowSpecError(EngineError)` — DAG validation/construction errors
  - `UnknownNodeError` (the `node_id` is not found in the registry)
  - `DuplicateAliasError`
  - `MissingDependencyError`
  - `CycleDetectedError`
- `NodeExecutionError(EngineError)` — the node failed (exception/invalid outcome)

Normative: the executor converts a node’s “raw exception” into `NodeOutcome(status="fail", error=...)` + trace and/or raises `NodeExecutionError` (see §8.1/§8.3).

### 4.1 Node ID and version: use `ComponentId` (Core components)

**Normative:** `NodeId = polisyos.core.components.ComponentId`.

#### Important format caveat (existing E1.4 ABI)

`ComponentId` is validated in the repository as `namespace.name@semver`, where `namespace` and `name` contain no dots.
Therefore, an example such as `scientist.node.plan@1.0.0` is **invalid** for the current `ComponentId` implementation.

**Normative node-naming convention for E1.6:**

- `namespace = "scientist"`
- `name` encodes the category using `_`:
  - `scientist.node_noop@1.0.0`
  - `scientist.node_set_state@1.0.0`
  - `scientist.node_emit_artifact@1.0.0`

(If the `ComponentId` grammar is extended later, this convention remains compatible — renaming can be handled through registry aliasing in E3.)

### 4.2 NodeSpec (metadata)

**Goal:** one node “passport” (for registry/discovery/UI/validation), independent of implementation.

Normative:

- `NodeSpec.metadata` is based on `polisyos.core.components.ComponentMetadata`
- `capabilities` MUST include `Capability.SCIENTIST_NODE`
- additional hints are allowed, but not required

Recommended model:

```python
from pydantic import BaseModel, ConfigDict, Field
from polisyos.core.components import ComponentMetadata

class NodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: ComponentMetadata
    # Optional: hints only (not a hard contract)
    state_reads: list[str] = Field(default_factory=list)
    state_writes: list[str] = Field(default_factory=list)
    produces: list[str] = Field(default_factory=list, description="Logical artifact keys")
```

### 4.3 Node interface (minimum)

Normative signature:

- `spec` (metadata: id/version/capabilities)
- `execute(ctx, state) -> NodeOutcome`

```python
from typing import Protocol, runtime_checkable
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.protocol import NodeOutcome, NodeSpec

@runtime_checkable
class Node(Protocol):
    @property
    def spec(self) -> NodeSpec: ...

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome: ...
```

**Invariants:**

- A Node must not perform side effects “around” `ExecutionContext` (for example, writing to arbitrary files).
  Write artifacts to CAS through `ctx.store`, and record them through state/index + trace.

- Node must not be imported by `polisyos.core.*` (dependency direction is upward into Scientist only).

### 4.4 `NodeOutcome` (required fields)

Normative fields:

- `status: ok|skip|fail`
- `state: ExperimentState` (updated)
- `artifacts: list[ArtifactRef]` (produced)
- `events: list[NodeEvent]` (structured events)
- `error: NodeError | None` (envelope)

```python
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.engine.state import ExperimentState

NodeStatus = Literal["ok", "skip", "fail"]

class NodeError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict, description="Must be canonical-json friendly (no float).")

class NodeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: Literal["debug", "info", "warn", "error"] = "info"
    code: str | None = None
    message: str
    attrs: dict[str, str | int | bool] = Field(default_factory=dict)

class NodeOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: NodeStatus
    state: ExperimentState
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    events: list[NodeEvent] = Field(default_factory=list)
    error: NodeError | None = None
```

**Normative rules:**

- `status="fail"` ⇒ `error` MUST be non‑null.
- `status="ok"|"skip"` ⇒ `error` SHOULD be null.
- `artifacts` are “what was produced” for trace/observability.
  Indexing (key → `ArtifactRef`) is done through `state.artifacts_index`/`state.reports_index`.

---

## 5) `ExperimentState` (minimally useful contract)

### 5.1 Purpose

`ExperimentState` is the workflow execution state, modeled as an artifact-oriented container:

- records **inputs** (refs) to Trinity/DataSnapshot/RegistryBundle/…;
- maintains an **index of results** (artifacts/reports) by logical keys;
- holds **params/budgets** as declarative values.

### 5.2 Minimum structure

Normative (v0, “sufficient for the engine”):

- `run_id: str`
- `inputs: dict[str, ArtifactRef]`
- `artifacts_index: dict[str, ArtifactRef]`
- `reports_index: dict[str, ArtifactRef]`
- `params: dict[str, str|int|bool|Decimal]`
- `budgets: dict[str, Decimal]` (or `params["budgets"]`, but a separate field is preferable)

### 5.3 Reserved keys in `state.inputs` (E1.6+ convention)

To let Nodes agree on standard inputs without hard-coding types in the engine, define reserved keys in `ExperimentState.inputs`:

- `trinity_bundle_ref` — `ArtifactRef.kind in {"ir.trinity_bundle"}`
- `data_snapshot_ref` — `ArtifactRef.kind == "fabric.data_snapshot"`
- `registry_bundle_ref` — `ArtifactRef.kind == "core.registry_bundle"`
- optionally, `knowledge_bundle_ref` — `ArtifactRef.kind == "scholar.knowledge_bundle"`
- optionally, `norm_pack_ref` — `ArtifactRef.kind == "ir.norm_pack"` (or a Lex port, if introduced)

Normative for E1.6:

- the engine does **not validate** the contents of these artifacts (that is the Node’s responsibility),
- the engine may validate that a key is present through `WorkflowSpec.required_binds`.

Recommended model:

```python
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from polisyos.core.artifacts.manifest import ArtifactRef

JsonScalar = str | int | bool | Decimal

class ExperimentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")
    run_id: str

    inputs: dict[str, ArtifactRef] = Field(default_factory=dict)
    artifacts_index: dict[str, ArtifactRef] = Field(default_factory=dict)
    reports_index: dict[str, ArtifactRef] = Field(default_factory=dict)

    params: dict[str, JsonScalar] = Field(default_factory=dict)
    budgets: dict[str, Decimal] = Field(default_factory=dict)
```

### 5.4 Canonicalization and “no floats”

By default, `FileSystemCAS.put_json()` uses `CanonSpec(forbid_floats=True)`.
Normative for the engine:

- `ExperimentState`, `WorkflowSpec`, and `WorkflowReport` must serialize without floats,
- use `Decimal` or `int` for budgets/limits (not `float`).

---

## 6) `ExecutionContext` (infrastructure + ports/clients)

### 6.1 Purpose

`ExecutionContext` is everything a Node needs to execute that is **not state**:

- CAS store,
- RunContext/trace,
- logger/tracer,
- ports (fabric/foundry/scholar/lex) as `Protocol`, so the engine does not import implementations.

### 6.2 Minimum structure

```python
from dataclasses import dataclass
import logging
from typing import Protocol, runtime_checkable

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.run.context import RunContext
from polisyos.core.contracts.foundry import CompileRequest, CompileResult, ExecuteRequest, ExecuteResult
from polisyos.core.contracts.fabric import DataViewRequestRef, DataSnapshotRef
from polisyos.core.contracts.scholar import ResearchIntent, KnowledgeBundleRef
from polisyos.core.contracts.lex import LegalContext, LegalReportRef, ChangeProposalRef

@runtime_checkable
class FoundryPort(Protocol):
    def compile(self, store: FileSystemCAS, request: CompileRequest) -> CompileResult: ...
    def execute(self, store: FileSystemCAS, request: ExecuteRequest) -> ExecuteResult: ...

@runtime_checkable
class FabricPort(Protocol):
    def snapshot(self, store: FileSystemCAS, request_ref: DataViewRequestRef) -> DataSnapshotRef: ...

@runtime_checkable
class ScholarPort(Protocol):
    def enrich(self, store: FileSystemCAS, intent: ResearchIntent) -> KnowledgeBundleRef: ...

@runtime_checkable
class LexPort(Protocol):
    def evaluate(self, store: FileSystemCAS, context: LegalContext) -> tuple[LegalReportRef, ChangeProposalRef | None]: ...

@dataclass(frozen=True)
class ExecutionContext:
    store: FileSystemCAS
    run: RunContext
    logger: logging.Logger
    # Optional: OpenTelemetry tracer (if the observability layer is enabled)
    tracer: "Tracer | None" = None

    fabric: FabricPort | None = None
    foundry: FoundryPort | None = None
    scholar: ScholarPort | None = None
    lex: LexPort | None = None
```

**Normative:** the engine does not create port implementations. It receives ready implementations through `ExecutionContext`.

### 6.3 `RunContext` lifecycle (how the engine writes traces)

In the current Core API, `RunContext` is created through:

```python
from polisyos.core.run.context import RunContext

run = RunContext.start(
    store=store,
    registry_bundle=registry_bundle_ref,  # ArtifactRef(kind="core.registry_bundle")
    run_id=state.run_id,
)
```

Normative for E1.6:

- take `registry_bundle_ref` from `state.inputs["registry_bundle_ref"]` (see §5.3),
- if the key is absent, tests/local runs may build a default bundle through `polisyos.core.registry.build_default_registry_bundle(store)`.

---

## 7) `WorkflowSpec` (DAG) — execution contract

### 7.1 Requirements

WorkflowSpec MUST:

- be serializable (Pydantic v2) and suitable for storage as a CAS artifact,
- describe a DAG of nodes (without cycles),
- allow node parameterization (`params`),
- fix an error policy (`fail_fast`/`continue`),
- explicitly declare input binds (minimum state check before start).

### 7.2 `WorkflowSpec` model (v0)

Normative model:

```python
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from polisyos.core.components import ComponentId

ErrorPolicy = Literal["fail_fast", "continue"]

class NodeInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    node_id: ComponentId
    params: dict[str, str | int | bool | Decimal] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list, description="List of node aliases")

class WorkflowSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")
    workflow_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")

    nodes: list[NodeInvocation] = Field(default_factory=list)

    # Binds: keys/paths that must be set in state before execution starts
    required_binds: list[str] = Field(default_factory=list)

    error_policy: ErrorPolicy = "fail_fast"
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_aliases(self) -> "WorkflowSpec":
        aliases = [n.alias for n in self.nodes]
        if len(set(aliases)) != len(aliases):
            raise ValueError("NodeInvocation.alias must be unique within workflow")
        return self
```

### 7.3 Serialization contract

`WorkflowSpec` must round-trip:

- `WorkflowSpec.model_dump_json()` → `WorkflowSpec.model_validate_json(...)`
- without loss and without floats.

Store `WorkflowSpec` in CAS as:

- kind: `scientist.workflow_spec`
- schema: `SchemaInfo(name="polisyos.scientist.engine.WorkflowSpec", version="1.0")`

---

## 8) Engine executor v0 (sequential, but “correct”)

### 8.1 Executor responsibilities

Executor v0 must:

1. Build and validate the DAG:
   - confirm there are no cycles,
   - confirm `depends_on` refers to existing `alias` values,
   - resolve every `node_id` through the registry.

2. Execute nodes in topological order (sequentially):
   - create a span/trace around each node,
   - call `node.execute(ctx, state)`,
   - update state,
   - record the result in the run trace (through `RunContext.emit`).

3. Handle `skip` and `fail`:
   - honor `skip` (the node decides whether to resume),
   - `fail_fast` stops after the first failure,
   - `continue` skips downstream nodes that depend on failed nodes (mark them `skipped_due_to_upstream`).

Additionally (normative):

- Any unhandled exception from `node.execute(...)`:
  - is caught by the executor,
  - is converted to `NodeOutcome(status="fail", error=NodeError(code="node.exception", ...))`,
  - is recorded in the trace/logs,
  - then `error_policy` is applied.

### 8.2 Bind validation

`required_binds` is a list of paths that must be set in state before execution starts.

Normative (v0): check that the value exists and is not `None`.

Recommended implementation:

- basic dot-path support (`inputs.trinity_bundle_ref`) is optional;
- at minimum, top-level keys only (`inputs`, `run_id`, …) are allowed; complex checks belong in Nodes.

### 8.3 Tracing and execution artifacts

Normative for E1.6:

- for each `NodeInvocation`, the executor writes at least two events to `RunContext.trace`:
  - `NODE_STARTED`
  - `NODE_OK|NODE_SKIP|NODE_FAIL`
- save the trace as the CAS artifact `core.trace.jsonl` in `RunContext.finalize()`.

This provides “node trace as an artifact” without introducing additional formats.

Limitation of the current `RunContext.emit()`:

- it accepts `metrics` and `refs` only, not `warnings/errors/events` as structures.

Therefore, for E1.6:

- `NodeOutcome.events` must be included in `ctx.logger` (structured log),
- when `ctx.tracer` is available, the executor may add events through `span.add_event(...)`,
- record `NodeOutcome.error`:
  - at minimum, through `ctx.logger.exception(...)`,
  - and/or through `RunContext.finalize(status="fail", errors=[...])` (`run_manifest.errors`).

### 8.4 Recommended node trace-event shape (semantics)

Use `RunContext.emit(phase, event, inputs, outputs, metrics)`:

- `phase = f"scientist.node.{alias}"` (or `phase="scientist.node"` + a field in the event name)
- `event`:
  - `NODE_STARTED`
  - `NODE_OK`
  - `NODE_SKIP`
  - `NODE_FAIL`
- `metrics`:
  - `duration_ms`
  - `status_ok` (0/1)
- `refs.inputs/refs.outputs`:
  - include produced `ArtifactRef`s from `NodeOutcome.artifacts` where possible.

### 8.4.1 Telemetry conventions (OpenTelemetry spans)

If `ExecutionContext.tracer` is set, the executor creates a span for each node.

Normative:

- span name: `scientist.node` (or `scientist.node.<alias>`, though a fixed name + attributes is preferable)
- attributes (minimum):
  - `polisyos.run_id` = `state.run_id`
  - `polisyos.workflow_id` = `workflow.workflow_id`
  - `polisyos.node.alias` = `inv.alias`
  - `polisyos.node.id` = `str(inv.node_id)`
  - `polisyos.node.status` = `outcome.status`
  - `polisyos.node.duration_ms` = `<int>`

Behavior:

- add `NodeOutcome.events` as span events (for example, `span.add_event(...)`) and/or log them through `ctx.logger`.

### 8.5 Minimal `WorkflowReport` (recommended, but in-memory is allowed)

To “properly represent skip/fail” and provide a stable report artifact, add a `WorkflowReport` if possible:

- contains a list of `NodeRunRecord` (alias, node_id, status, duration_ms, error?, produced artifact keys/refs),
- is saved to CAS:
  - kind: `scientist.workflow_report`
  - schema: `polisyos.scientist.engine.WorkflowReport@1.0`
- the report ref may be placed in `state.reports_index["workflow_report"]`.

If minimizing the scope of work:

- the executor may return the report as a Python object without writing it to CAS,
- but the “observability smoke” test must then check at least `core.trace.jsonl`.

### 8.6 Persist workflow inputs/outputs (recommended “repro path”)

For artifact-based workflow reproducibility, the executor should:

1. persist `WorkflowSpec` in CAS (kind `scientist.workflow_spec`) and add it as input to `RunContext`:
   - `run.add_input(workflow_spec_ref)`

2. optionally, persist the initial `ExperimentState` as `scientist.experiment_state` and add it as input.
3. after execution:
   - persist the final `ExperimentState` (kind `scientist.experiment_state`) and add it as output,
   - persist `WorkflowReport` (kind `scientist.workflow_report`) and add it as output,
   - `run.finalize(status="ok"|"fail")`.

For E1.6, item (1) + trace are sufficient as normative requirements; items (2–3) are strongly recommended.

---

## 9) Node registry/discovery v0

### 9.1 Registry API (minimum)

`NodeRegistry` — in‑process registry:

- `register(node)` / `register_provider(provider)`
- `get(node_id)`
- `list(filter)` (at minimum: capabilities/domain/tag)

**Conflict policy:** duplicate `node_id` ⇒ **fail** (safer for E1.6).

Versioning clarification:

- the workflow spec pins the full `node_id` (including semver),
- in E1.6, the registry does **not** resolve semver automatically,
- if multiple versions of the same component (`namespace.name@...`) are found, the registry must fail (to keep the workflow reproducible).

Normative registry structure (v0):

- primary key: full `ComponentId` (`str(ComponentId)`)
- secondary index: `component_key = f\"{namespace}.{name}\"` (without version) → must be unique

This provides:

- reproducibility (the workflow pins an exact version),
- early detection of conflicts (two versions of one node in the same process).

Recommended API (exact signatures):

```python
from polisyos.core.components import ComponentId, Capability
from polisyos.scientist.engine.protocol import Node

class NodeRegistry:
    def register(self, node: Node) -> None: ...
    def get(self, node_id: ComponentId | str) -> Node: ...  # raises UnknownNodeError
    def list(self, *, capability: Capability | None = None, tag: str | None = None) -> list[NodeSpec]: ...
```

### 9.2 Integration with Core components (if feasible)

The repository already has:

- `polisyos.core.components.ComponentRegistry`
- `polisyos.core.components.discover_entry_points()` (entry point group `polisyos.components`)

Normative discovery path for E1.6:

1. Call `discover_entry_points()`.
2. Select objects with `capabilities & Capability.SCIENTIST_NODE`.
3. If the object is a `ComponentProvider`, create a node through `create()` and register it.
4. If it is only `ComponentMetadata`, register the metadata (optional) without an instance, or reject it.

**Fallback:** if discovery is not yet used/configured, the registry loads built-ins directly.

---

## 10) Minimal built-in nodes (for checking the engine)

Three nodes without domain logic are sufficient for E1.6:

### 10.1 `noop`

- NodeId: `scientist.node_noop@1.0.0`
- Behavior: does nothing, returns `status="ok"`, and leaves state unchanged (apart from optional events).

### 10.2 `set_state`

- NodeId: `scientist.node_set_state@1.0.0`
- Params:
  - `key: str` (for example, `"params.foo"` or just `"foo"` in `state.params`)
  - `value: str|int|bool` (no floats)
- Behavior: writes the value to state (normative: `state.params[key]=value`).

### 10.3 `emit_artifact`

- NodeId: `scientist.node_emit_artifact@1.0.0`
- Params:
  - `key: str` — key in `state.artifacts_index`
  - `payload: dict` — small JSON structure without floats (for testing)
- Behavior:
  1. writes `payload` to CAS through `ctx.store.put_json(...)` (for example, kind `scientist.builtin.dummy`),
  2. adds an `ArtifactRef` to `state.artifacts_index[key]`,
  3. returns `NodeOutcome.artifacts=[ref]`.

---

## 11) Testing and validation (required for the phase)

### 11.1 Unit tests: executor

1. **Executor runs a DAG of three nodes**:
   - workflow: set_state → emit_artifact → noop
   - assertions:
     - execution order matches dependencies,
     - `state.params` has changed,
     - `state.artifacts_index` contains a ref,
     - the trace has an event for each node (or the report shows their statuses).

2. **Unknown node**:
   - a workflow with a `node_id` missing from the registry ⇒ error during DAG validation.

3. **Cycle**:
   - a cycle through `depends_on` ⇒ “cycle detected” error.

4. **Skip propagation (continue policy)**:
   - the first node fails,
   - a downstream node depends on it,
   - with `error_policy="continue"`, the downstream node is marked `skipped_due_to_upstream` in the report/trace.

Recommended test fixtures:

- `store = FileSystemCAS(tmp_path)` (CAS in a temporary directory)
- `registry_bundle = build_default_registry_bundle(store).bundle_ref` (or a fixture)
- `run = RunContext.start(store, registry_bundle=registry_bundle, run_id="R_test")`
- `ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test"))`
- `registry = NodeRegistry(); registry.register(Builtins...)`

### 11.2 Contract tests: WorkflowSpec serde

- `WorkflowSpec.model_dump_json()` round-trips without loss.
- canonical JSON (through `polisyos.core.canon.to_canonical_bytes`) succeeds (no floats).

### 11.3 Observability smoke

Minimum:

- each node has a span/trace record (OpenTelemetry span or `RunContext.trace` record).

Preferably:

- `RunContext.finalize()` creates a `core.trace.jsonl` artifact containing `NODE_*` events for every node.

---

## 12) Definition of Done (formally verifiable criteria)

1. `polisyos.scientist.engine` exists:
   - Node protocol + WorkflowSpec + executor + registry + minimal telemetry helpers.

2. Built-ins (`noop`/`set_state`/`emit_artifact`) exist, with a test that actually runs a DAG.
3. The engine contains no domain logic:
   - no `compile`/`simulate`/`legal`/data fetching inside the engine package.

4. A `WorkflowSpec` serialization/deserialization contract test exists.
5. Observability:
   - traces/spans are recorded for each node and checked by a smoke test.

---

## 13) Recommended implementation sequence (to keep the work bounded)

1. **Models and errors (contracts):**
   - `engine/errors.py`, `engine/state.py`, `engine/protocol.py`, `engine/workflow_spec.py`
   - add a `WorkflowSpec` serialization/deserialization contract test.

2. **Registry v0**:
   - in-process registry + built-in registration,
   - optionally, a discovery adapter over `polisyos.core.components.discovery`.

3. **Executor v0**:
   - DAG validation + topo sort,
   - execution + trace events in `RunContext`,
   - basic exception handling and `error_policy`.

4. **Builtins**:
   - noop/set_state/emit_artifact,
   - unit tests: DAG smoke + cycle/unknown node.

5. **Telemetry helpers**:
   - move span/trace attributes and names into `engine/telemetry.py`,
   - add a smoke test for traces/spans.

## Appendix A — Recommended DAG implementation in the executor (pseudocode)

```python
def topo_sort(workflow: WorkflowSpec) -> list[str]:
    # Kahn algorithm over aliases
    ...

def execute_workflow(ctx, registry, workflow, state):
    validate_binds(workflow.required_binds, state)
    order = topo_sort(workflow)

    results = {}
    failed = set()

    for alias in order:
        inv = invocations[alias]

        if any(dep in failed for dep in inv.depends_on):
            results[alias] = {"status": "skip", "reason": "upstream_failed"}
            continue

        node = registry.get(inv.node_id)  # raises if missing
        ctx.run.emit(f"scientist.node.{alias}", "NODE_STARTED")

        started = now()
        outcome = node.execute(ctx, state)
        duration_ms = ms_since(started)

        state = outcome.state
        # record artifacts/events

        if outcome.status == "fail":
            failed.add(alias)
            ctx.run.emit(f"scientist.node.{alias}", "NODE_FAIL", metrics={"duration_ms": duration_ms})
            if workflow.error_policy == "fail_fast":
                break
        elif outcome.status == "skip":
            ctx.run.emit(f"scientist.node.{alias}", "NODE_SKIP", metrics={"duration_ms": duration_ms})
        else:
            ctx.run.emit(f"scientist.node.{alias}", "NODE_OK", metrics={"duration_ms": duration_ms})

    return state, results
```

---

## Appendix B — Example `WorkflowSpec` (JSON)

```json
{
  "schema_version": "1.0",
  "workflow_id": "engine_smoke",
  "required_binds": ["run_id"],
  "error_policy": "fail_fast",
  "nodes": [
    {
      "alias": "set",
      "node_id": "scientist.node_set_state@1.0.0",
      "params": { "key": "foo", "value": "bar" },
      "depends_on": []
    },
    {
      "alias": "emit",
      "node_id": "scientist.node_emit_artifact@1.0.0",
      "params": { "key": "dummy" },
      "depends_on": ["set"]
    },
    {
      "alias": "noop",
      "node_id": "scientist.node_noop@1.0.0",
      "params": {},
      "depends_on": ["emit"]
    }
  ]
}
```

## D1-L4 Validation Links

| Link type           | Current anchor                                                                                                                                                                                                                                        |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source plan phase   | D1-L4 Phase 2 pass/analysis contracts and Phase 5 governance-frontier handoff                                                                                                                                                                         |
| Contract tests      | `tests/contract/test_scientist_workflow_spec_contract.py`, `tests/unit/scientist/nodes/builtins/compile/test_link_trinity.py`, `tests/unit/scientist/governance/test_validation_pipeline.py`, `tests/unit/scientist/governance/test_pass_registry.py` |
| Schema snapshots    | `schemas/snapshots/ir/gate_request.schema.json`, `schemas/snapshots/ir/gate_decision.schema.json`, `schemas/snapshots/ir/trinity_bundle.schema.json`                                                                                                  |
| Generated reference | [IR Schema Catalog](../reference/ir/schema-catalog.md), [JSON Schema Catalog](../reference/schemas.md)                                                                                                                                                |
