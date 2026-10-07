Прочитай также `execution-prompts/continuation-2026-10-07/COMMON.md` из fetched G. Полные пути ниже относительно `policy-engine/docs/research/e02-cloud-test-plan/`, если не указано иначе.

# F — продолжить работу после PR65 и завершить исходные критерии

Ты — облачный оркестратор F. Продолжай в существующей F-задаче: используй уже доказанные свойства и доведи все доступные codeable остатки до проверяемого результата. Не возвращай только очередной план или таблицу partial. На каждый из 35 исходных finding дай отдельное решение по исходной карточке, фактической цепочке producer → artifact → bridge → consumer → surface, решающему output и остаточной причине.

## Зафиксированная база и обязательное чтение

Свежо проверь origin, ветку, каталог, status и workspace admission. Сохраняй append-only историю: никаких reset/rebase/force, не исправляй неожиданную ветку переключением. Текущая публикационная точка G, указанная при постановке, — codex/e02-integration ff277db7798fc312654704fa51c52e00f53f10f4; fetch может показать более новый checkpoint — запиши реальный SHA и его отношение к этим пинам. Не пиши в integration branch; F публикует только свои topic/PR handoffs. Main не менять и не push.

Пины имеют разные роли: корневой evidence/adjudication carrier — 072d45a56d1119fe3e7665cec2cbbdca015d2934, tree f2b9b2d4bcc24a2feeae6f4873b61845a07cc090; точный product source — 8236d9c368336a5ea20c1586f29aea7321db6536, tree 724a77c88d4e6699ffead58a5e3e3990fb88640a; PR65 transfer carrier — 421f1dd977b237307394c68820caab4156716eb2, tree 0508db0976255da2d970168d1300ec6dbafcb1b2. Transfer/closeout carrier не является единым product candidate для всех методов. Для каждого компонента используй его собственные candidate SHA/tree и receipt.

Полностью прочитай root AGENTS.md, policy-engine/CONTRIBUTING.md, полный policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/HANDOFF.md, execution-organization/README.md, полный result pack и failure/repair register. Перед использованием baseline выполни из корня репозитория:

    python3 policy-engine/docs/research/e02-cloud-test-plan/results/import_results.py --check

Затем прочитай verification.json, выполни query.py --unit F --failures-only --limit 30 и точечные запросы. Уточняй знаменатели по полным TSV/JSONL/receipts, а ownership — по полным bundle-owners.tsv, finding-owners.tsv и оригинальным карточкам. Read-only summaries — навигация, не доказательство.

Прочитай из опубликованного root 072 и текущего Git:

- closure-decisions/README.md, F.md, coverage.json, method-decisions.md (F-M1–F-M16), runtime-profiles.md, cross-unit-contracts.md, semantic-decisions.md, execution-sequence.md, verification-and-closeout.md;
- integration/reviews/F-pr65-continuation-audit-2026-10-06.md;
- implementation-handoffs/F/continuation-transfer-20261006/REPORT.md, full-audit.json, per-ID/, artifact-transports.json;
- implementation-handoffs/F/continuation-closeout-20261006.json и его полный transport;
- original source cards B_r19_original.md и LA_r09_original.md через точные bindings из coverage.json.

Полная текущая таблица — 35 ID / 17 bundles / 36 original bindings; LA-016 имеет две привязки к одной карточке и остаётся одним ID. Сохрани исходную норму отдельно от короткой подписи и от промежуточного outcome. Текущая рекомендация F: 25 closed / 9 limited / 1 held; отдельная рекомендация по bounded technical criteria: 30 / 4 / 1; checks: 33 PASS / 2 UNRUN. Формальная G-приёмка не выдана. Ранний PR65 счёт 17/16/2 устарел. Check PASS, finding outcome, техническая рекомендация и G acceptance — четыре разные вещи.

## Полный собственный знаменатель F

Обнови ровно эти 17 bundle-групп, сохраняя строку каждого ID:

| Bundle | IDs |
|---|---|
| FIT-01 | B54, B56 |
| CAU-01 | B204–B206 |
| CAU-02 | B207–B209 |
| CAU-03 | B210, B211 |
| CAU-04 | B212, B213 |
| CAU-05 | LA-016 |
| GRF-01 | B216, B217, LA-007, LA-019 |
| GRF-02 | B219, B220 |
| GRF-03 | B214, B218 |
| SCM-01 | B221, B222 |
| SCM-02 | B215, B223 |
| SCM-03 | B224, B225 |
| ECO-01 | LA-004, LA-035 |
| FRY-01 | LA-001, LA-002, LA-037 |
| FRY-03 | LA-003 |
| API-01 | LA-020 |
| LEX-01 | LA-017 |

Не переисполняй неизменившийся bounded-проверенный пакет. F использует точные ранее доказанные candidate/receipt только на неизменившейся части и перепроверяет новый source delta, зависимости и affected consumer. Не перетаскивай и не cherry-pick cumulative carrier как новый owner patch.

