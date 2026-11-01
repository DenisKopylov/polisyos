# CYC-05 — правдивые лимиты, завершение и структурная проверка
## Проход C07 · v005 · 31 октября 2026 · B15 / B29 / B30

**Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Read-only аудит продукта. Код, тесты и конфигурация репозитория не изменялись. [Исходное поручение и карточки](../05_Источники/CYC-05_исходные_строки.txt), [индекс прочитанных исходников](../05_Источники/C07_источники.json).

## 1. Итог: исходные механизмы изменены, но не весь критерий завершён

**B15:** запрошенные и эффективные лимиты теперь представлены явно; для настроенного source-derived маршрута действительно создаются дочерние узлы и рёбра. Нельзя больше описывать всю HTTP-композицию как безусловно одноузловую. Сохраняются ограниченные профили и обязательная подготовка контекста: наличие этого маршрута не означает автоматической произвольной декомпозиции любого нового запроса.

**B29:** producer больше не превращает каждый `stop` в `abstain`. Нормальная остановка, остановка по ресурсу и воздержание сохраняют разные терминальные основания. Это изменение нужно сохранить. Однако исполненная проверка всей цепочки producer → persisted history → API → фактический UI в этом проходе отсутствует.

**B30:** отсутствие исходников, пустой знаменатель и parse/read error больше не служат положительным прямым structural receipt. Главное: в рассмотренном штатном N6-финализаторе прежний полный AST-census уже не вызывается ради положительного допуска. Вместо этого используется существующий владелец идентичности загруженной сборки. Но его readiness для N6 сейчас явно и безусловно остаётся `UNRUN`. Завершённого положительного моста от проверенного deployment к N6-currentness ещё нет.

| ID | Реализованное и защищаемое | Остаток | Статус этого аудита |
|---|---|---|---|
| B15 | Requested/effective/reason; exact child-set; граф и ограниченные результаты | Квалифицировать текущую полную цепочку, границу выбранного профиля и остановку с сохранением частичного результата | `partially_assessed` |
| B29 | Typed stop map, `stop/stopped` отдельно от `abstain/abstained` | Native round-trip и потребители; отдельно проверить подмену соседних статусов без изменения терминала | `partially_assessed` |
| B30 | Честная недоступность, диагностический census, identity owner, no full AST in N6 finish | Реальный issuer/build-binding для current/PASS, invalidation и packaged/readback; не снять ограничение вручную | `partially_assessed` |

Полных закрытий нет. **Новый доказанный production-баг в этом проходе не объявлен.** Есть подтверждённый исходниками незавершённый путь и точно очерченные неисполненные проверки. Это важнее искусственного поиска новой ошибки в каждом пакете.

## 2. B15: от видимого лимита к настоящему графу

### 2.1. Лимит теперь не скрыт

`_resolve_http_recursive_budget` сохраняет `requested_max_iterations`, `effective_max_iterations`, `recursive_budget` и `clamp_reason`. Для запроса 7 текущий профиль принимает 3 и указывает `requested_max_iterations_above_http_cycle_cap_3`. Без выбранного child-маршрута бюджет остаётся depth=0 / nodes=1. Снять эту защиту ради совпадения requested/effective не требуется. [C07-S01]

Для configured candidate-child профиля поддержаны один или два ребёнка. Третий не отрезается молча, а отвергается как выход за профиль. Generic source-complete профиль берёт весь установленный набор: depth=1, nodes=1+child_count и одинаковые requested/effective child counts. Одновременное задание двух профилей отвергается. Это не безлимитная рекурсия: `RecursiveCycleBudget` отдельно ограничивает глубину до 99 и узлы до 100, проверяет min/max cycles. [C07-S01, C07-S06]

Локальные probes воспроизвели 7→3, двухдетный configured-профиль, трёхдетный generic-профиль, отказ неоднозначной конфигурации и отказ третьего configured child. Round-trip выполнен на переписанных бюджетных DTO с реальным Pydantic, **не через импорт проектных моделей**. Неверные/нулевые raw-входы helper не объявлены публичным дефектом: допустимость таких входов HTTP-DTO в этом проходе не установлена.

### 2.2. Бюджет в отчёте не равен выполнению бюджета

