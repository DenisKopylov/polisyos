# OPT-03 — рабочий warm-start и сохранённое GP-состояние
## C20 · 31 октября 2026 года

**Исходные IDs:** B114, B115. **Порядок:** 20/127, LANE-02. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит; source/tests/config/dependencies не менялись. Далее — OPT-04.

## Решение

**Частичная оценка; исходные механизмы B114 и B115 существенно изменены.** Исторические наблюдения уже входят в общий effective corpus до выбора initial sampling и training subset. Дополнение совместимой выборки использует conditioning обученной модели, а не новый GP с параметрами по умолчанию. Несовместимая база и недоступный conditioning переводят вычисление на явный full refit. Это сохранять.

Остатки не означают, что нужно заново строить warm-start: **C20-R01** — крайний `max_train_size=1` не ограничивает подвыборку из-за `[-0:]`; **C20-R02** — поздно отвергнутый snapshot уже успевает очистить действительную модель и изменить base state. Отдельно остаются native numerical qualification, устаревшее ожидание batch iteration в найденном test и совместимость conditioned-fit с fresh-refit source verifier.

**19 ограниченных observations MATCH, 0 ERROR в итоговом запуске.** Истинный GP, native package, project pytest, CAS и MethodJob не исполнялись. Фикстура theta=7 доказывает только порядок вызовов, не настоящие гиперпараметры, качество posterior или эмпирическую состоятельность.

## 1. Требование и две независимые оси

[Исходный OPT-03](../05_Источники/OPT-03_исходные_строки.txt) требует использовать пригодные уже оплаченные наблюдения и сохранять выученную модель между допустимыми refit. Это два разных свойства: допуск численного основания и экономное обновление модели. Схожесть задачи не является достаточным основанием для переноса чисел.

LLM может выбрать модель и следующий исследовательский шаг. Существующий численный слой должен честно применить именно совместимые данные, сохранить transform/noise basis и объяснить отказ. Отсутствие универсального детерминированного изобретателя моделей здесь не дефект. Полезный generic candidate search не приравнивается к source-admitted native GP и тем более к authority политики.

| ID | Уже сделано — сохранить | Конкретный остаток |
|---|---|---|
| B114 | Общий warm/current corpus; provenance/replicate дедупликация; история отказов; threshold и subset видят историю; штатный bridge и source verifier | C20-R01 для крайних caps; native source→admission→training; точная область стоимости и допустимых replay |
| B115 | Append-only conditioning; сохранённая full-refit граница; refit при изменённом X/Y и при ошибке backend; typed continuation metadata; numerical oracle tests | C20-R02 атомарный отказ snapshot; native learned state/posterior/transform/noise checks; совместимость source verification с conditioning |

## 2. B114: список истории больше не побочное хранилище

`_effective_training_corpus` объединяет `self._warm_evals` и текущие evaluations, отбрасывает недопустимые исходы и несовместимые координаты, сверяет профиль и устраняет повтор одного origin/replica. `suggest` использует его длину до `n_initial`; `_select_training_subset` тоже обращается к нему. Повторное объединение не удваивает строки из-за identity-set. [S01:896–928,1197–1278,1328–1373]

В P01 три исторические и одна новая запись дали четыре selected rows. P02 подал один и тот же origin дважды и через warm/current: повтор остался один; явная новая replica/seed сохранилась. Это не подсчёт независимых эмпирических единиц, а механика заявленной идентичности.

P03 исключил malformed outcome, отсутствие provenance, неверную размерность, другой transform и другой context с пятью разными причинами. P04 сохранил rejection ledger через настоящий `StrategyState.to_artifact/from_artifact`; поля строки были audit dataclass, не native Evaluation. Generic низкоуровневый режим намеренно допускает finite caller-supplied candidate score. Настоящий configured-rule admission здесь не подменён этим режимом. [S01:248–338,864–895]

Самоописанный `configured_native_gp` не даёт права reuse: `warm_start` требует private admission от свежего source verifier; P05 получил отказ `native GP profile lacks fresh fit-basis admission`. Нельзя «починить» warm-start снятием этого отказа. [S01:260–277]

P06 получил одинаковые cold Sobol параметры для whole и warm/current разбиения одного совместимого корпуса. P07 с шестью warm rows вышел из cold phase; при отсутствующем backend выбран честный `random_no_botorch`. Это доказывает влияние истории на порог, но не обучение GP.

## 3. Существующая прикладная цепь, не только отдельный helper

