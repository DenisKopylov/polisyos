# CAL-03 — Одинаковая finite admission для одного и нескольких стартов

**LANE-10 · B183, B195 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Доставить потребителю проверенный конечный fit с честной причиной выбора, сохранив diagnostics каждого старта.

**Тип:** C109-R01 fix; C109-G01 native qualification.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/CAL-03.md), [исходные карточки](../05_Основания/Аудит/05_Источники/CAL-03_исходные_строки.txt), [трассировка](../04_Трассировка/CAL-03.json).

## 2. Уже работает — сохранить

- Fresh per-start span factory и независимый no-op context; attributes не мутируют.
- Finite loss admission, missing/known-bad Hessian distinction, explicit fallback, deterministic ties и histories.
- Raw Hessian condition не заменять repaired condition; best_identifiability — отдельная ranking policy, не best_loss threshold.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| B183 | qualify | REQ-CAL-03-03, REQ-CAL-03-04 | Factory исправлена; подтвердить actual SDK/lifecycle на двух native starts. |
| B195 | fix | REQ-CAL-03-01, REQ-CAL-03-02, REQ-CAL-03-04 | Selector исправлен, single runtime caller ещё обходит admission. |
| C109-R01 | fix | REQ-CAL-03-01 | Убрать len>1 admission bypass, не уничтожать ограниченный finite результат. |
| C109-G01 | qualify | REQ-CAL-03-03, REQ-CAL-03-04 | Stdlib context и NumPy fallback не заменяют native optimizer/OTel/Hessian. |

## 4. Нормативные требования результата

**REQ-CAL-03-01.** Один и несколько runtime runs должны проходить select_best finite-loss admission до final projection; при отсутствии finite run обычный успешный report не создаётся.

**REQ-CAL-03-02.** Finite, но ill-conditioned кандидат должен оставаться доступным как ограниченный результат с точным fallback reason; missing Hessian не равен inf/NaN/negative/malformed condition.

**REQ-CAL-03-03.** Каждый restart должен получить свежий context и start index; telemetry и no-op routes сохраняют primary exception, истории и фактический lifecycle status.

**REQ-CAL-03-04.** Native two-start fit должен передать выбранные state/weights/history/Hessian и reason из одного runtime record; native raw degeneracy должна достигнуть реального selector.

## 5. Конкретное техническое решение — рекомендуемый способ

- В calibrator.py вынести построение SingleRunResult и вызов select_best из len(multi_start_runs)>1, применять и к одному run; общий selected_run extraction оставить одним блоком. Нулевой список и no-finite ValueError оформить существующим failure/lifecycle путём, сохраняя diagnostics и histories; не вводить второй selector.
- Не менять _condition_status, _select_best_loss и _select_best_identifiability ради single fix. Не менять raw Hessian calculation: repaired matrix и raw condition решают разные задачи.
- Существующий _calibration_span_context уже фабрика; менять только при реальном native несоответствии. Расширить test_cal_03/test_multi_start и calibration_lifecycle вместо новой telemetry системы.

