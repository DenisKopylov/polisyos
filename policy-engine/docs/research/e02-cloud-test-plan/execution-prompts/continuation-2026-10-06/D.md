# D — продолжение E02 с опубликованной базы

Сначала полностью прочитай `AGENTS.md`, `policy-engine/CONTRIBUTING.md` и `policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/HANDOFF.md`, прежде чем выполнять работу. Короткие E02-пути в этом поручении означают `policy-engine/docs/research/e02-cloud-test-plan/`; команды ниже выполняются от корня репозитория, кроме явно указанного subshell. Все необходимые решения находятся в tracked `closure-decisions/`, а локальные ignored outputs не являются входом облачной задачи.

Перед созданием любого checkout/worktree прочитай `policy-engine/tools/devx/workspace/README.md#worktree-admission`, выбери реальные точные branch и absolute worktree root, и выполни read-only `workspace doctor --worktree-admission create` с этими `--branch` и `--path`. Сохрани полный JSON; после создания проверь тот же pair через `resume`. Resume до создания допустим только для явно возобновлённой совпадающей lane. Не запускай команды с неразрешёнными placeholders и не prune-ь старые регистрации автоматически. Git — обязательный handoff для G; в другие пользовательские чаты не отправляй сообщения без прямой авторизации человека. После сохранения deciding outputs и полезных изменений переносите повторимые тестовые каталоги и использованные рабочие окружения только в Корзину. Корзину не очищайте; production data, код, полезную документацию и уникальные данные сохраняйте.

A–F работают только на собственных topic branches и не публикуют в `main`. G — единственный publisher интеграционной ветки. Будущая публикация в `main` требует отдельной явной авторизации пользователя для конкретной публикации; разрешение на уже опубликованный anchor не является постоянным.

Для admission назначь shell-переменным `E02_TOPIC_BRANCH` и `E02_WORKTREE_ROOT` выбранные реальные значения (второе — absolute path), затем выполни от корня репозитория:

```sh
(cd policy-engine && uv run --no-sync polisyos-tools workspace doctor --worktree-admission create --branch "${E02_TOPIC_BRANCH:?set actual branch}" --path "${E02_WORKTREE_ROOT:?set absolute worktree root}")
```

После создания checkout повтори ту же команду с `--worktree-admission resume` и той же парой. В облачной среде без штатной Корзины не удаляй данные навсегда: перечисли точные cleanup candidates в handoff.

Ты — облачный оркестратор D. Доведи все 17 пакетов и 45 findings до работающего механизма, consumer и независимой проверки. Полная карта — policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/D.md и coverage.json.

## Прочитай и проверь базу

Прочитай AGENTS.md, policy-engine/CONTRIBUTING.md, полный policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/HANDOFF.md, policy-engine/docs/research/e02-cloud-test-plan/execution-organization/README.md и policy-engine/docs/reference/policy-design-case-failure-patterns.md. Из policy-engine/docs/research/e02-cloud-test-plan/closure-decisions прочитай README, D, method-decisions, runtime-profiles, execution-sequence, cross-unit-contracts, verification-and-closeout и delivery-evidence. Сверяй полные owner TSV и canonical bundle criteria.

Из корня репозитория сначала запусти:

```sh
python3 policy-engine/docs/research/e02-cloud-test-plan/results/import_results.py --check
```

Затем прочитай полный policy-engine/docs/research/e02-cloud-test-plan/results/verification.json; после него запусти python3 policy-engine/docs/research/e02-cloud-test-plan/results/query.py --failures-only --limit 30 и точечные запросы. Query — навигация; ownership устанавливай по полным TSV и bundle criteria.

Выполни git fetch origin; запиши git status -sb и SHA/tree fetched origin/main.
Проверь, что anchor 1ddcd7b3905e52c0d19db091823a64830139fa64 — ancestor; slice base всё равно fetched origin/main. До каждого создания выбери точные branch и absolute root path и прочитай policy-engine/tools/devx/workspace/README.md#worktree-admission.
В product directory выполни `uv run --no-sync polisyos-tools workspace doctor --worktree-admission create` с выбранными реальными `--branch` и `--path`.
Сохрани JSON receipt (0 admit, 1 reject, 2 incomplete). После создания проверь ту же пару через resume; только для matching lane. Не prune/delete registrations.

Кандидат 6ac534aef6d19dc7b6d0cd2f969d16e6d8e756b2 основан на c40, вне G97 ancestry; receipts применимы только к unchanged assertions на exact source/tree. Fetch D refs/handoffs; проверь base/tree, полный code/test diff, runtime, oracle, negative, outputs. Новый head требует delta review; автор не reviewer своего кода. G sole publisher integration; D topic branches only. Handoff via Git, без сообщений в другие чаты без прямого разрешения.

## Пять очередей

Веди taskboard пяти очередей. Используй до 20 прямых помощников для независимых owners, oracles, negative tests, consumers и review; без children. Один writer и независимый reviewer на механизм; immutable candidates. В cloud не вводи CPU/process/test-worker limits; сериализуй только shared fixtures, ports и writers.

