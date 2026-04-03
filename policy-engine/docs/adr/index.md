# ADR Index

> Index of 93 ADR files in `docs/adr/`, grouped by domain with status, summary and related decisions.

## Status Summary

- Accepted: 24
- Proposed: 68
- Deprecated: 0
- Superseded: 1

## Domain Index

- [Architecture](#architecture)
- [Governance](#governance)
- [Causal](#causal)
- [Security](#security)
- [Data](#data)
- [IR](#ir)
- [Scientist](#scientist)
- [Lex](#lex)
- [Fabric](#fabric)
- [Foundry](#foundry)
- [Operations](#operations)

## Architecture

| ADR | Status | Title | Summary | Related |
|-----|--------|-------|---------|---------|
| [0001](0001-remove-legacy-foundry-engine.md) | accepted | Удаляем legacy Foundry engine | В кодовой базе есть два пути исполнения Foundry: новый patch VM / ProgramGraph и устаревшее ядро SimulationKernel. | — |
| [0002](0002-scientist-flow-nodes-only.md) | accepted | Сводим Scientist на flow_nodes-only | В оркестраторе сосуществуют два пути исполнения: новый LangGraph workflow и старый набор нод с прямыми вызовами Foundry и записью в `logs/`. | — |
| [0004](0004-architecture-boundaries-import-gate.md) | accepted | Architecture Boundaries Import Gate | До этого правила импортов были частично описаны и частично закодированы, что приводило к расхождениям и скрытым циклам. | — |
| [0005](0005-abi-schema-gate-versioning.md) | accepted | ABI Versioning Gate via JSON Schema Snapshots | Контрактные модели в `polisyos.ir.*` и словари/enum world ABI (`EdgeKind`, `NodeKind`) используются как межслойный ABI для Foundry, Scien... | — |
| [0032](0032-llm-as-context-interpreter-not-structure-source.md) | proposed | LLM as Context Interpreter, Not Structural Source | Phase 9 introduces LLM-assisted causal graph construction. | — |
| [0033](0033-json-serializable-mechanism-families-only.md) | proposed | JSON-Serializable Mechanism Families Only | Phase 10 GCM (Graphical Causal Model) fitting assigns functional mechanisms to each node in a structural causal model. | — |
| [0035](0035-two-step-screening-haiku-sonnet.md) | proposed | Two-Step Article Screening (Haiku / Sonnet) | Phase 0 academic batch pipeline ingests articles from OpenAlex for causal claim extraction into the Structured Knowledge Graph. | — |
| [0044](0044-literature-first-single-reconciliation-strategy.md) | proposed | Literature-First as the Single Reconciliation Strategy | When reconciling a data-driven causal graph (e.g., from PC/FCI discovery) with the literature-derived SKG graph, multiple strategies are... | — |
| [0053](0053-architecture-freeze-contracts.md) | proposed | Architecture Freeze at Assembly Points | The policy engine architecture defines assembly point contracts: IR schemas, import gates (enforced by `import_policy.toml`), and foundry... | — |
| [0054](0054-skg-on-academic-module.md) | proposed | SKG Built on the Academic Module | The Scientific Knowledge Graph (SKG) aggregates causal evidence from academic literature. | 0043 |
| [0055](0055-dataset-graph-on-datasets-module.md) | proposed | Dataset Graph Built on the Datasets Module | The Dataset Graph tracks variable availability, measurement quality, and temporal coverage across ingested datasets for each context (cou... | 0047, 0050, 0054 |
| [0058](0058-compatibility-policy-additive-changes-only.md) | proposed | Only additive schema changes (1.0 to 1.1), dual-read migration | The IR layer serialises causal models, governance reports, and decision packets into versioned JSON schemas. | — |
| [0060](0060-migration-budget-one-controlled-switch.md) | proposed | Migration Budget = 1: single controlled switch, no feature flags | Feature flags provide runtime flexibility but introduce combinatorial testing complexity and long-lived conditional paths that are easy t... | — |
| [0061](0061-import-gate-ci-contract.md) | proposed | Import gate as CI contract (lint_foundry.py --strict on every PR) | The foundry layer must remain a pure computational core with no upward dependencies on scientist, fabric, or lex. | — |
| [0073](0073-rustworkx-instead-of-networkx.md) | proposed | rustworkx instead of NetworkX for graph computations (Phases 0/9/12) | Phases 0, 9, and 12 perform intensive graph operations: cycle detection, d-separation queries, topological sorting, ancestor/descendant l... | — |
| [0077](0077-rustworkx-tight-loop-algorithms.md) | proposed | rustworkx for in-memory tight-loop algorithms (cycle breaking, resolution loop) | The resolution loop (Phase 9) and `_break_cycles` (Phase 0) are the two hottest graph algorithm paths in the pipeline. | 0073 |
| [0078](0078-phase-8-split-8a-8b.md) | proposed | Phase 8 split into 8A + 8B; TransportabilityRequiredPass moved to end of Phase 12 | Phase 8 currently bundles two conceptually distinct concerns: (8A) constructing the transportability diagram by annotating S-nodes for do... | — |
| [0080](0080-tech-consolidation-stack.md) | proposed | Tech consolidation stack for causal inference, discovery, and graphs | The causal-methods landscape in PolicyOS has grown organically, accumulating overlapping dependencies: DoWhy and EconML for inference, ti... | 0026 |
| [0096](0096-canonical-product-root-and-workspace-boundary.md) | accepted | Canonical Product Root and Workspace Boundary | Repository root and `policy-engine/` accumulated overlapping product signals, making the real source of truth hard to identify quickly. | 0053 |

## Governance

| ADR | Status | Title | Summary | Related |
|-----|--------|-------|---------|---------|
| [0007](0007-human-gate-protocol.md) | accepted | Human Gate Protocol in IR | Human gate ранее был распределён между: - `ExperimentState.params["require_human_gate"]` - `ExperimentState.params["gate_decision"]` (стр... | — |
| [0086](0086-sutva-assumption-check-pass.md) | proposed | SUTVA Assumption Check Pass | The Stable Unit Treatment Value Assumption (SUTVA) underpins most causal inference estimators in the foundry. | — |

## Causal

| ADR | Status | Title | Summary | Related |
|-----|--------|-------|---------|---------|
| [0013](0013-uncertainty-propagation-pipeline.md) | accepted | Uncertainty Propagation Pipeline | ADR-0012 introduced a typed `UncertaintyEnvelope`, but the runtime pipeline did not propagate uncertainty from inputs to simulation outputs. | 0012 |
| [0018](0018-causal-estimator-protocol.md) | proposed | Causal Estimator Protocol (Phase 12) | Phase 12 adds quasi-experimental causal inference methods into Foundry methods (NUMPY backend). | — |
| [0020](0020-robustness-sensitivity-stress.md) | proposed | Robustness Modes (Sensitivity + Stress Test) (Phase 13) | Phase 13 adds robustness analysis capabilities: 1. | — |
| [0025](0025-scm-structural-causal-model-vs-synthetic-control.md) | accepted | SCM Terminology Split (Structural Causal Model vs Synthetic Control) | The codebase historically used `scm` in paths and filenames for the Abadie Synthetic Control method. | — |
| [0026](0026-notears-excluded-from-default-discovery.md) | accepted | Exclude NOTEARS from Default Causal Discovery Stack | Phase 1 formalizes terminology and baseline causal stack decisions for subsequent phases. | — |
| [0027](0027-dowhy-primary-graph-identify-estimate.md) | accepted | DoWhy as Primary Graph-Based Identify/Estimate Method | Phase 2 of the SCM implementation requires graph-based causal identification and estimation in Foundry. | — |
| [0028](0028-refutation-mandatory-for-observational-estimates.md) | accepted | Refutation Mandatory for Observational DoWhy Estimates | Phase 3 of SCM v3 introduces robustness requirements for observational causal estimates. | — |
| [0029](0029-e-value-ate-rr-conversion-strategy.md) | accepted | E-Value ATE-to-Risk-Ratio Conversion Strategy | Phase 4 sensitivity analysis computes E-values to quantify the minimum strength of unmeasured confounding that could explain away an obse... | — |
| [0031](0031-block-bootstrap-for-time-series-stability.md) | proposed | Block Bootstrap for Time-Series Causal Discovery Stability | Phase 6 PCMCI-based causal discovery operates on time-series data where observations are temporally dependent. | 0030 |
| [0034](0034-simplified-tr-backdoor-only.md) | proposed | Simplified Transportability -- Backdoor-Only (Phase 12a) | Phase 12 requires transportability analysis to assess whether causal effect estimates from a source context can be validly applied in a t... | 0039 |
| [0038](0038-law-t-transportability-required.md) | proposed | Law T -- Transportability Required for External Estimates | Phases 8 and 12 enable reuse of causal effect estimates across different policy contexts. | 0039 |
| [0039](0039-context-profile-distance-inference-level.md) | proposed | Context Profile Distance and Inference Level | Phase 12 transportability analysis requires quantified assessment of how "different" a source context is from a target context. | — |
| [0040](0040-max-transport-confidence-evidence-weight.md) | proposed | Parameter Selection by Max Transport Confidence x Evidence Weight | Phase 15 parameter resolution must select the best available causal effect parameter for a given policy question and target context. | 0028, 0038 |
| [0041](0041-confidence-aggregation-quality-score-replication-bonus.md) | proposed | Confidence Aggregation via Quality Score and Replication Bonus | Multiple studies may report on the same causal edge (e.g., "education -> income"). | — |
| [0045](0045-causal-edge-combined-confidence-formula-superseded.md) | superseded | Causal Edge Combined Confidence Formula (Superseded) | The original combined confidence formula for causal edges used a simple weighted product of literature confidence and data confidence: `c... | 0064 |
| [0046](0046-three-graph-closure-transportability.md) | proposed | Three-Graph Closure for Transportability | Transport analysis -- determining whether a causal effect estimated in one context applies to another -- requires reasoning about three d... | — |
| [0048](0048-transportability-resolution-loop-max-3-rounds.md) | proposed | Transportability Resolution Loop with Max 3 Rounds | S-node elimination in transportability analysis may require iterative resolution: adjusting for one S-node (context-varying factor) via a... | — |
| [0049](0049-constraint-severity-hard-blocks-transport.md) | proposed | Constraint Severity -- HARD Blocks Transportability | Legal constraints on causal transportability have varying severity. | 0048 |
| [0050](0050-context-dependent-proxy-penalties.md) | proposed | Context-Dependent Proxy Penalties | When a variable required for transportability adjustment is not directly available in the target context, a proxy variable may be substit... | — |
| [0063](0063-mediator-conditional-covariate-marginal.md) | proposed | Mediator P*(z\|x) conditional; covariate P*(z) marginal (Pearl & Bareinboim 2011) | When transporting causal effects across populations, the re-weighting strategy depends on whether a variable acts as a mediator or a cova... | — |
| [0064](0064-compute-combined-confidence-noisy-or.md) | proposed | compute_combined_confidence() = 1 - Prod(1-conf_i)^w_i (Noisy-OR) | Multiple independent evidence sources (literature priors, observational estimates, sensitivity analyses) each provide a confidence score... | — |
| [0065](0065-cycle-breaking-time-lag-conversion.md) | proposed | Cycle breaking via time-lag conversion (not edge deletion) | Causal graphs constructed from observational data or literature extraction sometimes contain cycles (e.g., A -> B -> A), which violate th... | — |
| [0066](0066-pag-dag-projection-u-dummy-nodes.md) | proposed | PAG to DAG projection: bidirectional edges to U-dummy nodes for dowhy.gcm | Constraint-based causal discovery algorithms (e.g., PC, FCI) produce Partial Ancestral Graphs (PAGs) that may contain bidirectional edges... | — |
| [0067](0067-multiplicative-confidence-penalties.md) | proposed | Multiplicative confidence penalties Prod(1-p_i) instead of additive | Governance passes and sensitivity analyses may flag issues that reduce confidence in a causal estimate (e.g., failed refutation, high sen... | — |
| [0069](0069-collider-check-s-node-elimination.md) | proposed | Collider (selection bias) check in _try_eliminate_s_node_simplified | Selection bias arises when conditioning on a collider (a node caused by both treatment and outcome, or their descendants) opens a spuriou... | — |
| [0070](0070-bidirectional-edge-u-node-backdoor-invalid.md) | proposed | Bidirectional edge (U-node) implies backdoor invalid, needs_advanced_tr | When a PAG contains a bidirectional edge X <-> Y, the U-dummy node projection (ADR-0066) introduces an unobserved confounder U_{XY}. | 0066 |
| [0072](0072-phase-12b-via-y0-causaleffect.md) | proposed | Phase 12b full do-calculus via y0/causaleffect bridge, not from-scratch s-ID | Phase 12b requires symbolic identification of causal effects in the presence of selection bias and transportability constraints (generali... | — |
| [0074](0074-numpyro-bayesian-scm.md) | proposed | NumPyro for Bayesian SCMs (Phase 15) | Phase 15 introduces Bayesian Structural Causal Models (SCMs) where each mechanism is a full posterior distribution rather than a point es... | — |
| [0075](0075-econml-cate-heterogeneous-effects.md) | proposed | EconML/CATE: heterogeneous effects via DML, Causal Forests (Phases 2/11) | Phases 2 and 11 require estimation of heterogeneous treatment effects (HTEs) to answer the policy question "for whom does the interventio... | — |
| [0079](0079-hybrid-scm-mechanism-source.md) | proposed | Hybrid SCM with MechanismSource (DATA_FITTED / LITERATURE_PRIOR / HYBRID / DEFAULT) | Phase 10 fits SCM mechanisms from observational data, and Phase 15 assigns Bayesian priors from the literature. | 0074 |
| [0081](0081-break-cycles-time-aware.md) | proposed | _break_cycles time-aware: skip for PCMCI output (tags={"time-series"}) | The `_break_cycles` step in graph reconciliation removes feedback edges to produce a DAG from a cyclic or partially directed graph. | — |
| [0083](0083-resolution-loop-proxy-depth-guard.md) | proposed | Resolution Loop proxy-depth guard: proxy variables don't generate new S-nodes | The resolution loop (Phase 9) handles unobserved variables by substituting proxy variables from the dataset catalog. | — |
| [0085](0085-pag-identification-conservative-policy.md) | proposed | PAG to Identification: CONSERVATIVE policy (identify iff identifiable in all DAGs in PAG) | Causal discovery algorithms (FCI, RFCI, BCCD) often produce a Partial Ancestral Graph (PAG) rather than a single DAG, representing an equ... | — |
| [0087](0087-llm-prior-calibration-ceiling.md) | proposed | LLM Prior Calibration Ceiling | The literature prior pipeline uses LLM-extracted effect sizes and directions as Bayesian priors for causal estimation. | 0094 |
| [0088](0088-three-layer-conflict-separation-hodge.md) | proposed | Three-Layer Conflict Separation with Hodge Diagnostics | Graph reconciliation merges causal structures from multiple sources (literature, discovery algorithms, expert elicitation). | — |
| [0089](0089-pre-implementation-survey-tr-scope.md) | proposed | Pre-Implementation Survey for Simplified TR Scope Validation | Transportability analysis requires specifying the scope of a policy intervention -- target population, geographic context, temporal windo... | — |
| [0090](0090-formal-proxy-validity-conditions.md) | proposed | Formal Proxy Validity Conditions | When a target variable is unavailable in the dataset, the system substitutes a proxy variable. | 0091 |
| [0091](0091-partial-identification-manski-bounds.md) | proposed | Partial Identification Bounds as Fallback for Non-Transportable Results | When formal transportability analysis concludes that a causal effect is `NON_TRANSPORTABLE` between source and target populations, the cu... | — |
| [0092](0092-harmonic-mean-confidence-composition.md) | proposed | Harmonic Mean for Confidence Composition in Proxy Chains | When a target variable is reached through a chain of proxy substitutions (e.g., variable A proxied by B, which is itself proxied by C), t... | 0094 |
| [0093](0093-dynamic-transportability-time-stationarity.md) | proposed | Dynamic Transportability with Time-Stationarity Flag | Standard transportability theory assumes that causal mechanisms are stable over time. | — |
| [0094](0094-confidence-ordinal-quality-score.md) | proposed | Confidence as Ordinal Quality Score | The system pervasively uses "confidence" values in [0, 1] -- attached to literature priors, proxy validations, transportability assessmen... | 0087, 0092 |
| [0095](0095-canonical-scm-test-fixtures.md) | proposed | Canonical SCM Test Fixtures | Causal inference modules (discovery, estimation, refutation, transportability) each maintain ad-hoc test graphs, leading to duplicated se... | — |

## Security

| ADR | Status | Title | Summary | Related |
|-----|--------|-------|---------|---------|
| [0010](0010-cas-artifact-signing-ed25519.md) | accepted | CAS Artifact Signing (Ed25519) | CAS в Policy OS уже гарантирует integrity (`sha256(blob)`), но не гарантирует authenticity и non-repudiation. | 0006 |
| [0023](0023-cell-based-tenant-isolation.md) | accepted | Cell-Based Tenant Isolation Foundation | PolicyOS needs tenant isolation suitable for government workloads. | — |

## Data

| ADR | Status | Title | Summary | Related |
|-----|--------|-------|---------|---------|
| [0015](0015-knowledge-bundle-freshness-protocol.md) | accepted | KnowledgeBundle Freshness Protocol | Scholar knowledge bundles were immutable CAS artifacts without explicit temporal metadata. | — |
| [0042](0042-duckdb-for-skg-storage.md) | proposed | DuckDB for SKG Storage | The Scientific Knowledge Graph (SKG) requires analytical query capability for aggregation across studies, filtering by variable, context,... | — |
| [0043](0043-skg-versioning-retraction-handling.md) | proposed | SKG Versioning and Retraction Handling | Scientific knowledge evolves: new studies may revise effect estimates, and retractions must invalidate derived artifacts (edges, confiden... | — |
| [0047](0047-graph-federation-cross-references.md) | proposed | Graph Federation with Cross-References | The three graphs (SKG, Dataset Graph, Legal Graph) have fundamentally different update rhythms: SKG updates weekly via OpenAlex sync, Dat... | — |
| [0052](0052-data-gap-first-class-object.md) | proposed | DataGap as a First-Class Object | When a variable needed for transportability adjustment (e.g., P*(Z) in the target context) is missing from available datasets, the transp... | 0050 |
| [0062](0062-knowledge-snapshot-id-mandatory-input-ref.md) | proposed | knowledge_snapshot_id + mandatory InputRef for lineage sync | The academic and datasets batch pipelines produce knowledge snapshots that feed into causal model construction. | — |
| [0068](0068-wvs-wave-temporal-matching.md) | proposed | WVS wave-based temporal matching find_closest_in_wave(max_distance=3) | The World Values Survey publishes data in discrete waves (e.g., Wave 6: 2010-2014, Wave 7: 2017-2022) rather than annual releases. | — |
| [0076](0076-kuzudb-causal-graph-queries.md) | proposed | KuzuDB for causal graph Cypher queries, aligned with fabric/world/materialize/kuzu.py | Causal graphs in PolicyOS serve two roles: algorithmic (d-separation, identification) and analytical (ad-hoc queries like "which confound... | 0073 |

## IR

| ADR | Status | Title | Summary | Related |
|-----|--------|-------|---------|---------|
| [0003](0003-ir-v1-deprecate-remove.md) | accepted | IR v1.0 → deprecate → remove | В системе одновременно присутствуют v2 Surface IR (актуальный путь) и v1 PolicyRequestIR (legacy совместимость). | — |
| [0012](0012-uncertainty-envelope-ir-contract.md) | accepted | UncertaintyEnvelope IR Contract | Policy OS produces uncertainty from multiple independent subsystems with incompatible shapes: - Foundry calibration exposes Hessian-deriv... | — |
| [0022](0022-policy-portfolio-ir-extension.md) | accepted | PolicyPortfolio IR Extension | `PolicySpec` models a single policy configuration. | — |
| [0030](0030-causal-graph-model-ir-artifact.md) | accepted | CausalGraphModel as IR Artifact (DAG / CPDAG / PAG) | Phase 5 introduces a first-class causal graph contract that must: 1. | 0064 |
| [0036](0036-variable-canonizer-hierarchical-names.md) | proposed | Variable Canonizer with Hierarchical Names | Phase 0 knowledge pipeline must merge causal claims from multiple studies into a unified Structured Knowledge Graph. | — |
| [0071](0071-intervention-spec-soft-stochastic.md) | proposed | InterventionSpec for soft/stochastic interventions from Legal Graph (Phase 11) | Phase 11 integrates legal constraints from Lex into causal inference via the Legal Graph. | — |
| [0084](0084-formal-grammar-canonical-variable-names.md) | proposed | Formal BNF grammar for canonical variable names + seed 200 vars | PolicyOS merges causal graphs from multiple discovery methods, literature priors, and dataset catalogs. | — |
| [ADR-004](ADR-004-policy-surface-removal.md) | accepted | Trinity-Only IR Runtime | Legacy surface IR support had already been disabled in runtime execution paths, but dead code, tests, and docs still referenced it. | 0003 |

## Scientist

| ADR | Status | Title | Summary | Related |
|-----|--------|-------|---------|---------|
| [0008](0008-scientist-node-idempotency-contract.md) | accepted | Scientist Node Idempotency Contract | Scientist DAG содержит дорогостоящие и нестабильные операции (Foundry compile/execute, Scholar/Fabric/Lex integration). | 0003 |
| [0009](0009-decision-packet-replay-protocol.md) | proposed | DecisionPacket Replay Protocol | Policy OS requires offline, auditable replay from a single `DecisionPacket` reference. | — |
| [0011](0011-scientist-checkpoint-resume.md) | accepted | Scientist DAG Checkpoint/Resume | Scientist DAG runs can be long-running. | 0008, 0009 |
| [0059](0059-scientist-causal-full-parallel-workflow.md) | proposed | scientist_causal_full parallel with scientist_default, single cutover | The existing `scientist_default` workflow covers the core policy-evaluation loop but lacks advanced causal inference steps such as graph... | — |

## Lex

| ADR | Status | Title | Summary | Related |
|-----|--------|-------|---------|---------|
| [0019](0019-lex-norm-impact-analysis.md) | proposed | Lex Norm Impact Analysis API (Phase 13) | Phase 13 requires a deterministic "law-change simulator" for what-if analysis: - mutate a baseline `NormPack` - compare old/new packs str... | — |
| [0037](0037-law-l-edges-without-evidence-support.md) | proposed | Law L -- Edges Without Evidence Support | Phases 5 and 8 construct causal graphs from multiple sources: SKG literature priors, data-driven discovery, LLM suggestions, and expert i... | — |
| [0051](0051-legal-to-dag-mapping-types.md) | proposed | Legal-to-DAG Mapping Types | Legal constraints affect causal directed acyclic graphs (DAGs) in structurally different ways. | — |
| [0057](0057-legal-bridge-via-lex-api.md) | proposed | Legal bridge via lex/api.py, not separate legal_graph/ module | The scientist workflow requires legal constraint information (e.g., jurisdiction applicability, regulatory restrictions) when evaluating... | — |

## Fabric

| ADR | Status | Title | Summary | Related |
|-----|--------|-------|---------|---------|
| [0021](0021-connector-schema-contracts-and-storage-port.md) | accepted | Connector Schema Contracts and StoragePort Boundary | Phase 16 requires: 1. | — |
| [0056](0056-wgi-wdi-fabric-connector-wvs-new.md) | proposed | WGI/WDI via fabric WorldBankConnector, WVS as new fabric connector | The policy engine needs access to World Governance Indicators (WGI) and World Development Indicators (WDI) datasets, both published by th... | — |

## Foundry

| ADR | Status | Title | Summary | Related |
|-----|--------|-------|---------|---------|
| [0082](0082-abm-bridge-adaptive-tolerance.md) | proposed | ABM bridge adaptive tolerance (2-sigma variance) + NON_LINEAR_DIVERGENCE at phase transitions | The ABM bridge compares agent-based simulation outputs against SCM-predicted causal effects to validate structural assumptions. | — |

## Operations

| ADR | Status | Title | Summary | Related |
|-----|--------|-------|---------|---------|
| [0006](0006-slo-definitions.md) | accepted | SLO Definitions for Scientist DAG | До изменения observability покрывала операционные метрики (`workflow_runs_total`, `llm_tokens_total`, `governance_pass_duration_seconds`)... | — |
