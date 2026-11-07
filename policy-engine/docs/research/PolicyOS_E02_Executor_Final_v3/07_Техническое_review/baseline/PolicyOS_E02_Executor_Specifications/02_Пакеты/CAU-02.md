# CAU-02 — Staggered theta_sel: native unit influence, согласованный CI/H0 и anticipation

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-05 · CP5 · B207, B208, B209.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Квалифицировать текущую содержательную inference, а не вновь bootstrap готовых ATT cells. Сохранить fixed target, shared unit contributions, finite-B inversion и useful point-only/gap results; донести их через registry/CAS/fresh selected reader без расширения scientific claim.

**Тип работы:** Preserve/qualify-only текущих numerical repairs; scoped design applicability. Новых R не установлено; product change только при воспроизведённом native несоответствии или конкретно выбранном расширении design.

[Аудит](../05_Основания/Аудит/02_Пакеты/CAU-02.md) · [остатки](../05_Основания/Аудит/01_Реестры/C53_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/CAU-02_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C53_источники.json) · [трассировка](../04_Трассировка/CAU-02.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

B207 unit influence с estimated cohort-share derivative уже реализован; B208 centered studentized Mammen scalar test и CI inversion едины; B209 controls timing>t+anticipation и baseline g−1−a уже исправлены. theta_sel намеренно отличается от старого cell-size weighted target; не выдавать это за equivalent move. A10/A12: dedicated metadata/FQN cutover не заменяет inference, finite DGP не доказывает universal coverage.

- `preserve:0525`: Fixed cohort-share theta_sel и explicit eligible periods → REQ-CAU-02-01; TEST-CAU-02-01, TEST-CAU-02-06.
- `preserve:0526`: Shared independent-unit influence включая cohort share derivative → REQ-CAU-02-02; TEST-CAU-02-02.
- `preserve:0527`: Mammen draw общий для зависимых cell contributions → REQ-CAU-02-02; TEST-CAU-02-03.
- `preserve:0528`: Единая finite-B plus-one CI/test inversion и closed endpoints → REQ-CAU-02-03; TEST-CAU-02-03.
- `preserve:0529`: Anticipation-aware admissible controls и точные cell gaps → REQ-CAU-02-04; TEST-CAU-02-04.
- `preserve:0530`: Point-only degenerate result без fake CI/p → REQ-CAU-02-02; TEST-CAU-02-02.
- `preserve:0531`: Current target/diagnostic binding и non-gating numerical report → REQ-CAU-02-01, REQ-CAU-02-05; TEST-CAU-02-05, TEST-CAU-02-06.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C53-G01` | qualify: Actual native registry/RNG/CAS/selected-reader lifecycle. | REQ-CAU-02-01, REQ-CAU-02-02, REQ-CAU-02-03, REQ-CAU-02-04, REQ-CAU-02-05 |
| `C53-G02` | qualify: Finite independent-unit scalar inference and intended design applicability, not universal coverage. | REQ-CAU-02-01, REQ-CAU-02-02, REQ-CAU-02-03, REQ-CAU-02-06 |
| `C53-G03` | qualify: Empirical anticipation/identification assumptions separate from correct eligibility. | REQ-CAU-02-04, REQ-CAU-02-07 |

Все source-registry remaining также связаны: `remaining:0327`, `remaining:0328`, `remaining:0329`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-CAU-02-01
Сохранить fixed study horizon/eligible periods каждой cohort и theta_sel: среднее cell effects внутри cohort, затем estimated ever-treated cohort shares. Current target binding включает actual outcomes/treatment/timing/unit/time alignment; diagnostic window имеет отдельный binding. Изменение target не скрывается сменой metadata label.
Источник: B207, B208; C53-G01, C53-G02. Проверки: TEST-CAU-02-01, TEST-CAU-02-06.

### REQ-CAU-02-02
Один multiplier draw действует на полный influence независимой panel unit во всех её treated/control cell contributions, включая derivative estimated cohort shares. Одна ATT cell с варьирующими units не даёт искусственный нулевой SE. Degenerate influence сохраняет point с ASSUMPTION_FAILED/без CI и p, не [point,point].
Источник: B207; C53-G01, C53-G02. Проверки: TEST-CAU-02-02, TEST-CAU-02-03.

### REQ-CAU-02-03
H0 theta_sel=null_effect, p и confidence interval используют одну centered studentized finite-B plus-one inversion с declared Decimal significance/integer tail rule. Reported closed endpoints не отвергаются, ближайшие внешние nextafter values отвергаются при том же draw corpus; B недостаточный для уровня даёт INPUT_INVALID, не ложную точность.
Источник: B208; C53-G01, C53-G02. Проверки: TEST-CAU-02-03.

### REQ-CAU-02-04
Anticipation применяется совместно к baseline и controls: g−1−a, never-treated либо timing>t+a. Boundary g=t+a исключена из чистых controls; missing baseline/no-control cell сохраняется как precise requested-target gap, без silent shrink target. a=0/not-yet-treated остаются допустимыми.
Источник: B209; C53-G01, C53-G03. Проверки: TEST-CAU-02-04.

### REQ-CAU-02-05
Native declared producer/registry/dispatcher с actual RNG injection, source loading, persisted report/envelope и fresh selected readers сохраняет target/diagnostic reconciliation. Old slot adapter и dedicated request дают одинаковый текущий report на одинаковом effective input; historical FQN lifecycle принадлежит CAU-05. Typed numerical SUCCESS не выдаёт EvalSafety/causal-policy authority.
Источник: B207, B208, B209; C53-G01. Проверки: TEST-CAU-02-05, TEST-CAU-02-06.

### REQ-CAU-02-06
Independent known-DGP smoke выполняется в его конечном predeclared scope, с точными repetitions/seeds и binomial acceptance; результат не называется uniform nominal coverage. Фактический study design должен обосновывать independent panel units, effective sampling unit и pointwise scalar target; shared cross-unit shocks/clusters/simultaneous bands требуют конкретного другого контракта, не самовольного повышения claims текущего метода.
Источник: B207, B208; C53-G02. Проверки: TEST-CAU-02-07.

### REQ-CAU-02-07
Anticipation window, parallel trends и untreated potential outcomes обосновываются для конкретных данных независимо от LLM proposal/pretrend nonrejection/synthetic effect. При неизвестном основании сохранить conditional estimate/diagnostics либо point-only/gap, не выдумать причинную validity и не запретить все полезные candidate calculations.
Источник: B209; C53-G03. Проверки: TEST-CAU-02-04, TEST-CAU-02-07.

## 5. Конкретное техническое решение

Текущая реализация уже делает содержательную замену inference: `_staggered_target_contract` фиксирует target/eligible periods, `_cohort_time_cells` строит eligibility сanticipation, `_selected_participation_influence` суммирует common-control и cohort-share terms, Mammen draws действуют на unit score. Эти owners сохраняются, не вводить отдельный bootstrap service и не увеличивать B вместо проверки закона.

Native acceptance должна проходить registry/dispatcher RNG injection и actual Scientist selected source/report readers. Independent functional derivative и known-DGP suite уже есть; расширять их native lifecycle controls, а не переписывать expected values по implementation. CI/p endpoint inversion — одна процедура; никакого отдельного cosmetic p fix. Если supported native profile воспроизводит численное несоответствие, repair у этого же owner с failing control.

theta_sel — declared новая weighting semantics, не старый target с новым label. Сохранить profile/version/target identity в current reports и не переписывать historical values. Actual-study review ограничен выбранным query: independent-unit assumption, anticipation, parallel trends и intended target. Если нужна assignment-cluster или simultaneous inference, сначала named design/algorithm/acceptance decision; это не неограниченное поручение реализовать все DiD методы. Пока текущий scope не применим, preserve conditional/point-only numerical work с точным ограничением.

### Текущие owners и источники

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py:526–694](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L526-L694)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py:716–765](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L716-L765)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py:808–835](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L808-L835)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py:909–998](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L909-L998)
- [policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py:462–651](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py#L462-L651)
- [policy-engine/tests/unit/foundry/methods/catalog/causal/test_did_selected_participation.py:237–274](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_did_selected_participation.py#L237-L274)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-CAU-02-01 · native independent functional derivative
**NOT_RUN. REQ:** REQ-CAU-02-01.
**Setup:** Existing unequal-cohort fixture sizes2/4 и follow-up4/2; separate weighted empirical functional oracle perturbs each unit mass.
**Действие:** Actual target/influence plus independent finite derivative; alter eligible periods, then diagnostic-only time_treatment.
**Oracle:** theta_sel41/6, old cell-size5.75 distinct and labelled intentional. Every unit derivative matches independently computed functional within explicit finite-difference tolerance from existing test. Target change alters target/binding; diagnostic-window change does not silently alter scalar target but changes diagnostic binding.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_did_selected_participation.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-02-02 · native one-cell/share-term removal control
**NOT_RUN. REQ:** REQ-CAU-02-02.
**Setup:** Treated changes[2,4,6,8], controls0; unequal cohorts for share term; constant effect degenerate case.
**Действие:** Actual inference; independent finite resampling/functional oracle; controlled omission cohort-share term only in test mutant.
**Oracle:** One-cell ATT5/SE≈1.118034 and nonzero interval; resampling one ready cell would have support{5} and fails control. Share-term removal changes SE≈1.327185→.443402 and violates derivative oracle. Degenerate point preserved with no CI/p and declared reason. Не требовать percentile[3,7] от другой inference law.
**Место:** `test_did_selected_participation.py; tests/unit/remediation/test_cau_02.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-02-03 · native RNG/inversion endpoints
**NOT_RUN. REQ:** REQ-CAU-02-02, REQ-CAU-02-03.
**Setup:** Actual injected NumPy RNG recorder delegates choice; B399,n12; confidence/B pairs(.8,99),(.95,399),(.99,999), H0 at point/endpoints/nextafter outside.
**Действие:** Registered estimator consumes RNG, persists report, fresh read verifies counts/decision.
**Oracle:** Draw shapes128×12,128×12,128×12,15×12; shared unit scores not6cell resamples. Same draws define interval/p/tail integer rule; endpoints accepted, outside rejected, H0point p1; too-smallB INPUT_INVALID. Explicit seed/profile preserved, not hardcoded global RNG.
**Место:** `test_did_selected_participation.py; test_cau_02.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-02-04 · native anticipation/domain-gap matrix
**NOT_RUN. REQ:** REQ-CAU-02-04, REQ-CAU-02-07.
**Setup:** g2 cohort effect2, g3 anticipates10 at t2 witha1, never-treated units; a0; g=t+a; missing baseline/no controls/invalid anticipation.
**Действие:** Actual target/cell eligibility and scalar report.
**Oracle:** ATT(2,2)=2 not-3, controls exclude g3; aggregate theta_sel6 distinguished from onecell2. a0 valid. Missing requested cells not silently removed, exact reason and original target retained. Empirical choice ofa remains assumption, not established by passing toy case.
**Место:** `tests/unit/remediation/test_cau_02.py; did.py::_cohort_time_cells`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-02-05 · native registered routes E02-I05-B
**NOT_RUN. REQ:** REQ-CAU-02-05.
**Setup:** Same panel/seed/effective params via old slot staggered=True and dedicated request; actual dispatcher/signature/RNG and CAS/source/report/envelope.
**Действие:** Run both current routes and primary Scientist job; fresh selected consumer.
**Oracle:** Whole current reports equivalent including theta_sel/CI/p/diagnostics/source bindings; useful numeric output reaches consumer, no EvalSafety permission fabricated. No stubs for registration/RNG/job/source/CAS. Historical oldFQN replay separate CAU-05.
**Место:** `run_causal_evaluation.py::_run_primary_causal_job; test_cau_02.py; shared CAU-05 lifecycle suite`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-02-06 · native fresh diagnostic/target tamper
**NOT_RUN. REQ:** REQ-CAU-02-01, REQ-CAU-02-05.
**Setup:** Saved current report; alter diagnostic window only, unit alignment only, eligible periods; rewrite diagnostic payload and recompute producer hash to match forged payload.
**Действие:** Actual selected data/bound-source readers after native CAS load.
**Oracle:** Fresh recomputation rejects changed content despite internally consistent hash; unchanged control accepted. Target and diagnostic identities remain distinct, all relevant source quantities bound. Point/diagnostic claims do not become authority merely from valid serialization.
**Место:** `scientist/nodes/builtins/simulate/run_causal_evaluation.py:462–651`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-02-07 · bounded native DGP and actual-study scope review
**NOT_RUN. REQ:** REQ-CAU-02-06, REQ-CAU-02-07.
**Setup:** Existing160 paired repetitions seeds73000+replication, n400,6periods,2cohorts, AR.6 withinunit,B399, null0/alternative1.5. Separately actual intended panel design with documented assignment/dependence/anticipation.
**Действие:** Run existing predeclared test once in shared numerical slot; record rejection/coverage/power counts. Review actual sampling/identification assumptions before claiming broader inference.
**Oracle:** Use existing binom.interval(.995,160,.05/.95), power>=.95×160; no tuning seeds/threshold after result. Historical6/154/160/154 are prior observations, not mandatory exact counts across changed backend. Cross-unit dependence or simultaneous target outside current scope remains explicit or routes to a specifically justified existing method; real-data causal validity not inferred from DGP/pretrend.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_did_selected_participation.py::test_seeded_serial_panel_null_coverage_and_alternative_binomial_bounds`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_cau_02.py
python -m pytest -q tests/unit/foundry/methods/catalog/causal/test_did_selected_participation.py
# Native shared source/CAS/registry variants согласовать с CAU-05; DGP только один bounded numerical slot.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I05-B**: [канонический контракт LANE-05](../03_Интеграция/LANE-05.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

CAU-02 numerical staggered owner; CAU-01 shared panel/report semantics; CAU-05 final registry/cutover/current-reader integration. did.py один writer. Один native E02-I05-B и один predeclared bounded DGP, не повторять campaign на каждом packet.

- **CAU-01:** Panel metadata/identity and shared report contract, но standard CR0 NaN-label defect не переносится на staggered route без evidence.
- **CAU-05:** Accountable dedicated/old-plan lifecycle и один registry/source/report integration owner.

## 8. Совместимость, миграция и возврат

Current old-slot adapter и dedicated request должны сохранять equivalent current report, но historical old cell-size target не переименовывается theta_sel. Method/target version explicit; unsupported historical replay решение CAU-05. Rollback сохраняет point/diagnostics и ограничивает inference, не возвращает cell resampling/uncentered p или anticipating controls. Нового product diff не требуется, если native repairs проходят.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0: reusable method/target contracts](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Общий panel/unit/target механизм применим к новым совместимым исследованиям; LLM предлагает вопрос/assumptions, не назначает validity.
- [wave5-evidence-substitution-ratification.md — K01/K07–K08](../05_Основания/Архитектура/wave5-evidence-substitution-ratification.md): Численный CI и finite smoke не заменяют causal identification/empirical authority; useful point-only результат сохраняется.

## 10. Конечные решения и сдача

### DEC-CAU-02-DESIGN
**Вопрос:** Применим ли independent-unit pointwise theta_sel к выбранным данным?
**Кто решает:** DiD method/study reviewer.
**Конечное действие/выход:** Зафиксировать target/horizon/cohorts, sampling/assignment clusters/shared shocks, anticipation и identification assumptions. При несовместимости выбрать конкретный existing qualified method либо ограниченный point-only/conditional результат; более широкая inference отдельное bounded extension с oracle.
**До решения:** Current scope large independent units/pointwise scalar; finite-cluster/simultaneous guarantees не заявляются.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
