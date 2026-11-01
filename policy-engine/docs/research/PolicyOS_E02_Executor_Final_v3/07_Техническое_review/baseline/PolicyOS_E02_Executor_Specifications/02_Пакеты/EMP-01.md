# EMP-01 — Точная численная ширина и измерительный scope без подмены эмпирического основания

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-03 · CP1 · B16, B31, B33.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Сохранить полезный owner-bound расчёт/transport; исправить две ошибки ширины ValueOuterSet и определить/подключить действительную область измерения до выборки. Не выдавать country filter, сохранённый report или выбранный граф за научно установленный эмпирический эффект.

**Тип работы:** Два bounded numeric repair; адресное расширение/уточнение scope bridge C28-G01; native и научная квалификация C28-G02/G03. Частичное candidate исследование не блокируется до полного empirical admission.

[Аудит](../05_Основания/Аудит/02_Пакеты/EMP-01.md) · [остатки](../05_Основания/Аудит/01_Реестры/C28_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/EMP-01_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C28_источники.json) · [трассировка](../04_Трассировка/EMP-01.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

**B16:** country-before-LIMIT, cap+1 и отказ неоднозначного unit/source уже работают; сохранить REQ-04, дополнить смысловой scope REQ-05. **B31:** identification/statistical endpoints и owner-run basis уже разделены; сохранять REQ-03/07, ремонт ширины REQ-01/02 и совместимость REQ-08. **B33:** граф уже загружается по selected profile, а не строится из названий; сохранять/квалифицировать REQ-06/07. B32 и LA-051 — FRC-01/FRC-02, не этот пакет. В карточке нет отдельного LK/S; реальные causal owners и полезные conditional результаты сохраняются.

- `preserve:0049`: Country filter before LIMIT. → REQ-EMP-01-04; TEST-EMP-01-04.
- `preserve:0050`: Cap+1 truncation refusal. → REQ-EMP-01-04; TEST-EMP-01-04.
- `preserve:0051`: Unit/source binding and source row hashes. → REQ-EMP-01-04, REQ-EMP-01-05; TEST-EMP-01-04, TEST-EMP-01-05.
- `preserve:0052`: Activated row projection has separate full physical content checks. → REQ-EMP-01-04, REQ-EMP-01-05; TEST-EMP-01-04, TEST-EMP-01-05.
- `preserve:0098`: Separate asymmetric statistical interval. → REQ-EMP-01-03; TEST-EMP-01-03.
- `preserve:0099`: No report-only value projection. → REQ-EMP-01-07; TEST-EMP-01-03.
- `preserve:0100`: Exact method input/run/report/estimand chain in source. → REQ-EMP-01-03, REQ-EMP-01-07; TEST-EMP-01-03, TEST-EMP-01-07.
- `preserve:0105`: No topology invented from names. → REQ-EMP-01-06; TEST-EMP-01-06.
- `preserve:0106`: Selected-profile graph and problem/world bindings. → REQ-EMP-01-06; TEST-EMP-01-06.
- `preserve:0107`: Persisted run basis and fresh solver recomputation. → REQ-EMP-01-06, REQ-EMP-01-07; TEST-EMP-01-06, TEST-EMP-01-07.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C28-R01` | fix: Убрать зависимость численного admission от абсолютной единицы с явной совместимостью. | REQ-EMP-01-01, REQ-EMP-01-08 |
| `C28-R02` | fix: Не допускать nonfinite derived width до сохранения; checksum не ослаблять. | REQ-EMP-01-02, REQ-EMP-01-08 |
| `C28-G01` | capability: Это не только запуск теста: определить/связать поддержанную измерительную область через существующие owners; unsupported срез ограничить адресно. | REQ-EMP-01-04, REQ-EMP-01-05 |
| `C28-G02` | qualify: Работающий candidate путь сохраняется; scientific/model/assignment основания устанавливаются отдельно. | REQ-EMP-01-03, REQ-EMP-01-06, REQ-EMP-01-07 |
| `C28-G03` | qualify: Реальные SQL, registry, CAS, solver и fresh consumers вместо прежних внешних fixtures. | REQ-EMP-01-03, REQ-EMP-01-04, REQ-EMP-01-05, REQ-EMP-01-06, REQ-EMP-01-07, REQ-EMP-01-08 |

Все source-registry remaining также связаны: `remaining:0041`, `remaining:0042`, `remaining:0075`, `remaining:0076`, `remaining:0077`, `remaining:0078`, `remaining:0083`, `remaining:0084`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-EMP-01-01
Новая численная политика interval_box должна сохранять положительную представимую ширину hi−lo без округления до фиксированного числа десятичных разрядов. При допустимой смене единиц масштаба a>0, не теряющей различимость endpoints и сохраняющей конечную представимую width, proxy/nonzero admissibility не меняется; вырожденный proxy с равными endpoints отклоняется. Point identification и statistical uncertainty не смешиваются.
Источник: B31; C28-R01. Проверки: TEST-EMP-01-01.

### REQ-EMP-01-02
Если конечные endpoints дают непредставимую nonfinite производную width, live construction нового ValueOuterSet должен адресно отказать до сериализации. Ни Infinity, ни null вместо width не могут стать успешным сохраняемым контрактом; normal finite range продолжает проходить roundtrip.
Источник: B31; C28-R02. Проверки: TEST-EMP-01-02.

### REQ-EMP-01-03
Point identification [2,2] с отдельно сообщённым asymmetric statistical CI [0,10] должно сохранять обе пары точно по их роли через JSON/CAS/readback. Bounds не расширяются произвольными 10%/0.01 и не симметризуются со сужением. Координата зависит от estimand/unit, а не только имени estimator.
Источник: B31; C28-G02, C28-G03. Проверки: TEST-EMP-01-03.

### REQ-EMP-01-04
В действительном catalog SQL объявленный scope применяется до ORDER/LIMIT; cap+1 обнаруживает усечение и отличает его от пустой/слишком малой выборки. Неоднозначные unit-period, источники или единицы нельзя молча усреднять. Source identities и отдельная полная проверка activated observation projection сохраняются.
Источник: B16; C28-G01, C28-G03. Проверки: TEST-EMP-01-04, TEST-EMP-01-05.

### REQ-EMP-01-05
Каждое поддержанное поле области измерения, существенно различающее population/entity/time/regime/source version, должно быть связано с фактическим owner contract, выбором rows до cap и content identity потреблённого профиля. Если источники/контракт не выражают запрошенный срез, gateway возвращает адресное unsupported scope/нужное основание, а не молча country-wide данные. Country-only candidate профиль может оставаться доступным с явно более узким смыслом, не притворяясь запрошенным subgroup estimate.
Источник: B16; C28-G01. Проверки: TEST-EMP-01-05.

### REQ-EMP-01-06
Selection diagram сохраняет топологию выбранного causal artifact, его profile/schema/problem/WMR binding и measured S-nodes без выдуманной причинной роли. Две модели с одинаковыми именами узлов и разными рёбрами не сводятся к одному шаблону. Missing/wrong-profile/foreign-context граф не получает transport receipt; LLM hypothesis остаётся явно candidate до bridge.
Источник: B33; C28-G02, C28-G03. Проверки: TEST-EMP-01-06.

### REQ-EMP-01-07
Положительный method/transport результат проходит actual owner→registry-selected runner/solver→persisted input/run/report→fresh resolver/consumer с проверкой исходного смысла и bytes. Bare report не заменяет run basis. Consumer-asserted assignment/support, неизвестная связь bounds/estimand и неустановленная калибровка сохраняют candidate/search_only/non-production роль; отдельно установленное основание может расширить только затронутое использование.
Источник: B31, B33; C28-G02, C28-G03. Проверки: TEST-EMP-01-03, TEST-EMP-01-06, TEST-EMP-01-07.

### REQ-EMP-01-08
Изменение numerical width semantics должно иметь однозначно различимую версию/профиль записи и reader. Старый checksum проверяется по старому объявленному контракту, новый — по новому; historical bytes не переписываются, а reader не угадывает версию по тому, какой checksum случайно сошёлся. Tampered width отвергается в обоих профилях.
Источник: B31; C28-R01, C28-R02, C28-G03. Проверки: TEST-EMP-01-01, TEST-EMP-01-02, TEST-EMP-01-08.

## 5. Конкретное техническое решение

**Численный owner.** Изменять `_derive_interval_widths` и admission в `ValueOuterSet`, а не отдельные consumers. Предлагаемый новый контракт использует фактический представимый `hi-lo`, проверенный `math.isfinite`, без `round(...,12)`. Для нового exact-endpoint профиля point означает равенство endpoints, proxy — хотя бы одну строго положительную width. Это unit-covariant при смене масштаба, сохраняющей различимость endpoints и конечную представимость производной width; это не обещание восстановить информацию, уже потерянную float conversion. Если нужна измерительная tolerance, она должна быть declared coordinate/unit-bound параметром, а не общей константой1e-9. Не добавлять вымышленную минимальную ширину.

**Совместимость — часть ремонта.** Current `from_persisted_payload` сравнивает derived checksum точно, поэтому простая смена функции сломает историческое чтение. До изменения определить существующий artifact/profile owner для persisted ValueOuterSet (DEC-NUMERIC). Предпочесть его versioned numerical profile; если он не выражает различие, минимальное явное version field в текущем контракте допустимо после обзора consumers. Старый reader должен проверять old checksum старым алгоритмом. Новый writer выдаёт только новую версию; legacy acceptance не служит promotion нового результата. Не принимать любой из двух checksum без версии. Проверить также canonical payload/hash и static JAX tree roundtrip: их presentation rounding не должно незаметно схлопывать deciding численное различие нового профиля. Это квалификация затронутого представления, а не заявление о найденной production hash-коллизии.

**Измерительный scope.** У `RealValueOwnerGateway._load_value_data_profile_from_source` сейчас outcome и country идут в loader, но не полный measurement scope. Не читать произвольный `condition_json.population` как универсальный стандарт. В DEC-SCOPE составить точную таблицу `DesignProblem/selected source profile → существующее поле ObservationRecord/catalog → SQL predicate → retained provenance/hash`. Для поддержанного mapping передавать его через существующий loader, фильтровать до LIMIT и включать значимые scope/source-version данные в selected profile identity. Неуспешное разрешение означает адресный unsupported scope; оно не должно silently расширять популяцию. Activated projection уже проверяет полный физический content, эту сильную ветку не заменять упрощённым общим hash.

**Граф/метод.** Сохранить `_build_candidate_selection_diagram`, producer-owned method-run basis и fresh resolver. Исполнитель расширяет только подтверждённо отсутствующую связь, не заново строит T→Y. LLM может предложить граф и estimand; существующий выбранный artifact bridge и реальный runner/solver должны потребить именно их. Численный результат остаётся полезным условным расчётом, пока отсутствует отдельное основание empirical promotion.

### Текущие owners и источники

- [policy-engine/src/polisyos/core/contracts/value_outer_set.py:58–82](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/contracts/value_outer_set.py#L58-L82)
- [policy-engine/src/polisyos/core/contracts/value_outer_set.py:151–398](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/contracts/value_outer_set.py#L151-L398)
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:5999–6076](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L5999-L6076)
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:16154–16410](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L16154-L16410)
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:16538–16697](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L16538-L16697)
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:16970–17122](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L16970-L17122)
- [policy-engine/src/polisyos/ir/observation/contracts.py:131–209](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/observation/contracts.py#L131-L209)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-EMP-01-01 · native contract/numerical metamorphic
**NOT_RUN. REQ:** REQ-EMP-01-01, REQ-EMP-01-08.
**Setup:** Новые interval_box fixtures с proxy bounds [0,1e-6], после unit scaling [0,1e-10], partial [0,1e-13], exact equal endpoints; добавить representable соседние floats и отрицательные bounds.
**Действие:** Создать DTO, получить derived width, выполнить model_dump_json/from_persisted_payload и координатно согласованное масштабирование.
**Oracle:** Обе proxy ширины положительны и допустимы; partial width не 0; equal proxy отвергнут. Для этих fixtures width равна фактическому float hi−lo, без decimal rounding. Масштабирование оценивается с заранее заданной float tolerance и одинаковым физическим интервалом, не с битовой идентичностью разных units. Old round(...,12)/absolute1e-9 должен провалить контроль.
**Место:** `src/polisyos/core/contracts/value_outer_set.py; tests/unit/remediation/test_emp_01.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-EMP-01-02 · native overflow/roundtrip
**NOT_RUN. REQ:** REQ-EMP-01-02, REQ-EMP-01-08.
**Setup:** Finite endpoints [-1e308,1e308] и обычный finite контроль [-1e100,1e100]; дополнительно умножить endpoints контроля на 1e208: endpoints остаются конечными ±1e308, но width переполняется.
**Действие:** Вызвать live construction и JSON serializer только для принятых моделей.
**Oracle:** Непредставимая width, включая результат масштабирования с конечными endpoints, получает точный ValueError до записи: здесь инвариантность REQ-01 не применяется, отказ не означает вырожденность или рост определённости. Valid wide interval сохраняется и читается; никакого null/Infinity. Ослабление from_persisted_payload checksum не считается ремонтом.
**Место:** `src/polisyos/core/contracts/value_outer_set.py; ближайший существующий contract suite`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-EMP-01-03 · native report/value consumer
**NOT_RUN. REQ:** REQ-EMP-01-03, REQ-EMP-01-07.
**Setup:** Существующий owner-run fixture с point2/CI[0,10] и полный actual run basis; отрицательный bare report, foreign run basis и метод другого имени при том же estimand.
**Действие:** Запустить native producer/конверсию, сохранить ValueOuterSet, прочитать свежим reader и передать затронутому N8 consumer.
**Oracle:** Identification [2,2] отдельно от statistical[0,10], asymmetric CI не сужен; exact estimand/unit identity сохраняется, одно имя метода не создаёт новую предметную координату. Bare report/foreign binding отказываются; valid candidate сохраняется как search_only без выдуманной authority.
**Место:** `tests/unit/remediation/test_emp_01.py; generation_cycle.py::_produce_value_owner_method_run_basis/_value_outer_set_from_owner_method_run_basis`.
**Doubles:** Допустим synthetic panel. Actual registry/runner, selected profile, CAS и resolver не подменяются. Новый testcase расширяет имеющийся owner-basis путь.

### TEST-EMP-01-04 · native DuckDB/catalog
**NOT_RUN. REQ:** REQ-EMP-01-04.
**Setup:** Существующий test_scope_filter_excludes_other_regions_before_profile_limit: более20000 чужих rows и подходящий малый country профиль; отдельно20001 подходящая строка, пустой набор, duplicate unit-period и mixed units/sources.
**Действие:** Через real catalog reader/RealValueOwnerGateway загрузить профиль с выбранной страной.
**Oracle:** Чужие rows не вытесняют подходящие до LIMIT; cap+1 даёт value_owner_rows_truncated, empty не то же самое; ambiguous rows не усредняются. Activated projection physical-content negatives также остаются действительными.
**Место:** `tests/unit/remediation/test_emp_01.py`.
**Doubles:** Тестовый DuckDB catalog и данные разрешены; reader с заранее ожидаемым массивом не доказывает SQL ordering/scope.

### TEST-EMP-01-05 · native measurement-scope bridge
**NOT_RUN. REQ:** REQ-EMP-01-04, REQ-EMP-01-05.
**Setup:** После DEC-EMP-01-SCOPE взять один реально поддержанный source mapping с различающей entity/population/time/regime координатой. Два набора могут иметь одинаковую численную summary, но разные scope/row IDs. Отдельно unsupported subgroup.
**Действие:** Запросить каждый scope через gateway, сохранить actual selected rows/source profile, читать свежим consumer; изменить только значимое scope поле/condition.
**Oracle:** Поддержанные запросы выбирают разные правильные row sets до cap и имеют разную содержательную identity; unsupported scope даёт точный ограниченный исход, не fallback на другую популяцию. Нельзя засчитать произвольный fixture-key population как доказательство существующего catalog mapping.
**Место:** `generation_cycle.py::RealValueOwnerGateway/_load_value_data_profile_from_catalog_reader; ir/observation/contracts.py::ObservationRecord`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-EMP-01-06 · native selected graph/transport E02-I03-A
**NOT_RUN. REQ:** REQ-EMP-01-06, REQ-EMP-01-07.
**Setup:** Переиспользовать _selected_profile_transport_case и два графа с теми же nodes, разными рёбрами; реальные selected artifact profiles и problem/WMR.
**Действие:** Вызвать gateway.run_transport, сохранить graph/diagram/solver result, разрешить fresh _resolve_value_transport_run_basis. Затем remove graph, substitute profile/context или query node.
**Oracle:** Valid diagram.base_graph равен выбранному графу, два различающихся графа не превращены в T→Y template; S-nodes сохраняют measured source/target и role=None. Fresh native solver согласован; substitutions адресно отвергнуты, candidate scope сохранён.
**Место:** `tests/unit/remediation/test_emp_01.py::test_selected_profile_graph_reaches_fresh_candidate_transport_receipt; test_fresh_transport_admission_refuses_removed_or_substituted_graph`.
**Doubles:** Synthetic graph/data допустимы; graph DTO admission, profile binding, actual CAS/solver/consumer не заменяются fixtures.

### TEST-EMP-01-07 · bounded empirical-use decision + native negative
**NOT_RUN. REQ:** REQ-EMP-01-07.
**Setup:** Candidate report с truthful consumer_asserted treatment/support и объявленной LLM hypothesis; отдельно реально доступный evidence case либо явное отсутствие такого case.
**Действие:** Проследить все load-bearing основания и visible N8 limitation; попытаться повысить role одним finite CI/числом observations/receipt.
**Oracle:** Candidate полезен и читается, но production_value_eligible=False/search_only не исчезают от marker. Для более сильного claim нужен адресный комплект assignment/source/model/bounds-estimand/calibration evidence; при его отсутствии scientific closure NOT_ESTABLISHED, а не universal-inventor blocker.
**Место:** `generation_cycle.py::RealValueOwnerGateway; существующие method-run/transport acceptance owners`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-EMP-01-08 · versioned compatibility/integrity
**NOT_RUN. REQ:** REQ-EMP-01-08.
**Setup:** Заморозить genuine old payloads до правки, включая округлённую малую width и ordinary point/proxy; новый численный профиль. Не создавать legacy bytes новым serializer.
**Действие:** Проверить old reader/explicit migration и new writer/new reader; изменить только checksum, metadata версии или endpoint.
**Oracle:** Старые bytes проверяются собственным историческим правилом и не объявляются current semantic acceptance автоматически; новые проходят new roundtrip. Tampering отказан; попытка трактовать новую запись как legacy не обходит version admission. Выбранное решение DEC-EMP-01-NUMERIC фиксировано в test, не угадывается.
**Место:** `ValueOuterSet.from_persisted_payload; существующий artifact/profile owner выбранный при DEC-EMP-01-NUMERIC`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_emp_01.py
# Добавленные numerical/versioned cases запускать по действительному владельцу теста после обнаружения пути.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I03-A**: [канонический контракт LANE-03](../03_Интеграция/LANE-03.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

Численный контракт — один writer `core/contracts/value_outer_set.py`; gateway/profile изменения — согласованный writer `generation_cycle.py` с обязательными CYC/ACQ/FRC companions. Не редактировать общий большой файл параллельно. Сначала проверить новый/старый numeric contract и scope mapping, затем узкие patches, затем E02-I03-A после стабилизации inputs. Временная/калибровочная семантика S10 здесь не меняется.

- **CYC-01:** Существующий selected problem/profile/context producer; наследованный предшественник, не повторный заказ его реализации.
- **FRC-01/FRC-02:** Время, calibration receipt и S10 находятся у этих owners. Scope/ValueOuterSet здесь не должны переписывать forecast gate.
- **ACQ-01 / LANE-07:** Activated projection и ObservationRecord semantics согласовать с настоящим producer; не новый параллельный measurement DTO.
- **GRF-01/GRF-02:** Переиспользовать canonical graph/solver contracts, не собственный graph engine.

## 8. Совместимость, миграция и возврат

Изменение допустимости point/proxy и checksum — намеренный versioned numerical delta, не equivalent move. Исторические ValueOuterSet/run artifacts сохраняются byte-for-byte; читатель должен различать историческую проверку целостности и текущую пригодность. Scope extension меняет содержательную identity только при изменении решающих входов; одинаковые summaries не разрешают reuse чужого scope. Rollback возвращает согласованную пару writer/reader и сохраняет новый профиль как явно unsupported там, где старый код его не умеет; нельзя падать назад к guessed legacy или отключать checksum. Неподдержанный empirical scope не блокирует независимый simulation-only K1.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0, lines559–617](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Генеральность достигается общим numerical/scope механизмом и честной границей, а не branch по имени страны. Проверки масштаба и второго реально различающего scope показывают переносимость без требования всезнания.
- [policy-design-execution-topology.md — lines143–159: applicability versus semantic judgment](../05_Основания/Архитектура/policy-design-execution-topology.md): Механические bindings/finite bounds не доказывают causal graph. LLM hypothesis может дать исследовательский candidate, но не самостоятельно empirical authority.

## 10. Конечные решения и сдача

### DEC-EMP-01-NUMERIC
**Вопрос:** Какой существующий persisted profile/version владеет изменением width semantics?
**Кто решает:** ValueOuterSet и реальный artifact/profile owner, reviewer совместимости.
**Конечное действие/выход:** Проследить все writers/from_persisted_payload consumers и заморозить конечные genuine old fixtures; выбрать existing versioned profile либо минимальное explicit version field. Сдать карту old/new read/write и distinguishing checksum controls до изменения serializer.
**До решения:** Не менять старые bytes и не угадывать version; локальная numerical правка не принимается без совместимого reader решения.

### DEC-EMP-01-SCOPE
**Вопрос:** Какие population/entity/time/regime координаты реально представлены выбранным источником?
**Кто решает:** Gateway и настоящий measurement/catalog producer.
**Конечное действие/выход:** На одном поддержанном источнике проверить полный mapping полей, одну содержательную смену scope и один неподдержанный срез. Выдать таблицу mapping и реализованный общий handoff либо точную объявленную границу плюс конкретный недостающий producer field. Не подменять отсутствие mapping произвольным fixture ключом.
**До решения:** Country-only candidate сохраняет объявленный ограниченный scope; иной запрошенный scope не заменяется им молча.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
