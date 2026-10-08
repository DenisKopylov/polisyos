# C — продолжение после C4 (7 октября 2026)

Ты — локальный оркестратор C. Цель — довести оставшуюся работу 33 C-пакетов и 54 findings до проверяемых решений по исходным критериям, передавая G точные receipts для независимой интеграционной приёмки. Это инструкция к продолжению, не новая adjudication: root C4 рекомендовал 31 `closed`, 9 `limited`, 14 `held`; формальный статус G для всех 54 остаётся `not_adjudicated`. Приёмка кода и закрытие finding — отдельные решения.

## Зафиксированное состояние и обязательное чтение

Начинай с текущего опубликованного `origin/codex/e02-integration`, запиши SHA/tree, ветку и `git status`; C4 carrier зафиксировал frozen G83 и позднее fetched G75; текущий разбор G выполнен на `6e8725faa42ca28c8fd72e5f8da4ca0f6e6a8f79`. Сначала fetch и проверь актуальный checkpoint/ancestry; эта публикация документации не меняет source acceptance. C root — `c5668bcb9ac76a55984fce0d196197dbfded1151`, tree `d360d36e2cf2dbd13e60422e174e229491e384be`. Источник исходных критериев — pinned main `198076863e143dea9f89f02734b13d50dae3eed5`; его anchor `1ddcd7b3905e52c0d19db091823a64830139fa64` присутствует в истории. Новая публикация в main для продолжения не требуется.

До действий прочитай корневой `AGENTS.md`, `policy-engine/CONTRIBUTING.md`, `execution-prompts/HANDOFF.md`, `execution-organization/README.md`, полный `closure-decisions/README.md`, `C.md`, `coverage.json`, `method-decisions.md` (включая C-M1/M2), `runtime-profiles.md`, `cross-unit-contracts.md`, `verification-and-closeout.md`, C4 root carrier и точный C54 table. C54 table — `C54-current-root-20261007-c4-v4.json` и `.md` в commit `847929e3e0cac30fb49ff61a47ecaf46d41ac94d`; JSON blob `466f4035d8634776b76cf4c6106b6bb99e003077`. Используй полные исходные criterion cards, owner rows, source и deciding evidence; summaries — только навигация. До использования transferred result pack запусти `python3 policy-engine/docs/research/e02-cloud-test-plan/results/import_results.py --check`, прочитай `verification.json`, затем `query.py --failures-only --limit 30` и точечные запросы. Проверка импорта подтвердила целостность перенесённых таблиц, но архивы исходных прогонов отсутствуют; baseline PASS/FAIL и короткая выборка не доказывают поведение нового candidate.

У C4 проверен полный знаменатель: 33 bundles, 54 findings, 59 criterion occurrences; original wording hashes совпали по всем 59 строкам. Это не означает, что все evidence refs или внешние источники нужно разрешить либо проверять. Ниже перечислены все 54 строки и актуальное действие; при любом изменении статуса сверяй его снова с полным C54 table. Relevant pattern pass: P29 behavioral oracle/removal, P35 полный знаменатель, P37 независимость gate premise, P38 property/proxy divergence, P40 повтор одного класса, P41 происхождение inherited red.

Оперативные уточнения G: [разбор C/D](../../integration/reviews/2026-10-07-CD-C4-a795/README.md) и [все54 next actions](../../integration/reviews/2026-10-07-CD-C4-a795/C54-actions.md). FQN support/alias/retirement — обычная bounded API lifecycle работа C вместе с canonical owner; не создавай новое institutional approval для LA-005/006/026/027.

## Две новые C slices: результат и точные границы

**CAN / LA-021, candidate `e3cb3fafc847b94a5d4b3adc03b814b4c711920c`, tree `2d27c9c182cf550088c5a8c072dc2f36df84e20d`; handoff `60b523c2d0e1a587f2f1d4b92a0ac9a89a1f49db`.** Изменён один canonical IR Mapping intake и его тест/README/release companion. Исправлена только JSON-mode форма separator tuple/list до strict profile validation; обычный `Mapping` передаётся до реального FileSystemCAS manifest readback, payload читается и остаётся тем же. На candidate сообщены 46 затронутых source tests PASS; отдельный witness прошёл полную JSON-mode Mapping сериализацию манифеста и fresh readback; 19 недопустимых профилей отказываются до чтения bytes, удаление normalizer делает positive witness красным. Старый G55b Mapping FAIL относится к прежнему source и этой исправленной дельте; **не выдавай его повторно как незакрытую CAN правку и не проси автора повторить тот же fix**. LA-021 всё ещё `held`: raw Core byte-emission/admission contract принадлежит B Core owner; для exact e3 non-editable wheel installed readback пока `UNRUN`, потому что локально отсутствовал Hatchling `>=1.27`. G может выполнить только точную wheel-проверку, если нужный build backend уже доступен локально и есть слот; старый wheel от 55b не годится. До решения B/Core и installed layer не объявляй весь LA-021 закрытым.

