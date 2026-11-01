# UQP-01 — Квалифицированная effective invocation и source-bound response

**LANE-10 · B186, B189, B190, B191 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Номинальный, delta и MC результаты относятся к одной фактической функции и одинаковым fixed inputs.

**Тип:** preserve/qualify-only: C113-G01/G02; код менять только при воспроизведённом contract mismatch.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/UQP-01.md), [исходные карточки](../05_Основания/Аудит/05_Источники/UQP-01_исходные_строки.txt), [трассировка](../04_Трассировка/UQP-01.json).

## 2. Уже работает — сохранить

- Полное fixed+varying binding до evaluator; intentional default отличается от explicit0.
- Никаких guessed sensitivity; additive zero-baseline effect, partial known outputs и candidate-only mapping.
- Missing не zero; настоящий nondifferentiable fallback сохраняется.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| B186 | qualify | REQ-UQP-01-01, REQ-UQP-01-05 | Binding repaired; native backend precision scope уточнить. |
| B189 | qualify | REQ-UQP-01-02, REQ-UQP-01-05 | NoFloat control не JAX. |
| B190 | qualify | REQ-UQP-01-02, REQ-UQP-01-04 | Partial/source reconciliation есть; не требовать универсального model inventor. |
| B191 | qualify | REQ-UQP-01-03 | Missing typed repaired; native result builder проверить. |
| C113-G01 | qualify | REQ-UQP-01-01, REQ-UQP-01-02, REQ-UQP-01-03, REQ-UQP-01-04 | Actual native source→dispatch→persist path вместо numerical shim. |
| C113-G02 | qualify | REQ-UQP-01-05 | Зафиксирована precision boundary, не доказанный runtime defect. |

## 4. Нормативные требования результата

**REQ-UQP-01-01.** Nominal/probe/delta/random/QMC должны использовать одну effective invocation с fixed inputs и только объявленными varying coordinates.

**REQ-UQP-01-02.** Actual affine/source response должен проходить eager/JIT/Jacobian без Python cast tracer; unknown/partial map остаётся ограниченной, настоящий zero-baseline effect не исчезает.

**REQ-UQP-01-03.** Missing output должен иметь адресный UNKNOWN/non-gating outcome, а настоящая constant0 — zero result; структурный binding failure не повторяется сотнями sampled calls.

**REQ-UQP-01-04.** Source-bound response должен сохранить exact execute/calibration refs, digests, centers, units и roster до persisted consumer; caller hypothesis не становится подтверждённой картой.

**REQ-UQP-01-05.** Delta probe/execution должны объявлять согласованный numeric dtype/domain; representability boundary не скрывается несогласованными nominal и projected meanings.

## 5. Конкретное техническое решение — рекомендуемый способ

- Существующие _validate_effective_inputs и full nominal merge уже корректны: сначала native tests, не переписывать. Расширить test_uqp_01/test_delta/node tests.
- Проверить actual source-bound branch 1010–1280 и additive projection 1484–1562; не открыть fast delta на guessed map. При обнаруженном mismatch менять соответствующий owner, сохраняя intentional defaults и partial semantics.
- C113-G02: конечная таблица dtype по dispatcher probe/delta/nominal/model inputs. Предпочтительна единая existing numeric policy/coercion boundary, не global JAX x64 switch. Решение фиксирует accepted domain и explicit lossy conversion; не обещать arbitrary decimal precision.

