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