В `WarmStartBridge` обнаруженные похожие runs передаются `TransferLearningManager.get_warm_start_evaluations` вместе с целевым fingerprint. Transfer manager хранит историю версии 5, params, normalized coordinates, objectives, source assessment, provenance и metadata; сопоставляет bounds, split, units, origin, tenant и objective-rule basis. Similarity используется для discovery, не как разрешение numerical reuse. [S04:1–161; S05:58–410]

Далее настоящий `SearchLoopRunner` связывает generator с store и MethodJob run profile, вызывает bridge, затем `warm_start_for_context`. Генератор проверяет actual native optimizer, unit/rule/source receipt и CAS chain перед private admission в optimizer. [S06:1840–1912; S03:286–519]

Для fitted source уже есть `SearchGPFitBasis`, selected training/acquisition refs и source reader. `_recompute_search_gp_fit_basis` разрешает saved bounds/config/backend, перечитывает refs, строит GP и сопоставляет fitted fingerprint/profile; это не простое доверие строке `warm_start_eligible=True`. В этом аудите прочитаны указанные окна verifier, не объявлен полный аудит всех его вложенных функций. [S07:350–465,905–1043,1140–1215]

Найден действительный native test с Source Search→MethodJob→CAS→bridge→target Search: один fitted source observation принят, три начальных не выданы за fitted GP, один target training corpus из трёх строк содержит source ID. Изменение года context при прежних единицах приводит к отказу. Проверка источника имеет typed unit и реальные fit-basis refs. Это значительно сильнее marker-only test, но **здесь прочитано, не исполнено**. [S10:1560–1665,2060–2190]

## 4. B115: обновление без refit не создаёт обученную модель заново

