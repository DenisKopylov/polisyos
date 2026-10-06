# F — продолжение E02

Сначала полностью прочитай `AGENTS.md`, `policy-engine/CONTRIBUTING.md` и `policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/HANDOFF.md`, прежде чем выполнять работу. Короткие E02-пути в этом поручении означают `policy-engine/docs/research/e02-cloud-test-plan/`; команды ниже выполняются от корня репозитория, кроме явно указанного subshell. Все необходимые решения находятся в tracked `closure-decisions/`, а локальные ignored outputs не являются входом облачной задачи.

Перед созданием любого checkout/worktree прочитай `policy-engine/tools/devx/workspace/README.md#worktree-admission`, выбери реальные точные branch и absolute worktree root, и выполни read-only `workspace doctor --worktree-admission create` с этими `--branch` и `--path`. Сохрани полный JSON; после создания проверь тот же pair через `resume`. Resume до создания допустим только для явно возобновлённой совпадающей lane. Не запускай команды с неразрешёнными placeholders и не prune-ь старые регистрации автоматически. Git — обязательный handoff для G; в другие пользовательские чаты не отправляй сообщения без прямой авторизации человека. После сохранения deciding outputs и полезных изменений переносите повторимые тестовые каталоги и использованные рабочие окружения только в Корзину. Корзину не очищайте; production data, код, полезную документацию и уникальные данные сохраняйте.

A–F работают только на собственных topic branches и не публикуют в `main`. G — единственный publisher интеграционной ветки. Будущая публикация в `main` требует отдельной явной авторизации пользователя для конкретной публикации; разрешение на уже опубликованный anchor не является постоянным.

Для admission назначь shell-переменным `E02_TOPIC_BRANCH` и `E02_WORKTREE_ROOT` выбранные реальные значения (второе — absolute path), затем выполни от корня репозитория:

```sh
(cd policy-engine && uv run --no-sync polisyos-tools workspace doctor --worktree-admission create --branch "${E02_TOPIC_BRANCH:?set actual branch}" --path "${E02_WORKTREE_ROOT:?set absolute worktree root}")
```

После создания checkout повтори ту же команду с `--worktree-admission resume` и той же парой. В облачной среде без штатной Корзины не удаляй данные навсегда: перечисли точные cleanup candidates в handoff.

Ты — облачный оркестратор F. Доведи свои 17 bundles / 35 findings до исполнения исходных критериев и отдельного решения по каждому. E02 означает repo-relative каталог policy-engine/docs/research/e02-cloud-test-plan. Полный inventory, owner paths, selectors и oracle — в E02/closure-decisions/F.md и coverage.json; сверяй каждый ID с исходной карточкой.

## База и входы

G опубликовал anchor 1ddcd7b3905e52c0d19db091823a64830139fa64. Fetch origin; подтверди, что свежий origin/main содержит его предком, запиши фактические main SHA/tree и ответвляйся от текущего main. G97 source 97c85fae2d4505ec8248540d98b9556296244208 / tree e77c0741d3b19acb43e07a0de2bdb97c8fa98ee3 — audit base, не текущий candidate. Перепроверь уже принятый код; не применяй его из старых веток. Не push-ить main.

До использования результатов запусти python3 policy-engine/docs/research/e02-cloud-test-plan/results/import_results.py --check, проверь verification.json и выполни python3 policy-engine/docs/research/e02-cloud-test-plan/results/query.py --unit F --failures-only --limit 30 плюс точечные запросы. Ownership бери из полных TSV/coverage/cards/handoffs, не summaries. Прочти AGENTS.md, CONTRIBUTING.md, HANDOFF.md, execution-organization/README.md, pattern register, closure-decisions/README.md, F.md, method-decisions F-M1–F-M16, runtime-profiles F, cross-unit-contracts, semantic-decisions и verification-and-closeout.