**NET/ING / новый C test-only slice `8580eb4a13cbd734e0a685069ea5bb16a1c5ee63`, tree `267fef2e1a46aee7a7b2c1f6baaa00bf66e3cbd9`; handoff `373c9623071f60c08f5e362e61d211829e5d8f5a`.** Production `streaming.py` не менялся. Десять selected current-composition checks прошли, независимая проверка дала bounded GO для cleanup-owner поведения: при startup/disconnect ошибках старый pool/handle остаётся у registry owner; новый отдельный session обрабатывает следующий row/checkpoint; permit возвращён ровно один раз (`pending_permit=false`, semaphore `1`); shutdown повторно закрывает тот же старый handle; no-op `_retain_cleanup_owner` нарушает assertion. Это не доказывает закрытие физического socket/FD: тест использует `file://`, где disconnect no-op; также нет hard physical-capacity или RSS guarantee. B87 остаётся отдельным открытым B finding.

Два B pool-stream selectors ещё `UNRUN` из-за ошибки fixture, которая сравнивает canonical JSON key-pairs со строкой `_message_id:event-N`. Путь исправления — decoder-only в B-owned oracle: распарсить канонические JSON pairs и сравнить упорядоченные key/value identities; не менять production serialization и не создавать C second writer. Fixture owner B: JSON-decode каждый persisted key, сравнить exact ordered field/value pairs; malformed/field/value/order mismatch остаётся красным. Cap-refusal selector должен проверять `StreamCapacityError(stage="restore", rows=2, max_rows=1)`, а не generic exception. Точные selectors: `test_pool_stream_budget_oracle.py::test_restored_frontier_above_new_cap_refuses_before_consumer_effects` и `...::test_admitted_recovery_emits_two_sessions_once_with_original_lineage`. После публикации исправленной fixture B/C владельцы сверяют их с текущим provider/API на точном immutable candidate и сохраняют полный output. Не объединяй прежние отдельные B receipts `1/1` и `7/1` в одну волну и не переноси их на новый C runtime. C-owned `test_net_ing_current_frontier.py` уже показал cap-1 отказ до poll/flush/commit/CAS write и cap-3 recovery; повторяй только при изменении upstream contract.

## Матрица оставшейся работы: все 54 строки

### Root C4 рекомендовал `closed` (31); G ещё должен независимо записать verdict

Для этих строк не повторяй неизменившиеся полные suites. Проверь immutable source/evidence и передай G точное bounded решение. Новая delta или изменившийся upstream contract требуют только affected re-review.

- **B17** — зафиксировать конечный provider/deadline критерий; не добавлять license policy prerequisite.
- **B81** — at-least-once с dedupe, failure/reopen/retry и cap-3 refusal/recovery; сохранить checkpoint-metadata limitation.
- **B82** — восстановление COUNT/TUMBLING/SESSION/SLIDING плюс cap refusal/recovery; no-output replay меняет checkpoint/cursor metadata.
- **B84** — только retained state, input rows/serialized bytes, output refs и cap path; нет вывода о RSS, pre-return allocation или spill.
- **B85** — exact contributor lineage для трёх восстановленных rows и fresh readback; не byte-idempotent checkpoint replay.
- **B86** — только объявленные FieldSpec profiles; не выводить schema из batch DataFrame dtype.
- **B88** — только retained source-card replay profile.
- **B138** — ограниченные JOIN lineage и saved-result readback, не все production routes.
- **B139** — occurrence identity в фактическом JOIN/SUMMARY input order; `source_a_value` — occurrence witness, не permutation-invariant event identity.
- **B140** — fixture-bound request contract, без caller-wide domain-ID policy.
- **B141** — fixture schema/local SQL, без global column rule.
- **B142** — isolated DuckDB fixture, без вывода о deployed service.
- **B143** — `_union` live MergeLogEntry reference peak, не RSS/global O(1).
- **B144** — operation-count bound, не walltime/production-memory speedup.
- **B145** — consensus только на declared inputs, без вывода об общей independence/valid measurement/unit comparability.
- **B146–B147** — сохранить именно периодное поведение `_period_to_dates`/builder: поддержанные calendar formats, leap/quarter/year, quarantine invalid/missing/bad-month, inclusive `period_end`; для `_iter_observation_metric_frames` — immutable per-source snapshot до первого yield, resume по row offset + metric ordinal, downstream D2 shards/counters/no duplicate IDs, admission/schema/semantic errors не становятся fallback.
- **LA-008** — bounded import/package result; внешние dynamic-import и configuration consumers не установлены.
- **LA-009** — bounded plugin/configuration consumers; внешние consumers не установлены.
- **LA-010** — разделить результат source `migrate.py` delegation и установленную CLI/strict DTO.
- **LA-011** — только selected workspace map/package, без out-of-checkout bootstrap или dependency sync claim.
- **LA-012** — bounded wrapper; unpublished external users и unrun benchmarks/JAX surface вне результата.
- **LA-013** — exact wheel/sdist/member bytes и five-root workspace map; host dependency setup и external source history вне результата.
- **LA-022** — конечная DomainPlugin discovery/ABI migration; будущая owner-issued admission — отдельная capability.
- **LA-030** — bounded D4 producer→artifact→public `read_api`, не все pipeline governance или production data.
- **LA-031** — шесть registered-stage parity/readback и пять direct importers; сохранить D5 clock projection и D3 optional-input limits.
- **LA-043** — все три generator corruption/missing/extra cases и независимый consumer, без unbounded external operations.
- **LA-044** — package generation и фактический installed consumer для declared scope.
- **LA-047** — focused Common/IR source suite, без installed root-layout claim.
- **LA-048** — RunManifest nested-path persistence/readback и Runtime resolution, не database dry-run.
- **LA-049** — Trinity source suite только для current version, не installed migration behavior.

