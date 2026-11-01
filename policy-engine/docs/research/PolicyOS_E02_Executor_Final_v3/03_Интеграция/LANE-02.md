# LANE-02: общий интеграционный контракт

**Цель:** Поиск действительно исполняет новые подходящие кандидаты, использует совместимую историю, сохраняет экономию и завершает допустимый бюджет без ложного promotion.

Состояние проверок: **NOT_RUN**. Это обязательные критерии будущей связанной приёмки, а не свидетельство текущего PASS. Семейство запускается один раз для согласованного изменения; локальные packet tests не дублируют его инфраструктуру.

## Область и зависимости

Пакеты: CTL-01, CTL-03, SRV-01, SRV-03, CTL-02, STP-01, OPT-01, OPT-02, OPT-03, OPT-04, FUN-01, FUN-02, FUN-03, TRN-01, TRN-02, TRN-03

- Общий сохранённый артефакт/ledger берётся из LANE-06.
- Funnel calibration получает LANE-03 typed evidence, а не внутреннюю замену чужого issuer.

## Профиль и допустимые подмены

- **P-CORE:** policy-engine Python >=3.14,<3.15; actual project lock/extras, supported existing environment; imports bind tested checkout/artifact (основание: policy-engine/pyproject.toml:8)
- **P-SEARCH:** P-CORE + actual locked GP backend for the selected GP/search continuation claim. Native vector-index qualification only when actually used, via P-INDEX; GP is not a prerequisite for an embedding-only route. (основание: policy-engine/pyproject.toml; test_gp_resume_witness.py)
- **P-INDEX:** P-CORE + selected vector-search extra hnswlib==0.8.0, actual native build/ABI, OS/arch/interpreter/lock and ef/index profile; fake index is wiring-only. No install implied by this specification. (основание: policy-engine/pyproject.toml [project.optional-dependencies].vector-search; uv.lock)

- Детерминированная маленькая objective и управляемые события/clock.
- Для driver/funnel seam можно задать внешний evaluator; для CP3 actual-consumer части оставить настоящий MethodJob/receipt/CAS.
- Mock GP/HNSW достаточен только для wiring; хотя бы один применимый tiny native posterior/index witness отдельно.

Подмена запрещена для принимаемого свойства: если проверяется запись/чтение, actual store и fresh reader обязательны; если численный метод — actual backend; если physical cleanup — actual OS resource. Внешний provider/encoder может быть лёгким и контролируемым, когда качество модели/сети не входит в claim.

## Подготовка и порядок

1. На выбранном поддерживаемом профиле связать checkout/build SHA и входные fixtures. Использовать существующие test owners ниже, прочитать их реальные seams перед расширением
2. Выполнить локальные REQ/TEST затронутых пакетов, затем каждый применимый вариант этого семейства. Независимые варианты допускают раздельный запуск
3. Положительный прогон должен пройти actual producer→передача/хранение→fresh consumer. При отсутствии хранения в конкретном алгоритме проверить непосредственный downstream consumer, не придумывая CAS ради отчётности
4. Повторить адресный негативный/граничный контроль. Изменение одного deciding input или отключение исправленного механизма должно менять наблюдаемый исход; unrelated пригодный результат остаётся доступным
5. Сохранить входы, события/значения/ошибки, ref identities, численные tolerances и команды. Итог связывает покрытые REQ, а не только список пакетных имён

## E02-I02-A — Новый run → actual SearchService/MethodJob → результат

Покрываемая область: CTL-01, CTL-03, SRV-01, SRV-03, STP-01

**Положительный oracle:** Два запуска имеют раздельные расходы/best; explicit continuation сохраняет нужную историю. Empty→candidate продолжается, always-empty завершён явно; sentinel расходует свою долю без обучения surrogate.

**Различающий негативный oracle:** Delayed tell старого generation не меняет новый run; overlapping tell не перемешивает results. Cancel/error сохраняет partial ledger; NaN budget, malformed typed result, stock sentinel codec не получают молчаливый success. Bounded proposal-budget exhaustion сохраняется как отдельная причина; finite-domain exhaustion требует полного census/enumeration выбранного конечного domain, а не одной исчерпанной попытки.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I02-B — Состояние стратегии и полезный search → promotion

Покрываемая область: CTL-02, OPT-01, OPT-02, OPT-03, OPT-04

**Положительный oracle:** Cold/warm и restored Random/Sobol/GP дают объявленную следующую точку и posterior; реальные SearchSpace/params/полные IDs достигают MethodJob. Pareto совпадает с независимым oracle; конкурентная публикация не затирает лучшего поздним худшим. Pending и completed dedup используют одну effective executable identity в выбранной measurement basis; независимые replicas допускаются только явно объявленной provenance/replica policy.