## Обязательные реальные остатки

**Graph intake — исправить или честно ограничить.** Разбери tracked handoff implementation-handoffs/F/graph-intake-review-20261006.json и полный candidate/source. В measured producer→reconcile→CAS пути действующий ref возвращает ok без разрешения текущего content: после реального изменения X→Y на Y→X сохраняется старое X→Y, и shaped nonexistent ref тоже проходит. Кроме того, reconciler теряет endpoint marks: circle-circle PAG может быть сохранён как X→Y DAG без warning/review. Lagged intake пока не доказан через защищённого temporal consumer. Устранить class-wide: current ref сначала разрешается и content-reconciles; неизвестная ориентация сохраняется или typed-refuses до admission. Проверить положительный versioned graph, смену направления, missing/stale/fake ref, tail-tail/circle и lagged/static refusal на реальном reader. Не объявлять это решённым finite ADMG oracle или preflight is_valid. Если exact current source уже содержит исправление — предъяви его source-bound receipt и только affected checks.

**Installed-worker source reconciliation.** Отдельный head `3dde887e22592cdd7c1fe8865707afdfd72dc6fb` содержит девять новых commits после старого reviewed candidate `ab56a0f3`; `causal_graph.py` отличается от source8236/F-API. Сверь полный source/test/companion delta и canonical F/IR blobs, выбери один согласованный producer/reader contract и проверь только affected installed consumers. Старые199 PASS source8236 не являются whole-head PASS3dde. Не импортируй competing mixed carrier без reconciliation.

**Causal authority и ConfidencePass.** Сохрани реальные действующие protections: numeric SUCCESS/CI и поле identified_estimand сами не дают admission; missing/fake/wrong basis не должен становиться gate_eligible. ConfidencePass сохраняет блокирующую causal issue при отсутствующем/повреждённом sibling simulation CAS. Сейчас отдельный TMLE selected consumer и issue-preservation доказаны, но совмещённый consumer witness отсутствует. Проведи один тест по реальному пути: actual TMLE-produced persisted report → actual ConfidencePass/value consumer; оставь SUCCESS/CI/markers, затем добавь missing/corrupt sibling simulation reference и докажи, что blocker сохраняется. Положительный control — действительная admitted basis, а не строка/UUID/self-attestation. Если общий gate/IR — чужой canonical owner, не пиши параллельный механизм: подготовь узкий dependency packet и F-owned consumer proof.

Проверь уже опубликованные source fixes для content-bound Core/PDC identity, actual EvalSafety/context/challenge admission, normalized method output slots/raw-envelope distinction и DiD diagnostic binding по time_treatment. Не переписывай их и не повторяй весь suite: используй точные receipts source 8236, проверь только affected composed consumers после любого изменённого upstream contract. Никакой positive scientific authority из point estimate, worker package, compiler marker или warning suppression.

**Оставь ранее bounded-проверенные методы в узких поддержанных профилях.** Сверяй criterion, а не расширяй его до общего research project:

- B204–206: заявленные Standard DiD estimability/HC1-CR0/requested interval and honest pretrend states; pretrend non-rejection не доказывает assumption. B207–209: фиксированный selected-cohort target с оценёнными shares и ratio IF, shared-unit Mammen draws, centered/studentized null и согласованной инверсией pointwise interval; не меняй на θ_W/обычный нецентрированный bootstrap.
- B210–211: sharp CCT RBC/HC0 и поддержанная weighted algebra. Не заявляй fuzzy/clustered/masspoint/bandwidth-selector support без их входов и oracle. Clean-room RBC уже сравнивался с pinned rdrobust 2.1.0; не добавляй package в продукт автоматически. Сохрани выбранный clean-room runtime и independent external oracle; изменение поставляемой зависимости требует отдельного обоснования API/profile/совместимости по существующему method decision.
- DoWhy остаётся отдельным настоящим Python 3.12 / DoWhy 0.14 worker при Python 3.14 приложении: без собственного сервиса, чужой CAS writer и pickle. Реальный выбранный worker fit → CAS → fresh reader уже есть. Внутрипроцессные Python 3.14 DoWhy/EconML markers остаются UNRUN. Выбранная backend pass не выдаёт whole Node admission или реальную идентификацию.
- B216/B217 ограничены конечным static ADMG / настоящими указанными callers. Не обещай universal ID, PAG/CPDAG completeness или temporal causal identification. B220 detached-cache rows — bounded property; согласуй release fragment с фактическим public-surface inventory. B222 — existing polynomial helper/saved typed payload → CAS → query/twin/fresh reader; это не требование превращать default Hybrid fitter в nonlinear. B223 различает outcome/ITE distribution, estimator CI и posterior interval; MC spread fixed fit не CI. B224 do-surgery не запускает заменённый natural mechanism; B225 сохраняет истинный conditional tail law, не заменяет его атомом.
- TMLE держит bounded regular iid/binary EIF profile, при нарушении positivity не выдумывает доверительный gate. B54 cache/provenance property сохраняется; B56 требует фактический admitted shared-study workload и ресурсный budget только где это исходный критерий. Не выдумывай общий scheduler и не меняй число научных folds ради budget.

