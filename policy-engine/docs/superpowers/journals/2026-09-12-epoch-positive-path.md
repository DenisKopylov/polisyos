# Epoch positive path — журнал lane

Branch: `codex/epoch-positive-path`. Slice base:
`034f30c64a79eb2020c04c6f0b0f07c90a74a1ee`.
Worktree: `/Users/deniskopylov/polisyos/.worktrees/epoch-positive-path`.

## Stage 1 boundary

Результат: [R1–R5 и EP-F01–EP-F08](../specs/2026-09-12-epoch-positive-path-stage1.md).
Stage 1 коммитится до любого изменения source. Исследование не назначает authority
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
