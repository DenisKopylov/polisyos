# R20: общее review плана и применение пяти решений SDD

Дата: 24 октября 2026. База review: `9f32d2706d60a5970d6fdd9ec9896242271a02ab`.
Текущие изменения — документация. Product execution — **UNRUN**; E02 acceptance
этим review не установлена. Код, окружения и production data не изменялись.

**Вывод:** программа сохраняет согласованную основу для исполнения после E02.
Общее review обнаружило реальные пропуски потребителей, слишком узкие проверки
исходных долгов и несколько неверных границ ожидания. Они исправлены в действующих
задачах и предпочтительных решениях. Наличие подробного плана не доказывает
реализацию capability, пригодность конкретного внешнего основания или готовность
к практическому применению.

## 1. Что согласовано и применено

[Канонический датированный record](../../../../system-design-decisions/lifecycle-cross-scope-clarifications-r19-ratification.md)
применяет ровно пять одобренных пользователем предложений:

1. **R19-SDD-01:** ссылки на субъект и parent/child связи не переносят authority,
   admissibility, rights, audience, applicability или currentness.
2. **R19-SDD-02:** конфликт SDD разбирается по точным версиям, области и защищённому
   действию; до решения удерживается затронутое применение, независимая работа продолжается.
3. **R19-SDD-03:** передача права изменять нормативное видение требует действительного
   делегирования принципалом; доступ к репозиторию или ключу этого права не создаёт.
4. **R19-SDD-04:** все stable IDs открытых вопросов vision §8.4 связаны с Decision
   Log; эмпирическое свидетельство не закрывает нормативный выбор. Набор берётся из
   канонического источника, а не навсегда фиксируется сегодняшним числом.
5. **R19-SDD-05:** составное утверждение требует своей обоснованности, границ и
   зависимостей. Принадлежность к группе не означает adoption; сумма отдельных
   эффектов не доказывает совместный причинный или программный результат.

Датированные дополнения внесены в соответствующие SDD, создан DL-PDC-0017.
Исторические решения/receipts сохранены. Draft target architecture и execution
topology не ратифицированы целиком; их конкретные proposed механизмы, thresholds,
schemas и неприкреплённая lattice algebra не стали обязательными по соседству.
Другие C03/AS2/WP proposals имеют прежнее standing.

## 2. Объём и метод review

Проверен полный действующий набор `tasks.json`: **121 задача** и соответствующие
121 preferred-solution записи. Сохранены **84 вопроса**, 20 R19 solution cards,
все исходные task IDs и **368 прямых `depends_on` связей**. Добавлен один
вопросный маршрут CNT-06 → структурная квалификация для R18-D06-Q02: теперь
**388 question→task routes** вместо исторических 387. Это дополнительный
producer/consumer slice существующей задачи, не новый глобальный prerequisite.

| Разрез | Полный task denominator / дополнительная проверка |
|---|---|
| Acquisition и substantive foundations | CAP-01–06, CNT-01–09; все расширения и native-input границы |
| Custody / lifecycle | LIF-01–09; права, retention, currentness, source-use owner |
| Deployment / operations | OPS-01–12; местные/remote tiers, ресурсные и операционные зависимости |
| Search / design / studies | DES-01–12; substantive alternatives, productive positives, study/learning cycle |
| GY | GYD-01–33; исходные 77 строк и 36 открытых/неизмеренных обязательств на review pin |
| Atlas | UI-01–20; исходные DS12/13/5 критерии, audiences, transports, вспомогательные negatives |
| Долги | DEB-01–14; полный inventory из 277 строк, включая 86 nonclosed на исходном pin |
| Вход / финал | P0-ACCEPT, P0-REBIND, FINAL-FREEZE/REVIEW/REPLAY/USE; стадийность и отсутствие скрытого допуска |
| Сквозные проверки | 368 edges, mirrors R14–R19, ссылки/anchors, текущее standing, SDD scope, structural learning |

Работали 12 прямых read-only reviewers без детей; root один изменял tracked
документы и отдельно сверял предложения с исходными критериями. После исправлений
проводились ограниченные delta reviews. Первичный CAP/CNT отчёт был неполон;
до принятия review scope расширен до всех 15 задач. Первое scientific delta review
нашло противоречащие старые O1 формулировки; исправлены действующие mirrors,
не только новый поясняющий документ. Эти ограничения не скрыты за суммой PASS.

