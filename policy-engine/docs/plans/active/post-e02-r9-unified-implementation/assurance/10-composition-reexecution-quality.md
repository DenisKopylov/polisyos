# R16: независимые проверки композиции и пересчёта

Это **спецификация будущих проверок**, не результаты запуска. Все product checks — UNRUN; исполнение после фактической приёмки E02. [Работы C1–C8](../solutions/16-composed-execution-and-revisions.md), [архитектура](../architecture/06-composition-and-reexecution.md), [обязательства](r16-capability-obligations.json). Исходные GY, Atlas, R9, DES и R15 критерии сохраняются; эти случаи их дополняют, не заменяют.

## Как проверять

Каждый selected case проходит реальный producer → persisted native artifact → bridge → свежий отдельный consumer и заявленную поверхность. Positive должен демонстрировать полезный результат. Набор из одних отказов не проходит. Удаление свойства при сохранённых полях/markers должно разрушать соответствующий semantic discriminator. Автор метода не автор окончательного независимого oracle. Малые аналитические модели проверяют алгоритм; для social/scientific validity нужны отдельные основания.

Заранее фиксировать source, inputs, method/executable/backend, target, information cut, допустимую численную гарантию, oracle и полный denominator. Сравнивать fresh и selective execution на одном basis. Для stochastic methods: exact replay относится только к заявленному deterministic sample-path profile; distributional agreement проверяется своим заранее выбранным statistical criterion. Same seed и похожее среднее сами по себе не критерий. Записать failures, skips, omissions и uncertainty; не складывать перекрывающиеся test counts.

<a id="Q01"></a>
## Q01 — Actual graph order и полнота исполнения

- **Positive:** graph A→B→C, artifact B действительно зависит от выхода A, C — от B; фактический полный порядок и active denominator доходят до fresh reader.
- **Adversarial:** поменять raw node list на C,B,A при пустом ExecPlan.order; затем omit/duplicate/unknown required node, undeclared active edge и неверный prune. Compiler либо строит и связывает правильный order, либо отказывает, не молча исполняет неполный plan.
- **Removal:** оставить schema/order labels, удалить проверку настоящей dependency/coverage; независимый output oracle выявляет ошибку. Поддержанный dynamic branch включается через native owner, а не отвергается только за динамичность.

<a id="Q02"></a>
## Q02 — Observation, intervention, mechanism, scenario

- **Positive:** для M1: X=U,Y=X и M2: X=U,Y=U, U~Bernoulli(1/2), observational distributions совпадают. При do(X=1) E[Y] различаются: 1 и 1/2. Отдельный scenario меняет распределение U с явным assumption; отдельная replacement mechanism меняет уравнение Y. Все четыре операции различимы в result/basis/consumer.
- **Adversarial:** принять conditioning on X=1 за do(X=1); заменить scenario assumption текущим наблюдением; same observational fit объявить interventional interchangeability.
- **Removal:** убрать structural/operation binding, сохранив заголовок «causal»; oracle и fresh comparison обнаруживают loss. Ни один controlled result не активирует operative world автоматически.

<a id="Q03"></a>
## Q03 — Joint fixed point и множественность

- **Positive:** x=1+y/2, y=2+x/4 дают x=16/7,y=18/7; joint result отличается от isolated one-pass. Два связанных native participants и fresh joint consumer должны согласоваться с независимым Fraction oracle в заявленной tolerance.
- **Adversarial:** x=1−x осциллирует при plain Picard, хотя root 1/2 существует; x=x² имеет roots 0 и 1. Nonconvergence не означает policy infeasible; выбор start не доказывает unique/socially preferred equilibrium. Unsupported cycle typed-refused без блокировки независимого DAG.
- **Removal:** заменить coupled execution однократным проходом, оставить convergence markers — oracle fails. Полная проверка joint effects не ограничивается pairwise compatibility.

<a id="Q04"></a>
## Q04 — Полная state purity и finalization

- **Positive:** для selected deterministic map сделать T(x),T(y),T(x) из одного допустимого initial state; одинаковые relevant outputs/state relation. Чистая функция не обязана сериализовать несуществующее mutable state. Все stateful participants имеют совместимый reset/replay либо честный narrower profile.
- **Adversarial:** participant скрыто увеличивает counter/RNG, remote member делает необратимый charge, final materialization использует иной input/state или вносит новый side effect. Старый residual не относится к новому result.
- **SCC-in-DAG discriminator:** перед/после coupled block поставить наблюдаемый one-shot source/effect. Bound block-only execution вызывает upstream acquisition один раз до solve, downstream effect только после выбранной finalization; full-plan callback обязан включить эти calls в actual purity/effect/resource denominator и отказаться от repeatability claim при non-repeatable member. Не считать «node вне SCC» доказательством отсутствия вызова.
- **Removal:** выключить actual map-closure binding, reset/replay или final actual-residual check при сохранённых state hashes/solver flag — свойство нарушается. Резерв на finalization входит в бюджет; отсутствие последнего обязательного подтверждения остаётся incomplete.

