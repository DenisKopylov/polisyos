# E1.4 (Phase 4) — Core ABI: CAS/Canon/Refs + Contract Ports + Component Skeleton

**Repo snapshot date**: 2026-02-03  
**Scope**: `policy-engine/src/polisyos/core/*` + minimal touchpoints in `fabric/`, `foundry/`, `scientist/`, and `runtime/` to reconnect imports.\\
**Primary goal**: make `polisyos.core` a unified infrastructure core (CAS + canonicalization + manifests + run/trace/observability + stable contract ports at module boundaries) **without leaking Scientist logic**.

> Historical snapshot note: Repository-state statements describe the dated snapshot above; phase labels and completion criteria belong to that historical plan. They do not establish current E02 status or end-to-end functionality.

---

## 0) Invariants (what must be true after this phase)

### 0.1 Architectural boundaries (import gate — source of truth)

Source of truth: ADR `policy-engine/docs/adr/0004-architecture-boundaries-import-gate.md` + `policy-engine/architecture/imports/policy.toml` + `policy-engine/tools/quality/lint/lint_imports.py`.

**Critical for E1.4:**

- `polisyos.ir.*` **does not import** `polisyos.core.*` (IR remains dependency-free).
- `polisyos.core.*` **may import** `polisyos.ir.*`, but **does not import** `polisyos.scientist.*` (no bottom-up cycles).
- Any module integration (Scientist↔Fabric↔Foundry↔Lex↔Scholar) passes **through**:
  - IR contracts (`polisyos.ir.*`) for what data is, and
  - Core contracts (`polisyos.core.contracts.*`) for how to pass artifacts/refs/ports.

### 0.2 Reproducibility by construction

Any artifact intended to be reproducible must:

1. have a **canonical** byte payload (or an explicitly marked canonicalization mode),
2. have an `ArtifactManifest` with `schema` + `inputs` + (where possible) `producer`/`env`,
3. be addressable through an `ArtifactID` (`sha256:<hex64>`),
4. be passed between layers through **typed refs** (see `polisyos.core.contracts.*`).

### 0.3 Contracts are ports, not implementations

Files in `polisyos.core.contracts.*` contain **only**:

- Pydantic models (envelopes / refs / “thin” DTOs),
- `Protocol`/`ABC` interfaces (for example, `RuleBackend`),
- very lightweight validation (`@model_validator`) without I/O or business logic.

Prohibited:

- importing concrete backend, engine, scheduler, and similar implementations,
- importing heavy dependencies (LLM clients, DB clients, network clients),
- performing side effects during import.

---

## 1) Non-goals (explicitly out of scope for this phase)

This phase does **not** implement:

- Fabric World Graph / claim/doc pipeline / Lex corpus storage (those are E2+).
- Scholar/Lex as subsystems (their implementation is E2+), although their contract ports are introduced now.
- A full “extension = package” marketplace (E3). E1.4 adds only a minimal component-model skeleton.
- Rewriting existing discovery/registry systems (connectors/methods/plugins); this phase only prepares for unification.

---

## 2) Current repository state (what already exists)

### 2.1 Core: CAS + canonicalization + manifests

Already implemented (and forming the foundation for E1.4):

- Canonicalization: `polisyos.core.canon.canon_json`
  - `CanonSpec` (`forbid_floats=True` by default)
  - `to_canonical_bytes()` supports `datetime/date/Decimal/bytes` and, when needed, **deterministically** encodes floats as tagged objects.
- CAS: `polisyos.core.artifacts.store.FileSystemCAS`
  - `put_bytes()` and `put_json()` write `.blob` + `.manifest.json` under the same `ArtifactID`
  - stores `inputs`, `schema`, `producer`, and `env`.
- Manifests: `polisyos.core.artifacts.manifest.ArtifactManifest`
  - minimal provenance chain through `inputs: list[InputRef]`.

### 2.2 Core: run/trace/observability

Already implemented:

- `polisyos.core.run.context.RunContext`
  - writes `trace.jsonl` (in the run directory)
  - on `finalize()`, saves the trace as the CAS artifact `core.trace.jsonl` and saves `core.run_manifest`.
