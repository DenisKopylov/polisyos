# TRN-01 — численный transfer и честный исторический результат
## C25 · 31 октября 2026 года

**Исходные IDs:** B128, B130, B131, B132. **Порядок:** 25/127, LANE-02. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит; следующий — TRN-02.

## Решение

**Основные локальные ремонты присутствуют и связаны друг с другом.** Transfer восстанавливает настоящие поля `ObjectiveValue`, сохраняет rejected rows, сортирует выбранную координату в минимизационной конвенции и перераспределяет квоту. Численный перенос требует полного целевого fingerprint, совпадения пространства, bounds, split, units, origin, tenant, направления и правила; затем читается выбранный history ref и проверяется его заголовок. Обратный конвертер больше не придумывает нулевой ref, не кладёт параметры в метрики и не дублирует selection в holdout.

Это не полное закрытие. Подтверждены **C25-R01:** потеря исходного timestamp при восстановлении; **C25-R02:** строка `"false"` в persisted `stage_a_passed` превращается в True. У обратного конвертера остаётся ограниченная способность: синтаксический ArtifactRef не подтверждает существование кандидата, исходный split/suite/profile не устанавливается. Его production caller не найден в проверенной области `policy-engine/src`; фактический runtime передаёт `Evaluation` прямо в дальнейший admission, поэтому загрязнение нативного GP этим конвертером не заявлено.

**26 MATCH, 0 ERROR**, exit 0 после исправления только audit-loader. Исполнены неизменённые определения transfer/bridge и настоящие DTO: ObjectiveValue, ObjectiveScoreAssessment, Evaluation, RunFingerprint, ArtifactRef, BenchmarkEvaluation. **Source replay и history reader — явные фикстуры; это не native product/CAS/GP test.**

## 1. Исходный смысл и две оси

[Полная исходная карточка](../05_Источники/TRN-01_исходные_строки.txt) требует не просто устранить TypeError, а не оживить с ним неподтверждённые числа. Сходство полезно для идеи; совместимость численного наблюдения, допустимость training split и право доступа — отдельные основания. LLM может предложить переносимую гипотезу без нового универсального deterministic transfer-engine.

| ID | Исходный ремонт — что сохранить | Содержательная способность и остаток |
|---|---|---|
| B128 | `raw_value`/direction/assessment восстановлены; malformed row видима с ID и причиной | C25-R01/R02: верно сохранить время и тип feasibility-флага. Native CAS round trip ещё не выполнен |
| B130 | MIN 1 раньше 9, MAX 9 раньше 1; round-robin заполняет свободную квоту, не превышая предел | Политика diversity, rejected diagnostics и численного корпуса должна оставаться явной; GP benefit не измерен |
| B131 | Полный target обязателен; exact binding и history header; source/rule replay; сохранены objectives, provenance и metadata | Совпадение полей не выдаёт полномочий. Есть дополнительный native GP receipt verifier и candidate-only route; проверить реальный источник и target owner, не ослабляя их |
| B132 | Разные candidate IDs; raw metric вместо normalized scalar; параметры только в metadata; holdout пуст; nonpromotable | C25-G01: подтвердить настоящий candidate/suite/split/profile либо оставить результат историческим Evaluation, а не переименовывать в измерение target suite |

## 2. Producer → persistence → consumer

### История и её восстановление

`register_run` допускает только Evaluation, чьи выбранные objective rules согласованы с fingerprint. Schema 5 сохраняет все координаты, raw value, direction, assessment, исходный результат, параметры, provenance, metadata, timestamp и execution status. В индекс помещается адрес **этого** history artifact вместе с возвращённым selected manifest profile. [S01:107–180,283–321]

`find_similar_runs` использует vector similarity только для поиска, после чего требует полный typed binding. `get_warm_start_evaluations` не имеет permissive варианта без target; несовместимый source не читается. `_read_history` разрешает exact Core JSON ref, проверяет selected profile, schema 3/4/5, run ID и все поля заголовка. LRU хранит immutable bytes, не разделяемые mutable Evaluation. Cache resource lifecycle подробнее относится к следующему TRN-02. [S01:182–281,739–919]

