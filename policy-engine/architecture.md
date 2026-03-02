```
policy-engine/  # Project root (Policy Engine / PolisyOS).
├── src/  # Python sources and build metadata.
│   └── polisyos/  # Main Python package.
│       ├── __init__.py
│       ├── common/  # Shared utilities: config, logging, JAX env, migrations, serialization.
│       │   ├── __init__.py
│       │   ├── async_tools.py  # Sync/async bridging utilities.
│       │   ├── config.py  # Central pydantic-settings configuration.
│       │   ├── jax_env.py  # JAX environment defaults, macOS backend safety.
│       │   ├── logger.py  # Structured logging (Loguru) + OpenTelemetry correlation.
│       │   ├── serialization.py  # Shared serialization helpers (JSON, msgpack).
│       │   ├── timestamps.py  # UTC timestamp utilities and formatting.
│       │   └── migrations/  # Deterministic schema migrations.
│       │       ├── __init__.py
│       │       ├── base.py  # Migration framework primitives.
│       │       └── manifest.py  # Dataset manifest migrations.
│       ├── core/  # Infrastructure: CAS, contracts, tracing, registry, observability, security.
│       │   ├── __init__.py
│       │   ├── artifacts/  # Artifact system: CAS store, IDs, manifests, environment capture.
│       │   │   ├── __init__.py
│       │   │   ├── _env_capture.py  # Environment snapshot capture logic.
│       │   │   ├── _env_comparison.py  # Environment diff comparison.
│       │   │   ├── _env_models.py  # Environment data models.
│       │   │   ├── _env_utils.py  # Environment utility helpers.
│       │   │   ├── environment.py  # Environment manifests for reproducibility.
│       │   │   ├── environment_parts.py  # Decomposed environment manifest helpers.
│       │   │   ├── graph.py  # Artifact dependency graph tracking.
│       │   │   ├── ids.py  # SHA-256 content-addressed identifiers.
│       │   │   ├── manifest.py  # Artifact manifest models.
│       │   │   ├── registry.py  # Registry bundle artifacts.
│       │   │   ├── signing.py  # Cryptographic artifact signing.
│       │   │   └── store.py  # Filesystem-backed CAS store.
│       │   ├── audit/  # Audit trail assembly, export, verification.
│       │   │   ├── __init__.py
│       │   │   ├── _assembler_archive.py  # Archive creation for audit bundles.
│       │   │   ├── _assembler_core.py  # Core assembler logic.
│       │   │   ├── _assembler_errors.py  # Assembler error types.
│       │   │   ├── _assembler_provenance.py  # Provenance attachment for bundles.
│       │   │   ├── _assembler_slsa.py  # SLSA attestation integration.
│       │   │   ├── assembler.py  # Audit bundle assembly facade.
│       │   │   ├── instructions_template.md  # Template for audit instructions.
│       │   │   ├── models.py  # Audit data models.
│       │   │   ├── prov_json.py  # PROV-JSON export for audit.
│       │   │   ├── report.py  # Human-readable audit reports.
│       │   │   ├── safe_tar.py  # Safe tar archive creation.
│       │   │   ├── standalone_verifier_template.py  # Standalone verifier script.
│       │   │   └── verifier.py  # Audit bundle verification.
│       │   ├── backends/  # Pluggable computation backend dispatch.
│       │   │   ├── __init__.py
│       │   │   └── dispatcher.py  # Backend selection and dispatch logic.
│       │   ├── cache/  # In-process caching primitives.
│       │   │   ├── __init__.py
│       │   │   ├── lru.py  # LRU cache implementation.
│       │   │   ├── protocol.py  # Cache protocol definition.
│       │   │   └── ttl.py  # TTL-based cache with expiration.
│       │   ├── canon/  # Canonical JSON serialization.
│       │   │   ├── __init__.py
│       │   │   ├── canon_json.py  # Deterministic JSON for hashing.
│       │   │   └── hashing.py  # Content-hash computation utilities.
│       │   ├── compiler/  # Compilation reporting.
│       │   │   ├── __init__.py
│       │   │   └── report.py  # Compile report models.
│       │   ├── components/  # Component system for extensible modules.
│       │   │   ├── __init__.py
│       │   │   ├── _cli_audit.py  # CLI subcommand: audit operations.
│       │   │   ├── _cli_components.py  # CLI subcommand: component listing/info.
│       │   │   ├── _cli_crypto.py  # CLI subcommand: crypto/signing operations.
│       │   │   ├── _cli_lex.py  # CLI subcommand: lex operations.
│       │   │   ├── _cli_replay.py  # CLI subcommand: replay operations.
│       │   │   ├── _cli_scholar.py  # CLI subcommand: scholar operations.
│       │   │   ├── _cli_scientist.py  # CLI subcommand: scientist operations.
│       │   │   ├── bootstrap.py  # Component system bootstrap/initialization.
│       │   │   ├── capabilities.py  # Component capability declarations.
│       │   │   ├── cli.py  # Component CLI (polisyos command).
│       │   │   ├── cli_parts.py  # Shared CLI helpers and formatting.
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
│       │   │   ├── control.py  # Control Plane request/response DTOs.
│       │   │   ├── cursor.py  # Cursor-based pagination contracts.
│       │   │   ├── distributional.py  # Distributional analysis contracts.
│       │   │   ├── execution_plan.py  # Execution-plan contracts for unified LLM policy cycle.
│       │   │   ├── fabric.py  # Fabric evidence/bounds contracts.
│       │   │   ├── foundry.py  # Foundry ProgramGraph/ExecPlan contracts.
│       │   │   ├── hte.py  # Heterogeneous treatment effects contracts.
│       │   │   ├── lex.py  # Lex layer contracts.
│       │   │   ├── provenance.py  # Provenance tracking contracts.
│       │   │   ├── runtime.py  # Runtime lifecycle contracts.
│       │   │   ├── scholar.py  # Scholar layer contracts.
│       │   │   ├── scientist.py  # Scientist critique/failure/timeline contracts.
│       │   │   ├── trinity.py  # Trinity ProblemFrame/PolicySpec/ModelSpec.
│       │   │   └── uncertainty.py  # Uncertainty envelope contracts.
│       │   ├── discovery/  # Service and component discovery.
│       │   │   ├── __init__.py
│       │   │   ├── base.py  # Discovery protocol and base scanner.
│       │   │   └── orchestrator.py  # Discovery orchestration across sources.
│       │   ├── errors/  # Shared error hierarchy.
│       │   │   ├── __init__.py
│       │   │   └── base.py  # Base exception classes.
│       │   ├── evaluation/  # Scoring and evaluation framework.
│       │   │   ├── __init__.py
│       │   │   └── scoring.py  # Pluggable scoring functions.
│       │   ├── governance/  # Core governance logic (shared by scientist).
│       │   │   ├── __init__.py
│       │   │   ├── profiles.py  # Validation profiles (fast/mvp/strict).
│       │   │   ├── legal/  # Legal compliance.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── ast_policy.py  # AST allowlist policy.
│       │   │   │   └── backends/  # Legal rule backends.
│       │   │   │       ├── __init__.py
│       │   │   │       ├── base.py  # Backend base.
│       │   │   │       ├── expr_ast.py  # Safe AST interpreter.
│       │   │   │       └── stub.py  # Stub backend.
│       │   │   └── passes/  # Validation passes.
│       │   │       ├── __init__.py
│       │   │       ├── base.py  # Pass base class.
│       │   │       ├── legal_pass.py  # Legal compliance check.
│       │   │       └── safety_pass.py  # Safety validation check.
│       │   ├── llm/  # LLM client abstraction.
│       │   │   ├── __init__.py
│       │   │   ├── cost.py  # Token cost accounting.
│       │   │   ├── protocols.py  # LLM client protocol definitions.
│       │   │   ├── response.py  # Standardized LLM response models.
│       │   │   ├── retry.py  # LLM retry/backoff logic.
│       │   │   └── traced_client.py  # TracedLLMClient with OTel spans.
│       │   ├── observability/  # OpenTelemetry tracing, metrics, logs.
│       │   │   ├── __init__.py
│       │   │   ├── _metrics_helpers.py  # Internal metrics helper functions.
│       │   │   ├── _metrics_registry_base.py  # Base metrics registry implementation.
│       │   │   ├── config.py  # OTel configuration and resource attributes.
│       │   │   ├── decorators.py  # @traced / @traced_method decorators.
│       │   │   ├── determinism.py  # Determinism tracking.
│       │   │   ├── logs.py  # Structured logging with trace correlation.
│       │   │   ├── metrics.py  # Prometheus-compatible metrics registry.
│       │   │   ├── metrics_parts.py  # Decomposed metric registration helpers.
│       │   │   ├── pricing.py  # Cost/pricing observability.
│       │   │   ├── propagation.py  # Trace context propagation.
│       │   │   └── tracer.py  # PolicyOSTracer singleton.
│       │   ├── pipeline/  # Generic pipeline execution framework.
│       │   │   ├── __init__.py
│       │   │   ├── base.py  # Pipeline step protocol.
│       │   │   ├── dag.py  # DAG-based pipeline executor.
│       │   │   └── linear.py  # Linear pipeline executor.
│       │   ├── registry/  # Registry bundle builder/loader.
│       │   │   ├── __init__.py
│       │   │   ├── base.py  # Registry base protocol.
│       │   │   ├── builder.py  # Build registry bundles.
│       │   │   ├── builder_from_fragments.py  # Build from IR fragments.
│       │   │   ├── generic.py  # Generic typed registry.
│       │   │   └── loader.py  # Load registry bundles.
│       │   ├── resilience/  # Resilience patterns for core services.
│       │   │   ├── __init__.py
│       │   │   └── retry.py  # Retry with exponential backoff.
│       │   ├── run/  # Run context and manifest.
│       │   │   ├── __init__.py
│       │   │   ├── context.py  # RunContext for single execution.
│       │   │   └── manifest.py  # Run manifest serialization.
│       │   ├── security/  # Multi-tenant security, RBAC, TEE, SLSA.
│       │   │   ├── __init__.py
│       │   │   ├── access_scope.py  # Row/column access scope definitions.
│       │   │   ├── audit_models.py  # Security audit event models.
│       │   │   ├── audit_sink.py  # Tamper-evident audit log sink.
│       │   │   ├── audit_verifier.py  # Audit chain integrity verifier.
│       │   │   ├── authz.py  # Authorization engine (OPA integration).
│       │   │   ├── cell.py  # Cell-level isolation primitives.
│       │   │   ├── db_backend.py  # Database backend with RLS support.
│       │   │   ├── delegation.py  # Capability delegation protocol.
│       │   │   ├── exceptions.py  # Security exception types.
│       │   │   ├── identity.py  # SPIFFE/SPIRE identity management.
│       │   │   ├── registry.py  # Security component registry.
│       │   │   ├── router.py  # Multi-tenant request router.
│       │   │   ├── sbom.py  # Software bill of materials generation.
│       │   │   ├── settings.py  # Security configuration settings.
│       │   │   ├── tee.py  # Trusted Execution Environment support.
│       │   │   ├── tee_middleware.py  # TEE attestation middleware.
│       │   │   ├── tenant_context.py  # Tenant context propagation.
│       │   │   └── slsa/  # SLSA supply-chain security.
│       │   │       ├── __init__.py
│       │   │       ├── attestation.py  # SLSA attestation generation.
│       │   │       ├── config.py  # SLSA configuration.
│       │   │       ├── fulcio.py  # Fulcio certificate integration.
│       │   │       ├── models.py  # SLSA provenance models.
│       │   │       └── rekor.py  # Rekor transparency log integration.
│       │   └── trace/  # Structured tracing records.
│       │       ├── __init__.py
│       │       ├── record.py  # TraceRecord model.
│       │       └── sink.py  # Trace sinks (JSONL).
│       ├── fabric/  # Unified Data Fabric: ingestion, catalog, evidence, quality, trust, connectors.
│       │   ├── __init__.py
│       │   ├── _connector_bridge.py  # Scientist→Fabric isolation (Law A).
│       │   ├── config.py  # Fabric configuration.
│       │   ├── connectors_ingestion.py  # Connector-based ingestion pipeline.
│       │   ├── evidence.py  # Evidence bundle models.
│       │   ├── fact_writer.py  # Immutable fact writer.
│       │   ├── fitness_report.py  # Data fitness reports.
│       │   ├── ingestion.py  # ETL pipeline (raw→staging→stores).
│       │   ├── manifest.py  # Dataset manifest models.
│       │   ├── quality.py  # Quality indicators and thresholds.
│       │   ├── registry.py  # UDF/function registry.
│       │   ├── segment_manifest.py  # Segment manifest models.
│       │   ├── tabular.py  # Tabular data utilities.
│       │   ├── trust.py  # Trust policies and uncertainty.
│       │   ├── trust_adapter.py  # Trust→uncertainty bridge adapter.
│       │   ├── world_query.py  # World model query interface.
│       │   ├── catalog/  # Metric-level data contracts.
│       │   │   ├── __init__.py
│       │   │   ├── binding.py  # Hash-locked metric bindings.
│       │   │   ├── contract.py  # DataContract models.
│       │   │   ├── registry.py  # DataContractRegistry.
│       │   │   ├── resolver_fast_lane.py  # Deterministic FastLane resolver for metric→fetch plan.
│       │   │   ├── search.py  # Metric search/disambiguation.
│       │   │   ├── source_bindings.py  # Curated metric→source bindings for FastLane resolution.
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
│       │   │   ├── world_events.py  # World event generation from claims.
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
│       │   │   ├── _registry_errors.py  # Registry error types.
│       │   │   ├── _registry_lifecycle.py  # Registry lifecycle management.
│       │   │   ├── _registry_models.py  # Registry internal models.
│       │   │   ├── base.py  # BaseConnector protocol.
│       │   │   ├── capabilities.py  # Protocol compliance checking.
│       │   │   ├── components.py  # Connector component definitions.
│       │   │   ├── components_bridge.py  # Connector↔component system bridge.
│       │   │   ├── discovery.py  # Connector discovery.
│       │   │   ├── pool.py  # Connection pooling.
│       │   │   ├── registry.py  # Connector registry facade.
│       │   │   ├── registry_core.py  # Core registry implementation.
│       │   │   ├── registry_core_parts.py  # Decomposed registry helpers.
│       │   │   ├── validation.py  # Input validation.
│       │   │   ├── bindings/  # Metric→source binding profiles.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── builtin_profiles.py  # Built-in binding profile definitions.
│       │   │   │   ├── models.py  # Binding data models.
│       │   │   │   ├── registry.py  # Binding profile registry.
│       │   │   │   └── resolver.py  # Binding resolution logic.
│       │   │   ├── cache/  # CAS-based caching.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── _store_core.py  # Core cache store logic.
│       │   │   │   ├── _store_index.py  # Cache index management.
│       │   │   │   ├── _store_models.py  # Cache entry models.
│       │   │   │   ├── _store_serialization.py  # Cache serialization.
│       │   │   │   ├── invalidation.py  # Cache invalidation.
│       │   │   │   ├── policy.py  # TTL policies.
│       │   │   │   ├── prefetch.py  # Prefetching.
│       │   │   │   ├── proxy.py  # Caching proxy layer.
│       │   │   │   ├── schema_aware.py  # Schema-aware cache keying.
│       │   │   │   └── store.py  # CAS cache store facade.
│       │   │   ├── contracts/  # Schema evolution and data contracts.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── _inference_config.py  # Schema inference configuration.
│       │   │   │   ├── _inference_engine.py  # Schema inference engine.
│       │   │   │   ├── _inference_result.py  # Inference result models.
│       │   │   │   ├── _inference_validation.py  # Inference validation.
│       │   │   │   ├── _schema_core.py  # Core schema operations.
│       │   │   │   ├── _schema_errors.py  # Schema error types.
│       │   │   │   ├── _schema_field.py  # Schema field definitions.
│       │   │   │   ├── _schema_types.py  # Schema type system.
│       │   │   │   ├── contract.py  # Connector data contracts.
│       │   │   │   ├── contract_registry.py  # Contract registry.
│       │   │   │   ├── evolution.py  # Contract evolution.
│       │   │   │   ├── inference.py  # Schema inference facade.
│       │   │   │   ├── registry.py  # Schema registry.
│       │   │   │   ├── schema.py  # Schema management.
│       │   │   │   └── validation_middleware.py  # Contract validation middleware.
│       │   │   ├── federation/  # Cross-connector federation.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── composer.py  # Federation composition.
│       │   │   │   ├── evidence_aggregation.py  # Evidence aggregation.
│       │   │   │   ├── planner.py  # Federation query planning.
│       │   │   │   ├── ranker.py  # Source ranking.
│       │   │   │   ├── resolver.py  # Conflict resolution.
│       │   │   │   └── types.py  # Federation types.
│       │   │   ├── profiles/  # Source connection profiles.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── builtin_profiles.py  # Built-in source profile definitions.
│       │   │   │   ├── models.py  # Profile data models.
│       │   │   │   ├── registry.py  # Source profile registry.
│       │   │   │   └── resolver.py  # Profile resolution logic.
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
│       │   │   ├── sources/  # Production data source connectors.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── ckan_catalog.py  # CKAN catalog discovery connector.
│       │   │   │   ├── ckan_resource.py  # CKAN resource download connector.
│       │   │   │   ├── eurostat.py  # Eurostat statistics connector.
│       │   │   │   ├── http_base.py  # Shared HTTP connector base class.
│       │   │   │   ├── http_common.py  # Common HTTP utilities.
│       │   │   │   ├── opendatasoft.py  # OpenDataSoft portal connector.
│       │   │   │   ├── rest_json.py  # Generic REST/JSON source connector.
│       │   │   │   ├── sdmx_source.py  # SDMX statistical data connector.
│       │   │   │   ├── socrata.py  # Socrata open data connector.
│       │   │   │   ├── sparql.py  # SPARQL endpoint connector.
│       │   │   │   ├── ukons.py  # UK ONS statistics connector.
│       │   │   │   ├── world_bank.py  # World Bank data connector.
│       │   │   │   └── _contracts/  # Source-specific data contracts.
│       │   │   │       ├── __init__.py
│       │   │   │       ├── eurostat_contracts.py  # Eurostat schema contracts.
│       │   │   │       ├── sdmx_contracts.py  # SDMX schema contracts.
│       │   │   │       ├── ukons_contracts.py  # UK ONS schema contracts.
│       │   │   │       └── world_bank_contracts.py  # World Bank schema contracts.
│       │   │   ├── testing/  # Connector test infrastructure.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── contracts.py  # Test contracts.
│       │   │   │   ├── fixtures.py  # Test fixtures.
│       │   │   │   ├── harness.py  # ConnectorTestHarness.
│       │   │   │   └── simulator.py  # APISimulator.
│       │   │   ├── transform/  # Data transformation pipeline.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── _common.py  # Shared transform utilities.
│       │   │   │   ├── aggregator.py  # Data aggregation.
│       │   │   │   ├── filter.py  # Data filtering.
│       │   │   │   ├── harmonizer.py  # Data harmonization.
│       │   │   │   ├── imputer.py  # Missing data imputation.
│       │   │   │   ├── normalizer.py  # Data normalization.
│       │   │   │   ├── pipeline.py  # Pipeline orchestration.
│       │   │   │   └── validator.py  # Transformation validation.
│       │   │   └── types/  # Type system.
│       │   │       ├── __init__.py
│       │   │       ├── _coercion_engine.py  # Coercion dispatch engine.
│       │   │       ├── _coercion_errors.py  # Coercion error types.
│       │   │       ├── _coercion_policies.py  # Coercion policy definitions.
│       │   │       ├── _coercion_rules.py  # Individual coercion rules.
│       │   │       ├── _units_base.py  # Unit base types.
│       │   │       ├── _units_core.py  # Core unit conversion logic.
│       │   │       ├── _units_errors.py  # Unit conversion errors.
│       │   │       ├── _units_prefixes.py  # SI/metric prefix handling.
│       │   │       ├── _units_registry.py  # Unit registry implementation.
│       │   │       ├── coercion.py  # Type coercion facade.
│       │   │       ├── connector_types.py  # Connector types.
│       │   │       ├── dimensions.py  # Dimensional data types.
│       │   │       ├── temporal.py  # Temporal types.
│       │   │       └── units.py  # Unit conversion facade.
│       │   ├── data_plane/  # Incremental data ingestion and replay.
│       │   │   ├── __init__.py
│       │   │   ├── cursor_store.py  # Cursor-based pagination state store.
│       │   │   ├── modes.py  # Ingestion mode definitions (full/incremental/streaming).
│       │   │   ├── orchestrator.py  # Incremental ingestion orchestrator.
│       │   │   ├── regression.py  # Data regression detection.
│       │   │   ├── replay_store.py  # Record/replay store for ingestion.
│       │   │   └── watermark.py  # High-watermark tracking for incremental loads.
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
│       │   ├── pii/  # PII detection and redaction.
│       │   │   ├── __init__.py
│       │   │   ├── detector.py  # PII detection engine (Presidio).
│       │   │   ├── models.py  # PII annotation models.
│       │   │   └── stage.py  # PII processing pipeline stage.
│       │   ├── provenance/  # W3C PROV-O provenance.
│       │   │   ├── __init__.py
│       │   │   ├── core.py  # PROV-O graph models.
│       │   │   └── export_provo.py  # PROV-O export.
│       │   ├── retrieval/  # Hybrid data retrieval service.
│       │   │   ├── __init__.py
│       │   │   ├── executor.py  # FetchPlan preview/execute with quality gate.
│       │   │   ├── explore_lane.py  # Bounded on-demand metadata discovery (ExploreLane).
│       │   │   └── service.py  # Hybrid retrieval service (FastLane + ExploreLane + PromotionLane).
│       │   ├── security/  # Fabric-level data security.
│       │   │   ├── __init__.py
│       │   │   └── column_mask.py  # Column-level data masking.
│       │   ├── storage/  # Pluggable storage backends.
│       │   │   ├── __init__.py
│       │   │   ├── duckdb_adapter.py  # DuckDB storage adapter.
│       │   │   ├── memory_adapter.py  # In-memory storage adapter.
│       │   │   └── port.py  # Storage port (abstract interface).
│       │   └── world/  # World model and state management.
│       │       ├── __init__.py
│       │       ├── events.py  # World event bus.
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
│       │   ├── _executor_graph.py  # Executor graph representation.
│       │   ├── _executor_models.py  # Executor internal models.
│       │   ├── _executor_ops.py  # Executor operation primitives.
│       │   ├── _executor_patching.py  # State patching logic.
│       │   ├── _executor_snapshots.py  # Execution snapshot management.
│       │   ├── agent_metrics.py  # Agent-level metrics collection.
│       │   ├── agents.py  # Agent type definitions.
│       │   ├── conflict_checker.py  # Static slot-write conflict detection.
│       │   ├── constraints_engine.py  # Constraint evaluation engine.
│       │   ├── cost_model.py  # Heuristic cost model.
│       │   ├── executor.py  # JAX step/scan/batch executor facade.
│       │   ├── layout.py  # State layout management.
│       │   ├── loss.py  # Loss function utilities.
│       │   ├── merge_engine.py  # CRDT-inspired merge semantics.
│       │   ├── patch_vm.py  # Patch-based virtual machine.
│       │   ├── profiles.py  # Execution profiles.
│       │   ├── queue.py  # Execution queue.
│       │   ├── registry.py  # Foundry component registry.
│       │   ├── specs.py  # Specification models.
│       │   ├── trace.py  # Foundry tracing.
│       │   ├── types.py  # Core Foundry types.
│       │   ├── utils.py  # Foundry utility helpers.
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
│       │   ├── contracts/  # Foundry-level contracts.
│       │   │   ├── __init__.py
│       │   │   ├── fidelity.py  # Simulation fidelity contracts.
│       │   │   ├── mechanism.py  # Mechanism contracts.
│       │   │   └── state.py  # State contracts.
│       │   ├── data_plane/  # Foundry↔Fabric data bindings.
│       │   │   ├── __init__.py
│       │   │   └── bindings.py  # Input/output data binding definitions.
│       │   ├── domain/  # Economic domain schemas.
│       │   │   ├── __init__.py
│       │   │   └── schema.py  # Domain schema definitions.
│       │   ├── execute/  # Execution orchestration.
│       │   │   ├── __init__.py
│       │   │   └── api.py  # Execution public API.
│       │   ├── mechanisms/  # Reusable economic mechanisms.
│       │   │   ├── __init__.py
│       │   │   ├── fiscal.py  # Fiscal policy mechanisms.
│       │   │   ├── labor.py  # Labor market mechanisms.
│       │   │   └── treasury.py  # RNG/seed treasury.
│       │   ├── methods/  # Method implementations and catalog.
│       │   │   ├── __init__.py
│       │   │   ├── _artifacts_chain.py  # Chain artifact tracking.
│       │   │   ├── _artifacts_evidence.py  # Evidence artifact handling.
│       │   │   ├── _artifacts_fingerprint.py  # Artifact fingerprint computation.
│       │   │   ├── _artifacts_method.py  # Method artifact management.
│       │   │   ├── _artifacts_records.py  # Artifact record types.
│       │   │   ├── artifacts.py  # Method artifact facade.
│       │   │   ├── artifacts_parts.py  # Decomposed artifact helpers.
│       │   │   ├── base.py  # Base method protocol.
│       │   │   ├── catalog_snapshot.py  # Method catalog snapshot builder from MethodRegistry.
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
│       │   │   │   │   ├── synthetic_control.py  # Synthetic Control method (Abadie).
│       │   │   │   │   ├── scm.py  # Legacy shim for synthetic_control.py.
│       │   │   │   │   └── structural_time_series.py  # Structural time series.
│       │   │   │   ├── econometrics/  # Econometric methods.
│       │   │   │   │   ├── __init__.py
│       │   │   │   │   ├── _registry_boot.py  # Auto-registration.
│       │   │   │   │   ├── iv.py  # Instrumental variables.
│       │   │   │   │   ├── panel.py  # Panel data models.
│       │   │   │   │   ├── protocols.py  # Econometric protocols.
│       │   │   │   │   └── timeseries.py  # Time series models.
│       │   │   │   └── optimization/  # Optimization methods.
│       │   │   │       ├── __init__.py
│       │   │   │       ├── _registry_boot.py  # Auto-registration.
│       │   │   │       ├── io_model.py  # Input-output model.
│       │   │   │       ├── lp.py  # Linear programming.
│       │   │   │       ├── milp.py  # Mixed-integer linear programming.
│       │   │   │       └── protocols.py  # Optimization protocols.
│       │   │   ├── causal/  # Causal method standalone wrappers.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── _common.py  # Shared causal utilities.
│       │   │   │   ├── _econml_adapter.py  # EconML integration.
│       │   │   │   ├── _registry_boot.py  # Auto-registration.
│       │   │   │   ├── cate.py  # CATE estimation wrapper.
│       │   │   │   ├── did.py  # DiD wrapper.
│       │   │   │   ├── dml.py  # DML wrapper.
│       │   │   │   ├── meta_learners.py  # Meta-learner wrapper.
│       │   │   │   ├── policy_learning.py  # Policy learning wrapper.
│       │   │   │   ├── protocols.py  # Causal protocols.
│       │   │   │   ├── rdd.py  # RDD wrapper.
│       │   │   │   ├── synthetic_control.py  # Synthetic Control wrapper.
│       │   │   │   ├── scm.py  # Legacy shim wrapper.
│       │   │   │   └── structural_time_series.py  # STS wrapper.
│       │   │   ├── econometrics/  # Econometric method standalone wrappers.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── _registry_boot.py  # Auto-registration.
│       │   │   │   ├── iv.py  # IV wrapper.
│       │   │   │   ├── panel.py  # Panel data wrapper.
│       │   │   │   ├── protocols.py  # Econometric protocols.
│       │   │   │   └── timeseries.py  # Time series wrapper.
│       │   │   ├── optimization/  # Optimization method standalone wrappers.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── _registry_boot.py  # Auto-registration.
│       │   │   │   ├── io_model.py  # IO model wrapper.
│       │   │   │   ├── lp.py  # LP wrapper.
│       │   │   │   ├── milp.py  # MILP wrapper.
│       │   │   │   └── protocols.py  # Optimization protocols.
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
│       │   ├── canon.py  # Canonical representations.
│       │   ├── citations.py  # Citation tracking models.
│       │   ├── connectors.py  # Connector IR integration.
│       │   ├── fact_log.py  # Fact log IR models.
│       │   ├── loaders.py  # Universal policy loader.
│       │   ├── migration_report.py  # Migration report models.
│       │   ├── model_spec.py  # ModelSpec (data snapshots, assumptions).
│       │   ├── norm_pack.py  # NormPack/NormRule contracts.
│       │   ├── portfolio.py  # Policy portfolio models.
│       │   ├── predicate.py  # Predicate expressions.
│       │   ├── queries.py  # IR query models.
│       │   ├── refs.py  # IR reference types.
│       │   ├── registry_fragments.py  # IR registry fragments.
│       │   ├── types.py  # IR type definitions.
│       │   ├── units.py  # Unit system models.
│       │   ├── analytics/  # Analytical IR models.
│       │   │   ├── __init__.py
│       │   │   ├── applicability.py  # Policy applicability checks.
│       │   │   ├── backtest.py  # Backtesting IR models.
│       │   │   ├── calibration.py  # Calibration IR models.
│       │   │   ├── causal.py  # Causal effect IR models.
│       │   │   ├── data_views.py  # Data view definitions.
│       │   │   ├── distributional.py  # Distributional analysis IR.
│       │   │   ├── hte.py  # HTE result IR models.
│       │   │   └── uncertainty.py  # Uncertainty envelope IR.
│       │   ├── artifacts/  # IR artifact contracts and I/O.
│       │   │   ├── __init__.py
│       │   │   ├── contracts.py  # Artifact contract definitions.
│       │   │   └── io.py  # Artifact serialization/deserialization.
│       │   ├── governance/  # Governance-related IR models.
│       │   │   ├── __init__.py
│       │   │   ├── gate.py  # Gate context/decision IR models.
│       │   │   ├── policy_spec.py  # PolicySpec (interventions).
│       │   │   ├── problem_frame.py  # ProblemFrame (goals/KPIs).
│       │   │   ├── schedule.py  # Schedule models.
│       │   │   ├── selector_expr.py  # Selector expressions.
│       │   │   └── validation.py  # IR validation.
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
│       │   │   ├── _trinity_linker.py  # Trinity linker implementation.
│       │   │   ├── _trinity_mechanisms.py  # Trinity mechanism resolution.
│       │   │   ├── _trinity_models.py  # Trinity linker models.
│       │   │   ├── _trinity_params.py  # Trinity parameter resolution.
│       │   │   ├── link_trinity.py  # Trinity linking facade.
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
│       │   ├── artifacts.py  # Lex artifact management.
│       │   ├── common.py  # Shared lex utilities.
│       │   ├── errors.py  # Lex error types.
│       │   ├── factlog.py  # Lex fact log integration.
│       │   ├── types.py  # Lex type definitions.
│       │   ├── batch/  # Lex batch pipeline for legal document processing.
│       │   │   ├── __init__.py
│       │   │   ├── __main__.py  # Module entry point.
│       │   │   ├── canonicalizers.py  # Canonicalizers for SPO extraction.
│       │   │   ├── cli.py  # CLI entry point for Lex batch pipeline.
│       │   │   ├── config.py  # Configuration for Lex batch pipeline.
│       │   │   ├── embedder.py  # Generate embeddings and build HNSW indexes.
│       │   │   ├── graph_builder.py  # Stream SPO results into DuckDB knowledge graph.
│       │   │   ├── openai_batch_embeddings.py  # OpenAI Batch API workflow for embeddings.
│       │   │   ├── pipeline.py  # Orchestrate all stages of the batch pipeline.
│       │   │   ├── progress.py  # Checkpoint/resume tracker for batch pipeline.
│       │   │   ├── provisions_io.py  # Disk helpers for Stage 2 provisions with shard prefix.
│       │   │   ├── quality_report.py  # Quality report and quality gates.
│       │   │   ├── spo_extractor.py  # Async LLM-based 2-pass SPO extraction.
│       │   │   ├── spo_prompts.py  # Prompt templates for Ukrainian legal provision extraction.
│       │   │   ├── structurer.py  # Lightweight provision extraction using UA regex.
│       │   │   └── xml_parser.py  # Stream-parse ЄДРНПА XML dumps into NPADocument objects.
│       │   ├── corpus/  # Legal document corpus.
│       │   │   ├── __init__.py
│       │   │   ├── index.py  # Corpus indexing.
│       │   │   ├── ingest.py  # Corpus ingestion.
│       │   │   ├── structure.py  # Document structure.
│       │   │   └── versioning.py  # Corpus versioning.
│       │   ├── knowledge/  # Legal knowledge graph.
│       │   │   ├── __init__.py
│       │   │   ├── search.py  # Hybrid search API for legal knowledge graph.
│       │   │   ├── store.py  # Read-only DuckDB knowledge graph + HNSW vector indexes.
│       │   │   └── types.py  # Domain types for knowledge graph (SPO entities, facts).
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
│       ├── runtime/  # Run lifecycle, manifests, HTTP API.
│       │   ├── __init__.py
│       │   ├── api.py  # Runtime lifecycle API.
│       │   ├── manifest.py  # Portable run manifests.
│       │   ├── replay.py  # Run replay infrastructure.
│       │   └── http/  # FastAPI HTTP runtime server.
│       │       ├── __init__.py
│       │       ├── app.py  # FastAPI application factory.
│       │       ├── authz_middleware.py  # Authorization middleware.
│       │       ├── cell_router_middleware.py  # Cell-based request routing.
│       │       ├── dependencies.py  # FastAPI dependency injection.
│       │       ├── errors.py  # HTTP error handlers.
│       │       ├── jwt_auth_middleware.py  # JWT authentication middleware.
│       │       ├── openapi_contract.py  # OpenAPI schema contract validation and example generation.
│       │       ├── routes/  # API route modules.
│       │       │   ├── __init__.py
│       │       │   ├── artifacts.py  # /artifacts endpoints.
│       │       │   ├── control.py  # /api/v1/control/ endpoints (Control Plane).
│       │       │   ├── debug.py  # /debug endpoints.
│       │       │   ├── health.py  # /health endpoints.
│       │       │   └── runs.py  # /runs endpoints.
│       │       └── services/  # Business logic services.
│       │           ├── __init__.py
│       │           ├── artifact_inspector.py  # Artifact inspection service.
│       │           ├── control.py  # Control Plane business logic service.
│       │           ├── debug.py  # Debug service.
│       │           ├── lineage.py  # Lineage tracking service.
│       │           ├── run_index.py  # Run index/search service.
│       │           ├── task_runner.py  # Background task runner for control-plane operations.
│       │           ├── timeline.py  # Timeline service.
│       │           └── adapters/  # Service adapters.
│       │               ├── __init__.py
│       │               └── core_run.py  # Core run adapter.
│       ├── scholar/  # Knowledge discovery layer.
│       │   ├── __init__.py
│       │   ├── api.py  # Scholar public API.
│       │   ├── errors.py  # Scholar errors.
│       │   ├── freshness.py  # Source freshness monitoring.
│       │   ├── freshness_store.py  # Freshness metadata persistence.
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
│           ├── api.py  # Scientist public API.
│           ├── llm_cycle.py  # Unified LLM policy cycle orchestrator with DAG execution.
│           ├── publisher.py  # Result publishing.
│           ├── replay_backend.py  # Replay backend for re-execution.
│           ├── adapters/  # External system bridges.
│           │   ├── __init__.py
│           │   ├── fabric_bridge.py  # Fabric integration bridge.
│           │   └── foundry_bridge.py  # Foundry integration bridge.
│           ├── agent/  # Hierarchical agent system.
│           │   ├── __init__.py
│           │   ├── _drafter_formatting.py  # Drafter output formatting.
│           │   ├── _drafter_llm.py  # Drafter LLM interaction.
│           │   ├── _drafter_orchestrator.py  # Drafter orchestration logic.
│           │   ├── _drafter_parsing.py  # Drafter response parsing.
│           │   ├── _drafter_passes.py  # Drafter multi-pass processing.
│           │   ├── base.py  # Base agent class.
│           │   ├── code_verifier.py  # Generated code safety verifier.
│           │   ├── constitution.py  # Agent constitutional constraints.
│           │   ├── constraint_context.py  # Constraint context propagation.
│           │   ├── critic.py  # Critic agent.
│           │   ├── data_need_extractor.py  # DataNeedExtractor agent (mock + LLM).
│           │   ├── drafter.py  # Drafter agent facade.
│           │   ├── drafter_clients.py  # Drafter LLM client wrappers.
│           │   ├── drafter_factory.py  # Drafter instance factory.
│           │   ├── drafter_models.py  # Drafter data models.
│           │   ├── drafter_multipass.py  # Multi-pass drafter orchestrator.
│           │   ├── drafter_multipass_parts.py  # Decomposed multi-pass helpers.
│           │   ├── failure_card.py  # Failure card generation.
│           │   ├── failure_index.py  # Failure index for pattern tracking.
│           │   ├── feasibility.py  # Feasibility probe logic.
│           │   ├── feasibility_duckdb.py  # DuckDB-based feasibility checks.
│           │   ├── formalizer.py  # Formalizer agent.
│           │   ├── informed_critic.py  # Evidence-informed critic agent.
│           │   ├── knowledge_base.py  # Agent knowledge base.
│           │   ├── memory.py  # Agent memory.
│           │   ├── norm_loader.py  # Norm loading for agent context.
│           │   ├── pi.py  # PI agent.
│           │   ├── prompt.py  # Prompt construction.
│           │   ├── prompts.py  # Prompt templates.
│           │   ├── protocols.py  # Agent protocols.
│           │   ├── rag.py  # RAG index for knowledge retrieval.
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
│           │   ├── iteration_state_machine.py  # Iteration lifecycle state machine transitions.
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
│           │       ├── pii_check_pass.py  # PII detection governance pass.
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
│           │   ├── human_gate.py  # Human-in-the-loop gate.
│           │   ├── node_registry.py  # Workflow node registry.
│           │   ├── parameter_extraction.py  # Parameter extraction from specs.
│           │   ├── slot_compiler.py  # Slot→mechanism compiler.
│           │   ├── slot_semantics.py  # Slot semantic validation.
│           │   ├── slot_specifier.py  # Slot specifier parsing.
│           │   ├── types.py  # Kernel type definitions.
│           │   ├── url_routing.py  # URL-based resource routing.
│           │   └── world_validation.py  # World state validation.
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
│           │       │   ├── bind_foundry_inputs.py  # Foundry input data binding.
│           │       │   ├── build_data_snapshot.py  # Data snapshot.
│           │       │   └── enrich_knowledge.py  # Knowledge enrichment.
│           │       ├── decide/  # Decision nodes.
│           │       │   ├── __init__.py
│           │       │   └── build_decision_packet.py  # Decision packet.
│           │       ├── governance/  # Governance nodes.
│           │       │   ├── __init__.py
│           │       │   ├── data_plane_gate.py  # Data plane access gate.
│           │       │   ├── legal_check.py  # Legal check node.
│           │       │   └── run_governance.py  # Governance node.
│           │       ├── planning/  # Planning and preflight nodes.
│           │       │   ├── __init__.py
│           │       │   ├── build_execution_plan.py  # Execution plan construction node.
│           │       │   ├── build_method_catalog_snapshot.py  # Method catalog snapshot node.
│           │       │   ├── ready_to_run.py  # Ready-to-run gate node.
│           │       │   ├── run_evaluator.py  # Evaluator execution node.
│           │       │   └── run_preflight.py  # Preflight validation node.
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
│           │   ├── diversity.py  # Diversity-promoting selection.
│           │   ├── objective.py  # Objective functions.
│           │   ├── portfolio.py  # Policy portfolio optimization.
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
│           └── workflows/  # Workflow engines and predefined builders.
│               ├── __init__.py
│               ├── builder.py  # Workflow builder.
│               ├── default.py  # Default workflow.
│               ├── engine_base.py  # Engine base class.
│               ├── engine_langgraph.py  # LangGraph engine.
│               └── engine_simple.py  # Simple sequential engine.
├── schemas/  # ABI schema registry and snapshots.
│   ├── __init__.py
│   ├── abi_models.py  # ABI model definitions for schema generation.
│   ├── runtime_api_v1.openapi.json  # Runtime HTTP API OpenAPI spec.
│   └── snapshots/
│       ├── connectors/  # Connector schema snapshots.
│       │   └── contracts.json  # Connector data contracts.
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
│           ├── policy_portfolio.schema.json  # Policy portfolio.
│           ├── policy_recommendation.schema.json  # Policy recommendation.
│           ├── policy_spec.schema.json  # PolicySpec.
│           ├── problem_frame.schema.json  # ProblemFrame.
│           ├── prov_activity.schema.json  # Provenance activity.
│           ├── quality_report.schema.json  # Quality report.
│           ├── trinity_bundle.schema.json  # TrinityBundle.
│           ├── trust_assessment.schema.json  # Trust assessment.
│           ├── uncertainty_envelope.schema.json  # Uncertainty envelope.
│           └── world_event.schema.json  # World event.
├── ops/  # Operations: monitoring, observability, alerting, infra.
│   ├── docker-compose.observability.yml  # Observability stack.
│   ├── grafana/  # Grafana dashboards.
│   │   ├── dashboards/
│   │   │   ├── executive-overview.json  # Executive cost/performance.
│   │   │   ├── foundry-hpc.json  # HPC simulation dashboard.
│   │   │   ├── knowledge-freshness.json  # Knowledge freshness monitoring.
│   │   │   ├── scientist-agents.json  # Agent workflow dashboard.
│   │   │   ├── security-phase4.json  # Security metrics dashboard.
│   │   │   └── slo-overview.json  # SLO tracking dashboard.
│   │   └── provisioning/
│   │       └── dashboards.yml  # Dashboard auto-provisioning.
│   ├── prometheus/  # Prometheus configuration.
│   │   ├── alerts.yml  # Alerting rules.
│   │   ├── prometheus.yml  # Scrape configuration.
│   │   ├── recording_rules.yml  # Metric pre-computation.
│   │   ├── slo_alerts.yml  # SLO alerting rules.
│   │   ├── slo_recording_rules.yml  # SLO recording rules.
│   │   └── rules/  # Additional rule files.
│   │       ├── audit_chain_alerts.yml  # Audit chain integrity alerts.
│   │       └── mtls-rules.yaml  # mTLS monitoring rules.
│   ├── opa/  # OPA policy-as-code.
│   │   └── policies/
│   │       ├── data_classification.rego  # Data classification policy.
│   │       ├── data_classification_test.rego  # Data classification tests.
│   │       ├── decision.rego  # Decision authorization policy.
│   │       ├── decision_test.rego  # Decision policy tests.
│   │       ├── delegation_guard.rego  # Delegation guard policy.
│   │       ├── delegation_guard_test.rego  # Delegation guard tests.
│   │       ├── deploy.rego  # Deployment policy.
│   │       ├── deploy_test.rego  # Deployment policy tests.
│   │       ├── role_access.rego  # Role-based access policy.
│   │       ├── role_access_test.rego  # Role access tests.
│   │       ├── tenant_boundary.rego  # Tenant boundary isolation.
│   │       ├── tenant_boundary_test.rego  # Tenant boundary tests.
│   │       ├── vulnerability.rego  # Vulnerability policy.
│   │       └── vulnerability_test.rego  # Vulnerability policy tests.
│   ├── helm/  # Helm charts for Kubernetes deployment.
│   │   ├── polisyos-cell/  # Cell isolation Helm chart.
│   │   │   ├── Chart.yaml  # Chart metadata.
│   │   │   ├── values.yaml  # Default values.
│   │   │   ├── policies/  # OPA policies bundled in chart.
│   │   │   │   ├── data_classification.rego  # Data classification.
│   │   │   │   ├── decision.rego  # Decision authorization.
│   │   │   │   ├── delegation_guard.rego  # Delegation guard.
│   │   │   │   ├── deploy.rego  # Deployment policy.
│   │   │   │   ├── role_access.rego  # Role access.
│   │   │   │   ├── tenant_boundary.rego  # Tenant boundary.
│   │   │   │   └── vulnerability.rego  # Vulnerability checks.
│   │   │   ├── templates/
│   │   │   │   ├── _helpers.tpl  # Template helpers.
│   │   │   │   ├── configmap-opa-policies.yaml  # OPA policy ConfigMap.
│   │   │   │   ├── namespace.yaml  # Namespace creation.
│   │   │   │   ├── networkpolicy.yaml  # Network policies.
│   │   │   │   ├── NOTES.txt  # Post-install notes.
│   │   │   │   ├── podsecuritystandard.yaml  # Pod security standards.
│   │   │   │   ├── rbac.yaml  # RBAC roles and bindings.
│   │   │   │   ├── resourcequota.yaml  # Resource quotas.
│   │   │   │   ├── runtimeclass-confidential.yaml  # Confidential compute runtime.
│   │   │   │   └── server-policy.yaml  # Server admission policy.
│   │   │   └── tests/
│   │   │       └── test-isolation.yaml  # Isolation test manifest.
│   │   ├── keycloak/  # Keycloak identity provider chart.
│   │   │   ├── Chart.yaml  # Chart metadata.
│   │   │   ├── values.yaml  # Default values.
│   │   │   └── templates/
│   │   │       ├── namespace.yaml  # Namespace creation.
│   │   │       ├── service.yaml  # Keycloak service.
│   │   │       └── statefulset.yaml  # Keycloak StatefulSet.
│   │   └── spire/  # SPIRE identity framework chart.
│   │       ├── Chart.yaml  # Chart metadata.
│   │       ├── values.yaml  # Default values.
│   │       └── templates/
│   │           ├── agent-configmap.yaml  # Agent configuration.
│   │           ├── agent-daemonset.yaml  # Agent DaemonSet.
│   │           ├── namespace.yaml  # Namespace creation.
│   │           ├── server-configmap.yaml  # Server configuration.
│   │           ├── server-deployment.yaml  # Server Deployment.
│   │           ├── server-service.yaml  # Server Service.
│   │           └── service-accounts.yaml  # Service accounts.
│   ├── migrations/  # Database migrations.
│   │   ├── 001_tenant_columns.sql  # Add tenant columns.
│   │   ├── 002_tenant_backfill.sql  # Backfill tenant data.
│   │   ├── 003_rls_enable.sql  # Enable row-level security.
│   │   ├── 003_rls_disable_rollback.sql  # RLS rollback script.
│   │   └── 004_roles_grants.sql  # Role and grant setup.
│   ├── terraform/  # Terraform modules.
│   │   └── modules/
│   │       └── confidential_nodepool/
│   │           └── main.tf  # Confidential compute node pool.
│   └── scripts/  # Operational scripts.
│       └── install-linkerd.sh  # Linkerd service mesh installer.
├── tests/  # Test suite.
│   ├── conftest.py  # Root fixtures.
│   ├── test_arch_import_gate.py  # Import boundary enforcement.
│   ├── test_components_bridge.py  # Component bridge tests.
│   ├── test_components_discovery.py  # Component discovery tests.
│   ├── test_components_id_semver.py  # Component ID/semver tests.
│   ├── test_packs_discovery.py  # Pack discovery tests.
│   ├── test_public_api_facades.py  # Public API facade tests.
│   ├── contract/  # Contract and schema tests.
│   │   ├── conftest.py
│   │   ├── test_abi_diff_tool.py  # ABI diff tool tests.
│   │   ├── test_applicability_contract.py  # Applicability contract tests.
│   │   ├── test_citations_contract.py  # Citations contract tests.
│   │   ├── test_foundry_facade_contracts.py  # Foundry facade tests.
│   │   ├── test_foundry_input_bindings_contract.py  # Foundry input binding tests.
│   │   ├── test_gate_models.py  # Gate model tests.
│   │   ├── test_gate_protocol.py  # Gate protocol tests.
│   │   ├── test_golden_record_ids.py  # Golden record ID tests.
│   │   ├── test_ir_migrations.py  # IR migration tests.
│   │   ├── test_kernel_models.py  # Kernel model tests.
│   │   ├── test_run_experiment_slo.py  # Run experiment SLO tests.
│   │   ├── test_scientist_workflow_spec_contract.py  # Workflow spec tests.
│   │   ├── test_security_metrics_helpers.py  # Security metrics helper tests.
│   │   ├── test_slo_metrics.py  # SLO metrics tests.
│   │   ├── test_trinity_contracts.py  # Trinity contract tests.
│   │   ├── test_trinity_linker_contract.py  # Trinity linker tests.
│   │   ├── test_trinity_migration.py  # Trinity migration tests.
│   │   └── test_world_abi_contract.py  # World ABI tests.
│   ├── core/  # Core infrastructure tests.
│   │   ├── test_backend_dispatcher.py  # Backend dispatcher tests.
│   │   ├── test_cache.py  # Cache subsystem tests.
│   │   ├── test_discovery_base.py  # Discovery base tests.
│   │   ├── test_error_base.py  # Error hierarchy tests.
│   │   ├── test_hashing.py  # Hashing tests.
│   │   ├── test_llm_core.py  # LLM core client tests.
│   │   ├── test_pipeline.py  # Pipeline framework tests.
│   │   ├── test_registry_base.py  # Registry base tests.
│   │   ├── test_registry_generic.py  # Generic registry tests.
│   │   ├── test_scoring_framework.py  # Scoring framework tests.
│   │   ├── phase0/  # Phase-0 core tests.
│   │   │   ├── conftest.py
│   │   │   ├── test_artifact_export_import.py  # Artifact export/import.
│   │   │   ├── test_artifact_graph.py  # Artifact graph tracking.
│   │   │   ├── test_artifact_store.py  # CAS store tests.
│   │   │   ├── test_audit_export_verify.py  # Audit export/verify.
│   │   │   ├── test_audit_manifest_compat.py  # Audit manifest compatibility.
│   │   │   ├── test_canon_json.py  # Canonical JSON tests.
│   │   │   ├── test_cli.py  # CLI tests.
│   │   │   ├── test_cli_resume.py  # CLI resume tests.
│   │   │   ├── test_cli_signing.py  # CLI signing tests.
│   │   │   ├── test_decorators.py  # @traced decorator tests.
│   │   │   ├── test_environment_manifest.py  # Environment manifest tests.
│   │   │   ├── test_logs.py  # Log-trace correlation tests.
│   │   │   ├── test_metrics.py  # Metrics registry tests.
│   │   │   ├── test_observability.py  # Observability workflow tests.
│   │   │   ├── test_propagation.py  # Trace propagation tests.
│   │   │   ├── test_provenance_contract_shims.py  # Provenance contract shims.
│   │   │   ├── test_registry_bundle.py  # Registry bundle tests.
│   │   │   ├── test_run_context.py  # Run context tests.
│   │   │   ├── test_signing.py  # Signing tests.
│   │   │   ├── test_store_signing.py  # Store signing tests.
│   │   │   └── test_tracer.py  # Tracer singleton tests.
│   │   ├── components/  # Component system tests.
│   │   │   ├── test_connector_kind_compliance.py  # Connector kind compliance.
│   │   │   ├── test_no_legacy_entrypoint_groups.py  # Legacy entrypoint check.
│   │   │   └── test_unified_bootstrap_idempotency.py  # Bootstrap idempotency.
│   │   ├── contracts/  # Core contract tests.
│   │   │   ├── test_execution_plan_contracts.py  # Execution plan contract tests.
│   │   │   └── test_ir_ref_facades.py  # IR reference facade tests.
│   │   └── security/  # Security subsystem tests.
│   │       ├── test_access_scope.py  # Access scope tests.
│   │       ├── test_audit_chain.py  # Audit chain integrity tests.
│   │       ├── test_auth_middlewares.py  # Auth middleware tests.
│   │       ├── test_authz.py  # Authorization tests.
│   │       ├── test_cell.py  # Cell isolation tests.
│   │       ├── test_db_backend.py  # DB backend tests.
│   │       ├── test_delegation.py  # Delegation tests.
│   │       ├── test_identity.py  # Identity management tests.
│   │       ├── test_registry.py  # Security registry tests.
│   │       ├── test_rls_isolation.py  # Row-level security tests.
│   │       ├── test_router.py  # Router tests.
│   │       ├── test_router_resolve_headers.py  # Router header resolution tests.
│   │       ├── test_sbom.py  # SBOM generation tests.
│   │       ├── test_tee.py  # TEE tests.
│   │       ├── test_tee_middleware.py  # TEE middleware tests.
│   │       └── test_tenant_context.py  # Tenant context tests.
│   ├── demos/  # Demo smoke tests.
│   │   └── run_laffer_demo.py  # Laffer demo.
│   ├── fabric/  # Fabric tests.
│   │   ├── test_claims_pipeline.py  # Claims pipeline tests.
│   │   ├── test_conflict_uncertainty_adapter.py  # Conflict uncertainty adapter.
│   │   ├── test_conflicts.py  # Conflict resolution tests.
│   │   ├── test_data_catalog.py  # Data catalog tests.
│   │   ├── test_docs_pipeline.py  # Docs pipeline tests.
│   │   ├── test_legal_evaluation.py  # Legal evaluation tests.
│   │   ├── test_lex_corpus.py  # Lex corpus tests.
│   │   ├── test_normpack.py  # Normpack tests.
│   │   ├── test_provenance.py  # Provenance tests.
│   │   ├── test_quality_indicators.py  # Quality indicator tests.
│   │   ├── test_scholar_extractor_components.py  # Scholar extractor tests.
│   │   ├── test_scholar_freshness.py  # Scholar freshness tests.
│   │   ├── test_scholar_freshness_store.py  # Scholar freshness store tests.
│   │   ├── test_scholar_mvp.py  # Scholar MVP tests.
│   │   ├── test_storage_port.py  # Storage port adapter tests.
│   │   ├── test_trust.py  # Trust system tests.
│   │   ├── test_trust_adapter.py  # Trust adapter tests.
│   │   ├── test_trust_two_pass.py  # Two-pass trust tests.
│   │   ├── test_world_kuzu.py  # Kùzu world tests.
│   │   ├── test_world_materialization.py  # Materialization tests.
│   │   ├── test_world_query_column_masking.py  # Column masking tests.
│   │   ├── test_world_query_multibackend.py  # Multi-backend query tests.
│   │   ├── test_world_store.py  # World store tests.
│   │   ├── connectors/  # Connector tests.
│   │   │   ├── conftest.py
│   │   │   ├── test_cache_system.py  # Cache system tests.
│   │   │   ├── test_components_bridge.py  # Components bridge tests.
│   │   │   ├── test_contract_system.py  # Contract system tests.
│   │   │   ├── test_federation.py  # Federation tests.
│   │   │   ├── test_harness.py  # Test harness tests.
│   │   │   ├── test_ingestion_fetch_activity_contract.py  # Ingestion fetch tests.
│   │   │   ├── test_integration.py  # Integration tests.
│   │   │   ├── test_protocol_compliance.py  # Protocol compliance.
│   │   │   ├── test_quality_system.py  # Quality system tests.
│   │   │   ├── test_registry.py  # Registry tests.
│   │   │   ├── test_resilience.py  # Resilience tests.
│   │   │   ├── test_schema_aware_cache.py  # Schema-aware cache tests.
│   │   │   ├── test_schema_system.py  # Schema system tests.
│   │   │   ├── test_transform_pipeline.py  # Transform pipeline tests.
│   │   │   ├── test_type_system.py  # Type system tests.
│   │   │   ├── bindings/  # Binding profile tests.
│   │   │   │   └── test_binding_profiles.py  # Binding profile tests.
│   │   │   ├── profiles/  # Source profile tests.
│   │   │   │   └── test_source_profiles.py  # Source profile tests.
│   │   │   ├── reference/  # Reference connector tests.
│   │   │   │   ├── test_rest_json.py  # REST/JSON tests.
│   │   │   │   ├── test_sdmx.py  # SDMX tests.
│   │   │   │   └── test_static_csv.py  # Static CSV tests.
│   │   │   └── sources/  # Production source connector tests.
│   │   │       ├── test_ckan.py  # CKAN connector tests.
│   │   │       ├── test_http_connector_base.py  # HTTP base tests.
│   │   │       ├── test_http_version_policy.py  # HTTP version policy tests.
│   │   │       ├── test_no_duplicate_http_helpers.py  # No duplicate helpers.
│   │   │       ├── test_opendatasoft.py  # OpenDataSoft connector tests.
│   │   │       ├── test_production_connectors.py  # Production connector tests.
│   │   │       ├── test_sdmx_source.py  # SDMX connector tests.
│   │   │       ├── test_socrata.py  # Socrata connector tests.
│   │   │       ├── test_sparql.py  # SPARQL connector tests.
│   │   │       ├── test_wave1_integration.py  # Wave 1 connector integration tests.
│   │   │       ├── test_wave2_integration.py  # Wave 2 connector integration tests.
│   │   │       └── test_wave3_integration.py  # Wave 3 connector integration tests.
│   │   ├── data_plane/  # Fabric data plane tests.
│   │   │   ├── test_cursor_store.py  # Cursor store tests.
│   │   │   ├── test_incremental.py  # Incremental ingestion tests.
│   │   │   ├── test_orchestrator.py  # Orchestrator tests.
│   │   │   ├── test_record_replay.py  # Record/replay tests.
│   │   │   ├── test_streaming_windowed.py  # Streaming windowed tests.
│   │   │   └── test_watermark.py  # Watermark tracking tests.
│   │   └── pii/  # PII tests.
│   │       └── test_presidio_detector.py  # Presidio PII detector tests.
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
│   │   ├── test_catalog_snapshot.py  # Method catalog snapshot tests.
│   │   ├── test_compile_determinism.py  # Compile determinism.
│   │   ├── test_compile_facade.py  # Compile facade tests.
│   │   ├── test_conflict_detection.py  # Conflict detection tests.
│   │   ├── test_constraints_executor.py  # Constraints executor tests.
│   │   ├── test_cost_model.py  # Cost model tests.
│   │   ├── test_execute_facade_smoke.py  # Execute facade smoke.
│   │   ├── test_execute_input_bindings.py  # Execute input bindings.
│   │   ├── test_execute_requires_input_bindings_ref.py  # Input bindings ref check.
│   │   ├── test_fiscal.py  # Fiscal tests.
│   │   ├── test_global_state.py  # Global state tests.
│   │   ├── test_gradients.py  # Gradient tests.
│   │   ├── test_health.py  # Health check tests.
│   │   ├── test_jit_compilation_tracker.py  # JIT tracker tests.
│   │   ├── test_jit_stability.py  # JIT stability tests.
│   │   ├── test_merge_determinism.py  # Merge determinism tests.
│   │   ├── test_nan_guard.py  # NaN guard tests.
│   │   ├── test_no_compat_facade_imports.py  # No compat facade imports.
│   │   ├── test_no_foundry_domain_imports.py  # No foundry domain imports.
│   │   ├── test_no_io_kernel.py  # No-IO kernel purity.
│   │   ├── test_patch_executor.py  # Patch executor tests.
│   │   ├── test_program_graph_ops.py  # Program graph ops tests.
│   │   ├── test_runtime_batch.py  # Runtime batch tests.
│   │   ├── test_uncertainty_propagation.py  # Uncertainty propagation.
│   │   ├── test_unified_dag_method_nodes.py  # Unified DAG method node tests.
│   │   ├── agent_sim/  # Agent sim tests.
│   │   │   └── test_monitoring.py  # Monitoring tests.
│   │   ├── analysis/  # Analysis tests.
│   │   │   └── test_distributional.py  # Distributional analysis tests.
│   │   ├── methods/  # Method tests.
│   │   │   ├── conftest.py
│   │   │   ├── test_artifacts.py  # Method artifact tests.
│   │   │   ├── test_base.py  # Base method tests.
│   │   │   ├── test_compiler.py  # Method compiler tests.
│   │   │   ├── test_components_bootstrap_adapter.py  # Bootstrap adapter tests.
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
│   │   │       │   ├── test_synthetic_control.py  # Synthetic Control tests.
│   │   │       │   ├── test_synthetic_control_imports.py  # Legacy/canonical import tests.
│   │   │       │   └── test_structural_time_series.py  # STS tests.
│   │   │       ├── econometrics/  # Econometric method tests.
│   │   │       │   ├── test_iv.py  # IV tests.
│   │   │       │   ├── test_panel.py  # Panel data tests.
│   │   │       │   ├── test_protocols.py  # Econometric protocol tests.
│   │   │       │   ├── test_registration.py  # Registration tests.
│   │   │       │   └── test_timeseries.py  # Time series tests.
│   │   │       └── optimization/  # Optimization method tests.
│   │   │           ├── test_methods.py  # Optimization method tests.
│   │   │           ├── test_protocols.py  # Optimization protocol tests.
│   │   │           └── test_registration.py  # Registration tests.
│   │   └── plugins/  # Plugin tests.
│   │       └── test_plugin_system.py  # Plugin system tests.
│   ├── integration/  # Cross-module integration tests.
│   │   └── test_human_gate_audit.py  # Human gate+audit integration.
│   ├── ir/  # IR tests.
│   │   ├── test_canon_hash_parity.py  # Canon hash parity tests.
│   │   ├── test_hte_backtest.py  # HTE+backtest IR tests.
│   │   ├── test_loaders.py  # Loader tests.
│   │   ├── test_no_core_imports.py  # No-core-imports boundary test.
│   │   ├── test_policy_portfolio.py  # Policy portfolio tests.
│   │   ├── test_queries_contracts.py  # Query contract tests.
│   │   ├── test_registry_fragments.py  # Registry fragment tests.
│   │   ├── test_registry_fragments_components.py  # Fragment component tests.
│   │   ├── test_trinity_loaders.py  # Trinity loader tests.
│   │   └── test_uncertainty.py  # Uncertainty IR tests.
│   ├── lex/  # Lex tests.
│   │   ├── batch/  # Lex batch pipeline tests.
│   │   │   ├── test_canonicalizers.py  # Canonicalizer tests.
│   │   │   ├── test_graph_builder_ids.py  # Graph builder ID tests.
│   │   │   ├── test_quality_report.py  # Quality report tests.
│   │   │   ├── test_sharding_config.py  # Sharding configuration tests.
│   │   │   ├── test_spo_extractor_normalization.py  # SPO extractor normalization tests.
│   │   │   └── test_structurer.py  # Structurer tests.
│   │   └── simulator/  # Lex simulator tests.
│   │       ├── test_diff.py  # Norm diff tests.
│   │       ├── test_engine.py  # Simulator engine tests.
│   │       └── test_mutator.py  # Norm mutator tests.
│   ├── lint/  # Lint rule tests.
│   │   └── test_legacy_cutover_lint.py  # Legacy cutover lint tests.
│   ├── performance/  # Performance tests.
│   │   └── test_overhead.py  # Observability overhead SLA.
│   ├── runtime/  # Runtime tests.
│   │   ├── test_replay_input_bindings_completeness.py  # Replay input bindings.
│   │   ├── test_replay_runtime.py  # Replay runtime tests.
│   │   ├── test_runtime_manifest_paths.py  # Manifest path tests.
│   │   └── http/  # HTTP API tests.
│   │       ├── conftest.py
│   │       ├── test_artifact_inspector_api.py  # Artifact inspector API tests.
│   │       ├── test_control_api.py  # Control Plane API tests.
│   │       ├── test_core_only_runs_api.py  # Core-only runs API tests.
│   │       ├── test_debug_api.py  # Debug API tests.
│   │       ├── test_e2e_ingestion.py  # End-to-end data ingestion tests.
│   │       ├── test_insights_api.py  # Insights API tests.
│   │       ├── test_nl_pipeline_materialization.py  # NL pipeline materialization tests.
│   │       ├── test_runs_api.py  # Runs API tests.
│   │       ├── test_runtime_api_authz.py  # Runtime API authorization tests.
│   │       ├── test_runtime_api_contract_hardening.py  # API contract hardening tests.
│   │       ├── test_runtime_api_no_legacy_sources.py  # No legacy sources check.
│   │       └── test_timeline_api.py  # Timeline API tests.
│   └── scientist/  # Scientist tests.
│       ├── conftest.py
│       ├── test_agent_protocols.py  # Agent protocol tests.
│       ├── test_backtesting.py  # Backtesting tests.
│       ├── test_bind_foundry_inputs_node.py  # Foundry input binding node tests.
│       ├── test_causal_evaluation_node.py  # Causal evaluation node.
│       ├── test_checkpoint.py  # Checkpoint tests.
│       ├── test_code_verifier.py  # Code verifier tests.
│       ├── test_code_verifier_security.py  # Code verifier security tests.
│       ├── test_compiler.py  # Compiler tests.
│       ├── test_constitution.py  # Constitution constraint tests.
│       ├── test_critic_factory.py  # Critic factory tests.
│       ├── test_data_plane_gate_node.py  # Data plane gate node tests.
│       ├── test_decision_card.py  # Decision card tests.
│       ├── test_decision_card_uncertainty_render.py  # Uncertainty rendering.
│       ├── test_decision_packet_distributional_econometrics.py  # Distributional+econometrics.
│       ├── test_decision_packet_node_v3.py  # Decision packet v3.
│       ├── test_distributional_analysis_node.py  # Distributional analysis.
│       ├── test_drafter_constitution.py  # Drafter constitution tests.
│       ├── test_engine_default_workflow_e1_7.py  # Default workflow tests.
│       ├── test_engine_default_workflow_p8.py  # Default workflow P8 tests.
│       ├── test_engine_executor_idempotency.py  # Idempotency tests.
│       ├── test_engine_executor_v0.py  # Executor v0 tests.
│       ├── test_engine_registry_v0.py  # Registry v0 tests.
│       ├── test_enrich_knowledge_cache_policy.py  # Knowledge cache policy tests.
│       ├── test_enrich_knowledge_node_freshness.py  # Knowledge freshness tests.
│       ├── test_failure_index.py  # Failure index tests.
│       ├── test_feasibility_probe.py  # Feasibility probe tests.
│       ├── test_idempotency.py  # Idempotency tests.
│       ├── test_informed_critic.py  # Informed critic tests.
│       ├── test_iteration_state_machine.py  # Iteration state machine tests.
│       ├── test_knowledge_base.py  # Knowledge base tests.
│       ├── test_llm_cycle_preflight.py  # LLM cycle preflight tests.
│       ├── test_multipass_drafter.py  # Multi-pass drafter tests.
│       ├── test_node_registry_components_bootstrap.py  # Node registry bootstrap tests.
│       ├── test_norm_loader.py  # Norm loader tests.
│       ├── test_propagate_uncertainty_node.py  # Uncertainty propagation node.
│       ├── test_rag_index.py  # RAG index tests.
│       ├── test_replay_backend.py  # Replay backend tests.
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
│       │   ├── test_pii_check_pass.py  # PII check pass tests.
│       │   ├── test_shared_shims.py  # Shared governance shims tests.
│       │   └── test_validation_pipeline.py  # Validation pipeline tests.
│       ├── integration/  # Scientist integration tests.
│       │   ├── test_checkpoint_resume.py  # Checkpoint+resume tests.
│       │   └── test_workflow_tracing.py  # Workflow tracing tests.
│       └── search/  # Search tests.
│           ├── conftest.py
│           ├── test_adversarial.py  # Adversarial search tests.
│           ├── test_diversity.py  # Diversity selection tests.
│           ├── test_portfolio_search.py  # Portfolio search tests.
│           ├── test_search_loop.py  # Search loop tests.
│           └── strategies/  # Strategy tests.
│               ├── conftest.py
│               ├── test_adapter.py  # Adapter tests.
│               ├── test_bayesian.py  # Bayesian tests.
│               ├── test_controller_batch.py  # Controller batch tests.
│               ├── test_multi_objective.py  # Multi-objective tests.
│               ├── test_random_grid.py  # Random/grid tests.
│               ├── test_resource_arbiter.py  # Resource arbiter tests.
│               └── test_space_codec.py  # Space codec tests.
├── tools/  # Developer tooling.
│   ├── lint/  # Architecture and import linters.
│   │   ├── check_scholar_imports.py  # Scholar import boundary checker.
│   │   ├── collect_arch_metrics.py  # Architecture metrics collector.
│   │   ├── compare_baseline.py  # Baseline metric comparison.
│   │   ├── lint_connector_hardening.py  # Connector hardening linter.
│   │   ├── lint_connectors.py  # Connector Law A/B linter.
│   │   ├── lint_foundry.py  # Foundry purity linter (Law B).
│   │   ├── lint_foundry_data_plane.py  # Foundry data plane linter.
│   │   ├── lint_imports.py  # Architecture import-boundary linter (Law A).
│   │   └── lint_legacy_cutover.py  # Legacy cutover progress linter.
│   ├── diagnostics/  # Diagnostic and schema tools.
│   │   ├── abi_diff.py  # ABI schema diff tool.
│   │   ├── capture_env.py  # Environment reproducibility manifest.
│   │   ├── check_perf_regression.py  # Performance regression checker.
│   │   ├── check_scientist_node_version_bump.py  # Node version bump check.
│   │   ├── check_setup.py  # Setup diagnostics.
│   │   ├── check_state_reads.py  # State read pattern checker.
│   │   ├── check_udf_perf.py  # UDF perf diagnostics.
│   │   ├── gen_schema.py  # JSON Schema snapshot generator.
│   │   ├── generate_ir_schema.py  # IR schema generator.
│   │   ├── scan_fabric.py  # Fabric data contract scanner.
│   │   └── visualize_provenance.py  # Provenance graph visualizer.
│   ├── demos/  # Demo scripts.
│   │   ├── run_export_demo.py  # Export demo.
│   │   ├── run_laffer_demo.py  # Laffer curve demo.
│   │   ├── run_mechanism_design.py  # Differentiable mechanism design demo.
│   │   ├── run_udf_hybrid_demo.py  # UDF hybrid demo.
│   │   └── run_udf_query_demo.py  # UDF query demo.
│   ├── benchmarks/  # Performance benchmarks.
│   │   ├── bench_domain.py  # Domain benchmark.
│   │   └── bench_simulation.py  # Simulation benchmark.
│   ├── connectors/  # Connector tools.
│   │   ├── check_contracts.py  # Connector contract validation.
│   │   └── scaffold.py  # Connector scaffold generator.
│   ├── migrations/  # Migration tools.
│   │   ├── migrate.py  # Migration runner.
│   │   └── migrate_duckdb_to_pg.py  # DuckDB→PostgreSQL migration.
│   └── runtime/  # Runtime tools.
│       ├── archive_legacy_runs.py  # Legacy run archival.
│       ├── check_runtime_api_contract.py  # Runtime API contract validation script.
│       ├── export_runtime_openapi.py  # OpenAPI spec export.
│       ├── generate_runtime_client.py  # TypeScript client generation.
│       └── inventory_legacy_runs.py  # Legacy run inventory.
├── data/  # Data workspace and reference datasets.
│   ├── norms/  # Norm packs (YAML).
│   │   └── sample_norms.yaml  # Sample norm pack.
│   ├── raw/  # Raw input datasets.
│   │   ├── agents.csv  # Agent data.
│   │   ├── interactions.csv  # Interaction data.
│   │   └── macro.csv  # Macroeconomic data.
│   ├── staging/  # ETL intermediate outputs.
│   │   ├── agents.parquet  # Staged agent data.
│   │   ├── interactions.parquet  # Staged interactions.
│   │   └── macro.parquet  # Staged macro data.
│   ├── curated/  # Curated datasets with manifests.
│   │   ├── agents.parquet  # Curated agent data.
│   │   ├── agents_manifest.json  # Agent data manifest.
│   │   ├── data_contracts.json  # Data contract definitions.
│   │   ├── entity_resolution_manifest.json  # Entity resolution manifest.
│   │   ├── interactions.parquet  # Curated interactions.
│   │   ├── interactions_manifest.json  # Interactions manifest.
│   │   ├── macro.parquet  # Curated macro data.
│   │   ├── macro_manifest.json  # Macro data manifest.
│   │   └── udf_schema.json  # UDF schema definitions.
│   └── databases/  # Embedded databases.
│       ├── demo_udf.duckdb  # Demo UDF DuckDB.
│       ├── demo_udf.kuzu  # Demo UDF Kùzu.
│       ├── integration.duckdb  # Integration test DuckDB.
│       ├── simulation.duckdb  # Simulation DuckDB.
│       ├── simulation.kuzu  # Simulation Kùzu.
│       ├── test_macro.duckdb  # Test macro DuckDB.
│       ├── test_udf.duckdb  # Test UDF DuckDB.
│       └── test_udf.kuzu  # Test UDF Kùzu.
├── frontend/  # Frontend applications.
│   ├── runtime-api-client/  # TypeScript API client.
│   │   ├── runtimeApiClient.ts  # TypeScript API client source.
│   │   └── runtimeApiClient.js  # Compiled JavaScript client.
│   ├── runtime-dashboard/  # React 18 + Vite + TailwindCSS monitoring dashboard.
│   │   ├── vite.config.ts  # Vite build configuration.
│   │   ├── tailwind.config.ts  # Tailwind CSS configuration.
│   │   └── src/
│   │       ├── main.tsx  # Application entry point.
│   │       ├── App.tsx  # Root component with routing.
│   │       ├── api/  # API layer.
│   │       │   ├── client.ts  # API client configuration.
│   │       │   ├── http.ts  # HTTP utilities.
│   │       │   ├── queryClient.ts  # React Query client configuration.
│   │       │   ├── queryKeys.ts  # Query key constants.
│   │       │   ├── types.ts  # Generated TypeScript types from OpenAPI.
│   │       │   ├── validators.ts  # Zod validators for API responses.
│   │       │   └── hooks/  # React Query hooks.
│   │       │       ├── useArtifactContent.ts  # Artifact content fetching.
│   │       │       ├── useArtifactLineage.ts  # Artifact lineage graph.
│   │       │       ├── useArtifactManifest.ts  # Artifact manifest fetching.
│   │       │       ├── useArtifactSchema.ts  # Artifact schema fetching.
│   │       │       ├── useCacheStatus.ts  # Cache status query.
│   │       │       ├── useConnectors.ts  # Connector listing.
│   │       │       ├── useDataCatalogSearch.ts  # Data catalog search.
│   │       │       ├── useDataIndexStats.ts  # Data index statistics.
│   │       │       ├── useDataPromotionCandidates.ts  # Data promotion candidates.
│   │       │       ├── useDiscoverDataSources.ts  # Data source discovery.
│   │       │       ├── useGovernanceDebug.ts  # Governance debug info.
│   │       │       ├── useHealth.ts  # Health check query.
│   │       │       ├── useIngestData.ts  # Data ingestion mutation.
│   │       │       ├── useLaunchNlRun.ts  # Natural language run launch.
│   │       │       ├── useLaunchRun.ts  # Policy run launch mutation.
│   │       │       ├── useLexGraphStats.ts  # Lex knowledge graph statistics.
│   │       │       ├── useLexPipelineStatus.ts  # Lex pipeline status query.
│   │       │       ├── useLexSearch.ts  # Lex knowledge graph search.
│   │       │       ├── useLexTrigger.ts  # Lex pipeline trigger mutation.
│   │       │       ├── useLlmProfiles.ts  # LLM profile listing.
│   │       │       ├── useNodeDebug.ts  # Node debug info.
│   │       │       ├── usePreviewFetchPlan.ts  # Fetch plan preview.
│   │       │       ├── usePromotionDecision.ts  # Promotion decision mutation.
│   │       │       ├── useResolveDataNeeds.ts  # Data needs resolution.
│   │       │       ├── useRunAgents.ts  # Run agent details.
│   │       │       ├── useRunDetails.ts  # Run detail fetching.
│   │       │       ├── useRunErrors.ts  # Run error fetching.
│   │       │       ├── useRunLineage.ts  # Run lineage graph.
│   │       │       ├── useRunNodes.ts  # Run node listing.
│   │       │       ├── useRunTimeline.ts  # Run timeline events.
│   │       │       ├── useRunWorkflow.ts  # Run workflow state.
│   │       │       ├── useRuns.ts  # Run listing query.
│   │       │       └── useSourceProfiles.ts  # Source profile listing.
│   │       ├── components/  # UI components.
│   │       │   ├── agents/
│   │       │   │   └── AgentPipelinePanel.tsx  # Agent pipeline visualization.
│   │       │   ├── data/
│   │       │   │   └── DataIntelligencePanel.tsx  # Data analysis and recommendations.
│   │       │   ├── debug/
│   │       │   │   ├── ErrorsPanel.tsx  # Error display panel.
│   │       │   │   └── NodeDebugPanel.tsx  # Node debug inspection.
│   │       │   ├── decision/
│   │       │   │   └── DecisionCardView.tsx  # Decision card display.
│   │       │   ├── governance/
│   │       │   │   └── GovernanceReport.tsx  # Governance report view.
│   │       │   ├── layout/
│   │       │   │   ├── Header.tsx  # Application header.
│   │       │   │   ├── Shell.tsx  # Application shell layout.
│   │       │   │   └── Sidebar.tsx  # Navigation sidebar.
│   │       │   ├── shared/
│   │       │   │   ├── ApiErrorAlert.tsx  # API error display.
│   │       │   │   ├── EmptyState.tsx  # Empty state placeholder.
│   │       │   │   ├── JsonPreview.tsx  # JSON data preview.
│   │       │   │   ├── LineageGraph.tsx  # Lineage graph visualization.
│   │       │   │   └── StatusBadge.tsx  # Status indicator badge.
│   │       │   ├── simulation/
│   │       │   │   ├── CalibrationReport.tsx  # Calibration report view.
│   │       │   │   ├── DistributionalPanel.tsx  # Distributional analysis panel.
│   │       │   │   ├── MetricsPanel.tsx  # Simulation metrics display.
│   │       │   │   ├── SimulationResultsViewer.tsx  # Simulation results.
│   │       │   │   └── UncertaintyOverlay.tsx  # Uncertainty visualization overlay.
│   │       │   ├── trinity/
│   │       │   │   ├── InterventionDetail.tsx  # Intervention detail view.
│   │       │   │   ├── TrinityCard.tsx  # Trinity artifact card.
│   │       │   │   └── TrinityDiff.tsx  # Trinity diff visualization.
│   │       │   ├── ui/
│   │       │   │   └── card.tsx  # Reusable card component.
│   │       │   └── workflow/
│   │       │       └── WorkflowDagPanel.tsx  # Workflow DAG visualization.
│   │       ├── lib/  # Shared utilities.
│   │       │   ├── constants.ts  # Application constants.
│   │       │   ├── parsing.ts  # Data parsing utilities.
│   │       │   ├── utils.ts  # General utility functions.
│   │       │   └── domain/  # Domain logic.
│   │       │       ├── agents.ts  # Agent-related utilities.
│   │       │       ├── decision.ts  # Decision domain logic.
│   │       │       ├── governance.ts  # Governance domain logic.
│   │       │       ├── simulation.ts  # Simulation domain logic.
│   │       │       ├── trinity.ts  # Trinity domain logic.
│   │       │       └── workflow.ts  # Workflow domain logic.
│   │       └── pages/  # Route pages.
│   │           ├── ArtifactInspector.tsx  # Artifact inspection page.
│   │           ├── Dashboard.tsx  # Main dashboard page.
│   │           ├── DataManagement.tsx  # Data management page.
│   │           ├── LaunchRun.tsx  # Run launch page.
│   │           ├── LexKnowledgeGraph.tsx  # Knowledge graph visualization page.
│   │           ├── RunDetail.tsx  # Run detail page.
│   │           ├── RunsList.tsx  # Runs list page.
│   │           ├── SourcesManagement.tsx  # Source profile management page.
│   │           └── SystemHealth.tsx  # System health page.
│   └── runtime-reference-shell/  # Reference UI shell.
│       ├── index.html  # Shell HTML entry point.
│       ├── app.js  # Shell application logic.
│       └── styles.css  # Shell styles.
├── pyproject.toml  # Project metadata, deps, tool config.
├── import_policy.toml  # Architecture import-boundary rules (Law A).
├── import_exceptions.toml  # Temporary import gate exceptions.
└── (root files)
    ├── architecture.md  # This document.
    ├── arch_cycles_register.csv  # Architecture cycle tracking register.
    ├── import_debt_register.csv  # Import debt tracking register.
    ├── import_exceptions_registry.md  # Import exceptions documentation.
    ├── freeze_policy.md  # API freeze policy documentation.
    ├── jax_bootstrap.py  # JAX environment defaults.
    ├── migrate.py  # Schema migration CLI.
    ├── install.sh  # Bootstrap installer.
    ├── env_example.txt  # Environment variables template.
    ├── uv.lock  # Locked dependency graph.
    ├── Dockerfile.reproducible  # Reproducible container build.
    ├── .pre-commit-config.yaml  # Pre-commit hooks.
    └── .gitignore  # Git ignore rules.
```
