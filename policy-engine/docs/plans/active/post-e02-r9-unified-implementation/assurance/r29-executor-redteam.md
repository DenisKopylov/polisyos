# R29: редтим R28 с позиции будущего исполнителя

Base: `dff86303a023ae75ed49b914eaeacb18813539ee`. Это исправление документации,
не реализация, E02 acceptance или adjudication findings. Task/preferred manifests
сохраняют прежние immutable bytes. Актуальный вход для исполнителя —
[guide](../execution/work-cards/executor-guide.md), назначенная карточка и
заполненный [packet](../execution/task-decomposition/work-packet.md).

## Что проверяли

Шесть прямых независимых reviewer-разрезов: вход и все role prompts; P0/FINAL;
DEB-01–07; DEB-08–14; содержательная композиция; машинные и читаемые маршруты.
Reviewer работали без детей и без продуктовых изменений; tracked-правки
делал root. Повторный review проверяет только исправленный delta. После него
устранены два найденных несовпадения rendering/registry; их повторная сверка
завершилась bounded GO. Предел каждого review сохранён отдельно.

Содержательное чтение карточек охватило весь набор первых действий R28 и
соседний CNT-05.mandate-choice: 53 разные Markdown-карточки. Это ограниченный
семантический denominator, не утверждение о новом подробном аудите всех 262
карточек. Полная структурная сверка проходит все 262 карточки, 121 parent,
coverage/routes, immutable manifests и локальные ссылки отдельно. Результаты
такой сверки не заменяют содержательное чтение linked contracts.

## Найденное и исправленное

| ID | Конкретная проблема | Решение для исполнителя |
|---|---|---|
| R29-F01 | P0-ACCEPT можно прочесть как ожидание rebind, который потребляет её собственный output | Карточка прямо разрешает read-only чтение уже выданного G решения; root назначает lease на existing journal. Отсутствие решения не заменяется шаблоном, продуктовый entry не открывается. Это устранение неоднозначности, не новый процесс приёмки. |
| R29-F02 | Запрет заменять supplier stub мог запрещать и полезную isolated preparation | Fixtures допустимы по реальному pinned interface agreement в test scope. Preparation evidence не заменяет actual persisted supplier output для composition/protected use/acceptance; supplier lease не передаётся. |
| R29-F03 | Заголовок removal смешивал code mutation, подмену evidence и documentary corruption; запрет verifier менять producer не называл изоляцию | Общий guide и prompts различают изменяемый объект и наблюдение. Source-required binding substitution оставляет verifier включённым. Code removal имеет paired baseline/mutant и внешний неизменный oracle; setup crash не является успехом контроля. Redundant guards не обязаны каждый поодиночке быть незаменимыми. |
| R29-F04 | DEB-06 negative не раскрывал две исходные границы merge | Добавлены unrelated predecessor bases и stale merge origin с точной причиной limitation/refusal; valid merge positive и остальные случаи сохранены. |
| R29-F05 | DEB-09 Q02 был назначен delegation-mandate, но её первые действия описывали DS15 вместо полномочия human principal на SDD amendment | Две отдельные purpose-bound evidence rows. Для Q02 сначала поиск accepted history, затем identity/exact act/scope/time/revocation/challenge. Неустановленное standing оставляет amendment предложением; работа по действующим правилам продолжается. Parent handoff включает существующий amendment process и условный FINAL-USE. |
| R29-F06 | DEB-13 показывал likelihood probe, но не все назначенные owner/measure/cost controls; commissioning оставался слишком абстрактным | Назван Atlas/DS15 scope owner с P0/root и конкретный fallback DEB-13: исследовать/предложить extension native owner. Добавлены zero-information oracle/tolerance, owner/measure/cost/capacity falsifiers и labeled conditional gross EVSI. Реальный набор residual rows перечисляется заново; исторические 15 не становятся лимитом или all-or-nothing gate. |
| R29-F07 | OPS-05 `witness or fence` позволял ограничиться missing-witness refusal | Отдельные reconciliation и intervening-withdrawal fence сценарии с доступными inputs. Baseline допускает обоснованный scope, mutant проверяется на фактическом false-current. Blanket quarantine не считается positive. |
| R29-F08 | Primary route скрывал составного исполнителя в CNT-05 U003 и CAP-04 U062 | Сохранены primary receivers. `clause_uses` явно поручает сохранение prior choice существующему mandate-choice; уже названные CAP-04 native-events/currentness-join получают execute подрезультаты вместо только binding. Conditions и LIF-02 ownership сохраняются. |
| R29-F09 | Возможно чрезмерное чтение внешнего authority hold и различия ролей | DEB-09 policy-signer явно сохраняет candidate construction. W5 допускает одного института в разных ролях при explicit mandate и отдельных bindings, сохраняя требуемую независимость history holder. Это уточнения, не признанные новые product defects. |

