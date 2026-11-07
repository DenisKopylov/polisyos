# CAL-04 — Identity-safe reuse уже проверенного final snapshot

**LANE-10 · B184, B196, B203 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Не терять полезное последнее обновление и не выполнять повторно тождественный final forward; derivatives остаются связаны с параметрами.

**Тип:** C110-R01 narrow fix; C110-G01 native qualification.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/CAL-04.md), [исходные карточки](../05_Основания/Аудит/05_Источники/CAL-04_исходные_строки.txt), [трассировка](../04_Трассировка/CAL-04.json).

## 2. Уже работает — сохранить

- Last candidate оценивается, overshoot/NaN не вытесняют checked state.
- Final weights/replica сопоставимы; final report проекции берутся из одного snapshot.
- Local Hessian key и derivatives parameter-connected; histories и limited outcomes сохраняются.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| B184 | fix | REQ-CAL-04-01, REQ-CAL-04-05 | Shared forward уже есть; stationary tie теряет его. |
| B196 | qualify | REQ-CAL-04-02, REQ-CAL-04-03 | Last evaluation исправлена; сохранить comparable objective и native boundary. |
| B203 | qualify | REQ-CAL-04-04, REQ-CAL-04-05 | Local key/reuse исправлены; native derivative proof обязателен. |
| C110-R01 | fix | REQ-CAL-04-01, REQ-CAL-04-02 | Переиспользовать по state/objective identity, не по loss. |
| C110-G01 | qualify | REQ-CAL-04-02, REQ-CAL-04-03, REQ-CAL-04-04, REQ-CAL-04-05 | Existing tests частично scan-double; отдельно native route. |

## 4. Нормативные требования результата

**REQ-CAL-04-01.** При точном совпадении выбранного state и objective identity с уже оценённым candidate final projection должна использовать его snapshot даже при scalar-loss tie.

**REQ-CAL-04-02.** Равенство только loss не должно разрешать reuse другого point; tie policy сохраняет прежнее проверенное состояние, а weights/replica changes требуют сопоставимой оценки.

**REQ-CAL-04-03.** Последний produced candidate должен конкурировать только после finite evaluation; при невозможности оценки сохраняются последний checked state и причина ограничения.

**REQ-CAL-04-04.** Final Hessian переиспользуется только при полном local key match; mismatch/None вызывает расчёт, disabled — нет. Производные продолжают зависеть от переданных параметров.

**REQ-CAL-04-05.** Native final report loss/components/traces должны соответствовать выбранному state/weights/replica без redundant identical scans; число calls не интерпретируется как wall-time speedup.

## 5. Конкретное техническое решение — рекомендуемый способ

- В finalization после candidate_selected, если выбран baseline и baseline_forward отсутствует, проверить exact pytree leaves/shape/dtype equality выбранного state и candidate, weights и final replica/objective closure identity. При finite candidate_forward и полном совпадении присвоить его selected_forward; иначе оставить existing fallback. Сравнение np.array_equal для finite host snapshots уместно вне JIT; equality loss недостаточно.
- Не менять strict lower-loss tie policy. Не устранять baseline re-evaluation при final weights/step strategy: она обеспечивает сопоставимость. Shared snapshot применим к projections, не к differentiable objective closure.
- Сохранить _HessianReuseKey fields и local run scope. Не строить cross-run global cache и не удалять Hessians других starts, необходимых selector. Расширить existing test_cal_04, затем один общий native wave.

