# Complete Policy Engine Architecture

> **Last updated:** January 27, 2026 (added Runtime module with Environment Fingerprinting, Agent Policy Artifacts system, comprehensive monitoring/test coverage for agent simulation and plugin system, compile-time conflict detection, cost estimation model, NaN/Inf runtime guards, DecisionCard human-readable summaries, RunTimeline observability artifacts, and enhanced Scientist contracts)
>
> This document contains the complete architecture of the Policy Engine project with detailed descriptions of all files in the `src/`, `tests/`, and `tools/` directories.

## Project Structure

```
policy-engine/
├── pyproject.toml / uv.lock          # Project dependencies and build configuration managed by uv
├── README.md                         # Main project documentation with architecture overview
├── env_example.txt                   # Template for environment variables and API keys
├── install.sh                        # Automated installation script for all dependencies
├── policy_ir_schema.json             # Generated JSON Schema for PolicySurfaceIR validation
├── model_spec_schema.json            # Generated JSON Schema for ModelSpec validation (Trinity)
├── policy_spec_schema.json           # Generated JSON Schema for PolicySpec validation (Trinity)
├── problem_frame_schema.json         # Generated JSON Schema for ProblemFrame validation (Trinity)
├── .env                              # API keys and environment configuration (not in Git!)
├── .polisyos/                        # Content-Addressable Storage (CAS) for artifacts
│   └── artifacts/sha256/...          # SHA256-addressed artifacts (blobs, manifests) for reproducibility
├── data/                             # Data pipeline directories with ETL processing stages
│   ├── raw/                          # Raw CSV files and source datasets from external sources
│   ├── staging/                      # Intermediate Parquet files after ETL transformations
│   ├── curated/                      # Final processed data ready for analysis
│   │   ├── *.duckdb                  # Analytical databases (DuckDB) for OLAP queries
│   │   ├── *.kuzu                    # Graph databases (Kùzu) for relationship analysis
│   │   ├── fact_log/                 # Immutable facts with provenance tracking
│   │   ├── udf_schema.json           # UDF whitelist configuration and access tier definitions
│   │   └── manifests/                # Dataset manifests with quality metadata and statistics
│   └── manifests/                    # Global dataset manifests for data governance
├── logs/                             # Structured JSON Lines logs for monitoring and debugging
├── runs/                             # Runtime experiment results with full reproducibility
│   └── <run_id>/                     # Each directory represents a single experiment run
│       ├── manifest.json             # RunManifest with metadata, artifacts, and provenance
│       ├── audit.jsonl               # Complete audit trail of all operations and decisions
│       └── artifacts/                # Structured experiment outputs and results
│           ├── policy_ir/            # Policy IR artifacts and configurations
│           ├── simulation_results/   # Simulation metrics and outcome data
│           ├── data_views/           # Results of UDF query executions
│           └── registry_bundle/      # Registry bundles for experiment reproducibility
├── src/polisyos/                     # Core system modules source code
│   ├── __init__.py                   # Empty package initializer (marks directory as Python package)
│   ├── common/                       # Fundamental utilities with no external dependencies
│   │   ├── __init__.py               # Exports configuration and logging interfaces
│   │   ├── config.py                 # Centralized application configuration and environment setup
│   │   ├── jax_env.py                # Safe JAX backend configuration for macOS compatibility
│   │   ├── logger.py                 # Unified structured logging interface (Loguru with fallback to standard logging)
│   │   ├── migrations/               # Deterministic artifact versioning and schema evolution
│   │   │   ├── __init__.py           # Exports migration system API
│   │   │   ├── base.py               # Core migration system with version management
│   │   │   ├── manifest.py           # Dataset Manifest migration logic and transformations
│   │   │   ├── policy_ir.py          # Policy IR schema migrations between versions
│   │   │   └── README.md             # Migration system documentation and usage examples
│   │   └── README.md                 # Common module documentation and architectural role
│   ├── core/                         # Fundamental artifacts infrastructure and inter-module contracts
│   │   ├── __init__.py               # Exports core module public API
│   │   ├── artifacts/                # Content-addressable artifact management and storage system
│   │   │   ├── __init__.py           # Exports artifacts management API
│   │   │   ├── environment.py        # Environment manifest structures for reproducible execution contexts
│   │   │   ├── ids.py                # Unique artifact identifiers (ArtifactID) with SHA256 hashing
│   │   │   ├── manifest.py           # Artifact metadata structures (ArtifactManifest, ArtifactRef)
│   │   │   ├── README.md             # Artifact system documentation and CAS principles
│   │   │   ├── registry.py           # Component registry bundles for reproducible deployments
│   │   │   └── store.py              # FileSystem CAS implementation with integrity verification
│   │   ├── canon/                    # Canonical JSON serialization for deterministic hashing
│   │   │   ├── __init__.py           # Exports canonical JSON serialization API
│   │   │   ├── canon_json.py         # Deterministic JSON serialization (CanonSpec, to_canonical_bytes)
│   │   │   └── README.md             # Canonical serialization documentation and usage
│   │   ├── compiler/                 # Compilation and linking reports management
│   │   │   ├── __init__.py           # Exports compilation reports API
│   │   │   ├── README.md             # Compilation reports documentation
│   │   │   └── report.py             # Compilation report management (CompileReport, put_compile_report)
│   │   ├── contracts/                # Type-safe contracts between system modules
│   │   │   ├── __init__.py           # Exports contracts API
│   │   │   ├── compiler.py           # Compiler contracts (CompileReportRef, LinkReportRef)
│   │   │   ├── fabric.py             # Fabric contracts (6 reference types + data models, quality indicators)
│   │   │   ├── foundry.py            # Foundry contracts (16 reference types + execution models, agent policy artifacts)
│   │   │   ├── scientist.py          # Scientist contracts (FailureCardRef, PolicyIRRef, CritiqueRef, TimelineRef, DecisionCardRef)
│   │   │   ├── trinity.py            # Trinity contracts (ProblemFrame, PolicySpec, ModelSpec, TrinityBundle)
│   │   │   ├── legal.py              # Legal compliance contracts (NormPack, NormRule, RuleBackend)
│   │   │   └── README.md             # Inter-module contracts documentation
│   │   ├── README.md                 # Core module architecture and responsibilities
│   │   ├── registry/                 # Component registry building and loading system
│   │   │   ├── __init__.py           # Exports registry management API
│   │   │   ├── builder.py            # Registry bundle building (build_default_registry_bundle, build_registry_bundle)
│   │   │   ├── loader.py             # Registry bundle loading (load_registry_bundle_content, load_registry_bundle_payload)
│   │   │   └── README.md             # Registry system documentation and bundle formats
│   │   ├── run/                      # Execution contexts and run manifests management
│   │   │   ├── __init__.py           # Exports run context API
│   │   │   ├── context.py            # Execution context management (RunContext)
│   │   │   ├── manifest.py           # Run manifest structures (RunManifest)
│   │   │   └── README.md             # Execution contexts documentation
│   │   └── trace/                    # Distributed tracing and operation logging system
│   │     ├── __init__.py             # Exports tracing API
│   │     ├── README.md               # Tracing system documentation and usage
│   │     ├── record.py               # Trace record structures (TraceRecord)
│   │     └── sink.py                 # Trace output sinks (JsonlTraceSink, TraceSink)
│   ├── fabric/                       # Unified Data Fabric (data processing + cryptographic evidence)
│   │   ├── __init__.py               # Exports Fabric module public API (run_ingestion, catalog components)
│   │   ├── catalog/                  # Metric-level data contract catalog system
│   │   │   ├── __init__.py           # Exports catalog API (DataContract, MetricBinding, DataContractRegistry)
│   │   │   ├── binding.py            # MetricBinding - hash-locked immutable references to contracts
│   │   │   ├── contract.py           # DataContract models and validation (DataType, Granularity, PIITier)
│   │   │   ├── registry.py           # DataContractRegistry with hash validation and contract loading
│   │   │   ├── search.py             # MetricSearcher with fuzzy matching and disambiguation
│   │   │   └── validate.py           # Contract validation from JSON and collection loading
│   │   ├── config.py                 # Fabric layer configuration and data source setup (FabricConfig, CatalogConfig)
│   │   ├── evidence.py               # Cryptographically verifiable evidence bundles for data provenance
│   │   ├── fact_writer.py            # Immutable fact writer for audit trails and provenance
│   │   ├── fitness_report.py         # Data quality fitness assessment and human-readable reports
│   │   ├── quality.py                # Quality indicators, thresholds, and level determination system
│   │   ├── ingestion.py              # Full ETL pipeline (CSV → DuckDB + Kùzu with validation)
│   │   ├── io/                       # Multi-backend storage interfaces (DuckDB + Kùzu)
│   │   │   ├── __init__.py           # Exports IO interfaces API
│   │   │   ├── db.py                 # DuckDB interface for analytical queries and aggregations
│   │   │   ├── graph_store.py        # Kùzu interface for graph data and relationship queries
│   │   │   └── README.md             # IO interfaces documentation and performance characteristics
│   │   ├── manifest.py               # Dataset manifests with quality metadata and statistics
│   │   ├── materializer.py           # Fact Log materialization into relational tables
│   │   ├── README.md                 # Fabric module architecture and data processing pipeline
│   │   ├── registry.py               # UDF function registry with security and access control
│   │   ├── schema.py                 # Fabric data schemas and type definitions
│   │   ├── segment_manifest.py       # Segment manifests for data partitioning and optimization
│   │   ├── trust.py                  # Trust policies with statistical verification and uncertainty bounds
│   │   ├── provenance/               # W3C PROV-O provenance tracking system
│   │   │   ├── __init__.py          # Exports provenance API
│   │   │   ├── core.py               # ProvenanceCoreGraph and entity models (ProvenanceEntity, ProvenanceActivity, ProvenanceAgent)
│   │   │   └── export_provo.py       # PROV-O JSON-LD and N-Quads export
│   │   └── udf/                      # User Defined Functions (secure compiled queries)
│   │       ├── __init__.py           # Exports UDF system API
│   │       ├── compiler.py           # UDF query compilation with security checks
│   │       ├── config.py             # UDF whitelist configuration and access tier management
│   │       ├── engine.py             # UDF execution engine with query optimization
│   │       ├── passes/               # UDF compiler passes for optimization and validation
│   │       │   ├── __init__.py       # Exports compiler passes API
│   │       │   ├── lowering.py       # UDF lowering to SQL/Python execution primitives
│   │       │   ├── merge.py          # Query optimization merging and deduplication
│   │       │   ├── privacy.py        # Privacy-preserving transformations and checks
│   │       │   ├── resolution.py     # UDF dependency resolution and linking
│   │       │   └── typecheck.py      # Static type checking for UDF expressions
│   │       ├── plan.py               # UDF query planning and execution optimization
│   │       ├── README.md             # UDF system documentation and security model
│   │       └── schema.py             # UDF query schemas and validation rules
│   ├── foundry/                      # JAX mathematical core (differentiable policy simulation)
│   │   ├── __init__.py               # Exports Foundry module public API
│   │   ├── agent_metrics.py          # Agent-level metrics for simulation analysis
│   │   ├── agent_sim/                # Heterogeneous agent simulation with neural networks
│   │   │   ├── __init__.py           # Exports agent simulation API (37+ components including monitoring, artifacts, fingerprinting)
│   │   │   ├── actor_critic.py       # Actor-Critic architectures for reinforcement learning
│   │   │   ├── analysis.py           # Post-simulation analysis and statistical evaluation
│   │   │   ├── artifact.py           # Immutable, content-addressable artifacts for trained agent policies
│   │   │   ├── credit_assignment.py  # Multi-agent credit assignment and reward distribution
│   │   │   ├── dashboard.py          # Real-time simulation monitoring dashboard
│   │   │   ├── demographics.py       # Agent lifecycle processes (birth, aging, death, migration)
│   │   │   ├── distribution_executor.py # Distributed simulation execution across multiple workers
│   │   │   ├── distribution_mechanisms.py # Resource distribution mechanisms and algorithms
│   │   │   ├── distributions.py      # Statistical distributions for agent heterogeneity
│   │   │   ├── evolution.py          # Evolutionary algorithms for agent adaptation
│   │   │   ├── executor.py           # Main agent simulation executor with JAX compilation
│   │   │   ├── experiment.py         # Experiment management and parameter sweeping
│   │   │   ├── government_policy.py  # Government policy interventions in simulations
│   │   │   ├── graph_executor.py     # Graph-based executor for network interactions
│   │   │   ├── graph_mechanisms.py   # Graph-aware economic mechanisms
│   │   │   ├── graph_observations.py # Graph-structured observation spaces
│   │   │   ├── graphs.py             # Agent social network structures and dynamics
│   │   │   ├── jit_training.py       # JIT-compiled agent training loops
│   │   │   ├── mechanism.py          # Core economic mechanism implementations
│   │   │   ├── mechanisms.py         # Collection of economic mechanisms (taxes, subsidies, queues)
│   │   │   ├── metrics.py            # Simulation metrics and inequality measures
│   │   │   ├── modes.py              # Simulation execution modes (single/multi-fidelity)
│   │   │   ├── mpc.py                # Model Predictive Control for agent decision making
│   │   │   ├── policy.py             # Agent behavioral policies and decision rules
│   │   │   ├── population_executor.py # Population-level simulation executor
│   │   │   ├── population_mechanisms.py # Population-wide economic mechanisms
│   │   │   ├── population.py         # Population dynamics and demographic management
│   │   │   ├── prng.py               # Pseudorandom number generation for reproducibility
│   │   │   ├── README.md             # Agent simulation documentation and neural architectures
│   │   │   ├── rewards.py            # Agent reward systems and incentive structures
│   │   │   ├── rl.py                 # Reinforcement learning algorithms for agents
│   │   │   ├── state.py              # Agent state representations and transitions
│   │   │   ├── temporal_executor.py  # Temporal simulation executor for time-series analysis
│   │   │   ├── temporal_mechanisms.py # Time-aware economic mechanisms
│   │   │   ├── temporal.py           # Temporal aspects and memory in simulations
│   │   │   ├── training.py           # Agent training procedures and curriculum learning
│   │   │   └── vfi.py                # Value Function Iteration for dynamic programming
│   │   ├── agents.py                 # Base agent definitions and state structures
│   │   ├── base.py                   # Core Foundry components and utilities
│   │   ├── calibration/              # Parameter calibration using Optax optimization
│   │   │   ├── __init__.py           # Exports calibration API
│   │   │   ├── bijectors.py          # Parameter transformation bijectors for constrained optimization
│   │   │   ├── calibrator.py         # Main parameter calibrator with Optax integration
│   │   │   ├── loss.py               # Calibration loss functions and metrics
│   │   │   ├── preflight.py          # Calibration preflight checks and validation
│   │   │   ├── pure_executor.py      # Pure functional executor for calibration runs
│   │   │   ├── README.md             # Calibration system documentation and algorithms
│   │   │   └── report.py             # Calibration reports with convergence analysis
│   │   ├── compiler.py               # IR compilation to ProgramGraph + ExecPlan
│   ├── conflict_checker.py        # Compile-time conflict detection and resolution analysis
│   ├── cost_model.py              # Execution cost estimation with self-calibration
│   │   ├── constraints_engine.py     # Policy constraint validation and enforcement engine
│   │   ├── domain/                   # Economic domain model (GlobalState, AgentState)
│   │   ├── runtime/                  # Patch-based execution runtime with JAX and environment fingerprinting
│   │   │   ├── __init__.py           # Exports runtime module public API (step, run_scan, execute_program_batch)
│   │   │   ├── fingerprint.py        # Environment fingerprinting and determinism tier configuration
│   │   │   ├── nan_guard.py          # Runtime NaN/Inf detection with diagnostics for STRICT validation
│   │   │   └── README.md             # Runtime module documentation and environment fingerprinting system
│   │   │   ├── __init__.py           # Exports domain model API
│   │   │   ├── README.md             # Domain model documentation and state evolution
│   │   │   ├── schema.py             # Economic model schemas and validation
│   │   │   └── state.py              # Global and agent state representations
│   │   ├── executor.py               # Main simulation executor with JAX compilation
│   │   ├── fiscal.py                 # Fiscal policy mechanisms and tax implementations
│   │   ├── labor.py                  # Labor market mechanisms and employment dynamics
│   │   ├── layout.py                 # Simulation component layout and memory management
│   │   ├── loss.py                   # Policy optimization loss functions
│   │   ├── merge_engine.py           # CRDT-inspired merge engine for deterministic state updates
│   │   ├── patch_vm.py               # Patch-based virtual machine for incremental updates
│   │   ├── plugins/                  # Plugin system for domain extension and customization
│   │   │   ├── __init__.py           # Exports plugin system API
│   │   │   ├── api.py                # Plugin API interfaces and contracts
│   │   │   ├── cli.py                # Command-line interface for plugin management
│   │   │   ├── composite.py          # Composite plugins for complex domain extensions
│   │   │   ├── core.py               # Core plugin system infrastructure
│   │   │   ├── discovery.py          # Automatic plugin discovery and loading
│   │   │   ├── economics/            # Economic domain plugins
│   │   │   │   ├── __init__.py       # Exports economics plugin API
│   │   │   │   ├── mechanisms.py     # Economic mechanism plugin implementations
│   │   │   │   ├── objectives.py     # Plugin objective functions and metrics
│   │   │   │   ├── plugin.py         # Base economics plugin class
│   │   │   │   └── rewards.py        # Plugin reward system implementations
│   │   │   └── README.md             # Plugin system documentation and extension guide
│   │   ├── queue.py                  # Queue mechanisms and resource allocation algorithms
│   │   ├── README.md                 # Foundry module documentation and JAX integration
│   │   ├── registry.py               # Foundry component registry and dependency injection
│   │   ├── runtime.py                # Patch-based execution runtime with JAX
│   │   ├── specs.py                  # Simulation specifications and parameter definitions
│   │   ├── trace.py                  # Execution tracing and debugging utilities
│   │   ├── treasury.py               # Treasury management and government budget tracking
│   │   ├── types.py                  # Foundry-specific type definitions and annotations
│   │   └── utils.py                  # Foundry utility functions and helper classes
│   ├── ir/                           # Intermediate Representation (canonical contracts)
│   │   ├── __init__.py               # Exports IR module public API
│   │   ├── calibration.py            # Parameter calibration contracts and specifications
│   │   ├── data_views.py             # Data query contracts (PANEL/SNAPSHOT/NETWORK views)
│   │   ├── fact_log.py               # Immutable facts with cryptographic provenance tracking
│   │   ├── kernel/                   # Fundamental registries (mechanisms, slots, units, metrics)
│   │   │   ├── __init__.py           # Exports kernel API
│   │   │   ├── base.py               # Core kernel definitions and type system
│   │   │   ├── constraints.py        # Policy constraint definitions and validation
│   │   │   ├── mechanisms.py         # Registry of economic mechanisms and interventions
│   │   │   ├── merge_rules.py        # Policy merging rules and conflict resolution
│   │   │   ├── metrics.py            # System metrics and measurement definitions
│   │   │   ├── numbers.py            # Numerical type definitions and precision handling
│   │   │   ├── README.md             # Kernel documentation and registry specifications
│   │   │   ├── selector_fields.py    # Policy selector field definitions and validation
│   │   │   ├── slots.py              # System state slots and data flow definitions
│   │   │   ├── time_semantics.py     # Temporal semantics and time-aware operations
│   │   │   ├── trust.py              # Trust policies and evidence validation rules
│   │   │   ├── units.py              # Measurement units and dimensional analysis
│   │   │   └── values.py             # Value types and data representations
│   │   ├── linker.py                 # Policy validation and linking against kernel registries
│   │   ├── loaders.py                # Universal policy loading with auto-detection
│   │   ├── migrations/               # Deterministic migrations between IR versions
│   │   │   ├── __init__.py           # Exports IR migration API
│   │   │   ├── trinity_migration.py  # Migration utilities for Trinity framework adoption
│   │   │   └── README.md             # IR migration documentation and version compatibility
│   │   ├── predicate.py              # Policy predicates and conditional logic
│   │   ├── README.md                 # IR module documentation and contract specifications
│   │   ├── surface.py                # PolicySurfaceIR v2.0 (main policy contract)
│   │   ├── trinity.py                # Trinity framework (ProblemFrame, PolicySpec, ModelSpec, TrinityBundle)
│   │   ├── model_spec.py             # ModelSpec implementation with data snapshots and time semantics
│   │   ├── policy_spec.py            # PolicySpec implementation with interventions and parameters
│   │   ├── problem_frame.py          # ProblemFrame implementation with KPIs and success criteria
│   │   ├── norm_pack.py              # Normative packages for legal compliance validation (NormPack, NormRule, NormRef)
│   │   ├── types.py                  # IR-specific type definitions and annotations
│   │   ├── units.py                  # Unit conversion and measurement utilities
│   │   └── validation.py             # IR structure validation and error reporting
│   ├── runtime/                      # Experiment lifecycle management and reproducibility
│   │   ├── __init__.py               # Exports runtime module public API
│   │   ├── api.py                    # Core runtime API (start_run, finalize_run, log_artifact)
│   │   ├── manifest.py               # Run manifests with portable artifact references
│   │   └── README.md                 # Runtime API documentation and lifecycle management
│   └── scientist/                    # AI-driven experiment orchestration and policy design
│       ├── __init__.py               # Exports scientist module public API
│       ├── agent/                    # LLM-based agents (Drafter, MockAgent, PolicyGenerator)
│       │   ├── __init__.py           # Exports agent API
│       │   ├── base.py               # Base agent class with common functionality
│       │   ├── critic.py             # Critic agent for policy evaluation and critique generation
│       │   ├── drafter.py            # Drafter agent for policy generation from natural language
│       │   ├── failure_card.py       # Structured artifacts for self-healing workflow failures
│       │   ├── formalizer.py         # Formalizer agent for mathematical formalization of policies
│       │   ├── memory.py             # Short-term memory for Reflexion workflow conversation tracking
│       │   ├── pi.py                 # Policy Iteration agent for optimization and refinement
│       │   ├── prompt.py             # Prompt management and template system
│       │   ├── prompts.py            # Curated collection of LLM prompts and templates
│       │   ├── protocols.py          # Agent communication protocols and interfaces
│       │   ├── reflexion.py          # Self-healing workflow orchestrator with intelligent routing
│       │   └── README.md             # Agent system documentation and LLM integration
│       ├── compute/                  # Task specifications and execution backends
│       │   ├── __init__.py           # Exports compute API
│       │   ├── job_spec.py           # Job specifications and resource requirements
│       │   ├── README.md             # Compute system documentation
│       │   └── runner.py             # Task runner with backend abstraction
│       ├── doe/                      # Design of Experiments (ScenarioSweep, AblationPlan)
│       │   ├── __init__.py           # Exports DoE API
│       │   ├── designs.py            # Experiment design patterns and parameter sweeps
│       │   └── README.md             # Design of Experiments documentation
│       ├── governance/               # Preflight/postflight validation and safety checks
│       │   ├── __init__.py           # Exports governance API
│       │   ├── passes/               # Modular validation passes system
│       │   │   ├── __init__.py       # Exports validation passes API
│       │   │   ├── base.py           # Base classes for validation passes and compliance issues
│       │   │   ├── budget_pass.py    # Budget constraint validation (compute, evidence, complexity)
│       │   │   ├── legal_pass.py     # Legal norm compliance validation with pluggable backends
│       │   │   ├── privacy_pass.py   # Privacy and data protection validation
│       │   │   ├── quality_gate_pass.py # Data quality validation before simulation execution
│       │   │   ├── safety_pass.py    # Policy safety and mechanism validation
│       │   │   └── schema_pass.py    # Policy schema validation and structure checks
│       │   ├── pipeline.py           # Validation pipeline orchestrator with short-circuit logic
│       │   ├── postflight.py         # Post-execution validation and result verification
│       │   ├── preflight.py          # Pre-execution safety checks and validation
│       │   ├── profiles.py           # Validation profiles (fast/mvp/strict) with configurable passes
│       │   ├── telemetry.py          # Validation tracing and performance monitoring
│       │   ├── legal/                # Legal validation backends for norm evaluation
│       │   │   ├── __init__.py       # Exports legal backends API
│       │   │   ├── backends/         # Pluggable rule evaluation backends
│       │   │   │   ├── __init__.py   # Exports backends API
│       │   │   │   ├── base.py       # RuleBackend protocol and evaluation contracts
│       │   │   │   └── stub.py       # StubBackend implementation for Phase 10 reference
│       │   │   └── README.md         # Legal validation backend documentation and architecture
│       │   └── README.md             # Governance system documentation and policies
│       ├── kernel/                   # Core orchestration (FSM, budgets, guards, human gates)
│       │   ├── __init__.py           # Exports kernel API
│       │   ├── budgets.py            # Resource budget management and allocation
│       │   ├── fsm.py                # Finite State Machine for experiment orchestration
│       │   ├── guards.py             # Safety guards and execution constraints
│       │   ├── human_gate.py         # Human-in-the-loop decision gates
│       │   └── README.md             # Kernel documentation and orchestration patterns
│       ├── orchestrator/             # LangGraph workflow orchestration with 9 phases
│       │   ├── __init__.py           # Exports orchestrator API
│       │   ├── audit.py              # Operation audit trail and compliance tracking
│       │   ├── compiler.py           # Workflow compilation and optimization
│       │   ├── data_loader.py        # Experiment data loading and preprocessing
│       │   ├── decision_card.py      # Human-readable summaries of experiment results
│       │   ├── decision_packet.py    # Structured decision packets for workflow communication (DecisionPacket with run_timeline, decision_card, validation_trace)
│       │   ├── flow_nodes.py         # Workflow graph nodes and execution logic
│       │   ├── nodes.py              # Base workflow node implementations
│       │   ├── optimizer.py          # Workflow optimization and parallelization
│       │   ├── README.md             # Orchestrator documentation and 9-phase workflow
│       │   ├── registry.py           # Component registry for workflow extensibility
│       │   ├── run_record.py         # Experiment run records and state persistence
│       │   ├── run_timeline.py       # Timeline artifact for observability and tracing
│       │   ├── state.py              # Workflow state management and transitions
│       │   ├── workflow.py           # Main workflow orchestrator with LangGraph integration
│       │   └── workflow_compiler.py  # Workflow compilation to executable graphs
│       ├── publisher.py              # Result publishing and experiment finalization
│       └── README.md                 # Scientist module documentation and AI orchestration
├── tests/                            # Comprehensive test suite ensuring system quality and architecture compliance
│   ├── conftest.py                   # Pytest configuration and JAX setup for all tests
│   ├── contract/                     # Contract tests validating IR schemas and migrations
│   │   ├── README.md                 # Contract testing documentation and validation patterns
│   │   ├── test_fabric_gates.py      # Fabric layer input validation and precondition testing
│   │   ├── test_ir_contract.py       # PolicySurfaceIR validation, selectors, TranslatableString handling
│   │   ├── test_ir_migrations.py     # IR schema migrations between versions and compatibility
│   │   ├── test_kernel_models.py     # Kernel model validation (slots, units, merge rules, time semantics)
│   │   ├── test_surface_ir.py        # Surface IR validation, linker testing, semantic fingerprinting
│   │   ├── test_trinity_contracts.py # Trinity framework contracts (ProblemFrame, PolicySpec, ModelSpec)
│   │   └── test_trinity_migration.py # Trinity migration utilities and round-trip compatibility
│   ├── core_phase0/                  # Phase 0 tests for fundamental core components
│   │   ├── conftest.py               # Core-specific test configuration and fixtures
│   │   ├── README.md                 # Core testing documentation and Phase 0 architecture
│   │   ├── test_artifact_store.py    # FileSystemCAS testing, deduplication, integrity verification
│   │   ├── test_canon_json.py        # Canonical JSON serialization testing, deterministic hashing
│   │   ├── test_environment_manifest.py # Environment manifest structures and reproducible contexts
│   │   ├── test_registry_bundle.py   # Registry bundle building and loading verification
│   │   └── test_run_context.py       # Run context testing and artifact producer validation
│   ├── demos/                        # Demo integration tests for end-to-end functionality
│   │   ├── README.md                 # Demo testing documentation and integration patterns
│   │   └── run_laffer_demo.py        # Laffer curve demo execution test from tools/demos/
│   ├── fabric/                       # Data layer integration tests (ingestion, evidence, trust)
│   │   ├── README.md                 # Fabric testing documentation and data pipeline validation
│   │   ├── test_data_catalog.py      # Data contract catalog system (contracts, bindings, search, registry)
│   │   ├── test_evidence_bundle.py   # Evidence bundles, ingestion pipeline, provenance tracking
│   │   ├── test_provenance.py        # Provenance subsystem, entities, graphs, PROV-O export, persistence
│   │   ├── test_quality_indicators.py # Quality indicators calculation, fitness reports, and quality gate validation
│   │   └── test_trust_two_pass.py    # Trust system validation with uncertainty bounds analysis
│   ├── foundry/                      # Mathematical core unit tests (JAX, simulations)
│   │   ├── agent_sim/                # Agent simulation testing suite
│   │   │   ├── README.md             # Agent simulation monitoring tests documentation
│   │   │   └── test_monitoring.py    # MetricsCollector, ExperimentTracker, DashboardGenerator testing
│   │   ├── plugins/                  # Plugin system integration tests
│   │   │   ├── README.md             # Foundry plugin system tests documentation
│   │   │   └── test_plugin_system.py # PluginRegistry, CompositeExecutor, EconomicsPlugin domain configs
│   │   ├── README.md                 # Foundry testing documentation and JAX integration patterns
│   │   ├── test_adaptive_agents.py   # Adaptive agent behavior and learning algorithm validation
│   │   ├── test_agent_simulation_step1.py # Agent simulation step 1 validation
│   │   ├── test_agent_simulation_step2.py # Agent simulation step 2 validation
│   │   ├── test_agent_simulation_step3.py # Agent simulation step 3 validation
│   │   ├── test_agent_simulation_step4.py # Agent simulation step 4 validation
│   │   ├── test_agent_simulation_step5.py # Agent simulation step 5 validation
│   │   ├── test_agent_simulation_step6.py # Agent simulation step 6 validation
│   │   ├── test_calibrator_fidelity.py # Parameter calibrator fidelity and accuracy testing
│   │   ├── test_calibrator_mvp.py     # Minimum viable calibrator functionality testing
│   │   ├── test_constraints_executor.py # Policy constraints executor validation
│   │   ├── test_fiscal.py             # Fiscal policy mechanisms and tax system testing
│   │   ├── test_global_state.py       # Global economic state management and evolution
│   │   ├── test_gradients.py          # Gradient computation and automatic differentiation
│   │   ├── test_health.py             # Simulation health checks and stability monitoring
│   │   ├── test_jit_stability.py      # JIT compilation stability and performance validation
│   │   ├── test_merge_determinism.py  # Merge engine determinism and CRDT-inspired state updates
│   │   ├── test_patch_executor.py     # Patch-based execution engine testing
│   │   ├── test_program_graph_ops.py  # Program graph operations and transformations
│   │   ├── test_runtime_batch.py      # Batch runtime execution and parallel processing
│   │   ├── test_conflict_detection.py # Compile-time conflict detection and resolution analysis testing
│   │   ├── test_cost_model.py         # Execution cost estimation model testing
│   │   └── test_nan_guard.py          # NaN/Inf runtime guard testing
│   ├── integration/                  # End-to-end integration tests (calibration UDF, workflow)
│   │   ├── README.md                 # Integration testing documentation and system validation
│   │   ├── test_calibration_udf.py   # Parameter calibration through UDF system integration
│   │   ├── test_workflow_llm.py      # LLM-driven workflow integration and policy generation
│   │   └── test_workflow_smoke.py    # Basic workflow smoke tests and orchestration validation
│   ├── ir/                           # IR loading and transformation testing
│   │   ├── README.md                 # IR testing documentation and validation patterns
│   │   └── test_loaders.py           # Universal policy loader testing with auto-detection
│   ├── README.md                     # Complete test suite documentation and architecture
│   ├── runtime/                      # Experiment lifecycle management testing
│   │   ├── README.md                 # Runtime testing documentation and lifecycle validation
│   │   └── test_runtime_manifest_paths.py # Runtime manifests with portable path resolution
│   └── test_agent_artifact.py        # AgentPolicyArtifact round-trip serialization, environment fingerprinting, hot-swap validation
│   └── scientist/                    # AI components and orchestration testing
│       ├── governance/               # Governance layer testing
│       │   ├── test_legal_pass.py    # Legal validation pass testing and backend integration
│       │   └── test_validation_pipeline.py # Validation pipeline orchestration and compliance testing
│       ├── README.md                 # Scientist testing documentation and AI validation
│       ├── test_agent_protocols.py   # Agent communication protocols and interface validation
│       ├── test_compiler.py          # Scientist workflow compiler testing and optimization
│       ├── test_decision_card.py     # DecisionCard deterministic generation and markdown rendering
│       ├── test_decision_packet_v2.py # DecisionPacket v1.1 with timeline and card support
│       ├── test_multi_agent_workflow.py # Multi-agent workflow integration and memory persistence testing
│       ├── test_reflexion_loop.py    # Reflexion loop and FailureCard system validation
│       └── test_run_timeline.py      # RunTimeline event recording and analytics
└── tools/                            # Developer tools and demonstrations ensuring architecture compliance
    ├── benchmarks/                   # Performance benchmarks for JAX and simulation components
    │   ├── bench_domain.py           # Economic domain model benchmark (JAX + Equinox + GlobalState allocation)
    │   ├── bench_simulation.py       # Full simulation pipeline benchmark with economic cycles
    │   └── README.md                 # Benchmarking documentation and performance analysis
    ├── demos/                        # Demonstration scripts showcasing system capabilities
    │   ├── README.md                 # Demo scripts documentation and usage examples
    │   ├── run_export_demo.py        # Simulation results export demo (Parquet, JSON, CSV, HDF5)
    │   ├── run_ingest_demo.py        # Complete ingestion pipeline demo (CSV → DuckDB + Kuzu)
    │   ├── run_laffer_demo.py        # Laffer curve economic policy demonstration
    │   ├── run_optimizer_demo.py     # Multi-objective policy optimization demo (NSGA-II)
    │   ├── run_udf_hybrid_demo.py    # Hybrid queries demo (SQL + Python UDF with ML)
    │   └── run_udf_query_demo.py     # UDF queries demo on Unified Data Fabric
    ├── diagnostics/                  # System diagnostics and performance analysis tools
    │   ├── check_setup.py            # Comprehensive component installation verification
    │   ├── check_udf_perf.py         # UDF performance profiling and optimization analysis
    │   ├── generate_ir_schema.py     # JSON Schema generation from Pydantic models
    │   └── README.md                 # Diagnostic tools documentation and troubleshooting
    ├── gen_schema.py                 # JSON Schema generation utility from Pydantic models
    ├── lint_foundry.py               # Mathematical core purity linter (Law B compliance)
    ├── lint_imports.py               # Architectural dependency linter (Law A compliance)
    ├── scan_fabric.py                # Bootstrap utility to scan DuckDB files and generate draft data contracts
    ├── capture_env.py                # Environment capture and manifest generation tool
    ├── visualize_provenance.py       # Provenance graph visualization and verification tool
    ├── migrate_ir.py                 # Specialized Policy IR migration tool
    ├── migrate.py                    # Universal artifact migration tool
    ├── migrate_to_trinity.py         # Batch migration tool for Trinity framework adoption
    ├── README.md                     # Developer tools documentation and best practices
    └── run_mechanism_design.py       # End-to-end differentiable mechanism design demonstration
```