- `polisyos.core.trace.*`
  - `TraceRecord` and `JsonlTraceSink` (not canonical; run-specific).
- `polisyos.core.observability.*`
  - OTel/metrics scaffolding exists; for E1.4, the attributes/identifiers must be **aligned** without adding Scientist dependencies.

### 2.3 Core: the contracts layer exists but needs to be brought up to “ports”

`polisyos.core.contracts` currently exists:

```text
core/contracts/
  compiler.py
  fabric.py
  foundry.py
  legal.py
  scientist.py
  trinity.py
```

**Problems/gaps relative to the E1.4 target:**

1. There are no `lex.py` or `scholar.py` ports (add them now as ABI boundaries).
2. `core/contracts/scientist.py` contains its own `ArtifactRef` (incompatible with `core.artifacts.manifest.ArtifactRef`), which weakens typing and introduces two parallel ref models.
3. `core/contracts/legal.py` is already a “Lex port” in meaning, but its name and contents do not match the target set (`LegalContext`, `LegalReportRef`, `ChangeProposalRef`).

### 2.4 The import gate already exists and passes

The script `policy-engine/tools/quality/lint/lint_imports.py`, using `architecture/imports/policy.toml` (v1), reports:

- **violations: none** (core/ir/foundry do not import Scientist)
- cycles exist at the package level (`polisyos.fabric`↔`polisyos.fabric.udf`, `polisyos.scientist`↔subpackages). Cycles are **not** an E1.4 target, but must be considered when extending contracts/components (do not add new ones).

---

## 3) Target after E1.4 (what is introduced)

### 3.1 The only stable port layer: `polisyos.core.contracts.*`

The target E1.4 port set (the minimum sufficient set for integrations):

- `trinity.py` — refs + `TrinityBundle` envelope
- `fabric.py` — DataView/DataSnapshot requests+responses (refs)
- `foundry.py` — ExecPlan/ExecConfig/SimulationResult (refs + envelopes)
- `compiler.py` — Compile/Link reports (refs)
- `lex.py` — LegalContext/LegalReportRef/ChangeProposalRef + backend protocol (RuleBackend)
- `scholar.py` — ResearchIntent/KnowledgeBundleRef envelopes (refs)
- `scientist.py` — ExperimentStateRef/DecisionPacketRef (refs only; no logic)

**Rule**: contracts modules do not import implementations or create dependency cycles.

### 3.2 Canon/manifest/run/trace are standardized for use across all layers

Foundry/Fabric/Scholar/Lex must be able to:

- write artifacts to CAS (through `FileSystemCAS`)
- populate manifests (`schema`, `inputs`, `producer`, `env`)
- use `RunContext`/trace **without** importing Scientist
- exchange results through `core.contracts.*` refs.

### 3.3 Component-model skeleton in Core (preparation for E3)

Add `polisyos.core.components.*`:

- `ComponentId` (`namespace.name@semver`)
- `ComponentMetadata` (domains, jurisdictions, tags, capabilities)
- `Capabilities` enum/flag
- `Registry` + conflict policy
- `Discovery` (entry_points + dev scan)

E1.4 does **not** require reconnecting existing subsystems (connectors/methods) to core/components, but the ID/metadata format is fixed now.

---

## 4) Work 4.1 — Fix “how not to do it” #2 (the Legal port must not depend on Scientist)

### 4.1.1 Symptom to prohibit permanently

Prohibited pattern:

- `core/contracts/legal.py` (or any Core module) imports `RuleBackend`/ASTPolicy/ValidationProfile from `polisyos.scientist.*`.

Reason:

- Core ceases to be a lower layer and acquires control-plane knowledge.

### 4.1.2 Target solution (normative)

**E1.4 decision:** move the “Legal port” to `polisyos.core.contracts.lex` and make it the single “official” home for legal interfaces.

- `core/contracts/lex.py` contains:
  - `IssueSeverity`, `ComplianceIssue`
  - `RuleBackend` (`Protocol`)
  - `LegalContext` (input envelope)
  - `LegalReportRef`, `ChangeProposalRef` (typed refs)
  - optionally, `LegalReport`/`ChangeProposal` envelopes as DTOs (no logic)
