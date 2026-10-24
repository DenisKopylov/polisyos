# R19: композиция полного жизненного цикла

Статус: решения и обязательства будущей реализации. База — `6416d09d99fa5b219dd36b1c74750b23e11c3c93`. Реализация начинается после фактической приёмки E02 и связывания выбранного slice с принятым source. Ни один текст здесь не является product PASS, G acceptance, closure, новым enum или автоматически ратифицированным SDD.

[84 вопроса и решения](../solutions/lifecycle-r19/README.md) · [Проверки](../assurance/12-full-lifecycle-quality.md) · [Параллельность](../execution/10-full-lifecycle-parallelism.md)

## 1. Что именно меняется

R18 перечислил вопросы; R19 выбирает исполнимые направления и дополняет существующие задачи. Карточка решения связывает вопрос, механизм, текущие anchors, альтернативы, contract, полный поток, migration, resource behavior, внешние входы и различающие проверки. `r19_extension` в двух task catalogs содержит конкретные действия и positive/adversarial/removal для выбранного owner. Старые поля, зависимости и обязанности R14–R17 сохраняются.

84 вопроса не означают 84 модуля или последовательных gate. Названия Sxx-Mx — адреса описаний, не реестр продуктовых сервисов. Перечисленные поля — минимальные семантические связи; исполнитель выбирает совместимое расширение существующего artifact/registry. Новый DTO, status, scheduler, identity registry или certificate нельзя оправдать одним новым названием в карточке. Применяется wire-existing → extend → consolidate → build-new с доказанным отсутствием подходящего owner.

## 2. Два независимых различения

Первое: истинность/достаточность результата и полномочие совершить политическое действие. Система может подписать проверенный условный вывод «при этих предпосылках, для этой популяции, по этой шкале результат такой» без полномочия выбрать коллективного победителя. Право выбора не делает плохую модель хорошей. Гипотетическая шкала остаётся гипотетической, но сама по себе не запрещает корректное условное сравнение.

Второе: candidate computation и protected use. Неизвестное основание переносится как явное ограничение в разрешённой candidate работе; оно не подменяется default. Для protected use проверяются именно релевантные предпосылки этого утверждения/действия. Неприменимый атрибут может быть N/A с обоснованной применимостью; отсутствующий обязательный атрибут не становится N/A. Нет глобального gate «все основания всей системы известны».

Любой mixed row раскладывается: внешний акт → внешнее evidence → наше получение/проверка → реакция нашего claim → поверхность. Автоматизировать можно повторное применение уже квалифицированного правила к разрешённому scope, не выдумывая новый человеческий акт для каждого вызова.

## 3. Единые владельцы значений

| Значение/переход | Существующий маршрут | Чего не создавать |
|---|---|---|
| Discovery, query/coverage/no-hit | CAP-01, source/use admission CAP-03/06 | Второй каталог или «доказательство отсутствия в мире» |
| Фактическое внешнее изменение | CAP-04 | Fake source event из внутренней диагностики |
| Пригодность данных/метода к утверждению | CNT-06 и selected native method | Центральный сервис научной истины |
| Независимость и сопоставление оснований | CNT-08; native provenance | Считать URL/издателей независимыми исследованиями |
| Мера, unit, популяция, шкала ценности | CNT-05; принятые method/output contracts | Назначать смысл по имени или общей числовой форме |
| Law/applicability | CAP-05/CNT-04/DES-05 | Передавать legal owner причинное exposure estimation |
| Actual influence | LIF-07 | Вторую lineage базу |
| Claim enrollment/currentness/publication fence | LIF-02 | Приравнивать solver recompute к текущей публикации |
| Physical runtime enforcement | OPS-08; один LIF-06 permit owner | Второй scheduler или использовать денежный ledger как permit |
| External physical/public capacity | CNT-07 evidence → DES-11/GYD-30 | Смешивать специалисто-часы программы с GPU quota PolicyOS |
| Joint composition certificate | GYD-30, reconciled existing owner | Третий certificate/portfolio authority service |
| LLM invocation / quality / influence | DES-09 / DES-10 / LIF-07 | Делать provider alias executable identity или LLM output authority |
| Studies / acquisition | DES-12 и existing method/permit/rights owners | Исполнение внешнего эксперимента без отдельного допуска |
| Rights/disclosure at actual sink | LIF-05 + selected surfaces | Privacy guarantee из counters или названия review |
| Human correction / revision / rendition | DES-06/07, UI-01/02/04, LIF-02 | Внешнюю редакцию автоматически считать adoption |

