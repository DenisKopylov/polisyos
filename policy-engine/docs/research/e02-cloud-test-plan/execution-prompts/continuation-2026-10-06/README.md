# E02: шесть поручений продолжения после публикации main

G опубликовал код, пакет решений и publication companions в `origin/main`
на `1ddcd7b3905e52c0d19db091823a64830139fa64` (tree
`498ff43267dfceaacdeb8de92b1e79cb38a44316`). Это минимальный anchor новой базы;
фактическую базу каждого slice берите из свежего `git fetch origin`,
проверяя ancestry и записывая её SHA/tree. Этот каталог добавлен следующим
append-only коммитом. Старые локальные исследовательские ветки не являются базой.

Каждый файл ниже — отдельный готовый промпт для соответствующего оркестратора.
Все входные инструкции и решения доступны в Git. Перед работой полностью
прочитайте root `AGENTS.md`, `policy-engine/CONTRIBUTING.md` и
[HANDOFF](../HANDOFF.md); admission проверяйте для реальной точной branch/path.

| Агент | Среда | Готовый промпт | Полная очередь решений | Bundles / findings |
| --- | --- | --- | --- | --- |
| A | Локальная | [A](A.md) | [Решения A](../../closure-decisions/A.md) | 13 / 34 |
| B | Облачная | [B](B.md) | [Решения B](../../closure-decisions/B.md) | 25 / 60 |
| C | Локальная | [C](C.md) | [Решения C](../../closure-decisions/C.md) | 33 / 54 |
| D | Облачная | [D](D.md) | [Решения D](../../closure-decisions/D.md) | 17 / 45 |
| E | Облачная | [E](E.md) | [Решения E](../../closure-decisions/E.md) | 22 / 54 |
| F | Облачная | [F](F.md) | [Решения F](../../closure-decisions/F.md) | 17 / 35 |

Знаменатель таблицы пересчитан из полного `bundle-owners.tsv` и
`finding-owners.tsv` в [execution-organization](../../execution-organization/README.md):
127 bundle rows, 282 finding rows. Полные исходные criteria и ownership
обязательны; короткая failure query не заменяет их.

После importer `--check` используйте [пакет решений](../../closure-decisions/README.md),
[выбранные методы](../../closure-decisions/method-decisions.md),
[runtime profiles](../../closure-decisions/runtime-profiles.md),
[semantic decisions](../../closure-decisions/semantic-decisions.md),
[контракты](../../closure-decisions/cross-unit-contracts.md) и
[порядок проверки](../../closure-decisions/verification-and-closeout.md).
Промпт задаёт исполнение всей очереди, включая реальные методы и consumers;
ещё один bounded checkpoint не завершает исходный критерий.

Будущая публикация в `main` требует отдельной явной авторизации пользователя
для конкретной публикации. Разрешение на этот checkpoint и его prompts не
является постоянным. G остаётся единственным publisher integration. A–F push-ят только свои topic
ветки/PR и committed handoff JSON; G fetch-ит точные refs, принимает код и
closure finding раздельно. Уже принятые предки не применяйте заново.
Четыре implementation edges: A/CYC-01→E/FRC-01, A/EMP-01→E/FRC-02,
A/CYC-02→B/RES-03, B/NET-01→C/ING-02. B↔C read-impact cycle требует
reconciliation затронутых consumers, но не ожидания завершения всей чужой очереди.

A/C/G используют одну локальную очередь тяжёлых прогонов; этот лимит не
переносится в cloud B/D/E/F. Production data остаётся локально read-only и
нужна только intrinsically data-dependent criteria. Сгенерированные повторимые
каталоги после сохранения deciding outputs можно перемещать только в Корзину;
Корзину агенты не очищают. Код, полезная документация и уникальные данные сохраняются.

[Publication record](../../integration/publication-2026-10-06.md) фиксирует
459 scoped passing cases и оставшиеся красные architecture/runtime API gates.
Это рабочая база продолжения, не E02 closeout и не CI-green. Finding outcomes,
check outcomes, unavailable inputs и skipped backends должны остаться раздельными.

Pattern pass: P01/P02/P03 — довести цепочку до consumer/surface; P05/P15 —
не подписывать candidate; P29/P32/P37/P38 — независимый runtime discriminator;
P35 — полный знаменатель; P40 — исправлять класс либо объявлять конечный residual;
P41 — атрибутировать red только по exact slice-base replay. Acceptance поручения:
вся owner-очередь получает row-level решение с реальным deciding evidence,
а не только план, refusal или число PASS.
