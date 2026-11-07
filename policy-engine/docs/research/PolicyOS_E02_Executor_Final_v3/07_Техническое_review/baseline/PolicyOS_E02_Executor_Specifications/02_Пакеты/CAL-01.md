# CAL-01 — Один temporal/unit смысл до target materialization

**LANE-07 · CP4 · B176, B177, B178 · fix + preserve + native qualification.**

**Практическая цель:** Разрешённые наблюдения достигают calibration consumer с теми же временем, единицами и support; технический порядок IDs или строк не меняет величину.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/CAL-01.md) · [остатки C91](../05_Основания/Аудит/01_Реестры/C91_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/CAL-01_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. C91 не доказывает ложный successful fit: downstream finite guard существует. CP4 original window.

## 2. Сохранить работающий смысл
- Same-period fail closed без ID/trust выбора
- Paired metadata
- Explicit-axis sorting и requested-column refusal
- Dtype promotion/empty support refusal
- Zero/endpoint-fill и masked missing distinction
- LK01 distinct calibration owners

Защищённые различения: LK01. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C91-R01: fix** → REQ-CAL-01-01. Единая axis admission перед temporal kernels.
- **C91-R02: fix** → REQ-CAL-01-02. Paired canonicalization до inferred endpoints.
- **C91-R03: fix** → REQ-CAL-01-03. Whole-series unit/interval contract, не unit guessing.
- **C91-G01: qualify** → REQ-CAL-01-04, REQ-CAL-01-05. Native real consumer и scoped scientific qualification.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-CAL-01-01
Preflight должен один раз проверить конечность source и target time axis и разрешить duplicate policy до interpolation/optimizer. В отсутствие уже объявленного содержательного преобразования duplicate source timestamps отклоняются; positional mode сохраняется только когда действительно выбран.

**TEST-CAL-01-01 — native unit / integration; NOT_RUN.**
- Setup: Linear/ffill, time[0,0,1] с перестановкой первых values; NaN/±Inf source/target axis; missing requested time_column; valid positional.
- Действие: Actual fetch/extract/prepare_targets до optimizer.
- Точный oracle: Duplicate/nonfinite/missing declared column → targeted error до optimizer, не arbitrary latest value/NaN. Valid positional и explicit endpoint-fill работают.
- Doubles/границы: Настоящий preflight/config; native JAX для final path, NumPy-only probe не градиентная приёмка.

### REQ-CAL-01-02
Source axis и связанные values/masks/metadata должны получить один допустимый paired order до inferred grid construction и equal-length shortcut. Перестановка одинаковых time/value pairs не меняет target/report axis или aligned values.

**TEST-CAL-01-02 — native unit / integration; NOT_RUN.**
- Setup: Pairs(0,0),(1,10),(2,20) в двух permutations, steps2 и steps3, no explicit axis; separately explicit[.5,1.5].
- Действие: prepare_targets обеих branches.
- Точный oracle: Inferredsteps2→axis[0,2],values[0,20] в обоихпорядках; equal length ordered paired result; explicit→[5,15]. Metadata IDs/split/masks двигаются вместе, не только time.
- Doubles/границы: Не угадывать calendar units из float; temporal conversion только declared contract.

### REQ-CAL-01-03
Compiler должен проверить совместимость declared unit и interval semantics всей target series, не только same-period multiplicity. Без explicit conversion contract смешение share/percent отклоняется с сохранением исходных observations для repair.

**TEST-CAL-01-03 — native unit / integration; NOT_RUN.**
- Setup: Valid records .5/share январь и 50/percent февраль; sameunit positive; explicit upstream normalized percent→share with lineage.
- Действие: CalibrationTargetBundleCompiler.compile и downstream quality adapter.
- Точный oracle: Mixed declared units не становится [.5,50] weighted target; sameunit represented; explicit converted [.5,.5] accepted с unit/provenance. Переименование IDs или trust не выбирает winner.
- Doubles/границы: Не heuristic metric-name conversion; actual record/compiler/router, не DTOcopy.

### REQ-CAL-01-04
Сохранить same-period ambiguity refusal, paired metadata и различие observed zero/declared fill/no support. Integer/float fill0.5 равнозначен; empty+steps не создаёт measured zero; missing bundle slots имеют нулевую coverage/trust, не fake observations.

**TEST-CAL-01-04 — native unit / integration; NOT_RUN.**
- Setup: Same period two sources/IDs/trust, integer[1]/float[1.0]fill.5, empty steps3, actual zero[0,0], endpoint fill, masked calendar gaps.
- Действие: Actual compiler/raw preflight и support consumer.
- Точный oracle: Ambiguity refusal invariant to IDs; fill[1,.5,.5], empty refusal, observed zeros kept, endpoint[1,2,2] kept; missing mask not valid measure.
- Doubles/границы: Не auto mean/maxtrust; positive fill и zero обязательны.

### REQ-CAL-01-05
Один native observation→target→optimizer/report witness должен доказать использование исправленных axes/units/masks реальным consumer; scientific adequacy остаётся отдельной qualification конкретных inputs. LK01 разделяет Foundry/predictive/DDM calibration.

**TEST-CAL-01-05 — native unit / integration; NOT_RUN.**
- Setup: Supported JAX, tiny identifiable model с valid units/time, selected source inputs и persisted report; no-support negative.
- Действие: Совместный CAL lane10 consumer с CAL-02 scale/train mask contract; fresh report read.
- Точный oracle: Actual finite fit/gradient/report связан с исправленными inputs; no-support не goodfit. Никаких fake JAX/NumPy substitution; candidate fixture не эмпирический сертификат.
- Doubles/границы: Контролируемая synthetic model допустима для mechanism; real JAX optimizer/report/CAS требуется для claimed boundary.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

`src/polisyos/foundry/calibration/preflight.py::prepare_targets` сейчас строит inferred linspace(time[0],time[-1]) до `_resample_series` sort; equal-length branch возвращает values без sort. Вынести один локальный normalize/admit source-axis step перед обеими branches: validate dimensionality/length/finite; stable paired sort; reject duplicates без explicit upstream policy; канонические endpoints используются для inferred grid. `_resample_series` потребляет уже admitted pairs, сохраняя defensive checks для прямых callers. Explicit target axis проверяется finite и совместима с объявленной coordinate semantics; не сортировать user-requested target order скрыто. Positional mode без declared time-column остаётся доступен. Endpoint-fill не выключать.

`src/polisyos/foundry/calibration/measurement.py::CalibrationTargetBundleCompiler.compile` после grouping до arrays проверяет unit/interval compatibility всей selected series. Выбрать минимальный безопасный контракт: одинаковая canonical declared unit; conversion только existing upstream owner с исходными IDs, формулой/версией и new derived values. Не разделять единицы молча на новые targets и не брать unit первого record. Сохранить unit declaration в target/report binding по existing extensible contract; если field отсутствует, additive typed declaration согласовать с IR owner (`src/polisyos/ir/analytics/calibration.py`) и CAL-02, не вставлять неподтверждённый default.

Same-period `_select_observation_for_period` уже правильно отказывает. `_align_by_length` dtype promotion/empty guard уже исправлены — preserve. Native integration отнести к общей calibration wave, а не запускать оптимизатор отдельно на каждый локальный тест. Соседний loss finite guard сохраняется, но поздний inf loss не заменяет ранний temporal mismatch.

## 6. Общая интеграция и порядок
**E02-I07-C**, [канонический LANE-07](../03_Интеграция/LANE-07.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- CAL-02/CAL-06 shared preflight/measurement write mutex; one writer
- E02-I07-C local source→target; shared lane10 optimizer/report evidence without duplicate infrastructure

Owners/callers: `src/polisyos/foundry/calibration/preflight.py::prepare_targets`; `src/polisyos/foundry/calibration/preflight.py::_resample_series`; `src/polisyos/foundry/calibration/measurement.py::CalibrationTargetBundleCompiler.compile`; `src/polisyos/ir/analytics/calibration.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Historical fitted reports/observations immutable. Новый unit/axis policy — intentional semantic delta с input/version binding; старые results остаются qualified. Rollback affected ambiguous input refused, не automatic mean/IDwinner. Literal cp окно этого пакета CP4, несмотря на lane07: coordination с CAL02/06, не новая очередь runtime.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Не требовать универсального интерпретатора физических единиц. Explicit typed transform и конечный domain contract достаточны для полезной работы; новая семантика может требовать общего кода, но не case-by-case branches по metric name.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/remediation/test_cal_01.py`, `tests/unit/foundry/calibration/test_preflight.py`, `tests/unit/foundry/calibration/test_measurement.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
