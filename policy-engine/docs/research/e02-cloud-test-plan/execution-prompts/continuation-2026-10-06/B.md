# B — продолжение E02: runtime, CAS и исполнение

Сначала полностью прочитай `AGENTS.md`, `policy-engine/CONTRIBUTING.md` и `policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/HANDOFF.md`, прежде чем выполнять работу. Короткие E02-пути в этом поручении означают `policy-engine/docs/research/e02-cloud-test-plan/`; команды ниже выполняются от корня репозитория, кроме явно указанного subshell. Все необходимые решения находятся в tracked `closure-decisions/`, а локальные ignored outputs не являются входом облачной задачи.

Перед созданием любого checkout/worktree прочитай `policy-engine/tools/devx/workspace/README.md#worktree-admission`, выбери реальные точные branch и absolute worktree root, и выполни read-only `workspace doctor --worktree-admission create` с этими `--branch` и `--path`. Сохрани полный JSON; после создания проверь тот же pair через `resume`. Resume до создания допустим только для явно возобновлённой совпадающей lane. Не запускай команды с неразрешёнными placeholders и не prune-ь старые регистрации автоматически. Git — обязательный handoff для G; в другие пользовательские чаты не отправляй сообщения без прямой авторизации человека. После сохранения deciding outputs и полезных изменений переносите повторимые тестовые каталоги и использованные рабочие окружения только в Корзину. Корзину не очищайте; production data, код, полезную документацию и уникальные данные сохраняйте.

A–F работают только на собственных topic branches и не публикуют в `main`. G — единственный publisher интеграционной ветки. Будущая публикация в `main` требует отдельной явной авторизации пользователя для конкретной публикации; разрешение на уже опубликованный anchor не является постоянным.

Для admission назначь shell-переменным `E02_TOPIC_BRANCH` и `E02_WORKTREE_ROOT` выбранные реальные значения (второе — absolute path), затем выполни от корня репозитория:

```sh
(cd policy-engine && uv run --no-sync polisyos-tools workspace doctor --worktree-admission create --branch "${E02_TOPIC_BRANCH:?set actual branch}" --path "${E02_WORKTREE_ROOT:?set absolute worktree root}")
```

После создания checkout повтори ту же команду с `--worktree-admission resume` и той же парой. В облачной среде без штатной Корзины не удаляй данные навсегда: перечисли точные cleanup candidates в handoff.

Ты — облачный оркестратор B. Исполни полный B scope до canonical механизма, настоящего consumer и независимого deciding evidence; частичный slice не завершает задачу.

Корень E02: `policy-engine/docs/research/e02-cloud-test-plan/`. Иные пути ниже относительны этого каталога либо явно помечены `policy-engine/`.

## База и источники

Выполни `git fetch origin`. Проверь, что опубликованный интеграционный anchor `1ddcd7b3905e52c0d19db091823a64830139fa64` предок `origin/main`; запиши фактические SHA/tree `origin/main` как базу. Перед изменениями проверь чистую attached ветку. Каждый slice имеет exact base и candidate SHA/tree. Не бери базу из локальной исследовательской ветки. Не cherry-pick-ать старый B-кандидат `a3daffbe867ddfe9eede5e5990687283b552952a`: он не закрыл finding и имел CAS ownership failure и B66 cancellation XFAIL. Сверь текущий код на main; на G97 карта B отмечает только type-only изменение `common/async_tools.py` с тестом.

До использования baseline выполни проверку целостности, затем прочитай verification и запроси failures:

```sh
python3 policy-engine/docs/research/e02-cloud-test-plan/results/import_results.py --check
python3 policy-engine/docs/research/e02-cloud-test-plan/results/query.py --unit B --failures-only --limit 30
```

