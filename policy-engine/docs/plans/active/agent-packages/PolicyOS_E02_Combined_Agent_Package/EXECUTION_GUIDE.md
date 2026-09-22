# PolicyOS — совместная исполнительская редакция E02

**S02/r19 + L01/r09 · 19 сентября 2026 года · 127 рабочих пакетов.**

## 1. Что изменено и что является основанием

План объединяет **225 технических B-находок и 57 самостоятельных LA-карточек решений**. Это 282 исходных записи разных типов, не 282 подтверждённых production-багa. **Восемь S-направлений развития** остаются отдельными и не включаются автоматически в реализацию. **36 K-разграничений legacy-аудита** становятся защищаемыми ограничениями LK01–LK36; их исходный текст и номера K сохранены.

База обоих аудитов — `5fd3ebcc15637e98bbd4938de5d62ee5004504a8`. В E02 выполнены полный разбор предоставленного legacy-текста, сопоставление с E01 и подготовка плана. **Актуальный HEAD, код PolicyOS, CI и Mac пользователя в этой работе не испытывались.** Точные source bytes, SHA-256, строки и поздние уточнения сохранены в `source/`. Прежние E01 Markdown/ZIP/guide находятся в `parent/` как история, не как второй активный план.

Распределение и последовательности E02 — инженерные решения организации, а не новые выводы исходных аудитов. Предлагаемые новые пути не объявлены существующими. Evidence-архивы legacy-аудита, source snapshots и probes, упомянутые в исторических разделах, отдельно не переданы: **они не включены как будто полученные или повторно исполненные**. Для native регрессии достаточно построить малый тест из описанного контрпримера на реальном checkout.

Sol и Luna — выбранные пользователем роли; документ не задаёт фактические model IDs, reasoning/API параметры или конфиг Codex. Инференс моделей предполагается в используемом удалённом сервисе; локальные ресурсы ограничиваются инструментами и тестами на Mac.

## 2. Команда без дополнительных руководящих агентов

| Роль | Целевое число | Эластичность |
|---|---:|---|
| Исполнители пакетов | 8 | preparer может стать девятым executor |
| Независимые reviewers | 3 | executor/preparer может стать четвёртым при backlog=4 |
| I2/preparers | 2 | число меняется по готовому буферу |
| I1 broker | 1 | единственный владелец общей вычислительной очереди |
| Integration writer | 1 | последовательная запись integration branch |
| **Прямые leaf workers (confirmed target)** | **15** | **не считая Sol; при меньшей фактической ёмкости роли эластично перераспределяются; без субагентов** |

Sol диспетчеризует одну очередь B+LA, утверждает write-set, решения о совместимости и приёмку. Исполнитель получает один умеренный пакет и отдельный branch/worktree/base SHA; следующий пакет можно передать новому агенту без огромного накопленного контекста. Если runtime даёт меньше seats, используется максимум доступных с сохранением review independence/write isolation, а предел записывается. Subagents — leaf workers, новых своих агентов не создают. Нет 127 одновременно открытых worktree.

**I1** единолично ведёт integration branch, merge queue, глобальную test queue, подготовку среды и CP-окна. **I2** проверяет cross-boundary contracts, совместимость миграций, path map, исторические readers и review общих DTO. I2 не правит production-файл параллельно его исполнителю; glue patch требует своего write-set и review. Проверяющий не автор принимаемого patch; другой агент обеспечивает процедурную независимость, не независимость ошибок моделей или внешнюю сертификацию.

## 3. Один связанный поток вместо «сначала B, потом cleanup»

127 пакетов — атомы выдачи. **12 migration lanes** — подсказки совместного планирования, а не 12 гигантских поручений, общие блокировки или новые обязательные фазы. Все 84 прежних ID сохранены; шесть B-находок перенесены в четыре более точных пакета. Остальная новая работа добавлена без перенумерации исходных находок.