В CYC-05 уже есть worker/progress-тест, который проверяет requested=7/effective=3. Но это N4 proposal-only путь: builder и внешняя compiler-граница контролируются фикстурой, а результат явно имеет `recursive_budget_application_status="not_applied_n4_proposal_only"`; N5/N8/N9/S8 — `not_run`. Сохранить такую честность. Этот тест подтверждает предназначенную проекцию, а не исполненную численную рекурсию. [C07-S07]

### 2.3. Рёбра создаются из действительных child-входов

Рассмотренный service не просто увеличивает depth. Он вызывает `derive_n4_candidate_child_problems`, сверяет полный child denominator с выбранным profile set, проверяет parent/source/context/job/scope bindings и формирует `problems_by_node`. Далее `derive_recursive_design_graph` получает конкретные `module_refs` и `(root_ref, child_ref)` для каждого ребёнка. Вызов существующего recursive controller получает этот граф, те же дочерние задачи, контексты и бюджет. Отсутствующий source, неправильный набор или несовпавший контекст не заменяются придуманными узлами. [C07-S01]

Это реальная интеграционная работа, которую не следует заказывать повторно. При этом имеющийся договор требует заранее разрешённого профиля и соответствующих входов. Нет основания объявлять доказанной универсальную семантическую декомпозицию произвольной политики.

### 2.4. Два вида тестов не должны сливаться

`test_workspace_fixture_children_flow_through_recursive_graph_and_n5` использует два экземпляра одной именованной Workspace-фикстурной задачи, меняет aliases и связывает их с parent. Реальный parent N5 и CAS-readback там присутствуют; листья и источники являются контролируемыми тестовыми элементами. Проверка полезна для identities, сохранения child relations и запретов неправильной композиции. Но две разные alias-строки сами по себе не означают два разных предметных вопроса. [C07-S07]

Более сильный `test_original_second_capture_serves_two_meaningful_children_through_fresh_get` уже проверяет два разных source-derived предложения: tax credit и procurement distress backstop; третье предложение working-capital guarantee остаётся заблокированным. Тест сохраняет исходную запись, пропускает её через ordinary POST, dispatch, compiled artifact и свежий GET; сравнивает точный набор детей, их profile bindings, численные N5 refs и историю. Для каждого листа ожидается одна завершённая итерация; requested/effective=1, children=2, nodes=3. Изъятие одного source-derived ребёнка при сохранённой графовой оболочке имеет отдельный отрицательный контроль. [C07-S08]

Этот тест **прочитан, не запущен**. В нём контролируемый LLM gateway, записанный ответ, подготовленный source-root и профиль. Он не измеряет качество нового LLM-планирования, доступность production-источника или фактическое знание о мире. Слово fresh GET означает новое чтение endpoint, не автоматически новый процесс/новую установку.

### 2.5. Дети-альтернативы не становятся составной политикой

`ParentJointCandidateSelectionV2` прямо хранит `source_candidate_relationship="alternatives"`, `composition_status="not_established"` и отсутствие установленного child-to-parent refinement. Гипотетическая диагностика объединения допустима, но не делает полученный набор authored compound design. Это ограничение сохраняется в request/result bindings. [C07-S06]

С учётом установки пользователя LLM может предложить декомпозицию, отношения частей и гипотезу их совместного действия. Требовать отдельного универсального детерминированного автора политики не нужно. Но исполнение должно различать **альтернативы**, **обязательные совместные компоненты** и **последовательные шаги**, а также потреблять соответствующую реальную модель взаимодействий. Наличие стрелок root→child не устанавливает эти отношения за LLM.

## 3. B29: правильный терминал должен пережить каждую проекцию

### 3.1. Producer исправлен содержательно

`_N6_TERMINAL_STOP_PROJECTIONS` задаёт полную таблицу по `SearchTerminalKind`; helper проверяет полноту знаменателя перед использованием. Для frontier stable, grounded admissible, grounded partial admissible, budget exhausted и search ceiling repair required он выдаёт `stop`. Для настоящего grounded abstention — `abstain`. Остальные терминалы нельзя произвольно использовать как stop: они дают адресный отказ. [C07-S02]

