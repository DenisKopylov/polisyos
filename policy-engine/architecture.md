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
│       │   │   └── types.py  # Connector error types and supporting data structures.
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
│   │   │   └── test_protocol_compliance.py  # Pytest module exercising connector protocol compliance.
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
