# STR-01 — Раздельные occurrence counts и независимый selected intent

**LANE-10 · B106, B107 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Полезный stress worst-case и фактическая доля проверенного множества не зависят от top-k и не присваивают себе право выбора objective.

**Тип:** C119-R01 count fix; C119-G01 selected-intent capability; C119-G02 native qualification.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/STR-01.md), [исходные карточки](../05_Основания/Аудит/05_Источники/STR-01_исходные_строки.txt), [трассировка](../04_Трассировка/STR-01.json).

## 2. Уже работает — сохранить

- Typed direction до sampling; единый badness, raw adaptive history.
- Occurrence counts до dedupe/top-k; empty/partial не robust.
- Unbound score refusal и exact source/selected-profile guards; diagnostics полезны без authority.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| B106 | fix | REQ-STR-01-01, REQ-STR-01-02, REQ-STR-01-03 | Pre-top-k fixed, unavailable valid count remaining и source-intent positive gap. |
| B107 | qualify | REQ-STR-01-02, REQ-STR-01-04 | Actual direction fixed; native CompositeObjective route проверить. |
| C119-R01 | fix | REQ-STR-01-01 | total-invalid считает unavailable valid. |
| C119-G01 | capability | REQ-STR-01-03 | Нужна actual selected request/run-state связь, не снятие отказа. |
| C119-G02 | qualify | REQ-STR-01-02, REQ-STR-01-04 | Native strategy/CAS/Level5 отдельно от fixture. |

## 4. Нормативные требования результата

**REQ-STR-01-01.** Valid count должен исключать unavailable и invalid occurrences, сохраняя attempted и разные причины без переименования unknown в numerical invalid.

**REQ-STR-01-02.** Search/worst/threshold/stopping должны использовать одну typed direction и raw value; presentation cap/dedup не меняют occurrence counters.

**REQ-STR-01-03.** Protected finite score должен связываться с independently selected request/run-state objective intent, exact candidate/plan/outcome profiles; self-carried rule не основание.

**REQ-STR-01-04.** Native CompositeObjective/StrategyAdapter/persisted fresh consumer должны сохранять useful diagnostics и unbound refusal при отсутствии intent; finite inspected fraction не population probability.

## 5. Конкретное техническое решение — рекомендуемый способ

- В adversarial.py report metadata считать valid=total_evaluated−invalid−unavailable либо increment explicit valid at admitted finite outcome; предпочтительно derive from mutually exclusive outcome status ledger и assert conservation. Не менять score guard.
- Census current request/run-state objective selection and source profiles, передать exact existing selected-intent reference в stress evidence; fresh stress_report resolver independently resolves и сравнивает direction/threshold/subject/plan. Если producer отсутствует, конкретный typed binding proposal, не producer available=true.
- Сохранить badness owner stress_report.py и actual main loop; retired NegatedCompositeObjective не исправлять как будто он current owner. Existing direction/adversarial tests расширить, нового optimizer не создавать.

**Существующие code/test owners:**
- [`src/polisyos/scientist/methods/search/adversarial.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/adversarial.py).
- [`src/polisyos/scientist/methods/doe/stress_report.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/stress_report.py).
- [`src/polisyos/scientist/methods/search/objective.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/objective.py).
- [`tests/unit/scientist/search/test_adversarial_direction_c49.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/search/test_adversarial_direction_c49.py).
- [`tests/unit/scientist/search/test_adversarial.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/search/test_adversarial.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-STR-01-01 → REQ-STR-01-01

**Уровень:** actual stress report. **Ожидается:** positive + negative + boundary.

**Setup:** Один unavailable; один invalid; один valid; mixed3.

**Действие:** Actual run_stress_test→metadata, top-k1/10.

**Oracle:** Single unavailable attempted1/unavailable1/invalid0/valid0; mixed valid1. Partition counts sum attempted; robustness None для incomplete, причины preserved.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-STR-01-02 → REQ-STR-01-02

**Уровень:** direction table. **Ожидается:** positive + negative + boundary.

**Setup:** Utility values10/−5 threshold0; cost−5/10; typed invalid direction.

**Действие:** Run direct/adaptive routes.

**Oracle:** Worst utility−5/cost10; severity/stopping consistent; invalid direction before sampling. Raw history8/−4 остаётся raw, не universal negation.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-STR-01-03 → REQ-STR-01-02, REQ-STR-01-04

**Уровень:** native occurrence and strategy. **Ожидается:** positive + negative + boundary.

**Setup:** Ten repeated violations, top-k1/10, real CompositeObjective and StrategyAdapter; empty control.

**Действие:** Actual search/report; inspect counts/selected examples.

**Oracle:** Observed/high10, unique1, examples capped; no count change with top-k. Empty no robust score; native objective cost direction correct.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-STR-01-04 → REQ-STR-01-03, REQ-STR-01-04

**Уровень:** E02-I10-C fresh selected intent. **Ожидается:** positive + negative + boundary.

**Setup:** Existing request/run-state selected objective captured before outcomes, actual artifact store and fresh Level5 consumer.

**Действие:** Bind intent→candidate/plan→complete ordered occurrence rows; mutate direction/threshold/source/profile; absent-intent control.

**Oracle:** Matched independently selected intent permits only declared finite-set score when all existing guards hold; mismatch/unavailable/zero denominator refuses. Without adequate owner G01 remains gap, raw diagnostics available.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I10-C** из [канонического lane integration-контракта](../03_Интеграция/LANE-10.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: нет. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

DOE-01 generator finite plan; objective/run-state owner binding не дублирует search engine. Native profile CP3.

## 8. Совместимость и восстановление

Metadata valid count intentionally corrected; unavailable remains separate status. Existing historical reports readable, current protected score requires fresh binding; rollback не включает self-issued authority.

## 9. Free-grow и design decisions

- [North Star §5](../05_Основания/Архитектура/policy-design-causal-operating-system-north-star.md#5-data-acquisition-and-the-real-product) и [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md#d25-epistemic-regime-architecture): ограниченный поиск даёт полезный результат и следующий запрос данных, не ложную полноту. [Синтез §4](../05_Основания/Исследование/design_direction.md): развивать существующий общий механизм.

## 10. Решения, которые нельзя подменить догадкой

- DEC-STR-01-01: finite selected-intent producer census; выбрать existing reference and validation predicate. Выход minimal positive source→fresh score path либо exact missing contract; не заявлять создание authority через один replay.

## 11. Что предъявить и что не является готовностью

Narrow count repaired плюс native direction/positive selected-intent path отдельно. Отсутствие intent не повод удалить useful stress diagnostics.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0168` → REQ-STR-01-01; total-invalid считает unavailable valid.
- `remaining:0169` → REQ-STR-01-03; Нужна actual selected request/run-state связь, не снятие отказа.
- `remaining:0170` → REQ-STR-01-02, REQ-STR-01-04; Native strategy/CAS/Level5 отдельно от fixture.
- `preserve:0280` → REQ-STR-01-02; Typed pre-work direction intake — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0281` → REQ-STR-01-02; Single badness convention — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0282` → REQ-STR-01-02; Raw adaptive history — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0283` → REQ-STR-01-01, REQ-STR-01-02; Occurrence counts before dedupe/top-k — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0284` → REQ-STR-01-03, REQ-STR-01-04; Unbound score refusal — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0285` → REQ-STR-01-03, REQ-STR-01-04; Exact source/selected-profile guards — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