### `limited` (9): сохранить bounded результат и закрывать только перечисленное

- **B79** — B connector/cursor owner связывает точный dataset, `ingestion_run_id`, cursor и evidence content; положительный promotion, отказ при absent/forged/mismatch и restart на том же source. Не требовать B83 identity для B79.
- **LA-006** — путь отсутствует уже в pinned trees; не восстанавливать и не удалять дальше. C package/public-surface owner выбирает bounded support/retirement exact `polisyos.foundry.domain.mechanisms` FQN, direct import/packaging и negative-reexport companions. Не требуй глобального разрешения 317 unrelated loader destinations или unknown external callers без доказанной direct dependency; их остаток сохраняется ограничением.
- **LA-024** — license authority даёт source-specific reuse rules для fetch/storage/normalization/inference/downstream; до этого только технический URL/MIME/bytes/CAS результат.
- **LA-034** — G фиксирует bounded tracked-consumer census; внешний тест нужен только после называния конкретного producer и consumer.
- **LA-038** — G downstream owner фиксирует bounded writer/readback; production corpus/assets нужны только если заявлен production scope.
- **LA-039** — сохранить fresh fixture producer/reader/removal; immutable model/corpus provenance запрашивать только для production claim.
- **LA-041** — bounded cache invalidation/checkpoint/failure retry и CAT editable fixture; remote/global source history и external authorization не заявлять.
- **LA-042** — retained legacy entrypoint в exact tested profile; external caller history/model-release owner нужен только при расширении scope.
- **LA-050** — MIG owner ищет authorized historical 0.9 manifest либо сохраняет предел: 19 documented paths, 129 columns/10 tables и четыре проверенных current 1.0 manifests. Не объявлять исторический 0.9 отсутствующим.

### `held` (14): ждать конкретного владельца/входа, не подменять authority фикстурой

