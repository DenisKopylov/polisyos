# Policy Engine (PolisyOS) v2.4.0

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

**Latest Update:** January 30, 2026 (Performance Regression Detection, Enhanced Diagnostics, Core Observability v2.0, Phase 18 Security v2.1, Tools Ecosystem Expansion, Ops Infrastructure)
**Current Architecture Version:** v2.4.1 (Performance Regression Detection, Core Observability v2.0, Phase 18 Security v2.1, Tools Ecosystem, Ops Infrastructure, Enhanced Diagnostics)

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

The system is organized as a set of layers with intentionally **directed dependencies** (Law A):

- **Scientist** → IR, Fabric, Foundry, Runtime, Core, Common
  Orchestration sits at the top and is allowed to depend on most layers. Includes hierarchical agent system (PI→Drafter→Formalizer→Critic), FSM-based workflow orchestration, self-healing reflexion patterns, governance passes pipeline, Phase 18 safe expression evaluation, legal compliance validation, search loop system with two-stage filtering, workflow engines (LangGraph/SimpleLoop), LLM tracing infrastructure, decision card system, run timeline tracking, and multi-agent workflow orchestration with Phase 2 instrumentation (flow node tracing, LLM client instrumentation, governance pipeline spans, end-to-end workflow tracing).

- **Fabric** → IR, Core, Common
  Data layer depends on contracts and infrastructure, but not on orchestration. Includes unified data fabric with evidence bundles, provenance tracking, trust quantification, quality indicators system, fitness reports, quality gate pass integration, data contract catalog system, ingestion pipeline, trust two-pass comparison, and materializer engine for incremental updates.

- **Foundry** → IR, Core, Common
  Execution core depends on contracts and infrastructure, but not on data storage/orchestration. Includes JAX-based simulation engine with compile-time conflict detection, cost modeling, NaN guard for numerical stability, agent artifacts with environment fingerprinting, merge determinism, patch-based state management, plugin system with capability-based registry, adaptive agents with learning metrics, calibrator fidelity control, gradient health monitoring, and runtime batch execution.

- **Runtime** → IR, Core, Common
  Run lifecycle management depends on contracts and infrastructure. Provides portable run manifests, artifact management, audit trail logging, and full observability integration with PolicyOSTracer and MetricsRegistry.

- **IR** → Core, Common
  Contracts depend on canonicalization/typing infrastructure. Includes Trinity IR (ProblemFrame/PolicySpec/ModelSpec), PolicySurfaceIR compatibility layer with migration support, norm pack contracts for legal compliance, kernel registries, and legal AST backends with pluggable rule evaluation.

- **Core** → Common
  Infrastructure depends only on minimal utilities. Includes comprehensive observability system (PolicyOSTracer singleton, MetricsRegistry, @traced decorator, log-trace correlation, context propagation), content-addressable storage, canonical JSON serialization, conflict detection, cost modeling, NaN guard, Trinity contracts, legal compliance contracts, and environment manifest system with compatibility scoring.

- **Common** → (none)
  Foundational utilities should remain dependency-light. Includes OpenTelemetry-integrated logging, JAX environment configuration, migration system with Trinity format support, and path utilities.

**Tools Layer** → All layers (diagnostics, linting, migration, benchmarking, demos)
Developer tools provide cross-cutting capabilities: architectural linting (Law A/B enforcement), schema generation (Law C), performance regression detection, migration utilities, observability diagnostics, demo scripts for all system components, diagnostic tools, provenance visualization, fabric scanning, and environment capture.

**Ops Layer** → Core, Tools (monitoring, alerting, visualization)
Operational infrastructure provides production-grade monitoring and observability: Docker Compose observability stack (Prometheus + Grafana), performance metrics collection, alerting rules, executive dashboards, and CI/CD integration for performance regression detection.

**Enforcement**:
- `tools/lint_imports.py` checks for forbidden imports and cycles (Law A).
- `tools/lint_foundry.py` checks Foundry purity (Law B).

