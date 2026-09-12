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