## Architectural Principles

This document follows the same architectural principles as the main project README.md:

- **Law A (Dependencies)**: Unidirectional dependencies (flowing inward through architecture layers)
- **Law B (Compiler Pipeline)**: NL → LLM → IR → Compilation → Runtime execution flow
- **Law C (Contracts)**: IR as single source of truth for all system contracts
- **Law D (Reproducibility)**: Full reproducibility through CAS artifacts and complete audit trails
- **Law E (Evidence)**: Cryptographically verifiable evidence for all results and decisions
- **Law F (Trinity)**: Orthogonal decomposition of experiments into ProblemFrame, PolicySpec, and ModelSpec

## Description Legend

Each file in the architecture includes a detailed description of its functionality following these patterns:
- **Core Components**: `__init__.py` - exports module's public API interfaces
- **README Files**: Comprehensive documentation for modules, subsystems, and usage patterns
- **Executable Files**: Detailed description of primary functionality and integration points
- **Test Files**: Specific testing scope, validation targets, and key verification checks

## Trinity Framework

The Trinity Framework represents a major architectural evolution that decomposes policy experiments into three orthogonal components:

### ProblemFrame ("What")
- **Purpose**: Defines the problem space, success criteria, and stakeholder context
- **Contents**: KPIs, constraints, actors, problem statement, and success criteria tags
- **Immutability**: Fixed within an experiment context for reproducible evaluation
- **Files**: `ir/problem_frame.py`, `problem_frame_schema.json`