---

## End-to-end flow (business logic)

At a high level, Policy Engine runs an experiment as a staged pipeline:

1. **Intent intake** (`user_request`)
   A natural-language request describes a policy intervention, constraints, goals, and context.

2. **Scientist orchestration (hierarchical agents + FSM workflow + search)**
   Scientist orchestrates a multi-agent workflow with FSM-based phase management that includes:
   - Hierarchical agent system: PI Agent decomposes tasks → Drafter generates policy drafts → Formalizer creates IR → Critic validates and critiques
   - Self-healing reflexion: FailureCard system with ShortTermMemory and ReflexionOrchestrator for intelligent repair routing
   - Workflow engines: LangGraph-based declarative orchestration with conditional routing and state management
   - Search loop system: Two-stage filtering (cheap/expensive evaluation) with composite objectives and intelligent stopping criteria
   - Phase 2 instrumentation: End-to-end tracing of flow nodes, LLM client interactions, and governance pipeline spans

3. **IR construction (Trinity + kernel registries + legal norms)**
   Policies are represented as typed IR. The modern representation is Trinity:
   - `ProblemFrame` ("why / what success means")
   - `PolicySpec` ("what intervention we change")
   - `ModelSpec` ("how/where the model and data are configured")
   - `NormPack` ("legal compliance rules with jurisdiction context")

4. **Validation & linking (governance passes pipeline)**
   IR is validated through modular governance passes including:
   - Schema validation (Trinity contracts, PolicySurfaceIR compatibility)
   - Safety checks (mechanism validation, constraint enforcement)
   - Privacy controls (PII tiers, access control)
   - Legal compliance (Phase 18 AST-based safe expression evaluation)
   - Quality gates (data readiness via quality indicators system)
   - Budget enforcement (compute, evidence, legitimacy, complexity limits)
   Then linked against kernel registries (mechanisms, slots, merge rules, units, metrics).

5. **Data views & Fabric execution (evidence + trust + quality)**
   Fabric produces data views (via UDF compilation and execution) and attaches comprehensive metadata:
   - Evidence bundles with cryptographic provenance verification
   - Trust quantification with uncertainty bounds and two-pass comparison
   - Quality indicators (missingness, staleness, coverage, outliers) with fitness reports
   - Quality gate enforcement blocking execution on poor data quality
   - Data contract catalog system for structured data access
   - Materializer engine for incremental relational view updates

6. **Compilation (Foundry with conflict detection + cost modeling)**
   Foundry compiles policy IR into executable representation (`ProgramGraph` + `ExecPlan`), performs comprehensive static checks:
   - Conflict detection (multiple writers, merge rules validation)
   - Cost modeling with budget tracking and performance prediction
   - NaN guard for numerical stability monitoring
   - Agent artifacts with environment fingerprinting and determinism tier validation
   - Patch-based execution planning with state delta management

7. **Simulation execution (Foundry runtime with safety + monitoring)**
   Foundry executes the compiled plan in JAX (step/scan/batch) with runtime safeguards:
   - Deterministic merge semantics with state consistency validation
   - Runtime safety tools (NaN/Inf guard, numerical stability diagnostics)
   - Plugin system with capability-based registry and composite executors
   - Adaptive agents with learning metrics and continuous action spaces
   - Gradient health monitoring and uncertainty quantification

8. **Governance (preflight/postflight with legal compliance)**
   Governance evaluates through comprehensive validation pipeline:
   - Legality (norm packs via pluggable backends: AST expression evaluation, LLM analysis)
   - Privacy (data access tiers and transformation controls)
   - Quality gates (data readiness with configurable thresholds)
   - Budget/safety constraints with human gate escalation
   - Phase 18 security (AST policy validation, safe expression execution)

