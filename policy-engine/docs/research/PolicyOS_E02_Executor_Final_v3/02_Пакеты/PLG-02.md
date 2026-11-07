# PLG-02 — PolisySimulator: честный rollout result вместо псевдообучения

## 1. Паспорт и результат

**LANE-04 · CP4 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: LA-023. Тип: result role remediation + native capability boundary.

Старый TrainingResult(actor,reward_trace,state) остаётся полезным historical/evaluation результатом, но больше не получает trained/PPO-loss статус по default.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/PLG-02.md), [все остатки](../05_Основания/Аудит/01_Реестры/C40_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/PLG-02_исходные_строки.txt), исходный объединённый план §PLG-02 (исторические строки 4995–5089).

## 2. Уже работает — сохранить

- Typed bridge_pending reasons, refusal до actor/rollout/store для несовместимого adapter.
- Ordinary run/trajectory/metrics и previous simulator policy/state при typed training refusal.
- Actual narrow trainer bridge существует; in-memory genuine training допускается без обязательного CAS.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C40-R01 | fix: Conservative unmarked role/default и explicit current producer marker; CLI не выводит PPO/trained по class fallback. | REQ-PLG-02-01 |
| C40-G01 | qualify: Native actual state/process CLI unsupported + ordinary run; fixture result handoff не learning proof. | REQ-PLG-02-02 |
| C40-G02 | shared; owner PLG-03: Earlier source-review этап2 выполнен C41; оставшаяся native learning/artifact обязанность REQ-PLG-03-02/-03, не duplicate PPO. | REQ-PLG-02-03 |

### Исходные обязанности, не только новые R

- LA-023 этап1: truthful result/CLI отдельно от этап2 actual learning. Accountable closure PLG-03; один source ID, не две независимые миграции.
- Исторический reward-only train уже заменён; исправить нынешний unmarked result default, не возвращать старую orchestration.
- C40-G02 source-review этап2 superseded выполненным C41 разбором; current replacement native gradient/artifact acceptance в PLG-03, не повтор чтения.

## 4. Нормативный контракт

### REQ-PLG-02-01
TrainingResult сохраняет первые3 positional поля, но отсутствие explicit current producer role/version означает historical/evaluation/unknown, не trained. Новый native train success явно устанавливает qualified training role/status после adapter outcome; CLI success/PPO label возможны только для этой роли, non-null policy и отсутствия reason. Legacy trace/actor сохраняются без loss relabeling. Old-layout instance fallback к dataclass class default также conservative. CAS artifact не обязателен для поддержанного in-memory outcome.

Источник: LA-023; аудит: C40-R01; проверки: TEST-PLG-02-01.

### REQ-PLG-02-02
Unsupported actual state/profile/selector возвращает typed bridge_pending без actor/update/persistence и без нового output каталога; process CLI exit1, usage exit2. Existing simulator state/policy не заменяются failed outcome. Ordinary run остаётся доступен, установленная policy передаётся adapter для evaluation, collect_trajectory=False соблюдается; unexpected internal RuntimeError не success.

Источник: LA-023; аудит: C40-G01; проверки: TEST-PLG-02-02.

### REQ-PLG-02-03
Явно маркированный supported result принимается только после настоящей producer chain PLG-03: optimizer metrics не rewards, policy action/parameter effect и selected artifact/readback при выбранной persistence. Этап1 не считается реализованным learning от одного marker; C40-G02 historical source-review obligation заменена C41 native acceptance, трассировка остаётся.

Источник: LA-023; аудит: C40-G02; проверки: TEST-PLG-02-03.

## 5. Техническое решение и producer → consumer

В api.TrainingResult добавить conservative explicit role/version (либо расширить status с default unknown) сохранив3 positional поля; текущий PolisySimulator.train success задаёт роль явно. В cli.cmd_train централизовать predicate trained outcome: role/status current, no reason, policy present; unknown сохранять как diagnostics/evaluation, не plot_losses. Compatibility reader/getattr defaults должны быть conservative даже у old-layout объекта. Не требовать artifact_refs для in-memory capability; actual artifact qualification PLG-03.

### Проверенные owners на срезе
- policy-engine/src/polisyos/foundry/plugins/api.py: TrainingResult, PolisySimulator.train/run
- policy-engine/src/polisyos/foundry/plugins/cli.py: cmd_train
- policy-engine/src/polisyos/foundry/plugins/training_adapter.py: EconomicsTrainingAdapter.assess/train

Просто status='trained' default или artifact existence не определяют происхождение history. Удаление historical traces хуже explicit unknown; новый optimizer не нужен.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-PLG-02-01
- Уровень: unit + targeted native integration.
- Setup: Actual constructor старых3 fields actor,[2,2,2],state с0updates; None,[] case; trusted synthetic old-layout instance lacking new fields; explicit current producer positive.
- Действие: CLI cmd_train/result presentation and plotting gate; safe local serialization compatibility only trusted fixtures.
- Точный oracle: Legacy remains accessible but exit1/unqualified-training (или отдельный non-training presentation), no Training complete/PPO loss/training plot. Empty actor never success. Explicit genuine in-memory result can exit0 без CAS; malformed marker/reason refusal. Old default fallback не trained.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-PLG-02-02
- Уровень: native package + process CLI.
- Setup: Canonical unsupported multi-domain/interaction/config/boolean-selector fixtures; existing initialized simulator.
- Действие: train unsupported, ordinary run before/after, main parser misuse.
- Точный oracle: Pending precise code, no actor/update/write/output; old policy/state intact; normal run produces trajectory/current state. CLI1 vs usage2; unexpected error retains failure cause.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-PLG-02-03
- Уровень: unit + targeted native integration.
- Setup: Shared tiny PLG-03 native witness and actual TrainingResult projection.
- Действие: Obtain genuine outcome, pass API→CLI; evaluate with no update/store calls.
- Точный oracle: Explicit training role originates current successful producer, loss exactly optimizer history; evaluation не retrain. Marker alone не evidence и не заменяет PLG-03 tests.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_plg_02.py`; `policy-engine/tests/unit/remediation/test_plg_03.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: controlled unsupported adapter и legacy result fixtures в unit; native positive только real PLG-03. Запрещено: fixture supported outcome как update proof, untrusted pickle, обязательный CAS для всех in-memory results.

## 7. Общая интеграция и порядок

Shared files api/cli lease с PLG-03; PLG-02 owns result role, PLG-03 owns actual optimizer/action/artifact. LA-023 accepted только с обоими outcomes.

Точные общие сценарии: E02-I04-C из [контракта интеграции](../03_Интеграция/LANE-04.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: нет обязательного нового предшественника; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Defaults меняют ошибочную атрибуцию, не теряют старые поля. Version/role additive; old serialized objects не повышаются до trained задним числом. C40-G02 source-reading superseded C41, native requirement сохраняется.

## 9. Free-grow и design direction

- Исторический output сохраняется, текущий смысл/authority не выдаются class default.
- Полезное evaluation и honest pending остаются первоклассными, не требуют универсального trainer.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

## 10. Нерешённые решения и передача

- Выбрать minimal status-vs-role API расширение после caller census; exact legacy fallback должен быть unqualified и проверяться отдельным negative test.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для native численных/JIT/train проверок P-JAX (тот же lock, JAX/jaxlib/optax, deterministic tiny CPU); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.


Полные probes исходного аудита доставлены отдельно в phase1 ZIP; ссылки аудита на них не означают включение тяжёлой evidence в этот исполнительский комплект.