### PolicySpec ("How")
- **Purpose**: Specifies policy interventions, parameters, and implementation details
- **Contents**: Intervention actions with schedules, implementation notes, and policy labels
- **Iterability**: Subject to optimization and iterative refinement during experiments
- **Files**: `ir/policy_spec.py`, `policy_spec_schema.json`

### ModelSpec ("Where")
- **Purpose**: Configures the computational model, data sources, and simulation assumptions
- **Contents**: Data snapshots, registry bundles, time semantics, and model assumptions
- **Role**: The "laboratory bench" providing the experimental environment
- **Files**: `ir/model_spec.py`, `model_spec_schema.json`

### TrinityBundle
- **Purpose**: Container for transporting and processing complete Trinity specifications
- **Integration**: Used as DecisionPacket input in orchestration workflows
- **Migration**: Supports round-trip compatibility with legacy PolicySurfaceIR format
- **Files**: `ir/trinity.py`, `ir/migrations/trinity_migration.py`, `tools/migrate_to_trinity.py`

### Benefits
- **Separation of Concerns**: Orthogonal decomposition enables focused optimization of each aspect
- **Composability**: Mix and match different problem frames, policies, and models for experimentation
- **Traceability**: Clear provenance tracking from problem definition through execution
- **Reproducibility**: Deterministic experiment setup with explicit assumptions and constraints

