# PLG-03 — реальный Economics learning bridge и несогласованное HARD действие
## C41 · 31 октября 2026 года

**Исходный ID:** LA-023, этап 2/2 и accountable closure. **Порядок:** 41/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит.

## Решение

**Настоящий однодоменный bridge существует:** public train передаёт policy в Economics adapter, тот использует canonical JIT PPO owner, настоящий temporal action owner, отдельную reward correction, selected profile и learned artifact/readback. Старый reward-only loop не является текущим train. Третий optimizer не нужен.

**C41-R01:** при явно выбранном `HARD_DISCRETE` оба collectors записывают sampled action, а temporal mechanism выполняет deterministic mean. Пара action→transition, передаваемая PPO, не совпадает. Default fluid и relaxed controls согласованы. **23 bounded MATCH / 0 ERROR; native training не исполнен.** LA-023 полностью не закрыта; C40-R01 также остаётся.

## 1. Матрица исходной задачи

| ID / этап | Реальная сохранённая часть | Остаток |
|---|---|---|
| LA-023 / 2 из 2 | Узкий Economics→GlobalState/PureExecutor bridge; action/reward/reset/state; existing PPO updates; artifact schema 1.1/profile; strict readback и ordinary evaluation | C41-R01: HARD action binding; G01: fresh native gradient/artifact/continuation acceptance; G02: ограничения capability и научной роли |
| LA-023 / 1 из 2, перенос C40 | Unsupported result/CLI честны, simulation полезна | C40-R01: unmarked legacy-compatible result default trained; C40-G01 native public boundary, без повторной аттестации |

[Полная исходная карточка](../05_Источники/PLG-03_исходные_строки.txt), строки 5090–5199. Повторный LA-023 учитывается один раз; этап 2 не стирает остаток этапа 1.

## 2. Actual owner и producer→consumer chain

