# SCM v3 Fullspec Verification

- Generated (UTC): `2026-03-03T17:32:15.944874+00:00`
- Spec: `/Users/deniskopylov/polisyos/scm-implementation-spec-v3.md`
- Base verification: `/Users/deniskopylov/polisyos/policy-engine/docs/reports/scm_v3_verification_evidence_20260303_173006.json`

## Summary

- DoD PASS: **162 / 162**
- Laws PASS: **13 / 13**
- SL PASS: **8 / 8**

## DoD Matrix

| ID | Phase | Requirement | Status | Evidence | Severity | Notes |
|---|---|---|---|---|---|---|
| DOD-001 | -1 | Контракты зафиксированы как snapshot tests (`gen_schema.py --check` для каждого) | PASS | gate_lint_foundry; gate_lint_imports; gate_schema_fabric; gate_schema_ir; workflow_guards | P0 blocker |  |
| DOD-002 | -1 | `lint_foundry.py` обновлён с новыми directory policies | PASS | gate_lint_foundry; gate_lint_imports; gate_schema_fabric; gate_schema_ir; workflow_guards | P0 blocker |  |
| DOD-003 | -1 | `scientist_causal_full` workflow зарегистрирован (пустой: только существующие ноды) | PASS | gate_lint_foundry; gate_lint_imports; gate_schema_fabric; gate_schema_ir; workflow_guards | P0 blocker |  |
| DOD-004 | -1 | CI pipeline: schema check + lint + import gate на каждый PR | PASS | gate_lint_foundry; gate_lint_imports; gate_schema_fabric; gate_schema_ir; workflow_guards | P0 blocker |  |
| DOD-005 | -1 | ADR-0053 (Architecture Freeze) принят командой | PASS | gate_lint_foundry; gate_lint_imports; gate_schema_fabric; gate_schema_ir; workflow_guards | P0 blocker |  |
| DOD-006 | 0A | `PolicyArticleExtractor` обрабатывает статьи из OpenAlex с двухшаговым скринингом | PASS | phase0_quality_integration | P3 low |  |
| DOD-007 | 0A | `ArticleExtractionResult` сериализуется и проходит JSON Schema snapshot | PASS | phase0_quality_integration | P3 low |  |
| DOD-008 | 0A | `ScientificKnowledgeGraph` строится в DuckDB из набора `ArticleExtractionResult` | PASS | phase0_quality_integration | P3 low |  |
| DOD-009 | 0A | `source_context` заполняется при экстракции (не в Фазе 12) | PASS | phase0_quality_integration | P3 low |  |
| DOD-010 | 0A | `VariableCanonizer` — детерминированный, с кэшем в DuckDB, fuzzy match | PASS | phase0_quality_integration | P3 low |  |
| DOD-011 | 0A | `aggregate_edge_confidence` — 1 RCT > 9 observational (golden test) | PASS | phase0_quality_integration | P3 low |  |
| DOD-012 | 0A | `priority_filter` — matching по display_name (не по topic ID) | PASS | phase0_quality_integration | P3 low |  |
| DOD-013 | 0A | Тест: 50 статей по экономической политике → >200 causal claims, >100 parameters | PASS | phase0_quality_integration; phase15_parameters | P3 low |  |
| DOD-014 | 0A | Канонизация: "gdp growth" и "economic growth" → один узел `gdp_growth` | PASS | phase0_quality_integration | P3 low |  |
| DOD-015 | 0A | Rate limiting для OpenAlex API: max 10 req/sec, backoff при 429 | PASS | phase0_quality_integration | P3 low |  |
| DOD-016 | 0A | Кэширование: одна статья обрабатывается ровно один раз (CAS hash по DOI/openalex_id) | PASS | phase0_quality_integration | P3 low |  |
| DOD-017 | 0A | `academic-skg` optional dependency group изолирована — без неё все остальные фазы работают | PASS | phase0_quality_integration | P3 low |  |
| DOD-018 | 0A | `ExtractorStats` — стоимость tracking (по аналогии с SPO pipeline) | PASS | phase0_quality_integration | P3 low |  |
| DOD-019 | 0A | `skg_versions` таблица, retraction handling | PASS | phase0_quality_integration | P3 low |  |
| DOD-020 | 0B | Data sources (WGI, WVS, WDI) — bulk download + DuckDB таблицы | PASS | phase0_quality_integration | P3 low |  |
| DOD-021 | 0B | `DatasetRegistry` — DuckDB-backed каталог с seed alignments для WGI/WVS/WDI/IMF | PASS | phase0_quality_integration | P3 low |  |
| DOD-022 | 0B | `DatasetRegistry.find_datasets_for_variable()` — прямые + прокси результаты | PASS | phase0_quality_integration | P3 low |  |
| DOD-023 | 0B | Тест: WVS wave-based temporal matching корректно выбирает ближайшую волну | PASS | phase0_quality_integration | P3 low |  |
| DOD-024 | 0C | `ProxyResolver` — контекстно-зависимые штрафы, не фиксированные константы | PASS | phase0_quality_integration; phase12_transportability | P3 low |  |
| DOD-025 | 0C | `LegalConstraintBridge` — hard/soft constraints, `LegalToDAGMapping` с `requires_expert_review=True` | PASS | phase0_quality_integration; phase12_transportability; phase6_7_jax_ci_backend | P3 low |  |
| DOD-026 | 0C | `ConstraintSeverity.HARD` → блокирует транспортировку (не просто снижает confidence) | PASS | phase0_quality_integration; phase12_transportability; phase6_7_jax_ci_backend | P3 low |  |
| DOD-027 | 0C | Golden test: Legal constraint "ретроактивность запрещена" → `MECHANISM_NODE` S-узел | PASS | phase0_quality_integration; phase12_transportability; phase6_7_jax_ci_backend | P3 low |  |
| DOD-028 | 0D | Интеграционный тест: полный pipeline от OpenAlex query до DuckDB с SKG + Dataset Graph + Legal Bridge | PASS | phase0_quality_integration | P3 low |  |
| DOD-029 | 0D | Smoke test: >80% извлечённых causal claims имеют каноничные имена переменных | PASS | phase0_quality_integration | P3 low |  |
| DOD-030 | 0D | Golden test: known article → expected `ArticleExtractionResult` (regression guard) | PASS | phase0_quality_integration | P3 low |  |
| DOD-031 | 1 | `synthetic_control.py` — основной файл, `scm.py` — shim | PASS | workflow_guards | P3 low |  |
| DOD-032 | 1 | `_registry_boot.py` обновлён | PASS | workflow_guards | P3 low |  |
| DOD-033 | 1 | ADR-0025, ADR-0026 в `docs/adr/` | PASS | workflow_guards | P3 low |  |
| DOD-034 | 1 | Все существующие тесты проходят | PASS | workflow_guards | P3 low |  |
| DOD-035 | 2 | `DoWhyIdentifyEstimate` зарегистрирован в `MethodRegistry` как `causal.inference.dowhy_identify_estimate@1.0.0` | PASS | causal_methods_suite | P1 high |  |
| DOD-036 | 2 | `GraphCausalData` — входной тип для graph-based методов, `model_validator` проверяет консистентность | PASS | causal_methods_suite | P1 high |  |
| DOD-037 | 2 | `CausalMethod` расширен: `DOWHY_BACKDOOR`, `DOWHY_IV`, `DOWHY_FRONTDOOR` | PASS | causal_methods_suite | P1 high |  |
| DOD-038 | 2 | `CausalEffectReport` расширен: `identified_estimand`, `graph_ref` | PASS | causal_methods_suite; phase12b_symbolic_bridge | P1 high |  |
| DOD-039 | 2 | Тест: linear confounding scenario → ATE ±0.1 от ground truth | PASS | causal_methods_suite | P1 high |  |
| DOD-040 | 2 | JSON Schema snapshot для расширенного `CausalEffectReport` | PASS | causal_methods_suite; phase12b_symbolic_bridge | P1 high |  |
| DOD-041 | 2 | ADR-0027 в `docs/adr/` | PASS | causal_methods_suite | P1 high |  |
| DOD-042 | 3 | `DoWhyRefute` — 4 refutation теста, seed из `random_seed` | PASS | causal_methods_suite | P1 high |  |
| DOD-043 | 3 | `RefutationResult` — JSON Schema snapshot | PASS | causal_methods_suite | P1 high |  |
| DOD-044 | 3 | Тест: synthetic confounded data → `random_common_cause` не отвергает | PASS | causal_methods_suite | P1 high |  |
| DOD-045 | 3 | ADR-0028: Refutation mandatory для observational estimates | PASS | causal_methods_suite | P1 high |  |
| DOD-046 | 4 | `SensitivityMetrics` Foundry method — E-value, Robustness Value, Rosenbaum Γ | PASS | causal_methods_suite | P3 low |  |
| DOD-047 | 4 | `SensitivityResult` — JSON Schema snapshot | PASS | causal_methods_suite | P3 low |  |
| DOD-048 | 4 | E-value `conversion_method` записывается для auditability (ADR-0029) | PASS | causal_methods_suite | P3 low |  |
| DOD-049 | 4 | Golden test: known confounded scenario → E-value matches hand calculation | PASS | causal_methods_suite | P3 low |  |
| DOD-050 | 4 | Интеграция в DecisionPacket секция 3.2 | PASS | causal_methods_suite | P3 low |  |
| DOD-051 | 5 | `CausalGraphModel` — DAG/CPDAG/PAG через EdgeMark | PASS | causal_methods_suite; ir_contracts_suite | P3 low |  |
| DOD-052 | 5 | `CausalEdge.compute_combined_confidence()` — тест: два источника > один | PASS | causal_methods_suite; ir_contracts_suite | P3 low |  |
| DOD-053 | 5 | `to_gml()` корректен для DoWhy | PASS | causal_methods_suite; ir_contracts_suite | P3 low |  |
| DOD-054 | 5 | `to_kuzu()` материализация в KuzuDB (паттерн `world/materialize/kuzu.py`) | PASS | causal_methods_suite; ir_contracts_suite | P3 low |  |
| DOD-055 | 5 | `to_rustworkx()` для in-memory графовых алгоритмов (primary) | PASS | causal_methods_suite; ir_contracts_suite | P3 low |  |
| DOD-056 | 5 | `to_networkx()` legacy shim для discovery библиотек (causal-learn/tigramite требуют NetworkX) | PASS | causal_methods_suite; ir_contracts_suite | P3 low |  |
| DOD-057 | 5 | JSON Schema snapshot | PASS | causal_methods_suite; ir_contracts_suite | P3 low |  |
| DOD-058 | 5 | ADR-0030 | PASS | causal_methods_suite; ir_contracts_suite | P3 low |  |
| DOD-059 | 6 | `PCMCIDiscovery` — timeout 10 min, default `par_corr`, `max_lag=5` | PASS | phase6_7_jax_ci_backend | P1 high |  |
| DOD-060 | 6 | `CausalDiscoveryReport` — JSON Schema snapshot | PASS | phase6_7_jax_ci_backend | P1 high |  |
| DOD-061 | 6 | Block bootstrap stability ≥100 runs для production | PASS | phase6_7_jax_ci_backend | P1 high |  |
| DOD-062 | 6 | Тест: VAR(1) synthetic data → восстанавливает ground truth DAG | PASS | phase6_7_jax_ci_backend | P1 high |  |
| DOD-063 | 6 | ADR-0031: Block bootstrap для time-series stability | PASS | phase6_7_jax_ci_backend | P1 high |  |
| DOD-064 | 6 | (Опционально) JAX-vectorized ParCorr для >30 переменных — см. Приложение B.7 | PASS | phase6_7_jax_ci_backend | P1 high |  |
| DOD-065 | 7 | PC, FCI, GES зарегистрированы в `MethodRegistry` | PASS | phase6_7_jax_ci_backend | P1 high |  |
| DOD-066 | 7 | FCI → `CausalGraphModel` с `graph_type=PAG`, EdgeMark.CIRCLE | PASS | phase6_7_jax_ci_backend | P1 high |  |
| DOD-067 | 7 | PAG хранится рядом с resolved DAG (не теряем информацию) | PASS | phase6_7_jax_ci_backend | P1 high |  |
| DOD-068 | 7 | Тест: FCI с latent confounder → PAG корректен | PASS | phase6_7_jax_ci_backend | P1 high |  |
| DOD-069 | 7 | `PAGIdentificationPolicy.CONSERVATIVE` — default для всех PAG-based запросов | PASS | phase6_7_jax_ci_backend | P1 high |  |
| DOD-070 | 7 | ADR-0085 | PASS | phase6_7_jax_ci_backend | P1 high |  |
| DOD-071 | 8A | `LiteratureGatePass` — FAST: skip, MVP: WARNING, STRICT: BLOCKER | PASS | governance_suite; phase12_transportability | P2 medium |  |
| DOD-072 | 8A | `HumanReviewRequiredPass` — создаёт review request для STRICT | PASS | governance_suite; phase12_transportability | P2 medium |  |
| DOD-073 | 8A | `SutvaCheckPass` — WARNING для market-wide policies (ADR-0086) | PASS | governance_suite; phase12_transportability | P2 medium |  |
| DOD-074 | 8A | `sutva_assumed: bool` + `sutva_violation_risk` поля в CausalEffectReport / TransportabilityResult | PASS | governance_suite; phase12_transportability; phase12b_symbolic_bridge | P2 medium |  |
| DOD-075 | 8A | Все passes (8A) зарегистрированы в `ValidationPipeline` | PASS | governance_suite; phase12_transportability | P2 medium |  |
| DOD-076 | 8A | ordered by `estimated_cost_ms` (cheapest first) | PASS | governance_suite; phase12_transportability | P2 medium |  |
| DOD-077 | 8A | Тест: graph с `unsupported_by_evidence` edge → STRICT блокирует | PASS | governance_suite; phase12_transportability | P2 medium |  |
| DOD-078 | 8A | Тест: treatment=`tax_rate` → `SUTVA_VIOLATION_RISK` WARNING | PASS | governance_suite; phase12_transportability | P2 medium |  |
| DOD-079 | 8A | `TransportabilityRequiredPass` → реализуется в Фазе 12 (подфаза 8B) | PASS | governance_suite; phase12_transportability | P2 medium |  |
| DOD-080 | 9 | `BuildLiteraturePrior` Foundry method — запрашивает SKG | PASS | phase9_reconciliation | P2 medium |  |
| DOD-081 | 9 | `LiteratureCausalPrior` — JSON Schema snapshot | PASS | phase9_reconciliation | P2 medium |  |
| DOD-082 | 9 | `ReconcileCausalGraph` — LITERATURE_FIRST стратегия | PASS | phase9_reconciliation | P2 medium |  |
| DOD-083 | 9 | Только одна стратегия в MVP (остальные — backlog) | PASS | phase9_reconciliation | P2 medium |  |
| DOD-084 | 9 | LLM prior ceiling = 0.3 для LLM-only рёбер (ADR-0087) | PASS | phase9_reconciliation | P2 medium |  |
| DOD-085 | 9 | LLM + SKG overlap → replication_bonus += 0.05 (не полный boost) | PASS | phase9_reconciliation | P2 medium |  |
| DOD-086 | 9 | `ReconciliationDiagnostics` — Hodge-метрики (patchable, irreducible, cyclic) (ADR-0088) | PASS | phase9_reconciliation | P2 medium |  |
| DOD-087 | 9 | `delta^0`, `delta^1`, `D1` и правило построения 2-симплексов (`A_ijk`) реализованы явно в коде | PASS | phase9_reconciliation | P2 medium |  |
| DOD-088 | 9 | Декомпозиция работает для arbitrary `alpha ∈ C^1` (не только cocycle) | PASS | phase9_reconciliation | P2 medium |  |
| DOD-089 | 9 | Gauge-fixing: pinning по connected components + fallback `epsilon=1e-6` ridge | PASS | phase9_reconciliation | P2 medium |  |
| DOD-090 | 9 | Hard limits соблюдаются: `MAX_RECON_SOURCES=128`, `MAX_RECON_EDGES=4096`, `MAX_TRIANGLES=20000`, `TRIANGLE_BUDGET_MS=250` | PASS | phase9_reconciliation | P2 medium |  |
| DOD-091 | 9 | При превышении лимитов: `diagnostics_truncated=True`, `truncation_reason` заполнен | PASS | phase9_reconciliation | P2 medium |  |
| DOD-092 | 9 | `irreducible_conflict_norm > 0.5` → `needs_expert_review = True` | PASS | phase9_reconciliation | P2 medium |  |
| DOD-093 | 9 | `cyclic_inconsistency_norm > 0.3` → WARNING | PASS | phase9_reconciliation | P2 medium |  |
| DOD-094 | 9 | Тест: literature + data agree → boosted confidence > каждого по отдельности | PASS | phase9_reconciliation | P2 medium |  |
| DOD-095 | 9 | Тест: data contradicts literature direction → data wins | PASS | phase9_reconciliation | P2 medium |  |
| DOD-096 | 9 | Тест: only LLM hint → `unsupported_by_evidence=True`, confidence ≤ 0.3 | PASS | phase9_reconciliation | P2 medium |  |
| DOD-097 | 9 | Тест: цикл → ребро с min confidence конвертировано в лагированную структуру (lag=1) | PASS | phase9_reconciliation | P2 medium |  |
| DOD-098 | 9 | Тест: >8 пересекающихся циклов → fallback на удаление после `max_cycles`, warning в metadata | PASS | phase9_reconciliation | P2 medium |  |
| DOD-099 | 9 | Тест: ребро с lag=2 при `max_lag_depth=2` → удаление (не лагирование глубже) | PASS | phase9_reconciliation | P2 medium |  |
| DOD-100 | 9 | Тест: triangle conflict (A→B=0.8, B→C=0.9, A→C=0.2) → cyclic_inconsistency > 0 | PASS | phase9_reconciliation | P2 medium |  |
| DOD-101 | 9 | ADR-0032: LLM как интерпретатор контекста, не источник структуры | PASS | phase9_reconciliation | P2 medium |  |
| DOD-102 | 9 | ADR-0087: LLM Prior Calibration Model | PASS | phase9_reconciliation | P2 medium |  |
| DOD-103 | 9 | ADR-0088: Трёхслойное разделение конфликтов + Hodge-диагностики | PASS | phase9_reconciliation | P2 medium |  |
| DOD-104 | 10 | `StructuralCausalModelSpec` — JSON Schema snapshot | PASS | causal_methods_suite; ir_contracts_suite | P2 medium |  |
| DOD-105 | 10 | `GCMFit` — auto-assignment mechanisms, fit metrics | PASS | causal_methods_suite; ir_contracts_suite | P2 medium |  |
| DOD-106 | 10 | `_pag_to_dag_projection()` — корректная проекция PAG→DAG с U-узлами | PASS | causal_methods_suite; ir_contracts_suite | P2 medium |  |
| DOD-107 | 10 | Тест: PAG с бидирекциональным ребром → DAG с U-node → GCMFit не падает | PASS | causal_methods_suite; ir_contracts_suite | P2 medium |  |
| DOD-108 | 10 | `NodeMechanism.family_params` — только JSON-serializable (Закон H) | PASS | causal_methods_suite; ir_contracts_suite | P2 medium |  |
| DOD-109 | 10 | Тест: linear SCM → fitted → predict matches | PASS | causal_methods_suite; ir_contracts_suite | P2 medium |  |
| DOD-110 | 10 | ADR-0033: JSON-serializable mechanism families only | PASS | causal_methods_suite; ir_contracts_suite | P2 medium |  |
| DOD-111 | 11 | `GCMQuery` Foundry method — interventional + counterfactual | PASS | causal_methods_suite; ir_contracts_suite | P1 high |  |
| DOD-112 | 11 | `CausalQueryResult.to_uncertainty_envelope()` — совместим с существующим UncertaintyEnvelope | PASS | causal_methods_suite; ir_contracts_suite | P1 high |  |
| DOD-113 | 11 | Тест: do(X=1) vs do(X=0) → ATE совпадает с DoWhy estimate | PASS | causal_methods_suite; ir_contracts_suite | P1 high |  |
| DOD-114 | 11 | JSON Schema snapshot | PASS | causal_methods_suite; ir_contracts_suite | P1 high |  |
| DOD-115 | 12 | `ContextProfile` с `distance_to()` — тест: post-communist penalty корректен | PASS | phase12_transportability | P1 high |  |
| DOD-116 | 12 | `inference_level` tracking — INFERRED_BASIC vs ENRICHED | PASS | phase12_transportability | P1 high |  |
| DOD-117 | 12 | `enrich_from_datasources()` — WGI/WVS/WDI integration | PASS | phase12_transportability | P1 high |  |
| DOD-118 | 12 | `build_selection_diagram()` автоматически генерирует S-узлы из delta > 0.2 | PASS | phase12_transportability | P1 high |  |
| DOD-119 | 12 | `CheckTransportability`: DIRECT / TRANSPORTABLE / NON_TRANSPORTABLE | PASS | phase12_transportability | P1 high |  |
| DOD-120 | 12 | `algorithm_version="simplified_tr_v2"`, `unsupported_cases` populated | PASS | phase12_transportability | P1 high |  |
| DOD-121 | 12 | Явно документировано что покрывается и не покрывается | PASS | phase12_transportability | P1 high |  |
| DOD-122 | 12 | `TransportabilityResult` — JSON Schema snapshot | PASS | phase12_transportability | P1 high |  |
| DOD-123 | 12 | `RunTransportabilityNode` обрабатывает статьи без source_context (graceful skip) | PASS | phase12_transportability | P1 high |  |
| DOD-124 | 12 | `TransportabilityRequiredPass` интегрирован в governance (Подфаза 8B, после стабилизации ResolutionLoop) | PASS | phase12_transportability | P1 high |  |
| DOD-125 | 12 | DecisionPacket `3.3` содержит `transportability_summary` | PASS | phase12_transportability | P1 high |  |
| DOD-126 | 12 | `TransportabilityResolutionLoop` — итеративный resolver, max 3 раунда | PASS | phase12_transportability | P1 high |  |
| DOD-127 | 12 | `DataGap` — explicit reporting: переменная + контекст + доступные прокси + impact | PASS | phase12_transportability | P1 high |  |
| DOD-128 | 12 | `PStarZResult` — вычисленный P*(Z) с полным lineage (dataset_id, raw_var, proxy_chain) | PASS | phase12_transportability | P1 high |  |
| DOD-129 | 12 | `SNode.origin` — различает `CONTEXT_DELTA`, `LEGAL`, `DATA_MISMATCH` | PASS | phase12_transportability | P1 high |  |
| DOD-130 | 12 | Legal constraints: `HARD` → `feasible=False`, `SOFT` → дополнительные S-узлы | PASS | phase12_transportability; phase6_7_jax_ci_backend | P1 high |  |
| DOD-131 | 12 | `LegalToDAGMapping` с `requires_expert_review=True` для всех маппингов в MVP | PASS | phase12_transportability | P1 high |  |
| DOD-132 | 12 | Прокси-штрафы контекстно-зависимые (не фиксированные константы) | PASS | phase12_transportability | P1 high |  |
| DOD-133 | 12 | Pre-implementation survey: 30-50 policy questions → Simplified TR scope validation (ADR-0089) | PASS | phase12_transportability | P1 high |  |
| DOD-134 | 12 | `ProxyValidityChecklist` — формальные условия для каждого прокси (ADR-0090) | PASS | phase12_transportability | P1 high |  |
| DOD-135 | 12 | `PartialIdentificationResult` — Manski bounds fallback для NON_TRANSPORTABLE (ADR-0091) | PASS | phase12_transportability | P1 high |  |
| DOD-136 | 12 | `compose_confidence_harmonic()` для proxy chains (ADR-0092) | PASS | phase12_transportability | P1 high |  |
| DOD-137 | 12 | `AlignmentCertificationPolicy` реализован: typed certificates + `tau_min` (bounded 0.55..0.95) + `max_chain_length=5` | PASS | phase12_transportability | P1 high |  |
| DOD-138 | 12 | Outer objective реализован: `coverage - lambda_conflict * irreducible_conflict_norm` | PASS | phase12_transportability | P1 high |  |
| DOD-139 | 12 | Outer search bounded: `TAU_GRID=8`, `LAMBDA_GRID<=3`, `TYPE_CONFIGS_MAX=6`, `MAX_OUTER_SOLVES=48`, `MAX_OUTER_WALLTIME_SEC=3.0` | PASS | phase12_transportability | P1 high |  |
| DOD-140 | 12 | При budget exhaustion: `outer_search_truncated=True` + `search_budget_exhausted` в events | PASS | phase12_transportability | P1 high |  |
| DOD-141 | 12 | `assumes_time_stationarity` flag для lagged effects в transport path (ADR-0093) | PASS | phase12_transportability | P1 high |  |
| DOD-142 | 12 | Golden test: DE→UA tax reform с legal constraint → resolution_rounds=2, legal_s_nodes populated | PASS | phase12_transportability; phase6_7_jax_ci_backend | P1 high |  |
| DOD-143 | 12 | Golden test: отсутствующий P*(Z) → DataGap с proxy suggestion | PASS | phase12_transportability | P1 high |  |
| DOD-144 | 12 | Golden test: proxy с exclusion violation → `requires_expert_review=True` | PASS | phase12_transportability | P1 high |  |
| DOD-145 | 12 | Golden test: NON_TRANSPORTABLE → Manski bounds с `is_informative` check | PASS | phase12_transportability | P1 high |  |
| DOD-146 | 12 | Lineage через все три графа: ATE → article + dataset + НПА (полная цепочка) | PASS | phase12_transportability | P1 high |  |
| DOD-147 | 13 | `MacroMicroMapping` — маппинг SCM ↔ ABM переменных | PASS | causal_methods_suite | P3 low |  |
| DOD-148 | 13 | `ABMAlignmentReport` — JSON Schema snapshot | PASS | causal_methods_suite | P3 low |  |
| DOD-149 | 13 | Adaptive tolerance (2σ ABM variance, не глобальная 0.2) | PASS | causal_methods_suite | P3 low |  |
| DOD-150 | 13 | Phase transition detection: `NON_LINEAR_DIVERGENCE` при резком скачке | PASS | causal_methods_suite | P3 low |  |
| DOD-151 | 13 | Широкий tolerance "consistent" — WARNING, не BLOCKER (риск: ABM alignment шумный) | PASS | causal_methods_suite | P3 low |  |
| DOD-152 | 13 | `RunABMConsistencyCheckNode` — scientist node | PASS | causal_methods_suite | P3 low |  |
| DOD-153 | 14 | `CausalModelEnsemble` — max 10 members (budget cap) | PASS | causal_methods_suite | P3 low |  |
| DOD-154 | 14 | `edge_inclusion_frequency` — рёбра в ≥50% members → consensus | PASS | causal_methods_suite | P3 low |  |
| DOD-155 | 14 | `to_uncertainty_envelope()` — совместим с существующим UncertaintyEnvelope | PASS | causal_methods_suite | P3 low |  |
| DOD-156 | 14 | Тест: 3 discovery methods на одних данных → ensemble captures structural uncertainty | PASS | causal_methods_suite | P3 low |  |
| DOD-157 | 15 | `ParameterSelector.select_for_context()` — max(confidence × evidence_weight) | PASS | phase15_parameters | P1 high |  |
| DOD-158 | 15 | Параметры с transport_confidence < 0.3 исключаются; fallback → warning | PASS | phase12_transportability; phase15_parameters | P1 high |  |
| DOD-159 | 15 | `uncertainty_multiplier` корректно inflate CI: confidence=0.5 → multiplier=2.0 | PASS | phase15_parameters | P1 high |  |
| DOD-160 | 15 | `ContextAdaptiveParameterBundle` — JSON Schema snapshot | PASS | phase15_parameters | P1 high |  |
| DOD-161 | 15 | `ResolveParametersNode` интегрирован в default workflow до JAX-шага | PASS | phase15_parameters | P1 high |  |
| DOD-162 | 15 | Тест e2e: SKG → select fiscal_multiplier для UA → выбирает CEE-region статью | PASS | phase15_parameters | P1 high |  |