Примеры обязательного совмещения: B12 + LA-046 → ACQ-01; B32 + LA-051 → FRC-01; B118/119 + выделение run-state LA-015 → CTL-01; B146 + observation часть LA-031 → OBS-01; B14/40/69/95 + точечная LA-057 → RUN-01; DiD численные repairs с LA-016 → CAU-01 и последующий CAU-05. Разные механизмы со сходным названием не объединяются только ради меньшего числа файлов.

Большие LA-области имеют несколько конечных этапов. `legacy_to_bundles.json` задаёт их состав и **одного accountable closure owner**. Завершение первого этапа не закрывает карточку целиком. Например, отсутствие ложного сообщения об обучении в PLG-02 не означает появление реального trainer bridge PLG-03; честный no-calibration в FRC-01 не означает готовность FRC-02. Состояние `compatibility_pending` или `bridge_pending` сохраняется отдельно, без остановки независимой работы.

## 4. Реализация и перенос в одном поручении, но не в одном неразличимом diff

Для пакета с relocation сначала снять нужный **characterization corpus**. Коммит переноса сохраняет valid bytes, значения, ошибки, роль данных, RNG и supported API. Следующий исправляющий коммит меняет конкретный контрпример и проверяется соответствующей регрессией. Финальный retirement снимает только уже ненужный адрес после проверки consumers/lifecycle. Допустима другая последовательность при более дешёвом проверяемом переходе, но её причина фиксируется.

Не требуется падение численного теста для доказанно эквивалентного перемещения. Для него нужны сохранение поведения, import-direction/identity tests и отрицательная проверка возвращения старой лишней реализации. Для настоящего bugfix нужны различающая регрессия и положительный контроль. Не делать старое ошибочное поведение неприкосновенным golden-эталоном; **ожидаемая дельта обозначается до изменения**.

Точный конечный census D/C включает доступные source/relative imports, FQN/string/file loaders, configs, generated artifacts, public APIs и packaging. Ноль совпадений индексного поиска не равен полному отсутствию клиентов. Но недоступность всех возможных внешних систем не повод бесконечно сканировать проект: перечислить конкретную непроверенную обязанность, сохранить минимальный нужный facade и продолжить следующую готовую работу. Восемь D-карточек не являются восемью безусловными командами удаления.

## 5. Путь после перемещения — часть задания

`relocation_map.json` содержит **21 связанную карту** source→target; часть — extraction, не whole-file rename. Предлагаемые пути разрешает I2 по текущим repository правилам до записи. Один раз принятую карту он сообщает затронутым пакетам; исполнители не повторяют общий поиск владельца каждый раз.

До завершения move lease охватывает обе стороны, тесты и конкретные shared config changes. После merge I2 записывает actual target и commit; остальные B/LA задачи, regression imports и symbolic registry paths используют **действительную новую реализацию**. Зеленый тест старой копии после cutover не принимается как проверка новой. Возвращать прежнюю production-копию ради упрощения patch запрещено.

Physical `__module__`, serialization FQN, exception/class identity и saved symbol paths проверяются там, где поддержаны. Изменение Python-адреса не даёт права переписать CAS hashes, model identity, старые receipts или scientific profile.

## 6. MacBook Air M2 / 16 GB: общий взвешенный бюджет

Машина задана пользователем: Apple M2, 16 GB RAM, macOS Tahoe 26.6.2. Эти правила — **стартовая политика**, не измеренный оптимум и не гарантия пикового RSS.

| Класс | Общий лимит на весь Mac | Назначение |
|---|---|---|
| E: чтение/редактирование/review | До15 direct leaf workers | Работа продолжается при занятой test queue; permit не требуется |
| L: лёгкий адресный test/lint | **До7 resource-bearing process groups и7 L-equivalent units** | micro=0.5, standard=1, измеренный medium обычно2–3 |
| N/C: native/numerical/build/install/checkpoint | **Один эксклюзивный job, полный бюджет7** | Сначала drain L; другие resource-bearing jobs ждут |
| Named shared resources | Один владелец на ресурс | ports, browser/Playwright, DuckDB/DB, CAS/scratch и governed artifacts |