Public `train` допускает конкретный adapter, создаёт либо переиспользует actor, передаёт config/store, а затем сохраняет outcome policy/state. `initialize` очищает learned policy/config; `run` при наличии policy идёт через adapter. Это не прежний rollout-reward substitute. [S13:102–291](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/api.py#L102-L291)

Adapter допускает один canonical Economics domain без interactions и требует полный согласованный набор mechanisms. Wage/hours перевозятся через native savings_target/education_years; policy-specific fields тоже конвертируются. Native temporal consumption заменяет plugin consumption, остальные Economics mechanisms сохраняются в bridge executor. Profile ограничен active finite nonnegative wealth **и income**, CRRA; signed-resource simulation вне этого training profile не запрещается. [S01:144–287](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/training_adapter.py#L144-L287) [S01:313–417](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/training_adapter.py#L313-L417) [S01:423–627](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/training_adapter.py#L423-L627)

Actual `_economic_reward_correction` делает native reward равным Economics reward, а не объявляет две разные utility conventions одинаковыми. P21 выполняет обе actual формулы и correction на конечном fixture; совпадение алгебры не доказывает autodiff correctness или научную адекватность reward. P20 actual population predicate допускает inactive NaN/negative padding, но отказывает отрицательному active income. [S01:290–310](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/training_adapter.py#L290-L310) [S10:11–48](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/economics/rewards.py#L11-L48) [S11:56–96](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/agent_sim/rewards.py#L56-L96)

Canonical `train_actor_critic_with_artifact` вызывает existing JIT trainer. В нём actor определяет distribution/actions; `ppo_loss` потребляет trajectory actions/log-probs; `jax.value_and_grad` → Optax clipping/Adam → `apply_updates`. Это реальный source update path, не только имя функции. Selected monitor терминально останавливает неподдержанный transition до PPO. Ни JAX, ни эти gradients в C41 не запускались. [S04:227–365](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/agent_sim/training.py#L227-L365) [S02:408–435](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/agent_sim/jit_training.py#L408-L435) [S02:461–536](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/agent_sim/jit_training.py#L461-L536) [S07:109–168](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/agent_sim/rl.py#L109-L168)

## 3. C41-R01 — записанное HARD действие не выполнено

Collector независимо от fidelity вызывает `sample_actions`, записывает action и log-prob, затем вызывает executor с `config.fidelity`. В actual temporal mechanism `HARD_DISCRETE` выбирает `action_output` без sampling. Для fluid/relaxed sampler использует тот же mechanism key; этот полезный coupling сохранён. В metrics-enabled collector та же развилка отсутствует. [S02:238–334](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/agent_sim/jit_training.py#L238-L334) [S02:628–726](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/agent_sim/jit_training.py#L628-L726) [S03:79–127](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/agent_sim/temporal_mechanisms.py#L79-L127)

**Различающий bounded witness, P01–P04:** actual nested collector bodies и actual temporal/sample_actions definitions; fixture actor mean=0, std=1; scripted normal noise=2; wealth=100, income=10. Observations/state/executor/RNG — явные seams, NumPy вместо JAX. Log-prob — observer fixture, selected monitor выключен в этом отдельном witness.

| Fidelity | Записанный action | Фактически применённый action | Consumption |
|---|---:|---:|---:|
| fluid | 2 | 2 | 96.8876786 |
| relaxed | 2 | 2 | 96.8876786 |
| hard, основной collector | 2 | 0 | 55 |
| hard, metrics collector | 2 | 0 | 55 |

P05 exact adapter admission/train с fixture native outcome подтверждает, что HARD config доходит до existing trainer; admission не переводит его в typed unsupported. Default config — fluid, поэтому дефект **не распространяется автоматически на каждый запуск**. [S01:705–739](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/training_adapter.py#L705-L739) [S06:12–48](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/agent_sim/training_config.py#L12-L48)

Нарушен load-bearing контракт trajectory: PPO считает вероятность действия, которого environment в этом шаге не выполнила. Возможное искажение gradient — следствие по source chain; **его величина и факт завершённого native HARD training здесь не измерены**. Минимальный путь: согласовать action recording/execution у существующих owners либо честно ограничить такой training fidelity; сохранить полезный HARD evaluation. Проверить оба collectors, не создавать третий PPO loop.

## 4. Update honesty, zero gradient и evaluation

P06–P08 исполняют actual gates: zero/nonfinite parameter delta либо zero next-action effect дают typed pending до evaluation/store. P09 fixture supported outcome проходит trainer→artifact weights→evaluation→result, losses берутся из optimizer metrics, не rewards. Эти outcomes сконструированы и **не считаются обучением**. [S01:748–813](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/training_adapter.py#L748-L813)

Исходная карточка разрешает нулевому градиенту не менять policy. Текущий API консервативно маркирует такой случай `training_update_not_observed`, не возвращает fake trained actor и не пишет CAS. Это допустимое явное ограничение capability, **не C41-R**. Прочитанный native test действительно задаёт max_grad_norm=0, проверяет no-op weights и pending; в этой среде он не исполнялся. [S15:649–701](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_plg_03.py#L649-L701)

P10–P12 actual evaluation guard требует все steps+1 states, проверяет каждый intermediate resource domain и terminal status: последующее восстановление final state не стирает ранний отказ. P23 unsupported utility/zero episodes не достигают trainer. [S01:815–839](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/training_adapter.py#L815-L839)

## 5. Learned artifact и его роль

Current producer сериализует actual trained weights, attaches metrics/fingerprint/I/O; selected wrapper ставит schema 1.1 и source-defined training profile. Store валидирует все declared metrics до записи обоих blobs, сохраняет float metrics как Decimal copy; hash-reader проверяет bytes. Adapter читает именно supplied owner и выбранный manifest ref, проверяет typed schema и payload descriptor, вызывает strict policy loader. [S05:193–246](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/agent_sim/artifact.py#L193-L246) [S05:590–721](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/agent_sim/artifact.py#L590-L721) [S01:777–805](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/training_adapter.py#L777-L805)

P13–P19 исполняют actual DTO/store/hash/readback algorithms с **in-memory fixture store, fingerprint и final weight loader**, не с Core CAS/Equinox. Отсутствующий profile, подменённые descriptor/schema, nonfinite metric и изменённые weight bytes различаются; invalid metric даёт 0 writes. Runtime float не изменяется при Decimal storage copy. Legacy schema 1.0 остаётся profileless; её fallback placeholders явно не attestation training metrics. P14 доказывает transport owner/ref, а не tenant-security enforcement.

## 6. Качество существующих tests и граница принятия

Focused test прочитан полностью, 1812 строк. Главный native case наблюдает **реальные pre-clipping gradients**, делегирует original Optax update, затем сравнивает same-seed replay без observer. Он открывает fresh CAS/skeleton, проверяет parameter/action difference, действие learned actor на следующий transition, missing-weight removal, post-training public continuation, отсутствие train/store при evaluation, changed seed и reset. Это содержательный witness design, а не одна проверка status. [S15:254–548](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_plg_03.py#L254-L548)

Другие tests проверяют complete JAX conditional pytree ABI, intermediate terminal refusal, native exception cause, legacy/current schema и CLI. Tenant store cases явно stub native trainer/deltas: они доказывают owner transport, а не обновление policy. Эти уровни нельзя смешивать. [S15:184–251](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_plg_03.py#L184-L251) [S15:1279–1533](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_plg_03.py#L1279-L1533) [S15:1536–1717](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_plg_03.py#L1536-L1717)

Native команда завершилась **до collection**, exit 1: `No module named pytest`. JAX/Equinox/Optax отсутствуют. Ничего не установлено; repository source не менялся. Наличие real tests и source optimizer не даёт свежего native PASS. Следующий engineering шаг — small supported native wave и HARD distinguishing control, а не массовое обучение.

## 7. Сохранить и продолжить

Сохранить узкий actual bridge, canonical PPO owner, typed unsupported reasons, active resource guard, complete intermediate monitor, explicit schema/profile, ordinary rollouts и текущие meaningful tests. Исправить action-transition binding у существующих owners. Не выдавать tiny update, artifact existence или synthetic examples за внешнюю валидность модели/политики; научное обоснование и lifecycle остаются отдельными.

[Диагностика](../04_Проверки/C41_PLG03/bounded_diagnostics.json) · [Команды](../04_Проверки/C41_PLG03/commands.json) · [Native границы](../04_Проверки/C41_PLG03/native_verification.json) · [Источники](../05_Источники/C41_источники.json) · [Остатки](../01_Реестры/C41_остатки.json) · [Перенос C40](PLG-02.md).

**41/127 пакетов рассмотрены ограниченно; 98 уникальных B/LA частично оценены. Следующий — CMP-01. Полного закрытия нет.**