`_refinement_decision` использует эту таблицу, а `_search_iteration` повторяет тот же выбор: `stopped` против `abstained`. При конфликте decision и action/terminal producer отвергает несогласованность. Типы и названия не создают новый уровень полномочий. В частности, `budget_exhausted → stopped` **не означает успешную рекомендацию**: причина остановки остаётся budget exhausted, а `search_ceiling_repair_required` остаётся потребностью в ремонте. [C07-S02]

В локальной таблице проверены пять stop-состояний, настоящее воздержание, шесть forced-stop отказов, неизвестный терминал и две конфликтные комбинации. Контроль удаления одного свойства вернул старое `frontier_stable → abstain`; различающий тест это обнаружил. Проверялись переписанные ветки, не настоящий PDC serializer или весь generation controller.

### 3.2. Safety cap не является доказательством исчерпания знания

В обычном N6 при достижении `max_cycles` сохраняются накопленные циклы/summaries, верхнее состояние становится blocked с причиной `voi_safety_cap_reached_without_scheduler_stop`. Последняя refinement/search проекция явно меняется на block/blocked_no_retry. Внешний `generation_cycle_terminal_state` отображает этот конкретный случай в `BUDGET_EXHAUSTED`, `budget_kind="cycle"`. Это контролируемое прекращение работы, не доказательство отсутствия лучшей политики. [C07-S03]

Также обнаружен полезный явный предел проверки: комментарий `_generation_cycle_block_guard_reason` говорит, что численный safety cap нельзя полностью реконструировать из standalone N6 run, поскольку `max_cycles` не поле этого объекта. Intrinsic validator в этом случае проверяет ожидаемую форму причины и advance, а не восстанавливает значение cap. В HTTP enclosing artifact есть budget resolution, поэтому правильная приёмка должна сверить **оба** уровня. Отсутствие cap в leaf не объявлено самостоятельным багом всей системы. [C07-S03]

### 3.3. Историческая читаемость и нынешний допуск разведены

`validate_generation_cycle_run_history` проверяет точную историческую проекцию и intrinsic checks без требования нынешней актуальности deployment. Candidate validator переносит невыданную currentness как ограничение и отдельно отвергает известный stale. Strict validator требует актуального свидетельства. Их нельзя сделать одним blanket-отказом: иначе улучшение структурной честности снова закроет уже разрешённую исследовательскую работу. [C07-S03]

В прочитанном intrinsic validator есть сверка terminal с фактическими grounding/value, source/identity, заблокированной VOI-action, истории и фронтов. Однако полный испытанный readback нормального stop с контролируемой порчей только refinement/iteration-полей здесь не установлен. Это адресная задача проверки, **не уже доказанный обход валидатора**. Существующие UI search snippets о поддержке `stopped` являются только указателями; браузер, Atlas и вся frontend-проекция не исполнены.

## 4. B30: честный diagnostic есть; положительный deployment bridge не завершён

### 4.1. Старый прямой census больше не выдаёт пустое благополучие

`_collect_strangle_source_census` отличает отсутствующий `src/polisyos`, пустой набор, ошибку чтения, ошибку UTF-8/AST и прямые `run_fixture` вызовы. При неполноте digest не выдаётся как положительное полное основание. При полном чтении формируется content-dependent digest и список callers; разрешённая старая fixture-site отделена. Локальные файловые пробы проверили эти различия и изменение digest при смене bytes. Применялся явный hash-adapter вместо проектного канона: это тест чувствительности, не проверка подлинного production digest. [C07-S04]

У такого прямого name/attribute scan остаётся известная граница: вызов через alias не распознаётся как direct call. Локальный контроль это показал. Нельзя трактовать `strangled` этого ограниченного helper как доказательство полной недостижимости любой динамической ветви. Его receipt сам несёт соответствующие limitations. Это не обнаруженный обход нынешнего N9. [C07-S04]

Более поздний `inspect_n6_source_census` явно описывает входной path denominator, перечисляет неподтверждённые bindings/динамические формы, использует явный обход каталогов и оставляет production verdict `UNRUN` даже при полном счёте файлов. Этот inspector в данном проходе прочитан, но не исполнен. Отсутствие положительного verdict не следует исправлять заменой константы. [C07-S04]

### 4.2. Штатный N6 не обязан повторять такой AST-обход в финале

