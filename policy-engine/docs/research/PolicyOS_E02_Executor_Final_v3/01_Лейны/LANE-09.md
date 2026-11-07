# LANE-09 — Scholar byte provenance и LLM reuse/accounting

**Статус: исполнительское ТЗ, NOT_IMPLEMENTED; все будущие TEST — NOT_RUN.**

## Точный состав

- [SCL-01](../02_Пакеты/SCL-01.md) · [JSON](../04_Трассировка/SCL-01.json)
- [SCL-03](../02_Пакеты/SCL-03.md) · [JSON](../04_Трассировка/SCL-03.json)
- [LLM-01](../02_Пакеты/LLM-01.md) · [JSON](../04_Трассировка/LLM-01.json)
- [LLM-02](../02_Пакеты/LLM-02.md) · [JSON](../04_Трассировка/LLM-02.json)

## Порядок и единые owners

1. SCL-01 current fetch/cache policy и absolute failover deadline → SCL-03 raw-ref preservation/fetch metadata→actual docs consumer. Offline initial URL/saved-content admission предшествует cache return; live DNS выполняется лишь на разрешённом fresh fetch, не блокирует eligible persisted reuse. Common Scholar fetcher — один sequential writer.
2. LLM-01 budget/trace isolation и shared optional-tracer fallback → LLM-02 guarded singleflight readmission и finite TranslatorInputBundle reuse closure. Existing factory/ledger/settlement owners не заменяются вторым accounting service.
3. LLM-01 owns PolicyOSTracer optional no-op signature/callback compatibility; LLM-02 consumes it. LLM-02 не вводит NL tools cache или меняет default temperature0.1. Только explicit temperature0 path eligible в declared scope.
4. Все четыре пакета — CP2. Scholar fetch и LLM transport may use controlled providers; actual CAS/binding/ledger/currentness gates не заменяются permissive fixtures для native acceptance.

## Связанная содержательная приёмка

- **E02-I09-A:** actual captured raw response/snapshot → snippets → manual normalization/enrichment → real document ingress/fresh read. Raw bytes/ref/profile/size связаны, search snippet не выдаётся за полный документ или verification.
- **E02-I09-B:** current factory → eligible exact prepared request → one backend miss/singleflight/reuse → per-consumer accounting settlement/trace → translator result. Shared revision race допускает bounded fresh guarded readmission, не bypass authorizer.

Finite six-role translator closure включает только реально поддержанные input roles и явно фиксирует unknown/uncovered material. Не каждая URL строка есть fetch request. Semantic LLM proposal отделён от проверяемых execution inputs, evidence и outputs.

Канонический [integration contract LANE-09](../03_Интеграция/LANE-09.md) задаёт exact E02-I IDs и общий evidence set. Локальные regressions сохраняют свои exact oracles; shared success не заменяет failing-before/removal controls.

## Положительная способность и пределы

LLM-02 positive strict reuse path обязателен: current materialized input bundle, actual translator explicit T0 без tools, selected CAS/owner admission и полезный PolicyBrief. Refusal всех запросов не считается завершённой capability. SCL-03 source bytes до actual docs consumer обязательны; восстановление текста из excerpt не допустимо. Optional trace отказ не маскирует provider/mandatory accounting outcome; unknown settlement/recovery отдельно наблюдаемы.

## Qualification и передача

Supported Python >=3.14,<3.15 и фактически resolved dependencies/lock. Передать commit/write map, requirements→tests, actual commands/exits/logs, native/fixture distinction, selected input/output hashes и fresh-reader assertions. Изолированные inputs/provider doubles разрешены согласно пакетам; product CAS/DB/HNSW/ledger/consumer не подменять при native claim. Historical audit passes и independent arithmetic calculators не становятся current native suite PASS. Установки, deployment и внешние mutations требуют отдельного разрешения.

Design alignment: [Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) и [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md). Совместимые новые inputs идут через общий contract; новая семантика может требовать нового обоснованного кода. Guards и evidence не подменяют полезную работу, LLM semantic proposal не подменяет executable truth.
