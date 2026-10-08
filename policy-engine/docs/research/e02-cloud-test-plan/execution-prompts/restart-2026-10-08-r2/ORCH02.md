# ORCH02 — own engineering repairs и G-compatible candidate

Продолжи ORCH02 на **существующей здоровой recovery cloud VM**. Старый `failed to query executor configuration capabilities` уже преодолён: proposals восстановлены, применены, проверены и опубликованы. Не повторять blob recovery,522-doc readback или completed native waves. Текущий остаток — собственные quality failures, выбор source/dependency composition и недоставленные consumers; новая машина эти остатки не решает.

PolicyOS E02 сейчас исполняется вертикальными механизмами. Ты coordinator четырёх изолированных writers: C05, C06-DFK, C06-CAN, C12; source пишет только соответствующий canonical writer. Независимые reviewers/testers прямые, без детей; источник и reviewer разных авторств. G принимает original completed candidate commits и отдельно adjudicates findings. Production corpus, private roots/digests и institutional authority остаются у local L01/L02. Работа на ограниченных portable fixtures разрешена сейчас.

## Точные входы и сохранение

Fetch `codex/e02-integration` и четыре own topics. Прочти из G полностью AGENTS/HANDOFF/CONTRIBUTING, `parallel-2026-10-08/{COMMON.md,dispatch.json,C05.md,C06.md,C12.md}`, этот r2 пакет. Полный actual final handoff:
`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/orch02-recovery-20261008/final-handoff.json@e2a737ffda0e3fc5b621e0ba539a0563fe151e1a`.
Путь preimage reconciliation рядом с ним; его24paths — own footprint, не полный consumer/dependency denominator.

| Writer | Own base | Frozen source | Published topic head |
|---|---|---|---|
| C05 | `8dfa7f3c544461c0ff081861848fcc5d8523da5b` | `66151f3b7c806fdd0af0e6b2f71762e4defcc023` | `2a7f9bf8f02aa8e751614f751b6d9ee2af2dfe5e` |
| C06-DFK | `a13f6c1acfe15a6750d71c6e86521f119d794def` | `cbbfffd367fe283813a8177575d26c0ede8d20c4` | `e4bd1527c941ff880a5d34898c57428c7be4b1cc` |
| C06-CAN | `f00dd7661a8d3329fb1fa1b049decb0d1d2f277b` | `4901e26841e2be0ae6ef393754abed5cafb1e2d4` | `6602fbd087ef31d3f8eff42e94fc1fc074326d45` |
| C12 | `c60e37e7833b2dbb22af1868e31dc3f519d6a4f2` | `192c8b935b824e2e4d38276f10d3061877207e9f` | `9c46da826c3d54b6d0a13cc1772bda4b2c646e68` |

Topics называются `codex/e02-C-orch02-{c05,c06-dfk,c06-can,c12}-recovery`; coordinator — `codex/e02-C-orch02-recovery-coordination`. Найди **существующие реальные directories** из predecessor admission receipts/actual Git worktree registry, проверь branch/HEAD/status и fresh resume admission на этом host. Не выводить filesystem path из имени branch. Healthy matching lanes reuse; known own pending delta сохранить. Unexpected branch/tree не reset/rebase/switch. Полные commits/source origins и prior publications остаются append-only.

Predecessor admitted paths: `/workspace/orch02-c05`, `/workspace/orch02-c06-dfk`, `/workspace/orch02-c06-can`, `/workspace/orch02-c12`; coordinator `/workspace/orch02-recovery`. Это snapshots, не гарантия присутствия на другом host. Missing matching lane после actual admission можно создать от её exact fetchable topic head; existing matching directory нельзя пересоздать или переключить.

G analysis source — `0321633c0e6d9a87bccfbbe889a4998934c52dd3`; `e01d15c71a46c129805ab8e9f5310b53cad6efdc` добавляет только L01/L02 metadata, product source тот же. Это **prospective reconciliation/verification base**, не приёмка старых own-base implementations. Если новый fetched G изменил реальные dependencies, сверить delta перед composition. C12 `77be→9c46` и coordinator `de1→e2` добавляют evidence/docs, source192 не меняется.

## Работа начать сейчас — четыре независимые очереди

### C05: устранить собственный красный и сохранить substance

