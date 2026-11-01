# FUN-02 — изоляция reduced-config и правдивый результат воронки
## C23 · 31 октября 2026 года

**Исходные IDs:** B157, B160, B162, B165. **Порядок:** 23/127, LANE-02. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит; далее — FUN-03.

## Решение

**Основные первоначальные дефекты отремонтированы в рассмотренных owners; полное закрытие не заявлено.** L3 копирует пять маленьких mapping перед flat overlay и больше не меняет full-конфигурацию L4. Empty/capped funnel не выдаёт 0/APPROVE. Итоговый compatibility verdict вычисляется из aggregate, а stage verdict хранится отдельно. Missing/broken/null/negative/nonfinite CI больше не выдаются за нулевую uncertainty; корректный ноль сохраняется.

Остались **C23-R01** — узкий overflow промежуточной арифметики при больших конечных width/effect — и **C23-R02** — producer создаёт heuristic width с честным `draw_execution_status=not_instrumented`, но adapter называет его `full_fidelity_bootstrap`. Второй остаток касается смысла диагностической projection, **не доказанного обхода scientific/promotion authority**.

Итог **25 MATCH, 0 ERROR, exit 0**. Исполнены actual selected adapter/config/aggregate/helper/serializer definitions и настоящие Pydantic uncertainty DTO. Engines, score admission, evaluation source и внешние owners — явные фикстуры. Native pytest/PolicyOS/CAS/Foundry **UNRUN**; dependency install отсутствует.

## 1. Исходный ремонт и предметный результат

[Оригинальный пакет](../05_Источники/FUN-02_исходные_строки.txt) требует не только разных чисел L3/L4, а достоверного смысла fidelity, результата и неопределённости. LLM может предложить параметры исследования; технический слой должен сохранить full-input, явно сказать, что не исполнено, и не превратить proxy в эмпирическое измерение.

| ID | Сохранить текущий ремонт | Остаток |
|---|---|---|
| B157 | Local copies пяти config mappings; большие data/model/CAS handles не копируются; L3 profile виден в feedback | Native backend actual work/cost и принятие эффективного full profile не аттестованы. Изоляция не обещает защиту от произвольной мутации вложенного объекта самим engine |
| B160 | `objective_value=None`, NOT_EVALUATED, false promising; cap после выполненной части даёт partial/defer; admitted zero сохраняется | Actual source-admitted zero и end-to-end consumers — native qualification |
| B162 | Причины missing/invalid/effect_invalid, валидные finite/zero controls; overflow преобразования huge int уже обработан | C23-R01: overflow `2*effect`; C23-R02: bootstrap label не связан с действительным методом получения width |
| B165 | Aggregate verdict заменяет stage verdict независимо от наличия поля; stage result и score не стираются | Native consumer migration, score-source admission и публикационные полномочия этим replay не доказаны |

## 2. B157 — минимальная изоляция действительно работает