9. **Artifactization & observability**
   Results are persisted as content-addressed artifacts with full observability:
   - DecisionPacket v2 with evidence references, uncertainty bounds, and timeline integration
   - DecisionCard with deterministic human-readable summaries and key metrics extraction
   - RunTimeline with event-based tracking, phase durations, and performance metrics
   - Core observability integration (PolicyOSTracer, MetricsRegistry, @traced instrumentation)
   - Comprehensive audit trail with provenance tracking and reproducible execution

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

- **Compiler**: IR → executable graph/plan with compile-time conflict detection and cost estimation.
- **Static checks**: compile-time conflict detection (multiple writers, merge rules), cost modeling with budget tracking, performance prediction, NaN guard for numerical stability monitoring.
- **Deterministic merge**: patch-based execution and merge rules for stable state updates with state consistency validation.
- **Runtime safety**: NaN/Inf guard for numerical stability, environment fingerprinting, agent artifacts with determinism tier validation.
- **Advanced features**: Agent simulation with learning metrics, plugin system with capability-based registry, adaptive agents, merge determinism, patch executor with state deltas and snapshots.

### Governance: passes and issues

Governance is a pass pipeline that returns structured issues:
- **`ComplianceIssue`**: message, severity, code, path, suggestion, optional input value.
- Validation profiles select which passes run and at what strictness.

Typical passes include:
- **Schema pass**: verifies IR structural validity and required fields with Trinity contract validation.
- **Safety pass**: checks for unsafe/invalid mechanism configurations and execution risks including conflict detection.
- **Budget pass**: enforces resource budgets (time/complexity/limits) for the workflow with cost modeling integration.
- **Privacy pass**: enforces access tiers and privacy rules for data views/UDFs with trust quantification.
- **Quality gate pass**: blocks execution when required data quality indicators are not met, integrates with quality indicators system and fitness reports.
- **Legal pass**: evaluates norm packs via pluggable backends (AST, LLM, Stub) with Phase 18 safe expression evaluation, AST policy validation, and security testing.

### Legal compliance: NormPacks and safe evaluation (Phase 18)

- **`NormPack`**: a collection of normative rules for a jurisdiction/context with effective dates and metadata.
- **`NormRule`**: rule type (obligation/prohibition/permission), human description, backend references, metadata, jurisdiction context.
- **Rule backends**: pluggable evaluation engines with protocol-based architecture.

Phase 18 introduced **safe expression evaluation** with comprehensive security:
- **`ASTPolicy`**: allowlist-based validator and resource limits (deny by default) with attack vector rejection.
- **`SafeExpressionEvaluator`**: interprets a safe AST subset (no `eval`/`exec`, no calls, no attribute access, no builtin functions).
- **`ExpressionASTBackend`**: integrates rule evaluation with the LegalPass pipeline and governance security testing.
- **Security features**: AST limits enforcement, mathematical operations validation, variable binding security, class escape prevention.
- **AST Policy Enforcement**: Forbidden construct rejection, resource limits (nodes/depth/length/names), mathematical correctness validation, norm execution security.

### Decision outputs

- **DecisionPacket v2**: enhanced structured output container with evidence references, uncertainty bounds, timeline integration, and comprehensive metadata tracking.
- **DecisionCard**: deterministic human-readable summary with verdict/confidence evaluation, key metrics extraction, issues summarization, and artifact cross-references.
- **RunTimeline**: event-based timeline system with phase tracking, node durations, artifact creation events, validation outcomes, and performance metrics for full observability.

### Scientist orchestration abstractions

- **Agent hierarchy**: PI→Drafter→Formalizer→Critic protocol-based system with structured problem decomposition and self-healing capabilities.
- **Self-healing reflexion**: FailureCard system with ShortTermMemory, intelligent routing, and ReflexionOrchestrator for automated error recovery.
- **Workflow engines**: LangGraph-based declarative orchestration and SimpleLoopEngine with conditional routing, state management, and unified WorkflowEngine interface.
- **Search framework**: Two-stage filtering (cheap/expensive evaluation), composite objectives, and intelligent stopping criteria for policy optimization.
- **FSM kernel**: Phase-based state machine with 9 phases, budget controls, guards, and human gate integration.
- **Phase 2 instrumentation**: End-to-end workflow tracing with flow node tracing, LLM client instrumentation, and governance pipeline spans.