- **B80** — verified evidence bound к точным dataset/run/cursor/content до promotion; positive, marker-kept отказ для absent/forged/mismatch и restart. Не затаскивать B83 как prerequisite.
- **B83** — B source-contract owner задаёт source-owned event/version identity, связанную с cursor/replay. Oracle `a,b,c,a` до/после restart, 86,400-second UTC expiry, source/partition isolation, independent map, durable live-key bound и refusal до eviction. Синтетический `_message_id` не authority.
- **LA-005** — public-surface owner решает, поддержан ли `polisyos.foundry.domain.schema`, с shipped-version/import/persisted identity, или авторизует retirement.
- **LA-018** — source-rights/trusted-source authority предоставляет source-bound identity, permitted purpose, verifiable trust input; HYG/C-W08 и canonical Lex/F-W07 owners проверяют selector и marker-kept `source_auth:null` отказ. Сейчас этот witness выбирает неавторизованный документ.
- **LA-021** — см. CAN выше: G не повторяет Mapping fix; ждёт B raw Core emission/admission contract или bounded bypass и, если backend доступен, exact e3 wheel/readback. Остаётся held до обоих слоёв.
- **LA-023** — product owner решает `.train`/historical `TrainingResult` promise; C-W15 — typed cross-call checkpoint/RNG profile или explicit unsupported. Не повторять completed one-call suite.
- **LA-025** — license authority разрешает reuse точных source bytes для точных Scholar операций; строка license не permission.
- **LA-026** — Data Forge schema owner решает, есть ли у `GeneratedSchemaModule` producer/consumer и supported FQN; иначе авторизует retirement только placeholder, сохраняя `kernel.schemas`.
- **LA-027** — DFK schema + active-plan owners решают canonical import, alias window и migration timing до compatibility changes.
- **LA-028** — A runtime/lifecycle owner выдаёт typed `run_profile/context`; C связывает same-profile producer→HTTP и доказывает missing-profile refusal без invented default.
- **LA-029** — G local resource coordinator вместе с UDF owner выделяет один eligible Linux/C7 candidate и проверяет create/start/stop/restart/cleanup + removal control. SSH timeout — availability evidence, не product failure и не доказательство отсутствия провайдера.
- **LA-032** — C-W19 owner даёт versioned source→ID inventory producer/artifact/bridge для четырёх readers; проверки correct selection и отказов missing/forged/swapped inventory.
- **LA-036 (BERL, математически load-bearing)** — E/F предоставляют content-bound conditional law с точным population/cohort, feature schema/order, epoch/time, support и verifier provenance. C подключает conditional draw/expectation к существующему coalition executor и проверяет оба настоящих consumers: Runtime `explanation_reliability` и Scientist `phase5_preflight`; persisted ExplanationBundle читается заново. Не объявлять conditional только по `background`/marker и не подменять условный закон маргинальным Kernel/SHAP background.
  - Следуй C-M1: verified Gaussian law; формулы conditional mean/covariance из pinned `method-decisions.md`; finite/symmetric/PSD covariance, точное variable order/schema и singular-support проверка, без скрытого jitter. Для affine model — hand-derived exact oracle. Для нелинейного bounded профиля заморозить K coalitions, epsilon/delta и IID fixed N до sampling; `N = ceil((b-a)^2 * log(2*K/delta) / (2*epsilon^2))`, union bound относится только к admitted law/model и structural bound. Если cap меньше required N — `precision_not_met` с достигнутой границей; не уменьшать N и не выдавать требуемую precision. Unbounded/unsupported функции — только заранее объявленный диагностический estimate/MCSE, не certified precision. Removal/mismatch negatives должны проверять law bytes, source/model/population/epoch, support, order и both consumers. C-M2 finite-support empirical law — только после одинаковой content-bound joint rows/weights/order; пустая stratum — typed unsupported.
- **LA-040** — C-W04/DFI сначала связывает persisted generation, immutable assets и served query profile. После получения paired inputs G может выполнить нужную criterion-specific bounded local read-only membership/projection проверку на exact candidate. Пользователь уже разрешил такую работу; новой авторизации на чтение нужных полей не требуется. Не экспортировать/copy payload, не сканировать корпус или подменять ordered membership basis полным DB hash. Историческое отсутствие чтения — факт прошлого run, не новый запрет. Выбранная DB присутствует (около 19 GB); не называть input unavailable. Не переносить no-row-read restriction на прочие findings как blanket правило; там используй только минимальные read-only inputs, прямо нужные исходному критерию.

## Организация исполнения и передачи

Параллельность строй по реальным independent tasks: при необходимости используй до 20 **прямых** помощников, каждый с immutable SHA, конкретным критерием, ожидаемым output и разрешёнными путями; помощники не создают детей. Автор не рецензирует собственный код. Приёмщик читает exact candidate/tree и полный source/test/companion diff; test получает изолированный checkout. Не размножай review для неизменившихся 31 строк. Тяжёлую локальную A/C/G проверку координируй в одном общем слоте; это ограничение не распространяется на облачные B/D/E/F.

На каждую source slice — отдельный append-only C topic и committed handoff, с exact base/candidate/tree, ancestry, writer/companions, canonical producer→artifact→bridge→consumer, independent oracle, negative/removal control, decisive output, environment и limitations. C публикует только собственные `codex/e02-C-*` topics. Регулярно fetch-ь G checkpoint, не переписывай историю и не cherry-pick/reset/rebase/force-push. **Не публикуй в main и не публикуй integration branch: единственный publisher G.** Между чатами сообщений не отправляй; Git handoff — канал.

Перед кодом отдели механизм, verification/oracle, missing input и authority decision. После изменения upstream contract повтори только затронутый consumer/property check. Общий дорогой replay выполняется один раз на frozen G SHA, не после каждого merge. Сохраняй полный deciding output и source/hash ссылки, избегай копировать derivable dumps. Production data остаётся read-only и не переносится в cloud; используй его только если exact criterion этого требует в рамках имеющейся авторизации пользователя. Не вводи новую общую норму полноты, обязательный census внешних callers или универсальное production-data prerequisite. `SKIP/UNRUN`, недоступный backend и отсутствующий authority вход — явные ограничения, не PASS.

Закрытие считается достигнутым, когда source property проходит на настоящем consumer path, независимый oracle и discriminating negative/removal подтверждают именно критерий, все companions сохранены, outputs привязаны к exact tree, а G отдельно зафиксировал admission и finding verdict. До этого используй точный root status/limitation и не переименовывай `limited`/`held` в `closed`.