Точные источники исправлений: `DEB-06.task.adversarial`;
`DEB-09.task.r19_extension.question_slices[0]` с actual ID `R18-D23-Q02` и
[S18-M2 / решение Q02](../solutions/lifecycle-r19/S18.md#r18-d23-q02);
`DEB-13.task.removal`, `solution.implementation_steps[0]`,
`solution.acceptance_discriminators[4]` и
[R18-D09-Q04](../solutions/lifecycle-r19/S09.md#r18-d09-q04);
`OPS-05.task.acceptance_steps[4]`; `CNT-05.task.positive`;
`CAP-04.task.r19_extension.question_slices[3]` с actual ID `R18-D22-Q04`.
Selectors разрешаются по parent ID и pinned blobs из
[coverage](../execution/work-cards/coverage.json), не по позиции parent в массиве.

## Самостоятельное решение root после редтима

Повторение одного класса остановлено общей нормой вместо нового слоя per-card
gates. Для compound fragment primary accountability не присваивает все native
leases. `execute` subclause называет существующий конкретный output; `binding`
сохраняет ограничение и не выдаётся за исполнение. По этой норме сверены два
найденных сложных маршрута, их parent joins и читаемые карточки.

Не принят механический совет «везде удалять code guard». DEB-08 receipt binding
и DEB-14 scope evidence имеют исходные falsifiers с действующим verifier;
они сохраняются. Для mechanism removal нужна причинная связь между отключённым
свойством и нарушенным oracle. Реальная exception может быть наблюдением
нарушения, но exit/signal или ошибка setup сами по себе этого не устанавливают.

Не введены обязательные внешние разрешения для ordinary engineering, полностью
заданного hypothetical calculation, accepted-history lookup или isolated fixture
под действующим assignment. Actual institutional authority, empirical grounding
и source rights не получаются от synthetic positive. Missing cost и capacity
ограничивают свои claims, а не всякий численный результат.

DEB-09 не разделяется ещё раз: два условных evidence uses имеют общий intake
порядок, но отдельные rows, проверки и consumers. Это не новая implementation
роль или succession service. DEB-13 остаётся связной formula→artifact→consumer
задачей с четырьмя checkpoint-действиями; эти действия не добавляют DAG edges.

## Сохранность и границы результата

Новых task IDs, карточек, групп, primary receiver moves, direct dependencies,
after-card edges, lease namespaces, product enums или SDD edits нет. Сохраняются
все исходные fragments и constraints. Добавлено одно supplemental clause use
для CNT-05; два существующих CAP-04 uses уточнены `binding → execute`. Изменение
DEB-09 parent join раскрывает уже назначенный Q02, не новую зависимость.

[Документарная validation R29](r29-validation.json) завершилась PASS: 7 196 primary
fragments и 3 711 inherited fields сохранены; supplemental clause uses — 259
(было 258), original direct edges — 368, consumption routes — 471. Это количества
полного JSON/Markdown denominator, не число доказанных capabilities. Validation сверяет source bytes и каждый UID/selector, value-based
question identity, secondary subclauses и их rendering, parent joins, неизменные
стадии/DAG/lease contracts и все локальные file links в своём полном denominator.
Число первых шагов фиксируется для сохранности, но не используется как лимит
допуска: маленькая карточка тоже может потерять требование.

Reviewer verdicts и полный output лёгкой validation сохраняются в локальном
ignored `_build/post-e02-r29-redteam-20261024`; компактный receipt хранится рядом
с этим документом. Эти ignored источники — provenance review, не будущие dispatch
inputs. На другом checkout operative источники — tracked карточки/manifests,
принятый E02 source и actual packet/journal.

Все предметные product positives, negatives, mutation controls и actual
source/path/lease binding остаются будущей работой. Документарный GO не доказывает
реальность runtime chain и не гарантирует отсутствия иных семантических пробелов.
Реализация и продуктовые тесты до E02 acceptance не начаты; тяжёлых процессов нет.

Pattern pass: P01/P02 (реальная цепь), P04/P05 (условный результат и authority),
P13/P39 (контекст без скрытой нагрузки), P27/P31 (canonical writer),
P29/P32/P33/P37/P38 (наблюдаемое свойство и experiment type),
P35/P36 (полный структурный denominator и точный source), P40/P41 (class fix и
честные границы проверки). Target — исполнитель понимает первое действие,
свой output, чужую обязанность и различающую проверку без усечения criterion.
