# PLG-03 — Один DomainPlugin → существующий trainer: реальный learning bridge

**Редакция: PROPOSED v2 — адресные изменения FN-PLG-ORACLE, FN-PLG-INACTIVE. Содержательное review изменений выполнено; принятие проектом и реализация остаются отдельными шагами. Все product tests NOT_RUN.**

## 1. Паспорт и результат

**LANE-04 · CP4 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: LA-023. Тип: HARD trajectory repair + native learning/artifact qualification.

Согласовать action→transition PPO и доказать настоящий tiny one-domain update→следующее действие→fresh artifact; не создавать третий optimizer и не объявлять update научным улучшением.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/PLG-03.md), [все остатки](../05_Основания/Аудит/01_Реестры/C41_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/PLG-03_исходные_строки.txt), исходный объединённый план §PLG-03 (исторические строки 5090–5199).

## 2. Уже работает — сохранить

- Canonical JIT PPO/Optax owner и narrow Economics/CRRA bridge, active finite nonnegative wealth/income profile, terminal intermediate guards.
- Typed unsupported/zero-update pending; ordinary simulation/HARD evaluation, reset и continuation.
- Schema1.1 selected training profile, learned weights, strict readback через supplied owner; legacy1.0 не получает training attestation.
- LA-023 stage1 result role и CLI исправляются у PLG-02, не дублируются.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C41-R01 | fix: HARD sampled-action/mean-transition несогласованность устранить на shared training admission/action contract, оба collectors. | REQ-PLG-03-01 |
| C41-G01 | qualify: Реальный pre-clipping gradient/update, same-seed control, fresh policy consumer/reset/continuation. | REQ-PLG-03-02, REQ-PLG-03-03 |
| C41-G02 | qualify: Zero update pending и narrow profile честны; tiny policy effect не empirical learning quality. | REQ-PLG-03-02, REQ-PLG-03-04 |

### Исходные обязанности, не только новые R

- LA-023 stage2: actual obs/action/reward/reset/state bridge уже существует; current old reward-loop отсутствует. Требуется квалифицировать, а не заново написать PPO.
- Zero gradient вправе не менять policy; current training_update_not_observed pending допустим, не defect.
- C40-R01/G01 carried к PLG-02; C40-G02 source-review этап2 superseded C41, native replacement остаётся здесь.

## 4. Нормативный контракт

### REQ-PLG-03-01
PPO trajectory action/log_prob должны относиться к действию, реально исполненному temporal transition, в обоих create_jit_trainer collectors. Минимальное принятое направление: HARD_DISCRETE training явно unsupported до collector/optimizer/artifact/output creation, пока deterministic-mean behavior не имеет согласованной PPO sampling law; ordinary HARD evaluation сохраняется. Fluid/relaxed продолжают shared mechanism-key sampled action law. Альтернативное полноценное HARD обучение допустимо только после общего action-selection/execution контракта и доказанного likelihood oracle, не простого log_prob(mean) для прежней Gaussian sampling law.

Источник: LA-023; аудит: C41-R01; проверки: TEST-PLG-03-01.

### REQ-PLG-03-02
Supported one-domain Economics/CRRA native tiny run выполняет1–2 настоящих updates: конечный ненулевой pre-clipping gradient, original Optax update, parameter delta и next-action effect отличны от independent same-seed no-update control. Train/eval/reset/continuation и supplied seed сохраняются. Zero/nonfinite/no-action-effect даёт existing typed pending; active negative/nonfinite wealth или income и любой intermediate terminal transition останавливают до PPO/publication, даже если final state мог восстановиться. Ненулевой effect недостаточен: actual PPO loss/gradient должны соответствовать independent clipped-surrogate/value/entropy и GAE oracle с fixed old-policy/target values. Разрешённый inactive padding не влияет на активное training computation через payload; stored state не переписывается. Same-shape/same-key inactive finite→NaN pair квалифицируется на actual collector→PPO→Optax. Это проверка source-derived гипотезы, не утверждение уже исполненного runtime defect; при существующей защите документировать actual boundary вместо лишнего patch.

Источник: LA-023; аудит: C41-G01, C41-G02; проверки: TEST-PLG-03-02.

