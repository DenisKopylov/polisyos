# ADRs By Topic

> Generated from `docs/adr/index.toml`; use this as the topic navigation surface.

## Topic Summary

| Topic | Description | Count |
| --- | --- | --- |
| `repository-structure` | Repository topology, package layout, import boundaries, docs governance, and workspace hygiene. | 32 |
| `observation` | Observability, causal evidence, scientist workflows, measurement, confidence, and validity. | 49 |
| `security` | Tenant isolation, signing, secrets, trust stores, and other security controls. | 4 |
| `runtime-state` | Runtime state, replay, idempotency, CAS, snapshots, persistence, and lifecycle behavior. | 20 |
| `schemas` | IR, API, schema, serialization, registry, metadata, and compatibility contracts. | 16 |
| `testing` | Test topology, fixtures, golden data, drift checks, and reproducibility gates. | 4 |
| `release` | Release trains, SemVer, versioning, deprecation, migration, and retraction policy. | 6 |
| `frontend` | Frontend workspace, dashboard, UI language, themes, and authored text surfaces. | 5 |
| `product-domain` | Domain-level Foundry, Fabric, Lex, Data Forge, synthetic-world, and product concepts. | 50 |

## Topic Index

### repository-structure

| ADR | Status | Package | Title | Related |
| --- | --- | --- | --- | --- |
| [0004](0004-architecture-boundaries-import-gate.md) | `accepted` | `repository` | Architecture Boundaries Import Gate | 0115, 0127 |
| [0053](0053-architecture-freeze-contracts.md) | `proposed` | `repository` | Architecture Freeze at Assembly Points | - |
| [0065](0065-cycle-breaking-time-lag-conversion.md) | `proposed` | `repository` | Cycle breaking via time-lag conversion (not edge deletion) | - |
| [0077](0077-rustworkx-tight-loop-algorithms.md) | `proposed` | `repository` | rustworkx for in-memory tight-loop algorithms (cycle breaking, resolution loop) | - |
| [0096](0096-canonical-product-root-and-workspace-boundary.md) | `accepted` | `repository` | Canonical Product Root and Workspace Boundary | - |
| [0111](0111-workspace-root-boundary-sota-contract.md) | `proposed` | `repository` | Workspace Root Boundary as a SOTA Contract | - |
| [0115](0115-layered-architecture-enforcement.md) | `proposed` | `repository` | Layered Architecture Enforcement | 0004, 0061, 0111, 0121 |
| [0119](0119-frontend-monorepo-workspace.md) | `proposed` | `frontend` | JavaScript Monorepo Workspace | - |
| [0120](0120-test-topology-mirror.md) | `proposed` | `repository` | Test Topology Mirror | - |
| [0126](0126-docs-lifecycle-diataxis-plans-archive.md) | `proposed` | `repository` | Docs Lifecycle via Diataxis and Plan Buckets | 0096, 0111, 0115 |
| [0127](0127-repo-hygiene-gates.md) | `proposed` | `repository` | Repository Hygiene Gates | 0004, 0115, 0118, 0126 |
| [0146](0146-product-root-decision.md) | `accepted` | `repository` | Product Root Decision | 0096, 0111, RSR-0130, RSR-0131 |
| [RSR-0129](repository-structure-0129-empty-placeholder-package-policy.md) | `proposed` | `repository` | Empty Placeholder Package Policy | 0127, RSR-0136 |
| [RSR-0130](repository-structure-0130-workspace-boundary.md) | `accepted` | `repository` | Workspace Boundary | 0096, 0111 |
| [RSR-0131](repository-structure-0131-build-cache-umbrella.md) | `proposed` | `repository` | Build Output and Cache Umbrella | 0127 |
| [RSR-0132](repository-structure-0132-architecture-governance-source.md) | `proposed` | `repository` | Architecture as Single Governance Source | 0004, 0115 |
| [RSR-0133](repository-structure-0133-package-layout-budget.md) | `proposed` | `repository` | Top-Level Package Size Budget and Facade Pattern | 0127 |
| [RSR-0134](repository-structure-0134-cross-package-name-registry.md) | `proposed` | `repository` | Cross-Package Shared Name Registry | 0115 |
| [RSR-0135](repository-structure-0135-versioning-out-of-package-names.md) | `accepted` | `repository` | Versioning Out of Package Names And Compatibility Contracts | 0118 |
| [RSR-0136](repository-structure-0136-foundry-methods-flat-vs-catalog.md) | `accepted` | `polisyos.foundry` | Foundry Methods Flat vs Catalog | RSR-0129 |
| [RSR-0137](repository-structure-0137-production-data-fixtures.md) | `accepted` | `repository` | Production Data and Fixtures Classification | 0123 |
| [RSR-0138](repository-structure-0138-synthetic-world-agent-sim.md) | `accepted` | `polisyos.fabric` | Synthetic World and Agent Sim Merge Direction | RSR-0134 |
| [RSR-0139](repository-structure-0139-calibration-canonical-home.md) | `accepted` | `repository` | Canonical Home for Calibration | RSR-0134 |
| [RSR-0140](repository-structure-0140-pickle-checkpoint-compatibility.md) | `accepted` | `repository` | Pickle and Checkpoint Compatibility Safety Net | - |
| [RSR-0141](repository-structure-0141-dynamic-import-registry.md) | `accepted` | `repository` | Dynamic Import Registry | - |
| [RSR-0142](repository-structure-0142-libcst-module-move-codemod.md) | `accepted` | `repository` | LibCST Module Move Codemod | - |
| [RSR-0143](repository-structure-0143-decomposition-blueprint-contract.md) | `accepted` | `repository` | Decomposition Blueprint Contract | - |
| [RSR-0144](repository-structure-0144-jax-pydantic-registration-reexport-shims.md) | `accepted` | `repository` | JAX/Pydantic Registrations and Re-export Shim Shape | - |
| [RSR-0145](repository-structure-0145-import-cycle-baseline.md) | `accepted` | `repository` | Import Cycle Baseline | - |
| [RSR-0146](repository-structure-0146-foundry-execute-executor-naming.md) | `accepted` | `polisyos.foundry` | Foundry Execute/Executor Naming Boundary | - |
| [RSR-0147](repository-structure-0147-data-root-local-state-naming.md) | `accepted` | `repository` | Data Root Local State Naming | 0146, RSR-0131, RSR-0137 |
| [RSR-0148](repository-structure-0148-cross-cutting-concern-canonical-homes.md) | `accepted` | `repository` | Cross-Cutting Concern Canonical Homes | 0116, RSR-0134, RSR-0139 |

