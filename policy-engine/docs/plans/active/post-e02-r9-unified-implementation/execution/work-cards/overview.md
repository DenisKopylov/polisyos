# R26: сколько работ и как они сгруппированы

Рабочих карточек — **261**, логических групп — **11**. Они раскрывают полный исходный набор из **121 родительской задачи**; родители не прибавляются к этому числу. Карточки разных ролей — реализация, consumer/input, verification и coordination — не равнозначны по трудоёмкости и не являются счётчиком готовых capabilities.

| Группа | Дробных карточек | Для чего нужна |
|---|---:|---|
| [G00 — Вход в программу, интеграция и итоговый допуск](groups/G00.md) | **6** | Принятый E02 → сверенный source/obligation scope → freeze/review/replay → решение о допустимом первом применении. |
| [G01 — Поиск, получение и точная фиксация источников](groups/G01.md) | **20** | Запрос/выбор источника → законный capture/query → immutable representation и provenance → допущенный consumer. |
| [G02 — Смысл оснований: право, метрики, ценности и участники](groups/G02.md) | **23** | Полученные источники → source-bound смысл/единица/время/назначение → typed основание → конкретный design/use. |
| [G03 — Каузальное обоснование и обучаемая модель мира](groups/G03.md) | **21** | Точные наблюдения/гипотезы → идентификация и независимая проверка → bounded effect/knowledge → versioned world update. |
| [G04 — Содержательный поиск политик и перенос опыта](groups/G04.md) | **8** | Intent/основания → разные mechanisms/hypotheses → feedback/acquisition/search choice → полезный следующий candidate. |
| [G05 — Совместные расчёты, траектории и исследования](groups/G05.md) | **22** | Выбранные methods/models/assumptions → native execution/composition → scoped результат/uncertainty → design comparison или новый evidence intake. |
| [G06 — Допустимость, полномочия и квалифицированные решения](groups/G06.md) | **31** | Candidate/evidence/mandate → owner-qualified admission → limitation/refusal/decision → разрешённая claim/surface. |
| [G07 — Долгая custody: актуальность, права и переиздание](groups/G07.md) | **34** | Enrolled dependency/duty → admitted change/expiry/observation → bounded revalidation/reuse/reissue → честный current/history reader. |
| [G08 — Документы, интерфейсы и понятные человеку результаты](groups/G08.md) | **21** | Admitted native output → exact semantic projection/document → authorized audience → edit/history/feedback readback. |
| [G09 — Развёртывание, исполнители, хранилища и ресурсы](groups/G09.md) | **37** | Commissioned profile → native worker/store/permit → bounded actual execution → verified recovery/egress/result. |
| [G10 — Независимые проверки и качество свидетельств](groups/G10.md) | **38** | Полный source-derived scope → independent oracle/negative/removal → exact deciding output → composed acceptance. |
| **Всего** | **261** | Полный текущий набор, без двойного учёта cross-group ссылок |

## Как устроена работа

Каждая карточка имеет один понятный результат, предпочтительный native путь, границу owner, входы, output/consumer и positive/negative/removal. Её parent page показывает место среди siblings и общий join. Входящие связи сохраняют различие между preparation, actual output и окончательной приёмкой.

Для исполнителя entry point — назначенная карточка, не весь каталог. Root/lead держит полную карту original obligations и source pins; leaf читает свой operative context и необходимое замыкание contracts. Сложный неделимый invariant выполняется последовательными checkpoints одним writer, а не несколькими конкурирующими реализациями.

Шесть P0/FINAL карточек — aggregate coordination, а не небольшие code tasks. Распределение всех карточек по ролям: `consumer` — 94, `coordination` — 9, `input` — 19, `mechanism` — 74, `verification` — 65. Это классификация поручений, не дополнительные подразделения системы.

## Что защищает от потерь и путаницы

- Все original parent IDs, source/debt references, extensions и исходные stage/dependency rules сохранены. Exact source fragments имеют accountable routes; составной fragment не считается одним простым требованием.
- Один primary group на карточку. Одна canonical writer/lease boundary на механизм. Cross-group ссылка передаёт результат, а не создаёт вторую реализацию.
- Parent join называет реальные outputs и fresh consumer. Работа, необходимая для join, не прячется в слове «интеграция».
- Context review отдельно от формального счётчика. Число ссылок/UID не доказывает понятность; если operative scope снова перегружен, назначение уточняется без потери source clauses.
- Группы не являются очередью запуска. Независимая подготовка идёт по stage и реальным leases; общий replay остаётся одним, с выбранными кампаниями.

## Что остаётся до исполнения

После фактической приёмки E02 — exact accepted-source rebind, реальные code/generated leases, выбранные supplier artifacts, backend/rights/resource inputs и dispatch grant. Текущие числа описывают эту редакцию плана, не ограничивают free-grow и не обещают столько же одновременных исполнителей. Реализация и продуктовые тесты здесь не запускались.

[Проверка и ограничения](../../assurance/r26-grouping-review.md) · [Все карточки и маршруты](registry.json) · [Исходные source-fragment bindings](coverage.json).
