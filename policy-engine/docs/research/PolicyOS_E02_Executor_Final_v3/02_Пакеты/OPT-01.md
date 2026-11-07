# OPT-01 — Полная неизменная координата и полезный Pareto-фронт

**LANE-02 · B108, B109, B110, B111 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/OPT-01.md), [исходная карточка](../05_Основания/Аудит/05_Источники/OPT-01_исходные_строки.txt), строки 2251–2385.
**Практический результат:** Получить из настоящих измерений согласованный фронт и перечитать его без потери split/unit/direction; не объявлять частичный набор полным пространством политик.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Direct deficit aliases с необходимыми units; missing/null/zero/conflicts различены.
- Balance-stock не становится period deficit по одному имени; нормальный declared mapping нужен отдельно.
- Исправленные 2D/3D сравнения и distinct equal identities.
- Направления нормализуются до сравнения; независимый slow oracle остаётся в тестах, не заменяет production fast algorithm.
- Canonical metric/split/unit-state/unit/direction hash; duplicate refusal; display отделён.
- Настоящие Pydantic schema/hash/key-set checks и JSON сохранение tradeoff.
- Missing/nonfinite отдельно от usable subset; точные omission indexes/ids.
- Known witness допускает True, partial assessment не даёт неподтверждённое False.
- Finite reference/HV guards; пустой набор не становится numeric infinity.
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C18_остатки:0 | REQ-OPT-01-01 | fix: C18-R01: active schema до Boolean. |
| audit-residual:C18_остатки:1 | REQ-OPT-01-02 | fix: C18-R02: immutable effective snapshot. |
| audit-residual:C18_остатки:2 | REQ-OPT-01-03 | fix: Canonical identity не потеряна; исправляется display boundary. |
| audit-residual:C18_остатки:3 | REQ-OPT-01-03 | qualify: Source split/unit qualification, не доказанный holdout bypass. |
| audit-residual:C18_остатки:4 | REQ-OPT-01-06 | qualify: Объявленное approximation не выдавать за exact. |
| audit-residual:C18_остатки:5 | REQ-OPT-01-05 | capability: Реальный law/producer/consumer и корректный stock-flow смысл. |
| B108 | REQ-OPT-01-05 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B109 | REQ-OPT-01-04 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B110 | REQ-OPT-01-01, REQ-OPT-01-02, REQ-OPT-01-03 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B111 | REQ-OPT-01-01, REQ-OPT-01-03, REQ-OPT-01-04, REQ-OPT-01-06 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0171 | REQ-OPT-01-05 | qualify: Настоящее measurement→objective→consumer, не source-only. |
| remaining:0172 | REQ-OPT-01-05 | fix: Предметный закон stock/flow и cross-family reconciliation. |
| remaining:0173 | REQ-OPT-01-04 | qualify: Native comparator и выбранный consumer. |
| remaining:0174 | REQ-OPT-01-04 | qualify: Актуальный provider-path отдельно от исторического census. |
| remaining:0175 | REQ-OPT-01-01 | fix: Активная canonical schema. |
| remaining:0176 | REQ-OPT-01-02 | fix: Изоляция входного и выходного договора. |
| remaining:0177 | REQ-OPT-01-03 | fix: Display и фактическая split/unit basis. |
| remaining:0178 | REQ-OPT-01-03 | qualify: Producer→CAS→registry→fresh reader. |
| remaining:0179 | REQ-OPT-01-01, REQ-OPT-01-04 | fix: Foreign schema отказ, partial semantics сохраняется. |
| remaining:0180 | REQ-OPT-01-06 | qualify: Proxy и exact HV различены; input universe ограничен. |

## 3. Нормативные REQ и конкретное решение

### REQ-OPT-01-01 — fix
Перед is_dominated сравнивать complete-схему front с активным эффективным договором; несовместимость не возвращает False.

**Решение на существующих владельцах.** В ParetoPromoter.is_dominated после внутренней DTO-validation сопоставить canonical coordinate IDs/definitions, не display-label и не порядок списка. При различии вернуть существующий адресный отказ сравнения; разрешённое преобразование требует явного adapter и новой basis. Не принуждать True. Положительное свидетельство partial front сохраняется только на совместимой схеме.
**Приёмка:** TEST-OPT-01-01.

### REQ-OPT-01-02 — fix
Эффективная comparison policy и выдаваемые snapshots не изменяются через caller alias.

**Решение на существующих владельцах.** В конструкторе promoter создать маленький immutable/deep-copied contract metric/split/unit/direction. Чтение значений, IDs и schema использовать из одного снимка. DTO результата получает независимую схему; embedded evaluation должен быть согласованным snapshot либо immutable ref, а не изменяемым источником против сохранённых coordinate_values. Не deepcopy сервисы/datasets. Явная смена цели создаёт новый owner/basis.
**Приёмка:** TEST-OPT-01-02.

