# Epoch positive path — журнал lane

Branch: `codex/epoch-positive-path`. Slice base:
`034f30c64a79eb2020c04c6f0b0f07c90a74a1ee`.
Worktree: `/Users/deniskopylov/polisyos/.worktrees/epoch-positive-path`.

## Stage 1 boundary

Результат: [R1–R5 и EP-F01–EP-F08](../specs/2026-09-12-epoch-positive-path-stage1.md).
Stage 1 commit `5d6154ba1bfa0a03b5ee462062e5af5c6b357307` прочитан обратно из
attached branch; содержимое каждого пути побайтно совпало с worktree. Source не менялся. Исследование не назначает authority
и не утверждает production admission. `DEBT-REGISTER.md`, `LEDGER.md`, generated
surfaces и guardrails baselines не менялись. No push / no sync.

Name-admission повторён непосредственно перед `git worktree add`; он вернул
`admitted`, exit `0`. После создания attachment перечитан: ожидаемая branch и
точный base. Первая интерактивная выдача doctor была усечена, поэтому deciding
запуск повторён с полным сохранением stdout/stderr до создания worktree.

## Evidence

Все raw paths ниже относительно `docs/superpowers/journals/epoch-positive-path/`.
`raw/` gitignored; трактовать отсутствующий локальный raw как unavailable, не как
нулевой результат. Tracked source читается по `path@source_base`, копии source
не сохраняются в evidence.

| Receipt | SHA-256 | Что устанавливает |
| --- | --- | --- |
| `raw/admission.json` | `2849c202b35ebe5acefff54acc2b4c0bd651f5a246674ab2651c8bd60debe315` | Предсозданный name-admission, exit 0; не атомарная reservation |
| `raw/positive-census.json` | `e1feee00330a0659b2256f9ce26be35a23740584b7698bd05ddd19a4b19ae50a` | Полный `src/**/*.py` AST + independent Git/filesystem denominator, path/content read receipts и case-insensitive lexical cross-check; dynamic/external dispatch unresolved |
| `raw/row-selection.json` | `b0babc11c3c46305b244b66551a9460ed0b0a303e1b95be3497903d6cdea9372` | Все десять commissioning IDs найдены через canonical Markdown tokenizer и независимо anchored scanner; source `.md` hash, failures и exclusions сохранены |

Новый reusable measurement instrument не добавлен. Исследовательские reads
раскрывают selector, успешные/неуспешные reads, denominator и named unresolved
boundaries по `docs/how-to/author-measurement-instruments.md`; AST не является
runtime reachability oracle. Register selection намеренно не охватывает другие ID.

## Проверки Stage 1

Запущены только точные pytest nodes: no-signer before owner reads; exact history
predecessor; custody CLI durable refusal; acquisition CLI durable refusal;
production qualification refusal; non-coercive denominator reconciliation;
fake verifier provenance refusal. Полный вывод: `raw/stage1-targeted.txt`.
Отдельный in-memory removal probe сохраняет tracked source/DTO/refusal markers,
но отключает intake validation; неизменённый corrupt-provenance negative должен
стать красным (`raw/removal_probe.py`, `raw/removal-provenance.txt`).

Registered ledger check и architecture guardrails запущены каждый единственной
командой своей invocation, stdout/stderr полностью направлены в
`raw/ledger-check.txt` и `raw/guardrails-check.txt`. На момент Stage 1 записи
финальные exit codes ещё не получены; никакой зелёный статус не выведен из запуска.

Provisioning: offline `uv sync` вернул 1 из-за отсутствующего wheel в cache;
обычный frozen sync завершился 0. `corepack pnpm install --frozen-lockfile`
завершился 0 до любого TypeScript scanner. Ни lockfile, ни dependency declarations
не изменены. Общее contended resource — CPU/import cache на этой машине; state
store каждого targeted test изолирован `tmp_path`.

## Routing всех findings

- EP-F04: обе reduction proposals направлены в исходные пары ID; register не правится.
- EP-F05: stale verification blocker направлен в
  `ds18-positive-transition-verification-producer-missing`, existing GY-CR4 disposition.
- EP-F06/07 и positive temporal reader: существующая DS18 production row;
  concrete verifier — существующая verification row. Не отдельный sovereign subsystem.
- EP-F08: обе DS15 строки остаются отдельным acquisition work; transition lane
  не меняет порт, world state или re-entry semantics.
- Tool cache miss — nowhere в product register: восстановлен provisioning,
  не дефект продукта и не evidence его поведения.
- Текущий root checkout на другой branch — nowhere: пользователь явно потребовал
  отдельный worktree; он создан на заданном base без изменения root checkout.

Stage 1 не нашёл разрешения ждать институт перед build. Проверка reuse для
owner-controlled configuration, independent producer identity и complete provider
inputs продолжается до Stage 2; она не может заменить эти факты произвольными CAS
labels или объявленным `independently_reconciled`.


## EP-D01 и итог исследования

