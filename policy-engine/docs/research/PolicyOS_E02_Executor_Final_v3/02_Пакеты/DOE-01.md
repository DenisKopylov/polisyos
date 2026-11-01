# DOE-01 — Квалификация bounded/adaptive DoE и передачи последнего дизайна

**LANE-10 · B97, B98, B99 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Возвращать реально завершённое исследование с его дизайном и наблюдаемой стоимостью без скрытых раундов.

**Тип:** C116-G01 qualify; C116-G02 lifecycle/consumer binding; локальные B97–99 repaired.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/DOE-01.md), [исходные карточки](../05_Основания/Аудит/05_Источники/DOE-01_исходные_строки.txt), [трассировка](../04_Трассировка/DOE-01.json).

## 2. Уже работает — сохранить

- Lazy exact GRID prefix и own bounded array.
- Last completed result, explicit allow_large_run и phase-specific attempts.
- Неизвестное количество строк после evaluator exception остаётся unknown, не0.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| B97 | qualify | REQ-DOE-01-01 | Lazy repair сохранить. |
| B98 | lifecycle | REQ-DOE-01-02, REQ-DOE-01-03 | Hidden rerun убран; result без exact sample ref требует consumer binding. |
| B99 | qualify | REQ-DOE-01-02, REQ-DOE-01-04 | Permission repaired; per-design не суммарный cap. |
| C116-G01 | qualify | REQ-DOE-01-01, REQ-DOE-01-02 | Нужны actual SALib/consumer, synthetic analyzer не научная квалификация. |
| C116-G02 | lifecycle | REQ-DOE-01-03, REQ-DOE-01-04 | Finite owner/caller census и exact design handoff, не новый registry. |

## 4. Нормативные требования результата

**REQ-DOE-01-01.** GRID_EXTREME должен материализовать только разрешённый prefix и не удерживать полный product; ограниченность покрытия явно сохраняется.

**REQ-DOE-01-02.** AdaptiveSampler должен возвращать последний completed round без hidden rerun; permission не повышается, ошибки последующей стадии не уничтожают прежний результат.

**REQ-DOE-01-03.** Передача final result должна связывать его с фактическим design/axes/seed/stream и completed round; при отсутствии production caller нужен bounded owner decision, не фиктивный source ref.

**REQ-DOE-01-04.** Отчёт стоимости должен различать per-design cap, известные completed rows, неизвестную partial evaluation и sampling/analysis cost; это не новый global budget grant.

## 5. Конкретное техническое решение — рекомендуемый способ

- Не менять исправленный islice/materialization и permission guard без regression. Существующие test_doe_01 расширить real SALib route.
- Установить actual consumers AdaptiveResult: если existing trajectory artifact owner достаточен, добавить optional exact final-design ref/context к result/round, writer сохраняет source matrix и axes/seed/backend, reader сверяет. Если production caller не найден — документировать API handoff и интегрировать minimal existing scientific consumer, не invent orchestration service.
- Использовать attempts и total_evaluations для наблюдаемой стоимости; global budget только через существующего owner, если найден. Независимая confirming replica — отдельный explicit round/seed, не служебный rerun.

**Существующие code/test owners:**
- [`src/polisyos/scientist/methods/doe/adaptive.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/adaptive.py).
- [`src/polisyos/scientist/methods/doe/sampling.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/sampling.py).
- [`src/polisyos/scientist/methods/doe/designs.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/designs.py).
- [`tests/unit/remediation/test_doe_01.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_doe_01.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-DOE-01-01 → REQ-DOE-01-01

**Уровень:** generator property. **Ожидается:** positive + negative + boundary.

**Setup:** 12 bounded parameters, cap3.

**Действие:** Count product iteration и inspect ndarray.base; compare exact old prefix generated only in tiny control.

**Oracle:** Ровно3 rows, shape3×12, float64 nbytes288, base=None; 10 constant axes отмечают limited coverage, не4096 corners.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DOE-01-02 → REQ-DOE-01-02, REQ-DOE-01-04

**Уровень:** adaptive real orchestration. **Ожидается:** positive + negative + boundary.

**Setup:** 2 params Morris; one/two rounds trajectories2/4; cap6 False/True; generation/evaluation/analysis faults.

**Действие:** Actual AdaptiveSampler with bounded real SALib; phase faults injected only at declared boundary.

**Oracle:** Calls [6] или[6,12], не hidden third; False stops before12, True permits. Failed second analysis preserves first result6 и observed rows18; evaluator partial unknown не0.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DOE-01-03 → REQ-DOE-01-03, REQ-DOE-01-04

**Уровень:** E02-I10-C actual handoff. **Ожидается:** positive + negative + boundary.

**Setup:** Finite census AdaptiveSampler callers and existing trajectory storage; selected actual small design.

**Действие:** Bind last completed design through existing artifact/ref owner, fresh consumer reload; mutate seed/axes/round identity.

**Oracle:** Consumer воспроизводит именно final completed design; mismatch не выдаёт valid indices. Если caller отсутствует, явный adapter contract+bounded implementation path, no fabricated lifecycle PASS.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I10-C** из [канонического lane integration-контракта](../03_Интеграция/LANE-10.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: нет. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

DOE-02 владеет mapping/seed/design identity, DOE-03 retained trajectory consumer. CP3, не блокировать CAL CP4 whole lane.

## 8. Совместимость и восстановление

Existing return semantics и explicit override сохраняются; additive ref/context по actual owner. Legacy bare result читается с not-established source scope, не переаттестуется.

## 9. Free-grow и design decisions

- [North Star §5](../05_Основания/Архитектура/policy-design-causal-operating-system-north-star.md#5-data-acquisition-and-the-real-product) и [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md#d25-epistemic-regime-architecture): ограниченный поиск даёт полезный результат и следующий запрос данных, не ложную полноту. [Синтез §4](../05_Основания/Исследование/design_direction.md): развивать существующий общий механизм.

## 10. Решения, которые нельзя подменить догадкой

- DEC-DOE-01-01: finite caller/storage census, выбрать existing artifact handoff либо точный missing adapter. Выход — producer/consumer diagram и minimal acceptance fixture. Не считать отсутствие найденного caller универсальным system failure.

## 11. Что предъявить и что не является готовностью

Native repaired mechanics плюс exact design handoff. Ranking stability не scientific convergence, три угла не robust-policy coverage.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0161` → REQ-DOE-01-01, REQ-DOE-01-02; Нужны actual SALib/consumer, synthetic analyzer не научная квалификация.
- `remaining:0162` → REQ-DOE-01-03, REQ-DOE-01-04; Finite owner/caller census и exact design handoff, не новый registry.
- `preserve:0261` → REQ-DOE-01-01; Lazy exact GRID prefix — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0262` → REQ-DOE-01-01; Own bounded array — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0263` → REQ-DOE-01-02, REQ-DOE-01-03; Last completed result — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0264` → REQ-DOE-01-02; Explicit permission preservation — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0265` → REQ-DOE-01-04; Phase-specific observed work — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0266` → REQ-DOE-01-04; Unknown evaluator work remains unknown — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
