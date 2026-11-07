# PCL-01 — Representation-invariant report→receipt и конечная совместимость calibration alias

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-03 · CP3 · LA-052, LA-053.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Закрыть потерю ограничивающего continuous report после сериализации в mapping; сохранить уже правильный measured denominator, типизированный receipt и canonical numerical tests. Согласовать native public imports и конечное решение compatibility, не удаляя полезный alias автоматически.

**Тип работы:** Ремонт условного consumer gap C30-R01; native/измерительная квалификация C30-G01/G03; lifecycle C30-G02. Старые empty-positive, numerical migration и разделение источника уже исправлены — не переписывать заново.

[Аудит](../05_Основания/Аудит/02_Пакеты/PCL-01.md) · [остатки](../05_Основания/Аудит/01_Реестры/C30_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/PCL-01_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C30_источники.json) · [трассировка](../04_Трассировка/PCL-01.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

**LA-052:** current curve/continuous owner уже различает not_evaluated/incomplete/evaluated и receipt source assurance. Сохранить REQ-03/04; новый ремонт касается typed↔serialized consumer REQ-01/02 и реальной цепочки REQ-05. **LA-053:** numerical tests уже у canonical owner; старый Scientist test identity-only. Сохранить REQ-06 и завершить bounded lifecycle решение REQ-07. **LK01/LK30:** predictive diagnostics не заменяют Foundry parameter calibration и DDM drift. **LK32:** TruthfulnessReceipt выполняет reconciliation, а не повторную калибровку/институциональный admission.

- `preserve:0783`: Unknown metrics and explicit inventory. → REQ-PCL-01-03; TEST-PCL-01-03.
- `preserve:0784`: Length/refusal and measured positive/negative controls. → REQ-PCL-01-03, REQ-PCL-01-04; TEST-PCL-01-03, TEST-PCL-01-04.
- `preserve:0785`: Actual typed receipt/reconciliation and source assurance. → REQ-PCL-01-01, REQ-PCL-01-02, REQ-PCL-01-04, REQ-PCL-01-05; TEST-PCL-01-01, TEST-PCL-01-02, TEST-PCL-01-04, TEST-PCL-01-05.
- `preserve:0786`: Bootstrap/PIT/ENCE and binary independence. → REQ-PCL-01-02, REQ-PCL-01-04; TEST-PCL-01-02, TEST-PCL-01-04.
- `preserve:0787`: Canonical numerical tests. → REQ-PCL-01-03, REQ-PCL-01-04, REQ-PCL-01-06; TEST-PCL-01-03, TEST-PCL-01-04, TEST-PCL-01-06.
- `preserve:0788`: Identity-only old test. → REQ-PCL-01-06; TEST-PCL-01-06.
- `preserve:0789`: Three same public objects. → REQ-PCL-01-06; TEST-PCL-01-06.
- `preserve:0790`: Predictive/parameter/drift owner roles distinct. → REQ-PCL-01-04, REQ-PCL-01-05; TEST-PCL-01-04, TEST-PCL-01-05.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C30-R01` | fix: Закрыть representation-sensitive precedence на known serialized report boundary, не глобальной доверчивой dict эвристикой. | REQ-PCL-01-01, REQ-PCL-01-02 |
| `C30-G01` | qualify: Native numerical/report/receipt и public distribution graph вместо isolated shells. | REQ-PCL-01-03, REQ-PCL-01-04, REQ-PCL-01-05, REQ-PCL-01-06 |
| `C30-G02` | lifecycle: Поддерживаемый alias — не дефект; конечный census и declared window до удаления. | REQ-PCL-01-06, REQ-PCL-01-07 |
| `C30-G03` | shared: Численные показатели сохраняются, measurement source binding у existing producer/bridge. | REQ-PCL-01-04, REQ-PCL-01-05; FRC-02 |

Все source-registry remaining также связаны: `remaining:0481`, `remaining:0482`, `remaining:0483`, `remaining:0484`, `remaining:0485`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-PCL-01-01
Для поддержанного continuous report output один и тот же валидированный CalibrationDiagnosticsReport в typed форме, JSON mapping и после сохранения/readback должен давать одинаковый ограничивающий receipt при merge с положительным sidecar. Empty/incomplete/source-not-established output не может сохранять approximate_calibrated только из-за изменения представления.
Источник: LA-052; C30-R01. Проверки: TEST-PCL-01-01, TEST-PCL-01-05.

### REQ-PCL-01-02
Serialized continuous report восстанавливается по известному owner/output contract и полной DTO validation до receipt reconciliation. Самоназвание task=continuous не устанавливает ни происхождение, ни пригодность; malformed/неподтверждённое expected output не может fall through к unbound positive sidecar. Generic valid receipt и binary/multiclass contracts сохраняют собственную семантику, без навязывания continuous interval inventory.
Источник: LA-052; C30-R01. Проверки: TEST-PCL-01-01, TEST-PCL-01-02, TEST-PCL-01-05.

### REQ-PCL-01-03
Canonical curve/continuous APIs сохраняют полный inventory запроса: empty comparisons дают None-метрики и not_evaluated, пропущенная часть — incomplete с перечисленными уровнями, misaligned/surplus lengths — точную ошибку. n_obs не подменяет число interval comparisons. Доступная измеренная часть остаётся диагностически видимой, но неполнота не получает positive calibration tier и не запускает bootstrap как полный корпус.
Источник: LA-052; C30-G01. Проверки: TEST-PCL-01-03.

### REQ-PCL-01-04
Корректные95/100 при nominal.95 и0/100 остаются различимыми по actual coverage/ECE; bootstrap/PIT/ENCE и small-sample downgrade сохраняются. Для continuous report candidate_numeric_tier отделён от фактического source assurance: хорошая математика без measurement binding остаётся unverified с measurement_source_not_established.
Источник: LA-052; C30-G03, C30-G01. Проверки: TEST-PCL-01-04.

### REQ-PCL-01-05
Ремонт проверяется через настоящий method runner/dispatcher merge, output representation boundary, запись и свежий reader; typed report и receipt models не заменяются фикстурами. Положительный содержательный numerical report доходит до потребителя с точным scope, а sidecar не повышает его роль. Реальный observed source/experiment bridge проверяется совместно с FRC-02, не создаётся новым глобальным receipt registry.
Источник: LA-052; C30-G01, C30-G03. Проверки: TEST-PCL-01-05.

### REQ-PCL-01-06
В поддержанном compatibility окне public root, actual calibration.curve и Scientist alias экспортируют те же CalibrationPoint, CalibrationResult и compute_calibration_curve, с прежними valid values и exceptions. Численные tests остаются у canonical owner; старый файл содержит только проверку identity, не вторую копию численного набора.
Источник: LA-053; C30-G01, C30-G02. Проверки: TEST-PCL-01-06.

### REQ-PCL-01-07
Retirement старого Scientist адреса допускается только после конечного census прямых/относительных FQN, config/notebook/generated/public surfaces и решения по внешнему supported window. Пока основание недостаточно, supported alias явно сохраняется. Если снятие разрешено, удаляется только этот reexport и связанные declarations, с negative import/packaging проверкой; весь backtesting и новые цепочки aliases не создаются/не удаляются ради этой задачи.
Источник: LA-053; C30-G02. Проверки: TEST-PCL-01-07.

## 5. Конкретное техническое решение

**Ремонт на границе, а не новая математика.** Current `_typed_continuous_receipts` видит только DTO, `_merge_dispatch_result` принимает `MethodResult.output: Any`, а telemetry `_record_execution` тоже извлекает receipt. Нужна одна контрактная нормализация representation до обоих consumers. Предпочтительно использовать известный `MethodSignature.output_slots`/его output contract в dispatcher, восстановить `CalibrationDiagnosticsReport.model_validate` для объявленного report slot и передать полученный typed объект в existing extraction/reconciliation. Нормализовать один раз и переиспользовать результат merge/telemetry, не писать два разных decoder.

IR generic receipt helper не должен импортировать Foundry/Scientist для поиска registry. Контекст известного output contract передаёт верхний dispatcher либо уже существующий serialization owner. Если конкретный путь не имеет такого контекста, unbound positive sidecar не считается доказательством continuous calibration: поддержать явный ограниченный outcome либо требовать known contract на этой boundary. Полный validated DTO может использоваться для **понижения** сильного sidecar, но наличие dict/task label не создаёт source authority. Не добавлять эвристику `task==continuous ⇒ trust dict` и не ослаблять validation exceptions так, чтобы failure снова fall through к positive sidecar.

**Сохранить текущую численную реализацию.** Публичный API уже ведёт в `calibration/curve/_compute.py` и `calibration/diagnostics/continuous.py`. Unknown metrics/incomplete inventory, bootstrap suppression и real report receipt — нужный результат, а не незавершённость, которую лечат low ECE threshold. Для хорошего continuous корпуса сохранять candidate_numeric_tier, measurement_source_not_established остаётся до actual FRC-02 source binding. Binary/multiclass ветки не переписывать под interval-only контракт.

**Alias:** обычные imports уже должны использовать `polisyos.calibration`, а старый15-line Scientist shim и34-line identity test полезны до DEC-ALIAS. Не переносить numerical suites заново, не удалять весь backtesting. Снять только точный адрес после полного finite surface census и compatibility решения. Изменение receipt semantics и alias removal — разные reviewable части, даже если их сдают в одном окне.

### Текущие owners и источники

- [policy-engine/src/polisyos/calibration/curve/_compute.py:12–86](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/calibration/curve/_compute.py#L12-L86)
- [policy-engine/src/polisyos/calibration/diagnostics/continuous.py:24–187](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/calibration/diagnostics/continuous.py#L24-L187)
- [policy-engine/src/polisyos/ir/analytics/calibration_diagnostics.py:93–325](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/calibration_diagnostics.py#L93-L325)
- [policy-engine/src/polisyos/ir/analytics/_truthfulness.py:183–240](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/_truthfulness.py#L183-L240)
- [policy-engine/src/polisyos/foundry/methods/backends/dispatch.py:387–417](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/dispatch.py#L387-L417)
- [policy-engine/src/polisyos/foundry/methods/backends/protocol.py:199–222](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/protocol.py#L199-L222)
- [policy-engine/tests/unit/scientist/methods/backtesting/test_calibration_curve.py:1–34](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/methods/backtesting/test_calibration_curve.py#L1-L34)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-PCL-01-01 · native local merge regression
**NOT_RUN. REQ:** REQ-PCL-01-01, REQ-PCL-01-02.
**Setup:** Actual evaluate_continuous(y_true=100 finite values, intervals={}) и положительный sidecar TruthfulnessReceipt; варианты typed report, model_dump(mode=json), canonical JSON readback. Повторить incomplete report и вложенные output/artifact containers.
**Действие:** Создать actual MethodResult и вызвать actual _merge_dispatch_result с выбранным declared output contract; отдельно непосредственный extractor boundary по поддержанному контракту.
**Oracle:** Все три формы ограничивают sidecar до одного unverified receipt, с сохранёнными scope/reasons. В прежнем коде mapping оставлял approximate_calibrated — этот различающий случай обязан краснеть до ремонта. Дублированная ссылка на тот же контейнер/cycle не вызывает бесконечной рекурсии.
**Место:** `tests/unit/foundry/methods/test_truthfulness_protocol.py; tests/unit/calibration/diagnostics/test_continuous.py; methods/backends/dispatch.py::_merge_dispatch_result`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-PCL-01-02 · native contract confusion/negative
**NOT_RUN. REQ:** REQ-PCL-01-02.
**Setup:** Expected CalibrationDiagnosticsReport slot: полный DTO mapping, malformed missing metrics, inconsistent inventory, unsupported schema/version; отдельно чужой dict только task=continuous и genuine binary/multiclass report.
**Действие:** Провести через normalizer/merge и actual TruthfulnessReceipt reconciliation.
**Oracle:** Known valid DTO восстановлен; expected malformed payload адресно отказан либо получает ограниченный result без positive receipt. Чужой self-label не становится authenticated report. Binary/multiclass сохраняют свой valid receipt и не требуют interval_coverage; произвольная неподтверждённая metadata не может создавать сильную continuous роль.
**Место:** `tests/unit/foundry/methods/test_truthfulness_protocol.py; ir/analytics/_truthfulness.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-PCL-01-03 · native canonical numeric/denominator matrix
**NOT_RUN. REQ:** REQ-PCL-01-03.
**Setup:** 100 finite y; intervals={} и[]/levels=[]; empty y; missing both intervals/samples; лишний level/set; short set; partial и all-skipped sets; metadata claim5comparisons при одном bin.
**Действие:** Вызвать existing compute_calibration_curve/evaluate_continuous, сохранить настоящий report, прочитать model_validate_json и вызвать to_truthfulness_receipt.
**Oracle:** Empty comparisons0, метрики None, not_evaluated/error и receipt unverified. Partial сохраняет measured metrics, incomplete inventory и отсутствие full bootstrap; misalignment адресно отвергнут. Actual bins/counts побеждают нарисованную metadata.
**Место:** `tests/unit/calibration/curve/test__compute.py; tests/unit/calibration/diagnostics/test_continuous.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-PCL-01-04 · native numerical positive/negative and task scope
**NOT_RUN. REQ:** REQ-PCL-01-04.
**Setup:** Предзаданные .95 intervals с95/100 и0/100 покрытия; small sample10; samples для PIT/ENCE и bootstrap с фиксированным RNG.
**Действие:** Выполнить canonical API/report/readback/receipt; сравнить actual numeric fields и source assurance.
**Oracle:** ECE0 против.95; хорошие значения не теряются при сохраняющемся unverified/source_not_established. Small-sample downgrade и samples/default-level behavior сохранены, явные levels=[] не заменены default. Binary/multiclass не проходят чужой continuous guard.
**Место:** `tests/unit/calibration/diagnostics/test_continuous.py; tests/unit/calibration/curve/test__compute.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-PCL-01-05 · native dispatch/persist/fresh consumer E02-I03-B
**NOT_RUN. REQ:** REQ-PCL-01-01, REQ-PCL-01-02, REQ-PCL-01-05.
**Setup:** Тестовый method с объявленным текущим report output contract, вычисляющий genuine evaluate_continuous; actual supported runner/MethodDispatcher, настоящий serializer/CAS/reader, sidecar конфликт. Если найден действительный такой producer — использовать его вместо test method.
**Действие:** Пропустить typed и serialized forms по одной declared boundary; сохранить итог, прочитать свежим consumer; затем чужой schema/source/sidecar.
**Oracle:** Одинаковый итоговый ограниченный receipt и численные значения во всех поддержанных формах, без повышения source assurance. Malformed expected report не замещается sidecar. Реальное FRC-02 measurement admission — отдельный bound variant, не от одного DTO.
**Место:** `foundry/methods/backends/dispatch.py; tests/unit/foundry/methods/test_truthfulness_protocol.py`.
**Doubles:** Тестовый method/data допустимы для generic dispatcher contract; он обязан звать actual calibration owner. Runner, merge, models, serializer/CAS и consumer не подменяются. Такой тест не доказывает prevalence в production.

### TEST-PCL-01-06 · native public import/installed distribution
**NOT_RUN. REQ:** REQ-PCL-01-06.
**Setup:** Поддержанный Python и actual built/installed distribution в отдельной согласованной packaging среде; root, implementation package и legacy Scientist import.
**Действие:** Запустить существующий identity-only test плюс canonical numeric suites; записать import origins, exceptions и при необходимости время startup без обещанного ускорения.
**Oracle:** Все три объекта тождественны, normal values/errors сохранены, numerical tests не скопированы в old path. Импорт не привязан случайно к checkout вместо installed artifact; отсутствие package extras честно BLOCKED.
**Место:** `tests/unit/scientist/methods/backtesting/test_calibration_curve.py; calibration/__init__.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-PCL-01-07 · finite lifecycle census/decision
**NOT_RUN. REQ:** REQ-PCL-01-07.
**Setup:** Закреплённый полный перечень репозиторных src/tests/config/notebooks/generated/public manifests; отдельно доступные external consumer сведения и объявленный support договор, не выдуманный zero-external graph.
**Действие:** Сохранить denominator/path hits с классификацией executable/compatibility/history. Принять retain-window либо authorized-retire; во втором варианте проверить wheel contents и отсутствие import/FQN, canonical API positive.
**Oracle:** Retain — alias и identity test остаются намеренно. Retire — только reexport/declarations исчезают, canonical API жив, старый адрес адресно не разрешается; нет tombstone или новой alias chain. Неизвестные внешние callers явно ограничивают решение, не считаются нулём.
**Место:** `scientist/methods/backtesting/calibration_curve.py; architecture/public_surface/contract.toml и generated surfaces`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/calibration/curve/test__compute.py tests/unit/calibration/diagnostics/test_continuous.py
python -m pytest -q tests/unit/scientist/methods/backtesting/test_calibration_curve.py tests/unit/foundry/methods/test_truthfulness_protocol.py
# Новый serialized merge regression добавить к действительному dispatcher/receipt suite, selector разрешить по checkout.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I03-B**: [канонический контракт LANE-03](../03_Интеграция/LANE-03.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

Один writer generic IR receipt extraction, dispatcher companion обязателен для actual serialized/output/telemetry route. Numerical owners не получают второй acceptance policy. Сначала distinct typed/mapping regression и actual contract handoff, затем focused suite, затем один E02-I03-B variant. Alias lifecycle можно исследовать параллельно, но его unknown external scope не блокирует адресный receipt repair.

- **FRC-02:** Один measurement-source bridge и общий native scenario; numeric report здесь не повышает роль сам.
- **FRC-01:** Summary/support refs должны сохранять ограничения report/receipt; shared gateway writer согласован.
- **API-01 / LANE-12:** Переиспользовать existing public-surface/packaging правила для finite alias lifecycle, без общего массового удаления.

## 8. Совместимость, миграция и возврат

Новый repair не переименовывает public CalibrationResult и не переписывает старые receipts. Для expected serialized report malformed/несогласованный payload становится явным отказом/ограничением — намеренный fix; canonical valid typed/JSON report остаётся эквивалентным. Исторические positive receipts без measured basis не переаттестовываются и могут требовать re-evaluation по владельцу. Retain/retire alias фиксируется отдельно. Rollback не должен возвращать lost-report precedence; при временной деградации ограничить только непроверенный serialized continuous route, сохранив typed и canonical numerical API.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0, lines559–617](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Один declared output contract нормализует разные представления без ветки по конкретному method/case. Новая семантика источника не возникает из универсального dict decoder.
- [wave5-evidence-substitution-ratification.md — K01 и K07–K08](../05_Основания/Архитектура/wave5-evidence-substitution-ratification.md): Численная согласованность и sidecar marker не заменяют источник измерений. Сохраняется полезный candidate, а не только отказ. TruthfulnessReceipt не присваивает права решения.

## 10. Конечные решения и сдача

### DEC-PCL-01-BOUNDARY
**Вопрос:** Где actual serialized CalibrationDiagnosticsReport имеет известный output contract?
**Кто решает:** Dispatcher/serialization owner вместе с canonical calibration owner.
**Конечное действие/выход:** Проследить actual producers и output-slot metadata до merge и telemetry; выбрать существующий contract-carrying seam. Сдать одну реализованную нормализацию и native controlled producer path; если production caller не найден, явно ограничить claim generic contract acceptance, не утверждать production prevalence.
**До решения:** Не распознавать authority по произвольному task label и не оставлять positive sidecar как fallback после invalid expected report.

### DEC-PCL-01-ALIAS
**Вопрос:** Завершилось ли поддерживаемое окно Scientist calibration_curve alias?
**Кто решает:** Public API/release owner; технический reviewer.
**Конечное действие/выход:** Сдать TEST-07 census, публичный статус и доступное внешнее подтверждение; выбрать retain с названным основанием либо retirement точного адреса. Дату не назначать произвольно.
**До решения:** Alias поддерживается, identity-only test сохраняется; numerical repair сдаётся независимо.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
