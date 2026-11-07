# FED-01 — зерно данных, cell lineage, имена и numeric CONSENSUS

## 1. Решение

**Ограниченно оценён, не закрыт.** Для B138/B140/B141 найдены реальные исправления: cell-level origins переживают следующую композицию и выбранный persisted replay; JOIN заранее проверяет кратность, null identity и допустимое расширение; внутренние имена не уничтожают пользовательские поля. B145 теперь считает фактических участников и исключения, но остаются **C89-R01: finite aggregation overflow** и **C89-R02: singleton strict MEDIAN shortcut**.

Свежий результат: **5 MATCH; 36 unchanged existing bodies / 47 cases: 46 PASS, 1 Parquet BLOCKED**. Existing selected JSON producer → реальные файлы → fresh reader → повторная композиция исполнены. Это не native installed application: composer потребовал только скобки в трёх Python3.14 except headers во внешней runtime copy; parent initializers/telemetry изолированы.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Карточка](../05_Источники/FED-01_исходные_строки.txt) · [Pinned sources](../05_Источники/C89_источники.json).

**Уточнение C88:** UDF-05 завершил Ukraine subset, а не весь LANE-07. FED-01, FED-02 и CAL-01 остаются в LANE-07 до order91. Counts C88 и nextFED-01 были верны; прежний отчёт сохранён. [Явная erratum](../04_Проверки/C89_FED01/Уточнение_C88_очереди.md).

## 2. Матрица исходных IDs

| ID | Подтверждённая реализация | Остаток |
|---|---|---|
| B138 | Реальные origins каждой ячейки вместо first_metadata; JOIN/OVERLAY continuation; selected mixed parent reread | G01 native/Parquet; G02 unknown leaf history не issuer truth |
| B140 | many_to_one default; declared m:m с row budget; pre-materialization multiplicity/size; nulls не связываются без explicit flag | G01 full acquisition; G02 предметный смысл grain/aggregation |
| B141 | Fresh internal names/aliases; __source_id и *_left сохранены; all4 strategies persisted/nested corpus | G01 supported complete caller qualification |
| B145 | Strict invalid input refusal; partial contributions/exclusions/absence и physical occurrences | R01 finite result overflow; R02 scalar singleton policy; G02 units/independence |

LK04 соблюдён: маленький finite helper выполняет полезный boundary check и не заменён удалением. Scalar MEDIAN выбирает существующего производителя; CONSENSUS создаёт новый aggregate. Исправлять одну границу допустимости не значит смешивать эти операции.

## 3. Owner → persisted derivation → consumer

Composer хранит неизменяемый owner-held basis отдельно от mutable DataFrame attrs. В каждой ячейке — tokens выбранных физических occurrences и declarations. JOIN передаёт origins через обе стороны; конфликт ранжируется по настоящему leaf, а aggregate с несколькими origins нельзя притворно ранжировать как один trusted source. OVERLAY переносит origins заполненного значения (`S01`, `S02`).

До копирования/merge JOIN вычисляет нормализованные частоты ключей и размер каждого intermediate relation. Default many_to_one отказывает на duplicate right keys; explicit many_to_many требует join_max_rows. Неизвестные null не match по умолчанию, explicit matching учитывается в той же cardinality estimate. Это engineering/grain contract, не доказательство предметной идентичности (`S01:1032–1200`, `S03`).

Existing artifact owner сохраняет exact tagged scalars/dtypes, request, source bytes, result и lineage/summary. Fresh reader проверяет отдельно выбранный digest, заново открывает selected parents из независимо переданного registry, повторяет actual composition и сравнивает весь result/basis/summary. Чужие attrs и child-provided parent-frame не заменяют реальные parent bytes. Selected bytes могут быть recomputed, но leaf history остаётся consumer_asserted и результат — software_derivation_candidate (`S05`).

Это не только неиспользуемый helper: opt-in `fetch_federated` формирует captured source inputs, вызывает persist owner и canonical selected intake, а result сохраняет quality UNVERIFIED/completeness0 и explicit unknown-currentness/source-scope flags (`S11`). Этот service bridge прочитан, но registry/network/native execution не выполнялись. Shared receipt replay не удостоверяет научную независимость leaves.

## 4. Свежие проверки

