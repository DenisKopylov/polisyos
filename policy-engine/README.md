# Policy Engine (PolisyOS)

Policy Engine is an **AI-driven policy operating system** for designing, validating, calibrating, and executing public-policy interventions as reproducible computational experiments.

It is built around a **compiler pipeline** mindset:
- start from a natural-language policy intent,
- produce typed policy contracts (IR),
- compile them into executable program graphs,
- run simulations in a JAX-based engine,
- enforce governance (quality, privacy, legal compliance),
- persist everything as content-addressed artifacts with auditability.

This README describes **the project laws**, **data/decision flows**, **business logic**, **dependency logic**, **technologies**, and **key abstractions**.  
For a file-by-file map of the repository, see `architecture.md`.

---

## Core promise (what the system guarantees)

- **Typed contracts at boundaries**: IR and contracts define the shape of every major artifact; runtime components validate at boundaries.
- **Reproducibility-first execution**: runs and artifacts are content-addressed, traceable, and (where feasible) deterministic.
- **Governance before and after execution**: preflight/postflight checks gate unsafe, invalid, low-quality, privacy-violating, or legally non-compliant policies.
- **Separation of concerns**: data layer (Fabric) is isolated from orchestration (Scientist) and from pure execution core (Foundry).

---

## Project laws (invariants)

These are the “laws” the codebase is designed to uphold (some enforced by tooling/tests, some by convention and review).

- **Law A — Import Gate (architectural boundaries)**  
  Critical reverse dependencies are forbidden (e.g., Foundry must not depend on Fabric; Fabric must not depend on Scientist). Cycles are surfaced by tooling.

- **Law B — Foundry is a JAX core (no direct I/O)**  
  Foundry aims to be a pure execution kernel: no DB/network/file I/O and no side-effectful debugging calls in core code. Purity is supported by custom linting.

- **Law C — Contracts are the single source of truth**  
  IR (in `polisyos.ir`) and typed inter-module contracts (in `polisyos.core.contracts`) define canonical data models. JSON Schemas are generated from these models.

- **Law D — Every run is auditable and (as much as possible) reproducible**  
  A run has an ID, controlled randomness, a trace/audit trail, and content-addressed artifacts.

- **Law E — Evidence and provenance are mandatory for data**  
  Fabric records provenance/evidence for datasets and transformations (PROV-O integration), and can materialize immutable fact logs.

- **Law F — Fidelity control**  
  The system supports trading off speed vs accuracy via fidelity settings in simulation/calibration subsystems.

- **Law G — Uncertainty quantification is first-class**  
  Trust and calibration can return uncertainty bounds, and artifacts record these results.

- **Law H — Governance and budgets bound computation and risk**  
  Scientist controls budgets, validation profiles, and escalation mechanisms (including human gates where applicable).

- **Law I — Trust + privacy are enforced in data access**  
  Access tiers and privacy checks apply to data views and UDFs; trust policies reason about uncertainty and data quality.

- **Law J — Legal compliance is a pluggable evaluation layer**  
  Normative rules are expressed as `NormPack`s; evaluation is delegated to backends (e.g., safe AST expression backend).

- **Law K — Quality gate enforcement**  
  Data must pass configured quality checks before being used in simulations or decision-making.

---

## Dependency model (how layers depend)

The system is organized as a set of layers with intentionally **directed dependencies**:

- **Scientist** → IR, Fabric, Foundry, Runtime, Core, Common  
  Orchestration sits at the top and is allowed to depend on most layers.
- **Fabric** → IR, Core, Common  
  Data layer depends on contracts and infrastructure, but not on orchestration.
- **Foundry** → IR, Core, Common  
  Execution core depends on contracts and infrastructure, but not on data storage/orchestration.
- **Runtime** → IR, Core, Common  
  Run lifecycle management depends on contracts and infrastructure.
- **IR** → Core, Common  
  Contracts depend on canonicalization/typing infrastructure.
- **Core** → Common  
  Infrastructure depends only on minimal utilities.
- **Common** → (none)  
  Foundational utilities should remain dependency-light.

**Enforcement**:
- `tools/lint_imports.py` checks for forbidden imports and cycles (Law A).
- `tools/lint_foundry.py` checks Foundry purity (Law B).

---

## End-to-end flow (business logic)

At a high level, Policy Engine runs an experiment as a staged pipeline:

1. **Intent intake** (`user_request`)  
   A natural-language request describes a policy intervention, constraints, goals, and context.

2. **Scientist orchestration (agent + workflow + search)**  
   Scientist orchestrates a workflow (optionally graph-based via LangGraph) that can:
   - draft policies,
   - formalize them into typed IR,
   - critique and repair them (self-healing reflexion),
   - optimize parameters via search (two-stage evaluation).