**Существующие code/test owners:**
- [`src/polisyos/foundry/calibration/calibrator.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py).
- [`src/polisyos/foundry/calibration/hessian.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/hessian.py).
- [`tests/unit/remediation/test_cal_04.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_cal_04.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-CAL-04-01 → REQ-CAL-04-01, REQ-CAL-04-02, REQ-CAL-04-05

**Уровень:** actual finalization regression. **Ожидается:** positive + negative + boundary.

**Setup:** f=(x−1)²; baseline=candidate=0, weights=1, fixed final replica; отдельный baseline0/candidate2 equal-loss control.

**Действие:** Измерить final forward calls и selected point.

**Oracle:** Identical state: один final evaluation используется для report; scalar tie разных точек сохраняет 0 и его trace, не trace2. Removing identity reuse возвращает два identical calls.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CAL-04-02 → REQ-CAL-04-02, REQ-CAL-04-03

**Уровень:** native optimizer/finalization. **Ожидается:** positive + negative + boundary.

**Setup:** x0=0, f=(x−1)²; один SGD-equivalent controlled step 0.5, overshoot4, NaN; fixed/step seed и changed weights.

**Действие:** Actual Calibrator witnesses плюс real optax step; ограничить budget перед final evaluation.

**Oracle:** 0.5/loss0.25 admitted, 4/NaN не вытесняют checked0/loss1; rtol=1e-6 atol=1e-6. При невозможности оценки explicit unchecked-update diagnostic, не ложный final improvement.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CAL-04-03 → REQ-CAL-04-04, REQ-CAL-04-05

**Уровень:** native Hessian identity. **Ожидается:** positive + negative + boundary.

**Setup:** Quartic f=x⁴, points −0.5,0.25,1; selected0.25, затем0.5.

**Действие:** Actual native compute/reuse; mutate каждый key field из existing regression и disabled.

**Oracle:** Три initial Hessians, reuse без четвёртого; mismatch требует четвёртый. H(0.25)=0.75, H(0.5)=3, rtol=1e-5 atol=1e-6. Nonfinite/None key не совпадает. Detached trace mutation должен провалить derivative oracle.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CAL-04-04 → REQ-CAL-04-05

**Уровень:** E02-I10-A native report. **Ожидается:** positive + negative + boundary.

**Setup:** Реальный tiny run_pure_scan mechanism и report caller; no scan replacement.

**Действие:** One/two starts → final report → readback.

**Oracle:** Все projections из одной выбранной identity; intentional extra stochastic replica имеет отдельную роль/seed и не удаляется ради счётчика.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I10-A** из [канонического lane integration-контракта](../03_Интеграция/LANE-10.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: CAL-03. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

Один writer calibrator.py вместе с CAL-02/03/06. Snapshot identity должна использовать ту же final training objective CAL-02; admission CAL-03 выполняется до report.

## 8. Совместимость и восстановление

Public report schema не требуется менять для narrow fix; численные values и tie policy прежние. Historical records не пересчитывать. При сомнительной identity безопасен recompute, не reuse.

## 9. Free-grow и design decisions

- [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md#d25-epistemic-regime-architecture): полезный ограниченный numerical result сохраняется без присвоения empirical authority. [Синтез §4](../05_Основания/Исследование/design_direction.md): общий механизм вместо отдельной ветки на каждый кейс.

## 10. Решения, которые нельзя подменить догадкой

Блокирующих внешних решений не требуется; технический вариант уточняется только при подтверждённой несовместимости названного owner.

## 11. Что предъявить и что не является готовностью

Exact stationary regression и different-point equal-loss control обязательны. Native derivatives/optax/report квалифицировать отдельно от counted scan fixture. Global optimum и процент ускорения не заявляются.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0306` → REQ-CAL-04-01, REQ-CAL-04-02; Переиспользовать по state/objective identity, не по loss.
- `remaining:0307` → REQ-CAL-04-02, REQ-CAL-04-03, REQ-CAL-04-04, REQ-CAL-04-05; Existing tests частично scan-double; отдельно native route.
- `preserve:0469` → REQ-CAL-04-03; Evaluated last candidate — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0470` → REQ-CAL-04-02; Comparable final weights/replica — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0471` → REQ-CAL-04-02, REQ-CAL-04-03; Historical checked state — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0472` → REQ-CAL-04-01, REQ-CAL-04-05; Shared final snapshot — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0473` → REQ-CAL-04-04; Parameter-connected derivative closures — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0474` → REQ-CAL-04-04; Exact local Hessian key — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0475` → REQ-CAL-04-03, REQ-CAL-04-05; Limited results/history preservation — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
