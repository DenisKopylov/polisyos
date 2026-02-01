# Policy Engine (PolisyOS) v2.4.2

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

**Latest Update:** February 1, 2026 (Enhanced Agent Simulation System, Advanced Calibration Framework, Self-Healing Workflow Architecture, Data Connectors Phase 2.2 Complete, Quality Assessment System v2.1, Fact Log System Integration, Legal Compliance AST Backend, Core Observability v2.1, Runtime Environment Fingerprinting, Trinity IR Migration System)
**Current Architecture Version:** v2.4.2 (Enhanced Agent Simulation System, Advanced Calibration Framework, Self-Healing Workflow Architecture, Data Connectors Phase 2.2 Complete, Quality Assessment System v2.1, Fact Log System Integration, Legal Compliance AST Backend, Core Observability v2.1, Runtime Environment Fingerprinting, Trinity IR Migration System)

---

## Core promise (what the system guarantees)

- **Typed contracts at boundaries**: IR and contracts define the shape of every major artifact; runtime components validate at boundaries.
- **Reproducibility-first execution**: runs and artifacts are content-addressed, traceable, and (where feasible) deterministic.
- **Governance before and after execution**: preflight/postflight checks gate unsafe, invalid, low-quality, privacy-violating, or legally non-compliant policies.
- **Separation of concerns**: data layer (Fabric) is isolated from orchestration (Scientist) and from pure execution core (Foundry).

---

## Developer docs

- Data connector contribution guide: `docs/connectors/CONTRIBUTING.md`

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
  Orchestration sits at the top and is allowed to depend on most layers. Includes hierarchical agent system with protocols and self-healing (PI→Drafter→Formalizer→Critic with FailureCard routing and ShortTermMemory), FSM-based workflow orchestration with 9 phases and guards, governance passes pipeline with legal compliance (AST Policy backend, NormPack evaluation, safe expression evaluation), search framework with two-stage filtering and intelligent stopping criteria, workflow engines (LangGraph declarative orchestration, SimpleLoop for basic processes), LLM tracing infrastructure with TracedLLMClient and OpenTelemetry integration, decision packet system with evidence references and uncertainty bounds, decision card summaries, run timeline tracking with event-based observability, multi-agent workflow orchestration with Phase 2 instrumentation, kernel layer with budgets (Compute/Evidence/Legitimacy/Complexity) and human gates, compute layer with job specifications and distributed execution backends, and comprehensive governance with preflight/postflight checks and validation profiles.

- **Fabric** → IR, Core, Common
  Data layer depends on contracts and infrastructure, but not on orchestration. Includes unified data fabric with Phase 2.2 data connectors system (capability-based protocol, registry with lazy loading, discovery, connection pooling, federation, resilience patterns), evidence bundles with cryptographic verification, W3C PROV-O compliant provenance tracking v2.0, trust quantification with statistical verification and two-pass comparison, quality indicators system v2.1 (missingness/staleness/coverage/outlier/schema drift detection), fitness reports with configurable thresholds and quality gate validation, data contract catalog with hash-locked bindings and fuzzy search with disambiguation, ingestion pipeline with entity resolution and reconciliation, fact log system with immutable facts, deterministic IDs and semantic network, materializer engine for incremental relational updates, trust policies with statistical verification, and CAS integration with Arrow support for high-performance columnar data.

- **Foundry** → IR, Core, Common
  Execution core depends on contracts and infrastructure, but not on data storage/orchestration. Includes JAX-based simulation engine with advanced agent simulation system (32 modules: actor-critic architectures, demographics, evolution algorithms, graph mechanisms, temporal processing), compile-time conflict detection and cost modeling, NaN guard for numerical stability, agent artifacts with environment fingerprinting and determinism tier validation, merge determinism with patch-based state management, plugin system with capability-based registry, adaptive agents with learning metrics and continuous action spaces, calibrator with bijectors and loss functions (MSE/Huber/weighted), gradient health monitoring and uncertainty quantification, runtime batch execution, and comprehensive test suite covering all simulation components.

- **Runtime** → IR, Core, Common
  Run lifecycle management depends on contracts and infrastructure. Provides portable run manifests, artifact management, audit trail logging, and full observability integration with PolicyOSTracer and MetricsRegistry.

- **IR** → Core, Common
  Contracts depend on canonicalization/typing infrastructure. Includes Trinity IR architecture (ProblemFrame for problem definition, PolicySpec for interventions, ModelSpec for simulation configuration), PolicySurfaceIR compatibility layer with migration support, data connectors contracts for external data sources integration, AST policy system for safe expression evaluation with resource limits and security validation, norm pack contracts for legal compliance with deontic logic support, kernel registries (mechanisms/slots/units/merge rules/constraints/metrics/trust), fact log semantic network contracts, and legal AST backends with pluggable rule evaluation.

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

3. **IR construction (Trinity + kernel registries + legal norms + data connectors)**
   Policies are represented as typed IR with Trinity architecture for clean separation of concerns:
   - `ProblemFrame` ("why / what success means" - constant throughout experiment)
   - `PolicySpec` ("what intervention we change" - iterated during optimization)
   - `ModelSpec` ("how/where the model and data are configured" - varied for sensitivity analysis)
   - `TrinityBundle` (typed container with migration support between versions)
   - `NormPack` ("legal compliance rules with jurisdiction context and AST evaluation")
   - `Data Connectors` ("capability-based protocol for external data sources integration")

4. **Validation & linking (governance passes pipeline + quality assessment)**
   IR is validated through comprehensive governance passes including:
   - Schema validation (Trinity contracts, PolicySurfaceIR compatibility, migration support)
   - Safety checks (mechanism validation, constraint enforcement, compile-time conflict detection)
   - Privacy controls (PII tiers, access control, data contract validation)
   - Legal compliance (Phase 18 AST-based safe expression evaluation, NormPack validation)
   - Quality gates (data readiness via quality indicators system v2.1 with configurable thresholds)
   - Trust validation (statistical verification, evidence bundles, provenance tracking)
   - Budget enforcement (compute, evidence, legitimacy, complexity limits with multi-tier controls)
   Then linked against kernel registries (mechanisms, slots, merge rules, units, metrics).

5. **Data views & Fabric execution (evidence + trust + quality + provenance + connectors)**
   Fabric produces data views (via UDF compilation and execution) and attaches comprehensive metadata:
   - Evidence bundles with cryptographic provenance verification, CAS storage, and deterministic artifact IDs
   - Trust quantification with uncertainty bounds, statistical verification, two-pass comparison, and configurable policies
   - Quality indicators system v2.1 (missingness, staleness, coverage, schema drift, outlier detection) with fitness reports, configurable thresholds, and quality gate validation integration
   - Data contract catalog with hash-locked bindings, fuzzy search with disambiguation, and schema evolution support
   - Provenance system v2.0 with W3C PROV-O compliance, complete lineage tracking, and multi-format export (JSON-LD, N-Quads)
   - Fact log system with immutable facts, deterministic IDs, semantic network, and incremental materialization
   - Materializer engine for incremental relational view updates from fact log with schema evolution and type inference
   - Data connectors system (Phase 2.2 complete) with capability-based protocol, registry with lazy loading, discovery, connection pooling, federation, resilience patterns (circuit breaker, retry), and quality assurance for external data sources

6. **Compilation (Foundry with advanced agent simulation + calibration)**
   Foundry compiles policy IR into executable representation (`ProgramGraph` + `ExecPlan`), performs comprehensive static checks and supports advanced simulation features:
   - Conflict detection (multiple writers, merge rules validation, compile-time analysis)
   - Cost modeling with budget tracking, performance prediction, and samokalirovka
   - NaN guard for numerical stability monitoring with diagnostics
   - Agent artifacts with environment fingerprinting, determinism tier validation, and compatibility scoring
   - Patch-based execution planning with state delta management and merge determinism
   - Advanced agent simulation (32 modules: actor-critic, demographics, evolution algorithms, graph mechanisms)
   - Calibration framework with bijectors, loss functions (MSE/Huber/weighted), and uncertainty quantification

7. **Simulation execution (Foundry runtime with safety + monitoring)**
   Foundry executes the compiled plan in JAX (step/scan/batch) with runtime safeguards:
   - Deterministic merge semantics with state consistency validation
   - Runtime safety tools (NaN/Inf guard, numerical stability diagnostics)
   - Plugin system with capability-based registry and composite executors
   - Adaptive agents with learning metrics and continuous action spaces
   - Gradient health monitoring and uncertainty quantification

