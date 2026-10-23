# Post-E02: единая программа R9, GY, Atlas и остаточных долгов

**Дата текущего дополнения:** 23 октября 2026. **Статус:** проект исполнения; продуктовые проверки UNRUN. **Начало реализации:** только после фактической приёмки E02. Предположение «E02 будет полностью завершён» используется для планирования, а не как разрешение начать код.

**Цель:** довести инфраструктуру внешних оснований, незавершённые механизмы PolicyOS и их рабочие поверхности до согласованного, проверяемого состояния; затем обоснованно допустить ограниченное практическое применение. Ограничивается конкретное применение, а не универсальная архитектура или весь объём программы.

Это интегрирующий слой над каноническими планами. Он сохраняет их исторические статусы, связывает остатки с конкретными работами и устраняет дублирование исполнителей. Он не изменяет system-design-decisions, не присваивает closure IDs, не принимает E02 и не объявляет источники атласа допустимыми для реального policy case.

## Как читать

1. [Executive summary R13 — PDF, 10 страниц](executive/summary.pdf), [текст с отметкой версии](executive/summary.md) и дополнения [R14](executive/r14-capabilities.md) / [R15](executive/r15-adaptive-and-models.md) / [R16](executive/r16-composed-models.md).
2. [Границы, источники и правила перехода](execution/01-charter-and-entry.md).
3. [Сверенный остаток](inventory/README.md), [исходные версии](inventory/sources.json), полные GY/Atlas/debt crosswalks.
4. [Архитектура композиции](architecture/01-integration-boundaries.md): кто пишет общий механизм, кто только потребляет.
5. [Пакеты работ](workstreams/README.md) и [машинный план](tasks.json): исходные обязательства, зависимости, пути владельцев, результат, миграция, позитивные и отрицательные проверки.
6. [Предпочтительные решения для всех 121 задач](solutions/index.md), [общие механизмы](solutions/00-shared-decisions.md), [research sources](solutions/sources.md), [самостоятельное review](solutions/root-review.md).
7. [Исполнение и параллельность](execution/02-parallel-execution.md), [волны и критический путь](execution/03-waves.md), [правила изменения плана](execution/04-change-and-rebind.md), [стадии готовности и допуска](execution/05-stage-and-release-contracts.md), [реальные конфликты записи](execution/06-conflicts-and-dispatch.md).
8. [Приёмка](assurance/01-assurance.md), [матрица сценариев R9](inventory/r9-obligations.json), [допуск практического применения](operations/02-practical-use.md).
9. [Развёртывание](operations/01-deployment.md) и [готовые задания](prompts/README.md).

## Что является источником истины

- Исходный статус — канонический GY §8.5, окончательные уточнения owning Atlas slice и точная строка DEBT-REGISTER. Более позднее исправление имеет преимущество перед старой обзорной таблицей; противоречие сохраняется явно.
- Новые рабочие ID и зависимости — `tasks.json`. Подробный документ раскрывает работу; он не создаёт второго scheduler.
- Готовность к dispatch — реальная приёмка E02, полная перепривязка затронутого task/owner closure, требуемая стадия upstream (включая явно согласованный интерфейс), непересекающаяся аренда записи и ресурсы. Глобальный P0 завершает весь census до FINAL-FREEZE; отдельные независимые участки могут начать раньше. Наличие строки или mock недостаточно.
- Готовность capability — настоящая цепь producer → persisted artifact/event → bridge → consumer → verification → surface и семантическая отрицательная проверка.
- Фактическая приёмка — существующее решение G с точно ограниченными source/input/backend/evidence. Файл этого плана не заменяет такое решение.

Все утверждения о коде здесь — ограниченные статические наблюдения на версиях из `inventory/sources.json`. После E02 выполняется адресная перепривязка. Старые документы и выполненные задачи не переписываются для красоты нового плана. Непроверенная граница остаётся `not_established`, а реально отсутствующее звено получает точную capability-метку.

## Параллельность

Предусмотрено до 100 **помощников суммарно**, включая прямых исполнителей, руководителей и их детей; root в этот пользовательский лимит не входит. Будущее исполнение допускает `root → lead → leaf`, если это разрешено runtime и конкретным назначением root. Leaf детей не создаёт. При более строгих runtime-правилах root назначает всех напрямую; текст плана не расширяет полномочия инструмента. Число 100 — ёмкость команды, а не обещание ста одновременных изменений кода. Общий DTO, генератор, семантический owner и интеграционная ветка имеют по одному писателю. Обзоры, независимые оракулы и подготовка разных consumers выполняются параллельно.

Pattern pass: P01/P02/P03, P04/P05/P07/P08/P14/P15, P27/P29/P31–P41. Главные предотвращаемые ошибки: документ вместо capability, повторное исполнение уже закрытого механизма, общий статус вместо точного остатка, параллельные владельцы одного смысла, тест маркеров вместо свойства и предположение о принятом E02 вместо приёмки.


