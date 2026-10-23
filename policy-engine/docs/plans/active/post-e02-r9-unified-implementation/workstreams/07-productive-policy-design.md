# DES: содержательный дизайн, обучение и документы

Реализация — только после фактической E02 acceptance и task-scoped rebind. Это дополнение общего плана, не отдельная система. [Карточки всех DES задач и прежних дополнений](../solutions/13-productive-design.md) содержат preferred solution, шаги, native anchors, migration, external inputs и различающие проверки. [Архитектурная связка](../architecture/04-generative-search-learning-and-documents.md).

| Пакет | Единственная ответственность | Самостоятельная подготовка |
|---|---|---|
| DES-01 | Intent/framing → native formulator/N4 | Контракт с UI-05; не ждать всех foundations |
| DES-02 | N4 реальные разные механизмы и hypotheses | Generation/corpus против согласованного intent/invocation interface |
| DES-03 | Scientist structure/parameter trials и совместная оценка | Space/optimizer/oracles; joint/value suppliers нужны при composition |
| DES-04 | N6/N7 фактический feedback/acquisition/retention | Порты и distinguishing examples; не второй scheduler |
| DES-05 | Native Lex multi-norm synthesis и design adapter | Relation interface + разрешённый corpus; CNT-04 поставляет case facts |
| DES-06 | Документ как meaningful bound projection | Общий AST/edit interface, renderer/carrier, private UI |
| DES-07 | Human edit/import → typed patch → recomputation | Параллельно DES-06 после interface; shared schema один writer |
| DES-08 | Existing memory → actual later search influence | Retrieval/applicability/transfer; не ждать O1/O3 activation |
| DES-09 | Общая фактическая LLM invocation/context/trace | Native gateway/egress/budget interfaces; model credentials only for actual call |
| DES-10 | Независимый quality protocol и финальное сравнение | Cases/oracles/reader questions до freeze; исполнение в FINAL-REPLAY |

## Композиция без искусственной последовательности

`depends_on` остаётся preparation graph; DES upstream edges с `interface_agreement` разрешают изолированную подготовку, не приёмку mock вместо actual supplier. Для выбранного end-to-end case нужны фактически произведённые framing → N4 candidates → numerical/joint outcomes → N6 feedback/fronts → document → human edit → new owner result. Legal branch и memory suppliers нужны, если проверяется соответствующая ветвь; необязательный legal use не блокирует иной numeric/design case.

После разрешённого входа параллельно готовятся: intent, invocation, grammar/generation, legal corpus/synthesis, numerical oracle, document rendering/import and quality corpus. Это рабочие направления, не обещание такого же числа одновременно пишущих агентов. `search.py` общий для DES-03/08; formulator/ledger для DES-01/02/08/09; document AST/route для DES-06/07; DTO/generator family общая с Atlas. Root назначает одного writer, остальные передают точные patches/consumer requests. Разные adapters, независимые оракулы и reviews не сериализуются из-за принадлежности к одному пакету.

[Conflict groups](../execution/conflict-groups.json) задаёт пересечения; root связывает их с реальными путями на accepted tree. [Stages](../execution/stage-requirements.json) отделяют owner readiness, composition и obligation disposition. DES-10 готовит проверку до freeze; его финальный outcome не prerequisite собственного FINAL-FREEZE. Все DES readiness входят в общий freeze, затем независимый review и одна общая волна. Дорогое сравнение допустимо шардировать по cases/arms с общим resource budget и frozen identity.

## Непотерянные обязательства

[Десять R14 obligations](../assurance/r14-capability-obligations.json) дополняют, а не заменяют исходные GY/Atlas/debt/R9 inventories. 24 `r14_extension` поля обязательны при назначении прежних tasks. Для старой карточки читается и новая extension. FINAL-USE требует явной disposition обоих наборов; unavailable real-model/reader evidence нельзя спрятать за unit PASS или «candidate-only».

Внешний hold допускается только после проверки, что недостающее — настоящий внешний факт/право/доступ/компетентное суждение, а не ненаписанный native producer или несогласованный внутренний interface. Человеческое участие точечно: реальный мандат, неразрешимая неоднозначность выбора, право/акт или независимая оценка. Не требуется человек для каждого детерминированного semantic binding. Missing participants ограничивают usability claim; внутренний документный механизм можно закончить и проверить отдельно.

Pattern pass: P01/P02/P03/P05/P10/P11/P13/P15/P25/P27/P29/P31–P41. Положительная substantive цепь обязательна наряду с refusal; free-grow проверяется новым conforming ресурсом без search-code edit. Product execution UNRUN; SDD untouched.

Конкретизация shared-writer: DES-01 пишет formulator.py и принимает requests DES-02/08/09; DES-02 пишет hypothesis_ledger.py; DES-09 пишет prompt_tool_ledger.py и native context boundary. Последние два файла не получают параллельных писателей от consumer tasks. Exact paths перепроверяются при rebind.

## R15: две дополнительные native цепи

[DES-11/12](../solutions/14-adaptive-trajectories-and-studies.md) и 28 `r15_extension` обязательны для соответствующих назначений. DES-11 — trajectory producer/evaluator и fresh frontier result; DES-12 — существующий Foundry causal study designer, analysis binding и evidence return. Они готовятся параллельно после E02/scoped rebind, не зависят друг от друга. DES-03 сохраняет общий search writer; DES-04 — acquisition/feedback bridge; GYD-30 — joint evaluation. Новым задачам нельзя параллельно править эти файлы лишь потому, что task IDs различны.

Interface agreement достаточно для native isolated preparation. Composed acceptance требует actual selected suppliers. Numeric EVSI/DEB-13 — только для scientific numeric-value claim; unsupported EVSI не блокирует честный nonnumeric study design. DES-10 готовит R15 cases до freeze и исполняет в той же FINAL-REPLAY. [R15 obligations](../assurance/r15-capability-obligations.json) имеют отдельную disposition; original/R14 требования сохранены. Conditional technology — не универсальная установка всех пакетов.
