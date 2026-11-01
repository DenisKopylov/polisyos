# PLG-03 — Один DomainPlugin → существующий trainer: реальный learning bridge

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
Supported one-domain Economics/CRRA native tiny run выполняет1–2 настоящих updates: конечный ненулевой pre-clipping gradient, original Optax update, parameter delta и next-action effect отличны от independent same-seed no-update control. Train/eval/reset/continuation и supplied seed сохраняются. Zero/nonfinite/no-action-effect даёт existing typed pending; active negative/nonfinite wealth или income и любой intermediate terminal transition останавливают до PPO/publication, даже если final state мог восстановиться.

Источник: LA-023; аудит: C41-G01, C41-G02; проверки: TEST-PLG-03-02.

### REQ-PLG-03-03
Actual trained weights/optimizer metrics/schema1.1 source-defined training_profile публикуются через supplied store/tenant owner и exact selected ref, fresh store+skeleton strict loader восстанавливает policy с тем же действием. Missing/tampered weights, descriptor/schema/profile mismatch и nonfinite metrics не дают trained persisted artifact; invalid metrics до обоих writes. Legacy1.0 остаётся readable profileless без invented training metadata.

Источник: LA-023; аудит: C41-G01; проверки: TEST-PLG-03-03.

### REQ-PLG-03-04
Public result использует explicit current producer role PLG-02, losses только optimizer metrics, historical traces не PPO. Unsupported profiles/hard-training refusal сохраняют ordinary run и previous policy/state. Learned action difference означает узкую capability, а не гарантированное welfare/causal improvement; scientific usefulness требует отдельного data/model/eval основания. Accountable LA-023 закрывает оба этапа, не только честный отказ.

Источник: LA-023; аудит: C41-G02; проверки: TEST-PLG-03-04.

## 5. Техническое решение и producer → consumer

Предпочтительный узкий ремонт — общий training-fidelity validator, вызываемый обоими canonical JIT trainer factories и high-level adapter до artifact/actor/output setup; использовать существующий TrainingBridgeError/public capability reason mapping, дать точный unsupported code. Не менять TemporalConsumptionMechanism HARD evaluation law. Если принято сохранить HARD training, вынести actual action selection в shared primitive и либо передавать executed action в executor, либо возвращать его с distribution/log_prob; проверка on-policy likelihood обязательна, recording mean alone недостаточно. Все прочие working trainer/profile/artifact gates сохраняются. PLG-02 единственный owner result-role patch.

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
- Уровень: native JAX/Equinox/Optax tiny learning.
- Setup: Existing main test_plg_03 native profile, fixed actor seed and initial state; observer делегирует original update, same-seed run без observer и no-update/max_grad_norm0 control.
- Действие: 1–2updates, evaluate next transition, public continue, initialize reset; signed/inactive padding/intermediate bad then recovered controls.
- Точный oracle: Raw gradient finite/nonzero; original update вызван, parameter/action effect сверх no-update. Same-seed replay совпадает; eval0updates/0store. Zero clip→pending/no trained artifact; inactive padding allowed within profile, active violations terminal до optimizer, reset clears learned state.
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
