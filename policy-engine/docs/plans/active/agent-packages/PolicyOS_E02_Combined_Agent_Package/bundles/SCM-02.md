# SCM-02 — Factual abduction и две явные стороны attribution

**E02 · окно CP5 · локальная проверка N · начальный статус planned.**

**B:** B215, B223. **LA:** Нет; технический пакет B.

**Предшественники:** [SCM-01](../bundles/SCM-01.md). **Совместная очередь:** LANE-05.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Отделить фактически наблюдённых родителей от model-imputed values. Для поддержанного linear-Gaussian partial evidence использовать условный закон noises; полный invertible factual input сохраняет точную residual-инверсию. Явно представить target и comparator, различив no-override и observational baseline.

**Различающие тесты и сохраняемое поведение.** X=Ux, Y=X+Uy, evidenceY=2, doX=0 даёт mean=1/variance=0.5 в поддержанном Gaussian-контроле, а полное X=1, Y=2 —Y(0)=1. Для Y=1+3X targetX=2/baselineX=0 контраст 6, не 0; одинаковые явные стороны дают 0. Shared-U и независимые межмировые выборки не смешиваются.

**Не считать исправлением.** Не считать подставленное среднее наблюдением, не подменять counterfactual обычным intervention и не трактовать None одновременно как наследование и отмену.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py
policy-engine/src/polisyos/foundry/methods/catalog/causal/twin_network_query.py
policy-engine/src/polisyos/ir/analytics/causal_queries.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/ir/analytics/structural_causal_model.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_scm_02.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** GRF-03, SCM-01, SCM-03. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Условия общего использования:**

**A07.** Active-query pruning сохраняет правильную surgery, immutable topology, factual ancestors и shared-noise/replica semantics. Частичный temporal/PAG профиль не присваивается статическому успеху.

**Ресурс:** N/C — I1 broker drains L and admits one exclusive native/numerical/build or checkpoint job using the full seven-unit budget; no other resource-bearing job runs concurrently. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без permit. Immutable argv/cwd/worktree/SHA/selectors/timeout/output root and named resources are fixed at admission; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное основание B215

Источник B_r19, строки 5230–5243; полный неизменённый текст.

<!-- SOURCE_BEGIN B:B215 -->
## B215. Абдукция принимает подставленное среднее скрытого родителя за наблюдённый факт

**Приоритет:** высокий для контрфактуала с неполным factual context; точный линейно-Gaussian путь возможен без универсального sampler. **Основание:** _abduce_linear_noises и _simulate_samples; CF01–CF03. [C20.R11–R12, C20.E05]

**Проблема.** Перед восстановлением шума ненаблюдаемые узлы заполняются линейным предсказанием или нулём. Проверка all(parent in pseudo_observed) затем считает их известными и вычисляет один residual для наблюдённого потомка. При counterfactual simulation этот residual фиксируется вместо условного распределения экзогенных переменных.

**Воспроизведение.** SCM: X=Ux, Y=X+Uy, независимые Ux,Uy~N(0,1). Factual evidence содержит только Y=2, запрос do(X=0). Точный Gaussian conditioning даёт Uy|Y=2 со средним 1 и дисперсией 0,5. Исходная абдукция подставила X=0, восстановила Uy=2; 100 контрфактических реализаций дали среднее 2 и дисперсию 0. При полном наблюдении X=1,Y=2 контроль правильно даёт детерминированный Y(0)=1.

**Рекомендуемое исправление.** Различать фактически наблюдённых родителей и модельно восстановленные значения. Когда invertible-механизм и все необходимые factual inputs действительно известны, использовать существующую точную residual-инверсию. В линейно-Gaussian случае с неполным наблюдением решать условную Gaussian-задачу; в общем случае нужна явная поддержанная posterior-abduction либо ограничение соответствующего контрфактуала. Фиксировать одну и ту же posterior-noise реализацию для сравниваемых миров и хранить её происхождение.

**Экономия.** Для линейного случая условную факторизацию можно подготовить один раз для заданного observation pattern и модели, затем переиспользовать векторизованные реализации. Увеличение числа draws исходного детерминированного residual только повторит неверную точку. Не нужно запрещать все counterfactuals либо подменять factual-condition обычным intervention-запросом.

**Граница.** Исполнены выбранные настоящие traversal/abduction/sample-loop тела, но механизм ограничен явно тестовым LINEAR/ATOMIC backend и небольшими DTO. Полные GCMQuery/twin-network, проверка идентификации SCM, native query-result и CAS не запускались. Формула контрольного Gaussian-conditioning рассчитана напрямую; это не inference из реальных социальных данных.

<!-- SOURCE_END B:B215 -->

## Исходное основание B223

Источник B_r19, строки 5431–5444; полный неизменённый текст.

<!-- SOURCE_BEGIN B:B223 -->
## B223. Attribution вычитает одно и то же вмешательство из самого себя

**Происхождение и приоритет:** C21-08. Высокий; локальная правка интерфейса режима. Основания: ветвь ATTRIBUTION и `_simulate_samples`/`_effective_intervention`. [C21.R05]

**Проблема.** Основная attribution-ветвь передаёт целевое intervention. Для baseline передаётся `intervention_override=None`, но query остаётся INTERVENTIONAL с прежним treatment_value. В sampler None означает «взять эффективное вмешательство из query», а не «не вмешиваться». Оба вычисления поэтому получают один do-режим.

**ATTR01.** В детерминированной модели Y=1+3X и запросе X=2 все сто treated- и baseline-реализаций имеют X=2, Y=7. Средний контраст равен нулю. Явный baseline do(X=0) даёт правильный контраст 6. Проверены две настоящие выбранные ветви вызова, а не native CausalQueryResult или registry.

**Исправление.** Разделить отсутствие override, явный observational-режим и явное альтернативное вмешательство. Лучше представлять две разрешённые стороны контраста отдельно: целевой режим, baseline, популяция, исход и соответствующее состояние мира. Значение `None` не должно одновременно обозначать «унаследовать» и «отменить» действие.

После этой правки нужно сохранить смысл статистики: разность средних независимых межмировых выборок и распределение индивидуальных эффектов с общими U — разные объекты. Уже существующий twin-network реализует shared-noise путь; его можно использовать при соответствующих предпосылках, а не строить новый движок.

**Приёмка.** Известный ненулевой линейный эффект, одинаковые явно заданные режимы с нулевым контрастом, observational baseline и стохастическая политика с определённым сравнением. Сохранять оба query-ref в результате. Исправление не устанавливает, что конкретное вмешательство эмпирически идентифицировано: оно делает исполняемый контраст соответствующим запросу.

<!-- SOURCE_END B:B223 -->