Повторный primary-source review уточнил раннее предположение об отсутствии
новых решений. `producer_identity_ref` может означать canonical origin либо
отдельное полномочие producer на minting; `C5-PREREQ-DV-EPOCH-ADMISSION`,
Task 4.4 и `CB-D01/CB-H01/CB-H02` требуют binding, но не выбирают accepted evidence
этой связи. [Decision card EP-D01](../specs/2026-09-12-epoch-positive-path-stage1.md#ep-d01--решение-на-котором-применяется-stop-rule)
содержит оба исхода и один различающий case. Независимый reviewer принял это как
NEW semantic-admission question по `P40`, а не ещё один owner-unappointed blocker.

Terminal: **`complete-pending-an-architect-decision on EP-D01: meaning and
admission evidence of epoch-transition producer identity`**. Stage 2 не начат
по stop rule пользователя; engineering gaps остаются названными и не закрываются
этой исследовательской поставкой. Нужен смысл authority assertion и достаточное
evidence, а не имя института. Решение может сослаться на существующий finding.

## Полученные behavioral receipts

| Полный output / harness | SHA-256 | Реально полученный exit / значение |
| --- | --- | --- |
| `raw/stage1-targeted.txt` | `68ecd873622e007ddd8867d8797300eb21d5cb2e3193529b683c7a295a2d6d09` | `1`; CLI child timeouts, не passing suite |
| `raw/removal_probe.py` | `ec203f8ccc32933f9503becc96aeb3bbdd33c2168a6d9d8a2526da7648f45a9c` | In-memory отключение `_validate_epoch_transition_receipt`; source/DTO/markers неизменны |
| `raw/removal-provenance.txt` | `db1e0e16017d0ee7439a5a47218573a433a920808d659ea920da53eec5bc4feb` | `1`; unchanged corrupt-provenance negative: `DID NOT RAISE` |
| `raw/provenance-restored.txt` | `423b1d0e014eb1eab96f4420f7b344c2615be505dd574b756ac884826ca74f2d` | `0`; тот же exact negative на исходном implementation |
| `raw/signed_tail_probe.py` | `6599773c00e8e05fe432902733fabd03ef3ee1813789b03c76ecc768315ce49f` | Изолированные test-controlled history/providers/key; не production admission |
| `raw/signed-tail.txt` | `543f911578c082a65453353b801d405a165c15ac2d5174b073d73df1c68c9031` | `0`; actual signed persistence/readback + Ed25519 verify проходят, producer возвращает `epoch_transition_exact_evidence_unavailable` |

Полный selector первого запуска (каждый путь — конкретный test node, не каталог):

```text
uv run --no-sync python -m pytest -q
 tests/unit/runtime/quality/test_epoch_validity_cascade.py::test_unappointed_transition_signer_returns_typed_negative_before_owner_reads
 tests/unit/runtime/quality/test_epoch_validity_cascade.py::test_file_transition_history_adapter_resolves_exact_declared_predecessor
 tests/unit/runtime/quality/test_epoch_custody_audit.py::test_cli_persists_both_unappointed_roles
 tests/unit/runtime/quality/test_acquisition_epoch_admission.py::test_python_module_is_runnable_terminus
 tests/unit/runtime/quality/test_semantic_epoch.py::test_production_acquisition_invokes_epoch_adapter_and_returns_policy_admission_missing
 tests/unit/scientist/validation/test_decision_validity_service.py::test_epoch_denominator_reconciliation_receipt_bridges_both_owner_definitions
 tests/unit/scientist/validation/test_decision_validity_service.py::test_epoch_batch_rejects_fake_verifier_provenance_without_state
```

Это один argv; переносы только для читаемости. CLI custody был остановлен самим
test harness на `180 s`, acquisition CLI — на `120 s`, до stdout/stderr.
Они остаются **runtime invocation unverified by this run**; не выдано ни
`inherited failure`, ни подтверждение production readiness. Destination:
этот журнал, verification/tooling limitation; source не изменялся и отдельная
product debt из двух таймаутов не выводится. No timeout был увеличен в tests.

Восстановленный negative запущен как
`uv run --no-sync python -m pytest -q tests/unit/scientist/validation/test_decision_validity_service.py::test_epoch_batch_rejects_corrupt_appointed_verifier_provenance_without_batch_state`.
Probes: `uv run --no-sync python <raw/removal_probe.py>` и
`uv run --no-sync python <raw/signed_tail_probe.py>`; полные пути выше.

Incidental signing finding направлен в **EP-D01 reuse boundary**, не в общий
security backlog: generic strict identity check отклоняет mismatch только если
обе identity присутствуют (`core/artifacts/signing.py:639-655`). В этой lane это
доказывает недостаточность этого API для producer authority; оно не объявлено
универсальной уязвимостью и unrelated signing source не исправлялся.


## Первая guardrails wave: невалидная для clean freeze

`uv run polisyos-tools architecture guardrails check` вернул **`2`**, не `0/1`.
Инструмент явно сообщил `UNRUN`, потому что OpenAPI generator не завершился:
`OwnerValidationTimeoutError` для `confidence-ledger-risk-spend` после `184 s`.
Partial artifact output дополнительно приписал generator изменения journal/spec
вне assigned scratch. Это **наши параллельные doc writes во время measurement**,
а не установленная порча от generator. `P41`: не называется inherited.
Destination — этот журнал, lane verification sequencing; исправление — frozen
повтор exact guardrails command после прекращения записей. Никакого sync.
Первый полный output сохранён как `raw/guardrails-check.txt`, SHA-256
`2d4df1e367d68bb9b3fb4fe0835431c0d0860b8fc942df26205ecdb0adae27b1`.

В первой wave одновременно работали Python import/owner-validation процессы;
их причинная связь с timeout не установлена. Для контроля этого фактора
final guardrails повторяется после завершения
ledger и при byte-frozen документах; итоговый receipt дописывается только после
его выхода. Первая wave не используется как clean verdict.

## Окончательные deciding gates и граница P41

Frozen wave выполнена на attached `04973dfb757d431d1ad3e912d10007c33cc246a9`;
до окончания команды tracked documents/source не менялись. Затем тот же exact
guardrails command выполнен в существующем integration worktree на attached
`main` с точным slice base `034f30c64a79eb2020c04c6f0b0f07c90a74a1ee`.
Attachment и чистота base перечитаны до и после replay. Каждый ledger/guardrails
запуск оставался единственной shell command своей invocation, с полным capture
stdout/stderr. Дополнений к команде, sync или изменения snapshot не было.

| Полный output / receipt | SHA-256 | Реальный результат |
| --- | --- | --- |
| `raw/ledger-check.txt` | `3a5a44ae364a637b8a982e04420a17e1d9cc521f4a89cd30846be865155f20dd` | `0`; instrument сообщает `complete_verdict: true` в пределах своего file-reader coverage |
| `raw/ledger-receipt.json` | `f8a6932632cd4ddd9f5153b3bc1a2e62bb756a803778aa5daec32e90efcebd1b` | Process-start time и completion observation; elapsed upper bound `2499.815 s` |
| `raw/guardrails-frozen.txt` | `06619b9b47c0da7de4ed7c947bead25b5e9dffc954eea0bc2729ed6ec1c4123c` | `1`; completed OpenAPI output differs from committed snapshot |
| `raw/guardrails-base.txt` | `444e2163b80db1e9edee88288055c5dc32704fde44f59f0088a655b15b333939` | `1`; same diagnostic on the exact slice base |
| `raw/guardrails-receipts.json` | `0c53ca67a5ba398466930d17a6a974c6b0aa2a493f83863ae4fbf8b4c42d5f3e` | Invocation-to-observed-completion upper bounds: frozen `433.866 s`, base `702.480 s`; scopes and limitations |

Ledger проверяет в том числе resolving test identities через collection, не
исполняет положительный epoch path и не подтверждает его admission. Каждое
информационное замечание полного output маршрутизировано в указанный там debt ID;
в частности GY-DEF23 сопоставлен с его source standing. Это не новые closures
и не повод менять запрещённые register/ledger files в этой lane.

Final guardrails failure — `runtime-openapi-snapshot`:
`schemas/runtime_api_v1.openapi.json` отличается от generated bytes. Frozen
повтор не сообщил ни прежнего timeout, ни escape от параллельной записи docs.
Диагностики frozen/base побайтно равны после замены только точных worktree prefixes.
Это **воспроизведение finding**, не доказательство равенства generated bytes:
временные generated snapshots не удержаны и такое равенство не заявляется.

**P41: inherited classification = `not_established`.** Полное непересечение
изменённых путей с transitive OpenAPI/owner-validator input denominator не доказано.
Guardrails копирует product tree, а отсутствие source diff само по себе не
доказывает неучастие документов в consulted dependency basis. Кроме того,
существующие окружения использовали разные patch versions: lane Python `3.14.3`,
base Python `3.14.0`. Поэтому повтор на правильной базе не превращён в более
сильный вывод о владельце breakage. Destination: правило **P41**, зарегистрированная
family **runtime-openapi-snapshot**, approval owner **team-polisyos**, version owner
**team-runtime** (`architecture/generated_artifacts.toml:728-748@source_base`).
Поставка не объявляет guardrails зелёным и не чинит incidental snapshot drift.
Standalone Atlas-gate notice — explicit nowhere для этой lane: Atlas surface
не изменена и эта проверка не входила в commissioning.

## Полные независимые review conclusions

Пересылка исходных deciding conclusions после freeze не была новым review round;
никаких новых findings/source edits она не добавила. Retained summaries не
подменяют полный текст:

| Review | SHA-256 |
| --- | --- |
| `raw/review-positive-mechanism.md` | `061590c1fc00d7e1faaa2490667c5941aa5d99f14410ba9d0be22054fc0faf51` |
| `raw/review-row-adjudication.md` | `d81dc625284a5395d558524f1b096489694a8442e199f8de0c464b883a0a58dc` |

Первый полный R1–R5 review относится к Stage 1 commit; EP-D01 прошёл отдельный
delta review. Поздний readback reviewer проверял R2, а не повторял весь census.
Оба review явно сохраняют эту границу и оставляют independent engineering gaps
открытыми. Failure/repair register перечитан перед closeout, включая P37–P41;
новое правило или изменение pattern register не требуется.

Terminal остаётся **`complete-pending-an-architect-decision on EP-D01: meaning
and admission evidence of epoch-transition producer identity`**. Source, tests,
`DEBT-REGISTER.md`, `LEDGER.md` и generated artifacts не изменены. Исследовательская
поставка не является реализацией positive production chain.

## Stage 2 — продолжение после ответа EP-D01

Исторические findings и terminal Stage 1 выше не переписаны. Исполнение продолжено
от attached `7478bc5222505429722b57cbb9293bd854454aa8`; base of record остаётся
`034f30c64a79eb2020c04c6f0b0f07c90a74a1ee`. Ответ архитектора установил provenance
canonical execution как смысл producer identity; отдельное minting right withheld.
Append-only execution contract закоммичен как
`9cc6aba6621c1f534fcaaa091d925a3cb373b106` и перечитан из attached branch до source
edits; исходный Stage 1 prefix сверён побайтно с `7478bc522`.

Исправленный stop predicate относится к конкретному зависимому звену. Смешанный
remainder не останавливает независимую инженерную работу; пустое назначение
не блокирует mechanism и composition root. Destination исправления — EP-F06/07
и execution contract этой lane, без редактирования register/ledger.

### Зарегистрированная generation basis и среда

До новых deciding gates lane `.venv` переведена на тот же interpreter, что и main:
Python `3.14.0`, base executable
`/opt/homebrew/Cellar/python@3.14/3.14.0_1/Frameworks/Python.framework/Versions/3.14/bin/python3.14`.
`uv sync --python <exact-base-executable> --offline --frozen --extra lint --extra test
--extra runtime --extra ml` вернул `1`: wheel `scikit-learn==1.8.0` отсутствовал
в локальном cache. Повтор той же provision без `--offline` вернул `0`; после него
interpreter/version/base executable перечитаны из lane `.venv`. Dependency lock
не менялся. Это provision, не product gate. Family `runtime-openapi-snapshot`
по-прежнему требует зарегистрированные runtime/ml extras; успешный exit producer
сам по себе не доказывает эту basis.

| Полный output, relative to `docs/superpowers/journals/epoch-positive-path/` | SHA-256 | Результат |
| --- | --- | --- |
| `raw/stage2-provision.txt` | `5aa2c19842e332bee1758fffd13dd72675629133904e55c602bc8fbd092dfa71` | `1`, offline cache miss |
| `raw/stage2-provision-online.txt` | `3092a9c0c0306c0bd76c28fac7070cc71a242f34e5119f04e7127b75670469d8` | `0`, frozen registered extras installed |
| `raw/stage2-dvs-enumeration-red.txt` | `3606767fd521580aced223997343cf46a6868cde8f86d049e698b346ec6d71af` | `1`, intended missing complete target-to-owner reader |

Последний RED — Python `3.14.0`, exact three named pytest nodes in
`tests/unit/scientist/validation/test_decision_validity_service.py`:
`test_epoch_impact_snapshot_for_targets_enumerates_all_owner_keys`,
`test_epoch_impact_snapshot_for_targets_refuses_incomplete_owner_index`,
`test_epoch_impact_snapshot_for_targets_rejects_false_artifact_profile`.
Parametrized corruption composition — unreadable member, missing owner row,
wrong owner filename; independent counterpart is the full packet index. Source
implementation отсутствовала при запуске; result is the expected missing-method
failure, not an environment timeout. Later GREEN/removal receipts follow below.

### Stage 2: выполненные production links и собственные найденные дефекты

Применена independent code-verification matrix: canonical emission/origin, actual
HTTP caller, strict owner/reconciliation, исходные negatives и property removal.
Источники требований — EP-D01, CB-D02/D04/D12 и Task 4.3/4.4, не fixture markers.
Run-control endpoint действительно вызывает production bridge: изначально пустой
origin-owner не может прочитать известный signed artifact; actual canonical
execution создаёт admission, затем exact readback допускает strict batch.
Контролируемые institutional/source inputs этой пробы не являются appointments.

Первый HTTP запуск не дошёл до продукта: отсутствовал production catalog.
Создана ignored symlink `production_data` на main read-only directory; database
read-session открывается с `read_only=True`. Фикстура затем выявила собственный
missing tenant ownership. Артефакты стали создаваться в настоящем tenant context.
Отдельная startup-проба уже выявила source defect: verifier provenance был
создан до tenant context и не читался HTTP. Исправление — реальная идемпотентная
запись собственных canonical verifier bytes через обычный CAS writer в active
tenant/cell, без обхода ownership для чужого evidence. Удаление этой записи вновь
делает исходную HTTP-проверку красной.

Origin и issuance admission indexes получили operation-time tenant/cell scope.
Scope берётся из trusted access/tenant context, не из request DTO. Читается весь
индекс выбранного scope; нечитаемые members не пропускаются. Эти находки — один
P32/P37 class на более глубоком уровне, а не новые институциональные blockers.

Обе CLI subprocess-пробы повторены отдельно. Реальные exits — `0` и `0` на
Python 3.14.0; существующие child bounds 180s/120s в этих изолированных запусках
не сработали. Предыдущие timeout outputs не переименованы в product failures.

Все следующие root результаты произведены lane `.venv` на CPython 3.14.0 с
зарегистрированными frozen runtime/ml extras; полный interpreter basis указан
выше. Полные stdout/stderr сохранены, включая собственные RED и setup failures.
Для CLI selector — точные nodes, названные выше. HTTP selector —
`tests/unit/runtime/http/test_decision_validity_api.py::test_canonical_epoch_origin_reaches_registered_http_batch_intake`.
Removal harness вызывает этот неизменённый node и требует фактический pytest exit1
после удаления каждого свойства. Исходные consumer AST отдельно сверены с
7478bc522; это проверка сохранности, а не замена behavioral negatives.

| Полный output в `epoch-positive-path/raw/` | SHA-256 | Actual exit / scope |
| --- | --- | --- |
| `stage2-http-intake-attempt1.txt` | `fc697b90c163955c48fb3a9ee74426ca2638517adf364a7801cdb034ce23dfa0` | `1`; HTTP fixture setup: missing read-only production catalog; not a product verdict |
| `stage2-http-intake-attempt2.txt` | `50b9ccf51ca3e9707b60348727b687e67a900a4314b45d9ee8d2933a9516f85a` | `1`; Actual HTTP refused unowned fixture artifacts; request-shape and signature-code negatives passed |
| `stage2-http-intake-attempt3.txt` | `423b1d0e014eb1eab96f4420f7b344c2615be505dd574b756ac884826ca74f2d` | `0`; Controlled canonical signed origin reaches actual registered HTTP route |
| `stage2-startup-provenance-red.txt` | `81ed7e468002196c31a23d76c5703cb0bbf500539526e444a42d6d58b577e0a7` | `1`; Actual HTTP rejected startup provenance as unowned; own product defect |
| `stage2-startup-provenance-green.txt` | `c4b808d34f4db00b333696dec1f3a43a2887d8bfe0cb7af07a3cb98ff43a7830` | `0`; HTTP startup provenance and canonical verifier targeted nodes |
| `stage2-http-production-bridge.txt` | `9ca1fa2e8165577b11eacde04a729b3e68fdb540a05bab5536e1ea6a2ae5e2bd` | `1`; New test asserted wrong existing refusal code; no product change |
| `stage2-http-production-bridge-2.txt` | `423b1d0e014eb1eab96f4420f7b344c2615be505dd574b756ac884826ca74f2d` | `0`; Actual HTTP invokes canonical producer and newly admits previously absent origin before strict batch |
| `stage2-http-removal-probes.txt` | `71e53a33ffeb491a763573a42764caeea8c427408d21c5f5da924c699b719f34` | `0`; Harness baseline0 and each unchanged HTTP node1 after actual producer/provenance property removal |
| `stage2-original-intake-negatives.txt` | `06955fb47f16312e5d13266c774a2aa4648c46e423cbe6564a92e25b68e39131` | `0`; Original strict provenance/denominator/ambiguous/corrupt/frozen-binding/omitted-target/replay/crash nodes |
| `stage2-custody-cli.txt` | `423b1d0e014eb1eab96f4420f7b344c2615be505dd574b756ac884826ca74f2d` | `0`; Exact test_cli_persists_both_unappointed_roles; existing180s bound; run alone |
| `stage2-acquisition-cli.txt` | `423b1d0e014eb1eab96f4420f7b344c2615be505dd574b756ac884826ca74f2d` | `0`; Exact test_python_module_is_runnable_terminus; existing120s bound; run alone |
| `stage2-preserved-boundaries-final.txt` | `1f8d458d0774578b96b3a63792e87255b4e6b68e790b1bf77606a82ab6a88bd3` | `0`; Selected protected AST methods + Stage1 byteprefix + protected register/ledger preservation; not runtimeproof |

Incidental findings routing: tenant composition и origin/issuance admission —
существующая `ds18-positive-transition-production-unorchestrated`; strict
verification/reconciliation — `ds18-positive-transition-verification-producer-missing`.
Read-only catalog setup и ошибочный expected code новой test fixture — explicit
nowhere в product register, это исправленные harness/setup issues. Public facade
companions следуют existing architecture public-surface owner; generated counts
выведены из полного состава exports, не заморожены тестовой константой. Guardrails
sync и baseline update не выполнялись.

### Дополнительные review receipts и сохранённые границы

Полные независимые reviews (relative paths под `epoch-positive-path/`):

| Complete review | SHA-256 | Область |
| --- | --- | --- |
| `raw/stage2-config-review.md` | `a89038f4b3c18c8d49c654c411b2ab20b76f3f2412a5a50f32758a0a572df91f` | Configured policy/custody/native verification, retained signed-false-hash falsifier, operation attestation; полный argv и hashes deciding outputs внутри |
| `raw/stage2-promotion-config-review.md` | `c619204ff12eb71d02bec6300a4065e004c0f672a2bbe9c81d88119c7a202931` | Actual deployment install → promotion query owner и pre-N9 gate; protected consumer predicates неизменны; removal of each composition link detected |
| `raw/stage2-positive-verifier-review.md` | `f530f2454dd79f46926bb5715f930fd4866dedf3ae7bd11f2540a822a97ac046` | Exact producer/origin, tenant index, frozen reconciliation, full owner packet custody, bounded shared-DVS denial residual |

Все перечисленные reviewer runtime gates используют CPython 3.14.0. Сам review
не означает appointed native authority; actual configured fixtures и default
refusals отделены в каждом receipt. Новые conditional branches проверены
behavioral removal, не поиском field names. Нечитаемый raw на другой машине —
unavailable evidence, не отрицательный результат и не ноль.

В первом review native signed transport принял ложный predicate content hash.
Это собственный P32/P37 escape. Repair сохранил независимую native verification
как привилегированный типизированный slot: без её реального implementation
`policy_owner_relation_not_established`. Тот же signed-false-hash falsifier после
repair отказывает. Другая native semantic hash domain не угадывается по raw CAS.
Destination — обе исходные predicate-policy rows, не назначение new authority.

Оригинальный `DecisionValidityService.admit_epoch_validity_batch`,
`NoEpochTransitionVerifier.verify`, transition `_bind_transition`,
promotion-query validation/negative owner и `ArtifactEpochValidityAuthorityGate`
не меняют свои deciding bodies. Composition может дойти до EP-D03 с реальным
qualified result, но consumer всё ещё отказывает. Temporal positive-reader arms
также сохранены. Это precise dependent links, не причина остановить producer,
independent origin, complete impact или deployment wiring.

Review обнаружил cross-tenant false impact: общий старый DVS index содержал
недоступный packet другого tenant, а новый reader включал его в snapshot.
Перед selection теперь exact-read/verify каждого packet; всё множество owner
packet/dependency JSON остаётся denominator. Missing/foreign member даёт refusal.
Существующий общий DVS owner index может отказать при foreign rows; миграция всех
DVS consumers на tenant partitions не выполнена и не заявляется. Это bounded
availability residual существующей verification row; ложного mixed-scope
admission новая ветвь не даёт. Исходный RED сохранён в reviewer receipt.

### Frozen source evidence and final targeted-wave findings

Stage 2 строит canonical invocation origin из реального State/RunManifest/NodeSpec
и отдельно observed source/loaded code. Независимая проверка сохранила различие
между observation и complete admitted execution closure. Recipe вычисляется
Runtime owner; native owner должен независимо reconcile полный code/tool/environment
denominator. Отсутствующий source остаётся typed nonreceipt. Это bounded P37/P38
residual CB-D12, не отдельное minting right и не отмена EP-D01.

Собственная candidate-regression найдена и исправлена: обычный JSON dictionary,
похожий на ArtifactRef, преждевременно валидировался как authority reference.
Теперь полное наблюдение сохраняется, absent/default source возвращает nonreceipt
до authority-grade reads; configured admission по-прежнему проверяет точные bytes.
Настоящий random_seed и finite-float params меняют invocation/recipe и packet
согласно execution. Удаление environment reread или native owner readback при
сохранённых markers ловится неизменёнными negatives.

HTTP witness усилен до реального Claim ledger advance: origin index первоначально
пуст, endpoint запускает canonical producer, strict intake завершает batch,
существующий Claim owner сохраняет successor head и MARKED_STALE event.
Контролируемая test authority не выбирается deployment по умолчанию.

Все runtime результаты ниже используют lane CPython3.14.0 и frozen runtime/ml
extras; это не повтор Stage1 gate на3.14.3. Full output и command scope сохранены
в referenced receipts. Scoped GREEN не объявляет broader NL wave зелёной.

| Raw evidence under `epoch-positive-path/raw/` | SHA-256 | Actual meaning |
| --- | --- | --- |
| `issuance-closeout-receipt.json` | `37fdffe0fa5703483fb226f275510bd11b36f3f9095102b55401e63222da0f68` | Complete argv, frozen source hashes, scoped exit0; broad NL exit1 separately retained; environment/owner-readback removal actual exit1 |
| `stage2-closure-attestation-review.md` | `4418f735a3a9e592ea24eac2be52d3f5aa27f12a72defb8dfeb013e1bee9ec06` | Captured execution-closure operation: RED1, GREEN0, removal detected, configured HTTP0 |
| `stage2-positive-final-delta.md` | `b5ae3d5537aee6461a2fb77b161518c350a824c683ba6c18f7a6bce70894c192` | Actual HTTP canonical producer → completed batch → real Claim ledger head advance; no consumer weakening |
| `stage2-http-removal-probes-final.txt` | `76204ade65a52818f3483477e72883d86c18c147a170d37295d6eebcce199bfc` | Harness exit0: baseline HTTP0; actual producer trigger and active-tenant provenance removal each expose unchanged test with pytest1 |
| `stage2-http-removal-probes.py` | `b53e3dab9c8803792b16a566d437740d6caa29294877551ef2b5b9a621ed2b9d` | Complete HTTP behavioral removal harness; no marker-only acceptance |
| `stage2-public-surface-frozen.txt` | `7736c8619e426b73b682176b69f7d5a8ce3d3de18e163c2a5f15f2455ccabf57` | Canonical public owner regenerated exact tracked composition; exit0, no diff, no guardrails sync |
| `stage2-public-surface-final-crosscheck.json` | `1be5c0bcfed6baf2991f837760d78261f34efc9833c6dfcfa29a18e20238efb3` | Independent literal __all__ AST vs complete inventory entries for the named public modules |
| `stage2-final-static-receipt.json` | `da39b8605e27e5611e8056e0cb5fe0c810837d24553a69ebf78f517c2edc42ed` | Complete changed Python file denominator, ruff0 and git diff --check0; Python3.14.0 |
| `stage2-final-targeted-receipt.json` | `90d16d484bfa52f703f5f341c234f5528f5c715f01aff025dd1a717db4a724d8` | Full named-file targeted wave exit1: original mixed-document constructor test omitted newly required epoch collaborator; source authority refusal was not reached |

Incidental destinations: candidate reference interpretation → existing production
row and P37/P38; mixed-document constructor test companion → explicit nowhere in
product register (the existing refusal stays mandatory); NL authority identity
failure → the existing runtime authority publication owner, diagnosis/replay below.
No register or ledger edit is implied by these destinations.

### Companion repair and complete row-set reconciliation

The original mixed-document negative now supplies the newly required epoch
collaborator from the same factory instance. Its `factory-only` exception
assertion is unchanged. No production constructor or authority consumer changed.
The full previously red named-file command is replayed below, not replaced by
only its green subset.

- `epoch-positive-path/raw/stage2-mixed-deployment-companion-review.md` @ SHA-256 `d67d21b054b6cf361efbab6ea1b6eca9df230dc9132095d192f0404b69158bbf` — Exact original constructor negative exit0; only new collaborator argument added to its fixture.
- `epoch-positive-path/raw/stage2-row-composition-check-exact.txt` @ SHA-256 `0d1957aa1699b483812dbcca7148354fd988c1899f556ac788ddeb753c5c4143` — exit0: commissioned IDs = appended disposition IDs = exact first-column register members.
- `epoch-positive-path/raw/stage2-preserved-boundaries-frozen.txt` @ SHA-256 `95a04931261dcc7af4303b2ee25e7d3d79eebbe9380bd084a2e8ef5b7ea11caa` — exit0: original protected deciding AST, Stage1 byte prefixes and protected register/ledger bytes reread.

The initial row cross-check exited1 because its harness matched cross-references
in row prose as if they were first-column identities. The corrected instrument
uses exact first-column membership, retains the full commissioned denominator,
and reconciles all three sources. Both outputs are retained; no ambiguous match
was reported as an absent row. Destination: explicit nowhere in the product
register, a corrected lane evidence harness (P35/P38).

### Source freeze and exact targeted replay

The complete originally red named-file argv was rerun after the single mandatory
test companion repair. Actual exit **0**, wall time 104.466s, CPython3.14.0.
No directory-wide pytest command was used. The selector denominator is the exact
file list in the receipt, with canonical pytest execution as its independent
collection/execution cross-check; no constant test total is pinned.

- Complete command/interpreter/result: `epoch-positive-path/raw/stage2-final-targeted-replay-receipt.json` @ SHA-256 `cd5d1f774b79f475e53eb3157c6a2278649e0c0847beb9a4d4b9468f6df31732`.
- Complete deciding output: `epoch-positive-path/raw/stage2-final-targeted-replay.txt` @ SHA-256 `7207695f774a89cab03be766edd6e60ec4c93f6b01817bcc1ff64d2d8d4be496`.

Failure/repair register reread before freeze, specifically P37/P38/P40/P41.
The broader NL publication failure remains separately under exact slice-base
replay; it is not erased by these passing epoch checks. No remaining source
writer is active. Source, tests and mandatory companion documents are committed
at this boundary; registered ledger and guardrails results follow separately.

### Registered gates on the attached source commit

Source commit `476383d759232c062171b34f1357145a10473827` was read back
from `codex/epoch-positive-path` before deciding gates. Both registered commands
were each the ONLY shell command in their invocation, with complete output
redirection. Scheduling correction to the earlier plan: they overlapped after
source freeze because the ledger collector and isolated generation probes had
separate scratch and no shared owner writes. This changes scheduling only.

Ledger actual exit **0**. Guardrails actual exit **1**, only the registered
OpenAPI snapshot mismatch. Live gate and OpenAPI child processes used exactly
CPython3.14.0; the child producer was invoked with runtime/ml extras. The canonical
OpenAPI owner then returned0 into scratch. Full parsed JSON comparison confines
the candidate difference to the confidence-ledger-risk-spend response example
and its consulted dependency/replay/projection bindings. It is not a route/DTO
change. Independent complete denominator review and companion verification follow.

- `epoch-positive-path/raw/stage2-source-commit-readback.json` @ SHA-256 `594ff578f62f61ca2ad1842282079d60ea55031dc6a4b24ec8e2c706e4bd4a21` — Attached source commit476383d75; every committed changed blob independently reread vs worktree; clean.
- `epoch-positive-path/raw/stage2-registered-gates-first-receipt.json` @ SHA-256 `f8dde1e7043547e2a4285d7b009bebf2aa34725460c95e333969a556da6f6158` — Registered ledger actual0; first guardrails actual1 on OpenAPI only; canonical producer actual0; exact argv and live3.14.0 witnesses.
- `epoch-positive-path/raw/stage2-ledger-check.txt` @ SHA-256 `45a091563ee40761ac0b415b91d8c2390ead2022a2648b7344a9017994d00a61` — Complete registered output; informational findings retain the existing row IDs printed by their owner.
- `epoch-positive-path/raw/stage2-architecture-guardrails.txt` @ SHA-256 `06619b9b47c0da7de4ed7c947bead25b5e9dffc954eea0bc2729ed6ec1c4123c` — Complete first guardrail output; snapshot drift is not an inherited exclusion.
- `epoch-positive-path/raw/nl-importer-adjudication.md` @ SHA-256 `f546a590c8103c786bfb2c5cb6d1f274784cd0fc4e6387439790809735d4f3b2` — Full-module current/base actual1/1; same failed-node list; changed-path intersection defeats P41 inherited exclusion.
- `epoch-positive-path/raw/nl-adjudication-evidence-sha256.json` @ SHA-256 `139509a443f167bb074fcf894f37158c8826edd16095a3c19861d47c825ea54f` — Complete NL output/diagnostic/source-origin evidence manifest, including harness failures.
- `epoch-positive-path/raw/nl-base-cleanup-receipt.json` @ SHA-256 `c77ad972c59e21befdc300555f595cfc4e34f7584384a7fca86717cef43890ca` — Only reconstructible base export removed; complete deciding evidence retained; symlink targets preserved.
- `epoch-positive-path/raw/stage2-public-scratch-cleanup.json` @ SHA-256 `81a9be8458510890cf40b34171c8318d77c14b0ece3658e212443d79694b2841` — Only reconstructible canonical public-owner scratch copies removed; committed outputs and deciding evidence retained.

NL finding destination is **EP-B01**, the explicit backlog entry appended to
the Stage2 specification, owned by Runtime NL authority publication. No source
repair or inherited exclusion is claimed for it. Ledger informational findings
remain with their existing row IDs/rules in the complete output; no row status
or standing is rewritten.

### OpenAPI mandatory companion adjudication

The registered snapshot includes the confidence-ledger owner's actually consulted
dependency basis. Its full denominator is the completed validation worker's
`dependency_bindings`: all observed file types, directory listings and explicitly
missing paths under the product root. It is **not** a Python-file count. The
independent reviewer rehashed every member, reconstructed the aggregate and
worker receipt, and obtained exactly the canonical candidate bindings. No unreadable
member is converted to zero. The kind/file-type/root breakdown and full membership
are in the referenced outputs, rather than freezing the moved total in a test.

Complete JSON comparison, independently repeated, confines the change to existing
confidence-ledger-risk-spend example provenance and its dependent replay/projection
identities. Components and non-example structure match. Real generated client
renders match. No consumer, operation, DTO or authority/status rule changes.
The registered owner mandates refreshing this consulted-basis companion; no
guardrails sync or baseline update is used. Historical old-manifest causality
was not reconstructed and no inherited exclusion is claimed.

The complete consulted basis excludes lane docs, release fragments and Git HEAD;
these final record changes do not alter its identity. The exact candidate
`sha256:39d4bba20ad24062d8dea4599e8847bc59346b92fff4ded638b4388eaacc282b`
was copied into `schemas/runtime_api_v1.openapi.json`; the release fragment
declares its compatible `schema-openapi-abi` example update.

- `epoch-positive-path/raw/stage2-openapi-independent-basis-review.json` @ SHA-256 `b8335ff334ee99c654ad56b66f6fee730e06b0812908a8973572873fa7de03e4` — Complete owner binding denominator independently rehashed; candidate aggregate and worker receipt exactly equal; complete JSON changes confined to existing response example.
- `epoch-positive-path/raw/stage2-openapi-dependency-worker.json` @ SHA-256 `64ad7c24e8d56460990687c7c4b39aebe124dd3c0285c6194ce5a2302ccc997c` — Full deciding owner output with dependency_bindings; existing confidence-ledger validation, no ledger generation.
- `epoch-positive-path/raw/stage2-openapi-dependency-worker-receipt.json` @ SHA-256 `8564a553613433e16c0ca70f88a770d871f1b5706391c9b6c8f5234c8124d6e4` — Actual worker exit0, CPython3.14.0,27.42s, exact request/argv/basis.
- `epoch-positive-path/raw/stage2-openapi-complete-json-diff.json` @ SHA-256 `16c87cfcd5feb31ca1a3f230e776407e21088c8f86c4b10e4e7fe28186d59b27` — Root complete JSON-tree comparison, cross-checked independently by reviewer; no operation/component change.

The next registered guardrails run tests this committed companion. Runtime
source/tests remain the already reviewed and exercised source commit.