3. **IR construction (Trinity + kernel registries)**  
   Policies are represented as typed IR. The modern representation is Trinity:
   - `ProblemFrame` (“why / what success means”)
   - `PolicySpec` (“what intervention we change”)
   - `ModelSpec` (“how/where the model and data are configured”)

4. **Validation & linking**  
   IR is validated (schema, types, constraints), then linked against kernel registries (mechanisms, slots, merge rules, units, metrics).

5. **Data views & Fabric execution**  
   Fabric produces data views (via UDF compilation and execution) and attaches provenance/evidence/quality metadata.

6. **Compilation (Foundry)**  
   Foundry compiles policy IR into an executable representation (e.g., `ProgramGraph` + `ExecPlan`), performs static checks (e.g., conflict detection), and prepares runtime execution.

7. **Simulation execution (Foundry runtime)**  
   Foundry executes the compiled plan in JAX (step/scan/batch), using deterministic merge semantics and runtime safety tools (e.g., NaN/Inf guard).

8. **Governance (preflight/postflight)**  
   Governance evaluates:
   - legality (norm packs),
   - privacy (data access and transformations),
   - quality gates (data readiness),
   - budgets/safety constraints.

9. **Artifactization**  
   Results are persisted as content-addressed artifacts and packaged into decision outputs (DecisionPacket, DecisionCard, RunTimeline).

---

## Key abstractions (what to learn first)

### Trinity IR

- **`ProblemFrame`**: problem definition, KPIs, success criteria, constraints.
- **`PolicySpec`**: interventions, parameters, schedules, implementation hints.
- **`ModelSpec`**: model assumptions, time semantics, data snapshots, registry bundles.
- **`TrinityBundle`**: a typed container referencing the three artifacts plus metadata.

### PolicySurfaceIR (legacy-compatible surface)

`PolicySurfaceIR` remains as a compatibility layer and a “single object” surface representation in some paths; migrations and loaders bridge it to/from Trinity.

### Kernel registries (IR kernel)

The IR kernel defines registries that make policies composable and checkable:
- mechanism registry (what can execute),
- slot registry (what state exists),
- merge rules (how concurrent updates resolve deterministically),
- units/metrics/time semantics registries.

### Fabric: contracts, provenance, evidence, trust

- **Data contracts** describe metric-level datasets and access tiers.
- **Evidence bundles** and **provenance graphs** record where data came from and how it was transformed.
- **Quality indicators** quantify data readiness; quality gates block execution on poor inputs.
- **Trust policies** reason about uncertainty and bounds.
- **UDF system** compiles safe, typed “data views” used by the rest of the engine.

### Foundry: compilation and execution core

- **Compiler**: IR → executable graph/plan.
- **Static checks**: conflict detection and cost estimation before expensive execution.
- **Deterministic merge**: patch-based execution and merge rules for stable state updates.
- **Runtime safety**: NaN/Inf guard, environment fingerprinting.

### Governance: passes and issues

Governance is a pass pipeline that returns structured issues:
- **`ComplianceIssue`**: message, severity, code, path, suggestion, optional input value.
- Validation profiles select which passes run and at what strictness.

Typical passes include:
- **Schema pass**: verifies IR structural validity and required fields.
- **Safety pass**: checks for unsafe/invalid mechanism configurations and execution risks.
- **Budget pass**: enforces resource budgets (time/complexity/limits) for the workflow.
- **Privacy pass**: enforces access tiers and privacy rules for data views/UDFs.
- **Quality gate pass**: blocks execution when required data quality indicators are not met.
- **Legal pass**: evaluates norm packs via pluggable backends and emits compliance issues.

### Legal compliance: NormPacks and safe evaluation (Phase 18)

- **`NormPack`**: a collection of normative rules for a jurisdiction/context.
- **`NormRule`**: rule type (obligation/prohibition/permission), human description, backend references, metadata.
- **Rule backends**: pluggable evaluation engines.

Phase 18 introduced **safe expression evaluation**:
- **`ASTPolicy`**: allowlist-based validator and resource limits (deny by default).
- **`SafeExpressionEvaluator`**: interprets a safe AST subset (no `eval`/`exec`, no calls, no attribute access).
- **`ExpressionASTBackend`**: integrates rule evaluation with the LegalPass pipeline.

### Decision outputs

- **DecisionPacket**: structured output container (policy IR, results, validations, references).
- **DecisionCard**: deterministic human-readable summary derived from a DecisionPacket.
- **RunTimeline**: event timeline for observability (phases, node timings, artifacts, validation outcomes).

---

## Codebase tour (directories by responsibility)

This section explains *what each major directory is for* without listing the full file tree.