Лёгкая проверка JSON, ссылок, исходных IDs, зеркал и DAG выполняется stdlib без
импорта продукта. Её результат и происхождение review записаны в
[R20 validation](r20-validation.json). Это проверка документов, не runtime test.

## 3. Исправления, влияющие на исполнение

| Найденная проблема | Исправление и различающий сигнал будущей реализации |
|---|---|
| Одобренные SDD всё ещё выглядели pending; старые counts/anchors вводили в заблуждение | Текущее standing и entrypoints обновлены; historical receipts остаются привязаны к старому source. Проверка проходит по полному набору task/question IDs и ссылок. |
| OPS-10 превращал измеренное исчерпание одной машины в обязательный повод для любого cloud tier | При scale-rationale требуется соответствующее измерение; custody, topology, availability и operability могут дать другой обоснованный выбор. Сравнение с более простым вариантом и точная remote conformance сохраняются. |
| LIF-05 не назначал фактического producer решения о source-use | Перед dispatch закрепляются существующий native owner/path и companions; если producer отсутствует, назначается узкое внутреннее расширение. Access context/retention plan сами не выдают grant. |
| CAP-02 мог получить query permission, но не иметь stage-связи с разрешением на первую запись | Conditional LIF-05/native output проверяется непосредственно перед выбранной materialization. CAP-01 query egress, LIF-05 placement и CAP-03 reuse admission различаются. Query-only negative доказывает отсутствие raw bytes в запрещённых temp/cache/log/CAS sinks. |
| Structural learning смешивался с O1 posterior и прямым DES-12→WMR переходом | [Один writer, два научно различных входа](../solutions/18-structural-world-learning.md): native method/CNT-06 квалифицирует структурное свидетельство, GYD-12 отдельно проверяет действующее правило записи и публикует поколение. O1/AS3/WP obligations сохранены для effect-пути. |
| DS1-N010 был ошибочно привязан к AtlasRunDeck | UI-10 возвращён к DS5 C09 AuthzProvider/protected chrome. Loading/error/malformed/401, prior-user и tenant-switch не дают permission/MFA/high-stakes action; permission-free PUBLIC control остаётся доступен. DS20 не переоткрывается. |
| DS13 терял generic transparency feed и различение learning history | UI-04 пишет/читает их из одного canonical event/history source, используя UI-03 index. “This case” и “new evidence” не означают автоматического causal finding. Optional regulator channel не заменяет обязательный generic feed. |
| DS12 перечислял каналы, но не назначал REVIEWER/EXPERT представления; CI-bar был неполон | UI-02 владеет четырьмя audience projections одного record. Отдельно проверяются реальные CI predicates: egress, headers, responsive/locale/plain-language и owner-derived performance budget. CI не доказывает human comprehension. |
| UI-01 Q05 не имел actual currentness supplier | Conditional LIF-02 reaction → fresh UI-01 view. Базовая signature authentication независима и не выдаётся за validity/currentness. |
| DEB-03 проверял private imports, теряя private attributes того же класса | Полный source-bound reach set, включая intra-package/runtime/container cases; unsupported dynamic cases остаются явным residual. Отдельно сохраняются оба release-inventory review conjuncts. |
| DEB-05 ремонтировал CalibrationReport, не весь shared fixture helper | Census реальных `_with_runtime_fixture_authority` callers/kinds и sibling payloads; strict DTO и malformed≠empty сохранены. Generic CAS не становится schema owner по умолчанию. |
| DEB-06 смешивал GY-DEF23 context с owned closure и не связывал UI-19 | GY-DEF23 остаётся DEB-09. Реальный persisted lineage/reissue output читается свежим UI-19; reciprocal acceptance — emission→observation, не цикл старта задач. |
| Internal owner gaps выглядели вечными external waits | DEB-04 назначает Foundry/GY-N12 reconciliation; team-architecture распределяет CORR/INT-R2 в DEB-07; Atlas/DS15 + root комиссионируют metric owner в DEB-13. Внешние signer/mandate/holder факты по-прежнему нельзя изготовить. |
| WDI effort basis был ошибочно назван обязательным institutional input | Восстановлено уже принятое 2026-09-17 option A: canonical owner использует измеренное сопоставимое effort либо явно обоснованную оценку. CAP-03 поставляет actual cost artifact; DEB-07 сверяет исходное обязательство. Paid/licensed source меняет предпосылку. Gross EVSI не требует стоимости; net/cost-dependent claim требует. |