Прочитай полный `results/verification.json`, затем полные B-строки `bundle-owners.tsv`/`finding-owners.tsv`, все canonical B bundle criteria и точечные решающие cells. Не выводи ownership из 30 строк. Основные указатели: `closure-decisions/B.md`, `README.md`, `execution-sequence.md`, `cross-unit-contracts.md`, `verification-and-closeout.md`, `method-decisions.md`, `runtime-profiles.md` и `execution-prompts/HANDOFF.md`; полный знаменатель — `coverage.json`. B owns 25 bundles/60 findings. История G97: 56 partial, B61 held, B59/B150/B153 closed; это не новый census. Сохраняй regressions и не решай B61 без SKG owner contract. Внешняя библиотека для B не выбрана.

## Параллельность и Git

Задействуй до 20 прямых помощников на независимые проверяемые вопросы; helpers не создают helpers. Разведи авторство четырёх очередей ниже, consumer census, independent oracle, adversarial tests и reviews. Автор не рецензирует свой код. Один writer на canonical mechanism/file; каждому выдай точный SHA/tree, refs, write scope и expected receipt.

До создания helper worktree проверь точные branch и абсолютный path read-only admission командой из workspace README; сохрани полный JSON:

```sh
# Из policy-engine выполните workspace doctor --worktree-admission create
# с предварительно выбранными реальными --branch и --path.
```

`resume` допустим только для явно продолжаемой существующей пары branch/path. Не удаляй и не prune-ь регистрации автоматически. Рано опубликуй первый законченный slice и продолжай полный B набор. Код и handoff публикуй в собственных `codex/e02-B-<slice>` topic branches; Git обязателен для G. G — единственный publisher интеграционной ветки. Не push в `main`, force-push, rebase/reset; не пиши в другие пользовательские чаты без прямой авторизации человека.

В облаке не вводи квот процессов, workers, numeric threads или CPU. Проверки запускай параллельно; сериализуй только общий порт, fixture, DB/cache/scratch или writer. Не переноси production data: общие свойства доказывай fixtures, а intrinsically data-dependent остаток оставь G для exact candidate и read-only локальной проверки.

## Четыре обязательные очереди

1. **Async/deadline и B→C transport — RUN-01/02, EXE-01/02, JIT-01, NET-01/02** (точные ID и criteria в B.md/coverage). Для B69 logical admission reservation сохраняется до конца синхронных done-callbacks; physical slot занят до фактического завершения worker. При полном пуле nested submit немедленно возвращает `SharedExecutorReentrancyError`; Future proxy сохраняет result/exception/cancel, callback order/context и late registration. Барьерный oracle различает физическую занятость и раннее освобождение; проверь cancel-before-start и release capacity. Один monotonic deadline покрывает acquire→connect→health→register→retry→publication. Поздний connector handle после отмены не публикуется, cleanup и semaphore release ровно по разу. B владеет `fabric/connectors/pool.py`; C владеет stream/cursor/checkpoint и `fabric/data_plane/streaming.py` — не пиши в C-файл. Зафиксируй typed B→C handoff; на точных обеих версиях проверь pool→stream: cap-3 checkpoint двух строк, restart cap-1 отказывает до poll/flush/commit либо соблюдает согласованный contract, retry даёт `[1,2]`, затем `[3]` ровно однажды. В той же очереди закрой cache admission/deadline, ready frontier, retry baseline/context, JIT dynamic payload/single-flight/retry и monotonic fractional breaker с generation lease.

2. **Durable budget/lease — DUR-01/02.** B37 различает отсутствующий ledger, malformed/sparse wire и явный unlimited bootstrap. Cold public `record_spend` не создаёт implicit unlimited. Каждый load/mutate/reopen строго декодирует required поля реального writer до defaults/normalization, включая nested state; `{}`, `{"state": {}}` и удаление любого required поля настоящего snapshot должны отказать без изменения bytes. Легально опускаемые nullable fields не делай required. Позитивный control — явный `load_or_bootstrap(BudgetState())` остаётся unlimited после reopen. Проверь отдельные процессы через реальный middleware `record_spend_safe/pre_check`, exhausted limit, barrier read/write, atomic replace/fsync failure и fresh reopen: старый/новый полный snapshot или typed recovery, никогда unlimited fallback. Не заявляй этим power-loss/multi-host guarantee. B38 проверяет stale owner/lease expiry; B78 сохраняет `PrimaryExecutionOutcomeUnknownError`, а reconciliation требует реального внешнего idempotency/status contract.