### REQ-PLG-03-03
Actual trained weights/optimizer metrics/schema1.1 source-defined training_profile публикуются через supplied store/tenant owner и exact selected ref, fresh store+skeleton strict loader восстанавливает policy с тем же действием. Missing/tampered weights, descriptor/schema/profile mismatch и nonfinite metrics не дают trained persisted artifact; invalid metrics до обоих writes. Legacy1.0 остаётся readable profileless без invented training metadata.

Источник: LA-023; аудит: C41-G01; проверки: TEST-PLG-03-03.

### REQ-PLG-03-04
Public result использует explicit current producer role PLG-02, losses только optimizer metrics, historical traces не PPO. Unsupported profiles/hard-training refusal сохраняют ordinary run и previous policy/state. Learned action difference означает узкую capability, а не гарантированное welfare/causal improvement; scientific usefulness требует отдельного data/model/eval основания. Accountable LA-023 закрывает оба этапа, не только честный отказ.

Источник: LA-023; аудит: C41-G02; проверки: TEST-PLG-03-04.

## 5. Техническое решение и producer → consumer

Предпочтительный узкий ремонт — общий training-fidelity validator, вызываемый обоими canonical JIT trainer factories и high-level adapter до artifact/actor/output setup; использовать существующий TrainingBridgeError/public capability reason mapping, дать точный unsupported code. Не менять TemporalConsumptionMechanism HARD evaluation law. Если принято сохранить HARD training, вынести actual action selection в shared primitive и либо передавать executed action в executor, либо возвращать его с distribution/log_prob; проверка on-policy likelihood обязательна, recording mean alone недостаточно. Все прочие working trainer/profile/artifact gates сохраняются. PLG-02 единственный owner result-role patch.

**Дополнительная квалификация FN-PLG-ORACLE/FN-PLG-INACTIVE (PROPOSED v2).** Сохранить existing agent_sim.rl/Optax owners; не переносить обучение в новый framework. Добавить независимую математическую проверку policy-gradient direction/clipping и fixed GAE targets, затем прежний actual native update/artifact witness. Отдельно выполнить paired inactive-padding run: форма arrays, active indices, initial actor/optimizer и per-agent key arrangement фиксированы; меняется только разрешённый inactive income finite→NaN. Source review показывает возможную цепь raw inactive observation→actor→NaN*0 в masked loss, но native исход не известен. Если witness подтверждает проблему, нейтрализовать только inactive computational operands до actor/reward/GAE/nonlinear loss, сохраняя исходный stored payload и active/intermediate-terminal guards. Если existing boundary уже защищает, зафиксировать её и сохранить distinguishing test. Append-padding со сменой shape не объявлять точной RNG invariance без per-agent key contract.

### Проверенные owners на срезе
- policy-engine/src/polisyos/foundry/agent_sim/jit_training.py: create_jit_trainer, create_jit_trainer_with_metrics
- policy-engine/src/polisyos/foundry/agent_sim/temporal_mechanisms.py: TemporalConsumptionMechanism.apply
- policy-engine/src/polisyos/foundry/plugins/training_adapter.py: EconomicsTrainingAdapter.train, _require_supported_evaluation_trajectory
- policy-engine/src/polisyos/foundry/agent_sim/training.py: train_actor_critic_with_artifact
- policy-engine/src/polisyos/foundry/agent_sim/artifact.py: store_policy_artifact, load_policy_artifact
- policy-engine/src/polisyos/foundry/plugins/api.py: PolisySimulator.train