**Различающий негативный oracle:** Foreign metric/schema/split/unit/направление, stale mutable comparison basis и неподдержанный legacy state отвергаются без изменения live модели; cap=1 действительно ограничивает, exhaustion даёт честный остаток. Budget exhaustion не переименовывается в полное исчерпание domain. Measured-only transfer — отдельное optional расширение DEC-OPT-03-02, не обход нынешнего fitted-native guard.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I02-C — Один кандидат: полный funnel против A/B

Покрываемая область: FUN-01, FUN-02, FUN-03

**Положительный oracle:** На одном basis совпадают потреблённые configs, stages, costs, артефакты и итог; новое основание продолжает адресно. Valid finite uncertainty допускает действие только в своей роли. Положительный FUN-03 путь доходит до существующего назначенного protected writer: finite permit связан с subject/attempt/predecessor, фактический commit выполняется один раз. FUN-03 переносит одну versioned confusion-count projection TP/FP/FN/TN, определение выбранной FOR/FNR/FDR/precision метрики, denominator/cohort/window и sampling/missing-label scope через actual consumers; finite score +0.0/-0.0 сохраняется как значение, не fallback по truthiness.

**Различающий негативный oracle:** Split не повторяет ранние evaluate незаметно; empty criterion, insufficient correlation, undefined/overflow CI не становятся measured drift/PASS; stale разрешение не вызывает effectful callback. Revoke до сериализованной commit boundary исключает действие; bool callback и свежий preflight без этой boundary не считаются permit. Observed zero error — descriptive observation, не population PASS по одному ненулевому denominator; operational metric/tolerance и interval/sampling/evidence criterion выбираются в DEC-FUN-03-03. Undefined ratio, incompatible fallback basis или недостоверная selection не получают stronger permit; legacy semantics не переписываются.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I02-D — История и память → действительный warm consumer

Покрываемая область: TRN-01, TRN-02, TRN-03

**Положительный oracle:** Две сохранённые оценки: совместимая source-admitted история используется без повторной оплаты исходного измерения; fit/condition/refit следует объявленному continuation profile и измеряется отдельно, похожая несовместимая остаётся только подсказкой. Snapshot/alias версии, timestamp и evidence age сохраняются; local/transfer применяют одинаковые фильтры. Положительный профиль использует нынешние source-admission/fitted-native guards. Optional measured-observation расширение DEC-OPT-03-02, если отдельно принято и квалифицировано, отличает verified actual measurement от source surrogate prediction/continuation; target fit и его стоимость остаются явными.

**Различающий негативный oracle:** ANN oversampling не прячет совместимые результаты в заявленной области; injection add/load оставляет старое поколение целым; повторное чтение не омолаживает evidence и не дублирует sample. Отсутствие optional measured-only профиля не блокирует локальный repair и не превращает incompatible hint в измерение.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## Существующие места расширения tests

Список означает проверенные пути, не доказательство полноты или запуска всего содержимого. Новые проверки добавлять к ближайшему владельцу; отдельный harness создавать только при реальном разрыве.

- [policy-engine/tests/unit/scientist/methods/autotune/test_v5_search_pipeline.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/methods/autotune/test_v5_search_pipeline.py) — SHA256 `717294efd13f9a6570875c133b2a5dce0e0e0691e504d5c8b3a318b15ec834b7`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/scientist/search/strategies/test_gp_resume_witness.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/search/strategies/test_gp_resume_witness.py) — SHA256 `259ac9aa04da021fb88538ab6c846e706249afda40ec7c10eac57eb214b6eabc`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/scientist/methods/autotune/test_registry_and_runner.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/methods/autotune/test_registry_and_runner.py) — SHA256 `bd9c2b00274a7cce441e3c728c5cac242ecc581933040075da9903cf518a5499`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/scientist/search/funnel/test_transition_accounting_semantics.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/search/funnel/test_transition_accounting_semantics.py) — SHA256 `9faf2334eb0b7dbea4d6c75e79179f4a5384d191a3d90619cbff71b58bc4d588`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/scientist/agent/test_vector_memory_native_custody.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/agent/test_vector_memory_native_custody.py) — SHA256 `8bdbdc2c1c29ec44cba31040e6d897e240f0d27848c42516d4c60dac3d5e361a`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.

## Выход приёмки

- Один manifest исполнения семейства: base/head SHA, scenario-ID, связанные REQ/TEST, профиль, входы и их hash, actual commands/exit, фактические positive/negative oracles, ограничения
- Перечень doubles с объяснением, какое свойство ими не проверяется
- Для failure/unknown: точная стадия и сохранённый полезный результат. Не перекрашивать BLOCKED/UNRUN в PASS
- Ремонт механизма и предметная валидность имеют разные решения. Синтетический механизм может пройти, не подтверждая прогноз/каузальную идентификацию/мандат реального кейса