Это не «семь тестов на каждого агента». Каждый job включает свои дочерние процессы и native pools; намеренные дети одного admitted race входят в его permit. Малый массив не делает тяжёлый import лёгким. Для intended race допустимы два участника внутри одного контролируемого job; для fail-fast — несколько маленьких coroutines. Глобальное workers=1 не должно уничтожать сам проверяемый race.

**I1 — единственный broker очереди.** Исполнитель передаёт immutable request: executable, exact argv, cwd/worktree, code SHA, selectors/identities, timeout, class/cost, named resources, output root и basetemp. Submission атомарно копирует bytes в unique ready entry и сохраняет SHA; короткая `fcntl.flock`-критическая секция единственного queue writer-а атомарно claim-ит ready entry, проверяет capacity/resources и обновляет projection; pytest/review внутри lock не выполняются. Permit освобождается после завершения process group, установленного cleanup и сохранения receipt/artifact, не после review. Никто не обязан запускать `top`, проверять memory pressure или повторять environment inspection перед каждой правкой. Отдельная система мониторинга нагрузки не входит в deliverables. Реакция — на OOM, зависший собственный test process, устойчивую потерю отзывчивости либо сообщение пользователя; I1 останавливает новые тесты, разбирает известный job и понижает его класс/объём.

Нельзя запускать полные pytest/coverage после каждого пакета, `-n auto`, скрытые test watchers, параллельные `sync/install`, несколько Node builds или service clusters. Для OpenBLAS/OpenMP сохранить прежний test-launch профиль `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` до импорта; он **не является доказанным cap всех JAX/Apple native threads**. Не добавлять случайные XLA-флаги. Не менять production defaults и число научных folds/draws ради скорости тестовой машины.

**Новые legacy-проверки не запускают тяжёлую предметную работу:** Scholar transport использует fake responses, не live HTTP; embedding wiring — маленькие тексты и injected encoder, один tiny native index отдельно; training bridge — один-два updates короткого согласованного механизма, не полномасштабное PPO; DDM — маленькие native event/model transitions, не повторная FP calibration на потоках; Ukraine provisioning/C7 server-only pipeline не исполняется на Mac для проверки relocation — проверяются command/cwd/env и сохранение policy. Client generation и wheel/sdist объединяются в CP6.

При необходимости настоящего backend выполнить **один небольшой N-test**: fixture не объявляется доказательством native behavior. Отсутствующая зависимость создаёт конкретный `deferred_native` item с владельцем/окном, а не бесконечные installs и не фиктивный success. Малый statistical smoke проверяет механизм, не номинальное покрытие на всех данных.

## 7. Setup и worktrees

Один SETUP-01: зафиксировать HEAD, прочитать repository AGENTS/правила, определить project Python/lock/extras и существующие проверочные команды, подготовить macOS arm64 environment, базовый import smoke и test queue. Не сверять автоматически Linux/Python versions исторических probes как требования проекта.

Отдельный linked worktree/branch для каждого активного writer, не независимые полные clones. У reviewer свой read-only snapshot либо agreed test branch; `.venv`, `node_modules` и caches не копируются. Пока job читает worktree, его checkout/source/dependencies не меняются. После сохранённого commit/handoff ненужный worktree освобождается штатно; пользовательские uncommitted changes не удаляются и `reset --hard` не применяется.

Общее неизменяемое dependency environment допустимо только с доказанной привязкой импортов к тестируемому worktree; shared editable install на другом checkout недопустима. После нового worktree/environment/install/build должно оставаться минимум 10 GiB свободного диска (актуальное решение владельца). Путь изменённого импортируемого модуля проверяется при создании/первом native запуске worktree, не перед каждой командой. Каждому job свои tmp, CAS/DB fixtures и port при необходимости; production user storage не используется для fault injection.