- `core/contracts/legal.py` becomes:
  - a deprecated shim: `from .lex import *` (re-export) for one release cycle
  - a comment saying “use core.contracts.lex”

#### Why do this instead of “keeping legal.py”?

- In the target architecture, “Lex” is a standalone domain service on top of Fabric, so `lex.py` is a more accurate port name.
- Backward compatibility is preserved through re-exports, so Scientist/Governance are not broken immediately.

### 4.1.3 Contract: `RuleBackend`

Normative signature (at minimum):

```python
@runtime_checkable
class RuleBackend(Protocol):
    @property
    def backend_id(self) -> str: ...

    def evaluate(self, norm_pack: NormPack, context: dict) -> list[ComplianceIssue]: ...
```

**Invariants:**

- the backend is **stateless** (repeated calls with the same inputs do not depend on previous calls).
- the backend does **not write** to external systems by itself (all writes go through the calling layer).
- `ComplianceIssue.pass_id` is set by the calling pass (or fixed to “legal”—choose and document one rule; preferably, the pass sets `pass_id`, while the backend returns issues without knowing about the pipeline).

### 4.1.4 Contract: `LegalContext`

Goal: make the Lex-check input typed and unified without tying it to an implementation.

**Minimum contents for E1.4:**

- `trinity: TrinityBundle` or refs to Trinity (ProblemFrameRef/PolicySpecRef/ModelSpecRef)
- `fabric_results: list[FabricResultRef] | None`
- `foundry: { exec_plan_ref, simulation_result_ref } | None`
- `jurisdiction: str`
- `as_of_date: str | None` (ISO)
- `norm_pack_ref: ArtifactRef | None` (if norms have already been assembled as an artifact) **or** `norm_pack: NormPack | None`

Important: `LegalContext` must **not** embed huge payloads (tables, texts). Refs only.

### 4.1.5 Lex port outputs (minimum)

- `LegalReportRef`:
  - `kind="lex.legal_report"`
  - `media_type="application/json"`
- `ChangeProposalRef` (optional):
  - `kind="lex.change_proposal"`
  - `media_type="application/json"`

Schemas (`SchemaInfo.name/version`) are fixed in the Lex implementation (E2), but refs are introduced now.

### 4.1.6 DoD for 4.1

- `core/contracts/lex.py` exists and is exported from `core/contracts/__init__.py`.
- `core/contracts/legal.py` is either renamed or turned into a re-export (with no dependency on Scientist).
- `tools/quality/lint/lint_imports.py` reports no violations.

---

## 5) Work 4.2 — Canonicalization + manifests + refs: reproducibility by construction

### 5.2.1 Canonical JSON ABI (polisyos.canon.json)

**Source of truth**: `polisyos.core.canon.canon_json`.

#### 5.2.1.1 Encoding rules (normative)

- `dict`:
  - keys must be `str` only
  - `sort_keys=True`
- `datetime`:
  - normalized to UTC
  - serialized as `{"_type":"datetime","iso_utc":"...Z"}`
- `date`:
  - `{"_type":"date","iso":"YYYY-MM-DD"}`
- `Decimal`:
  - `{"_type":"decimal","value":"<decimal-as-string>"}`
- `bytes`:
  - `{"_type":"bytes","encoding":"base64","data":"..."}`
- `float`:
  - **prohibited by default**
  - if `CanonSpec.forbid_floats=False`, serialized as `{"_type":"float","repr":"<.17g>"}` (deterministically)

#### 5.2.1.2 `CanonSpec` and the “signal in the manifest”

Problem with the current state:

- `ArtifactManifest.canon` records only `{name, version}` and does **not represent parameters** (for example, `forbid_floats`).

**E1.4 decision (specification):**

Extend `CanonInfo` so that the manifest **unambiguously describes** the canonicalization mode.

Minimum option (recommended):

```python
class CanonInfo(BaseModel):
    name: str
    version: str
    forbid_floats: bool = True
    forbid_nan_inf: bool = True
    sort_keys: bool = True
    separators: tuple[str, str] = (",", ":")
    ensure_ascii: bool = False
```