### Governance and compliance

- **Governance passes**: Modular validation pipeline (schema, safety, privacy, legal, quality gate) with pluggable backends and telemetry.
- **Legal compliance (Phase 18)**: AST-based safe expression evaluation with ASTPolicy validation, SafeExpressionEvaluator, pluggable rule backends, and governance security testing.
- **Quality assessment**: QualityIndicators system with fitness reports, configurable thresholds, and quality gate enforcement.
- **Trust quantification**: Multi-tier evidence validation with uncertainty bounds and statistical verification.

### Core Observability System

Production-grade telemetry and monitoring infrastructure:
- **Distributed tracing**: PolicyOSTracer singleton with OpenTelemetry integration, span hierarchy, lazy initialization, and PolicyOS-specific attributes.
- **Metrics collection**: Prometheus-compatible MetricsRegistry with histogram timers, counters, and workflow metrics recording.
- **Log correlation**: Automatic injection of trace_id and span_id into logs via TraceContextFilter with structured JSON logging.
- **Context propagation**: Thread-safe trace context propagation across async operations and service boundaries via headers.
- **Instrumentation**: Zero-configuration @traced decorator for automatic span creation with sync/async support, custom attributes, and exception capture.
- **LLM tracing**: TracedLLMClient with provider-agnostic interface, token tracking, and performance monitoring.

---

## Codebase tour (directories by responsibility)

This section explains *what each major directory is for* without listing the full file tree.

- **`src/polisyos/common`**: minimal shared utilities (configuration, logging, JAX env defaults, migrations).
- **`src/polisyos/core`**: infrastructure layer (CAS artifacts, canonical JSON, typed contracts, comprehensive observability system, registries, run context, conflict detection, cost modeling, NaN guard, Trinity contracts, legal contracts).
- **`src/polisyos/ir`**: canonical policy/data contracts (Trinity + PolicySurfaceIR), loaders/migrations, kernel registries, validation.
- **`src/polisyos/fabric`**: Unified Data Fabric (ingestion, data contracts, UDF system, evidence/provenance, quality/trust).
- **`src/polisyos/foundry`**: execution core (compile IR to executable plans; run JAX simulations; calibration; conflict detection; cost modeling; NaN guard; agent artifacts; patch-based execution).
- **`src/polisyos/scientist`**: orchestration “brain” (hierarchical agent system with PI→Drafter→Formalizer→Critic, FSM-based workflow orchestration, self-healing reflexion patterns, governance passes pipeline, Phase 18 legal compliance, search loop system with two-stage filtering, workflow engines, LLM tracing infrastructure, decision card system, run timeline tracking, Phase 2 instrumentation).
- **`src/polisyos/runtime`**: run lifecycle APIs and portable run manifests (where run artifacts are stored and referenced).

- **`data/`**: local data workspace, plus normative packs in `data/norms/`.
- **`tools/`**: comprehensive developer toolkit (architectural linters, schema generators, migration tools, diagnostic scripts, performance benchmarks, demo scripts, provenance visualizers, fabric scanners, environment capture utilities).
- **`ops/`**: operational infrastructure (Docker Compose observability stack, Prometheus configuration, Grafana dashboards, alerting rules, monitoring automation).
- **`tests/`**: extensive test suite (contract tests, core observability tests, fabric tests, foundry tests, scientist tests, integration tests, performance tests).
- **`docs/`**: ADRs and contract specifications.

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
- **opentelemetry-api** / **opentelemetry-sdk** (distributed tracing and telemetry)
- **prometheus_client** (metrics collection and exposition)

