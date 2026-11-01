# LANE-01: общий интеграционный контракт

**Цель:** Получить полезный условный расчёт штатным входом и содержательно продолжить его после нового основания, не требуя заранее известного домена.

Состояние проверок: **NOT_RUN**. Это обязательные критерии будущей связанной приёмки, а не свидетельство текущего PASS. Семейство запускается один раз для согласованного изменения; локальные packet tests не дублируют его инфраструктуру.

## Область и зависимости

Пакеты: CYC-01, REQ-01, CYC-03, ACQ-01, CYC-04, CYC-02, CYC-05, SIM-01, SIM-02, SIM-03, SEL-01

- CP1 использует compile/IR contracts LANE-04; persistence/attempt contracts LANE-06.
- Для реального acquisition источником может быть LANE-08/09; недоступность одного источника не блокирует независимый допустимый путь.

## Профиль и допустимые подмены

- **P-CORE:** policy-engine Python >=3.14,<3.15; actual project lock/extras, supported existing environment; imports bind tested checkout/artifact (основание: policy-engine/pyproject.toml:8)
- **P-JAX:** P-CORE + locked base JAX/jaxlib/optax; deterministic CPU tiny mechanism unless selected accelerator explicitly required; no invented XLA flags (основание: policy-engine/pyproject.toml; AGENTS.md)

- Только контролируемые внешние данные/доступный finite source; test tenant и временный store.
- Внешний proposal/LLM может быть детерминированным; реальный requirement builder, admission, binding, numerical producer и fresh reader не подменяются для принимаемого свойства.

Подмена запрещена для принимаемого свойства: если проверяется запись/чтение, actual store и fresh reader обязательны; если численный метод — actual backend; если physical cleanup — actual OS resource. Внешний provider/encoder может быть лёгким и контролируемым, когда качество модели/сети не входит в claim.

## Подготовка и порядок

1. На выбранном поддерживаемом профиле связать checkout/build SHA и входные fixtures. Использовать существующие test owners ниже, прочитать их реальные seams перед расширением
2. Выполнить локальные REQ/TEST затронутых пакетов, затем каждый применимый вариант этого семейства. Независимые варианты допускают раздельный запуск
3. Положительный прогон должен пройти actual producer→передача/хранение→fresh consumer. При отсутствии хранения в конкретном алгоритме проверить непосредственный downstream consumer, не придумывая CAS ради отчётности
4. Повторить адресный негативный/граничный контроль. Изменение одного deciding input или отключение исправленного механизма должно менять наблюдаемый исход; unrelated пригодный результат остаётся доступным
5. Сохранить входы, события/значения/ошибки, ref identities, численные tolerances и команды. Итог связывает покрытые REQ, а не только список пакетных имён

## E02-I01-A — Штатный вход → N5 → сохранённый N8

Покрываемая область: CYC-01, CYC-02, SIM-01, SIM-02, SIM-03, SEL-01

**Положительный oracle:** Реальный request/builder/selection/численный producer сохраняет один result; fresh reader воспроизводит значение, единицы, basis и ограничения. Подходящий второй метод работает после несовместимого первого; singleton допустим. Композиция сохраняет не только суммы, но совместные последствия/конфликты. SIM-03 seed qualification отдельно использует actual stochastic engine с y=u+(2+u)*a, evidence{} либо declared partial evidence: paired effect=2+u, endpoints/mean/SE сверяются по реальным draws; deterministic integer comparator остаётся самостоятельным control. Native NCM confidence quantile детерминирован из qualified existing stdlib/SciPy inverse-normal implementation с устойчивым near1 tail, без100000 ambient normal draws на каждый call; actual same-seed worlds/summary/CI не зависят от ambient NumPy RNG.

**Различающий негативный oracle:** Изменение problem/model/catalog binding, пропуск обязательного coupled input, alias вместо независимого основания, nonfinite paired output либо duplicate moment не даёт ложного успеха. Нельзя выключить все методы и назвать отказ ремонтом. Смена seed labels без изменения фактически полученных unobserved-noise draws не доказывает seed propagation; наблюдённый исход, фиксирующий U, не используется как seed-sensitive witness. Invalid confidence отказывает до sampling; singleton/normal-interval assumptions и empirical coverage отдельно, finite CI не scientific guarantee.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I01-B — Новый intent и acquisition → re-entry

Покрываемая область: REQ-01, CYC-03, ACQ-01

**Положительный oracle:** Явный requirement сохраняет смысл, область и unresolved; новый разрешённый источник проходит admission и создаёт новое согласованное основание. A→B→B→B→C удерживает равное B и продолжает по C без лишнего запроса/повторного вычисления.

**Различающий негативный oracle:** Неизвестный domain не подменяется известным; old source/epoch/context отвергается только в зависимой операции. Поддержанный candidate продолжает исследование с ограничением, а не исчезает из-за authority gate.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I01-C — Полезный следующий шаг и честная остановка

Покрываемая область: CYC-04, CYC-05

**Положительный oracle:** После grounding сравниваются действительно допустимые варианты и информативная проверка; переданный ресурс, цена N5 и причина остановки доходят до consumer/public view. Actual выбранный build/distribution evidence от LANE-12 проходит существующий confidence_ledger issuer/verifier и даёт current N6 readiness на фактически загруженном baseline; это техническая пригодность, не институциональное полномочие.

**Различающий негативный oracle:** Изменение доступности позднего N5/N8 не оставляет устаревшую альтернативу; missing value-proxy не становится нулём. Исчерпанный ресурс останавливает новую работу, но сохраняет результат и конкретный путь продолжения. Missing/stale/unappointed build basis не заменяется константой PASS; исторический результат остаётся доступным.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## Существующие места расширения tests

Список означает проверенные пути, не доказательство полноты или запуска всего содержимого. Новые проверки добавлять к ближайшему владельцу; отдельный harness создавать только при реальном разрыве.

- [policy-engine/tests/integration/runtime_quality/test_configured_candidate_simulation_served.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/runtime_quality/test_configured_candidate_simulation_served.py) — SHA256 `0f7d905373d0156483cf591c76239268b970fe648b1dbd508e5d98d02c07f33b`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/integration/core_runtime/test_acquisition_retained_sequential_served.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/core_runtime/test_acquisition_retained_sequential_served.py) — SHA256 `f9f19f845495f7389f6966fb97315e03f8dd4fa6d8695a0f3999449e024aa722`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/integration/core_runtime/test_acquisition_authority_served.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/core_runtime/test_acquisition_authority_served.py) — SHA256 `b38bb88bd0d10d276ac54abc1787594ad52d49c1dab8e91ce63289f230551aa8`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/data_requirement/test_compiler.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/data_requirement/test_compiler.py) — SHA256 `61d3ca8af4245ba9853e20d59b4d867415491112e1bde77edd259cb6a25ea0a0`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/foundry/coupling/test_estimation.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/coupling/test_estimation.py) — SHA256 `1f01107d6aecef17b150694493463894da7fe7077e42b17366dc74c70a8a893a`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.

## Выход приёмки

- Один manifest исполнения семейства: base/head SHA, scenario-ID, связанные REQ/TEST, профиль, входы и их hash, actual commands/exit, фактические positive/negative oracles, ограничения
- Перечень doubles с объяснением, какое свойство ими не проверяется
- Для failure/unknown: точная стадия и сохранённый полезный результат. Не перекрашивать BLOCKED/UNRUN в PASS
- Ремонт механизма и предметная валидность имеют разные решения. Синтетический механизм может пройти, не подтверждая прогноз/каузальную идентификацию/мандат реального кейса