8. **Governance (preflight/postflight with legal compliance + quality gates)**
   Governance evaluates through comprehensive validation pipeline with modular passes:
   - Legality (norm packs via pluggable backends: AST expression evaluation, safe expression evaluator, LLM analysis)
   - Privacy (data access tiers, transformation controls, PII classification)
   - Quality gates (data readiness via quality indicators system v2.1 with fitness reports and configurable thresholds)
   - Trust validation (statistical verification, evidence bundles, provenance compliance)
   - Budget/safety constraints with human gate escalation and multi-tier controls
   - Phase 18 security (AST policy validation, safe expression execution, resource limits enforcement)

9. **Artifactization & observability (CAS + runtime + core observability)**
   Results are persisted as content-addressed artifacts with comprehensive observability and audit capabilities:
   - DecisionPacket v2 with evidence references, uncertainty bounds, fabric result integration, and timeline tracking
   - DecisionCard with deterministic human-readable summaries, key metrics extraction, compliance status, and artifact cross-references
   - RunTimeline with event-based tracking, phase durations, node timings, artifact creation events, validation outcomes, and performance metrics
   - RunManifest with environment manifests for reproducible simulations, budget usage tracking, and pruning reasons
   - Core observability v2.1 (PolicyOSTracer singleton, MetricsRegistry, @traced decorators, log-trace correlation, context propagation, LLM tracing, distributed tracing)
   - Runtime infrastructure with audit trails (JSON Lines), artifact management, and environment fingerprinting
   - Comprehensive provenance tracking with W3C PROV-O compliance and evidence bundle verification

---

## Key abstractions (what to learn first)

### Trinity IR Architecture v2.4.2

- **`ProblemFrame`**: "Why" artifact - problem definition, KPIs, success criteria, constraints, stakeholders (constant throughout experiment with stakeholder analysis and constraint modeling).
- **`PolicySpec`**: "What" artifact - interventions, parameters, schedules, implementation hints, mechanism bindings (iterated during optimization with policy labels and implementation notes).
- **`ModelSpec`**: "How" artifact - model assumptions, time semantics, data snapshots, registry bundles, model notes and labels (varied for sensitivity analysis with assumption tracking).
- **`TrinityBundle`**: typed container referencing the three artifacts plus metadata, migration support, and source schema version tracking.

### PolicySurfaceIR (legacy-compatible surface)

`PolicySurfaceIR` remains as a compatibility layer and a “single object” surface representation in some paths; migrations and loaders bridge it to/from Trinity.

### Kernel registries (IR kernel)

The IR kernel defines registries that make policies composable and checkable:
- mechanism registry (what can execute),
- slot registry (what state exists),
- merge rules (how concurrent updates resolve deterministically),
- units/metrics/time semantics registries.

### Quality Assessment System v2.1

- **`QualityIndicators`**: Objective metrics (missingness, staleness, coverage, schema drift, outlier ratio) computed from datasets with computation methods and timestamps.
- **`QualityLevel`**: Ordered classification (EXCELLENT/GOOD/ACCEPTABLE/POOR/UNUSABLE) with semantic meaning for decision making.
- **`QualityThresholds`**: Configurable thresholds for different profiles (FAST/MVP/STRICT) with per-metric limits and warning levels.
- **`DataFitnessReport`**: Human-readable reports with failure reasons, summary statistics, and profile-based assessment for data suitability validation.

### Fact Log System

- **`Fact`**: Immutable knowledge representation with subject-predicate-object structure, provenance tracking, trust policies, and legal metadata.
- **`FactBatch`**: Collection of facts for batch processing with segment management and deterministic ID generation.
- **`FactProvenance`**: Complete lineage tracking with source artifacts, ingestion runs, and collection timestamps.
- **`FactLog`**: Semantic network of facts with deterministic IDs, temporal validity, and incremental materialization support.

### Data Connectors System (Phase 2.2)

- **`SourceConnector`**: Protocol-based interface for external data sources with capability declarations and async operations.
- **`ConnectorCapability`**: Bitmask system for 15+ capabilities (FULL_FETCH, STREAMING, DATE_RANGE_FILTER, SCHEMA_INTROSPECTION, etc.).
- **`ConnectorRegistry`**: Singleton registry with lazy loading, plugin discovery, and connection pooling.
- **`FetchRequest/FetchResult`**: Typed request/response structures with evidence bundles and deterministic caching keys.

### Fabric: contracts, provenance, evidence, trust, quality

- **Data contracts** describe metric-level datasets with hash-locked bindings and fuzzy search with disambiguation.
- **Evidence bundles** provide cryptographic verification with CAS storage and deterministic artifact IDs.
- **Provenance system** implements W3C PROV-O compliance with complete lineage tracking and semantic graphs.
- **Quality indicators system** (missingness/staleness/coverage/outliers) with fitness reports and configurable thresholds.
- **Quality gate validation** blocks execution on poor data quality through governance pipeline integration.
- **Trust policies** provide statistical verification with uncertainty bounds and two-pass comparison.
- **Fact log system** enables immutable audit trails with deterministic fact IDs and semantic networks.
- **Data connectors** (Phase 2.2) support capability-based protocol plus registry, discovery, and pooling.
- **Materializer engine** performs incremental updates from fact log to relational views.
- **UDF system** compiles safe, typed "data views" with Arrow support and multi-backend execution.

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
- **Trinity IR generation**: Creates ProblemFrame (constant), PolicySpec (iterated), and ModelSpec (varied) artifacts for comprehensive policy representation.
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
- **`src/polisyos/fabric`**: Unified Data Fabric (Phase 2.2 data connectors with capability-based protocol, federation, resilience patterns; data contract catalog with hash-locked bindings; evidence bundles with cryptographic verification; provenance system v2.0 with W3C PROV-O compliance; quality indicators system v2.1 with configurable thresholds; fact log system with immutable facts and semantic network; materializer engine for incremental updates; trust policies with statistical verification; UDF compilation pipeline with security passes).
- **`src/polisyos/foundry`**: execution core (compile IR to executable plans with advanced agent simulation system; run JAX simulations with 32 modules for demographics, evolution algorithms, graph mechanisms; calibration framework with bijectors and loss functions; compile-time conflict detection and cost modeling; NaN guard with diagnostics; agent artifacts with environment fingerprinting; patch-based execution with merge determinism; plugin system with capability-based registry).
- **`src/polisyos/scientist`**: orchestration “brain” (hierarchical agent system with protocols and self-healing via FailureCard routing; FSM-based workflow orchestration with 9 phases and guards; governance passes pipeline with legal compliance via AST backends; search framework with two-stage filtering and intelligent stopping criteria; workflow engines with LangGraph declarative orchestration; LLM tracing infrastructure with TracedLLMClient; decision packet system with evidence references; decision card summaries; run timeline tracking with event-based observability; kernel layer with multi-tier budgets; compute layer with job specifications; doe designs for experiment planning).
- **`src/polisyos/runtime`**: run lifecycle APIs and portable run manifests (where run artifacts are stored and referenced with environment manifests for reproducibility, audit trails in JSON Lines format, budget usage tracking, and artifact management with relative paths for portability).

- **`data/`**: local data workspace, plus normative packs in `data/norms/`.
- **`tools/`**: comprehensive developer toolkit (architectural linters, schema generators, migration tools, diagnostic scripts, performance benchmarks, demo scripts, provenance visualizers, fabric scanners, environment capture utilities).
- **`ops/`**: operational infrastructure (Docker Compose observability stack, Prometheus configuration, Grafana dashboards, alerting rules, monitoring automation).
- **`tests/`**: extensive test suite (contract tests, core observability tests, fabric tests, foundry tests, scientist tests, integration tests, performance tests).
- **`docs/`**: ADRs and contract specifications.

---

## Full file tree