`_deserialize_evaluation` создаёт настоящий Evaluation и ObjectiveValue, не устаревший `value=...`. Ошибки структуры превращаются в видимую STAGE_B_ERROR с `transfer_error`, а не `continue`. Assessment заново согласуется с retained source и selected rule. Текущая scalar convention — **raw выбранной scalar-координаты**; нормализация находится в `ObjectiveValue.normalized_value`. Нельзя переносить старое утверждение «всякий scalar уже minimized» на этот HEAD. [S01:500–738; S03:106–158; S04:1160–1228,2715–2829]

### Реальные потребители и ограничения

* SearchLoopRunner строит actual method-run profile, загружает native Evaluation через bridge, затем вызывает `warm_start_for_context`. Он **не** вызывает `evaluations_to_benchmarks`. [S07:1840–1895]
* Bayesian generator требует настоящий configured native GP, target MethodJob run profile, selected objective replay, source evaluation ref, receipt и `_verify_search_source_profile_receipt`. Сходный fingerprint сам по себе не становится GP observation. Этот verifier в C25 прочитан как вызов и граница, но целиком не исполнен. [S08:287–490]
* Candidate-only policy path сравнивает rules с реально выбранной конфигурацией и tenant с `ctx.run.tenant_id`, разрешает portable index и добавляет exact source history/binding/index refs. Он явно предназначен для **повторной оценки** текущего кандидата. [S09:992–1081]

Следовательно, существующая работа значительно шире DTO-ремонта. При этом native CAS/receipt verification и target reevaluation в этой среде не выполнены. Полное равенство metadata, включая явно supplied None для nullable полей, не доказывает институциональное разрешение либо научную сопоставимость. Отдельный широкий discovery аналогий не следует заменять запретом любой межзадачной идеи; в прочитанном candidate-only loader используется строгий поиск, а наличие остальных возможных аналоговых путей здесь не исчерпано.

## 3. Различающие исполнимые наблюдения

Диагностика исполняет actual definitions, не ручную копию алгоритма. Audit loader проверяет Git blob каждого исходника. На source-score boundary использована явно объявленная deterministic fixture; history reader возвращает подготовленные JSON rows. Это позволяет проверить constructor, правила отбора и wire shape, **но не аттестовать исходные измерения**.

| Наблюдения | Результат |
|---|---|
| P01, P26 | JSON → настоящий ObjectiveValue/Evaluation; bridge передаёт target, возвращает строку, provenance и metadata сохранены |
| P02, P03 | MIN: выбран raw 1; MAX: выбран raw 9, normalized −9 |
| P04 | Истории длиной 1 и 3 дают все 4 строки при лимите 4 |
| P05–P12 | Изменение space, bounds, split, units, origin, tenant, direction, rule исключает source **до history read** |
| P13 | Без keyword-only target возникает TypeError, не permissive reuse |
| P14 | Нет direction: строка остаётся с исходным ID, STAGE_B_ERROR и причиной |
| P15, P16 | Изменённый source в declared fixture либо другое selected rule не дают valid observation |
| P20–P22 | Настоящие Pydantic benchmark JSON round trips: разные refs, raw MAX 0.8, holdout пуст, параметры вне metrics; неадресуемый ID пропускается |
| P25 | Rejected diagnostics остаются в ограниченной выдаче и занимают её квоту: 2 результата, из них 1 valid, хотя в другом source есть ещё valid row |

P25 — не возврат к старому floor-quota дефекту: политика явно сохраняет отклонённые строки и разнообразие источников. **C25-G03:** различить лимит diagnostic delivery и admitted training corpus, если нужна заявленная квота именно допустимых наблюдений. Не удалять rejected evidence ради красивого count и не объявлять полученные два объекта двумя численными наблюдениями.

## 4. Подтверждённые остатки

### C25-R01 — timestamp сохраняется, но не восстанавливается

**Важность:** низкая для текущего численного отбора, существенная для верности исторической записи.

Serializer записывает `evaluation.timestamp.isoformat()`. Constructor в `_deserialize_evaluation` не передаёт timestamp, поэтому настоящий Evaluation использует `datetime.now(UTC)`. **P17:** исходное `2001-01-01T00:00:00+00:00` заменено временем аудита, остальные поля и experiment metadata сохранились. [S01:316,622–637; S03:119]