В текущих `GenerationCycleController.run` и `_finish_run_after_loop` используются наблюдения `observe_n6_deployment_currentness`. Run сохраняет identity-status и привязанную identity. В финальный объект кладётся `_n6_not_established_strangle_receipt`; legacy recompute всего `src` здесь не вызывается. Не следует снова предлагать cache поверх уже неиспользуемого в этом финализаторе обхода. Это вывод о рассмотренном маршруте, не всеобщий census любых structural scans в репозитории. [C07-S03]

Существующий `confidence_ledger` имеет import-time loaded identity, baseline с lock/project/source/runtime, отдельную проверку loaded/disk consistency и механизмы стабильного снимка. Поэтому задача не требует второй системы идентичностей. `capture_loaded_deployment_identity` возвращает ранее захваченный снимок, а не повторно парсит всё дерево на каждом N6. Это не равнозначно доказательству неизменности диска после загрузки: источник прямо разделяет capture и последующую проверку допуска. [C07-S05]

### 4.3. Точная незавершённость — readiness не может сейчас дать PASS

`inspect_packaged_deployment_identity` в просмотренной реализации **безусловно** возвращает `verdict="UNRUN"` и три неразрешённых пункта: `packaged_build_identity_issuer_not_appointed`, `n6_strangle_census_not_established`, `deployment_authority_issuer_not_appointed`. Наличие файла manifest или lock лишь отражается в диагностике; оно не меняет verdict. [C07-S05]

`observe_n6_deployment_currentness` умеет различать несовпадение известных identities (`stale`), отсутствие исторической identity и неустановленную loaded identity. Но даже одинаковые установленные identities возвращают `not_established / UNRUN`, поскольку readiness остаётся таким. Положительная ветвь `current/PASS` описана в consumer, но **не достигается через нынешнего readiness producer**. Изолированная композиция с явно заданной loaded identity подтверждает ровно это условие. Реальный import-time capture и authority ledger не исполнялись. [C07-S05]

В `_finish_run_after_loop` неполная currentness не допускает `_promote_completed_generation`; кандидатные результаты сохраняются. Это правильная предохранительная граница незавершённого механизма, а не основание объявить её полноценной готовой способностью. Не установлена невозможность любого другого N9-контекста во всём проекте. [C07-S03]

### 4.4. Экономное направление дальнейшего завершения

Сначала определить фактический поддержанный deployment-профиль и структурное свойство, для которого нужен положительный результат. Затем у существующих build/identity владельцев связать проверенный артефакт со срезом реально исполняемого кода, релевантными entrypoints/import bindings и версиями правил. Нормальное повторное чтение того же среза должно быть дешёвым; существенная смена основания должна требовать нового результата.

Не требуется универсально доказывать статическим анализом безопасность любой возможной Python-программы. Нужен конечный, проверяемый контракт поддержанного исполнения с честно перечисленной областью. Недостающая issuer-привязка не должна закрывать низкополномочное исследование, но она не должна исчезнуть из защищённого допуска только потому, что исследование дало хороший результат. Это развитие **существующего** owner chain, не ещё один registry/receipt framework.

## 5. Матрица доказательств и следующая адресная приёмка

| Критерий | Наблюдение данного прохода | Что ещё должно быть исполнено |
|---|---|---|
| Запрошенные/эффективные limits | Исходник + малые probes + существующий progress-test прочитан | Реальный worker readback на принимаемом SHA |
| Два содержательных ребёнка | Service строит exact graph; сильный served test найден и прочитан по нужным секциям | Выполнить тот же контроль без подмены N5 и сверить сохранённый denominator |
| Сохранение при budget stop | N6 сохраняет историю; рекурсивный raw-source показывает partial builder и frontier continuation | Малый stop после первого ребёнка: результат первого доступен, второй не объявлен вычисленным |
| Normal stop ≠ abstention | Положительные и отрицательные ветви изолированно исполнены | Проектный DTO/history/HTTP/UI readback; corruption control соседних полей |
| Missing/parse/read/caller различены | Малый настоящий filesystem/AST с явными адаптерами | Настоящие receipt/validator и installed-profile negative |
| Нет повторного full AST в N6 finish | Трасса current owner вместо legacy recompute | Измерить реальные чтения на неизменной развёрнутой версии, не заявлять ускорение без замера |
| Значимая смена не использует старое positive | Currentness различает заданные different identities; исходники authority consistency прочитаны | Настоящая смена code/lock/binding при действующем qualified issuer |
| Положительный issuer доступен | **Нет: текущий producer безусловно UNRUN** | Завершить его назначенную область/проводку, затем отдельно принимать positive chain |

