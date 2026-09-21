# PLG-02 — PolisySimulator: честный rollout result вместо псевдообучения

**E02 · окно CP4 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-023 (M).

**Предшественники:** Нет. **Совместная очередь:** LANE-04.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Разделить существующий rollout-evaluation и capability train. CLI не пишет Training complete/Final loss при неизменном actor и reward history. Поддержанные historical TrainingResult читаются с исходной ролью, не как доказанное learned-state. Это маленькая исправляющая часть до actual trainer bridge.

**Различающие тесты и сохраняемое поведение.** Fixture rollout с rewards [2,2,2] и нулём optimizer updates остаётся полезным evaluation, не trained policy. Train запрос без совместимого execution adapter даёт точную capability причину. Старые simulation/domain routines работают; CLI текст и return semantics согласованы.

**Не считать исправлением.** Не удалять plugin/economics и не обозначать rewards как optimizer loss. Не заявлять обучение от создания ActorCritic.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-023:** Этап 1/2: честная capability/result/CLI; реальное обучение одного домена — PLG-03. Accountable closure: **PLG-03**; необходимые пакеты: PLG-02, PLG-03.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/foundry/plugins/api.py
policy-engine/src/polisyos/foundry/plugins/cli.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/foundry/agent_sim/training.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_plg_02.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** PLG-03. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Условия общего использования:**

**A17.** Honest rollout/unsupported принят отдельно; он не означает реализованное обучение. Требуется настоящий policy→actions→gradient/update bridge для заявленного train capability.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

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

