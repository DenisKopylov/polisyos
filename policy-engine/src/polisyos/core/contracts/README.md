# Contracts — Типизированные контракты

Типизированные контракты взаимодействия между модулями PolisyOS. Каждый контракт — typed-ссылка (`ArtifactRef` с `Literal` kind/media_type), обеспечивающая типобезопасность на границах модулей.

## Архитектура

```
contracts/
├── fabric.py          # Fabric: запросы, планы, evidence, результаты (7+ типов)
├── foundry.py         # Foundry: графы, IR, state, симуляции, patches (15+ типов)
├── trinity.py         # Trinity: ProblemFrame, PolicySpec, ModelSpec
├── lex.py             # Lex: NormPack, compliance, RuleBackend protocol
├── scientist.py       # Scientist: эксперименты, failure cards, decision cards (11 типов)
├── scholar.py         # Scholar: ResearchIntent, KnowledgeBundle
├── compiler.py        # Compiler: отчеты компиляции/линковки
├── backtest.py        # Backtesting: BacktestReportRef
├── causal.py          # Causal inference: CausalEffectReportRef
├── distributional.py  # Distributional analysis: DistributionalReportRef
├── hte.py             # HTE: HTEResultRef, PolicyRecommendationRef
├── uncertainty.py     # Uncertainty: UncertaintyEnvelopeRef
├── legal.py           # DEPRECATED shim → lex.py
└── __init__.py        # Реэкспорт всех контрактов (193 символа в __all__)
```

## Паттерн контрактов

Все контракты наследуют `ArtifactRef` и фиксируют `kind` / `media_type` через `Literal`:

```python
class FabricResultRef(ArtifactRef):
    kind: Literal["fabric.result_bundle"] = "fabric.result_bundle"
    media_type: Literal["application/json"] = "application/json"
```

## Fabric Contracts

Обработка данных, агрегация, evidence management.

| Контракт | Kind | Назначение |
|----------|------|------------|
| `DataViewRequestRef` | `fabric.data_view_request` | Запрос на представление данных |
| `QueryPlan` / `QueryPlanRef` | `fabric.query_plan` | План запроса с шагами выполнения |
| `EvidenceBundle` / `EvidenceBundleRef` | `fabric.evidence_bundle` | Пакет доказательств с provenance и quality indicators |
| `FabricResult` / `FabricResultRef` | `fabric.result_bundle` | Результат обработки с метаданными |
| `UncertaintyBounds` / `UncertaintyBoundsRef` | `fabric.uncertainty_bounds` | Границы неопределенности |
| `WarningsBundle` / `WarningsRef` | `fabric.warnings` | Предупреждения о проблемах |
| `DataSnapshot` / `DataSnapshotRef` | `fabric.data_snapshot` | Фиксированный снапшот данных |

## Foundry Contracts

Симуляция и исполнение политик: программные графы, state management, patches, cost modeling.

**Компиляция и IR:**
- `ProgramGraph` / `ProgramGraphRef` — граф программы с узлами и операциями
- `LoweredIR` / `LoweredIRRef` — пониженное IR для исполнения
- `CompileRequest` / `CompileResult` — запрос и результат компиляции
- `FoundryCompileConfig`, `FoundryValidationFlags` — конфигурация компиляции

**Исполнение:**
- `ExecPlan` / `ExecPlanRef` — план исполнения с environment tracking
- `ExecConfig` / `ExecConfigRef` — конфигурация исполнения
- `ExecuteRequest` / `ExecuteResult` — запрос и результат исполнения
- `FoundryExecConfig` — расширенная конфигурация
- `TreasurySeed` / `TreasurySeedRef` — сид для deterministic execution

**State management:**
- `StateSnapshot` / `StateSnapshotRef` — снапшоты состояния
- `StateDelta` / `StateDeltaRef` — patch-based обновления состояния

**Результаты и мониторинг:**
- `SimulationResult` / `SimulationResultRef` — результаты симуляции
- `Metrics` / `MetricsRef` — метрики исполнения
- `TraceSliceRef` — срезы трассировки
- `CalibrationReportRef` — отчеты калибровки
- `EnvironmentManifestRef` — ссылка на манифест окружения
- `DerivedArtifact` — производные артефакты

## Trinity Contracts

Фундаментальные спецификации: "почему" → "что" → "как".

| Контракт | Назначение |
|----------|------------|
| `ProblemFrameRef` | Контекст и требования к политике ("почему") |
| `PolicySpecRef` | Структура и поведение политики ("что") |
| `ModelSpecRef` | Модель мира и компоненты ("как") |
| `TrinityBundle` / `TrinityBundleRef` | Полный bundle всех трех спецификаций |
| `TrinityManifest` | Манифест с версиями |

## Lex Contracts

Compliance-валидация политик и pluggable rule backends.

- `NormPack` / `NormRef` / `NormRule` / `RuleType` — нормативные пакеты и правила
- `RuleBackend` (Protocol) — pluggable backend для валидации
- `ComplianceIssue` / `IssueSeverity` — проблемы compliance (BLOCKER/CRITICAL/WARNING/INFO)
- `LegalContext` / `LegalEvaluationRequest` / `LegalReport` / `LegalReportRef` — контекст и результаты валидации
- `ChangeProposal` / `ChangeProposalRef` — предложения изменений
- `NormDiffRef` / `NormImpactReportRef` — diff и impact analysis нормативных пакетов

## Scientist Contracts

Оркестрация экспериментов и жизненный цикл политик.

| Контракт | Назначение |
|----------|------------|
| `ExperimentStateRef` | Снапшоты экспериментального состояния |
| `DecisionPacketRef` | Пакеты решений |
| `DecisionCardRef` | Детерминированные сводки (verdict, generated_at) |
| `FailureCardRef` | Карты неудач (attempt_number, error_code, can_retry) |
| `CritiqueRef` | Оценки критика |
| `TimelineRef` | Таймлайны экспериментов (event_count, duration) |
| `TrinityIRRef` | TrinityBundle с версиями и статусом |
| `CheckpointRef` | Контрольные точки |
| `GovernanceReportRef` | Отчеты governance |
| `SensitivityResultRef` | Результаты анализа чувствительности |
| `StressTestReportRef` | Отчеты стресс-тестирования |

## Scholar Contracts

ABI-стык для исследовательского обогащения.

- `ResearchIntent` / `ResearchIntentRef` — запросы на исследование (domain, topic, jurisdictions, time_window, budgets)
- `KnowledgeBundle` / `KnowledgeBundleRef` — пакеты знаний
- `BudgetsV1` / `ThresholdsV1` — бюджеты и пороги
- `SourceKind` / `SourceSpec` — источники данных

## Analytical Contracts (IR-домен)

Контракты для аналитических подсистем — каузальный анализ, backtesting, distributional analysis.

| Контракт | Kind | Назначение |
|----------|------|------------|
| `BacktestReportRef` | `ir.backtest_report` | Результаты backtesting-анализа политик |
| `CausalEffectReportRef` | `ir.causal_effect_report` | Результаты оценки каузальных эффектов |
| `DistributionalReportRef` | `ir.distributional_report` | Результаты distributional analysis |
| `HTEResultRef` | `ir.hte_result` | Heterogeneous treatment effects |
| `PolicyRecommendationRef` | `ir.policy_recommendation` | Рекомендации политик на основе HTE |
| `UncertaintyEnvelopeRef` | `ir.uncertainty_envelope` | Результаты квантификации неопределенности |

## Compiler Contracts

- `CompileReportRef` — отчет компиляции политики (`compiler.compile_report`)
- `LinkReportRef` — отчет линковки программы (`compiler.link_report`)
