# EMP-01 — область данных, интервалы и причинный граф
## C28 · 31 октября 2026 года

**Исходные IDs:** B16, B31, B33. **Порядок:** 28/127, начало LANE-03. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Аудит без изменения продукта.

## Решение

Историческое описание не переносится на текущую реализацию целиком. **Географический фильтр применяется перед LIMIT, переполнение лимита отказно отличается от отсутствия данных, неоднозначные unit-period и источники не усредняются.** Статистический интервал хранится отдельно от множества идентификации; отчёт без основания запуска больше не превращается в ValueOuterSet. Selection diagram использует выбранный причинный граф, а не выдумывает T→Y из имён переменных. Существуют producer→CAS→fresh consumer пути для ограниченного запуска метода и транспорта.

Сохраняются **два подтверждённых численных дефекта контракта ширины**: зависимость допустимости proxy от масштаба единиц и переполнение производной ширины при конечных границах. Отдельно остаются квалификационные пробелы: country scope не равен полной предметной области измерения; корректное сохранение расчёта не делает его эмпирически обоснованным. Нативное исполнение не подтверждено.

**25 MATCH, 0 ERROR**, exit 0: реальные определения ValueOuterSet, owner projection, loader и builder с явно указанными внешними фикстурами. Это не 25 штатных тестов и не product PASS.

## 1. Матрица исходных требований

| ID | Что сохранено и исправлено | Что остаётся |
|---|---|---|
| B16 | Country predicate и параметры до LIMIT; чтение 20001 строки для обнаружения превышения 20000; единицы обязательны; дубль unit-period и несколько источников отклоняются; source hashes сохранены | C28-G01: population/time/regime и полная семантика измерения не установлены одним country_code; C28-G03: реальный SQL/owner chain не запускался |
| B31 | Разделены identification и statistical endpoints; асимметричный CI не сужается; bare report запрещён; новый run basis связывает estimand, unit, точные входные байты и native report | C28-R01/R02: численная политика ширины; C28-G02: основания идентификации и калибровки не заменяются candidate run; C28-G03 |
| B33 | Выбранный профиль графа, schema, nodes, problem/WMR binding; реальная топология, measured S-nodes с role=None; persisted run basis и fresh recomputation в коде | C28-G02: выбранный граф — ещё не научно подтверждённая модель; C28-G03: native цепочка и solver не исполнялись |

[Исходная карточка](../05_Источники/EMP-01_исходные_строки.txt), строки 3413–3529. Предшественник CYC-01 сохранён без переаттестации. B32/LA-051 относятся к следующему FRC-01: их полнота здесь не присваивается.

## 2. B16: от владельца данных до входа метода

`RealValueOwnerGateway` проверяет активного владельца catalog, получает availability, разрешает jurisdiction region через country-code boundary и передаёт регион loader. Arbitrary basin/state label не принимается за страну. Loader добавляет регион в SQL WHERE до ORDER/LIMIT и читает cap+1; при превышении выдаёт `value_owner_rows_truncated`, а не готовый неполный профиль. [S02:5999–6076](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L5999-L6076) [S02:16154–16410](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L16154-L16410)