Alternative (if the manifest schema should not be extended): `canon_params_hash` + `canon_params_json`.

**Requirement:** every `put_json(..., canon_spec=...)` write must be represented correctly in the manifest.

### 5.2.2 Manifest inputs/derivation (normative minimum)

#### 5.2.2.1 InputRef

`InputRef` remains minimal:

- `artifact_id`
- `role` (string role identifier)

However, E1.4 fixes a **shared vocabulary of roles** for key artifacts so that derivation chains are readable:

- `registry_bundle`
- `problem_frame` / `policy_spec` / `model_spec`
- `data_view_request` / `query_plan` / `data_snapshot`
- `program_graph` / `exec_plan` / `exec_config`
- `state_snapshot` / `state_delta`
- `metrics`
- `environment_manifest`
- `trace`
- `evidence_bundle`

#### 5.2.2.2 `ProducerInfo` and its connection to the component model

E1.4 fixes this rule:

- `ProducerInfo.component` must be a `ComponentId` (see §6)
- `ProducerInfo.version` matches `ComponentId.semver` (or duplicates it)
- `ProducerInfo.git` is optional, but if present it must be truthful (commit + dirty state)

### 5.2.3 Typed refs: one base class

Normative rule:

- `polisyos.core.artifacts.manifest.ArtifactRef` is the **only** base class for refs at the Core level.
- Every `*Ref` in `polisyos.core.contracts.*` must:
  - inherit from `ArtifactRef`
  - pin `kind` and `media_type` through `Literal[...]`
  - optionally add denormalized fields, but only if they are computed deterministically from the payload.

This removes the current “two realities” of refs (especially in `core/contracts/scientist.py`).

### 5.2.4 `RunContext` / Trace / Metrics (unification)

E1.4 fixes a “three-layer” observability model:

1. **Trace (run timeline)** — JSONL artifact `core.trace.jsonl` (not required to be canonical; it is an audit log).
2. **Metrics (numeric results)** — artifacts `foundry.metrics` / `fabric.uncertainty_bounds`, etc. (must be canonical).
3. **OTel/Prometheus** — operational observability (outside CAS), correlated through `run_id` and `artifact_id`.

Conventions for `RunContext.emit()`:

- `phase` = a module (`core|fabric|foundry|scientist|lex|scholar`) or sub-phase (`foundry.execute`).
- `event` = a stable UPPER_SNAKE code (`RUN_STARTED`, `EXEC_STEP`, `LEGAL_CHECK_STARTED`).
- `refs.inputs/outputs` = `ArtifactRef` only (or a typed subclass).

---

## 6) Work 4.3 — Core contract ports at module boundaries

### 6.3.1 `polisyos.core.contracts` structure (target)

```text
polisyos/core/contracts/
  __init__.py
  compiler.py
  fabric.py
  foundry.py
  trinity.py
  scientist.py
  lex.py        # NEW (E1.4)
  scholar.py    # NEW (E1.4)
  legal.py      # deprecated shim (re-export lex)
```

### 6.3.2 Normative import rules for contracts

Allowed:

- stdlib
- `pydantic`, `typing_extensions`
- `polisyos.core.artifacts.*` (ArtifactID/ArtifactRef/SchemaInfo/…)
- `polisyos.ir.*` (if the contract needs IR types: Trinity models, NormPack)

Prohibited:

- `polisyos.fabric.*`, `polisyos.foundry.*`, `polisyos.scientist.*` (contracts may describe these as refs, but must not import implementations)

### 6.3.3 Trinity port (`contracts/trinity.py`)

Add/pin:

- `ProblemFrameRef`, `PolicySpecRef`, `ModelSpecRef` (already present)
- `TrinityBundle` (already present)
- **add** `TrinityBundleRef` (if the bundle is also stored and passed as a single artifact ref)

Recommended kinds:

- `ir.problem_frame`
- `ir.policy_spec`
- `ir.model_spec`
- `ir.trinity_bundle` (if introduced)

