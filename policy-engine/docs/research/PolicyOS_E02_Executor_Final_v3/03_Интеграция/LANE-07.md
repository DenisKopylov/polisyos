# LANE-07: общий интеграционный контракт

**Цель:** Предметные наблюдения, демография и federation сохраняют действительный источник каждой величины и дают пригодный input к модели без фабрикации измерений.

Состояние проверок: **NOT_RUN**. Это обязательные критерии будущей связанной приёмки, а не свидетельство текущего PASS. Семейство запускается один раз для согласованного изменения; локальные packet tests не дублируют его инфраструктуру.

## Область и зависимости

Пакеты: UDF-01, OBS-01, UDF-02, OBS-02, UDF-04, UDF-05, FED-01, FED-02, CAL-01

- CAL-01 передаёт target contract CAL-02 в LANE-10 (CP4); остальные CP2.
- Shared source generation/CAS contracts LANE-08/06; reuse не равен общему владельцу domain/calibration.

## Профиль и допустимые подмены

- **P-CORE:** policy-engine Python >=3.14,<3.15; actual project lock/extras, supported existing environment; imports bind tested checkout/artifact (основание: policy-engine/pyproject.toml:8)
- **P-DATA:** P-CORE with native selected pyarrow/Parquet, NumPy/NPZ, DuckDB/graph backend when claimed; ordinary JSON seam not Parquet qualification (основание: policy-engine/pyproject.toml; OBS-02/UDF-02/EMB audit reports)

- Tiny real Parquet/JSON/NPZ и локальный snapshot; external acquisition fixture помечается synthetic.
- Provisioning/server-only проверяет command/cwd/env и guard, не запускает production jobs.
- Для cell-source replay настоящий selected artifact reader; не just expected DataFrame fixture.

Подмена запрещена для принимаемого свойства: если проверяется запись/чтение, actual store и fresh reader обязательны; если численный метод — actual backend; если physical cleanup — actual OS resource. Внешний provider/encoder может быть лёгким и контролируемым, когда качество модели/сети не входит в claim.

## Подготовка и порядок

1. На выбранном поддерживаемом профиле связать checkout/build SHA и входные fixtures. Использовать существующие test owners ниже, прочитать их реальные seams перед расширением
2. Выполнить локальные REQ/TEST затронутых пакетов, затем каждый применимый вариант этого семейства. Независимые варианты допускают раздельный запуск
3. Положительный прогон должен пройти actual producer→передача/хранение→fresh consumer. При отсутствии хранения в конкретном алгоритме проверить непосредственный downstream consumer, не придумывая CAS ради отчётности
4. Повторить адресный негативный/граничный контроль. Изменение одного deciding input или отключение исправленного механизма должно менять наблюдаемый исход; unrelated пригодный результат остаётся доступным
5. Сохранить входы, события/значения/ошибки, ref identities, численные tolerances и команды. Итог связывает покрытые REQ, а не только список пакетных имён

## E02-I07-A — Украинский raw/snapshot → builder → typed observation

Покрываемая область: UDF-01, OBS-01, UDF-02, OBS-02, UDF-04

**Положительный oracle:** Actual handoff aliases/bytes и I/O owner сохраняют данные; валидный календарь/finite value проходит. Restart/rebatch после partial yield даёт тот же принятый набор без повторения prefix.

**Различающий негативный oracle:** Invalid period, tampered selected projection, reader snapshot mutation или mapper failure сохраняет точную причину/partial accounting; missing не становится измеренным нулём. Server-only action не запускается на неподходящем profile.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I07-B — Demography/federation → selected artifact → second read

Покрываемая область: UDF-05, FED-01, FED-02

**Положительный oracle:** Три источника, repeated keys и разные audit modes сохраняют primary precedence и producer каждой cell после второго JOIN/persistence. Bounded details сохраняют полные counts; lawful empty UNION доступен. UDF donor IDs валидируются по исходным scalars до общего NumPy dtype: mixed integer/float inputs сохраняют exact int64 IDs. FED/UQS finite binary64 mean используют один тонкий owner над CPython3.14 statistics.mean, midpoint — тот же owner; independent rational oracle не вызывает producer mean.

**Различающий негативный oracle:** Role overwrite, fractional donor truncation, aggregate overflow, wrong mapping/source/lineage не становятся правильными данными; отсутствие authority не стирает candidate composition. Mixed [2**53+1,1.0], int64 boundaries и перестановки не должны терять identity от float coercion; из уже округлённого float невозможно восстановить прежний integer. Custom accumulation требует измеренного преимущества и equivalence, не новой арифметической системы.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I07-C — Observation → calibration target bundle

Покрываемая область: CAL-01

**Положительный oracle:** Сортировка paired time/value/metadata инвариантна observation ID; requested grid и fractional fill проходят; поддержанный однозначный target даёт usable measurements.

**Различающий негативный oracle:** Duplicate source timestamps без объявленной содержательной duplicate policy, nonfinite source/target time, нарушения declared target coordinate/model contract, conflicting same-period источники и empty support не маскируются случайным tie-break, NaN или good-fit. Область отказа ровно affected target; повторный finite target query сам по себе не нарушение, если его допускает выбранный interpolation-query profile.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## Существующие места расширения tests

Список означает проверенные пути, не доказательство полноты или запуска всего содержимого. Новые проверки добавлять к ближайшему владельцу; отдельный harness создавать только при реальном разрыве.

- [policy-engine/tests/unit/remediation/test_obs_02.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_obs_02.py) — SHA256 `0654a6d3c9cc9286bb7b491d6c17ccc614ab075cb32c6c9c0f3bbcf984f719f8`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/data_forge/domains/ukraine/test_demography_source_inventory.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/data_forge/domains/ukraine/test_demography_source_inventory.py) — SHA256 `76e5ba88eed68583219688f401a915469a3a1b93d63eebac40634dda1a40bd49`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/fabric/connectors/test_federation_artifact.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/fabric/connectors/test_federation_artifact.py) — SHA256 `9f11c281ef2d9100cc62005575cd29f1fb9ad0eb335c48fc34caff3434174109`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/fabric/connectors/test_federation_cold_c93.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/fabric/connectors/test_federation_cold_c93.py) — SHA256 `5a23329edc3fe8cb9b3d35b06ec07c56abdc1a9a2676680d41ea1891a590fd49`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/remediation/test_cal_01.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_cal_01.py) — SHA256 `8c343db6ca5d1003606156e47cc9fd47da3c484dd2a5b946a8527bc785628441`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.

## Выход приёмки

- Один manifest исполнения семейства: base/head SHA, scenario-ID, связанные REQ/TEST, профиль, входы и их hash, actual commands/exit, фактические positive/negative oracles, ограничения
- Перечень doubles с объяснением, какое свойство ими не проверяется
- Для failure/unknown: точная стадия и сохранённый полезный результат. Не перекрашивать BLOCKED/UNRUN в PASS
- Ремонт механизма и предметная валидность имеют разные решения. Синтетический механизм может пройти, не подтверждая прогноз/каузальную идентификацию/мандат реального кейса
