# Одна задача дизайна — несколько оснований

Мысленный пример, 2026-10-20. Числа синтетические. Это не оценка реальной политики, не causal receipt и не универсальный шаблон.

---

## 1. Вопрос задачи

Предположим, principal просит разработать изменение доходной поддержки, которое улучшит положение уязвимых людей при определённых фискальных и правовых ограничениях. Даже такая формулировка ещё не задаёт точный objective: нужно установить, кто считается уязвимым, какой income concept используется, чей горизонт важен и какие tradeoffs допускаются.

Одна задача может породить несколько обоснованных постановок, а внутри них — несколько policy candidates. Смена постановки сохраняется как явная ветвь, а не как незаметная подмена результата.

## 2. Какие основания могут различаться

| Ось | Возможные основания | Что требуется перед сравнением |
| --- | --- | --- |
| Наблюдения | Survey microdata, administrative records, qualitative implementation evidence | Coverage, period, rights, linkage, measurement differences |
| Доход | Market income, disposable income, consumption proxy | Definition, taxes/transfers/in-kind items, price basis |
| Единица | Person, household, equivalent adult | Aggregation/weighting and equivalence-scale convention |
| Причинность | Разные механизмы take-up, labour response, spillovers | Identification assumptions и связь lever→actual change |
| Неравенство | Gini, Atkinson с указанным параметром, tail shares | Формула, domain, цель и explicit choice rationale |
| Бедность | Relative line, nationally defined line, international monitoring line | Scope и правило исчисления; не подмена benefit eligibility |
| Время | Current costs, lifetime impacts, разные appraisal conventions | Horizon, price adjustment, discount convention и sensitivity |
| Право | Применимая норма; её обоснованные competing interpretations | Jurisdiction/version/governing correspondence; новая норма требует reform scenario |
| Ценности | Среднее благосостояние, приоритет худшему положению, rights constraints | Principal, mandate, explicit conditional frame и dissent |
| Исполнение | Разные delivery channels, staffing, compliance | Реальные capacity/permission inputs, uncertainty и actor responsibility |

Множество комбинаций не является декартовым произведением. Income definition и equivalence rule должны быть совместимы; модель переноса требует соответствующего target context. Несовместимая комбинация не становится ещё одним голосом в multiverse.

## 3. Конкретный reversal только от метрики

Рассмотрим пять людей с равными весами и положительными доходами в одной условной единице. Не вводим ни household equivalence, ни survey inference, ни причинное утверждение.

| Распределение | Доходы | Среднее | Gini | Atkinson, ε = 2 |
| --- | --- | ---: | ---: | ---: |
| A | 1; 2; 3; 4; 10 | 4 | 0,400 | ≈ 0,4275 |
| B | 0,5; 3; 4; 5; 7,5 | 4 | 0,320 | ≈ 0,5714 |

Для этой конечной совокупности используется `G = ΣᵢΣⱼ |yᵢ − yⱼ| / (2 n² μ)`, без sample correction. Для положительных доходов при ε=2: `A₂ = 1 − 1 / (μ × mean(1/y))`. Значения A₂ равны соответственно `56/131` и `4/7`; это позволяет проверить арифметику независимо от округления.

По Gini B менее неравно. По Atkinson с ε=2 B более неравно: потере самого бедного здесь придаётся больший вес. Ни один результат не является вычислительной ошибкой. Без указания вопроса и выбора convention утверждение «B уменьшает неравенство» скрывает существенную зависимость.

Источник методологического направления — [S-MEASURE-02 в каталоге](../sources.json), с явно ограниченным доступом к UNECE handbook; приведённая арифметика — собственный иллюстративный вывод по указанным формулам. Здесь не утверждается, что исходный handbook был полностью проверен, что ε=2 авторизован principal или что любой policy intervention действительно создаст B.

## 4. Что система должна показать

Результат полезнее единственного рейтинга:

- при declared Gini objective B предпочтительнее A по данному измерению;
- при declared Atkinson ε=2 objective A предпочтительнее B;
- среднее одинаково, но положение самого бедного ухудшено в B;
- ranking зависит от normative/measurement choice; выбор principal пока не установлен;
- causal effect, feasibility, applicable law и distributional uncertainty не оценены этим расчётом.

Если несколько authorized objectives конфликтуют, можно показать tradeoff/Pareto relation в их объявленном пространстве. Это не разрешает усреднить их веса или заменить некомпенсируемое ограничение компенсацией. Для числа «общее улучшение» потребуется отдельно обоснованное правило сравнения.

## 5. Поиск и обучение внутри этой задачи

Сначала exploratory поиск обнаруживает income concepts, метрики, causal mechanisms и возможные policy levers. Результаты могут изменить вопрос. Для подтверждающего исследования выбирается и сохраняется конкретный portfolio с inclusion/exclusion, mandatory checks, synthesis и stopping design. Если после просмотра результатов добавлена новая метрика, она остаётся новым exploratory branch, пока не выполнено подходящее подтверждение; дата записи сама по себе не устраняет selection.

Две модели могут одинаково объяснять наблюдаемые доходы и по-разному предсказывать реакцию на изменение выплат. Это причина искать различающее свидетельство, bounds или robust decision, а не усреднить прогнозы без основания. VOI может выбрать изучение take-up или measurement validity, если именно оно меняет решение. Юридическое полномочие нельзя заменить измерением дополнительных доходов.

После реального внешнего исполнения система сравнивает outcome с прогнозом, но сначала различает неисполнение, изменённое измерение, внешний shock и ошибку causal mechanism. До разрешённого диагноза не выполняется causal update. При этом можно улучшать discovery hints или записывать наблюдение в допустимом candidate scope.

## 6. След, который остаётся обозримым

Будущая task basis связывает: вопрос/версию → выбранные source refs → definitions и conventions → исполненный method/run → output → claim и его ограничения. Отдельно сохраняются отвергнутые альтернативы, причины выбора, relation evidence и audience restrictions. Source correction может потребовать пересчитать конкретный claim; смена value mandate создаёт другой decision context и не переписывает прежнюю арифметику.

Пример является falsifier для системы: если после metric reversal она продолжает публиковать безусловное «неравенство снизилось», проблема в consumer/surface или смысловом binding, даже когда обе формулы вычислены правильно. Это будущий semantic test, не выполненный здесь runtime тест.
