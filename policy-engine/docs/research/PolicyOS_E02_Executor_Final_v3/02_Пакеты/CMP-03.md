# CMP-03 — Полное и семантически одинаковое ручное/автоматическое связывание

## 1. Паспорт и результат

**LANE-04 · CP-1 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B47, B48. Тип: два узких ремонта + native квалификация.

Исправить достоверность selected-edge diagnostics и предпочтения среди максимально полных matching, сохранив все structural/semantic gates и полезный explicit route.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/CMP-03.md), [все остатки](../05_Основания/Аудит/01_Реестры/C44_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/CMP-03_исходные_строки.txt), исходный объединённый план §CMP-03 (исторические строки 5428–5529).

## 2. Уже работает — сохранить

- Полный admissible graph строится до выбора; augmenting-path способность перераспределять flexible source ради полноты сохраняется.
- Explicit mapping, unit/shape/contract checks и canonical semantic registry остаются общими с auto; unknown семантика означает unconstrained, не доказанную корректность.
- Strict pair link требует полноты пары, composer допускает partial edge и проверяет joint DAG completeness; уже занятые auto target inputs исключаются.
- Bounds overlap остаётся warning-only согласно текущему checker, не новый hard gate.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C44-R01 | fix: Diagnostics ошибочно используют stale src_name; привязать каждую строку к actual matched_source. | REQ-CMP-03-01 |
| C44-R02 | fix: Оптимизировать предпочтения назначения целиком после максимальной мощности, не только локальную очередь target. | REQ-CMP-03-02 |
| C44-G01 | qualify: Все oracles повторить с native compiler/dispatcher/checkpoint в P-CORE, не подменяя registry. | REQ-CMP-03-01, REQ-CMP-03-02, REQ-CMP-03-03 |
| C44-G02 | qualify: Типы и именованный allowance не являются residualization или эмпирическим обоснованием; explicit meaningful choice сохраняется. | REQ-CMP-03-03 |

### Исходные обязанности, не только новые R

- B47: сначала максимальная полнота допустимого назначения, затем configured preferences; flexible/fixed witness и нейтральные переименования должны сохранять существование решения (REQ02).
- B48: одинаковая обязательная semantic/structural оценка auto/explicit, pair versus whole-DAG completeness и explicit adapter path; никаких научных claims из matching (REQ03).

## 4. Нормативный контракт

### REQ-CMP-03-01
SlotLinker._link_auto выводит exact-name decision, Auto-linked, used и alternatives из выбранного matched_source/SlotBinding, а не loop-local source предыдущего обхода. Каждая строка называет допустимое фактическое ребро; alternatives исключают только выбранный source. Rematching не может ложно подавить warning. Correct binding и numerical result неизменны, corrected diagnostics доходят до result и fresh checkpoint readback.

Источник: B47, B48; аудит: C44-R01, C44-G01; проверки: TEST-CMP-03-01.

### REQ-CMP-03-02
Среди admissible assignments auto сначала максимизирует число связанных targets, затем лексикографически суммарные компоненты существующего _score_candidate (при prefer_exact_names=True exact-name первая компонента), затем стабильный tie-break по sorted(target,source). Имя не может уменьшить полноту. Единственный output right при inputs left/right выбирает right→right; два отдельных producers left=10/right=20 для 100*left+right дают1020 при обоих connect orders. prefer_exact_names=False отключает именно name preference; не обещать общую connect-order независимость для содержательно неоднозначного многорёберного DAG.

Источник: B47, B48; аудит: C44-R02, C44-G01; проверки: TEST-CMP-03-02.

### REQ-CMP-03-03
Auto/explicit применяют один admissibility contract: canonical outcome→residual допустим, outcome→treatment запрещён; binary_treatment→treatment допустим. Unit/shape/concrete-contract mismatch остаются отказом, bounds mismatch warning-only. Composer joint typed sources L/R дают30 при полной связке; неполный DAG и tampered forbidden edge отвергаются финальной проверкой. Unknown names не получают semantic attestation; содержательно неоднозначный estimate требует explicit mapping/существующего adapter, а не arbitrary matching.

Источник: B47, B48; аудит: C44-G01, C44-G02; проверки: TEST-CMP-03-03.

## 5. Техническое решение и producer → consumer

