# CMP-03 — matching, semantic parity и точность выбранной связи
## C44 · 31 октября 2026 года

**Исходные IDs:** B47, B48. **Порядок:** 44/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит.

## Решение

Основная исходная поломка B47 исправлена: строится полный набор допустимых рёбер и применяется augmenting-path matching. B48 также имеет общий фактический semantic/structural контракт для auto и explicit, с отдельной финальной проверкой совместной полноты DAG.

Однако обнаружены **два ограниченных остатка**: неверные сообщения о выбранном source и потеря `prefer_exact_names` при равной полноте назначения. Оба прослежены до реальных consumers; численный результат и диагностическая строка различаются явно. **23 итоговых bounded MATCH; native tests BLOCKED.** MATCH здесь включает воспроизведённый дефект, не означает product PASS.

## 1. Матрица исходных IDs

| ID | Подтверждённая полезная реализация | Остаток |
|---|---|---|
| B47 | Полный допустимый двудольный граф, augmenting paths, сохранённые unit/shape/contract checks | R01 diagnostics; R02 предпочтения; G01 native; G02 содержательный смысл |
| B48 | Actual canonical semantic registry в обеих ветках; строгая pair completeness и final joint completeness; forbidden-edge recheck | G01 native; G02 научные пределы registry и matching |

[Полная карточка](../05_Источники/CMP-03_исходные_строки.txt), строки 5428–5529. Не требуется возвращать старый жадный алгоритм, ослаблять checks или запрещать полезную explicit composition.

## 2. Что действительно исправлено в B47