### observation

| ADR | Status | Package | Title | Related |
| --- | --- | --- | --- | --- |
| [0002](0002-scientist-flow-nodes-only.md) | `accepted` | `polisyos.scientist` | Сводим Scientist на flow_nodes-only | - |
| [0006](0006-slo-definitions.md) | `accepted` | `polisyos.scientist` | SLO Definitions for Scientist DAG | 0116, 0127 |
| [0009](0009-decision-packet-replay-protocol.md) | `proposed` | `polisyos.scientist` | DecisionPacket Replay Protocol | - |
| [0011](0011-scientist-checkpoint-resume.md) | `accepted` | `polisyos.scientist` | Scientist DAG Checkpoint/Resume | - |
| [0013](0013-uncertainty-propagation-pipeline.md) | `accepted` | `repository` | Uncertainty Propagation Pipeline | 0012 |
| [0025](0025-scm-structural-causal-model-vs-synthetic-control.md) | `accepted` | `repository` | SCM Terminology Split (Structural Causal Model vs Synthetic Control) | - |
| [0026](0026-notears-excluded-from-default-discovery.md) | `accepted` | `repository` | Exclude NOTEARS from Default Causal Discovery Stack | - |
| [0028](0028-refutation-mandatory-for-observational-estimates.md) | `accepted` | `repository` | Refutation Mandatory for Observational DoWhy Estimates | - |
| [0029](0029-e-value-ate-rr-conversion-strategy.md) | `accepted` | `repository` | E-Value ATE-to-Risk-Ratio Conversion Strategy | - |
| [0031](0031-block-bootstrap-for-time-series-stability.md) | `proposed` | `repository` | Block Bootstrap for Time-Series Causal Discovery Stability | - |
| [0034](0034-simplified-tr-backdoor-only.md) | `proposed` | `repository` | Simplified Transportability -- Backdoor-Only (Phase 12a) | - |
| [0041](0041-confidence-aggregation-quality-score-replication-bonus.md) | `proposed` | `repository` | Confidence Aggregation via Quality Score and Replication Bonus | - |
| [0044](0044-literature-first-single-reconciliation-strategy.md) | `proposed` | `repository` | Literature-First as the Single Reconciliation Strategy | - |
| [0045](0045-causal-edge-combined-confidence-formula-superseded.md) | `superseded` | `repository` | Causal Edge Combined Confidence Formula (Superseded) | 0064 |
| [0046](0046-three-graph-closure-transportability.md) | `proposed` | `repository` | Three-Graph Closure for Transportability | - |
| [0047](0047-graph-federation-cross-references.md) | `proposed` | `repository` | Graph Federation with Cross-References | - |
| [0048](0048-transportability-resolution-loop-max-3-rounds.md) | `proposed` | `repository` | Transportability Resolution Loop with Max 3 Rounds | - |
| [0050](0050-context-dependent-proxy-penalties.md) | `proposed` | `repository` | Context-Dependent Proxy Penalties | - |
| [0059](0059-scientist-causal-full-parallel-workflow.md) | `proposed` | `polisyos.scientist` | scientist_causal_full parallel with scientist_default, single cutover | - |
| [0064](0064-compute-combined-confidence-noisy-or.md) | `proposed` | `repository` | compute_combined_confidence() = 1 - Prod(1-conf_i)^w_i (Noisy-OR) | - |
| [0066](0066-pag-dag-projection-u-dummy-nodes.md) | `proposed` | `repository` | PAG to DAG projection: bidirectional edges to U-dummy nodes for dowhy.gcm | - |
| [0067](0067-multiplicative-confidence-penalties.md) | `proposed` | `repository` | Multiplicative confidence penalties Prod(1-p_i) instead of additive | - |
| [0069](0069-collider-check-s-node-elimination.md) | `proposed` | `polisyos.scientist` | Collider (selection bias) check in \_try_eliminate_s_node_simplified | - |
| [0070](0070-bidirectional-edge-u-node-backdoor-invalid.md) | `proposed` | `polisyos.scientist` | Bidirectional edge (U-node) implies backdoor invalid, needs_advanced_tr | - |
| [0073](0073-rustworkx-instead-of-networkx.md) | `proposed` | `repository` | rustworkx instead of NetworkX for graph computations (Phases 0/9/12) | - |
| [0075](0075-econml-cate-heterogeneous-effects.md) | `proposed` | `repository` | EconML/CATE: heterogeneous effects via DML, Causal Forests (Phases 2/11) | - |
| [0080](0080-tech-consolidation-stack.md) | `proposed` | `repository` | Tech consolidation stack for causal inference, discovery, and graphs | - |
| [0083](0083-resolution-loop-proxy-depth-guard.md) | `proposed` | `repository` | Resolution Loop proxy-depth guard: proxy variables don't generate new S-nodes | - |
| [0085](0085-pag-identification-conservative-policy.md) | `proposed` | `repository` | PAG to Identification: CONSERVATIVE policy (identify iff identifiable in all DAGs in PAG) | - |
| [0086](0086-sutva-assumption-check-pass.md) | `proposed` | `repository` | SUTVA Assumption Check Pass | - |
| [0089](0089-pre-implementation-survey-tr-scope.md) | `proposed` | `repository` | Pre-Implementation Survey for Simplified TR Scope Validation | - |
| [0090](0090-formal-proxy-validity-conditions.md) | `proposed` | `repository` | Formal Proxy Validity Conditions | - |
| [0091](0091-partial-identification-manski-bounds.md) | `proposed` | `repository` | Partial Identification Bounds as Fallback for Non-Transportable Results | - |
| [0092](0092-harmonic-mean-confidence-composition.md) | `proposed` | `repository` | Harmonic Mean for Confidence Composition in Proxy Chains | - |
| [0093](0093-dynamic-transportability-time-stationarity.md) | `proposed` | `repository` | Dynamic Transportability with Time-Stationarity Flag | - |
| [0094](0094-confidence-ordinal-quality-score.md) | `proposed` | `repository` | Confidence as Ordinal Quality Score | - |
| [0116](0116-observability-otel-first.md) | `proposed` | `repository` | OTel-First Observability | 0006, 0101, 0122, 0123 |
| [0129](0129-scientist-claim-ledger.md) | `accepted` | `polisyos.scientist` | Scientist Claim Ledger Boundary | - |
| [0130](0130-scientist-research-dag.md) | `accepted` | `polisyos.scientist` | Scientist Research DAG Boundary | - |
| [0131](0131-scientist-readiness-ladder.md) | `accepted` | `polisyos.scientist` | Scientist Readiness Ladder Boundary | - |
| [0132](0132-scientist-voi-compute-law.md) | `accepted` | `polisyos.scientist` | Scientist VOI Compute Law | - |
| [0153](0153-diagnostic-slos-assurance-case-and-attestation.md) | `accepted` | `repository` | Diagnostic SLOs, Assurance Case, And Attestation | 0006, 0010, 0116, 0128, 0147, 0148, 0149, 0150, 0151, 0152 |
| [0160](0160-evidence-portfolio-independence-multiverse-synthesis.md) | `accepted` | `repository` | Evidence Portfolio, Independence Map, Multiverse, And Synthesis | 0020, 0028, 0041, 0129, 0152, 0156, 0159, 0161 |
| [0164](0164-run-cost-proportionality-evidence-budget-governance.md) | `accepted` | `repository` | Run Cost, Proportionality, And Evidence Budget Governance | 0150, 0156, 0157, 0160, 0161, 0163, 0165 |
| [0166](0166-evidence-acquisition-decision-boundaries.md) | `accepted` | `repository` | Evidence Acquisition Decision Boundaries | 0052, 0132, 0147, 0150, 0152, 0156, 0157, 0159, 0160, 0163, 0164 |
| [0171](0171-review-effectiveness-telemetry-advisory-first.md) | `accepted` | `polisyos.runtime` | Review Effectiveness Telemetry Advisory First | 0147, 0150, 0154, 0156, 0162, 0163, 0164, 0165 |
| [0172](0172-balanced-memory-influence-ledger.md) | `accepted` | `repository` | Balanced Memory Influence Ledger | - |
| [0173](0173-obligation-frontier-and-bundle-control.md) | `accepted` | `repository` | Obligation Frontier And Bundle Control | - |
| [0174](0174-policy-evidence-capability-graph.md) | `accepted` | `repository` | Policy Evidence Capability Graph | 0147, 0152, 0156, 0158, 0159, 0160, 0166, 0168, 0172, 0173 |