На final source Ruff99 относится к **одному owned** `data_forge/domains/catalog/batch/core_sources/loaders.py`: F40141, ANN40131, TC00411, S6086, SIM1173, F8213, E5012, TC0011, RUF0341. Это не99 новых возможностей или доказанный inherited debt. `_ConnectorSessionCache` undefined и runtime-used imports под TYPE_CHECKING требуют настоящего binding/lifecycle repair. Dynamic SQL проверить по actual parameter/identifier contract; не suppress/noqa ради green. Использовать существующие connector/cache/profile mechanisms, не второй session store.

Сначала exact current source lint + scoped mypy с complete outputs. Mypy binding summary14 расходится с соседним output19; выбрать actual command/candidate/path/profile и прочитать весь output. Missing dependency stubs отделить от object-callable/undefined/export/generic-type source errors; не убрать strict flags, не массово заменить typed contracts на Any или ignore. Existing source scopes включают loaders, common `generation_basis.py`, catalog, `fabric/retrieval/service.py` и pipeline manifests; physical tests C05 — `test_dfi_03.py` и `test_dfk_02.py`. Whole-library cleanup вне blast radius не нужен, но runtime name defect в owned loader нельзя экспортировать как tooling.

После source repair: freeze → independent review → affected tests реального loader/session/retrieval/warm caches и profile/content currentness; same-ID mutation, unchanged positive, missing/foreign profile, legacy empty-plan mode, matched property removal.112старых PASS остаются source661-qualified. Проконтролировать, что WVS hot-loop regression не возвращён style/type исправлением. HTTP headers/credentials/corpus revision/concurrent atomic snapshots остаются объявленной исходной bounded scope, если original criterion не требует большего.

### C06-DFK: подготовить настоящую current-source composition

31tests,20real-Git cases,13650selected text paths и отдельные installed9/9 уже выполнены на cbb. Не повторять долгий census на неизменённых inputs ради занятости. На prospective G надо reconcile parser **и** его admitted lifecycle/canonical tool identity: в G выбранный old-base `schema_fqn_census.py` отсутствует. Absence сама по себе не доказывает retirement; изучить canonical retirement/CLI/manifest records. Не воскресить retired schema/codegen family. Если существующий current census owner есть — предложить перенос generic Git two-path parsing туда; если capability пока не admitted — доставить полный bounded existing-tool adoption candidate с explicit public/retirement obligations.

Сохранить staged rename versus unstaged Y=R/intention-to-add различие, missing selected tracked path refusal и полный Git-visible denominator. `_01` physical writer C06, `_02` C05: после composition выполнить их affected family вместе, не конкурировать за файлы. No-src import check остаётся SKIP, не package import PASS. External/binary/ignored/historical/computed callers absence не утверждать.

### C06-CAN: проверить reader на G и выдать конечную compatibility matrix

Три existing reader/test/docs preimages совпадают с G; new release fragment отсутствует в G. Это самый короткий первый G-based reader candidate, **не automatic acceptance** и не permission импортировать old writer overlay.95native/36wheel/36rebuilt-wheel относятся к source490 и своему885-origin dependency contour, где есть older identifiability supplier; до G composed PASS сверить полные origins.

Read-only реальные current producer/default `put_json` + reader consumers доступны немедленно. Матрица: default current artifact, profile-less historical artifact, nondefault Core/options, Core-only tag-set, raw-Core bypass, missing/mismatch/fake profile. Для каждого exact bytes→actual fresh reader→typed result и minimal required rule/version. Reader изменять только в существующем lease; Core store/adapter/defaults — C02/G. До ratified compatibility evidence сохранять strict reject/declared limitation, не invent default profile или silent fallback. Если default producer не читается own reader — это actionable producer/consumer seam, доставить exact test/property/patch proposal соответствующему writer, не требование полного freeze.

### C12: current typing, real request intent и consumer handshake

Fresh Ruff final привязан к192 и PASS; mypy receipt относится к **677 до финального style/source commit**, поэтому14не финальный source результат. Повторить exact two-file gate на192. Owned `lex/knowledge/store.py` failures: object iteration/Any return, undefined `epoch_contract.LegalAmendmentWindow*`, optional tuple indexing, generic tuples, float/string и int(object). Типы/импорты исправить по настоящему existing epoch/window/store contract, без duplicate DTO или guessed annotation. HNSW optional stub problem записать tooling отдельно; supported locked environment provision разрешён без общих lockfile changes.

36старых PASS не доказывают served mapping. Portable path: immutable requested generation/model/profile → existing encoded query → reopened persisted fresh reader; missing/stale/mixed generation отказ **до encoder/index**, guard-removal вызывает настоящие consumers и FAIL. Same assets/hash с подменённым callable остаётся declared residual, не endless repair ladder.