<a id="Q05"></a>
## Q05 — Multi-rate, события и late correction

- **Positive:** temporal producer и consumer с разными supported steps передают stock/flow по выбранной interpolation/aggregation law. Поздняя correction меняет affected suffix от совместимого checkpoint; старый lawfully retained as-known-then result читается неизменным; при обязательном удалении сохраняется разрешённая historical/deletion projection с unavailable replay.
- **Adversarial:** event time принять за knowledge availability; restored participant clock не совпадает с другими; rate передать как amount, двойной учет boundary event, zero-time event loop, одинаковые timestamps со значимым различным порядком.
- **Removal:** убрать cutoff/clock/state-consistency consumption; независимый timeline/quantity oracle обнаруживает future leakage или двойной учет. Для неподдержанного calendar/event semantics отказ ограничен соответствующим coupling.

<a id="Q06"></a>
## Q06 — Selective reuse и настоящий rerun

- **Positive:** в Q03 заменить a в x=a+y/2 с 1 на 2: x=24/7,y=20/7. Независимый u=7×2 остаётся reusable. Actual admitted change → durable continuation → actual native computation → new fresh reader; selective result совпадает с clean recompute по declared guarantee. Счётчики вызываемых participants подтверждают затронутую область и useful reuse.
- **Adversarial:** dirty event есть, actual dispatch отсутствует; stale artifact назван новым; recompute по другим inputs; empty read-set ошибочно принят complete; все outputs каждый раз отказаны.
- **Removal:** убрать rerun bridge или required invalidation edge, сохранив events/fields; positive/new-basis oracle fails. Без standing duty система честно показывает next action вместо фиктивной автоматичности.

<a id="Q07"></a>
## Q07 — Отрицательные и динамические зависимости

- **Positive:** при отсутствии selected FX rate/query result фиксируется scoped negative/membership dependency; появление записи меняет calculation либо разрешает прежний typed limitation. Изменение branch condition пересобирает actual read-set и result.
- **Adversarial:** cache учитывает только прочитанные present records; adapter скрыто читает environment/file/network; каталог changed вне старого positive membership; query с неполным index ошибочно доказывает absence.
- **Removal:** удалить negative-dependency registration при сохранённых input list и cache hit — fresh-recompute comparison fails. Неполный read-set запускает conservative scoped recompute/limitation, не фиктивный exact cache hit. Private absence/hash не раскрывается чужому audience.

<a id="Q08"></a>
## Q08 — Равное число, иная семантика/use

- **Positive:** numerically unchanged output при изменении права, construct, support или selection basis получает нужную новую qualification и public reaction. Authority-only revision не требует бессмысленного повторения deterministic arithmetic.
- **Adversarial:** scalar-equality pruning прекращает rights/currentness cascade; old valid admission переносится на новый purpose/tenant; одинаковые marginal means скрывают иную joint distribution/correlation.
- **Removal:** удалить use/semantic check, оставить numeric result и lineage markers; actual protected consumer перестаёт корректно отказывать/ограничивать. История не уничтожается из-за утраты current authority; lawful retention/use оцениваются отдельно.

<a id="Q09"></a>
## Q09 — Coherent cut, enrollment и recovery

- **Positive:** registered source vector указывает incarnation/position каждого source и проверенный consistency scope; enrollment C→W replay применяет actual events, fresh head учитывает их.
- **Adversarial:** событие между snapshot и subscription; crash после effect до ack; offset reset; cursor ниже retention floor; один watermark выдан за all-source atomic snapshot; incompatible release components склеены. Duplicate delivery idempotent в объявленной effect domain.
- **Removal:** удалить enrollment replay/currentness fence или source-incarnation check; targeted interleaving обнаруживает stale current result. Это не обещание global exactly-once across CAS/SQL/provider.

<a id="Q10"></a>
## Q10 — Evidence dependence, correction и retraction

- **Positive:** Beta(1,1) и один Bernoulli success при bound sampling/selection profile дают posterior mean 2/3. Повторная доставка того же observation не меняет 2/3; второе success, **условно независимое при фиксированном общем θ в той же sampling model** даёт 3/4. Retraction единственного observation возвращает prior при поддержанном lawful refit; original published-as-of history сохраняется.
- **Adversarial:** две статьи об одной cohort считаются двумя trials; correlated D2 использует p(D2|theta) без основания вместо p(D2|theta,D1); posterior summary объявлен обратимым; удалённый record недоступен для обязательного refit; retrospective smoothing переименован в знание на прошлую дату.
- **Removal:** удалить duplicate/dependence/retraction consumption, сохранив evidence refs; independent oracle/claim consumer fails. При неподдержанном update honest limitation допустима, но toy supported positive всё равно нужен. Не навязывать Bayesian представление всем методам.