В [S01:1373–1439](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py#L1373-L1439) первоначальный/refit путь вызывает `SingleTaskGP` и `fit_gpytorch_mll`. До плановой границы проверяется настоящий prefix X и Y; изменённый прошлый observation или несовпадающие model inputs требуют refit.

Для append выполняются model.eval, при необходимости prediction cache, затем `condition_on_observations` только на добавленных строках. При исключении происходит bounded full refit. `_model_train_x_matches_fitted` допускает raw или transformed coordinates, а не слепое сравнение разных систем координат. Последняя полная refit iteration/size при успешном conditioning не переписываются. [S01:1373–1493]

| Исполненный контроль с NumPy tensor/model fixtures | Наблюдение |
|---|---|
| Первые 8 строк | constructor → fit, fixture theta=7 |
| Добавлена девятая строка до refit interval | eval → cache → condition; без constructor/fit; 9 строк, прежняя theta и refit boundary |
| Тот же точный корпус | Нет нового factory/fit/condition |
| Изменён прежний Y либо порядок X/Y | constructor → fit |
| Conditioning выдаёт исключение | condition → constructor → fit |
| Достигнут плановый interval | constructor → fit |

Это P11–P17: различающий контроль маршрута существующего `_fit_gp`, не проверка численного закона GPyTorch. Фикстура сама сохраняет theta/transforms; их сохранение настоящим backend ещё надо исполнить. Полезное направление ремонта подтверждено, но ни этот факт, ни отсутствие backend не дают полного закрытия B115.

## 5. Сильные numerical tests уже есть — не подменять их новыми фикстурами

`test_bayesian_no_refit_preserves_learned_gp_state_with_new_observation` работает с настоящим SingleTaskGP, записывает named_parameters и transform state, проверяет девятую строку без второго fit, затем изменение исхода с новым fit. `test_restored_append_preserves_actual_full_refit_boundary_and_learned_basis` проверяет сохранение state и реальную refit boundary. [S08:655–817]

`test_gp_resume_witness.py` содержит независимый NumPy Cholesky posterior для явно проверенных RBFKernel/ConstantMean, сравнивает mean/covariance/UCB, проверяет conditioned checkpoint и target restandardization, а также removal controls: отсутствие load_state_dict и отключение восстановления transform должны разрушить numerical соответствие. Отдельный case допускает действительно наступивший scheduled refit. [S09:1–298]

Это научно содержательная **численная проверка программного GP-профиля**, но не внешняя эмпирическая проверка модели политики. Все указанные tests — UNRUN: нет pytest и Torch/BoTorch. Не требуется новый общий test framework; следующий шаг — исполнить и квалифицировать эти найденные tests на поддержанном runtime.

## 6. C20-R01 — `max_train_size=1` не ограничивает корпус

**Тип:** подтверждённый локальный дефект; **важность:** низкая/средняя при таком config; **уверенность:** высокая локально. [S01:1197–1207]

`recent_n = max_train_size // 2` даёт 0; `filtered[-recent_n:]` становится `filtered[-0:]`, то есть весь корпус. На восьми пригодных строках P08 при cap=4 оставил 4, но P09 при cap=1 оставил 8. P10 при cap=0 также оставил 8. `BayesianConfig` — dataclass без проверки допустимого диапазона; default=512 этим контрпримером не опровергнут.

Последствие — заявленный малый training cap не соблюдается; конкретный production memory/time не измерен. Не нужно менять полезный default subset policy: достаточно определить допустимый диапазон и корректно обработать нулевую recent-часть. Исполнить отличающий test cap=1; cap=0 должен иметь явный контракт, а не молча означать unlimited.

## 7. C20-R02 — поздний отказ snapshot изменяет live state

**Тип:** подтверждённая локальная ошибка атомарности; **важность:** средняя, условная; **уверенность:** высокая для control flow. [S01:1085–1195]

`set_state` делает несколько полезных ранних проверок: objective binding, version, space и full-refit counters. Затем вызывает `super().set_state`, обновляет rejection ledger, обнуляет model/train state и только позднее проверяет наличие/shape/finite fitted corpus и загружает model state.

P19 подал snapshot с корректным заголовком и counters, но без fitted_train_X/Y. При live model и iteration=7 метод выбросил `GP continuation fitted corpus is missing from snapshot`, однако после отказа model уже None, iteration=2. Непрозрачные model bytes не загружались; реальный Torch не использовался. Это точное исполнение порядка операций с NumPy tensor boundary, не доказательство поведения любого повреждённого реального checkpoint.

**Минимальное направление:** проверить и материализовать весь малый новый GP/state набор до замены текущего либо явно определить необратимо закрываемый lifecycle и вернуть его состояние. Существующие ранние отказы сохранять. Нужен test, что отклонённый continuation не уничтожает полезную текущую модель/состояние, а не только `pytest.raises` на пустом fresh owner. Не переносить произвольный state_dict в другую базу ради восстановления.

## 8. Квалификационные границы

**C20-G01 — native acceptance и стоимость.** Не измерены время/память fit против condition и реальная численная эквивалентность. Найденные native witnesses достаточнее fixture theta; их следует использовать, а не объявлять фикстуру эмпирическим доказательством.

**C20-G02 — старое ожидание batch iteration в tests.** В `test_whole_and_warm_split_use_the_same_actual_cold_sobol_plan` ожидание batch iteration=0, тогда как действительный suggest_batch записывает history_count. P18 на трёх строках получил 3. Это локально различённое несовпадение test expectation, а не свидетельство, что весь pytest был запущен и упал. Сохранять раздельность attempted/current/corpus counts; согласовать утверждение test с нынешним контрактом, не возвращать неверный счётчик ради зелёного результата. [S08:354–382; S01:962–981]

**C20-G03 — conditioned GP против fresh full-refit verification.** Рабочая модель после append сохраняет прежние гиперпараметры и transforms. Source verifier заново вызывает `_fit_full_gp` и требует совпадения fitted model fingerprint. Найденный end-to-end native test задаёт refit_interval=1, поэтому не квалифицирует перенос результата из genuinely conditioned model. Нужно различающее native исполнение именно этой комбинации; без него нельзя ни утверждать работоспособный warm reuse после conditioning, ни объявлять научную ошибку. Минимальное направление — согласованный существующий fit/continuation contract, не второй verifier framework. [S01:1397–1422; S07:1149–1171; S10:1575–1577]

## 9. Протокол и преемственность

`probe_opt03.py` сверяет Git blobs, исполняет точные выбранные AST-тела. Generic candidate rows — явная audit dataclass; tensor/model/Torch boundary — NumPy/spy fixtures. Native score/source authority, constructor backend setup и model serialization не исполнялись.

Первый запуск: exit 1, 18 MATCH/1 ERROR. Ошибка была в audit-сравнении tuple до JSON с list после JSON в P04, не в продукте. Сравнение исправлено на одинаковое JSON-представление; исходный лог сохранён. Итог: exit 0, 19 MATCH/0 ERROR. SciPy предупреждение о небалансе неполного Sobol prefix сохранено, не скрыто.

[Протокол](../04_Проверки/C20_OPT03/bounded_diagnostics.json) · [команды](../04_Проверки/C20_OPT03/commands.json) · [границы](../04_Проверки/C20_OPT03/Чтение_и_границы.md) · [источники](../05_Источники/C20_источники.json) · [остатки](../01_Реестры/C20_остатки.json).

**20/127 пакетов рассмотрены ограниченно; 51 уникальный B/LA частично оценён; полного закрытия нет.** 19 предыдущих packet reports/evidence сохранены. Следующий — **OPT-04 / B116, B117**.