- **`src/polisyos/common`**: minimal shared utilities (configuration, logging, JAX env defaults, migrations).
- **`src/polisyos/core`**: infrastructure layer (CAS artifacts, canonical JSON, typed contracts, tracing, registries, run context).
- **`src/polisyos/ir`**: canonical policy/data contracts (Trinity + PolicySurfaceIR), loaders/migrations, kernel registries, validation.
- **`src/polisyos/fabric`**: Unified Data Fabric (ingestion, data contracts, UDF system, evidence/provenance, quality/trust).
- **`src/polisyos/foundry`**: execution core (compile IR to executable plans; run JAX simulations; calibration; determinism tools).
- **`src/polisyos/scientist`**: orchestration “brain” (agents, workflow engines, governance passes, search/optimization, publishing).
- **`src/polisyos/runtime`**: run lifecycle APIs and portable run manifests (where run artifacts are stored and referenced).

- **`data/`**: local data workspace, plus normative packs in `data/norms/`.
- **`tools/`**: developer utilities (custom linters, migrations, diagnostics, demos, benchmarks).
- **`tests/`**: unit/contract/integration test suite.
- **`docs/`**: ADRs and contract specs.

---

## Technology stack and dependencies

### Language runtime

- **Python**: `>=3.11`
- **Pydantic v2**: contracts and validation

### Numerical core

- **JAX / jaxlib**
- **jax-metal** (optional, Apple Silicon backend)
- **Equinox**, **Optax**, **Diffrax**
- **Chex**, **Jaxtyping**

### Data layer

- **DuckDB** (analytical store)
- **Kùzu** (graph store)
- **PyArrow**, **pandas**
- **W3C PROV-O style provenance** (implemented in Fabric provenance subsystem)

### Orchestration and optimization

- **LangGraph**, **LangChain**
- **pymoo** (multi-objective optimization)

### UI / visualization

- **Streamlit**, **Plotly** (dashboarding)

### Observability / configuration

- **loguru** (structured logging)
- **python-dotenv** (local environment variable loading)

### Dev tooling

- **pytest**, **hypothesis**
- **ruff**, **mypy**
- **pre-commit**

---

## Running the system

### Prerequisites

- Python `>=3.11`

### Option A: uv (recommended)

```bash
# Create/sync the local virtualenv in .venv from uv.lock
# (use --frozen to avoid lockfile drift)
uv sync --frozen --extra dev

# Minimal (runtime-only) environment:
# uv sync --frozen --no-dev
```

#### Activate the environment (optional)

If you prefer a classic workflow, activate `.venv` and run commands directly:

```bash
source .venv/bin/activate
python -V
```

#### Run without activation (recommended)

You can also avoid activation and run everything via `uv run`:

```bash
uv run python -V
```

### Option B: pip (fallback)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### Environment variables (.env)

Local defaults and runtime switches can be set via `.env` (loaded by `python-dotenv`):

```bash
# if you don't already have one:
cp env_example.txt .env
```

### Smoke check (recommended)

```bash
uv run python tools/diagnostics/check_setup.py
```

### macOS + JAX note

On macOS, JAX may auto-select an experimental Metal backend that can crash in some environments.  
Import `jax_bootstrap.py` before importing `jax` in local scripts.

### Run an experiment workflow

`run_experiment.py` is a convenience entrypoint that builds a Scientist workflow and invokes it with a minimal state.

```bash
uv run python run_experiment.py "Design a tax policy that reduces inequality without increasing deficit" \
  --db-path integration.duckdb \
  --runtime-base-dir runs
```

### Run the dashboard

```bash
uv run streamlit run dashboard.py
```

### Run tests

```bash
uv run pytest
```

### Run linters

```bash
uv run ruff check .
uv run mypy .
uv run python tools/lint_imports.py
uv run python tools/lint_foundry.py
```

---

## Working with legal norms (NormPacks)

### Where norms live

- `data/norms/sample_norms.yaml` contains example norms for the Phase 18 safe-expression backend.

### Expression safety model (Phase 18)

- Expressions are **validated** by an allowlist-based AST policy (**deny by default**).
- Only a safe subset is supported (boolean ops, comparisons, basic arithmetic, literals, variable names).
- Function calls, attribute access, subscripts, imports, comprehensions, lambdas, and dunder names are forbidden.
- Resource limits (nodes/depth/length/names) mitigate denial-of-service style expressions.

### How legal evaluation works

- A `NormPack` is selected/attached (by workflow or configuration).
- Governance runs the legal pass.
- The selected backend (e.g., `expr_ast`) evaluates `NormRule.metadata.when/must/must_not` against a provided context.
- Violations become `ComplianceIssue`s with severity and suggestions.

---

## Reproducibility and artifacts

- **CAS storage** lives under `.polisyos/artifacts/sha256/` (blobs and manifests).
- **Run products** are written under `runs/<run_id>/` by default (manifests, audits, artifacts; exact layout evolves with the runtime API).
- The system prefers deterministic serialization and content-addressing for robust provenance and caching.