## Runtime Module & Environment Fingerprinting

The Runtime module introduces a comprehensive environment fingerprinting system and low-level execution primitives for reproducible neural network policy deployment.

### Runtime Module (`foundry/runtime/`)

**Purpose**: Provides pure JAX execution primitives and environment capture for deterministic policy deployment.

#### Core Execution Functions
- **`step`**: Pure JAX function for single simulation step execution
- **`run_scan`**: Efficient sequential execution using `jax.lax.scan`
- **`execute_program_batch`**: Parallel batch execution with deterministic RNG layout

#### Environment Fingerprinting (`fingerprint.py`)
- **`EnvironmentFingerprint`**: Lightweight environment capture (<1KB JSON, <100ms capture)
- **`DeterminismTier`**: Three-tier determinism guarantee system (STRICT_CPU, BEST_EFFORT_GPU, NONDETERMINISTIC)
- **`configure_determinism`**: JAX/XLA configuration for specified determinism levels

#### Runtime NaN/Inf Guard (`nan_guard.py`)
- **`NaNGuard`**: Runtime detection of NaN/Inf values with human-readable diagnostics
- **`NaNDiagnostic`**: Structured diagnostic information for numerical issues
- **`create_nan_guard_for_profile`**: Profile-based guard configuration (disabled/fast/mvp/strict)
- **Performance**: Efficient `jnp.any()` checks with configurable frequency
- **Integration**: Only enabled in STRICT validation profile for debugging