[L3 state owner, S01:258–305](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/funnel/level3_medium.py#L258-L305) копирует `data_config`, `estimation_config`, `scenario_config`, `subgroup_config`, `model_config` через `dict(config)` и меняет только принадлежащие L3 ключи. None становится пустым mapping; иной тип явно отвергается. Большой dataset/model/CAS не deep-copy. Это соответствует требованию, а не недостаток само по себе.

**P01** исполняет настоящие L3.evaluate→_build_reduced_state и L4.evaluate→ExpensiveStage.evaluate с recording engine и явной fixture score-admission границей:

* Caller fraction=1, bootstrap=500, SCM=full остаются неизменны.
* L3 engine получает fraction=0.2, bootstrap=50, SCM=reduced.
* L4 engine после L3 получает тот же input, что отдельная прямая L4 на исходном context.
* Dataset/model/CAS сохраняют исходную object identity; никакого копирования всего набора данных нет.

**P02** характеризует границу: произвольный вложенный `model_config['tuning']` остаётся shared. Сам adapter его не меняет; mutation в тесте сделана аудиторским caller после построения state. Это **не воспроизведение старого B157 и не новый доказанный native дефект**. Если конкретный engine мутирует собственные nested config, исправление принадлежит его фактическому mutable owner. **P03:** list вместо data_config даёт явный TypeError до engine, не silent fallback.

L4 использует текущий caller profile; не навязывает универсальный максимум bootstrap и не требует L0–L6 для каждого исследования. Нативный policy adapter дополнительно передаёт backend явный `fidelity=self._fidelity`; он различает medium/full независимо от имени config. `effective_estimation_config` передаётся отдельно, requested draws и digest связываются с invocation, но draw execution остаётся not_instrumented. [S07:334–470; S08:620–675; S09:400–428]

**C23-G01:** recording engine подтверждает переданные inputs, но не то, что настоящий engine выполнил 50 или 500 bootstrap draws и L3 действительно дешевле. Текущий native код сам не выдаёт requested count за executed count. Сохранить это различие; не объявлять instrumentation gap отсутствующей всей scientific capability.

## 3. B160/B165 — результат стадии и итог теперь разделены

`_empty_result` возвращает None/UNAVAILABLE, NOT_EVALUATED, false promising. `_mark_terminal` без stage_results ставит defer. `_evaluation_status` отличает not_evaluated, partial и evaluated. Для capped full после выполненных stages добавлен guard, не позволяющий назвать такой план полным. `_compatibility_result` сначала выбирает verdict из aggregate, сохраняет исходный под `stage_verdict`, затем формирует обещанный интерфейс. [S03:1959–2092,855–867]

| Опыт | Итог compatibility | Score | Сохранённая полезная часть |
|---|---|---|---|
| P04: пустой funnel | NOT_EVALUATED, defer | None | Нет выдуманного вычисления |
| P05: L4 исключена cap=2 | NOT_EVALUATED, defer | None | L4 не вызвана |
| P06: выполненный fixture-admitted zero | APPROVE | **0.0** | Ноль не заменён отсутствием |
| P07: stage APPROVE + terminal defer | DEFER, false promising | **0.0** | `_funnel_result` перспективен; stage_verdict=APPROVE |
| P08: тот же defer без stage verdict | DEFER, false promising | **0.0** | Отсутствующее необязательное поле не меняет итог |
| P09: stage APPROVE + terminal reject | REJECT | **0.0** | Stage verdict хранится отдельно |
| P10: L0 выполнена, L4 исключена cap | DEFER, partial | **0.0** | Частичное измерение не стирается |

P06–P10 доказывают routing/projection mechanics после **явной fixture-admission**, не истинность нулевого измерения. Нативные tests `test_score_admission_finalization.py` проверяют actual selected-score recomputation, available zero, invalid/missing units и non-GDP basis; все 210 строк прочитаны, но tests **UNRUN**. [S12]

Stage B возвращает both `_funnel_result` и `_funnel_outcome`; consumer обязан читать назначенное поле, а не самый удобный APPROVE. Actual lifecycle передаёт результат в source/candidate identity admission, а blueprint сериализует aggregate отдельно. Эти source-пути прослежены в C22, не переисполнены C23. Дефект old `setdefault` в нынешнем wrapper не обнаружен. Полная миграция всех внешних consumers не объявлена завершённой.

## 4. B162 — missing/invalid/zero различаются, а не подменяются default bootstrap

Общий `statistical_uncertainty_from_ci_width` используется L3 и L4. Он проверяет наличие mapping/width, None, bool, преобразование float с **OverflowError**, конечность и знак; отдельно проверяет effect. Error возвращает level=1 **с причиной** ci_width_missing, ci_width_invalid или effect_invalid; это не утверждение измеренной единичной uncertainty. [S04:190–297; S05:100–233]

P11–P23 с настоящими helper и Pydantic DTO:

* missing/null → `ci_width_missing`, level1;
* broken/negative/NaN/bool → `ci_width_invalid`, level1;
* width=0, ATE=2 → level0;
* width=0.4, ATE=2 → level0.1;
* missing ATE → `effect_invalid`, level1;
* ATE=0, width>0 → level1; ATE=0, width=0 → level0;
* огромный integer `10**400` в width или effect корректно классифицируется invalid, а не выбрасывает OverflowError наружу.

Первоначальная аудиторская гипотеза о последнем исключении **опровергнута**. Не включена в остатки. Истинный zero width не запрещается blanket-правилом; scientific допустимость вырожденного интервала требует фактического метода, не решается этим helper.

### C23-R01 — overflow промежуточного знаменателя

**Важность:** низкая, экстремальный численный край. **P24:** оба входа конечны: width=ATE=1e308. Выражение `ci_width / (2.0 * effect)` получает бесконечный знаменатель и выдаёт **0**, сохраняя bootstrap label. Устойчивая reference арифметика `(0.5 * width) / effect` даёт **0.5**. Это не NaN-input и не overflow float-conversion; существующие guards его не ловят.

Остаток — численно устойчивое отношение с проверкой конечности промежуточного результата и объявленного масштаба. Не заменять все крайние значения константой и не объявлять этот редкий вход доказательством обычного production вреда. Source-read owner: [S04:286–297](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/funnel/types.py#L286-L297).

### C23-R02 — heuristic width получает имя эмпирического метода

Более содержательная producer→consumer граница: `_build_policy_simulation_results_impl` создаёт width=0.1 для non-selection fidelity либо 0.12 для selection, увеличивает его через uncertainty/feasibility heuristic и записывает в `bootstrap.ci_width`. При этом тот же payload **честно** указывает `draw_execution_status='not_instrumented'`, actual draw counts=None и пустые metric_units. [S09:450–541]

L4 `_build_uncertainty_envelope` передаёт эту width общему helper с `source='full bootstrap/full estimator stack'` и `quantification_method='full_fidelity_bootstrap'`; helper читает только width и ATE, не статус происхождения. **P25** исполняет actual producer body и actual L4 consumer: width0.1, ATE1, draw_status=not_instrumented → level0.05 с method full_fidelity_bootstrap. Evaluation/fiscal/ambiguity объекты — явные фикстуры; production backend не исполнялся.

Это подтверждённое локальное несоответствие **semantic label**, а не доказанная scientific authority. Actual production evaluator вызывает этот builder после своих safety/source checks, что найдено в source; весь путь не запускался. [S10:850–978] Orchestrator различает historical uncertainty envelope и fresh source-owned current read; численный routing envelope не становится автоматически публикационным доказательством. [S03:880–1129]

Минимальное направление — сохранить реальный вычислительный результат и routing-полезность, но передавать действительное происхождение width. Heuristic должен называться proxy; отсутствующая bootstrap measurement не должна приобретать имя bootstrap только через ключ словаря или fidelity. При наличии настоящего source-owned interval нужны его scale/method/input binding, а не ещё одна self-asserted метка. Не требовать нового универсального детерминированного изобретателя моделей и не выбрасывать полезные промежуточные результаты.

## 5. Tests и границы доказательств

Полностью прочитаны remediation `test_fun_02.py`, `test_level3_medium.py`, `test_level4_full.py`, `test_score_admission_finalization.py`. Их coverage включает owned-config identity, empty/capped, zero, width negatives и aggregate override. В старом `test_level4_full_emits_full_fidelity_stage_result` engine не поставляет metric_units, а test ожидает promising и численный objective; нынешний actual ExpensiveStage требует source-admitted unit. Это **C23-G02: test-contract qualification**, не объявленный результат native pytest.

**C23-G03:** научная валидность bootstrap, declared scale/units, actual source-score admission, physical workload и полный downstream consumer не аттестованы. Настоящие backend/source safety guards не заменены фикстурой в продукте — они просто не запускались в аудите. Actual producer diagnostic не посчитан эмпирической authority.

Python3.12 не разбирает отдельные полные файлы с Python3.14 `except TypeError, ValueError`. Сохранены два SyntaxError logs. Для bounded replay взяты **неизменённые полные определения** нужных классов из exact line slices, а не преобразованы product files. В третьем запуске ошибочная граница audit slice отрезала return у Envelope.with_update; исправлена только граница loader. Две гипотезы о huge-int исключении оказались неверны и заменены preserving controls. Все исходные failed logs сохранены; финал **25 MATCH/0 ERROR, exit0**. Это не native compatibility test на Python3.14.

[Протокол](../04_Проверки/C23_FUN02/bounded_diagnostics.json) · [команды](../04_Проверки/C23_FUN02/commands.json) · [границы](../04_Проверки/C23_FUN02/Чтение_и_границы.md) · [источники](../05_Источники/C23_источники.json) · [остатки](../01_Реестры/C23_остатки.json).

**23/127 пакетов рассмотрены ограниченно; 60 уникальных B/LA частично оценены; полного закрытия нет.** Все 22 предыдущих packet reports/evidence сохранены. Следующий — **FUN-03 / B161, B163, B164**.