### Dev tooling

- **pytest**, **pytest-benchmark**, **hypothesis**
- **ruff**, **mypy**
- **pre-commit**

### Operational monitoring

- **Docker Compose** (observability stack orchestration)
- **Prometheus** (metrics collection and alerting)
- **Grafana** (dashboards and visualization)

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

### Performance regression check

```bash
# Run performance benchmarks
uv run pytest tests/performance/ --benchmark-json=results.json

# Check for regressions against baseline
uv run python tools/diagnostics/check_perf_regression.py results.json
```

### Operational monitoring setup

```bash
# Start observability stack (Prometheus + Grafana)
cd ops && docker-compose -f docker-compose.observability.yml up -d

# Access monitoring:
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
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
# Code quality
uv run ruff check .
uv run mypy .

# Architecture compliance
uv run python tools/lint_imports.py
uv run python tools/lint_foundry.py

# Schema validation
uv run python tools/gen_schema.py --check
```

---

## Working with legal norms (NormPacks)

### Where norms live

- `data/norms/sample_norms.yaml` contains example norms for the Phase 18 safe-expression backend.

### Expression safety model (Phase 18)

- Expressions are **validated** by an allowlist-based AST policy (**deny by default**) with comprehensive attack vector rejection.
- Only a safe subset is supported (boolean ops, comparisons, basic arithmetic, literals, variable names, mathematical operations).
- Function calls, attribute access, subscripts, imports, comprehensions, lambdas, dunder names, builtin functions, and class escapes are forbidden.
- Resource limits (nodes/depth/length/names) mitigate denial-of-service style expressions with AST limits enforcement.
- Security features include AST policy validation, safe expression evaluators, mathematical correctness validation, variable binding security, and expression evaluator robustness.
- **ASTPolicy**: Allowlist-based validator with attack vector rejection and resource limits.
- **SafeExpressionEvaluator**: Interprets safe AST subset with no `eval`/`exec`, no calls, no attribute access, no builtin functions.
- **ExpressionASTBackend**: Integrates rule evaluation with LegalPass pipeline and governance security testing.

### How legal evaluation works

- A `NormPack` is selected/attached (by workflow or configuration).
- Governance runs the legal pass.
- The selected backend (e.g., `expr_ast`) evaluates `NormRule.metadata.when/must/must_not` against a provided context.
- Violations become `ComplianceIssue`s with severity and suggestions.

---

## Operational monitoring and observability

Policy Engine includes comprehensive production-grade monitoring infrastructure for tracking performance, detecting issues, and ensuring system reliability.

### Monitoring stack

**Components:**
- **Prometheus**: Metrics collection, alerting, and time-series database
- **Grafana**: Dashboards for executive overview, HPC performance, and agent analytics
- **Docker Compose**: Containerized observability stack with service dependencies

**Monitored metrics:**
- LLM costs and token consumption (budget alerts: $50/hour, $100/hour critical)
- Agent workflow performance and success rates (failure thresholds: 5%, 20%)
- HPC simulation throughput and JIT compilation efficiency
- Calibration convergence and gradient health monitoring

### Quick start monitoring

```bash
# Launch monitoring stack
cd ops && docker-compose -f docker-compose.observability.yml up -d

# Configure PolicyOS metrics export
export POLISYOS_METRICS_PORT=9464
export POLISYOS_LLM_BUDGET_HOURLY=50

# Access interfaces
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
```

### CI/CD integration

Performance regression detection is integrated into CI/CD pipelines with automated benchmarking against baseline commits and configurable alert thresholds for latency, throughput, and overhead metrics.

---

## Reproducibility and artifacts

