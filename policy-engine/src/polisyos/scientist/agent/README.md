# Agent (`polisyos.scientist.agent`)

`agent` — опциональный policy-authoring контур Scientist: PI, drafter, formalizer,
critic, reflexion и supporting RAG/feasibility инструменты для генерации и ревью
policy artifacts до их передачи в runtime.

## Роль в системе

- **Зависит от:** `ir`, `llm`, `core.llm`, `lex`, `core.artifacts`
- **Используется в:** policy authoring, critique/reflexion loops, optional search integrations
- Пакет не является обязательной частью `run_experiment()`, но формирует upstream
  policy/problem artifacts для policy-design workflows.

## Ключевые концепции

- **Role protocols** — `PIAgent`, `DrafterAgent`, `FormalizerAgent`, `CriticAgent`.
- **Mock + LLM implementations** — тестовый и production-like execution modes.
- **Multipass drafting** — staged drafter with optional RAG and verification hooks.
- **Reflexion/memory** — short-term memory, failure cards, retry-aware critique loops.
- **Informed critic** — feasibility, norm loading, RAG and code verification integration.
- **Lazy exports** — package deliberately избегает eager import chain.

## Public API

- Протоколы и typed contracts: `ProblemFrame`, `DraftResult`, `CritiqueReport`,
  `DataNeedSpec`, `DelegationResult`
- Factory/helpers: `create_drafter_agent(...)`, `create_critic_agent(...)`
- Основные реализации: `LLMPIAgent`, `LLMDrafterAgent`, `LLMFormalizerAgent`,
  `LLMCriticAgent` и mock-аналоги
- Supporting tools: `RAGConfig`, `CASRAGIndex`, `CodeVerificationSandbox`,
  `DuckDBFeasibilityProbe`, `FailurePatternIndex`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 45
- Exports: 60
- Public surface intentionally broad; imports остаются lazy для защиты от circular dependencies