Предыдущий результат — transfer/navigation-only, raw archives отсутствуют; старые PASS не доказывают новый candidate. Ограниченно приняты API-01, CAU-02 admission, FRY-01 contracts, ECO-01 dtype и LEX-01 binding: не повторяй без delta и не считай closure. B219 held до backend readback; optional SKIP/UNRUN не PASS.

## Организация и приёмка

Используй до 20 прямых агентов по независимым срезам, без grandchildren. Группируй по source paths: один writer на механизм/schema/lock и отдельный reviewer. Каждому дай immutable SHA, isolated checkout, write paths и acceptance evidence.

В облаке не вводи process/worker/thread/CPU quotas; запускай проверки параллельно, сериализуя только shared mutable resource. Не загружай production data. Synthetic DGP достаточно; intrinsically source/law/history-dependent критерий пометь limited/UNRUN и запроси через G точный read-only rerun на candidate.

Используй append-only codex/e02-F-<slug> topic branches; G — единственный publisher integration. Для slice запиши base, полный diff, implementation SHA/tree и отдельный committed handoff JSON в E02/implementation-handoffs/F. После push перечитай remote SHA. Не пиши в другие чаты.

Для каждого finding раздельно укажи check PASS/FAIL/ERROR/SKIP/UNRUN и outcome closed/limited/held/open, criterion, producer→artifact→bridge→consumer, oracle/negative, SHA/tree и output. Проверь remove-property-keep-markers и P38. P41 требует exact slice-base replay и полный disjoint denominator, иначе not_established. Второй escape класса по P40 требует расширить механизм или задать конечную limitation/falsifier. Старые PASS, refusal, marker, schema и importability closure не доказывают.

Полный inventory: CAU-01 B204–206; CAU-02 B207–209; CAU-03 B210–211; CAU-04 B212–213; CAU-05 LA-016; FIT-01 B54/B56; GRF-01 B216/B217/LA-007/LA-019; GRF-02 B219/B220; GRF-03 B214/B218; SCM-01 B221/B222; SCM-02 B215/B223; SCM-03 B224/B225; ECO-01 LA-004/LA-035; LEX-01 LA-017; API-01 LA-020; FRY-01 LA-001/002/037; FRY-03 LA-003. Финальный отчёт — строка на каждый из 35 IDs.

## Выбранные решения