### Agent Policy Artifacts (`agent_sim/artifact.py`)

**Purpose**: Immutable, content-addressable artifacts for trained neural network policies with full provenance tracking.

#### Key Features
- **Content-Addressable Storage**: SHA256-based artifact identification and integrity verification
- **Environment Validation**: Compatibility scoring between training and deployment environments
- **Hot-Swap Safety**: I/O shape validation for runtime policy replacement
- **Provenance Tracking**: Complete audit trail (training run, steps, loss, environment fingerprint)

#### Artifact Components
- **`AgentPolicyArtifact`**: Generic artifact container for trained policies
- **`TrainingMetrics`**: Comprehensive training provenance information
- **`IOShapeSpec`**: I/O compatibility specification for safe hot-swapping

### Integration with Artifact System

**Storage**: Policies stored as separate weights/manifest artifacts in CAS
**Loading**: Environment validation before policy deployment
**Compatibility**: Automated compatibility scoring between environments
**Hot-Swap**: Runtime policy replacement with shape validation

### Benefits
- **Bit-Exact Reproducibility**: Environment fingerprinting ensures identical computation results
- **Safe Deployment**: Compatibility validation prevents incompatible policy deployment
- **Provenance Tracking**: Complete audit trail from training through deployment
- **Performance**: JIT-compiled execution with minimal overhead
- **Scalability**: Batch execution primitives for parallel simulation