Для C10/A сформировать готовый exact integration packet: public callable/typed input/output, required encoder provenance, generation/model/member/profile identity, minimal actual caller delta, response/negative selectors. Сопоставить его с новым **fetchable** C10 recovery handoff, если появился; новый supplier source не принимать по summary. C12 не пишет A lifecycle, Core DTO, `lex_pipeline` или общие API/generated paths. Portable generic consumer/packet и own typing не ждут L01 production corpus либо общей G приёмки. Authentic production vector positive — L02 только после минимального matching tuple.

## Как reconcile с G без ещё одного круга вопросов

G разрешает writers **подготовить и проверить G-compatible proposals в собственных scopes сейчас**. Это инженерный выбор prospective base, без formal/source acceptance. Canonical author строит pathwise reconciliation и сохраняет все G foreign hunks/old topic history; не переносит целые unrelated old branch snapshots и не заменяет current files blindly postimages. Нужные upstream DFI→CAT→Legal commits/contract bytes pin отдельно: CAT alone не доказывает DFI currentness. Complete preimage matrix: C05 восемь existing differences+дваnew, DFK три differences+одинnew, CAN ноль existing differences+одинnew, C12 четыре differences+дваnew.

Если existing own lane удобно продвигается обычным безопасным merge — сверить полный actual delta и все conflicts по owners. Если для honest G-based port нужна отдельная isolation, создать её **один раз после read-only actual admission**, сохранив старую lane/topic/receipts; author переподготавливает собственный delta с полной before/after reconciliation и new freeze. Не switch/reset/rebase старую worktree, не force/cherry-pick, не выдавать old own-base PASS за G-result. Source ancestry/input manifest должен показать весь выбранный DAG и любое отличие supplier, даже если вне непосредственных changed paths. Foreign conflict оформляется exact owner packet, остальные ready tasks продолжаются.

Global engineering red: C05 partial nongenerated architecture; C06 full architecture; C12 full architecture required generated families completed с OpenAPI/other drift. Own illegal imports исправить через canonical public API в своих paths. Global baseline/policy/lock/generated writer G; required public API extension — exact companion proposal. Не менять policy/baseline/expiry, чтобы спрятать finding. P41 only exact slice-base replay + full-denominator zero overlap; иначе not_established. Standalone Atlas/optional families не входят в доказанный default result.

Invocation scanner: C05/C12 exit3 UNRESOLVED — partial static model, не доказанный runtime bug; C06 exit0 — тоже partial static model. Сначала классифицировать existing exact unresolved caller sites и исполнимые call/negative witnesses; не повторять170MB census без изменённого input. A real dynamic invocation positive доказывает только свою конкретную boundary. Broad portable replay C13 ждёт selected G freeze; own focused compile/type/reader/negative не ждут его.

## Завершение и заранее известные fallback

- Reuse current VM, actual profiles/origins фиксировать. Missing executable/stub/backend — точный scoped ERROR/SKIP/UNRUN; lawful pinned provisioning выполнить, если оно делает check исполнимым. Python/Node deviations не скрывать; for TypeScript scanner сначала `corepack pnpm install --frozen-lockfile` по supported recipe. No artificial cloud compute quota; serialize только shared mutable DB/cache/index/port/artifact.
- Required native hook red — полный traceback/input/cwd/candidate packet, диагностика уровня caller/source/issuer; [G-DEVX.md](G-DEVX.md) объясняет known root convention и unresolved gates. Не переносить cloud ORCH03 blocker автоматически на здоровые ORCH02 lanes. Hooks/authority не обходить, baseline не «обновлять» до прохода.
- Нет minimal external tuple — ограничить только соответствующий authentic positive. Portable repair, negative, source reconciliation и готовый caller handoff продолжать. Не возвращаться с вопросом о уже выданном owned path/fixture или требованием «принять всё G».
- Independent final review → ordinary implementation commit → отдельный exact-source handoff → own-topic normal push/remote readback. Полные deciding outputs/removals умеренного размера, raw ignored; tracked source snapshots не копировать в receipt. Closure proposals/source admission/formal closure отдельны. Main/integration не публиковать, production data не переносить.

Ожидаемая доставка: исправленный typed C05 и C12 source, ready G-compatible DFK/CAN candidates, finite CAN compatibility/caller decisions, actual C12 consumer handoff, truthful architecture/invocation residuals. Простого повторного ledger недостаточно. Неизвестные authority facts сохранить честно; не изобретать law/currentness ради законченного отчёта.