### security

| ADR | Status | Package | Title | Related |
| --- | --- | --- | --- | --- |
| [0010](0010-cas-artifact-signing-ed25519.md) | `accepted` | `repository` | CAS Artifact Signing (Ed25519) | 0118, 0122, 0123 |
| [0023](0023-cell-based-tenant-isolation.md) | `accepted` | `repository` | Cell-Based Tenant Isolation Foundation | - |
| [0102](0102-key-rotation-lifecycle-and-trust-store-policy.md) | `accepted` | `repository` | Key Rotation Lifecycle and Trust Store Policy | - |
| [0117](0117-secret-backend-protocol.md) | `proposed` | `repository` | Secret Backend Protocol | - |

### runtime-state

| ADR | Status | Package | Title | Related |
| --- | --- | --- | --- | --- |
| [0008](0008-scientist-node-idempotency-contract.md) | `accepted` | `polisyos.scientist` | Scientist Node Idempotency Contract | - |
| [0097](0097-runtime-rate-limiting-and-idempotency.md) | `accepted` | `polisyos.runtime` | Runtime Rate Limiting and Idempotency | - |
| [0098](0098-cas-abstraction-boundary.md) | `accepted` | `polisyos.runtime` | CAS Abstraction Boundary for Runtime Services | - |
| [0099](0099-runtime-lifecycle-and-di-container.md) | `accepted` | `polisyos.runtime` | Runtime Lifecycle and Dependency-Injection Container | - |
| [0101](0101-runtime-audit-trail-model.md) | `accepted` | `polisyos.runtime` | Runtime Audit Trail Model | - |
| [0103](0103-async-cas-adapter-roadmap.md) | `accepted` | `repository` | Async CAS Adapter Roadmap | - |
| [0104](0104-ir-canonical-cas-policy.md) | `accepted` | `polisyos.ir` | IR Canonical JSON and CAS Hash Policy | - |
| [0147](0147-production-evidence-authority-ordering.md) | `accepted` | `repository` | Production Evidence Authority Ordering | 0010, 0098, 0101, 0104, 0123, 0148, 0149, 0150, ADR-043 |
| [0148](0148-serious-run-state-machine-and-phase-barriers.md) | `accepted` | `polisyos.runtime` | Serious Run State Machine And Phase Barriers | 0008, 0009, 0097, 0099, 0101, 0147, 0149, 0150 |
| [0149](0149-effective-mode-and-fallback-degradation-ledger.md) | `accepted` | `polisyos.runtime` | Effective Mode And Fallback Degradation Ledger | 0097, 0101, 0116, 0147, 0148, 0150, RSR-0137 |
| [0150](0150-scorecard-readiness-approval-projection-boundaries.md) | `accepted` | `polisyos.runtime` | Scorecard, Readiness, Approval, And Projection Boundaries | 0007, 0099, 0100, 0101, 0147, 0148, 0149, ADR-043, ADR-044 |
| [0154](0154-diagnostic-event-envelope-and-runtime-log-contract.md) | `accepted` | `polisyos.runtime` | Diagnostic Event Envelope And Runtime Log Contract | 0097, 0101, 0116, 0124, 0147, 0148, 0149, 0150, 0151, 0153 |
| [0155](0155-production-invariant-registry-and-ownership-contract.md) | `accepted` | `repository` | Production Invariant Registry And Ownership Contract | 0147, 0148, 0149, 0150, 0151, 0152, 0153, 0154 |
| [0156](0156-policy-design-case-runtime-quality-assurance-profile.md) | `accepted` | `polisyos.runtime` | Policy Design Case Runtime Quality Assurance Profile | 0147, 0150, 0152, 0153, 0155, 0157, 0161 |
| [0162](0162-human-oversight-publication-external-audit-authority.md) | `accepted` | `repository` | Human Oversight, Publication, And External Audit Authority | 0147, 0150, 0153, 0154, 0156, 0157, 0161, 0163 |
| [0163](0163-lifecycle-ddm-ex-post-calibration.md) | `accepted` | `repository` | Lifecycle, DDM, Ex-Post Outcomes, And Calibration | 0149, 0150, 0154, 0156, 0160, 0161, 0162, 0164 |
| [0169](0169-bounded-liveness-and-runtime-escalation.md) | `accepted` | `polisyos.runtime` | Bounded Liveness And Runtime Escalation | 0006, 0011, 0097, 0148, 0153, 0154, 0156, 0164, 0165, 0166 |
| [0170](0170-contestability-and-recourse-boundaries.md) | `accepted` | `repository` | Contestability And Recourse Boundaries | 0147, 0150, 0153, 0156, 0157, 0162, 0163, 0166 |
| [0175](0175-layer3-grounding-subordination-discipline.md) | `accepted` | `polisyos.runtime` | Layer 3 Grounding Subordination Discipline | 0156, 0173, 0174 |
| [ADR-004](ADR-004-policy-surface-removal.md) | `completed` | `polisyos.ir` | Trinity-Only IR Runtime | - |

