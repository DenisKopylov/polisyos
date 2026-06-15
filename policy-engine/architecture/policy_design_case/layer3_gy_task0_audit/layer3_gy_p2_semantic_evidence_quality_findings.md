# GY P2 Semantic Evidence Quality Audit Findings

Task 0 follow-up slice for `docs/plans/active/layer3-slices/GY-engine-subordination.md`.

Scope: semantic adequacy of catalog search, metric-binding search quality, Scholar/OpenAlex + SKG reuse truth, and KnowledgeToolkit route/tool completeness.

This is audit-only. No runtime, catalog, Scholar, or toolkit behavior was changed.

## Method

- Ran `DatasetCatalogGraph.search_datasets` against the production catalog at `production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb`.
- Labeled a five-case silver benchmark with route-level construct and scope criteria.
- Compared free-text catalog search against `search_metric_bindings`.
- Queried the production Scholar SKG at `production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb`.
- Probed `KnowledgeToolkit` registry conversion through `build_knowledge_tool_registry(KnowledgeToolkit())`.
- Did not run network fetches, agents, or fixes.

Machine-readable audit: `architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_p2_semantic_evidence_quality_audit.json`.

## Headline Finding

Catalog and Scholar substrates are real, but P2 does not yet support route authority.

The production catalog has 137,176 datasets, 605,408 distributions, and 56,846 metric bindings. The production Scholar SKG has 310,829 articles, 7,607 causal edges, and 62,248 parameter estimates. Those are strong substrates.

But the route-like semantic probes are not authority-safe:

- Catalog silver benchmark: construct-only precision@5 was `0.56`, but route-admissible construct+scope precision@5 was `0.0`.
- Four of four country-filtered catalog cases returned zero.
- Scholar natural-language work search returned zero for five route-like queries.
- KnowledgeToolkit registered only 3 of 20 expected tools in the runtime adapter probe.

## Findings

### P2-1: Catalog top-k discovery has zero route-admissible precision

Observed:

- `sentence_transformers` is unavailable, so catalog search falls back to text-only despite HNSW index files being present.
- Text search returns `DatasetSearchResult.similarity = 1.0` for all text candidates, so consumers do not receive calibrated relevance.
- Five GY-like cases produced 25 judged top-k rows.
- Construct-only precision@5 was `0.56`, but construct+scope route precision@5 was `0.0`.
- `UA`, `PL`, and `PK` country filters returned zero in all four scoped cases.

Implication: GY-1 cannot treat catalog top-k search as admissible discovery. It is candidate discovery until construct, jurisdiction/scope, source-contract, and measurement-root gates are joined.

### P2-2: Metric bindings help but do not close semantic adequacy

Observed:

- `credit_access`, `poverty_rate`, `displacement`, and `social_protection_coverage` resolve through metric binding search.
- `firm survival` and `cash transfer` return zero metric bindings.
- `energy poverty` splits into `energy_intensity` and `poverty_rate`.
- `electricity price` returns `electricity_access` and generic `avg_price`.

Implication: the stronger deterministic layer is incomplete for policy constructs. GY-1 needs a construct handshake across `DataRequirementSpec`, metric binding search, catalog search, and FetchPlan admission.

### P2-3: Scholar/OpenAlex SKG is rich but not route-query complete

Observed:

- The production SKG is real: 310,829 articles, 7,607 edges, 7,607 transport scores, 723 contested edges, and 62,248 parameter estimates.
- `ScholarKnowledgeGraph.find_relevant_works` returned zero for five route-like natural-language queries.
- Canonical edge queries work for some known pairs: `fiscal.cash_transfer -> economic.consumption` and `climate.drought_resilient_irrigation -> energy.electricity_reliability`.
- `finance.small_business_lending -> economic.firm_productivity` and `finance.small_business_lending -> labor.employment_rate` returned zero.

Implication: Scholar/OpenAlex should remain in the plan, but GY-6 cannot rely on a reuse pointer. It needs canonical query traces, no-hit frontiers, and a clear boundary between web evidence bundles and L2 SKG authority.

### P2-4: KnowledgeToolkit route/tool completeness is weaker than the class suggests

Observed:

- `KnowledgeToolkit` declares dataset, Scholar, legal, and memory methods.
- The generic adapter registered only `get_dataset_connector`, `remember`, and `recall` in a runtime probe.
- Most methods failed registration because `get_type_hints` cannot resolve annotations imported only under `TYPE_CHECKING`.
- Production route use found in this pass is legal-only (`KnowledgeToolkit(legal_graph=...)`) or formatting-only (`KnowledgeToolkit().format_web_evidence_context(...)`).
- No default runtime/NL route injection of `DatasetCatalogGraph` or `ScholarKnowledgeGraph` into `KnowledgeToolkit` was found.

Implication: for GY, the toolkit is built but not route-complete. It needs runtime registration proof and event-backed tool-call artifacts before it can be counted as G6 route evidence.

### P2-5: Web evidence bundles are real but intentionally not L2 SKG authority

Observed:

- `ScholarDeepSearchService` can produce and persist `scholar.web_evidence_bundle`.
- `project_web_evidence_bundle_to_research_dag` projects query/fetch/snippet/support nodes.
- The integration fixture proves a web bundle can project into a Scientist research DAG.
- G2 guardrails explicitly reject `web_evidence_bundle_ref` as canonical L2 SKG search.

Implication: this is good authority hygiene. GY-6 must decide whether it needs web evidence, canonical SKG evidence, or both, and must not conflate their authority envelopes.

## GY Plan Implication

GY-1 should include a semantic adequacy gate before treating catalog search or metric bindings as source truth. Minimum acceptance: reviewed construct labels, route-scope precision threshold, zero-hit frontier records, and source-contract/Freshness/measurement-root joins before FetchPlan execution.

GY-6 should not be written as "use Scholar/OpenAlex/KnowledgeToolkit" in the abstract. It needs explicit acceptance for SKG query traces, web-bundle authority boundaries, no-hit frontier persistence, runtime tool registration, and event-backed tool-loop outputs.

Validator:

```bash
python3 tools/quality/validation/check_layer3_gy_p2_semantic_evidence_quality_audit.py --json
```

Focused tests:

```bash
uv run pytest tests/repo_quality/tools/test_layer3_gy_p2_semantic_evidence_quality_audit.py -q
```