Это конкретная потеря исходной идентичности времени, а не доказанное нарушение текущего TTL или gain модели: в проверенных strategy/autotune источниках отдельный timestamp-based admission не найден. Минимальное продолжение — сохранять исходное event time, отдельно обозначать restore time и явно классифицировать malformed/legacy timestamp. Нельзя выдавать время загрузки за время эксперимента.

### C25-R02 — malformed feasibility-флаг становится положительным

**Важность:** средняя на границе исторической схемы; native safety bypass не заявлен.

`stage_a_passed=bool(row.get("stage_a_passed", False))` превращает непустую строку `"false"` в True. **P18:** настоящий JSON boolean false остаётся infeasible; **P19:** меняется только wire type/value на строку `"false"`, и восстановленный actual Evaluation имеет `stage_a_passed=True`, `is_valid=True` при одинаковом выбранном score и declared source-replay fixture. [S01:622–637; S03:147–158]

Typed writer обычно сериализует boolean, поэтому наблюдение касается malformed/legacy/внешне сформированной строки за history boundary; оно не доказывает, что штатный producer создаёт такую строку. Но `_read_history` проверяет общий заголовок и dict rows, не тип этого поля; различение malformed row уже является обязанностью адаптера. Требуется strict boolean admission или адресный rejected result, не truthiness. Дальнейший native GP receipt verifier остаётся отдельной защитой и здесь не обходился.

## 5. C25-G01 — обратный benchmark bridge всё ещё не устанавливает исходное испытание

[Конвертер](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/warm_start.py#L78-L161) больше **не генерирует** нулевые ref и не фабрикует holdout. Это полезный ремонт. Однако `ArtifactRef(candidate_id, kind="search.candidate")` проверяет форму, не загрузку реального кандидата; selected profile отсутствует. Default suite — `warm_start`, runtime split всегда SELECTION, исходный split/suite не входит в signature и не разрешается из source evidence.

* **P23:** Evaluation с metadata о hidden_holdout/original suite/profile всё равно становится selection/warm_start без этих полей. Metadata сама не authenticated authority; опыт доказывает отсутствие selected source handoff, а не истинность переданного hidden_holdout.
* **P24:** syntactically valid zero digest принимается. Это не возврат прежнего «всем придумать нулевой ID»: он пришёл во входе. Но наличие syntactic ref нельзя описывать как доказанно существующий artifact.

Nonpromotable и `warm_start_limited` сохранены; они не делают source split установленным. Правильное продолжение — использовать уже настоящий Evaluation либо resolve исходные candidate/suite/split/profile и сохранить их без переименования; target reevaluation создаёт **новый** benchmark. В полной `policy-engine/src` области найден только definition обратного метода; вызовы — в tests. Поэтому production распространённость этого остатка не завышена.

## 6. Native тесты и границы принятия

995-строчный `tests/unit/scientist/methods/autotune/test_warm_start.py` прочитан по последовательным диапазонам. Он содержит actual CAS fixtures, проверки заголовка, правил, нормализации, malformed rows, native DTO и resource cache. `test_trn_01.py` не найден; это предложение sourceplan, не обязательное имя реализованного теста.

**C25-G02:** pytest/torch/botorch отсутствуют, supported Python 3.14 не запускался. Native tests не исполнялись. У `_MemoryVectorIndex` в прочитанном тесте есть add/query, но нет `lookup_metadata`, хотя один round-trip передаёт fingerprint без history ref и current reader вызывает exact lookup. Это source-level несогласованность конкретного fixture, **не объявленный фактический pytest failure**. Положительные bounded observations не закрывают её.

Первый запуск audit-loader остановился на `_MISSING` до диагностики: sentinel должен быть определён до загрузки функции с default argument. Исправлена только загрузочная обвязка; следующий запуск дал **26 MATCH / 0 ERROR**. Оба полных logs сохранены. Product checkout и зависимости не менялись. MATCH включает воспроизведённые дефекты и не означает product PASS.

[Диагностика](../04_Проверки/C25_TRN01/bounded_diagnostics.json) · [команды](../04_Проверки/C25_TRN01/commands.json) · [границы](../04_Проверки/C25_TRN01/Чтение_и_границы.md) · [источники](../05_Источники/C25_источники.json) · [остатки](../01_Реестры/C25_остатки.json).

**25/127 пакетов рассмотрены ограниченно; 67 уникальных B/LA частично оценены; полного закрытия нет.** Следующий — **TRN-02 / B129, B133, B134**.
