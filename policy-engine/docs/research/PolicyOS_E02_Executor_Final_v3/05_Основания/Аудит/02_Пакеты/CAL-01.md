# CAL-01 — наблюдения, временная ось и отсутствие опоры

## 1. Решение

**Ограниченно оценён, не закрыт.** Исправлены исходные same-period overwrite по ID, отсутствие запрошенного time column, сортировка пар при явной оси, truncation дробного fill и фиктивные нули из пустого ряда. Сохранены реальные нули, разрешённое endpoint-fill и совместная привязка metadata. Остались три подтверждённые границы: **неразрешённые duplicate/nonfinite time; inferred grid из несортированных endpoints; разные declared units между периодами одного target.**

Свежий результат **5 MATCH; 19 unchanged existing bodies / 20 cases PASS**. Это actual compiler с поддерживаемым NumPy fallback и actual NumPy temporal kernels, а не native JAX optimizer. Два ранних harness setup failures сохранены отдельно, затем исправлена только внешняя диагностическая оснастка.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Карточка](../05_Источники/CAL-01_исходные_строки.txt) · [Источники](../05_Источники/C91_источники.json).

## 2. Матрица исходных IDs

| ID | Сохранённое и подтверждённое | Остаток |
|---|---|---|
| B176 | Любая multiplicity target–period отказывает до выбора по ID/source/trust; records разных дат сохраняют paired values/masks/IDs | C91-R03: cross-period units; G01 native chain |
| B177 | Length mismatch и missing requested time_column отказывают; actual paired stable sort даёт [5,15] на explicit grid | C91-R01 duplicate/nonfinite; R02 inferred grid |
| B178 | Integer/float fill0.5 совпадает; empty+explicit horizon не становится нулевой опорой | G01 полный fit/report; наблюдаемый ноль и endpoint-fill сохраняются |
| LK01 | Predictive calibration, Foundry parameter calibration и DDM detector calibration имеют разные owners | Не объединять по совпадению имени |

## 3. Producer → consumer

`ObservationRecord` проверяет finite values, interval, scope и proxy declaration; `ObservationPanel` — family/time grain. Compiler группирует family/metric/scope/locator, затем period; `_select_observation_for_period` требует ровно одну строку. Это сознательный fail-closed repair, а не потерянная возможность автоматически выбирать максимальный trust. Ambiguous records должны разрешаться существующим upstream owner с lineage (`S02:193–226`, `S04`).

Compiler строит общий отсортированный calendar и одновременно заполняет value, trust, coverage, censor, lag, shock, schema, observation ID и split. Для отсутствующих точек оставляет value0, но **coverage0/trust0 и missing ID**: это masked slot, не утверждение наблюдаемого нуля. Настоящий registry/router и splitter исполнены; их default policies не получили новую scientific authority (`S02:248–366`, `S06–S07`).

Raw branch получает callback/UDF result через `fetch_targets` → actual `extract_fabric_series` → `resolve_steps` → `prepare_targets`. Выходные arrays/time axes передаются Calibrator; measurement bundle идёт отдельной веткой, без повторной raw interpolation. Там shape/coverage/training support проверяются отдельно. Downstream pointwise loss имеет finite guard и возвращает inf при nonfinite targets; находка R01 **не означает успешный ложный fit** (`S01`, `S08:2474–2569`, `S09:26–55`).

## 4. Свежие проверки

1. **P01:** все existing CAL-01 tests и8 preflight class tests, плюс actual compiler missing-mask test:19 bodies/20 cases PASS. Переименование IDs, конфликт источников, разные trust/units одной даты не выбирают победителя; paired metadata после reorder сохранены. Missing time/length mismatch/empty targets отказывают; fractional fill и ordinary endpoint-fill работают.
2. **P02 / R01:** actual config и raw values `[10,20,30]`, time `[0,0,1]`, target grid `[0,1]`. И linear, и ffill дают `[20,30]`; перестановка первых двух равнодатных измерений даёт `[10,30]`. Никакой source/version/aggregation policy не объявлена. Nonfinite source axis и отдельно actual config.time_axis с NaN дают target `[10,nan]`, не ранний temporal mismatch.
3. **P03 / R02:** те же пары `(0,0),(1,10),(2,20)` при steps2 без explicit axis дают grid `[0,2]` и values `[0,20]`. Перестановка `(2,20),(0,0),(1,10)` даёт grid `[2,1]` и `[20,10]`: grid уже построен до внутренней сортировки. Positive control с explicit `[.5,1.5]` даёт `[5,15]` для обеих перестановок.
4. **P04 / R03:** настоящие validated records `.5/share` в январе2023 и `50/percent` в феврале2023 объединены в один target `[.5,50]`. Target spec не хранит unit; actual quality adapter даёт обеим точкам положительный вес≈0.595. IDs сохранены. Не заявляется, что правильный upstream unit normalizer допускает такой вход или что полный fit запущен.
5. **P05:** declared callback возвращает actual pandas table с несортированными time/value pairs; настоящие fetch/extract/prepare дают `[5,15]`. Missing requested column отказывает; реально наблюдённые `[0,0]` сохраняются; empty horizon input отказывает. Это callback producer, не network Fabric service.

