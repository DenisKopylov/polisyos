# E02: публикация базы продолжения, 2026-10-06

Пользователь явно поручил G перенести нынешнюю интеграцию в `origin/main`,
затем подготовить шесть заданий A–F. Это публикация рабочей базы продолжения,
а не E02 closeout, production promotion или утверждение CI-green.
Старые записи `main_publication: not_authorized` остаются историческими снимками.

Код и пакет решений опубликованы fast-forward в обе remote refs — `main` и
`codex/e02-integration` — на `1ddcd7b3905e52c0d19db091823a64830139fa64`,
tree `498ff43267dfceaacdeb8de92b1e79cb38a44316`. После push выполнен fetch
и readback remote main. История не переписана; обычные hooks не отключались.
[Шесть промптов продолжения](../execution-prompts/continuation-2026-10-06/README.md)
добавлены следующим append-only коммитом в ту же опубликованную историю.

## Код и приёмка

Проверенный source: `1c0a87b385d65aa17f63b26157295976c4029ea3`,
tree `7c5f08b211010a468b69b8c75f0cafc68b3f4d52`; предыдущий remote main:
`c40d4acae1ce58b597267255026d9356565828fd`.
История допускает fast-forward. Все 15 checkpoint slices сверены по ancestry
и footprint: 14 bounded code slices и один D navigation slice.
Held runtime candidates в эту базу не добавлены. Новых finding closures нет.

Четыре независимых code-review lanes рассмотрели canonical/ABI,
calibration/DoE, backtesting и causal/economics/Lex изменения.
Результат — bounded GO с сохранением ранее объявленных ограничений.
Поздний `B/run-final` из PR #33 не принят и не включён.
Текущие topic heads проверяются заново при будущей приёмке, без повторного
cherry-pick уже принятых предков.

Публикационные companions уточняют фактическую совместимость Lex и calibration:
public-stable `NormImpactAnalyzer` сохраняет явный пустой plan и отказывает
неподдержанным passes; experimental calibration не подтверждает неполную кривую.
Исправления release metadata и cloud-ссылок не меняют source/tests/lockfile.

## Свежие deciding checks

Полные умеренные outputs и receipts находятся в
[checks/main-publication-20261006](checks/main-publication-20261006/).
Их локальные абсолютные paths описывают исходную среду; удалённый читатель
пользуется соседними tracked logs и воспроизводит selectors на указанном source.

- Изолированный `git archive` проверен по всем 13 679 tracked blobs;
  импорты шли из его source, без production data и копирования dependencies.
- 41 selector: все 21 changed test files и 20 direct consumer selectors.
  Первый pytest wave: 406 PASS, 8 SALib skips, 0 failures/errors, 74.84 s.
- SALib 1.5.2, multiprocess 0.70.19 и dill 0.4.1 установлены в отдельный
  ignored overlay. Повтор только пропущенных selectors: 53 PASS,
  0 skips/failures/errors, 2.08 s. Базовая venv и lockfile не изменены.
- JUnit reconciliation дал 459 разных passing case identities и нулевое
  пересечение passing cases двух waves. Это scoped regression, не вся suite.
- Ruff check по 39 changed product Python paths — PASS.
  Format check — FAIL: `doe/analysis.py`, `doe/uncertainty.py`,
  `tests/unit/remediation/test_doe_02.py`; косметический долг не скрыт.
- Results importer `--check` — PASS до чтения inputs. Coverage `--self-check`
  — PASS: 127 bundles, 282 findings, 291 criterion occurrences;
  четыре count-preserving corruption controls отвергнуты.
- Workspace admission G после Trash-only переноса stale admin и Finder
  metadata — `admitted`, complete verdict, без findings/unresolved inputs.

[Exact clean guard receipt](checks/main-publication-20261006/clean-candidate-guardrails.json)
фиксирует candidate `1ddcd7b` / tree `498ff432`, неизменённые branch/status/tree
до и после двух команд, полные соседние outputs и их SHA256:

