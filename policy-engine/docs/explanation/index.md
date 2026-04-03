# Explanation

> Контекст, обоснования и дизайн-решения за архитектурой PolicyOS.

Документы этого раздела объясняют **почему** система устроена именно так,
а не **как** с ней работать (для этого есть [How-to](../how-to/index.md))
и не **что** в ней есть (для этого есть [Reference](../reference/index.md)).

| Document | Topic |
|----------|-------|
| [Architecture](architecture.md) | Обзор системы, слои, зависимости |
| [Trinity](trinity.md) | ProblemFrame / PolicySpec / ModelSpec — разделение Why/What/How |
| [Freeze Policy](freeze-policy.md) | Architecture freeze, import gates, exception policy |
| [Causal Engine](causal-engine.md) | Каузальный pipeline: discovery → identification → estimation |
| [Governance Model](governance-model.md) | Pass registry, gates, human review |
| [Data Fabric](data-fabric.md) | Коннекторы, world store, data plane |
| [Lex Pipeline](lex-pipeline.md) | Правовой корпус, SPO, knowledge graph |
| [IR Design](ir-design.md) | Почему IR отделён от Foundry, Scientist, Fabric и Runtime |
| [Observation Contracts](observation-contracts.md) | Формальные data-to-model контракты для causal/calibration |
| [Security Model](security-model.md) | JWT, OPA, SPIFFE, CAS signing, FedRAMP |