В role prompts добавлено общее правило вывода всех `*_extension` из manifest:
пропущенный R15 companion не должен теряться ни при назначении, ни при review.

Все эти изменения внесены в существующие задачи, preferred solutions и затронутые
workstream/ownership/acceptance companions. Ошибочная UI-10 принадлежность к
run-deck/governed-projection конфликтным группам убрана; точные AuthzProvider/chrome
пути по-прежнему арендуются. Новая верхнеуровневая задача или второй механизм
для каждого найденного случая не создавались.

## 4. Как теперь читать и исполнять план

- `tasks.json` задаёт работу, условия и actual suppliers; preferred solutions
  предлагают reuse-first путь, human cards объясняют его. R14–R17 и R19 extensions, включая назначенные через R19 вопросы R18,
  обязательны в выбранном scope, а не заменяются одной ранней base card.
- Source original criterion и accepted-source rebind определяют, осталось ли
  требование открытым. Research pin, название задачи, status label или summary
  не дают closure. Обоснованное отклонение фиксируется через существующий
  change/rebind protocol с обновлением всех affected consumers.
- `depends_on` не означает «весь supplier task полностью закончен»:
  [стадийные требования](../execution/stage-requirements.json) различают interface
  agreement, owner readiness, actual composition и original disposition.
  Добавленные связи materialization/currentness/lineage/metric действуют там,
  где выполняется их эффект или заявляется соответствующий положительный результат.
- Параллельно готовятся независимые owners и consumer companions. Общий путь записи,
  generated family или реальный contended resource сериализуется по точной аренде.
  Граф сам по себе не является измерением доступного compute или обещанием ста агентов.
- E02 acceptance остаётся обязательным входом реализации. После него scoped rebind
  позволяет независимому участку начать без ожидания всего глобального P0; полный
  original-set census обязателен до общего freeze.
- FINAL-REPLAY запускается на точной согласованной source/input/backend identity
  после независимых reviews. FAIL/ERROR/SKIP/UNRUN сохраняются; диагностически
  завершённый запуск не равен accepted closeout и не разрешает FINAL-USE.

## 5. Что остаётся настоящей неопределённостью

**Accepted E02 tree ещё не привязан в этом пакете.** Поэтому конкретные пути,
действующие schemas/rules, поглощённые E02 долги и точный changed footprint
проверяются при rebind. Приведённые native anchors — исследованные candidates,
а не разрешение править любой названный файл параллельно.

**Для operative structural promotion нужно фактически применимое правило.**
Если accepted source уже содержит его, используется оно; отсутствие только кода
producer/bridge/verifier — assigned engineering. Если отсутствует именно принятое
правило для данного перехода, готовится узкое предложение действующему принципалу.
CNT-06 scientific qualification и наличие method result сами write authority
не дают. Candidate/conditional исследования продолжаются; ими нельзя закрыть
operative positive. Новое SDD по этой теме здесь не ратифицировано.

**Подлинные внешние основания остаются внешними.** Реальные permissions, mandates,
appointment/delegation, provenance/currentness, данные/returned study results и
компетентные institutional acts должны быть получены по существующим путям.
Внутреннее исследование, выбор implementation owner, построение adapter или
оценка бесплатного acquisition effort не маскируются под external dependency.
Неизвестный источник/право ограничивает затронутый use, а не всё исследование.

**Детализация не отменяет будущий engineering choice.** Нельзя заранее доказать
производительность, native compatibility, поддержку каждого backend или истинность
социально-экономической модели. Для такого результата нужны реальные deciding
outputs. Не установленные budgets и conditional deployment tiers остаются scoped
obligations, а исторические source counts не превращаются в вечные константы.

Pattern pass: P01/P02/P03/P04/P05/P07/P08/P10/P13/P14/P15/P20/P27/P29/P31/P32/P35/P36/P37/P38/P40/P41.
Review исправляет целые обнаруженные классы границ, сохраняет полезный positive
и реальный adversarial/removal discriminator; не вводит новые product enums,
универсальные default grants, второй writer или глобальное ожидание всех inputs.
