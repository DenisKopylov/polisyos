# CAL-06 — Явный частичный uncertainty scope без потери tied covariance

**LANE-10 · B197, B198 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Сохранить uncertainty оценённых A/B при наличии неоценённого C, не выдавая отсутствующую uncertainty C за ноль.

**Тип:** C111-R01 scoped-contract fix; C111-G01 persistence/propagation qualification.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/CAL-06.md), [исходные карточки](../05_Основания/Аудит/05_Источники/CAL-06_исходные_строки.txt), [трассировка](../04_Трассировка/CAL-06.json).

## 2. Уже работает — сохранить

- Explicit coordinate order/matrix, JΣJᵀ, cross-terms и singular null space.
- Bounds conflict отказ; unknown STD не выдумывается; v1 legacy и v2 explicit projection различены.
- Typed conditional mean/std имеет приоритет перед metadata/display; heuristic и gate_eligible=false сохраняются.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| B197 | fix | REQ-CAL-06-01, REQ-CAL-06-02, REQ-CAL-06-03, REQ-CAL-06-05 | Основная projection есть; all-handles coverage теряет active subset. |
| B198 | qualify | REQ-CAL-06-04, REQ-CAL-06-05 | Typed carrier repair сохранить и проверить downstream. |
| C111-R01 | fix | REQ-CAL-06-01, REQ-CAL-06-02 | Добавить explicit scope, не снять coverage validator. |
| C111-G01 | qualify | REQ-CAL-06-03, REQ-CAL-06-04, REQ-CAL-06-05 | DTO JSON и joint builder не actual CAS/full propagation. |

## 4. Нормативные требования результата

**REQ-CAL-06-01.** Report должен явно отделять множество оценённых uncertainty fields от всех сохранённых point values; полная валидная projection этого scope сохраняется при unrelated unassigned handle.

**REQ-CAL-06-02.** Projection должна проверять exact field/coordinate order, coverage выбранного scope, matrix shape/finite и duplicate handles; неподдерживаемая или неполная projection не угадывается по имени.

**REQ-CAL-06-03.** Tied fields должны получать JΣJᵀ с cross-covariance и singular dependence; неизвестный C не получает fake zero variance или самостоятельный Normal.

**REQ-CAL-06-04.** Изменение только display level/metadata не должно менять typed conditional sigma или повышать heuristic/gating status; отсутствие подходящего law остаётся явно ограниченным.

**REQ-CAL-06-05.** Новый scoped report должен пройти actual persist/load и существующий propagation consumer, сохранив scope, basis, law и ограничения; старые v1/v2 records остаются читаемыми по своим contracts.

## 5. Конкретное техническое решение — рекомендуемый способ

- В calibrator projection producer строить field_order только из реально назначенных group handles, сохраняя calibrated_params для всех point values. Добавить явный uncertainty field scope в canonical CalibrationReport contract; existing complete означает complete within declared scope, а не безусловное равенство всем point values. Предпочтителен additive typed field с explicit version/profile; нельзя молча переопределить смысл старого complete.
- Validator требует scope subset calibrated_params, exact projection field coverage и exact coordinate basis uncertainties.params, отсутствие duplicate handles. Unassigned fields перечислить как point-only limitation. Adapter уже перебирает projection.field_order: обновить scope admission, не угадывать имена.
- Сохранить _projected_field_covariance и typed ParametricFitCarrier/extract_std. UQP-02 владеет singular joint sampling; здесь проверить его consumer, не создавать второй sampler. Миграцию schema выбрать по фактическим readers в ограниченном DEC.

- Canonical schema owner — foundry/calibration/report.py::CalibrationReport.validate_coordinate_projection_contract; текущие 2.0/2.1 требуют coverage всех calibrated_params, поэтому partial scope требует explicit version/profile migration, не только изменения producer loop.