Команды/селекторы следующей native-проверки ограничены реально найденными тестами в `native_verification.json`; они здесь не запускаются. Предлагаемые новые corruption/сопоставительные сценарии не выдаются за существующие тесты.

## 6. Выполненное в этом выпуске

**25 bounded characterizations, 25 MATCH, 0 MISMATCH.** В число входят группы терминалов, характеризация ограничений и один removal control; совпадение с ограничением не является продуктовым PASS. Python и файловые операции настоящие, бюджетные DTO переписаны под установленный Pydantic. Проектные импорты, PDC validators, N4/N5, CAS, HTTP, ledger и браузер не исполнялись.

[Исполняемый probe](../04_Проверки/C07_CYC05/probe_cyc05.py) · [Результаты](../04_Проверки/C07_CYC05/bounded_diagnostics.json) · [Границы](../04_Проверки/C07_CYC05/Чтение_и_границы.md) · [Остатки](../01_Реестры/C07_остатки.json).

Исходный план и шесть предыдущих отчётов сохранены. Следующий пакет в исходном порядке — **SIM-01 (B06/B07)**. Переход к его чтению не снимает нерешённых activation-условий предыдущих пакетов.

## Источники

**C07-S01** — `policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py`. Requested/effective budget, source-derived children, exact graph and actual recursive call. [строки 150–285](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py#L150-L285) · [строки 2300–2600](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py#L2300-L2600) · [строки 2590–2750](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py#L2590-L2750). pinned source read; native UNRUN.

**C07-S02** — `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`. Complete terminal map and producer stop/abstain projections. [строки 495–525](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L495-L525) · [строки 19590–19752](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L19590-L19752). source read; isolated transcribed branch probes; project DTO UNRUN.

**C07-S03** — `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`. Run/safety cap, post-loop identity and N9 refusal, history/candidate/current validators. [строки 8400–8820](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L8400-L8820) · [строки 14790–14935](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L14790-L14935) · [строки 15195–15590](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L15195-L15590). pinned source read; native UNRUN.

**C07-S04** — `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`. Legacy direct AST census versus explicit non-authoritative source inspector. [строки 2800–3140](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L2800-L3140) · [строки 20040–20410](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L20040-L20410). source read; old direct-census transcription over tiny files; new inspector not executed.

**C07-S05** — `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py`. Existing loaded identity owner; unconditional packaged UNRUN; currentness and source-bound authority checks. [строки 800–1080](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/confidence_ledger.py#L800-L1080) · [строки 5430–5680](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/confidence_ledger.py#L5430-L5680) · [строки 5700–5840](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/confidence_ledger.py#L5700-L5840). source read; decision transcription with injected identity; actual owner not imported.

**C07-S06** — `policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py`. Explicit recursion budget; child bindings; hypothetical alternatives are not authored compound policy. [строки 1–285](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py#L1-L285) · [строки 1470–1780](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py#L1470-L1780). pinned source read; native UNRUN.

**C07-S07** — `policy-engine/tests/unit/remediation/test_cyc_05.py`. Existing missing/parse/source tests, proposal-only budget progress, fixture two-child numerical parent and negatives. [строки 1–340](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_cyc_05.py#L1-L340) · [строки 340–740](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_cyc_05.py#L340-L740) · [строки 740–825](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_cyc_05.py#L740-L825). full test-source read; all native tests UNRUN.

**C07-S08** — `policy-engine/tests/integration/runtime_quality/test_generic_n4_child_profile_set_served.py`. Stronger two-meaningful-child POST/worker/N5/GET test; controlled recorded source. [строки 560–635](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/runtime_quality/test_generic_n4_child_profile_set_served.py#L560-L635) · [строки 760–1120](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/runtime_quality/test_generic_n4_child_profile_set_served.py#L760-L1120). bounded test-source read; fixture preparation not fully reaudited; native UNRUN.