Предыдущая документарная проверка R11: [receipt](assurance/document-validation.json), [независимые review и root dispositions](assurance/review-disposition.md). Future code execution и E02 acceptance остаются отдельными действиями.

Последующий глубокий разбор: [R11 — findings и решения](assurance/redteam-r11-disposition.md), [85 дополнительных обязательств Atlas](inventory/atlas-auxiliary-obligations.json). На этапе R11 manifest содержал 109 задач; новые задания уточняют ранее нераспределённые критерии, не увеличивают исходные debt IDs.

Самостоятельный повторный разбор: [R12 — исправления и границы проверки](assurance/self-review-r12.md), [точные стадии и условные зависимости](execution/07-scoped-readiness.md). [Receipt R12](assurance/self-review-r12-validation.json). Изменения R12 проверены автором документации, без новых субагентов; прежние независимые reviews не выданы за review нового delta.

R13 добавляет конкретные способы реализации, alternatives/tradeoffs, migration, free-grow и falsifiers для каждого task. [Исследование и red-team](solutions/review-disposition.md) и [проверка полного пакета](solutions/validation.json). [Два нормативных уточнения](solutions/decision-clarifications.md) подготовлены без изменения SDD: AS2 comparator и фактическая активация WP-01/02. Обычные инженерные отклонения разрешены при evidence-bound обосновании и сохранении исходного свойства.

## R14: содержательный поиск, обучение, право и документы

На этапе R14 manifest содержал 119 task objects: прежние 109 сохранены, добавлены DES-01–10; 24 прежние строки получили явный additive scope. Это число задач/контрольных точек, не независимых capabilities и не оценка длительности. [Архитектурное решение](architecture/04-generative-search-learning-and-documents.md), [аудит конкретных пробелов](assurance/07-r14-capability-audit.md), [10 решений и 24 дополнения](solutions/13-productive-design.md), [качество](assurance/08-productive-search-and-document-quality.md), [организация работы](workstreams/07-productive-policy-design.md).

R13 receipts и PDF — исторический снимок до R14; их hashes не проверяют новый delta. Актуальная документарная проверка и review: [R14 disposition](assurance/r14-review-disposition.md), [validation](assurance/r14-validation.json). Ни E02, ни runtime результаты этой документацией не принимаются.

## R15: адаптивные траектории, исследовательский дизайн и методы

Актуальный manifest содержит **121 task object**: DES-11/12 добавлены к полным 119 предыдущим; **28 существующих строк** имеют обязательные `r15_extension`. Это не число независимых engines. [Две implementation cards](solutions/14-adaptive-trajectories-and-studies.md), [восемь технических профилей](solutions/15-technical-method-lifecycle.md), [full-cycle архитектура](architecture/05-adaptive-design-and-research.md), [semantic acceptance](assurance/09-adaptive-research-and-method-quality.md), [обязательства](assurance/r15-capability-obligations.json), [редтим/root review](assurance/r15-review-disposition.md) и [документарная проверка](assurance/r15-validation.json).

Отдельное [исследование совместного исполнения разнородных моделей](research/heterogeneous-model-execution.md) выбирает native DAG/fixed-point reuse и условные дальнейшие extensions; оно не вводит новый обязательный simulator или SDD. R13 PDF и R14 receipts сохранены как исторические версии; актуальное executive дополнение — [R15](executive/r15-adaptive-and-models.md). Реализация по-прежнему только после приёмки E02.

## R16: неоднородные модели и пересчёт

[Executive R16](executive/r16-composed-models.md), [архитектура](architecture/06-composition-and-reexecution.md), [восемь исполнимых slices](solutions/16-composed-execution-and-revisions.md), [17 quality cases](assurance/10-composition-reexecution-quality.md), [dispatch](execution/08-composition-stages.md), [исследование](research/composition-reexecution-r16.md), [independent redteam и root review](assurance/r16-review.md). `r16_extension` дополняет 28 из 121 задач; обязательства зеркальны в preferred-solutions. Новый scheduler и новый root task не создаются. Реализация только после E02; продуктовые проверки UNRUN.

## R17: долгосрочная жизнь дизайна, преемственность и доступ

[Executive R17](executive/r17-design-lifetimes.md), [сохранение](architecture/07-completed-design-custody.md), [действующая политика и преемственность](architecture/08-incumbent-policy-succession.md), [изоляция/доступ](architecture/09-design-isolation-and-access.md), [D1–D7 решения](solutions/17-design-custody-and-succession.md), [Q01–Q18](assurance/11-design-custody-succession-access.md), [dispatch](execution/09-design-lifetimes-and-access.md), [исследование](research/design-custody-succession-access-r17.md), [review](assurance/r17-review.md) и [doc validation](assurance/r17-validation.json). 41 из 121 task objects получили additive `r17_extension`; все прежние criteria сохранены, mirror проверяется по полному множеству. Новые root tasks/глобальные dependency barriers не введены. Реализация только после фактической приёмки E02; product execution UNRUN.