```
policy-engine/  # Project root (Policy Engine / PolisyOS).
├── .polisyos/  # Local Content-Addressable Storage (CAS) root used by the artifact system.
│   └── artifacts/  # CAS artifact storage (sha256 fanout).
│       └── sha256/  # CAS blobs/manifests addressed by SHA-256.
│           ├── 02/  # Directory.
│           │   └── 2c/  # Directory.
│           │       ├── 022c70fa0335c562e3bdff195cb06114d21b717e8bb616d8ed454571159b8f5e.blob  # CAS payload blob (content-addressed).
│           │       └── 022c70fa0335c562e3bdff195cb06114d21b717e8bb616d8ed454571159b8f5e.manifest.json  # CAS manifest describing the corresponding blob.
│           ├── 35/  # Directory.
│           │   └── 91/  # Directory.
│           │       ├── 3591f9b5f324774444b147e01be817a4f1a48cfb409a209fa8719c775aa8f972.blob  # CAS payload blob (content-addressed).
│           │       └── 3591f9b5f324774444b147e01be817a4f1a48cfb409a209fa8719c775aa8f972.manifest.json  # CAS manifest describing the corresponding blob.
│           ├── 37/  # Directory.
│           │   └── 24/  # Directory.
│           │       ├── 37241e31e7efa2c325006e46ca6531f95c8c7a2298ddf54d78610762f9a3ee1a.blob  # CAS payload blob (content-addressed).
│           │       └── 37241e31e7efa2c325006e46ca6531f95c8c7a2298ddf54d78610762f9a3ee1a.manifest.json  # CAS manifest describing the corresponding blob.
│           ├── 3b/  # Directory.
│           │   └── 90/  # Directory.
│           │       ├── 3b906e5c1c5b745efa00557a8d2452e11513792b44a29853885661988f48fb13.blob  # CAS payload blob (content-addressed).
│           │       └── 3b906e5c1c5b745efa00557a8d2452e11513792b44a29853885661988f48fb13.manifest.json  # CAS manifest describing the corresponding blob.
│           ├── 59/  # Directory.
│           │   └── 7b/  # Directory.
│           │       ├── 597bf89c30c026760bb21645d9ae2083b67ee4701c5406e1a55746eff778671d.blob  # CAS payload blob (content-addressed).
│           │       └── 597bf89c30c026760bb21645d9ae2083b67ee4701c5406e1a55746eff778671d.manifest.json  # CAS manifest describing the corresponding blob.
│           ├── 70/  # Directory.
│           │   └── 26/  # Directory.
│           │       ├── 702664ce8617112cd5e6dad3ef205051a31aca495bbb42bde1350f14c2a90d91.blob  # CAS payload blob (content-addressed).
│           │       └── 702664ce8617112cd5e6dad3ef205051a31aca495bbb42bde1350f14c2a90d91.manifest.json  # CAS manifest describing the corresponding blob.
│           ├── 78/  # Directory.
│           │   └── b9/  # Directory.
│           │       ├── 78b99187607043dde9528ccc8792b34c6eaa021bde2fc7fcdeee6fbe4fae3c80.blob  # CAS payload blob (content-addressed).
│           │       └── 78b99187607043dde9528ccc8792b34c6eaa021bde2fc7fcdeee6fbe4fae3c80.manifest.json  # CAS manifest describing the corresponding blob.
│           ├── 82/  # Directory.
│           │   └── 73/  # Directory.
│           │       ├── 82731c31ba603a46760bb47a3696fdbd5cb5c884d286ba8408e3d017a89cdd77.blob  # CAS payload blob (content-addressed).
│           │       └── 82731c31ba603a46760bb47a3696fdbd5cb5c884d286ba8408e3d017a89cdd77.manifest.json  # CAS manifest describing the corresponding blob.
│           ├── ad/  # Directory.
│           │   └── 54/  # Directory.
│           │       ├── ad5475e67654ccf8dcb5ea87f89384f68d36326aec3743dcdb1f6e5e4cda815a.blob  # CAS payload blob (content-addressed).
│           │       └── ad5475e67654ccf8dcb5ea87f89384f68d36326aec3743dcdb1f6e5e4cda815a.manifest.json  # CAS manifest describing the corresponding blob.
│           ├── d5/  # Directory.
│           │   └── 39/  # Directory.
│           │       ├── d5390a939cf74bcb7af3da921bc53cdcaee56da0fb591c90f4eb9daa7dddc23d.blob  # CAS payload blob (content-addressed).
│           │       └── d5390a939cf74bcb7af3da921bc53cdcaee56da0fb591c90f4eb9daa7dddc23d.manifest.json  # CAS manifest describing the corresponding blob.
│           ├── e4/  # Directory.
│           │   └── 2f/  # Directory.
│           │       ├── e42fef1b12dc244f395cf96e35c2e9d9a4e5c283554f97276d21524e22220ede.blob  # CAS payload blob (content-addressed).
│           │       └── e42fef1b12dc244f395cf96e35c2e9d9a4e5c283554f97276d21524e22220ede.manifest.json  # CAS manifest describing the corresponding blob.
│           └── ea/  # Directory.
│               └── a7/  # Directory.
│                   ├── eaa7fda75fa39b2c8a4a4ee537b20958dd53005e469a12e45816177358a442ae.blob  # CAS payload blob (content-addressed).
│                   └── eaa7fda75fa39b2c8a4a4ee537b20958dd53005e469a12e45816177358a442ae.manifest.json  # CAS manifest describing the corresponding blob.
├── .github/  # GitHub Actions workflows and automation.
│   └── workflows/  # CI/CD pipeline definitions.
│       └── perf.yml  # Performance regression testing workflow (pytest-benchmark comparison).
├── .vscode/  # Editor workspace configuration (VSCode/Cursor).
│   └── settings.json  # Workspace editor settings (formatting, linting, etc.).
├── data/  # Data workspace (raw/staging) and reference datasets.
│   ├── norms/  # Norm packs (YAML) for legal compliance evaluation.
│   │   └── sample_norms.yaml  # Sample norm pack demonstrating safe expression rules (Phase 18).
│   ├── raw/  # Raw input datasets (placeholder).
│   │   └── .gitkeep  # Placeholder to keep empty directory in Git.
│   ├── staging/  # ETL intermediate outputs (Parquet fixtures).
│   │   ├── .gitkeep  # Placeholder to keep empty directory in Git.
│   │   ├── agents.parquet  # Parquet dataset snapshot (staging fixture).
│   │   ├── interactions.parquet  # Parquet dataset snapshot (staging fixture).
│   │   └── macro.parquet  # Parquet dataset snapshot (staging fixture).
│   └── README.md  # Data layout and ETL conventions for the local data workspace.
├── docs/  # Design notes and specifications.
│   ├── adr/  # Architecture Decision Records (ADRs).
│   │   ├── 0001-remove-legacy-foundry-engine.md  # Architecture Decision Record (ADR).
│   │   ├── 0002-scientist-flow-nodes-only.md  # Architecture Decision Record (ADR).
│   │   └── 0003-ir-v1-deprecate-remove.md  # Architecture Decision Record (ADR).
│   ├── connectors/  # Connector development documentation.
│   │   └── CONTRIBUTING.md  # Guide for contributing data connectors to Policy OS.
│   └── contracts/  # Contract semantics documentation (Trinity, merge semantics).
│       ├── MERGE_SEMANTICS.md  # Contract semantics documentation.
│       └── TRINITY.md  # Contract semantics documentation.
├── examples/  # Small runnable examples.
│   └── ir_base_demo.py  # File.
├── logs/  # Local logs (fixtures / developer artifacts).
│   └── system.log  # Example/system log file (fixture).
├── ops/  # Operations infrastructure: monitoring, observability, alerting stack.
│   ├── docker-compose.observability.yml  # Docker Compose configuration for observability stack.
│   ├── grafana/  # Grafana dashboards and provisioning.
│   │   ├── dashboards/  # JSON dashboard definitions.
│   │   │   ├── executive-overview.json  # Executive dashboard for cost/performance overview.
│   │   │   ├── foundry-hpc.json  # HPC simulation performance dashboard.
│   │   │   └── scientist-agents.json  # Agent workflow performance dashboard.
│   │   ├── provisioning/  # Grafana provisioning configuration.
│   │   │   └── dashboards.yml  # Automatic dashboard provisioning.
│   │   └── README.md  # Grafana setup documentation.
│   ├── prometheus/  # Prometheus configuration and alerting rules.
│   │   ├── alerts.yml  # Alerting rules for cost, performance, and system issues.
│   │   ├── prometheus.yml  # Main Prometheus scrape configuration.
│   │   ├── recording_rules.yml  # Metric pre-computation rules.
│   │   └── README.md  # Prometheus setup documentation.
│   └── README.md  # Operations infrastructure documentation.
├── src/  # Python sources and build metadata.
│   ├── policy_engine.egg-info/  # Build metadata produced by packaging tools.
│   │   ├── PKG-INFO  # Packaged project metadata (generated).
│   │   ├── SOURCES.txt  # Packaged file list (generated).
│   │   ├── dependency_links.txt  # Build metadata file (generated).
│   │   ├── entry_points.txt  # Console script entry points (generated).
│   │   ├── requires.txt  # Dependency requirements (generated).
│   │   └── top_level.txt  # Top-level import package names (generated).
│   └── polisyos/  # Main Python package implementing the policy OS.
│       ├── common/  # Shared utilities: config, logging with trace correlation, JAX env defaults, migrations.
│       │   ├── migrations/  # Deterministic migrations for schema-managed artifacts.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── base.py  # Migration framework primitives (versioning, dispatch).
│       │   │   ├── manifest.py  # Dataset manifest migrations.
│       │   │   └── policy_ir.py  # Policy IR migrations.
│       │   ├── README.md  # Documentation for this directory/module.
│       │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   ├── config.py  # Central configuration (pydantic-settings) and environment wiring.
│       │   ├── jax_env.py  # JAX environment defaults and macOS backend safety toggles.
│       │   ├── async_tools.py  # Asynchronous utilities for sync/async code bridging.
│       │   └── logger.py  # Structured logging setup (Loguru) with OpenTelemetry trace correlation.
│       ├── core/  # Infrastructure: artifacts/CAS, canonical JSON, contracts, tracing, registry, run context.
│       │   ├── artifacts/  # Artifact system: IDs, manifests, environment manifests, CAS store.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── environment.py  # Environment manifest models for reproducible execution contexts.
│       │   │   ├── ids.py  # Content-addressed identifiers (SHA-256) and ID helpers.
│       │   │   ├── manifest.py  # Artifact manifest models (refs, metadata).
│       │   │   ├── registry.py  # Registry bundle artifacts and helpers.
│       │   │   └── store.py  # Filesystem-backed CAS store implementation.
│       │   ├── canon/  # Canonical JSON serialization (deterministic hashing).
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   └── canon_json.py  # Canonical JSON serialization used for deterministic hashing.
│       │   ├── compiler/  # Compilation reporting utilities.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   └── report.py  # Compile report data models and persistence helpers.
│       │   ├── contracts/  # Typed inter-module contracts (Foundry/Fabric/Scientist/Trinity/Legal).
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── compiler.py  # Compiler-related typed references and models.
│       │   │   ├── fabric.py  # Fabric-related typed references (evidence, results, bounds).
│       │   │   ├── foundry.py  # Foundry-related typed references (ProgramGraph, ExecPlan, etc.).
│       │   │   ├── legal.py  # Legal contracts: NormPack/NormRule/RuleBackend/RuleType.
│       │   │   ├── scientist.py  # Scientist contracts: critique, failure cards, timelines, decision cards.
│       │   │   └── trinity.py  # Trinity contracts: ProblemFrame/PolicySpec/ModelSpec + bundle/refs.
│       │   ├── registry/  # Registry bundle builder/loader (reproducible components).
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── builder.py  # Build registry bundles from available components.
│       │   │   └── loader.py  # Load registry bundles (content and payload).
│       │   ├── run/  # Run context and run manifest models.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── context.py  # RunContext: execution context for a single run.
│       │   │   └── manifest.py  # Run manifest models and serialization.
│       │   ├── trace/  # Structured tracing records and sinks.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── record.py  # TraceRecord model for structured tracing.
│       │   │   └── sink.py  # Trace sinks (e.g., JSONL sink).
│       │   ├── observability/  # Production-grade telemetry system (OpenTelemetry tracing, metrics, logs, propagation).
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── config.py  # OpenTelemetry configuration and resource attributes + HPC observability control.
│       │   │   ├── decorators.py  # @traced and @traced_method decorators for automatic function instrumentation.
│       │   │   ├── logs.py  # Structured logging with trace correlation.
│       │   │   ├── metrics.py  # Prometheus-compatible metrics registry and timers + CAS operation metrics.
│       │   │   ├── propagation.py  # Trace context propagation across threads/services.
│       │   │   └── tracer.py  # PolicyOSTracer singleton with OpenTelemetry integration.
│       │   ├── README.md  # Documentation for this directory/module.
│       │   └── __init__.py  # Python package initializer (public exports live here).
│       ├── fabric/  # Unified Data Fabric: ingestion, catalog, evidence, quality, trust, UDF queries, external connectors.
│       │   ├── catalog/  # Metric-level data contracts and bindings registry.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── binding.py  # MetricBinding: hash-locked binding between names and contracts.
│       │   │   ├── contract.py  # DataContract models and validation (types, granularity, PII tiers).
│       │   │   ├── registry.py  # DataContractRegistry: load/validate/search contracts.
│       │   │   ├── search.py  # Metric search and fuzzy disambiguation utilities.
│       │   │   └── validate.py  # Helpers to validate contract collections.
│       │   ├── io/  # DuckDB/Kùzu storage backends.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── db.py  # DuckDB backend for analytical queries and tables.
│       │   │   └── graph_store.py  # Kùzu backend for graph storage and queries.
│       │   ├── provenance/  # W3C PROV-O provenance graph and exporters.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── core.py  # PROV-O graph core models and relationships.
│       │   │   └── export_provo.py  # Export provenance graphs to PROV-O formats.
│       │   ├── udf/  # Secure UDF compilation/execution layer for data views.
│       │   │   ├── passes/  # UDF compiler passes (lowering, typing, privacy, etc.).
│       │   │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   │   ├── lowering.py  # Lower UDF IR into backend-executable primitives.
│       │   │   │   ├── merge.py  # Optimize/merge UDF plans and remove duplicates.
│       │   │   │   ├── privacy.py  # Privacy enforcement pass for UDF queries.
│       │   │   │   ├── resolution.py  # Resolve dependencies and link UDF components.
│       │   │   │   └── typecheck.py  # Static type checker for UDF expressions.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── compiler.py  # UDF compiler with security/type checks and pass pipeline.
│       │   │   ├── config.py  # UDF allowlist configuration and access tier policies.
│       │   │   ├── engine.py  # UDF execution engine (planning + execution).
│       │   │   ├── plan.py  # UDF query planning and optimization.
│       │   │   └── schema.py  # UDF IR/schema validation for query definitions.
│       │   ├── README.md  # Documentation for this directory/module.
│       │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   ├── _connector_bridge.py  # Connector bridge for Scientist layer isolation (Law A enforcement).
│       │   ├── config.py  # Fabric configuration (paths, backends, catalog settings).
│       │   ├── evidence.py  # Evidence bundle models and cryptographic/provenance scaffolding.
│       │   ├── fact_writer.py  # Immutable fact writer for audit/provenance-friendly logs.
│       │   ├── fitness_report.py  # Human-readable data fitness reports.
│       │   ├── ingestion.py  # ETL ingestion pipeline (raw → staging → queryable stores).
│       │   ├── manifest.py  # Dataset manifest models (quality/provenance metadata).
│       │   ├── materializer.py  # Materialize fact logs into relational/graph views.
│       │   ├── quality.py  # Quality indicators, thresholds, and quality level evaluation.
│       │   ├── registry.py  # UDF/function registry (allowlists, access tiers).
│       │   ├── schema.py  # Fabric schema/types shared across ingestion and UDF.
│       │   ├── segment_manifest.py  # Segment manifest models (partitioning, optimization metadata).
│       │   └── trust.py  # Trust policies and uncertainty quantification utilities.
│       │   ├── connectors/  # External data source connectors with protocol compliance and capability system.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── base.py  # BaseConnector protocol and core types (ConnectionConfig, FetchRequest, etc.).
│       │   │   ├── capabilities.py  # Capability validation utilities and protocol compliance checking.
│       │   │   ├── discovery.py  # Connector discovery via entry points and dev-only paths.
│       │   │   ├── pool.py  # Connection pooling with health checks and eviction.
│       │   │   ├── registry.py  # Connector registry with indices and lazy loading.
│       │   │   ├── cache/  # CAS-based caching system with invalidation and prefetching.
│       │   │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   │   ├── invalidation.py  # Cache invalidation strategies and policies.
│       │   │   │   ├── policy.py  # Cache policies and TTL management.
│       │   │   │   ├── prefetch.py  # Intelligent prefetching for performance optimization.
│       │   │   │   ├── proxy.py  # Caching proxy layer for connectors.
│       │   │   │   └── store.py  # CAS store implementation for connector caching.
│       │   │   ├── contracts/  # Contract evolution and schema management for connectors.
│       │   │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   │   ├── evolution.py  # Contract evolution and migration utilities.
│       │   │   │   ├── inference.py  # Schema inference from data sources.
│       │   │   │   ├── registry.py  # Contract registry and validation.
│       │   │   │   └── schema.py  # Schema management and validation utilities.
│       │   │   ├── federation/  # Cross-connector federation and composition.
│       │   │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   │   ├── composer.py  # Federation composition logic.
│       │   │   │   ├── evidence_aggregation.py  # Evidence aggregation across federated sources.
│       │   │   │   ├── planner.py  # Federation query planning.
│       │   │   │   ├── ranker.py  # Source ranking and selection for federation.
│       │   │   │   ├── resolver.py  # Federation resolution and conflict handling.
│       │   │   │   └── types.py  # Federation type definitions.
│       │   │   ├── quality/  # Data quality assessment and validation.
│       │   │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   │   ├── completeness.py  # Data completeness validation.
│       │   │   │   ├── consistency.py  # Data consistency checks.
│       │   │   │   ├── freshness.py  # Data freshness assessment.
│       │   │   │   ├── report.py  # Quality assessment reports.
│       │   │   │   └── validator.py  # Quality validation utilities.
│       │   │   ├── reference/  # Reference connector implementations.
│       │   │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   │   ├── rest_json.py  # REST/JSON connector reference implementation.
│       │   │   │   ├── sdmx.py  # SDMX connector reference implementation.
│       │   │   │   └── static_csv.py  # Static CSV connector reference implementation.
│       │   │   ├── resilience/  # Resilience patterns for connector operations.
│       │   │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   │   ├── circuit_breaker.py  # Circuit breaker pattern implementation.
│       │   │   │   ├── fallback.py  # Fallback handling for connector failures.
│       │   │   │   ├── rate_limiter.py  # Rate limiting for connector requests.
│       │   │   │   └── retry.py  # Retry logic for connector operations.
│       │   │   ├── testing/  # Testing infrastructure for connectors.
│       │   │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   │   ├── contracts.py  # Testing contract definitions.
│       │   │   │   ├── fixtures.py  # Test fixtures for connector testing.
│       │   │   │   ├── harness.py  # ConnectorTestHarness for protocol compliance.
│       │   │   │   └── simulator.py  # APISimulator for offline testing.
│       │   │   ├── transform/  # Data transformation and processing pipeline.
│       │   │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   │   ├── aggregator.py  # Data aggregation utilities.
│       │   │   │   ├── filter.py  # Data filtering and selection.
│       │   │   │   ├── harmonizer.py  # Data harmonization across sources.
│       │   │   │   ├── imputer.py  # Missing data imputation.
│       │   │   │   ├── normalizer.py  # Data normalization utilities.
│       │   │   │   ├── pipeline.py  # Transformation pipeline orchestration.
│       │   │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   │   └── validator.py  # Data validation during transformation.
│       │   │   └── types/  # Type system and data type utilities.
│       │   │       ├── __init__.py  # Python package initializer (public exports live here).
│       │   │       ├── coercion.py  # Type coercion utilities.
│       │   │       ├── connector_types.py  # Connector-specific type definitions.
│       │   │       ├── dimensions.py  # Dimensional data type handling.
│       │   │       ├── temporal.py  # Temporal data type utilities.
│       │   │       └── units.py  # Unit conversion and validation.
│       ├── foundry/  # JAX execution core: compilation, runtime, simulation, calibration, determinism tools.
│       │   ├── agent_sim/  # Agent-based simulation subsystem.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── actor_critic.py  # Python module implementing 'actor_critic'.
│       │   │   ├── analysis.py  # Python module implementing 'analysis'.
│       │   │   ├── artifact.py  # Python module implementing 'artifact'.
│       │   │   ├── credit_assignment.py  # Python module implementing 'credit_assignment'.
│       │   │   ├── dashboard.py  # Python module implementing 'dashboard'.
│       │   │   ├── demographics.py  # Python module implementing 'demographics'.
│       │   │   ├── distribution_executor.py  # Python module implementing 'distribution_executor'.
│       │   │   ├── distribution_mechanisms.py  # Python module implementing 'distribution_mechanisms'.
│       │   │   ├── distributions.py  # Python module implementing 'distributions'.
│       │   │   ├── evolution.py  # Python module implementing 'evolution'.
│       │   │   ├── executor.py  # Python module implementing 'executor'.
│       │   │   ├── experiment.py  # Python module implementing 'experiment'.
│       │   │   ├── government_policy.py  # Python module implementing 'government_policy'.
│       │   │   ├── graph_executor.py  # Python module implementing 'graph_executor'.
│       │   │   ├── graph_mechanisms.py  # Python module implementing 'graph_mechanisms'.
│       │   │   ├── graph_observations.py  # Python module implementing 'graph_observations'.
│       │   │   ├── graphs.py  # Python module implementing 'graphs'.
│       │   │   ├── jit_training.py  # Python module implementing 'jit_training'.
│       │   │   ├── mechanism.py  # Python module implementing 'mechanism'.
│       │   │   ├── mechanisms.py  # Python module implementing 'mechanisms'.
│       │   │   ├── metrics.py  # Python module implementing 'metrics'.
│       │   │   ├── modes.py  # Python module implementing 'modes'.
│       │   │   ├── mpc.py  # Python module implementing 'mpc'.
│       │   │   ├── policy.py  # Python module implementing 'policy'.
│       │   │   ├── population.py  # Python module implementing 'population'.
│       │   │   ├── population_executor.py  # Python module implementing 'population_executor'.
│       │   │   ├── population_mechanisms.py  # Python module implementing 'population_mechanisms'.
│       │   │   ├── prng.py  # Python module implementing 'prng'.
│       │   │   ├── rewards.py  # Python module implementing 'rewards'.
│       │   │   ├── rl.py  # Python module implementing 'rl'.
│       │   │   ├── state.py  # Python module implementing 'state'.
│       │   │   ├── temporal.py  # Python module implementing 'temporal'.
│       │   │   ├── temporal_executor.py  # Python module implementing 'temporal_executor'.
│       │   │   ├── temporal_mechanisms.py  # Python module implementing 'temporal_mechanisms'.
│       │   │   ├── training.py  # Python module implementing 'training'.
│       │   │   ├── vfi.py  # Python module implementing 'vfi'.
│       │   │   └── visualization.py  # Python module implementing 'visualization'.
│       │   ├── calibration/  # Parameter calibration subsystem (gradient-based optimization).
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── bijectors.py  # Bijectors for parameter constraint enforcement (sigmoid, softplus).
│       │   │   ├── calibrator.py  # Calibrator class for parameter optimization.
│       │   │   ├── loss.py  # Loss functions (MSE, Huber, weighted loss).
│       │   │   ├── preflight.py  # Data preparation and configuration validation.
│       │   │   ├── pure_executor.py  # JAX pure executor for calibration runs.
│       │   │   └── report.py  # Calibration reports with fit quality metrics.
│       │   ├── domain/  # Economic domain state schemas and types.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── schema.py  # Python module implementing 'schema'.
│       │   │   └── state.py  # Python module implementing 'state'.
│       │   ├── plugins/  # Plugin system for extending the domain/mechanisms/objectives.
│       │   │   ├── economics/  # Economics plugin implementations.
│       │   │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   │   ├── mechanisms.py  # Python module implementing 'mechanisms'.
│       │   │   │   ├── objectives.py  # Python module implementing 'objectives'.
│       │   │   │   ├── plugin.py  # Python module implementing 'plugin'.
│       │   │   │   ├── rewards.py  # Python module implementing 'rewards'.
│       │   │   │   └── state.py  # Python module implementing 'state'.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── api.py  # Python module implementing 'api'.
│       │   │   ├── cli.py  # Python module implementing 'cli'.
│       │   │   ├── composite.py  # Python module implementing 'composite'.
│       │   │   ├── core.py  # Python module implementing 'core'.
│       │   │   └── discovery.py  # Python module implementing 'discovery'.
│       │   ├── runtime/  # Runtime utilities (determinism fingerprinting, NaN guard).
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   │   ├── api.py  # Runtime run lifecycle API (start/finalize/log artifacts).
│       │   │   │   └── manifest.py  # Portable runtime manifest and path resolution helpers.
│       │   │   ├── fingerprint.py  # Environment fingerprinting and determinism tier controls.
│       │   │   └── nan_guard.py  # Runtime NaN/Inf detection and diagnostics.
│       │   ├── README.md  # Documentation for this directory/module.
│       │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   ├── agent_metrics.py  # Python module implementing 'agent_metrics'.
│       │   ├── agents.py  # Python module implementing 'agents'.
│       │   ├── base.py  # Python module implementing 'base'.
│       │   ├── compiler.py  # Compile IR policies into ProgramGraph and ExecPlan.
│       │   ├── conflict_checker.py  # Static conflict detection on slot writes (pre-JAX).
│       │   ├── constraints_engine.py  # Constraint evaluation and enforcement engine for policies.
│       │   ├── cost_model.py  # Heuristic cost model for compile/runtime budgeting.
│       │   ├── executor.py  # Execute compiled programs (JAX step/scan/batch).
│       │   ├── fiscal.py  # Python module implementing 'fiscal'.
│       │   ├── labor.py  # Python module implementing 'labor'.
│       │   ├── layout.py  # Python module implementing 'layout'.
│       │   ├── loss.py  # Python module implementing 'loss'.
│       │   ├── merge_engine.py  # Deterministic merge semantics (CRDT-inspired) for state updates.
│       │   ├── patch_vm.py  # Patch-based virtual machine for incremental updates.
│       │   ├── queue.py  # Python module implementing 'queue'.
│       │   ├── registry.py  # Foundry component registry and dependency injection utilities.
│       │   ├── specs.py  # Python module implementing 'specs'.
│       │   ├── trace.py  # Python module implementing 'trace'.
│       │   ├── treasury.py  # RNG/seed treasury for reproducible stochastic simulations.
│       │   ├── types.py  # Core Foundry types (fidelity levels, specs, typing helpers).
│       │   └── utils.py  # Python module implementing 'utils'.
│       ├── ir/  # Canonical IR contracts: PolicySurfaceIR, Trinity artifacts, kernel registries, loaders, validation.
│       │   ├── kernel/  # IR kernel registries: mechanisms, slots, units, merge rules, time semantics.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── base.py  # Python module implementing 'base'.
│       │   │   ├── constraints.py  # Python module implementing 'constraints'.
│       │   │   ├── mechanisms.py  # Python module implementing 'mechanisms'.
│       │   │   ├── merge_rules.py  # Python module implementing 'merge_rules'.
│       │   │   ├── metrics.py  # Python module implementing 'metrics'.
│       │   │   ├── numbers.py  # Python module implementing 'numbers'.
│       │   │   ├── selector_fields.py  # Python module implementing 'selector_fields'.
│       │   │   ├── slots.py  # Python module implementing 'slots'.
│       │   │   ├── time_semantics.py  # Python module implementing 'time_semantics'.
│       │   │   ├── trust.py  # Python module implementing 'trust'.
│       │   │   ├── units.py  # Python module implementing 'units'.
│       │   │   └── values.py  # Python module implementing 'values'.
│       │   ├── migrations/  # IR format migrations and Trinity bridging utilities.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   └── trinity_migration.py  # Python module implementing 'trinity_migration'.
│       │   ├── README.md  # Documentation for this directory/module.
│       │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   ├── calibration.py  # Python module implementing 'calibration'.
│       │   ├── data_views.py  # Python module implementing 'data_views'.
│       │   ├── fact_log.py  # Python module implementing 'fact_log'.
│       │   ├── linker.py  # Validate and link IR against kernel registries.
│       │   ├── loaders.py  # Universal policy loader (auto-detect versions/formats).
│       │   ├── model_spec.py  # ModelSpec models (data snapshots, assumptions, time semantics).
│       │   ├── norm_pack.py  # NormPack/NormRule contracts and validation (incl. safe expression checks).
│       │   ├── policy_spec.py  # PolicySpec models (interventions/parameters).
│       │   ├── predicate.py  # Python module implementing 'predicate'.
│       │   ├── problem_frame.py  # ProblemFrame models (goals/KPIs/constraints).
│       │   ├── surface.py  # PolicySurfaceIR (canonical policy contract, legacy-compatible surface).
│       │   ├── trinity.py  # Trinity artifacts and bundle (ProblemFrame/PolicySpec/ModelSpec).
│       │   ├── types.py  # Python module implementing 'types'.
│       │   ├── units.py  # Python module implementing 'units'.
│       │   └── validation.py  # Python module implementing 'validation'.
│       ├── runtime/  # Run lifecycle API and portable run manifests.
│       │   ├── README.md  # Documentation for this directory/module.
│       │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   ├── api.py  # Runtime run lifecycle API (start/finalize/log artifacts).
│       │   └── manifest.py  # Portable runtime manifest and path resolution helpers.
│       ├── scientist/  # Orchestration layer: agents, workflows, governance passes, search optimization.
│       │   ├── agent/  # Hierarchical agent system (PI/Drafter/Formalizer/Critic + reflexion).
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── base.py  # Python module implementing 'base'.
│       │   │   ├── critic.py  # Critic agent with TracedLLMClient integration.
│       │   │   ├── drafter.py  # Drafter agent with TracedLLMClient integration.
│       │   │   ├── failure_card.py  # Python module implementing 'failure_card'.
│       │   │   ├── formalizer.py  # Formalizer agent with TracedLLMClient integration.
│       │   │   ├── memory.py  # Python module implementing 'memory'.
│       │   │   ├── pi.py  # PI agent with TracedLLMClient integration.
│       │   │   ├── prompt.py  # Python module implementing 'prompt'.
│       │   │   ├── prompts.py  # Python module implementing 'prompts'.
│       │   │   ├── protocols.py  # Python module implementing 'protocols'.
│       │   │   └── reflexion.py  # Self-healing reflexion loop (repair attempts, pruning).
│       │   ├── compute/  # Compute backends abstraction (runner + job specs).
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── job_spec.py  # Python module implementing 'job_spec'.
│       │   │   └── runner.py  # Python module implementing 'runner'.
│       │   ├── doe/  # Design of Experiments utilities.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   └── designs.py  # Python module implementing 'designs'.
│       │   ├── governance/  # Preflight/postflight validation pipeline and compliance checks.
│       │   │   ├── legal/  # Legal compliance subsystem (norm packs, backends, security policy).
│       │   │   │   ├── backends/  # Pluggable legal rule backends.
│       │   │   │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   │   │   ├── base.py  # Python module implementing 'base'.
│       │   │   │   │   ├── expr_ast.py  # Safe AST interpreter and Legal RuleBackend implementation (no eval/exec).
│       │   │   │   │   └── stub.py  # Python module implementing 'stub'.
│       │   │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   │   └── ast_policy.py  # AST allowlist policy and resource limits for safe expression validation.
│       │   │   ├── passes/  # Validation passes (schema, safety, legal, privacy, quality gate, budgets).
│       │   │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   │   ├── base.py  # Python module implementing 'base'.
│       │   │   │   ├── budget_pass.py  # Python module implementing 'budget_pass'.
│       │   │   │   ├── legal_pass.py  # Python module implementing 'legal_pass'.
│       │   │   │   ├── privacy_pass.py  # Python module implementing 'privacy_pass'.
│       │   │   │   ├── quality_gate_pass.py  # Python module implementing 'quality_gate_pass'.
│       │   │   │   ├── safety_pass.py  # Python module implementing 'safety_pass'.
│       │   │   │   └── schema_pass.py  # Python module implementing 'schema_pass'.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── pipeline.py  # Governance pipeline orchestrator for validation passes.
│       │   │   ├── postflight.py  # Post-execution validation entrypoint.
│       │   │   ├── preflight.py  # Pre-execution validation entrypoint.
│       │   │   ├── profiles.py  # Validation profiles (fast/mvp/strict) selecting passes and limits.
│       │   │   └── telemetry.py  # Governance telemetry capture (timings, summaries).
│       │   ├── kernel/  # Scientist kernel (FSM, budgets, guards, human gates).
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── budgets.py  # Python module implementing 'budgets'.
│       │   │   ├── fsm.py  # Python module implementing 'fsm'.
│       │   │   ├── guards.py  # Python module implementing 'guards'.
│       │   │   └── human_gate.py  # Python module implementing 'human_gate'.
│       │   ├── llm/  # LLM layer: tracing и monitoring для LLM взаимодействий.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   └── traced_client.py  # TracedLLMClient с OpenTelemetry интеграцией.
│       │   ├── orchestrator/  # Workflow orchestration: nodes, state, audit, decision packet/card, timeline.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── audit.py  # Python module implementing 'audit'.
│       │   │   ├── compiler.py  # Python module implementing 'compiler'.
│       │   │   ├── data_loader.py  # Python module implementing 'data_loader'.
│       │   │   ├── decision_card.py  # DecisionCard: deterministic human-readable summary artifact.
│       │   │   ├── decision_packet.py  # DecisionPacket: structured run output container (artifacts + validations).
│       │   │   ├── flow_nodes.py  # Workflow node implementations and routing logic.
│       │   │   ├── nodes.py  # Python module implementing 'nodes'.
│       │   │   ├── optimizer.py  # Python module implementing 'optimizer'.
│       │   │   ├── registry.py  # Python module implementing 'registry'.
│       │   │   ├── run_record.py  # Python module implementing 'run_record'.
│       │   │   ├── run_timeline.py  # RunTimeline: event timeline artifact for observability.
│       │   │   ├── state.py  # Python module implementing 'state'.
│       │   │   └── workflow.py  # Build and run the main Scientist workflow graph.
│       │   ├── search/  # Search/optimization framework.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── controller.py  # SearchController: optimization loop coordination.
│       │   │   ├── objective.py  # Python module implementing 'objective'.
│       │   │   ├── stages.py  # Two-stage evaluation (cheap vs expensive) for optimization.
│       │   │   └── stopping.py  # Stopping criteria for search/optimization.
│       │   ├── workflow/  # Workflow engine abstractions.
│       │   │   ├── README.md  # Documentation for this directory/module.
│       │   │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   │   ├── engine_base.py  # Python module implementing 'engine_base'.
│       │   │   ├── engine_langgraph.py  # LangGraph-based workflow engine implementation.
│       │   │   └── engine_simple.py  # Simple sequential workflow engine implementation.
│       │   ├── README.md  # Documentation for this directory/module.
│       │   ├── __init__.py  # Python package initializer (public exports live here).
│       │   └── publisher.py  # Publish/finalize results (artifacts, summaries).
│       └── __init__.py  # Python package initializer (public exports live here).
├── tests/  # Test suite.
│   ├── contract/  # Contract and schema tests for IR/Trinity/kernel.
│   │   ├── README.md  # Documentation for this directory/module.
│   │   ├── test_fabric_gates.py  # Pytest module exercising fabric gates.
│   │   ├── test_ir_contract.py  # Pytest module exercising ir contract.
│   │   ├── test_ir_migrations.py  # Pytest module exercising ir migrations.
│   │   ├── test_kernel_models.py  # Pytest module exercising kernel models.
│   │   ├── test_surface_ir.py  # Pytest module exercising surface ir.
│   │   ├── test_trinity_contracts.py  # Pytest module exercising trinity contracts.
│   │   └── test_trinity_migration.py  # Pytest module exercising trinity migration.
│   ├── core_phase0/  # Core infrastructure tests (CAS, canonical JSON, registry bundles, observability system).
│   │   ├── README.md  # Documentation for this directory/module.
│   │   ├── conftest.py  # Pytest shared fixtures and configuration.
│   │   ├── test_artifact_store.py  # Pytest module exercising artifact store.
│   │   ├── test_canon_json.py  # Pytest module exercising canon json.
│   │   ├── test_decorators.py  # Pytest module exercising @traced decorator for automatic instrumentation.
│   │   ├── test_environment_manifest.py  # Pytest module exercising environment manifest.
│   │   ├── test_logs.py  # Pytest module exercising log-trace correlation.
│   │   ├── test_metrics.py  # Pytest module exercising metrics registry and timers.
│   │   ├── test_observability.py  # Pytest module exercising integrated observability workflows.
│   │   ├── test_propagation.py  # Pytest module exercising trace context propagation.
│   │   ├── test_registry_bundle.py  # Pytest module exercising registry bundle.
│   │   ├── test_run_context.py  # Pytest module exercising run context.
│   │   └── test_tracer.py  # Pytest module exercising PolicyOSTracer singleton.
│   ├── demos/  # Demo smoke tests.
│   │   ├── README.md  # Documentation for this directory/module.
│   │   └── run_laffer_demo.py  # File.
│   ├── fabric/  # Fabric tests.
│   │   ├── connectors/  # Connector protocol compliance tests.
│   │   │   ├── __init__.py  # Python package initializer (public exports live here).
│   │   │   ├── test_integration.py  # Phase 2.12 Integration & Governance verification suite.
│   │   │   ├── test_protocol_compliance.py  # Pytest module exercising connector protocol compliance.
│   │   │   └── test_registry.py  # Pytest module exercising registry, pooling, and discovery.
│   │   ├── README.md  # Documentation for this directory/module.
│   │   ├── test_data_catalog.py  # Pytest module exercising data catalog.
│   │   ├── test_evidence_bundle.py  # Pytest module exercising evidence bundle.
│   │   ├── test_provenance.py  # Pytest module exercising provenance.
│   │   ├── test_quality_indicators.py  # Pytest module exercising quality indicators.
│   │   └── test_trust_two_pass.py  # Pytest module exercising trust two pass.
│   ├── foundry/  # Foundry tests.
│   │   ├── agent_sim/  # Agent simulation monitoring tests.
│   │   │   ├── README.md  # Documentation for this directory/module.
│   │   │   └── test_monitoring.py  # Pytest module exercising monitoring.
│   │   ├── plugins/  # Plugin system tests.
│   │   │   ├── README.md  # Documentation for this directory/module.
│   │   │   └── test_plugin_system.py  # Pytest module exercising plugin system.
│   │   ├── README.md  # Documentation for this directory/module.
│   │   ├── test_adaptive_agents.py  # Pytest module exercising adaptive agents.
│   │   ├── test_agent_artifact.py  # Pytest module exercising agent artifact.
│   │   ├── test_agent_simulation_step1.py  # Pytest module exercising agent simulation step1.
│   │   ├── test_agent_simulation_step2.py  # Pytest module exercising agent simulation step2.
│   │   ├── test_agent_simulation_step3.py  # Pytest module exercising agent simulation step3.
│   │   ├── test_agent_simulation_step4.py  # Pytest module exercising agent simulation step4.
│   │   ├── test_agent_simulation_step5.py  # Pytest module exercising agent simulation step5.
│   │   ├── test_agent_simulation_step6.py  # Pytest module exercising agent simulation step6.
│   │   ├── test_calibrator_fidelity.py  # Pytest module exercising calibrator fidelity.
│   │   ├── test_calibrator_mvp.py  # Pytest module exercising calibrator mvp.
│   │   ├── test_conflict_detection.py  # Pytest module exercising conflict detection.
│   │   ├── test_constraints_executor.py  # Pytest module exercising constraints executor.
│   │   ├── test_cost_model.py  # Pytest module exercising cost model.
│   │   ├── test_fiscal.py  # Pytest module exercising fiscal.
│   │   ├── test_global_state.py  # Pytest module exercising global state.
│   │   ├── test_gradients.py  # Pytest module exercising gradients.
│   │   ├── test_health.py  # Pytest module exercising health.
│   │   ├── test_jit_compilation_tracker.py # JIT compilation tracking и optimization metrics
│   │   ├── test_jit_stability.py  # Pytest module exercising jit stability.
│   │   ├── test_merge_determinism.py  # Pytest module exercising merge determinism.
│   │   ├── test_nan_guard.py  # Pytest module exercising nan guard.
│   │   ├── test_patch_executor.py  # Pytest module exercising patch executor.
│   │   ├── test_program_graph_ops.py  # Pytest module exercising program graph ops.
│   │   └── test_runtime_batch.py  # Pytest module exercising runtime batch.
│   ├── integration/  # Cross-module integration tests.
│   │   ├── README.md  # Documentation for this directory/module.
│   │   ├── test_calibration_udf.py  # Pytest module exercising calibration udf.
│   │   ├── test_workflow_llm.py  # Pytest module exercising workflow llm.
│   │   └── test_workflow_smoke.py  # Pytest module exercising workflow smoke.
│   ├── ir/  # IR tests.
│   │   ├── README.md  # Documentation for this directory/module.
│   │   └── test_loaders.py  # Pytest module exercising loaders.
│   ├── runtime/  # Runtime tests.
│   │   ├── README.md  # Documentation for this directory/module.
│   │   └── test_runtime_manifest_paths.py  # Pytest module exercising runtime manifest paths.
│   ├── scientist/  # Scientist tests.
│   │   ├── governance/  # Governance/legal compliance tests (safe expressions, passes).
│   │   │   ├── README.md  # Documentation for this directory/module.
│   │   │   ├── test_legal_pass.py  # Pytest module exercising legal pass.
│   │   │   ├── test_norm_execution.py  # Pytest module exercising norm execution.
│   │   │   └── test_validation_pipeline.py  # Pytest module exercising validation pipeline.
│   │   ├── search/  # Search framework tests.
│   │   │   ├── README.md  # Documentation for this directory/module.
│   │   │   ├── __init__.py  # Python package initializer (public exports live here).
│   │   │   ├── conftest.py  # Pytest shared fixtures and configuration.
│   │   │   └── test_search_loop.py  # Pytest module exercising search loop.
│   │   ├── integration/  # Integration tests for workflow tracing.
│   │   │   └── test_workflow_tracing.py  # Integration test for end-to-end workflow tracing.
│   │   ├── README.md  # Documentation for this directory/module.
│   │   ├── conftest.py  # Pytest shared fixtures and configuration.
│   │   ├── test_agent_protocols.py  # Pytest module exercising agent protocols.
│   │   ├── test_compiler.py  # Pytest module exercising compiler.
│   │   ├── test_decision_card.py  # Pytest module exercising decision card.
│   │   ├── test_decision_packet_v2.py  # Pytest module exercising decision packet v2.
│   │   ├── test_instrumentation.py  # Phase 2 instrumentation tests for Scientist workflow.
│   │   ├── test_multi_agent_workflow.py  # Pytest module exercising multi agent workflow.
│   │   ├── test_reflexion_loop.py  # Pytest module exercising reflexion loop.
│   │   └── test_run_timeline.py  # Pytest module exercising run timeline.
│   ├── README.md  # Documentation for this directory/module.
│   └── conftest.py  # Pytest shared fixtures and configuration.
├── performance/  # Performance validation tests (observability overhead SLA enforcement).
│   ├── README.md  # Documentation for performance tests.
│   └── test_overhead.py  # Overhead validation for simulation, CAS I/O, calibration operations.
├── tools/  # Developer tooling: linters, migrations, diagnostics, benchmarks, demos.
│   ├── benchmarks/  # Performance benchmarks.
│   │   ├── README.md  # Documentation for this directory/module.
│   │   ├── bench_domain.py  # Benchmark script.
│   │   └── bench_simulation.py  # Benchmark script.
│   ├── demos/  # Runnable demo scripts.
│   │   ├── README.md  # Documentation for this directory/module.
│   │   ├── run_export_demo.py  # Demo script.
│   │   ├── run_ingest_demo.py  # Demo script.
│   │   ├── run_laffer_demo.py  # Demo script.
│   │   ├── run_optimizer_demo.py  # Demo script.
│   │   ├── run_udf_hybrid_demo.py  # Demo script.
│   │   └── run_udf_query_demo.py  # Demo script.
│   ├── connectors/  # Connector development tools.
│   │   ├── lint_connectors.py  # Law A/B enforcement linter for connectors.
│   │   └── scaffold.py  # Connector scaffold generator for new implementations.
│   ├── diagnostics/  # Diagnostics scripts.
│   │   ├── README.md  # Documentation for this directory/module.
│   │   ├── check_setup.py  # Diagnostics script.
│   │   ├── check_udf_perf.py  # Diagnostics script.
│   │   ├── check_perf_regression.py  # Performance regression checker for CI/CD (pytest-benchmark comparison).
│   │   └── generate_ir_schema.py  # Diagnostics script.
│   ├── README.md  # Documentation for this directory/module.
│   ├── capture_env.py  # Capture environment details into a reproducibility manifest.
│   ├── gen_schema.py  # Generate JSON Schema snapshots from Pydantic models.
│   ├── lint_foundry.py  # Foundry purity linter (Law B enforcement).
│   ├── lint_imports.py  # Architecture import-boundary linter (Law A enforcement).
│   ├── migrate.py  # File.
│   ├── migrate_ir.py  # Migrate Policy IR artifacts between schema versions.
│   ├── migrate_to_trinity.py  # Batch migration utilities from Surface IR to Trinity artifacts.
│   ├── run_mechanism_design.py  # End-to-end differentiable mechanism design demo/driver.
│   ├── scan_fabric.py  # Scan data stores and draft Fabric data contracts.
│   └── visualize_provenance.py  # Visualize and verify provenance graphs.
├── .gitignore  # Git ignore rules for the project workspace.
├── .pre-commit-config.yaml  # Pre-commit hooks configuration (formatting/linting checks).
├── Dockerfile.reproducible  # Reproducible container build definition.
├── README.md  # Main project README (high-level concepts, flows, and usage).
├── architecture.md  # Project file-by-file structure reference (this document).
├── dashboard.py  # Streamlit dashboard entrypoint for visualizing runs and artifacts.
├── env_example.txt  # Environment variables template.
├── install.sh  # Bootstrap installer script (dev setup).
├── jax_bootstrap.py  # Applies safe JAX environment defaults before importing jax.
├── migrate.py  # CLI tool to migrate schema-managed artifacts to target versions.
├── model_spec_schema.json  # Generated JSON Schema snapshot for ModelSpec.
├── policy_ir_schema.json  # Generated JSON Schema snapshot for PolicySurfaceIR.
├── policy_spec_schema.json  # Generated JSON Schema snapshot for PolicySpec.
├── problem_frame_schema.json  # Generated JSON Schema snapshot for ProblemFrame.
├── pyproject.toml  # Project metadata, dependencies, and tool configuration.
├── run_experiment.py  # CLI entrypoint to run a Scientist workflow for an experiment.
└── uv.lock  # Locked dependency graph for uv.
```

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