В _link_auto оставить построение полного admissible candidate_edges и общий checker. Исправление R01 локальное: после matched_targets lookup единственный selected name = binding.source_slot; exact_name/used/alternatives строить от него. R02 оформить как общий maximum-cardinality, preference-optimal bipartite assignment в том же owner: допустим min-cost augmenting-path flow, где сначала достигается максимальная мощность, затем минимизируется cost, эквивалентный лексикографическому максимуму сумм пяти _score_candidate components. При integer encoding каждый старший разряд должен превышать максимально возможную сумму младших для фактического n; либо сравнивать score tuples напрямую без float magic constants. Stable tie-break только после score. Не использовать exhaustive 3! oracle как production algorithm; не ставить произвольный лимит с отказом ранее поддержанных больших inputs. Существующий composer filtering занятых target slots сохранить; данный repair меняет локальное оптимальное назначение, не вводит глобальный scientific planner. Выбранные binding/diagnostics проходят current chain checks, IO, execution и checkpoint; mismatch старых persisted diagnostics с новым compiler — честный existing reconciliation отказ, не тихое переписывание истории.

### Проверенные owners на срезе
- policy-engine/src/polisyos/foundry/methods/components/linker.py: SlotLinker._link_auto, _score_candidate, validate_chain
- policy-engine/src/polisyos/foundry/methods/components/composer.py: MethodComposer.connect
- policy-engine/src/polisyos/foundry/methods/components/slot_schema.py: is_semantically_compatible
- policy-engine/src/polisyos/foundry/methods/types/checker.py: check_slot_compatibility

Можно сохранить augmenting-path implementation и добавить cost-aware residual improvement до optimum; обязательны cardinality/score oracle и отсутствие exponential production search. Одной сортировки targets недостаточно для общего заявленного preference contract.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-CMP-03-01
- Уровень: native linker + executors + persistence.
- Setup: Flexible a_flexible(None)/b_fixed(B)→c_first(B)/d_second(A), actual methods output values producing2010; rematch a→z,z→zz; native checkpoint.
- Действие: Inspect binding+all diagnostics, sequential/async execute, save/read/resume; compare old stale-source implementation as negative control.
- Точный oracle: Binding fixed→first/flexible→second; diagnostic names exactly bindings (never forbidden b_fixed→d_second); rematch warnings not suppressed by stale name; numerical2010 preserved; checkpoint returns2 results,0 new dispatch and same corrected diagnostics.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CMP-03-02
- Уровень: algorithm unit + native composer.
- Setup: Single right output vs left/right inputs; two native producer nodes left10/right20→100*left+right; flexible/fixed and independent brute-force small contract graph oracle.
- Действие: Run both connect orders, names permutations, preference on/off; enumerate729 3×3 None/A/B contract graphs and compare cardinality+objective to independent exhaustive assignments.
- Точный oracle: right→right when preference on; both DAG orders1020; all graph cardinalities agree (baseline583 full,120 size2,24 size1,2 empty for unchanged census); chosen objective maximal among max-cardinality solutions. Flexible/fixed remains complete. Old algorithm fails single-source/preference witness.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CMP-03-03
- Уровень: unit + targeted native integration.
- Setup: Real canonical slot_schema and checker, no semantic stub; units/shapes/contracts incompatible cases, bounds warning, explicit typed L/R producers, unknown estimate names.
- Действие: Run auto/explicit pair and full composer finalize; corrupt a selected edge; execute accepted full DAG sequential/async.
- Точный oracle: Same accept/reject meaning in both branches, preserving existing exception classes; typed full output30, incomplete/forbidden refuse; bounds accept withwarning; unknown accepted only as unconstrained. No claim allowance computes residualization.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_cmp_03.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: tiny deterministic methods, independent exhaustive oracle ограниченных графов. Запрещено: semantic registry stub в native parity; fake checkpoint writer; выключение unit/shape/contract gate.

## 7. Общая интеграция и порядок

Shared linker/composer lease с CMP-02; corrected warnings проходят его context/checkpoint checks. Native compile→two executors witness общий, не отдельный тяжёлый pipeline.

Точные общие сценарии: E02-I04-A из [контракта интеграции](../03_Интеграция/LANE-04.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: CMP-02; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Intended delta: preference-correct assignments и truthful diagnostics; may change auto result where previous preference violated. Explicit mapping remains stable escape route. Old checkpoint diagnostics not rewritten; rebuild/reexecute when reconciliation rejects incompatible old compiler context.

## 9. Free-grow и design direction

- Автоматический поиск обслуживает расширяемый typed contract, но не изобретает семантику данных.
- Сохранённый warning — evidence of compiler decision, поэтому должен описывать actual edge; долговечность не превращает ложное сообщение в истинное.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

## 10. Нерешённые решения и передача

Новых блокирующих продуктовых решений не требуется. Реальную доступность supported runtime установить до native проверки; недоступность оформлять NOT_RUN, не PASS.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для native численных/JIT/train проверок P-JAX (тот же lock, JAX/jaxlib/optax, deterministic tiny CPU); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.


Полные probes исходного аудита доставлены отдельно в phase1 ZIP; ссылки аудита на них не означают включение тяжёлой evidence в этот исполнительский комплект.