**Существующие code/test owners:**
- [`src/polisyos/foundry/uncertainty/delta.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/delta.py).
- [`src/polisyos/foundry/uncertainty/dispatcher.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/dispatcher.py).
- [`src/polisyos/foundry/uncertainty/protocol.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/protocol.py).
- [`src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py).
- [`tests/unit/remediation/test_uqp_01.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_uqp_01.py).
- [`tests/unit/foundry/uncertainty/test_delta.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/uncertainty/test_delta.py).
- [`tests/unit/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-UQP-01-01 → REQ-UQP-01-01, REQ-UQP-01-03

**Уровень:** native complete call. **Ожидается:** positive + negative + boundary.

**Setup:** y=x*scale, x10 sigma1, fixed scale2; required missing scale; default7 и explicit0.

**Действие:** Nominal/probe/delta/MC с call recorder, реальные numerical engines.

**Oracle:** Point20, delta variance4 (rtol=1e-5 atol=1e-6); все calls scale2. Required missing отвергается до evaluation, default7 только при omission, explicit0 не заменяется default.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-UQP-01-02 → REQ-UQP-01-02

**Уровень:** JAX eager/JIT. **Ожидается:** positive + negative + boundary.

**Setup:** Explicit affine y=x−2 at x2, sigma1; partial z unmapped.

**Действие:** jax.jacfwd/jit и dispatcher; nondifferentiable control отдельно.

**Oracle:** Jacobian1, point0 variance1 (atol=1e-6); delta chosen без MC draws. z unresolved/non-gating; реальные nondifferentiable inputs допускают declared MC fallback, не blanket refusal.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-UQP-01-03 → REQ-UQP-01-03

**Уровень:** result boundary. **Ожидается:** positive + negative + boundary.

**Setup:** Function returns actual0, missing requested key; all-missing и mixed.

**Действие:** Actual delta/MC result builders и serialize/read.

**Oracle:** Actual0 остаётся0, missing UNKNOWN, partial present preserved; all missing не successful numeric evaluation; no fabricated [0,0].

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-UQP-01-04 → REQ-UQP-01-02, REQ-UQP-01-04

**Уровень:** E02-I10-B source route. **Ожидается:** positive + negative + boundary.

**Setup:** Existing node source-bound execute-response refs, actual tmp store, small parameter-connected model.

**Действие:** Resolve→dispatch→persist/read; tamper center/unit/digest/roster.

**Oracle:** Matched source reaches consumer; mismatches fail closed только affected claim. Caller-only remains candidate and useful. Recomputed fixture Jacobian без source admission недостаточен.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-UQP-01-05 → REQ-UQP-01-05

**Уровень:** numeric profile qualification. **Ожидается:** positive + negative + boundary.

**Setup:** x=100000001, y=x−1e8, затем representable x=100000000; current float32 and only supported configured x64 profile.

**Действие:** Capture actual backend/dtype, nominal input coercion и output; compare exact representable inputs.

**Oracle:** Float32 coerces first x to1e8, result0; Python uncoerced1 не выдавать за ту же nominal evaluation. Выбранный профиль либо uses consistent coerced nominal with explicit limitation, либо rejects out-of-domain requested precision; x64 если реально supported даёт1 (atol=1e-9).

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I10-B** из [канонического lane integration-контракта](../03_Интеграция/LANE-10.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: нет. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

UQP-02/03 общий dispatcher/MC writer; численный job один, shared fixture. Source response contract не дублировать у каждого backend.

## 8. Совместимость и восстановление

No forced product diff для repaired paths. Numeric profile change versioned/declared, historical results retain dtype and limitations; не задним числом повышать precision.

## 9. Free-grow и design decisions

- [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md#d25-epistemic-regime-architecture) и [синтез §4](../05_Основания/Исследование/design_direction.md): uncertainty/conditional outputs полезны без незаслуженной authority; новый совместимый law использует общий механизм, не доменную ветку.

## 10. Решения, которые нельзя подменить догадкой

- DEC-UQP-01-01: по фактическому model/backend contract выбрать consistent coercion+declared domain либо stricter requested-precision refusal. Выход — dtype table, acceptance thresholds и compatibility note; rounding само по себе не defect.

## 11. Что предъявить и что не является готовностью

Native JAX и actual node/CAS evidence, не custom finite-difference shim. Repair acceptance не scientific validity response model.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0311` → REQ-UQP-01-01, REQ-UQP-01-02, REQ-UQP-01-03, REQ-UQP-01-04; Actual native source→dispatch→persist path вместо numerical shim.
- `remaining:0312` → REQ-UQP-01-05; Зафиксирована precision boundary, не доказанный runtime defect.
- `preserve:0481` → REQ-UQP-01-01; Complete effective invocation — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0482` → REQ-UQP-01-01, REQ-UQP-01-03; Required binding before evaluation — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0483` → REQ-UQP-01-01; Intentional defaults vs explicit zero — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0484` → REQ-UQP-01-02, REQ-UQP-01-04; No invented sensitivity — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0485` → REQ-UQP-01-02; Additive zero-baseline effect — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0486` → REQ-UQP-01-02, REQ-UQP-01-04; Candidate-only mapping — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0487` → REQ-UQP-01-03; Typed missing output — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0488` → REQ-UQP-01-02; Native nondifferentiable fallback — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
