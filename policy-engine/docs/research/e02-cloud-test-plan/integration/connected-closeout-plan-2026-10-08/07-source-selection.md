# Source selection перед следующей интеграцией

Каждый slice проверяется от **своего** published base, по immutable candidate/tree и committed receipt. Raw branch delta, inverse delta уже принятого source и code authorship — разные вещи. Число blobs в большой delivery не означает столько новых механизмов. G не cherry-pick/rebase/reset чужую history.

## Точные входы

Все полные SHA/tree и row-source paths — [inputs.json](inputs.json). A8b содержит G6f в ancestry; G ещё не содержит A8b. E8d является ancestor E7bf, F852 является ancestor G6f через ordinary merge99c7. B1e/a0 — fetched commits, topic остаётся53b; source runtime UNRUN. Croot переносит separate source DAGs; Dreceipt643 переносит freeze8e и несколько source-qualified executions.

| Механизм / range | Полный changed-path denominator | Смысл |
|---|---:|---|
| G6f → A8b, raw branch delta | 1 377 paths, в том числе31 production `.py`,59 tests,6 generated surfaces | Это composition footprint, не attribution ownership A. Latest tip docs-only не делает весь delta docs-only. |
| B prepared `2d3a990…→1e18a965…` | 52 paths;7 production `.py`,7 tests,3 source README,1 release среди direct18 | Остальное — evidence. Native/removal отсутствуют; 13 affected contours являются **названным scope**, не полным dynamic closure. |
| C stream `19807686…→81a4af1…` | 15 paths;3 production `.py`,3 tests,pyproject+lock,2 releases | Dependency lock и B pool/CAS inputs обязательно входят в selected composition. |
| C DFK `28b04149…→a13f6c1…` | 8 paths | Runtime retirement и обязательный census companion принимаются с отдельными verdicts; defective companion нельзя исключить из full-unit footprint. |
| C DFI `12190b1e…→ab441663…` | 30 paths;6 production `.py`,1 test,23 evidence | Same-ID profile currentness — original LA-041 defect class, не требование production corpus. |
| C CAT `ab441663…→8dfa7f3…` | 36 paths;14 production `.py`,6 tests и companions | CAT наследует DFI. Нельзя принять downstream history так, будто held upstream отсутствует. |
| C Legal `f428b…→c60e37e…` | 10 paths;4 production `.py`,1 test и companions | Его history несёт DFI→CAT; query-profile increment bounded, serving input отдельно. |
| D source `83e7c…→8e864f4…` | 3 540 paths;77 production `.py`,156 tests,61 release fragments,2 generated exports,2 tools | Полный branch-relative footprint включает много evidence и наследованных cross-owner paths; он не назначает все77 production files D. Latest receipt tail64355 включает771 paths и отдельные поздние tests/companions. |
| E source `df5258b7…→8d8e7b3…` | 7 paths;2 production `.py`,3 tests,source README,release | Source delta от предшествующего published E checkpoint. Receipt tail7bf direct меняет1 TSV; весь ancestor source от этого не исчезает. |
| F profile `2c095…→852cc370…` | 9 paths;2 production `.py`,4 tests и companions | Уже находится в G; повторный импорт или inverse diff не нужен. |

Эти избранные denominators относятся к конкретным source ranges, а не к сумме всей работы unit. Полный независимый range/companion census перечисляет16 ranges; retained complete output и hash — analysis receipt. Для review нового topic G снова читает актуальный полный footprint; эта таблица не future allowlist.

## B/D choices, которые нельзя решить «взять последний»

| Canonical owner path | D selected identity | Prepared/current B identity | Следующее решение |
|---|---|---|---|
| `scientist/orchestration/engine/executor.py` | `fe0aadf975873aa54d35008d5020b66c6c6778fa` | `5f71059129d195dd285ba3e9907dcb1b16bf18f6` | B owner сохраняет принятые G/V11 invariants при producer-scope/SKG delta; D reruns только affected context/history consumer. |
| `core/artifacts/store.py` | blob prefix `092ffe` | current B `02e325`, G `72127a` | B owner выбирает совместимую CAS verify/snapshot/view semantics; actual F query reader проверяется в Linux profile. Prefix — locator, полный blob recomputed from path@selected SHA перед admission. |
| `scientist/orchestration/llm/budget_enforcer.py` | `7105b2` | current B `70b606` | Явно сопоставить event/ack/pending/owner construction; A/D consumers получают тот же contract. |

Gateway decoder `0dc65ee8cbe6477c50deb965d4d7cc12b3f6c5a2`, ledger prefix`edc20a` и middleware prefix`596731` имеют выровненные selected inputs в проанализированных receipts. Это факт byte identity, а не разрешение переносить весь D10 wave на иной composed tree. Selected owners подтверждают full hashes и dependency closures перед новым acceptance.

## Mandatory companions и независимые evidence boundaries

- A DTO changes: OpenAPI, API client/types, dashboard types/validator и actual fresh reader. Old ab93 export rendering не квалифицирует A8b family.
- E Profile1/Profile2: generated schema snapshots/manifest, facade/public inventory и reference; graph facade/Methods README reconciliation canonical F owner. Four conflict paths наблюдались against99c7; он ancestorG6f, но current-base conflict state всё равно требуется recompute.
- C DFK: census tool/test, README/release и report. C CAN: adapter profile, raw Core emission decision и current installed consumer — разные properties.
- C stream: source/test/README/release **и** dependency lock. C DFI→CAT→Legal: upstream basis исправление + downstream delta refresh.
- D service/funnel: selected B CAS/budget/evaluator source, actual Node/history consumers и generated public projection. GP, origin projection, Node15 и D10 — отдельные scopes, не одна summed wave.
- F852: native/wheel evidence carry; exact rebuilt sdist и changed3.12 worker body UNRUN там, где требуется criterion. Graph guard fixes не закрывают B56 resource admission.

Первый merge attempt — в isolated review candidate; conflicts возвращаются canonical writers. Integration accepted commits добавляются последовательно и публикуются G. После изменения contract все actual affected reads учитываются, включая edges вне четырёх исторически declared. Full dynamic/external consumer denominator остаётся bounded, если он ещё не установлен; field/path count не заменяет semantic consumer.