Внешнюю библиотеку выбирай, когда её фактический estimator, estimand, API/result semantics и допустимая поставка совпадают. Иначе reuse не оправдан: сохраняй корректную узкую реализацию и сравнивай с независимым oracle. Не замещай выбранный метод одноимённым package без сквозного producer/consumer свидетельства.

**Экономика: сверяй исходную карточку, не переносные подписи.** LA-004 требует сравнить native/plugin fiscal/labor модели при намеренно одинаковых режимах и доказать divergence на разных законах/контрактах. Это не Gini, не welfare-normative hold и не утверждение, что один профиль лучше. Пересверь точные строки original LA_r09, receipt и все зависимые поля отчёта.

LA-035 исходно про перенос и идентичность исторического GlobalState normalized-income/budget loss: сохранить именно его формулу, sign/scale regimes, бюджетный штраф, numeric guards и подтверждённых callers. Если score/objective остаётся прежним, отсутствие нового optimizer или normative welfare packet не является барьером и не нужно придумывать новое normative owner review. Только изменение welfare intent, ранжирования или желаемого объекта требует accountable owner/versioned objective. Проверь все original acceptance условия, включая реальные state/guardrail/JIT/gradient только там, где карточка их требует, и поправь все зависимые current captions. Не называй эту функцию максимизацией сырого дохода.

Gini отдельно: его bounded mathematical property доказана на неотрицательных доходах, но строгий C/PPO producer→Gini cross-path ещё не прогнан. Проведи narrow synthetic actual-route probe для signed active wealth. Если отрицательное богатство доходит до стандартного Gini, зафиксируй несоответствие исходной области; до решения canonical domain owner возвращай typed unavailable/limitation. Не clamp, не подменяй finite неверный coefficient и не выдумывай signed-Gini law. Не создавай новый finding ID для этого аспекта.

**Legacy, API и legal limits.** LA-007/LA-019/LA-020 оценивай по полному реальному maintained loader/FQN/direct/star/private/docs/install деноминатору. Source census candidates (включая computed imports), неизвестные external callers и 38 UNKNOWN export totals не доказывают ни фактических клиентов, ни их отсутствия. Разрешено закрыть только исходную поддержанную migration window; внешний/вычисляемый остаток обозначь явно и не утверждай repository-wide zero. LA-001 relocation RNG salt к исполнителю bounded-проверен; v1 same-node draw at steps 0/1 — отдельный disclosed law, не повод менять finding. LA-002 catalog/IC migration не требует четырёх новых family→state execution maps. LA-003 сохраняет law/PatchMap/RNG/ABI и объявленную precision boundary. LA-016 требует actual dedicated DiD request/FQN/flags/slots/plan migration, а не только wrapper. LA-017 dedupe не доказывает действующее право: authoritative current-law conclusion требует ровно нужный NormPack/source hash/jurisdiction/effective-time/custody input; без него оставь узкий limitation. Отсутствующий 175c blob — только четыре исторические non-deciding references, не блокирующий вход для текущих 35 IDs.

## Проверка, handoff и finish

Для каждой доступной codeable задачи: один canonical writer; source-bound immutable candidate SHA/tree; весь diff footprint включая tests/docs/release companions; positive runtime property; независимый oracle; negative/fake/retained-marker discriminator; affected producer/bridge/consumer/surface; полный deciding output. Коммит implementation отдельно от committed handoff receipt. Возвращай только точные, применимые slices; G fetch-ит exact remote refs и сам решает code acceptance. Finding closure остаётся отдельно.

В облаке запускай все готовые проверки параллельно. Не вводи CPU, worker, thread, test-count или quota ограничения; сериализуй только реально общий mutable fixture/cache/port/file. Production dataset не переносить; локально использовать read-only exact candidate только если исходный критерий зависит от фактических данных. После всех source changes дождись всех независимых reviews, затем один раз выполни дорогую affected/final wave. Общий G replay остаётся за G на integration freeze.

Финальный F пакет должен содержать ровно 35 строк: исходный критерий и binding, component SHA/tree, actual consumer/output, oracle/negative, решение F и его rationale, code slice/commit, отдельный статус проверки, G acceptance (если уже опубликована), limitation/owner/input и next concrete result. Исправь неверные dependent captions по P36. Сохрани unavailable inputs, skipped backends и remaining verification. Не засчитывай 33 PASS как 33 finding closure; не обещай 25 или 30 закрытий без row evidence. Не назначай F, G или себя научным/институциональным authority owner.

Сохраняй source, docs, уникальные inputs и deciding outputs. У облачного executor нет native Trash: не удаляй данные и не очищай корзину; при обнаружении повторимых неценных scratch/checkouts выдай точный перечень кандидатов для локального рассмотрения. Никакой main публикации.
