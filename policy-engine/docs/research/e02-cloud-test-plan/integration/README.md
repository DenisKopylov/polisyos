# Непрерывная интеграция E02

Current continuation checkpoint: [checkpoint-09](checkpoint-09.json), with
[second-wave accepted code and owner actions](reviews/2026-10-06-second-wave.md).
Source312 has58 passing affected-consumer cases; broad E02 freeze/replay remains pending.

G ведёт `codex/e02-integration` от опубликованного `origin/main`:
`c40d4acae1ce58b597267255026d9356565828fd`, tree
`897662caf73bd4487f798d66938b74d7abfe753e`. Этот checkpoint фиксирует входы
и подготовку приёмки. Решения фиксируются в [checkpoint-07](checkpoint-07.json)
и [independent review](reviews/2026-10-05-first-pass.md). Новых finding closure
decisions пока нет. Исследовательский source `6978076…` не является новым
кандидатом. Протокол исполнения — [HANDOFF](../execution-prompts/HANDOFF.md).

G-local provenance: ссылки в этом integration record на ignored `_build/**` outputs или абсолютные workspace paths относятся только к исторической локальной среде G. Их bytes не входят в Git и недоступны в cloud checkout; содержимое там `not_established`. Это не remote dependency. Сохраняйте `path@sha256`; если отсутствующий artifact станет решающим, повторите точную проверку на candidate.

## Проверка входов

[Startup receipt](startup.json) сохраняет свежий `import_results.py --check`,
полные outputs двух corruption controls и восстановленной копии. Importer
прошёл на опубликованной базе; изменение `PASS` на `FAILED` в первом
совпадении `cells.tsv` и добавление bytes к `received/F01.txt` отвергнуты.
После восстановления копии проверка снова прошла. Это проверка transferred
text и index binding; product closure и VM receipt custody остаются
`not_established`.

Полный denominator `results/cells.tsv` — Python test file × source-cut:
2 074 строки (1 673 PASS, 307 FAILED, 88 ERROR, 5 COLLECTION_SKIP,
1 COLLECTION_ERROR). Query `--failures-only --limit 30` имеет 401 совпадение;
лимит показа не задаёт множество и не определяет владельцев. Владельцы
берутся из [bundle owners](../execution-organization/bundle-owners.tsv) и
[finding owners](../execution-organization/finding-owners.tsv).
Для transferred source pack F01–F15 получены reports о полном чтении пяти
раздельных helper-партиций. Эти reports служат intake-навигацией; scientific
predicates проверяются по source bytes, коду и deciding outputs.

## Состояние рабочей среды

Новый checkout создан native worktree tool и прикреплён к этому чату. G
именовал ветку на том же base. Дополнительное правило workspace admission
было обнаружено в опубликованном `AGENTS.md` после создания checkout.
Retrospective resume-проверка точных branch/path вернула `UNRUN`, exit 2:
старая регистрация
`/Users/deniskopylov/.codex/scratch/p41-r13d-slice-base-2522-20260926/polisyos`
недоступна. Это исторический результат в startup receipt. Исследование
установило dangling symlink к отсутствующему именованному checkout в Trash.
G переместил только symlink в reversible quarantine. Независимый readback
нашёл Git admin record, index и HEAD log; их до/после byte equality не
установлена. Повторный admission вернул `admitted`,
exit 0. [Operations receipt](operations.json) связывает exact selectors,
решение, полный локальный output и границы наблюдения. Бывшие checkout bytes
и dirty state не восстановлены; перечисление Trash недоступно.

Свежий `corepack pnpm install --frozen-lockfile` и live remote readback
записаны в operations receipt. На момент readback опубликован base `c40d4aca…`;
startup commit ещё локальный. Наличие dependencies само по себе не доказывает
typecheck; hook skip не используется как PASS.

## Приёмка поступающих slices

Git — обязательный канал. G fetch-ит exact topic/PR head, читает committed
`implementation-handoffs/<unit>/<slice>.json`, связывает slice base,
implementation commits, candidate tree и полный diff с tests/companions.
Первые fetched B/D receipts проверяются по immutable candidates: B RUN,
D baseline map, RL checkpoint, transfer generation и GP witness. До
завершения independent checks они остаются очередью. E FRC и D funnel
изменения обнаружены; на первом fetched head committed handoff отсутствовал.

В независимую очередь идут отдельные вопросы:

| Вопрос | Сигнал приёмки |
| --- | --- |
| Ancestry, receipt, input identity | Git/content binding независимо пересчитан; deciding bytes доступны |
| Owner, diff, companions | Канонический writer и весь footprint сверены с критерием |
| Runtime property | Реальный producer → persisted artifact/event → bridge → consumer |
| Oracle и adversarial discriminator | Независимый expected result и proxy-divergent negative control |
| Consumer, API, surface | Readback, status/authority/time/provenance не теряются на границе |
| Outputs и limitations | Полные deciding outputs, точный scope, skipped backends и следующий owner |