Сменить только stored action на mean может убрать численное расхождение, но не доказать корректность PPO behavior likelihood. Honest fidelity restriction сохраняет useful supported training/evaluation и дешевле новой stochastic law.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-PLG-03-01
- Уровень: unit + targeted native integration.
- Setup: Actor mean0,std1; deterministic controlled action fixture для unit плюс actual native temporal law; wealth100,income10; оба collector factories.
- Действие: Request HARD train через public API и direct canonical factory; ordinary HARD eval; fluid/relaxed collector/action transition fixed key.
- Точный oracle: HARD training precise unsupported до sampler/optimizer/store, no output; evaluation mean0→consumption55 сохраняется. Fluid/relaxed recorded action equals applied action and log_prob соответствует same distribution/key; noise2 unit control даёт≈96.8876786. Никакого silent fidelity coercion.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-PLG-03-02
- Уровень: native JAX/Equinox/Optax tiny learning Дополнительно unit-level independent PPO/GAE oracle с реальными owner functions; analytic unit не заменяет native learning/artifact path..
- Setup: Existing main test_plg_03 native profile, fixed actor seed and initial state; observer делегирует original update, same-seed run без observer и no-update/max_grad_norm0 control. Unit PPO: actual continuous ActorCritic с action_dim1, все matrix weights/biases=0, action_log_std=0; единственная варьируемая scalar μ — actor_out.bias[0], при μ=0 mean0/std1/value0. Observation inputs конечные нули, T=1/n_agents=2, actions[+1,−1], active_mask[1,1], raw advantages[+1,−1], returns0, value_coef=entropy_coef=0, clip_epsilon=.2. Все inputs/owner arithmetic явно float32. Для ratio sets R=[1.3,.7], [.9,1.1], [.7,1.3] вычислить fixed old_log_probs отдельно через Python math normal log-density при mean0/std1 минус math.log(R_i), затем cast float32; не product compute_log_prob. Normalization: mean0/std1, ε=fl32(1e-8), K=fl32(1+ε)=1, A_norm=[+1/K,−1/K]. GAE unit отдельно: T=2/n_agents=1, rewards[1,2], values[.25,.5], final_value1, gamma=.5, lambda=1, все active. Native padding pair фиксирует shape/active indices/keys, меняет только inactive income finite→NaN; активные данные одинаковы. Дополнительные component controls используют тот же actual ActorCritic, но fixed advantages[0,0], fixed returns[1,3], critic_out.bias[0]=ν=0 и action_log_std[0]=ℓ=0, mean0; old_log_probs остаются fixed независимо вычисленными target values. Varied actual architecture coordinates — ν и ℓ, не mocked values/distribution. Пары (value_coef,entropy_coef): (.5,0),(.25,0),(0,.1),(0,.2),(.5,.1),(.25,.2); все inputs и coefficients float32. При ℓ=0 log-std clipping неактивен. Исходные три policy clip cases с advantages[+1,−1] сохраняются отдельно.
- Действие: 1–2updates, evaluate next transition, public continue, initialize reset; signed/inactive padding/intermediate bad then recovered controls. Для unit вызывать actual ppo_loss и jax.grad по μ через immutable replacement actual actor_out.bias; eager/JIT, без fake gradient. Actual compute_returns_and_advantages проверить с dones[false,false], [false,true], [true,true]. В native padding pair выполнить прежние1–2 actual updates и readback; original Optax не подменяется.
- Точный oracle: Raw gradient finite/nonzero; original update вызван, parameter/action effect сверх no-update. Same-seed replay совпадает; eval0updates/0store. Zero clip→pending/no trained artifact; inactive padding allowed within profile, active violations terminal до optimizer, reset clears learned state. PPO independent reference: r_i=exp(log Normal(a_i;μ,1)−old_lp_i), L=−mean(min(r_i*A_norm_i,clip(r_i,.8,1.2)*A_norm_i)); Python math reference использует фактические stored float32 old_lp/actions и K, а не product helper. При μ=0 ideal losses для трёх R равны−.2/K,+.1/K,+.3/K; dL/dlog(r)=[0,0], [−.45,+.55]/K, [−.35,+.65]/K; поскольку dlog Normal(a;μ,1)/dμ=a−μ, actual actor-bias gradients0,−1/K,−1/K. Разница округления old_lp/exp учитывается независимым reference, fixed rtol=5e-6/atol=2e-6 для loss/gradient, без подбора после результата. Sign-flip и removal of clipping обязаны нарушить хотя бы один oracle. GAE returns/advantages: no terminals [2.25,2.5]/[2,2]; last terminal [2,2]/[1.75,1.5]; both terminals [1,2]/[.75,1.5], atol=1e-6/rtol=1e-6; terminal unit не отменяет отказ native profile на intermediate terminal. Native inactive finite/NaN pair имеет finite metrics, одинаковые active action/selected parameters/gradient/update в rtol=1e-6/atol=1e-6, исходный inactive payload сохранён; active-row NaN остаётся отказом до update/store. Для scalar PPO unit old_lp/advantages/returns являются фиксированными target inputs; actor native action-law consistency отдельно остаётся TEST01. Welfare improvement не утверждается. Nonzero component oracle: H0=.5*(1+math.log(2*math.pi)); value_loss=mean((ν−[1,3])²), поэтому приν=ℓ=0 raw value_loss5, raw entropyH0, policy_loss0, total=5*c_v−c_e*H0, dL/dν=−4*c_v, dL/dℓ=−c_e. Проверять отдельно actual reported components, total и jax.grad по обоим actual actor fields eager/JIT для каждой coefficient pair; reference использует фактически представимые float32 coefficient values и независимый math H0. Для (.5,0) total2.5/dν−2; (.25,0) total1.25/dν−1; при cv0 totals−ce*H0 и dℓ−ce; combined pairs соответствуют той же sum formula. Fixed rtol=5e-6/atol=2e-6, не увеличивать после результата. Удаление/смена знака/игнорирование coefficients value или entropy обязаны нарушить oracle; гипотетический native дефект этим не объявляется. Advantages/returns/old policy targets не дифференцируются по ν/ℓ, никакого welfare claim.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-PLG-03-03
- Уровень: native owner-bound artifact → fresh strict policy.
- Setup: Real tenant-owned CAS, trained artifact from TEST02, independent fresh store/skeleton; second selected view same content.
- Действие: Store/load exact ref, compare next action; remove weights, tamper bytes/profile/descriptor, NaN metric; legacy1.0 read.
- Точный oracle: Exact source profile/owner preserved, same policy action; no default-view substitution. Invalid metric writes0; missing/tamper refusal; legacy readable but no inferred metrics/authority. Runtime float metrics unaffected by Decimal storage copy.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-PLG-03-04
- Уровень: unit + targeted native integration.
- Setup: Actual PLG-02 result predicate and shared native successful/unsupported outcomes.
- Действие: API→CLI→ordinary run; legacy3fields negative; no-CAS genuine positive.
- Точный oracle: Only genuine explicit current producer result labelled trained/PPO; legacy remains evaluation/unknown, no training plot. Unsupported leaves state/policy intact; in-memory genuine allowed. Output states scope/limitations without scientific success claim.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_plg_03.py`; `policy-engine/tests/unit/remediation/test_plg_02.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: controlled actor/noise только unit binding oracle, delegating gradient/update observers; tiny synthetic state. Запрещено: fake gradient/Optax/CAS/final weight loader для native qualification, seed delta как обучение, fleet/large model downloads.