### schemas

| ADR | Status | Package | Title | Related |
| --- | --- | --- | --- | --- |
| [0003](0003-ir-v1-deprecate-remove.md) | `accepted` | `polisyos.ir` | IR v1.0 → deprecate → remove | - |
| [0007](0007-human-gate-protocol.md) | `accepted` | `polisyos.ir` | Human Gate Protocol in IR | - |
| [0012](0012-uncertainty-envelope-ir-contract.md) | `accepted` | `polisyos.ir` | UncertaintyEnvelope IR Contract | - |
| [0022](0022-policy-portfolio-ir-extension.md) | `accepted` | `polisyos.ir` | PolicyPortfolio IR Extension | - |
| [0033](0033-json-serializable-mechanism-families-only.md) | `proposed` | `repository` | JSON-Serializable Mechanism Families Only | - |
| [0040](0040-max-transport-confidence-evidence-weight.md) | `proposed` | `polisyos.ir` | Parameter Selection by Max Transport Confidence x Evidence Weight | - |
| [0049](0049-constraint-severity-hard-blocks-transport.md) | `proposed` | `polisyos.ir` | Constraint Severity -- HARD Blocks Transportability | - |
| [0058](0058-compatibility-policy-additive-changes-only.md) | `proposed` | `polisyos.ir` | Only additive schema changes (1.0 to 1.1), dual-read migration | - |
| [0105](0105-trinity-linking-validation-policy.md) | `accepted` | `polisyos.ir` | Trinity Linking, Dependency Ordering, and Validation Containment | - |
| [0106](0106-ir-shared-validation-and-id-policy.md) | `accepted` | `polisyos.ir` | IR Shared Validation Toolkit and Identifier Policy | - |
| [0107](0107-ir-analytics-normalization-and-schema-compatibility.md) | `accepted` | `polisyos.ir` | IR Analytics Normalization and Schema Compatibility Policy | - |
| [0108](0108-ir-schema-catalog-and-reflection.md) | `accepted` | `polisyos.ir` | IR Schema Catalog and Reflection API | 0005, 0104, 0107 |
| [0109](0109-ir-transport-and-interoperability-bridges.md) | `accepted` | `polisyos.ir` | IR Transport and Interoperability Bridges | 0005, 0098, 0104, 0108 |
| [0110](0110-ir-frontier-governance-and-causal-contracts.md) | `accepted` | `polisyos.ir` | Ir Frontier Governance And Causal Contracts | - |
| [0114](0114-schema-registry-and-evolution.md) | `proposed` | `polisyos.ir` | Schema Registry and Evolution Rules | 0005, 0108, 0118, 0122, 0123 |
| [0151](0151-evidence-schema-compatibility-and-legacy-quarantine.md) | `accepted` | `repository` | Evidence Schema Compatibility And Legacy Quarantine | 0005, 0108, 0114, 0123, 0147, 0148, 0150 |