### 6.3.4 Fabric port (`contracts/fabric.py`)

Goal: make the “entry into the world” and “exit from the world” typed for Scientist/Foundry/Scholar/Lex.

**Minimum E1.4 refs:**

- `DataViewRequestRef` (already present)
- `QueryPlanRef` (already present)
- `FabricResultRef` (already present)
- `EvidenceBundleRef` (Core ref for ports; IR may keep an isomorphic “string ref” for its schemas)
- `UncertaintyBoundsRef` / `WarningsRef` (already present)

**Add in E1.4:**

- `DataSnapshotRef` (for fixed data snapshots used as input by Foundry)
- `DataSnapshot` envelope (optional; refs are sufficient)

**Normative separation:**

- `DataViewRequest` = request (declarative contract)
- `QueryPlan` = “how to get it”
- `FabricResult` = “what was obtained” (refs to data/evidence/uncertainty/warnings)
- `DataSnapshot` = “fixed input for computations” (may be a separate kind of `FabricResult`)

### 6.3.5 Foundry port (`contracts/foundry.py`)

**Refs (minimum):**

- `ProgramGraphRef`, `ExecPlanRef`, `ExecConfigRef` (present)
- `StateSnapshotRef`, `StateDeltaRef`, `MetricsRef`, `TraceSliceRef` (present)
- **add** `SimulationResultRef` (+ `SimulationResult` envelope)

**`SimulationResult` (E1.4) — Scientist↔Foundry contract:**

- references to:
  - `exec_plan_ref`
  - `metrics_ref` (required)
  - `state_snapshot_ref` (optional)
  - `environment_ref` / `environment_fingerprint` (optional)
  - `trace_slice_ref` (optional)

Meaning: Scientist must not know about Foundry executor’s internal classes; it sees only the result as an artifact.

### 6.3.6 Scientist port (`contracts/scientist.py`)

E1.4 fixes:

- `contracts.scientist` contains **refs/envelopes only**, not workflow logic.

**Minimum refs:**

- `ExperimentStateRef` (`kind="scientist.experiment_state"`)
- `DecisionPacketRef` (`kind="scientist.decision_packet"`)

Possible additional refs (if already in the code and needed):

- `FailureCardRef`, `TimelineRef`, `DecisionCardRef`, `PolicyIRRef`, `CritiqueRef`

**Key E1.4 refactor:**

- remove the internal `ArtifactRef` from `core/contracts/scientist.py` and instead inherit from `core.artifacts.manifest.ArtifactRef`, as in the other ports.

### 6.3.7 Scholar port (`contracts/scholar.py`)

E1.4 adds only the ABI boundary (no Scholar implementation):

**Input:** `ResearchIntent` (envelope)

- domain/topic
- jurisdiction(s)
- time window
- required outputs (docs/claims/bundles)
- budgets/limits

**Output:** `KnowledgeBundleRef`

- `kind="scholar.knowledge_bundle"`
- `media_type="application/json"`

Optional: `EnrichmentReportRef` (audit artifact).

### 6.3.8 Lex port (`contracts/lex.py`)

See §4.1.

---

## 7) Work 4.4 — Component model skeleton (E1.4, minimal)

### 7.4.1 Why this is part of E1.4

To make “extension = package” a mechanism in E3, we need a **shared ABI for component identity** and a **shared discovery/registry mechanism** that can later support:

- Foundry methods
- Fabric connectors
- Scientist nodes
- Scholar/Lex backends

For E1.4, a “skeleton” is sufficient (without reconnecting existing systems).

### 7.4.2 File structure (target)

```text
polisyos/core/components/
  __init__.py
  ids.py
  metadata.py
  capabilities.py
  protocols.py
  registry.py
  discovery.py
  compliance.py
```

### 7.4.3 ComponentId (normative)

**Format:** `namespace.name@semver`

Normative rules:

- `namespace` and `name`:
  - lowercase `[a-z][a-z0-9_]*`
  - `.` is only the namespace/name separator (not allowed within either segment)
- `semver`:
  - minimum `MAJOR.MINOR.PATCH`
  - pre-release/build metadata is allowed as in SemVer (optional)

