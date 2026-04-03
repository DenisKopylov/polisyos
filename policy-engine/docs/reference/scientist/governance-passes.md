# Scientist Governance Passes
Related explanation: [Governance Model](../../explanation/governance-model.md).

All governance validators implement `validate(ctx: PassContext) -> list[ComplianceIssue]`. The registry loads passes from `polisyos.scientist_governance_passes`, merges builtin fallbacks, and trims runtime execution with `runtime_profile()`.

## Builtin Passes

| `pass_id` | Class | Cost ms | Purpose | Reads from state | Emits / blocks on |
|-----------|-------|---------|---------|------------------|-------------------|
| `budget` | `BudgetPass` | `5` | Budget ceilings for simulation, LLM usage, and graph complexity | `ctx.ir` and profile thresholds | `BUDGET_EXHAUSTED_*`, `COMPLEXITY_EXCEEDED`, `GRAPH_COST_HIGH` |
| `checkpoint` | `CheckpointPass` | `20` | Reproducibility and replay checkpoint presence | explicit checkpoint payloads | `CHECKPOINT_MISSING`, `CHECKPOINT_ORDER` |
| `citation_validator` | `CitationValidatorPass` | `30` | Citation traceability and confidence hygiene | citation payloads in pass state | `CITATION_*` blockers / warnings |
| `confidence` | `ConfidencePass` | `50` | Confidence-envelope and CI threshold validation | uncertainty envelope artifacts | `CONFIDENCE_*` gates |
| `cross_graph_evidence` | `CrossGraphEvidencePass` | `25` | Cross-graph evidence completeness, legality, transportability | `_store`, `artifacts_index`, `cross_graph_evidence_profile` | `CROSS_GRAPH_*` issues, blocker in stricter profiles |
| `equity` | `EquityPass` | `25` | Distributional fairness and vulnerable-group impact | `_store`, `artifacts_index`, `distributional_report` | `EQUITY_*` warnings / blockers |
| `escalation` | `EscalationPass` | `10` | Required human escalation for high-risk decisions | escalation markers in pass state | `ESCALATION_*` |
| `freshness` | `FreshnessPass` | `15` | Source staleness and timestamp validation | freshness timestamps in pass state | `FRESHNESS_*` |
| `human_review_required` | `HumanReviewRequiredPass` | `50` | Mark runs that require explicit human review | `_store`, `artifacts_index`, causal graph references | `HUMAN_REVIEW_REQUESTED` |
| `legal` | `LegalPass` | `100` | Legal rule evaluation against a resolved norm pack | `norm_pack` plus state context | backend-produced legal issues |
| `literature_gate` | `LiteratureGatePass` | `30` | Unsupported-edge gate based on literature prior coverage | `_store`, `artifacts_index`, causal graph refs | `LITERATURE_GATE_UNSUPPORTED_EDGE` |
| `normative_arbitration` | `NormativeArbitrationPass` | `20` | Normative dissent, rights, and hard-constraint arbitration | `_store`, `artifacts_index`, `normative_arbitration_result` | `NORMATIVE_*` |
| `pii_check` | `PIICheckPass` | `10` | Tenant-tier-specific PII handling | `pii_scan_results`, `tenant_tier` | `PII_*` |
| `privacy` | `PrivacyPass` | `20` | Privacy tier and sensitive-access checks | `pii_tier`, `data_view_requests` | `PII_TIER_HIGH`, `SENSITIVE_ACCESS_TIER`, `ACCESS_TIER_UNKNOWN` |
| `quality` | `QualityGatePass` | `500` | Data quality and evidence readiness before execution | catalog, evidence, quality, and metric refs | `QUALITY_*`, `NO_EVIDENCE_BUNDLE`, `INDICATORS_UNAVAILABLE`, `DATA_STALENESS` |
| `rate_limiter` | `RateLimiterPass` | `5` | Per-run usage ceilings for external systems | `usage` | `RATE_LIMIT_*` |
| `refutation` | `RefutationPass` | `10` | Refutation test coverage and outcome validation | `_store`, `artifacts_index`, `causal_report` | `REFUTATION_*` |
| `safety` | `SafetyPass` | `25` | Mechanism-type safety against the registry bundle | `ctx.ir`, `ctx.registry_bundle` | `UNKNOWN_MECHANISM`, `REGISTRY_UNAVAILABLE` |
| `schema` | `SchemaPass` | `15` | IR structural validation | current IR payload | `IR_MISSING`, `NO_INTERVENTIONS`, `SCHEMA_VALIDATION_ERROR` |
| `strategic_response` | `StrategicResponsePass` | `20` | Strategic-response runtime evidence and multiplicity review | `_store`, `artifacts_index`, `params`, `strategic_response*` | `STRATEGIC_RESPONSE_*`, `HUMAN_REVIEW_REQUESTED` |
| `sutva_check` | `SutvaCheckPass` | `20` | Spillover / interference warning gate | `_store`, `artifacts_index`, `causal_report`, `query_treatment` | `SUTVA_VIOLATION_RISK` |
| `transportability_required` | `TransportabilityRequiredPass` | `20` | External-context effects require transportability support | `_store`, `artifacts_index`, causal report refs | `TRANSPORT_*` |

## Notes

| Item | Detail |
|------|--------|
| Runtime filtering | `runtime_profile()` keeps only runtime-safe passes such as `confidence`, `equity`, `cross_graph_evidence`, `refutation`, `strategic_response`, `sutva_check`, and `transportability_required` |
| Shim modules | `polisyos.scientist.governance.passes.legal_pass` and `safety_pass` are deprecated shims over `polisyos.core.governance.passes.*` |
| Failure model | A pass blocks the pipeline whenever it emits at least one `ComplianceIssue` with blocker severity under the active `ValidationProfile` |

## Registry API

::: polisyos.scientist.governance

::: polisyos.scientist.governance.pass_registry

::: polisyos.scientist.governance.passes

::: polisyos.scientist.governance.passes.strategic_response_pass