**Существующие code/test owners:**
- [`src/polisyos/foundry/calibration/calibrator.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py).
- [`src/polisyos/foundry/calibration/multi_start.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/multi_start.py).
- [`src/polisyos/foundry/calibration/hessian.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/hessian.py).
- [`tests/unit/remediation/test_cal_03.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_cal_03.py).
- [`tests/unit/foundry/calibration/test_multi_start.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/calibration/test_multi_start.py).
- [`tests/unit/foundry/calibration/test_calibration_lifecycle.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/calibration/test_calibration_lifecycle.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-CAL-03-01 → REQ-CAL-03-01, REQ-CAL-03-02

**Уровень:** actual Calibrator selection + selector table. **Ожидается:** positive + negative + boundary.

**Setup:** Single inf/NaN/malformed loss; finite 0.5; пары в обоих порядках.

**Действие:** Вызвать runtime orchestration до projection и actual selector для обеих policies.

**Oracle:** No-finite: явный failure с сохранёнными diagnostics, final report не успешен; finite выбирается независимо от положения NaN. All-limited finite возвращается с fallback; ties детерминированы.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CAL-03-02 → REQ-CAL-03-02, REQ-CAL-03-04

**Уровень:** native Hessian → selection. **Ожидается:** positive + negative + boundary.

**Setup:** f(x)=0 и f(x)=x² при x=0; threshold=1e8; loss 0.1/0.5 соответственно.

**Действие:** Вычислить настоящие JAX Hessians и передать в select_best.

**Oracle:** Raw eigenvalues 0/2 (atol=1e-6), condition inf/1; best_loss выбирает finite acceptable 0.5. Damping не превращает inf в missing; missing сохраняет loss-only режим.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CAL-03-03 → REQ-CAL-03-03

**Уровень:** real OTel lifecycle. **Ожидается:** positive + negative + boundary.

**Setup:** In-memory OTel SDK exporter, два starts; затем no-op; controlled exporter exception отдельно от model failure.

**Действие:** Запустить оба режима и проверить emitted spans/exception chain.

**Oracle:** Два distinct child spans с indices 0/1, корректный end/status, общий attributes не изменён. Primary model failure не заменён telemetry failure; существующая объявленная best-effort policy соблюдена.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CAL-03-04 → REQ-CAL-03-01, REQ-CAL-03-03, REQ-CAL-03-04

**Уровень:** E02-I10-A native integration. **Ожидается:** positive + negative + boundary.

**Setup:** Tiny actual parameter-connected model, JAX/optax, два starts и single control.

**Действие:** Run → actual final report → consumer; controlled nonfinite initial route.

**Oracle:** Selected params/loss/weights/reason принадлежат одной записи; finite useful report доступен, invalid single не доходит обычным success. Нельзя подменять optimizer/scan для native claim.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I10-A** из [канонического lane integration-контракта](../03_Интеграция/LANE-10.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: CAL-02. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

CAL-02/04/06 сериализуют запись calibrator.py. CP4 — согласованная calibration acceptance, не полный CI gate. CAL-04 selected snapshot/Hessian record не потерять при общем extraction.

## 8. Совместимость и восстановление

Normal finite single_run reason сохраняется; nonfinite formerly-selected result теперь явный failure, historical reports не переписываются. Finite limited results остаются читаемыми; rollback не должен вновь разрешать invalid ordinary success.

## 9. Free-grow и design decisions

- [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md#d25-epistemic-regime-architecture): полезный ограниченный numerical result сохраняется без присвоения empirical authority. [Синтез §4](../05_Основания/Исследование/design_direction.md): общий механизм вместо отдельной ветки на каждый кейс.

## 10. Решения, которые нельзя подменить догадкой

Блокирующих внешних решений не требуется; технический вариант уточняется только при подтверждённой несовместимости названного owner.

## 11. Что предъявить и что не является готовностью

Предъявить regression на actual single caller, two-start native OTel и raw-Hessian consumer. Табличный test_global_minimum не доказывает глобальный минимум или scientific identifiability.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0304` → REQ-CAL-03-01; Убрать len>1 admission bypass, не уничтожать ограниченный finite результат.
- `remaining:0305` → REQ-CAL-03-03, REQ-CAL-03-04; Stdlib context и NumPy fallback не заменяют native optimizer/OTel/Hessian.
- `preserve:0462` → REQ-CAL-03-03; Fresh per-start span context — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0463` → REQ-CAL-03-03; Start identity и no-op path — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0464` → REQ-CAL-03-01; Finite loss admission в selector — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0465` → REQ-CAL-03-02; Missing/known-bad condition distinction — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0466` → REQ-CAL-03-02; Explicit limited-result fallback — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0467` → REQ-CAL-03-02, REQ-CAL-03-04; Histories и deterministic ties — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0468` → REQ-CAL-03-02, REQ-CAL-03-04; Raw Hessian condition — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