Таблица распределяет значения, не заменяет path census. До write исполнитель сверяет actual owner и companions на принятом E02; две существующие одноимённые реализации сначала консолидируются согласно GYD-30, а не дополняются третьей.

## 4. Минимальные общие связи

Каждая связь хранится у своего owner: exact artifact/edition/content ref; declared use/claim/scope; профиль и применимая версия правила/метода; authority purpose и audience; relevant time coordinates; provenance и степень проверки предиката. Родительская связь, key ownership, role name, hash строки или наличие поля ничего из этого не доказывают автоматически.

Qualified local custody-subject ref допустим без внешнего institutional ID. Внешние aliases — опциональные, source/time-qualified. Equality не доказывает continuity, допустимость объединения, authority, permission или transfer evidence. Не вводится глобальный PolicyMatter ontology, issuer или cardinality.

Смысл target задают target-defining rules. Изменение фактически измеренной численности при неизменном правиле популяции может быть uncertainty той же оценки. Изменение самого inclusion/aggregation/denominator rule создаёт отдельный target, даже если число совпало. Аналогично: одинаковая размерность не доказывает calibration; средний эффект около нуля не доказывает отсутствие SCM-ребра; pointwise interval не даёт simultaneous/anytime guarantee.

## 5. Поток от нового знания до актуального утверждения

1. CAP-01/selected connector или native assessment producer получает content-bound материал под actual rights/query-disclosure profile.
2. Native owner различает source fact, measurement, scientific interpretation, hypothetical assumption и institutional act; сохраняет профиль, версии и relevant time.
3. LIF-07 связывает реально повлиявшие inputs с outputs. Ссылка «читали документ» не заменяет load-bearing influence.
4. CAP-04 выпускает реальные внешние события. Собственная квалифицированная CNT-06 assessment отдельно поступает в LIF-02 и может изменить наше утверждение без webhook; она не маскируется под внешний акт.
5. LIF-02 оценивает scoped dependency closure и немедленно ограждает затронутое current/protected use. Recompute может быть delayed/offline; это не разрешает stale green. Не затронутые claims продолжают жить.
6. Native method/DES-11/GYD-30 пересчитывает выбранный closure. Candidate, qualified conditional output, scoped claim reaction и institutional adoption остаются разными переходами.
7. Fresh UI-19/current decision API-MACHINE и выбранные export/browser consumers читают новый status и basis. Историческая выдача сохраняется as-known; system не обещает отзыв скачанных внешних копий.

Различаются представление member outcomes, проверенный описательный/арифметический вывод и joint-policy/system claim. Сумма сопоставимых наблюдаемых величин может быть подписана ровно как этот расчёт: её target, measure/unit, coverage, editions и operator проверены; она не утверждает independence, совместный causal effect, feasibility или program admissibility. Совместная uncertainty требует dependence/covariance basis либо корректной границы. Для вывода о совокупном вмешательстве и authority программы сохраняются D2.6/CouplingGate, доказанная decomposition и релевантное emergent/system-level grounding. Unknown coupling не означает modularity; сумма stand-alone causal estimates не даёт joint effect. Каждый scoped aggregate имеет свой enrollment/dependency closure, а индивидуальные claims сохраняются.

Структурное обучение имеет отдельный [путь CNT-06/native method → GYD-12](../solutions/18-structural-world-learning.md): фактический study/result и lineage квалифицируют структурное утверждение, после чего единственный world writer проверяет применимое правило записи. O1 effect-posterior и WP-01/02 не заменяют structural warrant. W5-K03 сохраняется в своей области; отсутствие принятого structural write rule ограничивает operative promotion, а не candidate/conditional исследование.

## 6. Автономный поиск и содержательное обучение

LLM предлагает новые механизмы, framing, studies и документы; selected method owners проверяют соответствующие scientific/legal/value predicates. Candidate search может самостоятельно распределять разрешённый бюджет между обратимыми исследованиями по versioned operational exploration profile, не спрашивая политические веса при каждом сравнении. Такое распределение не объявляет социального победителя и не разрешает внешнее действие.