1. **Поиск и GP:** OPT-01/02/03, CTL-02. Переиспользуй locked optional BoTorch+GPyTorch SingleTaskGP, не пиши новый GP и не переходи на sklearn/Ax/TPE. Restore должен применять реальные train_X/train_Y и fitted mean/kernel/likelihood/noise, transforms, corpus/basis, refit clock и RNG. Semantic dates и bool/int schema — содержательные. Same-basis restore/append не вызывает MLL fit; initial=1, resume/append=0, due refit/basis change>0. Добавь fixed-parameter analytic oracle без model.posterior на 8–12 неповторных точках: независимо вычисли C=K(X,X)+sigma²I, mean и полную covariance, учитывая сохранённые transforms и исходные units; append сверь с реальным conditioning. Изменение fitted parameter, transform, warm row, RNG или checkpoint type при сохранённых markers должно менять результат либо fail closed. Backend missing = UNRUN.

2. **Transfer:** TRN-01/02/03. ANN — только discovery; каждый GP row требует exact ArtifactRef resolve из существующего CAS и content binding data/model/evaluator/split/metric/unit/direction/owner. В VectorMemoryStore собери immutable {dim,index,keys,metadata,key-map,ref/version}, опубликуй единым pointer swap, query захватывает pointer один раз. Barrier test через реальные readers доказывает цельный old/new generation при load/add; same ref с altered bytes откажет. Не добавляй второй latest pointer и не обещай distributed atomicity. Lesson local/transfer filters совпадают; access time не обновляет evidence freshness.

3. **Champion и SearchService:** OPT-04, SRV-01/03. Сравнение champion связывает exact candidate/evaluation/suite ArtifactRef+content, split/data/metric/profile/version; при смене suite сравнивай на одной базе. Проверь existing ChampionRegistry lock/flock, reread canonical predecessor, CAS/atomic pointer, competing writers, crash и fresh reader. G97 не имеет expected_predecessor API: не добавляй параметр, второй registry или distributed guarantee. Докажи реальный ask/tell caller/cutover, history, stopping, partial result, failure/resume и bounded rollback; чистый contract import не доказывает consumer.

4. **Controller, funnel, деньги и promotion:** CTL-01/03, FUN-01/02/03. Вызови фактического resource owner через существующие BudgetMiddleware→BudgetLedger/FileBudgetLedger; trace/display/estimate/compute_actual_usd не есть debit. Проверь stable run/candidate/attempt/event ID, settlement, persisted snapshot до/после и reopen, повторная доставка не удваивает charge; full/split сравнивай по реальным events. Отрицательный контроль сохраняет trace cost=1, удаляет settlement. Сохраняй per-run state и различия empty/zero/partial/failed, stage/aggregate verdict. B123: malformed-present typed result без scalar fallback; absent input — отдельный legacy control. B157 — real effective config.

   B164: bool promotion_write_allowed не authority. Требуется owner-issued typed permit с current независимой проверкой, candidate, run/ticket generation, purpose, schema/policy, provenance, validity и revocation epoch. Write owner проверяет revoke/generation в той же commit linearization boundary, сериализованной с revoke, что и эффект. Barrier negative отзывает после preflight: при bool=true effect count=0; valid permit даёт один write. Если issuer/verifier owner/API не существует, зафиксируй минимальный integrate-contract и bridge_missing; не строй новую permission subsystem. На повторном escape этого класса (P40) расширь механизм или зафиксируй ограничение с falsifier.

5. **Stopping и stress:** STP-01, STR-01. B122: нормализуй направление; plateau только при gain ≤ max(0.01 objective units, 0.01×abs(historical_best)); без объявленной unit/profile convergence не заявляй. B41 сохраняет freshness. B106 считает attempted, finite-evaluated и violations каждого scenario до grouping/top-k; один scenario максимум один раз. Fraction=(finite−violated)/finite; нулевой знаменатель unavailable, unknown/incomplete отдельно и partial. Это observed sample fraction, не population probability; изменение cap/grouping не меняет счётчик. B107 проверяет objective direction.

В каждой очереди запускай точные defining и affected-consumer tests, указанные в policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/D.md; добавь недостающий negative/removal probe. Каждый handoff JSON в policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/ фиксирует slice base, commit/tree, полный changed-path set, environment/backend/seed/inputs, runtime property, consumer, независимый oracle, divergent proxy, negative, complete deciding output, predicate basis и limitations. Сначала commit реализации, затем отдельный receipt commit со ссылкой на implementation SHA. После freeze/review проведи одну широкую wave, не после каждого merge.

## Вердикт и границы

Различай finding verdict closed/limited/held/open, исторический partial и check PASS/FAIL/ERROR/SKIP/UNRUN. Кодовая приёмка не закрывает finding; на каждый criterion требуется evidence либо owner/input. P41 inherited требует exact command на slice base и нулевого overlap с complete input denominator; иначе provenance not_established. Production проверяй локально/read-only только если criterion требует данные: exact candidate, minimum ref, без cloud transfer. Closeout: commits, per-bundle/finding outcomes, unavailable inputs, skipped backends, remaining verification; никаких unsupported claims.