API (minimum):

- `ComponentId.parse(str) -> ComponentId`
- `str(ComponentId) -> "namespace.name@x.y.z"`
- properties: `.namespace`, `.name`, `.version`

### 7.4.4 ComponentMetadata (normative)

Minimum fields:

- `component_id: ComponentId`
- `display_name: str | None`
- `description: str | None`
- `domains: list[str]`
- `jurisdictions: list[str]`
- `tags: list[str]`
- `capabilities: set[Capability]` (or a `Capabilities` flag)
- `provides: list[str]` (optional: what it provides, for search)
- `depends_on: list[ComponentId]` (optional; for E1.4, these may remain strings)

### 7.4.5 Capabilities (normative)

For E1.4, a small but stable set is sufficient:

- `CAS_READ`, `CAS_WRITE`
- `FABRIC_QUERY`, `FABRIC_WRITE`
- `FOUNDRY_COMPILE`, `FOUNDRY_EXECUTE`
- `LEX_EVALUATE`
- `SCHOLAR_ENRICH`
- `SCIENTIST_NODE`

Recommendation: use `Flag` (as with `ConnectorCapability`) for composition.

### 7.4.6 Registry (target behavior)

The registry stores:

- `component_id -> metadata`
- `component_id -> factory/provider` (optional; may be omitted in E1.4)

**Conflict policy (minimum):**

- `ERROR` (duplicate id)
- `PREFER_HIGHEST_SEMVER`
- `FIRST_WINS`

The registry can query:

- by capability
- by domain
- by jurisdiction
- by tag

### 7.4.7 Discovery (entry_points + dev scan)

E1.4 fixes:

- entry point group: `polisyos.components` (universal)
- contract: the entry point returns either `ComponentMetadata` or a `ComponentProvider` (`Protocol`)

Development scan (optional for E1.4):

- scan the directory for `py` files with a `__polisyos_components__` metadata list.

**Important:** discovery must not pull in heavy imports unnecessarily. Prefer lazy imports.

---

## 8) Deliverables (what must be introduced or changed)

### 8.1 Code (core)

- `src/polisyos/core/contracts/lex.py` (new)
- `src/polisyos/core/contracts/scholar.py` (new)
- `src/polisyos/core/contracts/legal.py` → deprecated shim (re-export `lex`)
- `src/polisyos/core/contracts/scientist.py` → unify refs on `core.artifacts.manifest.ArtifactRef`
- `src/polisyos/core/artifacts/manifest.py` → extend `CanonInfo` (to represent the canonicalization mode)
- `src/polisyos/core/components/*` (new package skeleton)

### 8.2 Touchpoints (minimal import changes)

- `scientist/governance/*` → switch `core.contracts.legal` to `core.contracts.lex` if needed
- adapt locations that create/validate Scientist refs to the new base ref (if `contracts.scientist` changes)

### 8.3 Docs

- update `src/polisyos/core/README.md` (important: align the IR↔Core dependency description with the import gate; IR does **not** depend on Core)
- update `src/polisyos/core/contracts/README.md` (add Lex/Scholar ports and rules)
- add/update an ADR/section on component IDs if needed; it may be part of `core/components/README.md`

---

## 9) Definition of Done (formally verifiable criteria)

### 9.1 Dependency check

- `python3 tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml` → **Violations: none**
- In particular, `polisyos.core.*` does not import `polisyos.scientist.*` (directly or transitively through contracts).

### 9.2 Contracts ports

- `polisyos.core.contracts` contains `lex.py` and `scholar.py`.
- `contracts` contain only models/Protocol/ABC (no implementations).
- `contracts.scientist` has no second, locally defined `ArtifactRef`; there is one base ref.

### 9.3 Canon/manifest correctness

- Every artifact written by `put_json` receives a manifest with the correct `canon` (including `CanonSpec` parameters).
- For artifacts that allow floats (for example, env/telemetry), the canonicalization mode is explicitly represented in the manifest.

### 9.4 Component skeleton

- `polisyos.core.components` exists and imports without side effects.
- A minimal `ComponentId` parser/validator + `ComponentMetadata` + `Discovery` + `Registry` are present.