<a id="Q11"></a>
## Q11 — Candidate learning и authorized world activation

- **Positive:** новое evidence изменяет candidate/model-sensitive comparison; только actual qualified O1/O3 route меняет operative world и его consumer. Hypothetical branch остаётся доступной без присвоения authority.
- **Adversarial:** discovery O2, LLM proposal, surrogate или remembered winner активирует world; model average использует выдуманные вероятности; два siblings одного evidence объявлены независимыми.
- **Removal:** убрать activation/dependence bridge check при сохранённых «validated» полях — protected consumer fails. Positive полезного exploratory поиска сохраняется, но его result не повышается автоматически.

<a id="Q12"></a>
## Q12 — Executable и structural identity

- **Positive:** изменить executable/mapping/model law при неизменных именах/ABI и одинаковом baseline number; affected descendants получают новый computation identity и interventional checks. Для Q03 заменить y=2+x/4 на y=2: при a=1 получается x=2,y=2.
- **Adversarial:** old cache/resume принят по method FQN, schema version или slot names; checkpoint state мигрирован без применимого state law; новый target support принят за прежний estimand.
- **Removal:** убрать actual executable/structural dependency binding, сохранив version labels — new-mechanism oracle fails. Verified no-effect equivalence может обосновать bounded reuse, но не назначается по сходству имён.

<a id="Q13"></a>
## Q13 — Competing revisions, cancellation, fairness

- **Positive:** pause trial A; admit and finish relevant B; resume A. A сохраняется как historical result и не перезаписывает desired current head своего branch. Независимый scenario branch C может завершиться отдельно. Coalesced calculations ссылаются на полный принятый event history.
- **Adversarial:** бесконечный update stream всегда переносит запуск «на потом»; cancel/lease expiry освобождает занятую capacity; lost event при dedupe commit; coalescing скрывает revocation; один global lock блокирует unrelated branches.
- **Removal:** убрать completion fence, actual dispatch или event-before-coalescing rule; interleaving/continuation positive fails. Duty имеет selected bounded lag/fairness/terminal policy; исчерпание не объявляется mathematical infeasibility.

<a id="Q14"></a>
## Q14 — Численная честность и stochastic coupling

- **Positive:** tolerance/scaling относится к actual declared quantities и final materialized result. Для fixed sample-path deterministic mode frozen shocks привязаны к semantic entities/time, а не только seed. Expected-map/stochastic approximation имеет свой validated stopping/inference rule.
- **Adversarial:** T(x)=(1−ε)x+ε имеет root 1, но в x=0 residual ε может быть мал при ошибке 1; поэтому small residual без conditioning/error law не даёт small solution/policy error. Шаг h/2 может не уменьшить communication error при variable-step co-simulation. Идентичные marginal uncertainty intervals скрывают dependence.
- **Expected-map false-green:** на R задать Tω(x)=x+δ+ξ, δ>0, ξ=±δ с равными вероятностями. E[Tω(x)]=x+δ не имеет fixed point, но realization ξ=−δ даёт нулевой sampled residual. Сохранённый `noise_sd` и zero residual не должны пройти expected-equilibrium admission сами по себе; нужен выбранный validated stochastic criterion/его sufficient evidence или typed limitation. Fixed frozen-path statement остаётся иной, явно условной guarantee. Не добавлять clipping/projection, меняющую этот oracle.
- **Removal:** удалить claimed actual residual/error/stochastic contract check; соответствующий oracle обнаруживает ложную гарантию. Domain conservation проверяется лишь для conserved quantity с bound sources/sinks; не для произвольной social metric.

<a id="Q15"></a>
## Q15 — Free-grow и second consumer

- **Positive:** добавить третьего conforming participant через реальный registry/bootstrap, не central family switch. Его output реально меняет supported composition и читается как минимум non-first consumer; installed/public route проверяется при таком claim.
- **Adversarial:** registry entry есть, dispatch не вызывает implementation; новые required clock/state/semantic facets игнорируются; plugin import разрешает arbitrary downloaded code; новая conforming family требует per-family hard-coded dispatch branch. Owner-reviewed declarative registration, security admission и adapter для действительно нового semantic class допустимы; они не ложная потеря free-grow.
- **Requiredness discriminator:** изменить content-bound owning consumer/profile contract так, что новая facet обязательна; adapter продолжает её опускать или называет optional. Verifier выводит requirement из настоящего versioned producer/consumer/profile contract и отказывает/ограничивает dependent guarantee; self-declared adapter list не может сузить denominator. Missing/conflicting owner contract не трактуется как пустое множество требований.
- **Removal:** удалить owner-derived requiredness, actual third-participant dispatch или non-first consumer binding, оставив registration/labels — semantic positive fails. Новый неподдержанный semantic class требует reviewed adapter, но не блокирует supported native graph.