**Существующие code/test owners:**
- [`src/polisyos/foundry/calibration/calibrator.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py).
- [`src/polisyos/foundry/calibration/uncertainty_adapter.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py).
- [`src/polisyos/foundry/uncertainty/covariance.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/covariance.py).
- [`tests/unit/remediation/test_cal_06.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_cal_06.py).
- [`tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py).

- `src/polisyos/foundry/calibration/report.py` — CalibrationReport.validate_coordinate_projection_contract и CalibrationCoordinateProjection; actual schema versions 1.0/2.0/2.1.

## 6. Локальные проверки — все NOT_RUN

### TEST-CAL-06-01 → REQ-CAL-06-01, REQ-CAL-06-02, REQ-CAL-06-03

**Уровень:** producer→DTO→adapter. **Ожидается:** positive + negative + boundary.

**Setup:** A.rate/B.rate tied shared_rate=.25, group variance .0025, unrelated unselected C.rate=.7.

**Действие:** Actual resolver/projection/report/adapter; rename group; untied control.

**Oracle:** A/B envelopes 2, projected matrix все элементы .0025 (rtol=1e-6 atol=1e-9), rank1; C remains point-only/unknown uncertainty. Removing C не меняет A/B. No string-name inference.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CAL-06-02 → REQ-CAL-06-02, REQ-CAL-06-05

**Уровень:** contract migration/boundary. **Ожидается:** positive + negative + boundary.

**Setup:** Old v1/v2 report; new scoped record; duplicate/missing scope field, reordered coordinates, incompatible bounds.

**Действие:** Parse and consume each actual DTO.

**Oracle:** Legacy прежние rules; new exact basis accepted; ambiguity/mismatch адресный отказ. Не допускается declared complete coverage, если часть объявленного scope отсутствует.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CAL-06-03 → REQ-CAL-06-04

**Уровень:** typed-law roundtrip. **Ожидается:** positive + negative + boundary.

**Setup:** Typed Normal mean=.25 std=.05; display .8/.95; tampered metadata std=9; missing typed std.

**Действие:** Adapter → JSON → extract_std; legacy arbitrary band отдельно.

**Oracle:** Sigma=.05 для обоих levels с atol=1e-12; display widths различны; metadata не overrides typed law; incomplete typed carrier отказывает. Heuristic/non-gating flags неизменны, произвольная band не объявлена Normal.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CAL-06-04 → REQ-CAL-06-01, REQ-CAL-06-03, REQ-CAL-06-04, REQ-CAL-06-05

**Уровень:** E02-I10-A/B actual persistence/MC. **Ожидается:** positive + negative + boundary.

**Setup:** Native calibration report из selected tied params; actual configured tmp artifact store и fresh consumer; empirical drawn path UQP-02.

**Действие:** Persist/load → envelope→joint law→propagation; output f=A−B.

**Oracle:** Точный shared law даёт A=B и f=0 на каждом draw (float64 atol=1e-12, float32 atol=1e-6), C не включён в joint без law. Scope/flags сохраняются; missing artifact не заменяется fixture authority.

**Seams:** Synthetic model/observations допустимы; actual DTO/store/resolver/joint consumer обязательны. Фиксированный seed допустим, hardcoded draws вместо проверяемого joint sampler — нет.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I10-A, E02-I10-B** из [канонического lane integration-контракта](../03_Интеграция/LANE-10.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: CAL-04, UQP-02. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

CAL-04 upstream state; UQP-02 joint law dependency — не ждать целый lane. Согласовать canonical report schema owner с CAL-01; один writer calibrator.py.

## 8. Совместимость и восстановление

До изменения schema перечислить actual readers/writers и выбрать additive version/profile; old v2 complete semantics не изменять задним числом. Old records не получают fabricated scope. При unsupported reader выдать named limited result, сохранить point values и covariance.

## 9. Free-grow и design decisions

- [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md#d25-epistemic-regime-architecture): полезный ограниченный numerical result сохраняется без присвоения empirical authority. [Синтез §4](../05_Основания/Исследование/design_direction.md): общий механизм вместо отдельной ветки на каждый кейс.
- [Stage-0 §4.3](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md#43-k06--fail-closed-binds-the-protected-action-not-the-computation): неизвестность C ограничивает claim о C, не валидную A/B работу.

## 10. Решения, которые нельзя подменить догадкой

- DEC-CAL-06-01: finite census CalibrationReport readers/schema validators, затем решение additive field with new profile либо schema version. Критерии: не менять legacy complete meaning, сохранять exact scope, fresh reader rejection для неизвестного profile; выход — migration table и roundtrip fixtures.

## 11. Что предъявить и что не является готовностью

Ремонт принят при A/B positive scope и explicit C unknown, не при снятии guards. Native CAS/MC evidence отдельно от DTO-only. Conditional Hessian approximation не posterior/empirical authority.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0318` → REQ-CAL-06-01, REQ-CAL-06-02; Добавить explicit scope, не снять coverage validator.
- `remaining:0319` → REQ-CAL-06-03, REQ-CAL-06-04, REQ-CAL-06-05; DTO JSON и joint builder не actual CAS/full propagation.
- `preserve:0505` → REQ-CAL-06-01, REQ-CAL-06-02; Explicit coordinate projection — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0506` → REQ-CAL-06-03; Covariance cross-terms и singular rank — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0507` → REQ-CAL-06-02; Bounds refusal — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0508` → REQ-CAL-06-04; Typed conditional mean/std — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0509` → REQ-CAL-06-04, REQ-CAL-06-05; Heuristic/non-gating semantics — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0510` → REQ-CAL-06-03, REQ-CAL-06-04; Unknown STD refusal — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0511` → REQ-CAL-06-02, REQ-CAL-06-05; V1/V2 projection distinction — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