## 5. Что сохранить и что осталось

**Сохранить:** явный отказ при same-period ambiguity без автоматического mean/max-trust, paired metadata, requested-column validation, lengths, dtype promotion до padding, empty-support refusal, реальные нули/endpoint-fill, masked missing bundle slots и downstream finite guard. Не заменять это новой универсальной архитектурой.

**C91-R01 — medium, высокая уверенность.** [Temporal kernel](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/preflight.py#L63-L110) сортирует, но не устанавливает finite/duplicate semantics. Нужна единая admission на existing boundary до optimizer: конечность обеих осей, совместимые координаты и explicit duplicate policy либо адресный refusal. Не слепой dedupe и не запрет всех экстраполяций. Сохранять positional mode, когда он действительно выбран.

**C91-R02 — medium, высокая уверенность.** [Grid construction](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/preflight.py#L281-L305) использует raw `time[0]`/`time[-1]` раньше paired sort. Нужна одна разрешённая source-axis semantics до inferred-grid construction, с tests steps≠source length и отсутствующим config.time_axis. Исправленная explicit-grid ветка должна остаться рабочей.

**C91-R03 — medium, высокая уверенность.** [Target grouping/materialization](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/measurement.py#L248-L324) устраняет multiplicity внутри даты, но не проверяет units всей серии. Проверять совместимость declared unit/interval на existing compiler/upstream transform; несовместимость сохранять для repair/refuse или преобразовывать только по explicit contract с lineage. Не угадывать физический смысл по имени metric; отсутствие universal deterministic unit inventor не является требованием. Полная lineage не объявлена утраченной: observation IDs остаются.

**C91-G01 — qualification.** Нужен supported native existing corpus и один подходящий lane-level observation→target→optimizer/report consumer witness, а не дорогой дубликат на каждый пакет CAL. Physical time/frequency, единицы, источники, independence и допустимость преобразования устанавливаются отдельно от массива/Pydantic validation. Не переносить predictive diagnostics или DDM false-positive calibration в Foundry по одному названию (`S13–S16`).

## 6. Воспроизводимость и пределы

[Commands](../04_Проверки/C91_CAL01/commands.json) · [Диагностики](../04_Проверки/C91_CAL01/bounded_diagnostics.json) · [Native status](../04_Проверки/C91_CAL01/native_verification.json) · [Оснастка](../04_Проверки/C91_CAL01/Чтение_и_границы.md) · [Fixture authority limits](../04_Проверки/C91_CAL01/fixture_authority_limits.json) · [Остатки](../01_Реестры/C91_остатки.json).

Run03 exit0; run01/02 exit1 — ошибки выбора AST config classes в нашей оснастке, не product failures. Actual Record/Panel/registry/splitter/measurement импортированы; пять manifest DTO и config class bodies выделены unchanged. Preflight целиком, кроме import jax.numpy; jnp явно NumPy fixture. Measurement использует собственный предусмотренный NumPy fallback. Pytest helper не выдаётся за pytest. Exact executed ranges/import identities сохранены.

Native import BLOCKED на несовместимом с Python3.12 except syntax в транзитивном uncertainty.py; pytest/JAX отсутствуют. Это environment limitation, не defect supported Python3.14 продукта. Gradients, full optimizer/report/CAS и реальный Fabric intake не запускались; native loss guard только прочитан. Репозиторий и зависимости не менялись.

**91/127 рассмотрены ограниченно; LANE-07 теперь действительно пройден по всем пакетам. Следующий — DFK-02, LANE-08. Фаза 2 не начата.**