- Architecture guardrails — FAIL, exit 1, 167.917 s: 151 deep-import creep
  instances, baseline drift и drift generated OpenAPI/trust-posture outputs.
- Runtime API contract — FAIL, exit 1, 34.713 s: generated OpenAPI drift,
  включая confidence-ledger projection/source hashes и dependency count.

Эти результаты относятся к чистому кандидату. Атрибуция red —
`not_established`; inherited verdict без P41 replay не заявляется.
Первый architecture run пересёкся с намеренной правкой шести docs издателем;
он не является проверкой immutable `1c0` и не доказывает tool-caused mutation.
Общий дорогой E02 replay и data-dependent closeout остаются после исполнения
A–F и общего source freeze. Последующие prompt/docs companions не превращают
этот receipt в проверку другого полного tree; product source не меняется.

## CI и границы публикации

Live GitHub admission не обнаружил applied rulesets или classic protection.
Это не CI acceptance. Repo-tracked merge policy ожидает PR/review и зелёные
Fast/Standard gates; нынешнее поручение пользователя публикует конкретный
bounded checkpoint как новую рабочую базу с явно незакрытой verification.
Защиты, workflows и checks не отключаются и не ослабляются.

На предыдущем main `c40` Fast и Standard push runs были FAILED:
[Fast](https://github.com/DenisKopylov/polisyos/actions/runs/37317558355),
[Standard](https://github.com/DenisKopylov/polisyos/actions/runs/37317558363).
Наблюдались schema/OpenAPI drift, docs freshness/import-policy, catalog-source,
coverage и directory-health ошибки. Это baseline observations, не результаты
нового кандидата и не P41 inherited verdict.

После main push на `1ddcd7b` наблюдаются новые exact-head runs:
[Fast](https://github.com/DenisKopylov/polisyos/actions/runs/37439934478) — FAILED,
[Canary](https://github.com/DenisKopylov/polisyos/actions/runs/37439934444) — FAILED;
[Standard](https://github.com/DenisKopylov/polisyos/actions/runs/37439934467) и
[Core release gate](https://github.com/DenisKopylov/polisyos/actions/runs/37439934469)
на момент snapshot ещё выполнялись. Это отдельные результаты опубликованного
checkpoint; их причина не объявляется inherited. Fast сообщил устаревшие
`feedback_solve_result.schema.json`/`_manifest.json`, 21 import-policy violation
и expired docs freshness baseline (10 observed / 0 expected); unit suite
после import gate не выполнялась. Canary остановился до scorecard: отсутствовал
требуемый short-lived service-principal token. Это недоступный run prerequisite,
не доказательство поведения продукта. Следующий docs/prompt push имеет
собственный HEAD и собственные CI results.

Исходный VM raw pack отсутствует; grade results остаётся
`transfer_and_navigation_only`. Organization DOCX не передан, поэтому его
независимый recomputation — UNRUN. DoWhy/EconML/Temporal и production-dependent
closures не установлены этим scoped прогоном. Production data остаётся локально
read-only; полного переноса в cloud и blanket data requirement нет.

## Остатки, передаваемые владельцам

Полная очередь остаётся в [closure-decisions](../closure-decisions/README.md).
Дополнительные конкретные discriminators следующей волны:

- F/ECO: для `[1e-12, 2e-12, 3e-12]` pairwise Gini равен `2/9`,
  прежний fixed-epsilon denominator даёт примерно `-1.33053836`.
  Dtype repair не доказал математическую корректность этой функции.
- F/LEX: повтор `legal,legal` не должен дважды считать один blocker;
  определить unique-plan admission и проверить настоящий report consumer.
- E/BKT: non-rejection `p>alpha` не доказывает bias equivalence или Grade A
  neutrality; purpose и meaningful-bias margin должны иметь владельца.

Каждое из этих наблюдений относится к реальному свойству, а не к новому
автоматически закрытому finding ID. Pattern pass: P01/P02, P04/P05,
P29/P32/P35/P37/P38/P40/P41; receipt acceptance, code acceptance и finding
closure остаются раздельными.
