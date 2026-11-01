# PLG-02 — честный capability отказ и остаток немаркированного result ABI
## C40 · 31 октября 2026 года

**Исходный ID:** LA-023, **этап 1/2**. **Порядок:** 40/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит. Accountable closure — PLG-03.

## Решение

**Основной текущий pseudo-training путь заменён:** неподдержанный profile получает typed `bridge_pending`, без созданного actor, reward-as-loss или trained policy. CLI на таком результате возвращает 1, не пишет «Training complete», не показывает PPO loss и не создаёт output directory. Обычный simulation run сохранён.

**18 MATCH, 0 ERROR; C40-R01 остаётся на legacy-compatible result boundary:** три прежних немаркированных поля `TrainingResult(actor, history, state)` получают default `status="trained"`; CLI доверяет этому default и может назвать исторический reward trace PPO loss. Это не утверждение, что нынешний native train делает так же.

## 1. Матрица исходной задачи

| ID / этап | Подтверждённая часть | Остаток |
|---|---|---|
| LA-023 / 1 из 2 | Typed capability reasons; unsupported request не запускает fake training; CLI refusal/usage codes; полезный run/trajectory; supported outcome handoff | C40-R01: unmarked historical-compatible result role; G01: native state/CLI tests; G02: следующий PLG-03 actual learning/artifact |

[Полная карточка](../05_Источники/PLG-02_исходные_строки.txt), строки 4995–5089. Honest refusal не равен реализованному обучению; существующий реальный bridge также нельзя объявить отсутствующим по старому описанию LA-023.

## 2. Unsupported request не превращается в псевдорезультат

Actual `train` сначала проверяет узкий adapter. Если он отсутствует, assessment возвращает конкретный code/message; result содержит policy None, empty loss_history и bridge_pending. Этот return расположен до ActorCritic creation и построения training store. [S01:202–249](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/api.py#L202-L249)

P01 исполняет exact train с неподдержанными state/executor: `training_execution_adapter_missing`, **0 actor constructions, 0 rollout calls**, output directory не создан. P02 actual assessment различает несколько domains, иной execution order, interactions, missing config и отключённый labor; P03 отказывает строковому bool selector. P04 labor-disabled profile доходит до public result с `training_composite_profile_unsupported` и сохраняет исходный state. Canonical type identities в этих probes — явные fixtures, не native trees. [S03:453–526](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/training_adapter.py#L453-L526) [S05:45–60](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/agent_sim/jit_training.py#L45-L60)

P05 `TrainingBridgeError(training_update_not_observed)` возвращается как typed pending: предыдущие simulator policy/state сохранены, но не выдаются в result как вновь обученные. P16 неожиданная RuntimeError не маскируется под успех. [S01:268–291](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/api.py#L268-L291)

## 3. CLI и обычный run согласованы с capability

P07 exact `cmd_train` возвращает 1, печатает status/reason, не создаёт каталог/plot и не выводит training success/loss/artifact. P08 даже `status="trained"` с непустой reason остаётся отказом. P12 actual main передаёт отказ команды как return 1; P13 argument parser сохраняет отдельный usage exit 2. [S02:24–65](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/cli.py#L24-L65) [S02:116–159](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/cli.py#L116-L159)

P14 exact ordinary run возвращает SimulationResult с trajectory/final state и обновляет simulator state — полезный rollout не удалён. P18 aggregate/distribution metric lookup остаётся simulation API, не optimizer history. P15 при установленной policy run передаёт именно её adapter и соблюдает collect_trajectory=False. [S01:137–200](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/api.py#L137-L200) [S01:366–390](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/api.py#L366-L390)

P06 supported fixture outcome проходит через actual handoff: simulator получает outcome policy/state/config, result — его losses/artifact. P17 CLI показывает PPO label и artifact для такого явно заданного supported fixture. **Это проверка транспорта результата, не свидетельство gradient update.**

## 4. C40-R01 — старый немаркированный результат автоматически получает trained

Public dataclass сохраняет прежние обязательные поля actor/history/state и добавляет defaults `status="trained"`, reason None, artifact None. Отдельной legacy/evaluation роли или обязательного version marker на этой границе нет. CLI проверяет status/reason, но не различает происхождение старой history. [S01:402–418](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/api.py#L402-L418) [S02:138–159](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/cli.py#L138-L159)

**P09:** actual `TrainingResult(actor,[2,2,2],state)` без новых полей сохраняет тот же actor; в fixture было 0 optimizer updates. Exact CLI возвращает **0**, пишет `Training complete!`, `PPO loss: 2.0000`, вызывает plotting branch. **P10:** даже `TrainingResult(None,[],state)` с defaults проходит success branch. Не утверждается, что реальный нынешний adapter возвращает такую комбинацию.

P11 собственный synthetic old-layout object с отсутствующими новыми instance fields после локального pickle readback разрешает `status` через новый class default trained. Это **не настоящий исторический архив**, не доказательство конкретного production deserializer и не запуск untrusted pickle. Результат уточняет механизм backward-compatible field fallback, а не расширяет эмпирический охват.

Минимальный остаток — сохранить старые actor/reward traces с честной historical/evaluation/unknown ролью, а подтверждённый текущий training producer маркировать явно. CLI не должен придавать научную роль одному default. Не нужно удалять полезные данные или требовать обязательно persisted CAS для допустимого in-memory native результата.

## 5. Реальный trainer уже есть; этап 2 пока не принят

Текущий narrow Economics adapter вызывает `train_actor_critic_with_artifact`, проверяет parameter/action delta, evaluation trajectory и selected artifact profile, а при store выполняет readback. Canonical training owner содержит PPO/Optax updates. Это важное отличие от исторического тела train с простым reward loop. [S03:686–815](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/training_adapter.py#L686-L815) [S06:54–131](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/agent_sim/training.py#L54-L131) [S06:291–365](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/agent_sim/training.py#L291-L365)

В C40 эти части прочитаны, **не исполнены**. Parameter difference от seed, реальный gradient/update, zero-gradient semantics, действие policy на следующий шаг, reset/continuation и persisted identity должны быть последовательно оценены в PLG-03. Ни наличие functions, ни fixture success не закрывают это автоматически.

## 6. Проверки и продолжение

Полные найденные PLG-02/CLI tests прочитаны. Native команда остановилась до collection: `No module named pytest`, exit 1. Один bounded запуск дал 18 MATCH / 0 ERROR, включая R01. State identity/config/RNG/adapter/result/plot seams открыто описаны; native package, optimizer, CAS и настоящий archived result не заявлены.

Сохранить текущие typed refusals, обычные rollouts, полезный narrow bridge и отдельный canonical trainer. Следующий шаг — исправить result-role ambiguity у существующего boundary и проверить **PLG-03** без третьего PPO loop. LA-023 в unique-ID denominator учитывается один раз.

[Диагностика](../04_Проверки/C40_PLG02/bounded_diagnostics.json) · [Команды](../04_Проверки/C40_PLG02/commands.json) · [Native границы](../04_Проверки/C40_PLG02/native_verification.json) · [Источники](../05_Источники/C40_источники.json) · [Остатки](../01_Реестры/C40_остатки.json).

**40/127 пакетов рассмотрены ограниченно; следующий — PLG-03. Полного закрытия нет.**