- **DuckDB** (analytical store with incremental materialization)
- **Kùzu** (graph store for social network analysis)
- **PyArrow**, **pandas** (high-performance data processing)
- **W3C PROV-O style provenance** (implemented in Fabric provenance subsystem v2.0 with JSON-LD/N-Quads export)

### Orchestration and optimization

- **LangGraph**, **LangChain** (workflow orchestration and LLM integration)
- **pymoo** (multi-objective optimization for policy search)
- **CMA-ES** (evolution algorithms for agent simulation)

### UI / visualization

- **Streamlit**, **Plotly** (dashboarding)

### Observability / configuration

- **loguru** (structured logging with trace correlation)
- **python-dotenv** (local environment variable loading)
- **opentelemetry-api** / **opentelemetry-sdk** (distributed tracing and telemetry)
- **prometheus_client** (metrics collection and exposition)
- **hashlib** (deterministic ID generation for artifacts and facts)

### Dev tooling

- **pytest**, **pytest-benchmark**, **hypothesis** (testing and benchmarking)
- **ruff**, **mypy** (code quality and type checking)
- **pre-commit** (automated code quality checks)
- **difflib** (structured diff generation for validation reports)

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
- **Grafana**: Dashboards for executive overview, HPC performance, and agent analytics with PolicyOS-specific visualizations
- **Docker Compose**: Containerized observability stack with service dependencies
- **Core Observability v2.1**: PolicyOSTracer singleton, MetricsRegistry, @traced decorators, log-trace correlation, context propagation, LLM tracing, distributed tracing

