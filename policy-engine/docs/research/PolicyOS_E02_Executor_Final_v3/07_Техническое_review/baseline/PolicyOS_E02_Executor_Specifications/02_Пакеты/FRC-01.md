# FRC-01 — Сводка S10 без повторного выдумывания pass и реальные support refs

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-03 · CP1 · B32, LA-051.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Исправить повышение limit/floor=False до pass в summary; закончить честную связь support с реальными refs, сохранив численные diagnostics и полезный conditional forecast. Квалифицировать temporal/test boundary вместе с действительным bridge FRC-02.

**Тип работы:** Один подтверждённый semantic repair C29-R01; capability wiring C29-G02; квалификация и test maintenance C29-G01/G03/G04. Финальный accountable owner LA-051 — FRC-02, не дублирующий calibration producer.

[Аудит](../05_Основания/Аудит/02_Пакеты/FRC-01.md) · [остатки](../05_Основания/Аудит/01_Реестры/C29_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/FRC-01_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C29_источники.json) · [трассировка](../04_Трассировка/FRC-01.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

**B32:** default-date/now/credible уже устранены, сохранять реальные шесть ролей REQ-03 и conditional path REQ-05. **LA-051, этап1:** estimator shape уже не эмпирическая калибровка, сохранить REQ-02; summary исправить REQ-01; support-reference bridge дополнить REQ-04; actual producer/admission этап2 проверить совместно REQ-06. **LK29:** S10 арифметика, EvalSafety/WMR/candidate и production admission — разные guards, не удалять. **LK30:** generic calibration — действующий numerical owner; не заменять его новым framework и не применять predictive interval coverage к CI причинного параметра без совместимого дизайна. Историческая фраза C29 «FRC-02 ещё unassessed» относится к порядку фазы1, не состоянию полного комплекта.

- `preserve:0101`: Bound aware temporal roles. → REQ-FRC-01-03; TEST-FRC-01-03.
- `preserve:0102`: No default credible/floor. → REQ-FRC-01-01, REQ-FRC-01-02, REQ-FRC-01-05; TEST-FRC-01-01, TEST-FRC-01-02, TEST-FRC-01-05.
- `preserve:0103`: Raw mapping is insufficient. → REQ-FRC-01-03, REQ-FRC-01-05, REQ-FRC-01-07; TEST-FRC-01-03, TEST-FRC-01-06.
- `preserve:0104`: Conditional simulation-only path. → REQ-FRC-01-05; TEST-FRC-01-02, TEST-FRC-01-05.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C29-R01` | fix: Summary не имеет права пересоздавать floor по counts. | REQ-FRC-01-01 |
| `C29-G01` | shared: Реальный bridge уже существует; full producer/reopen qualification одна, не дублирующая реализация. | REQ-FRC-01-05, REQ-FRC-01-06; FRC-02 |
| `C29-G02` | capability: Связать actual support content; optional неизвестное не фабриковать строками. | REQ-FRC-01-04, REQ-FRC-01-06 |
| `C29-G03` | lifecycle: Ограниченный temporal contract и обслуживание устаревшего characterization, не автоматическое снятие guards. | REQ-FRC-01-03, REQ-FRC-01-07 |
| `C29-G04` | qualify: Actual native owners и scientific scope вместо fixture claims; общий served run переиспользуется. | REQ-FRC-01-02, REQ-FRC-01-05, REQ-FRC-01-06, REQ-FRC-01-07; FRC-02 |

Все source-registry remaining также связаны: `remaining:0079`, `remaining:0080`, `remaining:0081`, `remaining:0082`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-FRC-01-01
summarize_forecast_support_integrity должен сохранять описательные numerator/denominator/pass_rate, но не создавать admitted calibration pass/floor из одного равенства counts. При входном limit/floor=False и10/10 итог не может быть pass/floor=True. Для непустого согласованного набора действительных passed/floor=True записей с совместимым governed threshold/rule/scope и выполненными остальными admission conditions summary обязан сохранять pass/floor=True, в том числе95/100 при explicit threshold.90 или.95; counts не обязаны равняться denominator. Иначе admitted pass не разрешён; неоднородность или ограничение видны в issue_codes и ограниченном summary, не отменяя полезные отдельные записи.
Источник: LA-051; C29-R01. Проверки: TEST-FRC-01-01.

### REQ-FRC-01-02
Finite estimator point/CI, nominal confidence и sample count остаются estimator-shape diagnostics, не измеренными coverage/error/числителем калибровки. Без разрешённого calibration evidence report=None остаётся blocked, имеющийся report — ограниченным; nominal0.8→0.95 без observations не улучшает empirical metrics или floor.
Источник: B32, LA-051; C29-G04. Проверки: TEST-FRC-01-02.

### REQ-FRC-01-03
Шесть временных ролей передаются из связанного источника без now/зашитой даты/искусственного сдвига и сравниваются на canonical admission. Для текущего bounded temporal profile сохраняются aware UTC, различимость и его порядок; missing/naive/несовместимое окно не создают record. Иной реальный дизайн требует согласованного явного расширения обоих owners, а не фальсификации timestamps.
Источник: B32, LA-051; C29-G03. Проверки: TEST-FRC-01-03.

### REQ-FRC-01-04
S10 support должен ссылаться на действительный producer artifact для заявленной содержательной поддержки и интервала, с тем же selected method/estimand/unit/level/source identity. Полный selected ArtifactRefModel, включая manifest_profile_sha256, должен сохраняться через producer, persisted support и fresh reader; ID-only строка допустима для отображения, не admission. URI, сочинённый из ID или суффикса /95, не может заменять разрешение содержания. Неустановленные optional source/method/sensitivity/equilibrium/distribution refs остаются None/пустыми с точным ограничением; затронутый governed tier не повышается, но доступный conditional результат сохраняется.
Источник: B32, LA-051; C29-G02. Проверки: TEST-FRC-01-04, TEST-FRC-01-06.

### REQ-FRC-01-05
Simulation-only/advisory и корректный предиктивный результат сохраняют useful numerical payload при отсутствии эмпирической/causal authority. Raw mapping, отсутствующая credibility, foreign N4 outcome relation либо отсутствующий evidence ref не создают calibration record/credible/floor. S10 purpose denials, EvalSafety/WMR/candidate binding и non-production роль сохраняются в actual envelope/summary consumers.
Источник: B32, LA-051; C29-G01, C29-G04. Проверки: TEST-FRC-01-02, TEST-FRC-01-03, TEST-FRC-01-05, TEST-FRC-01-06.

### REQ-FRC-01-06
Через существующий HTTP producer и reopened reader canonical empirical evidence loader должен передать реальные refs, method/version/rule/history/времена и полученный calibration статус в gateway/S10. Положительный путь и его отрицательные binding controls выполняются один раз в E02-I03-B с FRC-02; resolved-wrapper fixture не заменяет это свидетельство.
Источник: B32, LA-051; C29-G01, C29-G02, C29-G04. Проверки: TEST-FRC-01-06.

### REQ-FRC-01-07
Устаревший FRC-01 temporal characterization должен быть согласован с actual admitted boundary: отдельный отрицательный raw-map/неверное окно и положительный real producer→loader случай. Тест не требует восстановления raw bypass и не утверждает false PASS по историческому header RED; historical run evidence не переписывается.
Источник: B32, LA-051; C29-G03, C29-G04. Проверки: TEST-FRC-01-03, TEST-FRC-01-06.

## 5. Конкретное техническое решение

**Summary repair:** у `outcome_prediction.py::summarize_forecast_support_integrity` оставить arithmetic totals отдельными от admitted disposition. Добавить явный pure reduction входных `calibration_status`, `floor_passed`, threshold/rule и совместимости observable scope. Для согласованной непустой группы pass может только наследоваться от всех admitted pass records; никакой формулы `numerator==denominator` для нового floor. При mixed/blocked/missing basis итог limit/blocked с конкретным issue и сохранёнными отдельными records; ограничение одного несвязанного claim не отменяет пригодность другого. Если нужен общий threshold для неоднородных групп — это новый governed aggregation contract; здесь его не изобретать. Покрытие95/100 может быть admitted pass по своему threshold, поэтому нельзя также требовать100/100 после ремонта.

**Support wiring:** `_build_s10_forecast_inputs` уже получает resolved empirical projection и references. Дополнить handoff существующими producer artifacts выбранного прогноза/метода; передавать полный selected `ArtifactRefModel` в canonical loader, не `interval://hash/95`. `_s10_artifact_ref_id` возвращает только ID и теряет `manifest_profile_sha256`, поэтому годится лишь как display helper. Если нынешнее поле support допускает только строку, использовать существующее profile-bearing typed extension/locator и согласованно обновить producer/persisted reader; не восстанавливать profile по default manifest. Согласовать с BKT-01 REQ-04 (сохранение selected MetricsRef), без нового store. Проверить содержание level/estimand/source у producer boundary, затем передать связанную ссылку. Optional source_contract/method_validity/sensitivity/equilibrium/distribution поля в ForecastSupport уже nullable/списки: при отсутствии действительного evidence использовать их штатное пустое представление и existing limitation refs. Не строить отдельный assurance store и не отключать conditional forecast ради optional ref. Для governed tier, требующего interval, отсутствие binding ограничивает именно этот tier.

**Времена и tests:** current temporal profile в `forecast_bridge.py` и `_bound_s10_temporal_roles` согласованно строгий. Не исправлять raw-map старый testcase возвратом bypass. Positive characterization строится через имеющийся canonical producer/loader; raw map и несовместимое окно становятся отдельными negatives. Если новый реальный дизайн допускает совпадение временных ролей, изменить named profile у обоих owners вместе после DEC-TIME, а не глобально требовать разные физические моменты для всех исследований.

**Сохранённый путь:** report shape → diagnostics (не calibration); compatible forecast/history → canonical measured report/evidence → loader → gateway → S10 → summary/envelope → reopened consumer. Causal CI не становится predictive interval одной сменой имени. S10 остаётся ограниченным назначением и не заменяет EvalSafety/WMR/candidate/epoch guards.

### Текущие owners и источники

- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:17173–17186](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L17173-L17186)
- [policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py:105–257](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py#L105-L257)
- [policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py:590–649](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py#L590-L649)
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:17217–17590](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L17217-L17590)
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:17649–17829](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L17649-L17829)
- [policy-engine/src/polisyos/calibration/forecast_bridge.py:345–366](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/calibration/forecast_bridge.py#L345-L366)
- [policy-engine/tests/unit/remediation/test_frc_01.py:105–185](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_frc_01.py#L105-L185)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-FRC-01-01 · native summary DTO + sibling consumer
**NOT_RUN. REQ:** REQ-FRC-01-01.
**Setup:** Actual ForecastCalibrationRecord(limit,floor=False,n=10,d=10) и blocked support из C29-P16; отдельно genuine passed1row с floorTrue;95/100 с upstream pass/floorTrue и explicit threshold.90/.95; mixed pass+limit, zero denominator и разные threshold/rule/scope.
**Действие:** Вызвать actual summarize_forecast_support_integrity и затронутый proving-ground summary consumer; переставить порядок records.
**Oracle:** 10/10 остаётся descriptive rate1, но summary не pass/floorTrue, issue сохраняет upstream limitation. Homogeneous genuine all-pass при сохранённых compatible bindings и floorTrue обязан дать summary pass/floorTrue;95/100 при explicit threshold.90/.95 и выполненных остальных admission conditions также pass/floorTrue, не always-limit. Это сохраняет уже обоснованный upstream pass, не выводит его из counts; mixed/zero/несовместимые профили не дают общего admitted pass. Counts и purpose denials не теряются. Старый counts-only код обязан провалить limit10/10 контроль.
**Место:** `tests/unit/runtime/quality/test_design_axes_outcome_prediction.py; proving_ground/causal_forecast_search.py summary call`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-FRC-01-02 · native estimator adapter + numerical distinction
**NOT_RUN. REQ:** REQ-FRC-01-02, REQ-FRC-01-05.
**Setup:** Один finite report с nominal0.8/0.95, отсутствующий report и failed diagnostic; отдельно два genuine predictive corpora при одинаковом nominal0.95: все observations внутри/вне intervals.
**Действие:** Вызвать actual _s10_calibration_evidence_from_report и actual canonical calibration curve на соответствующем predictive корпусе.
**Oracle:** Report shape не создаёт empirical numerator/denominator/coverage; None blocked, failed diagnostic limit/floorFalse. Curve действительно различает coverage1/0 и ECE≈.05/.95, но эти два независимых численных контроля не связывают causal parameter CI с индивидуальными outcomes.
**Место:** `tests/unit/remediation/test_frc_01.py; calibration/curve/_compute.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-FRC-01-03 · native temporal boundary + test maintenance
**NOT_RUN. REQ:** REQ-FRC-01-03, REQ-FRC-01-05, REQ-FRC-01-07.
**Setup:** Шесть реальных distinct aware времён из canonical admitted fixture FRC-02; изменить одно на missing/naive/equal/неверный order. Отдельно old raw mapping из test_calibration_time_roles_are_preserved_from_bound_evidence.
**Действие:** Провести через EmpiricalCalibrationContext, _resolve_s10_empirical_evidence и S10 builder; сравнить each role после записи/readback.
**Oracle:** Valid роли сохраняются как те же instants в UTC, нет now/default. Raw mapping без owner admission не создаёт record; old incompatible window — negative. Equal roles честно ограничены текущим профилем, а не сдвинуты на микросекунду. Изменение admitted profile допускается только согласованным DEC-TIME.
**Место:** `tests/unit/remediation/test_frc_01.py; calibration/forecast_bridge.py::EmpiricalCalibrationContext`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-FRC-01-04 · native support-reference wiring
**NOT_RUN. REQ:** REQ-FRC-01-04.
**Setup:** Два реальных persisted prediction/report artifacts с уровнями0.80 и0.95, одинаковым point; optional sensitivity/equilibrium artifact отсутствует либо другой source/method. Для одинаковых bytes создать sibling manifest profiles: valid selected/foreign default и обратную конфигурацию.
**Действие:** Собрать support через действительный gateway, разрешить interval ref выбранным reader, затем подменить foreign artifact или убрать ссылку.
**Oracle:** 0.80 support ссылается на реальный0.80 interval content, не всегда /95; foreign method/estimand/source ref отказан либо точно ограничен. Отсутствующий optional evidence не заменяется придуманным URI. Conditional численный payload остаётся доступным; строковое наличие ref не считается доказательством. В обеих sibling-profile конфигурациях reader потребляет только explicitly selected profile; default lookup не заменяет выбор и foreign profile не проходит.
**Место:** `generation_cycle.py::_build_s10_forecast_inputs; actual predictive_calibration producer/reader`.
**Doubles:** Реальные tiny persisted artifacts разрешены. Нельзя сделать только строковый suffix test и назвать content-binding принятым.

### TEST-FRC-01-05 · native typed support/envelope preservation
**NOT_RUN. REQ:** REQ-FRC-01-05.
**Setup:** Simulation-only без calibration record; predictive-only bound record; unbound N4 outcome; missing counterfactual credibility.
**Действие:** Передать через actual build_forecast_support/envelope/summary и затронутый downstream purpose check.
**Oracle:** Simulation-only сохраняет advisory outcome без empirical record; predictive не даёт causal/treatment/production/S11 authority. Unbound outcome не получает tier только из корректного наблюдаемого ряда. Missing credibility остаётся insufficient_history/not_established в своём профиле.
**Место:** `tests/unit/runtime/quality/test_design_axes_outcome_prediction.py; generation_cycle.py::_s10_value_authority_boundary`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-FRC-01-06 · native served create→reopen E02-I03-B
**NOT_RUN. REQ:** REQ-FRC-01-04, REQ-FRC-01-05, REQ-FRC-01-06, REQ-FRC-01-07.
**Setup:** Один compatible ForecastOwner/backtest корпус и source-bound method/rule/times; действительные HTTP service create/reopen и canonical loader, согласованные с FRC-02/PCL-01.
**Действие:** Создать и сохранить evidence/S10, переоткрыть fresh service/reader; контролируемо менять method version, rule, temporal roles, ref availability, selected manifest profile при тех же bytes или N4 relation.
**Oracle:** Valid report/receipt/record сохраняют measured corpus и полные profile-bearing refs/times, включая непрерывность manifest_profile_sha256. Valid selected при foreign default работает; foreign selected при valid default отказывает. Wrong bindings/unknown refs не дают pass; данные и полезный conditional прогноз остаются видимы с адресной причиной. Actual loader не заменён вручную созданной _S10ResolvedEmpiricalEvidence.
**Место:** `runtime/http/services/predictive_calibration.py; существующие native acceptance tests FRC-02`.
**Doubles:** Только внешний transport/clock вне проверяемых временных фактов допускает controllable double. Forecast/calibration/CAS/loaders/S10 consumers — actual.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_frc_01.py tests/unit/runtime/quality/test_design_axes_outcome_prediction.py
# Shared served create/reopen: точные selectors канонического FRC-02 acceptance, один согласованный запуск.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I03-A, E02-I03-B**: [канонический контракт LANE-03](../03_Интеграция/LANE-03.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

Один writer summary owner и один согласованный gateway writer, FRC-02 обязательный companion. Сначала distinguishing limit10/10 и optional-ref characterization, затем summary/wiring, потом shared native E02-I03-B. В собственном локальном FRC-01 не создавать второй HTTP/CAS harness. Содержательный результат FRC-02 не присваивается только по наличию его отчёта.

- **CYC-01:** Реальный request/context owner, не повторная реализация.
- **FRC-02:** Accountable LA-051 bridge/served qualification; совместные gateway fields и temporal profile.
- **PCL-01:** Canonical numeric calibration/report/receipt contract; не второй расчет coverage здесь.
- **EMP-01:** Сохраняемые scope/value bounds переданы в общую summary без повышения силы.

## 8. Совместимость, миграция и возврат

Исторические records сохраняются со своими timestamps/provenance; новый summary отражает исходные ограничения, не меняет старые записи. Изменение summary pass — намеренный semantic fix; downstream displays/tests обновить, не присваивая summary самостоятельной authority. Удаление manufactured optional refs требует учесть readers, ожидавших непустую строку: они получают explicit missing/limitation, а не success-shaped placeholder. Версию temporal profile не менять без DEC-TIME и companion FRC-02. Rollback должен сохранять отказ ложному pass; нельзя восстанавливать count-only promotion для старого UI.

## 9. Free-grow и обоснованные границы

- [policy-design-custody-time-model.md — §2–5: semantic time roles, family-native contracts](../05_Основания/Архитектура/policy-design-custody-time-model.md): Разные роли времени не равны обязательной искусственной разнице instants. Сохраняется нынешний ограниченный профиль; новый дизайн расширяется семантически, не через now/подгонку дат.
- [wave5-evidence-substitution-ratification.md — K01 и K07–K08: evidence substitution boundaries](../05_Основания/Архитектура/wave5-evidence-substitution-ratification.md): Finite CI, строковый ref и арифметическая доля не заменяют measured evidence/право использования. Положительный conditional путь сохраняется; документация не повод добавить универсальный бумажный gate.

## 10. Конечные решения и сдача

### DEC-FRC-01-TIME
**Вопрос:** Нужен ли реальному поддержанному эксперименту иной temporal profile, например совпадающие роли?
**Кто решает:** FRC-01/FRC-02 и владелец экспериментального дизайна.
**Конечное действие/выход:** Предъявить один конкретный дизайн и шесть семантических ролей, объяснить допустимые равенства/порядок. Выбрать сохранение текущего профиля либо versioned согласованное расширение bridge/S10 с positive/negative controls.
**До решения:** Никаких искусственных дат; текущий профиль принимается только в его declared scope.

### DEC-FRC-01-SUPPORT
**Вопрос:** Какие optional support refs имеют реального producer/reader на выбранном forecast пути?
**Кто решает:** Gateway/ForecastOwner и затронутый S10 consumer.
**Конечное действие/выход:** Составить конечную таблицу source_contract/method_validity/sensitivity/equilibrium/distribution/interval: actual producer field→artifact→reader либо not_established. Реализовать доступные bindings; для отсутствующих — штатное empty+limitation, без фиктивного URI.
**До решения:** Только реально связанный support получает более сильную роль, conditional payload не удаляется.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