Review выполняется на immutable SHA/tree. Автор не является независимым
reviewer своего кода. Helpers не пишут в integration branch и не делегируют.
G добавляет только принятые commits последовательно и append-only, сохраняя
upstream history. Конфликт возвращается canonical owner. Новый head требует
delta review, dependency reconciliation и свежего affected evidence.

Code acceptance и finding closure записываются отдельно. Неустановленные
predicates (`consumer_asserted`, `institutionally_supplied`, `not_established`)
не включают authority gate. Inherited red требует exact-command replay на
slice-base и полного disjointness proof; пока это не выполнено, источник
красного — `not_established`.

## Зависимости и вычисления

Четыре declared edges из organisation plan исследуются отдельно:
`CYC-01→FRC-01`, `EMP-01→FRC-02`, `CYC-02→RES-03`, `NET-01→ING-02`.
Общие writers: A — `runtime/quality/generation_cycle.py` и HTTP
`run_lifecycle.py`; C — `fabric/data_plane/streaming.py`. Supplier передаёт
contract/artifact и discriminator; consumer bridge меняет его owner.
CAS/schema/history/UQ/graph consumers получают targeted recheck после
изменения соответствующего upstream contract.

Локальные A/C/G делят один тяжёлый numerical/data slot и начинают с одного
численного потока. DB, fixed port, mutable scratch/cache и governed artifact
writer сериализуются отдельно. Лёгкие checks и reviews идут параллельно.
На B/D/E/F cloud VM этот лимит не переносится. Production inputs остаются
локальными и read-only; полный dataset требуется только по самому criterion.

Broad backend/CI/replay wave и data-dependent closeout ещё не запускались:
они выполняются один раз после source freeze и завершения reviews. До freeze
применяются defining-property, negative и affected consumer checks.
DoWhy/EconML/Temporal или другие недоступные backends записываются как
SKIP/UNRUN с границей вывода. Push в `main` требует новой явной авторизации.

## Pattern pass

P01/P02/P03: принимать demonstrated chain и surface, сохранять точную
missing-capability label. P05/P09/P15: не повышать diagnostic/LLM/package
результат до authority. P27/P31: canonical writer и общий invariant.
P29/P32/P33/P37/P38: runtime property, content binding, independent oracle
и falsify-the-declaration controls. P35: полный source/path denominator.
P40: второй escape того же класса требует расширения механизма либо
declared bounded residual с falsifier. P41: красный атрибутируется только
на slice-base. Существующие риски — отсутствующие VM deciding bytes,
незамкнутые served producers и held public-IR decisions. Workspace admission
теперь установлен для точной G пары. Acceptance signal — проверенный slice и consumed
artifact/readback, не число jobs или цвет baseline.

Текущие адресные HOLD, dependency interlocks и consumer rechecks перечислены в
[owner actions](reviews/2026-10-05-owner-actions.md). Checkpoint-06 добавляет
economic dtype, Lex input/plan binding, bias statistical support, forecast
producer, Morris geometry и CAL-05 mapped-schedule refusal к ранее принятым
code slices. Finding closure не заявлена. Cal/UQ, streaming и cold budget
mutation сохраняют HOLD по независимым локальным falsifiers; runner exit 0
этих probes не является product PASS. Checkpoint-07 принимает ограниченный Core-to-IR adapter profile; 52 адресных случая, paired readback и два wrapped backtest consumer прошли на source 97c85fae. SAE bundle-route не дошёл до route из-за недоступного catalog input и не проверяет adapter branch (persist_artifacts=false); inline persistence route остаётся UNRUN. Прямые Core writers и полный CAN-01 closure остаются остатками.

[Recovered work](reviews/2026-10-05-recovered-work.md) определяет полезные
адаптации из retired checkout'ов и отличает их от устаревших/небезопасных
черновиков. Код сохранён в Git; промежуточные рабочие пространства перенесены
в Finder Trash. Production inputs остаются на исходном локальном месте.

## Следующая волна E02

[Шесть готовых промптов продолжения A–F](../execution-prompts/continuation-2026-10-06/README.md) доступны в опубликованной main-базе.
[Publication record](../integration/publication-2026-10-06.md) фиксирует checks и ограничения этой публикации.


[Пакет решений A–F](../closure-decisions/README.md) сопоставляет все 127 bundles
и 282 findings с конкретными следующими задачами, выбранными методами,
межгрупповыми контрактами и независимой приёмкой. Он анализирует source G97
и отдельно закреплённые owner heads; новых finding closures не заявляет.
Это исследовательский handoff для реализации полного критерия после bounded
checkpoints, а не дополнительный runtime replay.

## Continuation checkpoint, 2026-10-06

[Checkpoint-08](checkpoint-08.json) accepts the bounded direct CAS put regression.
[Current intake and owner actions](reviews/2026-10-06-first-wave.md) record exact
receipts, independent checks, held admissions and follow-up consumers.
No new finding closure or future main publication is authorized.
