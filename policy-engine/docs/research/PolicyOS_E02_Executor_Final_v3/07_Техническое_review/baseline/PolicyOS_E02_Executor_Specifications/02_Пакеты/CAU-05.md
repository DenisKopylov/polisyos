# CAU-05 — Dedicated DiD и ограниченный versioned replay без возврата umbrella в planning

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-05 · CP5 · LA-016.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Закрыть LA-016 на уровне фактического bootstrap, текущих callers и объявленной исторической совместимости. Сохранить corrected numerical owners; direct import не выдавать за frozen-plan replay.

**Тип работы:** Native qualification и lifecycle decision; metadata/cutover уже реализованы. Условное расширение существующего versioned replay owner только для подтверждённо поддерживаемого historical scope.

[Аудит](../05_Основания/Аудит/02_Пакеты/CAU-05.md) · [остатки](../05_Основания/Аудит/01_Реестры/C56_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/CAU-05_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C56_источники.json) · [трассировка](../04_Трассировка/CAU-05.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

LA-016 этап2/2, accountable CAU-05; CAU-01 этап1 и CAU-02 numerical companion. Independent constants, dedicated default boot и строгий direct adapter сохранены. A12: relocation не закрывает numerical/inferential fixes. did.py и оба numerical helpers не кандидаты удаления.

- `preserve:0622`: Independent metadata/common numerical helpers → REQ-CAU-05-01; TEST-CAU-05-01.
- `preserve:0623`: Dedicated default planning and maintained callers → REQ-CAU-05-02; TEST-CAU-05-02, TEST-CAU-05-03.
- `preserve:0624`: Strict old-slot/bool direct adapter → REQ-CAU-05-03; TEST-CAU-05-03, TEST-CAU-05-04.
- `preserve:0625`: Complete report/warnings and output aliases → REQ-CAU-05-03, REQ-CAU-05-06; TEST-CAU-05-03, TEST-CAU-05-07.
- `preserve:0626`: Non-gating candidate/scientific limits → REQ-CAU-05-06; TEST-CAU-05-07, TEST-CAU-05-08.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C56-G01` | qualify: Actual bootstrap/dispatch/CAS вместо isolated AST. | REQ-CAU-05-01, REQ-CAU-05-02, REQ-CAU-05-03, REQ-CAU-05-06 |
| `C56-G02` | lifecycle: Сначала finite supported history, затем existing versioned reader либо explicit retirement boundary. | REQ-CAU-05-03, REQ-CAU-05-04, REQ-CAU-05-05 |
| `C56-G03` | shared: Accountable LA016 связывает numerical companions, не повторяет и не закрывает их переносом metadata. | REQ-CAU-05-01, REQ-CAU-05-06; CAU-01/CAU-02 |

Все source-registry remaining также связаны: `remaining:0387`, `remaining:0388`, `remaining:0389`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-CAU-05-01
Standard/Staggered metadata и общие _run_* helpers не зависят от deprecated DifferenceInDifferences metadata/class binding. Assumptions/citations/equations сохраняются в независимых definitions и принадлежащих dedicated methods mappings, без cross-mutation.
Источник: LA-016; C56-G01, C56-G03. Проверки: TEST-CAU-05-01.

### REQ-CAU-05-02
Actual family component bridge/default registry/planner предлагают dedicated causal.inference.did.standard@1.0.0 и staggered@1.0.0, не retired generic. Maintained requests и benchmark callers достигают соответствующего numerical owner без legacy delegation.
Источник: LA-016; C56-G01. Проверки: TEST-CAU-05-02, TEST-CAU-05-03.

### REQ-CAU-05-03
Direct legacy adapter сохраняет old slots outcome_panel/treatment_indicator и bool/np.bool_ mode mapping. Конфликт old/new slots и ambiguous truthy values адресно отказаны. Equivalent effective old/dedicated запросы совпадают по всему corrected report, method_params, diagnostics и warnings; output aliases остаются согласованными.
Источник: LA-016; C56-G01, C56-G02. Проверки: TEST-CAU-05-03, TEST-CAU-05-04.

### REQ-CAU-05-04
До заявления historical replay определить конечный supported plan/schema/FQN/version scope и реальный persisted reader. Для поддержанной версии reader/migration однозначно преобразует old slots/mode в dedicated request, сохраняет original bytes/provenance и вычисляет новые corrected outputs с явным текущим method identity. Не добавлять implicit old-name alias в общий registry lookup ради обхода retirement.
Источник: LA-016; C56-G02. Проверки: TEST-CAU-05-05, TEST-CAU-05-06.

### REQ-CAU-05-05
Если historical support не заявлен или genuine fixtures недоступны, выходом lifecycle решения служит явно более узкий direct-import-only/retirement contract с unsupported version diagnostic и actionable migration boundary, а не обещание бесконечной совместимости. Не удалять полезный adapter до finite caller/artifact census и согласованного support window.
Источник: LA-016; C56-G02. Проверки: TEST-CAU-05-05, TEST-CAU-05-06.

### REQ-CAU-05-06
Native selected causal job→CAS→fresh reader сверяет whole persisted/offered report и envelope относительно фактических inputs и selected method; CAU-01/02 numerical oracles являются prerequisites общей приёмки. Source-bound numerical candidate сохраняется без automatic causal authority.
Источник: LA-016; C56-G01, C56-G03. Проверки: TEST-CAU-05-07, TEST-CAU-05-08.

## 5. Конкретное техническое решение

Existing `_DID_*` constants, dedicated classes и factory inventory уже правильны; не выполнять cosmetic relocation. Сохранить маленький direct compatibility adapter. Общий registry exact FQN branch намеренно не делает alias fallback. Историческую совместимость реализовывать на реальном versioned plan reader, где известны schema/version и old mode/slots, а не регистрировать umbrella для нового planning.

В DEC-REPLAY найти конечный поддерживаемый набор. Для него migration выдаёт явный dedicated FQN, canonical inputs и resolved parameters; конфликт identities отказывает до compute. Записать original plan identity и effective corrected method identity через существующую provenance связь, без параллельного migration store. Численная correction и interface mapping проверяются раздельно: не обещать битовое воспроизведение старой ошибочной статистики новым estimator. Если нужно именно historical execution, это отдельный pinned replay profile с явным статусом, не default result.

CAU-05 координирует один E02-I05-B: actual registry/dispatcher, persisted report и fresh consumer. Каждый numerical owner приносит свой oracle; shared scaffold не создаётся пять раз. Foreign report с правильными числовыми point/CI, но чужими diagnostics/inputs, не должен пройти. Отсутствие external corpus не мешает текущему dedicated пути, но ограничивает historical claim.

### Текущие owners и источники

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py:44–57](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L44-L57)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py:106–153](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L106-L153)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py:1074–1279](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L1074-L1279)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/_registry_boot.py:266–299](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/_registry_boot.py#L266-L299)
- [policy-engine/src/polisyos/foundry/methods/selection/registry.py:685–733](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/selection/registry.py#L685-L733)
- [policy-engine/src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py:5746–5804](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py#L5746-L5804)
- [policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py:539–615](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py#L539-L615)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-CAU-05-01 · native metadata ownership
**NOT_RUN. REQ:** REQ-CAU-05-01.
**Setup:** Заменить deprecated metadata poison object, затем отдельным контролем убрать legacy class binding; получить standard и staggered dedicated metadata.
**Действие:** Вызвать оба actual dedicated paths; мутировать допустимую копию assumptions одного потребителя и снова прочитать другого.
**Oracle:** Оба вычисления работают; definitions/citations/equations сохраняются; чужая mutation не меняет независимый owner. Не удалять numerical module для проверки retirement.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_did_diagnostics_ownership.py; tests/unit/remediation/test_cau_05.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-05-02 · native boot/request route
**NOT_RUN. REQ:** REQ-CAU-05-02.
**Setup:** Actual builtin component family loader, clean registry; maintained _default_g2_runtime_method_candidate.
**Действие:** Bootstrap без fixture registry; resolve dedicated FQNs, inspect actual request signature, request old full/short FQN.
**Oracle:** Dedicated owners зарегистрированы и исполнимы, standard signature без staggered flag; retired generic не предложен и default lookup отказывает. Synthetic planner refs не становятся empirical evidence.
**Место:** `tests/unit/runtime/quality/test_did_request_route.py; _registry_boot.py; extensions/_builtin_loader.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-05-03 · native equivalent route/callers
**NOT_RUN. REQ:** REQ-CAU-05-02, REQ-CAU-05-03.
**Setup:** Standard cluster80% и staggered not-yet-treated95%,399 draws, fixed seed; обе формы slots. Poison legacy pure_step для maintained benchmark controls.
**Действие:** Сравнить legacy direct adapter и dedicated result целиком; отдельно вызвать maintained benchmark runners.
**Oracle:** Report/result и envelope/uncertainty_envelope aliases согласованы; whole JSON report и warnings одинаковы для equivalent requests. Maintained callers не обращаются к poison legacy; numerical semantics остаются corrected, не исторически flawed.
**Место:** `tests/unit/remediation/test_cau_05.py; benchmarks/interference/policy_did_interference.py; benchmarks/natural_experiments/policy_natural_experiments.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-05-04 · native ambiguity boundary
**NOT_RUN. REQ:** REQ-CAU-05-03.
**Setup:** Mode values string false/true,0,1,None,empty collection; old+new aliases вместе; unknown DTO field; positive bool and np.bool_.
**Действие:** Materialize и dispatch через соответствующий actual entrypoint.
**Oracle:** Неподдержанные mode/slots не выбирают другой estimator через truthiness. Valid booleans и однозначные old slots сохраняют intended route. Ошибка остаётся typed/адресной, не generic success.
**Место:** `did.py::_legacy_staggered_flag; DifferenceInDifferences.materialize_input`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-05-05 · finite caller/artifact census
**NOT_RUN. REQ:** REQ-CAU-05-04, REQ-CAU-05-05.
**Setup:** Git-tracked Python плюс declared serialization/config/plan formats и доступный historical fixture corpus; denominator отдельно для каждого.
**Действие:** Найти FQN literals, import/alias usages, computed method identity producers и persisted plan/schema versions; назвать недоступные external domains.
**Oracle:** Таблица exact old→new scope с реальным owner reader, evidence и support decision. Отсутствие literal в Python не доказывает отсутствие frozen plans; counts8231/101 из аудита не вечный acceptance oracle.
**Место:** `Существующий replay/migration owner обнаружить по actual plan DTO/reader; C56 census как исторический locator, не новый runtime registry`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-05-06 · native versioned compatibility
**NOT_RUN. REQ:** REQ-CAU-05-04, REQ-CAU-05-05.
**Setup:** Для каждой объявленной supported version genuine old plan bytes и equivalent dedicated plan; unsupported version и ambiguous aliases negatives.
**Действие:** Прочитать actual existing versioned reader, выполнить migration/replay в свежем процессе и сохранить explicit original→effective identity mapping. Если support не заявлен — выполнить точный retirement refusal case.
**Oracle:** Supported old plan воспроизводимо даёт corrected effective request/report/warnings, historical bytes не переписаны; unsupported version не угадывается, не fallback на arbitrary newest. Default new planning остаётся dedicated. Без genuine fixture историческая квалификация NOT_ESTABLISHED, не fake PASS.
**Место:** `DEC-CAU-05-REPLAY; existing versioned plan owner`.
**Doubles:** Синтетический old-shaped dict годится для нового adapter unit test, не заменяет genuine historical replay evidence.

### TEST-CAU-05-07 · native E02-I05-B whole lifecycle
**NOT_RUN. REQ:** REQ-CAU-05-06.
**Setup:** Actual standard/staggered registered source-bound jobs с synthetic panels; actual CAS и fresh reader.
**Действие:** Выполнить primary job, сверить canonical report/envelope; изменить diagnostic window, target, unit score metadata или envelope при согласованной peer serialization.
**Oracle:** Valid outputs доходят до consumer. Подмена решающих facts отклонена относительно actual source/producer, не просто report==peer. Full report и candidate role сохраняются; прямой pure_step не считается этой проверкой.
**Место:** `scientist/nodes/builtins/simulate/run_causal_evaluation.py; existing selected DiD consumer tests`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-05-08 · shared numerical/scientific closeout
**NOT_RUN. REQ:** REQ-CAU-05-06.
**Setup:** Результаты CAU-01 partition/CR0/quantile и CAU-02 influence/anticipation/bootstrap/DGP в том же accepted revision.
**Действие:** Связать exact commands/results с LA-016 closeout; проверить non-gating projection на реальном report.
**Oracle:** Metadata migration не объявляет numerical tests PASS автоматически. Все требуемые исправления/qualified boundaries видимы; empirical identification не выводится из CI, синтетического planner marker или interface name.
**Место:** `CAU-01/CAU-02; E02-I05-B`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_cau_05.py tests/unit/foundry/methods/catalog/causal/test_did_diagnostics_ownership.py tests/unit/runtime/quality/test_did_request_route.py
# Versioned replay selector определяется DEC-REPLAY по actual owner; не выдумывать существующий test.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I05-B**: [канонический контракт LANE-05](../03_Интеграция/LANE-05.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

Один writer did.py для CAU-01/02/05; согласовать numerical patches до migration acceptance. Existing versioned plan owner определяется census; его изменение имеет собственный review. No deletion did.py, numerical helpers или general registry redesign.

- **CAU-01:** Оригинальный predecessor: detached metadata и corrected standard inference, включая partition repair.
- **CAU-02:** Оригинальный predecessor: corrected staggered target/variance/anticipation/bootstrap.
- **CAU-03/CAU-04:** Переиспользуют shared whole-report lifecycle сценарий, но не являются новой обязательной зависимостью локального DiD migration.

## 8. Совместимость, миграция и возврат

Dedicated cutover уже intentionally excludes generic from default registry. Preserve direct adapter до explicit retirement decision. New migration не изменяет archived bytes; old/new effective results маркируются exact method/version. Rollback возвращает совместимую пару reader/mapping, а не незаметно выбирает другой estimator. Поддержка всех неопределённых старых FQN не требуется.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Явные reusable method contracts дают рост через registry; legacy mapping — ограниченная совместимость, не вечная новая ветка для каждого plan.
- [policy-design-execution-topology.md — Applicability versus semantic judgment](../05_Основания/Архитектура/policy-design-execution-topology.md): Interface migration не обосновывает parallel trends/identification. Полезный numerical candidate сохраняется без authority fiction.

## 10. Конечные решения и сдача

### DEC-CAU-05-REPLAY
**Вопрос:** Какие frozen plan/schema/FQN версии действительно поддерживаются и каким reader?
**Кто решает:** DiD lifecycle owner и actual persisted-plan owner.
**Конечное действие/выход:** Сдать finite census, доступные genuine fixtures и таблицу supported/retired/unknown. Для supported scope расширить existing reader минимальным versioned mapping и actual replay test; иначе документировать direct-import-only support и actionable migration, не заявляя original broad replay исполненным.
**До решения:** Dedicated new planning; direct adapter сохранён; unknown external history не считается доказанно отсутствующей.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
