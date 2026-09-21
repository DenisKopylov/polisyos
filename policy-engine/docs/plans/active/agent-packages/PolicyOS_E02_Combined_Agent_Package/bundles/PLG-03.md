# PLG-03 — Один DomainPlugin → существующий trainer: реальный learning bridge

**E02 · окно CP4 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-023 (M).

**Предшественники:** [PLG-02](../bundles/PLG-02.md). **Совместная очередь:** LANE-04.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Для одного согласованного домена связать obs/action/reward/reset/state с существующим train_actor_critic, PureExecutor и TemporalConsumptionMechanism. Не вводить третий PPO-loop. Сохранить фактически обновлённую policy и её execution identity; затем снять старую псевдо-training orchestration.

**Различающие тесты и сохраняемое поведение.** Один tiny native rollout и один-два optimizer updates: nonzero gradient меняет параметры и следующие actions; zero gradient вправе не менять. Train/eval, RNG/reset/continuation и learned artifact readback. Unsupported CompositeState сохраняет честное ограничение, не silent default. Без совместимого adapter LA-023 остаётся частично завершённой.

**Не считать исправлением.** Не запускать массовое обучение, GPU fleet или скачивание больших моделей на Mac. Не принимать parameter difference от seed вместо gradient update.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-023:** Этап 2/2 и accountable closure реального однодоменного bridge. Честный unsupported в PLG-02 не объявляется реализованным trainer. Accountable closure: **PLG-03**; необходимые пакеты: PLG-02, PLG-03.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/foundry/plugins/api.py
policy-engine/src/polisyos/foundry/plugins/cli.py
policy-engine/src/polisyos/foundry/plugins/training_adapter.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/foundry/agent_sim/training.py
policy-engine/src/polisyos/foundry/plugins/core.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_plg_03.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** PLG-02. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-04, MOVE-20. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A17.** Honest rollout/unsupported принят отдельно; он не означает реализованное обучение. Требуется настоящий policy→actions→gradient/update bridge для заявленного train capability.

**Ресурс:** N/C — I1 broker drains L and admits one exclusive native/numerical/build or checkpoint job using the full seven-unit budget; no other resource-bearing job runs concurrently. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без permit. Immutable argv/cwd/worktree/SHA/selectors/timeout/output root and named resources are fixed at admission; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-023

Источник LA_r09, строки 1052–1083; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-023 -->
## LA-023. PolisySimulator.train: сбор rollout-наград под видом обучения

Слияние / разделение ответственности

**Статус.** Несоответствие функции и интерфейса подтверждено; есть отдельный настоящий training owner.

**Точная область:**

`src/polisyos/foundry/plugins/api.py#PolisySimulator.train`

`src/polisyos/foundry/plugins/api.py#TrainingResult`

`src/polisyos/foundry/plugins/cli.py#cmd_train`

**Что установлено и почему это legacy.** Метод создаёт ActorCritic, выполняет self.run и складывает reward в loss_history. В рассмотренном run/train нет передачи actor в динамику и нет gradient/optimizer update. Возвращается тот же actor под именем trained_policy. CLI пишет Training complete и показывает награду как Final loss. Это живой остаток раннего high-level demo API, не просто файл без импортов.

**Что сохранить.** Композитные rollouts, состояние доменов, цели и диагностику rewards. Не выдавать прежние reward traces за loss оптимизатора; historical TrainingResult при чтении должен сохранить происхождение и оговорку. Не удалять все plugins/economics или рабочие модели вместе с этой оболочкой.

**Куда перенести / с чем объединить.** Существующий foundry/agent_sim/training.py::train_actor_critic — кандидат на единственного владельца обучения: там есть trajectory, PPO gradients и Optax updates. Но он требует PureExecutor и TemporalConsumptionMechanism; CompositeState/CompositeExecutor не являются доказанной заменой. Нужен узкий адаптер obs/action/reward/state либо явное ограничение train для несовместимого домена.

**Порядок миграции.** Немедленно уточнить capability/result semantics: текущий цикл может остаться rollout evaluation, но не успешным обучением. Подключить trainer для одного согласованного домена, обновить CLI, сохранять фактический learned-state artifact. После сравнительной приёмки удалить псевдо-training orchestration; не создавать третий самостоятельный PPO-loop.

**Приёмка.** На ненулевом градиенте проверить изменение параметров и влияние policy на следующие actions, train/eval separation, RNG, reset/continuation и метрики. Нулевой градиент допустимо не меняет policy. Локально выбранное исходное train-тело с fixture rollout выполнило три эпизода, собрало [2,2,2] и вернуло неизменный actor с нулём вызовов.

**Приоритет.** Высокий приоритет смысловой честности. Уточнение результата дешёво; настоящая миграция обучения зависит от совместимости состояния.

**Граница вывода.** PPO/Optax и полный PolisySimulator не запускались. Более содержательный trainer не признан исправным по одному чтению. Тестовые actor/rollout — явные фикстуры, а не измерение качества реального обучения.

**Основания.** E53, E54, E55. P11–P12; выбранное исходное тело train, fixture actor/state/reward/RNG.

<!-- PAGEBREAK -->

<!-- SOURCE_END LA:LA-023 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK08 -->
## K08. DomainPlugin не равен FoundryMethodPlugin

State factory, rewards, objectives, lifecycle и observations доменного plugin не покрываются одним методом pure_step. Общая discovery-инфраструктура полезна, но смена entry-point group без bridge меняет ABI. Поддержанные runtime registries могут оставаться отдельными lookup-структурами. [E49, E50, E51, E52, E66]

<!-- SOURCE_END LK:LK08 -->