- **CAS storage** lives under `.polisyos/artifacts/sha256/` (blobs and manifests) with comprehensive observability integration.
- **Run products** are written under `runs/<run_id>/` by default (manifests, audits, artifacts, decision cards, run timelines; exact layout evolves with the runtime API).
- The system prefers deterministic serialization and content-addressing for robust provenance and caching with full distributed tracing support.
- **Environment manifests** capture system state for reproducible simulations with compatibility scoring and risk assessment.
- **Evidence bundles** and **trust metrics** provide cryptographic verification of data provenance and quality.
- **Core observability**: PolicyOSTracer singleton, MetricsRegistry, @traced decorators, log-trace correlation, context propagation, LLM tracing, and end-to-end workflow tracing across all components.
- **Run timeline tracking**: Event-based timeline system with phase durations, node timings, artifact creation, validation outcomes, and performance metrics for comprehensive audit trails.
- **Performance regression detection**: Automated CI/CD workflows with pytest-benchmark integration, statistical analysis, and configurable thresholds for overhead validation (simulation <2%, CAS I/O <5%, calibration <3%).
- **Enhanced diagnostics**: Comprehensive setup validation, UDF performance profiling, schema generation, provenance visualization, and fabric scanning tools.

---

## Testing infrastructure

Policy Engine includes comprehensive testing infrastructure ensuring quality across all architectural layers:

### Test architecture by layers

Following the compiler pipeline architecture, tests are organized by responsibility:

- **Contract Tests**: IR schema validation, Trinity contracts, migrations, kernel models, linker validation
- **Core Phase 0 Tests**: Artifact store, canonical JSON, observability system (PolicyOSTracer, MetricsRegistry, @traced), environment manifests, log correlation, context propagation, decorators, propagation, tracer
- **Fabric Tests**: Data catalog system, evidence bundles, provenance, trust quantification, quality indicators, fitness reports, quality gate pass, trust two-pass
- **Foundry Tests**: JAX simulation engine, agent artifacts, plugin system, adaptive agents, merge determinism, NaN guard, cost model, conflict detection, gradient health, calibrator systems, jit compilation tracker, jit stability, patch executor, program graph ops, runtime batch
- **Scientist Tests**: Hierarchical agent system (PI→Drafter→Formalizer→Critic), governance passes pipeline, Phase 18 legal compliance, search loop system, workflow engines, LLM tracing, decision outputs, Phase 2 instrumentation, decision card, decision packet v2, run timeline, multi-agent workflow, reflexion loop
- **Integration Tests**: End-to-end workflows, calibration UDF integration, LLM workflow orchestration, real database testing, workflow smoke test, workflow LLM
- **Runtime Tests**: Run lifecycle management, artifact paths, manifest portability

### Test execution

```bash
# All tests (unit + integration)
pytest

# Fast unit tests only (no integration)
pytest -m "not integration"

# Integration tests only (with databases)
pytest -m integration

# By layer
pytest tests/core_phase0/ -v    # Core infrastructure + observability
pytest tests/fabric/ -v         # Data fabric + quality
pytest tests/foundry/ -v        # JAX simulation engine
pytest tests/scientist/ -v      # Agent orchestration + governance

# Specific components
pytest tests/scientist/governance/ -v  # Legal compliance + Phase 18 security
pytest tests/scientist/search/ -v      # Optimization loop system
pytest tests/scientist/integration/ -v # End-to-end workflow tracing + Phase 2 instrumentation
```

### Key testing principles

- **CPU Enforcement**: All tests force CPU execution for consistent results across CI/CD environments
- **Mock Systems**: Comprehensive mock implementations for testing without external dependencies (LLM APIs, databases)
- **Architectural Validation**: Tests enforce dependency laws and boundary contracts
- **Phase 18 Security**: Extensive testing of AST policy validation, safe expression evaluation, security boundaries, norm execution security, and governance security testing
- **Observability Coverage**: Full testing of tracing, metrics, log correlation, context propagation, Phase 2 instrumentation, and workflow tracing
- **Quality Gates**: Data quality validation prevents execution on poor-quality inputs