## 7. Общая интеграция и порядок

Один real tiny train witness переиспользуется PLG-02 CLI, ECO selected profile и artifact owner transport; отдельные tenant stub tests не считаются update proof. Api/cli writes согласовать с PLG-02.

Точные общие сценарии: E02-I04-C из [контракта интеграции](../03_Интеграция/LANE-04.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: PLG-02; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Default fluid не затронут; HARD evaluation preserved. Explicit HARD training restriction — документированное снятие неподдержанного семантического claim, а не закрытие полной HARD training capability; потенциальное функциональное сужение явно внести в release notes. Это не постоянный архитектурный запрет: при требовании HARD training владелец принимает ограниченное решение по общему action/likelihood контракту (§10), после native oracle режим вновь допускается. Legacy schema/result не переаттестуются. No new universal DomainPlugin trainer.

## 9. Free-grow и design direction

- Полезный one-domain learned policy допускается с узким conditional scope; unsupported fidelity не закрывает остальные режимы.
- Action/transition/likelihood общий контракт расширения, не специальная ветка по одному fixture.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

## 10. Нерешённые решения и передача

- Если проект требует HARD training сейчас, выбрать полноценный action/likelihood contract вместо предложенного scoped refusal и предъявить native oracle до признания поддержки. Без такого выбора безопасный executable default — honest unsupported.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для native численных/JIT/train проверок P-JAX (тот же lock, JAX/jaxlib/optax, deterministic tiny CPU); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.


Полные probes исходного аудита доставлены отдельно в phase1 ZIP; ссылки аудита на них не означают включение тяжёлой evidence в этот исполнительский комплект.