## Laws

| Law | Status | Evidence | Severity | Notes |
|---|---|---|---|---|
| LAW-A (Import Gate) | PASS | gate_lint_imports; gate_lint_foundry | P3 low | Import/lint gates. |
| LAW-B (Foundry Pure) | PASS | causal_methods_suite | P3 low | Foundry causal method suites. |
| LAW-C (Contract-first snapshots) | PASS | gate_schema_ir; gate_schema_fabric | P3 low | Schema gates. |
| LAW-D (Reproducibility) | PASS | causal_methods_suite | P3 low | Deterministic/statistical tests. |
| LAW-E (Evidence) | PASS | ir_contracts_suite; phase12_transportability | P3 low | Lineage/evidence path. |
| LAW-F (Pure Step) | PASS | causal_methods_suite | P3 low | Pure-step contracts. |
| LAW-G (Graph Closure) | PASS | phase12_transportability | P3 low | Three-graph transport closure. |
| LAW-H (Stable Digest) | PASS | ir_contracts_suite | P3 low | Canonical serialization/digests. |
| LAW-K (Governance) | PASS | governance_suite | P3 low | Validation pipeline gates. |
| LAW-L (Literature-first) | PASS | phase9_reconciliation | P3 low | Literature prior checks. |
| LAW-S (Three-Layer) | PASS | phase9_reconciliation; phase12_transportability | P3 low | Layered conflict handling. |
| LAW-T (Transport-aware) | PASS | phase12_transportability | P3 low | Transportability contract checks. |
| LAW-V (SUTVA) | PASS | phase12_transportability | P3 low | SUTVA-aware transport checks. |

## SL Layers

| Layer | Status | Evidence | Severity | Notes |
|---|---|---|---|---|
| SL-1 (Canonicalization Layer) | PASS | phase0_quality_integration | P3 low | Phase 0 canonicalization path. |
| SL-2 (Lineage Chain) | PASS | ir_contracts_suite; phase12_transportability | P3 low | End-to-end lineage evidence. |
| SL-3 (Method Selection Diagnostics) | PASS | phase9_reconciliation | P3 low | Graph reconciliation diagnostics. |
| SL-4 (Three-Graph Closure) | PASS | phase12_transportability | P3 low | Transportability three-graph closure. |
| SL-5 (Canonical SCM Fixtures) | PASS | causal_methods_suite | P3 low | Causal fixture-rich suites. |
| SL-6 (Integration Test Matrix) | PASS | phase12_transportability; governance_suite | P3 low | Cross-layer integration. |
| SL-7 (Operational SLO) | PASS | phase0_quality_integration | P3 low | Operational quality baseline. |
| SL-8 (Data Governance) | PASS | governance_suite | P3 low | Governance checks. |