### testing

| ADR | Status | Package | Title | Related |
| --- | --- | --- | --- | --- |
| [0020](0020-robustness-sensitivity-stress.md) | `proposed` | `repository` | Robustness Modes (Sensitivity + Stress Test) (Phase 13) | - |
| [0095](0095-canonical-scm-test-fixtures.md) | `proposed` | `repository` | Canonical SCM Test Fixtures | - |
| [0128](0128-hermetic-reproducibility.md) | `proposed` | `repository` | Hermetic Reproducibility | 0010, 0118, 0122, 0123 |
| [0165](0165-formal-policy-case-substrate-invariant-specs.md) | `accepted` | `repository` | Formal Policy Case And Substrate Invariant Specs | 0147, 0148, 0149, 0150, 0151, 0152, 0153, 0154, 0155, 0156, 0162, 0163, 0164 |

### release

| ADR | Status | Package | Title | Related |
| --- | --- | --- | --- | --- |
| [0005](0005-abi-schema-gate-versioning.md) | `accepted` | `polisyos.ir` | ABI Versioning Gate via JSON Schema Snapshots | 0114, 0123 |
| [0043](0043-skg-versioning-retraction-handling.md) | `proposed` | `polisyos.data_forge` | SKG Versioning and Retraction Handling | - |
| [0060](0060-migration-budget-one-controlled-switch.md) | `proposed` | `repository` | Migration Budget = 1: single controlled switch, no feature flags | - |
| [0100](0100-runtime-api-versioning-and-deprecation-policy.md) | `accepted` | `polisyos.runtime` | Runtime API Versioning and Deprecation Policy | - |
| [0118](0118-release-train-and-semver-contracts.md) | `proposed` | `repository` | Release Train and SemVer Contracts | 0010, 0114, 0123 |
| [0124](0124-llm-idempotency-and-prompt-versioning.md) | `proposed` | `polisyos.runtime` | LLM Idempotency and Prompt Versioning | 0032, 0035, 0097 |

