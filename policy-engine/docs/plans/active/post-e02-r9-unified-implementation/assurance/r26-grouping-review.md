# R26: группировка, сохранность scope и review размера

Статус: документация будущего исполнения. Product execution **UNRUN**; E02 не
принимается этим документом. Исходный pin: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`.
[Короткий обзор и точные количества](../execution/work-cards/overview.md) ·
[Документарная проверка](r26-validation.json).

## Что изменено

Вместо выдачи целого широкого parent по историческому префиксу подготовлены
конкретные рабочие карточки. У каждой один primary home по способности системы,
проверяемый результат, предпочтительный native путь, входы/выход/consumer,
owner boundary, независимая подготовка, joint acceptance и falsifiers.

Parent IDs, исходные criteria и debt references, task-level DAG, все extensions,
исторические closures и preferred source rows не переписаны. Parent pages держат
полноту и named joined outputs; groups помогают найти работу, но не образуют
модули, owners или новые очереди. Набор вырос в числе назначений, а не в числе
обещанных возможностей.

## Проверка потери требований

[coverage.json](../execution/work-cards/coverage.json) связывает каждый selected
source fragment с одним accountable route. Это **не атомизация требований**:
один fragment может содержать несколько обязанностей. `clause_uses` и named
supplier outputs сохраняют такие подрезультаты без двойного учёта fragment.
Inherited поля отдельно сохраняют identity/source IDs, owners/leases, scope,
stages, conditional/execution rules и зеркальные extensions. Root/lead отвечает
за весь parent; leaf получает только нужный operative closure, а не скрытый
приказ реализовать siblings через ссылку «прочитать весь parent».

Полнота маршрутизации проверена по всему JSON-набору, а не выборке. Смысл каждой
новой карточки просмотрен автором соответствующего разреза и root; отдельный
cross-review атаковал зависимости и стыки владельцев. Это не новое полное
исследование всех транзитивных исторических документов или принятых будущих
кодовых paths. После E02 original-set/source delta и actual consumer closure
подлежат обязательному rebind; прежняя source-qualified проверка не переносится
на изменённые bytes автоматически.

## Исправления, сделанные в ходе review

| Найденная проблема | Исправление и граница |
|---|---|
| Direct, acceptance и conditional supplier links смешивались в одном списке | У routes отдельные source selectors, applicability и stages. Только canonical direct relations определяют свой preparation stage; дополнительные interface links не создают gate. |
| Неусловный список joins делал optional/альтернативные пути обязательными | У potential composition links явные conditions; independent route eligibility, design-only и native-event/observation сохраняют свой scope. Нет общего joins-DAG/all-of. |
| Reciprocal `after` превращали права/актуальность/recovery в цикл ожидания | Actual outputs перемещены в composition joins; подготовка против согласованного contract независима. Реальные source, permission и effect boundaries сохраняются. |
| UI-15 Docs IA не имела своего source clause | Назначен exact implementation clause и explicit consume DS11 posture; Docs не пишет status и не создаёт второй claim register. |
| Mixed DEB-09 fragment терял отдельный epoch-qualification результат | Один primary route плюс отдельный subclause consumer; роли signer/holder/delegation/qualification не взаимозаменяемы. |
| CAP-03 cost card только ожидала уже готовый cost artifact | Карточка явно выполняет native admission/cost companion; единственный schedule writer остаётся acquisition_planner, DEB-07 reconciles, DEB-13 consumes. Measured/justified estimate/paid-source bases различны. |
| Internal unallocated caller/reader выглядел внешним вечным блокером | Task lead обязан исследовать actual native seam и назначить repair; реальные institutional acts, authority и данные остаются отдельными inputs. |
| FA1 receipt/trust/toolchain могли дублировать общую инфраструктуру | GYD-15 потребляет canonical CAS/OPS/source-right evidence на N8; cutoff independence остаётся отдельным predicate. |
| LIF-05 restore wording конкурировала с OPS-05 | LIF-05 выдаёт placement rights/retention/existence result; OPS-05 владеет quarantine/cut/physical enablement; LIF-02 — claim currentness. Один actual reader fence соединяет эти outputs. |
| LIF-02 operative map теряла standing-duty и selected-capacity inputs | Добавлены точные conditional LIF-04/OPS-11/LIF-06/OPS-08 joins. UI читает результат LIF-02; новой UI→OPS-11 start dependency нет. |
| Selected deployment без objective мог становиться unselected | Выбранная/mandatory ветка с отсутствующим input остаётся limited/blocked; unselected допустим только в исходно условном scope с reentry trigger. |
| OPS-05 byte-release ошибочно требовала restore receipt для всех reads | Exact immutable object/version и actual reader/sink проверяются для любого выбранного read; restore-cut provenance обязательна только для восстановленного объекта. |
| LIF-09 witness preparation ожидала общего freeze/owner closure | Подготовка native route/oracle независима; actual selected-row run потребляет frozen accepted source/input/backend identities через composition join. |
| DES-12 делала исследовательский return необходимым для prospective EVSI | Предварительная EVSI использует обоснованный predictive model/current evidence; фактический return позже обновляет/проверяет оценку. Нет универсального EVSI gate или ожидания permission для подготовки adapter. |
| Общая LLM invocation и legal-branch цепь была неявна | Добавлены selected consumption links DES-09→DES-05/06/08 и DES-05/GYD-05→DES-06, без blanket provider requirement. |
| CNT-08/09 prose расширяла currentness и UI-17 ownership | LIF-07 даёт influence closure, LIF-02 меняет currentness; UI-17 владеет выбранной acquisition surface, остальные readers остаются у native owners. |

## Размер и отсутствие скрытого задания

Split проходит по independently falsifiable output, а не по папке, transport,
числу строк или всем вариантам status. В частности, права и фактическое release,
историческая authentication и currentness, numerical trial и frontier,
private document и edit-back, evaluation campaigns и institutional acts имеют
разные условия и результаты. Их общий writer/contract не размножается.

Неделимые invariants оставлены целиком: complete-set census, shared grammar,
source-qualified FDR, единая memory-transfer chain. Для длинных, но связных
DES-06/DES-08 явно названы checkpoints. P0/FINAL — coordination, не маленькие code
задачи. Parent join не выдаёт скрытую инженерную работу интегратору: отсутствующий
bridge получает назначенную карточку/owner или явный typed residual.

Число source fragments и длина текста использованы для поиска перегрузки,
**не как лимит**. Exact-path/write/resource overlap устанавливается по принятому
E02; совпадающий namespace нельзя считать доказательством независимости.
Generated family и shared native file имеют одного writer; независимы только
действительно разные подготовка, чтение и oracles. Никакое число карточек не
обещает такое же количество параллельных исполнителей.

## Происхождение review и остатки

Девять прямых помощников проработали все семейства, десятый отдельно атаковал
маршруты и dependency semantics. Повторные cross-reviews проверили связки
Atlas/LIF/OPS, GYD/DEB/CAP, DES/Atlas/Legal и внутренние after/joins. Root сверил
каждый новый результат/solution/consumer, исправил выявленные неоднозначности
и перечитал generated documents. Ни один помощник не создавал детей и не менял
продуктовый код; root один собирал tracked документацию.

После materialization независимый cold read обнаружил два остатка OPS-05/LIF-09,
указанные выше. Они исправлены; повторное чтение точных карточек и registry дало
bounded GO. Это проверка изменённой dependency/optionality границы, не новая
приёмка всех runtime свойств. Полный журнал —
`policy-engine/_build/post-e02-r26-groups-20261024/cross-review-delta.md`.

Исходные ignored reports и полные deciding outputs сохранены рядом с receipt
под `policy-engine/_build/post-e02-r26-groups-20261024/`; tracked registry хранит
их paths/digests. Итоговые карточки/coverage остаются самодостаточными в Git,
полные исходные manifests цитируются, а не копируются в отчёты.

Остатки: фактическая приёмка E02; accepted-source/code/generated/interface rebind;
реальные внешние acts/data и selected deployment/resource/backend inputs;
independent code review и real-path positive/negative/removal во время исполнения.
Structural PASS подтверждает только перечисленные свойства документации.
Он не доказывает, что весь будущий runtime заработал или что новых нюансов не будет.

Pattern pass: P01/P02/P03/P13/P27/P29/P31/P35/P37/P38/P39/P40.
Разделение работы сохраняет исходный смысл и native owners; status/authority,
rule/time/provenance, действующие ограничения и original closure не ослаблены.