1. **P01 — 20 PASS / 1 BLOCKED.** Существующие body tests проверяют тройной JOIN `[10,null]`/`[null,20]`/`[100,200]` → `[10,200]` с корректным B-origin второго значения; source mutation отказ; bounded m:m, null controls, pre-merge budget; реальные __source_id/value_left; finite/invalid strict consensus, mode и aligned audit values. Parquet body остановился на отсутствующем engine, не заменён fake serializer.
2. **P02 — 15 bodies / 26 cases PASS.** Actual JSON persist/reopen, mixed parent в обеих позициях, второй nested persistence, independently selected parent registry, tamper/ref forgery, copied/changed attrs refusal, per-column policy и physical occurrence identity. Во всех4 strategies одноисточниковый generated-looking name corpus переживает disk и nested continuation. Numeric partial consensus `[10,14,inf,bad,null]` даёт12, participants2/excluded2 с причинами; aggregate нельзя затем считать single trusted leaf. Erased copy допускается лишь как новый явно limited candidate, не как восстановленная history.
3. **P03 / R01.** Strict mean и strict median для `[1e308,1e308]` возвращают **inf**, хотя точный representable результат — **1e308**. Actual persist staging-readback и fresh selected replay сохраняют inf: participants2/excluded0. Входной finite check не контролирует арифметическое переполнение результата. NumPy RuntimeWarnings сохранены. Wire codec способен представить inf, а software replay честно повторяет тот же calculation — это не математическая корректность.
4. **P04 / R02.** Actual unchanged scalar resolver для `[inf,None]` и `[bad,None]` сначала фильтрует null, видит одного кандидата и возвращает invalid value с `single_source`, не вызывая strict MEDIAN validity. Numeric CONSENSUS с теми же values отказывает. Это различие admission, не требование равенства scalar winner и statistical aggregate.
5. **P05.** Actual OVERLAY создаёт `[10,20]` с разными origins; последующий JOIN с medium source даёт `[10,200]`, и конфликт20 действительно связан с low B. Полезное поячеечное происхождение не потеряно при другом strategy transition.

MATCH P03/P04 означает воспроизведение дефекта. Synthetic источники и declared trust не выданы за observed data или issuer attestation.

## 5. Сохранить и доработать

**Сохранить:** owned cell basis, selected-parent replay, limited leaf-history contract, explicit cardinality/null/row-budget controls, точные scalar/dtype profiles, обратимые internal aliases, actual participant/exclusion/absence identities, useful finite helper и distinction aggregate/source selection. Не dedupe повторяющиеся keys без предметного правила, не запрещать explicit bounded m:m и не объявлять null общим субъектом по удобству.

**C89-R01, medium/high confidence.** Численно устойчивое вычисление mean/even median и отдельная проверка конечности point result нужны до publication. Конечный representable aggregate нельзя превращать в inf только из-за промежуточной суммы. Relevant [calculation](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/connectors/federation/composer.py#L1718-L1724). Сохранить ordinary12, partial evidence counts и отдельно объявленный categorical mode. Не использовать успешный replay как oracle scientific validity.

**C89-R02, medium/high confidence.** Numeric validity strict MEDIAN следует согласовать до single-effective-candidate shortcut ([dispatch](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/connectors/federation/resolver.py#L105-L129)). Null остаётся отсутствием, inf/bad — другой случай. Нельзя менять полезную semantics FIRST_AVAILABLE/TRUST или заменять consensus выбором одного source ради общего helper.

Оба R ограничены текущим composer/resolver/selected artifact. Не установлено, что inf проходит дальше в ObservationRecord: соседний contract требует finite observed_value (`S08`). Не заявлено production воздействие, обход downstream governance или готовая policy recommendation.

**G01 — native activation.** Нужны supported Python3.14, настоящий pytest/Parquet, public facade и opt-in acquisition → typed receipt → independent reopen в разрешённом окружении. Сейчас native facade import BLOCKED TypeVar(default) в транзитивном module на Python3.12. Composer execution syntax-adapted, tracing no-op. Это не source defect от неподходящей среды.

**G02 — смысл данных.** Декларации grain, units, source scope, независимости и currentness требуют конкретных предметных evidence. Система честно ограничивает эти факты; отсутствие универсального verifier не само по себе дефект. Использовать существующие owner/boundary contracts, не строить параллельную universal provenance platform.

## 6. Проверяемость

[Commands/exit/logs](../04_Проверки/C89_FED01/commands.json) · [Diagnostics](../04_Проверки/C89_FED01/bounded_diagnostics.json) · [Native limits](../04_Проверки/C89_FED01/native_verification.json) · [Точные3 syntax replacements](../04_Проверки/C89_FED01/run01/syntax_adapter.json) · [Fixture limits](../04_Проверки/C89_FED01/fixture_authority_limits.json) · [Остатки](../01_Реестры/C89_остатки.json).

Run01 exit0, 5 MATCH, 46 PASS/1 BLOCKED. 35 bodies прошли, один Parquet body blocked; ни один native suite не заявлен. Core canon hashing, IR metadata DTOs и actual artifact modules не подменялись. Две parent shells, telemetry no-op, pytest helper и внешняя composer copy названы явно. JSON negative forgeries — test fixtures, не повреждение dossier archive.

Checkout чист; source/tests/config/dependencies не изменены, install/fetch/server не запускались. **89/127 рассмотрены ограниченно; следующий — FED-02. Фаза 2 не начата.**
