# LANE-08 — Catalog/embedding generations и устойчивый ingest

**Статус: исполнительское ТЗ, NOT_IMPLEMENTED; все будущие TEST — NOT_RUN.**

## Точный состав

- [DFK-02](../02_Пакеты/DFK-02.md) · [JSON](../04_Трассировка/DFK-02.json)
- [DFI-01](../02_Пакеты/DFI-01.md) · [JSON](../04_Трассировка/DFI-01.json)
- [DFI-02](../02_Пакеты/DFI-02.md) · [JSON](../04_Трассировка/DFI-02.json)
- [EMB-01](../02_Пакеты/EMB-01.md) · [JSON](../04_Трассировка/EMB-01.json)
- [EMB-02](../02_Пакеты/EMB-02.md) · [JSON](../04_Трассировка/EMB-02.json)
- [EMB-03](../02_Пакеты/EMB-03.md) · [JSON](../04_Трассировка/EMB-03.json)
- [DFI-03](../02_Пакеты/DFI-03.md) · [JSON](../04_Трассировка/DFI-03.json)
- [ING-01](../02_Пакеты/ING-01.md) · [JSON](../04_Трассировка/ING-01.json)
- [ING-02](../02_Пакеты/ING-02.md) · [JSON](../04_Трассировка/ING-02.json)
- [ING-03](../02_Пакеты/ING-03.md) · [JSON](../04_Трассировка/ING-03.json)
- [NET-01](../02_Пакеты/NET-01.md) · [JSON](../04_Трассировка/NET-01.json)
- [NET-02](../02_Пакеты/NET-02.md) · [JSON](../04_Трассировка/NET-02.json)

## Порядок и единые owners

1. DFK-02 canonical catalog policy и DFI-01 leaf independence → DFI-02 counters/facade/native ingest. LA-038 accountable closure у DFI-02, phase1 не засчитывается как полная миграция.
2. EMB-01 native compute → EMB-02 semantic preselection → EMB-03 Legal incremental/owned serving. LA-039 accountable у EMB-02, LA-040/042 у EMB-03. Один kernel publisher, не третий Legal writer.
3. DFI-03 принимает EMB-02 selected generation contract и исправляет harvest receipt/CLI resume. Shared catalog pipeline.py sections: DFI-02 counters, EMB-02 embedding consumption, DFI-03 receipt/resume. Один sequential file writer с review всех consumers.
4. NET-01 lifecycle и ING-01 cursor/replay → ING-02 frontier/state/lineage → ING-03 exact bytes/schema. Shared streaming.py sections не редактируются конкурентно. NET-02 rate/circuit feedback независим по файлам, затем общий transport witness.
5. Все 12 пакетов — CP2. Native P-CORE/P-DATA дополняются конечным P-INDEX: actual hnswlib0.8.0 native build/OS/ABI. Для owned Legal serving отдельно P-LEGAL-OWNED: rag-local/ST2.7.0, runtime по lock и заранее предоставленные local CPU1024 assets. GP backend не prerequisite этой embedding цепи. Missing native material → NOT_QUALIFIED, не fake encoder PASS; одна общая heavy suite, не дубликат на каждый packet.

## Связанная содержательная приёмка

- **E02-I08-A:** rich canonical source policy → native core ingest → current receipts/resume → fresh Fabric consumer. Catalog-only metadata selection не требует executable connector, но execution guard сохраняется.
- **E02-I08-B:** actual DB projections → native NPZ/HNSW staged generation → semantic preselection → fresh guarded readers/search. Legal owned runtime material даёт положительный supported served query; generic candidate и source-relation authority различаются.
- **E02-I08-C:** actual finite source/transport → ingestion/cache/PII/CAS/evidence → cursor/window/restart/quarantine → fresh served consumer. Physical cleanup, deadline/rate/circuit и replay egress controls проверяются реальными owners.

Канонический [integration contract LANE-08](../03_Интеграция/LANE-08.md) задаёт exact E02-I IDs и общий evidence set. Локальные regressions сохраняют свои exact oracles; shared success не заменяет failing-before/removal controls.

## Положительная способность и пределы

Важные положительные работы: EMB-03 supported owner→producer→served query; ING-01 useful incremental materialization и multi-namespace replay для однозначного declared layout; ING-02 withdrawal A→dependent window revalidation; ING-03 bounded valid stream без смены окна. Ambiguous identical request hash в разных replay namespaces отказывает до partial execution, а не выбирает похожую запись. Finite source evidence не переносится автоматически на live completeness/rights. Legal candidate search полезен, но не выдумывает независимую source-relation verification. Honest unsupported disk spill допустим; имя стратегии само по себе не implementation.

## Qualification и передача

Supported Python >=3.14,<3.15 и фактически resolved dependencies/lock. Передать commit/write map, requirements→tests, actual commands/exits/logs, native/fixture distinction, selected input/output hashes и fresh-reader assertions. Изолированные inputs/provider doubles разрешены согласно пакетам; product CAS/DB/HNSW/ledger/consumer не подменять при native claim. Historical audit passes и independent arithmetic calculators не становятся current native suite PASS. Установки, deployment и внешние mutations требуют отдельного разрешения.

Design alignment: [Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) и [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md). Совместимые новые inputs идут через общий contract; новая семантика может требовать нового обоснованного кода. Guards и evidence не подменяют полезную работу, LLM semantic proposal не подменяет executable truth.

## Уточнения технического ревью v2

DFI-03 direct harvest переиспользует existing async selected-stage admission/completion, не synchronous benchmark/QC/publish helper; off-only resume=False не закрывает smart currentness. Для stronger retrieval claim E02-I08-B раздельно принимает finite index-topology witness и predeclared relevance/holdout utility; exact cosine reference не универсальная exact ANN гарантия. Это не gate локального publisher repair. Cost — measurement-first cold/warm breakdown, без обязательного нового lease/cache и без stat-only trust. Shared integration profile формулировки согласует общий integrator.