## DecisionCard & RunTimeline Artifacts

The Scientist module introduces comprehensive observability and human-readable reporting through two new artifact types that enhance experiment transparency and result communication.

### DecisionCard (`scientist/orchestrator/decision_card.py`)

**Purpose**: Deterministic human-readable summaries of experiment results with structured formatting for stakeholders and audit trails.

#### Key Features
- **Deterministic Generation**: Same DecisionPacket always produces identical DecisionCard
- **Markdown Rendering**: Human-readable format with emojis, tables, and structured sections
- **Compliance Summary**: Blocker/warning/info counts with failed pass identification
- **Key Metrics Display**: Formatted economic indicators with baseline deltas
- **Artifact References**: Links to PolicyIR, simulation results, and evidence bundles
- **Source Hash Tracking**: Deterministic fingerprint for result verification

#### DecisionCard Components
- **`Verdict`**: APPROVE/REJECT/NEEDS_REVISION/PENDING/UNKNOWN with emoji indicators
- **`Confidence`**: HIGH/MEDIUM/LOW based on blocker/warning counts
- **`IssuesSummary`**: Structured compliance issues with blocker counting
- **`KeyMetric`**: Formatted metric display with units and baseline deltas
- **`ArtifactReference`**: Typed references to experiment artifacts

### RunTimeline (`scientist/orchestrator/run_timeline.py`)