- CAU-01: hand/independent OLS oracle ATT=3. Rank-deficient preperiods — invalid; недостаточные — not_testable, никогда passed. Разделяй HC1 iid и unit-cluster CR0; не обещай small-cluster coverage.
- CAU-02: реализуй фиксированный overall-participation scalar target: усредни eligible ATT по заранее заданным post-periods каждой когорты, затем взвесь по estimated ever-treated cohort share. Включи ratio influence term доли. Один iid Mammen multiplier на panel unit общий для всех cells; используй centered studentized null test и инвертируй ту же проверку в pointwise CI. Не используй θ_W, uncentered bootstrap, silent cell drops/renormalization или anticipation-contaminated controls. Проверь unbalanced-cohort DGP, null/alternative, binomial coverage bounds и реальный run_causal_evaluation → CAS → fresh consumer.
- CAU-03: нужен sharp RDD RBC, не WLS covariance/IK heuristic/flag. Сверь tau_bc, se.rb, robust CI и настройки с rdrobust 2.1.0 на curved heteroskedastic DGP и seeded coverage. Fuzzy ограничен до typed treatment input. Изолированная dev install и numerical oracle уже разрешены этой задачей; не запрашивай новое подтверждение. GPL-3.0 distribution decision отдельное: subprocess его не решает. При отказе включать пакет реализуй clean-room CCT RBC по публикации без копирования GPL source. Не оставляй RBC навсегда unsupported; нужен реальный non-skipping backend consumer test.
- CAU-04: приложение остаётся Python 3.14; DoWhy 0.14 — pinned Python 3.12 worker через existing bounded orchestration. Worker без PolicyOS import/CAS/authority; versioned strict JSON. Parent валидирует refs/response, пишет CAS, Python 3.14 consumer читает artifact. Реальный вызов: CausalModel → identify_effect(proceed_when_unidentifiable=False) → estimate_effect для backdoor.linear_regression ATE, control=0/treatment=1, target_units="ate", confidence_intervals=True и method_params={"confidence_level":0.95}. Не передавай confidence_level прямым аргументом. Проверь фактический estimator level и get_confidence_intervals(confidence_level=0.95). CI только finite ordered scalar формы (2,) или (1,2); malformed/reversed/extra/NaN/Inf не исправляй. Сверь statsmodels OLS alpha=.05. API/metadata не PASS.
- SCM-01 отдельно требует реальный DoWhy GCM mechanism assignment → gcm.fit → source/row-bound persisted model → fresh reader; import и NumPy fallback не засчитываются. DGP X normal, Y=2X+noise: проверь do(1)-do(0)=2 и row permutation negative.
- SCM-02/03: outcome/ITE quantiles — distribution, не estimator CI; CI требует independent-unit bootstrap с refit, posterior interval имеет отдельный тип. Gaussian abduction сравни с аналитическими conditional mean/covariance, включая singular evidence и common row IDs. Для Y=1+3X same-arm contrast=0, do(2)-do(0)=6. Проверь точный do surgery и CDF/support только declared Normal/Uniform/TruncatedNormal samplers; unknown law и lagged static query — typed limited/refusal.
- FIT-01: recompute cache identity из data/config/fold/model/seed/split; caller key не bypass validation. Все folds реально исполняются в existing worker budget. Binary TMLE сохраняет [0,1]; EIF interval ограничен своим regular iid profile.
- GRF: independent exhaustive small-graph m-separation и latent-DAG surgery oracles. Для B219 установи NetworkX 3.6.1 и проверь actual MultiDiGraph mixed parallel-edge export/readback; B219 held до этого. B220 проверяет nested mutation/cache/copy. GRF-03 не повышает PAG approximation или lag serialization до identification; static GCM реально отказывает на lagged/unresolved graph. После graph contract change повтори A EMP-01; при E uncertainty change — F CAU-04/SCM-01.
- API-01: полный consumer/FQN/docs/monkeypatch/export census с denominator, затем wheel/sdist install и canonical identity. FRY-01 докажи seed→persisted salt→actual RNG и family certificate→state consumer→installed layout. FRY-03 сравни реальные fiscal/labor/plugin patches на equivalent fixture, сохраняя различия units/laws.
- ECO-01: не выдумывай welfare norm; historical normalized-income score при income≥1 равен −1 при любом масштабе. Помимо dtype, проверь Gini независимой pairwise формулой: [1e−12,2e−12,3e−12] должно дать 2/9; текущий +1e−8 denominator даёт −1.33053836. Проверь scale invariance и typed behavior при нулевом среднем. Исправь реальный Gini defect как scientific-function работу, а не dtype patch; closure LA-004/035 только если это совпадает с исходным критерием — нового finding ID не создавай.
- LEX-01: duplicate legal/legal pass refs не должны удваивать blockers: canonical dedupe или typed refusal, проверка actual plan consumer. Это не новый ID и не closure всего LA-017 само по себе. Lexical diff выдаёт source-bound topics, не causal KPI/legal authority; current-law input остаётся local-only, если exact criterion этого требует.
- Scientist policy-gate graph intake проверь только по предлагаемому узкому пути через существующий reconcile_causal_graph owner; не присваивай F все graph writers. propagate_uncertainty.py остаётся E writer. Подробности остальных F критериев бери из F.md/method-decisions.md; не повторяй принятую работу.

## Передача G

Передай topic refs/SHAs и committed receipts через Git. Сдай таблицу 35 IDs: criterion, actual consumer, code SHA, check result, finding outcome, limitation/следующий owner. Различай accepted code и closed findings; укажи unavailable inputs, skipped backends и UNRUN.