---

## 10) Migration plan (recommended implementation sequence)

1. **Lex/Scholar ports**: add `core/contracts/lex.py` and `core/contracts/scholar.py`; make `legal.py` a shim.
2. **Unify Scientist refs**: align `core/contracts/scientist.py` with `ArtifactRef` from `core.artifacts.manifest`.
3. **Extend CanonInfo**: update `CanonInfo` and manifest writing in `FileSystemCAS.put_json()` so that `canon_spec` parameters are represented.
4. **Component skeleton**: add `core/components/*` without integrating with existing discovery.
5. **Docs + import gate**: update READMEs/docs and ensure `lint_imports` reports no new cycles or violations.

---

## Appendix A — Practical notes (anti-footguns)

### A.1 Do not add new cycles

Existing import cycles must not get worse. Be especially careful with:

- `__init__.py` (lazy imports are preferable to eager imports)
- contracts modules (they must not pull in upper-level packages)

### A.2 “Strings vs. types” for IDs

- In IR: `ArtifactID` remains a string conforming to `ARTIFACT_ID_PATTERN`.
- In Core: `ArtifactID` is a type (`core.artifacts.ids.ArtifactID`), and refs use `ArtifactRef`.
- Between them: ports (`core.contracts.*`) are the only “bridge” between string-based IR contracts and typed Core refs.

### A.3 Versioning

- Canonicalization: `CanonSpec.version` and `CanonInfo.version` must change when the algorithm changes.
- Contracts: additions are backward compatible; removals happen only through a deprecation cycle.

---

## Appendix B — Contract inventory (kinds ↔ refs) (E1.4 baseline)

Below is an inventory of artifact references that must be treated as part of the port layer's **public ABI**.

> Note: exact `SchemaInfo.name/version` values may differ in the current code, but E1.4 fixes the rule: **if a payload has `schema_version`, record it in the manifest**. For infrastructure envelopes without `schema_version`, `SchemaInfo(name=..., version="0.1.0")` is allowed, as it is today.

### B.1 Trinity (`polisyos.core.contracts.trinity`)

| Ref class                | kind                | media_type         | Notes                         |
| ------------------------ | ------------------- | ------------------ | ----------------------------- |
| `ProblemFrameRef`        | `ir.problem_frame`  | `application/json` | problem definition            |
| `PolicySpecRef`          | `ir.policy_spec`    | `application/json` | policy definition             |
| `ModelSpecRef`           | `ir.model_spec`     | `application/json` | model definition              |
| `TrinityBundleRef` (NEW) | `ir.trinity_bundle` | `application/json` | optional “bundle as artifact” |

### B.2 Fabric (`polisyos.core.contracts.fabric`)

| Ref class                       | kind                        | media_type         | Notes                             |
| ------------------------------- | --------------------------- | ------------------ | --------------------------------- |
| `DataViewRequestRef`            | `ir.data_view_request`      | `application/json` | request contract                  |
| `QueryPlanRef`                  | `fabric.query_plan`         | `application/json` | execution plan                    |
| `FabricResultRef`               | `fabric.result_bundle`      | `application/json` | result envelope                   |
| `EvidenceBundleRef` (core port) | `fabric.evidence_bundle`    | `application/json` | evidence/provenance envelope      |
| `UncertaintyBoundsRef`          | `fabric.uncertainty_bounds` | `application/json` | uncertainty metadata              |
| `WarningsRef`                   | `fabric.warnings`           | `application/json` | warnings bundle                   |
| `DataSnapshotRef` (NEW)         | `fabric.data_snapshot`      | `application/json` | fixed snapshot for compute inputs |

### B.3 Foundry (`polisyos.core.contracts.foundry`)