<a id="Q16"></a>
## Q16 — Полный resource/effect denominator

- **Positive:** budget покрывает all actual participant calls в multistart/Jacobian/retry, held permits, read/spill/CAS/checkpoint bytes и terminal reserve. Nested child не deadlocks за permit, удерживаемым ожидающим parent. Process termination reconciled отдельно от cancel request.
- **Adversarial:** стоимость одного graph выдана за полную; hidden expensive provider call; duplicated external charge; incomplete member default-zero; final publish превышает budget; one-shot remote effect поставлен внутрь repeatable map; cross-tenant reuse раскрывает existence.
- **Removal:** убрать aggregate accounting/effect admission, оставив cost fields — counter/control detects excess or unauthorized effect. Measured bounded work/RSS не доказывают scientific validity; encryption не доказывает population adequacy. Remote cells условны по deployment profile, не общий blocker локального случая.

<a id="Q17"></a>
## Q17 — Полный полезный design/research cycle

Связать в одном небольшом native case: initial composition → новое наблюдение → selective rerun → alternative mechanism → separate scenario → model-sensitive comparison → decision-informative study proposal → controlled independent returned evidence → разрешённый revised dossier/currentness. Positive показывает changed recommendation либо содержательно доказанную устойчивость; специально выбранный discriminatory toy обязан различать варианты. Uninformative duplicate не считается новым подтверждением. Фактическое институциональное исполнение study не имитируется.

Удалить по отдельности actual joint participant, rerun dispatch, study-return bridge и fresh surface consumption при сохранённых красивых текстах/markers: соответствующая полезная capability должна перестать проходить. Полные authority/status/time/reason fields берутся от owners, UI/LLM не вычисляет их заново. Для fairness/utility использовать matched compute/input/profile baseline, held-out stress cases и полный denominator, не выбирать post-hoc удобные сценарии. Исходный GY-AS2 сохраняется.

## Freeze и отчётность

Scoped proofs выполняются владельцами после E02. Все selected Q-cases входят в existing FINAL-FREEZE → FINAL-REVIEW → FINAL-REPLAY; отдельной дорогой глобальной волны R16 нет. Неподдержанная optional profile получает explicit disposition; required capability не исчезает из denominator. Report различает source implementation, useful behavior, mathematical guarantee, external validity и current lawful/public use. Historical E02 closures не меняются.

Pattern pass: P01/P02/P04/P05/P07/P08/P10/P14/P15/P27/P29/P31/P32/P33/P35/P37/P38/P40/P41. До реализации конкретные gaps — `bridge_missing`, `verification_missing`, иногда `consumer_missing`/`surface_missing`; точное текущее состояние устанавливает accepted-E02 rebind, не этот исследовательский документ. Новая атака классифицируется как новый класс или пример уже описанного residual; не запускать бесконечную лестницу per-fixture repairs.

## R23: различающие дополнения к Q06/Q09/Q13/Q14

- **Cache и случайность:** один qualified frozen realization проходит свой
  cache-on/off replay criterion. Новый native stochastic replicate получает новый
  invocation/draw basis и проверяется по заранее выбранному scientific guarantee.
  Разные допустимые samples сами по себе не cache defect; повтор старого draw как
  нового независимого evidence — defect. Убрать invocation relation при сохранённых
  seed/cache labels: второй случай обязан обнаруживаться. Distributional agreement
  не восстанавливает утраченный exact historical artifact.
- **Порядок observations:** медленный poll A начинает раньше B, B видит изменение
  и fences use, затем A возвращает старые bytes. Local completion position не
  снимает fence. Qualified follow-up восстанавливает лишь поддержанную as-of
  гарантию; независимый scope продолжает работу. Удаление expected-head/order
  reconciliation при сохранённых journal labels разрушает этот discriminator.
- **Прогресс:** поток review markers/retry IDs не засчитывается за actual service
  и не сбрасывает overdue age. Реальный policy-bound review outcome оставляет
  accountable continuation/transfer/cutoff либо явно unresolved coverage. Убрать
  affected custody reaction, оставить metrics — claim consumer выявляет ложную
  актуальность. Best-effort expiry не доказывает гарантию исполнения service class.

Это будущие selected-path cases; сейчас runtime **UNRUN**. Полные task mirrors:
[LIF](../solutions/02-custody.md), [lineage/resources](../solutions/03-lineage.md).