### frontend

| ADR | Status | Package | Title | Related |
| --- | --- | --- | --- | --- |
| [ADR-042](ADR-042-janus-atlas-dual-brand.md) | `approved` | `frontend` | Janus-Atlas Dual Brand | ADR-045, ADR-046 |
| [ADR-044](ADR-044-time-as-primitive.md) | `approved` | `repository` | Time as a UI Primitive | 0122, ADR-043 |
| [ADR-045](ADR-045-glyph-alphabet-limit-10.md) | `approved` | `frontend` | Closed Glyph Alphabet — Ten Radicals | ADR-042, ADR-046 |
| [ADR-046](ADR-046-authored-text-registry.md) | `approved` | `repository` | Authored Text Registry | ADR-042, ADR-043 |
| [ADR-047](ADR-047-atlas-v4-dark-theme-canonicalization.md) | `approved` | `frontend` | Atlas v4 dark theme canonicalization | - |

### product-domain

| ADR | Status | Package | Title | Related |
| --- | --- | --- | --- | --- |
| [0001](0001-remove-legacy-foundry-engine.md) | `accepted` | `polisyos.foundry` | Удаляем legacy Foundry engine | - |
| [0015](0015-knowledge-bundle-freshness-protocol.md) | `accepted` | `polisyos.data_forge` | KnowledgeBundle Freshness Protocol | - |
| [0018](0018-causal-estimator-protocol.md) | `proposed` | `polisyos.foundry` | Causal Estimator Protocol (Phase 12) | - |
| [0019](0019-lex-norm-impact-analysis.md) | `proposed` | `polisyos.lex` | Lex Norm Impact Analysis API (Phase 13) | - |
| [0021](0021-connector-schema-contracts-and-storage-port.md) | `accepted` | `polisyos.fabric` | Connector Schema Contracts And Storage Port | - |
| [0027](0027-dowhy-primary-graph-identify-estimate.md) | `accepted` | `polisyos.foundry` | DoWhy as Primary Graph-Based Identify/Estimate Method | - |
| [0030](0030-causal-graph-model-ir-artifact.md) | `accepted` | `polisyos.ir` | CausalGraphModel as IR Artifact (DAG / CPDAG / PAG) | - |
| [0032](0032-llm-as-context-interpreter-not-structure-source.md) | `proposed` | `repository` | LLM as Context Interpreter, Not Structural Source | - |
| [0035](0035-two-step-screening-haiku-sonnet.md) | `proposed` | `repository` | Two-Step Article Screening (Haiku / Sonnet) | - |
| [0036](0036-variable-canonizer-hierarchical-names.md) | `proposed` | `repository` | Variable Canonizer with Hierarchical Names | - |
| [0037](0037-law-l-edges-without-evidence-support.md) | `proposed` | `polisyos.lex` | Law L -- Edges Without Evidence Support | - |
| [0038](0038-law-t-transportability-required.md) | `proposed` | `polisyos.lex` | Law T -- Transportability Required for External Estimates | - |
| [0039](0039-context-profile-distance-inference-level.md) | `proposed` | `repository` | Context Profile Distance and Inference Level | - |
| [0042](0042-duckdb-for-skg-storage.md) | `proposed` | `polisyos.data_forge` | DuckDB for SKG Storage | - |
| [0051](0051-legal-to-dag-mapping-types.md) | `proposed` | `polisyos.lex` | Legal-to-DAG Mapping Types | - |
| [0052](0052-data-gap-first-class-object.md) | `proposed` | `repository` | DataGap as a First-Class Object | - |
| [0054](0054-skg-on-academic-module.md) | `proposed` | `polisyos.data_forge` | SKG Built on the Academic Module | - |
| [0055](0055-dataset-graph-on-datasets-module.md) | `proposed` | `polisyos.data_forge` | Dataset Graph Built on the Datasets Module | - |
| [0056](0056-wgi-wdi-fabric-connector-wvs-new.md) | `proposed` | `polisyos.fabric` | WGI/WDI via fabric WorldBankConnector, WVS as new fabric connector | - |
| [0057](0057-legal-bridge-via-lex-api.md) | `proposed` | `polisyos.lex` | Legal bridge via lex/api.py, not separate legal_graph/ module | - |
| [0061](0061-import-gate-ci-contract.md) | `proposed` | `polisyos.foundry` | Import gate as CI contract (lint_foundry.py --strict on every PR) | - |
| [0062](0062-knowledge-snapshot-id-mandatory-input-ref.md) | `proposed` | `polisyos.data_forge` | knowledge_snapshot_id + mandatory InputRef for lineage sync | - |
| [0063](0063-mediator-conditional-covariate-marginal.md) | `proposed` | `repository` | Mediator P*(z|x) conditional; covariate P*(z) marginal (Pearl & Bareinboim 2011) | - |
| [0068](0068-wvs-wave-temporal-matching.md) | `proposed` | `polisyos.fabric` | WVS wave-based temporal matching find_closest_in_wave(max_distance=3) | - |
| [0071](0071-intervention-spec-soft-stochastic.md) | `proposed` | `polisyos.lex` | InterventionSpec for soft/stochastic interventions from Legal Graph (Phase 11) | - |
| [0072](0072-phase-12b-via-y0-causaleffect.md) | `proposed` | `repository` | Phase 12b full do-calculus via y0/causaleffect bridge, not from-scratch s-ID | - |
| [0074](0074-numpyro-bayesian-scm.md) | `proposed` | `repository` | NumPyro for Bayesian SCMs (Phase 15) | - |
| [0076](0076-kuzudb-causal-graph-queries.md) | `proposed` | `polisyos.fabric` | KuzuDB for causal graph Cypher queries, aligned with fabric/world/materialize/kuzu.py | - |
| [0078](0078-phase-8-split-8a-8b.md) | `proposed` | `repository` | Phase 8 split into 8A + 8B; TransportabilityRequiredPass moved to end of Phase 12 | - |
| [0079](0079-hybrid-scm-mechanism-source.md) | `proposed` | `repository` | Hybrid SCM with MechanismSource (DATA_FITTED / LITERATURE_PRIOR / HYBRID / DEFAULT) | - |
| [0081](0081-break-cycles-time-aware.md) | `proposed` | `repository` | \_break_cycles time-aware: skip for PCMCI output (tags={"time-series"}) | - |
| [0082](0082-abm-bridge-adaptive-tolerance.md) | `proposed` | `repository` | ABM bridge adaptive tolerance (2-sigma variance) + NON_LINEAR_DIVERGENCE at phase transitions | - |
| [0084](0084-formal-grammar-canonical-variable-names.md) | `proposed` | `repository` | Formal BNF grammar for canonical variable names + seed 200 vars | - |
| [0087](0087-llm-prior-calibration-ceiling.md) | `proposed` | `repository` | LLM Prior Calibration Ceiling | - |
| [0088](0088-three-layer-conflict-separation-hodge.md) | `proposed` | `repository` | Three-Layer Conflict Separation with Hodge Diagnostics | - |
| [0112](0112-data-forge-consolidation.md) | `proposed` | `polisyos.data_forge` | Data Forge Consolidation | - |
| [0113](0113-asset-centric-pipeline-model.md) | `proposed` | `repository` | Asset-Centric Pipeline Model | - |
| [0121](0121-python-monorepo-uv-workspaces.md) | `proposed` | `repository` | Python Monorepo via uv Workspaces | 0004, 0096, 0115 |
| [0122](0122-lakehouse-snapshot-semantics.md) | `proposed` | `polisyos.data_forge` | Lakehouse Snapshot Semantics | 0010, 0015, 0113 |
| [0123](0123-artifact-ref-governance.md) | `proposed` | `repository` | ArtifactRef Governance Metadata | 0010, 0021, 0062, 0105 |
| [0125](0125-quality-regime-golden-differential-drift-consumer-contracts.md) | `proposed` | `polisyos.data_forge` | Quality Regime for Data Forge Assets | 0062, 0095, 0113, 0114 |
| [0133](0133-fabric-streaming-scale-semantics.md) | `accepted` | `polisyos.fabric` | Fabric Streaming Scale Semantics | - |
| [0152](0152-semantic-binding-lineage-and-claim-evidence.md) | `accepted` | `repository` | Semantic Binding, Lineage, And Claim Evidence | 0015, 0021, 0043, 0123, 0147, 0148, 0150, 0151, ADR-043 |
| [0157](0157-policy-intent-capability-ledger-authority-profile.md) | `accepted` | `repository` | Policy Intent Envelope, Capability Ledger, And Authority Profile Mapping | 0129, 0131, 0149, 0150, 0152, 0156, 0158 |
| [0158](0158-concept-spine-multi-jurisdiction-reconciliation.md) | `accepted` | `polisyos.ir` | Concept Spine And Multi-Jurisdiction Reconciliation | 0036, 0051, 0147, 0152, 0156, 0157, 0159 |
| [0159](0159-production-evidence-producer-contracts.md) | `accepted` | `repository` | Production Evidence Producer Contracts For Lex, Fabric, Scholar, And Data Forge | 0015, 0021, 0112, 0122, 0152, 0156, 0158, 0160 |
| [0161](0161-claim-argument-warrant-compiler-closeout-gate.md) | `accepted` | `repository` | Claim Argument, Warrant Reliability, And Compiler Closeout Gate | 0129, 0147, 0152, 0153, 0156, 0160 |
| [0167](0167-participation-legitimacy-matrix.md) | `accepted` | `repository` | Participation Legitimacy Matrix | 0147, 0150, 0152, 0156, 0157, 0159, 0160, 0162, 0166 |
| [0168](0168-legal-hierarchy-and-competence.md) | `accepted` | `polisyos.lex` | Legal Hierarchy And Competence Boundaries | 0051, 0057, 0147, 0150, 0152, 0157, 0158, 0159, 0166 |
| [ADR-043](ADR-043-provenance-law.md) | `approved` | `polisyos.lex` | Provenance Law Through QuantityValue | 0123, ADR-044, ADR-046 |
