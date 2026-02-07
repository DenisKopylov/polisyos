```
policy-engine/  # Project root (Policy Engine / PolisyOS).
├── src/  # Python sources and build metadata.
│   └── polisyos/  # Main Python package.
│       ├── __init__.py
│       ├── common/  # Shared utilities: config, logging, JAX env, migrations.
│       │   ├── __init__.py
│       │   ├── async_tools.py  # Sync/async bridging utilities.
│       │   ├── config.py  # Central pydantic-settings configuration.
│       │   ├── jax_env.py  # JAX environment defaults, macOS backend safety.
│       │   ├── logger.py  # Structured logging (Loguru) + OpenTelemetry correlation.
│       │   └── migrations/  # Deterministic schema migrations.
│       │       ├── __init__.py
│       │       ├── base.py  # Migration framework primitives.
│       │       └── manifest.py  # Dataset manifest migrations.
│       ├── core/  # Infrastructure: CAS, contracts, tracing, registry, observability.
│       │   ├── __init__.py
│       │   ├── artifacts/  # Artifact system: CAS store, IDs, manifests.
│       │   │   ├── __init__.py
│       │   │   ├── environment.py  # Environment manifests for reproducibility.
│       │   │   ├── graph.py  # Artifact dependency graph tracking.
│       │   │   ├── ids.py  # SHA-256 content-addressed identifiers.
│       │   │   ├── manifest.py  # Artifact manifest models.
│       │   │   ├── registry.py  # Registry bundle artifacts.
│       │   │   ├── signing.py  # Cryptographic artifact signing.
│       │   │   └── store.py  # Filesystem-backed CAS store.
│       │   ├── audit/  # Audit trail assembly, export, verification.
│       │   │   ├── __init__.py
│       │   │   ├── assembler.py  # Audit bundle assembly.
│       │   │   ├── instructions_template.md  # Template for audit instructions.
│       │   │   ├── models.py  # Audit data models.
│       │   │   ├── prov_json.py  # PROV-JSON export for audit.
│       │   │   ├── report.py  # Human-readable audit reports.
│       │   │   ├── safe_tar.py  # Safe tar archive creation.
│       │   │   ├── standalone_verifier_template.py  # Standalone verifier script.
│       │   │   └── verifier.py  # Audit bundle verification.
│       │   ├── canon/  # Canonical JSON serialization.
│       │   │   ├── __init__.py
│       │   │   └── canon_json.py  # Deterministic JSON for hashing.
│       │   ├── compiler/  # Compilation reporting.
│       │   │   ├── __init__.py
│       │   │   └── report.py  # Compile report models.
│       │   ├── components/  # Component system for extensible modules.
│       │   │   ├── __init__.py
│       │   │   ├── capabilities.py  # Component capability declarations.
│       │   │   ├── cli.py  # Component CLI (polisyos command).
│       │   │   ├── compliance.py  # Component compliance checks.
│       │   │   ├── discovery.py  # Entry-point component discovery.
│       │   │   ├── ids.py  # Component identity and semver.
│       │   │   ├── metadata.py  # Component metadata models.
│       │   │   ├── protocols.py  # Component protocol definitions.
│       │   │   └── registry.py  # Component registry.
│       │   ├── contracts/  # Typed inter-module contracts.
│       │   │   ├── __init__.py
│       │   │   ├── backtest.py  # Backtesting contracts.
│       │   │   ├── causal.py  # Causal inference contracts.
│       │   │   ├── compiler.py  # Compiler typed references.
│       │   │   ├── distributional.py  # Distributional analysis contracts.
│       │   │   ├── fabric.py  # Fabric evidence/bounds contracts.
│       │   │   ├── foundry.py  # Foundry ProgramGraph/ExecPlan contracts.
│       │   │   ├── hte.py  # Heterogeneous treatment effects contracts.
│       │   │   ├── legal.py  # NormPack/NormRule/RuleBackend contracts.
│       │   │   ├── lex.py  # Lex layer contracts.
│       │   │   ├── scholar.py  # Scholar layer contracts.
│       │   │   ├── scientist.py  # Scientist critique/failure/timeline contracts.
│       │   │   ├── trinity.py  # Trinity ProblemFrame/PolicySpec/ModelSpec.
│       │   │   └── uncertainty.py  # Uncertainty envelope contracts.
│       │   ├── observability/  # OpenTelemetry tracing, metrics, logs.
│       │   │   ├── __init__.py
│       │   │   ├── config.py  # OTel configuration and resource attributes.
│       │   │   ├── decorators.py  # @traced / @traced_method decorators.
│       │   │   ├── determinism.py  # Determinism tracking.
│       │   │   ├── logs.py  # Structured logging with trace correlation.
│       │   │   ├── metrics.py  # Prometheus-compatible metrics registry.
│       │   │   ├── pricing.py  # Cost/pricing observability.
│       │   │   ├── propagation.py  # Trace context propagation.
│       │   │   └── tracer.py  # PolicyOSTracer singleton.
│       │   ├── registry/  # Registry bundle builder/loader.
│       │   │   ├── __init__.py
│       │   │   ├── builder.py  # Build registry bundles.
│       │   │   ├── builder_from_fragments.py  # Build from IR fragments.
│       │   │   └── loader.py  # Load registry bundles.
│       │   ├── run/  # Run context and manifest.
│       │   │   ├── __init__.py
│       │   │   ├── context.py  # RunContext for single execution.
│       │   │   └── manifest.py  # Run manifest serialization.
│       │   └── trace/  # Structured tracing records.
│       │       ├── __init__.py
│       │       ├── record.py  # TraceRecord model.
│       │       └── sink.py  # Trace sinks (JSONL).
│       ├── fabric/  # Unified Data Fabric: ingestion, catalog, evidence, quality, trust, UDF, connectors.
│       │   ├── __init__.py
│       │   ├── _connector_bridge.py  # Scientist→Fabric isolation (Law A).
│       │   ├── config.py  # Fabric configuration.
│       │   ├── connectors_ingestion.py  # Connector-based ingestion pipeline.
│       │   ├── demo_csv_ingestion.py  # CSV ingestion demo.
│       │   ├── evidence.py  # Evidence bundle models.
│       │   ├── fact_writer.py  # Immutable fact writer.
│       │   ├── fitness_report.py  # Data fitness reports.
│       │   ├── ingestion.py  # ETL pipeline (raw→staging→stores).
│       │   ├── manifest.py  # Dataset manifest models.
│       │   ├── quality.py  # Quality indicators and thresholds.
│       │   ├── registry.py  # UDF/function registry.
│       │   ├── segment_manifest.py  # Segment manifest models.
│       │   ├── trust.py  # Trust policies and uncertainty.
│       │   ├── trust_adapter.py  # Trust→uncertainty bridge adapter.
│       │   ├── world_query.py  # World model query interface.
│       │   ├── catalog/  # Metric-level data contracts.
│       │   │   ├── __init__.py
│       │   │   ├── binding.py  # Hash-locked metric bindings.
│       │   │   ├── contract.py  # DataContract models.
│       │   │   ├── registry.py  # DataContractRegistry.
│       │   │   ├── search.py  # Metric search/disambiguation.
│       │   │   └── validate.py  # Contract collection validation.
│       │   ├── claims/  # Claims management and verification.
│       │   │   ├── __init__.py
│       │   │   ├── canonicalize.py  # Claim canonicalization.
│       │   │   ├── citations.py  # Citation tracking.
│       │   │   ├── errors.py  # Claims error types.
│       │   │   ├── extraction.py  # Claim extraction.
│       │   │   ├── extractor_registry.py  # Extractor plugin registry.
│       │   │   ├── normalize.py  # Claim normalization.
│       │   │   ├── persist.py  # Claim persistence.
│       │   │   ├── types.py  # Claim type definitions.
│       │   │   ├── backends/  # Claim extraction backends.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── explicit_lines_v1.py  # Explicit lines extractor.
│       │   │   │   ├── lex_norm_regex_v1.py  # Lex norm regex extractor.
│       │   │   │   └── regex_numeric_v1.py  # Regex numeric extractor.
│       │   │   └── conflicts/  # Conflict detection and resolution.
│       │   │       ├── __init__.py
│       │   │       ├── detect.py  # Conflict detection.
│       │   │       ├── key.py  # Conflict key generation.
│       │   │       ├── policies.py  # Resolution policies.
│       │   │       ├── resolve.py  # Conflict resolution.
│       │   │       ├── score_claims.py  # Claim scoring.
│       │   │       ├── score_docs.py  # Document scoring.
│       │   │       ├── types.py  # Conflict type definitions.
│       │   │       └── uncertainty_adapter.py  # Uncertainty integration.
│       │   ├── connectors/  # External data source connectors.
│       │   │   ├── __init__.py
│       │   │   ├── base.py  # BaseConnector protocol.
│       │   │   ├── capabilities.py  # Protocol compliance checking.
│       │   │   ├── discovery.py  # Connector discovery.
│       │   │   ├── pool.py  # Connection pooling.
│       │   │   ├── registry.py  # Connector registry.
│       │   │   ├── validation.py  # Input validation.
│       │   │   ├── cache/  # CAS-based caching.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── invalidation.py  # Cache invalidation.
│       │   │   │   ├── policy.py  # TTL policies.
│       │   │   │   ├── prefetch.py  # Prefetching.
│       │   │   │   ├── proxy.py  # Caching proxy layer.
│       │   │   │   └── store.py  # CAS cache store.
│       │   │   ├── contracts/  # Schema evolution.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── evolution.py  # Contract evolution.
│       │   │   │   ├── inference.py  # Schema inference.
│       │   │   │   ├── registry.py  # Contract registry.
│       │   │   │   └── schema.py  # Schema management.
│       │   │   ├── federation/  # Cross-connector federation.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── composer.py  # Federation composition.
│       │   │   │   ├── evidence_aggregation.py  # Evidence aggregation.
│       │   │   │   ├── planner.py  # Federation query planning.
│       │   │   │   ├── ranker.py  # Source ranking.
│       │   │   │   ├── resolver.py  # Conflict resolution.
│       │   │   │   └── types.py  # Federation types.
│       │   │   ├── quality/  # Data quality assessment.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── completeness.py  # Completeness validation.
│       │   │   │   ├── consistency.py  # Consistency checks.
│       │   │   │   ├── freshness.py  # Freshness assessment.
│       │   │   │   ├── report.py  # Quality reports.
│       │   │   │   └── validator.py  # Quality validation.
│       │   │   ├── reference/  # Reference connector implementations.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── rest_json.py  # REST/JSON connector.
│       │   │   │   ├── sdmx.py  # SDMX connector.
│       │   │   │   └── static_csv.py  # Static CSV connector.
│       │   │   ├── resilience/  # Resilience patterns.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── circuit_breaker.py  # Circuit breaker.
│       │   │   │   ├── fallback.py  # Fallback handling.
│       │   │   │   ├── rate_limiter.py  # Rate limiting.
│       │   │   │   └── retry.py  # Retry logic.
│       │   │   ├── testing/  # Connector test infrastructure.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── contracts.py  # Test contracts.
│       │   │   │   ├── fixtures.py  # Test fixtures.
│       │   │   │   ├── harness.py  # ConnectorTestHarness.
│       │   │   │   └── simulator.py  # APISimulator.
│       │   │   ├── transform/  # Data transformation pipeline.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── aggregator.py  # Data aggregation.
│       │   │   │   ├── filter.py  # Data filtering.
│       │   │   │   ├── harmonizer.py  # Data harmonization.
│       │   │   │   ├── imputer.py  # Missing data imputation.
│       │   │   │   ├── normalizer.py  # Data normalization.
│       │   │   │   ├── pipeline.py  # Pipeline orchestration.
│       │   │   │   └── validator.py  # Transformation validation.
│       │   │   └── types/  # Type system.
│       │   │       ├── __init__.py
│       │   │       ├── coercion.py  # Type coercion.
│       │   │       ├── connector_types.py  # Connector types.
│       │   │       ├── dimensions.py  # Dimensional data types.
│       │   │       ├── temporal.py  # Temporal types.
│       │   │       └── units.py  # Unit conversion.
│       │   ├── docs/  # Document processing pipeline.
│       │   │   ├── __init__.py
│       │   │   ├── chunking.py  # Document chunking.
│       │   │   ├── errors.py  # Document errors.
│       │   │   ├── ingestion.py  # Document ingestion.
│       │   │   ├── normalize.py  # Text normalization.
│       │   │   ├── structure.py  # Structure extraction.
│       │   │   ├── types.py  # Document types.
│       │   │   └── backends/  # Format backends.
│       │   │       ├── __init__.py
│       │   │       ├── pdf.py  # PDF processing.
│       │   │       ├── text_html.py  # HTML processing.
│       │   │       └── text_plain.py  # Plain text processing.
│       │   ├── io/  # Storage backends.
│       │   │   ├── __init__.py
│       │   │   └── db.py  # DuckDB backend.
│       │   ├── provenance/  # W3C PROV-O provenance.
│       │   │   ├── __init__.py
│       │   │   ├── core.py  # PROV-O graph models.
│       │   │   └── export_provo.py  # PROV-O export.
│       │   └── world/  # World model and state management.
│       │       ├── __init__.py
│       │       ├── materialize/  # World materialization.
│       │       │   ├── __init__.py
│       │       │   ├── duckdb.py  # DuckDB materializer.
│       │       │   ├── errors.py  # Materialization errors.
│       │       │   ├── kuzu.py  # Kùzu materializer.
│       │       │   ├── projections.py  # Projection definitions.
│       │       │   ├── rules.py  # Materialization rules.
│       │       │   ├── sql.py  # SQL generation.
│       │       │   └── staging.py  # Staging pipeline.
│       │       └── store/  # World persistence.
│       │           ├── __init__.py
│       │           ├── emit.py  # Event emission.
│       │           ├── errors.py  # Store errors.
│       │           ├── ids.py  # World entity IDs.
│       │           ├── persist.py  # Persistence layer.
│       │           ├── provenance.py  # Store provenance.
│       │           ├── segments.py  # Segment management.
│       │           └── validate.py  # Store validation.
│       ├── foundry/  # JAX execution core: compilation, simulation, calibration, uncertainty.
│       │   ├── __init__.py
│       │   ├── agent_metrics.py  # Agent-level metrics collection.
│       │   ├── agents.py  # Agent type definitions.
│       │   ├── base.py  # Foundry base abstractions.
│       │   ├── conflict_checker.py  # Static slot-write conflict detection.
│       │   ├── constraints_engine.py  # Constraint evaluation engine.
│       │   ├── cost_model.py  # Heuristic cost model.
│       │   ├── executor.py  # JAX step/scan/batch executor.
│       │   ├── fiscal.py  # Fiscal policy mechanisms.
│       │   ├── labor.py  # Labor market mechanisms.
│       │   ├── layout.py  # State layout management.
│       │   ├── loss.py  # Loss function utilities.
│       │   ├── merge_engine.py  # CRDT-inspired merge semantics.
│       │   ├── patch_vm.py  # Patch-based virtual machine.
│       │   ├── profiles.py  # Execution profiles.
│       │   ├── queue.py  # Execution queue.
│       │   ├── registry.py  # Foundry component registry.
│       │   ├── specs.py  # Specification models.
│       │   ├── trace.py  # Foundry tracing.
│       │   ├── treasury.py  # RNG/seed treasury.
│       │   ├── types.py  # Core Foundry types.
│       │   ├── agent_sim/  # Agent-based simulation subsystem.
│       │   │   ├── __init__.py
│       │   │   ├── actor_critic.py  # Actor-critic RL.
│       │   │   ├── analysis.py  # Simulation analysis.
│       │   │   ├── artifact.py  # Simulation artifacts.
│       │   │   ├── credit_assignment.py  # Credit assignment.
│       │   │   ├── dashboard.py  # Simulation dashboard.
│       │   │   ├── demographics.py  # Demographic modeling.
│       │   │   ├── distribution_executor.py  # Distribution execution.
│       │   │   ├── distribution_mechanisms.py  # Distribution mechanisms.
│       │   │   ├── distributions.py  # Distribution definitions.
│       │   │   ├── evolution.py  # Evolutionary dynamics.
│       │   │   ├── executor.py  # Simulation executor.
│       │   │   ├── experiment.py  # Experiment management.
│       │   │   ├── government_policy.py  # Government policy rules.
│       │   │   ├── graph_executor.py  # Graph-based execution.
│       │   │   ├── graph_mechanisms.py  # Graph mechanisms.
│       │   │   ├── graph_observations.py  # Graph observations.
│       │   │   ├── graphs.py  # Graph structures.
│       │   │   ├── jit_training.py  # JIT-compiled training.
│       │   │   ├── mechanism.py  # Single mechanism abstraction.
│       │   │   ├── mechanisms.py  # Mechanism collection.
│       │   │   ├── metrics.py  # Simulation metrics.
│       │   │   ├── modes.py  # Simulation modes.
│       │   │   ├── mpc.py  # Model predictive control.
│       │   │   ├── policy.py  # Policy definitions.
│       │   │   ├── population.py  # Population modeling.
│       │   │   ├── population_executor.py  # Population executor.
│       │   │   ├── population_mechanisms.py  # Population mechanisms.
│       │   │   ├── prng.py  # PRNG management.
│       │   │   ├── rewards.py  # Reward functions.
│       │   │   ├── rl.py  # Reinforcement learning.
│       │   │   ├── state.py  # Simulation state.
│       │   │   ├── temporal.py  # Temporal dynamics.
│       │   │   ├── temporal_executor.py  # Temporal executor.
│       │   │   ├── temporal_mechanisms.py  # Temporal mechanisms.
│       │   │   ├── training.py  # Training loops.
│       │   │   ├── vfi.py  # Value function iteration.
│       │   │   └── visualization.py  # Simulation visualization.
│       │   ├── analysis/  # Post-simulation analysis.
│       │   │   ├── __init__.py
│       │   │   └── distributional.py  # Distributional impact analysis.
│       │   ├── calibration/  # Gradient-based parameter calibration.
│       │   │   ├── __init__.py
│       │   │   ├── bijectors.py  # Parameter constraint bijectors.
│       │   │   ├── calibrator.py  # Calibrator class.
│       │   │   ├── loss.py  # Calibration loss functions.
│       │   │   ├── preflight.py  # Pre-calibration validation.
│       │   │   ├── pure_executor.py  # JAX pure executor.
│       │   │   ├── report.py  # Calibration reports.
│       │   │   └── uncertainty_adapter.py  # Uncertainty propagation adapter.
│       │   ├── compile/  # Foundry compilation.
│       │   │   ├── __init__.py
│       │   │   ├── _graph.py  # Internal graph representation.
│       │   │   ├── api.py  # Compilation public API.
│       │   │   └── trinity_compiler.py  # Trinity→Foundry compiler.
│       │   ├── domain/  # Economic domain schemas.
│       │   │   ├── __init__.py
│       │   │   ├── schema.py  # Domain schema definitions.
│       │   │   └── state.py  # Domain state types.
│       │   ├── execute/  # Execution orchestration.
│       │   │   ├── __init__.py
│       │   │   └── api.py  # Execution public API.
│       │   ├── methods/  # Method implementations and catalog.
│       │   │   ├── __init__.py
│       │   │   ├── artifacts.py  # Method artifact management.
│       │   │   ├── base.py  # Base method protocol.
│       │   │   ├── compiler.py  # Method compiler.
│       │   │   ├── components_bridge.py  # Component system bridge.
│       │   │   ├── composer.py  # Method composition.
│       │   │   ├── discovery.py  # Method discovery.
│       │   │   ├── exceptions.py  # Method exceptions.
│       │   │   ├── linker.py  # Method linker.
│       │   │   ├── registry.py  # Method registry.
│       │   │   ├── resolution.py  # Method resolution.
│       │   │   ├── specialization.py  # Method specialization.
│       │   │   ├── backends/  # Execution backends.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── adapters.py  # Backend adapters.
│       │   │   │   ├── chain_executor.py  # Chain execution.
│       │   │   │   ├── dispatch.py  # Backend dispatch.
│       │   │   │   ├── jax_runner.py  # JAX runner.
│       │   │   │   ├── numpy_runner.py  # NumPy runner.
│       │   │   │   ├── protocol.py  # Backend protocol.
│       │   │   │   └── solver_runner.py  # Solver runner (OR-Tools/PuLP).
│       │   │   ├── catalog/  # Built-in method catalog.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── causal/  # Causal inference methods.
│       │   │   │   │   ├── __init__.py
│       │   │   │   │   ├── _common.py  # Shared causal utilities.
│       │   │   │   │   ├── _econml_adapter.py  # EconML integration.
│       │   │   │   │   ├── _registry_boot.py  # Auto-registration.
│       │   │   │   │   ├── cate.py  # CATE estimation.
│       │   │   │   │   ├── did.py  # Difference-in-differences.
│       │   │   │   │   ├── dml.py  # Double machine learning.
│       │   │   │   │   ├── meta_learners.py  # Meta-learner methods.
│       │   │   │   │   ├── policy_learning.py  # Policy learning.
│       │   │   │   │   ├── protocols.py  # Causal method protocols.
│       │   │   │   │   ├── rdd.py  # Regression discontinuity.
│       │   │   │   │   ├── scm.py  # Structural causal models.
│       │   │   │   │   └── structural_time_series.py  # Structural time series.
│       │   │   │   ├── econometrics/  # Econometric methods.
│       │   │   │   │   ├── __init__.py
│       │   │   │   │   ├── _registry_boot.py  # Auto-registration.
│       │   │   │   │   ├── iv.py  # Instrumental variables.
│       │   │   │   │   ├── panel.py  # Panel data models.
│       │   │   │   │   ├── protocols.py  # Econometric protocols.
│       │   │   │   │   └── timeseries.py  # Time series models.
│       │   │   │   ├── microsim/  # Microsimulation methods.
│       │   │   │   │   └── __init__.py
│       │   │   │   └── optimization/  # Optimization methods.
│       │   │   │       └── __init__.py
│       │   │   ├── testing/  # Method testing infrastructure.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── fixtures.py  # Test fixtures.
│       │   │   │   ├── golden.py  # Golden-file testing.
│       │   │   │   ├── jax_suite.py  # JAX backend test suite.
│       │   │   │   ├── numpy_suite.py  # NumPy backend test suite.
│       │   │   │   ├── solver_suite.py  # Solver backend test suite.
│       │   │   │   └── suite.py  # General test suite.
│       │   │   └── types/  # Method type system.
│       │   │       ├── __init__.py
│       │   │       ├── checker.py  # Type checker.
│       │   │       └── units.py  # Unit types.
│       │   ├── plugins/  # Plugin system.
│       │   │   ├── __init__.py
│       │   │   ├── api.py  # Plugin public API.
│       │   │   ├── cli.py  # Plugin CLI (polisy command).
│       │   │   ├── composite.py  # Composite plugins.
│       │   │   ├── core.py  # Plugin core.
│       │   │   ├── discovery.py  # Plugin discovery.
│       │   │   └── economics/  # Economics plugin.
│       │   │       ├── __init__.py
│       │   │       ├── mechanisms.py  # Economic mechanisms.
│       │   │       ├── objectives.py  # Economic objectives.
│       │   │       ├── plugin.py  # Plugin definition.
│       │   │       ├── rewards.py  # Economic rewards.
│       │   │       └── state.py  # Economic state.
│       │   ├── runtime/  # Runtime utilities.
│       │   │   ├── __init__.py
│       │   │   ├── fingerprint.py  # Environment fingerprinting.
│       │   │   └── nan_guard.py  # NaN/Inf detection.
│       │   └── uncertainty/  # Uncertainty propagation framework.
│       │       ├── __init__.py
│       │       ├── aggregator.py  # Uncertainty aggregation.
│       │       ├── analytical.py  # Analytical propagation.
│       │       ├── config.py  # Uncertainty configuration.
│       │       ├── covariance.py  # Covariance tracking.
│       │       ├── delta.py  # Delta method propagation.
│       │       ├── dispatcher.py  # Method dispatch.
│       │       ├── monte_carlo.py  # Monte Carlo propagation.
│       │       └── protocol.py  # Uncertainty protocol.
│       ├── ir/  # Canonical IR: TrinityBundle, kernel registries, loaders, validation.
│       │   ├── __init__.py
│       │   ├── applicability.py  # Policy applicability checks.
│       │   ├── backtest.py  # Backtesting IR models.
│       │   ├── calibration.py  # Calibration IR models.
│       │   ├── canon.py  # Canonical representations.
│       │   ├── causal.py  # Causal effect IR models.
│       │   ├── citations.py  # Citation tracking models.
│       │   ├── connectors.py  # Connector IR integration.
│       │   ├── data_views.py  # Data view definitions.
│       │   ├── distributional.py  # Distributional analysis IR.
│       │   ├── fact_log.py  # Fact log IR models.
│       │   ├── gate.py  # Gate context/decision IR models.
│       │   ├── hte.py  # HTE result IR models.
│       │   ├── loaders.py  # Universal policy loader.
│       │   ├── migration_report.py  # Migration report models.
│       │   ├── model_spec.py  # ModelSpec (data snapshots, assumptions).
│       │   ├── norm_pack.py  # NormPack/NormRule contracts.
│       │   ├── policy_spec.py  # PolicySpec (interventions).
│       │   ├── predicate.py  # Predicate expressions.
│       │   ├── problem_frame.py  # ProblemFrame (goals/KPIs).
│       │   ├── queries.py  # IR query models.
│       │   ├── refs.py  # IR reference types.
│       │   ├── registry_fragments.py  # IR registry fragments.
│       │   ├── schedule.py  # Schedule models.
│       │   ├── selector_expr.py  # Selector expressions.
│       │   ├── trinity.py  # Trinity artifacts and bundle.
│       │   ├── types.py  # IR type definitions.
│       │   ├── uncertainty.py  # Uncertainty envelope IR.
│       │   ├── units.py  # Unit system models.
│       │   ├── validation.py  # IR validation.
│       │   ├── kernel/  # Kernel registries: mechanisms, slots, units, rules.
│       │   │   ├── __init__.py
│       │   │   ├── base.py  # Kernel base types.
│       │   │   ├── constraints.py  # Kernel constraints.
│       │   │   ├── mechanisms.py  # Mechanism registry.
│       │   │   ├── merge_rules.py  # Merge rule registry.
│       │   │   ├── metrics.py  # Kernel metrics.
│       │   │   ├── numbers.py  # Numeric type registry.
│       │   │   ├── selector_fields.py  # Selector field registry.
│       │   │   ├── slots.py  # Slot registry.
│       │   │   ├── time_semantics.py  # Time semantics registry.
│       │   │   ├── trust.py  # Trust level registry.
│       │   │   ├── units.py  # Unit registry.
│       │   │   └── values.py  # Value type registry.
│       │   ├── linker/  # IR linking and dependency resolution.
│       │   │   ├── __init__.py
│       │   │   ├── link_trinity.py  # Trinity linking.
│       │   │   ├── reports.py  # Linker reports.
│       │   │   └── types.py  # Linker types.
│       │   ├── migrations/  # IR format migrations.
│       │   │   ├── __init__.py
│       │   │   ├── base.py  # Migration base.
│       │   │   ├── policy_ir.py  # Policy IR migrations.
│       │   │   └── trinity_migration.py  # Trinity migration.
│       │   ├── trinity/  # Trinity artifact processing.
│       │   │   ├── __init__.py
│       │   │   └── loaders.py  # Trinity loaders.
│       │   └── world/  # World model IR.
│       │       ├── __init__.py
│       │       ├── abi.py  # World ABI definitions.
│       │       ├── claim.py  # Claim models.
│       │       ├── conflict.py  # Conflict models.
│       │       ├── doc.py  # Document models.
│       │       ├── event.py  # Event models.
│       │       ├── ids.py  # World entity IDs.
│       │       ├── predicates.py  # World predicates.
│       │       ├── quality.py  # Quality models.
│       │       └── trust.py  # Trust models.
│       ├── lex/  # Legal corpus and norm evaluation.
│       │   ├── __init__.py
│       │   ├── api.py  # Lex public API.
│       │   ├── errors.py  # Lex error types.
│       │   ├── types.py  # Lex type definitions.
│       │   ├── corpus/  # Legal document corpus.
│       │   │   ├── __init__.py
│       │   │   ├── index.py  # Corpus indexing.
│       │   │   ├── ingest.py  # Corpus ingestion.
│       │   │   ├── structure.py  # Document structure.
│       │   │   └── versioning.py  # Corpus versioning.
│       │   ├── legal_evaluation/  # Legal rule evaluation.
│       │   │   ├── __init__.py
│       │   │   ├── change_proposals.py  # Legal change proposals.
│       │   │   ├── context_builder.py  # Evaluation context.
│       │   │   ├── evaluate.py  # Rule evaluation.
│       │   │   ├── evaluator_registry.py  # Evaluator plugin registry.
│       │   │   └── backends/  # Evaluation backends.
│       │   │       ├── __init__.py
│       │   │       └── simple_v1.py  # Simple evaluator.
│       │   ├── normpack/  # Norm pack assembly.
│       │   │   ├── __init__.py
│       │   │   ├── applicability.py  # Norm applicability.
│       │   │   ├── assemble_pack.py  # Pack assembly.
│       │   │   ├── extract_norm_claims.py  # Norm claim extraction.
│       │   │   ├── policies.py  # Norm policies.
│       │   │   ├── provider_registry.py  # Provider registry.
│       │   │   └── select_sources.py  # Source selection.
│       │   └── simulator/  # Lex regulatory change simulator.
│       │       ├── __init__.py
│       │       ├── cli.py  # Simulator CLI.
│       │       ├── diff.py  # Norm diff computation.
│       │       ├── engine.py  # Simulation engine.
│       │       ├── mutator.py  # Norm mutation.
│       │       └── report.py  # Simulation reports.
│       ├── packs/  # Domain-specific policy packs.
│       │   ├── __init__.py
│       │   ├── econ/  # Economic policy pack.
│       │   │   ├── __init__.py
│       │   │   ├── components.py  # Economic components.
│       │   │   └── ir_fragments.py  # Economic IR fragments.
│       │   └── roads/  # Road infrastructure pack.
│       │       ├── __init__.py
│       │       ├── components.py  # Road components.
│       │       ├── foundry_methods.py  # Road simulation methods.
│       │       ├── ir_fragments.py  # Road IR fragments.
│       │       ├── lex_evaluators.py  # Road legal evaluators.
│       │       ├── norms_provider.py  # Road norm provider.
│       │       └── scholar_extractors.py  # Road claim extractors.
│       ├── runtime/  # Run lifecycle and manifests.
│       │   ├── __init__.py
│       │   ├── api.py  # Runtime lifecycle API.
│       │   ├── manifest.py  # Portable run manifests.
│       │   └── replay.py  # Run replay infrastructure.
│       ├── scholar/  # Knowledge discovery layer.
│       │   ├── __init__.py
│       │   ├── api.py  # Scholar public API.
│       │   ├── errors.py  # Scholar errors.
│       │   ├── policies.py  # Discovery policies.
│       │   ├── types.py  # Scholar type definitions.
│       │   ├── discover/  # Knowledge discovery.
│       │   │   ├── __init__.py
│       │   │   ├── http_fetch.py  # HTTP-based discovery.
│       │   │   ├── local_files.py  # Local file discovery.
│       │   │   └── manual.py  # Manual entry.
│       │   └── orchestrator/  # Discovery orchestration.
│       │       ├── __init__.py
│       │       ├── bundle.py  # Knowledge bundle assembly.
│       │       └── enrich.py  # Knowledge enrichment.
│       └── scientist/  # Orchestration: agents, workflows, governance, search.
│           ├── __init__.py
│           ├── foundry.py  # Foundry integration bridge.
│           ├── publisher.py  # Result publishing.
│           ├── replay_backend.py  # Replay backend for re-execution.
│           ├── agent/  # Hierarchical agent system.
│           │   ├── __init__.py
│           │   ├── base.py  # Base agent class.
│           │   ├── critic.py  # Critic agent.
│           │   ├── drafter.py  # Drafter agent.
│           │   ├── failure_card.py  # Failure card generation.
│           │   ├── formalizer.py  # Formalizer agent.
│           │   ├── memory.py  # Agent memory.
│           │   ├── pi.py  # PI agent.
│           │   ├── prompt.py  # Prompt construction.
│           │   ├── prompts.py  # Prompt templates.
│           │   ├── protocols.py  # Agent protocols.
│           │   └── reflexion.py  # Self-healing reflexion loop.
│           ├── backtesting/  # Policy backtesting framework.
│           │   ├── __init__.py
│           │   ├── cli.py  # Backtesting CLI.
│           │   ├── evaluator.py  # Backtest evaluator.
│           │   ├── masking.py  # Temporal data masking.
│           │   ├── orchestrator.py  # Backtest orchestrator.
│           │   ├── plan.py  # Backtest plan generation.
│           │   └── trust_scorer.py  # Trust-weighted scoring.
│           ├── compute/  # Compute backend abstraction.
│           │   ├── __init__.py
│           │   ├── job_spec.py  # Job specifications.
│           │   └── runner.py  # Job runner.
│           ├── doe/  # Design of Experiments.
│           │   ├── __init__.py
│           │   ├── analysis.py  # DOE analysis.
│           │   ├── designs.py  # Experimental designs.
│           │   ├── sampling.py  # Sampling strategies.
│           │   └── stress_report.py  # Stress test reports.
│           ├── engine/  # Workflow engine.
│           │   ├── __init__.py
│           │   ├── checkpoint.py  # Workflow checkpointing.
│           │   ├── context.py  # Execution context.
│           │   ├── errors.py  # Engine errors.
│           │   ├── executor.py  # Workflow executor.
│           │   ├── idempotency.py  # Idempotent execution.
│           │   ├── protocol.py  # Engine protocol.
│           │   ├── registry.py  # Node registry.
│           │   ├── state.py  # Workflow state.
│           │   ├── telemetry.py  # Engine telemetry.
│           │   ├── workflow_spec.py  # Workflow specification.
│           │   └── builtins/  # Built-in operations.
│           │       ├── __init__.py
│           │       ├── emit_artifact.py  # Artifact emission.
│           │       ├── noop.py  # No-op node.
│           │       └── set_state.py  # State setter.
│           ├── governance/  # Governance pipeline.
│           │   ├── __init__.py
│           │   ├── pipeline.py  # Pipeline orchestrator.
│           │   ├── postflight.py  # Post-execution validation.
│           │   ├── preflight.py  # Pre-execution validation.
│           │   ├── profiles.py  # Validation profiles (fast/mvp/strict).
│           │   ├── report.py  # Governance reports.
│           │   ├── telemetry.py  # Governance telemetry.
│           │   ├── legal/  # Legal compliance.
│           │   │   ├── __init__.py
│           │   │   ├── ast_policy.py  # AST allowlist policy.
│           │   │   └── backends/  # Legal rule backends.
│           │   │       ├── __init__.py
│           │   │       ├── base.py  # Backend base.
│           │   │       ├── expr_ast.py  # Safe AST interpreter.
│           │   │       └── stub.py  # Stub backend.
│           │   └── passes/  # Validation passes.
│           │       ├── __init__.py
│           │       ├── base.py  # Pass base class.
│           │       ├── budget_pass.py  # Budget checks.
│           │       ├── confidence_pass.py  # Confidence threshold checks.
│           │       ├── equity_pass.py  # Equity/fairness checks.
│           │       ├── legal_pass.py  # Legal compliance.
│           │       ├── privacy_pass.py  # Privacy checks.
│           │       ├── quality_gate_pass.py  # Quality gates.
│           │       ├── safety_pass.py  # Safety checks.
│           │       └── schema_pass.py  # Schema validation.
│           ├── kernel/  # Scientist kernel.
│           │   ├── __init__.py
│           │   ├── budgets.py  # Budget management.
│           │   ├── fsm.py  # Finite state machine.
│           │   ├── gate_protocol.py  # Human gate protocol.
│           │   ├── guards.py  # State transition guards.
│           │   └── human_gate.py  # Human-in-the-loop gate.
│           ├── llm/  # LLM integration.
│           │   ├── __init__.py
│           │   └── traced_client.py  # TracedLLMClient with OTel.
│           ├── nodes/  # Workflow node implementations.
│           │   ├── __init__.py
│           │   └── builtins/  # Built-in nodes.
│           │       ├── __init__.py
│           │       ├── errors.py  # Node errors.
│           │       ├── state_keys.py  # State key constants.
│           │       ├── compile/  # Compilation nodes.
│           │       │   ├── __init__.py
│           │       │   ├── compile_foundry.py  # Foundry compilation.
│           │       │   └── link_trinity.py  # Trinity linking.
│           │       ├── data/  # Data processing nodes.
│           │       │   ├── __init__.py
│           │       │   ├── build_data_snapshot.py  # Data snapshot.
│           │       │   └── enrich_knowledge.py  # Knowledge enrichment.
│           │       ├── decide/  # Decision nodes.
│           │       │   ├── __init__.py
│           │       │   └── build_decision_packet.py  # Decision packet.
│           │       ├── governance/  # Governance nodes.
│           │       │   ├── __init__.py
│           │       │   ├── legal_check.py  # Legal check node.
│           │       │   └── run_governance.py  # Governance node.
│           │       └── simulate/  # Simulation nodes.
│           │           ├── __init__.py
│           │           ├── propagate_uncertainty.py  # Uncertainty propagation.
│           │           ├── run_causal_evaluation.py  # Causal evaluation.
│           │           ├── run_distributional_analysis.py  # Distributional analysis.
│           │           └── run_simulation.py  # Simulation execution.
│           ├── orchestrator/  # High-level orchestration.
│           │   ├── __init__.py
│           │   └── decision_card.py  # Decision card generation.
│           ├── search/  # Search/optimization framework.
│           │   ├── __init__.py
│           │   ├── adversarial.py  # Adversarial search.
│           │   ├── controller.py  # SearchController.
│           │   ├── objective.py  # Objective functions.
│           │   ├── sensitivity_adapter.py  # Sensitivity analysis adapter.
│           │   ├── stages.py  # Two-stage evaluation.
│           │   ├── stopping.py  # Stopping criteria.
│           │   └── strategies/  # Search strategies.
│           │       ├── __init__.py
│           │       ├── _deps.py  # Optional dependency checks.
│           │       ├── acquisition.py  # Acquisition functions.
│           │       ├── adapter.py  # Strategy adapter.
│           │       ├── base.py  # Base strategy.
│           │       ├── bayesian.py  # Bayesian optimization.
│           │       ├── codec.py  # Space encoding/decoding.
│           │       ├── errors.py  # Strategy errors.
│           │       ├── grid.py  # Grid search.
│           │       ├── multi_fidelity.py  # Multi-fidelity optimization.
│           │       ├── multi_objective.py  # Multi-objective optimization.
│           │       ├── normalization.py  # Objective normalization.
│           │       ├── objective_adapter.py  # Objective adapter.
│           │       ├── random.py  # Random search.
│           │       ├── resource_arbiter.py  # Resource allocation.
│           │       ├── rl_wrapper.py  # RL strategy wrapper.
│           │       ├── runtime.py  # Runtime strategy utilities.
│           │       ├── space.py  # Search space definitions.
│           │       ├── surrogate.py  # Surrogate modeling.
│           │       └── types.py  # Strategy types.
│           ├── workflow/  # Workflow engines.
│           │   ├── __init__.py
│           │   ├── engine_base.py  # Engine base class.
│           │   ├── engine_langgraph.py  # LangGraph engine.
│           │   └── engine_simple.py  # Simple sequential engine.
│           └── workflows/  # Predefined workflows.
│               ├── __init__.py
│               ├── builder.py  # Workflow builder.
│               └── default.py  # Default workflow.
├── schemas/  # ABI schema registry and snapshots.
│   ├── __init__.py
│   ├── abi_models.py  # ABI model definitions for schema generation.
│   ├── README.md
│   └── snapshots/
│       ├── fabric/  # Fabric ABI snapshots.
│       │   ├── _manifest.json  # Fabric schema manifest.
│       │   ├── edge_kind.schema.json  # Edge kind enum.
│       │   └── node_kind.schema.json  # Node kind enum.
│       └── ir/  # IR model JSON Schema snapshots.
│           ├── _manifest.json  # IR schema manifest.
│           ├── backtest_report.schema.json  # Backtest report schema.
│           ├── calibration_config.schema.json  # Calibration config.
│           ├── causal_effect_report.schema.json  # Causal effect report.
│           ├── claim.schema.json  # Claim schema.
│           ├── conflict_resolution.schema.json  # Conflict resolution.
│           ├── conflict_set.schema.json  # Conflict set.
│           ├── conflict_set_resolution.schema.json  # Conflict set resolution.
│           ├── data_view_request.schema.json  # Data view request.
│           ├── distributional_report.schema.json  # Distributional report.
│           ├── doc_fragment.schema.json  # Document fragment.
│           ├── doc_meta.schema.json  # Document metadata.
│           ├── fact.schema.json  # Fact schema.
│           ├── fact_segment_manifest.schema.json  # Fact segment manifest.
│           ├── gate_context.schema.json  # Gate context.
│           ├── gate_decision.schema.json  # Gate decision.
│           ├── gate_event.schema.json  # Gate event.
│           ├── gate_request.schema.json  # Gate request.
│           ├── hte_result.schema.json  # HTE result.
│           ├── model_spec.schema.json  # ModelSpec.
│           ├── norm_pack.schema.json  # NormPack.
│           ├── norm_ref.schema.json  # Norm reference.
│           ├── norm_rule.schema.json  # NormRule.
│           ├── policy_recommendation.schema.json  # Policy recommendation.
│           ├── policy_spec.schema.json  # PolicySpec.
│           ├── problem_frame.schema.json  # ProblemFrame.
│           ├── prov_activity.schema.json  # Provenance activity.
│           ├── quality_report.schema.json  # Quality report.
│           ├── trinity_bundle.schema.json  # TrinityBundle.
│           ├── trust_assessment.schema.json  # Trust assessment.
│           ├── uncertainty_envelope.schema.json  # Uncertainty envelope.
│           └── world_event.schema.json  # World event.
├── ops/  # Operations: monitoring, observability, alerting.
│   ├── README.md
│   ├── docker-compose.observability.yml  # Observability stack.
│   ├── grafana/  # Grafana dashboards.
│   │   ├── README.md
│   │   ├── dashboards/
│   │   │   ├── executive-overview.json  # Executive cost/performance.
│   │   │   ├── foundry-hpc.json  # HPC simulation dashboard.
│   │   │   ├── scientist-agents.json  # Agent workflow dashboard.
│   │   │   └── slo-overview.json  # SLO tracking dashboard.
│   │   └── provisioning/
│   │       └── dashboards.yml  # Dashboard auto-provisioning.
│   └── prometheus/  # Prometheus configuration.
│       ├── README.md
│       ├── alerts.yml  # Alerting rules.
│       ├── prometheus.yml  # Scrape configuration.
│       ├── recording_rules.yml  # Metric pre-computation.
│       ├── slo_alerts.yml  # SLO alerting rules.
│       └── slo_recording_rules.yml  # SLO recording rules.
├── tests/  # Test suite.
│   ├── conftest.py  # Root fixtures.
│   ├── test_arch_import_gate.py  # Import boundary enforcement.
│   ├── test_components_bridge_phase19.py  # Component bridge tests.
│   ├── test_components_discovery_phase19.py  # Component discovery tests.
│   ├── test_components_id_semver_phase19.py  # Component ID/semver tests.
│   ├── test_packs_discovery_phase19.py  # Pack discovery tests.
│   ├── test_public_api_facades.py  # Public API facade tests.
│   ├── contract/  # Contract and schema tests.
│   │   ├── conftest.py
│   │   ├── test_abi_diff_tool.py  # ABI diff tool tests.
│   │   ├── test_applicability_contract.py  # Applicability contract tests.
│   │   ├── test_citations_contract.py  # Citations contract tests.
│   │   ├── test_fabric_gates.py  # Fabric gate contract tests.
│   │   ├── test_foundry_facade_contracts.py  # Foundry facade tests.
│   │   ├── test_gate_models.py  # Gate model tests.
│   │   ├── test_gate_protocol.py  # Gate protocol tests.
│   │   ├── test_golden_record_ids.py  # Golden record ID tests.
│   │   ├── test_ir_migrations.py  # IR migration tests.
│   │   ├── test_kernel_models.py  # Kernel model tests.
│   │   ├── test_run_experiment_slo.py  # Run experiment SLO tests.
│   │   ├── test_scientist_workflow_spec_contract.py  # Workflow spec tests.
│   │   ├── test_slo_metrics.py  # SLO metrics tests.
│   │   ├── test_trinity_contracts.py  # Trinity contract tests.
│   │   ├── test_trinity_linker_contract.py  # Trinity linker tests.
│   │   ├── test_trinity_migration.py  # Trinity migration tests.
│   │   └── test_world_abi_contract.py  # World ABI tests.
│   ├── core_phase0/  # Core infrastructure tests.
│   │   ├── conftest.py
│   │   ├── test_artifact_export_import.py  # Artifact export/import.
│   │   ├── test_artifact_graph.py  # Artifact graph tracking.
│   │   ├── test_artifact_store.py  # CAS store tests.
│   │   ├── test_audit_export_verify.py  # Audit export/verify.
│   │   ├── test_canon_json.py  # Canonical JSON tests.
│   │   ├── test_cli_phase13.py  # CLI tests.
│   │   ├── test_cli_resume.py  # CLI resume tests.
│   │   ├── test_cli_signing.py  # CLI signing tests.
│   │   ├── test_decorators.py  # @traced decorator tests.
│   │   ├── test_environment_manifest.py  # Environment manifest tests.
│   │   ├── test_logs.py  # Log-trace correlation tests.
│   │   ├── test_metrics.py  # Metrics registry tests.
│   │   ├── test_observability.py  # Observability workflow tests.
│   │   ├── test_propagation.py  # Trace propagation tests.
│   │   ├── test_registry_bundle.py  # Registry bundle tests.
│   │   ├── test_run_context.py  # Run context tests.
│   │   ├── test_signing.py  # Signing tests.
│   │   ├── test_store_signing.py  # Store signing tests.
│   │   └── test_tracer.py  # Tracer singleton tests.
│   ├── demos/  # Demo smoke tests.
│   │   └── run_laffer_demo.py  # Laffer demo.
│   ├── fabric/  # Fabric tests.
│   │   ├── test_claims_pipeline_phase13.py  # Claims pipeline tests.
│   │   ├── test_conflict_uncertainty_adapter.py  # Conflict uncertainty adapter.
│   │   ├── test_conflicts_phase14.py  # Conflict resolution tests.
│   │   ├── test_data_catalog.py  # Data catalog tests.
│   │   ├── test_docs_pipeline_phase12.py  # Docs pipeline tests.
│   │   ├── test_evidence_bundle.py  # Evidence bundle tests.
│   │   ├── test_legal_evaluation_phase18.py  # Legal evaluation tests.
│   │   ├── test_lex_corpus_phase16.py  # Lex corpus tests.
│   │   ├── test_normpack_phase17.py  # Normpack tests.
│   │   ├── test_provenance.py  # Provenance tests.
│   │   ├── test_quality_indicators.py  # Quality indicator tests.
│   │   ├── test_scholar_extractor_components_phase19.py  # Scholar extractor tests.
│   │   ├── test_scholar_mvp_phase15.py  # Scholar MVP tests.
│   │   ├── test_trust_adapter.py  # Trust adapter tests.
│   │   ├── test_trust_phase14.py  # Trust system tests.
│   │   ├── test_trust_two_pass.py  # Two-pass trust tests.
│   │   ├── test_world_kuzu_phase11.py  # Kùzu world tests.
│   │   ├── test_world_materialization_phase10.py  # Materialization tests.
│   │   ├── test_world_store_phase9.py  # World store tests.
│   │   └── connectors/  # Connector tests.
│   │       ├── __init__.py
│   │       ├── conftest.py
│   │       ├── test_cache_system.py  # Cache system tests.
│   │       ├── test_federation.py  # Federation tests.
│   │       ├── test_harness.py  # Test harness tests.
│   │       ├── test_integration.py  # Integration tests.
│   │       ├── test_protocol_compliance.py  # Protocol compliance.
│   │       ├── test_quality_system.py  # Quality system tests.
│   │       ├── test_registry.py  # Registry tests.
│   │       ├── test_resilience.py  # Resilience tests.
│   │       ├── test_schema_system.py  # Schema system tests.
│   │       ├── test_transform_pipeline.py  # Transform pipeline tests.
│   │       ├── test_type_system.py  # Type system tests.
│   │       └── reference/  # Reference connector tests.
│   │           ├── test_rest_json.py  # REST/JSON tests.
│   │           ├── test_sdmx.py  # SDMX tests.
│   │           └── test_static_csv.py  # Static CSV tests.
│   ├── foundry/  # Foundry tests.
│   │   ├── test_adaptive_agents.py  # Adaptive agent tests.
│   │   ├── test_agent_artifact.py  # Agent artifact tests.
│   │   ├── test_agent_simulation_step1.py  # Agent sim step 1.
│   │   ├── test_agent_simulation_step2.py  # Agent sim step 2.
│   │   ├── test_agent_simulation_step3.py  # Agent sim step 3.
│   │   ├── test_agent_simulation_step4.py  # Agent sim step 4.
│   │   ├── test_agent_simulation_step5.py  # Agent sim step 5.
│   │   ├── test_agent_simulation_step6.py  # Agent sim step 6.
│   │   ├── test_calibration_uncertainty_adapter.py  # Calibration uncertainty.
│   │   ├── test_calibrator_fidelity.py  # Calibrator fidelity tests.
│   │   ├── test_calibrator_mvp.py  # Calibrator MVP tests.
│   │   ├── test_compile_determinism.py  # Compile determinism.
│   │   ├── test_compile_facade.py  # Compile facade tests.
│   │   ├── test_conflict_detection.py  # Conflict detection tests.
│   │   ├── test_constraints_executor.py  # Constraints executor tests.
│   │   ├── test_cost_model.py  # Cost model tests.
│   │   ├── test_execute_facade_smoke.py  # Execute facade smoke.
│   │   ├── test_fiscal.py  # Fiscal tests.
│   │   ├── test_global_state.py  # Global state tests.
│   │   ├── test_gradients.py  # Gradient tests.
│   │   ├── test_health.py  # Health check tests.
│   │   ├── test_jit_compilation_tracker.py  # JIT tracker tests.
│   │   ├── test_jit_stability.py  # JIT stability tests.
│   │   ├── test_merge_determinism.py  # Merge determinism tests.
│   │   ├── test_nan_guard.py  # NaN guard tests.
│   │   ├── test_no_io_kernel.py  # No-IO kernel purity.
│   │   ├── test_patch_executor.py  # Patch executor tests.
│   │   ├── test_program_graph_ops.py  # Program graph ops tests.
│   │   ├── test_runtime_batch.py  # Runtime batch tests.
│   │   ├── test_uncertainty_propagation.py  # Uncertainty propagation.
│   │   ├── agent_sim/  # Agent sim tests.
│   │   │   └── test_monitoring.py  # Monitoring tests.
│   │   ├── analysis/  # Analysis tests.
│   │   │   └── test_distributional.py  # Distributional analysis tests.
│   │   ├── methods/  # Method tests.
│   │   │   ├── conftest.py
│   │   │   ├── test_artifacts.py  # Method artifact tests.
│   │   │   ├── test_base.py  # Base method tests.
│   │   │   ├── test_compiler.py  # Method compiler tests.
│   │   │   ├── test_composer.py  # Method composer tests.
│   │   │   ├── test_discovery.py  # Method discovery tests.
│   │   │   ├── test_linker.py  # Method linker tests.
│   │   │   ├── test_metadata_assumptions.py  # Metadata/assumptions tests.
│   │   │   ├── test_protocol.py  # Method protocol tests.
│   │   │   ├── test_registry.py  # Method registry tests.
│   │   │   ├── test_testing_infra.py  # Testing infra tests.
│   │   │   ├── test_types.py  # Method type tests.
│   │   │   ├── backends/
│   │   │   │   └── test_backends.py  # Backend tests.
│   │   │   └── catalog/
│   │   │       ├── causal/  # Causal method tests.
│   │   │       │   ├── test_did.py  # DID tests.
│   │   │       │   ├── test_hte_methods.py  # HTE method tests.
│   │   │       │   ├── test_protocols.py  # Causal protocol tests.
│   │   │       │   ├── test_rdd.py  # RDD tests.
│   │   │       │   ├── test_registration.py  # Registration tests.
│   │   │       │   ├── test_scm.py  # SCM tests.
│   │   │       │   └── test_structural_time_series.py  # STS tests.
│   │   │       └── econometrics/  # Econometric method tests.
│   │   │           ├── test_iv.py  # IV tests.
│   │   │           ├── test_panel.py  # Panel data tests.
│   │   │           ├── test_protocols.py  # Econometric protocol tests.
│   │   │           ├── test_registration.py  # Registration tests.
│   │   │           └── test_timeseries.py  # Time series tests.
│   │   └── plugins/  # Plugin tests.
│   │       └── test_plugin_system.py  # Plugin system tests.
│   ├── integration/  # Cross-module integration tests.
│   │   ├── test_calibration_udf.py  # Calibration+UDF integration.
│   │   ├── test_human_gate_audit.py  # Human gate+audit integration.
│   │   ├── test_workflow_llm.py  # Workflow+LLM integration.
│   │   └── test_workflow_smoke.py  # Workflow smoke tests.
│   ├── ir/  # IR tests.
│   │   ├── test_hte_backtest.py  # HTE+backtest IR tests.
│   │   ├── test_loaders.py  # Loader tests.
│   │   ├── test_queries_contracts.py  # Query contract tests.
│   │   ├── test_registry_fragments.py  # Registry fragment tests.
│   │   ├── test_registry_fragments_components_phase19.py  # Fragment component tests.
│   │   ├── test_trinity_loaders.py  # Trinity loader tests.
│   │   └── test_uncertainty.py  # Uncertainty IR tests.
│   ├── lex/  # Lex tests.
│   │   └── simulator/  # Lex simulator tests.
│   │       ├── test_diff.py  # Norm diff tests.
│   │       ├── test_engine.py  # Simulator engine tests.
│   │       └── test_mutator.py  # Norm mutator tests.
│   ├── performance/  # Performance tests.
│   │   └── test_overhead.py  # Observability overhead SLA.
│   ├── runtime/  # Runtime tests.
│   │   ├── test_replay_runtime.py  # Replay runtime tests.
│   │   └── test_runtime_manifest_paths.py  # Manifest path tests.
│   └── scientist/  # Scientist tests.
│       ├── conftest.py
│       ├── test_agent_protocols.py  # Agent protocol tests.
│       ├── test_backtesting.py  # Backtesting tests.
│       ├── test_causal_evaluation_node.py  # Causal evaluation node.
│       ├── test_checkpoint.py  # Checkpoint tests.
│       ├── test_compiler.py  # Compiler tests.
│       ├── test_decision_card.py  # Decision card tests.
│       ├── test_decision_card_uncertainty_render.py  # Uncertainty rendering.
│       ├── test_decision_packet_distributional_econometrics.py  # Distributional+econometrics.
│       ├── test_decision_packet_node_v3.py  # Decision packet v3.
│       ├── test_decision_packet_v2.py  # Decision packet v2.
│       ├── test_distributional_analysis_node.py  # Distributional analysis.
│       ├── test_engine_default_workflow_e1_7.py  # Default workflow tests.
│       ├── test_engine_executor_idempotency.py  # Idempotency tests.
│       ├── test_engine_executor_v0.py  # Executor v0 tests.
│       ├── test_engine_registry_v0.py  # Registry v0 tests.
│       ├── test_flow_nodes_legacy_shim_e1_7.py  # Legacy shim tests.
│       ├── test_idempotency.py  # Idempotency tests.
│       ├── test_instrumentation.py  # Instrumentation tests.
│       ├── test_multi_agent_workflow.py  # Multi-agent workflow.
│       ├── test_propagate_uncertainty_node.py  # Uncertainty propagation node.
│       ├── test_reflexion_loop.py  # Reflexion loop tests.
│       ├── test_replay_backend.py  # Replay backend tests.
│       ├── test_run_timeline.py  # Run timeline tests.
│       ├── compute/
│       │   └── test_runner_polyglot.py  # Polyglot runner tests.
│       ├── doe/
│       │   ├── test_sampling.py  # DOE sampling tests.
│       │   └── test_sensitivity_plan.py  # Sensitivity plan tests.
│       ├── governance/  # Governance tests.
│       │   ├── test_confidence_pass.py  # Confidence pass tests.
│       │   ├── test_equity_pass.py  # Equity pass tests.
│       │   ├── test_legal_pass.py  # Legal pass tests.
│       │   ├── test_norm_execution.py  # Norm execution tests.
│       │   └── test_validation_pipeline.py  # Validation pipeline tests.
│       ├── integration/  # Scientist integration tests.
│       │   ├── test_checkpoint_resume.py  # Checkpoint+resume tests.
│       │   └── test_workflow_tracing.py  # Workflow tracing tests.
│       └── search/  # Search tests.
│           ├── __init__.py
│           ├── conftest.py
│           ├── test_adversarial.py  # Adversarial search tests.
│           ├── test_search_loop.py  # Search loop tests.
│           └── strategies/  # Strategy tests.
│               ├── __init__.py
│               ├── conftest.py
│               ├── test_adapter.py  # Adapter tests.
│               ├── test_bayesian.py  # Bayesian tests.
│               ├── test_controller_batch.py  # Controller batch tests.
│               ├── test_multi_objective.py  # Multi-objective tests.
│               ├── test_random_grid.py  # Random/grid tests.
│               ├── test_resource_arbiter.py  # Resource arbiter tests.
│               └── test_space_codec.py  # Space codec tests.
├── tools/  # Developer tooling.
│   ├── README.md
│   ├── abi_diff.py  # ABI schema diff tool.
│   ├── capture_env.py  # Environment reproducibility manifest.
│   ├── check_perf_regression.py  # Performance regression checker.
│   ├── check_scientist_node_version_bump.py  # Node version bump check.
│   ├── check_state_reads.py  # State read pattern checker.
│   ├── gen_schema.py  # JSON Schema snapshot generator.
│   ├── lint_connectors.py  # Connector Law A/B linter.
│   ├── lint_foundry.py  # Foundry purity linter (Law B).
│   ├── lint_imports.py  # Architecture import-boundary linter (Law A).
│   ├── migrate.py  # Migration runner.
│   ├── run_mechanism_design.py  # Differentiable mechanism design demo.
│   ├── scan_fabric.py  # Fabric data contract scanner.
│   ├── visualize_provenance.py  # Provenance graph visualizer.
│   ├── benchmarks/  # Performance benchmarks.
│   │   ├── bench_domain.py  # Domain benchmark.
│   │   └── bench_simulation.py  # Simulation benchmark.
│   ├── connectors/  # Connector tools.
│   │   └── scaffold.py  # Connector scaffold generator.
│   ├── demos/  # Demo scripts.
│   │   ├── run_export_demo.py  # Export demo.
│   │   ├── run_ingest_demo.py  # Ingestion demo.
│   │   ├── run_laffer_demo.py  # Laffer curve demo.
│   │   ├── run_optimizer_demo.py  # Optimizer demo.
│   │   ├── run_udf_hybrid_demo.py  # UDF hybrid demo.
│   │   └── run_udf_query_demo.py  # UDF query demo.
│   └── diagnostics/  # Diagnostic scripts.
│       ├── check_perf_regression.py  # Perf regression check.
│       ├── check_setup.py  # Setup diagnostics.
│       ├── check_udf_perf.py  # UDF perf diagnostics.
│       └── generate_ir_schema.py  # IR schema generator.
├── data/  # Data workspace and reference datasets.
│   ├── README.md
│   ├── norms/  # Norm packs (YAML).
│   │   └── sample_norms.yaml  # Sample norm pack.
│   ├── raw/  # Raw input datasets.
│   │   ├── .gitkeep
│   │   ├── agents.csv  # Agent data.
│   │   ├── interactions.csv  # Interaction data.
│   │   └── macro.csv  # Macroeconomic data.
│   ├── staging/  # ETL intermediate outputs.
│   │   ├── .gitkeep
│   │   ├── agents.parquet  # Staged agent data.
│   │   ├── interactions.parquet  # Staged interactions.
│   │   └── macro.parquet  # Staged macro data.
│   └── curated/  # Curated datasets with manifests.
│       ├── .gitkeep
│       ├── agents.parquet  # Curated agent data.
│       ├── agents_manifest.json  # Agent data manifest.
│       ├── data_contracts.json  # Data contract definitions.
│       ├── entity_resolution_manifest.json  # Entity resolution manifest.
│       ├── interactions.parquet  # Curated interactions.
│       ├── interactions_manifest.json  # Interactions manifest.
│       ├── macro.parquet  # Curated macro data.
│       ├── macro_manifest.json  # Macro data manifest.
│       └── udf_schema.json  # UDF schema definitions.
├── pyproject.toml  # Project metadata, deps, tool config.
├── import_policy.toml  # Architecture import-boundary rules (Law A).
├── import_exceptions.toml  # Temporary import gate exceptions.
└── (root files)
    ├── architecture.md  # This document.
    ├── dashboard.py  # Streamlit dashboard entrypoint.
    ├── env_example.txt  # Environment variables template.
    ├── install.sh  # Bootstrap installer.
    ├── jax_bootstrap.py  # JAX environment defaults.
    ├── migrate.py  # Schema migration CLI.
    ├── run_experiment.py  # Scientist workflow CLI.
    ├── uv.lock  # Locked dependency graph.
    ├── Dockerfile.reproducible  # Reproducible container build.
    ├── .pre-commit-config.yaml  # Pre-commit hooks.
    └── .gitignore  # Git ignore rules.
```