**Purpose**: Event-based timeline artifacts for observability, debugging, and performance analysis throughout experiment execution.

#### Key Features
- **Append-Only Design**: Thread-safe event recording with automatic indexing
- **Event Classification**: 12 event types (run_start, phase transitions, node execution, artifacts, validation, errors)
- **Phase Tracking**: Automatic phase start/end timing with duration calculation
- **Node Profiling**: Execution time tracking for workflow nodes
- **Validation Summary**: Pass/failure counts with detailed error analysis
- **Artifact Lifecycle**: Complete tracking of artifact creation and references
- **Trace Integration**: Automatic conversion to core TraceRecord format

#### Timeline Events
- **`RUN_START/RUN_END`**: Experiment lifecycle boundaries
- **`PHASE_START/PHASE_END`**: Workflow phase transitions with duration
- **`NODE_ENTER/NODE_EXIT`**: Individual node execution tracking
- **`ARTIFACT_CREATED`**: New artifact generation events
- **`VALIDATION_PASS/VALIDATION_FAIL`**: Governance validation results
- **`HUMAN_GATE/REFLEXION/ERROR`**: Self-healing and error events

#### Timeline Analytics
- **Phase Durations**: Per-phase execution times for bottleneck identification
- **Node Performance**: Execution time distribution across workflow nodes
- **Error Analysis**: Comprehensive error tracking with context
- **Validation Metrics**: Governance pass/failure ratios
- **Artifact Inventory**: Complete catalog of generated artifacts