**Monitored metrics:**
- LLM costs and token consumption (budget alerts: $50/hour, $100/hour critical)
- Agent workflow performance and success rates (failure thresholds: 5%, 20%)
- HPC simulation throughput and JIT compilation efficiency with gradient health monitoring
- Calibration convergence and uncertainty quantification
- Governance pipeline latency and pass success rates
- Quality gate validation outcomes and data fitness scores
- Evidence bundle verification and provenance tracking
- Runtime execution with environment fingerprinting and reproducibility checks

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

- **Contract Tests**: IR schema validation, Trinity contracts, migrations, kernel models, linker validation, data connectors contracts
- **Core Phase 0 Tests**: Artifact store, canonical JSON, observability system (PolicyOSTracer, MetricsRegistry, @traced), environment manifests, log correlation, context propagation, decorators, propagation, tracer
- **Fabric Tests**: Data connectors protocol compliance, data contract catalog (hash-locked bindings, fuzzy search), evidence bundles with CAS integration, provenance system (W3C PROV-O), trust quantification with statistical verification, quality indicators system (missingness/staleness/coverage/outliers), fitness reports with configurable thresholds, quality gate pass integration, fact log semantic network, materializer engine incremental updates, trust two-pass comparison
- **Foundry Tests**: JAX simulation engine, agent artifacts, plugin system, adaptive agents, merge determinism, NaN guard, cost model, conflict detection, gradient health, calibrator systems, jit compilation tracker, jit stability, patch executor, program graph ops, runtime batch
- **Scientist Tests**: Hierarchical agent system (PI→Drafter→Formalizer→Critic), Trinity IR generation, governance passes pipeline, Phase 18 legal compliance with AST policy, search loop system, workflow engines, LLM tracing, decision outputs, Phase 2 instrumentation, decision card, decision packet v2, run timeline, multi-agent workflow, reflexion loop
- **Integration Tests**: End-to-end workflows, calibration UDF integration, LLM workflow orchestration, real database testing, workflow smoke test, workflow LLM, data connectors integration
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