Stopping отделяет исчерпание бюджета, низкую ожидаемую ценность следующей проверки и реальную полноту. OFAT — только main-effect screen; выбранные правдоподобные взаимодействия проверяются bounded predeclared pair/fractional designs. Непроверенные взаимодействия остаются ограничением, не требуют полного factorial перед каждым шагом. Используемое learned warning переносится по релевантным method/version/preconditions; эмпирический negative требует target/transport grounds.

Gross EVSI зависит от decision utility, prior/likelihood и observation law. Стоимость нужна для net value/ranking, ресурсная доступность — для feasibility; отсутствие последних не стирает честный условный gross estimate. Эквивалентность по явной научной или гипотетической margin не означает политической несущественности.

Квалификация opaque LLM provider опирается на стабильный task/use profile и явно заданный envelope, а не новый profile на каждый prompt. Каждый invocation сохраняет exact inputs/outputs/route/context refs; представительная оценка выполняется на profile version, с применимыми критериями. Непрозрачная served identity остаётся неизвестной; alias hash её не создаёт. Drift изменяет eligibility/affected claims по реальному influence, а не автоматически переписывает историю всех результатов.

## 7. Вычислительная устойчивость и будущие обязательства

Один LIF-06 owner планирует по измеряемым enforcement dimensions; OPS-08 исполняет selected deployment profile. DRF применим к сопоставимым делимым residual resources с явной principal/anti-Sybil aggregation; не заменяет правила сроков custody и не подходит автоматически indivisible GPU/storage/rate. Числовые веса, сроки и приоритеты — versioned inputs выбранного service profile, не постоянные универсальные defaults.

До принятия новой currentness-bearing подписи/renewal связываются компетентный owner будущей duty, service profile/cutoff и её покрытие относительно уже принятых обязательств и измеренной capacity. Это не обещание предсказать все отказы; граница покрытия и реакция на outage явны. Infeasible commitment даёт costed refusal, более узкий cutoff/scope или допустимое ограничение, а не молчаливое обещание. Candidate work и несвязанные claims не блокируются.

Lease expiry/cancel не доказывает завершения процесса или внешнего эффекта. Permit удерживается до actual termination/effect reconciliation. Store restore должен сохранять monotonic attempt/epoch либо protected resume отказывает; OPS-12 anti-rollback является таким доказательством только при exact store/generation/restore binding. Unknown due-time predicate отдельно ограничивает claims соответствующей duty; отсутствие overdue event не доказывает своевременность. Модельное, нормативное, наблюдательное и операционное время остаются разными координатами.

Selected local/remote/hybrid/offline profile проверяет свой реальный producer/store/worker/consumer closure. Невыбранные deployment tiers не являются gate. Emergency exception проверяет actual OPS-01 delegation для конкретного scope/action/expiry; role label недостаточен. Разрешённое локальное containment не превращается во внешнее административное полномочие.

## 8. Расширяемость и пределы решения

Новый источник, метод, мера, язык, jurisdiction, resource class или carrier добавляется через существующий typed extension point и собственный semantic falsifier. Новый протокол/physical enforcement может требовать adapter; новая authority semantics — отдельного принятого решения. Конечные таблицы этих карточек не являются закрытой ontology; generic validators выводят набор из выбранного source of truth.

Реализация не должна утратить возможность сравнивать несовместимые основания, показывать векторы вместо одного score, сохранять спор, строить новые studies и возвращать costed refusal-with-a-path. Нельзя скрывать intrinsic non-identifiability за contract completeness. Непроверенная популяция/право/доступ/denominator остаётся конкретным внешним input или исследовательским residual.

[Пять R19 SDD clauses](proposals/r19-system-design-clarifications.md) согласованы и применены 2026-10-24; [каноническая запись](../../../../system-design-decisions/lifecycle-cross-scope-clarifications-r19-ratification.md). Прочие draft scopes не ратифицированы. Независимые инженерные части продолжаются по действующим правилам.

Pattern pass: P01/P02/P03/P04/P05/P07/P08/P10/P14/P15/P27/P29/P31/P32/P35/P37/P38/P40. Target — source-bound meaningful producer→consumer→fresh surface с scoped authority и falsifier; документация не присваивает capability-complete.
