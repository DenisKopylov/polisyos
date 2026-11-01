# UQP-03 — Однозначная остановка MC и честный conditional result

**LANE-10 · B193, B194 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Остановить работу по объявленному критерию и доставить полезную известную часть, не скрывая непокрытую область.

**Тип:** C115-G01 semantic lifecycle decision; C115-G02 native/source qualification; confirmed runtime R нет.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/UQP-03.md), [исходные карточки](../05_Основания/Аудит/05_Источники/UQP-03_исходные_строки.txt), [трассировка](../04_Трассировка/UQP-03.json).

## 2. Уже работает — сохранить

- Checkpoint-aligned batches и hard budget cap.
- Useful conditional samples, failed/unattempted counts, per-draw hashes и typed outcomes.
- Physical attempts отдельно от logical draws; bounded same-input retry, global error precedence; read-side authority guard.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| B193 | lifecycle | REQ-UQP-03-01, REQ-UQP-03-02 | Boundary repaired; purpose/name stopping требуют явного contract. |
| B194 | qualify | REQ-UQP-03-03, REQ-UQP-03-04, REQ-UQP-03-05 | Conditional ledger/retry repaired; source/native intake проверить. |
| C115-G01 | lifecycle | REQ-UQP-03-01, REQ-UQP-03-02 | Не объявлять отсутствующий MCSE runtime bug; выбрать смысл и compatibility. |
| C115-G02 | qualify | REQ-UQP-03-03, REQ-UQP-03-04, REQ-UQP-03-05 | Generic reader limits не снимать ради green fixture. |

## 4. Нормативные требования результата

**REQ-UQP-03-01.** Configured stopping profile должен однозначно называть full relative output width heuristic либо отдельный functional precision contract; historical half_width name не должен обещать half-width/MCSE.

**REQ-UQP-03-02.** Batches должны достигать checkpoint независимо от batch size, не превышать budget и сохранять unattempted count при early stop.

**REQ-UQP-03-03.** Input-dependent failures должны сохранять успешные draws как conditional result с полной failure/unattempted ledger и non-gating limitation; отсутствующая половина не заменяется нулями.

**REQ-UQP-03-04.** Transient retry должен повторять ту же invocation не более existing двух physical attempts; известная global cause приоритетна и не поглощается per-draw failure.

**REQ-UQP-03-05.** Fresh persisted Science/normative consumer должен проверять exact selected source/draw evidence и сохранять ограничения; complete producer counts сами не дают verified served-source authority.

## 5. Конкретное техническое решение — рекомендуемый способ

- Сначала caller/config census ci_half_width_target. Рекомендуется сохранить existing full-width algorithm как named width_decision_heuristic; legacy alias принимает прежнее numeric meaning с deprecation/explicit metadata, новые поля называют relative_full_width_target. Log converged заменить reached_width_target в этом profile. Не менять формулу на половину под тем же config.
- Если реальный caller требует MC error functional, ограниченное отдельное решение: выбрать mean/quantile/CDF, estimator и valid stopping plan, затем отдельный typed profile/tests; отсутствие такого caller не повод строить universal sequential library.
- _adaptive_batch_size, failure classifier и ledger уже repaired — product diff только по reproduced mismatch. Native bridge использовать существующий; если source verifier отсутствует, предъявить exact missing producer predicate и план расширения, не disable blanket safety caps.