Workspace lockfile, actual generated outputs, новые proposed paths разрешаются один раз при выдаче соответствующего пакета; в lease добавляются точные пути. Одновременные обновления общей registry/lockfile делает назначенный владелец последовательными небольшими дельтами, не конкурирующие implementers.

## 8. Готовый старт и динамическая очередь

**Сохранённый historical seed, не текущий dispatch и не barrier:** CYC-01, SEL-01, STA-01, ING-01, OPT-01, FRY-01, DDM-01, GRF-01, UDF-01. Список сохранён для воспроизводимости исходной раскладки; текущая работа идёт из live B+LA rolling queue, где поддерживаются минимум пять полностью специфицированных ready-пакетов сверх active. Фактические дополнительные paths, leases и review capacity сверяются при каждом dispatch.

Освободился writer → Sol выбирает следующий ready пакет из **общей B+LA очереди**. Держи минимум пять полностью специфицированных ready-пакетов помимо активных; если активных0–1 и буфер пуст, временно усиливай preparers до3–4, а при здоровом буфере оставляй не более одного preparer. Предпочитать продолжение уже начатой migration lane, когда оно снимает двойную правку hotspot, но не ждать занятого файла при наличии полезного независимого пакета. Широкая read-only подготовка допустима заранее; production patch потребляет принятый предшествующий контракт.

Условия: необходимые контракты присутствуют на base или удовлетворены доказанным existing solution; write lease не конфликтует; назначены reviewer, base и resource class; задача продвигает полезный путь, сохраняет данные/смысл или убирает повторную работу. Свободный slot не повод создавать новый refactor. Один executor не сдаёт более одного patch сверх текущей работы; review backlog `4` — мягкая пользовательская цель, не admission barrier, не cap active executors и не global STOP. Небольшой excess вызывает rebalancing в review/closeout, а не отклонение независимой работы.

## 9. Четыре вида связей

`depends_on` — selected implementation order (DAG); `write_conflicts` — взаимное исключение файлов, включая tests/proposed destinations; `activation_rules` — условия объявления общего маршрута готовым; `coordination_lanes` — совместное планирование без нового барьера. Read-after-write impact отдельно показывает, какие consumer tests адресно перепроверить после merge. Текстовый бесконфликтный merge не доказательство semantic compatibility.

I2 может сузить заранее заданное ребро при установленном достаточном контракте текущего кода, записав причину. Нельзя снимать dependency только ради загрузки slots или вводить global dependency «весь legacy до B». Cross-corpus relations различают **тот же участок**, **upstream contract**, **совместную приёмку** и **только похожий принцип**. Последний не разрешает слияние implementations.

## 10. Приёмка пакета и статусы

Для B: актуальность механизма → различающая регрессия → минимальный patch → положительный/негативный control → независимый review → targeted consumer check на принимаемом SHA. Fixed-SHA tests и первый содержательный review начинаются параллельно; consumer check следует после принятия обоих результатов. Для LA: scope/caller characterization → перенесённый/единый owner либо честный профиль → нужный behavioral fix → actual consumer cutover → проверенный retirement или точный остаток.

Рабочие состояния: `planned → active → patch_ready → reviewed → merged_local → accepted_checkpoint`. `merged_local` — только integration branch, не release. Возможные отдельные исходы: `already_resolved`, `not_reproduced`, `conditional_not_used`, `blocked_environment`, `decision_needed`, `deferred_native`, `resolved_by_explicit_limitation`, `compatibility_pending`, `bridge_pending`. У source records внутри пакета отдельные статусы. Для многоэтапной LA closure owner проверяет **все required_bundles**; источник не объявляется исправленным только потому, что один packet merged.