### REQ-OPT-01-03 — fix
Полная canonical coordinate сохраняется в реальном registry/CAS/readback; display collision и неподтверждённый split/unit не маскируются.

**Решение на существующих владельцах.** Сохранить существующие coordinate IDs в ParetoRegistry consumer. Legacy display-label сделать однозначным только на display-границе либо вернуть explicit collision limitation; не менять математическую identity ради labels. Взять actual BenchmarkEvaluation producer и связать runtime split/unit с policy перед принятием значения: общий holdout dict не доказывает hidden_holdout. Не заявлять обход доступа по локальному adapter.
**Приёмка:** TEST-OPT-01-03.

### REQ-OPT-01-04 — qualify
Квалифицировать существующий strict comparator и частичный полезный фронт без переписывания исправленного алгоритма.

**Решение на существующих владельцах.** Расширить существующий test_pareto малым независимым slow oracle; production 2D/3D skyline оставить быстрым. Проверить направления, равенства с разными candidate IDs, input permutations и сохранённые omission records у настоящего consumer. Прежний registered-provider census не является текущим отсутствием provider: выбрать действующий путь по checkout.
**Приёмка:** TEST-OPT-01-04.

### REQ-OPT-01-05 — capability
Фискальный score получать по объявленному measurement law, не отождествляя balance-stock и period deficit по ключу.

**Решение на существующих владельцах.** В существующем objective/source adapter определить поддержанный профиль period, sign, unit и cross-family reconciliation. Direct deficit с units сохраняется, настоящий zero не missing. Если stock/flow действительно преобразуются — требовать наблюдаемые входы закона/период и фиксировать derived basis. Иначе stock-only остаётся not_established. Проверку конфликта balance/deficit применять только к заявленно эквивалентным величинам, а не к законно различным stock и flow.
**Приёмка:** TEST-OPT-01-05.

### REQ-OPT-01-06 — fix
Hypervolume потреблять с явным алгоритмом, reference и пределом точности.

**Решение на существующих владельцах.** Сохранить точную 2D rectangle-union реализацию. Для >2D нынешний bounding-box proxy маркировать как approximation в доступном indicator contract/consumer; если consumer требует exact HV, подключить обоснованный алгоритм отдельно, не переименовывать proxy. Сравнение поколений только на одном declared finite reference и coordinate basis.
**Приёмка:** TEST-OPT-01-06.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-OPT-01-01 · NOT_RUN
- **Setup:** Front holdout score=2; queried score=1; fresh JSON reader; четыре owner со сменой metric/split/unit/direction и переставленная эквивалентная схема.
- **Действие:** Вызвать реальный is_dominated после round-trip, затем повторить на partial front с known witness.
- **Oracle:** Совместимый witness True; чужая полная схема — конкретная несовместимость, не False; порядок тех же осей не меняет отношение.
- **Positive / negative / boundary:** Complete same-basis без witness даёт False; partial без witness не даёт доказанного False; missing query не сравним.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-OPT-01-02 · NOT_RUN
- **Setup:** Один mutable PromotionPolicy maximize selection, A=2/B=1 и holdout A=9; вычисленный front.
- **Действие:** Изменить caller direction/split; изменить returned coordinate_schema и исходную evaluation; повторно вычислить и сериализовать старый/новый результат.
- **Oracle:** Старый owner сохраняет исходный смысл и hash; old snapshot внутренне согласован; новый явный contract выбирает согласно новой цели.
- **Positive / negative / boundary:** Нет обратного влияния old front на следующий; сохраняются duplicate-coordinate refusal и Pydantic hash/key validation.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-OPT-01-03 · NOT_RUN
- **Setup:** Два score split и delimiter-containing metric; источник с заявленным holdout и policy hidden_holdout; настоящий разрешённый store и registry.
- **Действие:** Producer→evaluation→compute_front→persist→fresh reader; проверить обе оси и source basis, затем несовместимый split.
- **Oracle:** Canonical tradeoff и IDs сохранены; display не теряет ось; непроверенный hidden split/unit не получает measured label.
- **Positive / negative / boundary:** Обычный authorized split проходит; malformed/hash tamper/missing coordinate отказ адресный, не общее отключение исследования.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-OPT-01-04 · NOT_RUN
- **Setup:** Сетка {-1,0,1} в 1–4 измерениях, равные кандидаты с разными refs, один invalid и один measured кандидат; actual registry.
- **Действие:** Сопоставить membership с определением weak-all/strict-one, затем перечитать partial result и пройти выбранный consumer.
- **Oracle:** Fast и slow фронты совпадают; invalid не становится бесконечностью; полезный assessed subset доступен с partial status.
- **Positive / negative / boundary:** Контроль <=→< обнаруживается исходными 2D/3D контрпримерами; ни один равный ID не исчезает; complete относится лишь к входной последовательности.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-OPT-01-05 · NOT_RUN
- **Setup:** Настоящий producer с direct deficit, эквивалентным по документированному закону представлением, missing/null/0/conflict и stock-only.
- **Действие:** Пройти source observation→BudgetDeficitObjective→search consumer с readback, сравнить score и basis.
- **Oracle:** Эквивалентные измерения одной величины дают одинаковый score; stock-only не притворяется периодным потоком; законные разные величины не образуют ложный конфликт.
- **Positive / negative / boundary:** Без unit/law ограничивается эта координата; другой полезный objective/candidate путь сохраняется; нет favourable invented zero.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-OPT-01-06 · NOT_RUN
- **Setup:** 2D oracle и 3D points (10,1,1),(1,10,1),(1,1,10) с нулевым reference; empty/invalid reference.
- **Действие:** Вычислить и сохранить indicator, прочитать actual reporting/ranking consumer.
- **Oracle:** 2D exact=8 для принятого fixture; 3D proxy=1000 не назван exact union=28; несовместимые references не дают сравнимое улучшение.
- **Positive / negative / boundary:** Reference/result finite либо explicit unavailable; пустота не превращается в infinity; membership не меняется ради indicator.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-B**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- OPT-02 делит autotune файлы: один writer на общий контракт; этот пакет владеет Pareto coordinate schema.
- OPT-04 потребляет comparison basis, но владеет champion publication и atomic registry.
- LAW/measurement owner даёт предметный закон; не выдумывать его в generic Pareto layer.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.