**Существующие code/test owners:**
- [`src/polisyos/foundry/uncertainty/config.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/config.py).
- [`src/polisyos/foundry/uncertainty/monte_carlo.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py).
- [`src/polisyos/foundry/uncertainty/evaluation_failures.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/evaluation_failures.py).
- [`src/polisyos/ir/analytics/uncertainty.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/uncertainty.py).
- [`tests/unit/remediation/test_uqp_03.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_uqp_03.py).
- [`tests/unit/foundry/uncertainty/test_monte_carlo_b194.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/uncertainty/test_monte_carlo_b194.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-UQP-03-01 → REQ-UQP-03-01

**Уровень:** stopping semantics. **Ожидается:** positive + negative + boundary.

**Setup:** Repeated 99/101 distribution n200 и10000; threshold.015; constant100.

**Действие:** Actual _check_adaptive_stop и serialized config/result label.

**Oracle:** Full relative width .02 (atol=1e-12) не проходит .015 при любом n; constant проходит. Label width_heuristic, не precision convergence; output interval не sigma/sqrt(n).

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-UQP-03-02 → REQ-UQP-03-02

**Уровень:** native checkpoint loops. **Ожидается:** positive + negative + boundary.

**Setup:** budget240,min50,checkpoint100,batch50/60; constant output.

**Действие:** Random и real Sobol native routes; boundary60 control.

**Oracle:** Оба stop100, unattempted140; logical draws100. Boundary60 не пропускается batch50; physical nominal call учитывается отдельно.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-UQP-03-03 → REQ-UQP-03-03

**Уровень:** conditional actual result. **Ожидается:** positive + negative + boundary.

**Setup:** x=linspace(-1,1,100), y=x, failure if x<0; missing/nonfinite variants и all-success/all-failed.

**Действие:** Actual result builder, DTO roundtrip.

**Oracle:** 50 useful values, mean50/99 (atol=1e-12), failure indices0..49, output coverage incomplete, gate false. Unconditional mean0 не заявлен; all-failed не valid numeric result.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-UQP-03-04 → REQ-UQP-03-04

**Уровень:** exception graph and retry. **Ожидается:** positive + negative + boundary.

**Setup:** Typed transient at x=−.25; same with PermissionError cause; cyclic cause control.

**Действие:** Actual evaluator classifier/loop; count logical/physical attempts.

**Oracle:** Transient exactly2 identical inputs/hash, one logical draw; global cause one attempt then escapes; cycle unknown, no unbounded retry.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-UQP-03-05 → REQ-UQP-03-03, REQ-UQP-03-05

**Уровень:** E02-I10-B persisted bridge. **Ожидается:** positive + negative + boundary.

**Setup:** Actual native producer→store→fresh Science/normative selected intake, partial and complete controls.

**Действие:** Resolve exact profile/source/draw ledger; tamper source digest/coverage/selected profile.

**Oracle:** Useful conditional carrier accessible with limitations; missing verifier/source remains typed not-established. Existing admitted positive profile if available proves only its scope, not institutional authorization or missingness theorem.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I10-B** из [канонического lane integration-контракта](../03_Интеграция/LANE-10.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: UQP-02. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

UQP-02 shared sampling; UQP-01 invocation; existing Science bridge owner, не новый реестр. Одна native lane wave.

## 8. Совместимость и восстановление

Legacy field сохраняет full-width meaning явно, не silently reinterpret divide2. Historical adaptive/partial results остаются candidate-only; current reader не повышает authority при readback.

## 9. Free-grow и design decisions

- [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md#d25-epistemic-regime-architecture) и [синтез §4](../05_Основания/Исследование/design_direction.md): uncertainty/conditional outputs полезны без незаслуженной authority; новый совместимый law использует общий механизм, не доменную ветку.

## 10. Решения, которые нельзя подменить догадкой

- DEC-UQP-03-01: finite consumer census выбирает width-only profile или дополнительный требуемый functional precision profile. Выход — version/alias table, exact stopping object, tests и отдельная statistical validation scope; precision claim без выбранного плана запрещён.

## 11. Что предъявить и что не является готовностью

Batch/ledger repair qualification отдельно от semantic stopping decision и отдельно от предметной missingness/coverage validation. Native complete fixture gate=true не external permit.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0316` → REQ-UQP-03-01, REQ-UQP-03-02; Не объявлять отсутствующий MCSE runtime bug; выбрать смысл и compatibility.
- `remaining:0317` → REQ-UQP-03-03, REQ-UQP-03-04, REQ-UQP-03-05; Generic reader limits не снимать ради green fixture.
- `preserve:0497` → REQ-UQP-03-02; Checkpoint-aligned batches — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0498` → REQ-UQP-03-03; Useful conditional samples — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0499` → REQ-UQP-03-03; Per-draw typed outcomes/hash — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0500` → REQ-UQP-03-04; Separate physical attempts/logical draws — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0501` → REQ-UQP-03-04; Bounded same-input transient retry — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0502` → REQ-UQP-03-04; Global-error precedence — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0503` → REQ-UQP-03-01, REQ-UQP-03-03; Non-gating incomplete/adaptive result — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0504` → REQ-UQP-03-05; Read-side authority refusal — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