Handoff фиксирует B/LA IDs и конкретные фазы, base/patch SHAs, write paths и path-map changes, characterization versus intended behavior delta, точные commands/exit codes/logs, native/fixture границы, deferred tests, counterpart review и условия retirement/activation. Полные логи отдельно, не в контексте всех агентов. Вредное упрощение — missing→0, nominal→observed, alias→independent evidence, expired pass→current permission — не принимается ради зелёного теста.

Слияние последовательное. Изменившиеся dependencies требуют адресного повторения затронутых tests на новом SHA, не полного CI. Один маленький revert/mutation control для существенного bugfix допустим; полный mutation-testing репозитория не требуется.

## 11. Шесть окон CP1–CP6

Активные checkpoint IDs переименованы из E01 K1–K6 в **CP1–CP6**, чтобы не спутать их с legacy K01–K36. Исторический текст обоих аудитов не переписан. Шесть окон — не шесть полных CI и не дополнительные окна на каждую LA.

| Окно | Связанный результат | Исходные T | Дополнение legacy |
|---|---|---|---|
| CP1 | Малый N5→N8, продолжение и композиция | T1,T2,T4, частьT3 | Явный N7 handoff; compile/catalog/layout relocation; no fabricated S10 pass |
| CP2 | State, replay, ingestion, CAS и source generations | T3,T5–T8,T13,T14 | Ukraine helpers, Scholar snapshot, embeddings/checkpoint generation, canon/migrations/retirement |
| CP3 | Search/history/funnel/backtesting | T9–T12,T15,T16 | SearchService cutover; generic calibration report→receipt; BERL и DDM отдельными tiny scenarios |
| CP4 | Одна calibration цель и uncertainty law | T17–T19 | Baseline/DomainPlugin profiles, реальный tiny trainer bridge, применимый S10 measurement bridge |
| CP5 | Graph/query/causal estimate | T20,T21 | Real packages после sibling cleanup; explicit surfaces и dedicated DiD replay |
| CP6 | Согласованная поставка | Краткий T1/T2/T3 и второй случай; выбранные regressions | Один packaging/installed-import pass и generated-client family; finite retirement census closeout |

CP-окна идут по готовности соответствующего блока, не диктуют очередность написания всей платформы. CP6 последнее. Нужный tiny native seam-test не ждёт общего конца окна, если без него нельзя принять центральный контракт. Linux/server-specific и unavailable native checks остаются отдельной матрицей, не объявляются покрытыми Mac.

## 12. Перенос прогресса из E01

E02 не предполагает ни что работа уже началась, ни что все84 пакета нетронуты. I1 однократно читает предоставленный actual ledger/commits, если они есть. Подтверждённый B-outcome переносится по исходному B-ID и точному evidence, а не по одному прежнему названию пакета. Split/cutover changes проверяются адресно; повторно чинить доказанно закрытый B не нужно. Новые LA этапы не становятся done из старого B-статуса. Удалять существующие branches или сбрасывать integration нельзя.

`E01_TO_E02.json` содержит сохранённые ID, changed assignments и новые packets; `PATH_MAP_TEMPLATE.json` — место для фактических выполненных moves. Эта процедура продолжает работу, а не заменяет её нулевым ledger.

## 13. Защита источников и полномочий

LA-045 включает позднее `_digest`: всего семь private functions и одна constant, при сохранённых hashlib/json и активном fallback. LA-057 — только module TypeVar и один import-name. LK35 сохраняет channel anyOf ручной DDM schema; LK34 — R2 signoff и запреты failed certificate/R1/R0. Generic predictive, Foundry parameter и DDM FP calibration не сливаются. Неизвестный consumer-contract/override-profile получает точное `decision_needed` у владельца, не самостоятельное изменение authority правил агентом.

Проверки toolkit в `qa/` подтверждают покрытие, DAG, полные исходные блоки и integrity файлов; **не выполненную реализацию и не независимое assurance-заключение о PolicyOS**. Скрипт `python3 verify_plan.py` не запускает проект и не устанавливает зависимости.