### Integration with DecisionPacket

**Enhanced DecisionPacket** now includes three new optional fields for comprehensive experiment documentation:

- **`run_timeline`**: Serialized RunTimeline artifact for observability
- **`decision_card`**: Cached deterministic DecisionCard (generated on-demand)
- **`validation_trace`**: Phase 9 telemetry data from governance validation

#### DecisionPacket Enhancement
```python
class DecisionPacket(BaseModel):
    # Existing fields...
    run_timeline: Optional[Dict[str, Any]] = None      # Timeline observability data
    validation_trace: Optional[Dict[str, Any]] = None  # Governance telemetry
    decision_card: Optional[Dict[str, Any]] = None     # Cached human-readable summary
```

### Scientist Contracts Enhancement

**New contract types** added to `core/contracts/scientist.py` for type-safe artifact references:

- **`TimelineRef`**: References to stored RunTimeline artifacts with run metadata
- **`DecisionCardRef`**: References to DecisionCard artifacts with verdict and generation info

#### Contract Integration
```python
# New contract exports in contracts/__init__.py
from .scientist import (
    TimelineRef,      # Timeline artifact references
    DecisionCardRef,  # DecisionCard artifact references
    # ... existing contracts
)
```

### Benefits
- **Enhanced Observability**: Complete event timeline for experiment debugging and optimization
- **Stakeholder Communication**: Human-readable summaries with structured compliance reporting
- **Audit Trail Enhancement**: Deterministic summaries with source hash verification
- **Performance Analysis**: Detailed timing and bottleneck identification
- **Result Transparency**: Clear verdict communication with confidence metrics
- **Artifact Provenance**: Complete lifecycle tracking from generation to consumption

## Compile-time Analysis & Validation

The compile-time analysis system provides static validation and optimization analysis before JAX compilation, ensuring reliable and efficient policy execution.

### Conflict Detection (`foundry/conflict_checker.py`)

**Purpose**: Static analysis of ProgramGraph for slot conflicts before runtime execution.

#### Key Features
- **Compile-time Analysis**: Pure Python analysis of mechanism slot interactions
- **Merge Rule Validation**: Verifies merge rules are properly registered and configured
- **Conflict Classification**: Uses MergeEngine semantics to classify conflict types
- **Actionable Diagnostics**: Provides specific suggestions for conflict resolution
- **Performance**: O(n*m) complexity where n=nodes, m=avg slots per node (<10ms typical)

#### Conflict Types Detected
- **Missing Slot Registration**: Unregistered slots in SlotRegistry
- **Missing Merge Rules**: Unregistered merge rules in MergeRuleRegistry
- **Multiple Writers**: Slots with multiple mechanisms writing without proper merge rules
- **Unsupported Merge Rules**: Invalid merge rule configurations

#### Integration with Governance
- **Compliance Issues**: Converts conflicts to Phase 9 ComplianceIssue format
- **Severity Levels**: Blocker, warning, and info classifications
- **Location Tracking**: Precise path information for debugging

### Cost Estimation Model (`foundry/cost_model.py`)

**Purpose**: Heuristic cost estimation with self-calibration for execution planning and budget control.

#### Key Features
- **Multi-dimensional Estimation**: Compile time, runtime, memory usage, and FLOPs
- **Self-calibrating Model**: Learns from telemetry to improve accuracy over time
- **Budget Enforcement**: Validates execution against configurable resource constraints
- **Mechanism-specific Costs**: Differentiated costs for different mechanism types
- **Agent Scaling**: Accounts for agent count and time step scaling

#### Cost Components
- **Compile Time**: JAX/XLA compilation overhead estimation
- **Runtime**: Per-step execution cost with mechanism and agent scaling
- **Memory**: Peak memory usage based on agent count and slot requirements
- **FLOPs**: Floating point operation estimates for performance analysis

#### Budget Controls
- **Time Limits**: Total execution, per-mechanism, and compile time budgets
- **Memory Limits**: Peak memory consumption constraints
- **Utilization Tracking**: Fraction of budget consumed with violation detection

### Integration Benefits
- **Pre-execution Validation**: Catches issues before expensive JAX compilation
- **Resource Planning**: Informed decisions about execution feasibility
- **Debugging Support**: Clear diagnostics for conflict resolution
- **Performance Optimization**: Cost-guided optimization decisions
- **System Reliability**: Prevents runtime failures through static analysis