`_link_auto` сначала проверяет structural compatibility и `_check_semantic` для всех кандидатов, затем ищет увеличивающие пути. Выбранный `matched_source` сохраняется в actual `SlotBinding`. [S02:317–414](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/linker.py#L317-L414)

- **P01:** исходные flexible→A/B и fixed→B дают правильное полное назначение: `b_fixed→c_first`, `a_flexible→d_second`.
- **P02:** четыре дополнительных нейтральных переименования, включая обратный lexical order, сохраняют существование и уникальное назначение.
- **P03:** все **729** маленьких графов с тремя sources/targets и contracts `None/A/B` совпадают с независимым перебором 3! назначений по максимальной мощности: 583 полных, 120 размера 2, 24 размера 1, 2 пустых. Oracle не копирует реализацию augmenting paths. Это ограниченный алгоритмический census, не доказательство для всех shapes/units/семантик.
- **P09–P11:** несовместимые units, strict shapes и concrete contracts отвергаются в обеих ветках; различие классов исключения auto/explicit не маскируется.

**R02 — предпочтения не решаются для назначения целиком.** Candidates сортируются по score внутри каждого target, но targets обходятся по имени. В P22 один output `right` выбирается для первого input `left`; input `right` остаётся пустым, хотя `right→right` имеет ту же мощность и включён `prefer_exact_names=True`. Максимальная полнота соблюдена, заданное предпочтение — нет. [S02:365–390](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/linker.py#L365-L390) [S02:603–624](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/linker.py#L603-L624)

P23 проходит actual composer и оба consumers. Два outputs `left=10`, `right=20`; target считает `100*left+right`. Explicit mapping даёт **1020** при обоих порядках `connect`, sequential и async. Auto даёт **1020**, если первым подключён left, и **2010**, если первым подключён right. Existing composer исключает уже занятые inputs — **collision здесь нет**, оба DAG полные. Проблема именно в порядке выбора при равной полноте. [S01:592–616](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/composer.py#L592-L616)

Имена в этом witness нейтральные, поэтому не утверждается ошибочный причинный смысл данных. Узкий ремонт — соблюдать настроенное предпочтение среди максимально полных назначений в существующем owner. Содержательную неоднозначность по-прежнему разрешает явный mapping/контракт, а не удобное имя.

## 3. R01 — actual binding правильный, описание выбранного ребра нет

После выбора `matched_source` diagnostics используют оставшийся от предыдущего цикла `src_name`. Он участвует в exact-name check, тексте `Auto-linked`, `used` и списке alternatives. [S02:397–430](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/linker.py#L397-L430)

P15 на исходном исправленном примере реально связывает `a_flexible→d_second`, но сообщает **`Auto-linked: b_fixed -> d_second`** — ребро, которое concrete contracts B→A вообще не допускают. P20 аналогично выбирает `estimate_a`, а строка `used` называет `estimate_b`.

P16 добавляет removal-подобный контроль видимости: после rematching фактически `a→z`, `z→zz`, но stale `src_name=z` делает первое ребро ложно exact-name. Для `z` отсутствуют и Auto-linked, и Multiple compatible sources warnings, хотя до matching имелись два допустимых кандидата.

Это не только косметика промежуточного объекта. **P17:** actual IO и sequential/async используют правильные bindings и получают **2010** для исходного card witness, но несут неверные warnings. **P18:** actual checkpoint producer сохраняет их в atomic JSON, fresh `ChainCheckpoint.load` и resume восстанавливают два результата, делают **0 новых dispatches** и сохраняют ту же ложную строку. Доказана устойчивость ошибки diagnostics, не неправильное вычисление по ней. Replay проверяет согласованность сохранённой диагностики с current compiler, а не её содержательную истинность. [S09:372–444](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py#L372-L444) [S09:530–579](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py#L530-L579)

Сохранить полезный matching и actual bindings; исправлять только общий расчёт диагностического source и связанные проверки. Новый audit owner или параллельная архитектура не нужны.

## 4. B48 — паритет проверен на реальном canonical registry

В отличие от нейтральной name-semantic заглушки C43, здесь полный `slot_schema.py` исполнен в отдельном module. P04 canonical outcome→residual допускается в auto/explicit; P05 outcome→treatment отвергается в обеих ветках именно `SemanticCompatibilityError`; P06 preflight возвращает False. P07 исключает forbidden outcome edge, но сохраняет допустимый binary_treatment→treatment. [S13:139–165](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/slot_schema.py#L139-L165) [S02:258–286](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/linker.py#L258-L286) [S02:335–363](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/linker.py#L335-L363)

P08 обе strict pair ветки отвергают неполноту. P13 actual builder временно допускает partial edge и принимает объединение двух typed producers; auto/explicit × sequential/async дают **30**. В этом контроле разные contracts L/R делают назначение однозначным независимо от имён. P14 final checker отвергает действительно недостающий input. P21 final chain validation повторно обнаруживает вручную испорченное семантическое ребро, хотя shape/unit compatible. [S02:216–228](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/linker.py#L216-L228) [S02:470–535](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/linker.py#L470-L535)

**Bounds не объявлены hard gate.** P12 воспроизводит документированный warning-only контракт для непересекающихся диапазонов в обеих ветках. Первоначальный audit oracle ожидал отказ ошибочно; ошибка сохранена, а не превращена в product defect. [S05:360–381](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/types/checker.py#L360-L381)

## 5. Содержательная способность и пределы

Реальная цепочка typed signature → admissible links → compiled DAG → IO/consumer → checkpoint/readback существует в данном ограниченном контуре. Но unknown slot names по текущему registry означают «не ограничено», не «смысл доказан» (P19). Полный matching двух неоднозначных estimates может сохранить warning, но не выбрать научно правильный estimate (P20). Разрешение outcome→residual само не вычисляет регрессию и не устанавливает предпосылки модели.

Сохранять actual semantic checks и useful explicit route. LLM может предложить связь, существующий контракт/adapter и evidence должны обосновать её использование; не нужен универсальный deterministic изобретатель моделей. Synthetic arithmetic и 729 contract graphs не являются empirical authority. Научная и native квалификация отделены как G02/G01.

## 6. Проверки и честная история

Прочитан весь `test_cmp_03.py`, 255 строк. Native команда завершилась до collection: `No module named pytest`, exit 1. Итоговый external probe: **23 MATCH / 0 ERROR**. Предыдущие попытки сохранены: 19/2 (неполный harness и неверное имя bounds аргумента), 20/1 (ошибочное ожидание hard bounds gate), 22/1 (ошибочное ожидание collision без учёта composer filtering). Менялся только внешний probe; исходники и зависимости нет.

Actual owners выполнялись из точных исходных определений; registry, dispatcher и result/provenance metadata остаются явными fixtures. Native installed imports, backend attestation, FX/JAX/Ray и authoritative publication не заявлены.

[Диагностика](../04_Проверки/C44_CMP03/bounded_diagnostics.json) · [Команды и неудачные попытки](../04_Проверки/C44_CMP03/commands.json) · [Границы](../04_Проверки/C44_CMP03/native_verification.json) · [Источники](../05_Источники/C44_источники.json) · [Остатки](../01_Реестры/C44_остатки.json).

**44/127 пакетов рассмотрены ограниченно; 105 уникальных B/LA частично оценены. Следующий — JIT-01. Полного закрытия нет.**