**P17** исполняет настоящий loader с reader-фикстурой: получены параметры `['outcome','UA','UA',[],None,None,20001]`, country predicate расположен до LIMIT; P18 проверяет отказ на слишком большом возвращённом наборе, P19 — отдельный результат пустой выборки. **SQL-движок не запускался.** Существующие тесты используют реальный DuckDB и более 20000 чужих строк, но в этой среде они только прочитаны. [S03:424–740](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_emp_01.py#L424-L740)

Общий `_value_owner_rows_from_source_rows` требует конечные численные значения, единственную строку unit-period, одну объявленную единицу и единый непустой dataset identity. Он не усредняет неоднозначность. Внутренний `_value_owner_row` ещё содержит mean, но проверенный caller передаёт туда singleton: наличие `fsum/len` само по себе **не воспроизводит старый дефект**. P10–P15 подтверждают нормальные строки, отказ дубля, смешанных источников/единиц, malformed JSON, пустой и короткой выборки. [S02:16538–16697](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L16538-L16697)

Активированная acquisition projection имеет дополнительную сильную проверку: точный набор observation IDs, совпадение физических полей, включая condition_json, и ограниченную подтверждённую WDI ISO3→ISO2/identity-unit ветвь. Она прочитана, не исполнена. Нельзя переносить ограничение обычной проекции на этот путь без его собственных условий. [S02:16210–16537](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L16210-L16537)

### C28-G01 — поддерживаемая область пока уже полной области измерения

Gateway передаёт outcome и country, но не отдельные population/time/regime predicates. Обычная row projection извлекает из condition_json только unit; в source-row hash входят outcome/unit/period/value/dataset/observation/unit, а не весь condition. **P16:** замена дополнительного поля `population` в искусственных condition objects оставляет одинаковые projected rows. Это демонстрация потери дополнительной семантики, **не доказательство наличия именно такого ключа и реальной коллизии в текущем catalog**.

Нужно определить поддерживаемую предметную область через существующие источники/measurement contracts либо адресно отказать неподдерживаемому срезу. Не следует молча изобретать subgroup mapping. Полноценный ObservationRecord уже содержит entity scope, period, source version и regime: новый параллельный контракт вместо связи с действующим не требуется. [S07:131–209](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/observation/contracts.py#L131-L209)

## 3. B31: не смешивать множество идентификации и статистическую неопределённость

`ValueOuterSet.lower/upper` описывают identification set; `statistical_lower/upper` — отдельные исходные статистические границы. P01 сохраняет point `[2,2]` и асимметричный CI `[0,10]` через JSON/readback, не объявляя point полной достоверностью. P04/P05 отклоняют перевёрнутую или неполную пару. Search-only результат не становится promotable. [S01:151–179](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/contracts/value_outer_set.py#L151-L179) [S01:341–398](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/contracts/value_outer_set.py#L341-L398)

Старый helper `_value_outer_set_from_foundry_result` теперь всегда отказывает отчёту без producer-owned run basis; P02/P03 различают отсутствие отчёта и отсутствие основания. Это правильная защита, а не регрессия, которую надо обойти для зелёного результата. [S02:18679–18707](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L18679-L18707)

Есть содержательная замена: `_produce_value_owner_method_run_basis` разрешает выбранный profile/assignment, связывает estimand с outcome/unit, сохраняет точный panel input, запускает registry-selected `NumpyRunner`, сохраняет report и execution receipt. Resolver повторно разрешает inputs/lineage, проверяет байты и report parameters; source route повторяет чтение owner profiles, bounds и реальный method run. Координата — hash полного dataclass estimand, а не имя метода. P20 проверяет именно field projection с тестовым dataclass/hash, не реальный EstimandSpec/CAS. [S02:21051–21063](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L21051-L21063) [S02:21788–22149](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L21788-L22149) [S02:22151–22574](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L22151-L22574)

### C28-R01 — абсолютная ширина зависит от единиц

`round(hi-lo,12)` и `_PROXY_WIDTH_TOLERANCE=1e-9` работают в числах без учёта координаты. **P06:** ширина `1e-6` принимается как proxy; та же физическая ширина после масштабирования единицы в 10000 раз (`1e-10`) отвергается как нулевая. **P07:** partial bounds `[0,1e-13]` различны, но reported width равна 0. [S01:78–82](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/contracts/value_outer_set.py#L78-L82) [S01:190–191](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/contracts/value_outer_set.py#L190-L191) [S01:375–391](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/contracts/value_outer_set.py#L375-L391)

Нужна явная численная политика, согласованная с координатой/единицей, а не новая произвольная минимальная ширина. Сохранить запрет реально вырожденного proxy и не расширять интервал выдуманным процентом. Важность — корректность общего контракта; текущий candidate source route использует partial/search_only, поэтому bypass production gate не заявляется.

### C28-R02 — конечные endpoints не гарантируют конечную width

**P08:** `[-1e308,1e308]` проходит endpoint validation, но вычитание даёт Infinity. `model_dump_json` пишет width `[null]`, canonical `from_persisted_payload` затем отказывает `width_tampered`. **P09** отдельно сохраняет полезный контроль настоящей подмены checksum. [S01:78–82](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/contracts/value_outer_set.py#L78-L82) [S01:241–289](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/contracts/value_outer_set.py#L241-L289)

Это крайний численный случай, не найденный реальный эмпирический набор. Следует отклонить непредставимую производную ширину до записи либо выбрать подходящее представление. Нельзя просто ослабить readback integrity.

## 4. B33: сохранённый граф вместо шаблона причинности

`_build_candidate_selection_diagram` повторно проверяет cycle context, problem/WMR identity, выбранный manifest profile, schema и реальные query/covariate nodes. Загруженный graph передаётся в `SelectionDiagramBuilder` без перестройки T→Y; измеренные различия добавляются как S-nodes с `role=None`, а не произвольной причинной ролью. Raw graph/hypothesis hint без artifact bridge остаётся candidate-only. [S02:16970–17122](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L16970-L17122)

**P21–P25:** нет графа/контекста/профиля/нужного узла — адресный отказ; две разные выбранные топологии сохраняются разными. Builder и boundary настоящие, **CAS/profile/context loader и graph DTO в диагностике — фикстуры**, поэтому это не проверка допуска поддельного графа настоящим владельцем.

Реальные persist/load функции существуют: writer умеет возвращать выбранный profile; loader использует owner/profile/version/DTO admission. Gateway вызывает `_run_value_transport`, сохраняющий request, graph, diagram и solver result; fresh resolver повторяет current graph binding и solver, сравнивает точные результаты. Existing `test_selected_profile_graph_reaches_fresh_candidate_transport_receipt` проходит такую структуру в исходном тесте; соседний тест удаляет graph, меняет профиль и context. Оба **UNRUN**, не PASS. [S06:1014–1050](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L1014-L1050) [S02:18251–18677](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L18251-L18677) [S03:214–338](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_emp_01.py#L214-L338)

## 5. Реальная способность и границы научного вывода

**C28-G02:** source assignment и поддержка исхода остаются consumer-asserted; source time и отношение bounds к estimand явно не установлены. Candidate basis имеет `production_value_eligible=False`; итог — `search_only`, а N8 сохраняет его и возвращает ограниченный `candidate_fixture_value_run_not_authority`, либо точный `treatment_assignment_not_owner_derived`. Не нужно удалять эту защиту: она не даёт исследовательскому вычислению притвориться эмпирическим разрешением. [S02:6750–6885](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L6750-L6885) [S02:22500–22574](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L22500-L22574)

Путь полезен уже сейчас: можно связать предложенные LLM модель/estimand и выбранные данные с воспроизводимым ограниченным вычислением. Для эмпирического результата остаются реальные основания treatment assignment, область данных, модельные предпосылки, отношение bounds/estimand и калибровка. Недостаток универсального детерминированного «изобретателя моделей» сам по себе не дефект; LLM-предложение также не является доказательством.

**C28-G03:** pytest, DuckDB, native CAS/Foundry/transport и полный штатный цикл не исполнялись; зависимости отсутствуют и не устанавливались. Утверждается чтение кода и 25 ограниченных наблюдений, не научная валидность. Два ранних harness failures и ошибка ожидания Pydantic serialization сохранены; исправлялся только внешний probe, после чего весь набор выполнен заново.

[Диагностика](../04_Проверки/C28_EMP01/bounded_diagnostics.json) · [команды и exit codes](../04_Проверки/C28_EMP01/commands.json) · [границы](../04_Проверки/C28_EMP01/Чтение_и_границы.md) · [источники](../05_Источники/C28_источники.json) · [остатки](../01_Реестры/C28_остатки.json).

**28/127 пакетов рассмотрены ограниченно; 76 уникальных B/LA частично оценены; полного закрытия нет.** Следующий пакет — **FRC-01 / B32, LA-051**, по исходной очереди.