## 8. Ограниченные решения

- **DEC-OPT-01-01**: Какой фискальный профиль и преобразование действительно поддержаны текущим producer? Owner: OPT-01 с владельцем measurement law. Варианты: direct period-deficit с явно связанными units/period; вычисление из stock transitions при наличии всех входов закона; stock-only остаётся not_established. Выбор по: Схема actual producer, единицы, период и различающий source→consumer fixture. Обязательный выход: Версионированный adapter contract и два действительно эквивалентных представления; без научного утверждения по одному имени ключа.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/methods/autotune/pareto.py:268–300](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/pareto.py#L268-L300) — `class ParetoPromoter`.
- [policy-engine/src/polisyos/scientist/methods/autotune/pareto.py:385–417](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/pareto.py#L385-L417) — `    def is_dominated(`.
- [policy-engine/src/polisyos/scientist/methods/search/objective.py:2072–2104](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/objective.py#L2072-L2104) — `elif kind == "budget_deficit":`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0286 | REQ-OPT-01-05, TEST-OPT-01-05 | Direct deficit aliases с необходимыми units; missing/null/zero/conflicts различены. |
| preserve:0287 | REQ-OPT-01-05, TEST-OPT-01-05 | Balance-stock не становится period deficit по одному имени; нормальный declared mapping нужен отдельно. |
| preserve:0288 | REQ-OPT-01-04, TEST-OPT-01-04 | Исправленные 2D/3D сравнения и distinct equal identities. |
| preserve:0289 | REQ-OPT-01-04, TEST-OPT-01-04 | Направления нормализуются до сравнения; независимый slow oracle остаётся в тестах, не заменяет production fast algorithm. |
| preserve:0290 | REQ-OPT-01-01, REQ-OPT-01-02, REQ-OPT-01-03, TEST-OPT-01-01, TEST-OPT-01-02, TEST-OPT-01-03 | Canonical metric/split/unit-state/unit/direction hash; duplicate refusal; display отделён. |
| preserve:0291 | REQ-OPT-01-01, REQ-OPT-01-02, REQ-OPT-01-03, TEST-OPT-01-01, TEST-OPT-01-02, TEST-OPT-01-03 | Настоящие Pydantic schema/hash/key-set checks и JSON сохранение tradeoff. |
| preserve:0292 | REQ-OPT-01-04, TEST-OPT-01-04 | Missing/nonfinite отдельно от usable subset; точные omission indexes/ids. |
| preserve:0293 | REQ-OPT-01-01, REQ-OPT-01-04, TEST-OPT-01-01, TEST-OPT-01-04 | Known witness допускает True, partial assessment не даёт неподтверждённое False. |
| preserve:0294 | REQ-OPT-01-06, TEST-OPT-01-06 | Finite reference/HV guards; пустой набор не становится numeric infinity. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/OPT-01.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