| Ref class                   | kind                           | media_type          | Notes                                   |
| --------------------------- | ------------------------------ | ------------------- | --------------------------------------- |
| `PolicySurfaceIRRef`        | `ir.policy_surface`            | `application/json`  | legacy surface IR artifact              |
| `ProgramGraphRef`           | `foundry.program_graph`        | `application/json`  | compiled program graph                  |
| `LoweredIRRef`              | `foundry.lowered_ir`           | `application/json`  | optional lowered IR                     |
| `ExecPlanRef`               | `foundry.exec_plan`            | `application/json`  | execution plan                          |
| `ExecConfigRef`             | `foundry.exec_config`          | `application/json`  | exec config                             |
| `StateSnapshotRef`          | `foundry.state_snapshot`       | `application/json`  | immutable snapshot                      |
| `StateDeltaRef`             | `foundry.state_delta`          | `application/json`  | patch/delta operations                  |
| `MetricsRef`                | `foundry.metrics`              | `application/json`  | metrics payload                         |
| `TraceSliceRef`             | `foundry.trace_slice`          | `application/jsonl` | slice of trace (optional)               |
| `EnvironmentManifestRef`    | `foundry.environment_manifest` | `application/json`  | reproducibility manifest                |
| `SimulationResultRef` (NEW) | `foundry.simulation_result`    | `application/json`  | top-level result envelope for Scientist |

### B.4 Compiler (`polisyos.core.contracts.compiler`)

| Ref class          | kind                      | media_type         | Notes          |
| ------------------ | ------------------------- | ------------------ | -------------- |
| `LinkReportRef`    | `compiler.link_report`    | `application/json` | link issues    |
| `CompileReportRef` | `compiler.compile_report` | `application/json` | compile issues |

### B.5 Lex (`polisyos.core.contracts.lex`)

| Ref class           | kind                  | media_type         | Notes              |
| ------------------- | --------------------- | ------------------ | ------------------ |
| `LegalReportRef`    | `lex.legal_report`    | `application/json` | compliance report  |
| `ChangeProposalRef` | `lex.change_proposal` | `application/json` | optional proposals |

### B.6 Scholar (`polisyos.core.contracts.scholar`)

| Ref class            | kind                       | media_type         | Notes            |
| -------------------- | -------------------------- | ------------------ | ---------------- |
| `KnowledgeBundleRef` | `scholar.knowledge_bundle` | `application/json` | graph/bundle ref |

### B.7 Scientist (`polisyos.core.contracts.scientist`)

| Ref class            | kind                         | media_type         | Notes                   |
| -------------------- | ---------------------------- | ------------------ | ----------------------- |
| `ExperimentStateRef` | `scientist.experiment_state` | `application/json` | workflow state snapshot |
| `DecisionPacketRef`  | `scientist.decision_packet`  | `application/json` | decision envelope       |

---

## Appendix C — CanonInfo schema migration (backward compatibility)

If `CanonInfo` is extended (see §5.2.1.2), migration should be “soft”:

- new fields have **defaults** → old manifests validate without changes;
- `ArtifactManifest.canon` may be `null` (for old/bytes-only artifacts) → the code must support this.

E1.4 requirement: when writing new artifacts, `FileSystemCAS.put_json()` must:

1. use the actual `canon_spec` (default or passed in),
2. write its parameters to `ArtifactManifest.canon`.

---

## Appendix D — DoD commands (manual checks)

From `policy-engine/`:

- import gate: `python3 tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml`
- (optional) fail on cycles (not an E1.4 requirement): `python3 tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml --fail-on-cycles`

## D1-L4 Validation Links

| Link type           | Current anchor                                                                                                                                                              |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source plan phase   | D1-L4 Phase 0 canon/CAS hardening and Phase 1 schema compatibility                                                                                                          |
| Contract tests      | `tests/unit/ir/test_canon_hardening.py`, `tests/contract/test_golden_record_ids.py`, `tests/unit/core/artifacts/test_ir_adapter.py`, `tests/contract/test_ir_migrations.py` |
| Schema snapshots    | `schemas/snapshots/ir/fact.schema.json`, `schemas/snapshots/ir/fact_segment_manifest.schema.json`, `schemas/snapshots/ir/trinity_bundle.schema.json`                        |
| Generated reference | [IR Schema Catalog](../reference/ir/schema-catalog.md), [JSON Schema Catalog](../reference/schemas.md)                                                                      |