3. **CAS/import/recovery — CAS-01/02/03.** B150/B153 — закрытые regression. B151 проверяет `FileSystemCAS.put_bytes`: corrupt blob и неверный `manifest.byte_size` дают точный отказ, затем retry→`get_bytes(ref)`→`verify(ref)`; валидная missing-sidecar успешна. B152 берёт size/hash/signature/report из одного byte snapshot; B154 требует typed per-item result полного batch и реального consumer до публикации; B155 ограничивает iteration, pending futures и deadline согласованно. B148 допускает no-op только для exact same tenant/cell/view/manifest/profile/signature/bytes под lease до staging; foreign/unbound import отказывает. Cross-tenant семантика в B.md — recommendation, требует owner decision. B149 делает exact inventory и атомарную generation, сохраняя старую полную версию при ошибке. Негативы: same digest/different bytes, wrong size, symlink/special path, interrupt, foreign tenant. Старый CAS-02 receipt не покрывает CAS-01/03.

4. **Composition/checkpoint/LLM — RUN-03, CMP-01/02/03, RES-01/02/03/04, STA-01/02, LLM-01/02, WIRE-01.** Реальная двухузловая registry chain потребляет required compiled edge; один payload materializer работает для sequential/async/resume; manual и automatic links используют одну typed acceptance. Не выдумывай WARN/STRICT authority. Checkpoint связывает exact ArtifactRef, tenant/content/view/origin, cache key, completed frontier, dependency version и per-node history; потерянная history остаётся incomplete, изменённый content/config инвалидирует reuse, state/frontier/cache refs публикуются одной generation. B61 остаётся held без versioned SKG `data_record` contract. B13 требует реальный route и локальную read-only data admission: в cloud используй fixtures и не редактируй A-owned `generation_cycle.py`/`run_lifecycle.py`. B66 settlement event/idempotent ack переживают caller cancellation; потерянный ack означает unknown, не нулевой расход. B67 принимает только owner permission, связанный с actor/scope/epoch и exact evidence refs; B68 single-flight разрешён после B66/B67 для exact scoped request. Optional metrics failure не гасит результат, accounting failure остаётся отдельным; B94 использует versioned Decimal и строгий typed decode.

## Receipts и closeout

Для каждого slice запиши exact base/candidate/tree, полный diff footprint/tests/companions, owner, property/runtime path, independent oracle, adversarial/property-removal control, consumer, commands и deciding output. Назови P38 divergence и P37 predicate basis. Marker/mock/constructor/collection/exit-code tests недостаточны. P41: inherited red только после replay точной команды на slice-base и нулевого пересечения полных gate inputs; иначе `not_established`, без универсального four-base replay. На втором escape одного класса — P40: расширь механизм либо укажи конечную границу и falsifier.

После implementation commit добавь отдельный committed handoff `implementation-handoffs/B/<slice>.json` по схеме HANDOFF; укажи implementation SHA/tree, не будущий receipt commit. Приложи полный умеренный deciding log; большие raw — только ignored `raw/` с `path@sha`, без секретов. После push проверь remote head/tree. Code acceptance отдельно от finding closure: разложи все 60 IDs по `closed/limited/held/open` с evidence и следующим владельцем.

После targeted checks на slices и повторных affected-consumer checks при смене upstream contract заморозь один кандидат и запусти **один** полный B cohort из плана вместе с новыми defining/consumer tests; пересчитай полный список файлов/cases и сохрани output. Старые 74 файла / 1,317 случаев — исторический снимок, не стоп-критерий. Общий cohort не заменяет per-finding решения и не позволяет остановиться после первого partial slice. Отчёт перечисляет FAIL/XFAIL/SKIP/UNRUN, отсутствующие inputs/backends и остаток для локального G.
