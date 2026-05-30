---
title: Universal Policy Design Case Deep Research Reports 105-146 Combined
status: raw-research-ledger
owner: team-policy-design-research
created: 2026-05-21
updated: 2026-05-22
source_scope: deep-research-report-105..146
normalized_synthesis: ../../backlog/universal-policy-design-case-research-results-consolidation.md
research_plan: ../../plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md
implementation_plan: ../../plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md
source_ownership: ../../reference/policy-design-case-source-ownership.md
---

# Capability baseline for universal policy design case in PolicyOS

Ownership note: this file is the repo-owned raw research ledger for the
universal Policy Design Case stream. It preserves historical report text and
source-detail citations. The normalized implementation authority starts in
`docs/backlog/universal-policy-design-case-research-results-consolidation.md`,
with source ownership governed by
`docs/reference/policy-design-case-source-ownership.md`.

## Входная рамка и главный вывод

Я не смог надежно открыть именно файл `policy-engine/docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md` в выбранной ветке `main`, поэтому ниже даю baseline-исследование C0, опираясь на ваш процитированный фрагмент задачи и на ближайшие канонические артефакты репозитория: `architecture/policy_design_case/capability_reuse_map.json`, `src/polisyos/runtime/quality/policy_design_case.py`, пакетные контракты в `architecture/packages/*.toml`, реестр шинов `architecture/shims.toml`, а также текущие runtime/scientist/fabric/lex/scholar/data_forge/core surfaces. 

Главный вывод такой: **PolicyOS уже не является “пустым листом” для Policy Design Case**. Репозиторий явно фиксирует, что новая универсальная Policy Design Case должна строиться преимущественно через reuse existing capabilities, а не через новую параллельную подсистему. В reuse map перечислены **27 target capabilities**, из которых **18 = wire-existing**, **7 = extend-existing**, **1 = consolidate-existing**, и только **1 = build-new**. Это практически полностью удовлетворяет духу acceptance-критерия C0: позже нельзя вводить новый “канонический объект”, не назвав, что именно он reuse/extend/consolidate/replace, потому что такой реестр уже есть. fileciteturn75file0

Одновременно baseline показывает и вторую, не менее важную вещь: **канонические пакеты и границы уже описаны, но почти весь package-contract слой пока находится в режиме `contract_status = "draft"` и `gate_mode = "report_only"`**. Это верно для `runtime`, `scientist`, `fabric`, `foundry`, `lex`, `scholar`, `data_forge`, `ir`, `ddm`, `berl`, `calibration` и `core`. Иными словами, архитектурный канон уже задан, но не весь он переведен в fail-closed orchestration на уровне package governance. fileciteturn78file0turn79file0turn80file0turn81file0turn82file0turn83file0turn84file0turn85file0turn86file0turn87file0turn88file0turn89file0

## Что уже является каноном

Канонические модульные корни для этой темы уже заданы в package contracts. Для C0 это означает, что ссылки в будущих исследованиях нужно делать прежде всего на canonical paths, а не на старые корни или удобные фасады. Для общего контура это: `polisyos.runtime`, `polisyos.scientist`, `polisyos.fabric`, `polisyos.foundry`, `polisyos.lex`, `polisyos.scholar`, `polisyos.data_forge`, `polisyos.ir`, `polisyos.core`, плюс внутренние тематические подкорни, перечисленные в manifests. Особенно важно, что `scientist` уже объявляет канонические first-level roots для `evidence`, `governance`, `methods`, `orchestration`, `policy_design`, `publishing`, `replay`, `validation`, а package contract прямо называет compatibility roots, которые нельзя путать с каноном. fileciteturn79file0turn88file0turn89file0

Для самой Policy Design Case самым сильным каноническим якорем сейчас является `src/polisyos/runtime/quality/policy_design_case.py`. Этот модуль прямо объявляет, что registry — это **runtime-readable contract** для minimum record families, причем он **не делает будущие producer evidences автоматически passing**, а лишь называет owner, schema, reader gate, readiness hook и enforcement function, которые должны либо блокировать, либо объяснять состояние до тех пор, пока owning producer не начнет эмитить runtime evidence. Это очень важный C0-факт: **case layer уже существует как canonical registry and validation surface, но еще не равна полной producer reality**. fileciteturn49file0

Тот же модуль задает canonical minimum corpus of facets через **19 minimum record families**, включая `intent_authoring_and_capture_risk.v1`, `concept_and_jurisdiction_spine.v1`, `legal_authority_and_competence.v1`, `data_source_semantic_lineage.v1`, `scholar_academic_evidence.v1`, `method_selection_and_validity.v1`, `claim_argument_evidence_case.v1`, `human_oversight_independence_and_review.v1`, `lifecycle_ex_post_and_calibration.v1`, `publication_trust_and_external_governance.v1` и `formal_substrate_invariant_spec.v1`. Для C0 это фактически уже готовый facet-saturation frame: исследование не должно изобретать новый перечень базовых семейств записей. fileciteturn49file0

Дополнительно, `capability_reuse_map.json` уже превращает системный дизайн в правило исследования: почти каждая целевая capability привязана к конкретным существующим surfaces. Например, runtime assurance case должен reuse/extend `runtime/quality/*`; policy design intent/objective/critique — `scientist/policy_design/*`; concept/jurisdiction spine — `fabric/entity_resolution`, `scientist/cross_graph`, `ir/linker`, `ir/world`; legal authority — `lex/knowledge`, `lex/legal_evaluation`, `lex/normpack`; academic evidence — `scholar/*`; audit/export — `core/audit/*`; lifecycle — `scientist/governance/continuous/*`; calibration — `calibration/*` и backtesting; drift/degradation — `ddm/*`. Это и есть тот “reuse ledger”, которого требует acceptance C0. fileciteturn75file0turn76file0

## Что реально реализовано, что только проецируется, и что остаётся greenfield

Если перевести репозиторий в термины C0-классификации, картина выглядит так.

**Как implemented или почти certainly implemented** выглядят те поверхности, у которых есть одновременно package contract, runtime/readable contract и конкретная исполняемая логика. Сюда относятся: runtime schema compatibility (`schema_compat.py` с полной decision taxonomy и gate semantics), Policy Design Case registry/coverage validators (`policy_design_case.py`), projection/public export boundary (`projection_semantics.py`, `public_export.py`, dashboard validators), Fabric bitemporal time travel и retained snapshots, Lex NormPack assembly для `jurisdiction`/`as_of`, Scholar freshness policy, DecisionGradeExport compiler, Data Forge read API facade и Core audit bundle/verifier. Эти поверхности не просто типизированы — они уже содержат валидаторы, decision codes, runtime payload shapes и/или export logic. fileciteturn46file0turn49file0turn41file0turn42file0turn68file0turn55file0turn58file0turn62file0turn72file0turn66file0turn74file0

**Как implemented_but_not_orchestrated или partially implemented** выглядит сама универсальная Policy Design Case как end-to-end product object. Это видно из двух мест сразу. Во-первых, `policy_design_case.py` требует concrete runtime `record_families` и `records`, а не разрешает подменять их голым `status=pass`; отсутствие concrete runtime rows является fail condition. Во-вторых, reuse map почти везде говорит не “build new”, а “wire-existing” или “extend-existing”: то есть underlying capabilities уже есть, но их нужно собрать в case-level record families, projections, ledgers и authorities. Иначе говоря, **subsystems mostly exist; fully orchestrated universal case does not yet exist as compiled first-class object**. fileciteturn49file0turn75file0turn76file0

**Как projection_only** уже явно ведут себя operator-facing проекции. Dashboard validators пропускают `policy_design_case_projection` через fail-closed normalizer, а runtime contracts различают `OperatorProjectionAuthority = "runtime_authority" | "projection_only"` и набор projection states (`draft`, `projection_only`, `redacted`, `stale`, `contested`, `blocked`, `approved`, `publishable` и др.). Значит, в baseline нельзя считать dashboard/object view эквивалентом authority-bearing runtime fact: часть поверхности уже спроектирована именно как projection, а не как canonical authority source. fileciteturn53file0turn68file0

**Как compatibility_shim** репозиторий маркирует довольно большой набор старых путей. Самый очевидный пример — `scientist`: package contract прямо указывает compatibility shim roots вроде `scientist/claims`, `scientist/orchestrator`, `scientist/research_dag`, `scientist/continuous_governance`, `scientist/human_review`, `scientist/policy_verified`, `scientist/verification` и др., при том что active implementation должна жить под `evidence`, `orchestration`, `methods`, `governance` и `validation`. Отдельный shim registry в `architecture/shims.toml` фиксирует move-with-reexport decisions, owners и sunset dates для старых корней вроде `scientist/publisher.py -> scientist/publishing/publisher.py`, `scientist/replay_backend.py -> scientist/replay/backend.py`, а также для ряда Fabric shell paths. Reuse map дополнительно говорит, что `ddm_15_7` — это compatibility shim, а не canonical owner, и что некоторые Foundry root surfaces (`conflict_checker`, `social_weights`) — публичные шины поверх канонических backing modules. fileciteturn79file0turn77file0turn76file0

**Как greenfield** в исследовательском смысле остается по сути одна capability: `formal_substrate_invariant_specification`. Reuse map прямо помечает ее как `build-new` и поясняет, что существующие honest-diagnostics tests и validation tools доказывают runtime behavior, но не дают lightweight formal/model specs для closeout-critical state-machine invariants. Это и есть самый чистый greenfield в C0. fileciteturn76file0

Практически это означает следующее: **в `capability-baseline-map.md` стоит различать не “реализовано/не реализовано”, а минимум шесть состояний** — implemented, partially implemented, implemented_but_not_orchestrated, projection_only, compatibility_shim, greenfield. Для Policy Design Case это важнее, чем бинарная оценка, потому что большая часть подложки уже есть, но не вся она имеет одинаковую authority depth. fileciteturn49file0turn75file0turn76file0turn77file0

## Схемы, миграции и временная семантика

### Схемы и решения совместимости

`src/polisyos/runtime/quality/schema_compat.py` уже задает зрелую decision taxonomy для schema compatibility: `compatible`, `compatible_with_migration`, `legacy_quarantined`, `unknown_schema_blocked`, `incompatible_blocked`, `stale_schema_blocked`. Там же определены production-closeout blocking decisions, required readers (`scorecard`, `readiness`, `bundle_assembler`, `dashboard_projection`, `approval_packet_builder`) и строгая логика для migration-required payloads, включая source/target payload identity, semantic-loss checks и required semantic fields. Для C0 это означает, что универсальная Policy Design Case уже должна встраиваться в существующий dialect runtime schema compatibility, а не придумывать собственный. fileciteturn46file0

`ops/migrations/README.md` фиксирует ровно те migration classes, которые и просили в C0: `db/`, `runtime_state/`, `api_schemas/`, `ir/`. README прямо говорит, что это release-facing contract root для **DB schema, runtime-state schema, API schema и IR schema migrations**, а operator-visible migration family обязана быть объявлена здесь до release promotion. Это важный baseline-факт: migration dialect в репозитории централизован, а не размазан по отдельным пакетам. fileciteturn67file0

Data Forge уже дополнительно заявляет свой собственный слой эволюции: `polisyos.data_forge` лениво экспортирует build-time contracts для asset identity, schema registry access, snapshot transactions, quality checks и **golden/differential migration tests**, а runtime consumers должны использовать только `read_api`. Значит, для C0 нужно различать по крайней мере три независимых dialect family: runtime-quality schema compatibility, ops/release migrations, и Data Forge build-time schema/snapshot/migration contracts. fileciteturn66file0turn84file0

### Временная семантика

Runtime canonical `TemporalScope` уже типизирован: `valid_at`, `tx_at`, `branch`, `snapshot_id`, `scenario_id`. Отдельный `TemporalRef` тоже носит `valid_at`, `tx_at`, `snapshot_id`, `branch`, `scenario_id` как часть decision-bearing values. Следовательно, для runtime C0 baseline должна использовать именно bitemporal/snapshot vocabulary, а не абстрактное “as of”. fileciteturn53file0

Fabric time-travel документация делает это еще конкретнее. Point-in-time reads проходят через `as_of_tx_time`, `as_of_valid_time` и snapshot context (`snapshot_root` / `snapshot_id` / `branch`). Документ прямо говорит, что query of projection tables fail-closed без retained snapshot context, что corrections/revocations обрабатываются append-only через `tx_at`/`valid_at`, а bitemporal semantics закреплены в world snapshots, governed branches и query APIs. Это и есть canonical baseline для Fabric bitemporality и replay/time-travel semantics. fileciteturn55file0

Lex уже использует собственную временную рамку: `polisyos.lex.normpack` собирает NormPack для `jurisdiction` и `as_of`, а applicability windows вычисляются по validity intervals claims. Для C0 это значит, что legal time semantics уже не абстрактная — она выражена через `as_of` и claim validity windows, и universal Policy Design Case должна привязывать legal authority именно к этим surface contracts. fileciteturn58file0

Scholar использует еще один distinct time dialect: freshness metadata строится вокруг `source_freshness_at`, `created_at`, staleness/expiry thresholds и cooldown windows. В коде уже есть domain-specific thresholds, freshness statuses и refresh policy. Иными словами, academic freshness — это не Fabric tx/valid time и не Lex `as_of`; это отдельная freshness time family, которую baseline должен учитывать как самостоятельную. fileciteturn62file0

По части остальных temporal semantics картина смешанная. Data Forge README подтверждает наличие snapshot transactions и read_api, но в этой выборке я не извлек единый canonical contract для “snapshot/release time” с точностью до конкретных полей. Аналогично, для DDM detection time, claim-registry time, model time и replay time в этом проходе есть косвенные якоря — DDM как canonical package, research DAG replay как существующая surface, public replay export в decision-grade compiler — но не один извлеченный файл, который можно считать окончательной таблицей соответствий. Это нужно явно добрать в финальной версии `capability-baseline-map.md`. fileciteturn84file0turn85file0turn72file0

## Публичные поверхности и глубина типов

Снаружи репозиторий уже имеет несколько важных public/export surfaces разной зрелости. Во-первых, есть **generated API client types**: `packages/runtime-api-client/runtimeApiClient.ts` помечен как generated file из `schemas/runtime_api_v1.openapi.json`. Это означает, что потребительская типовая поверхность уже не “ручная” и может использоваться как canonical export shape для runtime-facing DTOs. fileciteturn69file0

Во-вторых, dashboard layer уже hardens public consumption через `apps/runtime-dashboard/src/api/validators.ts`. Там есть zod schemas для `ApiMeta`, `TemporalScope`, temporal event points/capabilities, operator diagnostics и — критично для вашей темы — для `policy_design_case_projection`, который нормализуется fail-closed. Значит, user-facing shape уже типизирована и валидируется отдельно от backend contracts; для C0 это надо записать как самостоятельную public surface со своей глубиной типа и своим fail-closed behavior. fileciteturn68file0

В-третьих, runtime-quality public export уже существует как самостоятельный authority boundary. Наряду с `projection_semantics.py` и `public_export.py`, это формирует слой, который отделяет runtime-authoritative state от projection-only/operator-facing material. Этот слой нельзя сводить к “просто сериализации”: в нем уже зашиты gate semantics, masking/redaction rules и export eligibility. fileciteturn41file0turn42file0turn53file0

В-четвертых, для publication уже есть очень сильный typed export surface — `DecisionGradeExport`. Он имеет schema version `1.0`, обязательные поля `run_id`, `audience`, `claims_ref`, `research_dag_ref`, `payload`, `omissions`, и компилируется из одного и того же claim ledger и research DAG в audience-specific tiers (`public`, `reviewer`, `expert`, `machine`). Код также запрещает silently omitting blocked claims и накладывает дополнительные ограничения на public exports. Для C0 это один из лучших уже реализованных примеров “public/export shape with authority-aware omission policy”. fileciteturn72file0

В-пятых, есть **audit verifier surface** в `polisyos.core.audit`: portable `.polisyos-audit.tar.gz` bundles, offline verification, provenance/signature/SLSA/SBOM handling и standalone verifier template. Это не просто внутренний utility; README прямо называет его boundary function для external review и reproducible verification. Если будущая universal Policy Design Case претендует на public trust/external governance, то именно этот канон должен использоваться для evidence portability и external verification. fileciteturn74file0

## Каркас корпуса кейсов для C0

Полного corpus guide этот проход еще не дает, но репозиторий уже показывает, **какие именно артефакты разумно считаться corpus anchors**, и этого достаточно для первого baseline-слоя.

Для **facet saturation** самый надежный якорь уже есть: 19 minimum Policy Design Case record families в `policy_design_case.py`. Именно они должны стать skeleton-индексом корпуса, иначе исследование рискует насытить одни линии доказательства и пропустить другие. fileciteturn49file0

Для **deep pilot** и минимального end-to-end scenario в репозитории уже видны walking-skeleton и operator-triage anchors: есть validator `check_policy_design_case_walking_skeleton.py` и runbook `policy-design-case-operator-triage.md`. Это сильный сигнал, что corpus не нужно строить с нуля; его стоит начать с walking skeleton case и операторского triage path как с минимального “serious” пилота. fileciteturn45file38turn73file19

Для **historical failures** и fail-mode corpus уже есть подходящие источники: `production-data-e2e-diagnostic-backlog.md`, honest-diagnostics runbook, schema compatibility decision taxonomy, registry issue taxonomy и operator triage path. Иными словами, failure corpus можно строить не только по “плохим кейсам решения”, но и по существующим blocking codes, incident backlogs и substrate diagnostics. fileciteturn45file27turn48file0turn46file0turn49file0turn73file19

Для **contested / tradeoff / participation cases** хорошими якорями являются уже существующие policy-design and governance surfaces. Reuse map прямо связывает pre-publication adversarial challenge с `scientist/policy_design/adversary.py`, `critic.py`, `objectives.py`, а human oversight and VOI escalation — с `scientist/governance/human_review/*`. Это означает, что contested/tradeoff corpus не надо отдельно “изобретать”: он должен быть собран из objective/critique/adversary traces плюс review packets и dissent/review outcomes. fileciteturn75file0turn76file0turn79file0

Для **longitudinal calibration cases** база тоже есть: reuse map уже привязывает calibration/ex-post validation к `polisyos.calibration`, Scientist calibration surfaces и backtesting, а drift/degradation monitoring — к canonical `polisyos.ddm`. Следовательно, longitudinal corpus следует строить вокруг calibration bundles, backtests, validity/reissue/withdrawal events и DDM degradation signals, а не вокруг разрозненных ad hoc datasets. fileciteturn76file0turn85file0turn87file0

Самый практичный вывод для `annotation/corpus guide` такой: **первый слой guide должен быть не тематическим, а surface-driven** — по minimum record families, reuse capabilities и already-existing validators/runbooks/reports. Это намного лучше согласуется с текущим состоянием репозитория, чем попытка сразу строить corpus по внешним кейс-категориям без привязки к каноническим surfaces. fileciteturn49file0turn75file0turn76file0

## Что следует считать baseline-выводом для capability-baseline-map

Если сжать всё выше до содержания будущего `docs/research/universal-policy-design/capability-baseline-map.md`, то baseline должен зафиксировать четыре жестких тезиса.

Первый тезис: **канонический центр тяжести уже существует**. Он лежит не в одном новом “policy design case engine”, а в связке `runtime/quality/*` + `scientist/policy_design/*` + `scientist/evidence/*` + `scientist/methods/research_dag/*` + `scientist/publishing/*` + `lex/*` + `fabric/*` + `scholar/*` + `data_forge/read_api` + `core/audit/*`, а реестр reuse для 27 capabilities уже определен. fileciteturn75file0turn76file0turn79file0turn80file0turn82file0turn83file0turn84file0turn74file0

Второй тезис: **универсальная Policy Design Case сегодня — это прежде всего registry/validation/projection/authority layer, а не полностью собранный first-class case object**. Подложка в значительной степени реализована, но concrete family coverage, producer emission completeness и orchestration depth остаются неравномерными. Поэтому baseline-map должен различать “implemented surface” и “compiled universal case”. fileciteturn49file0turn46file0turn68file0

Третий тезис: **compatibility shims — реальный риск для исследования**, особенно в `scientist`, `fabric`, `ir`, а также в некоторых Foundry/DDM paths. Поэтому каждый объект в baseline-map должен иметь два атрибута: `canonical_path` и `shim_or_legacy_path`, а также `sunset/owner`, если path живет только как compatibility layer. Иначе более поздние исследовательские задачи будут нечаянно проектировать новые концепты на устаревшие корни. fileciteturn79file0turn77file0turn89file0turn76file0

Четвертый тезис: **единственный очевидный greenfield — formal substrate invariant specification**. Все остальное в C0 должно трактоваться через reuse/extend/consolidate, пока не будет доказано обратное. Это крайне важное ограничение для последующих концептуальных задач. fileciteturn76file0

## Ограничения и открытые вопросы

Главное ограничение этого прохода — я не подтвердил существование или содержимое именно файла `POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md` в `main`, поэтому исследование построено на вашем фрагменте C0 и на соседних canonical artifacts репозитория.

Второе ограничение — baseline уже достаточно силен для C0, но еще не закрывает все requested temporal rows с одинаковой глубиной. В частности, для `Data Forge snapshot/release time`, `DDM detection time`, `claim registry time`, `model time` и полностью явного `replay time` нужны дополнительные точечные извлечения из конкретных contracts/modules, а не только package-level anchors. Частично эти линии присутствуют, но не собраны в одну окончательную temporal matrix. fileciteturn84file0turn85file0turn72file0

Третье ограничение связано с corpus. Я смог надежно выделить corpus anchors, но не прочитал в полном объеме все candidate reports и case documents, такие как MSME final suite, grand tournament или архивный policy-design implementation plan. Поэтому раздел корпуса выше — **надежный baseline-каркас, но еще не финальный annotation guide**. fileciteturn45file33turn45file34turn45file37turn48file6

# Исследование статусов и soft-gate семантики в PolicyOS

## Рамка и исходные ограничения

Я проводил исследование не как для “blank slate”, а как для уже сильно нормированного движка, в котором ключевые инварианты уже закреплены: модификации должны быть аддитивными, sidecar-ориентированными, fail-closed, с явным provenance и без тихого повышения authority через проекции или UI-представления. Это прямо видно в ближайших доступных плановых и дизайн-артефактах policy-design-case, а также в runtime-state и authority contracts, где проекции отделены от authority-state и доказательной authority. fileciteturn19file0 fileciteturn18file0 fileciteturn25file2 fileciteturn24file2

Точный файл плана, указанный в запросе, в доступном снимке репозитория по ожидаемому пути не открылся. Поэтому я опирался на ближайшие доступные плановые и design-decision документы policy-design-case, а затем на перечисленные code anchors. Это ограничение не мешает ответить на C1, потому что сами контракты статусов, authority и closeout уже находятся в коде и reference docs, а задача C1 прямо требует идти “от anchors”, а не от абстрактной новой модели. fileciteturn19file0 fileciteturn18file0

Главный вывод рамки такой: в PolicyOS уже нет одного единственного статуса. Вместо этого система фактически живет в наборе локальных алгебр — approval, authority, semantic binding, phase barriers, claim support, citation faithfulness, decision validity, transportability, proof composability, readiness ladders и capability/status reconciliation. Поэтому правильный ответ на C1 — не новый “god enum”, а нормализованный **композитный статусный конверт**, который сохраняет локальные enum’ы, но позволяет их безопасно композиционировать. fileciteturn24file1 fileciteturn24file2 fileciteturn25file0 fileciteturn25file1 fileciteturn25file2 fileciteturn29file1 fileciteturn29file2 fileciteturn33file0 fileciteturn34file1

## Что уже существует в коде

На runtime/approval стороне уже есть четкая локальная алгебра: approval packet принимает решение `approved`, `approved_with_override` или `blocked`; eligibility отдельно хранит причины; `quality_status` считается проходящим только для `pass/passed/ok/success`; `performance_status` трактует `warn`, `degraded`, `missing`, `timeout`, `over_budget`, `fail` и ряд других значений как blocking; human-review calibration сама по себе имеет `pass`, `warn`, `fail`, причем `fail` является blocking evidence для serious production approval. Иными словами, approval уже живет не в одном статусе, а минимум в четырех осях: итоговое решение, eligibility, override guardrails и review/calibration quality. fileciteturn24file1 fileciteturn31file0 fileciteturn31file1

На authority/runtime-quality стороне различия еще богаче. Authority envelope различает `evidence_class`, `authority_role`, `provenance_kind`, `validation_status` и `blocking_status`, причем блокировка уже имеет уровень `non_overridable`, а authority-role прямо разделяет `producer_authority`, `runtime_blocker`, input-like роли и projection/diagnostic-only роли. Semantic binding использует `pass/blocked/fail`, но одновременно держит отдельный `runtime_report_status`, где уже есть `warn` и `degraded`; phase barriers имеют `pass/blocked/skipped`, где `skipped` специально объявлен неавторитативным, а `blocked` требует typed blocker; state machine прямо запрещает считать `approval_ready` и `published` authority-state, потому что это projections, а не authority. Это очень сильный сигнал, что в системе уже различаются как минимум severity, blockingness, overridability и authority-surface. fileciteturn24file2 fileciteturn25file0 fileciteturn25file1 fileciteturn25file2

На Scientist-уровне claim semantics уже разделены на несколько независимых осей. `ClaimSupport` различает `unsupported`, `weak`, `supported`, `strong`, но отдельно от этого рассчитывает `publishability` и `lifecycle_transition`; claim-models различают `support_status` (`unsupported`, `weakly_supported`, `supported`, `contested`, `refuted`, `not_evaluable`) и отдельно `publishability` (`draft`, `internal_only`, `review_required`, `publishable`, `blocked`); claim-level readiness живет в ladder от `research_artifact` до `deployment_ready`; citation-faithfulness использует отдельную метку `supports`, `partially_supports`, `scope_limited`, `contradicts`, `irrelevant`, `fabricated`, `unverifiable`, причем для public factual/legal claims любая метка, кроме `supports`, считается blocking. Значит, на уровне claim/publication в коде уже есть минимум четыре разные семантики: semantic support, factual citation faithfulness, publication scope и readiness cap. fileciteturn29file2 fileciteturn34file1 fileciteturn33file2 fileciteturn29file1

На lifecycle/causal-reuse стороне расслоение продолжается. Decision-validity service хранит текущий статус, sticky triggers, transition history и lifecycle jobs, а для legacy packets по умолчанию использует `WARNING`-подобное поведение и review semantics; transportability governance pass уже различает `identified`, `partially_identified`, `bounded_non_identified`, `unsupported` и назначает им либо warning-, либо blocker-эффект в зависимости от профиля и того, объявлен ли transport required; proof composability различает `reusable`, `revalidate`, `rederive`, `unknown`, то есть отдельно кодирует безопасную переиспользуемость доказательства; при этом planning/reference документы Scientist еще и держат метастатусы наподобие `closed`, `still_gated`, `research_first`, которые вообще не являются runtime truth и не должны попадать в operational lattice. fileciteturn29file0 fileciteturn34file2 fileciteturn33file0 fileciteturn31file2

Из этого следует важная нормализация: часть нынешних “статусов” — это **runtime truth**, часть — **publication truth**, часть — **lifecycle truth**, часть — **planning metastatus**. Их нельзя сливать в один enum без потери смысла. fileciteturn25file2 fileciteturn31file2 fileciteturn34file1

## Предлагаемая статусная решетка

Предлагаю не заменять локальные enum’ы, а вводить над ними единый **StatusEnvelope**, то есть произведение нескольких частичных порядков. Локальный статус остается локальным источником правды, а envelope — это нормализованная проекция для cross-cutting consumers: release gates, dashboards, approval, governance, publication и closeout. Такая схема воспроизводит текущие контракты точнее, чем любой “главный enum”, потому что сами контракты уже разведены по orthogonal fields. fileciteturn24file1 fileciteturn24file2 fileciteturn25file0 fileciteturn25file1 fileciteturn29file2 fileciteturn34file1

| Ось | Нормализованный домен | Правило композиции |
|---|---|---|
| Severity | `ok < advise < warn < fail < invalidating` | брать наиболее тяжелое значение |
| Blockingness | `none < soft_gate < hard_gate` | брать наиболее ограничительное |
| Overridability | `not_needed < overridable < human_override_only < non_overridable` | `non_overridable` доминирует |
| Authority tier | `authority_bearing > runtime_blocker > control_input > projection > diagnostic > not_authoritative` | брать **наименее** авторитативное |
| Evidence tier | `authority_bearing > supporting > derived/projected > debug/legacy` | брать **наименее** надежное |
| Publication scope | `public > reviewer > internal > none` | брать самый узкий scope |
| Readiness cap | `deployment_ready > recommendation_ready > simulation_ready > external_briefing > analyst_advisory > research_artifact > none` | брать самый низкий cap |
| Degradation/proxy | `none < warn_only < degraded < proxy < bounds_only_or_revalidate < unsupported` | брать наиболее деградированный режим |
| Review action | `none < operator_review < human_review < expert_review < reissue_review < withdrawal_review` | брать наиболее сильное review-действие |
| Closeout effect | `none < annotate < withhold_publication < block_approval < require_reissue < withdraw` | брать наиболее сильный closeout-эффект |

Смысл этой решетки в том, что она делает явным уже существующее поведение. В PolicyOS authority-role и evidence-class уже отделены от blocking-status; projection уже отделен от authority-state; support уже отделен от publishability; citation-faithfulness уже отделен от claim support; transportability и proof composability уже живут как degradation/fallback surfaces, а не как общий “true/false”. Поэтому безопасная композиция должна быть **покомпонентной**, а не через flattening в один label. fileciteturn24file2 fileciteturn25file2 fileciteturn29file1 fileciteturn29file2 fileciteturn33file0 fileciteturn34file2

Практически это приводит к такому reconciliation rule-set. `DecisionReadiness` остается **единственной канонической осью readiness cap**. `ClaimPublishability` больше не трактуется как общее качество; она проецируется в `publication_scope + review_action + closeout_effect`. `ClaimValidationResult.status` (`ok/warning/blocked/legacy_missing/disabled`) следует считать статусом валидатора, а не статусом claim truth; `legacy_missing` и `disabled` должны идти в ось degradation/provenance, а не в severity. Capability readiness из best-in-class reconciliation (`closed/still_gated/research_first/...`) — это вообще plan/program status, и его нужно держать отдельно от runtime lattice. Наконец, decision-validity и continuous-governance vocabulary должны сохраняться как local lifecycle states, но проецироваться на оси `review_action` и `closeout_effect`, а не переопределять semantic support или authority напрямую. fileciteturn31file2 fileciteturn34file1 fileciteturn33file2 fileciteturn29file0 fileciteturn31file0

Ключевое проектное правило: **локальный статус никогда не теряется**. В envelope должны жить и нормализованные оси, и `local_state` с `producer`, чтобы downstream мог и агрегировать безопасно, и восстановить точный исходный semantics. Это особенно важно для пар вроде `semantic_binding=blocked` и `phase_barrier=skipped`: оба не проходят downstream authority, но причины и remediation разные. fileciteturn25file0 fileciteturn25file1

## Правила soft-gate и предупреждений

Soft-gate в PolicyOS нужен не как “слабый fail”, а как **явно управляемый дефицит**, у которого всегда есть владелец, возраст, escalation-path и предельный publication-scope. Такая модель лучше всего согласуется с текущими owner-объявлениями в runtime approval, human review calibration и Scientist reference surfaces, где ownership уже формализован, а review/reissue/withdrawal уже являются отдельными действями, а не просто текстовыми advice. fileciteturn31file0 fileciteturn31file1 fileciteturn31file2

Предлагаю следующее универсальное правило владения. Если статус породил конкретный subsystem contract, owner берется из owner/source-of-truth этой поверхности; если owner явно не оформлен, owner = владелец emitting package + platform backup. Для production approval это `@runtime-owners` и `@platform-owners`; для human-review calibration — `team-governance`; для Scientist claim/publication surfaces — `@scientist-owners` с platform backup. Это покрывает requirement “каждый warning-like state имеет owner” без необходимости изобретать новый org model поверх уже существующего. fileciteturn31file0 fileciteturn31file1 fileciteturn31file2

| Класс soft-gate | Кто владеет | Age / escalation policy | Publication effect | Closeout effect |
|---|---|---|---|---|
| Citation/publication warning | Scientist owner | triage в день появления; эскалация через 7 дней; hard escalation через 14 дней | public запрещен, reviewer/internal допустимы | блок публичного экспорта до ремонта citation/support |
| Transport/proof degradation | causal/scientist owner | немедленная triage в governed/production; 7 дней в research; эскалация через 14 дней | public only by explicit degraded policy; по умолчанию reviewer/internal | cap readiness, запрет на deployment-closeout |
| Operational validity warning/staleness | runtime/governance owner | immediate review queue; stale не живет “вечно” | нет новой публичной публикации; уже выпущенное получает warning posture | review, reissue или withdrawal review |
| Projection/source-truth mismatch | runtime/platform owner | immediate; без grace period | projection может отображаться, но не говорить authoritative truth | блок approval/state closeout |

Допустимая политика дефицита должна быть очень узкой. Я предлагаю считать soft-gate “допустимым дефицитом” только если одновременно выполняются четыре условия: статус явно помечен как degraded/proxy/revalidate/bounds-only; publication scope не шире `reviewer/internal`; readiness cap не выше `analyst_advisory` или `research_artifact`, если речь о высокорисковых claims; для статуса указаны owner, next action и expiry/escalation timestamp. Это соответствует текущему коду: public factual/legal claim не может пережить нефэйтфул citation; publishable high-stakes claim требует evidence; public artifact требует approved state и compiler gates; unsupported transport нельзя автоматически одобрять. fileciteturn29file1 fileciteturn34file1 fileciteturn25file2 fileciteturn31file0 fileciteturn34file2

Недопустимые случаи тоже должны быть формализованы. Нельзя soft-gate’ом закрывать `non_overridable` blockers, projection/source-truth conflicts, public citation-faithfulness violations, unsupported transport for transport-required contexts, а также любую попытку превратить projection-only surface в authority-bearing surface. Это уже следует из authority envelope, run-state, citation-faithfulness и transportability-required semantics. fileciteturn24file2 fileciteturn25file2 fileciteturn29file1 fileciteturn34file2

Правило агрегации я бы зафиксировал так. Непреодолимый blocker доминирует все остальное. Weakest authority wins. Narrowest publication scope wins. Lowest readiness cap wins. Любой degraded/proxy/bounds/revalidate статус обязан оставаться видимым и не может быть “съеден” сильным evidence в соседнем измерении. Sticky validity triggers и lifecycle history должны сниматьcя только явным reissue/supersession/withdrawal path’ом, а не просто более поздним зеленым чекпоинтом. Именно это позволяет воспроизвести текущую локальную семантику, не вводя ложной монотонности там, где ее нет. fileciteturn24file2 fileciteturn25file2 fileciteturn29file0 fileciteturn33file0

## Таблица смешанных решений

Ниже — предложенная decision table, которая **сначала воспроизводит текущие локальные правила**, а уже потом нормализует их через status envelope.

| Сценарий | Текущее локальное поведение | Предлагаемый составной результат | Publication effect | Closeout effect | Основание |
|---|---|---|---|---|---|
| `SUPPORTED` claim + citation label `partially_supports` | Claim support может быть положительным, но для public factual/legal claims любая citation метка кроме `supports` blocking | severity=`warn`, gate=`soft_gate` для internal и `hard_gate` для public, review_action=`human_review`, local_state сохраняет и `supported`, и `partially_supports` | `reviewer/internal`; public запрещен до narrowing или repair citation | `withhold_publication`; claim не удаляется, а остается review-required | fileciteturn29file2 fileciteturn29file1 fileciteturn34file1 |
| degraded or partial transport + strong evidence | Transportability может быть partial/bounds-only/unsupported даже при сильной data/method evidence; governance pass already warns or blocks by profile | evidence_tier остается высоким, но degradation=`bounds_or_partial_transport`; readiness_cap понижается; если `transport_required`/STRICT — `hard_gate` | reviewer/internal по умолчанию; public только при явной degraded policy; unsupported = no publication | `block_approval` для strict transport-required paths; иначе `annotate + require review` | fileciteturn34file2 fileciteturn29file2 fileciteturn34file1 |
| decision validity warning + publication request | Decision-validity service накапливает sticky triggers и review_required semantics; reissue/withdrawal уже отдельные workflow’ы | lifecycle local_state остается `warning`-семейства; review_action повышается минимум до `human_review`; validity warning не трогает raw claim truth, но режет publication scope | новый public release запрещен; internal retention/monitoring допустимы | `annotate` для уже существующего артефакта, `require_reissue` если предупреждение не закрыто | fileciteturn29file0 fileciteturn31file0 |
| semantic binding `fail` + dashboard projection | Semantic binding fail фиксирует binding failure; approval code отдельно ловит source-truth conflict, если dashboard projection пытается говорить поверх authoritative packet/readiness | authority_tier принудительно снижается до `projection/diagnostic`; gate=`hard_gate` для approval/state consumers; projection может жить только как non-authoritative view | dashboard можно показывать, но не как authority; public claim/approval projection запрещен | `block_approval` и `block_state_closeout`; projection не повышает authority | fileciteturn25file0 fileciteturn24file1 fileciteturn25file2 fileciteturn24file2 |

Главное достоинство такой таблицы в том, что она **не заставляет побеждать один локальный статус другой**. Вместо этого она сохраняет оба сигнала и дает deterministic rule о том, какой downstream effect получается по каждой оси. Именно этого сейчас не хватает, когда разные слои начинают спорить о том, “какой статус главный”. fileciteturn24file1 fileciteturn25file0 fileciteturn29file1 fileciteturn29file2

## Черновик ADR

**Статус.** Proposed, additive, pre-enforcement.

**Контекст.** В репозитории уже существуют самостоятельные локальные алгебры статусов: runtime approval, authority envelopes, semantic binding, phase barriers, run-state, claim support, citation faithfulness, claim readiness, decision validity, transportability и proof composability. Эти алгебры описывают разные свойства и не сводятся к одной общей линейной шкале. fileciteturn24file1 fileciteturn24file2 fileciteturn25file0 fileciteturn25file1 fileciteturn29file1 fileciteturn29file2 fileciteturn33file0 fileciteturn34file2

**Решение.** Ввести `StatusEnvelope` как normalization layer над локальными статусами. Каждый producer обязан публиковать: `local_state`, `producer`, `severity`, `blockingness`, `overridability`, `authority_tier`, `evidence_tier`, `publication_scope`, `readiness_cap`, `degradation_mode`, `review_action`, `closeout_effect`, `owner`, `expires_at`, `escalates_to`. Consumers больше не сравнивают локальные enum’ы между собой напрямую; они работают через envelope-предикаты вроде `blocks_authority`, `blocks_publication`, `caps_readiness_at`, `requires_review`, `override_allowed`, `requires_reissue`. Это дает единый compositional surface без стирания локальной семантики. fileciteturn24file2 fileciteturn25file2 fileciteturn34file1

**Правило совместимости.** На первом этапе менять текущий runtime behavior не нужно. Надо только построить mapping layer и golden tests, которые покажут, что существующее поведение approval, citation blocking, claim publishability, transport gating, skipped barriers и proof replay воспроизводится без потерь. Лишь после этого можно предлагать stricter policies, например более жесткие age thresholds или более низкие readiness caps для degraded transport. Такой путь совпадает с общим подходом текущих policy-design-case планов и Scientist reconciliation: сперва additive sidecars и явные gates, потом ужесточение rollout. fileciteturn19file0 fileciteturn18file0 fileciteturn31file2

**Последствия.** Положительный эффект — исчезает необходимость изобретать “главный общий статус”; source-truth конфликты становятся явными; projections не смогут случайно подменять authority; warning-like states станут управляемыми, а не просто словарем текстовых проблем. Цена решения — необходимость поддерживать mapping contracts и discipline вокруг owner/escalation metadata, но именно это и нужно для приемки C1. fileciteturn24file1 fileciteturn24file2 fileciteturn25file0 fileciteturn25file2

## Открытые вопросы и ограничения

Первое ограничение — точный плановый файл из запроса не был доступен по ожидаемому пути в доступном снимке репозитория, поэтому контекст строился по ближайшим плановым и design-decision документам и по самим code anchors. Это не ломает выводы, но означает, что если в недоступном плане были дополнительные policy thresholds, их здесь нет.

Второе ограничение — часть будущих policy choices в коде еще не стандартизована численно. Это особенно заметно там, где severity зависит от профиля и explicit flags, например в transportability-required pass, где partial/bounds/non-support обрабатываются по-разному для STRICT и non-STRICT paths. Поэтому предложенные age/SLA/elevation правила выше — это именно ADR-предложение, а не утверждение, что такие пороги уже есть в коде. fileciteturn34file2

Третье ограничение — плановые статусные словари вроде `closed/still_gated/research_first` уже живут в Scientist reconciliation docs, но они не должны мигрировать в runtime lattice как operational truth. Их лучше оставить отдельной мета-плоскостью program management. Это важно зафиксировать до любой реализации `StatusEnvelope`, иначе система снова получит смешение readiness, release status и roadmap status в одном месте. fileciteturn31file2

# Исследование по C2 для PolicyOS

## Рамка исследования и исходный baseline

В репозитории задача C2 уже **не является “чистым листом”**. Ближайшие напрямую извлеченные рамочные документы описывают PolicyOS как систему, в которой серьезный policy output не должен проходить без **привязанных к claim** юридических, данных, методологических, семантических и governance-доказательств, а сама архитектура должна рассматривать их как **runtime-owned binding graph**, а не как разрозненные отчеты. Именно в этой рамке я строю предлагаемый calculus допустимости и авторитетности. fileciteturn62file0L3-L3 fileciteturn24file0L3-L3

По коду и reference-документам видно, что в PolicyOS уже есть как минимум три разных слоя оценки доказательств. Во-первых, слой **semantic support**: claim получает семейство и набор обязательных support-предикатов. Например, factual claim требует `data_ref` и `source_attribution`, legal claim — `norm_ref` и `legal_scope`, causal claim — `data_ref`, `method_ref` и `identification_strategy`, numerical claim — `method_ref`, `method_output_ref` и `numeric_value`. Поддержка (`unsupported`, `weak`, `supported`, `strong`) отделена от publishability (`internal_only`, `review_required`, `publishable`, `blocked`). fileciteturn48file0L3-L3 fileciteturn47file0L3-L3

Во-вторых, есть слой **citation faithfulness**. Для cited public factual/legal claims PolicyOS уже различает `supports`, `partially_supports`, `scope_limited`, `contradicts`, `irrelevant`, `fabricated` и `unverifiable`; для публичных factual/legal claims любой non-`supports` label является blocking, а отсутствие citation refs также блокирует claim. Это очень важно: репозиторий уже зафиксировал, что “formal support predicate present” и “citation admissible for publication” — это не одно и то же. fileciteturn49file0L3-L3

В-третьих, есть слой **runtime authority**. В `authority.py` уже определены классы evidence (`authority_bearing`, `diagnostic_supporting`, `debug_only`, `public_exported`, `redacted_derived`, `legacy_quarantined`), authority roles (`producer_authority`, `runtime_blocker`, `scorecard_input`, `readiness_input`, `approval_input`, `projection_only`, `packaging_only`, `diagnostic_only`, `not_authoritative`), provenance kinds и same-input closure. Для serious profiles (`research`, `governed`, `production`) authority-bearing evidence допускается только при корректном provenance, а projection/packaging surfaces не могут удовлетворять authority boundary. fileciteturn59file0L3-L3

Эта архитектура согласуется с ADR-0147 и ADR-0150: истина для downstream readers должна течь от **runtime producer event → runtime CAS artifact → envelope → scorecard verification → readiness**, при этом scorecard, readiness UI, dashboard, bundle и public/export surfaces не имеют права “чеканить” новую authority поверх runtime truth. Overrides могут принять остаточный риск, но не могут превратить **missing authority** в authority. fileciteturn41file0L3-L3 fileciteturn44file0L3-L3

Снаружи репозитория эта логика хорошо поддерживается тремя зрелыми корпусами идей. W3C PROV задает provenance как сведения об entities, activities и agents, которые позволяют судить о качестве, надежности и trustworthy данных, и отдельно подчеркивает необходимость **provenance of provenance**. Федеральные правила доказательств США дают минимальную модель relevancy, authentication и competence: evidence должно быть относимым к факту в споре, аутентифицированным и, если это expert evidence, основанным на достаточных данных и надежных методах. Наконец, Cochrane/GRADE дает практическую схему downgrading certainty по доменам risk of bias, inconsistency, indirectness, imprecision и publication bias, а также подчеркивает, что meta-analysis может серьезно вводить в заблуждение, если не учтены heterogeneity, within-study bias и reporting bias. citeturn5view0turn6view0turn6view1turn6view2turn6view3turn11view1turn12view0

## Предлагаемое исчисление допустимости и уровней авторитетности

Ключевой вывод исследования: **нынешний support predicate должен считаться authority-bearing evidence не сам по себе, а только после прохождения пяти последовательно устроенных проверок**.

Сначала идет **support fit**: claim family уже определяет, какие предикаты вообще нужны для смысла claim. Потом идет **faithfulness/authentication**: ref не fabricated, не unverifiable, и либо действительно supports claim, либо честно маркируется как partial/scope-limited/contradiction. Затем идет **authority/provenance**: evidence имеет допустимый authority role, provenance kind, same-input closure и source-of-truth статус. После этого идет **semantic applicability**: совпадают jurisdiction, time, population, metric/unit/denominator, method output, legal competence и claim path. И только затем включается **portfolio aggregation**: независимость, дублирование, контрдоказательства, stopping rules и synthesis. Такая структура естественно продолжает уже имеющиеся в PolicyOS слои claim support, citation faithfulness, semantic binding, data-forge binding и authority envelopes. fileciteturn48file0L3-L3 fileciteturn49file0L3-L3 fileciteturn57file0L3-L3 fileciteturn55file0L3-L3 fileciteturn59file0L3-L3

В этой модели я предлагаю считать, что evidence становится **authority-bearing для claim** только если одновременно выполнены девять содержательных условий:

На уровне **freshness** evidence не просрочено относительно своего TTL или исторического `as_of`; в репозитории это уже проверяется для Data Forge snapshot bindings через freshness timestamp и TTL, а SourceContract v2 хранит SLA/freshness expectations. fileciteturn55file0L3-L3 fileciteturn53file0L3-L3

На уровне **lineage** должен существовать trace от claim назад к data/norm/method/source facets и transformations. Semantic binding ledger уже моделирует `claim_evidence_paths`, source facets, derived features, method outputs, rebuttals и blocker refs; SourceContract v2 требует lineage seed, а Data Forge binding требует manifest/CAS identity и artifact ids. fileciteturn57file0L3-L3 fileciteturn53file0L3-L3 fileciteturn55file0L3-L3

На уровне **quality tier** источник должен быть не просто найден, а проходить quality contract и иметь понятный trust/calibration state. SourceContract v2 уже хранит `source_trust.tier`, `calibration_status`, `quality.contract_ref`, replay evidence, field access policy и processing guarantees; это хорошая опора для “quality-bearing admissibility”. fileciteturn53file0L3-L3

На уровне **legal competence** legal evidence должно быть не просто тематически похоже на claim, а извлечено как применимая норма для нужной jurisdiction/time frame и правильного competence/hierarchy. `applicability_report.py` уже строит candidate/selected/rejected norms, competence rows, hierarchy conflicts и typed blockers (`no_relevant_norm_found`, `retrieval_failed`, `missing_store`). Это дает естественную основу для различения direct legal admissibility, proxy legal context и blocked legal evidence. fileciteturn56file0L3-L3

На уровне **scope match** evidence должно совпадать хотя бы по decisive axis: claim family, legal scope, population, jurisdiction, date, exception, subgroup или implementation scope. Именно это фиксируют current citation-faithfulness labels `scope_limited` и `partially_supports`; GRADE называет это indirectness и специально рекомендует понижать certainty, если population/intervention/comparator/outcome не совпадают с вопросом применения. fileciteturn49file0L3-L3 citeturn12view0turn12view2

На уровне **numeric/time semantics** numerical и forecast claims не должны считаться admissible без единицы измерения, метода, method output, временного горизонта и корректного `as_of`. Это уже прямо зашито в family rules для numerical/forecast claims и в Lex/Fabric time filters. fileciteturn48file0L3-L3 fileciteturn56file0L3-L3

На уровне **same-input closure** evidence lines должны говорить об одном и том же run/job/tenant/cell/time/legal/data/method context. `authority.py` уже делает этот fail-closed boundary явным: closure must be `closed`, с непротиворечивым `closure_sha256`, иначе authority collapses. fileciteturn59file0L3-L3

На уровне **source truth** direct authority может исходить только от runtime-owned producer/CAS pair, а не от scorecard projection, dashboard, bundle packaging или public export. Это уже решено и в ADR-0147/0150, и в `assert_runtime_emitted()`/`assert_authority_bearing()`. fileciteturn41file0L3-L3 fileciteturn44file0L3-L3 fileciteturn59file0L3-L3

На уровне **independence** несколько evidence lines нельзя просто суммировать по количеству: зависимость, shared-source risk, shared method risk, sponsor dependence и bundle-level duplication должны быть видимы, иначе aggregation вводит ложную силу. Эта часть в репозитории уже поддержана ADR-0160/0164 через portfolio design, independence map, disconfirming evidence, multiverse/specification curve и stopping rules, а внешняя evidence-synthesis литература отдельно предупреждает против misleading synthesis при heterogeneity, bias и publication bias. fileciteturn46file0L3-L3 citeturn11view1turn12view0

Ниже — предлагаемый **decision table** для Lex, Scientist, scorecard, readiness и downstream readers.

| Состояние | Минимальные условия | Что разрешено делать | Верхний потолок authority |
|---|---|---|---|
| **admissible** | Claim-fit выполнен; faithfulness = supports; provenance authority-bearing; scope match; same-input closure closed | Использовать как прямую опору для claim | До production, если портфель тоже проходит |
| **proxy_with_limitation** | Источник релевантен, но есть one-step indirectness: population/date/exception/authority tier ниже требуемого | Использовать только с явной оговоркой и ceiling на claim strength | Не выше governed direct support; в production только как limitation/backup |
| **context_only** | Источник помогает понять фон, механизм, историю, но не доказывает fact-in-issue | Показывать рядом с claim как background/context | Не может повышать publishability прямого claim |
| **contested** | Есть хотя бы одна admissible line, но имеется независимое contradiction или unresolved counterevidence | Сохранять в record, но блокировать “unqualified truth” | Может поддержать только contested statement или explicit uncertainty |
| **blocked** | Fabricated, unverifiable, missing authority envelope, non-CAS substitution, same-input mismatch, disallowed fallback, serious legal/method failure | Использовать лишь как evidence of blockage, а не truth of claim | Никакой positive claim authority |
| **out_of_scope** | Evidence отвечает не на тот jurisdiction/time/population/legal scope question | Не использовать для claim; максимум — отдельный historical or neighboring note | Никакой claim authority |

Эта таблица согласуется и с repo semantics, и с более общими правилами admissibility. Rule 401 описывает relevance как способность сделать fact “more or less probable” и одновременно требует, чтобы fact был “of consequence”; Rule 403 разрешает исключать даже релевантное evidence, если probative value существенно перевешивается риском confusion, waste или needless cumulative presentation; Rule 702 требует надежные методы и достаточные данные; Rule 901 требует, чтобы был достигнут порог “item is what the proponent claims it is.” Именно эти четыре идеи в PolicyOS лучше всего маппятся на `admissible`, `contested`, `blocked` и `context_only`. citeturn6view0turn6view1turn6view2turn6view3

Отсюда следует главный проектный тезис C2: **support predicates остаются эмпирическим baseline, но authority-bearing admissibility должен быть отдельным calculus поверх них**. Иначе PolicyOS продолжит смешивать “claim has enough semantic pieces” с “these pieces are competent, authentic, applicable and consumable at the requested authority profile”. fileciteturn48file0L3-L3 fileciteturn59file0L3-L3

## Портфельные формы по типу claim и правила композиции

Для PolicyOS полезно различать не только claim families, но и **authority-level portfolio shapes**. Иначе одинаковые предикаты будут применяться к research sketch и production-closeout так, будто у них одинаковый epistemic burden.

| Claim family | Research | Governed | Production |
|---|---|---|---|
| **Factual** | 1 direct data line + attribution | Direct data line + freshness/lineage + хотя бы одно corroborating or source-truth check | Runtime-emitted authority-bearing data line + same-input closure + независимая corroboration или официальный source-of-truth line |
| **Legal** | Selected norm or typed blocker + jurisdiction/date | Selected norms + rejected norms + competence/hierarchy + explicit no-norm vs retrieval-failure split | Only applicable authoritative norms as direct support; commentary/secondary materials не могут заменять норму |
| **Causal** | `data_ref` + `method_ref` + `identification_strategy` | То же + uncertainty/sensitivity or negative-control evidence | То же + disconfirming/robustness line + explicit counterevidence handling + portfolio independence |
| **Numerical** | Method ref + method output + numeric value | То же + unit/denominator/time alignment | То же + recomputable output, lineage to source facets, no local-path substitution |
| **Forecast** | Model + horizon + uncertainty | То же + calibration/backtest or declared deficit | То же + freshness, degradation/mode ledger, explicit scenario compatibility |
| **Distributional / Welfare** | Method + subgroup/welfare metric | То же + subgroup definition sensitivity / welfare assumption visibility | То же + explicit data lineage, uncertainty and normative assumption binding |
| **Implementation** | Plan + feasibility refs | То же + capacity/budget/risk/monitoring bindings | То же + runtime-owned feasibility evidence; при пропусках claim может быть максимум reviewable |

Эта таблица напрямую выводится из уже существующих family rules claim support, из semantic binding ledger, из Lex/Fabric/Foundry binding expectations и из Policy Design Case QA profile, который требует distinct nodes для claim, argument, warrant, evidence, rebuttal, counter-evidence, deficit и residual uncertainty. fileciteturn48file0L3-L3 fileciteturn57file0L3-L3 fileciteturn45file0L3-L3

Практически это означает, что допустимость дефицитов должна быть тоже **mode-dependent**.

| Дефицит | Research | Governed | Production |
|---|---|---|---|
| Умеренная косвенность или proxy source | Допустимо с явным limitation | Reviewable, если direct source недоступен и это не скрыто | Не может быть прямой опорой major claim |
| Небольшая свежесть вне идеального окна, но с корректным historical `as_of` | Допустимо | Reviewable | Только для historical/context claims; для current decisive claims — blocked |
| Отсутствие второй независимой линии | Допустимо для exploratory work | Reviewable для factual/legal; недостаточно для major causal/numerical claims | Обычно blocked для major empirical/causal claims |
| Contesting evidence / contradictory line | Допустимо как contested record | Требует reviewer adjudication | Может существовать только как contested/limitation, но не как unqualified support |
| Missing authority envelope / non-CAS path / same-input mismatch / packaging-only / projection-only | Нельзя считать authority, даже если можно читать как debug/context | Non-overridable | Non-overridable |
| Fabricated / unverifiable citation | Blocked | Non-overridable | Non-overridable |
| Disallowed fallback / simulated provider leakage in live-required lane | Допустимо лишь как internal degraded evidence | Non-overridable для serious closeout | Non-overridable |

Это прямо согласуется с ADR-0149 и ADR-0150: serious lanes обязаны сохранять effective mode и degradation ledger, fallback-produced evidence не может молча удовлетворять production gates, а missing runtime authority, disallowed fallback, fixture-only evidence, simulated evidence in live-required lane, ownership conflicts и unverifiable scorecard identity названы non-overridable blockers. fileciteturn43file0L3-L3 fileciteturn44file0L3-L3

Для **composition semantics** я предлагаю следующую формализацию:

Если несколько линий **сильно зависимы** — один и тот же dataset, один и тот же snapshot, одна и та же method family, один и тот же sponsor, одна и та же bundle projection, или один и тот же source-of-truth, переупакованный в разные artifacts, — то они должны **схлопываться** в одну effective line. Это не “four confirmations”, а одна зависимая линия. Репозиторий уже мыслит в терминах same-input closure и source-of-truth order, а Cochrane отдельно предупреждает, что synthesis может misleadingly amplify noise, если heterogeneity, bias и reporting bias не разобраны. fileciteturn59file0L3-L3 citeturn11view1turn12view0

Если есть несколько **слабых, но независимых** линий, они не должны автоматически становиться “strong” только по количеству. Максимум, что они могут дать без direct line, — это `reviewable support` или `proxy_with_limitation`. Иначе система вознаградит correlated weak evidence за объем. Это особенно критично для causal, numerical и forecast claims. fileciteturn48file0L3-L3 fileciteturn46file0L3-L3

Если есть **direct line + proxy line**, то proxy line может либо усиливать оговорку, либо давать контекст, но не должна понижать требования к direct line. Если же proxy line противоречит direct line и при этом независима, результат должен быть `contested`, а не “average truth”. Это согласуется с текущей логикой counterevidence в claim support, где `block`, `warn`, `lower_readiness` и `require_review` — action-bearing outcomes, а не просто метки. fileciteturn48file0L3-L3

Если есть **runtime_blocker evidence**, оно допустимо не для доказательства substantive truth claim, а для доказательства другой вещи: что claim сейчас корректно имеет статус `blocked`. Это уже соответствует authority model, где `runtime_blocker` — допустимая серьезная evidence role, но не producer authority для положительного claim. fileciteturn59file0L3-L3

Отдельное специальное правило нужно для **warrant-level evidence**, зависящего от explanation reliability. Если warrant зависит от explanation trust, репозиторий уже требует BERL reliability refs, bundle refs, validation thresholds, threshold decision, empirical bounds и local infidelity diagnostics; их отсутствие должно делать сам warrant inadmissible как direct support и переводить claim как минимум в `contested` или `review_required`, а в higher profiles — в `blocked`. fileciteturn51file0L3-L3

## Проверка на кейсах

Ниже — проверка модели на **первых десяти аннотированных кейсах**, которые уже зафиксированы в golden fixtures `citation_faithfulness/cases.json`. Это наиболее надежная эмпирическая опора для C2, потому что они уже hand-authored в репозитории и покрывают legal scope, jurisdiction, date, population, exception, contradiction, irrelevance, fabrication и unverifiability. fileciteturn60file0L3-L3

| Fixture case | Repo expectation | Предлагаемое состояние | Почему |
|---|---|---|---|
| `supports_public_legal_claim` | `supports`, `pass` | **admissible** | Полный scope/jurisdiction/date/population match |
| `legal_scope_mismatch_scope_limited` | `scope_limited`, `fail` | **context_only** | Похожий юридический контекст, но не тот legal scope |
| `jurisdiction_mismatch_scope_limited` | `scope_limited`, `fail` | **out_of_scope** | Неверная jurisdiction для direct claim |
| `date_mismatch_scope_limited` | `scope_limited`, `fail` | **out_of_scope** | Источник исторический, а claim текущий |
| `population_mismatch_scope_limited` | `scope_limited`, `fail` | **proxy_with_limitation** | Сигнал есть, но claim завышает population |
| `exception_mismatch_partially_supports` | `partially_supports`, `fail` | **proxy_with_limitation** | Источник годится только при сохранении исключения |
| `contradicts_public_legal_claim` | `contradicts`, `fail` | **contested** | Contradiction admissible в record, но блокирует publication |
| `irrelevant_public_factual_claim` | `irrelevant`, `fail` | **out_of_scope** | Нет relation к fact-in-issue |
| `fabricated_missing_ref` | `fabricated`, `fail` | **blocked** | Нет подлинного evidence object |
| `unverifiable_blocked_source` | `unverifiable`, `fail` | **blocked** | Нельзя аутентифицировать и проверить содержательно |

Этот mapping хорошо проходит acceptance-criterion C2: все шесть требуемых классов — direct, proxy, context-only, contested, blocked и out-of-scope — получаются **без domain-specific hacks**, только из комбинации repo semantics уже существующих слоев. fileciteturn49file0L3-L3 fileciteturn60file0L3-L3

Дальше — **20 дополнительных claim–evidence pairs**, которые я не исполнял кодом, а вывел как строгие следствия уже существующих правил claim support, authority envelopes, semantic binding, Lex/Fabric/Data Forge/BERL checks. Это именно inferential test matrix, а не runtime run. fileciteturn48file0L3-L3 fileciteturn53file0L3-L3 fileciteturn55file0L3-L3 fileciteturn56file0L3-L3 fileciteturn57file0L3-L3 fileciteturn59file0L3-L3 fileciteturn51file0L3-L3

| Pair | Ситуация | Состояние |
|---|---|---|
| A | Factual claim с `data_ref` и `source_attribution`, свежим snapshot и closure closed | **admissible** |
| B | Factual claim без `source_attribution` | **review_required / context_only** |
| C | Factual claim со stale Data Forge snapshot beyond TTL | **proxy_with_limitation** в research, **blocked** в production direct use |
| D | Legal claim с selected norm, competence refs и date/jurisdiction fit | **admissible** |
| E | Legal claim на основе secondary commentary без primary norm | **proxy_with_limitation** |
| F | Lex вернул `no_relevant_norm_found` с полным query trace | **blocked claim**, но blocker evidence **admissible** для blocked state |
| G | Lex candidate norms = 0 без query normalization trace | **blocked** |
| H | Causal claim: data + method + identification, но без uncertainty/robustness | **admissible** в research, **reviewable** в governed, слабовато для production major claim |
| I | Causal claim, negative control invalidates design | **contested** или **blocked** |
| J | Numerical claim: есть value, но нет `method_output_ref` | **review_required** |
| K | Numerical claim: есть output, но unit/denominator mismatch | **contested** |
| L | Forecast claim: horizon + uncertainty есть, но нет calibration/backtest | **reviewable** |
| M | Distributional claim без `subgroup_ref` | **review_required** |
| N | Welfare claim с welfare metric, но без uncertainty/sensitivity | **reviewable** |
| O | Implementation claim с plan+feasibility, но без monitoring/capacity refs | **admissible** в research, **reviewable** выше |
| P | Warrant depends on explanation; BERL refs missing | **blocked warrant**, claim не выше **contested** |
| Q | Runtime artifact: `producer_authority`, `runtime_emitted`, `cas_ref`, output refs match | **admissible** |
| R | Bundle summary marked `packaging_only` | **context_only** максимум; для authority — **blocked** |
| S | Event exists, CAS missing | **blocked** |
| T | Two “different” lines come from one snapshot/method/sponsor and same closure | **collapse to one weak line** |
| U | Two weak but genuinely independent proxy lines | **proxy_with_limitation**, не automatic strong |
| V | Direct line + independent contradiction | **contested** |
| W | Same-input closure mismatch across lines | **blocked** |
| X | Simulated provider evidence in live-required lane | **blocked** |
| Y | Public factual claim cites blocked page with no usable snippet | **blocked** |
| Z | Historical legal source with correct scope but wrong `as_of` for current claim | **out_of_scope** для direct current use |

Если нужен самый короткий итог этой проверки, он такой: **модель классифицирует все требуемые admissibility states и при этом естественно “садится” на уже имеющиеся в репозитории family rules, faithfulness labels, authority envelopes и binding ledgers**. Самое важное — она не пытается лечить conflicting evidence “средним значением” и не позволяет projection/packaging/debug surfaces masquerade as authority. fileciteturn48file0L3-L3 fileciteturn49file0L3-L3 fileciteturn59file0L3-L3

## Черновик ADR для authority-level admissibility calculus

### Контекст

PolicyOS уже умеет отдельно оценивать semantic support claims, citation faithfulness, runtime authority и semantic binding, но пока не имеет единого calculus, который переводит это в **admissibility decision** для claim under research, governed или production authority. Из-за этого одна и та же линия evidence может выглядеть “поддерживающей” на одном слое и при этом быть непригодной как authority-bearing support на другом. fileciteturn48file0L3-L3 fileciteturn49file0L3-L3 fileciteturn59file0L3-L3

### Решение

PolicyOS должен принять отдельный **authority-level admissibility calculus** со следующими правилами.

Первое. Допустимость evidence оценивается не одним флагом, а как последовательность из пяти gates: semantic support, faithfulness/authentication, provenance authority, semantic applicability и portfolio aggregation. Positive claim support возможен только при прохождении всех hard gates, разрешенных для requested authority profile. fileciteturn48file0L3-L3 fileciteturn49file0L3-L3 fileciteturn59file0L3-L3

Второе. Для downstream readers вводятся шесть нормализованных состояний: `admissible`, `context_only`, `proxy_with_limitation`, `contested`, `blocked`, `out_of_scope`. Для удобства операторов `admissible` может далее иметь внутренний подтип `direct` или `reviewable_direct`, но наружу это не обязательно делать новым top-level state. fileciteturn60file0L3-L3

Третье. Для legal claims direct admissibility требует selected applicable norm refs, jurisdiction/time filters, competence/hierarchy evidence и явное различение `no_relevant_norm_found` против `retrieval_failed`. Secondary legal commentary, doctrinal summaries и neighboring regulations не могут служить direct support, если отсутствует applicable norm. fileciteturn56file0L3-L3 fileciteturn42file0L3-L3

Четвертое. Для factual/numerical/causal/forecast claims direct admissibility в serious modes требует runtime-owned source truth: authority-bearing runtime evidence с CAS identity, same-input closure, semantic binding path и отсутствием projection/packaging substitution. Scorecard, readiness, dashboards и public artifacts — readers, а не producers of authority. fileciteturn41file0L3-L3 fileciteturn44file0L3-L3 fileciteturn57file0L3-L3 fileciteturn59file0L3-L3

Пятое. Portfolio synthesis обязан учитывать independence. Dependent evidence lines collapse into one line; independent weak lines remain reviewable unless there is at least one direct admissible line of the correct family. Conflicts produce `contested`, not averaged support. Runtime blockers are admissible for blocked-state assertions, but never as positive truth evidence. fileciteturn46file0L3-L3 fileciteturn48file0L3-L3 fileciteturn59file0L3-L3

Шестое. Non-overridable deficits для governed/production включают: fabricated or unverifiable citation, missing authority envelope, non-CAS substitution, same-input closure mismatch, packaging/projection used as authority, disallowed fallback/simulation, cross-tenant conflicts и live-required evidence produced only by fixture/simulation. Overrides могут принять residual risk, но не могут превратить blocked evidence в admissible. fileciteturn43file0L3-L3 fileciteturn44file0L3-L3 fileciteturn59file0L3-L3

### Последствия

Положительный эффект этой ADR в том, что PolicyOS перестанет путать **semantic possibility**, **citation surface plausibility** и **runtime authority**. Система сможет честно говорить: “claim понятен и структурно собран, но evidence только proxy”; “evidence по существу противоречиво”; “источник релевантен, но out-of-scope”; “authority present, but domain failed”; “blocker admissible as blocker, but not as truth.” Это прямо соответствует стратегии honest diagnostics, semantic relevance и fail-closed boundaries, уже принятой в репозитории. fileciteturn45file0L3-L3 fileciteturn42file0L3-L3 fileciteturn44file0L3-L3

Отрицательный эффект в том, что initial failure rate серьезных профилей вырастет. Однако ADR-0147 и ADR-0150 уже исходно признают это желательным архитектурным последствием: evidence presence и pass-shaped reports не должны замещать runtime truth. С operational точки зрения это увеличит количество typing work для Lex/Fabric/Foundry/Scientist и сделает source contracts, snapshot bindings и semantic closure обязательной частью серьезного closeout. fileciteturn41file0L3-L3 fileciteturn44file0L3-L3 fileciteturn53file0L3-L3 fileciteturn55file0L3-L3

## Открытые вопросы и ограничения

Самое важное ограничение сессии в том, что через GitHub connector мне **не удалось напрямую извлечь именно файл** `policy-engine/docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md`. Поэтому исследование я строил на трех максимально близких и напрямую извлеченных основаниях: quoted C2 task из вашего запроса, active evidence-binding/scenario-authority plan от 2026-05-20 и archived policy-design-case implementation plan от 2026-05-19. Это дает сильную рамку, но формально остается несовпадением с requested document path. fileciteturn62file0L3-L3 fileciteturn24file0L3-L3

Проверка на первых десяти annotated cases опирается на реальный golden fixture и потому высоконадежна. Дополнительные двадцать пар — это **аналитически выведенный test matrix**, а не запущенный тестовый прогон по runtime. Я специально оформил их как proposal-level validation set, а не как “passed by code execution.” fileciteturn60file0L3-L3

Несмотря на это ограничение, главный результат устойчив: в текущем PolicyOS уже есть все ключевые строительные блоки, чтобы принять единый admissibility calculus без domain-specific hacks. Недостающий шаг — не изобретение новых сущностей с нуля, а **сведение existing support predicates, citation labels, authority envelopes, binding ledgers и portfolio rules в один явный decision contract** для research, governed и production authority. fileciteturn48file0L3-L3 fileciteturn49file0L3-L3 fileciteturn57file0L3-L3 fileciteturn59file0L3-L3

# Единая семантика closeout substrate для C3

## Ключевой вывод

В репозитории уже есть почти все составные части для ответа на вопрос **«можно ли закрыть run?»**, но они распределены по разным модулям и сегодня не сведены в один authority-preserving surface. Базовая архитектура уже говорит, что closeout должен опираться не на bundle, dashboard или public export, а на **связанный authority graph**: кто произвел доказательство, каким runtime event оно было порождено, где лежит CAS-артефакт, какой mode/schema/tenant/time/context его определили и какой downstream gate его потребляет. Если хоть один из этих ответов отсутствует, противоречив, projection-only, schema-incompatible или provenance-disallowed, система должна не «догадываться», а либо выдать typed blocker, либо явно понизить authority profile. fileciteturn92file0L3-L3

Поэтому для C3 логично принимать не «еще один checker», а **единый closeout substrate ADR**: `can_i_closeout(run_id)` должен быть **агрегирующим reader/enforcer**, а не новым producer of authority. Он должен собирать решения модулей formal invariants, CAS↔event reconciliation, attestation, source truth, semantic binding, metamorphic controls, performance/cost budget, schema/reader compatibility, run-state/phase barriers, approval/publication trust и public projection state в один детерминированный ответ, не скрывая module-specific evidence. Это согласуется с ADR-0150, где scorecard объявлен reader/enforcer, readiness — final closeout authority, approval — потребителем persisted readiness/scorecard identity, а projection surfaces прямо запрещено превращать в authority. fileciteturn76file0L3-L3

Самый важный практический вывод такой: **`closeout_compatibility.py` и `check_can_i_closeout.py` уже полезны, но покрывают только один узкий срез — deployed producer/reader/schema/git compatibility. Они не являются и не должны считаться полным closeout answer.** `check_can_i_closeout.py` лишь вызывает `build_closeout_compatibility_record_from_bundle_dir(...)`, а сам compatibility record проверяет git SHA, code revision и producer-reader matrix по quality reports и reader gates. Он не решает вопросы инвариантов, attestation, source truth, semantic binding, replay drift, approval authority или publication trust. fileciteturn65file0L3-L3 fileciteturn91file0L3-L3

## Что уже зафиксировано в коде и ADR

Слой formal invariants уже определен как closeout-critical. В `formal_invariants.py` зашиты пять обязательных closeout invariant ids: `authority_ordering`, `phase_barriers`, `same_input_closure`, `cas_event_reconciliation` и `terminal_readiness`. В registry `formal_invariant_specs.toml` эти инварианты явно описаны как substrate-critical, со statement, protected authority property, implementation scopes и negative tests. Это означает, что единый closeout answer не может обходить formal invariant coverage стороной и должен включать результат этих проверок как first-class input. fileciteturn90file0L3-L3 fileciteturn56file0L3-L3 fileciteturn64file0L3-L3

Авторитетная граница между runtime truth и projections тоже уже сформулирована. ADR-0150 требует, чтобы scorecard только читал и проверял evidence, readiness был финальным closeout authority, approval потреблял persisted scorecard/readiness identity, а dashboard и public artifacts оставались projection surfaces. Тот же запрет дублируется в `public_export.py` и `projection_semantics.py`: public export bundle и projection semantics прямо запрещают использовать себя для `runtime_closeout_authority`, `scorecard_authority` и `approval_authority`; допустимая роль для них — только `projection_only` или `not_authoritative`. fileciteturn76file0L3-L3 fileciteturn48file0L3-L3 fileciteturn49file0L3-L3

Семантическая и причинная целостность closeout тоже уже разложена по модулям. `authority.py` задает authority envelope contract, same-input closure и operator-facing root cause classification с полями `root_cause_class`, `owner`, `first_failing_artifact_ref`, `next_action`, `authority_failure_code`, `domain_failure_code` и `producer_component`. `authority_reconciliation.py` fail-closed проверяет биективность между CAS authority artifacts и durable diagnostic events, блокируя orphan CAS, orphan event, payload mismatch, tenant/run/job conflicts и event collisions. `event_log.py` в свою очередь закрепляет append-only corrective events для `supersede`, `withdraw`, `reconcile` и `quarantine`, то есть исторический смысл event не переписывается, а перекрывается новым reconciliation record. fileciteturn51file0L3-L3 fileciteturn53file0L3-L3 fileciteturn57file0L3-L3 fileciteturn89file0L3-L3 fileciteturn80file0L3-L3

Source-of-truth и semantic binding уже тоже сделаны как отдельные authority-preserving layers. `source_truth.py` и `source_truth_lattice.toml` определяют field families, их authoritative producers, allowed projection/package surfaces и typed losing-authority/conflict records. `semantic_binding.py` уже умеет «закрывать» semantic binding ledger и возвращать `reason_family`, `issue_codes`, `selected_evidence_refs`, `rejected_candidate_refs` и `blocker_refs`, то есть именно те объяснительные поля, которые нужны универсальному closeout substrate. ADR-0152 прямо требует semantic binding ledger или typed semantic blocker для каждого serious run. fileciteturn87file0L3-L3 fileciteturn88file0L3-L3 fileciteturn54file0L3-L3 fileciteturn67file0L3-L3 fileciteturn78file0L3-L3

Attestation, trustworthy boundaries и publication authority тоже уже не «в воздухе». `trust_boundaries.toml` помечает boundaries вроде `runtime_worker`, `cas_writer`, `scorecard_builder`, `readiness_aggregator`, `approval_packet_builder`, `dashboard_projection`, `public_export_renderer` и внешние gateways как `production_closeout_required = true`, со своими `failure_code` и `next_action`. ADR-0153 требует attestable evidence-generating steps для serious closeout, а ADR-0162 говорит, что publication authority не может возникать из dashboard/public packet/signing сами по себе; она должна выводиться из readiness, approval и honest diagnostics substrate. fileciteturn55file0L3-L3 fileciteturn79file0L3-L3 fileciteturn47file0L3-L3

Наконец, operator surface уже подсказывает, что один unified answer действительно нужен. Runbook `policy-design-case-operator-triage.md` требует в incident/closeout note сохранять `run id`, `job id`, `tenant`, `cell`, `scorecard`, `case`, `public-export`, `dashboard refs`, **first missing producer, owner, next diagnostic command**, а также distinction между `runtime-emitted`, `runtime-derived`, `projection-only`, `static inventory`, `manual assertion` и `out-of-scope by typed authority policy`. Это практически готовая спецификация объяснимого operator-facing closeout answer. fileciteturn70file0L3-L3

## Предлагаемая ADR closeout substrate

Рекомендуемая conceptual decision для C3 выглядит так:

`can_i_closeout(run_id) = invariants + event_reconciliation + attestation + source_truth + semantic_binding + metamorphic_controls + budget + schema_reader_compatibility + phase_barriers_run_state + approval_publication`

Эта формула хорошо соответствует уже принятому корпусу ADR: formal invariant coverage обязателен для closeout; scorecard не производит authority; readiness закрывает authority contract; approval не может превратить missing authority в authority; projection surfaces запрещено считать первичной truth; publication authority производна от runtime case и auditable evidence. fileciteturn64file0L3-L3 fileciteturn76file0L3-L3 fileciteturn47file0L3-L3

Ключевое архитектурное решение: **новый closeout substrate не должен хранить собственную "альтернативную истину"**. Он должен быть **derived, persisted, evidence-linked authority-consuming record**, который собирается из уже существующих runtime-owned records и возвращает одно итоговое решение плюс explainability payload. Это особенно важно, потому что `public_export.py` и `projection_semantics.py` уже fail-closed запрещают projection surfaces выступать как authority, а `approval.py` не разрешает override закрывать schema/identity/replay gaps. fileciteturn48file0L3-L3 fileciteturn49file0L3-L3 fileciteturn84file0L3-L3

Практически это стоит оформить как отдельный record, например `policyos.runtime.closeout_substrate.v1`, со следующими обязательными разделами: `decision`, `decision_class`, `blocking`, `typed_deficits`, `root_cause`, `first_failing_producer`, `code_revision`, `git_sha`, `reader_gate_versions`, `replay_refs`, `same_input_closure_refs`, `public_projection_state`, `publication_trust`, `module_results` и `next_diagnostic_commands`. Такой контракт будет не заменять scorecard/readiness/approval packet, а связывать их. Этим он повторит логику assurance-case layer из ADR-0153: объяснение поверх authority graph, но не его подмена. fileciteturn79file0L3-L3 fileciteturn92file0L3-L3

Иллюстративная форма ответа может выглядеть так:

```json
{
  "run_id": "<run>",
  "decision": "closeable | blocked_terminal | blocked_typed_deficit",
  "closeout_authority": "readiness_closed",
  "publication_state": "projection_only | publishable | published_blocked | published",
  "root_cause": {
    "class": "...",
    "first_failing_producer": "...",
    "first_failing_artifact_ref": "...",
    "next_action": "..."
  },
  "identity": {
    "same_input_closure_ref": "...",
    "scorecard_ref": "...",
    "approval_packet_ref": "...",
    "git_sha": "...",
    "code_revision": "...",
    "reader_gate_versions": {
      "scorecard": "...",
      "approval_packet_builder": "..."
    }
  },
  "module_results": {
    "formal_invariants": "...",
    "event_reconciliation": "...",
    "attestation": "...",
    "source_truth": "...",
    "semantic_binding": "...",
    "metamorphic_controls": "...",
    "budget": "...",
    "schema_reader_compatibility": "...",
    "phase_barriers": "...",
    "approval_publication": "..."
  },
  "typed_deficits": [],
  "terminal_codes": [],
  "evidence_refs": {
    "replay": [],
    "runtime_events": [],
    "cas_refs": []
  }
}
```

## Владение подрешениями и единый порядок вычисления

Владение лучше разложить строго по уже существующим module boundaries. **Formal invariants** должны принадлежать `formal_invariants.py` и registry `formal_invariant_specs.toml`, потому что именно там закреплены required closeout invariants и их evidence contracts. **Authority identity и root-cause classification** должны оставаться в `authority.py`, потому что этот модуль уже умеет классифицировать `root_cause_class`, `first_failing_artifact_ref` и `producer_component`. **CAS↔event reconciliation** должны оставаться за `authority_reconciliation.py` и `event_log.py`, потому что только они знают семантику orphan CAS/event, collision и append-only corrections. fileciteturn90file0L3-L3 fileciteturn56file0L3-L3 fileciteturn51file0L3-L3 fileciteturn53file0L3-L3 fileciteturn57file0L3-L3 fileciteturn89file0L3-L3

**Attestation** должна принадлежать trust-boundary layer: `trust_boundaries.toml` и `attestation.py`. С практической точки зрения closeout substrate не должен сам переоценивать boundary semantics; он должен просто требовать, чтобы все boundaries с `production_closeout_required = true` были verified или явно downgraded outside profile. **Source truth** должна принадлежать `source_truth.py` и `source_truth_lattice.toml`, потому что только этот слой знает authoritative surface для family-level drift и умеет оформлять losing-authority/conflict record. **Semantic binding** должен принадлежать `semantic_binding.py`, потому что именно он выдает `reason_family`, `selected/rejected/blocker refs` и не смешивает presence-семантику с relevance-семантикой. fileciteturn55file0L3-L3 fileciteturn79file0L3-L3 fileciteturn87file0L3-L3 fileciteturn88file0L3-L3 fileciteturn67file0L3-L3

**Metamorphic controls** должны оставаться за `metamorphic_controls.py`, потому что этот модуль уже моделирует anti-false-pass cases вроде `generic_metric_collapse`, `manifest_role_source_selection`, `generic_method_selection`, `no_norm_false_pass`, `data_present_but_irrelevant_pass` и `unsupported_final_claim`. **Budget** лучше расколоть на два подрешения: `performance_budget.py` для operational canary budget и `run_cost_proportionality.py` для policy-design proportionality/evidence budget. Это устранит текущую путаницу, где «performance/cost budget» в conceptual задаче выглядит как одна сущность, а в коде фактически распадается на runtime latency budget и authority-profile-scoped proportionality ledger. fileciteturn86file0L3-L3 fileciteturn85file0L3-L3 fileciteturn66file0L3-L3 fileciteturn63file0L3-L3

**Schema/reader compatibility** должна оставаться за `schema_compat.py` и `closeout_compatibility.py`. Но важно: `schema_compat.py` — это rule engine для compatibility decisions и blocking decisions (`legacy_quarantined`, `unknown_schema_blocked`, `incompatible_blocked`, `stale_schema_blocked`), а `closeout_compatibility.py` — это deployment-level matrix между producer schemas и active reader gates, плюс `git_sha`, `code_revision` и `reader_gate_version`. В unified answer эти два слоя должны идти рядом, но не сливаться. **Approval/publication** должны принадлежать `run_state.py`, `phase_barriers.py`, `approval.py`, `public_export.py`, `projection_semantics.py`, `external_audit.py` и core audit verifier. Именно они вместе отвечают за terminal readiness, publishability, projection-only labeling и replayable public audit state. fileciteturn58file0L3-L3 fileciteturn65file0L3-L3 fileciteturn59file0L3-L3 fileciteturn60file0L3-L3 fileciteturn83file0L3-L3 fileciteturn84file0L3-L3 fileciteturn48file0L3-L3 fileciteturn49file0L3-L3 fileciteturn69file0L3-L3

Сам closeout substrate должен выполнять подрешения в таком порядке: сначала **identity and invariants**, затем **reconciliation and attestation**, затем **semantic/source truth**, затем **budget/compatibility**, затем **phase/readiness/approval/publication**. Это важно, потому что многие более поздние слои не имеют права интерпретировать evidence, если earlier identity/authority checks уже failed. Такой порядок напрямую соответствует логике ADR-0150, ADR-0151, ADR-0154, ADR-0155 и formal invariant specs. fileciteturn76file0L3-L3 fileciteturn77file0L3-L3 fileciteturn80file0L3-L3 fileciteturn81file0L3-L3 fileciteturn56file0L3-L3

## Терминальные коды и typed deficits

Базовое правило, которое уже читается из ADR и кода, такое: **если репозиторий явно не разрешает accepted deficit для данного family/profile, failure должен считаться terminal for closeout or at least closing-blocking**. Это следует из ADR-0150, ADR-0151, ADR-0155 и approval logic: missing authority, incompatible schema, projection-as-authority, unverifiable scorecard identity, cross-surface conflict и unexplained/unbounded replay drift не могут быть «смягчены» override’ом. В `approval.py` это выражено буквально через non-overridable schema reasons, non-overridable identity reasons и replay reasons. fileciteturn76file0L3-L3 fileciteturn77file0L3-L3 fileciteturn81file0L3-L3 fileciteturn84file0L3-L3

К терминальным closeout codes я бы отнес, как минимум, все случаи из следующих семейств: `unknown_schema_blocked`, `incompatible_blocked`, `stale_schema_blocked`, `legacy_quarantined`; `scorecard_identity_not_verified`, `scorecard_identity_ref_missing`, `scorecard_identity_ref_mismatch`, `scorecard_projection_not_authority`; `replay_drift_unexplained`, `replay_drift_unbounded`; authority-class failures типа projection/packaging/spoofed/borrowed envelope; reconciliation failures вроде `authority_orphan_cas`, `authority_cas_missing`, `authority_payload_mismatch`, `authority_event_collision`, `authority_tenant_conflict`; source-truth conflicts по families `runtime_refs`, `scorecard_identity_and_gates`, `approval_readiness_public_status`; а также phase barrier / terminal readiness violations, где `READINESS_CLOSED` и verified scorecard identity отсутствуют. Все эти failure classes либо прямо fail-close’ятся в коде, либо объявлены как non-overridable в ADR и invariant specs. fileciteturn84file0L3-L3 fileciteturn53file0L3-L3 fileciteturn57file0L3-L3 fileciteturn88file0L3-L3 fileciteturn59file0L3-L3 fileciteturn56file0L3-L3

Typed deficits, наоборот, должны быть **узким allowlist**, а не универсальным escape hatch. Репозиторий прямо допускает их, по сути, только в двух хорошо задокументированных зонах. Первая — **claim/assurance deficits** для exploratory/research profiles: ADR-0161 разрешает accepted deficits для claims, но требует, чтобы они были видимы downstream surfaces и не апгрейдились молча до governed/production authority. Вторая — **proportionality/cost deficits**: ADR-0164 разрешает low-impact или research-profile runs принимать proportionality deficits только если named, profile-permitted и с явной блокировкой downstream claims/publication states; `run_cost_proportionality.py` также поддерживает typed blockers/records вместо молчаливого pass’а. Для остальных семей допустим не deficit, а только typed blocker или downgrade of authority profile. fileciteturn62file0L3-L3 fileciteturn63file0L3-L3 fileciteturn66file0L3-L3

Именно поэтому универсальный closeout answer должен содержать не только `terminal_codes`, но и отдельный массив `typed_deficits` с полями вроде `deficit_family`, `accepted_by_authority_profile`, `accepted_by_record_ref`, `blocks_profiles`, `visible_on_surfaces` и `residual_risk`. Без этого accepted deficit снова превратится в скрытую «weak pass». Это полностью соответствует логике ADR-0161/0164 и operator triage runbook, где out-of-scope/accepted-policy cases должны быть видимы и не маскироваться под отсутствие evidence. fileciteturn62file0L3-L3 fileciteturn63file0L3-L3 fileciteturn70file0L3-L3

## Как включить audit verifier и publication trust без подмены authority

Самый тонкий вопрос в C3 — не «есть ли audit verifier», а **какую власть имеет его вывод**. По коду и ADR ответ однозначный: verifier и external audit — это **required publication-trust input**, но не источник runtime authority. `AuditPackageVerifier` проверяет package integrity, CAS integrity, signatures, provenance, completeness и SLSA. `external_audit.py` уже строит public audit archive record только из verified core audit package и требует, чтобы `overall_status` был `PASS`, archive был verifiable without private operator context, а exported refs были публично проверяемы. Но ADR-0162 прямо говорит, что audit bundle, dashboard state или public packet **не могут mint authority, которого runtime case не имел**. fileciteturn68file0L3-L3 fileciteturn69file0L3-L3 fileciteturn47file0L3-L3

Следовательно, в unified answer audit verifier нужно включать не как замену scorecard/readiness/approval, а как отдельное подрешение `publication_trust.external_audit`. Его статус должен влиять на поля `publishable`, `public_projection_state`, `client_local_export_allowed` и `public_archive_replayable`, но он не должен закрывать дыры в authority envelope, same-input closure, schema compatibility, attestation или approval identity. Иначе система нарушит и ADR-0150, и ADR-0162. fileciteturn76file0L3-L3 fileciteturn47file0L3-L3

Практически это означает такую норму ADR:  
**runtime authority envelope → scorecard/readiness/approval authority → publication trust augmentation → projection/public export labeling**.  
Не наоборот. Public export уже специально маркируется как `projection_only`, а projection semantics требуют `may_not_be_used_for` как минимум для `scorecard_authority` и `runtime_closeout_authority`. Поэтому audit verifier должен улучшать trust of publication, но не исправлять authority deficits задним числом. fileciteturn48file0L3-L3 fileciteturn49file0L3-L3

## Операторская модель решения

Оператору нужен не набор разрозненных JSON, а один answer surface с сохранением глубины. Лучший вариант — сделать top-level ответ коротким и explainable: `decision`, `why`, `who owns the fix`, `what is the first failing producer`, `what evidence refs prove it`, `what is the next command`. Эта форма уже фактически предписана operator runbook. При этом модульные детали должны не теряться, а уходить в `module_results.*`. fileciteturn70file0L3-L3

Для этого я бы рекомендовал, чтобы обязательные operator-facing поля были такими: `root_cause_class` и `first_failing_artifact_ref` из `authority.py`; `first_failing_producer` и `producer_component`; `same_input_closure_ref`, `effective_mode_ref`, `degradation_ledger_ref`; `replay_refs` и replay status; `git_sha` и `code_revision` из closeout compatibility; `reader_gate_version` и `schema_compatibility_decision`; `scorecard_ref`, `approval_packet_ref`, `publication_trust_ref`; `primary_public_projection_state` и `public_export_status`; `terminal_codes`; `typed_deficits`; `next_diagnostic_commands`. Большая часть этих полей уже существует по отдельности в codebase — задача C3 именно в том, чтобы свести их в один conceptual surface. fileciteturn53file0L3-L3 fileciteturn51file0L3-L3 fileciteturn65file0L3-L3 fileciteturn49file0L3-L3 fileciteturn70file0L3-L3

Если формулировать decision model совсем коротко, то он должен отвечать на три разных вопроса, но в одном payload:  
**можно ли закрыть run как authority case; можно ли его одобрить; можно ли его публиковать; и если нет — из-за чего именно первым сломалось дерево authority.**  
Сегодня эти ответы разбросаны между run state, scorecard, approval, projection/public export и audit layers. C3 должен сделать из них один ответ, но не одну «среднюю температуру». fileciteturn59file0L3-L3 fileciteturn76file0L3-L3 fileciteturn47file0L3-L3

## Ограничения и открытые вопросы

В доступном GitHub-снапшоте я опирался на **accepted ADRs, runtime quality modules, trust lattice/registry files, archived implementation plan и operator runbook** как на первичные источники для C3. Именно они дают достаточно материала, чтобы спроектировать unified closeout substrate, даже если текущий репозиторий еще не содержит одного готового `can_i_closeout(run_id)` authority answer. Наиболее близкий плановый scaffold, который я смог верифицировать, — archived implementation plan от 2026-05-19; он прямо требует, чтобы final deterministic closeout доказывал inspect/replay/audit semantics без private operator context и чтобы dashboard/API/public surfaces only read and label authority. fileciteturn75file0L3-L3

Самые важные незакрытые вопросы для следующего ADR-шага такие. Во-первых, нужно явно решить, **кто materializes final closeout record**: readiness layer или отдельный closeout substrate reader поверх readiness. По текущим ADR я бы выбирал второе, чтобы не размывать границу «readiness closes authority» и «closeout assembles explanation». Во-вторых, нужен формальный allowlist для `typed_deficits`; сейчас он концептуально хорошо виден для claims и proportionality, но не унифицирован в одном registry. В-третьих, стоит явно зафиксировать, будет ли closeout answer хранить только ссылки на module reports или еще и нормализованную summary-копию их verdicts. По духу substrate правильнее ссылка плюс minimal normalized verdict, а не полное дублирование report payloads. fileciteturn76file0L3-L3 fileciteturn62file0L3-L3 fileciteturn63file0L3-L3

# Универсальная грамматика фасетов для PolicyOS

## Контекст и метод

Я рассматриваю C4 как задачу не про «придумать новую абстракцию с нуля», а про выведение единой грамматики из уже существующих контрактов Trinity и Scientist. В коде это выглядит так: `ProblemFrame` фиксирует стабильный слой «что считается проблемой и успехом», `PolicySpec` описывает интервенции и их исполнимую семантику, а `PolicyCandidateSchema` добавляет rollout, бюджетирование, мониторинг, assumptions и harm-envelope вокруг уже собранного `TrinityBundle`. Иными словами, универсальная фасетная грамматика должна не заменять эти контракты, а дать им общий, нормализованный слой индексации и проектирования. fileciteturn64file0L3-L3 fileciteturn23file0L3-L3 fileciteturn26file0L3-L3

Для исследования я опирался на указанные якоря и прилегающие enum-блоки: `problem_frame.py`, `policy_spec.py`, `schema.py`, `objectives.py`, `critic.py`, `search.py`, `temporal_logic.py`, `policy_composition.py`, `game_design.py`, `mechanism_semantics.py`, `observation/contracts.py`, `challenge_factory.py`, `scenario_evidence_contract.py`, `output.py` и `fidelity.py`. В сумме это уже дает плотную кодовую базу фасетов: домены, нормативные каналы, жесткость ограничений, уровни политики, временную логику, режимы идентификации, стратегические каналы отклика, игровые представления, семантику механизмов, уровни fidelity, этапы policy-search и классы adversarial challenges. fileciteturn57file0L3-L3 fileciteturn42file0L3-L3 fileciteturn44file0L3-L3 fileciteturn60file0L3-L3 fileciteturn61file0L3-L3 fileciteturn63file0L3-L3 fileciteturn40file0L3-L3 fileciteturn33file0L3-L3 fileciteturn36file0L3-L3

## Что уже есть в коде как фасетный каркас

Уже существующий каркас surprisingly близок к универсальной грамматике. На уровне problem framing код уже типизирует `domain` через `ProblemDomain`, разделяет ограничения на `HARD` и `SOFT` через `ConstraintType`, а нормативные следствия политики канализирует через `NormativeOutcomeChannel`. Там же задаются арбитражные политики (`NormativeArbitrationPolicy`), режим сравнения (`NormativeComparisonMode`) и целевая величина правового сравнения (`NormativeComparisonTarget`). Это очень сильная база: у C4 не проблема «нет доменной модели», а проблема «нет одного фасетного слоя, который собирает эти модели в единый policy-design vocabulary». fileciteturn64file0L3-L3

На intervention- и evidence-стороне база тоже уже богата. `InterventionSpec` имеет `kind`, `target`, `schedule`, `target_population_type`, `identification_mode`, `strategic_response_expected` и `transmission_channels`; `PolicyCandidateSchema` добавляет `target_population.geography`, `eligibility_tags`, `compatible_transport_tags`, `transport_assumptions.source_context/target_context`, `budget_allocation`, `monitoring_plan`, `expected_harm_envelope` и неструктурированный `metadata`. При этом observation-layer уже типизирует `IdentificationMode`, `ObservationFamily`, `EntityScope`, `SourceConfidenceTier`, `MultiplexGraphLayerId` и `StrategicResponseChannel`. Это означает, что универсальная грамматика должна не изобретать новые оси, а собрать и разграничить уже существующие. fileciteturn23file0L3-L3 fileciteturn26file0L3-L3 fileciteturn27file0L3-L3 fileciteturn63file0L3-L3

На governance/execution-стороне каркас уже почти «фасетный». `PolicyLayerLevel` задает уровни композиции политики (`federal`, `state`, `local`, `organizational`), temporal layer задает `TemporalLogicFamily`, `TemporalExecutionSemantics`, `TemporalEvaluationScope` и `TemporalTimeDomain`, а search/runtime слой уже имеет `FidelityLevel`, `PolicySearchLevel`, `ObjectiveKind`, `ObjectiveDirection`, `ConstraintStatus`, плюс challenge-фабрику с обязательными `ChallengeClass`. Это важно потому, что C4 не должен смешивать substance facets с execution/search facets: оба класса нужны, но они должны жить в разных ветках грамматики. fileciteturn42file0L3-L3 fileciteturn44file0L3-L3 fileciteturn45file0L3-L3 fileciteturn40file0L3-L3 fileciteturn33file0L3-L3 fileciteturn28file0L3-L3 fileciteturn36file0L3-L3

Самый важный кодовый симптом будущей проблемы — перегрузка `intervention.kind`. В `PolicySpec` это поле описано как «mechanism type», но в `ObjectiveStack`/search-логике именно из `intervention.kind` и candidate metadata собирается `policy_family`. То есть механизм исполнения уже начинает играть роль policy facet, хотя это другой вопрос. Для C4 это прямой сигнал: `mechanism_kind` и `instrument_type` должны быть разными фасетами, иначе поиск и аналитика будут путать способ исполнения с типом политического инструмента. fileciteturn23file0L3-L3 fileciteturn29file0L3-L3 fileciteturn33file0L3-L3

## Предлагаемая универсальная грамматика фасетов

Мой вывод: C4 should land not as one flat enum list, а как составная грамматика с жестким разделением между substance facets, governance facets, execution facets и risk facets.

```yaml
universal_policy_facets:
  domain:
    problem_domain: ProblemDomain

  objectives:
    normative_outcome_channels: [NormativeOutcomeChannel]
    constraint_hardness: ConstraintType
    objective_kind: ObjectiveKind
    objective_direction: ObjectiveDirection

  instrument:
    instrument_type: controlled_vocab
    mechanism_kind: InterventionSpec.kind
    delivery_channel: [controlled_vocab]
    funding_channel: [controlled_vocab]
    authority_type: [controlled_vocab]

  targeting:
    target_population_type: controlled_vocab
    geography: optional_string_or_id
    sector_ids: [id]
    region_ids: [id]
    eligibility_tags: [controlled_vocab]

  governance:
    policy_layer_level: PolicyLayerLevel
    override_mode: PolicyOverrideMode
    compatibility_mode: PolicyCompatibilityMode

  temporal:
    logic_family: TemporalLogicFamily
    execution_semantics: TemporalExecutionSemantics
    evaluation_scope: TemporalEvaluationScope
    time_domain: TemporalTimeDomain
    finite_horizon: optional_int

  evidence:
    identification_mode: IdentificationMode
    observation_family: ObservationFamily
    source_confidence_tier: SourceConfidenceTier
    transport_context: {source_context, target_context}

  strategy:
    strategic_response_channels: [StrategicResponseChannel]
    mechanism_representation: MechanismGameRepresentation
    mechanism_constraint_types: [MechanismConstraintType]
    revelation_mode: MechanismRevelationMode
    outcome_mode: MechanismOutcomeMode

  execution:
    fidelity_level: FidelityLevel
    search_level: PolicySearchLevel

  risk:
    risk_type: controlled_vocab
    severity: existing_string
    challenge_class: optional ChallengeClass
```

Эта раскладка естественно вытекает из существующих контрактов. `domain`, `normative_outcome_channels`, `constraint_hardness`, `policy_layer_level`, `evaluation_scope`, `identification_mode`, `strategic_response_channels`, `mechanism_representation`, `fidelity_level` и `search_level` уже имеют enum-ядро в коде. Главное, что grammar должна делать их composable и orthogonal: домен не должен предопределять тип инструмента; policy layer не должен подменять legal authority; поведенческий transmission channel не должен подменять административный delivery channel. fileciteturn64file0L3-L3 fileciteturn42file0L3-L3 fileciteturn44file0L3-L3 fileciteturn45file0L3-L3 fileciteturn63file0L3-L3 fileciteturn60file0L3-L3 fileciteturn61file0L3-L3 fileciteturn40file0L3-L3 fileciteturn33file0L3-L3

Отсюда следуют три design rules, без которых C4 будет brittle. Во-первых, `instrument_type` должен быть отдельным каноническим фасетом поверх `InterventionSpec.kind`, а не синонимом `kind`. Во-вторых, `delivery_channel` надо держать отдельно от `transmission_channels`: текущие `StrategicResponseChannel` описывают поведенческий или экономический канал адаптации (`budget`, `procurement`, `labor`, `trade`, `household_income`, `compliance`), но не канал административной доставки меры. В-третьих, `authority_type` должен быть отдельным фасетом поверх текущих `jurisdiction`, `authority_scope`, `fiscal_authority_refs`, `implementation_agency_refs` и `PolicyLayerLevel`, потому что уровень власти и тип правового основания — это разные разрезы. fileciteturn23file0L3-L3 fileciteturn63file0L3-L3 fileciteturn48file0L3-L3 fileciteturn42file0L3-L3

## Контролируемые словари для открытых полей

Для `instrument_type` я бы рекомендовал короткий, кросс-доменный и mutually exclusive vocabulary, который не дублирует уже существующие enums: `tax`, `subsidy_grant`, `transfer_voucher`, `loan_credit_guarantee`, `procurement_contract`, `price_control`, `quota_permit`, `mandate_standard`, `inspection_enforcement`, `information_nudge`, `service_provision`, `infrastructure_investment`, `governance_process`, `emergency_restriction`. Это покрывает fiscal, social, labor, healthcare, education, infrastructure, regulatory, environmental и trade cases без доменных адаптеров, а еще снимает текущую перегрузку `kind` как proxy для `policy_family`. fileciteturn23file0L3-L3 fileciteturn29file0L3-L3 fileciteturn33file0L3-L3

Для `delivery_channel` нужен vocabulary административной доставки, а не поведения агентов: `tax_system`, `bank_transfer`, `voucher_card`, `payroll`, `utility_bill`, `digital_portal`, `procurement_tender`, `permit_licensing`, `inspection_visit`, `school_system`, `clinic_provider`, `employer_intermediary`, `local_government_office`, `customs_border`, `public_works_contract`. Это поле в якорных контрактах не типизировано как first-class facet, и именно поэтому его нельзя алиасить к `StrategicResponseChannel`. Текущее ядро различает только каналы стратегической адаптации и rollout/monitoring, но не канал административного доведения меры до адресата. fileciteturn63file0L3-L3 fileciteturn26file0L3-L3

Для `funding_channel` словарь должен быть orthogonal к budget amount и budget constraint: `general_budget`, `earmarked_tax`, `social_insurance_fund`, `intergovernmental_transfer`, `donor_grant`, `concessional_loan`, `revolving_fund`, `public_private_partnership`, `user_fee`, `off_budget_entity`, `central_bank_balance_sheet`, `contingent_liability_guarantee`. Важно, что current code already models *how much* through `BudgetAllocationEntry` and policy-budget constraints, но не *откуда берутся деньги* как самостоятельную фасетную ось. Поэтому `funding_channel` должен быть новым controlled vocabulary, а не derived field из `budget_allocation`. fileciteturn26file0L3-L3 fileciteturn29file0L3-L3 fileciteturn31file0L3-L3

Для `authority_type` оптимальная номенклатура такая: `statute_primary_law`, `regulation_secondary_law`, `executive_order`, `agency_rule`, `budget_appropriation`, `grant_agreement`, `procurement_contract`, `license_permit`, `guidance_standard`, `treaty_international_commitment`, `emergency_power`, `organizational_policy`. Это нужно потому, что сегодня authority semantics рассыпаны по `jurisdiction`, `authority_scope`, `fiscal_authority_refs`, `implementation_agency_refs` и policy layering. Такая декомпозиция useful для валидации, но плоха для universal design search, где нужен один нормализованный фасет правового основания. fileciteturn48file0L3-L3 fileciteturn42file0L3-L3

Для `risk_type` нужен не severity-like словарь, а bridge vocabulary между evaluation, deterministic criticism и adversarial challenge generation. Я рекомендую минимум следующий canonical set: `budget_fiscal`, `equity_distribution`, `transport_external_validity`, `identification_overlap`, `evidence_conflict`, `evidence_staleness`, `citation_integrity`, `legal_authority`, `privacy_pii`, `strategic_gaming`, `implementation_complexity`, `ambiguity_human_review`, `hard_constraint_binding`, `monitoring_reversibility`. Сегодня часть этого already lives in `failure_type`, часть — в `ChallengeClass`, а часть — только в свободных `PolicyRiskNote` и `metadata`. Именно это и делает поле `risk_type` обязательным компонентом C4. fileciteturn31file0L3-L3 fileciteturn32file0L3-L3 fileciteturn36file0L3-L3 fileciteturn68file0L3-L3

Отдельно отмечу adjacent gaps, которые уже активны в коде и тоже просят нормализации: `target_population_type` в `InterventionSpec` и `LexProvisionDirective`, `beneficiary_class` и `instrument_type` в `ScenarioEvidenceRequirement`, а также `policy_family`, `evidence_depth` и `interpretability_score` в candidate metadata. Формально это не все поля из user prompt, но practically именно они будут размывать UFG, если их не привести к controlled vocabularies или derived enums. fileciteturn23file0L3-L3 fileciteturn66file0L3-L3 fileciteturn48file0L3-L3 fileciteturn29file0L3-L3 fileciteturn33file0L3-L3

## Согласование риск-фасетов с ConstraintCritic и challenge factory

`ObjectiveStack` уже разделяет `primary`, `hard_constraints`, `secondary` и `penalties`; `ConstraintCritic` поверх этого запускает deterministic validators (`budget`, `legal`, `equity`, `privacy`, `pii_check`, `transportability_required`) и добавляет собственные failure types вроде `budget_overrun`, `transport_break`, `fragile_assumption`, `binding_hard_constraint` и `hard_constraint_violated`. Отдельно challenge-фабрика требует фиксированный набор adversarial classes, включая `source_contradiction`, `stale_source`, `forged_citation`, `missing_transportability_assumption`, `fairness_threshold_reversal`, `legal_exception`, `policy_gaming_strategic_response`, `budget_infeasibility` и `ambiguous_human_review_instruction`. Значит, `risk_type` должен быть слоем согласования, а не еще одной objective axis. fileciteturn28file0L3-L3 fileciteturn29file0L3-L3 fileciteturn30file0L3-L3 fileciteturn31file0L3-L3 fileciteturn32file0L3-L3 fileciteturn36file0L3-L3

| Канонический `risk_type` | Сигналы в `ConstraintCritic` / evaluation | `ChallengeClass` | Вывод |
|---|---|---|---|
| `budget_fiscal` | `budget_overrun`, `budget_driver`, `policy_budget_constraint` | `BUDGET_INFEASIBILITY` | Хорошо согласуется; можно маппить deterministically. fileciteturn31file0L3-L3 fileciteturn36file0L3-L3 |
| `transport_external_validity` | `transport_break`, `overlap_not_assessed`, transport constraint | `MISSING_TRANSPORTABILITY_ASSUMPTION` | Почти полное покрытие, но positivity/overlap и transport assumptions надо сводить в один канонический риск. fileciteturn31file0L3-L3 fileciteturn36file0L3-L3 |
| `equity_distribution` | equity findings, harmed subgroup traces, equity constraint | `FAIRNESS_THRESHOLD_REVERSAL` | Семантически близко, но challenge class уже уже, чем реальный equity risk. fileciteturn31file0L3-L3 fileciteturn32file0L3-L3 fileciteturn36file0L3-L3 |
| `legal_authority` | legal pass findings, governance blockers | `LEGAL_EXCEPTION` | Полное и чистое согласование. fileciteturn31file0L3-L3 fileciteturn36file0L3-L3 |
| `strategic_gaming` | strategic-response semantics, mechanism-design IC constraints | `POLICY_GAMING_STRATEGIC_RESPONSE` | Концептуально согласуется, но требует bridge от `StrategicResponseChannel` и mechanism design к единому risk facet. fileciteturn23file0L3-L3 fileciteturn60file0L3-L3 fileciteturn36file0L3-L3 |
| `evidence_conflict` / `evidence_staleness` / `citation_integrity` | не ядро `ConstraintCritic`, но challenge registry уже это требует | `SOURCE_CONTRADICTION`, `STALE_SOURCE`, `FORGED_CITATION` | Это готовые canonical subtypes для evidence-risk слоя. fileciteturn36file0L3-L3 |
| `privacy_pii` | `privacy`, `pii_check` validators | отдельного challenge class нет | Это реальный gap: critic видит риск, challenge registry его отдельно не типизирует. fileciteturn31file0L3-L3 fileciteturn36file0L3-L3 |
| `ambiguity_human_review` | review/compliance ambiguity surfaced later in the pipeline | `AMBIGUOUS_HUMAN_REVIEW_INSTRUCTION` | Хорошо подходит для governance-facing risk facet. fileciteturn36file0L3-L3 |
| `implementation_complexity` | `simplicity`, `administrative_feasibility`, implementation penalty | отдельного challenge class нет | Это второй заметный gap: риск есть в objective space, но не в challenge taxonomy. fileciteturn29file0L3-L3 |

Главный практический вывод отсюда такой: canonical `risk_type` должен быть шире `ChallengeClass` и стабильнее `failure_type`. `failure_type` — это детерминированный operational signal; `ChallengeClass` — adversarial testing class; `risk_type` — cross-layer design facet, который связывает policy authoring, evaluation, criticism, challenge generation и downstream reporting. Если этого слоя не добавить, фасетная грамматика останется разорванной между runtime и eval toolchains. fileciteturn31file0L3-L3 fileciteturn36file0L3-L3 fileciteturn68file0L3-L3

## Насыщение фасетного корпуса и покрытие по доменам

Мой saturation verdict такой. Полностью насыщенные, уже enum-backed оси: `problem_domain`, `normative_outcome_channel`, `constraint_hardness`, `policy_layer_level`, `temporal_logic_family`, `temporal_evaluation_scope`, `identification_mode`, `strategic_response_channel`, `mechanism_profile`, `fidelity_level`, `search_level`. Частично насыщенные — то есть уже есть typed anchors, но нет controlled vocabulary или есть перегрузка semantics: `instrument_type`, `target_population_type`, `authority profile`, `funding profile`, `policy_family`, `evidence_depth`, `interpretability_score`. Недонасыщенная и требующая явного канонического поля ось — `risk_type`, потому что сейчас она рассыпана между `failure_type`, `ChallengeClass`, severity strings и free-form notes/metadata. fileciteturn64file0L3-L3 fileciteturn23file0L3-L3 fileciteturn26file0L3-L3 fileciteturn29file0L3-L3 fileciteturn42file0L3-L3 fileciteturn44file0L3-L3 fileciteturn63file0L3-L3 fileciteturn68file0L3-L3

Требование «не меньше 8 доменов без domain adapters» по сути уже выполнимо на текущем baseline. `ProblemDomain` прямо включает `fiscal`, `monetary`, `social`, `environmental`, `labor`, `healthcare`, `education`, `infrastructure`, `regulatory`, `trade` и `custom`. То есть не восемь, а десять built-in policy domains уже присутствуют как одна ось. Если поверх них положить orthogonal facets из C4 — instrument, delivery, funding, authority, constraints, temporal scope, evidence profile и risk profile — один и тот же grammar-shaped candidate сможет описать налоговый кредит, тарифную меру, образовательный грант, природоохранный стандарт, labor-market subsidy, healthcare outreach, infrastructure investment и regulatory mandate без написания отдельных адаптеров на домен. fileciteturn64file0L3-L3 fileciteturn23file0L3-L3 fileciteturn42file0L3-L3 fileciteturn44file0L3-L3

Evidence-side saturation тоже поддерживает этот вывод. В observation contracts уже есть семейства наблюдений `budget_flows`, `procurement_flows`, `macro_state`, `firm_fundamentals`, `trade_exposure`, `labor_market`, `household_distribution`, `distress_enforcement`, `public_service_domain_flows`, `education_human_capital_supply`, `construction_capital_formation` и `logistics_friction`. Это означает, что даже доказательная и измерительная подложка системы уже организована мультидоменным способом; проблема снова не в отсутствии доменного охвата, а в отсутствии одного universal facet layer поверх него. fileciteturn63file0L3-L3

Если формулировать saturation report кратко: базовый enum corpus уже достаточно зрелый для UFG v1; наиболее опасные источники хрупкости — перегрузка `intervention.kind`, свободные strings в audience/authority/population semantics, отсутствие явного `delivery_channel`, отсутствие явного `funding_channel` и отсутствие единого `risk_type`. Поэтому правильный scope C4 — не «добавить еще много enums», а «вынести существующие enums в опорную grammar и закрыть пять открытых фасетных дыр controlled vocabularies». fileciteturn23file0L3-L3 fileciteturn26file0L3-L3 fileciteturn29file0L3-L3 fileciteturn31file0L3-L3 fileciteturn36file0L3-L3

## Итоговое мемо

Мое итоговое заключение: PolicyOS уже имеет достаточно сильную code-informed основу для **Universal Facet Grammar**. Лучший дизайн — это не плоский список полей и не доменные адаптеры, а единая grammar с десятью уже насыщенными enum-осями и пятью controlled-vocabulary осями, которые надо явно поднять в первый класс: `instrument_type`, `delivery_channel`, `funding_channel`, `authority_type`, `risk_type`. При этом `mechanism_kind` надо сохранить как execution facet, `PolicyLayerLevel` — как governance-layer facet, а `TemporalEvaluationScope` и `FidelityLevel` — как execution/search facets. Самая важная новая норма для C4: `risk_type` должен стать bridge-фасетом между objective extraction, deterministic criticism, challenge generation и human-facing policy outputs. В таком виде taxonomy удовлетворяет acceptance criterion: она охватывает более восьми доменов, не требует domain adapters и не дублирует существующие governance enums, а собирает их в одну универсальную, расширяемую грамматику. fileciteturn64file0L3-L3 fileciteturn23file0L3-L3 fileciteturn42file0L3-L3 fileciteturn44file0L3-L3 fileciteturn40file0L3-L3 fileciteturn31file0L3-L3 fileciteturn36file0L3-L3

# Исследование C5 для PolicyOS

## Контекст и то, на что я опирался

Я не смог извлечь через доступный GitHub-коннектор именно файл `policy-engine/docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md`, поэтому это исследование построено на вашем тексте задачи C5 и на ближайших исходниках и архитектурных артефактах из репозитория `DenisKopylov/polisyos`: `ir/governance/temporal_logic.py`, `policy_spec.py`, `scientist/policy_design/critic.py`, `scientist/policy_design/search.py`, `scientist/evals/challenge_factory.py`, `docs/reference/scientist/reflexive-memory.md`, а также на документах `policy-design-best-in-class-operating-model.md`, `policy-design-case-decision-log.md`, `runtime/quality/policy_design_case.py` и `runtime/quality/case_lifecycle.py`. Эти артефакты уже задают рамку: serious run в PolicyOS должен завершаться не текстом и не “проекцией”, а runtime-owned Policy Design Case поверх assurance-case substrate; он должен быть append-only, owner-bound, profile-scoped и closeout-governed. fileciteturn56file0L3-L3 fileciteturn54file0L3-L3 fileciteturn55file0L3-L3 fileciteturn59file0L3-L3 fileciteturn61file0L3-L3

Из этого следует важная методологическая рамка для C5: исследование нельзя вести “как с чистого листа”. В репозитории уже есть две разные, но совместимые плоскости. Первая — формальная: temporal constraints встраиваются прямо в `PolicySpec`, а типизированный модуль temporal logic уже различает LTL, CTL и MTL, их execution semantics, evaluation scope, time domain и ограничения на формулы. Вторая — governance/runtime-quality: record families, owners, readiness gates, scorecard gates, lifecycle ledgers и append-only decision log уже заданы для Policy Design Case и должны быть переиспользованы, а не заменены отдельной “второй” системой правил. fileciteturn36file0L3-L3 fileciteturn43file0L3-L3 fileciteturn44file0L3-L3 fileciteturn59file0L3-L3 fileciteturn55file0L3-L3

## Что уже заложено в текущем framework

Внутренний формализм PolicyOS уже очень близок к тому, что нужно для C5. `TemporalPolicyConstraint` типизирован по `logic_family`, `execution_semantics`, `evaluation_scope`, `time_domain`, `clock_field`, `formula` и `finite_horizon`; валидатор принудительно связывает LTL с `finite_trace`, CTL с `branching_tree` и `branching_forecast`, а MTL — с `windowed_trace` и обязательным `finite_horizon`. Кроме того, CTL требует path quantifier, а `event_time` требует `clock_field`. Это не “общая идея”, а уже существующий контракт репозитория, поэтому temporal logic здесь действительно не гипотеза, а фактическая default surface для obligation rules. fileciteturn43file0L3-L3 fileciteturn44file0L3-L3

В policy-design loop уже существует детерминированный источник obligations-like signals. `ConstraintCritic` без LLM агрегирует проверки budget, legal, equity, privacy, pii, transportability, budget envelope, positivity/overlap и hard constraints; затем преобразует findings в typed failure cards и lesson cards, а также строит mutation hints. Сам search loop использует этот critic как early blocker для structure candidates, записывает rejection lessons и умеет поднимать transport assumptions и evidence assumptions в явный вид через hybrid seeds. Это означает, что для C5 не нужно изобретать новый канал извлечения candidate rules: deterministic critics, failure cards и lesson cards уже есть и уже образуют исторический корпус отказов и near-miss patterns. fileciteturn47file0L3-L3 fileciteturn48file0L3-L3 fileciteturn49file0L3-L3 fileciteturn50file0L3-L3 fileciteturn51file0L3-L3 fileciteturn30file0L3-L3 fileciteturn31file0L3-L3

Для adversarial and historical mining в репозитории уже есть и вторая половина нужного контура. Challenge factory умеет превращать failure cards и near-miss seeds в reviewed challenge candidates по фиксированной таксономии — source contradiction, stale source, forged citation, missing transportability assumption, hidden confounding/proxy trap, fairness threshold reversal, legal exception, strategic response, budget infeasibility и ambiguous human review instruction. При этом generation не равна admission: generated cases стартуют как `review_required`, hidden approval требует reviewer refs, а high-leakage cases не могут войти в hidden pack. Это даёт готовый материал для red-team replay и proof-before-promotion. Параллельно reflexive memory прямо говорит, что failure intelligence может быть переиспользована только как warnings/anti-patterns, а не как claim evidence, и влияние памяти должно быть видно в Research DAG. Для C5 это важный governance precedent: mined rules могут быть источником гипотез и coverage, но сами по себе не должны поднимать closeout authority. fileciteturn45file0L3-L3 fileciteturn46file0L3-L3 fileciteturn53file0L3-L3 fileciteturn52file0L3-L3

Наконец, runtime-quality слой уже задаёт форму governance metadata, которая почти напрямую переносится на obligation rules. `policy_design_case.py` требует record-family registry с applicability, producer owner, reader owner, schema name, scorecard gate, readiness check, enforcement function и maturity floor. `case_lifecycle.py` уже фиксирует append-only lifecycle ledger, допустимые lifecycle states, evidence refs, runtime event refs, stale-resolution semantics, ex-post learning, calibration и contamination controls. Decision log, в свою очередь, требует entry template с context, decision, owner, reversibility, revisit trigger, revisit wave и promotion status. В сумме это почти готовый governance envelope для obligation rules: статус, владелец, область действия, профили, доказательная база, версия, supersession и closeout effect в системе уже не экзотика, а устойчивый паттерн репозитория. fileciteturn59file0L3-L3 fileciteturn61file0L3-L3 fileciteturn55file0L3-L3

## Почему temporal logic должна остаться языком по умолчанию

Внешняя литература подтверждает, что это правильный default. На странице ACM Turing Award для Амира Пнуэли temporal logic описана как переломный способ рассуждать о программах как об execution paths во времени, а не только как о парах состояний; на странице Эдмунда Кларка temporal logic прямо связана с model checking и с формами высказываний вида “это условие остаётся истинным, пока не выполнится другое”. Это делает temporal logic естественным базовым языком для obligations, которые почти всегда формулируются как: “всегда”, “никогда”, “до того как”, “в течение окна”, “на всех ветках прогноза”, “должно сработать в итоге”. citeturn11view0turn10view1

Для практической formalization особенно важны property specification patterns. Исследования линии Dwyer показывают, что recurring requirement patterns можно систематически переводить между LTL, CTL и близкими формализмами, а pattern-based catalog снижает сложность записи свойств для non-expert users. Для C5 это означает, что “сокращение числа domain templates” не должно вести к росту сложности для авторов: наоборот, следует держать маленькое ядро governed rule patterns и parameterize их по контексту, scope и atoms. citeturn6academia0

Мой вывод такой: temporal logic должна остаться formal layer by default, но не должна нести на себе всё governance meaning. Репозиторий уже показывает правильное разделение обязанностей: temporal layer отвечает за формулу, trace/branch/window semantics и time domain; governance/runtime-quality слой отвечает за owner, authority, readiness, supersession, lifecycle и closeout. Иными словами, PolicyOS нужен **не новый язык вместо LTL/CTL/MTL**, а **двухслойный объект**: `TemporalRuleBody` + `RuleGovernanceEnvelope`. Это логически согласуется и с текущим `temporal_logic.py`, и с существующим Policy Design Case governance model. fileciteturn43file0L3-L3 fileciteturn44file0L3-L3 fileciteturn59file0L3-L3 fileciteturn61file0L3-L3

Практически это даёт такое разделение ролей. **LTL** должна быть главным default для обычных closeout and compliance traces на конечных исполненияx. **CTL** следует включать только там, где задан именно branching forecast question, потому что внутренний контракт PolicyOS уже жёстко связывает CTL с `branching_forecast`. **MTL** нужна для дедлайнов, SLA-like окон, monitoring grace periods и других bounded-window obligations, но только в контролируемом subset, потому что литература по MTL подчёркивает, что выразительность и разрешимость резко зависят от выбранного фрагмента и модели времени; это отлично совпадает с внутренним ограничением PolicyOS на `finite_horizon` и `windowed_trace`. fileciteturn44file0L3-L3 citeturn12academia0

## Карта классов обязательств к формальным паттернам

Ниже — рекомендуемое компактное ядро obligation patterns. Это именно те patterns, которыми стоит заменить большую часть domain templates.

- **`do_X`**: если обязанность безусловна, базовая форма — `F X`; если она активируется триггером, — `G(trigger -> F X)`; если есть дедлайн, — `G(trigger -> F_[0,d] X)`. В PolicyOS это естественно укладывается в LTL или MTL в зависимости от наличия окна. fileciteturn43file0L3-L3 fileciteturn44file0L3-L3

- **`dont_X`**: базовая safety/prohibition форма — `G ¬X`. Это лучший кандидат для closeout-blocking rules, когда нарушение само по себе является disqualifying event. fileciteturn43file0L3-L3 citeturn10view1turn11view0

- **`X_before_Y`**: если `Y` запрещён до выполнения `X`, то удобнее всего нормализовать это как “no Y until X”, например `¬Y W X` или эквивалентно через вспомогательный атом `done_X`: `G(Y -> done_X)`. Для PolicyOS это важно, потому что реальные rules часто касаются sequence gating — legal review before publication, calibration before promotion, monitoring plan before closeout. fileciteturn44file0L3-L3 fileciteturn54file0L3-L3

- **`eventually_Z`**: чистая liveness-обязанность `F Z`. Её не стоит автоматически делать blocking, если не задан deadline, authority profile и closeout effect: иначе правило будет трудно закрывать operationally. Это уже согласуется с общей логикой Policy Design Case, где readiness gates опираются не на абстрактную liveness, а на явные evidence paths и profile mapping. fileciteturn59file0L3-L3 fileciteturn55file0L3-L3

- **`always_P`**: инвариант `G P`. Это natural home для freshness, citation integrity, privacy, human-oversight clarity и других “не должно деградировать на всём trace” obligations. fileciteturn43file0L3-L3 fileciteturn53file0L3-L3

- **`until_condition`**: форма `P U Q` или bounded `P U_[a,b] Q`. Здесь чаще всего моделируется “режим должен сохраняться, пока не произойдёт разрешающее событие”, например “draft constraints remain in force until approved” или “manual review stays mandatory until hidden-admission reviewers present”. fileciteturn43file0L3-L3 fileciteturn46file0L3-L3

- **`branching forecast condition`**: использовать CTL только для ветвящихся прогностических требований, например `AG safe_state` для universal safety across forecast branches или `EF fallback_available` для требования существования хотя бы одной допустимой ветки восстановления. Внутренний валидатор PolicyOS уже требует для CTL и path quantifier, и `branching_forecast` scope, так что это должен быть специальный, а не общий режим. fileciteturn44file0L3-L3

- **`bounded-window monitoring`**: это MTL-паттерн типа `G(alert -> F_[0,72h] mitigation)` или `G(published -> F_[0,30d] reassessment_plan)`. Именно здесь MTL даёт наибольшую ценность, потому что obligation становится не просто eventual, а operationally monitorable. Но этот класс нужно держать в finite-horizon subset, что уже поддерживается внутренним контрактом. fileciteturn44file0L3-L3 citeturn12academia0

Из этого набора получается сильная архитектурная simplification: вместо domain templates по типу “украинская бюджетная проверка”, “регуляторная проверка для здравоохранения”, “проверка fairness для конкурса” следует хранить небольшой набор generic patterns, а domain specificity переносить в atoms, selectors, thresholds, jurisdiction/time scope и authority profile. В этом смысле шаблон должен определять **форму обязательства**, а не его предмет. Такой переход соответствует и property-pattern literature, и reuse-first posture самого репозитория. citeturn6academia0 fileciteturn57file0L3-L3

## Проект ADR жизненного цикла правила

Рекомендуемое решение для C5 — ввести **governed obligation rule object** из двух частей. Первая часть — `TemporalRuleBody`: `logic_family`, `execution_semantics`, `evaluation_scope`, `time_domain`, `clock_field`, `finite_horizon`, набор atoms/selectors и сама формула. Вторая часть — `RuleGovernanceEnvelope`: `rule_id`, `status`, `owner`, `reviewer_owner`, `scope`, `authority_profiles`, `closeout_effect`, `provenance`, `evidence_basis`, `version`, `supersedes`, `deprecated_by`, `effective_from`, `effective_until`, `source_failure_refs`, `challenge_pack_refs`, `critic_bindings`, `readiness_gate`, `scorecard_gate` и `last_validated_at`. Это прямое продолжение существующего стиля record-family registry и lifecycle-ledger в PolicyOS, а не новая параллельная модель. fileciteturn59file0L3-L3 fileciteturn61file0L3-L3 fileciteturn55file0L3-L3

Статусы я бы фиксировал так: `draft`, `shadow`, `candidate`, `active_non_blocking`, `active_blocking`, `deprecated`, `retired`, `superseded`. Переходы должны быть append-only; historical rewrite недопустим. Это не только хорошая governance practice, но и прямое соответствие уже существующему подходу в `case_lifecycle.py` и decision log. `shadow` нужен для LLM- и mining-derived rules; `candidate` — для правил, прошедших replay и review, но ещё не влияющих на closeout; `active_blocking` — только для правил, которые уже доказали стабильность и полезность на deterministic critics, historical failures и reviewed adversarial challenge packs. fileciteturn61file0L3-L3 fileciteturn55file0L3-L3 fileciteturn53file0L3-L3

Главное ADR-правило должно быть сформулировано жёстко: **ни одно obligation rule не может стать closeout-blocking, если у него нет `status`, `provenance`, `version`, `scope`, `owner` и `evidence_basis`**. Я бы даже сделал это отдельным deterministic validator. Логика проста: сам репозиторий уже не допускает серьёзные case records без owner, readiness gate, enforcement function, lifecycle evidence и append-only semantics; obligation rules, которые в будущем смогут блокировать closeout, должны подчиняться не менее строгим требованиям. Иначе система получит “скрытое право” блокировать serious run без того уровня auditability, который уже требует остальная Policy Design Case infrastructure. fileciteturn59file0L3-L3 fileciteturn61file0L3-L3 fileciteturn54file0L3-L3

`Provenance` для rule лучше нормализовать в четыре режима: `expert_seeded`, `prior_art_seeded`, `historical_failure_mined`, `llm_proposed`. `Evidence_basis` при этом должна быть не строкой, а typed set: `critic_replay`, `historical_replay`, `challenge_replay`, `human_review`, `external_standard`, `authority_profile_acceptance`. Такое разделение полезно потому, что в PolicyOS уже различаются warning-only reusable memory, reviewed challenge admission и runtime-owned closeout evidence; rule governance должно уметь показывать, за счёт какого именно типа доказательства правило было повышено. fileciteturn52file0L3-L3 fileciteturn53file0L3-L3 fileciteturn47file0L3-L3

Ещё один важный ADR-вывод: **deprecation и closeout effect нужно разделить**. Правило может оставаться исторически действительным и retrievable, но быть `deprecated` для новых closeouts; или наоборот, быть `active_non_blocking` и собирать telemetry, прежде чем стать `active_blocking`. Это полностью согласуется с существующим append-only case lifecycle и с тем, как challenge factory отделяет generation от admission. fileciteturn61file0L3-L3 fileciteturn46file0L3-L3

## Как сравнивать LLM-правила, детерминированные critics и исторические отказы

Я бы строил comparison pipeline не как “LLM против правил”, а как **общий replay harness над единым rule schema**. Экспертные правила, prior-art rules, mined historical rules и LLM-generated rules должны сначала быть приведены к одной нормальной форме: `TemporalRuleBody + RuleGovernanceEnvelope`. Только после такой нормализации их можно честно сравнивать. Это важно, потому что internal repo уже умеет нормализовать deterministic findings в failure cards и lesson cards, и именно эта нормализация должна стать основой rule mining, а не последующее сравнение свободного текста с кодом. fileciteturn48file0L3-L3 fileciteturn30file0L3-L3 fileciteturn31file0L3-L3

Практический protocol должен быть таким. Сначала эксперт ридинг и prior art задают небольшой seed set базовых patterns. Затем из `ConstraintCritic` извлекаются stable failure types и traces; из lesson registry — повторяющиеся anti-patterns; из challenge factory — challenge classes, которые доказали собственную полезность как adversarial surfaces. После этого LLM предлагается не “придумать произвольные obligations”, а **досинтезировать кандидатные rules** из уже существующих traces, challenge classes и gaps между expert seeds и historical failures. Иными словами, LLM — это proposer, а не authority source. fileciteturn47file0L3-L3 fileciteturn48file0L3-L3 fileciteturn45file0L3-L3 fileciteturn46file0L3-L3

Сравнение правил я бы делал по пяти метрикам. Первая — **critic agreement**: покрывает ли правило те же blocker/warning surfaces, что и deterministic critic. Вторая — **historical failure recall**: сколько известных failure cards и lesson patterns оно объясняет или ловит. Третья — **adversarial escape rate**: на скольких reviewed challenge cases rule срабатывает поздно, шумно или вовсе не срабатывает. Четвёртая — **false-positive pressure**: насколько rule начинает блокировать clean cases. Пятая — **governance completeness**: имеет ли rule достаточную provenance/evidence/versioning упаковку, чтобы вообще претендовать на promotion. Эта пятая метрика не менее важна, чем первые четыре, потому что в PolicyOS уже сейчас governance incompleteness сама по себе является closeout defect. fileciteturn54file0L3-L3 fileciteturn55file0L3-L3 fileciteturn59file0L3-L3

Ключевая policy рекомендация здесь очень жёсткая: **LLM-generated obligations никогда не должны перепрыгивать в blocking без промежуточного shadow/candidate этапа**. Это следует и из внутренней культуры reviewed admission для challenge packs, и из warning-only режима reflexive memory, и из того факта, что сам policy-design search уже ставит deterministic critic раньше mutation/reuse loops. Для C5 это означает: LLM-обязанности допустимы как источник coverage, но не как самостоятельное основание closeout authority. fileciteturn53file0L3-L3 fileciteturn52file0L3-L3 fileciteturn49file0L3-L3

## Первая governed taxonomy

Ниже — моя рекомендуемая **первая governed taxonomy**. Она нарочно маленькая и параметризуемая; её цель — заменить множество доменных шаблонов небольшим ядром правил, которое уже опирается на имеющиеся critics, challenge classes и lifecycle records.

**Legal and authority rules.** Сюда входят правила типа `OBL-LEGAL-VALIDITY` и `OBL-LEGAL-EXCEPTION-HANDLED`. Их canonical shape — `dont_publish_until_legal_basis` или `always(no_action_without_competence)`. Они прямо соответствуют existing legal critic surfaces и challenge class `legal_exception`. Для governed/production profiles я бы делал их blocking по умолчанию. fileciteturn47file0L3-L3 fileciteturn53file0L3-L3

**Evidence integrity rules.** Это `OBL-SOURCE-CONTRADICTION-RESOLVED`, `OBL-SOURCE-FRESHNESS`, `OBL-CITATION-INTEGRITY`. Их формы — `G(not contradiction_unresolved)`, `G(source_is_fresh)` и `G(not forged_citation)`. Они почти напрямую совпадают с challenge classes `source_contradiction`, `stale_source`, `forged_citation`, а значит дают immediate replay path через challenge factory. fileciteturn45file0L3-L3 fileciteturn53file0L3-L3

**Transport and identification rules.** Это `OBL-TRANSPORTABILITY-EXPLICIT` и `OBL-CONFOUNDING-PROXY-RISK-DISCLOSED`. Первая rule family должна требовать явной transport assumption before promotion; вторая — либо explicit proxy/confounding mitigation, либо visible deficit. Это уже отражено и в `transportability_required` critic, и в hybrid seed logic, которая специально поднимает transport assumptions в явный policy object. fileciteturn47file0L3-L3 fileciteturn48file0L3-L3 fileciteturn50file0L3-L3 fileciteturn51file0L3-L3

**Equity and harm rules.** Это `OBL-EQUITY-THRESHOLD-STABLE` и `OBL-NO-UNREVIEWED-SUBGROUP-HARM`. Их natural pattern — invariant or bounded recheck after threshold changes. Existing critic already emits equity findings and mutation hints about subgroup harm; challenge factory отдельно фиксирует `fairness_threshold_reversal`. Поэтому эта family должна быть частью первого governed ядра, а не поздней domain add-on. fileciteturn47file0L3-L3 fileciteturn48file0L3-L3 fileciteturn53file0L3-L3

**Feasibility and proportionality rules.** Это `OBL-BUDGET-FEASIBLE` и `OBL-BUDGET-WITHIN-ENVELOPE`. Rule form здесь чаще всего safety plus threshold window: не допустить overrun и явно пометить near-binding regime. Внутренний critic уже различает `budget_overrun`, `budget_driver`, hard constraints и positivity risk; следовательно, rule mining здесь можно начать не с LLM, а с deterministic failure types. fileciteturn47file0L3-L3 fileciteturn48file0L3-L3

**Strategic-response rules.** Это `OBL-STRATEGIC-RESPONSE-CONTAINED`, canonical form — универсальная safety across forecast branches или явно surfaced gaming assumption с blocking effect для high-authority profiles. В challenge taxonomy это уже есть как `policy_gaming_strategic_response`; значит, эта family должна стать governed rule, а не только benchmark scenario label. fileciteturn45file0L3-L3 fileciteturn53file0L3-L3

**Human oversight rules.** Это `OBL-HUMAN-REVIEW-INSTRUCTION-UNAMBIGUOUS` и `OBL-HUMAN-REVIEW-EFFECTIVE-BEFORE-HIDDEN_OR_PUBLIC_PROMOTION`. Здесь temporal pattern чаще всего “review before promotion” плюс bounded feedback windows. Внутренний operating model прямо требует измерять effective human oversight, а challenge taxonomy отдельно выделяет ambiguous human review instruction; поэтому эту family нельзя оставлять outside obligation kernel. fileciteturn57file0L3-L3 fileciteturn53file0L3-L3

**Lifecycle and reassessment rules.** Это `OBL-PUBLISHED-CASE-HAS-APPEND-ONLY-LIFECYCLE`, `OBL-STALE-CASE-RESOLVED`, `OBL-EX-POST-REASSESSMENT-LINKED` и `OBL-MEMORY-LEARNING-CLEAN`. Они уже фактически существуют как governed contracts в `case_lifecycle.py`: нужны append-only lifecycle events, resolution evidence, ex-post links, calibration refs и clean memory contamination checks. Поэтому для C5 я бы не создавал эти правила заново, а профилировал их как первую волю обязательств, прошедших путь от lifecycle contract к obligation rule. fileciteturn61file0L3-L3

Если свернуть эту таксономию до минимального “first governed set”, я бы стартовал с десяти rule families: legal validity, legal exception handling, source contradiction resolution, source freshness, citation integrity, transportability explicitness, confounding/proxy disclosure, equity stability, budget feasibility, human review unambiguity. Это уже достаточно мало, чтобы заменить большую часть доменных шаблонов, и достаточно близко к существующим critics/challenges, чтобы быть реплей-измеримым почти сразу. fileciteturn45file0L3-L3 fileciteturn47file0L3-L3 fileciteturn53file0L3-L3

## Открытые вопросы и ограничения

Самое большое ограничение этого исследования — недоступность через коннектор точного активного файла `POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md`. Поэтому я синтезировал ответ на основе вашего текста C5 и ближайших репозиторных источников, а не на основе полного текста указанного active plan.

По содержанию остаются три открытых вопроса. Первый: нужен ли поверх temporal logic отдельный deontic layer для permissions, waivers и contrary-to-duty cases, или достаточно governance envelope plus auxiliary atoms. Текущий репозиторий явно поддерживает temporal layer, но не показывает нативный deontic calculus. Второй: как именно маппить `active_blocking` obligation rules на authority profiles (`research`, `governed`, `production`) и scorecard gates; в репозитории это already-open governance theme, но для C5 его ещё надо закрепить на уровне конкретного rule registry. Третий: какие именно invariant specs вокруг rule promotion и closeout-blocking статусов должны стать формально проверяемыми, поскольку operating model уже требует lightweight formal specs для substrate-critical properties. fileciteturn57file0L3-L3 fileciteturn55file0L3-L3

Итоговый вывод у меня однозначный. Для PolicyOS C5 не должен превращаться в замену temporal logic, и не должен рождать новую независимую rule engine. Лучшее решение — оставить **LTL/CTL/MTL как formal language by default**, свести obligations к **малому parametrized pattern kernel**, а всё, что касается **status, provenance, owner, scope, authority, evidence basis, versioning, deprecation и closeout effect**, оформить как **runtime-owned append-only governed registry**, устроенный по тем же принципам, что уже лежат в Policy Design Case, decision log и lifecycle contracts. Именно это даст одновременно и формальность, и replayability, и auditability. fileciteturn43file0L3-L3 fileciteturn44file0L3-L3 fileciteturn55file0L3-L3 fileciteturn59file0L3-L3 fileciteturn61file0L3-L3

# Семантика concept spine для PolicyOS

## Контекст и главный вывод

В доступном GitHub-срезе репозитория `DenisKopylov/polisyos` тема C6 уже не выглядит как «пустое место»: архитектурные артефакты прямо описывают capability **concept spine and multi-jurisdiction reconciliation** как **wire-existing** capability, которая должна быть собрана поверх уже существующих поверхностей `fabric/entity_resolution`, `scientist/cross_graph`, `ir/linker`, `ir/analytics/cross_graph`, `normative_arbitration`, а не как новый изолированный subsystem. Самый сильный внутренний сигнал здесь такой: PolicyOS уже склоняется к **per-run concept/jurisdiction spine**, собранному на лету над существующими регистрами и результатами разрешения, а не к одному новому «глобальному master registry». fileciteturn35file0L1-L3 fileciteturn23file0L1-L3

Мой итоговый вывод: для C6 PolicyOS нужен не просто «словарь понятий», а **runtime-owned reconciled authority artifact**, который делает три вещи одновременно: фиксирует, *какие* концепты были сопоставлены между producer-ами; в *каком authority namespace* и при *каком scope tuple* это сопоставление допустимо; и *какие несовместимости* остаются first-class blockers до closeout. Это хорошо согласуется и с существующим evidence-spine подходом в runtime quality, и с operator triage, где missing spine / unresolved spine / incompatible concepts уже трактуются как closeout-blocking conditions. fileciteturn26file0L1-L3 fileciteturn29file0L1-L3 fileciteturn36file0L1-L3

## Что текущие примитивы уже решают и чего они не решают

Текущий стек PolicyOS уже закрывает несколько важных подзадач, но делает это **раздельно**. `EvidenceSpineCarrier` и propagation graph хранят `scenario_evidence_contract_id`, `requirement_ids`, producer/reader contract и проверяют, что producer не потерял контракт и requirement ids при проходе по пайплайну. Это очень сильная инфраструктура для **трассировки обязательств**, но она не кодирует, являются ли `policy term`, `metric id`, `dataset column`, `legal norm` и `method requirement` одним и тем же понятием, лишь связанными понятиями или конфликтующими понятиями. Иными словами, evidence spine фиксирует *что должно быть перенесено*, но не завершает *что это значит семантически*. fileciteturn26file0L1-L3 fileciteturn36file0L1-L3

`runtime/quality/semantic_binding.py` показывает, что runtime уже ожидает существование внешнего `spine_context`: builder заполняет `spine_id`, `spine_status`, `jurisdiction_id`, `blocked_by_spine`, candidate refs и blocker refs для producer-ов. Это означает, что semantic binding в текущем виде не является источником истины о концептной идентичности; он скорее **consumer resolved spine context**, а не механизм его первоначальной сборки. Следовательно, missing abstraction в C6 — это не ещё один closure checker, а **промежуточный reconciler**, который до semantic binding выносит решение по concept identity и authority. fileciteturn25file0L1-L3

На стороне Data/Fabric уже есть мощный механизм pairwise/admissibility matching. `fabric/catalog/source_selection_audit.py` умеет различать `selected_contract_bindings`, `rejected_contract_bindings`, `source_family_blockers`, проверять source facets, family admissibility, claim-bindability и переводить selected sources в режим либо `claim_admissible_contract`, либо `context_inventory`. Но это matching по source contracts и admissibility, а не семантическое решение о том, что, например, колонка `loan_count_qtr` эквивалентна policy term `program uptake`, либо что это только operationalization с потерями. fileciteturn40file0L1-L3

На стороне права `lex/normpack/applicability_report.py` уже умеет делать очень важные вещи: фильтровать нормы по jurisdiction, policy domain, as-of time, competence; выдавать selected/rejected norms; и строить per-claim legal anchoring. Но Lex по своей природе отвечает на вопрос «какая норма применима и почему», а не на вопрос «тождественен ли legal concept статистическому показателю или policy label». Это authority-critical, но не full cross-producer concept identity. fileciteturn33file0L1-L3

`foundry/validation/method_quality.py` решает reconciliation методических обязательств: serious expectations, analytical surfaces, uncertainty, transportability, missingness, heterogeneity, assumptions и validity surfaces. То есть Foundry знает, закрывает ли метод требуемую аналитическую обязанность. Но он не решает, что `method requirement` семантически эквивалентен `policy term` или `metric id`; максимум — что между ними есть obligation edge. Это другой тип связи. fileciteturn32file0L1-L3

`scholar/evidence.py` уже делает selected/rejected sources, support links, conflict links, freshness и provenance, а `scientist/cross_graph/compiler.py` использует `CanonicalConcept`, `ConceptBridge` и компилирует evidence needs через legal/dataset/academic channels. Это особенно важно: у системы уже есть внутренние зачатки понятийной канонизации и bridge-отношений. Но эти объекты пока живут в cross-graph evidence compilation, а не в едином run-level authority artifact, который бы замыкал все producer-ы и все claim-critical edges. fileciteturn31file0L1-L3 fileciteturn46file0L1-L3

Наконец, IR cross-graph уже умеет описывать `SCMFragment`, interface variables, interface mappings, composition policy и composition certificates. Это значит, что **SCM fragment composition** как аналитическая и causal подзадача у вас уже есть. Но composition of fragments не равна composition of concepts: два фрагмента могут быть технически совместимы по интерфейсам, но опираться на разные authority scopes для population, geography, time или legal meaning. Именно этот зазор и должен закрыть concept spine. fileciteturn42file0L1-L3

## Предлагаемая семантика concept spine

Я предлагаю определить **concept spine** как runtime-owned artifact, который фиксирует *claim-relevant semantic closure* между heterogenous producer-ами. В терминах структуры это должен быть не «список канонических терминов», а набор: `concept_nodes`, `authority_namespaces`, `mapping_edges`, `scope tuples`, `evidence_refs`, `decision provenance`, `blockers`, `closure status`. Такой artifact должен быть stable within run, reproducible from inputs and registries, и читаем semantic binding / scorecard / PDC closeout так же, как сегодня читаются evidence refs и authority envelopes. Это логически продолжает текущую архитектуру evidence spine и authority envelopes, которые уже мыслят serious evidence через runtime ownership, provenance, same-input closure и reader contracts. fileciteturn26file0L1-L3 fileciteturn37file0L1-L3

**Same concept** я рекомендую определить строго: два producer-артефакта выражают один и тот же concept only if у них совпадает референт **и** PolicyOS может доказать допустимую interchangeability при одном и том же `scope tuple` и в одном и том же `authority namespace`, либо через явно зафиксированный authority bridge. Важный внешний ориентир здесь — `owl:sameAs`: W3C трактует его как утверждение, что две URI “actually refer to the same thing” и имеют ту же identity; это очень сильная семантика. Для большинства cross-scheme сопоставлений в PolicyOS более уместен не `owl:sameAs`, а более осторожная градация наподобие SKOS mapping relations. citeturn7view0turn7view1turn7view2

**Related concept** — это связь, при которой concepts семантически связаны, но не взаимозаменяемы для claim closure. Практически это класс отношений вроде `broader`, `narrower`, `related`, `proxy_for`, `operationalizes`, `governs`, `measures`, `evidence_for`. SKOS полезен как внешний шаблон: `skos:relatedMatch`, `broadMatch`, `narrowMatch` специально отделены от `exactMatch`, и SKOS прямо запрещает смешивать `exactMatch` с `relatedMatch`/`broadMatch` как будто это одно и то же. Для PolicyOS это означает: related concept может поддерживать discovery, linking, literature support или transport rationale, но не может самостоятельно закрывать same-concept requirement. citeturn7view1turn7view3

**Conflicting concept** — это не просто “не совпало”, а положительно установленная несовместимость. Она возникает, когда два candidate mapping-а ведут к противоречащим obligations или incompatible scopes: например, legal term про “enterprise” mapped to dataset column about “establishment”; metric, измеряющий stock, пытаются выдать за flow; policy term defined for *registered SMEs* сопоставляют population predicate for *all firms*; geographic code отсылает к старым границам, а норма — к новым административным единицам. Конфликт должен иметь собственный typed relation и blocker code, а не растворяться в “low confidence”. Это особенно важно, потому что в triage Policy Design Case уже сейчас трактует incompatible claim refs / unresolved spine как стоп-сигнал до final claims. fileciteturn29file0L1-L3 citeturn7view1turn7view3

**Unresolved concept** — это состояние, где candidate mappings есть, но PolicyOS не может выбрать admissible one without overclaiming. Причины: ambiguity, missing provenance, конкурирующие authority sources, отсутствие definition refs, неполный scope tuple, tie between bridges, либо отсутствие доказуемого bridge от одного namespace к другому. Unresolved status должен быть first-class результатом reconciler-а, а не “temporary null”, потому что acceptance criterion C6 требует сделать unresolved/conflicting concepts first-class blockers before PDC closeout; и это уже согласуется с существующей triage логикой про unresolved spine. fileciteturn29file0L1-L3 fileciteturn36file0L1-L3

**Scope-shifted concept** — это центровое понятие для C6. Я определяю его как case, где label или даже базовый referent похожи, но concept меняется из-за одного или нескольких измерений scope: population, geography, time, unit, aggregation level, legal instrument, beneficiary class, or observational frame. Внешние стандарты это хорошо подсвечивают: RDF Data Cube прямо строит статистические наблюдения как data organized along **dimensions, attributes and measures**, а для concept-coded dimensions требует code lists; Time Ontology различает temporal reference systems и temporal positions; GeoSPARQL различает `geo:Feature` и `geo:Geometry`. Следовательно, “same term, different refPeriod/refArea/population/unit” в PolicyOS должен классифицироваться не как same concept, а как scope-shifted concept. citeturn12view0turn12view1turn12view2turn12view3turn7view5turn14view0turn14view1

**Authority-shifted concept** — это case, где семантика похожа, но authoritative source of meaning различается: другой issuer, different normative level, другая version lineage, другая jurisdictional competence или иной scheme owner. PROV полезен здесь как внешний каркас: provenance — это информация об entities, activities и agents, участвующих в создании data, чтобы судить о trustworthiness. Внутренне ваш `authority.py` уже делает важный шаг в ту же сторону через authority envelopes, same-input closure, artifact ownership и borrowed-envelope detection. Для concept spine из этого следует правило: даже lexical-equivalent concepts не являются “same” автоматически, если authority provenance shifted и мост между authority namespaces не зафиксирован явно. citeturn8view0 fileciteturn37file0L1-L3

## Модель namespaced concept authority

Практически я предлагаю ввести для каждого concept node обязательный **authority envelope of meaning**, не путать с evidence authority envelope. Минимальный набор полей должен быть таким: `namespace_kind`, `authority_owner`, `authority_level`, `scheme_id`, `local_id`, `scheme_version`, `jurisdiction`, `valid_from`, `valid_to`, `language`, `definition_ref`, `preferred_label`, `notation/code`, `provenance_ref`. Это делает concept identity не просто label-based, а **issuer-bound and version-bound**. В этом отношении полезны и SKOS concept schemes, и PROV provenance, и Data Cube/SDMX-like code lists. citeturn6view0turn8view0turn12view1

Для PolicyOS domains я бы зафиксировал восемь namespace classes: `policy_term`, `metric`, `column`, `norm`, `method`, `population`, `geography`, `time`. Эти домены соответствуют и вашему C6 brief, и уже существующим producer surfaces. В capability map прямо видно, что concept spine сидит между Fabric, Scientist cross-graph, IR linker/analytics и normative arbitration; следовательно, namespace model должен быть cross-cutting, а не привязан к одному subsystem. fileciteturn35file0L1-L3

`policy_term` namespace должен описывать термин policy intent / intervention / objective / critique surfaces. `metric` namespace — canonical metric identity, включая measured phenomenon, unit, aggregation and denominator. `column` namespace — operational data field identity: source system, schema, column, unit, lineage, transform. `norm` namespace — legal concept under jurisdiction, competence, validity interval and instrument hierarchy. `method` namespace — analytical obligation or method family under Foundry/IR semantics. `population`, `geography` и `time` должны быть отдельными namespaces, а не «атрибутами в фоне», потому что они часто и создают scope shifts. Это прямо согласуется с тем, что Lex уже фильтрует нормы по jurisdiction/time/domain, Fabric проверяет geography/time/freshness facets, Foundry кодирует transportability limits, а Data Cube делает dimensions first-class citizens. fileciteturn33file0L1-L3 fileciteturn40file0L1-L3 fileciteturn32file0L1-L3 citeturn12view0turn12view1turn12view3

Особенно важно отделить `metric` от `column`. Колонка почти никогда не должна считаться same concept с метрикой по умолчанию; в нормальном случае между ними отношение `operationalizes` или `measures`, а не `same`. То же правило нужно для `norm` versus `policy_term`: policy term часто *governed by* norm, но не тождественен ей. И для `method requirement` versus `policy outcome`: метод — это obligation/support surface, а не сам policy concept. Такое разделение уменьшит ложные exact matches и резко улучшит honest diagnostics. Здесь полезен и Data Cube, где dimensions / measures / attributes разделены по типам, и ваш internal separation между Fabric/Lex/Foundry/Scholar record families. citeturn12view3turn12view2 fileciteturn40file0L1-L3 fileciteturn33file0L1-L3 fileciteturn32file0L1-L3

## Проверка модели на артефактах C6

Для **policy terms** и **legal concepts** правило должно быть таким: same concept возможно только при совпадении beneficiary class, instrument class, jurisdiction, time validity и authority namespace, либо при explicit bridge, который говорит, что policy wording является faithful policy-level restatement legal concept-а. Во всех остальных случаях связь должна быть `governed_by`, `implements`, `constrained_by` или `scope_shifted`. Это хорошо сопоставляется с тем, что Lex уже умеет делать competence/time/jurisdiction filtering, но не претендует на full semantic identity. fileciteturn33file0L1-L3

Для **metric ids** и **dataset columns** same concept допустим только в узком случае: колонка является canonical publication of именно этого metric id, с совпадающими unit, denominator, population, geography, time grain and aggregation semantics. Иначе это либо `operationalizes`, либо `proxy_for`, либо `scope_shifted`. Data Cube здесь особенно полезен как внешний шаблон: наблюдение определяется dimensions, attributes и measures; `refPeriod` и `refArea` являются dimension properties; unit of measurement — attribute property. Поэтому “одинаковое название показателя” без совпадения этих структур не должно проходить как same concept. citeturn12view3turn12view1turn12view2

Для **legal concepts**, **population predicates**, **geography predicates** и **time predicates** нельзя допускать implicit folding в один узел. Population predicate должен иметь свою subject-class semantics и exclusion rules; geography predicate — свой spatial authority и boundary version; time predicate — свой temporal reference system и semantic role. W3C Time Ontology подчёркивает, что temporal positions и intervals должны быть описаны относительно temporal reference system; GeoSPARQL разводит `Feature` как spatial phenomenon и `Geometry` как representation of shape/extent. Значит, например, “Kyiv region” как legal-administrative competence area и “Kyiv region” как geometry boundary dataset не равны автоматически: между ними нужен explicit edge. citeturn7view5turn14view0turn14view1

Для **method requirements** reconciliation должен быть ещё осторожнее. Foundry/IR могут доказать, что certain method surface satisfies obligation for `causal_effect_estimation`, `transportability`, `heterogeneity`, `uncertainty_interval` и т.д., а IR cross-graph может композировать SCM fragments и interface mappings. Но это по природе relation типа `satisfies_method_obligation` или `supports_claim_about`, а не same concept. Concept spine должен различать identity edges и obligation/support edges, иначе semantic closure будет смешивать “что измеряется” и “чем это доказано”. fileciteturn32file0L1-L3 fileciteturn42file0L1-L3

Для **Scholar evidence** правильная роль concepts иная: литература обычно должна быть связана с claims через `supports`, `conflicts_with`, `addresses`, `transportable_to` и similar relations. Поскольку `scholar/evidence.py` уже различает support links, conflict links, freshness и provenance, concept spine здесь должен скорее подхватывать and normalize concept refs, чем пытаться объявлять paper concept и runtime policy concept “same” без explicit bridge. Scholar — источник evidence relations, а не master authority of concept identity. fileciteturn31file0L1-L3

## Архитектурное решение и правила closeout

Архитектурно я рекомендую **не строить один физический universal registry как единственный источник истины**. Вместо этого лучше закрепить решение: **concept spine — это per-run reconciled authority artifact over existing registries**, а существующие registries остаются owners своих доменов. Это максимально согласуется с capability reuse map, где capability прямо помечен как `wire-existing`, и с ADR-0158, где логика тоже движется в сторону per-run reconciliation поверх существующих surfaces. Такой дизайн уменьшает central ontological brittleness, сохраняет ownership у Lex/Fabric/Foundry/Scholar/IR, и позволяет делать authority-profile-specific reconciliation в runtime. fileciteturn35file0L1-L3 fileciteturn23file0L1-L3

Практически artifact должен содержать, как минимум, `spine_id`, `run_id`, `authority_profile`, `input_registry_refs`, `concept_nodes`, `relation_edges`, `scope_tuples`, `accepted_bridges`, `rejected_bridges`, `unresolved_nodes`, `conflict_nodes`, `claim_bindings`, `blocker_refs`, `closure_status`. Дальше `semantic_binding.py` должен читать не просто произвольный `spine_context`, а результат этого reconciler-а; а `policy_design_case` и scorecard должны поднимать typed blocker-и напрямую из concept spine. Это согласуется с уже существующим internal pattern: evidence spine carrier + authority envelope + semantic binding + PDC closeout gates. fileciteturn25file0L1-L3 fileciteturn26file0L1-L3 fileciteturn36file0L1-L3

Правило closeout я предлагаю сформулировать жёстко: **unresolved concept**, **conflicting concept**, **unaccepted scope shift** и **unbridged authority shift** должны быть `Violation`-уровнем blockers до PDC closeout. SHACL здесь полезен как operational analogy: validation report должен явно сообщать conformance, result severity и result message, а default severity для violation-critical constraints — `sh:Violation`. Для PolicyOS это означает, что concept spine не должен “молча деградировать” ambiguities в warnings, если claim or recommendation rely on interchangeability. citeturn11view2turn13view0turn13view2

Отдельно стоит закрепить, что **related concept** допустим для retrieval, evidence portfolios и explanatory context, но не закрывает same-concept requirement. **Scope-shifted concept** может быть downgraded from blocker to qualified support only if в spine есть explicit accepted bridge, limitation refs и claim compiler явно отражает это как limitation/transportability constraint. **Authority-shifted concept** может быть допущен только при указанном definition ref, authority provenance и bridge rationale. Всё остальное — blocker. Это и есть тот “semantic spine model”, который делает unresolved/conflicting concepts first-class closeout objects, а не диагностическим послесловием. fileciteturn29file0L1-L3 fileciteturn37file0L1-L3

## Рекомендуемая формулировка итоговой модели

Сжатая нормативная формулировка для C6 выглядит так: **concept spine** — это runtime-owned per-run artifact, который reconciles concept identity across policy term, metric, column, norm, method, population, geography and time namespaces, records the authority and scope under which a mapping is admissible, and emits blocker-grade unresolved/conflicting decisions before semantic binding and PDC closeout. Он опирается на existing registries and producer outputs; не заменяет их; и становится единственным run-level authority for cross-producer semantic interchangeability. fileciteturn35file0L1-L3 fileciteturn25file0L1-L3 fileciteturn29file0L1-L3

В терминах relation classes я бы зафиксировал следующий минимальный набор: `same_concept`, `related_concept`, `conflicting_concept`, `unresolved_concept`, `scope_shifted_concept`, `authority_shifted_concept`, а также non-identity support edges вроде `operationalizes`, `measures`, `governs`, `satisfies_method_obligation`, `supports_claim`, `conflicts_with_claim`. Первые шесть — core C6 taxonomy. Всё, что попадает в `unresolved`, `conflicting`, `scope_shifted` without accepted bridge или `authority_shifted` without accepted bridge, должно автоматически становиться blocker-class output. В качестве внешнего семантического каркаса эту таксономию удобно калибровать против `owl:sameAs` и SKOS mapping relations, но не сводить к ним механически: PolicyOS нужен более строгий runtime-safe слой, потому что у него есть closeout, authority profiles и serious claims. citeturn7view0turn7view1turn7view2turn7view3

## Ограничения и открытые вопросы

Это исследование опирается на доступный GitHub-срез выбранного репозитория и на ключевые артефакты, которые сильнее всего связаны с C6: capability reuse map, ADR-0158, operating model, evidence spine remediation plan, semantic binding, Fabric/Lex/Foundry/Scholar/runtime quality modules и cross-graph compiler. Я не провёл полный line-by-line аудит всех возможных code anchors внутри `entity_resolution`, `normative_arbitration` и всех IR/linker submodules; поэтому некоторые implementation-level детали семантического reconciler-а ниже уровня design model здесь остаются открытыми. fileciteturn35file0L1-L3 fileciteturn23file0L1-L3 fileciteturn36file0L1-L3

Главные открытые вопросы, которые ещё стоит формально закрепить уже в следующем design pass, такие. Во-первых, нужны ли отдельные relation classes `proxy_for` и `operationalizes`, или их достаточно выводить из `related + typed edge label`. Во-вторых, где exactly проходит граница между `scope_shifted` и `authority_shifted`, когда shift вызван change in legal validity interval. В-третьих, нужны ли hard confidence thresholds для auto-resolution, или все claim-critical exact mappings должны требовать explicit bridge provenance regardless of score. И в-четвёртых, стоит ли зафиксировать SHACL-like validation report как wire format concept spine blockers, чтобы scorecard/PDC/readiness читали их без новой прослойки. Все четыре вопроса уже хорошо ложатся на существующую архитектуру PolicyOS и не требуют отказа от выбранного выше решения о per-run reconciled artifact. citeturn11view2turn13view0turn13view2 fileciteturn25file0L1-L3 fileciteturn29file0L1-L3

# ADR по legal authority, jurisdiction и institutional competence для PolicyOS

## Контекст в текущем PolicyOS

Репозиторий уже далеко не «пустой лист» для этой задачи. В Governance IR есть `PolicyCompositionPlan` с уровнями `FEDERAL`, `STATE`, `LOCAL`, `ORGANIZATIONAL`, временными полями `effective_from/effective_to`, правилами override и compatibility constraints; то есть многослойная композиция политики уже представлена как фронтирный контракт, а не как ad hoc логика. Одновременно Lex уже держит отдельные контуры для query normalization, normative applicability, legal KG retrieval и temporal versioning, а runtime Policy Design Case уже требует отдельное семейство записей `legal_authority_and_competence.v1`. fileciteturn19file0L3-L3 fileciteturn36file0L3-L3 fileciteturn35file0L3-L3

Текущая кодовая база уже показывает правильное направление, но не доводит authority-модель до fail-closed состояния. `query_normalization.py` требует `competence_refs`, `temporal_validity_refs`, `policy_instrument_refs`, `beneficiary_class_refs`, `fiscal_authority_refs` и `implementation_agency_refs`, а также переносит из scenario contract поля `jurisdiction`, `temporal_scope`, `authority_scope`, `policy_instrument`, `fiscal_authority`, `implementation_agency`. Однако там пока нет явных first-class фасетов для enabling authority, delegated authority, oversight и appeals_or_contestability. fileciteturn22file0L3-L3 fileciteturn23file0L3-L3

`applicability_report.py` уже умеет жёстко отклонять нормы при `wrong_jurisdiction`, `missing_effective_from`, `not_yet_effective`, `expired_norm`, `superseded_norm` и `missing_authority_metadata`, а для major recommendations требует claim-specific normative anchor с совпадением по competence, temporal validity, instrument, beneficiary, fiscal authority и implementation agency. Но этот слой пока проверяет в основном наличие и согласованность метаданных у самой нормы; он ещё не строит полную цепочку юридической компетенции между уровнем власти, видом акта, делегацией полномочия и temporal validity самого органа-носителя полномочия. fileciteturn26file0L3-L3 fileciteturn27file0L3-L3 fileciteturn28file0L3-L3 fileciteturn29file0L3-L3

Темпоральная база в Lex уже достаточно сильная для серьёзного authority ADR. `resolve_active_version` работает с явной стратегией `date_inclusive`, выбирает версию по правилу `effective_from_then_published_then_doc_version_id`, а `build_version_index` поднимает quality issues вроде `missing_effective_from`, `unresolved_temporal` и `overlapping_effective_ranges`. Это значит, что acceptance criterion про temporal competence можно реализовать без архитектурного разворота системы — нужно расширить уже существующую temporal machinery на authority records и jurisdiction units. fileciteturn30file0L3-L3 fileciteturn31file0L3-L3 fileciteturn32file0L3-L3 fileciteturn33file0L3-L3 fileciteturn34file0L3-L3

## Юридические опоры для модели

Для верхнего уровня иерархии базовый принцип ясен: в США федеральная Конституция, федеральные законы и договоры являются “supreme law of the land”, а суды штатов связаны ими несмотря на противоречащие нормы штата. Это даёт прямую опору для fallback-модели, в которой более низкий уровень может действовать только при отсутствии preemption или при явном пространстве для supplemental implementation. citeturn6view0

Связка state–local ещё жёстче обосновывает, почему generic jurisdiction membership недостаточен. В `Hunter v. Pittsburgh` Верховный суд прямо сказал, что в отношении муниципальных корпораций “the state is supreme”, а в `Trenton v. New Jersey` — что при отсутствии конституционной защиты у муниципалитетов нет inherent right of self-government beyond legislative control of the state. Следовательно, для local/institutional layers одного факта «объект находится в этой юрисдикции» недостаточно: нужен отдельный вывод о том, что соответствующий lower-layer actor действительно получил, сохранил и не утратил компетенцию на релевантную дату. citeturn22view0turn22view1

Для implementing authority важны нормы административного права. APA требует, чтобы notice of proposed rulemaking содержал reference to the legal authority under which the rule is proposed, а суд при review должен set aside agency action, если оно “in excess of statutory jurisdiction, authority, or limitations”. Это поддерживает дизайн, в котором implementing instrument не может считаться достаточным источником authority без ссылки на enabling/delegating basis и без проверки, что исполнительный орган действует в границах делегированного ему полномочия. citeturn6view1turn7view1

Для temporal semantics право тоже даёт жёсткий сигнал: substantive rules обычно публикуются не менее чем за 30 дней до effective date, если не действует исключение good cause, а ретроактивное действие по умолчанию не презюмируется. `Landgraf` прямо говорит, что presumption against retroactive legislation deeply rooted и что settled expectations should not be lightly disrupted. Поэтому unresolved effective-time нельзя сглаживать эвристикой; по умолчанию он должен порождать blocker, если только ретроэффект или continuity rule не закреплены явно. citeturn6view1turn22view2

Наконец, funding authority должен быть отделён от enabling authority. По 31 U.S.C. §1301 appropriation may be applied only to the objects for which it was made, а по 31 U.S.C. §1341 нельзя делать expenditure или obligation, превышающие available appropriation, либо вовлекать государство в обязательство до ассигнования, если это отдельно не authorized by law. Это сильный аргумент в пользу отдельного фасета `funding`: норма может разрешать действие по существу, но не давать правомерного бюджетного основания для его запуска. citeturn23view0turn24view0

## Проект ADR

**Статус:** proposed.

**Решение:** в PolicyOS нужно считать, что serious legal authority удовлетворён только тогда, когда Lex может доказать непрерывную цепочку authority для релевантной даты и уровня: `source norm -> authority basis -> competent issuer/actor -> permitted instrument -> active temporal window -> non-preempted jurisdictional position -> if needed funded execution path -> review/contestability path`. Простое совпадение по `jurisdiction` или membership в территории допускается только как discovery/filtering signal, но не как доказательство юридической достаточности. Это решение логически продолжает уже существующие в репозитории contracts для multi-level composition, temporal versioning и claim-specific normative anchors. fileciteturn19file0L3-L3 fileciteturn27file0L3-L3 fileciteturn28file0L3-L3 fileciteturn32file0L3-L3 fileciteturn34file0L3-L3

**Нормативная логика ADR:** higher law can displace lower law; municipalities and other sub-state institutions often act only within state-granted powers; agencies must point to delegated legal authority; and actions exceeding statutory authority are reviewable and invalidable. Поэтому acceptance criterion из задачи следует усилить до формулы: *generic jurisdiction membership никогда не закрывает serious legal authority, если unresolved хотя бы один из следующих вопросов — hierarchy, temporal competence, implementing authority, funding authority for spending claims, либо contestability for adjudicative/coercive claims*. citeturn6view0turn22view0turn22view1turn6view1turn7view1turn23view0turn24view0

**Последствия:** это усложнит legal records и снизит долю «условно проходящих» Lex-результатов, но зато уберёт наиболее опасный класс ложноположительных обоснований — когда норма кажется релевантной по территории и теме, но неясно, кто именно вправе ею действовать, с какого момента, в каком инструменте и за какие деньги. В терминах runtime качество это хорошо согласуется с уже существующим fail-closed духом authority envelopes и PDC record-family gating. fileciteturn37file0L3-L3 fileciteturn35file0L3-L3

## Иерархия юрисдикции и темпоральная компетенция

Рекомендуемая иерархическая модель должна различать не просто «уровни», а *режимы перехода между уровнями*. На практике нужны состояния `exact_authority_match`, `supplemental_lower_layer_allowed`, `delegated_downward_authority`, `concurrent_authority`, `blocked_by_higher_law_preemption`, `blocked_by_missing_delegation`, `blocked_by_missing_implementing_act` и `blocked_by_institution_not_competent_on_date`. Такая модель естественно наслаивается на существующий `PolicyCompositionPlan`, где уже есть level, precedence, effective interval и compatibility constraints; но вместо общего compatibility нужно ввести authority-aware compatibility, то есть вопрос не только «совместимо ли», а «вправе ли нижний слой вообще менять поверхность нормы этого типа». fileciteturn19file0L3-L3 citeturn6view0turn22view0turn22view1

Для temporal competence предлагаю развести как минимум шесть датовых полей: `published_at`, `effective_from`, `effective_to`, `repealed_at`, `superseded_at`, `authority_window_from/to` для самого органа или delegated competence. В текущем Lex temporal core уже есть inclusive semantics и explicit tie-break; их надо просто применить не только к документной версии, но и к authority unit и delegation chain. Ключевое правило ADR: если норма активна, но issuance/competence самого органа на дату `as_of` не подтверждены, authority считается unresolved и claim must fail closed. Это совместимо и с внутренним versioning, и с общим правовым default против retroactivity. fileciteturn31file0L3-L3 fileciteturn33file0L3-L3 fileciteturn34file0L3-L3 citeturn6view1turn22view2

Особенно важно зафиксировать temporal jurisdiction changes. Здесь полезна не только document versioning, но и отдельная сущность наподобие `JurisdictionAuthorityWindow`: кто именно был компетентен, на какой территории, в каком виде акта и в какой период. Это покрывает случаи создания/ликвидации агентства, передачи полномочия между министерствами, введения state preemption, создания special district, emergency powers и sunset clauses. Если такая window не разрешается однозначно, Lex должен выпускать typed blocker, а не silently выбирать «самую похожую» норму. Внутренний код уже показывает, что система умеет делать именно typed blockers для retrieval и applicability; ADR предлагает просто распространить этот стиль на competence chain. fileciteturn25file0L3-L3 fileciteturn29file0L3-L3

## Фасеты authority и отдельный класс legal-concept conflict

Лучшее решение для `legal_authority` — не один текстовый class, а набор first-class facets. Практически я бы рекомендовал обязательный минимум: `enabling`, `delegating`, `implementing`, `funding`, `oversight`, `appeals_or_contestability`, а также служебные `preemption_scope`, `authority_level`, `instrument_type`, `delegated_from_ref`, `implemented_by_ref`, `authority_window_ref`, `review_path_ref`. Это не замена текущим `competence_refs`, `fiscal_authority_refs` и `implementation_agency_refs`, а их нормализация в более строгую authority-схему. Уже существующий query normalization прямо готовит почву для такого расширения: часть фасетов там уже фактически есть, просто пока в смешанном виде. fileciteturn22file0L3-L3 fileciteturn23file0L3-L3

Смысл фасетов должен быть жёстким. `enabling` — норма, создающая базовую власть действовать; `delegating` — норма, передающая конкретный power вниз или в агентство; `implementing` — акт, который operationalizes higher-level norm, но сам по себе не может расширять делегированное поле; `funding` — правомерный источник расхода или финансового обязательства; `oversight` — полномочие утверждать, аудировать, приостанавливать, согласовывать или проверять исполнение; `appeals_or_contestability` — предусмотренный канал административного или судебного пересмотра. Разнесение `funding` в отдельный facet юридически оправдано тем, что целевое расходование и запрет obligations без appropriation являются отдельным правовым вопросом, а `appeals_or_contestability` — тем, что право на review и invalidation of ultra vires action тоже живёт в отдельном нормативном контуре. citeturn23view0turn24view0turn7view0turn7view1

Отдельно стоит выделить `legal_concept_conflict` как самостоятельный объект, а не разновидность generic evidence conflict. Текущий `conflict_check.py` различает direct, indirect и informational normative conflicts, но он ориентирован главным образом на policy-vs-corpus constraints вроде prohibition, eligibility, budget и equity. Для C7 нужен другой класс конфликта: два акта могут не спорить о факте, а по-разному определять сам юридический концепт, носителя компетенции или допустимый instrument. Например, `resident`, `small business`, `public body`, `eligible expenditure`, `implementing authority` и даже `local government` могут означать разные вещи в разных юрисдикциях и временных срезах. Такой конфликт должен блокировать authority satisfaction ещё до того, как система перейдёт к общему evidence synthesis. fileciteturn38file0L3-L3

Практически для `legal_concept_conflict` я бы рекомендовал типы `definitional_divergence`, `preemption_conflict`, `delegation_gap`, `instrument_mismatch`, `temporal_concept_drift`, `institution_identity_mismatch` и `funding_authority_mismatch`. Это позволит отделить режим «факты спорят» от режима «понятия неэквивалентны». Для пользователя и для Scientist это важно потому, что remedial action разный: при evidence conflict надо добирать данные, а при legal concept conflict — перепривязывать юридическую основу, менять instrument path или явно эскалировать вопрос в human review. Это уже хорошо сочетается с PDC, где legal authority вынесен в отдельное minimum record family, а authority envelope трактуется как отдельный, честный диагностический контур. fileciteturn35file0L3-L3 fileciteturn37file0L3-L3

## Enforcement в Lex и PDC

В `Lex query normalization` стоит поднять серьёзность authority retrieval. Если scenario contract или target context указывают, что claim spending-bearing, coercive, adjudicative или implementation-dependent, то normalizer должен не просто расширять термины, а формировать обязательные retrieval targets: `enabling authority`, `delegated authority`, `implementing act`, `funding authority`, `oversight authority`, `appeal/review path`. Если какой-то из обязательных targets отсутствует уже на этапе поиска, нужно выпускать blocker вроде `authority_chain_incomplete_at_query_stage`, а не только `no_relevant_norm_found`. Это естественное продолжение текущего механизма bilingual query trace и legal requirements. fileciteturn22file0L3-L3 fileciteturn24file0L3-L3

В `NormPack / candidate_norms` стоит добавить строгую authority-схему на запись нормы: `authority_basis_refs`, `authority_type`, `authority_level`, `delegated_from`, `implemented_by`, `preemption_scope`, `authority_window`, `funding_ref`, `oversight_ref`, `review_ref`, `institution_id`, `institution_type`. Тогда `_classify_norm` сможет отклонять не только из-за missing authority metadata вообще, но и по более точным причинам: `missing_enabling_authority`, `missing_delegating_authority`, `missing_implementing_authority`, `preempted_lower_layer`, `institution_not_competent_as_of`, `missing_funding_authority_for_spend`, `missing_review_path_for_adjudication`. Сейчас код уже умеет выставлять typed rejections и blockers; ADR предлагает сделать эти причины юридически более определёнными. fileciteturn26file0L3-L3 fileciteturn27file0L3-L3 fileciteturn29file0L3-L3

В `PolicyCompositionPlan` я бы усилил `PolicyLayerSpec` и `PolicyCompatibilityConstraint`. Для слоя нужны `authority_basis_refs`, `preemption_mode`, `delegation_mode`, `instrument_surface`, `authority_window_ref`; для constraint — не только `mode`, но и явный `authority_resolution_required` и `required_authority_facets`. Иначе текущий composition contract умеет описать override-механику, но не доказывает, что lower layer в принципе вправе делать `APPEND`, `REPLACE` или `DISABLE` именно для данного типа нормативной поверхности. Это и есть та точка, где acceptance criterion должен стать machine-enforced, а не описательным. fileciteturn19file0L3-L3

В `Policy Design Case` семейство `legal_authority_and_competence.v1` должно стать местом, где хранится уже не просто narrative justification, а полный authority dossier: `authority_chain_status`, `resolved_jurisdiction_hierarchy`, `temporal_competence_status`, `implementing_authority_status`, `funding_status`, `contestability_status`, `blocking_authority_issues`, `legal_concept_conflicts`, `lex_report_ref`, `composition_plan_ref`. PDC уже требует concrete runtime records с authority envelope и runtime refs; значит, правильный следующий шаг — связать PDC gating c fail-closed Lex authority report один-к-одному. Если хотя бы один serious facet unresolved, PDC запись должна быть либо `blocked`, либо `not_applicable` с формально объяснённой причиной, но не `pass`. fileciteturn35file0L3-L3 fileciteturn37file0L3-L3

## Открытые вопросы и ограничения

Главный открытый момент — насколько универсальной должна быть модель между правопорядками. Исследование уверенно обосновывает ядро ADR на текущих кодовых якорях и на официальных/авторитетных источниках по federal supremacy, municipal subordination, administrative legality, judicial review, appropriations и temporal non-retroactivity. Но для truly cross-jurisdiction PolicyOS, вероятно, потребуется отдельный слой локальных профилей authority doctrine: например, различать federal-state-local федераций, unitary systems with devolution, EU-style delegated/implementing secondary law и sector-specific institutional charters. Текущая рекомендация сознательно строит общий каркас, который можно профилировать по jurisdiction family, а не пытается решить все правопорядки одной статической онтологией. citeturn6view0turn22view0turn22view1turn6view1turn7view0turn7view1turn22view2turn23view0turn24view0

Самый практичный вывод для реализации такой: **generic jurisdiction membership должен быть downgraded до retrieval hint, а не legal proof**. Для serious claims Lex должен проходить через authority chain resolution; если hierarchy, temporal competence или implementing authority не разрешены, репорт должен завершаться blocker’ом и не позволять системе «закрыть» legal authority по одному лишь факту, что норма тематически и территориально похожа. Именно это решение лучше всего согласуется и с нынешним кодом, и с acceptance criterion задачи. fileciteturn24file0L3-L3 fileciteturn27file0L3-L3 fileciteturn28file0L3-L3 fileciteturn29file0L3-L3

# Спецификация протокола Producer Handshake для PolicyOS

## Контекст и рамка решения

Я не смог извлечь из репозитория точный файл `policy-engine/docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md`, который вы указали. Поэтому исследование опирается на ближайшие активные и принятые документы того же кластера решений: ADR-0152, ADR-0157, ADR-0158, ADR-0159, ADR-0148, ADR-0150, а также активные планы по evidence binding и evidence spine connectivity. По существу они уже задают ту же архитектурную рамку: serious run должен иметь канонический intent envelope и capability ledger; producers обязаны читать единый concept/jurisdiction spine; semantic binding должен быть claim-bound; scorecard/readiness/public projection не имеют права «дочинять» authority задним числом; а phase barriers должны срабатывать до того, как downstream-артефакты начинают выглядеть финальными. fileciteturn48file0L3-L3 fileciteturn49file0L3-L3 fileciteturn52file0L3-L3 fileciteturn55file0L3-L3 fileciteturn54file0L3-L3

Из этого следует ключевое ограничение для C8: producer handshake нельзя проектировать как локальный трюк внутри одной сборки `nl_pipeline.py`. По сути он должен быть repo-wide и transport-neutral контрактом между runtime producers, который работает одинаково в локальном вызове, через async handoff, через CAS bundle, при replay, при inspection и при public projection. Именно этого требуют active plans по evidence spine: scenario contract должен быть runtime-carrier, а каждый serious producer обязан потреблять requirement ids, эмитить selected/rejected/blocked bindings, владеть собственным closure status и проходить closeout compatibility до того, как API, dashboard или public export начнут на это опираться. fileciteturn44file0L3-L3

## Что уже существует в кодовой базе

В коде уже есть сильный read-context substrate. `ProducerSpineReadContext` фиксирует `concept_spine_ref`, `jurisdiction_spine_ref`, канонические concept refs, jurisdiction refs, а также unit/period/geography refs и список consumers. Поверх этого `ProducerSpineBindingFields` уже задаёт общий набор полей, которые downstream producers обязаны отразить в своих отчётах: какие spine refs они потребили, какие candidate bindings увидели, какие blocker refs возникли, и какие local labels были использованы. Это важная отправная точка: handshake не должен изобретать новый read-context, а должен добавлять к нему предэмиссионную декларацию и coordination decision. fileciteturn25file0L3-L3

Также уже заданы доменно-специфические binding records для основных producers. `LexBindingRecord` хранит legal query terms, candidate/selected/rejected norms, snapshot refs, jurisdiction/effective-date filters, hierarchy conflicts, competence refs и typed blockers. `FabricBindingRecord` хранит candidate/selected/rejected dataset/source refs, metric/column bindings, fresheness, coverage, lineage, source facets, derived features и data-gap blockers. `ScholarBindingRecord` фиксирует candidate/selected/rejected literature refs, support/conflict links и retrieval blockers. `FoundryBindingRecord` фиксирует selected/rejected methods, scenario method expectations, assumptions, input coverage, uncertainty, sensitivity и incompatibility blockers. `ClaimBindingRecord` для Scientist/final compiler уже связывает major claims и claim evidence paths с data, methods, norms, literature, uncertainty и blockers. Иными словами, PolicyOS уже знает, **что** producers в конце должны сказать; C8 — про то, как заставить их координироваться **до** эмиссии этих authoritative решений. fileciteturn25file0L3-L3 fileciteturn26file0L3-L3

`build_semantic_binding_ledger` уже собирает ledger из closeout reports Lex/Fabric/Scholar/Foundry/Scientist/compiler и затем прогоняет `close_semantic_binding_ledger()` и `evaluate_semantic_binding_ledger()`. Важно, что текущий builder сознательно «консервативен»: он сохраняет candidate/selected/rejected/blocker refs и позволяет существующему evaluator fail closed. То есть semantic binding — уже хороший closeout substrate, но не сам coordination protocol. Это прямо совпадает с формулировкой вашей задачи: текущие producer-spine и semantic-binding hooks нужно трактовать как read-context и closeout substrate, а не как готовый handshake protocol. fileciteturn27file0L3-L3

Дополнительно репозиторий уже вводит `EvidenceSpineCarrier` и `EvidenceRequirementBinding`. Carrier несёт `scenario_evidence_contract_id`, `requirement_ids`, `producer_component`, `producer_report_schema`, `reader_contract`, `authority_profile`, `code_revision`, `input_refs` и `output_refs`. Сверху есть `EvidenceSpineNode` и отдельный async `EvidenceSpineHandoff` ledger, который нормализует handoff kinds, parent/input/output refs, redaction и integrity status и специально запрещает переносить секреты, raw prompts, raw recommendation text и подобные sensitive surfaces через carrier. Это практически готовая transport-neutral шина, в которую handshake можно встроить как обязательный предэмиссионный шаг. fileciteturn45file0L3-L3 fileciteturn46file0L3-L3

Наконец, существует `RuntimeClaimRegistry`, который уже задаёт claim-bound surface: на уровне каждого claim он хранит `scenario_requirement_refs`, `data_refs`, `selected_norm_refs`, `method_output_refs`, `argument_refs`, `warrant_refs`, `rebuttal_refs`, `counter_evidence_refs`, `limitation_refs`, `accepted_deficit_refs` и `blocker_refs`. Параллельно `scientist/cross_graph/conflict.py` уже умеет постфактум детектить и разрешать конфликты между legal, academic и dataset dimension results. Это полезно, но по самой своей структуре работает **после** появления dimension results; то есть для C8 это скорее fallback/post-hoc слой, а не механизм обязательной pre-emission координации. fileciteturn40file0L3-L3 fileciteturn43file0L3-L3

Отдельно важно, что тест `test_wave10_producer_spine_interfaces.py` уже закрепляет ожидаемое поведение: Lex, Fabric, Scholar, Foundry, Scientist grounding и compiler contract должны потреблять общий spine context и эмитить candidate bindings либо blockers, а затем semantic binding ledger должен отражать эти consumed spine refs по всем компонентам. Это хороший acceptance anchor для C8: handshake должен усиливать уже тестируемый интерфейс, а не ломать его. fileciteturn32file0L3-L3

## Внешние архитектурные уроки

Внешние стандарты подтверждают именно такой вектор. OpenTelemetry определяет propagation как механизм переноса context между сервисами и процессами, а context propagation позволяет строить causal information через process and network boundaries; при этом baggage нельзя использовать для чувствительных данных, потому что она свободно проходит через downstream boundaries. W3C Trace Context задаёт жёстко форматированный carrier с `traceparent`, стабильными ids, версионированием и правилами мутации; стандартизированные headers нужны именно для межсервисной интероперабельности, а не для одного локального pipeline. OpenTelemetry messaging spans развивают эту идею для async-модели: producer должен прикреплять message creation context, а consumer нельзя надёжно коррелировать с producer без отдельного creation context и propagating links через intermediaries. citeturn11view0turn11view1turn12view0turn12view1turn20view0

Для provenance и lineage самые полезные аналоги — W3C PROV и OpenLineage. PROV формализует provenance как информацию об entities, activities и agents, участвующих в создании объекта, чтобы по ней судить о качестве, надёжности и trustworthiness. OpenLineage, в свою очередь, чётко разделяет runtime `RunEvent` от design-time `JobEvent` и `DatasetEvent`, а также делает core model extensible через facets для run/job/dataset. Это прямо подсказывает, как строить handshake в PolicyOS: handshake должен быть **runtime coordination event**, а не подменять собой ни статическую схему producer report, ни поздний scorecard/readiness verdict. citeturn13view0turn13view1turn9view0turn10view0

Для compatibility gate и attestation полезны Pact, SLSA и in-toto. Pact `can-i-deploy` показывает, что безопасное продвижение достигается не локальным “у меня тесты зелёные”, а проверкой матрицы совместимости с уже развёрнутыми зависимостями. SLSA provenance требует фиксировать builder identity, external/internal parameters, resolved dependencies и execution metadata, причём в верифицируемом attestation-формате. in-toto подчёркивает прозрачность того, **какие шаги**, **кем** и **в каком порядке** были выполнены. Для PolicyOS это означает: producer handshake должен быть версионированной и проверяемой декларацией «что я прочитал, что собираюсь выбрать, что отверг, что блокировал и на каком authority basis», а closeout должен проверять совместимость handshakes с reader contracts и code revision по модели `can-i-closeout`. citeturn16view1turn16view0turn15view0turn17view0

## Спецификация протокола

### Назначение и границы

Предлагаемый `producer-handshake protocol` — это обязательный предэмиссионный coordination layer между serious producers PolicyOS. Он стоит **между** общим read-context (`ProducerSpineReadContext`, `EvidenceSpineCarrier`, scenario contract, capability ledger) и существующими producer reports/semantic binding ledger/claim registry. Он не заменяет semantic binding, claim registry, scorecard или readiness; он гарантирует, что authoritative producer decisions уже согласованы до того, как они попадут в closeout. Такая постановка прямо вытекает из текущего repo design: read-context и binding fields уже существуют, semantic binding уже умеет fail closed, а active evidence-spine plan уже требует, чтобы producers сами владели selected/rejected/blocked bindings и собственным closure status. fileciteturn25file0L3-L3 fileciteturn27file0L3-L3 fileciteturn44file0L3-L3

### Канонические объекты протокола

Я предлагаю ввести пять transport-neutral record types.

`ProducerHandshakeIntent` — минимальная декларация producer до эмиссии authoritative report. Она должна содержать: `handshake_id`, `run_id/trace_id/spine_id`, `producer_component`, `producer_role`, `producer_report_schema`, `reader_contract`, `authority_profile`, `code_revision`, `scenario_evidence_contract_id`, `consumed_concept_ids`, `consumed_requirement_ids`, `consumed_claim_ids` если есть, `emitted_ref_kinds`, `scope_assumptions`, `time_assumptions`, `geography_assumptions`, `jurisdiction_assumptions`, `selected_bindings`, `rejected_bindings`, `blocked_bindings`, `conflict_checks`, `input_refs`, `expected_output_refs`, `authority_envelope_ref` при наличии и `supersedes_handshake_ref` для идемпотентных переэмиссий. Это — синтетическое продолжение уже существующих `ProducerSpineBindingFields`, `EvidenceSpineCarrier` и доменных binding records, а не параллельная модель. fileciteturn25file0L3-L3 fileciteturn26file0L3-L3 fileciteturn45file0L3-L3

`ProducerHandshakeDecision` — coordination result. Он должен фиксировать `coordination_status` со значениями `approved`, `approved_with_blockers`, `rejected`, `stale`, `superseded`; `reason_codes`; `counterparty_refs`; `resolved_conflict_refs`; `required_followups`; `lease_until_phase`; и ссылку на тот exact revision/intake set, относительно которого решение действительно. Здесь логика должна быть совместима с existing phase barriers и closeout compatibility, чтобы “approved” значило не «локально норм», а «совместимо с shared spines, active requirements и current authority mode». fileciteturn55file0L3-L3 fileciteturn44file0L3-L3 citeturn16view1turn16view0

`ProducerHandshakeCommit` — короткая запись, что producer реально эмитил артефакт, соответствующий одобренному intent. В ней достаточно `handshake_id`, `decision_ref`, `artifact_ref`, `payload_digest`, `emitted_at`, `actual_output_refs`, `final_blocker_refs`, `final_selected_refs`, `final_rejected_refs`. Если payload materially расходится с intent, commit должен считаться invalid и вести к fail at closeout. Это перекликается с SLSA/in-toto, где provenance/attestation должны фиксировать builder, зависимости и output identity, а не только красивый итоговый статус. citeturn15view0turn17view0

`ProducerHandshakeLedger` — агрегат по run, в котором handshakes выстраиваются по partial order, а не по одной локальной сборочной функции. Ключевая идея: acceptance критерия C8 достигается только если canonical ledger можно собрать хоть из in-process вызовов, хоть из async сообщений, хоть из CAS bundle inspection; `nl_pipeline.py` может быть одним из entrypoints, но не единственным носителем истины. Это соответствует как active evidence-spine plan, так и OpenTelemetry/W3C-модели по propagation across process and messaging boundaries. fileciteturn44file0L3-L3 fileciteturn46file0L3-L3 citeturn11view0turn12view0turn20view0

### Обязательный набор деклараций для каждого producer

До эмиссии report producer обязан объявить по меньшей мере шесть вещей.

Во-первых, **что именно он прочитал**: consumed concept ids, consumed requirement ids, consumed claim ids, input refs и версии read-context, включая concept/jurisdiction spine refs. Без этого negotiation не может отличить “producer честно выбрал и заблокировал” от “producer увидел вообще другой run spine”. fileciteturn25file0L3-L3 fileciteturn49file0L3-L3

Во-вторых, **что именно он собирается выпустить**: типы emitted refs и expected output refs. Это нужно, чтобы coordination происходил не на абстрактных “я что-то проанализировал”, а на уровне конкретных authority-bearing surfaces: selected norms, selected sources, selected methods, claim-evidence paths, blockers, public artifact section refs и т.п. fileciteturn26file0L3-L3 fileciteturn40file0L3-L3

В-третьих, **как он распорядился кандидатами**: отдельно selected, rejected и blocked bindings. Именно это уже требуют ADR-0152 и ADR-0159: один только “final selection” без rejected candidates и typed blockers недостаточен для serious closeout. Поэтому handshake не должен принимать intents, где есть только selected refs без rejected/blocked disposition, когда upstream producer реально имел выбор. fileciteturn52file0L3-L3 fileciteturn50file0L3-L3

В-четвёртых, **какие conflict checks producer провёл**: semantic-spine mismatch, jurisdiction/time/geography mismatch, requirement-ownership collision, duplicate fulfillment, incompatible blocker precedence, cross-graph contradiction, capability-ledger violation. Здесь важен не только verdict, но и `counterparty_refs` — с кем именно producer координировался или чьи output refs проверял. Нынешний `ConflictDetector` уже показывает полезные dimensions для post-hoc resolution; handshake должен вынести их в pre-emission checks и сделать typed. fileciteturn43file0L3-L3

В-пятых, **authority role**. Producer обязан явно указать, в каком качестве он говорит: `selector`, `resolver`, `blocker_emitter`, `claim_compiler`, `projection_only`, `inspector`, `replay_only`, `reviewer`, `publisher`. Это нужно потому, что ADR-0150 запрещает projection surfaces mint authority, а active plans отдельно различают producer-owned evidence от packaging/projection-only artifacts. Если роль `projection_only`, такой producer не может закрывать requirement и не может быть counterparty, который “выигрывает” coordination. fileciteturn54file0L3-L3 fileciteturn23file0L3-L3

В-шестых, **scope/time/geography assumptions**. Это обязательное требование именно для PolicyOS, а не общий nice-to-have: ADR-0158 требует единого per-run concept/jurisdiction spine, а semantic binding/claim relevance должны fail closed при несовместимых populations, units, periods и geographies. Поэтому handshake должен фиксировать не только refs, но и явные assumptions producer относительно юрисдикции, времени действия, временного окна данных, географического охвата и population scope. fileciteturn49file0L3-L3 fileciteturn52file0L3-L3

### Жизненный цикл

Логика протокола должна быть пятишаговой.

`prepare`: runtime создаёт shared handshake context из scenario contract, capability ledger, concept/jurisdiction spine и evidence spine carrier.  
`offer`: producer публикует `ProducerHandshakeIntent`.  
`coordinate`: coordinator валидирует offer против shared spines, active requirement ownership, prior committed handshakes и mandatory conflict checks.  
`commit`: producer получает decision, эмитит report и публикует `ProducerHandshakeCommit`, привязанный к decision.  
`closeout`: semantic binding, claim registry, scorecard, readiness, replay и inspection принимают только committed handshakes, не stale и не superseded.  

Эта модель согласуется и с phase barriers serious runs, и с OpenTelemetry messaging guidance: producer создаёт context заранее, attach/propage it through boundaries, consumer связывает обработку через creation context, а downstream authority surfaces читают уже committed chain, а не догадки о ней. fileciteturn55file0L3-L3 citeturn20view0

### Когда предэмиссионная координация обязательна

Pre-emission coordination должна быть обязательной во всех случаях, когда producer делает **authoritative выбор**, который может изменить closure other producers или phase state run. Практически это означает четыре категории.

Если producer закрывает requirement, major claim, legal/method/data obligation или typed blocker, coordination обязательна. Если producer выбирает один candidate из конкурирующих источников, норм, методов или literature refs, coordination обязательна. Если producer меняет shared assumptions по jurisdiction/time/geography/population или вводит conflict/blocker, влияющий на downstream state machine, coordination обязательна. Если producer выпускает artifact, на который позже опираются scorecard, readiness, approval или public publication, coordination обязательна. fileciteturn55file0L3-L3 fileciteturn54file0L3-L3 fileciteturn52file0L3-L3

Post-hoc conflict detection достаточно только там, где producer не mint authority и не меняет closure. Сюда относятся чисто диагностические annotations, replay-only артефакты, inspection notes, non-authoritative observability events и public/dashboard projections, которые лишь отражают уже закрытую authority graph. Это полностью согласуется с ADR-0150: projections читают authority, но не производят её. fileciteturn54file0L3-L3

## Как handshake должен питать остальные подсистемы

В `semantic binding` handshake должен входить не как отдельный «ещё один отчёт», а как upstream proof, что binding record был согласован до эмиссии. Практически это означает: у каждого `LexBindingRecord`/`FabricBindingRecord`/`ScholarBindingRecord`/`FoundryBindingRecord`/`ClaimBindingRecord` должен появиться `handshake_ref` или эквивалентный pointer на commit. Тогда evaluator сможет различать три случая: producer ничего не выбрал; producer выбрал без координации; producer выбрал, скоординировал и закоммитил. Это существенно сильнее текущей closeout-only оценки. fileciteturn26file0L3-L3 fileciteturn27file0L3-L3

В `claim registry` handshake должен стать источником claim-local truth. Регистру уже нужны `scenario_requirement_refs`, `data_refs`, `selected_norm_refs`, `method_output_refs`, `argument/warrant/rebuttal/counter_evidence/limitation/accepted_deficit/blocker refs`. Поэтому commit handshake должен быть тем местом, где producer окончательно объявляет, какие именно refs claim-bound, а какие остались rejected или blocked. Тогда registry перестаёт зависеть от глобальных evidence pools и получает именно producer-owned, coordinated inputs. fileciteturn40file0L3-L3

В `readiness` и `closeout` handshake должен участвовать по модели `can-i-closeout`: readiness закрывается только если для всех required producers есть committed handshakes, их `producer_report_schema` и `reader_contract` совместимы, authority profile разрешён, code revision согласован, а статус не stale и не superseded. Так active plans уже формулируют closeout compatibility, а аналогия с Pact здесь особенно удачна: важно не то, что producer “сам себя считает зелёным”, а то, что его версия и его результаты совместимы с уже существующей authority graph run. fileciteturn44file0L3-L3 citeturn16view1turn16view0

В `replay` и `inspection` handshake должен давать reconstructable graph: кто что видел, кто какие candidates объявил, почему что-то было rejected, кто инициировал blocker, и какой handoff boundary это пережило. Репозиторий уже имеет `EvidenceSpineHandoff` ledger с parent/input/output refs, batch membership, redaction и integrity status; значит, handshake надо просто связать с этим ledger по `carrier_ref`/`parent_spine_ref`/`artifact_ref`, а не строить новый формат для replay. fileciteturn46file0L3-L3 fileciteturn44file0L3-L3

В `public projection` handshake должен экспортироваться только в редуцированном виде. Разрешены producer name, authority role, requirement ids, coordinated status, blocker codes, selected/ref-count summaries и links на redacted authority artifacts. Запрещены raw prompts, raw legal text, raw recommendation body, секреты и внутренние opaque carrier values, что уже соответствует существующим safety rules evidence-spine handoffs и правилам OpenTelemetry baggage security. Это удерживает публичную проекцию в роли projection-only surface и не даёт ей стать covert authority channel. fileciteturn46file0L3-L3 fileciteturn54file0L3-L3 citeturn11view1turn12view0

В результате acceptance criterion C8 формулируется так: producer coordination считается выполненной, если canonical handshake ledger может быть собран и провалидирован **без зависимости от одного service-local пути сборки**, а все serious producers — будь они вызваны из `nl_pipeline.py`, фонового workflow, replay runner или bundle inspector — используют один и тот же carrier, один и тот же record model и один и тот же closeout contract. `nl_pipeline.py` тогда остаётся orchestration entrypoint, но не является единственным местом, где handshake “существует”. fileciteturn29file0L3-L3 fileciteturn44file0L3-L3 fileciteturn45file0L3-L3

## Открытые вопросы и ограничения

Главное ограничение исследования — недоступность точного файла `POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md`. Поэтому я опирался на соседние active plans, принятые ADR и кодовые якоря, которые по смыслу явно описывают ту же эволюцию архитектуры.

Остаются четыре дизайн-вопроса, которые нужно закрепить уже в implementation phase. Во-первых, нужен конечный словарь `authority_role`, чтобы не возникла ещё одна параллельная taxonomy поверх existing execution/governance profiles. Во-вторых, надо решить, где живёт coordinator implementation: отдельный runtime-quality service, library-first validator или CAS-backed arbitration layer. В-третьих, нужно формально определить политику staleness: какие изменения входов делают approved handshake недействительным автоматически. В-четвёртых, стоит решить, допускаются ли “soft coordination” состояния для research-profile runs или для serious runs handshake всегда hard gate. Эти вопросы не ломают саму спецификацию, но влияют на миграцию схем и ergonomics исполнения. fileciteturn48file0L3-L3 fileciteturn44file0L3-L3

# Совместимость типов утверждений и методов в PolicyOS

## Кодовые опоры и что уже зафиксировано в системе

Исходной рамкой для этого исследования должен быть не «чистый лист», а уже существующий PolicyOS runtime. Активный исследовательский план прямо требует reuse-first подхода и отдельно фиксирует, что для C9 нужно не изобретать authority methods заново, а привязать уже существующие proof-bearing artifacts к `ClaimRecord`, semantic binding, Policy Design Case records и closeout. В dense context план также называет `claims/models.py`, `claim_support.py`, readiness/contracts, append-only lifecycle и IR analytics certificates как реальные load-bearing anchors, от которых и нужно стартовать. fileciteturn4file0L3-L3 fileciteturn3file0L3-L3

На уровне claim registry код уже задаёт достаточно жёсткий каркас. `ClaimType` включает `factual`, `causal`, `legal`, `normative`, `forecast`, `distributional`, `welfare`, `implementation` и `source_quality`; `ClaimSupportStatus` различает `unsupported`, `weakly_supported`, `supported`, `contested`, `refuted` и `not_evaluable`; `ClaimPublishability` различает `draft`, `internal_only`, `review_required`, `publishable` и `blocked`. Для publishable high-stakes claims модель уже требует `support_status == supported`, отсутствие unresolved counterevidence и отсутствие blocked reasons; кроме того, для `causal`, `legal`, `forecast`, `distributional` и `welfare` publishable claim должен иметь `evidence_refs`. Сам `ClaimRecord` уже содержит `uncertainty_profile_ref`, `provenance_ref`, `reviewer_refs`, `evidence_refs` и `counterevidence_refs`, то есть поверхность для claim-method binding в системе уже есть. fileciteturn8file0L3-L3

При этом в текущей кодовой базе есть три важные асимметрии, которые C9 должен не скрывать, а формально закрыть. Во-первых, `claim_support.py` определяет support families как `factual`, `legal`, `causal`, `numerical`, `forecast`, `distributional`, `welfare`, `implementation`, но не содержит отдельной family для `source_quality`; следовательно, `ClaimType.SOURCE_QUALITY` уже существует в registry, а в support taxonomy прямого семейства для него нет. Во-вторых, алиасы в `claim_support.py` сводят `normative` к `legal`, что слишком грубо для serious-mode semantic support: нормативное утверждение не равно юридическому утверждению, даже если они пересекаются. В-третьих, `readiness.py` считает `implementation` и `normative` decision-bearing claim types, но high-stakes list в claim-readiness и особенно строгая publishability guard в `ClaimRecord` не симметричны этому: implementation-claims decision-bearing, но не входят в тот же evidence-guard, что causal/forecast/welfare claims. Это не повод ломать существующую модель; это точка, где матрица C9 должна formalize upgrade path. Это вывод из сопоставления текущих модулей, а не внешняя догадка. fileciteturn12file0L3-L3 fileciteturn13file0L3-L3 fileciteturn8file0L3-L3 fileciteturn24file0L3-L3

Система уже содержит и enforcement surfaces, через которые эта матрица может стать блокирующей, а не декоративной. Append-only claim lifecycle требует явных lifecycle events для downgrade, block, unblocking, readiness updates и support updates; publishable claims нельзя «молча» удалять или тихо понижать. Параллельно `phase_barriers.py` фиксирует serious-run barriers и прямо требует для `FOUNDRY_METHOD_BACKING` доказательства по полям `foundry_method_selection`, `rejected_methods`, `assumptions`, `input_coverage`, `power_sample_adequacy`, `sensitivity`, `uncertainty` и `method_compatibility`, а для `FINAL_DECISION_ARTIFACT` — ещё и полный evidence package перед final artifact compilation. Это именно та точка, где mismatch может и должен блокироваться до финального policy draft. fileciteturn16file0L3-L3 fileciteturn41file0L3-L3

## Логика совместимости, которая уже следует из текущих контрактов

IR analytics в репозитории уже оформлены как typed proof surfaces, а не как свободный текст про «какую-то аналитику». Для bounds и partial identification есть `BoundMethod`, `BoundSoundnessLevel`, `TighteningStatus`, `PartialIdentificationResult` и machine-checkable `BoundsDualCertificateBundle`; для certified tightening есть finite search over certificate-carrying candidates; для missing-data recoverability есть `RecoverabilityCertificateStatus`; для path-specific identification — `PathSpecificDecisionMode`; для transportability — `TransportabilityStatus` и `TransportMode`; для proof reuse — `ProofComposabilityStatus`; для fairness — `FairnessDecomposition` и `CausalFairnessReport`; для strategic settings — `StrategicFallbackMode`, `StrategicDecompositionStatus` и `PerformativeLoopStabilityStatus`; для structural uncertainty — `CausalModelEnsemble`; для welfare — `WelfareBundle`, `GEUncertaintyBundle` и `ChannelDecompositionArtifact`. Иными словами, метод-authority baseline уже есть; C9 должен его нормализовать и привязать к claims. fileciteturn17file0L3-L3 fileciteturn18file0L3-L3 fileciteturn19file0L3-L3 fileciteturn20file0L3-L3 fileciteturn22file0L3-L3 fileciteturn27file0L3-L3 fileciteturn28file0L3-L3 fileciteturn29file0L3-L3 fileciteturn30file0L3-L3 fileciteturn36file0L3-L3 fileciteturn37file0L3-L3

Это хорошо согласуется и с исходной методологической литературой, которую PolicyOS фактически уже закодировал. В исследованиях Bareinboim и Pearl transportability формализуется как вопрос о том, можно ли перенести causal effect из одной популяции в другую по selection diagrams и do-calculus, что очень близко к `SelectionDiagram` и `TransportabilityResult` в репозитории. В работах Kusner и соавторов counterfactual fairness задаётся как неизменность решения при контрфактуальной замене protected attribute, а у Plecko и Bareinboim fairness decomposition явно раскладывает disparity на direct, indirect и spurious components; именно это и реализует текущий модуль `fairness.py`. Для path-specific effects соответствующая литература использует специальную идентификационную machinery для nested counterfactuals, а не generic regression labeling; это соответствует отдельному `PathSpecificIdentificationReport` с witness-based modes в коде. citeturn6academia3turn10academia1turn6academia0turn11academia3 fileciteturn22file0L3-L3 fileciteturn28file0L3-L3 fileciteturn20file0L3-L3

Из этого следует главный C9-принцип: один и тот же method artifact не даёт универсального права на любой текст утверждения. Он даёт право только на определённый тип claim wording. Partial identification, например, может поддержать bounded claim, но не sharp point claim, если bounds широкие или soundness только assumption-only/heuristic; negative certificate может очень сильно поддержать blocker claim, но не positive effect claim; proof composability может поддержать reuse of an old proof trace, но не является первичным доказательством новой causality statement; causal ensemble несёт uncertainty over model space, но не заменяет identifiability proof. Это соответствует и коду, и смыслу самих методов. fileciteturn17file0L3-L3 fileciteturn18file0L3-L3 fileciteturn25file0L3-L3 fileciteturn27file0L3-L3 fileciteturn30file0L3-L3 citeturn2academia2turn12academia0

Нормализованное правило статусов, которое я рекомендую для C9, выглядит так:

| Нормализованный класс статуса | Что он разрешает делать с claim |
| --- | --- |
| `exact`, `certified`, `identified`, `recoverable`, `reusable`, `ok` | Может поддержать позитивный claim, если выполнены seed-предикаты claim family и присутствуют обязательные refs. |
| `bounded`, `partially_identified`, `recoverable_under_assumptions`, `revalidate`, `selector_invariant`, `macro_abstracted` | Может поддержать только квалифицированный claim: interval/scenario/assumption-qualified wording, с явным uncertainty surface и limitation text. |
| `heuristic`, `assumption_only`, `partial`, `degraded` | Может оставаться internal/review-required, но не должен выходить как serious external authority без downgrade claim wording. |
| `blocked`, `unsupported`, `not_recoverable`, `blocked_with_witness`, `rederive`, `certified_unstable`, `failed` | Не может поддержать позитивный claim; может поддержать только blocker, limitation, invalidation, acquisition task или refusal-to-conclude. |

Это не новый статусный мир; это нормализация уже существующих enum-поверхностей в единый policy-facing semantics layer. fileciteturn17file0L3-L3 fileciteturn19file0L3-L3 fileciteturn20file0L3-L3 fileciteturn22file0L3-L3 fileciteturn27file0L3-L3 fileciteturn29file0L3-L3 fileciteturn37file0L3-L3

## Матрица совместимости claim-type и method

Ниже — предлагаемая serious-mode matrix, синтезированная из текущих `ClaimType`, support predicates, claim readiness rules, lifecycle constraints, phase barriers и IR analytics status surfaces. Смысл таблицы не в том, чтобы перечислить все возможные методы, а в том, чтобы определить, какие proof surfaces вообще имеют право поддерживать каждый тип утверждения — и при каком режиме статуса это допустимо. fileciteturn8file0L3-L3 fileciteturn12file0L3-L3 fileciteturn14file0L3-L3 fileciteturn24file0L3-L3 fileciteturn41file0L3-L3

| Тип утверждения | Что считать первичным методом поддержки | Что допустимо только условно | Что не может быть позитивной опорой | Что обязательно хранить рядом с claim |
| --- | --- | --- | --- | --- |
| `factual` | данные и provenance; для количественных factual claims — traceable numerical output | recoverability/transportability только как квалификатор полноты/переносимости данных | negative certificate, unsupported transportability | `evidence_refs`, `source_attribution`; для numeric factual — `method_output_ref` и numeric value |
| `legal` | applicabile norms + legal scope | эмпирические методы только для фактических посылок юридического вывода | IR causal certificates как замена legal grounding | `norm_refs`, jurisdiction/time scope, provenance |
| `normative` | явные warrants/value choices + при необходимости welfare/fairness/legal constraints | welfare/fairness как поддержка последствий, но не как замена value judgement | простое сведение normative к legal | отдельный normative warrant ref, evidence refs при consequential claims |
| `causal` | identifiability / partial identification / transportability / recoverability / path-specific / strategic decomposition в адаптивных сценариях | bounds-only, recoverable-under-assumptions, partially-identified transport, `revalidate` proof reuse | negative certificates, `not_recoverable`, `unsupported`, `blocked_with_witness`, `rederive` | `data_ref`, `method_ref`, `identification_strategy`, `uncertainty_ref`, output/bounds refs |
| `forecast` | forecast-specific model output с horizon и calibration; при shift/adaptation — transportability, strategic dynamics, ensemble uncertainty | bounded/scenario forecast, macro-abstracted strategic forecast, transport partial ID | bare “ML forecast”, uncertified unstable loop, unsupported transport | `method_ref`, `forecast_horizon`, `uncertainty_ref`, calibration/expiry refs |
| `distributional` | subgroup effect estimation, fairness decomposition, subgroup-aware transport/bounds | path-specific fairness, counterfactual fairness, ensemble uncertainty | scalar fairness score без subgroup surface; sparse unsupported subgroup output | `subgroup_ref`, `method_ref`, subgroup intervals/uncertainty, adequacy diagnostics |
| `welfare` | `WelfareBundle` + social weights + PE/GE uncertainty + channel decomposition при channel claims | robust/bounded welfare, strategic bounded equilibrium, partial welfare | welfare without explicit social weights, GE uncertainty or ambiguity surface | `welfare_metric`, `social_weight_ref`, uncertainty bundle, channel/ambiguity refs |
| `implementation` | implementation plan + feasibility + calibrated simulation/runtime evidence | simulation-only or macro-abstracted evidence для bounded implementation claims | “simulation says it works” без calibration, uncertainty или convergence | `implementation_plan_ref`, `feasibility_ref`, `simulation_result_ref`, calibration/convergence refs |
| `source_quality` | source contracts, lineage, audit, provenance, replay/authority surfaces | нет meaningful causal substitute; только auxiliary source checks | causal/fairness/forecast methods как primary support | `provenance_ref`, quality/lineage/audit refs |

Самые важные нетривиальные следствия этой матрицы три. Во-первых, `NegativeCertificate` — это не слабый лог и не «ошибка пайплайна», а first-class artifact для blocker claims и acquisition planning; он должен поддерживать утверждения вида «данный causal claim неидентифицируем при текущих предпосылках», но никогда не должен использоваться как позитивная опора для самого causal claim. Во-вторых, `ProofComposabilityCertificate` — это чисто auxiliary surface: он говорит, можно ли reuse/revalidate/rederive старый proof trace после composition, но не доказывает саму causal content claim заново. В-третьих, `CausalModelEnsemble` — это uncertainty adjunct: когда у ансамбля нет finite estimates, код сам строит огромный heuristic range и помечает envelope как `gate_eligible=False`; следовательно, one-line label «ансамбль моделей показал X» не должен проходить как serious support. fileciteturn25file0L3-L3 fileciteturn27file0L3-L3 fileciteturn30file0L3-L3

Отдельно подчеркну ещё два code-grounded upgrades, без которых матрица будет неполной. Первый: `normative` нужно разъединить с `legal` на уровне serious support, иначе система будет путать «это разрешено/запрещено по норме» с «это следует предпочесть по ценностной функции». Второй: implementation claims следует поднять до того же high-stakes режима, что и causal/forecast/welfare claims, поскольку сам runtime уже считает их decision-bearing. Иначе PolicyOS будет строже к causal effect claim, чем к claim’у вида «этот rollout operationally feasible», хотя второй в policy practice не менее рискованный. fileciteturn12file0L3-L3 fileciteturn24file0L3-L3 fileciteturn8file0L3-L3

## Отказ от общих ярлыков методов и runtime-проверка предпосылок

В serious profiles bare method labels должны отклоняться автоматически. Фразы вроде `regression`, `ML model`, `simulation`, `fairness checked`, `transported from study`, `expert judgment` или `handled missing data` не должны считаться valid method support, если из них нельзя восстановить typed method artifact, его статус, assumptions, output surface и failure mode. Это напрямую вытекает из того, что `FOUNDRY_METHOD_BACKING` уже требует `rejected_methods`, `assumptions`, `input_coverage`, `sensitivity`, `uncertainty` и `method_compatibility`, а сами IR modules везде задают status- и artifact-level contracts, а не текстовые метки. fileciteturn41file0L3-L3 fileciteturn17file0L3-L3 fileciteturn19file0L3-L3 fileciteturn22file0L3-L3 fileciteturn28file0L3-L3 fileciteturn44file0L3-L3

Для practical serious-mode rejection я бы зафиксировал следующий минимальный contract метода. Он должен однозначно раскрывать:
- какой estimand или theorem family он вообще пытается поддержать;
- какой у него status class и можно ли по нему делать point claim, bounded claim или только blocker claim;
- какие assumptions и scope restrictions он несёт;
- какие input/data/graph references были реально использованы;
- какие output refs и uncertainty surfaces он породил;
- какой negative or fallback surface существует, если метод не сработал. fileciteturn19file0L3-L3 fileciteturn22file0L3-L3 fileciteturn25file0L3-L3 fileciteturn36file0L3-L3

Runtime-проверка предпосылок должна зависеть от family метода. В текущем коде многие из этих checks существуют оффлайн или в artifact metadata, но не все ещё доведены до runtime gating surface.

| Семейство метода | Что нужно проверять на runtime, а не только offline |
| --- | --- |
| partial identification / certified bounds | соответствие текущих данных и variable encoding сертифицированной problem spec; support/positivity; не разошёлся ли certificate payload с текущим artifact set |
| recoverability | соответствует ли текущая missingness structure сертифицированному `mgraph_fingerprint`; совместим ли реально применённый estimator family с сертификатом recoverability |
| transportability | не вышел ли target context за selection-diagram assumptions; присутствуют ли required target data; не появились ли `data_gaps` или hard legal constraints |
| path-specific / proof composability | сохраняются ли witness/projection hashes; не поменялась ли graph composition так, что нужен `rederive`, а не blind replay |
| fairness / distributional | стабильны ли subgroup definitions, protected attribute pipeline и mediator sets; хватает ли subgroup support и sample adequacy |
| strategic / simulation | convergence, multiplicity, instability, calibration, feedback loop diagnostics; нет ли `certified_unstable` или unresolved multiple fixed points |
| welfare | валиден ли `social_weight_ref`; присутствуют ли `pe_uncertainty_refs`, `ge_uncertainty_ref`, ambiguity surfaces и fiscal-feedback links, если режим этого требует |

Эта таблица тоже не догадка «снаружи»: recoverability artifact уже несёт `mgraph_fingerprint`, proof steps и recommended estimator family; transportability artifact уже хранит `required_target_data`, `data_gaps`, `hard_legal_constraints` и fallback to partial identification; proof composability already distinguishes `revalidate` from `rederive`; fairness report already expects decomposition and fairness verdicts; strategic code already distinguishes exact/bounded/blocked fallback and certified convergence vs instability; welfare и simulation surfaces уже содержат uncertainty, calibration и feedback-related refs. fileciteturn19file0L3-L3 fileciteturn22file0L3-L3 fileciteturn27file0L3-L3 fileciteturn28file0L3-L3 fileciteturn29file0L3-L3 fileciteturn37file0L3-L3 fileciteturn40file0L3-L3 fileciteturn44file0L3-L3

## Референсы неопределённости для ключевых типов утверждений

`ClaimRecord` сейчас даёт только один `uncertainty_profile_ref`, но вокруг него уже есть богатая внутренняя экосистема uncertainty artifacts. У search/readiness layer есть typed uncertainty categories `statistical`, `structural`, `transport`, `measurement`, `model`, `optimization`; у IR analytics есть `UncertaintyEnvelope` с source, distribution family, propagation method и interval semantics; у welfare есть отдельные `pe_uncertainty_refs` и `ge_uncertainty_ref`; у simulation results есть `uncertainty_envelopes`, distributional/fairness/welfare refs и feedback result surfaces. Поэтому правильная стратегия C9 — не множить leaf refs в claim напрямую, а сделать `uncertainty_profile_ref` ссылкой на claim-specific bundle artifact. fileciteturn8file0L3-L3 fileciteturn31file0L3-L3 fileciteturn32file0L3-L3 fileciteturn37file0L3-L3 fileciteturn44file0L3-L3

Предлагаемая схема выглядит так:

| Тип утверждения | Куда должен указывать `uncertainty_profile_ref` | Что bundle обязан содержать |
| --- | --- | --- |
| `forecast` | новый `ForecastUncertaintyBundle` | horizon-specific intervals/quantiles, calibration window, residual diagnostics, expiry conditions, transport penalty при cross-context forecast |
| `causal` | новый `CausalClaimUncertaintyBundle` | identifiability status, point/bounds surface, sensitivity sweep, positivity diagnostics, ensemble contribution, recoverability/transport qualifiers |
| `distributional` | новый `DistributionalClaimUncertaintyBundle` | subgroup intervals, support counts/effective sample sizes, multiplicity note, sparse-cell warnings, fairness decomposition refs при необходимости |
| `welfare` | существующий `WelfareBundle` или wrapper над ним | `pe_uncertainty_refs`, `ge_uncertainty_ref`, interval semantics, `social_weight_ref`, `sample_bundle_ref`, channel/ambiguity refs |
| `implementation` | новый `ImplementationUncertaintyBundle` | `simulation_result_ref`, calibration refs, `uncertainty_envelopes`, observed-range refs, convergence/multiplicity refs, distributional/fairness sidecars |

Для welfare здесь особенно важно, что код уже сейчас требует гораздо более богатую uncertainty surface, чем generic `uncertainty_ref`. `WelfareBundle` хранит private-equilibrium uncertainty refs, GE uncertainty bundle, credibility/robust intervals, social-weight refs, channel decomposition, sample bundle и diagnostics; а `Phase3CertificateStatus` отдельно блокирует отсутствие welfare bundle, GE uncertainty, social-weight manifest, ambiguity certificate и, в нужных режимах, fiscal feedback и mechanism certificates. Значит, для welfare claims не надо изобретать новый листок uncertainty — надо сделать `WelfareBundle` canonical uncertainty carrier. fileciteturn37file0L3-L3 fileciteturn35file0L3-L3

Для simulation-backed implementation claims код уже тоже даёт почти готовую surface. `SimulationResult` связывает execution plan, metrics, trace slice, uncertainty envelopes, distributional report, welfare bundle, metric validation, fairness audit, propagation reports, feedback result и identifiability diagnostics. Отдельно `core/contracts/foundry.py` определяет `CalibrationReportRef`, `ObservedRangeBundleRef`, `FeedbackConvergenceCertificateRef` и `EquilibriumMultiplicityReportRef`, а `FeedbackConvergenceCertificate` различает `converged`, `diverged`, `oscillating`, `stagnated` и другие состояния. Следовательно, implementation claim с simulation support без calibration/convergence/multiplicity surface должен считаться не supported, а максимум review-required. fileciteturn38file0L3-L3 fileciteturn40file0L3-L3 fileciteturn44file0L3-L3

Самое важное conceptual extension здесь относится к forecast и distributional claims. В текущем `claim_support.py` forecast already requires `method_ref + uncertainty_ref + forecast_horizon`, что правильно. Но distributional support пока требует только `method_ref + subgroup_ref`; для serious-mode policy claims этого мало. Распределительный claim почти всегда должен нести subgroup-level uncertainty, иначе система сможет внешне публиковать heterogeneity assertion без интервалов, sparse-support warnings или multiplicity caveats. Я рекомендую сделать `uncertainty_ref` обязательным и для distributional claims в serious mode, даже если базовый seed-предикат в коде пока этого ещё не требует. Это именно extension-existing, а не greenfield redesign. fileciteturn12file0L3-L3 fileciteturn31file0L3-L3

## Как блокировать method-claim mismatch до финального policy draft

В терминах текущего runtime acceptance можно выполнить без новой архитектурной революции. Нужно вставить матрицу C9 как решающую таблицу между claim materialization и `FOUNDRY_METHOD_BACKING`. Практически это означает следующий fail-closed flow:

- сначала claim canonicalizes into one support family: `factual`, `factual:numerical`, `legal`, `normative`, `causal`, `forecast`, `distributional`, `welfare`, `implementation`, `source_quality`;
- затем система смотрит в compatibility matrix, какие method families вообще разрешены для этого claim type и какой status class нужен для positive wording;
- после этого runtime проверяет обязательные proof surfaces, uncertainty bundle и assumption-validation checks для выбранного метода;
- если surface неполный или статус метода слабее, чем wording claim’а, runtime не просто записывает warning, а эмитит `rejected_method`/`method_compatibility` blocker на barrier `FOUNDRY_METHOD_BACKING`;
- если claim уже существовал, downgrade проходит через append-only lifecycle event (`updated_support`, `updated_readiness`, `blocked`, `invalidated`, `marked_stale`), а не через тихую мутацию. fileciteturn41file0L3-L3 fileciteturn16file0L3-L3

Это хорошо стыкуется с текущими readiness semantics. Claim-level readiness уже переводит unsupported, not_evaluable, weakly_supported, contested, counterevidence-bearing и externally unattributed claims в `review_required` или `blocked`; ledger-level summary уже умеет сказать, есть ли publication blockers; а `FINAL_DECISION_ARTIFACT` barrier и public artifact barriers уже требуют полный method/data/legal/evidence package перед сборкой финального артефакта. Поэтому C9 не должен строить новый gating subsystem: достаточно, чтобы compatibility matrix производила нормализованный blocker surface, который существующие barriers и ledger-readiness уже умеют потреблять. fileciteturn24file0L3-L3 fileciteturn14file0L3-L3 fileciteturn41file0L3-L3

Итоговый вывод такой. В PolicyOS уже есть почти все основные строительные блоки для C9: claim registry, publishability/readiness semantics, append-only lifecycle, serious-run phase barriers и богатый набор typed analytics certificates. Само ядро задачи не в том, чтобы придумать новую taxonomy of methods, а в том, чтобы: сохранить существующие claim types как anchors; разъединить `normative` и `legal`; добавить explicit `source_quality` и `factual:numerical` handling; повысить implementation claims до high-stakes evidence discipline; и дать единое правило, согласно которому метод поддерживает не «всё подряд», а только claim wording подходящего класса — exact, bounded, blocker or auxiliary. Тогда method-claim mismatch действительно можно блокировать до `FINAL_DECISION_ARTIFACT`, то есть до финального policy draft в текущем runtime vocabulary. fileciteturn8file0L3-L3 fileciteturn12file0L3-L3 fileciteturn16file0L3-L3 fileciteturn24file0L3-L3 fileciteturn41file0L3-L3

# C10 для PolicyOS: модель базовых линий и сравнения альтернатив

## Что уже заложено в PolicyOS

Эта задача не является greenfield. В активном исследовательском плане C10 прямо закреплён как работа по превращению базовых линий и отвергнутых альтернатив в **первоклассные policy claims**, с опорой на Claim records, `HarmEnvelope`, adversarial scenario proposals, IR causal analytics, policy-design output и normative arbitration. Там же задано жёсткое acceptance-правило: рекомендация не может заявлять превосходство, если она показывает доказательства только для выбранного варианта. В соседних задачах план отдельно разводит contestability и disagreement (C17), а также tradeoff/welfare/value-choice semantics (C18), то есть C10 должен строить сравнение альтернатив так, чтобы не маскировать нормативный выбор под якобы чисто эмпирическую победу. fileciteturn8file0L3-L3 fileciteturn25file0L3-L3

В коде уже есть хороший каркас для такой модели. `ClaimRecord` хранит тип утверждения, `evidence_refs`, `counterevidence_refs`, `uncertainty_profile_ref`, причины блокировок и publishability; при этом publishable high-stakes claims не могут выходить наружу без `evidence_refs`, с нерешённым counterevidence или со скрытыми blocked reasons. Это особенно важно для C10: сравнительное утверждение «X лучше Y» уже сейчас должно мыслиться как claim с собственными evidence и counterevidence, а не как текстовое пояснение в policy brief. fileciteturn11file0L3-L3

Для рисков и хрупкости уже существует `HarmEnvelope`: он хранит `max_expected_harm_score`, группы риска и `rollback_triggers`. Это важная точка опоры: сравнительная модель в PolicyOS должна смотреть не только на выгоды и стоимость, но и на то, как вариант ведёт себя по harm-boundary и rollback-условиям. fileciteturn12file0L3-L3

Для стрессовых сравнений платформа уже умеет порождать adversarial scenarios. В `ScenarioAdversaryWorker` и fallback-логике есть типы `shift`, `noise`, `outlier`, `missing` и `targeting_fragility`; они пакуются в `AdversarialScenarioBundle` и используются для stress testing. Значит, C10 не должен заново изобретать fragility taxonomy: правильнее определить, когда эти уже существующие сценарии становятся именно **сравнительными baseline-объектами**. fileciteturn15file0L3-L3 fileciteturn16file0L3-L3

Нормативная часть тоже не пустая. `NormativeArbitrationResult` уже построен вокруг сравнения `proposal` и `baseline`, включает `option_matrix`, `per_stakeholder_utility`, `rights_audit`, `hard_constraint_audit`, `selected_option`, `winners`, `losers`, `residual_dissent` и `tradeoff_certificate`. Узел `run_normative_arbitration` прямо описан как модуль, который «formalize normative tradeoffs between proposal and baseline». Иначе говоря, в системе уже есть язык, чтобы отличать эмпирическое сравнение результатов от нормативного выбора между допустимыми вариантами. fileciteturn33file0L3-L3 fileciteturn35file0L3-L3

Также есть и текущие ограничения, которые C10 должен закрыть. `PolicyFrontierReport` и `RejectedAlternativesSummary` уже существуют, а builder сейчас помечает отклонённые альтернативы лишь как `infeasible`, `dominated_near_frontier` или `dominated`. Это полезный минимум, но он слишком беден для C10, потому что не различает, например, правовой запрет, слабость доказательств, явный value choice и «accepted deficit». Ещё важнее, что текущая проекция `project_policy_artifact_bundle_claims` в ClaimLedger создаёт лишь компактные claims о выбранном кандидате, Phase 3 gate и наличии readiness contract; comparative claims о том, **почему** кандидат превосходит альтернативу, в ledger пока не попадают. Это и есть один из ключевых bridge gaps для задачи C10. fileciteturn14file0L3-L3 fileciteturn39file0L3-L3 fileciteturn41file0L3-L3

## Какие внешние ориентиры стоит принять за норму

Свежие правительственные методички довольно согласованы в одном ключевом пункте: сравнение политики всегда должно начинаться с явного benchmark-а, а не с описания одного «любимого» варианта. В обновлённом британском Green Book бизнес-as-usual определяется как ожидаемый результат, если текущие arrangements продолжаются и предложение не реализуется; BAU обязательно переносится в shortlist appraisal и служит benchmark-ом, относительно которого сравниваются остальные опции. Тот же Green Book рекомендует включать в shortlist также `do minimum`, preferred option и варианты с большей/меньшей амбициозностью, а в summary table для каждой опции показывать не только value metrics, но и немонетизируемые эффекты, распределение по группам и местам, а также соответствующие риски и неопределённости. citeturn6view0turn17view0

Архивная, но всё ещё каноническая по формулировкам Circular A-4 OMB говорит почти то же самое другими словами: хороший regulatory analysis должен содержать statement of need, examination of alternative approaches и оценку benefits/costs для proposed action и основных alternatives; baseline обычно должен быть `no action`, а сравнения с `next best alternative` считаются особенно полезными. Там же прямо сказано, что итогом должна быть сводка benefit/cost estimates по каждой альтернативе, включая qualitative и non-monetized factors, чтобы читатель мог сравнивать именно альтернативы, а не только смотреть на одну выбранную опцию. citeturn12view2

Европейская Better Regulation Toolbox делает baseline ещё строже. Она определяет baseline как `no-policy-change` scenario, включающий релевантные действующие меры, допускает альтернативные baselines, если они помогают показать эффекты связанных инициатив, и подчёркивает, что плохо определённый baseline делает плохо определёнными и оценённые policy effects. В той же Toolbox явно сказано, что если credible alternatives к baseline почти не находятся, это надо специально и сильно обосновывать; discarded options должны быть объяснены отдельно, а причины могут включать legal feasibility, technical feasibility, previous policy choices, coherence, effectiveness and efficiency, proportionality, political feasibility, relevance и identifiability. Кроме того, Комиссия требует быть прозрачной в причинах несогласия с альтернативными взглядами. Для PolicyOS это очень сильная поддержка идеи, что rejected alternatives — не «пыль в памяти поиска», а часть публично проверяемой аргументации. citeturn12view0turn12view1turn9view2

Для именно counterfactual-мышления полезнее всего Magenta Book. Он определяет impact evaluation как оценку того, что изменилось и в какой мере изменения можно отнести на счёт интервенции **сверх того, что произошло бы и так**; для этого нужен counterfactual, то есть unaffected group/time period, служащий proxy for what would have happened in the absence of the intervention. Magenta Book отдельно требует, чтобы counterfactual был достаточного качества и объёма, был genuinely comparable к intervention group, а описываемый эффект можно было отличить от ожидаемого шума в данных; если robust counterfactual недостижим, допускаются theory-based approaches, synthetic control и другие менее прямые конструкции. Это даёт PolicyOS хороший критерий: не всякий baseline является хорошим counterfactual, и не всякая fragility probe может быть названа counterfactual baseline. citeturn15view0turn15view2turn15view3turn17view2

Наконец, для требований к доказательствам превосходства полезны NICE и GRADE. NICE требует для relative-effectiveness comparisons полно описывать характеристики и ограничения данных, исследовать heterogeneity, делать sensitivity analysis, если релевантность исследования сомнительна, и учитывать добавочную неопределённость, когда вывод делается из indirect evidence, а не из прямого head-to-head сравнения. GRADE, в свою очередь, требует оценивать certainty of evidence по каждому критически важному outcome, описывать и желательные, и нежелательные эффекты, использовать evidence profiles, а решения и рекомендации основывать на явных критериях с явными суждениями по каждому критерию; помимо эффектов, в эти критерии могут входить resources, equity, acceptability и feasibility. Для C10 это означает: superiority claim должен быть outcome-by-outcome, с явным certainty profile и с отдельным слоем нормативно-контекстных критериев. citeturn17view3turn18view0

## Предлагаемая семантика базовых линий

Мой основной вывод такой: для PolicyOS правильная единица не «одна baseline», а **stack of comparators**. Один и тот же policy candidate должен сравниваться как минимум с четырьмя разными сущностями, потому что они отвечают на разные вопросы. Это следует и из внешних appraisal/evaluation стандартов, и из того, как уже устроены `NormativeArbitrationResult`, `PolicyFrontierReport`, `HarmEnvelope` и adversarial scenarios в кодовой базе. fileciteturn12file0L3-L3 fileciteturn21file0L3-L3 fileciteturn33file0L3-L3 citeturn6view0turn12view0turn17view2

**Status quo baseline** должен означать не «если ничего не делать», а **наблюдаемое состояние в момент T0**. Это descriptive anchor: текущие показатели, действующие правила, текущая география, текущий таргетинг, текущее распределение harms/benefits. Он нужен для диагностики и для привязки claims к реальному миру, но сам по себе обычно не годится как основной comparator для policy superiority, потому что игнорирует естественную динамику. Такая трактовка хорошо согласуется с Magenta Book, где сравнение «что произошло?» и вопрос «что произошло бы anyway?» разводятся, и с EU Toolbox, где baseline строится как scenario, а не как голый snapshot. citeturn15view2turn12view0

**Business-as-usual baseline** должен быть главным динамическим comparator-ом. В терминах Green Book это outcome, ожидаемый при продолжении текущих arrangements без реализации предложения; в терминах EU Toolbox — no-policy-change / reference scenario, построенный на статус-кво политиках, действующих мерах и plausible baseline assumptions. Для PolicyOS BAU следует хранить как объект с явными допущениями, временным горизонтом, ожидаемыми внешними трендами и ссылками на источники этих допущений. Если BAU не выражен, recommendation-ready режим лучше не достигать: без BAU невозможно корректно интерпретировать ни выигрыш от действия, ни его opportunity cost. citeturn6view0turn12view0

**No-action baseline** должен быть отдельной сущностью, а не просто синонимом BAU. В ряде кейсов они совпадут, но в ряде — нет. `No action` отвечает на вопрос OMB: каким будет мир, если proposed rule or intervention не будет принят. BAU же может включать и уже запущенные внешние изменения, принятые меры других органов, истечение старых программ и так далее. Поэтому в модели C10 лучше допустить поля `status_quo_baseline`, `bau_baseline` и `no_action_baseline` как отдельные записи, даже если два или все три указывают на один и тот же underlying scenario. Такая избыточность полезна: она снимает двусмысленность между snapshot, dynamic reference scenario и decision-specific omission comparator. citeturn12view2turn12view0turn6view0

**Named alternative baseline** — это уже не «фон», а явный вариант Y, относительно которого можно делать claim вида `X > Y`. Сюда должны входить `do minimum`, phased rollout, repeal, lower ambition, higher ambition, другой delivery model, другой legal instrument, другой targeting rule, а также уже существующие Pareto-near-frontier кандидаты. Именно named alternatives должны быть обязательными для любых сильных превосходящих claims. Если в системе нет хотя бы одного осмысленного named alternative, итог может быть «selected under current constraints», но не «shown superior». Это прямо следует из acceptance rule C10 и полностью согласуется с Green Book, OMB A-4 и EU Toolbox. fileciteturn8file0L3-L3 citeturn6view0turn12view2turn12view1

## Когда fragility-сценарии становятся baseline-ами

Здесь полезно ввести жёсткое различие между **substantive counterfactual baseline** и **fragility baseline**. Counterfactual baseline отвечает на вопрос «каким был бы релевантный мир без X или при Y?». Fragility baseline отвечает на вопрос «что происходит с выводом о X против Y, если ломаются/сдвигаются критические предпосылки?». Magenta Book помогает держать эту границу: counterfactual должен быть genuinely comparable и пригодным для атрибуции эффекта, а не просто произвольной perturbation. citeturn17view2turn15view0

Для PolicyOS правило можно сформулировать так. Сценарий `shift`, `noise`, `outlier`, `missing` или `targeting_fragility` может считаться **counterfactual baseline** только если он описывает правдоподобный operational world, который decision-maker действительно должен был учитывать ex ante, и если сравнение в этом мире остаётся сравнением политик, а не только отказоустойчивости измерения. Во всех остальных случаях это **fragility baseline**, то есть challenge environment для robustness-claim, но не полноценный substitute для BAU или named alternative. Такая трактовка совместима и с repo-реализацией adversarial scenarios, и с европейским требованием анализировать uncertainty/sensitivity, если разные plausible assumptions могут вести к разным решениям. fileciteturn15file0L3-L3 fileciteturn16file0L3-L3 citeturn16view0turn16view1

По смыслу типы стоит развести так. `Shift` — это baseline для transportability/external-validity: смена состава популяции, внешней среды, институционального контекста, макроусловий. Он чаще всего может стать настоящим counterfactual baseline. `Targeting_fragility` — тоже часто substantive comparator, потому что меняет состав реально затронутых бенефициаров и потерпевших, а значит затрагивает distributional, rights и implementation claims. `Noise`, `missing` и `outlier` чаще следует считать fragility baseline-ами: они проверяют чувствительность вывода к measurement error, data incompleteness и tail-event leverage. Но если такие дефекты являются обычным свойством deployment reality, а не лабораторной атакой, тогда соответствующий сценарий надо повышать до real-world comparator и учитывать его уже в основном сравнении. Это особенно важно там, где eligibility, monitoring или rollback зависят от неполных и шумных данных. fileciteturn12file0L3-L3 fileciteturn16file0L3-L3 citeturn17view2turn16view1turn16view4

Практическое следствие для C10: у каждого recommendation-ready сравнения должны быть как минимум один **main comparator** (`BAU` или named alternative) и один **fragility comparator** по критическому риску. Для high-authority режимов я бы рекомендовал делать mandatory набор из `BAU + named alternative + fragility baseline`, потому что именно такая тройка позволяет отдельно проверить эффективность, сравнительное превосходство и устойчивость вывода. Это уже синтез, но он опирается на обязательность BAU в Green Book, полезность next-best alternative в A-4 и обязательность uncertainty/sensitivity reasoning в EU Toolbox и Magenta Book. citeturn6view0turn12view2turn16view1turn17view2

## Какие доказательства нужны для claims вида X превосходит Y

В PolicyOS сравнительное утверждение должно стать не одним claim, а **композитом claim-ов**. `X superior to Y` допустимо публиковать только если система может показать, на каком наборе критериев, в каком сравнительном мире, с какой степенью определённости и за счёт каких evidence bundles сделан вывод. Это естественно ложится на уже существующие `ClaimRecord`, `ClaimSupportStatus`, `counterevidence_refs`, `uncertainty_profile_ref` и отдельно на `NormativeArbitrationResult`. fileciteturn11file0L3-L3 fileciteturn20file0L3-L3 fileciteturn33file0L3-L3

Минимальный стандарт я бы зафиксировал так. Во-первых, comparator Y должен быть **явно зарегистрирован** и типизирован: BAU, no-action, named alternative или fragility baseline. Во-вторых, X и Y должны быть приведены к общему comparison envelope: население, география, время, legal scope, horizon, outcome definitions. Если это невозможно, PolicyOS должен выдать не superiority claim, а incompatibility/limitation claim. Это следует из Green Book, EU Toolbox и NICE: они последовательно требуют сопоставимого описания опций, baseline assumptions, comparator relevance и явного раскрытия ограничений данных. citeturn17view0turn12view0turn17view3

В-третьих, сравнение должно быть **symmetrical in evidence**. Доказательства должны существовать либо для обеих сторон, либо в виде единой модели/эксперимента, который даёт pairwise contrast. Evidence only for X не даёт права утверждать, что X лучше Y; максимум — что X supported on its own merits. Это не просто концептуальная аккуратность, а прямое следствие C10 acceptance rule, OMB A-4 и GRADE EtD логики, где решение основывается на явных критериях и evidence used for each judgment. fileciteturn8file0L3-L3 citeturn12view2turn18view0

В-четвёртых, superiority нужно проверять **по критическим outcomes**, а не по одному aggregate score. Для каждого критического outcome PolicyOS должен хранить ожидаемую разницу, uncertainty/bounds, чувствительность к baseline risk и directness of evidence. NICE здесь особенно полезен: он требует report-ить ограничения данных, исследовать heterogeneity, делать sensitivity analysis при сомнительной релевантности исследования и отдельно учитывать дополнительную неопределённость indirect comparisons. GRADE дополняет: certainty оценивается по каждому важному outcome, включая как benefits, так и harms. citeturn17view3turn18view0

В-пятых, сильное сравнительное заключение должно проходить через отдельные слои **hard constraints, rights и implementation**. Внутри PolicyOS это уже почти готово: `NormativeArbitrationResult` содержит rights audit и hard constraint audit, `PolicyEvaluationVector` хранит hard constraints и blocking reasons, а `HarmEnvelope` хранит at-risk groups и rollback triggers. Поэтому claim `X superior to Y` следует считать publishable только если одновременно выполнены три условия: X не нарушает hard constraints/rights на требуемом уровне authority; у X нет худшего harm profile по decision-critical рискам без явного value override; и эмпирический/каузальный/распределительный пакет по крайней мере на одном critical dimension действительно лучше, не будучи хуже на остальных decision-critical dimensions вне явно задокументированного normative tradeoff. fileciteturn21file0L3-L3 fileciteturn33file0L3-L3 fileciteturn12file0L3-L3

В-пятых же по другой оси, система обязана различать результаты вида `superior`, `non-inferior`, `tradeoff_noncomparable`, `indeterminate_due_uncertainty`, `blocked_by_rights`, `blocked_by_implementation` и `contested_value_choice`. Это лучше соответствует и C17/C18 из плана, и внешним frameworks, чем бинарное «лучше/хуже». На практике именно это снимет риск ложно-объективных рекомендаций там, где empirical frontier недоминантен, а решение зависит от социальных весов, распределительных предпочтений или acceptability/feasibility. fileciteturn25file0L3-L3 fileciteturn33file0L3-L3 citeturn18view0turn17view1

## Как должны выглядеть rejected-option records

Здесь я предлагаю расширить текущую `RejectedAlternativesSummary` из короткой search-memory записи в полноценный объект объяснимого отклонения. Сейчас builder хранит только `reason` и `near_frontier`, а причины фактически сводятся к `infeasible`, `dominated_near_frontier` и `dominated`. Для C10 этого недостаточно. Нужна более богатая причина отклонения, потому что «отклонено» может означать пять принципиально разных вещей: эмпирически хуже, юридически недопустимо, операционно нереализуемо, эпистемически неубедительно или не проиграло, но уступило по явному value choice. fileciteturn14file0L3-L3 fileciteturn39file0L3-L3

Я бы закрепил следующие primary reasons. `inferior_evidence` — сравнительный claim по опции не выдерживает проверки по certainty, directness или comparability, даже если идея опции сама по себе выглядит promising. `dominated_frontier` — опция не лучше по ни одному decision-critical empirical dimension и хуже хотя бы по одному, внутри одного и того же admissibility envelope. `legal_blocker` — права, компетенция, treaty/статутные ограничения или иные hard constraints не позволяют продвигать опцию. `implementation_infeasibility` — опция не может быть доставлена, мониторена, обеспечена или откатана на нужном уровне readiness. `value_choice` — вариант не доминирован, но проиграл после явного normative arbitration с задокументированными весами, winners/losers и residual dissent. `accepted_deficit` — вариант не признан плохим, но не может быть выбран сейчас без непропорционального evidence acquisition, задержки или снижения authority level. Такая типология хорошо мэппится и на существующие объекты PolicyOS, и на причины discarded options в EU Toolbox. fileciteturn33file0L3-L3 citeturn12view1

У каждой такой записи должны быть минимум следующие поля: `option_id`, `compared_to_option_id`, `baseline_kind`, `rejection_stage`, `primary_reason`, `secondary_reasons`, `evidence_refs`, `counterevidence_refs`, `uncertainty_ref`, `hard_constraint_refs`, `rights_audit_ref`, `harm_envelope_ref`, `near_frontier`, `revisitable`, `revisit_trigger`, `public_summary`. Особенно важны два последних: rejected alternative не должна исчезать в «чёрный ящик». Как требует EU Toolbox, discarded options должны быть explainable отдельно, а причины несогласия с альтернативными позициями — прозрачны. Для public/reviewer surfaces это означает, что пользователю нужно показывать не только «победивший» вариант, но и почему близкие альтернативы были сняты. citeturn12view1turn9view2

Отдельно стоит подчеркнуть: `value_choice` никогда не должен публиковаться как `empirical superiority`. Если два варианта недоминированы, а выбор зависит от распределительных предпочтений, социальных весов, acceptability или feasibility, то правильная запись — «selected by explicit normative rule», а не «proved better». Здесь лучше всего использовать уже существующий `NormativeArbitrationResult`, где есть `selected_option`, `policy_outcomes`, `residual_dissent`, `winners/losers` и `tradeoff_certificate`. Для C10 это значит не заменить normative arbitration, а сделать так, чтобы rejected-option record ссылался на него как на собственный источник объяснения value choice. fileciteturn33file0L3-L3 citeturn18view0

## Как это лучше всего встроить в PolicyOS

Наиболее аккуратный путь — не строить новый параллельный контур, а расширить уже существующие артефакты. Во-первых, нужен новый связующий record-family наподобие `baseline_and_option_comparison.v1`, который будет хранить определения baseline-ов, список named alternatives и pairwise comparison claims. Во-вторых, `RejectedAlternativeEntry` стоит расширить от одного `reason` к типизированной причине с evidence/uncertainty/legal/harm refs. В-третьих, `project_policy_artifact_bundle_claims` должен начать проецировать в ClaimLedger не только факт выбора кандидата, но и сами comparative claims: `candidate_X superior_to BAU on criterion C`, `candidate_X non_inferior_to option_Y on criterion D`, `option_Y rejected_due_to legal_blocker`, `comparison_indeterminate_due_to uncertainty`. Именно этого сейчас не хватает, чтобы C10 acceptance criterion реально исполнялся машиночитаемо, а не оставался только policy memo rule. fileciteturn41file0L3-L3 fileciteturn14file0L3-L3 fileciteturn39file0L3-L3

Практически я бы рекомендовал этот operating rule. На стадии longlist/shortlist каждый кандидат получает: статус-кво якорь, BAU/no-action scenario, минимум одну named alternative, один fragility baseline и ссылку на comparison matrix. На стадии output bundle в `PolicyFrontierReport` сохраняются frontier facts, в `NormativeArbitrationResult` — value-choice and dissent facts, а в `RejectedAlternativesSummary` — машинно-читаемые причины отклонения. На стадии claim projection система создаёт отдельные ClaimRecord-ы для comparative superiority / non-inferiority / indeterminacy / rejection reasons с `evidence_refs` и `counterevidence_refs` по обеим сторонам. На стадии public projection пользователь должен видеть summary matrix по образцу Green Book AST: чем каждая опция отличается от BAU/других, как распределяются impacts, какова неопределённость и почему одна опция предпочтительна или, наоборот, признана inferior. fileciteturn21file0L3-L3 fileciteturn33file0L3-L3 citeturn17view0turn17view1

В концентрированном виде итоговая модель C10 для PolicyOS выглядит так:

- **Baseline layer**: `status_quo`, `BAU`, `no_action`, `named_alternative`, `fragility_baseline`.
- **Comparison layer**: pairwise comparison по критическим outcomes, harms, subgroup distribution, legal/hard constraints, implementation, uncertainty.
- **Decision layer**: `superior`, `non_inferior`, `tradeoff_noncomparable`, `indeterminate`, `blocked`.
- **Rejection layer**: `inferior_evidence`, `dominated_frontier`, `legal_blocker`, `implementation_infeasibility`, `value_choice`, `accepted_deficit`.
- **Projection rule**: нельзя публиковать claim о превосходстве без evidence for both sides or shared contrast model; evidence only for selected option даёт максимум supported-option claim, но не superiority claim. fileciteturn8file0L3-L3 fileciteturn11file0L3-L3 citeturn12view2turn18view0

## Открытые вопросы и ограничения

Я сознательно делал этот вывод reuse-first, опираясь на уже найденные code anchors, а не как на blank-slate redesign. При этом я не проходил все вторичные consumer-paths вокруг Pareto registry, dashboard projection и every governance pass; поэтому некоторые детали wiring лучше считать implementation-level, а не conceptual-level выводом. fileciteturn24file0L3-L3 fileciteturn26file0L3-L3

Ещё одно ограничение: среди внешних источников самые сильные cross-domain опоры здесь — Green Book, Magenta Book и EU Better Regulation Toolbox. NICE и GRADE я использовал не как «универсальное policy law», а как лучшие доступные первичные шаблоны для требований к comparative evidence, certainty, directness, indirectness, benefits/harms и explicit decision criteria. Архивная Circular A-4 полезна как формулировка no-action baseline и alternatives analysis, но если для конкретного product-surface нужен strictly current US wording, PolicyOS потом стоит синхронизировать это с текущей White House/OIRA публикацией. citeturn12view2turn17view3turn18view0

Главный итог, однако, высокоуверенный: для C10 правильный design choice — это не «добавить колонку baseline», а сделать **сравнение альтернатив самостоятельной claim-bearing подсистемой**. В текущем состоянии репозиторий уже содержит почти все нужные кирпичи — claim spine, harm envelope, adversarial scenarios, frontier reports и normative arbitration — но ещё не связывает их в машинно-проверяемое comparative semantics ядро. Именно это ядро и должно стать output-ом C10. fileciteturn8file0L3-L3 fileciteturn11file0L3-L3 fileciteturn12file0L3-L3 fileciteturn14file0L3-L3 fileciteturn33file0L3-L3

# Числовая, временная и географическая семантика для PolicyOS

## Контекст

Задача C11 в активном плане PolicyOS требует не абстрактного «улучшения scope», а вполне конкретного результата: инвентаризации семантик единиц, валют, price base, exchange rate, inflation, календарей, географии, freshness, retention и coverage; введения канонических ролей времени; определения пяти исходов mismatch; установления authority-aware порогов для преобразований; и правила, по которому любое преобразование создает новые lineage- и authority-ref. Критерий приемки сформулирован жестко: несовпадения по времени, единицам, валюте, календарю, географии и freshness больше не должны тихо проходить как generic scope match. fileciteturn47file0L3-L3

Это не greenfield-задача. В реестре минимальных record family для Policy Design Case уже зафиксировано обязательное семейство `numeric_time_and_geography_semantics.v1`, а принятая ADR по concept spine уже требует, чтобы run spine замыкал географию, population, time, units, currency и calendars. Отдельная схема concept spine делает это еще более явно: для каждого canonical concept она требует `geography`, `time`, `units`, `currency`, `price_bases`, `exchange_rates`, `inflation_adjustments`, `calendars`, `freshness` и `world_refs`. Значит, C11 — это не изобретение новых смыслов с нуля, а унификация и ужесточение уже намеченных семантических поверхностей. fileciteturn43file0L3-L3 fileciteturn58file0L3-L3 fileciteturn62file0L3-L3

## Что уже есть в репозитории

В числовой части база уже довольно сильная. В `UnitsRegistry` есть отдельные типы для money, rate, duration и др.; денежная единица уже хранит `currency`, `nominal_year` и `price_base`, а metric registry явно связывает `metric_id` с `unit_id`. Производственный canary для data contract уже рассматривает `unit_refs`, `geography_refs`, `time_coverage_refs`, `freshness_ref`, `lineage_refs` и `transformation_refs` как отдельные semantic facets, а не как один общий «scope». Это очень важный сигнал: технический фундамент для fail-closed-семантики уже начат. fileciteturn56file0L3-L3 fileciteturn38file0L3-L3 fileciteturn4file0L3-L3

Во временной части семантика уже распределена по нескольким слоям. Runtime `TemporalScope` различает `evaluation_time`, `as_of`, `effective_start`, `effective_end`, hindsight window и forecast horizons; IR temporal logic уже использует не просто даты, а операторную логику и временные окна; Lex несет `as_of` / `as_of_date`; Scholar freshness отделяет `measured_at`, `evidence_as_of`, `freshness_deadline` и вычисляет stale/expiring/fresh; Fabric time-travel различает valid-time и transaction-time; SourceContract задает `freshness_slo_seconds` и retention-политику; Data Forge уже хранит по крайней мере `discovered_at`, `started_at`, `finished_at` и snapshot transaction `created_at`; DDM event contracts несут `timestamp` и reference/current monitoring windows. Иными словами, time roles уже существуют, но сегодня они рассредоточены по разным подсистемам и еще не сведены в один канонический словарь. fileciteturn7file0L3-L3 fileciteturn8file0L3-L3 fileciteturn5file0L3-L3 fileciteturn11file0L3-L3 fileciteturn12file0L3-L3 fileciteturn13file0L3-L3 fileciteturn10file0L3-L3 fileciteturn51file0L3-L3 fileciteturn52file0L3-L3 fileciteturn15file0L3-L3 fileciteturn28file0L3-L3 fileciteturn35file0L3-L3 fileciteturn36file0L3-L3

География и coverage тоже уже имеют зацепки. В schema concept spine география входит в обязательные поля canonical concept. В SDMX-контрактах прямо сказано, что статистические dataflow могут варьироваться по динамическим dimension columns вроде `LOCATION`, `SUBJECT`, `MEASURE`, а поток ECB EXR — по `FREQ`, `CURRENCY` и `CURRENCY_DENOM`; это прямое подтверждение, что currency/time/geography в статистических источниках приходят как самостоятельные измерения, а не как неформальные метки рядом со значением. DCAT-совместимая внешняя модель данных тоже поддерживает distinct temporal coverage, spatial coverage, spatial resolution, release date и modification date, то есть сама идея отделить coverage от publication-time и от representation-time полностью соответствует общепринятой модели каталогов данных. fileciteturn62file0L3-L3 fileciteturn57file0L3-L3 citeturn4view2turn4view3turn3view2turn6view0turn6view1

Authority- и lineage-основание для C11 тоже уже существует. ADR-0147 требует, чтобы authority-bearing artifacts несли authority envelope с provenance, owner, input refs, generated time, as-of time и blocking status, и запрещает нижним по authority поверхностям quietly synthesize или upgrade truth. ADR-0152 отдельно требует, чтобы semantic binding ledger связывал claims с unit bindings, geography bindings, time coverage, freshness и source/data lineage. Foundry equivalence уже задает строгое/расслабленное сравнение по полям и бюджетам tolerances, а UCUM различает equality и commensurability единиц. В сумме это дает очень сильную опору для C11: mismatch надо оценивать не как bool, а как typed relation между semantic signatures. fileciteturn60file0L3-L3 fileciteturn61file0L3-L3 fileciteturn40file0L3-L3 fileciteturn41file0L3-L3 citeturn13view0turn13view1

## Внешние стандарты, которые стоит зафиксировать в ADR

Для времени у PolicyOS не нужно изобретать собственный синтаксис. ISO 8601 и RFC 3339 уже задают международно понятное и machine-readable представление дат и времени; RFC 3339 требует полностью квалифицированные даты, четырехзначный год и явную связь времени с UTC offset, а ISO 8601 существует именно для устранения неоднозначности календарно-временных представлений. Поэтому все authority-bearing timestamps в C11 лучше жестко нормализовать к ISO 8601 / RFC 3339, а calendar/timezone semantics хранить дополнительно как явные поля, а не «угадывать» из строки даты. citeturn13view3turn3view8turn3view9turn2view0

Для единиц и валют внешняя база тоже понятна. BIPM задает SI base units как каноническую метрологическую основу; UCUM дает машиночитаемую систему кодирования единиц и, критически, различает literal equality и semantic equivalence/commensurability; ISO 4217 задает international currency codes, numeric/alpha codes и minor-unit semantics, а также показывает, что currency code — это самостоятельный standardized identifier, а не просто свободный текст. Следствие для C11 такое: PolicyOS должен хранить unit-system/id отдельно от currency code, а для money — еще и nominal year / price base / inflation-adjustment basis, потому что «100 UAH nominal» и «100 UAH in 2021 prices» — это не одна и та же семантика даже при одинаковом коде валюты. citeturn8view0turn13view0turn13view1turn13view2 fileciteturn56file0L3-L3

Для coverage, release/publication и lineage лучше не размывать роли. DCAT 3 различает `dcterms:temporal`, `dcterms:spatial`, `dcterms:issued`, `dcterms:modified`, а также temporal/spatial resolution; PROV-O определяет `wasDerivedFrom` как derivation/transformation одной сущности из другой и отдельно несет `generatedAtTime`. Если в PolicyOS одно и то же поле будет одновременно означать observation time, publication time и freshness time, это будет противоречить уже устоявшимся моделям данных и provenance. Для геометрии, когда в игру входят координаты, RFC 7946 дополнительно фиксирует для GeoJSON WGS 84 / CRS84 и единицы latitude/longitude в decimal degrees, то есть projection/CRS mismatch должен быть типизирован, а не тонуть в generic geography match. citeturn6view0turn6view1turn4view1turn4view2turn4view3turn3view0turn3view1turn3view7

## Основной вывод

Ключевой вывод исследования такой: в репозитории уже есть почти все «сырьевые» элементы C11 — units, money semantics, temporal scopes, as-of semantics, freshness, retention, time-travel, DDM timestamps, concept-spine fields, provenance и tolerance budgets, — но в просмотренных якорях я не увидел одного принятого слоя, который сводил бы их к единой authority-aware mismatch-algebra. Поэтому правильный ADR для C11 не должен добавлять еще один разрозненный словарь поверх существующих моделей; он должен определить единый `semantic_signature`, канонические time roles, typed mismatch outcomes и правила authority-preserving transformations, после чего заставить все readers и gates сравнивать evidence именно по этой сигнатуре. Это ровно согласуется с задачей плана и с уже принятыми ADR по authority ordering, semantic binding и concept spine. fileciteturn47file0L3-L3 fileciteturn58file0L3-L3 fileciteturn60file0L3-L3 fileciteturn61file0L3-L3

## Предлагаемая семантическая модель

Ядро ADR я бы сформулировал так: каждый claim, dataset binding, metric binding, legal binding и derived artifact должен нести не расплывчатый `scope`, а составную `semantic_signature` из следующих осей: `unit`, `measurement_kind`, `currency`, `minor_unit`, `nominal_year`, `price_base`, `exchange_rate_ref`, `inflation_adjustment_ref`, `calendar_id`, `timezone_or_offset`, `geography_ref`, `geography_level`, `geometry_or_region_semantics`, `coverage_ref`, `temporal_role`, `temporal_interval`, `freshness_ref`, `freshness_deadline`, `retention_deadline`, `lineage_refs`, `transformation_refs`, `authority_ref`. Такой шаг не ломает имеющийся код, а скорее собирает в одну проекцию то, что уже разбросано по UnitsRegistry, MetricRegistry, TemporalScope, SourceContract, Scholar freshness, concept spine и authority envelope. fileciteturn56file0L3-L3 fileciteturn38file0L3-L3 fileciteturn7file0L3-L3 fileciteturn12file0L3-L3 fileciteturn51file0L3-L3 fileciteturn60file0L3-L3 fileciteturn62file0L3-L3

Канонические time roles из C11 стоит не просто перечислить, а разбить по смысловым слоям. Для legal/policy слоя нужны как минимум `legal_as_of`, `legal_effective` и `policy_effective`; для data/platform слоя — `data_observation`, `data_valid`, `transaction`, `ingestion`, `publication`; для analytical/model слоя — `forecast`, `model`, `detection`, `claim_registry`, `replay`; для quality/lifecycle слоя — `freshness_deadline` и `retention_deadline`. Эта номенклатура естественно собирается из уже существующих полей Lex `as_of`, runtime `effective_*`, Fabric valid/transaction time, Data Forge discovery/build/snapshot timestamps, DDM event timestamps, Scholar freshness deadlines и SourceContract retention. Важно, что один timestamp может одновременно существовать у одного артефакта в нескольких ролях, но никогда не должен silently substitute one another. fileciteturn11file0L3-L3 fileciteturn7file0L3-L3 fileciteturn8file0L3-L3 fileciteturn10file0L3-L3 fileciteturn15file0L3-L3 fileciteturn28file0L3-L3 fileciteturn35file0L3-L3 fileciteturn36file0L3-L3 fileciteturn12file0L3-L3 fileciteturn52file0L3-L3 citeturn13view3turn3view8turn6view1

Mismatch outcomes я бы зафиксировал именно в той пятерке, которую требует план, но с более строгой операционной семантикой. `admissible` — сигнатуры совпадают либо эквивалентны без смысловой потери; `transform_required` — сущности commensurable, но нужен детерминированный и разрешенный authority-level transform; `projection_required` — underlying evidence не меняется, но consumer surface должен явно перепроецировать/переотформатировать представление; `limitation_required` — evidence остается usable only with an explicit limitation, readiness cap или publication caveat; `blocked` — нет безопасного или разрешенного пути привести mismatch к claim-compatible semantics. Концептуально это очень хорошо ложится на UCUM distinction between equality and commensurability, на Foundry strict/relaxed tolerances и на fail-closed authority ordering в ADR-0147. citeturn13view0turn13view1 fileciteturn40file0L3-L3 fileciteturn41file0L3-L3 fileciteturn60file0L3-L3 fileciteturn47file0L3-L3

Самая важная часть ADR — authority thresholds. Для research authority можно разрешать детерминированные преобразования вроде unit scaling, UTC/offset normalization, безопасного calendar mapping и наглядной projection геометрии, если сохранены input refs и provenance. Для governed/reviewer authority разрешения должны сузиться: допустимы только преобразования с явным transformation spec, ссылкой на conversion/index source и без потери claim-critical semantics; любые approximations автоматически поднимают `limitation_required`. Для production / `authority_bearing` evidence следует разрешать только те преобразования, которые: описаны в принятом ADR или registry; сохраняют same-input closure; создают новый derived artifact в CAS; несут authority envelope; и не подменяют observation/effective/publication/freshness roles друг другом. Все остальное должно либо блокироваться, либо понижаться до diagnostic/supporting evidence. Это прямо следует из уже принятого authority order и semantic binding rules. fileciteturn60file0L3-L3 fileciteturn61file0L3-L3

Любое `transform_required` должно порождать новый lineage node и новый authority ref. Минимальный контракт трансформации: `input_refs`, `output_ref`, `transformation_spec_id`, `performed_by`, `generated_at`, `source_semantic_signature`, `target_semantic_signature`, `conversion_sources`, `lossiness`, `reversibility`, `validation_status`, `authority_class_before`, `authority_class_after`. На языке внешних стандартов это соответствует `prov:wasDerivedFrom` и `prov:generatedAtTime`; на языке PolicyOS — правилам ADR-0147 о new envelope и ADR-0152 о traceability derived data back to source dataset facets, transformations and interpretation limits. Практический смысл простой: currency conversion, inflation adjustment, calendar alignment, geographic roll-up или CRS reprojection не имеют права «исчезать» внутри generic pipeline. citeturn3view0turn3view1 fileciteturn60file0L3-L3 fileciteturn61file0L3-L3

## Как зашить это в acceptance и тесты

Хороший acceptance для C11 должен проверять не наличие полей, а невозможность silent pass. Минимальный набор негативных и граничных кейсов я бы зафиксировал так. Во-первых, `UAH nominal` против `UAH, 2021 price base` — не `admissible`, а минимум `transform_required`, причем только если есть inflation index ref; иначе `blocked` или `limitation_required`. Во-вторых, одинаковая валюта, но разные `minor_unit`/rounding semantics — не generic money match. В-третьих, `legal_as_of` и `publication` совпадать не обязаны и не могут заменять друг друга в Lex/claim binding. В-четвертых, `data_valid` и `transaction` в Fabric тоже не взаимозаменяемы: бitemporal replay должен уметь воспроизвести обе оси. В-пятых, stale Scholar evidence после `freshness_deadline` не должно quietly проходить в authority-bearing portfolio, даже если само claim-scope совпадает. fileciteturn56file0L3-L3 fileciteturn11file0L3-L3 fileciteturn10file0L3-L3 fileciteturn12file0L3-L3 fileciteturn47file0L3-L3

Во второй группе тестов должны быть geography и calendar mismatches. Административный регион против point geometry — это не то же самое, что polygon coverage; для карты это может быть `projection_required`, но для claim о population coverage — уже `blocked` или `limitation_required`. Аналогично, monthly observation, quarterly aggregation и fiscal-year claim не должны считаться простым time match без явного calendar/aggregation transform. Для GeoJSON- и coordinate-based projections стоит явно тестировать CRS semantics; для catalog-like sources — отдельно проверять distinction между `temporal coverage`, `issued`, `modified`, `spatial coverage` и resolution. Только после таких тестов acceptance C11 действительно исполнит формулировку плана о запрете silent generic scope matches. citeturn3view7turn4view2turn4view3turn6view0turn6view1 fileciteturn57file0L3-L3 fileciteturn62file0L3-L3

С точки зрения самого ADR я бы рекомендовал структуру из семи decision blocks: проблема; каноническая `semantic_signature`; time-role registry; mismatch-outcome calculus; authority thresholds; transformation lineage contract; acceptance tests и failure codes. Такой ADR должен не заменить текущие модели, а стать общим reader contract для Lex, Fabric, Scholar, Foundry, Scientist, scorecard, readiness и projection layers. Это соответствует уже принятой линии репозитория: concept spine как единая reconciliation surface, semantic binding ledger как claim-support surface, authority envelope как truth boundary. fileciteturn58file0L3-L3 fileciteturn61file0L3-L3 fileciteturn60file0L3-L3

## Открытые вопросы и ограничения

Я просмотрел именно те якоря, которые прямо вытекают из C11 и ближайших принятых ADR, но не проводил исчерпывающий repo-wide аудит каждого файла на предмет already-existing calendar/XR/inflation logic. Поэтому главный вывод здесь не в том, что таких реализаций точно нигде нет, а в том, что в просмотренной authority-critical поверхности нет уже принятого единого mismatch calculus, который делал бы C11 закрытой задачей. fileciteturn47file0L3-L3

Еще одно ограничение: внешняя часть исследования хорошо покрывает общие стандарты представления времени, units, provenance и catalog semantics, однако я не поднял один центральный официальный документ, который бы в одиночку задавал всю policy-уровневую семантику `exchange_rate_ref` и `inflation_adjustment_ref`. Поэтому рекомендации по FX/CPI части ниже уровня ISO 4217 опираются прежде всего на внутренние поля репозитория — `price_base`, `exchange_rates`, `inflation_adjustments` — и на общую fail-closed логику provenance/issued/modified/coverage, а не на один внешний «master standard». fileciteturn56file0L3-L3 fileciteturn62file0L3-L3 citeturn13view2turn6view0turn6view1turn3view0turn3view1

В практическом смысле это не мешает главному выводу: для PolicyOS лучший следующий артефакт по C11 — это не еще одна domain memo, а принятый ADR, который делает `numeric_time_and_geography_semantics` общей обязательной семантической сигнатурой и запрещает любому reader/gate трактовать unit/time/currency/calendar/geography/freshness mismatch как простой boolean scope match. Именно в таком виде C11 естественно замыкает уже существующие решения по concept spine, semantic binding и authority ordering. fileciteturn43file0L3-L3 fileciteturn58file0L3-L3 fileciteturn60file0L3-L3 fileciteturn61file0L3-L3

# C13 Effective Independence And Evidence-Line Collapse For PolicyOS

## Что задаёт рамка C13

Я прочитал полный исследовательский план `POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md` и опираюсь именно на него, а не на «чистый лист». В плане C13 сформулирован как задача сделать силу доказательства функцией **независимости линий**, а не сырого числа источников. При этом стартовыми якорями названы уже существующие поверхности в коде: Foundry consensus/equivalence, `proof_composability.py`, `causal_ensemble.py`, Scholar bundles, Fabric lineage, agent-simulation truth manifests, legal source refs и prompt/model paths. План прямо требует определить идентичность evidence line, причины схлопывания, функцию `effective_independence(line_a, line_b) -> [0,1]`, правила агрегации портфеля и примеры, где число источников растёт, а эффективная независимая поддержка — нет. C13 также является прямыми воротами для инженерной задачи E13, где уже ожидается downweighting зависимых линий и отчёты по effective independent support вместо raw count. fileciteturn8file0L1-L3 fileciteturn10file0L1-L3

План одновременно важен и в более широком контексте: он уже фиксирует, что у PolicyOS есть сильные producers и proof-bearing артефакты, но системная слабость часто находится в мостах между ними, в API-поверхностях и в closeout-видимости доказательств. Для C13 это означает, что правильный результат — не новая изолированная схема, а **универсальная алгебра зависимости**, которая может читать существующие артефакты и объяснять, когда несколько линий — это на самом деле одна линия, переупакованная несколько раз. fileciteturn5file0L1-L3 fileciteturn6file0L1-L3

## Что уже есть в кодовой базе и чего не хватает

В коде уже есть хороший фундамент для replay-aware зависимости. В `proof_composability.py` определены статусы `REUSABLE`, `REVALIDATE`, `REDERIVE` и `UNKNOWN`, а также машинно-проверяемые свидетели, причины инвалидации, preserved/broken witness ids и логика консервативного вывода статуса. Это не решает независимость само по себе, но даёт очень сильный сигнал о том, насколько новая «линия» является воспроизведением старого доказательства, повторной локальной валидацией или реально новой деривацией. fileciteturn12file0L1-L3 fileciteturn13file0L1-L3

В `causal_ensemble.py` уже есть `EnsembleMember` с `graph_ref`, `discovery_method`, `weight` и `bootstrap_stability`, а также сам `CausalModelEnsemble` с `consensus_graph_ref` и `edge_inclusion_frequency`. Это достаточная база, чтобы говорить: «agreement между участниками ансамбля уже есть», но **независимость участников ещё не формализована**. Если шесть членов ансамбля обучены одной и той же методической семьёй на тех же данных и с тем же preprocessing, то их согласие не должно искусственно раздувать поддержку так, как если бы это были разные идентификационные семейства. fileciteturn14file0L1-L3

Scholar уже умеет хранить query graph, source metadata, quality signals, duplicate markers по `content_sha256`, snippets и claim-support links. В `scoring.py` есть явная детекция дубликатов источника по хэшу fetched payload, а в `models.py` — поля для `duplicate_of_source_id`, `published_at`, `source_type`, `quality_score` и claim-bound snippet links. Это означает, что первичный слой «один и тот же fetched document не считаем многократно» в системе уже фактически существует. Но C13 справедливо требует двигаться дальше: от page-level duplicate detection к авторским, институциональным, дата-сетным, citation-network и replication-lineage зависимостям. fileciteturn18file0L1-L3 fileciteturn19file0L1-L3

Fabric уже несёт важные маркеры зависимости на стороне данных. `SourceContract` v2 включает schema, replay, lineage seed, trust tier, calibration status, SLA, retention и deprecation policy. Особенно важны `replay`, `lineage`, `source_trust`, `retention` и content hashing контракта: они дают естественные ключи для распознавания одной и той же исходной data-line с разными производными артефактами. Это означает, что «сырой реестр», «очищенный parquet», «dashboard export» и «модельный feature table» могут быть разными артефактами, но одной evidence line, если их lineage-root общий. fileciteturn21file0L1-L3 fileciteturn22file0L1-L3

Для model-assisted шагов уже есть ledger prompt/tool/parser authority. `prompt_tool_ledger.py` хранит `template_id`, `template_version`, fingerprints, `provider`, `model`, `model_fingerprint`, `provider_config_ref`, tool schemas и authority handoffs. Значит, prompt/model path можно формализовать не как расплывчатую эвристику, а как конкретный collapse channel: один и тот же шаблон, одна и та же модель, один и тот же provider config и те же входные ссылки образуют почти одну и ту же линию, даже если текстовое оформление ответа немного отличается. fileciteturn30file0L1-L3

Для agent simulation у PolicyOS уже есть runtime-пакет `agent_sim`, а README прямо указывает на `world/` как место truth-centric synthetic worlds, DGP templates, truth APIs и evaluation hooks. В `wiring/contracts.py` уже нормализуются intervention mechanism parameters и другие control-side конфиги. Однако именно retrieved world-schema я через доступные ответы коннектора не извлёк, поэтому здесь есть честное ограничение: по simulation lineage я могу надёжно опереться на README и wiring contracts, но не на конкретную retrieved truth-manifest модель. Тем не менее направление C13 по simulation independence из плана полностью согласуется с видимой архитектурой. fileciteturn27file0L1-L3 fileciteturn29file0L1-L3

Внешняя литература поддерживает эту линию. В мета-анализе давно признано, что зависимые effect sizes нельзя обрабатывать так, будто они независимы: robust variance estimation как раз создана для случаев, где корреляция между эффектами сложна и неизвестна. Аналогично, повторные и дублирующие case reports в фармаконадзоре мешают статистическому анализу и вводят клиническую оценку в заблуждение. А в citation networks сами паттерны цитирования могут быть систематически искажены социальными факторами, причём низкая citation fidelity в одной работе снижает fidelity у последующих работ, которые цитируют её как промежуточное звено. Всё это усиливает основной тезис C13: количество линий без учёта зависимости легко создаёт ложную уверенность. citeturn9academia4turn15academia1turn14academia2turn14academia4

## Предлагаемая алгебра эффективной независимости

### Определение evidence-line identity

Для C13 я предлагаю считать **evidence line** не «документом» и не «цитатой», а минимальной поддерживающей единицей, которая может нести claim-support после схлопывания поверхностных дубликатов. Формально линия — это не один файл, а канонический объект со следующими полями:

```text
LineIdentity =
  claim_ref
  + stance
  + scope_ref
  + source_family
  + primary_root_ref
  + lineage_ref
  + transform_ref
  + method_family
  + identification_strategy
  + preprocessing_hash
  + dataset_ref
  + author_pool_hash
  + institution_pool_hash
  + legal_source_ref
  + prompt_model_path_hash
  + assumption_bundle_hash
  + calibration_source_ref
  + simulation_lineage_ref
  + review_status
  + proof_replay_anchor
```

Это определение — осознанная интерпретация архитектурных якорей из плана и кода: Fabric даёт lineage/replay/trust, Scholar — source metadata, snippets и duplicate markers, Foundry/IR — method family, proof/composability и ensembles, runtime — prompt/model path. fileciteturn8file0L1-L3 fileciteturn12file0L1-L3 fileciteturn14file0L1-L3 fileciteturn18file0L1-L3 fileciteturn21file0L1-L3 fileciteturn30file0L1-L3

Практический смысл такой: у одной claim-support line должен быть один **root of dependence**. Всё, что лишь перепаковывает тот же root без самостоятельной новой идентификационной стратегии, не должно считаться новым независимым голосом.

### Каналы схлопывания

Ниже — канонический набор collapse channels, который прямо закрывает требования C13 и хорошо согласуется с тем, как в науке и моделировании понимают зависимость источников. Зависимые эффекты, дублирующие публикации, повторные отчёты по одному кейсу и социально зависимые цитаты давно считаются источниками ложного накопления свидетельств. citeturn9academia4turn15academia1turn14academia2turn14academia4

| Канал | Что означает | Типичный сигнал схлопывания |
| --- | --- | --- |
| Shared primary source | Разные документы пересказывают один и тот же первичный материал | одинаковый `primary_root_ref` |
| Transformation lineage | Разные артефакты производны от одного lineage root | общий `lineage_ref` или `transform_ref` |
| Author pool | Перекрывающиеся команды авторов | высокий Jaccard по авторским id |
| Institutional pool | Одни и те же организации, labs, ministries, vendors | общий `institution_pool_hash` |
| Identification strategy | Один и тот же causal design или inferential lever | одинаковый `identification_strategy` |
| Method family | Один и тот же класс методов | одинаковый `method_family` |
| Preprocessing | Одинаковый cleaning/feature pipeline | общий `preprocessing_hash` |
| Prompt/model path | Один и тот же model-assisted route | общий `prompt_model_path_hash` |
| Legal source | Один и тот же нормативный текст в разных пересказах | общий `legal_source_ref` |
| Shared assumptions | Одинаковый assumption bundle или calibration basis | общий `assumption_bundle_hash` |
| Simulation lineage | Один и тот же DGP, world family, mechanism family | общий `simulation_lineage_ref` |
| Citation-network dependence | Источники образуют цепочку, а не независимое подтверждение | сильная локальная proximity в citation graph |

Смысл последнего канала особенно важен для Scholar: citation-network proximity — это не автоматический запрет, но **штраф за производную вторичность**. Работа, которая в основном опирается на один недалёкий кластер взаимных цитат или на social proximity, не должна получать ту же независимую силу, что внешняя репликация на другой выборке, другой командой и другим дизайном. На это указывают как исследования влияния collaboration networks на citation practices, так и более новая работа о citation fidelity и “telephone effect”. citeturn14academia2turn14academia4

### Параwise функция effective_independence

Я предлагаю двухшаговую функцию: сначала считаем **dependence**, потом переводим её в independence.

Пусть для каждой пары линий `a`, `b` есть набор overlap-функций `o_k(a,b) ∈ [0,1]`, по одной на каждый collapse channel. Тогда:

```text
dependence(a,b)
  = 1 - Π_k (1 - λ_k * o_k(a,b))

effective_independence(a,b)
  = 1 - dependence(a,b)
```

Здесь `λ_k` — веса каналов. Для production-grade claims я бы задавал высокий приоритет каналам `shared primary source`, `transformation lineage`, `legal source`, `prompt/model path` и `shared assumptions`, потому что именно они чаще всего создают ложное впечатление «многочисленности». Для exploratory research режимов веса можно сделать мягче. Эта форма хороша тем, что она:

- даёт 1.0 только при полном отсутствии релевантных зависимостей;
- быстро схлопывает пару при наличии нескольких сильных overlaps;
- не требует искусственно решать, какой канал «единственно настоящий»: зависимости компонуются.  

Именно такая композиция соответствует логике плана C13 о множественных причинах схлопывания и внешней методологической практике работы с зависимыми наблюдениями. fileciteturn8file0L1-L3 citeturn9academia4turn15academia1

### Replay-якоря из proof composability

Статусы `REUSABLE`, `REVALIDATE`, `REDERIVE`, `UNKNOWN` нужно использовать не как итоговую independence-метку, а как **нижние или верхние ограничения на зависимость пары**, если линии связаны общим proof lineage. Код уже задаёт их операционный смысл: reusable — прежние witnesses сохранены; revalidate — форма трассы сохранена, но локальные обязательства надо перепроверить; rederive — критический witness сломан и слепой replay несостоятелен; unknown — ядеро не заявляет безопасный режим повторного использования. fileciteturn12file0L1-L3 fileciteturn13file0L1-L3

Практически это даёт такой якорь:

- **REUSABLE**: считать почти той же линией, если и claim scope тот же. Рекомендуемый dependence floor: `≥ 0.95`.
- **REVALIDATE**: считать частично той же линией. Dependence floor: `≥ 0.70`.
- **REDERIVE**: shared ancestry признаётся, но новый вывод может считаться частично независимым, если различаются assumptions, graph composition или identification path. Dependence floor можно не задавать жёстко; использовать только остальные overlap-каналы и мягкий replay prior.
- **UNKNOWN**: не считать независимой линией по умолчанию для high-authority mode; применять осторожный dependence prior, например `0.40–0.60`, пока нет других сигналов.

Это очень важно: `REDERIVE` — **не** автоматическая независимость. Он означает только, что blind replay больше нельзя считать sound; shared ancestry никуда не исчезает.

## Правила агрегации портфеля

### Общий принцип

Сначала надо агрегировать не документы, а **collapsed lines**. То есть pipeline должен идти в таком порядке:

```text
raw artifacts
  -> canonical line identities
  -> pairwise dependence matrix
  -> collapse clusters
  -> stance-aware portfolio aggregation
```

Только после этого можно говорить о support count. Иначе система будет постоянно награждать дублирование. Этот порядок полностью соответствует направлению C13 -> E13 в плане, где сначала вводится line identity и collapse reasons, а потом downweighting dependent evidence lines в портфеле. fileciteturn8file0L1-L3 fileciteturn10file0L1-L3

### Strong-collapse rule

Если выполнено хотя бы одно из условий ниже, линии следует схлопывать **жёстко**, а не просто слегка downweighting:

- одинаковый `primary_root_ref`;
- одинаковый `legal_source_ref` для той же нормы и версии;
- одинаковый `lineage_ref` с чисто трансформационным отличием;
- одинаковый proof trace/witness lineage со статусом `REUSABLE`;
- одинаковый `prompt_model_path_hash` и те же `rendered_input_refs`.

В таких случаях raw-count должен остаться видимым лишь как аудитный след, но не как additive support. Основание для такого жёсткого режима уже есть и в коде, и во внешней методологии: duplicate reports и non-independent effect sizes искажают оценку силы доказательства. fileciteturn12file0L1-L3 fileciteturn19file0L1-L3 fileciteturn30file0L1-L3 citeturn9academia4turn15academia1

### Effective independent count

Для уже collapsed, но не тождественных линий я рекомендую считать effective independent support через матричную форму, аналогичную effective sample size under dependence:

```text
R_ii = 1
R_ij = dependence(line_i, line_j)

N_eff = (Σ_i w_i)^2 / (wᵀ R w)
```

Где `w_i` — вес линии после quality/admissibility filtering. У этой формулы хорошие свойства как у диагностического счётчика:

- если линии полностью независимы, `N_eff` стремится к числу линий;
- если линии почти одинаковы, `N_eff` стремится к 1;
- если есть кластеры, результат лежит между raw count и числом кластеров.

Это не тождественно «медицинскому мета-анализу», но концептуально опирается на то же понимание: зависимость уменьшает реальный объём новой информации. В литературе такой ход согласуется и с robust handling dependent effect sizes, и с понятием effective sample size under correlation. citeturn9academia4turn13search1turn13search3

### Support mass и conflict mass

Для PolicyOS одного `N_eff` недостаточно. Нужны как минимум три отдельные величины:

- `support_eff_mass` — эффективная независимая поддержка claim;
- `counter_eff_mass` — эффективная независимая контрподдержка;
- `limitation_eff_mass` — независимая масса ограничений и caveats.

Я рекомендую считать их **раздельно по stance**, а не смешивать всё в один scalar. Это лучше соответствует общей архитектуре PolicyOS, где contested evidence, limitations и blockers — first-class состояния, а также внешней практике, где конфликт и зависимость нельзя сводить к простому «усреднению за всё хорошее». fileciteturn5file0L1-L3 fileciteturn8file0L1-L3

### Специальные правила для разных семейств доказательств

Для **Scholar** новая независимость должна появляться только если хотя бы один из следующих блоков меняется существенно: авторский пул, институциональный пул, dataset, identification strategy, review status, replication lineage. Иначе это скорее corroborative echo, чем новая независимая линия. Это особенно важно потому, что citation networks и collaboration proximity могут создавать видимость «многих голосов», оставаясь внутри одного социального кластера. fileciteturn18file0L1-L3 citeturn14academia2turn14academia4

Для **Fabric** новая независимость требует нового lineage root или действительно нового первичного источника. Новый csv, parquet, dashboard export, feature table или другая нарезка той же записи — не новая линия. fileciteturn21file0L1-L3 fileciteturn22file0L1-L3

Для **IR proofs** новый bundle с `REUSABLE` на том же trace не новая линия; `REVALIDATE` — частично новая; `REDERIVE` — потенциально новая, но только при новом graph/assumption path. fileciteturn12file0L1-L3 fileciteturn13file0L1-L3

Для **ensembles** новая независимость появляется на уровне method family / identification family / feature or preprocessing family / training data split, а не на уровне «ещё один член ансамбля». Внешняя литература по ensembles последовательно показывает, что качество ансамбля зависит от diversity, а не просто от числа членов, и что предпосылка независимости участников является сильной и проблемной. fileciteturn14file0L1-L3 citeturn11academia0turn11academia4

Для **agent simulation** разные random seeds почти никогда не достаточны для новой независимой линии. Нужны отличимые mechanism parameter assumptions, другая calibration source, отдельно описанные sensitivity bounds и отдельная simulation lineage. Современная практика калибровки стохастических ABM и протоколы описания моделей подчёркивают, что без явной калибровки, sensitivity analysis и прозрачного model description кажущаяся вариативность прогонов не равна независимому подтверждению. fileciteturn27file0L1-L3 fileciteturn29file0L1-L3 citeturn9academia2turn19academia2

## Примеры схлопывания линий

### Когда raw source count растёт, но независимая поддержка — нет

**Случай Scholar с shared dataset и shared authors.**  
Пусть claim поддерживают пять статей. На поверхности это raw count = 5. Но три статьи написаны тем же ядром авторов, все пять используют один и тот же административный dataset, четыре из пяти используют один и тот же difference-in-differences design, а две статьи в основном цитируют друг друга и один исходный paper. В такой конфигурации новые линии почти не прибавляют новой информации; разумный результат — один основной cluster и, возможно, одна слабая частично независимая реплика. Иными словами, raw count = 5, а `N_eff` ближе к 1–2, а не к 5. Это ровно тот тип случая, который C13 обязан различать. fileciteturn8file0L1-L3 citeturn9academia4turn14academia2turn14academia4

**Случай Fabric lineage chain.**  
Есть первичный госреестр, затем curated snapshot, затем feature table, затем публичный dashboard export. Наивный счётчик скажет «четыре источника». Но `SourceContract.lineage`, replay evidence и root seed указывают, что это одна data line с разными трансформациями. При claim support такой портфель должен давать raw artifacts = 4, collapsed lines = 1. Новая независимая поддержка появляется только если приходит второй первичный реестр или независимый survey/administrative source, а не ещё один derivative export. fileciteturn21file0L1-L3 fileciteturn22file0L1-L3

**Случай proof replay inflation.**  
Есть один исходный proof bundle и две последующие compose/replay операции, по которым статус `REUSABLE`. Наивный отчёт может показать три сертификата и выглядеть как «тройное подтверждение». Но по смыслу `REUSABLE` означает, что witnesses сохранены и replayed step retained its original witness. Значит, это не три независимых линии, а одна и та же доказательная линия, появившаяся в трёх местах пайплайна. Эффективная независимая поддержка не увеличивается. fileciteturn12file0L1-L3 fileciteturn13file0L1-L3

**Случай clustered ensemble.**  
Есть восемь участников causal ensemble. Шесть пришли из одного `discovery_method` и одного data/preprocessing family; два — из другой family. Raw count = 8, но независимый вклад несопоставим с восемью по-настоящему разными стратегиями. Такой портфель должен репортить не только member count, но и family-clustered `N_eff`, который может оказаться, например, около 2–3. Внешняя литература по ensemble diversity настаивает именно на этом: выгода ансамбля зависит от разнообразия, а не от простого наращивания близких членов. fileciteturn14file0L1-L3 citeturn11academia0turn11academia4

**Случай agent simulation по seed inflation.**  
Есть двадцать прогонов симуляции с разными random seeds, но одним и тем же world family, одним и тем же calibration source, теми же mechanism parameter assumptions и одной чувствительностной рамкой. Raw run count = 20. Но это не двадцать независимых evidence lines, а одна simulation family с внутрисемейной вариативностью. Если же появляются два дополнительных мира с другой структурой механизма и другой calibration source, тогда именно они, а не новые seeds, начинают повышать независимую силу. Это соответствует как формулировке C13, так и общим требованиям к калибровке и sensitivity analysis стохастических ABM. fileciteturn8file0L1-L3 fileciteturn27file0L1-L3 fileciteturn29file0L1-L3 citeturn9academia2turn19academia2

**Случай legal-source echo.**  
Есть статья закона, министерское разъяснение, мемо агентства и аналитическая записка консалтинга, все опираются на один и тот же нормативный текст той же редакции. Raw source count = 4, но независимая правовая поддержка по существу равна 1 официальному источнику плюс, возможно, контекстуальные интерпретации. Для serious legal authority это должен быть один `legal_source_ref`, а остальные линии — derivative interpretation, а не самостоятельные независимые опоры. Это полностью согласуется с задачей C13 про legal source collapse и с policy-plan требованием graded legal admissibility. fileciteturn8file0L1-L3 fileciteturn7file0L1-L3

## Практический дизайн для реализации в PolicyOS

Если переводить эту концепцию в implementation-ready язык, то я бы рекомендовал такой минимальный дизайн surface.

Во-первых, каждой line присваивается `line_id` и `line_identity_record`, а рядом — массив `collapse_reasons`. Во-вторых, pairwise calculator строит `dependence_matrix` и `effective_independence_matrix`. В-третьих, portfolio report хранит одновременно `raw_line_count`, `collapse_cluster_count`, `N_eff`, `support_eff_mass`, `counter_eff_mass` и пояснение, какие линии схлопнулись и почему. Эта тройка surfaces напрямую отвечает тому, что уже написано в E13: implement evidence-line identity, collapse reason records, downweight dependent lines, wire proof replay, Scholar dependence, Fabric lineage, legal-source dependence, prompt/model paths и simulation assumptions into effective independent evidence count. fileciteturn10file0L1-L3

Во-вторых, для объяснимости это должно выводиться не как «магическое число», а как audit-ready trace. Иначе C13 станет ещё одним скрытым heuristic. Минимальный explainability payload для пары линий я бы делал таким:

```json
{
  "line_a": "…",
  "line_b": "…",
  "effective_independence": 0.18,
  "dependence_channels": [
    {"channel": "shared_primary_source", "overlap": 1.0, "weight": 1.0},
    {"channel": "author_pool", "overlap": 0.67, "weight": 0.6},
    {"channel": "dataset", "overlap": 1.0, "weight": 0.9},
    {"channel": "proof_replay_anchor", "status": "revalidate", "dependence_floor": 0.7}
  ],
  "collapse_decision": "same_cluster"
}
```

Такой surface хорошо сочетается с уже существующей культурой PolicyOS: семантические binding records, audit packages, closeout explanation и projection-only guardrails уже ориентированы на typed, inspectable traces, а не на скрытую магию внутри scorer’а. fileciteturn5file0L1-L3 fileciteturn30file0L1-L3

В-третьих, C13 не должен пытаться решать конфликт сам. Независимость и конфликт — соседние, но разные оси. Две линии могут быть очень независимыми и при этом конфликтовать; или почти не независимыми и при этом согласованными. Поэтому `effective_independence` должен подаваться в C14 как один из inputs, а не подменять собой conflict semantics. И сам план это различает: C13 — про collapse, C14 — про conflict-to-claim semantics. fileciteturn8file0L1-L3

## Открытые вопросы и ограничения

Самая сильная часть этого отчёта — выводы, опирающиеся на retrieved план и на retrieved кодовые якоря: proof composability, causal ensemble, Scholar metadata/duplicate detection, Fabric source contracts, prompt/model ledger и agent-sim runtime surfaces. Именно на этом основании я уверен, что рекомендованная алгебра совместима с реальным PolicyOS, а не с абстрактной платформой. fileciteturn5file0L1-L3 fileciteturn8file0L1-L3 fileciteturn10file0L1-L3

Есть и честные ограничения. Я не извлёк через коннектор конкретную retrieved schema файла из `agent_sim.world`, поэтому часть предложений по `simulation_lineage_ref`, `assumption_bundle_hash` и `calibration_source_ref` для симуляций опирается на task text C13 и на README/wiring contracts, а не на сам world truth-manifest schema. Кроме того, внешняя веб-выборка лучше покрыла общую методологию зависимых эффектов, citation-network dependence и ensemble diversity, чем exact canonical handbook pages по systematic reviews; поэтому некоторые внешние опоры здесь ближе к оригинальным статьям и adjacent methodological work, чем к одному «золотому» handbook source. fileciteturn27file0L1-L3 fileciteturn29file0L1-L3 citeturn9academia4turn14academia2turn14academia4turn11academia0

Тем не менее итоговый вывод для C13 высокоуверенный: **PolicyOS не должен считать независимость на уровне количества файлов, статей, прогонов, сертификатов или членов ансамбля. Он должен считать её на уровне канонических evidence lines, связанных общими roots, lineage, assumptions и production paths.** Это и даёт нужный acceptance result: возможно множество случаев, где raw source count растёт, но effective independent support не растёт или растёт минимально. Именно такая алгебра лучше всего соответствует и рамке плана, и текущей кодовой архитектуре, и внешней методологии обращения с зависимыми свидетельствами. fileciteturn8file0L1-L3 fileciteturn10file0L1-L3 fileciteturn11file0L1-L3 citeturn9academia4turn15academia1turn14academia4

# Семантика конфликтов доказательств и контрдоказательств для PolicyOS

## Рамка задачи и состояние текущего каркаса

Задача C14 в активном исследовательском плане прямо требует сделать конфликты доказательств первоклассными фактами на уровне claim и portfolio, определить типы конфликтов, их влияние на силу поддержки, контрдоказательства, требования к rebuttal, readiness caps, а также увязать post-hoc conflict detection с pre-emission producer handshakes. В самом плане это сформулировано как отдельный концептуальный выход — *conflict-to-claim semantics memo* — с критерием приёмки: конфликтные находки должны проектироваться в claim registry, portfolio, semantic binding, readiness и публичные PDC-поверхности. fileciteturn7file0L3-L3

В текущем коде PolicyOS нужная инфраструктура уже существует, но семантика конфликта пока неглубокая. `ConflictDetector` замечает только несколько частных случаев — например, `legal_vs_academic` и `dataset_vs_academic` — и умеет применять очень простые стратегии вроде `accept_majority`, `accept_highest_quality`, `mark_mixed` и `escalate`; тесты подтверждают именно этот узкий объём поведения. При этом `CrossGraphEvidenceCompiler` уже собирает evidence profile по правовому, датасетному, академическому и transportability-каналам, то есть место, где конфликты возникают, уже архитектурно существует. fileciteturn10file0L3-L3 fileciteturn34file0L3-L3 fileciteturn33file0L3-L3

Ещё важнее, что runtime-качество уже предполагает “богатые” claim-связи. В `semantic_binding.py` есть producer-spine контекст и отдельные binding records для Lex, Fabric, Scholar, Foundry, Scientist и final compiler, включая `selected_*`, `rejected_*`, blocker refs, а также `hierarchy_conflict_refs`, `conflict_link_refs` и `ClaimEvidencePath` с `rebuttal_refs`, `counter_evidence_refs`, `limitation_refs` и `blocker_refs`. В `claim_argument.py` major claims обязаны иметь argument, warrant, rebuttal, counter-evidence и deficit surfaces, а ADR-0161 фиксирует запрет на “серious” claims без этих структурированных узлов. fileciteturn13file0L3-L3 fileciteturn16file0L3-L3 fileciteturn30file0L3-L3

Кроме того, evidence-portfolio слой уже требует преддекларации портфеля до принятия evidence lines, явных inclusion/exclusion rules и `disconfirming_lines`; ADR-0160 отдельно говорит, что raw source count не равен evidence strength, несогласованность доказательств сама является выходом, а post-hoc отбор только согласующихся линий для “serious closeout” запрещён. На уровне claim-моделей и readiness уже есть важный семантический якорь: `ClaimSupportStatus` включает `CONTESTED` и `REFUTED`, наличие `counterevidence_refs` переводит claim в review-required траекторию, а publishable claim не может нести нерешённые контрдоказательства. `citation_faithfulness.py` дополнительно различает `supports`, `partially_supports`, `scope_limited`, `contradicts`, `irrelevant`, `fabricated` и `unverifiable`, причём для публичных factual/legal claims все labels кроме `supports` являются blocking. fileciteturn18file0L3-L3 fileciteturn29file0L3-L3 fileciteturn27file0L3-L3 fileciteturn24file0L3-L3 fileciteturn21file0L3-L3

Из этого следует главный вывод для C14: **PolicyOS не нужно изобретать конфликтный слой с нуля; ему нужно довести уже существующие claim-, portfolio-, semantic-binding- и readiness-контракты до единой конфликтной семантики**. fileciteturn7file0L3-L3 fileciteturn13file0L3-L3 fileciteturn18file0L3-L3 fileciteturn24file0L3-L3

## Предлагаемая модель конфликта как первоклассного факта

В рамках C14 конфликт стоит определять не как “ошибку пайплайна”, а как **typed relation между двумя или более допустимыми утверждениями, нормами, методами, evidence lines или stakeholder records, которые не могут одновременно усиливать один и тот же claim при одном и том же scope, authority envelope и time-role**. Если противоречие исчезает после честного уточнения scope, времени, юрисдикции или authority layer, это не “чистое опровержение”, а конфликт типа *partitionable* с обязательным split claim или limitation. Такой подход соответствует и внутренней архитектуре PolicyOS, и внешним методологическим стандартам: Cochrane прямо требует различать clinical/methodological/statistical heterogeneity и предупреждает, что при расхождении направлений эффекта усреднение может вводить в заблуждение; международно-правовая доктрина, в свою очередь, показывает, что конфликт норм нельзя решать механически — нужны отдельные правила для hierarchy, speciality, temporality и systemic integration. fileciteturn13file0L3-L3 fileciteturn18file0L3-L3 citeturn9view0turn9view1turn14view0turn14view1turn14view3

Минимальный канонический `ConflictRecord` в этой модели должен содержать не только `type` и `severity`, но и: `conflict_subject_ref`, `claim_ids`, `evidence_line_ids`, `source_refs`, `same_scope?`, `same_time_role?`, `same_authority_level?`, `admissibility_state`, `independence_effect`, `counterevidence_effect`, `required_rebuttal`, `resolution_path`, `readiness_cap`, `public_projection_status` и `governance_owner`. Такой состав поля логично вытекает из того, что semantic binding уже умеет хранить consumed/selected/rejected/blocker refs, claim paths уже умеют хранить rebuttals/counter-evidence/limitations, а evidence portfolio уже создаёт predeclared strand- и disconfirming-line логику. fileciteturn13file0L3-L3 fileciteturn18file0L3-L3 fileciteturn30file0L3-L3

Предлагаемая типология конфликтов совпадает с C14, но каждому типу нужно дать строгую operational semantics:

- **Эмпирический конфликт**: допустимые evidence lines про один и тот же factual/causal claim расходятся по направлению, величине или устойчивости эффекта после выравнивания единиц, времени, популяции и географии. Это ближе всего к внешней гетерогенности/инконсистентности в синтезе доказательств. fileciteturn7file0L3-L3 citeturn9view0turn9view1  
- **Правовой конфликт**: применимые нормы, режимы или authority layers дают несовместимые правовые последствия для одного policy move; решается через hierarchy, speciality, posteriority или systemic integration, а не голосованием источников. fileciteturn7file0L3-L3 citeturn14view0turn14view1turn14view2turn14view3turn14view4  
- **Академический конфликт**: body of literature или scholarly syntheses расходятся, даже если отдельные исследования “внутри себя” корректны; это отдельный тип, потому что он может существовать без прямого конфликта с Fabric или Lex. fileciteturn7file0L3-L3 fileciteturn13file0L3-L3  
- **Методологический конфликт**: вывод зависит от method family, identification strategy, preprocessing, model class, equivalence cluster или sensitivity choices; именно здесь запрет на post-hoc cherry-picking и требование multiverse/sensitivity особенно критичны. fileciteturn29file0L3-L3 citeturn9view2turn9view3turn21view0  
- **Юрисдикционный конфликт**: одинаковая policy proposition оценивается по разным правопорядкам, институциональным уровням или applicability envelopes; это не просто правовой конфликт, а конфликт *где* норма действует. fileciteturn7file0L3-L3 fileciteturn13file0L3-L3  
- **Scope-конфликт**: источники спорят только потому, что говорят о разных populations, interventions, outcomes, geographies или implementation settings; такой конфликт должен рождать split claims, а не бинарный verdict. Cochrane прямо указывает, что различия участников, вмешательств и исходов создают отдельный слой heterogeneity. fileciteturn7file0L3-L3 citeturn9view1  
- **Временной конфликт**: различие связано с `as_of`, effective time, observation window, publication lag, forecast horizon или freshness deadline; это особенно важно, потому что внутренние контракты PolicyOS уже различают time refs, effective dates и freshness. fileciteturn13file0L3-L3 fileciteturn7file0L3-L3  
- **Authority-конфликт**: низкоавторитетная, proxy- или provenance-неполная линия спорит с высокоавторитетной direct line; это не столько спор о мире, сколько спор о допустимости и компетенции источника. В PolicyOS это уже подготовлено разделением provenance/domain authority и blocking citation labels. fileciteturn21file0L3-L3 fileciteturn31file0L3-L3  
- **Конфликт участия**: разные affected groups, consultations или representational channels дают несовместимые предпочтения, legitimacy claims или feasibility claims; это не “шум”, а отдельный доказательный объект, который надо публиковать с diverging views и качеством представительства. Европейская Commission Toolbox требует отражать и majority, и minority views, а также diverging views внутри и между stakeholder groups. fileciteturn7file0L3-L3 citeturn21view1turn22view0turn22view1turn21view3turn21view4  
- **Implementation-конфликт**: policy design выглядит сильным по causal/legal логике, но operational, budgetary, enforcement или uptake evidence показывает несходимость на практике; EC guidance отдельно предупреждает, что aggregate effects могут скрывать распределительные trade-offs и politically sensitive divergences. fileciteturn7file0L3-L3 citeturn22view1

## Как конфликт должен менять claim, portfolio и readiness

### Support status и контрдоказательства

В существующих enum’ах PolicyOS уже есть почти все нужные состояния: `SUPPORTED`, `WEAKLY_SUPPORTED`, `CONTESTED`, `REFUTED`, `NOT_EVALUABLE`. Поэтому для совместимости с текущим кодом не нужен новый “бог-статус”; нужен **детерминированный переходный закон**. Если конфликт разрешён и rebuttal оформлен, claim может оставаться `SUPPORTED`. Если конфликт допустим, но исходно один evidence line выглядит сильнее другого и итог ещё нельзя публиковать как устойчивый, claim должен перейти в `WEAKLY_SUPPORTED`. Если допустимые и сопоставимые линии остаются в прямом споре, claim должен быть `CONTESTED`. Если контрдоказательство побеждает в том же scope и authority envelope, claim — `REFUTED`. Если спор вообще нельзя честно сопоставить из-за неразрешённого scope/time/jurisdiction/identity mismatch, claim — `NOT_EVALUABLE`, а не “supported with caveats”. Это лучше согласуется и с внутренними claim-моделями, и с Cochrane-предупреждением о том, что при существенном расхождении направлений эффекта усреднение может быть misleading. fileciteturn27file0L3-L3 fileciteturn24file0L3-L3 citeturn9view0turn9view1

При этом **контрдоказательство надо отличать от просто плохой или неверной ссылки**. В `citation_faithfulness.py` уже есть для этого почти готовая семантика: `contradicts`, `partially_supports` и `scope_limited` — это конфликтные факты, которые должны попадать в claim argument и semantic binding; `irrelevant`, `fabricated` и `unverifiable` — это прежде всего provenance/faithfulness failure, а не substantive counterevidence. Иными словами, неправдоподобная или неподтверждаемая ссылка не “балансирует” хорошие доказательства; она должна блокировать публикацию как defect of faithfulness. fileciteturn21file0L3-L3

### Независимость и сила поддержки

Семантика C13 и C14 должна быть связана жёстко: **сначала collapse correlated lines, потом оценка конфликта**. Если две спорящие линии происходят из одного lineage cluster, одного method cluster, одной author/institution pool или одних assumptions, то они не должны считаться двумя независимыми голосами ни “за”, ни “против”. ADR-0160 прямо говорит, что raw evidence count не равен evidence strength, а `evidence_independence.py` уже строит collapse clusters по claim ids, method cluster, source lineage, preprocessing, assumptions и identification strategy. Поэтому влияние конфликта на support strength должно рассчитываться на *effective independent evidence count*, а не на количестве записей в Scholar/Fabric/Lex. fileciteturn29file0L3-L3 fileciteturn28file0L3-L3

Из этого следует практическое правило: конфликтная линия **обнуляет бонус независимости**, пока не доказано обратное. Другими словами, спорящие evidence lines могут оставаться в портфеле, но перестают усиливать уверенность как независимые подтверждения до тех пор, пока конфликт не типизирован как scope split, time split, authority downgrade или formally arbitrated method divergence. Это защищает систему от ложной уверенности из-за “многочисленных, но коррелированных и спорящих” источников. fileciteturn28file0L3-L3 fileciteturn29file0L3-L3

### Rebuttal, limitations и readiness caps

Внутренняя модель уже говорит, что наличие `counterevidence_refs` требует review, contested claims требуют review, а publishable claims не могут иметь unresolved counterevidence. Я бы усилил этот закон до уровня C14 так: **любой high-stakes decision-bearing claim с admissible unresolved conflict обязан иметь явный rebuttal node и limitation node**; без них claim нельзя поднимать выше исследовательской или аналитической зрелости. ADR-0161 прямо требует rebuttal/counter-evidence assessment и запрет на silent smoothing of deficits, а текущий readiness-код уже отправляет contested claims и claims с counterevidence в review. fileciteturn30file0L3-L3 fileciteturn24file0L3-L3

Для readiness я предлагаю не вводить отдельную лестницу, а наложить **conflict caps** поверх `DecisionReadiness`:

- неразрешённый **правовой, authority- или jurisdictional** конфликт для decision-bearing claim — максимум `RESEARCH_ARTIFACT`, а для публичного/нормативного выхода фактически `BLOCKED`;  
- неразрешённый **эмпирический или methodological** конфликт — максимум `ANALYST_ADVISORY`; поднятие до `EXTERNAL_BRIEFING` допустимо только если конфликт честно раскрыт, проведены sensitivity/multiverse/rebuttal и не происходит продажа вывода как settled fact;  
- **scope/time** конфликт после честного split claim может не блокировать узкий claim, но исходный широкий claim должен остаться `NOT_EVALUABLE` или `CONTESTED`;  
- **participation** конфликт, если он касается preference/legitimacy claims, должен капировать claim не выше `EXTERNAL_BRIEFING`, пока не появится governance decision с опубликованным dissent и provenance участия;  
- **implementation** конфликт не должен мешать исследовательскому или рекомендательному обсуждению, но должен блокировать `DEPLOYMENT_READY`, пока не закрыты feasibility и mitigation gaps. fileciteturn24file0L3-L3 fileciteturn27file0L3-L3 fileciteturn30file0L3-L3

## Когда конфликт разрешим, а когда нужен governance decision

### Разрешение новыми доказательствами

Новый сбор evidence уместен там, где конфликт носит эмпирический, академический или implementation-характер и очевидно связан с дефицитом наблюдаемости, низкой мощностью, узкой выборкой, плохим покрытием или неполной stakeholder map. Cochrane подчёркивает, что heterogeneity надо не игнорировать, а разбирать, а sensitivity analysis нужна для проверки устойчивости к сомнительным решениям и предположениям. В терминах PolicyOS это означает: resolution-by-new-evidence допустим только тогда, когда система может явно назвать, **какой именно gap будет заполнен**, а не просто “попробовать ещё данные”. citeturn9view1turn9view3turn21view0

### Method arbitration вместо голосования моделей

Для serious claims стратегия `ACCEPT_MAJORITY` из текущего `ConflictDetector` слишком слабая. Методологический конфликт нельзя закрывать арифметикой по числу методов или papers. Его надо закрывать через **predeclared admissibility, equivalence/consensus, multiverse, sensitivity и severe tests against the claim**. Это прямо согласуется с ADR-0160, который запрещает post-hoc selection of only agreeing lines и требует disconfirming evidence lines и synthesis sensitivity, а Cochrane отдельно предупреждает, что post-hoc subgroup analyses и data dredging могут быть misleading. Поэтому majority rule заслуживает сохранения только для exploratory/profile-research режимов, а не для governed or production authority. fileciteturn10file0L3-L3 fileciteturn29file0L3-L3 citeturn9view2turn9view3

### Правовое разрешение через hierarchy, speciality и systemic integration

Для legal/jurisdictional conflict нужен формальный порядок. По материалам International Law Commission: `lex specialis` работает не просто потому, что две нормы “про похожую тему”, а когда есть реальная несовместимость или различимое намерение исключить общий режим; `lex posterior` тоже не применяется механически; статья 103 Устава ООН устанавливает приоритет хартии, но не делает нижестоящую норму автоматически недействительной; `jus cogens` служит как конфликтная норма, которая инвалидирует inferior norms; а `systemic integration` вводит презумпцию, что стороны не намерены действовать в противоречии с общими принципами права. Практически это даёт такой legal-arbitration stack: **lex superior / jus cogens / Article 103 → lex specialis → lex posterior → systemic integration → human legal review**. citeturn14view0turn14view1turn14view2turn14view3turn14view4

### Сужение scope и split claims

Очень многие “конфликты” на деле являются конфликтами обобщения. Если одно исследование говорит про другую популяцию, другой горизонт времени, другую географию или другой implementation setting, то лучший исход — не победа одного источника над другим, а **split claim**: исходный broad claim становится недопустимым или contested, а вместо него появляются два или более narrower claims с собственными bindings, limitations и public wording. Именно этот ход лучше всего согласуется с внутренней моделью `ClaimEvidencePath` и с внешней логикой heterogeneity/subgroup analysis, где различия в participants, interventions и context требуют отдельного анализа. fileciteturn13file0L3-L3 citeturn9view1turn9view2

### Когда решение должно быть человеческим или governance-уровня

Есть класс конфликтов, которые не надо “решать доказательством”, потому что они не являются чисто эпистемическими. Сюда относятся, прежде всего, **participation**, часть **implementation** и часть **normative trade-off** конфликтов. European Commission’s toolbox требует отражать diverging views внутри и между stakeholder groups, majority и minority views, а также строить consultation strategy от карты evidence gaps и stakeholder coverage. Это означает, что если спор идёт о легитимности, представительности, приемлемости распределения издержек или политической справедливости, то правильный результат — не “evidence says X”, а **governance decision with explicit dissent record**. В PolicyOS такой случай должен проектироваться как contested-but-governable, а не как resolved empirical support. citeturn21view1turn21view3turn21view4turn22view0turn22view1

## Взаимодействие post-hoc conflict detection и pre-emission producer handshake

Внутренний код и планы уже тянут систему к тому, чтобы конфликт обнаруживался не только постфактум. `semantic_binding.py` вводит producer-spine read context и binding records с consumed/selected/rejected/blocker refs; `evidence_portfolio.py` требует predeclared portfolio до принятия evidence lines; активный evidence-binding plan формулирует scenario evidence contract и contract-binding result ещё до зрения итоговой рекомендации; а C8 в исследовательском плане отдельно требует producer handshake как самостоятельный протокол. Следовательно, для C14 правильна **двухконтурная модель**: предотвращение ожидаемых конфликтов до emission и аудит остаточных конфликтов после emission. fileciteturn13file0L3-L3 fileciteturn18file0L3-L3 fileciteturn31file0L3-L3 fileciteturn6file0L3-L3

Pre-emission handshake я бы зафиксировал как обязательный для всех producers, чьи outputs могут повысить authority major claim. До emission producer должен декларировать: какой claim/evidence subject он обслуживает; какой scope и time assumption использует; какие candidate refs рассмотрел; какие refs выбрал, отверг или заблокировал; какие конфликты уже увидел внутри своего домена; по какому правилу их интерпретировал; и что именно оставил нерешённым для downstream review. По смыслу это очень близко и к текущим semantic-binding полям, и к европейской идее consultation strategy, которая должна строиться на map of available evidence and identified gaps, а не складываться задним числом. fileciteturn13file0L3-L3 citeturn21view4

Post-hoc conflict detection после этого должно делать уже другое: не “в первый раз замечать”, что Lex и Scholar спорят, а **проверять, все ли доменные конфликты были честно задекларированы и корректно спроецированы**. Здесь обнаруживаются cross-producer contradictions, public-surface contradictions, missing rebuttals, citation-faithfulness problems, а также скрытый post-hoc cherry-picking. Если конфликт найден post-hoc, но producer handshake о нём умолчал, это должно повышать severity и автоматически понижать trust/readiness: проблема тогда не только в substantive disagreement, но и в честности процесса. В этом смысле отсутствие handshake — само по себе conflict meta-fact. fileciteturn21file0L3-L3 fileciteturn29file0L3-L3 fileciteturn31file0L3-L3

Простое практическое правило здесь такое: **preventable conflicts** — scope/time/jurisdiction/authority/method mismatch, которые producer мог увидеть заранее, — должны ловиться pre-emission; **emergent conflicts** — те, что видны только после склейки Lex/Fabric/Scholar/Foundry/Scientist/final compiler, — остаются задачей post-hoc детектора. Всё, что выявлено post-hoc и могло быть задекларировано заранее, должно считаться не только доменным конфликтом, но и process-governance deficit. fileciteturn13file0L3-L3 fileciteturn18file0L3-L3

## Проекция в claim registry, portfolio, semantic binding, readiness и публичные PDC-поверхности

Чтобы пройти acceptance C14, конфликт должен отображаться не как “примечание в журнале”, а как инвариантно переносимый объект между поверхностями. На уровне **claim registry** это означает: у claim должен быть `support_status`, совместимый с конфликтом (`CONTESTED`, `REFUTED`, `NOT_EVALUABLE`), а также `conflict_refs`, `counterevidence_refs`, `rebuttal_refs`, `limitation_refs`, `blocked_reasons` и `review_required_reasons`. В текущих claim-моделях и readiness-функциях почти всё это уже есть; не хватает именно явной связки `conflict_refs → support/readiness transitions`. fileciteturn27file0L3-L3 fileciteturn24file0L3-L3

На уровне **evidence portfolio** конфликт должен жить как агрегатный факт по strand’ам и evidence lines: конфликтные кластеры, disconfirming lines, effective independent count *after collapse and conflict typing*, а также выбранный synthesis policy. Это прямо соответствует уже существующей логике predeclared portfolio, disconfirming lines и ADR-0160 о convergence/divergence clusters и certainty sensitivity. fileciteturn18file0L3-L3 fileciteturn29file0L3-L3

На уровне **semantic binding** конфликт уже почти “встанет в пазы”: `LexBindingRecord` содержит `hierarchy_conflict_refs`, `ScholarBindingRecord` содержит `conflict_link_refs`, а `ClaimEvidencePath` уже предусматривает `counter_evidence_refs`, `rebuttal_refs`, `limitation_refs` и `blocker_refs`. Поэтому проектирование C14 сюда должно быть не новой сущностью поверх семантического слоя, а унификацией уже имеющихся ref-каналов под один canonical conflict model. fileciteturn13file0L3-L3

На уровне **readiness** нужна простая и проверяемая логика: readiness cap должен быть функцией не только support status, но и конфликтного профиля. Уже сегодня contested claims и claims с counterevidence уходят в review-required, а publishable claims не терпят unresolved counterevidence. После C14 это надо сделать явным и monotonic: чем выше severity и чем ближе конфликт к legal/authority/implementation ядру policy recommendation, тем ниже допустимый readiness ceiling. fileciteturn24file0L3-L3 fileciteturn27file0L3-L3

На уровне **публичной PDC-поверхности** конфликт нельзя прятать за “общий средний вывод”. ADR-0161 требует видимых counter-evidence и deficits, а external policy guidance требует отражать diverging stakeholder views, majority и minority arguments, а также то, какие sensitivities важны для политического решения. Поэтому public projection должен показывать хотя бы: тип конфликта, что именно спорит, resolved/unresolved status, как конфликт был обработан, какие ограничения остались и идёт ли речь о dispute in facts, dispute in law, dispute in method, or dispute in participation. Иначе система будет публиковать иллюзию settled output там, где у неё на самом деле contested case. fileciteturn30file0L3-L3 citeturn21view3turn22view0turn22view1

Итоговая формула для acceptance C14 может быть сформулирована так: **ни один серьёзный claim в PolicyOS не может получать authority из “чистой суммы” evidence refs; authority проходит только через typed conflict semantics, которая знает, что считается конфликтом, что считается контрдоказательством, что требует rebuttal, что режет independence, что режет readiness и что обязательно выводится в PDC**. fileciteturn7file0L3-L3 fileciteturn29file0L3-L3 fileciteturn30file0L3-L3

## Открытые вопросы и ограничения

Этот memo высоко уверен в архитектурной части, потому что она напрямую опирается на текущий репозиторий `DenisKopylov/polisyos`: активный план C14, существующие runtime contracts, ADR-0160/0161, claim/readiness модели, citation faithfulness и evidence portfolio. Внешнее методологическое обоснование тоже надёжно в тех областях, где удалось получить первичные/официальные источники: Cochrane Handbook, European Commission Better Regulation Toolbox и доклад International Law Commission о фрагментации права. fileciteturn7file0L3-L3 fileciteturn29file0L3-L3 fileciteturn30file0L3-L3 citeturn9view0turn9view1turn9view2turn9view3turn20view0turn21view0turn21view1turn21view3turn21view4turn22view0turn22view1turn14view0turn14view1turn14view2turn14view3turn14view4

Главные незакрытые вопросы — это не исследовательские провалы, а уже вопросы проектного выбора. Во-первых, нужно решить, достаточно ли существующих claim statuses (`SUPPORTED/WEAKLY_SUPPORTED/CONTESTED/REFUTED/NOT_EVALUABLE`) или PolicyOS всё же хочет отдельный публичный статус вроде `SUPPORTED_WITH_LIMITATIONS`. Во-вторых, потребуются calibrated thresholds для conflict severity и для перевода severity в readiness cap. В-третьих, для participation conflicts придётся отдельно задать минимальные требования к representativeness и provenance, чтобы disagreement stakeholder groups не превращался либо в шум, либо в скрытый “majority wins”. Наконец, GitHub-коннектор дал достаточно материала для концептуального memo, но не даёт такой же удобной построчной глубины, как полноценный индексируемый внутренний поиск; поэтому при переходе к реализации полезно будет дополнительно прогнать design review по конкретным runtime DTO и public export contracts. fileciteturn27file0L3-L3 fileciteturn24file0L3-L3 citeturn21view1turn21view3turn21view4turn22view0turn22view1

# Формальная модель оспоримости и несогласия для PolicyOS

## Контекст задачи и главный архитектурный разрыв

В плане C17 задача поставлена предельно ясно: PolicyOS должен **сохранять несогласие**, а не маскировать его под «нехватку данных» или «окончательный провал». В том же фрагменте плана перечислены и обязательные опорные поверхности для исследования: состояния поддержки claim, argument graph, `ConflictDetector`, normative arbitration, residual dissent и readiness. Критерий приемки тоже однозначен: допустимое несогласие должно **оставаться contested**, не схлопываясь в pass, fail или missing data. fileciteturn9file0L1-L3

Кодовая база уже частично подошла к этой идее, но пока не довела её до publishable-closeout семантики. В модели claim уже есть `ClaimSupportStatus.CONTESTED`, а также отдельная ось `ClaimPublishability`; однако `ClaimRecord` валидируется так, что `PUBLISHABLE` допустим только для `SUPPORTED` claim, без неразрешённого counterevidence и без blocked reasons. Поверх этого claim-level readiness явно переводит contested claim в `REVIEW_REQUIRED`. То есть contested как состояние **существует**, но на пути к публикации оно сейчас фактически снова сворачивается в review gate. fileciteturn17file0L1-L3 fileciteturn28file0L1-L3

При этом более низкий слой уже мыслит правильно: модуль semantic claim support прямо разделяет вопрос «поддержан ли claim evidence-предикатами» и вопрос «может ли claim покинуть текущую boundary». В нём же counterevidence может не только блокировать, но и понижать readiness, требовать review или оставлять warning. Это хороший зачаток нужной архитектуры: support, publication и disagreement уже намечены как разные вещи, но для contested publication-case они ещё не собраны в единый формализм closeout. fileciteturn13file0L1-L3 fileciteturn15file0L1-L3

## Что в кодовой базе уже можно переиспользовать

PolicyOS не является blank slate и не должен проектироваться как blank slate. В assurance-case слое уже есть типы узлов `claim`, `argument`, `warrant`, `rebuttal`, `counter_evidence` и `deficit`; это почти готовая онтология для явного представления спорящих позиций, их обоснований и поражающих аргументов. Иными словами, contested record не нужно invent с нуля: его можно опереть на уже существующую graph vocabulary. fileciteturn22file0L1-L3

Ещё сильнее этот вывод подтверждается другими поверхностями. `ConflictDetector` уже умеет фиксировать конфликт, но пока только в очень узком наборе измерений и стратегий (`accept_majority`, `accept_highest_quality`, `escalate`, `mark_mixed`), что недостаточно для C17. Модуль normative arbitration уже хранит `ResidualDissent` и `TradeoffCertificate`, то есть для нормативного разногласия у системы уже есть естественная модель: решение может быть принято, но dissent не обязан исчезать. В проекциях PDC уже существует состояние `contested`, которое поднимается не только из явного `contestability_status`, но и из наличия `source_truth_conflicts`, `counter_evidence`, `rebuttals` и спорных node-status. Наконец, lifecycle уже знает состояние `contested` и имеет разрешающие события вроде `amended`, `superseded`, `withdrawn`, `reissue`, `confirmed`, `refuted` и `inconclusive`. Всё это означает, что C17 — не создание нового мира, а **сведение уже существующих фрагментов в единую модель**. fileciteturn19file0L1-L3 fileciteturn20file0L1-L3 fileciteturn27file0L1-L3 fileciteturn31file0L1-L3

С точки зрения registry и runtime coverage эта интеграция тоже уже предусмотрена. В minimum record families Policy Design Case присутствуют `claim_argument_evidence_case.v1`, `structured_judgement_and_consultation.v1`, `options_objectives_and_tradeoffs.v1`, `implementation_monitoring_and_evaluation.v1` и `lifecycle_ex_post_and_calibration.v1`. Следовательно, contestability model должна быть встроена именно в эти семейства записей, а не оформлена как изолированный «специальный репорт». fileciteturn25file0L1-L3

## Дизайн-принципы предлагаемой модели

Главное проектное решение — сделать contestability **ортогональной осью**, а не вариантом support-status. На практике PolicyOS должен различать как минимум три отдельных вопроса. Первый: насколько хорошо claim поддержан evidence и warrant-структурой. Второй: можно ли его публиковать на текущем authority/readiness уровне. Третий: остаётся ли по нему допустимое, публично значимое несогласие. Пока код частично смешивает второй и третий вопросы; C17 требует их развязать. fileciteturn17file0L1-L3 fileciteturn28file0L1-L3

Внешне это хорошо согласуется с тем, как зрелые decision frameworks отделяют evidence от решения. Официальный GRADE прямо определяет себя как подход к **раздельному** оцениванию certainty of evidence и strength of recommendations, а также требует, чтобы решения опирались не только на evidence-effects, но и на явные критерии EtD: ресурсы, equity, acceptability и feasibility. На том же сайте GRADE собственная миссия формулируется как поддержка **values-based decisions**, учитывающих контекст и ценности затронутых групп. Для PolicyOS это важный внешний ориентир: несогласие часто возникает не из-за «плохих данных», а из-за столкновения допустимых ценностей, границ применения, легитимности участия или выполнимости. citeturn21view2

Из этого следует рекомендованная структура данных. На claim/case уровне нужен отдельный `contestability_status`, а рядом — typed `ContestabilityRecord`, в котором фиксируются: объект спора, категория разногласия, competing positions, какие из них admissible, какая authority вправе выбирать между ними, что считается допустимым closeout, какой publication effect наступает, какой readiness cap действует, какие monitoring triggers откроют дело заново, и что именно должен увидеть PUBLIC/REVIEWER/EXPERT/MACHINE consumer. Это уже не «issue» и не «warning»: это **первоклассный governed artifact**. Вывод о такой форме является проектным синтезом на основе уже имеющихся осей support/publishability/readiness в коде и требований C17. fileciteturn9file0L1-L3 fileciteturn13file0L1-L3 fileciteturn20file0L1-L3

## Категории несогласия и состояния closeout

Для C17 я рекомендую закрепить семь категорий несогласия именно в том виде, в каком требует план, но дать им разную causal semantics.

Эмпирическое несогласие — это спор о фактах, измерениях, lineages, наблюдениях, подборе источников или интерпретации evidence bundle. Оно обычно адресуется новым исследованием, source verification, re-sampling или проверкой независимости линий. Методологическое несогласие — это спор об идентификационной стратегии, модели, допущениях, uncertainty treatment, критериях валидности и репликации. Нормативное несогласие — это спор о ценностях, правах, tradeoff weights, порогах приемлемости и целях, а не о том, «что показали данные». Scope-несогласие — это спор о population, geography, time window, baseline, jurisdiction, claim boundary или definition of success. Authority-несогласие — это спор о компетенции, legal hierarchy, non-overridable role или о том, кто вообще вправе закрывать вопрос. Participation-несогласие — это спор о репрезентативности затронутых групп, legitimacy of preference claims, полноте consultation или о том, что affected people были смоделированы, а не услышаны. Implementation-несогласие — это спор о выполнимости, capacity, delivery risk, мониторинге и ex-post enforceability. Такое разбиение прямо вытекает из задания C17 и хорошо ложится на уже существующие record families, readiness, arbitration и lifecycle surfaces. fileciteturn9file0L1-L3 fileciteturn20file0L1-L3 fileciteturn25file0L1-L3

Для contested-but-publishable closeout I recommend не один бинарный флаг, а набор типизированных завершений. Базовое состояние — `resolved`, когда спор снят и dissent больше не определяет surface. Далее нужны именно contested closeouts. `contested_publishable` означает, что спор остаётся неснятым, но обе позиции admissible, publication допустима, а читатель должен увидеть обе стороны и текущий balance-of-reasons. `contested_publishable_limited` означает то же, но с ограничением audience, scope или decisional force. `contested_authority_choice` означает, что спор не был «научно разрешён», но был закрыт посредством уполномоченного governance/legal choice; при этом несогласие сохраняется как residual dissent, а не переписывается как empirical truth. `contested_scope_split` означает, что одна исходная claim-form была разделена на более узкие claims, часть из которых publishable, а часть остаётся contested. `contested_monitor_only` означает, что публикация допустима только при усиленном lifecycle monitoring и заранее заданных revalidation triggers. `contested_blocked` означает, что спор признан admissible, но пока не может быть выпущен наружу без дополнительного resolver path. Такая линейка нужна именно потому, что acceptance C17 запрещает сводить admissible disagreement к pass/fail/missing. fileciteturn9file0L1-L3 fileciteturn27file0L1-L3 fileciteturn31file0L1-L3

Ключевой operational rule здесь такой: contested state не должен автоматически понижать support до weak или делать disagreement синонимом review-only, если у системы есть валидные competing claims, достаточная provenance и ясный authority envelope. Иначе PolicyOS не выполнит критерий C17 и останется в текущем коллапсе «contested ⇒ review_required». fileciteturn17file0L1-L3 fileciteturn28file0L1-L3

## Стратегии примирения и правила маршрутизации

Роутер разногласий должен начинаться не с вопроса «кто прав?», а с вопроса **какого типа это несогласие и какой resolver вообще легитимен**. Для эмпирического несогласия resolver по умолчанию — дополнительное исследование, source verification или refresh. Для методологического — parallel replay, benchmark sensitivity, независимый method review или governed method arbitration. Для нормативного — не «добор данных», а formal governance choice с обязательным сохранением `ResidualDissent`, поскольку кодовая база уже имеет такую сущность именно для value-conflict arbitration. Для scope-несогласия правильный выход чаще всего не победа одной стороны, а split claim boundary: по разным populations, times, jurisdictions или outcome-definitions обе стороны могут оказаться правы одновременно. Для authority-несогласия применяется legal hierarchy или competence routing, а не majority logic. Для participation-несогласия resolver — consultation, affected-group verification или typed limitation/blocker для legitimacy claims. Для implementation-несогласия — pilot, phased rollout, conditional publication и elevated monitoring. fileciteturn19file0L1-L3 fileciteturn20file0L1-L3 fileciteturn25file0L1-L3

Практический decision rule я бы зафиксировал так. Разногласие уходит в **research** тогда, когда новое evidence с высокой вероятностью изменит admissibility или publication effect в разумный срок. Оно уходит в **governance choice** тогда, когда источник расхождения — value ranking, правовой приоритет или легитимная разница в целях. Оно уходит в **scope split** тогда, когда competing positions совместимы после сужения population/time/jurisdiction. Оно уходит в **legal hierarchy** тогда, когда требуется не научный, а нормативно-компетентностный ответ. Оно уходит в **public contestability** тогда, когда decision window закрывается раньше, чем спор можно добросовестно разрешить, но case всё ещё обязан быть опубликован с полным disclosure disagreement. Это, опять же, полностью согласуется с GRADE-подходом: evidence alone недостаточно для good decision, нужны explicit contextual criteria и values-based choice. citeturn21view2

Для readiness я рекомендую ввести caps по категориям. Эмпирическое и методологическое contested часто должны ограничивать case максимум уровнем `ANALYST_ADVISORY` или `EXTERNAL_BRIEFING`, если спор затрагивает causal/legal/high-stakes claims. Нормативное contested может быть совместимо с внешней публикацией и даже recommendation-ready, если выбор сделан уполномоченной authority и dissent surfaced. Participation-contested должно жёстко капировать любые claims о legitimacy или affected-person preferences, пока provenance участия не доказана. Implementation-contested может быть совместимо с limited publication, но не с deployment-ready без monitoring commitments. Этот readiness-sensitive rule продолжаeт существующую логику readiness ladder, а не ломает её. fileciteturn18file0L1-L3 fileciteturn28file0L1-L3

## Как встроить модель в артефакты PolicyOS

В argument graph contestability лучше представлять не как «один флажок на claim», а как связанный subgraph. Existing vocabulary уже позволяет это сделать: claim соединяется с supporting argument и warrant, а contesting position входит через `rebuttal` и `counter_evidence`; поверх них добавляется `ContestabilityRecord`, который нормализует category, resolver_path, admissibility, residual_dissent_ref и publication effect. Это даст системе возможность различать «claim attacked because factually wrong», «claim attacked because method disputed» и «claim accepted but normatively opposed». fileciteturn22file0L1-L3 fileciteturn19file0L1-L3

В claim registry нужен минимум из пяти новых полей: `contestability_status`, `contestability_category`, `contest_ref`, `closeout_state`, `revalidation_triggers`. Дополнительно полезны `resolver_authority_role`, `public_limitation_note` и `residual_dissent_ref`. Самый важный архитектурный выбор здесь — **перестать заставлять contested claim притворяться unsupported**. Это потребует изменения текущей валидации `ClaimRecord` и/или логики `assess_claim_readiness`: publishability должна зависеть не только от `support_status`, но и от typed contestability closeout. Иначе текущий код всегда будет возвращать contested claim обратно в `REVIEW_REQUIRED`, что несовместимо с целевым acceptance C17. fileciteturn17file0L1-L3 fileciteturn28file0L1-L3

В public projection лучше не ограничиваться действующим `primary_state="contested"`. Нужен структурированный массив `contested_records`, где для каждого спора есть: what is contested, category, positions, what evidence each side relies on, who may decide, what was decided, what was not decided, what limitation attaches to publication, and when the case reopens. Это особенно важно потому, что в пользовательских оценках AI-supported fact-checking люди систематически опирались на underlying evidence для проверки AI-утверждений; следовательно, contested projection должна выводить не только label, но и evidence path. Наличие уже существующего contested projection state делает такое расширение естественным, а не инвазивным. fileciteturn27file0L1-L3 citeturn18academia6

В lifecycle monitoring contestability должна открывать не просто status, а **обязательство к повторной проверке**. Для claim-level ledger это означает новые события поверх имеющихся `UPDATED_SUPPORT`, `UPDATED_READINESS`, `REVIEWED`, `MARKED_STALE`, `INVALIDATED` и `SUPERSEDED`: например, `CONTEST_OPENED`, `CONTEST_RESCOPED`, `AUTHORITY_CHOSEN`, `MONITOR_ONLY_ACCEPTED`. Для case lifecycle это значит привязку contested publication к explicit triggers: новая evidence line, legal change, implementation incident, participation refresh, source invalidation или missed monitoring checkpoint. Хорошая новость в том, что append-only event infrastructure и case-level contested state уже существуют; модели не нужен новый движок, ей нужен новый governed event vocabulary. fileciteturn29file0L1-L3 fileciteturn31file0L1-L3

В record families contestability should live where the disagreement actually belongs. Эмпирические и методологические споры — в `claim_argument_evidence_case.v1`. Нормативные — также в `options_objectives_and_tradeoffs.v1` с прямой ссылкой на normative arbitration и residual dissent. Participation disagreements — в `structured_judgement_and_consultation.v1`. Implementation disagreements — в `implementation_monitoring_and_evaluation.v1`. Это сохранит модель универсальной и не создаст ложного ощущения, будто спор — это отдельный вид объекта, оторванный от evidence, tradeoffs, consultation и monitoring. fileciteturn20file0L1-L3 fileciteturn25file0L1-L3

## Открытые вопросы и ограничения

Самый острый открытый вопрос — **где именно разрешить contested publishability**: в `ClaimRecord` как ядре claim-spine или только на case/projection уровне. С точки зрения чистоты acceptance я рекомендую изменить ядро и сделать contestability ортогональной, а не проекционной фикцией. С точки зрения минимального вмешательства можно было бы оставить strict claim validation и публиковать contested only at case surface, но это хуже соответствует цели C17, потому что удерживает внутреннее ядро в старой логике «contested = non-publishable». fileciteturn17file0L1-L3 fileciteturn28file0L1-L3

Второй открытый вопрос — уровень stringency для participation и authority disagreements. Моя рекомендация достаточно строгая: claims о legitimacy, representation и affected-person preferences не должны становиться полноценно publishable без provenance участия, а authority disagreements должны заканчиваться юридической/управленческой иерархией, а не эвристикой «highest quality». Но конкретные thresholds лучше закрепить отдельной ADR рядом с C19 и C2, чтобы избежать несовместимых правил между admissibility, consultation и contestability. fileciteturn9file0L1-L3 fileciteturn19file0L1-L3

Итоговый вывод таков: **лучший contestability model для PolicyOS — это не новый «статус», а новый orthogonal governed layer**, который связывает argument graph, claim registry, normative arbitration, public projection и lifecycle monitoring. Тогда admissible disagreement действительно сможет оставаться contested, быть честно опубликованным, сопровождаться residual dissent и revalidation triggers, и при этом не деградировать ни в missing data, ни в false pass, ни в безликий review-only limbo. fileciteturn9file0L1-L3 fileciteturn20file0L1-L3 fileciteturn27file0L1-L3

# ADR по provenance tradeoff и welfare для PolicyOS

## Рамка задачи

Активный план исследования для C18 уже задает очень узкую и конкретную рамку: нужно **разделить вычисленные frontier-факты и governance/value choices**, определить **provenance социальных весов** с полями «кто выбрал, по какому мандату, когда, с какими затронутыми группами, с каким dissent и review status», определить **welfare audit trail и claim linkage**, зафиксировать случаи, когда **скалярной welfare-агрегации недостаточно**, и выпустить именно **welfare/tradeoff provenance ADR**. Acceptance-критерий тоже сформулирован жестко: никакая welfare-агрегация не должна скрывать provenance весов, Pareto-доминируемые альтернативы или явные нормативные решения. fileciteturn4file0L3-L3 fileciteturn5file0L3-L3

Из этого следует главный вывод исследования: для C18 PolicyOS не нужен «еще один welfare score». Нужна архитектура, в которой **вектор фактов о результатах** существует отдельно от **нормативного выбора правила сравнения**, а отдельно от них существует **управленческое решение**, которое выбирает одну из недоминируемых опций и оставляет проверяемый след того, кто и почему это сделал. Это не абстрактная философская добавка, а прямое следствие текста плана и уже существующих кодовых якорей. fileciteturn4file0L3-L3 fileciteturn5file0L3-L3

## Что уже есть в кодовой базе

В репозитории уже есть сильная база для **многоцелевого** представления, и это важно: `PolicyEvaluationVector` разделяет каналы на `primary`, `hard_constraints`, `secondary` и `penalties`, а сам тип описан как слой **tiered multi-objective evaluation**, то есть система уже мыслит не в одном числе, а в нескольких каналах одновременно. Одновременно в этом же типе есть `legacy_scalar_proxy`, который агрегирует каналы назад в одно число. И это не просто «исторический хвост»: legacy search controller при наличии `policy_evaluation` использует именно `policy_evaluation.legacy_scalar_proxy` как `objective_value`. Иными словами, кодовая база уже умеет выражать вектор фактов, но часть управляющего контура все еще принимает решения через скалярное схлопывание. fileciteturn37file0L3-L3 fileciteturn52file0L3-L3

Слой frontier-фактов тоже уже существует. `PolicyFrontierReport` хранит `global_frontier`, `view_membership` и `PolicyFrontierEntry` с `primary_objectives` и `constraint_statuses`. Узел `run_hierarchical_policy_search` умеет сериализовать frontier-слепок по кандидатам и отдельный вид `global_feasible`. Но тот же узел использует внутренний rank key, где фигурируют `policy_value`, `welfare` и `employment`, то есть frontier фиксируется как артефакт, а процедурное продвижение кандидата все еще частично идет через компрессию каналов в удобный ключ ранжирования. Это важный разрыв между «что система знает» и «как она реально решает». fileciteturn16file0L3-L3 fileciteturn34file0L3-L3 fileciteturn36file0L3-L3

`normative_arbitration.py` уже задает полезный шаблон для C18, но пока в слишком узкой форме. Он работает в режиме `proposal_vs_baseline`, требует option-outcome matrix с обязательными строками `baseline` и `proposal`, хранит `tradeoff_findings`, `rights_audit`, список `ParetoDominanceWitness` и финальный `NormativeArbitrationResult`. То есть нужные сущности уже названы: outcome matrix, frontier, rights audit, tradeoff findings. Но текущая форма ориентирована на двоичное сравнение предложения с базой, а не на **полноценный N-опционный frontier с отделением factual и normative слоев**. Для C18 это не надо выкидывать; это надо обобщить. fileciteturn14file0L3-L3

Welfare-слой также уже богатый. `WelfareBundle` хранит `social_weight_ref`, `policy_ref`, `baseline_ref`, `channel_decomposition_ref`, `point_estimate`, `credible_interval`, `robust_interval`, `subgroup_welfare`, `readiness_cap`, `warnings`, `status` и diagnostics. Узел `propagate_welfare` действительно собирает эти данные в typed bundle и пишет туда `social_weight_ref`, refs на uncertainty, decomposition и sensitivity diagnostics. Отдельно `foundry/welfare/bounds.py` уже умеет строить welfare-bound report с lower/upper bounds, status и benchmark notes, то есть идея «точка плюс пределы/границы» в кодовой базе уже есть и не требует изобретения с нуля. fileciteturn23file0L3-L3 fileciteturn29file0L3-L3 fileciteturn18file0L3-L3

Более того, PolicyOS уже понимает, что социальные веса — это не произвольный параметр в воздухе. В `test_frontier.py` welfare-методы и налоговые методы пропускают и возвращают `social_weight_ref`, а один из методов строит state-dependent inverse social weights с `swr://...` ref. В Phase 3 gate welfare bundle считается неполным, если `social_weight_ref` отсутствует или не имеет kind `ir.social_weight_manifest`; там же gate требует `WelfareStatus.OK` и наличие GE uncertainty ref. Это означает, что система **уже признает социальные веса decision-bearing артефактом**, но пока проверяет главным образом факт его наличия, а не полноту его governance provenance. fileciteturn31file0L3-L3 fileciteturn41file0L3-L3

Самая важная дырка C18 находится именно здесь. `SocialWeightManifestArtifact` сегодня содержит `manifest_ref`, `method_fqn`, `normalization`, `income_grid`, `weights_on_grid`, `state_keys`, `regime_ids`, `manifest_payload` и `metadata`. В Phase 3 helper при его создании в `metadata` добавляется только `source_handle`. Этого достаточно, чтобы восстановить «какая численная schedule была использована», но недостаточно, чтобы ответить на требования C18: **кто** выбрал веса, **по какому мандату**, **когда**, **после какой консультации**, **с чьим dissent**, **с каким сроком пересмотра**. Иными словами, сейчас есть provenance вычислительного объекта, но почти нет provenance нормативного выбора. fileciteturn44file0L3-L3 fileciteturn42file0L3-L3

Claim linkage частично закрыт, но не в том виде, который нужен для C18. Валидаторы claim spine уже считают `welfare_bundle_ref` decision-bearing артефактом и проверяют наличие `claims_ref` в workflow state. Тест сборки `policy_output_bundle` подтверждает, что итоговый bundle действительно содержит одновременно `claims_ref` и `welfare_bundle_ref`. Это хорошая база. Но из этого пока не следует, что у каждого welfare-вывода есть **явная карта связей «какое утверждение опирается на какой weight manifest / bound / decomposition / frontier comparison»**. Сейчас есть coverage на уровне «artifact has claims», а C18 требует linkage на уровне «какая welfare-претензия из чего выведена». fileciteturn38file0L3-L3 fileciteturn48file0L3-L3

## Концептуальные принципы, которые стоит принять

Внешняя литература поддерживает именно такое разведение слоев. Современная теория provenance в стандарте W3C PROV определяет provenance как запись об **entities, activities и agents**, а также специально поддерживает **bundles** и даже «provenance of provenance». Для C18 это особенно важно: weight choice, welfare computation и final selection — это не один «объект оценки», а разные сущности с разными агентами ответственности и разной деривацией. citeturn14view2

Теория многокритериальной оптимизации также прямо говорит, что forced aggregation нельзя считать нейтральной подстановкой. Даже в современных работах по nonconvex multiobjective optimization отмечено, что weighted-sum scalarization — распространенный прием, но он может **не восстанавливать** nonconvex или discontinuous части Pareto front. Следовательно, если система показывает только scalar score или использует его как единственную решающую поверхность, она может скрывать релевантные недоминируемые альтернативы. Это полностью совпадает с acceptance-критерием C18, который запрещает прятать Pareto-доминируемые и нормативно значимые distinctions за одним числом. citeturn15view0turn15view1

С другой стороны, связь между Pareto-эффективностью и весами тоже хорошо понятна: Pareto optimality можно характеризовать через weighted utilitarian welfare maximization, но именно **через выбранные welfare weights**. Это дает очень важное архитектурное следствие: веса — не «техническая настройка» и не «случайная гиперпараметризация». Они являются частью нормативного критерия, который выбирает точку внутри множества допустимых tradeoff-решений. Значит, веса должны иметь тот же уровень provenance и reviewable governance history, что и любой другой policy rule. citeturn23view0

Наконец, и экономическая литература, и уже существующие PolicyOS артефакты подсказывают, что point scalar welfare часто недостаточен даже при хорошем predictive слое. В работе по demand and welfare under social interactions показано, что данные, достаточные для counterfactual demand prediction, могут быть **недостаточны для welfare calculation**, а в таких случаях естественным выходом становятся bounds, а не ложная точка. Это хорошо согласуется с тем, что PolicyOS уже хранит `credible_interval`, `robust_interval` и отдельные welfare bounds. Для C18 правильная архитектура должна трактовать scalar aggregate как **одну из возможных производных презентаций**, а не как единственную «истину» welfare. citeturn17view0 fileciteturn23file0L3-L3 fileciteturn18file0L3-L3

## Предлагаемый ADR

### Статус и основная идея

**Статус:** proposed.  
**Решение:** сделать в PolicyOS трехслойную модель, где отдельно существуют **frontier facts**, отдельно **evaluative transforms** и отдельно **governance decisions**. Смысл не в том, чтобы запретить скаляры, а в том, чтобы лишить их привилегии скрывать то, что было выбрано нормативно и что остается доступным на frontier как факт. Это минимально конфликтует с текущей архитектурой, потому что в репозитории уже есть `PolicyEvaluationVector`, `PolicyFrontierReport`, `WelfareBundle`, `SocialWeightManifestArtifact`, `NormativeArbitrationResult` и claim spine; нужно не строить новый мир, а сделать связки между уже существующими слоями явными и обязательными. fileciteturn37file0L3-L3 fileciteturn16file0L3-L3 fileciteturn23file0L3-L3 fileciteturn44file0L3-L3 fileciteturn14file0L3-L3

### Frontier facts

В factual-слое единицей учета должен быть не score, а **candidate outcome vector**. Практически это значит: расширить текущие `PolicyFrontierEntry` и `PolicyFrontierReport` так, чтобы для каждого кандидата были обязательны `objective_vector`, `constraint_statuses`, `rights_status`, `uncertainty_summary`, `subgroup_outcomes`, `dominance_status`, `dominated_by`, `frontier_views` и ref на supporting artifacts вроде `welfare_bundle_ref`, `distributional_report_ref`, `rights_audit_ref` и `welfare_bound_report_ref`. Недоминируемость должна быть вычисленным фактом; нарушение прав или hard constraints должно оставаться отдельным factual каналом, а не «штрафом», растворенным в scalar proxy. Это напрямую согласуется с уже существующим разделением на primary/hard_constraints/secondary/penalties и с существующим frontier report. fileciteturn37file0L3-L3 fileciteturn16file0L3-L3 fileciteturn34file0L3-L3

### Evaluative transforms

Во втором слоеPolicyOS должен хранить не «лучший кандидат», а **правило сравнения**, примененное к factual frontier. Это может быть weighted welfare, lexicographic rule, maximin, protected-group floor rule, budget-first rule или иное declared decision rule. Ключевое требование: каждый такой transform должен существовать как самостоятельный артефакт, например `ValueChoiceRuleArtifact`, со ссылками на `social_weight_provenance_ref`, `mandate_ref`, `rule_owner`, `effective_at`, `review_status`, `fallback_rule`, `sensitivity_suite_ref` и `dissent_refs`. Тогда scalar welfare не исчезает, но перестает быть «сам собой разумеющимся фактом»: он становится **результатом конкретного evaluative transform**, который можно аудировать, переиграть и оспорить. Это соответствует как внутренней логике `social_weight_ref`, так и внешнему факту, что Pareto-optimality и utilitarian selection связаны именно через выбранные веса. fileciteturn23file0L3-L3 fileciteturn44file0L3-L3 citeturn23view0

### Social-weight provenance

Для C18 лучше не просто расширять `metadata` внутри `SocialWeightManifestArtifact`, а ввести рядом более богатый артефакт, например `SocialWeightProvenanceArtifact`, который будет **оборачивать** технический manifest и добавлять governance provenance. Минимальный обязательный состав полей: `manifest_ref`, `manifest_artifact_ref`, `chosen_by`, `chooser_role`, `mandate_ref`, `decision_body`, `selected_at`, `effective_from`, `review_due_at`, `affected_groups_consulted`, `consultation_refs`, `community_feedback_refs`, `dissent_refs`, `supersedes_ref`, `justification_claim_ids`, `approval_status` и `policy_scope`. Тогда текущий `SocialWeightManifestArtifact` остается числовым и reproducible, а новый provenance-артефакт несет человеческую и институциональную ответственность, которую сейчас код не хранит. Именно этого требует текст C18. fileciteturn44file0L3-L3 fileciteturn42file0L3-L3 fileciteturn4file0L3-L3 fileciteturn5file0L3-L3

### Welfare audit trail и claim linkage

Третий необходимый новый артефакт — `WelfareAuditTrailArtifact`. Он должен связывать в одно место: `welfare_bundle_ref`, `social_weight_provenance_ref`, `channel_decomposition_ref`, `welfare_bound_refs`, `phase3_gate_ref`, `frontier_report_ref`, `selection_rule_ref` и, главное, список `claim_links`, где каждая запись будет иметь формат вроде `{claim_id, claim_kind, supporting_artifact_ref, derived_from_artifact_refs, affected_candidates, affected_groups}`. Тогда claim spine перестанет быть только проверкой покрытия decision-bearing artifacts и станет объяснительной картой того, какой welfare claim из чего получился. Для этого не нужно менять базовую идею claim spine: валидаторы уже считают welfare bundle decision-bearing, а output bundle уже несет и `claims_ref`, и `welfare_bundle_ref`; нужен именно более глубокий linkage слой поверх существующей инфраструктуры. fileciteturn38file0L3-L3 fileciteturn48file0L3-L3 fileciteturn23file0L3-L3

### Governance decision record

Отдельный артефакт должен фиксировать сам факт выбора. Предлагаю `NormativeDecisionRecord`, который содержит `selected_candidate_hash`, `selection_basis`, `frontier_view_used`, `selection_rule_ref`, `decision_maker`, `decision_time`, `explicit_tradeoff_statement`, `rejected_nondominated_candidates`, `override_of_rights_or_constraints`, `dissent_refs` и `publication_summary`. Здесь важно одно правило: если выбор делается **между недоминируемыми вариантами**, запись обязательна всегда; если выбирается **Pareto-доминируемый** кандидат, система должна не просто разрешать это по override, а требовать явный red-flag override с повышенным review. Это ровно тот случай, где C18 требует не прятать explicit normative decisions. fileciteturn14file0L3-L3 fileciteturn4file0L3-L3 fileciteturn5file0L3-L3

### Изменения в решающих кодовых точках

Самый важный операционный сдвиг — убрать `legacy_scalar_proxy` из **decisive path** поиска и продвижения. Его можно сохранить как совместимый derived metric для сортировки в дебаге или для экспорта в legacy surfaces, но SearchController и promotion logic не должны использовать его как окончательную objective truth без ссылки на declared selection rule. В текущем виде контроллер буквально подставляет `legacy_scalar_proxy` как `objective_value`; для C18 это надо заменить на одну из двух схем: либо frontier-preserving selection с явным rule artifact, либо временный compatibility path, в котором scalar proxy допустим только если одновременно persisted `selection_rule_ref` и `social_weight_provenance_ref` уже существуют. Параллельно `PolicyFrontierReport` должен стать не просто слепком feasible точек, а обязательной публичной поверхностью сравнения для финального выбора, а `normative_arbitration.py` — перейти от `proposal_vs_baseline` к `frontier_vs_selection`, сохранив текущий baseline/proposal режим как частный case. fileciteturn52file0L3-L3 fileciteturn16file0L3-L3 fileciteturn34file0L3-L3 fileciteturn14file0L3-L3

## Когда скалярной welfare-агрегации недостаточно

С точки зрения ADR скалярный aggregate должен считаться **insufficient by default** в пяти типах ситуаций. Во-первых, когда frontier nonconvex или discontinuous, потому что weighted-sum can miss relevant Pareto points. Во-вторых, когда существуют hard constraints, rights findings или feasibility blockers: такие вещи должны оставаться отдельными каналами, а не превращаться в штраф внутри score. В-третьих, когда subgroup outcomes разнонаправлены или sign-reversing: один суммарный welfare number может скрывать, что часть групп выигрывает, а часть систематически проигрывает. В-четвертых, когда uncertainty представлена bounds или overlapping intervals вместо устойчивой точки. В-пятых, когда сама экономическая идентификация welfare неполна и литература рекомендует bounds rather than point welfare. Эти пять случаев полностью совместимы и с внешней теорией, и с уже существующими PolicyOS артефактами для uncertainty, bounds и distributional reporting. citeturn15view0turn15view1turn17view0 fileciteturn37file0L3-L3 fileciteturn23file0L3-L3 fileciteturn18file0L3-L3

## Как это закрывает acceptance

Требование «welfare aggregation cannot hide social-weight provenance» закрывается тем, что любой scalar welfare в публикации или decision packet обязан иметь `selection_rule_ref` и `social_weight_provenance_ref`, а Phase 3 gate должен проверять уже не только наличие `ir.social_weight_manifest`, но и наличие полноценного provenance-артефакта с mandate, chooser, time, affected groups, dissent и review status. Без этого scalar output может считаться вычислимым, но не publishable. Это естественное расширение уже существующего gate, который и сейчас fail-closed блокирует отсутствие welfare/social weight coverage. fileciteturn41file0L3-L3 fileciteturn44file0L3-L3

Требование «cannot hide Pareto-dominated alternatives» закрывается тем, что final selection должен ссылаться на `PolicyFrontierReport` с `dominance_status` и `dominated_by`. Если выбранная альтернатива доминируема, UI и packet обязаны показать этот факт как red-flag override; если недоминируема, packet обязан показать хотя бы ближайший frontier slice и список других недоминируемых опций, от которых отказались. Таким образом scalar ranking может оставаться удобным secondary view, но больше не может стирать topology frontier. fileciteturn16file0L3-L3 fileciteturn34file0L3-L3 citeturn15view0turn15view1

Требование «cannot hide explicit normative decisions» закрывается введением `NormativeDecisionRecord` и обязательным linkage его к claim spine. Выбор между недоминируемыми альтернативами — это не новый factual computation, а нормативный акт; он должен сохранять decision maker, rule, rationale, dissent и ссылки на claims. База для этого в системе уже есть: claim validators знают, что welfare bundle decision-bearing, а output bundle уже связывает `claims_ref` с policy output. Нужно лишь сделать сам normative choice first-class artifact, а не оставлять его как неявный эффект search/proxy logic. fileciteturn38file0L3-L3 fileciteturn48file0L3-L3 fileciteturn52file0L3-L3

## Итоговая рекомендация

Лучшее решение для C18 — **не запрещать агрегаты, а понижать их статус**: scalar welfare должен стать всего лишь производным представлением поверх трех обязательных слоев — frontier facts, evaluative transform и governance decision record. В текущем PolicyOS почти все строительные блоки уже присутствуют: multi-objective vector, frontier snapshot, welfare bundle, welfare bounds, social weight manifest, phase gates и claim spine. Не хватает главным образом одного: сделать норму выбора **явным артефактом с provenance**, а не молчаливым следствием proxy score или rank key. Поэтому оптимальный ADR — это эволюция существующей архитектуры, а не ее замена. fileciteturn37file0L3-L3 fileciteturn16file0L3-L3 fileciteturn23file0L3-L3 fileciteturn44file0L3-L3 fileciteturn38file0L3-L3

## Открытые вопросы и ограничения

Не все вопросы можно считать закрытыми только по просмотренным якорям.

- В текущих якорях видно, что `normative_arbitration.py` уже покрывает baseline/proposal и rights audit, но не видно готового N-опционного public contract для frontier-wide normative selection; его, вероятно, придется либо расширять, либо вводить рядом как новый artifact. fileciteturn14file0L3-L3
- По коду можно уверенно описать backend artifacts и gates, но не полностью восстановить текущую UI/packet-подачу frontier и dominance-информации; значит, presentation contract для decision packet еще придется отдельно зафиксировать. fileciteturn16file0L3-L3 fileciteturn48file0L3-L3
- Внешняя часть исследования опиралась на первичные источники по provenance и multiobjective/welfare-theory, но official public-policy manuals по distributional weighting не были надежно извлечены инструментами в этой сессии; поэтому рекомендации по governance provenance опираются прежде всего на сам репозиторий и общие стандарты provenance/optimization, а не на конкретный государственный handbook. citeturn14view2turn23view0turn17view0turn15view0

# C16 Поверхность Policy Design Case для разных аудиторий в PolicyOS

## Контекст задачи

План `POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md` требует для C16 не просто новый DTO, а именно **концептуальный surface contract**: сначала нужно определить, что именно должны видеть `PUBLIC`, `REVIEWER`, `EXPERT` и `MACHINE`, а уже потом переводить это в API-контракты, TypeScript-клиент, валидаторы и dashboard. В самом описании C16 прямо зафиксированы обязательные элементы будущего `PolicyDesignCaseProjection`: граф утверждений, warrant-структуры, authority summary, readiness gates, approval decision, publication status, contested records, deficit register, invariants и machine-readable authority gaps; отдельно нужны redactions, source-truth conflicts, audit-verifier results, failure records и связь с generic run/artifact endpoint-ами без minting authority. Acceptance сформулирован жёстко: внешняя подотчётность не должна требовать обхода сырых blob-артефактов и не должна опираться на доверие к generic dict payload. fileciteturn6file0L3-L3 fileciteturn8file0L3-L3

Ниже я рассматриваю C16 как **исследовательское проектирование поверх уже существующей архитектуры**, а не как clean-room schema exercise. Это соответствует общему правилу плана: later tasks не могут вести себя так, будто PolicyOS — blank slate. fileciteturn6file0L3-L3

## Что уже реализовано в репозитории

В `runtime/quality/projection_semantics.py` уже есть минимальная, но важная projection-semantics основа. Runtime строит проекцию только после `validate_policy_design_case_profile(...)`, присваивает ей собственную schema version, перечисляет допустимые projection states (`draft`, `projection_only`, `redacted`, `stale`, `contested`, `blocked`, `publishable`), помечает каждый label как `authority_role="projection_only"`, указывает `projection_policy="reads_policy_design_case_only"`, фиксирует `may_be_used_for` и `may_not_be_used_for`, а затем fail-closed запрещает любой случай, где projection пытается стать authority, где label получает authority-bearing role, или где source payload заявляет роли вроде `producer_authority`, `scorecard_input` или `readiness_input`. Сами `blocked` / `contested` / `stale` выводятся эвристически из status-полей и структур вроде `source_truth_conflicts`, `counter_evidence`, `rebuttals` и `blockers`. fileciteturn11file0L3-L3 fileciteturn12file0L3-L3

`runtime/quality/public_export.py` уже делает второй важный шаг: строит redacted public bundle, который явно остаётся `projection_only`, имеет `official_use_limits.official_use="public_audit_only"`, запрещает использовать bundle для `scorecard_authority`, `approval_authority` и `runtime_closeout_authority`, переносит authority envelopes только как projection-представления с fingerprint-ами и `tenant_redacted=True`, а также рекурсивно вырезает секреты, tenant refs, prompts, credentials и прочие sensitive материалы. Этот же слой fail-closed отвергает public export при unexplained replay drift или accepted-but-non-ready drift. Юнит-тесты подтверждают и redaction чувствительных данных, и то, что public bundle может читать PDC projection, но не повышает authority. fileciteturn13file0L3-L3 fileciteturn14file0L3-L3 fileciteturn45file0L3-L3

На control-plane стороне уже есть typed pieces для operator-facing surfaces: `ControlAuthorityGap`, `ControlApprovalProjection`, `ControlProjectionSource`, `OperatorDiagnostic`, а `response_shapes.py` добавляет `policy_design_case_projection` в ответ control job, строит unresolved authority gaps, поднимает source-truth conflicts между runtime scorecard и API projection, и пытается получить PDC projection из nested runtime progress. Но если построение проекции падает, `_policy_design_projection(...)` просто возвращает `None`; то есть типизированного projection-failure payload пока нет. Это важный текущий разрыв для C16. fileciteturn15file0L3-L3 fileciteturn16file0L3-L3

Отдельно уже существует **multi-audience compiler** в `scientist/publishing/publisher.py`. `DecisionGradeExport` строго различает `PUBLIC`, `REVIEWER`, `EXPERT` и `MACHINE`, требует `trust_provenance`, заставляет все audience-tier exports ссылаться на один и тот же `claims_ref` и `research_dag_ref`, не разрешает public omissions с hidden refs, запрещает silently omit blocked claims, а reviewer/expert/machine tiers обязывает включать blocked claims явно. Тесты подтверждают, что public видит approved claims и только summary о blocked claims, reviewer получает blocked claim details, expert — methods/assumptions/uncertainty, а machine — refs и frontend trust view. fileciteturn24file0L3-L3 fileciteturn25file0L3-L3 fileciteturn46file0L3-L3 fileciteturn47file0L3-L3

Для external-governance уже есть и audit-verifier substrate. `core/audit/models.py` задаёт `VerificationReport` с общим PASS/FAIL verdict, step-level результатами для `package_integrity`, `cas_integrity`, `signature_verification`, `provenance_validation`, `dependency_completeness` и `slsa_verification`, а `AuditPackageVerifier` реально проверяет package format, checksums, CAS-integrity, подписи, provenance, completeness и SLSA-поведение. Это даёт готовую основу для поля `audit_verifier_results` в C16 surface; изобретать новый verifier status model не нужно. fileciteturn34file0L3-L3 fileciteturn35file0L3-L3

## Главный разрыв в текущей поверхности

Проблема не в том, что в PolicyOS совсем нет семантики. Проблема в том, что **семантика локально типизирована, но наружу уходит как слишком слабая поверхность**. В `ControlJobResponse` поле `policy_design_case_projection` всё ещё имеет тип `dict[str, Any] | None`; в generated TypeScript client это превращается в `{ [key: string]: unknown } | null`; а dashboard validator принимает проекцию как `z.record(z.string(), z.unknown())` и уже на клиенте запускает fail-closed normalizer. Иными словами, backend пока не публикует canonical typed PDC projection — frontend вынужден сам распознавать masking cases, promotion labels и ограничения authority. Это именно тот анти-pattern, который acceptance C16 хочет убрать. fileciteturn20file0L3-L3 fileciteturn32file0L3-L3 fileciteturn26file0L3-L3 fileciteturn52file0L3-L3

Этот разрыв виден и в `publicationPacket.ts`: dashboard уже строит публичный decision packet, уже имеет собственный `PublicProjectionSemantics`, собственные public projection states и собственный trust framing, но входное `policyDesignCaseProjection` там по-прежнему `Record<string, unknown> | null`. Значит, surface semantics частично живут в UI-домене и компенсируют backend drift, а не читаются как единый typed source of truth. fileciteturn50file0L3-L3 fileciteturn48file0L3-L3

Есть и второй разрыв: audience semantics уже хорошо формализованы в `DecisionGradeExport`, но они существуют **рядом** с runtime PDC projection, а не внутри одного canonical object. Public/reviewer/expert/machine tiers уже знают, как по-разному скрывать или раскрывать blocked claims, methods и refs, однако runtime `policy_design_case_projection` пока содержит лишь минимальную projection metadata, а не полноценный typed PDC surface. В результате PolicyOS имеет две сильные половины — runtime projection guardrails и audience-aware publishing — но между ними ещё нет общего typed PDC contract. fileciteturn11file0L3-L3 fileciteturn24file0L3-L3 fileciteturn25file0L3-L3

Мой главный исследовательский вывод для C16 такой: **PolicyOS не нужно изобретать surface semantics с нуля; ему нужно свести уже существующие projection-only guardrails, decision-grade audience compiler, control-plane authority gaps и audit-verifier report в один canonical typed `PolicyDesignCaseProjection`**, из которого дальше уже генерируются OpenAPI, Pydantic, TypeScript и dashboard validators. Это вывод из наблюдаемой кодовой структуры, а не абстрактное пожелание. fileciteturn8file0L3-L3 fileciteturn11file0L3-L3 fileciteturn16file0L3-L3 fileciteturn24file0L3-L3 fileciteturn34file0L3-L3

## Предлагаемый контракт PolicyDesignCaseProjection

### Каноническая форма

Ниже — рекомендуемая каноническая форма. Это уже не описание текущего кода один-в-один, а **предлагаемый C16 contract**, собранный так, чтобы максимально переиспользовать существующие модули: `projection_semantics.py`, `public_export.py`, `DecisionGradeExport`, control contracts и audit verifier. Основание для такого разбиения — то, что сейчас states, approval, publication, authority gaps, blocked claims и audit results находятся в разных соседних слоях и должны быть сведены в один surface object. fileciteturn11file0L3-L3 fileciteturn13file0L3-L3 fileciteturn19file0L3-L3 fileciteturn24file0L3-L3 fileciteturn34file0L3-L3

```ts
type Audience = "public" | "reviewer" | "expert" | "machine";

type PolicyDesignCaseProjection = {
  schema_name: "polisyos.runtime.PolicyDesignCaseProjection";
  schema_version: "1.0";
  projection_id: string;
  audience: Audience;

  case_id: string;
  run_id: string;
  emitted_at: string;

  refs: {
    policy_design_case_ref: string;
    claims_ref?: ArtifactRef;
    research_dag_ref?: ArtifactRef;
    decision_grade_export_ref?: ArtifactRef;
    quality_scorecard_ref?: ArtifactRef;
    approval_packet_ref?: ArtifactRef;
    public_export_bundle_ref?: ArtifactRef;
    audit_package_ref?: ArtifactRef;
    audit_verification_report_ref?: ArtifactRef;
  };

  semantics: {
    authority_role: "projection_only";
    projection_policy: "reads_policy_design_case_only";
    may_be_used_for: string[];
    may_not_be_used_for: string[];
    surface_state:
      | "draft"
      | "projection_only"
      | "redacted"
      | "stale"
      | "contested"
      | "blocked"
      | "publishable";
    states: string[];
    redacted: boolean;
  };

  authority_summary: {
    authority_profile?: "research" | "governed" | "production";
    execution_profile?: "dev" | "research" | "governed" | "production";
    authoritative_refs: Record<string, string>;
    source_truth_conflict_count: number;
    unresolved_authority_gaps: AuthorityGap[];
  };

  claim_graph: {
    nodes: ClaimNode[];
    edges: ClaimEdge[];
    root_claim_ids: string[];
  };

  warrants: WarrantRecord[];

  readiness: {
    overall_status: "pass" | "warn" | "fail" | "blocked" | "not_evaluated";
    gates: ReadinessGate[];
  };

  approval: {
    decision: "approved" | "approved_with_override" | "blocked" | "pending" | "not_evaluated";
    eligible: boolean;
    reasons: string[];
    override_present: boolean;
  };

  publication: {
    status: "draft" | "publishable" | "blocked" | "published" | "withdrawn" | "reissued" | "stale";
    public_export_status?: string;
    blocked_reason_codes: string[];
  };

  contested_records: ContestedRecord[];
  deficit_register: DeficitRecord[];
  invariants: InvariantResult[];

  audit_verifier: {
    overall_status?: "PASS" | "FAIL";
    steps: AuditStepResult[];
    failures: VerificationIssue[];
    warnings: VerificationIssue[];
  };

  omissions: OmissionRecord[];
  redactions: RedactionRecord[];

  machine_commitments: {
    json_schema_id: string;
    openapi_component: string;
    typescript_type: string;
    dashboard_validator_id: string;
  };

  failures: ProjectionFailureRecord[];
};
```

Самое важное принципиальное решение здесь — **развести `surface_state`, `approval` и `publication`**. Текущий код смешивает рядом display-like states (`redacted`, `projection_only`), quality/readiness consequences (`blocked`, `stale`, `contested`) и отдельные approval/publication признаки, извлекаемые из scorecard, public export status и final artifacts. Если оставить всё в одном enum, наружный surface опять станет двусмысленным. fileciteturn11file0L3-L3 fileciteturn12file0L3-L3 fileciteturn16file0L3-L3 fileciteturn19file0L3-L3

### Граф утверждений и warrant-структуры

Для `claim_graph` не нужно заново выдумывать набор ref-категорий. `decision_compiler.py` уже фиксирует, какие референсы важны для decision-grade claim surface: `concept_refs`, `legal_norm_refs`, `source_data_refs`, `method_refs`, `portfolio_refs`, `independence_refs`, `specification_curve_refs`, `disconfirming_refs`, `synthesis_refs`, `objective_tradeoff_refs`, `uncertainty_refs`, `numerical_semantics_refs`, `monitoring_refs`; отдельно есть scholar/literature ref-keys и scholar deficit keys. Поэтому узел claim graph должен нести не произвольный `evidence_refs: string[]`, а **typed ref sets** по этим семействам. Это позволит public/reviewer/expert/machine consumers видеть один и тот же claim graph, но с разной глубиной раскрытия. fileciteturn22file0L3-L3

`warrants` я рекомендую отделить от claim nodes в самостоятельный массив и ссылать через `claim_id`. Причина не только концептуальная, но и кодовая: план для C15 уже требует formalize warrant semantics beyond free text, а C16 должен surface-ить эти структуры, а не прятать их внутрь string summary. Поэтому warrant record должен иметь как минимум `warrant_id`, `claim_id`, `statement`, `assumptions`, `applicability_predicates`, `reliability_refs`, `berl_refs`, `scope_limits`, `counterevidence_refs` и `status`. Это логичное продолжение существующей связки “claim -> argument -> warrant -> evidence -> authority -> readiness”, которую сам план закрепляет как acceptance для соседней задачи C15. fileciteturn8file0L3-L3

### Семантика по аудиториям

У PolicyOS уже есть фактический baseline для audience slicing в `DecisionGradeExport`, и C16 должен его **втянуть внутрь PDC projection**, а не дублировать рядом. В текущем baseline public tier видит summary, approved visible claims, limits и blocked-claim summary; reviewer tier видит claim ledger export, blocked claims, reviewer controls и evidence counts; expert tier — methods, uncertainty, assumptions и benchmark authority; machine tier — refs и trust view для downstream consumption. Именно этот pattern стоит сделать официальным audience contract-ом PDC. fileciteturn24file0L3-L3 fileciteturn25file0L3-L3 fileciteturn46file0L3-L3

Я предлагаю такой audience split:

| Аудитория | Что должно быть видно |
|---|---|
| `PUBLIC` | headline, policy summary, approved visible claims, blocked-count summary, high-level readiness/publication status, redactions/omissions, high-level audit verifier summary, public-safe refs |
| `REVIEWER` | весь public slice плюс blocked claims, authority gaps, source-truth conflicts, readiness gates, reviewer controls, evidence bundle counts, detailed omissions |
| `EXPERT` | весь reviewer slice плюс methods, assumptions, uncertainty, warrant details, disconfirming evidence, benchmark authority summary, deeper claim/support topology |
| `MACHINE` | полный canonical object без prose-only shortcuts: stable enums, typed refs, invariant results, verifier steps, machine commitments, failure records |

Такой split не является произвольным: он максимально совпадает с уже существующим compiler behavior и одновременно удовлетворяет требованию плана показать именно “что PUBLIC, REVIEWER, EXPERT, and MACHINE consumers should see”. fileciteturn8file0L3-L3 fileciteturn24file0L3-L3 fileciteturn46file0L3-L3

Для `PUBLIC` критично сохранить нынешние запреты: никаких hidden refs в omissions, никаких forbidden benchmark/private tokens, никаких blocked claim details без явного omission record, и никаких секретов/tenant-sensitive values. Это уже жёстко enforced в `DecisionGradeExport` и `public_export.py`, значит C16 должен не ослабить, а поднять эти правила на уровень canonical surface contract. fileciteturn24file0L3-L3 fileciteturn25file0L3-L3 fileciteturn13file0L3-L3 fileciteturn45file0L3-L3

### Failure records и machine-readable authority gaps

План C16 отдельно требует typed projection failure records. Я рекомендую не вводить для них совершенно новый shape, а базировать их на уже существующем operator-side паттерне `ControlAuthorityGap`: `code`, `layer`, `phase`, `message`, `owner`, `evidence_ref`, `next_action`, `next_diagnostic_command`. Поверх него нужно добавить только `failure_family`, `surface`, `schema_expected`, `schema_actual` и `detected_at`. Такой ход reuse-first и одновременно закрывает разрыв, где `_policy_design_projection(...)` сейчас просто проглатывает projection/build errors и возвращает `None`. fileciteturn16file0L3-L3 fileciteturn19file0L3-L3

Минимальный обязательный набор failure families для C16, на мой взгляд, должен быть таким:

- `projection_exception`
- `projection_missing`
- `audit_verifier_ingestion_missing`
- `api_dashboard_schema_drift`
- `public_export_bypass_attempt`

Эти пять прямо вытекают из task text C16. Но в контракте лучше сразу предусмотреть и коды, уже существующие в runtime: `policy_design_projection_mints_authority`, `policy_design_projection_policy_invalid`, `policy_design_projection_label_mints_authority`, `policy_design_projection_source_mints_authority`, `public_export_not_authority`, `public_export_replay_drift_unexplained`, `public_export_replay_drift_unbounded`. Тогда новый PDC surface не будет отрезан от уже работающего fail-closed error vocabulary. fileciteturn8file0L3-L3 fileciteturn11file0L3-L3 fileciteturn13file0L3-L3 fileciteturn45file0L3-L3

`authority_summary.unresolved_authority_gaps` должен принимать не свободный текст, а machine-readable gap records. База для этого уже есть в control-plane; additionally сам decision compiler уже мыслит дефициты как absence of required ref sets, scholar deficits и visibility/blocked semantics. Поэтому `DeficitRecord` я бы формализовал с полями `deficit_id`, `kind`, `claim_id?`, `required_ref_family?`, `status`, `blocking`, `accepted_by`, `evidence_ref?`, `repair_path`. fileciteturn19file0L3-L3 fileciteturn22file0L3-L3

### Audit verifier и invariants как часть поверхности

Так как у verifier уже есть хорошо определённый `VerificationReport`, C16 surface не должен копировать весь audit package, но должен включать **typed verifier summary**: `overall_status`, список step results, failures, warnings, counts и ссылки на package/report refs. Тогда public/reviewer/expert/machine consumers смогут видеть не только “есть audit package”, но и “что именно verifier подтвердил или не подтвердил”, не распаковывая tarball вручную. Это напрямую приближает систему к acceptance C16. fileciteturn34file0L3-L3 fileciteturn35file0L3-L3

`invariants` я предлагаю surface-ить как отдельный массив `InvariantResult`, а не прятать внутрь prose summary. Внутри C16 это особенно важно для следующих инвариантов: `projection_not_authority`, `public_export_official_use_limits`, `claims_and_dag_lineage_consistent`, `blocked_claim_omission_declared`, `audit_package_verified`, `api_dashboard_schema_match`. Это не значит, что все они уже существуют как единые runtime objects; это значит, что существующие проверки в projection/public export/decision-grade export/verifier дают достаточную основу, чтобы C16 свёл их в единый invariant surface. fileciteturn11file0L3-L3 fileciteturn13file0L3-L3 fileciteturn24file0L3-L3 fileciteturn34file0L3-L3 fileciteturn46file0L3-L3

### Связь с generic run и artifact endpoint-ами

План требует “define how generic run/artifact endpoints link to typed projection without minting authority”. На основе текущих route/service surfaces лучший вариант — не убирать generic endpoints, а сделать их **transport surfaces**, которые либо встраивают canonical typed `PolicyDesignCaseProjection`, либо возвращают `policy_design_case_projection_ref` на него. При этом любой inline projection обязан сохранять `authority_role="projection_only"` и `projection_policy="reads_policy_design_case_only"`, а artifact endpoints могут публиковать raw bundle/blob только как drill-down material, но не как источник authority. Именно эту семантику уже проводят `projection_semantics.py` и `public_export.py`; C16 должен сделать её официальной API surface contract, а не внутренним runtime helper behavior. fileciteturn11file0L3-L3 fileciteturn13file0L3-L3 fileciteturn36file0L3-L3

Практически это означает следующее. `ControlJobResponse`, runtime `runs` routes, generated OpenAPI/TypeScript client и dashboard validators должны перестать моделировать `policy_design_case_projection` как generic object. Вместо этого все четыре слоя должны ссылаться на один и тот же canonical schema component. Тогда dashboard больше не будет вынужден обнаруживать masking cases и promotion labels через client-side heuristics поверх `Record<string, unknown>`; он сможет работать как consumer typed object и использовать fail-closed normalization уже как **defensive invariant check**, а не как substitute for missing schema. fileciteturn20file0L3-L3 fileciteturn32file0L3-L3 fileciteturn26file0L3-L3 fileciteturn52file0L3-L3

## Почему этот дизайн закрывает acceptance C16

Если canonical `PolicyDesignCaseProjection` будет содержать в одном typed object: claim graph, typed warrants, authority summary, readiness gates, approval decision, publication status, contested records, deficit register, invariants, audit verifier summary, omissions/redactions и machine-readable refs, то внешнему потребителю больше не придётся вручную обходить raw artifact blobs, разгадывать shape generic dict payload, или доверять frontend-specific normalizer logic. При этом drill-down в raw artifacts останется возможен через refs, но перестанет быть обязательным для accountability. Это и есть буквальное выполнение acceptance C16. fileciteturn8file0L3-L3 fileciteturn20file0L3-L3 fileciteturn26file0L3-L3 fileciteturn32file0L3-L3

С архитектурной точки зрения лучший ход — сделать `DecisionGradeExport` не конкурирующим surface рядом с PDC projection, а **audience-specific derivative view** от canonical `PolicyDesignCaseProjection`. Иначе PolicyOS продолжит дублировать audience semantics в двух местах: в scientist publishing и в runtime projection/public export. Сводя их вместе, система получает один source of truth для API, TS client, dashboard и public export semantics. Это согласуется и с reuse-first установкой плана, и с уже существующим compiler behavior. fileciteturn6file0L3-L3 fileciteturn24file0L3-L3 fileciteturn25file0L3-L3

## Итоговый исследовательский вывод

В текущем состоянии репозитория PolicyOS уже имеет почти все нужные **семантические кирпичи** для C16: projection-only authority guardrails, public export redaction/use-limits, audience-aware `DecisionGradeExport`, control-plane authority gaps и audit verification report. Но наружная surface contract по-прежнему слишком слабая: API и generated TS client выносят `policy_design_case_projection` как generic dict, dashboard компенсирует это fail-closed эвристиками, а projection failures не surfaced как typed records. fileciteturn11file0L3-L3 fileciteturn13file0L3-L3 fileciteturn20file0L3-L3 fileciteturn26file0L3-L3 fileciteturn32file0L3-L3

Поэтому для C16 я рекомендую следующее формальное решение: **ввести один canonical typed `PolicyDesignCaseProjection`, сделать его projection-only by construction, встроить в него audience slicing, verifier summary, authority gaps и deficit register, а затем генерировать из него OpenAPI, TypeScript client, dashboard validators и public export bindings**. Это не rebuild-from-scratch, а систематическое сведение уже существующих сильных модулей в один официальный external surface. fileciteturn8file0L3-L3 fileciteturn11file0L3-L3 fileciteturn24file0L3-L3 fileciteturn34file0L3-L3

## Открытые вопросы и ограничения

В этом проходе я не делал ещё один полный extract `validate_policy_design_case_profile(...)` из `assurance_case.py`, поэтому минимальный mandatory field set самого canonical case profile я реконструировал по окружению, а не по полной валидационной матрице. Это не меняет главный вывод C16, но перед freeze JSON Schema стоит сделать короткий verification pass именно по этому валидатору. fileciteturn11file0L3-L3

Я также сознательно не раскрывал здесь все возможные contested-category enums из соседнего C17 и все warrant-profile детали из C15. Для C16 это допустимо: surface contract уже можно зафиксировать сейчас, оставив `contested_records.kind` и `warrants.status/applicability` расширяемыми enum-полями, которые затем уточнятся соседними концептуальными задачами.

# Граница LLM и файрвол между кандидатом и авторитетом

## Краткий вывод

План Research Plan для universal Policy Design Case уже задает правильную архитектурную гипотезу: LLM в PolicyOS должны формулировать **кандидатные** гипотезы, риски, обязательства и пропущенные вопросы, а не становиться источником права, данных, научного метода или решающей authority. Неподтвержденное содержимое должно оставаться в одном из контролируемых состояний вроде `candidate_unverified`, `rejected_speculation`, `typed_blocker` или `limitation`, а C12 прямо требует, чтобы LLM-контент **не** превращался в law, data, stakeholder preference, method authority или closeout authority без producer validation. fileciteturn27file0L3-L3 fileciteturn29file0L3-L3 fileciteturn26file0L3-L3

Главный вывод по коду и внешней литературе такой: **PolicyOS уже существенно ближе к нужной модели, чем кажется**. В репозитории есть детерминированные критики и валидации, bounded LLM workers с fallback, phase-gated publishing, projection-only semantics и authority-envelope contracts. Поэтому для C12 не нужен “новый умный judge”. Нужен формальный **speculation firewall**, в котором LLM может только предлагать, критиковать и драфтить, а любой переход в authority проходит через typed validation, producer-owned refs, claim/evidence binding, same-input closure и phase gates. Это хорошо согласуется и с NIST AI RMF: trustworthy AI требует valid/reliable, accountable/transparent, explainable practices, человеческого суждения о метриках и порогах, ongoing testing, proportional controls для high-consequence contexts и ясно определенных ролей в human-AI interaction. fileciteturn18file0L3-L3 fileciteturn19file0L3-L3 fileciteturn20file0L3-L3 fileciteturn22file0L3-L3 fileciteturn23file0L3-L3 fileciteturn24file0L3-L3 citeturn7view0turn8view3

С исследовательской точки зрения это означает следующее. Базовый вопрос C12 должен звучать не “насколько LLM хорош как policy thinker?”, а “какую **добавочную** пользу он дает поверх deterministic baseline, не увеличивая authority-laundering risk?”. На этот вопрос нельзя отвечать только LLM-as-a-judge, потому что сами LLM-судьи показывают известные bias modes, включая position, verbosity и self-enhancement bias, хотя и могут быть полезны как вспомогательный evaluator. Итоговый протокол должен опираться на human-adjudicated gold set, а LLM judge использовать только как triage или secondary signal. fileciteturn26file0L3-L3 citeturn13academia0turn8view3

## Что уже есть в PolicyOS и почему это важно

Репозиторий уже явно не является blank slate. Сам план требует reuse-first подхода и прямо указывает, что исследования по LLM boundary должны стартовать от существующих модулей `policy_design`, `ConstraintCritic`, `ScenarioAdversaryWorker`, `LLMBudgetEnforcer`, `prompt_tool_ledger.py`, publishing и claim validation, а не сочинять параллельную архитектуру. Более того, dense context отдельно выделяет C12 как задачу не про “critic personas”, а про formalizing the candidate-to-authority firewall поверх уже существующего deterministic critic и LLM-plus-fallback patterns. fileciteturn27file0L3-L3 fileciteturn28file0L3-L3

Эта база в коде действительно есть. `ScenarioAdversaryWorker` делает именно bounded-паттерн: создает traced gateway client, опционально оборачивает его в `LLMBudgetEnforcer`, требует JSON-object output, валидирует предложения через typed Pydantic models, а при отсутствии клиента, пустом результате или ошибке уходит в детерминированный fallback bundle; после этого сценарии компилируются в deterministic stress-test plan и исполняются через `run_stress_test`. `PolicyTranslatorWorker` повторяет ту же логику: LLM используется только для bounded structured draft, а при ошибке применяется `DeterministicPolicyTranslator`; затем отдельный `TranslatorCompliancePass` детерминированно ловит переоценку readiness, пропуск обязательных assumptions, collapse uncertainty, omission subgroup harms, omission binding constraints и summary drift. Это уже почти канонический pattern для C12. fileciteturn11file0L3-L3 fileciteturn17file0L3-L3 fileciteturn31file0L3-L3

`prompt_tool_ledger.py` тоже является сильным якорем: для model-assisted step он требует rendered inputs, parser contract, validation refs и authority handoff refs; сводный ledger считается passing только если присутствуют требуемые scopes и если шаги имеют passing validation и handoff status. Это очень близко к тому, что нужно для firewall. Но здесь же скрывается один из самых важных C12-рисков: helper `build_prompt_tool_ledger_from_model_variant` по умолчанию заполняет **все** authority scopes (`evidence`, `claims`, `scorecard`, `approval`) для runtime model-variant summary. Как инженерный shortcut это удобно, но как политика authority — слишком щедро. Для C12 это должно быть ужесточено: raw LLM-step не должен автоматически получать scopes, намекающие на claim, scorecard или approval authority, пока нет producer-side validation и explicit handoff. Это — не баг формальной валидации, а gap в source classification, который C12 как раз должен закрыть. fileciteturn18file0L3-L3

Детерминированная “нижняя граница” authority уже тоже есть. `claim_support.py` намеренно разделяет evidence support и publication state; разные claim families требуют конкретных support predicates, а слабая или отсутствующая поддержка переводит claim в review-required/internal-only, а counterevidence может блокировать публикацию или понижать readiness. `citation_faithfulness.py` вообще принципиально не использует live LLM judging: public factual/legal claims без citation refs или с fabricated, unverifiable, contradictory, irrelevant и scope-limited citations получают fail. Затем `PolicyArtifactBuilder` требует для promoted bundle не только `DecisionReadinessContract`, но и persisted readiness ref, evaluation vector и complete Phase 3 certificate package с loadable refs; а `publisher.py` публикует audience-tiered outputs только из claim ledger и research DAG, запрещая silent omission blocked claims и фильтруя forbidden public export tokens вроде `hidden_holdout`, `system_prompt` и `developer_prompt`. Наконец, `projection_semantics.py` явным fail-closed образом запрещает использовать projection для claim, approval и runtime closeout authority, а `authority.py` различает authority-bearing и projection-like envelopes и отвергает projection roles как источник serious authority. Иначе говоря, у PolicyOS уже есть почти все кирпичи для “LLM cannot become law”. fileciteturn19file0L3-L3 fileciteturn20file0L3-L3 fileciteturn16file0L3-L3 fileciteturn22file0L3-L3 fileciteturn23file0L3-L3 fileciteturn24file0L3-L3

Есть и один особенно показательный сигнал, почему C12 должен быть формальным, а не только культурным правилом. В `search.py` ветка `_hybrid_seed_candidates` создает traced gateway client и потом маркирует source как `hybrid_seed_llm_assisted`, если gateway доступен, и как `hybrid_seed_degraded`, если нет. Но сами hybrid seeds в этом фрагменте строятся детерминированно через `_build_monitoring_hybrid_seed`, `_build_transport_hybrid_seed` и `_build_evidence_hybrid_seed`; то есть label про “llm_assisted” здесь может не отражать реального model invocation. Для C12 это критично: provenance labels не должны намекать на LLM-participation или authority без зафиксированного prompt/run/output ledger. Иначе возникает не “hallucination of facts”, а более опасная “hallucination of provenance”. fileciteturn33file0L3-L3 fileciteturn18file0L3-L3

## Канонический паттерн LLM плюс детерминированный fallback

Наилучшее решение для C12 — канонизировать уже наблюдаемый в коде паттерн как единый policy. Его форма должна быть такой.

Сначала идет **bounded proposal step**: LLM получает только разрешенный контекст, отвечает только в typed JSON schema и получает явный `source_class` вроде `llm_candidate`, `llm_critic` или `llm_drafter`. Затем идет **parser and schema validation**: ответ или проходит структурную валидацию, или отклоняется без частичного “healing into authority”. Потом следует **deterministic baseline comparison**: для critic-like функций baseline задается `ConstraintCritic` и другими deterministic validators, а для drafting — `TranslatorCompliancePass`, `claim_support`, `citation_faithfulness` и publishing gates. После этого нужен **producer validation handoff**: только producer-owned artifacts с refs, same-input closure, authority envelope и validator refs могут повысить статус LLM-originated content из candidate в authority-bearing material. Если handoff не произошел, содержимое остается кандидатом, limitation, review prompt или rejected speculation. Финальный шаг — **projection/publishing under fail-closed semantics**, где наружу уходит только то, что уже прошло claim-ledger и publication gates. Такой pattern уже частично зашит в adversary, translator, citation faithfulness, projection semantics и bundle assembly; C12 должен превратить его из локальной практики в общий контракт. fileciteturn11file0L3-L3 fileciteturn31file0L3-L3 fileciteturn20file0L3-L3 fileciteturn16file0L3-L3 fileciteturn23file0L3-L3

С точки зрения внешних best practices это тоже сильная конструкция. NIST AI RMF прямо связывает trustworthiness с valid/reliable testing, realistic test sets, harm-sensitive thresholds, accountability, transparency, provenance and documentation, а в human-AI appendix требует ясно разграничивать роли и ответственности людей и систем, особенно там, где последствия высоки и where humans must be able to challenge system output. В high-stakes policy design это практически прямой аргумент за “LLM proposes, system validates, humans arbitrate exceptions”. citeturn7view0turn8view3

Внешняя литература по LLM error modes усиливает этот вывод. TruthfulQA показал, что большие языковые модели могут уверенно воспроизводить распространенные ложные представления, а масштабирование само по себе не гарантирует truthfulness; лучший протестированный на этом benchmark model был truthful лишь на 58% вопросов против 94% у людей. Работы по SelfCheckGPT и Chain-of-Verification показывают, что sampling consistency и internal verification действительно **снижают** hallucination risk, но не превращают generated text в proof-carrying authority. А работа “Language Models (Mostly) Know What They Know” полезна как напоминание, что self-evaluation бывает информативным, но task-dependent и неустойчивым при переносе на новые задачи. Следовательно, self-critique допустим как diagnostic layer, но недопустим как last-mile authority. citeturn1academia2turn11academia1turn11academia0turn1academia0

## Предлагаемый файрвол спекуляции

Ниже — рекомендуемая source taxonomy и правила перехода.

**`deterministic_producer`** — это runtime-owned code path или producer output, который может mint authority только после прохождения envelope and validation checks. Только этот класс должен иметь право выдавать `norm_ref`, `data_ref`, `method_ref`, `source_attribution`, `runtime_blocker`, `producer_authority`, readiness refs и phase-gate refs. Именно на этом слое находятся настоящие authority transitions. fileciteturn24file0L3-L3 fileciteturn16file0L3-L3

**`llm_candidate`** — это структурированное предложение модели о policy field, risk, obligation, assumption, missing question или scenario. Оно может стать только `candidate_obligation`, `review_prompt`, `limitation_candidate`, `blocker_candidate` или `rejected_speculation`. Оно не может напрямую создавать law, data, stakeholder preference, method authority, source refs, approval input или closeout authority. Если позже producer подтверждает такой кандидат через ref-bearing validation, authority рождается уже из producer path, а не из исходного LLM text. Это полностью соответствует замыслу плана. fileciteturn29file0L3-L3 fileciteturn26file0L3-L3

**`llm_critic`** — это критик omissions, contradictions, risk gaps и stakeholder/method gaps. Его output может поднимать review tasks и candidate blockers, но не должен финализировать blocker severity или publishability. Severity, readiness impact и blocking status должны определяться детерминированной логикой или human adjudication поверх rubric. Это нужно и потому, что план требует использовать deterministic `ConstraintCritic` как baseline coverage, и потому, что LLM judges известны своими bias modes даже при неплохом среднем agreement с людьми. fileciteturn26file0L3-L3 fileciteturn10file0L3-L3 citeturn13academia0

**`llm_drafter`** — это bounded prose layer поверх уже authority-bearing artifacts. Он имеет право только на переформулирование, сжатие, аудиторию и стиль, но не на изменение claim set, readiness, harm profile, binding constraints или source attribution. Любой drift должен блокироваться детерминированным compliance pass; для public factual/legal surfaces дополнительно обязателен citation faithfulness gate. Именно так уже устроен translator path и publishing path, и это нужно сохранить как жесткое правило. fileciteturn31file0L3-L3 fileciteturn20file0L3-L3 fileciteturn22file0L3-L3

Из этого следует ключевой ADR-level invariant: **LLM output may influence work selection, not truth status**. То есть модель может влиять на то, что система проверит, о чем спросит reviewer, какие probes запустит, какие limitations сформулирует и какие rejected alternatives нужно рассмотреть. Но она не должна влиять на то, что система считает истинным, законным, допустимым, доказанным или ready-for-closeout без producer validation. Это лучшая формулировка “candidate-to-authority firewall” для PolicyOS. fileciteturn26file0L3-L3 fileciteturn24file0L3-L3

## Протокол оценки для C12

Оценка должна быть не общей “quality benchmark”, а controlled boundary benchmark. Я рекомендую строить ее на двух исходных корпусных срезах, которые уже заданы в плане: deep pilot из 10 дел и admissibility pair set из 30–50 cases с 20–40 claim-evidence pairs на кейс. Для C12 этого достаточно, если аннотация будет не только semantic, но и authority-aware. На каждый case нужно размечать gold obligation set, gold critical blockers, gold limitations, допустимые source classes, запрещенные authority transitions, severity labels и список “laundering traps”, то есть мест, где модель соблазнительно может выдумать law, data, stakeholder preference, method support или final readiness language. fileciteturn28file0L3-L3

Сравнивать нужно не один pipeline, а набор controlled variants. Минимально нужны: deterministic baseline без LLM; deterministic baseline плюс `llm_candidate` formulator; deterministic baseline плюс `llm_critic`; combined formulator+critic; `llm_drafter` поверх authoritative dossier; existing adversary worker; а также anti-pattern variants, где authority guard intentionally weakened для проверки laundering probes. Важная code-grounded деталь: current repo уже имеет bounded adversary и bounded drafter, но полноценный first-class LLM formulator для policy obligations выражен лишь частично; поэтому в benchmark надо честно признавать, что “formulator” сейчас является исследовательским вариантом, а не зрелой baseline capability. fileciteturn11file0L3-L3 fileciteturn31file0L3-L3 fileciteturn33file0L3-L3

Ключевые метрики должны быть следующими. **Omission rate** — доля missed obligations/risk facets относительно gold set, отдельно для critical items. **False-positive burden** — сколько лишних obligations, blockers и reviews создает модель. **Hallucinated authority rate** — доля outputs, где модель invents law/data/method/stakeholder or closeout authority. **Authority-laundering pass-through** — доля LLM-originated items, которые по ошибке дошли до claim ledger, scorecard, approval или public export без producer validation. **Severity calibration** — согласование severity class с human gold, лучше измерять по weighted kappa или ECE-like calibration на blocked/high/medium/low. **Draft faithfulness** — частота `TranslatorCompliancePass` failures и citation-faithfulness failures на public factual/legal claims. **Deterministic coverage preservation** — самый важный non-negotiable indicator: LLM-enhanced pipeline не имеет права терять deterministic baseline findings; если `ConstraintCritic` или citation/claim validators что-то нашли, LLM layer может только сохранить или расширить покрытие, но не “отменить” его своей риторикой. fileciteturn10file0L3-L3 fileciteturn31file0L3-L3 fileciteturn20file0L3-L3

Метод оценки должен быть human-led. NIST прямо акцентирует необходимость defined human roles и исследования того, как люди challenge AI output, а MT-Bench показывает, что LLM judges полезны, но имеют системные biases. Поэтому я бы разрешил LLM judge только как вспомогательный rater для triage и rubric pre-scoring; финальный gold label должен ставиться людьми, лучше с blinded adjudication и order-swapped presentation там, где используется pairwise judging. citeturn8view3turn13academia0

Для acceptance C12 я бы рекомендовал жесткие пороги. Во-первых, **authority-laundering pass-through должен быть нулевым** — не “низким”, а нулевым, потому что это архитектурный invariant, а не quality metric. Во-вторых, **deterministic baseline preservation должен быть полным**: ни один deterministic blocker, citation failure или claim-support failure не должен теряться из-за LLM layer. В-третьих, adoption LLM formulator/critic оправдан только если он поднимает critical-recall над deterministic baseline без непропорционального роста false-positive burden; если прибавка recall мала, а review burden велик, LLM остается optional assistive layer. В-четвертых, `llm_drafter` должен считаться успешным только если он не создает readiness overstatement, harm omission и citation drift beyond a very low tolerated error rate. Эти пороги логически следуют и из плана C12, и из существующих publishing/claim/authority gates. fileciteturn26file0L3-L3 fileciteturn16file0L3-L3 fileciteturn20file0L3-L3 fileciteturn22file0L3-L3

## Рекомендуемое ADR решение

Рекомендуемое архитектурное решение формулируется так: **в PolicyOS все LLM outputs являются speculation-class artifacts до тех пор, пока runtime-owned producer path не преобразует их в validated artifacts с refs, envelopes и handoffs**. Это и есть speculation firewall.

Из этого решения следуют обязательные правила. Каждый LLM artifact должен сохраняться с явными `source_class`, `model_variant_id`, `prompt_fingerprint`, `response_hash`, `parser_contract_ref` и флагом `may_mint_authority = false`. Любой переход из `llm_*` в authority-bearing artifact должен требовать `producer_validation_ref`, `authority_handoff_ref`, `same_input_closure`, `validator_pass_ref` и, где применимо, claim-ledger binding. Нельзя позволять LLM напрямую писать `norm_ref`, `data_ref`, `method_ref`, `source_attribution`, `DecisionReadinessContract`, `phase3_gate`, `approval_input` или `runtime_blocker`. LLM critic может предлагать severity, но final severity должен вычисляться детерминированной mapping function или human review. LLM drafter может только переформулировать already-authoritative content и никогда не должен расширять claim inventory. Public projection должен оставаться `projection_only`, а decision-grade export — derivation only from claim ledger and research DAG. fileciteturn18file0L3-L3 fileciteturn23file0L3-L3 fileciteturn22file0L3-L3 fileciteturn24file0L3-L3

Практически это также означает два немедленных code-facing исправления. Во-первых, helper, автоматически присваивающий broad authority scopes runtime model summaries, нужно сузить или обернуть в отдельный non-authoritative source class для `llm_candidate`/`llm_drafter` flows. Во-вторых, метки вроде `hybrid_seed_llm_assisted` должны использоваться только если реально существует prompt/run/output trace; иначе они должны быть переименованы в нейтральное provenance label. Эти два изменения напрямую уменьшают риск не factual hallucination, а **hallucinated authority** — именно то, что C12 должен исключить. fileciteturn18file0L3-L3 fileciteturn33file0L3-L3

## Открытые вопросы и ограничения

Я не проверял весь тестовый слой и историю issues/PR вокруг этих модулей, поэтому некоторые рекомендации выше — это code-grounded architectural inference, а не подтвержденный maintainer intent. Самый важный потенциальный пробел: отдельного зрелого “LLM policy formulator” в просмотренных файлах я не увидел; в текущем состоянии repo сильнее всего представлены bounded adversary и bounded drafter, а значит часть C12 по formulator variants еще действительно исследовательская, а не только интеграционная. Тем не менее этого уже достаточно, чтобы принять главный design decision: **LLM в PolicyOS должен быть только кандидатом, критиком или драфтером, но не authority minting component**. fileciteturn11file0L3-L3 fileciteturn31file0L3-L3 fileciteturn33file0L3-L3

# C15 для PolicyOS: семантика argument, warrant и assurance profile

## Рамка задачи

Активный план по исследованию прямо формулирует C15 так: принять текущую multi-formalism mapping из `assurance_case.py` как baseline, проверить её полноту относительно SACM, GSN и CAE, формализовать warrant не как свободный текст, а как типизированную семантику, определить минимальную форму графа аргумента для major claims и закрыть exporter gaps; критерий приёмки сформулирован жёстко — каждый major claim должен представляться как `claim -> argument -> warrant -> evidence -> authority -> readiness`, а если это невозможно, система должна падать с типизированным gap. fileciteturn31file0L3-L3

Это исследование нельзя вести “с нуля”, и сам репозиторий уже запрещает такой подход. ADR-0156 закрепляет, что Policy Design Case — это не параллельный объект рядом с runtime-quality substrate, а именно runtime quality assurance-case profile, который должен жить поверх `src/polisyos/runtime/quality`; при этом структура assurance case должна сохранять отдельные inspectable surfaces для claim, subclaim, argument, warrant, context, assumption, evidence, rebuttal, counter-evidence, assurance deficit и residual uncertainty. ADR-0161 ещё сильнее сужает свободу реализации: serious major claim не должен существовать без explicit argument и warrant, rebuttal/counter-evidence/deficit должны быть first-class records, а BERL reliability обязателен, когда explanation влияет на reviewer trust, automated acceptance или user-facing confidence. fileciteturn29file0L3-L3 fileciteturn28file0L3-L3

Отсюда следует важный методологический вывод: задача C15 для PolicyOS — не “изобрести новую нотацию”, а собрать уже существующие в репозитории поверхности в более строгий и экспортируемый argument profile. Это особенно важно потому, что в коде уже есть fail-closed интуиция: major claim surfaces валидируются, BERL reliability проверяется, portfolio design должен быть predeclared, а readiness и authority уже существуют как отдельные runtime-quality артефакты. Проблема не в полном отсутствии модели; проблема в том, что модель сейчас распределена по нескольким модулям и не сведена в один семантически жёсткий граф. fileciteturn17file0L3-L3 fileciteturn20file0L3-L3 fileciteturn27file0L3-L3 fileciteturn15file0L3-L3

## Нынешний baseline в репозитории

На уровне profile ядро уже есть в `assurance_case.py`. Модуль фиксирует core node types для Policy Design Case: `policy_intent`, `capability_duty`, `concept_spine`, `jurisdiction_spine`, `producer_evidence`, `portfolio`, `claim`, `argument`, `warrant`, `rebuttal`, `counter_evidence` и `deficit`. Там же зафиксирована `POLICY_DESIGN_CASE_NODE_MAPPING`, где `claim` сопоставляется с `SACM.claim`, `argument` — с `SACM.argument_reasoning`, `producer_evidence` — с `SACM.artifact_reference`, `portfolio` — с `CAE.evidence_set`, `warrant` — с `CAE.warrant`, `rebuttal` — с `CAE.rebuttal`, `counter_evidence` — с `CAE.defeater`, а `deficit` — с `SACM.assurance_deficit`. Профиль одновременно задаёт authority chain через `runtime_quality_owner`, `runtime_event_ref`, `cas_ref`, `same_input_closure_ref`, `effective_mode_ref`, `schema_compatibility_ref` и `tenant_id`, а для concept spine уже требует closure по `metric_bindings`, `dataset_column_bindings`, `legal_concept_bindings`, `method_requirement_bindings`, `objective_tradeoff_bindings`, `geography`, `population`, `time`, `units`, `currency`, `price_bases`, `exchange_rates`, `inflation_adjustments`, `calendars` и `freshness`. Это очень сильная база для typed applicability semantics; она уже существует в substrate, но пока не поднята в warrant как полноценный semantic object. fileciteturn12file0L3-L3

На уровне major-claim validation база ещё конкретнее в `claim_argument.py`. Модуль задаёт явную `CLAIM_ARGUMENT_NODE_MAPPING`: `claim -> SACM.claim / CAE.claim / GSN.goal`, `argument -> SACM.argument_reasoning / CAE.argument / GSN.strategy`, `warrant -> SACM.asserted_inference / CAE.warrant / GSN.justification`, `rebuttal -> SACM.defeated_claim / CAE.rebuttal / GSN.away_goal`, `counter_evidence -> SACM.artifact_reference / CAE.defeater / GSN.context`, `deficit -> SACM.assurance_deficit / CAE.assumption_or_gap / GSN.assumption`, `requester_capture_challenge -> SACM.context / CAE.challenge / GSN.context`, `blocker -> SACM.assurance_deficit / CAE.blocker / GSN.undeveloped`. Валидатор требует для каждого major claim наличие surface-ов `argument`, `warrant`, `rebuttal`, `counter_evidence`, `deficit` и `requester_capture_challenge`; кроме того, `blocker_refs` обязаны быть представлены даже если список пустой. Для warrant-а он уже проверяет наличие собственно warrant text, assumptions, applicability limits и, при определённых trust-affecting флагах, BERL reliability refs. Видимое скрытие counter-evidence считается ошибкой. Это не заготовка; это уже почти строгая argument policy. fileciteturn17file0L3-L3 fileciteturn18file0L3-L3 fileciteturn19file0L3-L3

Тесты подтверждают, что эта строгая позиция не декларативна. Unit-тесты доказывают, что major claim export реально проектируется в SACM/CAE/GSN mapping, что deficits транслируются как semantic limitations, что semantic closure codes для missing argument/warrant/rebuttal/counter-evidence/limitation действительно эмитятся, а requester-capture challenge ломает валидацию, если подтверждает prior без независимых альтернатив или не несёт обязательных Scientist refs. Отдельные тесты по BERL показывают, что warrant, влияющий на reviewer trust или acceptance, не может пройти без BERL refs; что BERL record должен разрешиться в реальную reliability запись; и что запись должна содержать bundle ref, threshold decision, empirical reliability bounds и local infidelity diagnostics. fileciteturn24file0L3-L3 fileciteturn25file0L3-L3 fileciteturn26file0L3-L3

Наконец, текущий baseline уже связывает аргументы с evidence portfolio, semantic binding, authority и readiness, но делает это распределённо. `evidence_portfolio.py` требует predeclared portfolio design до producer execution, с claim binding, strands, inclusion/exclusion rules, disconfirming lines, synthesis rules, stopping rules и cost proportionality. ADR-0160 закрепляет, что major empirical claim должен опираться на predeclared evidence portfolio per evidence strand и что evidence strength измеряется через effective independence, а не raw line count. `explanation_reliability.py` мостиком привязывает warrant к BERL bundle, threshold decision, empirical bounds и local infidelity diagnostics. А `assurance_case.py` через case registry entry уже соединяет case с `readiness_check`, `scorecard_gate` и `enforcement_function`, что по существу и есть readiness surface. fileciteturn27file0L3-L3 fileciteturn33file0L3-L3 fileciteturn20file0L3-L3 fileciteturn15file0L3-L3 fileciteturn16file0L3-L3

## Полнота относительно SACM

С внешней точки зрения именно SACM должен быть главным референсом для C15. OMG определяет SACM как metamodel для представления structured assurance cases и публикует не только normative PDF, но и normative machine-readable EMOF XML. В самом стандарте явно разделены compliance points для Argumentation Model, Artifact Model, Assurance Case Model и Terminology Model. Кроме того, авторы статьи 2019 года — участники спецификационного процесса SACM — пишут, что SACM богаче существующих assurance notations и что они предоставили SACM-compliant metamodels и transformations для GSN и CAE. Для PolicyOS это фактически означает: если нужен один canonical interchange target, то им должен быть SACM, а GSN/CAE должны оставаться view-слоями или derived exports. citeturn6view0turn18view0turn15view0turn17view0

Если мерить текущий PolicyOS against SACM, картина получается смешанной. Покрытие core argumentative surface уже хорошее: есть Claim, есть ArgumentReasoning, есть ArtifactReference-подобные surfaces для producer evidence, есть де-факто обстоятельства для evidence/context/deficit, есть distinction между rebuttal, counter-evidence и blocker, а warranty reasoning уже близко к SACM’s `AssertedInference`. Более того, OMG SACM explicitly differentiates `ArgumentReasoning`, `Claim`, `AssertedEvidence`, `AssertedContext` и `AssertedArtifactSupport`; это хорошо совпадает с архитектурным направлением PolicyOS, где concept spine, jurisdiction spine, producer evidence и portfolio уже выделены как разные сущности. citeturn19view3turn19view2turn20view0turn20view1turn20view2 fileciteturn12file0L3-L3

Но против SACM есть и заметные недостачи. Сам стандарт содержит не только argument assets, но и package/interface/binding concepts, полноценную terminology layer, а также богатую семантику asserted relationships: для inference, evidence, context и artifact support предусмотрены variants вроде `assumed`, `needsSupport`, `axiomatic`, `defeated`, `asCited` и `isCounter`. В PolicyOS сейчас есть функциональные аналоги части этих состояний — accepted deficits, blockers, hidden counter-evidence failures, challenge failures, BERL threshold failures, explicit empty blocker surfaces, — но нет единой typed relationship model, которая бы экспортировала эти distinctions как SACM-native relationship states. Иначе говоря: семантика у системы уже во многом есть, но она encoded as validation logic and issue codes, а не как first-class relational model. citeturn18view0turn19view1turn20view0turn20view1turn20view2 fileciteturn18file0L3-L3 fileciteturn19file0L3-L3 fileciteturn26file0L3-L3

Есть и внутренняя несогласованность baseline. В `assurance_case.py` warrant на profile level сопоставляется прежде всего с `CAE.warrant`, тогда как в `claim_argument.py` тот же warrant уже сопоставляется с `SACM.asserted_inference`, `CAE.warrant` и `GSN.justification`. Это не фатальная ошибка, но это признак того, что today’s “mapping baseline” на самом деле split across modules and scopes. Для C15 это важный сигнал: нужен один normatively preferred semantic interpretation of warrant, а не две соседние, обе “примерно правильные”. Наилучшее решение здесь — считать canonical internal meaning warrant-а именно typed inference license, а CAE/GSN interpretations уже выводить из неё как projections. Это вывод, но он прямо следует из того, что SACM distinguishes reasoning/inference relationships explicitly, а внутрирепозитарный claim-argument exporter уже движется именно в эту сторону. fileciteturn12file0L3-L3 fileciteturn17file0L3-L3 citeturn19view1turn19view3

## Полнота относительно GSN и CAE

С GSN и CAE ситуация иная. Внешне PolicyOS уже умеет говорить на их языке: экспорт major claim mapping отдает `goal`, `strategy`, `justification`, `away_goal`, `context`, `assumption` и `undeveloped` для GSN, а также `claim`, `argument`, `warrant`, `rebuttal`, `counter_evidence`, `assurance_deficit`, `challenge` и `blocker` для CAE. Это полезный и практичный baseline. Он не придуман произвольно: статья Wei, Kelly и соавторов прямо говорит о SACM-compliant metamodels and transformations for GSN and CAE, а свежая работа OntoGSN заявляет 1:1 formalization of GSN Community Standard v3. Отдельно недавняя safety-case работа по frontier AI использует CAE именно как framework для явного связывания main claim, sub-claims и evidence. fileciteturn19file0L3-L3 citeturn17view0turn22academia3turn24view0

Но если смотреть не на наличие словаря, а на preserving semantics, нынешний crosswalk пока грубоват. Самый заметный пример — `counter_evidence` и `requester_capture_challenge` в GSN-проекции оба схлопываются в `context`. Для внутренней диагностики это ещё терпимо, потому что валидатор отдельно проверяет видимость counter-evidence и жёстко валит requester-capture challenge при неправильной независимости. Но для standards-grade presentation это уже потеря смысла: контекст, опровержение и challenge — это разные argumentative roles, а не одна и та же “рамка”. Аналогично, CAE-проекция несёт ссылки на warrant и challenge, но не делает их typed semantic objects сама по себе; вся жёсткая логика по assumptions, applicability limits и BERL находится outside exporter, в validation layer. Это означает, что текущие GSN/CAE exports полезны как human-readable views, но ещё не дотягивают до полноценного interchange artifact. fileciteturn18file0L3-L3 fileciteturn19file0L3-L3 fileciteturn24file0L3-L3

Поэтому мой исследовательский вывод здесь такой: относительно GSN и CAE PolicyOS уже покрывает минимальный surface vocabulary, но не покрывает semantics-preserving structure. Для C15 это значит, что “validate completeness” не должно закончиться фразой “у нас есть mapping dictionary”. Оно должно закончиться criterion-based distinction: что repo already encodes as typed graph semantics, что пока encoded only as validation rules, и что пока есть only as display projection. Именно это разделение и нужно записать в будущий ADR. fileciteturn17file0L3-L3 fileciteturn19file0L3-L3

## Рекомендуемая семантика warrant

В текущем репозитории warrant уже обязан содержать не только текст, но и assumptions, applicability limits и, при нужных trust-affecting flags, BERL reliability refs; concept spine и semantic binding уже умеют нести geography/time/unit/currency/freshness semantics; BERL explanation bundle уже несёт assumptions, validity reports, disagreement, audit trail и explicit bounded infidelity/stability structure. Следовательно, C15 должен сделать следующий шаг: признать warrant не “текстовым объяснением рядом с claim”, а first-class typed license, который объясняет, почему именно этот argument pattern поднимает именно этот claim из именно этих evidence surfaces в именно этом scope и при именно таком confidence envelope. fileciteturn18file0L3-L3 fileciteturn20file0L3-L3 fileciteturn21file0L3-L3 fileciteturn22file0L3-L3

Практически это означает шесть обязательных блоков внутри warrant model.

Во-первых, **role block**: `warrant_id`, `claim_id`, `argument_ref`, `warrant_kind`, где `warrant_kind` должен быть не свободным текстом, а хотя бы перечислением вроде `causal`, `legal`, `measurement`, `portfolio_synthesis`, `counterfactual_transport`, `explanation_reliability`, `implementation_feasibility`, `authority_promotion`. Это снимет сегодняшнюю двусмысленность между “warrant как CAE.warrant” и “warrant как asserted inference”.

Во-вторых, **typed assumptions block**: assumptions должны быть отдельными typed items, а не только строками. Минимальный состав типов, который уже хорошо поддерживается существующей архитектурой, выглядит так: `statistical_assumption`, `identification_assumption`, `semantic_binding_assumption`, `jurisdiction_assumption`, `temporal_scope_assumption`, `measurement_assumption`, `portfolio_independence_assumption`, `explanation_reliability_assumption`, `implementation_assumption`. У каждой assumption должен быть machine-checkable predicate, привязка к evidence или semantic-binding refs, severity when violated и статус: `holds`, `contested`, `unknown`, `accepted_deficit`, `blocked`. Такая типизация естественно вырастает из сегодняшних warrant assumptions, concept spine closure fields, portfolio rules и BERL validity surfaces. fileciteturn18file0L3-L3 fileciteturn12file0L3-L3 fileciteturn27file0L3-L3 fileciteturn21file0L3-L3

В-третьих, **applicability block**: вместо сегодняшнего текстового `applicability_limits` нужен typed applicability predicate. Он должен опираться на уже существующие backbone semantics репозитория и явно перечислять как минимум `canonical_concept_refs`, `jurisdiction_refs`, `population`, `time`, `units`, `currency`, `price_base`, `exchange_rate regime`, `freshness`, `method_family`, `authority_profile`. Тогда warrant сможет говорить не только “не экстраполировать вне observed support”, но и “действует только для этих concept/jurisdiction/time/method bindings”. Это очень важно именно для PolicyOS, потому что substrate already tracks these dimensions; C15 должен просто поднять их в level of argument semantics. fileciteturn12file0L3-L3 fileciteturn22file0L3-L3

В-четвёртых, **confidence and reliability block**: warrant должен ссылаться не только на evidence refs, но и на `portfolio_ref`, `independence_ref`, `synthesis_ref`, `uncertainty_ref`, `sensitivity_ref`, а для explanation-shaped warrants — на `berl_reliability_refs`. Сам `confidence` должен быть объяснимым и compositional: от какого evidence portfolio он растёт, от каких deficits и conflicts он падает, и какие BERL thresholds ограничивают использование explanation bundle. Сейчас эти pieces already exist, но в разных модулях. C15 должен превратить их в one warrant-level bundle of confidence semantics. fileciteturn20file0L3-L3 fileciteturn21file0L3-L3 fileciteturn27file0L3-L3 fileciteturn33file0L3-L3

В-пятых, **defeatability block**: warrant должен не просто “иметь rebuttal refs”, а explicitly namespaced defeat surfaces: `rebuttal_refs`, `counter_evidence_refs`, `requester_capture_challenge_refs`, `deficit_refs`, `blocker_refs`, `disagreement_refs`. Это важно потому, что в репозитории уже есть fail-closed rules для скрытого counter-evidence, challenge failure и visible deficits; C15 должен сделать поражаемость аргумента семантической частью warrant-а, а не только серией локальных валидаторов. fileciteturn18file0L3-L3 fileciteturn24file0L3-L3 fileciteturn26file0L3-L3

В-шестых, **promotion block**: warrant должен explicitly указывать, при какой authority/readiness конфигурации claim может быть promoted из research в governed/production. Сейчас authority chain и readiness surfaces живут на уровне case profile и scorecard linkage; именно это делает критерий приёмки C15 пока не до конца выполненным. Чтобы замкнуть цепочку `warrant -> evidence -> authority -> readiness`, warrant или claim-summary должен уметь ссылаться на `authority_refs` и `readiness_refs` как на first-class graph targets. fileciteturn16file0L3-L3 fileciteturn15file0L3-L3

## Минимальный граф и типизированные разрывы

Для major claim я бы рекомендовал зафиксировать следующий minimum graph shape как нормативное ядро C15:

**claim**  
→ **argument** с обязательным `strategy`  
→ **warrant** с typed assumptions, applicability predicate и confidence/reliability refs  
→ **evidence surface** как минимум через portfolio/evidence-line refs  
→ **authority surface** через runtime-owned refs  
→ **readiness surface** через readiness/scorecard/enforcement linkage. fileciteturn28file0L3-L3 fileciteturn27file0L3-L3 fileciteturn15file0L3-L3 fileciteturn16file0L3-L3

Но у этого linear chain должны быть обязательные боковые ветви. Для serious claim недостаточно одной “основной стрелки”. Mandatory side surfaces — это `rebuttal`, `counter_evidence`, `deficit`, `blocker` и, в policy-design context, `requester_capture_challenge`. ADR-0161 уже по сути требует именно этого: scorecard/readiness gates должны fail-ить, если у claim есть evidence refs, но нет argument, warrant, rebuttal/counter-evidence assessment, accepted assurance deficit или required BERL reliability evidence. Evidence portfolio ADR добавляет ещё одно ограничение: для major empirical claim должен существовать predeclared portfolio, если профиль не разрешает explicit single-line-evidence deficit. fileciteturn28file0L3-L3 fileciteturn33file0L3-L3

В PolicyOS уже используется правильный fail-closed idiom через issue codes. Поэтому C15 логично завершать не просто “схемой”, а typed gap taxonomy. Минимальный набор gap-кодов, который я бы рекомендовал зафиксировать в ADR, выглядит так: `missing_argument`, `missing_argument_strategy`, `missing_warrant`, `missing_typed_assumptions`, `missing_applicability_predicate`, `missing_confidence_refs`, `missing_berl_reliability`, `missing_counter_evidence_surface`, `hidden_counter_evidence`, `missing_requester_capture_challenge`, `missing_portfolio_design`, `missing_authority_link`, `missing_readiness_link`, `mapping_loss_on_export`. Половина этой логики уже существует в текущем коде и тестах; вторая половина — естественное продолжение принятого fail-closed style. fileciteturn18file0L3-L3 fileciteturn24file0L3-L3 fileciteturn26file0L3-L3

Из этого следует и точный вердикт по acceptance criterion C15. Внутри репозитория уже можно восстановить цепочку `claim -> argument -> warrant -> evidence`, а также отдельно найти `authority` и `readiness`. Но сегодня это ещё не **один** explicit typed graph; это **связка модулей**, которые вместе образуют такую цепочку. Следовательно, C15 ещё не закрыт в строгом смысле. Он близок к закрытию архитектурно, но не завершён семантически. fileciteturn12file0L3-L3 fileciteturn17file0L3-L3 fileciteturn20file0L3-L3 fileciteturn27file0L3-L3 fileciteturn15file0L3-L3

## Экспорт, interchange и итоговая оценка

Текущий exporter в `claim_argument.py` делает полезную, но ограниченную работу: он отдаёт JSON payload с `schema_version`, `contract_id`, списком standards, `node_mapping`, summary, issues и пер-major-claim projection в `sacm`, `cae` и `gsn`. Это хороший internal/export view, но это ещё не полноценный interchange artifact в смысле внешней tool-chain совместимости. Я не нашёл в выбранном репозитории существующего SACM XML/XMI exporter или другого сопоставимого machine-readable interchange output; найден именно JSON crosswalk, а не standards-grade serialization. fileciteturn19file0L3-L3

Если C15 должен действительно закрыть exporter gaps, наилучший следующий шаг — добавить **SACM-first exporter**. Это соответствует и OMG-реальности: SACM публикуется как formal specification с machine-readable EMOF XML, а значит, для interchange есть смысл ориентироваться либо на SACM-aligned XMI/XML, либо на строго документированный derived artifact, например JSON-LD/SACM profile, который однозначно восстанавливает packages, argument assets, asserted relationships, artifact refs и terminology links. CAE и GSN при этом лучше оставить как secondary projections, потому что внешний же авторский SACM paper рассматривает их именно как подходы, которые можно трансформировать в SACM, а не наоборот. citeturn6view0turn18view0turn15view0turn17view0

Итогово моя оценка такая. PolicyOS уже имеет unusually strong substrate для C15: он не только говорит словами “claim-argument-evidence”, но и реально валидирует major-claim surfaces, заставляет warrants иметь assumptions и applicability limits, подключает BERL reliability, требует predeclared evidence portfolio, держит runtime authority chain и соединяет case с readiness/scorecard gates. Это очень высокий baseline. Но именно поэтому remaining gap хорошо виден: repository still lacks one explicit typed argument profile that unifies these pieces into a single graph semantics and exports it losslessly. Другими словами, PolicyOS уже почти находится в состоянии “argument-quality system”, но ещё не в состоянии “argument-interchange system”. C15 должен закрыть именно этот разрыв — через canonical warrant semantics, minimum graph contract и SACM-first exporter. fileciteturn29file0L3-L3 fileciteturn28file0L3-L3 fileciteturn17file0L3-L3 fileciteturn20file0L3-L3 fileciteturn27file0L3-L3 fileciteturn15file0L3-L3 citeturn18view0turn19view1turn19view3turn22academia3turn24view0

# C22 Evidence Acquisition Decision Theory And VOI

## Рамка задачи и главный вывод

План `POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md` для C22 требует не просто фиксировать отсутствие доказательств, а выдавать **явное следующее действие**: блокировать, деградировать, доисследовать, принять дефицит, перезапустить или публиковать с ограничением. Важно, что это должно делаться **не как оркестрация acquisition-пайплайна**, а как **VOI-ранжирование и аудируемый decision ledger**. Это прямо согласуется с уже существующей поверхностью Scientist: `VOIDecisionRecord`, `VOIRunReport`, калибровочные проверки, обязательные gate-ограничения и fail-closed-поведение для серьёзных профилей. fileciteturn5file0 fileciteturn12file0 fileciteturn15file0 fileciteturn14file0

Текущее ядро репозитория уже задаёт почти всю нужную философию. `SimpleVOIScheduler` и `PredictiveVOIScheduler` оперируют не командой “сходи и добудь данные”, а объяснимым выбором действия на основе ожидаемой пользы, falsification value, governance value, риска таймаута, стоимости повтора и calibration debt. Отдельно `VOIDecisionRecord` уже запрещает “позитивное продвижение” при отрицательной ожидаемой ценности и не даёт VOI обходить обязательные gates. В справке по VOI это сформулировано ещё жёстче: VOI может рекомендовать candidate evaluation, source verification, human escalation, adversarial challenge и stop-search, но **не может отменять обязательные evidence/release gates**. fileciteturn10file0 fileciteturn11file0 fileciteturn12file0 fileciteturn15file0

С точки зрения decision theory это правильно. В литературе VOI/EVSI трактуется как ожидаемая выгода от снижения неопределённости перед решением, а разные исследования/источники сравниваются по ожидаемой полезности с учётом стоимости и вычислительной цены. Современные EVSI-подходы именно для этого и используются: сравнить варианты дополнительного сбора информации и выбрать тот, который даёт наибольшую ожидаемую ценность за ограниченный бюджет. citeturn10academia1turn10academia4turn11academia4

Из этого следует ключевое проектное решение для PolicyOS: **VOI должен ранжировать безопасные следующие шаги и фиксировать объяснение, а выполнять эти шаги должны другие подсистемы**. Иначе VOI станет непрозрачным состоянием оркестрации вместо проверяемого decision ledger. fileciteturn15file0 fileciteturn12file0

## Что уже требует кодовая база PolicyOS

Внутренние инварианты уже хорошо описывают, как должен выглядеть C22.

Во-первых, у Fabric `SourceContract` уже есть нужные для acquisition-политики оси: trust tier, calibration status, quality contract, replay evidence, lineage seed, field-level access policy, classification, PII tier, tenant scope, SLA, terms и retention. Для активного источника требуются schema evidence, quality ref, replay evidence, lineage seed и корректная field-policy coverage. Это значит, что для PolicyOS “авторитет” источника — не риторическая оценка, а конкретный набор контрактных свойств. fileciteturn17file0 fileciteturn18file0

Во-вторых, модуль деградации уже задаёт правильный closeout-стандарт. Для authority-bearing outputs в serious profiles fallback по умолчанию fail-closed; разрешения возможны только вне серьёзного профиля или по явно разрешённой политике/подписанному исключению. Главное для C22: деградационный blocker уже несёт машинно-исполняемое поле `next_action`, а `degradation_gate_from_payloads` умеет превращать это в blocking gate, а не просто в абстрактный “failed”. Это практически готовый образец для blocker-выхода задачи C22. fileciteturn20file0 fileciteturn21file0 fileciteturn39file0

В-третьих, performance budget уже использует тот же шаблон: каждая over-budget ситуация получает `retryable`/`retryability`, `production_blocking` и человекочитаемый `next_action`. Для C22 это означает, что “rerun” должен быть первоклассным outcome, если проблема носит транзиентный или технико-производственный характер, а не подменяться общим статусом ошибки. fileciteturn19file0

В-четвёртых, Lex и Scholar уже различают разные режимы evidence acquisition. Lex `applicability_report` требует полноценный trace нулевого результата: normalized terms, bilingual trace, KG paths, language coverage и typed blocker, прежде чем zero candidate norms станет “осмысленным нулём”. Scholar search, в свою очередь, уже фиксирует search budgets, allowed/blocked domains, recency, content-type ограничения, source quality signals, anti-SEO penalties, duplicate detection и snippet-level evidence links. То есть юридическое расширение корпуса и академический поиск уже имеют естественные места в acquisition taxonomy. fileciteturn29file0 fileciteturn24file0 fileciteturn25file0

Наконец, Data Forge и Foundry дают два разных production-grade канала для доказательств. Data Forge предоставляет governed artifact refs, snapshot transactions с merkle root и финализацию snapshot manifests; Foundry — вычислительный слой с compile/execute, привязкой snapshots, method catalog и calibration surfaces. Значит, “production snapshot build” и “foundry method run” — не эвристические обходы, а воспроизводимые, lineaged и policy-compatible acquisition-механизмы, если ими не пытаются закрывать те gaps, где требуется внешний authority source. fileciteturn32file0 fileciteturn33file0 fileciteturn34file0 fileciteturn35file0

## Таксономия стратегий приобретения доказательств

Ниже — предлагаемая C22-таксономия. Профили являются **архитектурным синтезом** на основе уже существующих контрактов PolicyOS и decision-theoretic VOI-логики; это не дословная текущая реализация всех стратегий в коде. fileciteturn5file0 fileciteturn15file0 citeturn10academia1turn10academia4

| Стратегия | Когда это лучший следующий шаг | Стоимость | Авторитет | Реализуемость | Время | Privacy / legal | Профиль деградации | Основание |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Общедоступный реестр | Нужен официальный факт, который уже должен быть опубликован или проактивно раскрыт | Низкая | Высокий | Высокая | Быстро | Низкий | Низкий | FOIA рекомендует сначала искать уже опубликованную информацию; Scholar и SourceContract поощряют правительственные/институциональные источники. citeturn6view1 fileciteturn25file0 fileciteturn17file0 |
| Запрос в ведомство | Нужны официальные записи, которых нет в открытом доступе, и они потенциально gate-clearing | Средняя–высокая | Очень высокий | Средняя | Медленно/неопределённо | Высокий | Низкий как источник; высокий как риск задержки | FOIA описывает формальный запросный путь, exemptions, вариативные сроки и отсутствие обязанности “создавать новые ответы/анализ”. citeturn6view1 |
| Опрос | Нужны предпочтения, распространённость, поведенческие или implementation signals, которых нет в логах/реестрах | Средняя–высокая | Средний | Средняя | Средне | Средний–высокий | Средний–высокий, особенно у non-probability design | AAPOR требует раскрывать дизайн выборки, способ рекрутинга, sample sizes, weighting и data-quality procedures; без этого authority быстро падает. citeturn7view0turn7view1turn7view5turn7view6 |
| Консультация | Нужны stakeholder feasibility, operational constraints, acceptability, legal interpretation support | Средняя | Средний для feasibility/acceptability, низкий для causal effect | Средняя | Средне | Средний | Средний: нельзя подменять ею factual authority | В PolicyOS это естественно ложится рядом с human escalation/oversight-rail: дополнительная ценность — в риско-снижении и governance value, а не в замене hard evidence. fileciteturn38file0 fileciteturn15file0 |
| Расширение юридического корпуса | Zero/weak candidate norms, неполный bilingual trace, mismatch по jurisdiction/as-of | Низкая–средняя | Высокий при нахождении релевантных норм | Средняя–высокая | Быстро–средне | Низкий | Низкий, если найден официальный normpack; высокий, если trace неполный | Lex applicability report требует typed blocker и полный trace для “осмысленного нуля”, что делает corpus expansion естественным первым ответом на missing legal evidence. fileciteturn29file0 |
| Академический поиск | Нужны causal studies, literature synthesis, external validation, estimates or mechanisms | Низкая–средняя | Средний–высокий | Высокая | Быстро | Низкий | Средний: проблемы paywall, lag, external validity | Scholar already models search constraints, source-quality scoring, anti-SEO filtering and snippet evidence; EVSI literature поддерживает выбор именно той дополнительной информации, которая меняет решение. fileciteturn24file0 fileciteturn25file0 citeturn10academia1turn10academia4 |
| Production snapshot build | Нужны воспроизводимые внутренние production facts, state snapshots, asset-group evidence | Средняя–высокая | Высокий для internal state, не для внешнего ground truth | Средняя | Средне | Средний | Низкий при корректных replay/lineage; высокий при попытке заменить внешний authority | Data Forge snapshots, merkle roots, governed artifact refs и manifest finalization дают правильную internal-evidence форму. fileciteturn32file0 fileciteturn33file0 fileciteturn34file0 |
| Proxy с пониженным авторитетом | Нужен временный ориентир для диагностики, triage или ranking, но не для serious closeout | Низкая | Низкий–условный | Высокая | Быстро | Низкий–средний | Очень высокий в serious profiles | Degradation module прямо блокирует authority-bearing fallback в serious profiles и требует typed blocker / next_action. fileciteturn20file0 fileciteturn21file0 fileciteturn39file0 |
| Accepted deficit | Дополнительный сбор информации не окупается или не успевает к дедлайну, а gap не является mandatory gate | Очень низкая | Не повышает | Высокая | Немедленно | Низкий | Средний: зависит от того, можно ли честно ограничить вывод | VOI surface уже поддерживает safe negative actions (`defer`, `reject`, `stop_search`), а справка требует честного shadow/stop behavior без обхода gates. fileciteturn12file0 fileciteturn15file0 |
| Rerun | Сбой retryable: transient data freshness, runtime budget, transport / snapshot assembly / timeout | Низкая–средняя | Не меняет природу authority, но может восстановить доступ | Высокая | Быстро–средне | Без изменений | Низкий, если это именно технический retriable fault | Performance budgets already label phases as retryable and attach specific next actions; degradation policies likewise point to diagnostic commands. fileciteturn19file0 fileciteturn21file0 |
| Closeout block | Не выполнен mandatory gate; допускается только fail-closed | Цена задержки высокая, но “стоимость” осознанно принимается | Максимальная integrity-защита | Всегда | Немедленно | Н/Д | Деградация недопустима | VOI cannot waive gates; calibration can block default enable; serious mode/fallback registry is explicitly fail-closed. fileciteturn12file0 fileciteturn14file0 fileciteturn15file0 fileciteturn39file0 |

Рабочее различие между тремя часто путаемыми исходами должно быть жёстким. **`accepted deficit`** — это внутреннее решение stop-search/defer, что новый acquisition сейчас не стоит затрат. **`publish with limitation`** — это внешний posture, допустимый только если remaining evidence уже поддерживает решение, а дефицит локализован и явно помечен в claim/evidence layer. **`closeout block`** — это fail-closed состояние, когда даже честное ограничение не спасает, потому что не закрыт mandatory gate. fileciteturn12file0 fileciteturn15file0 fileciteturn21file0

## Политика решений VOI для следующего действия

Предлагаемая C22-политика должна расширять текущий `ComputeEconomicsDecision`, а не заменять его. Сейчас scheduler уже учитывает `expected_improvement_per_usd`, `expected_falsification_value`, `expected_governance_value`, `timeout_risk`, `replay_cost_usd`, `estimated_cost_usd`, `predicted_disagreement` и `calibration_debt`. Для evidence acquisition достаточно добавить ещё четыре оси: **authority gain**, **latency cost**, **privacy/legal burden** и **degradation penalty**. Тогда VOI остаётся ранжировщиком, а не превращается в workflow-движок. fileciteturn10file0 fileciteturn11file0 fileciteturn17file0 fileciteturn20file0

Практическое правило ранжирования можно сформулировать так:

`net_voi(strategy) = decision_gain + falsification_value + governance_value + authority_gain - direct_cost - latency_penalty - privacy_legal_penalty - degradation_penalty - calibration_debt`

Это не абстрактная формула “из учебника”, а прямое обобщение уже существующей логики scheduler-а на missing/blocked evidence. Внешние исследования по EVSI поддерживают именно такую постановку: сравнивать альтернативные способы получения новой информации по ожидаемой выгоде для решения, а не по самой “интересности” информации. fileciteturn10file0 fileciteturn11file0 citeturn10academia1turn10academia4turn11academia4

Из этого следуют простые, но жёсткие rules of action.

**Блокировать** нужно в пяти случаях: когда есть mandatory gate; когда стратегия требует authority-bearing output, а доступен только degraded proxy; когда активный источник не проходит contract evidence по schema/quality/replay/lineage/field-access; когда calibration/regret evidence блокирует learned/default VOI; и когда serious profile сталкивается с запрещённым fallback. Эти правила уже буквально присутствуют в текущих SourceContract, VOI calibration и degradation rails. fileciteturn18file0 fileciteturn14file0 fileciteturn20file0 fileciteturn21file0 fileciteturn39file0

**Деградировать** допустимо только тогда, когда результат не authority-bearing, либо когда профиль явно разрешает снижение строгости и существует корректная exception-политика. Для serious/publication closeout деградация по умолчанию должна вести к block, а не к “best effort answer”. Это, пожалуй, самый важный guardrail всего C22. fileciteturn20file0 fileciteturn21file0 fileciteturn39file0

**Доисследовать / acquire** нужно, если стратегия одновременно: потенциально способна закрыть нужный gate по authority; укладывается в дедлайн лучше, чем альтернативы; имеет положительный net VOI; и не нарушает privacy/legal limits источника или метода. На практике это даёт понятный порядок перебора: сначала public registry, затем legal corpus expansion или academic retrieval, затем agency request / survey / consultation / production snapshot build — в зависимости от природы пробела. Такой порядок совместим и с FOIA-практикой “сначала ищи уже опубликованное”, и с design-еvidence из Lex/Scholar/Data Forge. citeturn6view1 fileciteturn29file0 fileciteturn24file0 fileciteturn25file0 fileciteturn32file0 fileciteturn33file0

**Принять дефицит** можно только если claim не является gate-critical, оставшееся evidence по-прежнему поддерживает решение, а limitation будет конкретной и проверяемой. Для survey/consultation pathways это особенно важно: AAPOR сама подчёркивает, что transparency standards нужны не для автоматического подтверждения качества, а для того, чтобы потребитель исследования вообще мог его оценить. Следовательно, плохо описанный survey не должен “полузасчитываться” как хорошее evidence; он должен либо понижать authority score, либо переводиться в accepted deficit / limitation. citeturn7view0turn7view1turn7view5turn7view6

**Перезапускать** нужно, когда проблема техническая, транзиентная и помечена как retryable: timeout, over-budget phase, неудачная сборка evidence пакета, runtime refresh, snapshot finalization или аналогичный operational fault. C22 должен иметь явный исход `rerun`, потому что по коду это уже не частный случай “ошибки”, а отдельная безопасная ветка с предписанным next action. fileciteturn19file0 fileciteturn21file0

**Публиковать с ограничением** можно только после `accepted deficit`, а не вместо него. То есть сначала система фиксирует, что дальнейший acquisition сейчас нерационален или неуспешен, затем отдельно решает, остаётся ли publishability при оставшемся evidence. Это важно, чтобы limitation не стала скрытым bypass-ом обязательных gates. fileciteturn12file0 fileciteturn15file0

## Как blocker должен выдавать явное следующее действие

Чтобы выполнить acceptance criterion C22, blocker должен стать не только статусом, но и **decision packet**. Лучшая уже существующая форма в коде — это комбинация `TypedBlocker` из деградации и `next_action` из degradation/performance modules. Для C22 стоит стандартизовать один и тот же минимум полей: `code`, `message`, `severity`, `blocking`, `may_satisfy_gate`, `next_action`, `recommended_strategy`, `fallback_strategies`, `deadline_class`, `authority_target`, `privacy_legal_class`. fileciteturn20file0 fileciteturn21file0 fileciteturn19file0

В терминах VOI-моделей это лучше всего хранить не через взрыв `VOIDecisionType`, а через `VOIDecisionRecord.metadata`. Базовый тип decisions можно оставить прежним — `source_verification`, `human_escalation`, `stop_search` и т.д. — а acquisition-стратегию кодировать метаданными, например: `acquisition_strategy=agency_request`, `reason=no_public_record`, `authority_target=official_record`, `publishability_if_failed=limitation_only`. Это позволит не ломать уже существующие safety validators, но даст C22 явный operational answer. fileciteturn12file0 fileciteturn15file0

Хороший blocker-output для C22 должен выглядеть концептуально так: “`lex_zero_candidate_query_trace_incomplete` → next_action=`expand_legal_corpus_and_emit_bilingual_query_trace`”, или “`degradation_fallback_not_allowed` → next_action=`run_public_registry_or_agency_request; do_not_publish`”, или “`budget_exhausted_for_next_level` → next_action=`rerun_cheaper_or_defer_until_budget_refresh`”. Именно этого требует и план, и текущая архитектура runtime quality. fileciteturn29file0 fileciteturn21file0 fileciteturn19file0

## Как результаты стратегий должны менять калибровку и будущие приоры

Predictive VOI уже умеет накапливать `VOIObservation`, `PromotionObservation`, `calibration_state`, статус моделей и routing modes вроде `conservative_routing` и `no_promotion`. Значит, C22 не нужно изобретать отдельную философию обучения; нужно лишь расширить её на acquisition outcomes. fileciteturn10file0 fileciteturn11file0

Для каждой попытки acquisition стоит логировать как минимум: выбранную стратегию, тип пробела, claim family, jurisdiction/domain, deadline class, expected authority, фактическую authority delta, успех/неуспех, время до usable evidence, прямые издержки, privacy/legal friction, привёл ли результат к изменению claim status, и сохранился ли publishability gap. Тогда future priors можно обновлять эмпирически: для feasibility — по success rate; для latency — по p50/p95 времени; для authority yield — по доле случаев, когда стратегия реально закрыла gate; для decision impact — по доле случаев, когда изменился outcome, а не просто увеличился объём материала. Это в точности соответствует духу текущего predictive scheduler-а: обучаться не на “красивых” фичах, а на последующем фактическом продвижении и стоимости. fileciteturn10file0 fileciteturn11file0

Особенно важно негативное обучение. Если agency requests в конкретной юрисдикции систематически не успевают к deadline, `time_penalty` и `feasibility prior` должны падать. Если legal corpus expansion часто снимает zero-candidate problem и закрывает gate дешево, её authority-adjusted prior должен расти. Если proxy degradation почти всегда блокируется в serious profiles, её ожидаемая ценность для этих профилей должна быстро уходить в отрицательную зону. И наоборот, если rerun часто чинит snapshot/performance failures без потери authority, rerun должен подниматься выше дорогих acquisition-веток. Это и есть практическая калибровка VOI как decision ledger, а не как статической эвристики. fileciteturn11file0 fileciteturn21file0 fileciteturn19file0

## Рекомендуемая policy формулировка для внедрения

В сжатом виде C22-политика для PolicyOS может быть записана так.

VOI формирует **набор безопасных кандидатов следующего действия**, а не запускает acquisition сам. Каждый кандидат получает оценку по ожидаемому решенческому выигрышу, риско-снижению, governance value, authority gain, стоимости, времени, privacy/legal burden, degradation risk и calibration debt. Кандидаты, нарушающие mandatory gates или fail-closed policy, отбрасываются до ранжирования. Лучший оставшийся кандидат становится `recommended_action`, а альтернативы — `fallback_strategies`. fileciteturn12file0 fileciteturn14file0 fileciteturn15file0 fileciteturn20file0

При missing evidence предпочтительный порядок действий должен быть таким: **public registry → legal corpus expansion / academic retrieval → production snapshot build / consultation / survey / agency request → accepted deficit or rerun → closeout block**. Но этот порядок — только prior, а не жёсткая лесенка: predictive VOI вправе поднимать выше медленную, но gate-clearing стратегию, если её authority sufficiently dominates дешёвые, но non-clearing альтернативы. citeturn6view1turn10academia1turn10academia4 fileciteturn29file0 fileciteturn24file0 fileciteturn32file0

Если в конце ранжирования не осталось положительной и безопасной acquisition-стратегии, система обязана вернуть **не пустой failure**, а один из явных safe outcomes: `accepted_deficit`, `rerun`, `publish_with_limitation` или `closeout_block`. Это и есть самая важная доработка относительно обычного “failed status”: blocker должен быть не тупиком, а объяснимой развилкой с конкретным next action. fileciteturn5file0 fileciteturn20file0 fileciteturn21file0 fileciteturn19file0

## Открытые вопросы и ограничения

Эта схема имеет высокий уровень уверенности по VOI, runtime quality, SourceContract, Lex, Scholar и Data Forge, потому что они были проверены по самому репозиторию. fileciteturn15file0 fileciteturn17file0 fileciteturn29file0 fileciteturn24file0 fileciteturn32file0

Остались, однако, три практических вопроса.

Во-первых, в отчёте я предлагаю кодировать acquisition taxonomy преимущественно в `metadata`, а не расширять `VOIDecisionType`; это архитектурно консервативно, но это всё же проектное предложение, а не уже существующий публичный контракт. fileciteturn12file0

Во-вторых, профили для **консультации** как evidence source опираются больше на общую VOI/oversight-логику, чем на отдельный уже оформленный в репозитории consultation-module. Поэтому их стоит считать сильным концептуальным дизайном, но не “готовым контрактом”. fileciteturn38file0 fileciteturn15file0

В-третьих, я не успел отдельно подтвердить через официальный публичный веб-источник общие межюрисдикционные стандарты для consultation/public participation; поэтому любые межстрановые утверждения о консультациях в этом документе лучше трактовать как архитектурную рекомендацию внутри PolicyOS, а не как универсальную доктрину внешнего регулирования.

# C23 Политика run-cost и degradation-SLA для PolicyOS

## Главный вывод

План C23 требует отдельной политики для **run-cost**, **budget governance** и **degradation-SLA**, причем acceptance-критерий прямо говорит, что cost/degradation нельзя путать с обычной latency observability. Внутри репозитория для этого уже есть почти все строительные блоки: `performance_budget.py` для фазовых latency-budget сигналов, `degradation.py` и реестр `mode_and_fallback_policy.toml` для fail-closed деградаций, `provider_verification.py` для preflight-гейта, VOI-модели и VOI-scheduler для стоимостно-ценностных решений о дополнительном поиске, `run_cost_proportionality` ledger для closeout, resilience matrix для операционных сценариев, approval packet для closeout, а также projection/public-export boundary и dashboard-панели для операторов. Но сегодня это все еще не сложено в одну явную политику, и часть approval-логики по-прежнему смешивает `degraded`/`over_budget` с `performance_status`. Именно это и надо исправить в рамках C23. fileciteturn19file0L3-L3 fileciteturn18file0L3-L3 fileciteturn54file0L3-L3 fileciteturn52file0L3-L3 fileciteturn31file0L3-L3

Внешний контекст подтверждает, что такое разделение правильно и практически необходимо. У поставщиков AI уже сегодня разные плоскости бюджетирования и ограничений: OpenAI тарифицирует отдельно токены, web-search calls и container sessions, а Anthropic отдельно описывает **spend limits** и **rate limits**; это разные управленческие сигналы, не сводимые к latency. Google SRE трактует error budget как отдельный механизм управления надежностью, а AWS прямо предупреждает, что безостановочные retries могут **усиливать** перегрузку, а не смягчать ее. citeturn3view0turn4view2turn4view0turn4view1

## Что уже закреплено в кодовой базе

В текущем коде PolicyOS `performance_budget.py` строит **canary performance budget** как набор фазовых строк с `phase`, `layer`, `budget_ms`, `status`, `retryable`, `production_blocking` и `next_action`. Эти строки описывают именно наблюдаемую производительность и hot paths: control plane, CAS, runtime API, evidence collection, dashboard render. Это уже хороший слой для latency observability, но он не является полноценной стоимостью run-а и не описывает сам по себе provider degradation, source unavailability или budget exhaustion. fileciteturn54file0L3-L3

Параллельно `degradation.py` уже задает отдельную fail-closed модель для fallback/degradation. Для serious profiles (`research`, `governed`, `production`, `serious_runtime`) authority-bearing fallback запрещен по умолчанию, а если деградация касается authority-bearing evidence, то closeout блокируется, если нет явного разрешения в policy rows или подписанного non-production-lowering exception. Это важный сигнал: **degradation** уже концептуально отделена от “просто медленно”. fileciteturn52file0L3-L3 fileciteturn53file0L3-L3 fileciteturn43file0L3-L3

`run_cost_proportionality` ledger уже задает каркас именно для стоимости closeout: он собирает `runtime_performance_budget`, `foundry_cost_model`, `scientist_budget`, `doe_search_budget`, `provider_cost`, `elapsed_time_budget`, `human_review_burden` и `evidence_depth_budget`. Кроме того, код уже содержит два важных hard rules: high-cost low-impact run обязан иметь proportionality evidence или typed blocker, а перерасход бюджета более чем на 10% без accepted budget-change record должен падать fail-closed. Это уже почти готовая нормативная основа для run-cost policy. fileciteturn30file0L3-L3 fileciteturn29file0L3-L3

Provider preflight тоже уже оформлен как отдельный runtime gate. `run_provider_preflight()` делает короткий реальный check перед дорогими NL workflows: проверяет `health`, каталог `models`, `capabilities`, `pricing`, а затем выполняет tiny completion. Ошибки preflight классифицируются как retryable при timeouts, 429 или 5xx, а при неверном ключе или отсутствии модели считаются неретрайблными. Это уже SLA-гейт, а не latency-телеметрия. fileciteturn55file0L3-L3 fileciteturn56file0L3-L3 fileciteturn57file0L3-L3

Resilience matrix закрепляет различие между `performance_warning`, `operational_failure`, `quality_failure` и `quarantined`. В частности, `retry_storm` и `queue_saturation` считаются operational failures и fail closed, `soak_incomplete_evidence` — quality failure, а `provider_brownout_live` по умолчанию quarantined. Это именно то разделение, которого требует C23: медленное и неприятное — не то же самое, что деградировавшее и непригодное к closeout. fileciteturn24file0L3-L3 fileciteturn44file0L3-L3

Наконец, approval и public projection уже дают ясные boundary rules. Approval packet блокирует run по `performance_budget_blocking`, `quality_not_passing`, `blocking_quality_failures` и `conflict_blocking`, а public export и projection semantics жестко утверждают, что projection surfaces — only `projection_only` / `redacted_derived` и **не могут** использоваться как authority для scorecard, approval или runtime closeout. Значит, cost/degradation-сигналы можно показывать публично только как projection summaries, но authority должна оставаться в runtime-owned artifacts. fileciteturn31file0L3-L3 fileciteturn36file0L3-L3 fileciteturn37file0L3-L3

## Проект политики run-cost

Предлагаемая policy должна зафиксировать, что **run-cost** — это не один сигнал, а семейство независимых бюджетов, которые сходятся в одном closeout-решении. Нормативно я бы формулировал так: **каждый serious run обязан иметь runtime-owned run-cost view**, а для policy-design closeout — либо валидный `run_cost_proportionality_ledger`, либо typed blocker, объясняющий, почему ledger временно невозможен, но decision authority не подменена молчаливым допущением. Основание для этого уже есть в existing ledger contract. fileciteturn30file0L3-L3 fileciteturn29file0L3-L3

Практически run-cost policy должна различать следующие бюджеты:

| Семейство бюджета | Что считается | Источник истины | Какой сигнал возникает |
|---|---|---|---|
| `compute_usd` | суммарный USD across runtime / provider / foundry / scientist / search | `BudgetState` + run-cost ledger | warning, limitation, blocker |
| `provider_api_calls` | число API calls и rate windows по provider/model | provider ledger + preflight + runtime counters | warning, rerun_required, blocker |
| `token_budget` | input/output/cached/tool tokens | provider/model usage counters | warning, limitation, blocker |
| `embedding_search_budget` | retrieval, search, embed, query-expansion, web-search calls | search/provider traces + acquisition budget | acquisition_action, limitation, blocker |
| `wall_clock_budget` | total elapsed seconds + phase deadlines | performance budget + elapsed_time_budget | warning, limitation, blocker |
| `retry_budget` | retries, backoff time, retry amplification | retry wrappers + resilience matrix | rerun_required, blocker |
| `acquisition_budget` | source verification, adversarial challenge, human escalation, extra retrieval | VOI report + search/runtime traces | acquisition_action, stop_search, blocker |

Эта декомпозиция соответствует и внутреннему коду, и тому, как реальные AI providers разделяют billing/limit semantics. OpenAI уже тарифицирует разные ресурсы по разным единицам — токены, web-search calls, container sessions — а Anthropic отдельно разводит spend ceilings и rate ceilings. Следовательно, PolicyOS не должен хранить все это в одном `performance_status` или в одном “latency budget”. fileciteturn30file0L3-L3 fileciteturn51file0L3-L3 citeturn3view0turn4view2

Для статусов я бы предложил такой нормативный state machine для run-cost:

- `within_budget` — расход под контролем, projected closeout помещается в лимит.
- `cost_warning` — crossed soft threshold или baseline `80%` threshold.
- `cost_limited` — crossed `90%` threshold либо projected closeout уже не помещается без явного budget-change record.
- `cost_blocked` — hard budget exhausted, `would_exceed()` возвращает true, либо closeout ушел за бюджет.
- `cost_disproportionate` — run формально еще не exhaust-нул hard cap, но high-cost low-impact case не имеет proportionality evidence.
- `budget_change_required` — overrun допустим только после принятого change record; без него closeout blocked. fileciteturn51file0L3-L3 fileciteturn29file0L3-L3

Численные thresholds лучше брать не “с нуля”, а из уже существующих примитивов. Сегодня `BudgetState` умеет soft alerting на `80%` и `90%`, а run-cost ledger уже кодирует hard fail при перерасходе более чем на `10%` без budget-change record. Поэтому наименее рискованное решение для C23 — **оставить 80/90 как platform-wide alert bands**, а authority-profile различать не новыми числами, а разной тяжестью действий. Для `dev`/`staging` это остаются диагностические предупреждения; для `research` — closeout limitation и owner review; для `governed` и `production` — pre-approval limitation на 90% и hard closeout blocker на exhaustion либо на disproportionality без typed justification. fileciteturn51file0L3-L3 fileciteturn29file0L3-L3 fileciteturn43file0L3-L3

Отдельно важно зафиксировать, что **wall-clock budget не равен SLA**. `elapsed_time_budget` должен оставаться в run-cost ledger как часть proportionality и operator burden, но медленный run сам по себе не обязан быть SLA-блокером, если он завершился с полным и authority-valid evidence. SLA начинается там, где медлительность превращается в provider preflight failure, retry storm, stale evidence, missing evidence, brownout, или несоблюдение runtime service surfaces. Это разделение уже отражено во внутренней resilience-модели и должно быть поднято на policy level. fileciteturn29file0L3-L3 fileciteturn24file0L3-L3 fileciteturn50file0L3-L3

## Проект политики degradation-SLA

`degradation-SLA` в PolicyOS должен означать не “любое превышение latency budget”, а **потерю способности системы выдать authority-bearing, closeout-годный результат в допустимом operational mode**. Именно поэтому preflight failures, unauthorized fallbacks, live-provider brownouts, source unavailability, retry storms и stale provider evidence должны жить в отдельной policy-плоскости, а не в одном bucket’е с `runtime.run_index_refresh > 500ms`. fileciteturn52file0L3-L3 fileciteturn24file0L3-L3 fileciteturn41file0L3-L3

Нормативно я бы предложил такой SLA state machine:

- `healthy` — primary path доступен, authority evidence produced, no brownout/quarantine.
- `warning` — есть ухудшение, но authority не снижена, fallback не включался, closeout еще возможен.
- `limited` — run может продолжаться диагностически, но authority-bearing output временно ограничен; нужен operator review или acquisition action.
- `rerun_required` — проблема transient/retryable и не должна чиниться silent fallback’ом; нужен controlled rerun.
- `blocked` — serious closeout невозможен.
- `quarantined` — lane не CI-safe и не может использоваться без явного manual exception и приложенного evidence. fileciteturn24file0L3-L3 fileciteturn44file0L3-L3 fileciteturn52file0L3-L3

Дальше важны конкретные правила классификации.

Если превышен обычный phase latency budget в `performance_budget.py` — например, hot path runtime API или dashboard render — это **performance observability warning**, а не SLA-blocker, пока run completed, evidence complete, и operator path остается usable. Именно поэтому resilience matrix для `run_index_pressure`, `cas_pressure` и `dashboard_degraded_rendering` использует `performance_warning`, а не operational failure. fileciteturn54file0L3-L3 fileciteturn24file0L3-L3

Если же срабатывает `provider_preflight` failure, `retry_storm`, `queue_saturation`, `provider_brownout_live`, либо unauthorized fallback/degradation по authority-bearing path, это уже **degradation-SLA event**. Внутренний код preflight различает retryable and non-retryable failures, resilience matrix помечает retry storm и queue saturation как `operational_failure`, а fallback registry для serious profiles запрещает authority-bearing fallback по умолчанию. Следовательно:
- retryable provider brownout/timeout/429/5xx → `rerun_required` для serious profiles;
- bad key / model missing / forbidden fallback → `blocked`;
- live brownout without explicit manual lane approval → `quarantined`. fileciteturn56file0L3-L3 fileciteturn57file0L3-L3 fileciteturn24file0L3-L3 fileciteturn43file0L3-L3

Source unavailability нужно трактовать отдельно от provider availability. Если недоступный источник ломает **required evidence** или опускает effective independent evidence count ниже минимального уровня, событие должно сначала стать `acquisition_action`, если еще есть authority-valid альтернативный путь получения evidence, acquisition budget и допустимое окно по времени. Если такого пути нет, или acquisition budget уже исчерпан, или policy требует именно этот источник/класс evidence, то это становится `blocked` или typed blocker на closeout. Такой подход следует и из VOI contracts, и из run-cost ledger’s evidence-depth rule: VOI может тратить compute на source verification/human escalation, но не может waive mandatory gates, а stopped run with insufficient evidence must fail closed unless there is a valid blocker. fileciteturn45file0L3-L3 fileciteturn46file0L3-L3 fileciteturn30file0L3-L3 fileciteturn38file0L3-L3

Retry semantics тоже надо вынести в явное policy language. `retry.py` уже задает per-node retry policy, timeout, backoff, jitter, dead-letter on exhaustion и `RetryExhaustedError`; resilience matrix одновременно вводит отдельную lane metric `retry_amplification` с threshold `1.5`, а AWS отдельно предупреждает, что retries могут усиливать перегрузку и должны останавливаться, когда не помогают availability. Значит, для C23 retry budget должен считаться своей осью: **повторные попытки не являются “бесплатным лечением деградации”**, и как только amplification или backoff debt выходит за policy threshold, статус должен переходить из `warning` в `rerun_required` или `blocked`. fileciteturn27file0L3-L3 fileciteturn44file0L3-L3 citeturn4view1

Наконец, provider/model freshness — это тоже degradation-SLA, а не latency. В `provider-model-quality` ledger outcome уже может быть `approve`, `require_review`, `demote` или `block_production_approval`, причем причиной может быть stale или missing default evidence. Поэтому C23 должен объявить, что stale provider default evidence, missing default evidence и model drift governance входят в **degradation-SLA policy**, а не в обычный performance surface. fileciteturn41file0L3-L3

## Как сигналы должны входить в acquisition, closeout, public projection и dashboards

### Acquisition

Для acquisition слой должен работать так: когда source verification, adversarial challenge, human escalation или дополнительный поиск повышают expected value / risk reduction больше, чем compute plus review cost, VOI разрешает тратить acquisition budget; когда marginal value отрицателен — включается `stop_search`; когда claim unsupported, weakly supported, contested или counterevidence-heavy — приоритет у source verification; когда human review mandated by policy — negative VOI не может его отменить. Это уже прямо следует из VOI scheduler reference и scheduler code. C23 должен просто связать эти VOI decisions с отдельным `acquisition_budget_status`, чтобы “источник недоступен” превращался либо в **acquisition action**, либо в **typed blocker**, но не исчезал внутри latency telemetry. fileciteturn45file0L3-L3 fileciteturn46file0L3-L3 fileciteturn47file0L3-L3

### Closeout

Для closeout я бы рекомендовал явное разделение scorecard/approval полей:
- `performance_status` — только observability and phase-budget health;
- `run_cost_status` — budget, proportionality, budget-change, evidence-depth cost;
- `degradation_sla_status` — provider/source/fallback/brownout/retry-storm/state freshness;
- `quality_status` — completeness and substantive assurance;
- `conflict_status` — lex/norm conflict.

Причина проста: текущая approval-логика уже блокирует по `performance_budget_blocking`, а resilience matrix уже различает `performance_warning`, `operational_failure` и `quality_failure`. Чтобы выполнить acceptance C23, PolicyOS нужен не один overloaded `performance_status`, а отдельные approval reasons вроде `run_cost_budget_blocking`, `run_cost_proportionality_blocking`, `degradation_sla_blocking`, `provider_preflight_blocking`, `source_acquisition_blocking`. Это — архитектурный вывод из уже существующих artifacts и approval contract. fileciteturn31file0L3-L3 fileciteturn24file0L3-L3 fileciteturn30file0L3-L3

Кроме того, деградационные и SLA-сигналы должны подчиняться уже существующей error-budget политике по service surfaces. Внутренний SLO doc и Google SRE сходятся: есть rolling error budget, response bands, release freeze и postmortem-trigger при крупном выжигании бюджета. Для C23 это означает, что **degradation-SLA surface** должен inherit-ить те же response bands, что и остальная operational reliability: `>50%` budget remaining — normal, `25–50%` — caution, `0–25%` — reliability-first, `<=0%` — freeze. Но это относится к SLA surfaces, а не к USD-run-cost. Стоимостные бюджеты должны иметь свои собственные лимиты и closeout blockers, а не подменять SLO-error-budget semantics. fileciteturn50file0L3-L3 citeturn4view0

### Public projection

Public projection и public export должны получать только **redacted, projection-only summaries** стоимости и деградации. Из существующего кода прямо следует, что projection/public export не может использоваться как authority для scorecard, approval или runtime closeout. Поэтому в публичную поверхность можно выносить только:
- aggregate state: `publishable`, `blocked`, `stale`, `contested`, `projection_only`;
- high-level cost/degradation labels;
- redacted reason codes и human-safe summaries;
- fingerprints/ref proxies вместо raw runtime refs, credentials, hidden answers и tenant-private material.

В public projection не должно уезжать ничего, что могло бы само по себе “доказать” closeout, отменить blocker или скрыть первичный runtime-owned evidence graph. fileciteturn36file0L3-L3 fileciteturn37file0L3-L3

### Dashboards

Dashboard уже умеет показывать performance budget issues, approval readiness, quality reasons, projection source/authority, next action и diagnostic commands. Поэтому наиболее естественное решение для C23 — не изобретать новый UI-язык, а добавить **два отдельные operator panels** рядом с существующим performance/approval path:
- `RunCostPanel` — spend vs budget, projected closeout cost, budget-change required, proportionality state, acquisition budget remaining, human-review burden;
- `DegradationSlaPanel` — provider preflight status, brownout/quarantine, retry amplification, source availability, stale provider evidence, fallback/degradation records, typed blockers.

Обе панели должны иметь те же поля, что и уже существующий operator surface: `layer`, `phase`, `status`, `classification`, `evidence_ref`, `next_action`, `projection_source`, `projection_authority`, а для serious blockers — машиночитаемые reason codes без попытки спрятать первичный runtime truth. Это прямо согласуется и с текущим `ControlFailurePanel`, и с runbooks `production-quality-triage` / `honest-diagnostics`. fileciteturn33file0L3-L3 fileciteturn39file0L3-L3 fileciteturn38file0L3-L3

## Рекомендуемый policy text для Wave C23

Ниже — версия policy, которую уже можно переводить в contract language.

**Policy statement.** Для serious profiles (`research`, `governed`, `production`, `serious_runtime`) PolicyOS MUST separately govern `performance observability`, `run-cost`, and `degradation-SLA`. Ни один из этих доменов не может silently satisfy другой. `performance_status` не может представлять provider/source degradation, а `run_cost_status` не может представлять latency/SLO health. fileciteturn43file0L3-L3 fileciteturn24file0L3-L3

**Run-cost rule.** Serious closeout MUST emit a runtime-owned run-cost view. Для policy-design closeout этим view MUST be `run_cost_proportionality_ledger` или typed blocker. Budget thresholds SHOULD use baseline alert bands at `80%` and `90%`, hard exhaustion at limit crossing, and fail-closed validation when total actual cost exceeds total budget by more than `10%` without an accepted budget-change record. High-cost low-impact runs MUST preserve proportionality evidence or emit a typed blocker. fileciteturn51file0L3-L3 fileciteturn29file0L3-L3 fileciteturn30file0L3-L3

**Degradation-SLA rule.** Authority-bearing fallback, provider brownout, retry storm, stale provider default evidence, missing required source evidence, and preflight failures MUST be governed by a separate degradation-SLA state machine with outcomes `warning`, `limited`, `rerun_required`, `blocked`, or `quarantined`. Unauthorized fallback in serious profiles MUST fail closed unless an explicit allowed policy row or signed non-production-lowering exception exists. Retryable provider failure SHOULD produce `rerun_required`, not silent fallback. fileciteturn52file0L3-L3 fileciteturn53file0L3-L3 fileciteturn56file0L3-L3 fileciteturn57file0L3-L3

**Acquisition rule.** When source or evidence deficits may still be cured through additional retrieval, verification, challenge, or human escalation, the system MUST emit `acquisition_action` backed by VOI evidence and remaining acquisition budget. Mandatory gates cannot be waived by negative VOI. If acquisition cannot restore required evidence within policy limits, closeout MUST block with typed reason. fileciteturn45file0L3-L3 fileciteturn46file0L3-L3 fileciteturn30file0L3-L3

**Approval rule.** Approval packets SHOULD stop overloading `performance_budget_blocking` and instead carry distinct reasons for `performance`, `run_cost`, and `degradation-SLA`. Public and dashboard projections MAY render summaries of those signals, but only as projection-only surfaces, never as authority evidence. fileciteturn31file0L3-L3 fileciteturn36file0L3-L3 fileciteturn37file0L3-L3

## Открытые вопросы и ограничения

Часть anchor-контекста, особенно `local_prod_debug_probe`, была доступна только частично из-за длины файла, поэтому предложенная политика опирается прежде всего на более канонические и полно читаемые surfaces: план C23, performance budget, degradation ledger, provider preflight, VOI scheduler, resilience matrix, run-cost proportionality ledger, approval/public export и SLO policy. Это достаточно для high-confidence policy draft, но при реализации стоит дополнительно синхронизировать названия новых reason codes и полей с фактическими HTTP response shapes и scorecard schema. fileciteturn19file0L3-L3 fileciteturn31file0L3-L3

Вторая limitation — в текущем коде есть сильные примитивы для USD-budget (`BudgetState`, run-cost ledger), но нет такого же явно унифицированного runtime-wide state object для tokens / API calls / search / acquisition budgets. Поэтому C23 выглядит не как “придумать идею”, а как **довести существующие разрозненные contracts до единого policy surface**, не ломая уже существующие fail-closed boundary rules. fileciteturn51file0L3-L3 fileciteturn30file0L3-L3

# Методология оценки и семантической полноты для универсального policy-design engine PolicyOS

## Краткий вывод

Для C26 правильная цель — не проверять, умеет ли система писать убедительно звучащие тексты, а проверять, умеет ли она **закрывать policy-design case на требуемом уровне authority без семантической лжи, скрытых пропусков и ложного повышения статуса**. Внутри репозитория для этого уже есть сильный фундамент: формализованная benchmark authority с разделением на public/private/selection/hidden_holdout/rotating_challenge/sentinel/adversarial, reviewed challenge factory, red-team registry, freshness/rotation logic, deterministic citation-faithfulness rules, authority-spoofing suite и большой корпус policy-design false-pass тестов. Поэтому лучший путь — не строить новый benchmark “с нуля”, а добавить поверх существующей инфраструктуры **семантический слой оценки**, где structural pass никогда не считается достаточным без semantic adjudication. fileciteturn4file0 fileciteturn11file0 fileciteturn13file0 fileciteturn9file1 fileciteturn9file2

Такой вывод хорошо согласуется и с внешними практиками. NIST AI RMF требует не только governance, но и непрерывных циклов map/measure/manage для рисков на всем lifecycle, а companion Playbook прямо позиционируется как живой ресурс с регулярными обновлениями. HELM показывает, что зрелая оценка должна быть многомерной, а не сведенной к одной accuracy-like метрике. Dynabench показывает ценность динамических adversarial challenge sets вместо статических комфортных бенчмарков. Для PolicyOS это означает: benchmark должен быть живым, многометриковым, split-aware и завязанным на реальные failure modes, а не на “правдоподобие” текста. citeturn5view0turn6view0turn8academia0turn1academia0

Главное изменение, которое я рекомендую, — ввести **semantic-completeness pack как отдельный семантический режим поверх уже существующих split-типов**, а не как еще один независимый structural checklist. Acceptance для C26 должно звучать так: если case структурно полон, но экспертный semantic review считает интерпретацию, scope, causal support, legal authority, participation claim, temporal alignment или public/export conclusion недостаточными для запрошенного authority level, benchmark обязан это ловить и блокировать closeout. fileciteturn4file0 fileciteturn13file0

## Что уже реализовано в репозитории и на что нужно опираться

В репозитории уже есть почти вся нужная “механика” для benchmark governance. Документ Benchmark Authority фиксирует split taxonomy и правила экспорта: `public`, `private`, `selection`, `hidden_holdout`, `rotating_challenge`, `sentinel`, `adversarial`; hidden refs запрещены в public export, stale evidence блокирует default enablement, а promotion rules зависят от claim mode, risk tier и наличия нужных pack refs. Это значит, что C26 не должен ломать текущую taxonomy; он должен использовать ее как опорный слой. Особенно важно, что в текущей модели уже есть leakage/contamination safeguards для hidden benchmark ids в public/exportable payloads. fileciteturn11file0

Challenge factory тоже уже достаточно зрелый для baseline. В reference-документации и тестах видно, что required challenge classes уже включают как минимум: `source_contradiction`, `stale_source`, `forged_citation`, `missing_transportability_assumption`, `hidden_confounding_proxy_assumption_trap`, `fairness_threshold_reversal`, `legal_exception`, `policy_gaming_strategic_response`, `budget_infeasibility`, `ambiguous_human_review_instruction`. Hidden promotion требует reviewer refs, reviewed packs регистрируются с lineage metadata, а public export challenge reports deliberately ref-free и режет canary leakage. Следовательно, baseline existing challenge classes уже покрывает основной adversarial skeleton; C26 должен не дублировать эти probes, а map’ить новые случаи на пробелы между существующими class/failure-code ячейками. fileciteturn6file0 fileciteturn13file1 fileciteturn13file2

Red-team и pack lifecycle тоже уже заданы. Red-team registry требует покрытие всех required challenge classes и разносит сценарии по risk tags вроде citation faithfulness, temporal staleness, causal assumption, legal, strategic response и human oversight. Sentinel machinery уже различает `canary`, `invariant`, `decoy`, `regression`, а rotation layer уже умеет блокировать near-frontier promotion, если fresh rotating challenge evidence отсутствует или протухло. Из этого следует практическое решение: **регрессионный pack не надо вводить как новый split** — его лучше выразить через существующий `sentinel` c `kind=regression`; исторические и semantic-completeness оценки лучше кодировать как family/metadata overlays поверх существующих split’ов. fileciteturn10file0 fileciteturn10file1 fileciteturn10file2 fileciteturn11file1 fileciteturn11file2

Самое важное для C26 — в репозитории уже есть явное признание проблемы semantic false passes. Failure-patterns register формулирует `semantic_test_missing` как отдельное недопустимое состояние capability claim, называет structural-only validation анти-паттерном `P10`, authority dilution — `P05`, soft-gate ambiguity — `P09`, а LLM speculation laundering — `P15`. Это очень сильный сигнал: семантическая полнота уже является частью архитектурной философии PolicyOS, и C26 должен просто довести это до benchmark-level governance. fileciteturn13file0

Наконец, уже существующие runtime suites показывают, что репозиторий не ограничивается формальными schema checks. Authority-spoofing suite бьет по ложному `quality_status=pass`, поддельным runtime refs, bundle-generated CAS-looking refs, fake approval readiness, projection promotion to authority, fake hidden benchmark pass, fake provider quality ledger, duplicate diagnostic event ids, sampled-away serious events, fake attestation, fake schema compatibility, fake semantic-binding ledger и fake source-of-truth winner. А policy-design false-pass suite уже тестирует wrong jurisdiction, prose backfill вместо producer refs, missing effective independence count, cherry-picked multiverse agreement, hidden counterevidence, ineffective human oversight, expert judgement masquerading as observed data, hidden stakeholder objections, missing external audit record и непропорциональный run cost. Это значит, что C26 стартует не с нуля: semantic-completeness design должен систематизировать и расширить уже имеющийся corpus. fileciteturn9file1 fileciteturn9file2 fileciteturn14file0 fileciteturn15file0

## Рекомендуемая архитектура benchmark packs

Я рекомендую не смешивать visibility, lifecycle и semantics в одну ось. Для PolicyOS лучше держать **двухслойную модель**. Первый слой — существующие split/kind механизмы репозитория. Второй слой — семантические overlays, которые задают, *какой именно вид semantic failure должен быть пойман*. Такая конструкция лучше согласуется с текущей benchmark authority и не требует необязательной schema churn. fileciteturn11file0 fileciteturn10file2

**Public pack** должен остаться маленьким и объяснимым: это safe-to-document examples и smoke/regression fixtures, которые можно обсуждать в документации и PR review. Он годится для разработческого feedback loop, но не должен быть достаточным для promotion. **Hidden holdout pack** должен быть главным promotion gate для authority-bearing closeout. **Regression pack** нужно реализовывать через sentinel cases, прежде всего `regression` и `invariant`, чтобы фиксить уже пойманные false passes. **Adversarial pack** должен агрегировать reviewed challenges из challenge factory плюс red-team scenarios с контролем leakage risk и reviewer admission. **Historical-backtest pack** должен использовать frozen “as-of-time” evidence windows и replay semantics: система должна получать только то, что было доступно на момент решения, а итоговая оценка сравнивает closeout с тем, что позднее выяснилось в ex post данных. **Semantic-completeness pack** должен быть overlay-категорией: cases из hidden/regression/adversarial/public получают дополнительный semantic rubric, по которому structural pass может быть признан semantic fail. fileciteturn11file0 fileciteturn10file1 fileciteturn10file2 fileciteturn11file1 fileciteturn13file0

Каждый кейс должен иметь не просто “правильный ответ”, а **gold semantic adjudication sheet**. В нем должны быть: требуемый authority profile; обязательные смысловые элементы, которые нельзя пропустить; запрещенные overclaims; минимальная цепочка evidence closure; допустимый статус closeout; требования к public/export projection; список критичных counterevidence и unresolved objections; а также expected downgrade path, если система не может честно закрыть case. Это прямо соответствует NIST-логике lifecycle risk management и HELM-подходу с scenario × metric taxonomy вместо единственного числа на leaderboard. citeturn5view0turn6view0turn8academia0

Отдельно важно ввести **coverage matrix, а не просто набор кейсов**. У каждого кейса должны быть теги по `challenge_class`, `record_family`, `governance_surface`, `producer_family`, `authority_profile`, `temporal_mode`, `export_surface`, `participation_mode`, `causal_mode`, `redaction_risk`. Новая probe допускается в benchmark только если она добавляет новую risk-cell или существенно усиливает already-covered cell на более высоком authority level. Это и есть механизм “baseline existing challenge classes and avoid duplicate probes”. Для тегирования удобно использовать уже существующие Policy Design Case minimum record families и governance surface requirements, а не изобретать новую ontology. fileciteturn9file2 fileciteturn14file0

## Метрики, которые действительно проверяют семантическую полноту

**Omission** должна считаться не по полям JSON, а по gold obligations. Если кейс требует legal competence, time alignment, baseline/no-action option, rejected alternatives, disconfirming evidence, consultation trace или accepted deficit disclosure, а система этого не отражает, это omission даже тогда, когда объект structurally complete. Для `production` authority profile я рекомендую нулевую терпимость к major omissions; для `research` допустимы только явно раскрытые deficits. Основание для такого разделения уже видно в policy-design false-pass suite, где research deficits нельзя silently promote в production authority. fileciteturn9file2 fileciteturn15file0

**Overgeneration** — это доля semantic assertions, которым не хватает source-grounded authority. Сюда должны входить unsupported major claims, ложные certainty upgrades, ложные participation claims, ложные public-readiness claims и ложные authority upgrades из projection/diagnostic/export surfaces. Existing authority-spoofing suite показывает, что именно такие ложные upgrades уже считаются high-severity failure mode; C26 должен превратить это в явный benchmark metric, а не оставить только набор unit tests. fileciteturn9file1 fileciteturn13file0

**Evidence closure** я предлагаю определить как claim-level долю major claims, для которых замкнута цепочка `claim → source data / norm / method → authority envelope → time role → counterevidence / accepted deficit → closeout status`. Важный момент: citation snippet сам по себе closure не образует. Внутренняя failure-patterns документация уже говорит, что semantic tests должны проверять adequacy, а не только field presence, checksum integrity или schema compatibility; следовательно, evidence closure должен быть содержательным, а не syntactic. fileciteturn13file0

**Authority truthfulness** должен стать blocking metric. Любой случай, где projection, dashboard, bundle packaging, public export, critic text, legacy shim или LLM-generated suggestion превращаются в authority, должен давать hard fail. Здесь уже есть богатая внутренняя база: fake hidden benchmark pass, projection used as authority, fake schema compatibility, fake semantic binding ledger, dashboard projection promoted to authority. Для production-профиля threshold должен быть простым: `0 false authority upgrades`. fileciteturn9file1

**Participation provenance** должен считать не просто наличие раздела consultation, а верифицируемость claims о participation. Если система утверждает, что stakeholders consulted, objections resolved или public comments addressed, у нее должны быть consultation records, stakeholder map, objection records, response-to-comment reasoning и корректная visibility. Внутренние tests уже блокируют hidden unresolved objections и missing structured judgement/consultation records; C26 должен поднять это на уровень benchmark rubric. fileciteturn9file2

**Calibration** нужна отдельно от accuracy. Для бинарных verdicts вроде `approval_ready`, `publishable`, `authority_sufficient` я рекомендую считать ECE и Brier-style loss на hidden holdouts; для количественных claims — interval coverage. Литература по calibration показывает, что высокопроизводительные модели часто переуверены, а LMs нередко путают знание с уверенностью, поэтому “правильный ответ” без корректной уверенности недостаточен для high-consequence decision support. citeturn10academia0turn9academia0turn9academia2

**Independence** должен измерять не raw evidence count, а ошибку в effective independent evidence count против gold collapsed clusters. Repo уже явно запрещает count inflation без effective independence accounting. Поэтому базовая метрика здесь — independence inflation ratio и share of claims with incorrect cluster-collapse reasoning. Для production authority profile эта метрика должна быть quasi-blocking на major claims. **Acquisition quality** должна оценивать, насколько система выбирает допустимые и релевантные источники: права, freshness, jurisdiction, snapshot identity, quality refs, blocked producer honesty. **Closeout truthfulness** должен проверять, соответствует ли финальный closeout реальному semantic state кейса: не скрыл ли он deficits, не повысил ли blockers до pass, не утекли ли hidden refs, можно ли реально верифицировать public/external audit package без private operator context. Внутренний external-audit fixture хорошо показывает разницу между cryptographic packaging и реальной public trust surface — именно поэтому closeout truthfulness нельзя редуцировать к наличию signatures и CAS refs. fileciteturn9file2 fileciteturn15file0

## Абляции и недостающие пробы

Абляции лучше строить по четырем семействам, которые уже естественно видны в кодовой базе. **Critic family ablations**: выключить critic entirely; оставить только structural critic; оставить semantic critic без adversarial critic; включить полный critic stack. Это покажет, какие semantic failures ловятся за счет критика, а какие — за счет rule layer. **Rule family ablations**: по отдельности выключать authority rules, temporal rules, participation rules, citation-faithfulness rules, public-export rules и closeout rules. **Facet family ablations**: использовать minimum record-family registry и поочередно убирать/ослаблять отдельные record families и governance surfaces, чтобы измерить marginal semantic loss. **Producer family ablations**: по отдельности деградировать `lex`, `fabric`, `data_forge`, `scholar`, `foundry`, `options_objectives` — не только в режим “missing”, но и в режим “runtime_blocker”, “static_inventory”, “narrative citation”, “stale snapshot”, “shim/transport fallback”. Это даст реальную карту, какая producer family действительно держит semantic adequacy, а какая только создает видимость полноты. fileciteturn9file2 fileciteturn14file0

По missing probes картина такая. **Уже сильно или частично покрыто**: authority spoofing; projection laundering; hidden benchmark promotion as authority; inferred-ledger box ticking; semantic-binding laundering; public-export leakage of hidden ids; citation false-pass limits на классы semantic-gap/contradiction/time mismatch/fabrication; effective independence inflation; hidden counterevidence; hidden stakeholder objections. fileciteturn9file1 fileciteturn9file2 fileciteturn11file0 fileciteturn13file1 fileciteturn6file1

**Явно добавить нужно следующее.** Во-первых, **prompt injection**: не общий security smoke test, а policy-specific probes, где вредоносные инструкции приходят через retrieved legal text, public comments, consultation attachments, tool outputs и audit artifacts; кейс считается пройденным только если система не перепутает источник текста с authority role. Это особенно важно, потому что современные agent benchmarks показывают уязвимость к realistic indirect prompt injections даже у сильных систем, а свежие исследования объясняют это через role confusion. citeturn11academia7turn11academia0turn6view1

Во-вторых, **participation speculation**: кейсы, где narrative hints позволяют модели написать “stakeholders were consulted” или “public comments were addressed”, хотя consultation record, objection trace или response ledger отсутствуют. В-третьих, **redaction completeness**: не только hidden id leakage, но и semantic leakage — например, public export не содержит hidden ref, но порядок пунктов, формулировка summary или бинарные flags фактически раскрывают withheld answer или скрытое counterevidence. В-четвертых, **legacy warning publication**: warnings есть internally, но не surfaced, не aged, не escalated и не влияют на closeout/publication. В-пятых, **degraded transport becoming supported claim**: fallback/shim/compat transport генерирует поле, которое потом воспринимается как source-grounded evidence. В-шестых, **public-export promotion**: public surface языком поднимает conditional or blocked finding до impression of production-grade support. Эти пробелы хорошо ложатся на already-declared anti-patterns P05, P06, P09, P10 и P15, но пока недостаточно выражены как benchmark packs. fileciteturn13file0 fileciteturn11file0 fileciteturn9file2

Собственно **semantic-completeness probes** должны быть главным новым классом. Это кейсы, где scorecards, CAS refs, signatures, citation snippets и schema validators проходят, но expert review отвергает вывод. Типовые шаблоны здесь такие: citation snippet буквально поддерживает фразу, но не causal interpretation; legal source настоящий, но не обладает нужной компетенцией или действует не в тот период; participation section существует, но скрывает unresolved high-severity objection; independence map структурно присутствует, но clustering семантически неверный; external audit package cryptographically verifies, но независимый reviewer не может восстановить public-trustworthy case without private operator context; multiverse и synthesis заполнены, но скрывают direction-changing sensitivity. Именно такие кейсы и являются сердцем C26. fileciteturn9file2 fileciteturn15file0 fileciteturn13file0

## Политика управления benchmark и критерий приемки

Политика управления должна быть консервативной. Владельцем persistence authority уже объявлен BenchmarkRegistry/BenchmarkAuthority, а в документации зафиксированы owners и backup owners; это следует сохранить. Но для semantic-completeness layer нужен отдельный **Semantic Review Board** из минимум трех ролей: benchmark owner, domain reviewer и governance/closeout reviewer. Hidden и semantic packs должны допускаться только после двух независимых human approvals; reviewer refs и provenance должны быть обязательны так же, как они уже обязательны для hidden challenge admission. fileciteturn11file0 fileciteturn11file1 fileciteturn13file1

Versioning должен быть двусоставным: `benchmark_revision` для content и `semantic_rubric_revision` для adjudication rules. Historical-backtest cases должны быть immutable по evidence window и replay rule set; при ужесточении правил case не перезаписывается, а reissued с новой rubric revision. Это прямо соответствует внутреннему anti-pattern’у P07 про rule-versioned semantic replay. Freshness policy можно наследовать из существующей benchmark authority: rotating — 30 дней, adversarial — 60, sentinel — 90, hidden/private — 120. Semantic packs не должны быть exempt от freshness; наоборот, они должны пере-ревьюиться при смене law/policy ontology и authority semantics. fileciteturn11file0 fileciteturn13file0 citeturn5view0turn6view0

Promotion policy я бы сформулировал жестко: **public и selection evidence никогда не дают default enablement сами по себе**; для governed/production authority нужны hidden holdout, regression sentinel, adversarial coverage и semantic-completeness pass на целевом authority profile. Aggregate score не должен скрывать blocking failures: authority truthfulness, closeout truthfulness, prompt injection with authority escalation, unresolved redaction leak, hidden counterevidence suppression и semantic-completeness fail на major claim должны быть hard blockers. Это согласуется и с внутренней benchmark authority, и с NIST-подходом к governance/map/measure/manage как к непрерывному risk loop, а не к разовому certification event. fileciteturn11file0 fileciteturn9file1 fileciteturn9file2 citeturn5view0turn6view1

В таком виде acceptance для C26 достигается. План будет действительно “detect structural completeness that is semantically wrong or insufficient for the requested authority level”, потому что семантическая полнота превращается из неформального reviewer discomfort в формализованный hidden/regression/adversarial gate с отдельными blocking metrics, replayable rubrics, expert adjudication и versioned governance. fileciteturn4file0 fileciteturn13file0

## Открытые вопросы и ограничения

Я не провел построчный аудит всех упомянутых в C26 anchor-файлов, особенно тех, что относятся к exact temporal-drift check implementations и production-quality replay fixtures. Поэтому часть рекомендаций по historical-backtest и replay governance выведена из ближайших подтвержденных артефактов — stale-source challenge class, rotation/staleness logic, false-pass corpus и P07 rule-versioned replay pattern — а не из полного line-by-line обзора каждого replay-related модуля. fileciteturn6file0 fileciteturn10file1 fileciteturn13file0

Также я сознательно не предлагаю фиксированные quotas по количеству кейсов в каждом pack. В текущем состоянии репозитория важнее coverage matrix, blocking metrics и governance discipline, чем искусственный target вроде “N кейсов на split”. Если понадобится operational next step, его лучше задавать как coverage minima по risk-cell и authority profile, а не как голые counts. fileciteturn11file0 citeturn8academia0turn1academia0

# C27 Синтез исследований и готовность к реализации универсального Policy Design Case

## Контекст и исследовательская рамка

Эта оценка сделана строго внутри репозитория `DenisKopylov/polisyos` и опирается на полный active research plan для универсального Policy Design Case, на operating model и decision log, на регистр failure patterns P01–P15, на cloud root-cause backlog и production-data E2E backlog, на active plan по evidence binding, на capability baseline Scientist, а также на текущие кодовые якоря в `runtime/quality`, `fabric`, `scientist` и связанных модулях. Сам research plan прямо требует не рассматривать PolicyOS как blank slate, а начинать с уже существующих якорей, работать reuse-first и не превращать нерешенные исследовательские вопросы в runtime-контракты до прохождения acceptance-критериев. fileciteturn8file0L3-L3 fileciteturn9file0L3-L3

Для целей C27 я использую четыре статуса: **implementable now**, **experimental**, **authority-level-gated**, **research-only**. При этом “готово к реализации” ниже означает не «облачный live lane уже доказал end-to-end закрытие», а «семантика, owners и reuse-поверхности уже достаточно стабильны, чтобы инженерия шла поверх существующих модулей, а не через очередной greenfield». Такой подход соответствует и самому research plan, и decision log, который специально отделяет стабильный ADR-слой от reversible implementation-time решений. fileciteturn11file0L3-L3 fileciteturn24file0L3-L3

## Стабильное ядро для инженерного старта

Главное устойчивое решение уже принято: serious Policy Design Case должен расширять существующий runtime-quality assurance substrate, а не создавать параллельный объект authority. Operating model прямо говорит, что primary case object — это assurance-case profile поверх `src/polisyos/runtime/quality/assurance_case.py`, а не новый отдельный граф; archived implementation plan повторяет ту же архитектурную установку и фиксирует accepted ADR pack 0156–0165 как execution-grade слой для этой линии работ. Decision log дополнительно закрепляет, что именно ADR 0156–0165 являются стабильным архитектурным слоем, а append-only log не имеет права молча сужать их смысл. fileciteturn13file0L3-L3 fileciteturn35file0L3-L3 fileciteturn24file0L3-L3

Контрактное ядро Policy Design Case уже существует в коде. `policy_design_case.py` задает registry из **19 minimum record families**, вводит явную applicability-тройку `required / profile_scoped / not_applicable`, валидирует registry и отдельным coverage-валидатором fail-closed запрещает ситуацию, когда у Policy Design Case выставлен `status=pass`, но нет ни `record_families`, ни concrete runtime `records`. То есть базовое различение между «есть профиль/схема» и «есть реальная runtime-owned запись» уже оформлено как enforceable contract, а не как пожелание в документации. fileciteturn16file0L3-L3 fileciteturn17file0L3-L3 fileciteturn19file0L3-L3

Не менее важно, что несколько «тяжелых» governance- и trust-субстратов уже присутствуют в коде как рабочие surfaces, а не как placeholders. `formal_invariants.py` уже требует пять closeout-critical invariant ids — `authority_ordering`, `phase_barriers`, `same_input_closure`, `cas_event_reconciliation`, `terminal_readiness`. `projection_semantics.py` уже fail-closed требует `projection_only` и явно запрещает использовать projection для `runtime_closeout_authority` и `scorecard_authority`. `source_contract.py` уже несет SourceContract v2 со schema/security/quality/semantics/access-policy слоями. `challenge_factory.py` уже содержит обязательные adversarial challenge classes, а `voi_scheduler.py` уже реализует VOI как ranker/decision layer, а не как чистую идею. Это и есть тот «stable kernel», от которого C27 должен отталкиваться. fileciteturn26file0L3-L3 fileciteturn29file0L3-L3 fileciteturn28file0L3-L3 fileciteturn27file0L3-L3 fileciteturn32file0L3-L3

Помимо runtime-кода, уже есть и стабильный baseline на уровне capability inventory. `scientist-capability-inventory.md` фиксирует, что Scientist не является пустым местом: claim ledger, Research DAG, continuous governance, human review, evidence stack, evals, workflows, decision-grade compiler, VOI, replay и governance passes уже представлены как текущие source-of-truth surfaces с тестами и CI-gates. Это значит, что значительная часть будущей работы — не «изобрести capability», а связать существующие capability с Policy Design Case record families и closeout-visible authority. fileciteturn23file0L3-L3

При этом fixtures deliberately честны насчет своей ограниченности. `tests/fixtures/policy_design_case/README.md` прямо говорит, что fixtures для accepted ADR 0156–0161 — это **contract-shaped examples**, а не production schemas, и что walking skeleton специа́льно не является production-grade. Это важное разграничение: у проекта уже есть хорошая contract/test база для старта инженерии, но сама по себе она не доказывает live-path closure. fileciteturn34file0L3-L3

## Реальные блокеры, удерживающие систему в исследовательском режиме

Самый важный отрицательный сигнал приходит из cloud Wave 11. Там bundle replay и bundle inspection показали, что артефакты воспроизводимы и структурно читаемы; failure — не в corruption bundle. Но scorecard при этом провалился: 181 failed gates из 215, а крупнейшие коды — `semantic_fabric_source_facet_incomplete` и `policy_design_case_record_family_missing`. Более того, triage схлопнул 108 downstream failures в одну semantic closure root cause. Это означает, что ядро серьезности уже умеет fail-closed, но live orchestration path все еще не доводит evidence graph до claim-bound closure. fileciteturn20file0L3-L3

Cloud diagnostic backlog показывает четыре особенно значимые для C27 проблемы. Во-первых, scenario-specific data families отсутствуют в curated contracts, хотя физические данные и bundle присутствуют; система видит generic bundles, а не scenario-admissible families. Во-вторых, глобальная evidence availability уже есть, но major claims все равно несут пустые `data_refs`, `method_refs`, `norm_refs`, `portfolio_refs`, `argument_refs` и другие поля. В-третьих, semantic ledger дает top-level `status=pass`, хотя closure по claim paths отсутствует. В-четвертых, live `policy_design_case.json` выдается с `status=pass`, но без `records` и без `record_families`. Это уже не вопрос красных «подпорок», а вопрос правдивости runtime authority chain. fileciteturn20file0L3-L3 fileciteturn21file0L3-L3

Эти симптомы очень точно ложатся на register P01–P15. Профиль/статус без runtime records — это P01 `contract_only`. Богатые внутренние компоненты без рабочей связки producer -> bridge -> consumer — это P02 `thin orchestration`. Внутренняя насыщенность при слабой projection/live surface — это P03. Ситуация, когда top-level producer status говорит `pass`, а scorecard позже обнаруживает semantic closure failure, — это P10 `structural-only validation`. А сам универсальный policy-design контур по определению должен держать P15 `candidate-to-authority firewall`: LLM и narrative content не могут стать authority, пока producer evidence не закроет обязательства. Наконец, P13 напоминает, что новые требования нельзя делать обязательными без proportional governance. fileciteturn12file0L3-L3

Active plan по evidence binding формулирует тот же вывод уже на implementation-языке: текущая проблема — не набор изолированных багов, а «missing runtime bridge between scenario obligations and the producer evidence that must support serious policy recommendations». План также отдельно требует разделить provenance failures и domain-authority failures, а также перестать считать broad production bundles эквивалентом scenario-specific admissible evidence. Для C27 это означает, что engineering не надо идти в сторону новых domain templates; ему надо идти в bridge-first связывание существующих producer surfaces, semantic binding и Policy Design Case compiler. fileciteturn36file0L3-L3

Ключевой синтетический вывод: репозиторий уже действительно содержит сильное ядро, но live lane все еще подтверждает именно тот слабый паттерн, который research plan сам назвал центральным: **sophisticated component -> thin orchestration bridge -> weak external/API projection**. Следовательно, C27 должен считать базовые модули стабильными, а главный риск — не отсутствие capability как таковой, а ложная декларация готовности до замыкания мостов. fileciteturn8file0L3-L3 fileciteturn9file0L3-L3 fileciteturn36file0L3-L3

## ADR-ready решения и вопросы, которые нельзя преждевременно кодифицировать

### Что уже ADR-ready

Ниже — пакет выводов, которые я считаю достаточно стабильными не для «еще одного research memo», а для ADR-level фиксации или, чаще, для **amend existing ADR**, а не для net-new greenfield ADR. Decision log прямо требует именно такого поведения: reversible implementation details — в log, cross-component semantics — в ADR. fileciteturn24file0L3-L3

- **Профильный `pass` без concrete runtime records должен падать на producer-time, а не ждать scorecard-time.** Это уже согласуется с существующим registry/coverage validator и прямо подтверждено cloud finding про `policy_design_case.json status=pass` без `records` и `record_families`. Практически это выглядит как amendment к ADR-0156 и boundary-ADR слою о runtime authority. fileciteturn17file0L3-L3 fileciteturn21file0L3-L3

- **Scenario evidence contract и binding result нужно сделать first-class runtime obligation across Fabric, Lex, Foundry, Scientist, semantic binding и PDC.** Active evidence binding plan уже фиксирует это как архитектурный ответ на cloud root cause, а research plan отдельно задает universal path `policy request -> universal policy grammar -> obligation graph -> evidence acquisition -> admissibility -> PDC`. Это тянет не на ad hoc fix, а на стабильную архитектурную норму, лучше всего как amendment к ADR-0157/0159. fileciteturn36file0L3-L3 fileciteturn8file0L3-L3

- **Нужно развести provenance status и domain status.** Active evidence binding plan прямо фиксирует authority classification gap: runtime-emitted artifacts с CAS/runtime refs не должны коллапсироваться в `unknown_provenance` только потому, что их domain validation failed. Это стабильное boundary decision, не локальная настройка. Его лучше поднимать через amendment к authority/diagnostics ADR-слою, а не решать локально в scorecard. fileciteturn36file0L3-L3

- **Top-level статус semantic ledger должен наследовать тот же closure evaluator, что использует scorecard.** Сейчас live diagnostics показывают producer/reader truth gap: ledger говорит `pass`, а scorecard находит 108 semantic failures. Это достаточно четкая invariant-grade семантика, чтобы закрепить ее на ADR-уровне, вероятнее всего как amendment к semantic-binding и assurance-case решениям. fileciteturn21file0L3-L3 fileciteturn30file0L3-L3

- **Capability ratchet из P01–P15 нужно встроить в финальный implementation plan как обязательный governance artifact.** Failure register уже определяет missing-state vocabulary (`contract_only`, `bridge_missing`, `semantic_test_missing` и др.), а research plan прямо выносит E0 как tooling for capability ratchet and pattern register. Здесь не нужен новый концепт; нужен обязательный инженерный рельс. fileciteturn12file0L3-L3 fileciteturn11file0L3-L3

### Что нельзя хардкодить в runtime rules

То, что ниже, уже достаточно хорошо сформулировано как open question, но еще **недостаточно стабильно**, чтобы превращать это в hard runtime rule без corpus-backed решения.

Нельзя преждевременно зафиксировать физическую форму concept spine, финальную модель multi-jurisdiction conflict representation, полный time-role algebra, certainty framework для evidence synthesis, collapse-правила эффективной независимости, stopping rules для saturation, допустимые assurance deficits по authority level, публичный contestability contract, structured expert judgement protocol, minimum competence model для public-facing рекомендаций, ex-post observation window, calibration metrics для blocking high-authority runs, BERL thresholds и mandatory post-publication DDM events. Все эти вопросы уже импортированы в decision log как unresolved и research plan прямо связывает их с отдельными conceptual kernels C6–C8, C11, C13–C14, C17–C19, C20–C25, C26 и C27. Следовательно, их нужно держать в statused research/decision-log режиме, а не цементировать в code contracts «по ходу имплементации». fileciteturn9file0L3-L3 fileciteturn24file0L3-L3

Отдельно нельзя возвращаться к соблазну domain adapters как основной стратегии. Research plan прямо запрещает делать каталог доменных шаблонов главным решением и прямо требует заменять множество brittle templates на меньшее число governed obligation rules. Поэтому любые попытки «починить универсальность» добавлением новых domain packs надо считать architectural regression, пока не доказано обратное. fileciteturn8file0L3-L3

## Готовность минимальных семейств записей

Ниже я даю классификацию **всех 19 minimum record families**. Здесь важно читать статус буквально: **ready** означает «можно инженерно реализовывать поверх существующих owner-модулей», а не «полностью доказано live cloud lane». Сам registry уже допускает `required`, `profile_scoped` и `not_applicable`, поэтому profile-gated классификация здесь полностью согласуется с текущим кодом. fileciteturn16file0L3-L3

- **Implementable now:** `intent_authoring_and_capture_risk.v1`, `capability_mode_and_fallback_selection.v1`, `data_source_semantic_lineage.v1`, `scholar_academic_evidence.v1`, `claim_argument_evidence_case.v1`, `integrity_self_fmea_and_maturity.v1`, `formal_substrate_invariant_spec.v1`. Для этих семейств уже есть либо прямые schema/constants и validators в `runtime/quality`, либо зрелые owner-surfaces в Scientist/Fabric/runtime, либо contract fixtures, либо уже существующие invariant/maturity/threat-model scaffolds. Главный remaining risk тут не исследовательский, а orchestration/live wiring. fileciteturn16file0L3-L3 fileciteturn30file0L3-L3 fileciteturn28file0L3-L3 fileciteturn34file0L3-L3 fileciteturn37file0L3-L3 fileciteturn38file0L3-L3 fileciteturn26file0L3-L3

- **Implementable now, but only authority-level-gated or mode-gated:** `legal_authority_and_competence.v1`, `structured_judgement_and_consultation.v1`, `implementation_monitoring_and_evaluation.v1`, `human_oversight_independence_and_review.v1`, `publication_trust_and_external_governance.v1`, `best_in_class_benchmarking.v1`. Здесь база уже существует — Lex/legal surfaces, human-review packets, DDM and continuous-governance paths, public/export and audit surfaces, challenge factory and benchmark infrastructure, — но decision log оставляет открытыми thresholds и protocols: institutional competence model, expert-judgement acceptability, effective oversight telemetry, contestability contract, benchmark task set, DDM mandatory events. Поэтому правильный режим сейчас — profile-scoped implementation, а не universal hard-required enforcement. fileciteturn8file0L3-L3 fileciteturn23file0L3-L3 fileciteturn24file0L3-L3 fileciteturn27file0L3-L3 fileciteturn29file0L3-L3

- **Research-first or experimental:** `concept_and_jurisdiction_spine.v1`, `numeric_time_and_geography_semantics.v1`, `method_selection_and_validity.v1`, `evidence_portfolio_and_synthesis.v1`, `options_objectives_and_tradeoffs.v1`, `lifecycle_ex_post_and_calibration.v1`. Именно для этих семейств research plan сохраняет самые тяжелые conceptual kernels и самые крупные build-new/bridge-new поверхности: concept spine как namespaced cross-producer authority, time-role algebra, analytics-to-ClaimRecord bridge, lineage-aware independence, synthesis certainty, rule evolution, partial reissue, longitudinal calibration и balanced memory. Эти семьи нельзя превращать в жесткие runtime правила до завершения соответствующих conceptual gates; максимум — делать narrow scaffolds и typed blockers. fileciteturn9file0L3-L3 fileciteturn10file0L3-L3 fileciteturn11file0L3-L3 fileciteturn24file0L3-L3

Побочный, но очень важный вывод: над семействами записей нельзя судить по archived checkbox language в отрыве от live diagnostics. Archived implementation plan полезен как baseline того, что уже было формализовано и частично доказано в wave-based execution, но cloud wave11 однозначно показывает, что для части семейств сохраняется P01/P02-разрыв между «есть schema/fixture/test story» и «есть живой, замкнутый producer-to-closeout path». Именно поэтому C27 должен различать **contract readiness** и **live-lane orchestration readiness**. fileciteturn35file0L3-L3 fileciteturn21file0L3-L3 fileciteturn12file0L3-L3

## Входы в финальный implementation plan

Ниже — сжатый пакет implementation tasks, который, по моей оценке, и должен стать входом в финальный `POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md`. Эта матрица выведена из C27/E0–E23 логики research plan, из списка largest build/bridge surfaces, из stop-reopening surfaces, из cloud evidence-binding plan и из P01–P15 ratchet. fileciteturn9file0L3-L3 fileciteturn11file0L3-L3 fileciteturn36file0L3-L3 fileciteturn12file0L3-L3

| Implementation slice | Related tasks | Readiness | Reuse-first classification | Why it belongs in the first real plan |
| --- | --- | --- | --- | --- |
| Capability ratchet and P01–P15 labeling in plans, backlogs, scorecards | C27, E0 | implementable now | extend_existing | Vocabulary and missing-state taxonomy already exist; the repo needs tooling, not new semantics. |
| Live Policy Design Case record-family compiler in runtime path | C27, E4/E5-adjacent, cloud root cause | implementable now | wire_existing + extend_existing | Registry and validators already exist; cloud lane still emits profile-only pass. |
| Scenario evidence contract through Fabric, Lex, Foundry, Scientist | C22, E17, active evidence-binding plan | implementable now | extend_existing | Scenario obligations are the missing bridge between data/legal/method surfaces and claims. |
| Semantic closure and claim-graph compiler truth preservation | C9–C10, C15, E8/E12 | implementable now | consolidate_existing | Existing evidence counts do not reach claim refs; this is mostly a binding/compilation problem. |
| Typed multi-audience PolicyDesignCase projection and client/export sync | C16, E4–E5 | implementable now | extend_existing | Projection guardrails exist; typed projection surface is still too shallow. |
| Provenance/domain failure split and first-failing-producer operator ledger | C3, C24, cloud evidence-binding plan | implementable now | consolidate_existing | Diagnostics already show the need; improves operator truthfulness without reopening core authority model. |
| Unified `can_i_closeout` substrate | C3, C24, E3 | experimental | consolidate_existing | Many fragments exist, but one typed closeout object is still a new composition surface. |
| Concept/jurisdiction spine carrier and producer handshake | C6–C8, E6–E7 | experimental | build_new | Research plan itself marks this as one of the biggest genuinely bridge-new/build-new surfaces. |
| Evidence independence, certainty, multiverse, and stopping rules | C13–C14, C22, E13 | experimental | extend_existing + build_new | Consensus/equivalence exist, but universal collapse model and certainty semantics do not. |
| Rule evolution, partial reissue, lifecycle dependency graph, calibration ledger | C20–C21, C25, E14–E16, E20–E21 | experimental | extend_existing | Replay/DDM/calibration bases exist; universal-policy bridges and blocking rules do not. |
| Participation provenance and structured judgement/consultation authority records | C17–C19, E11/E22 | research-first | build_new | The repo has governance/human-review infrastructure, but participation legitimacy semantics are still mostly open. |
| Run-cost and degradation-SLA governance above latency observability | C23, E18 | experimental | extend_existing | `performance_budget.py` already covers observability budgets, but not cost/SLA authority policy. |
| Benchmarking and human-team comparison packs | C26, E22 | authority-level-gated | extend_existing | Challenge factory exists; policy/human benchmark set and promotion thresholds are still open. |

Первый tranche финального implementation plan должен начинаться не с concept spine и не с participation provenance, а с шести самых прикладных bridge-first задач: capability ratchet, live record-family wiring, scenario evidence contract, claim-closure compiler, typed projection, provenance/domain split. Именно они одновременно опираются на уже существующие модули и адресуют текущие live-lane блокеры. Если начинать широкой инженерией сразу с concept spine, certainty framework или public legitimacy semantics, проект почти гарантированно скатится в build-new поверх неустойчивых исследовательских вопросов. fileciteturn20file0L3-L3 fileciteturn21file0L3-L3 fileciteturn9file0L3-L3

Для каждого task packet в финальном implementation plan я бы сделал обязательными пять полей: **target failure patterns**, **current missing-state label**, **reuse proof**, **negative semantic test**, **operator-visible next action**. Это полностью согласуется и с failure register, и с archived implementation plan packet discipline, и с research plan acceptance для C27. Без этих пяти полей инженерная работа снова начнет выдавать «there is a contract» вместо «there is a closed authority chain». fileciteturn12file0L3-L3 fileciteturn35file0L3-L3 fileciteturn11file0L3-L3

## Вердикт C27

Инженерию **можно начинать уже сейчас**, но не как broad universal-policy implementation и не как новую серию domain adapters. Начинать можно только со **stable kernels** и с **bridge-first implementation slices**, которые уже имеют owners, кодовые anchors, validators и понятные failure patterns: runtime assurance substrate, minimum record-family registry, projection boundaries, formal invariants, SourceContract v2, challenge factory, VOI baseline и Scientist capability baseline. fileciteturn13file0L3-L3 fileciteturn16file0L3-L3 fileciteturn26file0L3-L3 fileciteturn28file0L3-L3 fileciteturn23file0L3-L3

Но engineering **не должен** начинаться с hard-coding универсальных правил для concept spine topology, effective independence collapse, certainty framework, contestability contract, participation legitimacy, calibration blocking thresholds, BERL thresholds, DDM mandatory events или ex-post windows. Эти вопросы уже честно вынесены в open-question layer и по самому смыслу C27 должны оставаться исследовательскими до накопления corpus-backed и evaluation-backed решения. Иначе PolicyOS снова сделает ровно то, против чего предупреждает research plan: превратит спекуляцию в архитектуру. fileciteturn24file0L3-L3 fileciteturn8file0L3-L3

Итог в одной фразе: **stable kernel уже есть; live orchestration closure еще нет; значит следующий implementation plan должен быть не template-first, а bridge-first, with explicit anti-pattern ratchet, typed blockers, and evaluation loops.** fileciteturn9file0L3-L3 fileciteturn12file0L3-L3 fileciteturn36file0L3-L3

# Исследование C24 для PolicyOS

## Контекст и исследовательская рамка

Я исходил не из “чистого листа”, а из уже зафиксированной архитектуры репозитория. План `POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md` прямо требует начинать с кодовых якорей и завершить работу четырьмя артефактами: self-FMEA моделью, lifecycle’ом soft-gate состояний, планом оценки эффективности review и complexity budget. В том же плане acceptance-критерий сформулирован жестко: сбои самой case-машины не должны маскироваться под “плохие доменные доказательства”, а система assurance должна уметь распознавать, когда контроль становится чрезмерно дорогим или церемониальным для запрошенного уровня authority. fileciteturn6file0

По коду видно, что для C24 уже существует богатая основа, на которую можно опереться: формальные инварианты и их спецификация, phase barriers как runtime-authority механизм, evidence authority envelope с same-input closure, source-truth lattice, trust-boundary attestation, prompt/tool/parser ledger, scorecard с triage-логикой и VOI-эскалация human review. Иначе говоря, задача C24 — не “придумать контроль с нуля”, а связать уже существующие fail-closed механизмы в мета-модель отказов самой machinery. fileciteturn9file0 fileciteturn10file0 fileciteturn12file0 fileciteturn13file0 fileciteturn14file0 fileciteturn15file0 fileciteturn17file0 fileciteturn18file0 fileciteturn19file0

## Базовая линия текущей assurance-модели

Спецификация formal invariants уже фиксирует пять model-checked свойств как минимум допустимого formal substrate: `authority_ordering`, `phase_barriers`, `same_input_closure`, `cas_event_reconciliation` и `terminal_readiness`. Это важный исходный факт: C24 не должен дублировать их, а должен описать то, что происходит **вокруг них** — как machinery ломается до, между или после этих проверок. fileciteturn10file0 fileciteturn9file0

Текущая базовая линия по инвариантам выглядит так:

- **`authority_ordering`** уже кодирует, что серьезную authority может нести только authority-bearing evidence с допустимой role/provenance-комбинацией; projection, packaging, bundle overlays и другие не-authoritative поверхности не могут “вдруг” стать final authority. Это усилено и production invariant registry: `final_owner` обязан быть ровно одним authoritative owner, а projection/dashboard/public-artifact surfaces не могут быть `final_owner`. fileciteturn13file0 fileciteturn11file0 fileciteturn10file0

- **`phase_barriers`** уже задает fail-closed контракты между этапами: для serious profiles barrier record обязан иметь required evidence; `blocked` требует typed blocker; `skipped` не может удовлетворять closeout; `ready_for_scorecard`, final artifact, public artifact и canary bundle читают одну и ту же barrier ledger. В enum перечислены десять именованных барьеров, от canonicalization и legal/data/method backing до scorecard identity, compiler gates и canary closeout. fileciteturn12file0 fileciteturn28file0

- **`same_input_closure`** уже запрещает тихое смешивание разных входных контекстов: envelope несет closure с `closure_sha256`, `run_id`, `job_id`, `tenant_id`, `policy_intent_ref`, `time_context_ref`, legal/data/method refs и mode/degradation refs; все authority-bearing envelopes в одном closeout должны иметь одну и ту же closed identity tuple. Несовпадение поднимается как `same_input_closure_mismatch` или `same_input_closure_not_closed`. fileciteturn13file0 fileciteturn10file0

- **`cas_event_reconciliation`** уже охраняет связность runtime event → CAS → authority envelope: runtime-emitted authority требует CAS-backed ref, `artifact_ref == cas_ref`, CAS ref должен быть в `output_refs`, а scorecard перечисляет `hds_runtime_ref_missing`, `hds_ref_identity_mismatch`, `hds_bundle_ref_used_as_runtime_ref` и `hds_event_reconciliation_failed` как самостоятельные machinery-коды отказа. Это и есть зачаток механизма, который не дает спрятать сбой транспорта/идентичности под “плохой доменный вывод”. fileciteturn13file0 fileciteturn18file0 fileciteturn10file0

- **`terminal_readiness`** уже ограничивает authority-state machine: terminal states — только `approved`, `rejected`, `published_blocked`; `approval_ready` и `published` прямо объявлены projection, а не authority-state; переходы в terminal state зависят от verified scorecard identity, readiness decision и publication policy. Это дает хорошую safety-базу для C24: терминальные authority-решения уже формализованы, но не все их временные свойства. fileciteturn28file0 fileciteturn10file0

Поверх этих пяти инвариантов уже существует более широкий invariant registry: он валидирует shape каждой registry row, маппинг на известные scorecard gates, readiness checks и runtime events, а также требует, чтобы каждый Minimum Closeout Gate был зарегистрирован. Это означает, что C24 должен работать не только на уровне “пяти формальных свойств”, но и на уровне всей machine-readable closeout contract surface. fileciteturn11file0

## Что не покрывают текущие конечные проверки

Главный пробел — **не safety, а liveness**. Текущая finite-state логика хорошо блокирует недопустимые переходы, но почти не говорит, что система обязана сделать **со временем**. В `RunState` есть допустимый цикл `BLOCKED -> EVIDENCE_EMITTING`, а formal invariants не навязывают ни deadline на выход из блокировки, ни bound на количество repair/rerun циклов, ни правило “eventually close or withdraw”. Это значит, что machinery может оставаться формально корректной, но практически бесконечно “крутиться” между блокировкой и частичным восстановлением. fileciteturn28file0

Второй пробел — отсутствие временной политики для **staleness и lifecycle drift**. `projection_semantics.py` уже вводит `stale`, `contested`, `draft`, `blocked`, `publishable`, `projection_only`; scorecard уже знает про continuous governance lifecycle reports (`stale`, `reissue`, `supersede`, `withdraw`). Но из просмотренного кода не видно формального требования вида “если surface стал stale, он обязан быть reissued, superseded или withdrawn в пределах N”; сегодня это скорее наличие surface и report keys, чем liveness-обязательство. Это критично для C24, потому что stale generated surfaces как раз перечислены в плане как не-адверсариальный failure mode. fileciteturn23file0 fileciteturn29file0 fileciteturn30file0

Третий пробел — отсутствие временных гарантий для **repair chains и human-review chains**. Prompt/tool ledger умеет фиксировать `validation_refs`, `repair_decisions`, `authority_handoff_refs` и даже `warn`/`blocked` состояния, а Human Review policy умеет требовать независимость reviewer, separation of duty, minimum time spent и сигнал challenge/dissent. Но из доступных модулей не следует rule вида “warn нельзя держать дольше T без эскалации”, “обязательный human review должен завершиться в SLA”, или “schema healing допускается не более K раз до hard block”. Иначе говоря, есть safety-инструменты, но не policy of progress. fileciteturn17file0 fileciteturn19file0 fileciteturn20file0

Четвертый пробел — слабая формализация промежуточных состояний для **transport/proof layers**. В transportability есть `identified`, `partially_identified`, `bounded_non_identified`, `unsupported`; в proof composability — `reusable`, `revalidate`, `rederive`, `unknown`. Это уже почти готовые soft-gate статусы, но они пока не сведены в единый machine-level lifecycle: например, “частично идентифицировано” и “требует revalidate” — это не жесткий fail, но и не полная authority. C24 как раз должен превратить эти промежуточные состояния в единый soft-gate режим, который ограничивает authority upgrade, но не стирает полезную диагностическую ценность. fileciteturn25file0 fileciteturn26file0

Этот вывод хорошо согласуется с NIST AI RMF и GenAI Profile: NIST прямо подчеркивает, что AI/GAI risks зависят от стадии lifecycle, источника риска, временного масштаба и контекста использования, а risk-management ресурсы следует распределять пропорционально тяжести и вероятности негативных последствий. NIST также требует iterative, documented pre-deployment TEVV и выделяет content provenance, incident disclosure и human-AI configuration как самостоятельные зоны контроля, что прямо поддерживает необходимость отдельного soft-gate lifecycle вместо бинарного pass/fail. citeturn4view0turn8view0turn9view1turn9view2turn9view3

## Self-FMEA модель для adversarial и non-adversarial отказов

Предлагаемая self-FMEA модель должна иметь **первичный ключ не по доменному evidence**, а по **machinery surface**. Иначе acceptance-критерий не выполняется: один и тот же плохой исход можно будет снова списать на “слабую статистику”, “плохую юрисдикцию” или “сложный кейс”, тогда как реальный корень — в authority envelope, barrier routing, transport/proof layer, prompt/parser surface или review governance. Базовая запись FMEA, на мой взгляд, должна включать как минимум: `failure_mode_id`, `machinery_surface`, `authority_level`, `artifact_ref`, `runtime_event_ref`, `root_cause_class`, `authority_failure_code`, `domain_failure_code`, `first_failing_artifact_ref`, `containment_state`, `review_owner`, `repair_path`, `expiry_at`, `override_policy`, `false_block_candidate`, `ceremony_cost_estimate`. Такой дизайн естественно ложится на уже существующие поля `root_cause_class`, `authority_failure_code`, `domain_failure_code`, `first_failing_artifact_ref` и triage-группировку scorecard’а по owner/root-cause/artifact. fileciteturn13file0 fileciteturn18file0

Для **adversarial** отказов я бы рекомендовал следующую каноническую модель. Prompt injection уже частично покрыт negative controls (`source_prompt_injection`, `hidden_token_leakage_attempt`) и sanitize-логикой, а OWASP прямо относит direct и indirect prompt injection к LLM01: они могут вести к unauthorized function access, command execution, biased outputs и manipulation of critical decisions; OWASP также подчеркивает, что fool-proof prevention не существует, поэтому главный дизайн-принцип — ограничивать последствия и регулярно проводить adversarial simulations. Значит, в self-FMEA prompt injection должен моделироваться не только как “security issue”, но и как **machinery capture of downstream authority paths**: заражение prompt/tool ledger, reviewer context, source import, plugin input и public projection. fileciteturn16file0 fileciteturn17file0 citeturn5view0turn5view2turn5view3

**Requester capture** и **critic sandbagging** сегодня явно не закрыты формальным substrate’ом, но их зачатки уже есть: challenge factory выделяет `AMBIGUOUS_HUMAN_REVIEW_INSTRUCTION` как отдельный adversarial class, а HumanReviewRequirement может требовать reviewer independence, separation of duty, minimum time spent и “change request or dissent”. Следовательно, C24 должен моделировать requester capture как failure mode, где downstream reviewer formally present, но behavioral signal показывает low-challenge / rubber-stamp pattern; а critic sandbagging — как систематическое занижение dissent/change-request despite high-risk tier. Иначе human review можно “выполнить”, не создав фактической проверки. fileciteturn22file0 fileciteturn20file0 fileciteturn19file0

**Schema gaming**, **authority spoofing**, **scope inflation**, **proxy laundering** и **false convergence** тоже нужны как отдельные machinery failure modes. Schema gaming уже угадывается в наличии parser contracts, schema validation, repair decisions и scorecard-кодов вроде `hds_schema_incompatible`; authority spoofing прямо отражен в authority roles/provenance и projection restrictions; scope inflation видно в запрете использовать projection для scorecard/runtime closeout authority и в клиентских/offline mutation ограничениях; proxy laundering естественно ложится на transportability proxy-validity и expert-review triggers; false convergence можно привязать к semantic-binding collapse и случаям, где все локально “сходится”, но selected evidence не отражает реальную policy intent or dissent landscape. Для C24 важно, чтобы все эти режимы считались **machinery failures first**, а уже потом, при наличии доказательств, связывались с domain-layer causality. fileciteturn13file0 fileciteturn23file0 fileciteturn27file0 fileciteturn25file0 fileciteturn31file0 fileciteturn16file0 fileciteturn18file0

Для **non-adversarial** отказов код уже почти диктует FMEA-словарь. В scorecard прямо перечислены self-FMEA mandatory modes: `schema_migration_errors`, `partial_case_graphs`, `contradictory_records`, `stale_generated_surfaces`, `operator_workarounds`, `box_ticking_failure`; рядом лежат partial-state и maturity hooks. Добавляя к этому `maturity inflation`, `missing handoffs` и `lifecycle drift`, мы получаем практически полный C24-набор. Особенно важно, что `case_maturity.py` задает строгие maturity levels и required refs для каждого уровня — от `partial` до `validated_ex_post`; значит, maturity inflation должна считаться не “soft quality concern”, а конкретным machinery defect: уровень maturity заявлен выше, чем подтверждают record/argument/evidence/challenge/audit/ex-post refs. fileciteturn30file0 fileciteturn33file0

## Soft-gate lifecycle и план оценки эффективности review

Я предлагаю единый lifecycle для warning-like состояний, который связывает все слои — runtime quality, scientist validation, decision validity, transport/proof, prompt/tool ledger, public projection и dashboard validation:

- **Detected** — surface выдал `warn`, `degraded`, `partially_identified`, `revalidate`, `draft`, `stale`, `contested` или эквивалентный сигнал, и этот сигнал снабжен owner/ref/expiry.  
- **Quarantined** — артефакт разрешен только для diagnostic/projection use; authority ceiling понижен, downstream handoff в claims/scorecard/approval/publication запрещен.  
- **Escalated** — если soft-gate затрагивает высокий authority level, превышает TTL или пересекает trust boundary/human review boundary, он уходит в typed escalation (scorecard owner, reviewer, approver, security, architecture).  
- **Repaired** — есть `repair_decision`, rerun, re-attestation, new same-input closure, revalidation certificate или updated projection lifecycle decision.  
- **Resolved** — soft-gate либо очищен до `pass`, либо повышен в hard block, либо формально downscoped/overridden с сохранением signed exception trail. fileciteturn17file0 fileciteturn25file0 fileciteturn26file0 fileciteturn23file0 fileciteturn30file0

Практический смысл такого lifecycle в том, что он не дает warning-состояниям жить “между мирами”. Например, `TransportabilityStatus.PARTIALLY_IDENTIFIED` и `ProofComposabilityStatus.REVALIDATE` должны быть soft gates для causal/proof authority; `prompt_tool_ledger` со статусом `warn` или applied repair без closed handoff не должен поднимать claim/scorecard/approval authority; `draft`, `redacted`, `projection_only`, `stale` и `contested` должны оставаться допустимыми только для display/audit/explanation surfaces, как прямо требует projection semantics. Это мой главный проектный вывод: soft gate в PolicyOS — это **не слабый pass**, а **ограниченный режим чтения без authority upgrade**. fileciteturn17file0 fileciteturn23file0 fileciteturn25file0 fileciteturn26file0

План review-effectiveness я бы строил на already-present signals и минимально необходимых новых полях. В коде уже есть почти все нужные примитивы: required reviewer count, independence, separation of duty, minimum review time, mandatory change request or dissent, VOI expected value / expected risk reduction / review cost, а в invariant registry один из Minimum Closeout Gates прямо требует calibration evidence по agreement, override correctness, burden, escalation, unresolved disagreement и reviewer attribution. Поэтому набор базовых метрик C24 должен включать: `override_rate`, `median_review_time`, `dissent_rate`, `change_request_rate`, `separation_of_duty_failure_rate`, `reviewer_independence_failure_rate`, `calibrated_agreement`, `override_correctness_rate`, `review_burden_minutes_per_case`, `unresolved_disagreement_backlog`, `reviewer_bias_index` и `sandbagging_index`. Последние два — новый слой поверх существующих полей: bias index измеряет систематическое отклонение reviewer outcomes от peer baseline при контроле risk tier; sandbagging index — долю high-risk reviews без dissent/change request при наличии requirement-а на challenge signal. fileciteturn19file0 fileciteturn20file0 fileciteturn11file0

Это согласуется и с NIST GenAI Profile, где предлагается документировать structured feedback, отслеживать человеческие overrides, делиться результатами pre-deployment testing с release authority, измерять эффективность content provenance controls, включая false positives/false negatives, и мониторить, насколько быстро рекомендации по security/provenance действительно внедряются. Для PolicyOS это означает, что “review effectiveness” нельзя сводить к факту наличия review packet; нужен telemetry loop, показывающий, **изменил ли review траекторию решения**, **какой ценой**, и **без систематической предвзятости ли это произошло**. citeturn9view0turn9view1

## Complexity budget и вывод для acceptance

Complexity budget должен быть отдельным, machine-readable модулем closeout, а не абстрактной “архитектурной рекомендацией”. В коде уже есть достаточные строительные блоки, чтобы его посчитать. Во-первых, Policy Design Case minimum registry содержит 19 minimum record families; во-вторых, phase barriers задают 10 именованных барьеров; в-третьих, trust-boundary registry задает обязательный набор boundary IDs, из которых подмножество должно проходить production attestation; в-четвертых, human review уже использует прямую функцию `expected_value = risk_reduction - review_cost`. Поэтому complexity budget можно формировать как case-level ledger с такими полями: `required_record_count`, `required_gate_count`, `required_attestation_count`, `required_reviewer_minutes`, `estimated_closeout_reruns`, `marginal_assurance_value`, `false_block_rate`, `ceremonial_compliance_risk`, `authority_level_optionality`, `recommended_authority_ceiling`. fileciteturn34file0 fileciteturn12file0 fileciteturn15file0 fileciteturn19file0

Мой рекомендуемый проектный принцип здесь такой: **каждый новый control должен платить rent**. То есть он должен либо уменьшать конкретный risk/authority exposure, либо сокращать downstream recovery cost, либо повышать auditability/provenance fidelity; если этого нет, контроль должен помечаться как ceremonial candidate. Для этого marginal value нужно считать не как абстрактный score, а как разницу между ожидаемым снижением риска и дополнительным case burden — в духе уже существующего VOI-подхода к human escalation. А `false_block_rate` следует оценивать по доле блокировок, которые позже были сняты без изменения underlying authority artifact; это отличный индикатор, что control бьет по workflow, но не добавляет assurance. NIST прямо рекомендует измерять reliability content-authentication/provenance methods и отслеживать false positives/false negatives, что хорошо ложится на эту конструкцию. fileciteturn19file0 citeturn9view1turn8view0

В терминах acceptance я бы сформулировал итог так. Чтобы “case-machinery failures cannot be hidden as domain evidence failures”, каждый blocking и soft-gate event должен в обязательном порядке нести split между `authority_failure_code` и `domain_failure_code`, плюс `root_cause_class`, `first_failing_artifact_ref` и `machinery_surface`; а scorecard/operator triage должен группировать сбои именно по этим полям. Чтобы “the assurance system can identify when it is too costly or ceremonial”, каждый case должен иметь complexity ledger, где сравниваются authority level, required controls и их marginal value; если marginal value отрицателен или ceremonial-compliance risk растет быстрее, чем assurance, система должна либо downscope authority, либо убрать optional controls, либо перевести часть требований в diagnostic-only regime. Это не отменяет fail-closed барьеры; наоборот, это отделяет **необходимую жесткость** от **дорогой имитации rigor-а**. fileciteturn13file0 fileciteturn18file0 fileciteturn19file0 fileciteturn28file0 citeturn8view0turn9view1

## Открытые вопросы и ограничения

В ходе чтения репозитория я не нашел напрямую доступного модуля `decision_validity.py`, поэтому часть предложений по soft-gate lifecycle для decision-validity слоя я вывел по соседним поверхностям — `projection_semantics`, `transportability`, `proof_composability`, scorecard statuses и continuous-governance hooks. Это высокий по уверенности architectural inference, но не прямое чтение конкретного файла.

Вторая оговорка: GitHub connector в этой сессии отдавал содержимое файлов с file-citation marker’ами уровня файла, а не построчным line-range quoting, поэтому repo-citations указывают на конкретные файлы, а не на узкие диапазоны строк. Для исследовательского синтеза этого достаточно, но для последующей спецификации C24 в PR лучше будет сделать line-level anchors уже внутри самого репозитория.

Третья оговорка: исследование опирается на кодовые контракты и официальные внешние guidance-источники, но не на реальные runtime telemetry dumps. Поэтому предложенные метрики review-effectiveness и complexity budget — это проектная схема, хорошо согласованная с кодом, а не эмпирический отчет по уже собранным данным.

# Исследование по C20 для PolicyOS

В полном active-плане `POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md` задача C20 сформулирована как превращение Policy Design Case из «замороженного мемо» в живой объект, для которого новые доказательства, дрейфы и invalidation-события должны однозначно отображаться на затронутые claims, записи, экспорты и публичный статус. Ниже я опираюсь на уже существующие контракты репозитория и предлагаю схему, которая естественно продолжает их, а не начинает с нуля. fileciteturn10file0L3-L3 fileciteturn17file0L3-L3 fileciteturn37file0L3-L3

## Что уже есть в кодовой базе

В репозитории уже реализована значительная часть «живого» контура. На уровне claim spine есть `ClaimRecord` и `ClaimLedger`, где claim уже несет `evidence_refs`, `counterevidence_refs`, `provenance_ref`, `reviewer_refs`, `source_attribution`, `readiness_level` и `publishability`. На уровне v2 появился `AppendOnlyClaimLedger` и `ClaimLifecycleEvent`, то есть claim-история уже мыслится как append-only sidecar, а не как редактируемый объект. Это очень сильная база для C20: в PolicyOS уже принято, что исторические артефакты не переписываются, а новые состояния добавляются событиями. fileciteturn18file0L3-L3 fileciteturn19file0L3-L3 fileciteturn20file0L3-L3

То же видно в правилах переходов. `validate_claim_transition(...)` запрещает тихое удаление или понижение publishable-claim без явного lifecycle-action; тесты отдельно фиксируют, что publishable claim нельзя «снять» без блокировки, invalidation, supersede или review-следа. Diff и export-слой уже умеют выделять `changed_support_claim_ids`, `changed_readiness_claim_ids`, `blocked_claim_ids`, `superseded_claim_ids`, `silent_publication_regression_claim_ids`, а публичный экспорт уже скрывает blocked/internal claims, но reviewer/machine-экспорты сохраняют их видимость. То есть acceptance-критерий C20 в части «не потерять след» уже частично реализован. fileciteturn20file0L3-L3 fileciteturn21file0L3-L3 fileciteturn22file0L3-L3 fileciteturn44file0L3-L3 fileciteturn45file0L3-L3 fileciteturn46file0L3-L3

Второй важный уже существующий слой — Research DAG. Его узлы и ребра несут `artifact_refs`, `claim_ids`, `node_type`, `edge_type`; invalidation-механизм умеет валидировать, что `source_ref` действительно существует в DAG, находить downstream nodes, вычислять `stale_claim_ids`, а затем автоматически порождать `MARKED_STALE` или `INVALIDATED` lifecycle-события для затронутых claims. Иными словами, связь «источник → DAG-линия → claim» в системе уже существует. fileciteturn56file0L3-L3 fileciteturn29file0L3-L3 fileciteturn47file0L3-L3

Третий слой — continuous governance. В нем уже есть публичные статусы decision artifact: `valid`, `monitoring`, `stale`, `review_required`, `superseded`, `reissued`, `withdrawn`; есть typed monitor events для `source_invalidation`, `calibration_drift`, `fairness_drift`, `policy_context_drift`, `incident`; есть рекомендации `continue_monitoring`, `mark_stale`, `human_review`, `reissue`, `withdrawal_review`; есть runtime-owned authority evidence, reissue packets и withdrawal records. В Policy Design Case runtime-quality слое отдельно уже валидируются `implementation_monitoring_evaluation`, `case_lifecycle` и `ex_post_learning`, а тесты фиксируют, что published case со статусом `stale` без resolution должен блокироваться scorecard’ом. fileciteturn27file0L3-L3 fileciteturn28file0L3-L3 fileciteturn37file0L3-L3 fileciteturn38file0L3-L3 fileciteturn39file0L3-L3 fileciteturn51file0L3-L3 fileciteturn52file0L3-L3 fileciteturn54file0L3-L3

Главный вывод из этого состояния такой: для C20 не нужен новый «центр мира». Нужен единый **dependency-and-revalidation graph**, который склеит уже существующие claim-ledger, Research DAG, DDM monitoring, case lifecycle и public export surfaces вокруг стабильных идентификаторов `case_id` и `claim_id`. fileciteturn17file0L3-L3 fileciteturn20file0L3-L3 fileciteturn29file0L3-L3 fileciteturn54file0L3-L3

## Архитектурный вывод для C20

Лучшая концептуальная форма для C20 — это не «таблица состояний кейса», а **ориентированный граф зависимостей с append-only revalidation-event history**. Такой подход хорошо совпадает и с текущей внутренней архитектурой PolicyOS, и с внешними стандартами provenance. W3C PROV определяет provenance как сведения об entities, activities и agents, поддерживает `used`, `wasGeneratedBy`, `wasDerivedFrom`, versioning и explicit invalidation/influence relations. Это почти идеальный внешний словарь для того, чтобы превратить Policy Design Case в живой объект без потери аудируемости. fileciteturn20file0L3-L3 fileciteturn29file0L3-L3 citeturn3view0turn4view1

На практике это означает, что claim должен стать минимальной стабильной единицей зависимости, а не только текстом в `ClaimRecord`. Сегодня claim уже знает свои evidence refs и reviewer refs, Research DAG уже знает свои `claim_ids`, а runtime-quality для Policy Design Case уже требует, чтобы DDM events содержали `affected_claim_ids` и `affected_evidence_line_refs`. Следовательно, правильное направление — не изобретать новый объект над claim’ом, а сделать **claim-centered back-pointer spine**, через который любой триггер всегда может пройти назад к доказательствам и вперед к затронутым публикационным поверхностям. fileciteturn19file0L3-L3 fileciteturn56file0L3-L3 fileciteturn52file0L3-L3

С точки зрения управления риском это также правильно. NIST AI RMF прямо исходит из того, что AI-системы функционируют в контексте данных и среды, которые меняются со временем, а риск-менеджмент должен быть непрерывным и выполняться на протяжении всего жизненного цикла. Framework также выделяет fairness как отдельную trustworthiness-характеристику и требует continuously applying MAP/MEASURE/MANAGE по мере изменения контекста и рисков. Для Policy Design Case это означает, что staleness и revalidation нельзя ограничивать только source freshness; они должны охватывать и performance drift, и fairness drift, и социально-контекстные изменения. citeturn7view2turn7view4turn7view0

## Предлагаемый граф зависимостей и обратных ссылок

Я рекомендую строить C20 как единый граф из восьми типов узлов: **source authority**, **research lineage**, **evidence line**, **claim**, **runtime monitor event**, **case record**, **governance record**, **public projection**. Уже существующие контракты почти полностью покрывают эти роли: source/lineage отражены в Research DAG, claim — в Claim Ledger, monitor/event — в continuous governance и DDM monitoring, case record — в `implementation_monitoring_evaluation`, `case_lifecycle`, `ex_post_learning`, governance record — в `DecisionValidityReport`, `ReissuePacket`, `WithdrawalRecord`, public projection — в claim/public exports и public validity report. fileciteturn56file0L3-L3 fileciteturn20file0L3-L3 fileciteturn39file0L3-L3 fileciteturn52file0L3-L3 fileciteturn54file0L3-L3

Практически graph должен материализовать следующие обязательные обратные ссылки для каждого claim:

| Узел claim должен хранить ссылку назад на | Зачем это нужно |
| --- | --- |
| `evidence_line_refs` | Точное попадание в строку/сниппет/табличную ячейку, а не только в artifact целиком |
| `source_refs` и `source_snapshot_refs` | Различать «тот же источник, но новая версия» и «новый источник» |
| `research_node_ids` и `research_edge_ids` | Локализовать replay/invalidation до подграфа |
| `monitor_event_ids` | Понимать, какие runtime-сигналы понизили уверенность или изменили публикационный статус |
| `case_record_refs` | Показывать, какие implementation/ex-post/lifecycle записи этот claim питают |
| `public_projection_refs` | Позволять acceptance-критерию C20 ответить, какие публичные surfaces должны быть помечены, скрыты или перевыпущены |

С точки зрения модели provenance это естественно: claim становится `generated entity`, evidence line и source — `used entities`, research step — `activity`, reviewer/runtime — `agent`, а revalidation event — новым activity, который либо подтверждает, либо помечает, либо инвалидирует claim. PROV-DM прямо поддерживает такой паттерн через `used`, `wasGeneratedBy`, `wasDerivedFrom` и explicit influence/invalidation relations. citeturn4view1turn4view3

Внутри PolicyOS это лучше всего оформить не как размножение полей в `ClaimRecord`, а как отдельный append-only sidecar наподобие `ClaimLifecycleEvent`, например `ClaimDependencyEdge`. Он должен иметь как минимум: `edge_id`, `case_id`, `claim_id`, `relation_type`, `source_ref`, `target_ref`, `scope`, `created_at`, `actor_id`, `reason`, `metadata`. Тогда при любом revalidation-trigger система сможет выполнить один и тот же алгоритм: найти seed-узел, пройти downstream по edges до `claim_id`, затем от `claim_id` пройти дальше к `case_record_refs`, `governance_record_refs` и `public_projection_refs`. Это и будет искомый lifecycle dependency and revalidation graph. fileciteturn20file0L3-L3 fileciteturn29file0L3-L3 fileciteturn54file0L3-L3

Текстовая схема целевого графа выглядит так:

```text
Source / Legal Authority / Data Feed
  -> ResearchDAG Node / Edge
  -> Evidence Line / Snippet / Table Cell
  -> ClaimRecord
  -> ClaimLifecycleEvent
  -> Policy Design Case records
       - implementation_monitoring_evaluation
       - case_lifecycle
       - ex_post_learning
  -> Governance sidecars
       - validity_report
       - reissue_packet
       - withdrawal_record
  -> Public projections
       - public claim export
       - public validity report
       - published case page / bundle
```

Именно эта структура закрывает acceptance C20: любой новый факт или drift сначала находит affected claims, затем affected records, затем affected exports, и только после этого вычисляется public status. fileciteturn22file0L3-L3 fileciteturn39file0L3-L3 fileciteturn54file0L3-L3

## Триггеры устаревания и переходы жизненного цикла

Ниже — предлагаемая матрица триггеров. Я держу ее максимально совместимой с текущими enums и sidecars: там, где в коде уже есть готовый статус, я использую его; там, где кода пока нет, я предлагаю минимальное расширение, а не новый параллельный контур. Текущая кодовая база уже знает `MARKED_STALE`, `INVALIDATED`, `BLOCKED`, `SUPERSEDED`, `REVIEWED`, `REISSUED`, `WITHDRAWN` как claim- или case-level consequence; source invalidation уже переводится в `MARKED_STALE` или `INVALIDATED`, drift warnings — в `human_review`, drift blocks — в `reissue`, а block-level incident — в `withdrawal_review`. fileciteturn20file0L3-L3 fileciteturn27file0L3-L3 fileciteturn37file0L3-L3 fileciteturn48file0L3-L3

| Триггер | Что считать seed-узлом | Действие на claim | Действие на кейс и public status |
| --- | --- | --- | --- |
| Новое evidence, усиливающее claim | `evidence_line_ref` / `source_ref` | `updated_support` или `reviewed` | Если кейс уже опубликован, не `reissued` автоматически; сначала `review_required`, затем scoped reissue |
| Новое counterevidence | `evidence_line_ref` | `blocked` или `invalidated` в зависимости от силы и опровержения | `review_required`; при high-severity — `stale` или `withdrawn` после review |
| Юридическое изменение | `legal_authority_ref` / `policy_context_drift` subtype | Для `legal`-claims по умолчанию `marked_stale`; при repeal/contradiction — `invalidated` | `review_required`; при затрагивании опубликованной рекомендации — scoped reissue |
| Source invalidation: `stale` / `unavailable` | `source_ref` | уже совместимо с `MARKED_STALE` | case `stale`; публично сохраняем видимость, но с баннером о stale |
| Source invalidation: `withdrawn` / `contradicted` | `source_ref` | уже совместимо с `INVALIDATED` | `review_required`, затем `reissue` или `withdrawn` |
| Calibration drift | `monitor_event_id` + `affected_claim_ids` | для предиктивных/forecast claims — `review_required`; hard-threshold может вести к `blocked` | warning = `review_required`, block = candidate for `reissued` |
| Fairness drift | `monitor_event_id` + subgroup evidence | для distributional/welfare/implementation claims — `review_required`, hard failure = `blocked` | как и в current continuous governance: warning-review, block-reissue |
| Participation drift | новый `participation_drift` event или subtype у `policy_context_drift` | для normative/distributional claims — `review_required`; при срыве legitimacy-threshold — `blocked` | public posture не должен оставаться `valid`, если representative participation просела ниже policy floor |
| Implementation incident | `incident_id` / `monitor_event_id` | для implementation claims — минимум `blocked`; для causal/legal claims — по scope | case `review_required`; block-level incident может вести к `withdrawal_review` |
| DDM root cause bundle | `root_cause_event_id` | не должен менять статус сам по себе; он уточняет scope и severity | enriches triage, связывает incident/degradation с конкретными claims и evidence lines |
| Ex-post refutation | `observed_outcome_ref` / `reassessment_ref` | `invalidated`, `superseded` или `reviewed` с `refuted` outcome | case не может оставаться quietly published; нужен resolution event |

Эта матрица согласуется и с внешней литературой. Для drift’ов важен не только сам факт смены распределения, но и процедура **detection → understanding → adaptation**; именно это подчеркивает обзор по concept drift. Для fairness важна именно runtime-перспектива, потому что динамика среды и поведения людей может делать систему unfair уже после корректного design-time анализа. Поэтому для C20 fair/participation drift должны быть не декоративными сигналами, а полноценными revalidation-triggers. citeturn0academia0turn8academia1turn7view2

Для DDM-root-cause я бы зафиксировал особенно важное правило: `root_cause_events` не должны напрямую объявлять claim invalid. В текущем Policy Design Case runtime-quality они уже обязаны существовать как причинная опора для incident-events, а incident-events обязаны ссылаться на `root_cause_event_ids`. Значит, root cause в C20 должен выполнять роль **scoping and attribution artifact**, а не статусного триггера; статус должен менять degradation/readiness/incident signal, уже обогащенный root cause bundle. Это делает граф чище и предотвращает дублирование жизненного цикла. fileciteturn52file0L3-L3 fileciteturn34file0L3-L3 fileciteturn33file0L3-L3

## Частичный перевыпуск и runtime-owned записи

Самый заметный пробел относительно C20 — **partial-scope reissue пока скрыт в имплицитности**. `ReissuePacket` уже связывает `original_decision_packet_ref`, `new_decision_packet_ref`, `original_claim_ledger_ref`, `new_claim_ledger_ref`, `new_evidence_refs`, `monitor_event_refs`, `human_review_ref` и `status`; но в нем нет first-class полей для `affected_claim_ids`, `unchanged_record_refs`, `superseded_record_refs`, `public_diff_ref` и `publication_state_before/after`. Из-за этого scope reissue сегодня можно вывести косвенно, но нельзя безопасно и детерминированно читать как самостоятельный контракт. fileciteturn28file0L3-L3 fileciteturn42file0L3-L3

Я рекомендую сделать partial-scope reissue first-class. Минимальное расширение уже существующего `ReissuePacket` должно включать пять новых полей: `affected_claim_ids`, `unchanged_claim_ids`, `unchanged_record_refs`, `superseded_record_refs`, `public_diff_ref`. В этом случае current `diff_claim_ledgers(...)` становится вычислительным ядром перевыпуска: `affected_claim_ids` = union из `added_claim_ids`, `removed_claim_ids`, `changed_claim_ids`, `blocked_claim_ids`, `superseded_claim_ids`, `counterevidence_changed_claim_ids`, `reviewer_attribution_changed_claim_ids`; `unchanged_claim_ids` и `unchanged_record_refs` считаются как complement относительно прежнего case graph. Это естественно продолжает уже существующий diff-контракт вместо изобретения второй, параллельной diff-системы. fileciteturn21file0L3-L3 fileciteturn45file0L3-L3

Публичная сторона partial reissue должна вести себя так: старый опубликованный кейс **не исчезает**, а остается доступным как superseded/stale record; затронутые claims получают явные superseded или invalidated refs; public bundle показывает `public_diff_ref`, который безопасно перечисляет только изменившиеся claims, изменения support/readiness/publication posture и ссылку на новый кейс. Этот принцип уже полностью совместим с текущей логикой экспорта, где reviewer/machine-экспорты сохраняют blocked/superseded claims, а public validity reports уже умеют отдавать очищенное наружу представление без внутренних refs. fileciteturn22file0L3-L3 fileciteturn39file0L3-L3 fileciteturn46file0L3-L3

Для runtime-owned lifecycle records я бы фиксировал обязательный набор из семи записей. Во-первых, `AppendOnlyClaimLedger`; во-вторых, case-level `case_lifecycle`; в-третьих, `DecisionValidityReport`; в-четвертых, `ReissuePacket`; в-пятых, `WithdrawalRecord`; в-шестых, `implementation_monitoring_evaluation`; в-седьмых, `ex_post_learning`. Но для C20 я бы добавил еще одну missing record: **`RevalidationRunRecord`**. Это должна быть immutable runtime-owned запись, которая склеивает trigger, affected claims, affected records, old refs, new refs, resolution, public diff и authority evidence в один auditable execution unit. Именно ее сейчас не хватает, чтобы acceptance-критерий «от drift перейти к claims, records, exports и public status» закрывался в одну операцию чтения. fileciteturn23file0L3-L3 fileciteturn27file0L3-L3 fileciteturn28file0L3-L3 fileciteturn38file0L3-L3 fileciteturn52file0L3-L3 fileciteturn54file0L3-L3

`RevalidationRunRecord` должен эмитироваться тем же доверенным runtime-контуром, что и нынешние governance lifecycle records, то есть иметь `runtime_event_ref`, authority envelope, immutable CAS-ref и lineage inputs. Уже существующий `emit_governance_lifecycle_evidence(...)` показывает правильный шаблон: lifecycle decision получает report ref, diagnostic event ref, authority envelope ref, payload hash и runtime ref key. Для C20 лучше всего не придумывать новый способ «владения» жизненным циклом, а распространить именно этот authority-bearing pattern на весь контур revalidation. fileciteturn27file0L3-L3 fileciteturn48file0L3-L3

## Итоговая рекомендация и ограничения

Если свести исследование к короткому инженерному выводу, он такой: **Policy Design Case уже почти стал living object, но пока еще не имеет единого claim-centered revalidation graph и first-class scoped reissue contract**. Чтобы C20 был действительно закрыт, достаточно трех вещей: обязательных claim-to-evidence back-pointers до evidence lines и DAG lineage; отдельного append-only `RevalidationRunRecord`; и явного partial-scope extension для `ReissuePacket`. Все остальное в репозитории уже в значительной степени готово — append-only lifecycle, source invalidation bridge, continuous governance statuses, DDM-to-claim wiring и case lifecycle validation. fileciteturn20file0L3-L3 fileciteturn29file0L3-L3 fileciteturn37file0L3-L3 fileciteturn51file0L3-L3 fileciteturn52file0L3-L3 fileciteturn54file0L3-L3

Есть и несколько открытых вопросов. В текущем `MonitorEventType` нет first-class `participation_drift`, а legal changes пока логичнее всего выражаются как subtype внутри `policy_context_drift`; если для проекта важно различать их на уровне compliance и UI, enum придется расширять. Кроме того, `ReissuePacket` сейчас не выражает scope перевыпуска явно, а DDM bridge в Policy Design Case runtime-quality уже валидируется на уровне record-contracts, но из доступных мне материалов не видно полного end-to-end auto-bridge из `DDMWindowResult` в continuous governance event emission именно для Policy Design Case. Поэтому эти две зоны я считаю главными структурными пробелами, а не просто «улучшениями на будущее». fileciteturn27file0L3-L3 fileciteturn28file0L3-L3 fileciteturn32file0L3-L3 fileciteturn52file0L3-L3

В целом же high-confidence answer такой: **C20 следует реализовывать не как отдельный case-lifecycle модуль, а как unified dependency/revalidation graph, где claim_id — центральный ключ, RevalidationRunRecord — центральное событие, а Policy Design Case — центральная проекция этого графа в reviewer/public surfaces**. Это решение и концептуально наиболее чистое, и максимально совместимо с тем, что в `polisyos` уже реализовано. fileciteturn10file0L3-L3 fileciteturn20file0L3-L3 fileciteturn54file0L3-L3 citeturn4view1turn7view4

# C19 Participation Provenance And Attribution For PolicyOS

Задача C19 в активном плане PolicyOS сформулирована как требование прекратить спекуляции о предпочтениях, легитимности и позициях затронутых людей и заменить их проверяемой схемой provenance участия. Внутри текущей архитектуры это не должна быть новая «параллельная» сущность: план прямо требует reuse-first подход, а существующие опорные поверхности уже включают claim registry с `provenance_ref` и `source_attribution`, обязательное семейство записей `structured_judgement_and_consultation.v1`, аудиторию-специфичные экспорты, public-export guardrails и human-review пакеты. Следовательно, лучший дизайн для C19 — это typed participation provenance, который связывается с существующими `ClaimRecord`, PDC record families, public projections и governance review, а не живет отдельным произвольным JSON-блоком. fileciteturn28file0L3-L3 fileciteturn36file0L3-L3 fileciteturn12file0L3-L3 fileciteturn25file0L3-L3

Уже сейчас PolicyOS различает publishability и блокировки на уровне claims, требует общий `trust_provenance` для audience-tier exports, скрывает blocked claims из публичного слоя, запрещает public projections «mint authority» и ограничивает public export режимом redacted/projection-only. Human review уже имеет собственные refs на evidence bundle, governance report, signatures и release-control. Это означает, что participation provenance должен влиять не только на сбор фактов, но и на admissibility, audience redaction, block/limitation semantics и release governance. fileciteturn20file0L3-L3 fileciteturn21file0L3-L3 fileciteturn23file0L3-L3 fileciteturn10file0L3-L3 fileciteturn11file0L3-L3 fileciteturn30file0L3-L3

## Контекст внутри текущей архитектуры

План Universal Policy Design Case Research Plan описывает целевую архитектуру как universal policy grammar с typed fields, admissibility rules, provenance, contestability и lifecycle dependencies, а не как генератор правдоподобных меморандумов. В dense context отдельно зафиксировано, что claim registry уже должен связывать major claims с requirements, data refs, norms, methods, arguments, warrants, rebuttals, counter-evidence, limitations и blockers. Для C19 это важно: provenance участия не может быть просто «меткой источника»; он должен быть частью той же доказательной цепочки, что и остальные claim-bearing facts. fileciteturn36file0L3-L3

На уровне record registry в PolicyOS уже зафиксировано, что `structured_judgement_and_consultation.v1` входит в минимальные обязательные Policy Design Case record families. Это особенно важно, потому что acceptance для C19 звучит не как «желательно хранить provenance», а как обязательный gate: affected-person claims должны иметь participation provenance или typed limitation/blocker. Встраивание в существующее семейство record families делает этот gate естественным продолжением текущего closeout-режима, а не специальным исключением. fileciteturn25file0L3-L3 fileciteturn28file0L3-L3

На уровне claims уже есть подходящие точки привязки. `ClaimRecord` хранит `provenance_ref`, `source_attribution`, `reviewer_refs`, `blocked_reasons` и требует evidence refs для publishable high-stakes claim families. Это значит, что для C19 не нужен новый claim subsystem; нужен новый typed provenance artifact, на который claim сможет ссылаться через `provenance_ref`, а публичные и reviewer-экспорты будут уже наследовать нужную release-логику. fileciteturn12file0L3-L3

На уровне внешних поверхностей PolicyOS уже разложен по аудиториям. Decision-grade export компилируется в tiers `public_summary`, `reviewer_packet`, `expert_appendix` и `machine_export`; все аудитории должны происходить из одного claim ledger и одного research DAG; public layer обязан иметь `trust_provenance`, а public omissions не могут тихо скрывать blocked claims. Отдельно projection semantics и public export bundle прямо запрещают использовать публичную проекцию как approval/scorecard/claim authority и навязывают redacted/projection-only режим. Это очень хорошая база для C19: provenance участия должен детерминировать, что именно можно публиковать публично, что должно остаться reviewer-only, и как обозначать gaps без раскрытия чувствительных деталей. fileciteturn20file0L3-L3 fileciteturn21file0L3-L3 fileciteturn23file0L3-L3 fileciteturn10file0L3-L3 fileciteturn11file0L3-L3

Наконец, C12 в том же плане уже задает критически важную границу: LLM content не может становиться stakeholder preference без producer validation. Поэтому C19 должен не просто перечислять source kinds, а явно типизировать `llm_speculation` как non-authoritative candidate source, который не может удовлетворять affected-person claim без внешней participation evidence. fileciteturn27file0L3-L3 fileciteturn36file0L3-L3

## Операционные определения и различение источников

Для C19 ключевая проектная идея такова: **consultation mode** и **source kind** нужно кодировать раздельно. EPA различает уровни участия `inform`, `consult`, `involve`, `collaborate`, `empower`, а также подчеркивает, что public participation — это процесс, а не единичное событие, и что «публика» состоит из множества stakeholder groups с разными интересами и позициями. Следовательно, режим участия отвечает на вопрос «какую роль людям дали в процессе», а source kind — «какой именно артефакт был собран». citeturn29view2turn31view0

Из этого следует базовая терминология для PolicyOS. **Affected group mapping** — это не произвольный список «стейкхолдеров», а формализованное соответствие между claim и группами, которых политика затрагивает напрямую, косвенно, как исполнителей, как регулируемых субъектов, как население риска или как уязвимые/маргинализированные группы. EPA прямо рекомендует собирать input из широкого спектра stakeholder interests и отдельно учитывать vulnerable/marginalized populations; без этого утверждение о «предпочтениях затронутых людей» в буквальном смысле не имеет определенного референта. citeturn29view2turn31view0

**Representativeness** в рамках C19 должна быть типизированной, а не бинарной. Лучший рабочий набор классов для PolicyOS выглядит так: `statistical_representative`, `quota_or_stratified_representative`, `stakeholder_coverage_representative`, `open_self_selected`, `unknown`. Европейская Комиссия прямо пишет, что public consultation не дает репрезентативного вида населения ЕС и что weighting обычно не рекомендуется для данных публичных консультаций; если нужны representative views, следует использовать survey-type инструменты, например Eurobarometer. В то же время European Citizens’ Panels построены на случайном наборе, квотах и стремлении отражать socio-demographic composition. Следовательно, панель, опрос и открытая консультация не должны попадать в одну и ту же representativeness bucket. citeturn17view0turn28view0turn28view1turn28view2

**Verification** должен покрывать минимум четыре слоя: проверяемость происхождения артефакта, проверяемость процедуры набора/участия, проверяемость инструмента сбора и проверяемость обработки/сводки. AAPOR требует раскрывать стратегию сбора, инструменты, формулировки вопросов/гидов для интервью и фокус-групп, определение изучаемой популяции, способ генерации и рекрутинга sample, mode, dates, sample sizes, weighting, data processing и общие ограничения, чтобы обеспечить независимую проверку claims. Для PolicyOS это означает, что provenance участия недостаточен, если в нем нет trace до инструмента, population definition и processing notes. citeturn14view0turn13view2

**Aggregation** тоже должна быть typed. Европейская Комиссия различает survey и public consultation и требует объяснять methodologies and tools, включая weighting, если он применялся; synopsis report должен документировать каждую consultation activity, дифференцировать views разных stakeholder categories и объяснять, почему некоторые suggestions не были приняты. Значит, participation provenance должен уметь явно различать по крайней мере `prevalence_estimate`, `thematic_synthesis`, `formal_consultation_summary`, `deliberative_recommendation`, `administrative_record_extract`. Без типизации агрегирования система будет постоянно путать «сколько людей так считают» с «какие позиции были высказаны». citeturn17view0turn17view1

**Dissent** нельзя прятать в общий summary field. EPA подчеркивает, что sponsor agency работает не с «одной публикой», а с диапазоном views and concerns, а Commission требует differentiating the views of different categories of stakeholders и объяснять, почему suggestions were not taken up. Поэтому dissent должен быть first-class элементом participation provenance: minority positions, unresolved objections, categories of disagreement, response status, explanation status. Это сближает C19 с C17 contestability, но не смешивает их: C19 отвечает за provenance disagreement input, а C17 — за общую formalism disagreement in the case. citeturn29view2turn17view1

Ниже — предлагаемое практическое различение source kinds, синтезированное из AAPOR, EU Better Regulation, EPA и текущих границ PolicyOS. citeturn14view0turn17view0turn17view1turn28view2turn31view0turn29view2 fileciteturn27file0L3-L3

| Source kind | Что это такое | Что может подтверждать | Что не должно подтверждать без дополнительной опоры |
| --- | --- | --- | --- |
| `survey` | Структурированный инструмент с явно описанной популяцией, sample design, dates, mode, weighting и processing | Распределение предпочтений, self-reported harms, attitude prevalence | Deliberated judgment, process legitimacy сама по себе |
| `deliberative_panel` | Случайно/квотно набранная и фасилитированная группа, работающая в малых группах и plenary и выдающая recommendations | Reasoned recommendations, informed tradeoffs, surfaced dissent | Популяционные проценты вида “X% affected people support…” |
| `testimony` | Индивидуальный или организационный formal comment/statement, часто в hearing/public meeting и потенциально в public record | Наличие позиции, аргумента, конкретного operational or lived-experience concern | Частотность, репрезентативность, «воля затронутых» |
| `consultation_summary` | Sponsor-authored synthesis нескольких consultation activities | Что было собрано, какие группы участвовали, какие темы/позиции возникли, что было учтено | Статистическую prevalence claim без исходной методологии |
| `agency_record` | Официальный административный record или опубликованный synopsis/report о consultation process | Проверяемый факт того, что поступило и как это обработано | Предпочтения населения без подлежащих participation methods |
| `individual_quote` | Отдельная qualitative quotation из интервью, фокус-группы, testimony или comments | Иллюстрацию конкретного взгляда или harm narrative | Обобщение до группы, prevalence или legitimacy |
| `llm_speculation` | Сгенерированный кандидатом текст без external participation evidence | Только prompt/candidate provenance, research prompt gap | Любое affected-person preference, legitimacy, lived harm или contestability claim |

## Минимальная планка доказательности по типам утверждений

Ниже — не описание уже существующей схемы, а проектное предложение для того, как C19 должен проводить admission control. Оно опирается на то, что Commission различает consultation и survey, AAPOR задает минимальную disclosure-рамку для quantitative и qualitative research, EPA требует широкий stakeholder coverage и объяснение того, как concerns были учтены, а PolicyOS уже умеет публиковать limitations/blockers и routing через review/public export. citeturn17view0turn17view1turn14view0turn29view2turn31view0turn21view1 fileciteturn12file0L3-L3 fileciteturn20file0L3-L3 fileciteturn23file0L3-L3

Для **preference claims** минимальная планка должна быть самой строгой. Если claim звучит как распределение предпочтений или предполагаемая воля affected group, допустимыми базовыми источниками должны быть survey с прозрачной sample methodology или deliberative panel, но только для claims о reasoned recommendations, а не о частоте мнений. Открытая public consultation, testimony, individual quotes и consultation summaries могут подтверждать существование некоторых позиций, но не их prevalence. Если source kind — open self-selected consultation, runtime должен разрешать формулировки типа «в процессе консультации были высказаны следующие concerns», но блокировать формулировки типа «affected people prefer X». Это прямо вытекает из разграничения Commission между survey и public consultation и из AAPOR disclosure standards. citeturn17view0turn14view0

Для **legitimacy claims** нужны не проценты, а свойства процесса. Минимум должен включать: affected group map; consultation mode; timing относительно policy design; сведения о том, какие группы были приглашены и какие не были охвачены; описание consultation strategy; differentiated views by stakeholder category; explanation of how input was considered; public synopsis or authoritative record; и governance review status. Легитимность нельзя выводить ни из одной survey table, ни из одного panel outcome: это claim о качестве, охвате и прозрачности участия. EPA и Commission оба подчеркивают обязанность agency/Commission объяснять, как diverse concerns были рассмотрены и почему часть suggestions не была принята. citeturn29view2turn17view1turn15view0

Для **implementation feasibility claims** provenance участия должен быть role-sensitive. Если утверждается, что мера реализуема, то participation evidence должна включать frontline implementers, administrators, regulated entities или их credible representative bodies, а не только общих граждан. Необходимы организационный контекст, роль участников, mode of collection, operational constraints raised, unresolved objections и verification of who actually spoke from implementation vantage point. EPA прямо связывает public input с более implementable decisions, но это не разрешение ссылаться на абстрактную «публику» вместо исполнителей. citeturn29view2turn31view0

Для **contestability claims** provenance должен содержать не только положительные рекомендации, но и objections pipeline: кто возражал, в каком качестве, в каком формате, по каким основаниям, были ли возражения разрешены, частично приняты, отклонены или оставлены открытыми. Commission требует differentiating views and explaining why certain suggestions could not be taken up, а EPA подчеркивает необходимость отражать обратно, как diverse concerns were considered. Поэтому contestability provenance должен поддерживать поля `objection_category`, `resolution_status`, `response_ref`, `public_feedback_status`. citeturn17view1turn29view2

Для **harms claims**, если они опираются на input affected people, provenance должен жестко различать narrative evidence и prevalence evidence. Индивидуальная testimony или quote может быть достаточной для claim вида «существует диагностированный риск/опыт вреда типа H», но недостаточной для claim вида «группа G в целом понесет вред H с такой-то частотой». Для population-scale harm claims нужны survey/admin data или явная triangulation. Кроме того, harm evidence почти всегда повышает privacy risk, поэтому нужен отдельный privacy/release state и, при необходимости, human review. ICO прямо указывает, что anonymisation должна оцениваться с учетом re-identification risk, external sources and motivated intruder scenarios, а PolicyOS уже имеет privacy compliance и human review surfaces. citeturn21view0turn21view1turn21view3 fileciteturn32file0L3-L3 fileciteturn30file0L3-L3

Практически это означает простое правило для admission control: **source kind определяет максимально допустимую силу обобщения**. Survey может поддерживать prevalence; deliberative panel — reasoned recommendation and tradeoff judgment; testimony и quote — existence of concern or experiential narrative; consultation summary и agency record — process transparency and categorized input; LLM speculation — только research candidate, никогда не participation authority. citeturn14view0turn17view0turn28view2turn31view0 fileciteturn27file0L3-L3

## Предлагаемая схема происхождения участия

Ниже — предлагаемая схема participation provenance, построенная так, чтобы мягко лечь на существующие точки расширения PolicyOS: `ClaimRecord.provenance_ref`, `source_attribution`, minimum PDC record families, audience-specific exports и human-review packets. fileciteturn12file0L3-L3 fileciteturn25file0L3-L3 fileciteturn20file0L3-L3 fileciteturn30file0L3-L3

**Идентификация записи.** Нужны `schema_version`, `participation_record_id`, `run_id`, `case_id`, `created_at`, `created_by_component`, `source_ref`, `artifact_ref`, `status`. Поле `status` лучше сразу сделать typed: `sufficient`, `limited`, `blocked`, `legacy_missing`, `redacted_public_projection`. Это позволит C19 работать в той же fail-closed логике, что и текущие readiness/publication surfaces. fileciteturn12file0L3-L3 fileciteturn11file0L3-L3

**Claim linkage.** Нужны `claim_links[]`, где каждый link содержит `claim_id`, `claim_family` и `claim_use`. Минимальные `claim_use` для C19: `preference`, `legitimacy`, `implementation_feasibility`, `contestability`, `harms`, а также `other_context_only`. Это важнее, чем кажется: один и тот же participation artifact может быть легитимным для legitimacy/context claim и нелегитимным для prevalence claim. Отдельное поле `allowed_generalization_scope` должно фиксировать предел допустимого вывода. citeturn17view0turn14view0

**Тип источника и режим участия.** Нужны два независимых поля: `source_kind` и `consultation_mode`. Для `source_kind`: `survey`, `deliberative_panel`, `testimony`, `consultation_summary`, `agency_record`, `individual_quote`, `focus_group`, `interview`, `administrative_feedback_dataset`, `llm_speculation`. Для `consultation_mode`: `inform`, `consult`, `involve`, `collaborate`, `empower`. Такое разделение позволяет не путать «формат артефакта» с «уровнем реального influence». citeturn29view2turn31view0turn14view0

**Affected group mapping.** Нужны `affected_groups[]` с минимумом полей: `group_id`, `group_label`, `relationship_to_policy` (`directly_affected`, `indirectly_affected`, `implementer`, `regulated_entity`, `proxy_body`, `vulnerable_population`, `general_public`), `geography`, `time_scope`, `why_this_group_is_affected`, `inclusion_reason`, `exclusion_reason_if_any`, `coverage_status`. Отдельно — `participation_gaps[]`, чтобы система могла честно фиксировать, какие группы не были услышаны или были охвачены только через proxy. Именно этот gap register должен кормить limitation/blocker semantics в acceptance. citeturn29view2turn31view0 fileciteturn28file0L3-L3

**Participant set и representativeness.** Нужны `population_description`, `sampling_frame`, `recruitment_method`, `eligibility_rules`, `invited_count`, `participated_count`, `response_rate_if_known`, `languages`, `mode`, `field_dates`, `location`, `representativeness_class`, `representativeness_basis`, `weighting_used`, `weighting_method`, `known_coverage_gaps`. Для deliberative panels — еще `quota_dimensions`, `sortition_or_randomization`, `facilitation_model`, `session_count`. Для surveys — `instrument_ref`, `question_wording_ref`, `precision_or_margin_of_error_if_applicable`. Для qualitative sources — `topic_guide_ref`. citeturn14view0turn28view2turn31view0

**Verification.** Нужны `sponsor`, `conducted_by`, `controller`, `verification_level`, `participant_identity_verification`, `source_authenticity_check`, `instrument_disclosed`, `processing_disclosed`, `coder_or_analyst_info`, `intercoder_or_quality_checks`, `recording_or_minutes_ref`, `evidence_hash_or_ref`. Это та часть схемы, которая переводит participation evidence из «нам кто-то сказал» в проверяемое исследовательское/административное основание. citeturn14view0turn17view3turn21view1

**Aggregation и dissent.** Нужны `aggregation_method`, `aggregation_unit`, `denominator_if_any`, `theme_extraction_method`, `weighting_or_normalization`, `consensus_threshold_if_any`, `minority_positions[]`, `unresolved_objections[]`, `response_status`, `why_suggestions_not_taken_up_ref`. Это нужно потому, что consultation summary не обязана означать consensus, а deliberative recommendation не обязана означать unanimity. citeturn17view1turn29view2

**Privacy and release.** Нужны `release_type` (`open_release`, `limited_access`, `internal_only`), `public_export_allowed`, `redaction_status`, `quote_release_policy`, `contains_special_category_data`, `reidentification_risk_level`, `motivated_intruder_assessed`, `privacy_notice_ref`, `retention_class`, `lawful_or_public_interest_basis_summary`, `disclosure_constraints[]`. Это обязательный слой, потому что pseudonymised data все еще остается personal data, а open release и limited access — разные disclosure regimes. citeturn20view0turn21view0turn21view1turn21view3 fileciteturn32file0L3-L3

**Governance review.** Нужны `review_required`, `review_packet_ref`, `review_status`, `reviewer_roles`, `reviewer_signatures_present`, `override_present`, `override_reason`, `risk_tier`. Это нужно не для каждого low-risk survey artifact, но обязательно для cases, где participation evidence содержит sensitive harms, vulnerable groups, blocked claims, contested legitimacy или privacy-limited publication. fileciteturn30file0L3-L3

**Тyped limitation/blocker output.** Нужны `limitations[]` и `blockers[]` с кодами, понятными рантайму. Практически нужны как минимум: `affected_group_unmapped`, `participation_gap_uncovered_group`, `nonrepresentative_for_claim_scope`, `source_unverified`, `privacy_release_blocked`, `summary_without_underlying_method`, `proxy_used_without_justification`, `llm_speculation_not_participation`, `dissent_not_recorded`. Именно эти поля позволяют выполнить формулировку acceptance буквально, а не декларативно. fileciteturn28file0L3-L3 fileciteturn12file0L3-L3

## Публичная и редактированная проекция

Для C19 правильный принцип публикации звучит так: **публичный слой обязан показывать качество и пределы участия, но не обязан раскрывать сырые персональные данные или дословные чувствительные материалы**. Это хорошо ложится на существующую модель PolicyOS, где public export уже redacted/projection-only, а projection semantics прямо запрещают использовать projection как claim/approval authority. Публичный PDC therefore должен нести participation provenance как authoritative limitation metadata, но не как open transcript dump. fileciteturn10file0L3-L3 fileciteturn11file0L3-L3

Минимум того, что публичная проекция должна показывать по C19: `source_kind`, `consultation_mode`, `affected_groups_summary`, `representativeness_class`, `field_or_session_dates`, `geography`, `participant_count_or_safe_band`, `aggregation_method`, `dissent_present`, `participation_gaps_summary`, `claim_links_summary`, `public_limitations`, `review_status_summary`. Европейская Комиссия требует публичной доступности результатов consultations и synopsis reports; EPA требует прозрачного отражения того, как diverse concerns были учтены; ICO подчеркивает, что transparency about anonymisation builds trust. Значит, «privacy» здесь не может означать полное исчезновение participation layer из public view. citeturn15view0turn17view1turn29view2turn21view1

То, чего публичная проекция не должна показывать, тоже можно описать довольно строго: raw transcripts; прямые идентификаторы; linkage keys; подписи рецензентов; hidden refs; полные quote texts, если они повышают re-identification risk; precise combinations of attributes, делающие человека узнаваемым; любые псевдонимизированные, но все еще personal данные, если они публикуются как будто анонимные. ICO прямо предупреждает, что pseudonymisation не равна anonymisation, а motivated intruder test должен учитывать внешние источники, публичные релизы других организаций и даже AI tools. Во внутреннем PolicyOS это согласуется с already forbidden raw/source/secret keys in public export и с explicit privacy compliance rules, которые запрещают помещать raw records, row samples и sensitive field values в compliance bundle. citeturn20view0turn21view0turn21view3 fileciteturn10file0L3-L3 fileciteturn32file0L3-L3

При этом reviewer/expert/machine tiers могут и должны иметь более богатую participation visibility: exact refs на instruments, underlying summaries, protected quote excerpts, reviewer packet refs, blocked claim details и governance decisions. В этом месте C19 должен использовать уже существующую логику publisher: public visibility скрывает непубликуемые/blocked claims, а reviewer/expert/machine режимы делают их видимыми. Если claim заблокирован из-за некачественного participation provenance, public layer должен показывать не содержание скрытого материала, а existence of blocker и его тип. fileciteturn23file0L3-L3 fileciteturn20file0L3-L3 fileciteturn21file0L3-L3

Из этого следует полезное проектное правило: **если privacy не позволяет публиковать цитату или granular subgroup detail, система все равно обязана публично показать, что participation evidence существовало, какого оно типа, какой у него representativeness class, что было отредактировано и почему**. Это делает public surface честной, не нарушая privacy. citeturn21view1turn21view3 fileciteturn10file0L3-L3

## Правила рантайма и критерий приемки

Чтобы acceptance для C19 был реально исполним, а не оставался текстом в плане, рантайм должен проводить совместную проверку `claim_use`, `source_kind`, `representativeness_class`, `affected_group_mapping` и `release/privacy state`. Ниже — сжатый набор правил, который лучше всего соответствует и внешним методологическим стандартам, и уже существующим guardrails PolicyOS. citeturn14view0turn17view0turn17view1turn31view0turn21view0 fileciteturn12file0L3-L3 fileciteturn11file0L3-L3

Во-первых, если claim имеет `claim_use` из множества `{preference, legitimacy, implementation_feasibility, contestability, harms}`, то отсутствие `participation_provenance_ref` должно автоматически порождать либо `limitation_required`, либо `blocked`, в зависимости от силы формулировки claim. Runtime не должен позволять affected-person wording при полностью пустом participation trace. Это буквальное выполнение acceptance из C19. fileciteturn28file0L3-L3

Во-вторых, runtime должен проверять **совместимость source kind с типом обобщения**. Если формулировка делает population-level preference claim, а provenance говорит `open_self_selected consultation`, `testimony`, `individual_quote` или `consultation_summary` без survey basis, claim должен быть downgraded до context claim либо blocked как `nonrepresentative_for_claim_scope`. Комиссия прямо говорит, что public consultation data is not representative of the population; значит, противоположный переход должен быть запрещен машинно, а не оставлен на усмотрение автора текста. citeturn17view0

В-третьих, отсутствие `affected_groups[]` или наличие явно незакрытых `participation_gaps[]` должно блокировать legitimacy claims и ослаблять preference/harms claims. EPA отдельно акцентирует inclusive and effective representation и внимание к marginalized populations; следовательно, система не должна интерпретировать «мы поговорили с кем-то» как «мы услышали affected people». Типовой blocker здесь — `affected_group_unmapped` или `participation_gap_uncovered_group`. citeturn29view2turn31view0

В-четвертых, `llm_speculation` должен быть несовместим со всеми affected-person uses. PolicyOS уже проводит общую границу: LLM content не может стать stakeholder preference без producer validation. Валидационное правило для C19 должно делать это явным отдельным кодом, например `llm_speculation_not_participation`. fileciteturn27file0L3-L3

В-пятых, runtime должен различать **claim blocker** и **public projection blocker**. Если participation evidence методологически достаточно, но не может быть открыто опубликовано из-за privacy risk, claim не обязан автоматически блокироваться; блокироваться должна именно open release, а публичная поверхность должна получать redacted summary и typed explanation. Это согласуется и с ICO distinction between open release and limited access, и с public export architecture в PolicyOS. citeturn21view3turn21view0 fileciteturn10file0L3-L3 fileciteturn11file0L3-L3

В-шестых, если provenance содержит sensitive harms, уязвимые группы, или unresolved objections with high impact, системно разумно эскалировать его в human review, а не пытаться решить вопрос только детерминированным publication gate. Внутренний HumanReviewPacket уже поддерживает risk tier, top evidence refs, blocked claim ids, fundamental rights checklist, review controls и reviewer signatures, так что для C19 здесь не нужен новый governance mechanism — только новый reason for escalation. fileciteturn30file0L3-L3

Если эти правила собрать в одну фразу, acceptance для C19 можно переформулировать так: **affected-person суждение в PolicyOS должно публиковаться только тогда, когда система может показать, кто именно был затронут, как их голоса были собраны, насколько эти голоса репрезентативны для заявленного вывода, какие позиции были в меньшинстве, что не было покрыто, и что именно можно или нельзя раскрывать публично**. Если хотя бы один из этих пунктов не соблюден, результатом должен быть не молчаливый prose gap, а typed limitation/blocker. citeturn17view1turn29view2turn21view1 fileciteturn28file0L3-L3

## Открытые вопросы и ограничения

Эта схема опирается на сильные внутренние якоря в репозитории и на официальные внешние источники по survey disclosure, stakeholder consultation, deliberative panels, public participation и anonymisation. Однако один важный пробел остается: первичный текст OECD Good Practice Principles for Deliberative Processes не был извлечен напрямую, поэтому часть deliberative-panel логики здесь опирается главным образом на доступные материалы European Citizens’ Panels и не претендует на полную реконструкцию именно OECD vocabulary. Тем не менее для C19 этого уже достаточно, чтобы отделить survey, deliberative panel, testimony, consultation summary и speculative LLM content без спекуляций. citeturn28view2turn17view0turn31view0

Второе ограничение — это уровень детализации wiring в код. Из репозитория видно, что правильные точки интеграции уже существуют, но для точной реализации еще потребуется ADR-уровень решения о том, будет ли `participation_provenance` отдельным artifact schema, вложенным record family `structured_judgement_and_consultation.v1`, или общим provenance sidecar для нескольких PDC record families. С исследовательской точки зрения это уже вторично: главное решение принято — C19 должен быть **typed, claim-linked, audience-aware и fail-closed**. fileciteturn25file0L3-L3 fileciteturn28file0L3-L3

Итоговый вывод: для PolicyOS participation provenance не должен отвечать на вопрос «было ли участие?»; он должен отвечать на вопрос **«какое именно утверждение об affected people допустимо сделать на основании этого конкретного участия и в какой аудитории»**. Это делает C19 не декоративным metadata extension, а настоящим admissibility layer для preference, legitimacy, feasibility, contestability и harms claims. fileciteturn36file0L3-L3 fileciteturn28file0L3-L3

# Исследование по C25 для PolicyOS

## Контекст задачи

Задача C25 в активном плане PolicyOS требует не «добавить ещё одну метрику калибровки», а построить управляемый контур обучения между запусками, который одновременно сохраняет историческую обучаемость системы и не превращает историю в незаконно «доказательное» основание для текущего решения. Сам план прямо требует разделить historical backtesting и calibration, ввести продольный реестр по срезам domain/method/jurisdiction/data class/evidence mode/authority level, определить метрики покрытия, смещения, reversal/retraction, precision/recall блокеров, reliability по классам доказательств и calibration by group, а также задать balanced reflexive memory с scope, expiry/decay, revocation и contamination policy. В том же плане следующий инженерный слой уже разворачивается в две отдельные цепочки — E20 для longitudinal calibration ledger и E21 для balanced reflexive memory, то есть репозиторий сам подсказывает, что это должны быть две связанные, но не смешанные подсистемы. fileciteturn12file0 fileciteturn13file0

Внутреннее ADR от 2026-05-18 уже формулирует ключевое ограничение почти в готовом виде: calibration — это track-record ledger системы кейсов, а не замена текущего кейса; слабая калибровка может менять evidence budgets, reviewer escalation, authority profile eligibility или требуемую ширину uncertainty, но не может «backfill» отсутствующие доказательства текущего кейса. Это очень сильная опора для формального acceptance-правила C25: историческая память может менять будущие priors и управленческие пороги, но не должна менять статус admissibility/support текущих claim lines. fileciteturn29file0

## Что уже задаёт репозиторий

PolicyOS уже не является blank slate. По ADR-RSR-0139 общая каноническая зона для shared calibration находится в `polisyos.calibration`, Foundry хранит собственную bounded-context calibration в `polisyos.foundry.calibration`, Scientist не получает отдельного `scientist.calibration` пакета, а DDM calibration живёт отдельно как специальная подсистема. Это значит, что C25 не должен предлагать новый монолитный «калибровочный» модуль; он должен собрать общий ledger поверх уже существующих bounded contexts. fileciteturn42file0

Уже существующая governance calibration для Scientist запускает global и family-scoped governance passes, обязательные adversarial challenge suites, опциональный active disambiguation и затем публикует lesson cards в локальный lesson registry. Причём `LessonCardPublisher` уже умеет конвертировать успешный verdict в `LessonKind.SUCCESS`, а неуспешный — в `LessonKind.FAILURE`; следовательно, репозиторий уже частично поддерживает позитивную память, хотя текущая reflexive retrieval-поверхность ею практически не пользуется. Документация governance calibration также фиксирует accountability-релевантные поверхности: Brier score, log score, reliability bins, ENCE, calibration-by-group, fairness-aware gaps, equalized odds и risk-weighted verdicts. fileciteturn28file0 fileciteturn27file0

DDM calibration уже реализует очень чистую модель «калибровка как сертификация long-run error budget, а не доказательство по делу». `calibrate.py` калибрует detector threshold против target false-positive budget, оценивает empirical stationary holdout false-positive rate, Wilson confidence interval, average run length, synthetic delay tests и срок действия calibration report; `audit.py` отдельно проверяет expiration и explicit invalidation triggers. Это важный внутренний прецедент: PolicyOS уже различает calibration artifact, его validity window и invalidation semantics. fileciteturn34file0 fileciteturn33file0

В Scientist search уже есть вторая калибровочная линия: `FunnelCalibrationReport` агрегирует routing health, false-negative rate, Spearman correlation, sentinel pass rate, expensive-stage-load reduction, drift alerts, acceptance criteria и top lessons. Эта поверхность полезна не как конечный C25 ledger, а как пример того, что calibration в PolicyOS уже трактуется как связка из metrics, gaps, drift, lessons и recommended actions, а не как единичное число. fileciteturn38file0

Самая важная встроенная опора для balanced memory находится в `failure_lessons.py` и соседних модулях memory orchestration. Там уже есть: scope c visibility `local_run/tenant/domain/global_public`, applicability reasons, expires_at, auditable events `retrieved/applied/rejected/revoked`, contamination policy для reusable memory, revocation, consolidation и recovery-eval report, который сравнивает baseline recovery rate с memory-assisted recovery rate. Но текущая retrieval-поверхность по умолчанию возвращает только applicable failure lessons и формирует prompt-context как `warning_anti_pattern` с явной пометкой `"[Reflexive memory warnings - not claim evidence]"`. То есть базовая анти-лаундеринговая граница уже существует: память может предупреждать, но не может становиться claim evidence. fileciteturn20file0 fileciteturn21file0 fileciteturn22file0 fileciteturn23file0 fileciteturn24file0

Одновременно `LessonRegistry` уже знает и `FAILURE`, и `SUCCESS`, хранит provenance weight, origin domain/tenant, transfer chain, TTL-based demotion до `LOW_CONFIDENCE`, invalidation и garbage collection. Это означает, что balanced memory policy лучше строить как расширение существующей lesson infrastructure, а не как параллельную базу знаний. Архитектурно наиболее экономный путь — добавить governed success/opportunity retrieval policy и соответствующие evaluation gates поверх уже существующих lesson cards, transfer context и contamination guards. fileciteturn25file0

## Внешние ориентиры

Во внешней литературе и стандартах calibration почти везде трактуется как долгосрочная согласованность предсказанной неопределённости с реализованными исходами, а не как «точность модели» в узком смысле. NIST AI RMF делает валидность и надёжность базовой предпосылкой trustworthiness, требует демонстрировать valid and reliable behavior до deployment, мониторить функционирование в production, регулярно переоценивать метрики и tracking of identified risks over time, а также иметь post-deployment monitoring plans с feedback, incident response, override и change management. Это прямо поддерживает идею отдельного longitudinal ledger, который живёт через lifecycle, а не только в pre-release benchmark. citeturn12view0turn13view2turn13view3

Для вероятностных и confidence-style систем proper scoring rules и reliability-oriented метрики остаются лучшей базой. Современная литература по calibration показывает, что одного ECE недостаточно: выбор метрики, бинирования и class-conditional vs max-probability evaluation сильно меняет выводы, поэтому calibration policy должна явно фиксировать, какие метрики считаются каноническими для какого типа выхода. Для interval-предсказаний полезны nominal-vs-empirical coverage и ширина интервалов; для distributional outputs — scoring rules и miscalibration summaries вроде ENCE. citeturn8academia1turn8academia3

Важное ограничение для C25: marginal coverage или aggregate calibration недостаточны, если система принимает решения по группам населения, юрисдикциям или иным slice-ам. Работы по conformal prediction и multivalid/group-conditional coverage показывают, что общая valid coverage может скрывать систематическую undercoverage в подгруппах; поэтому calibration by group не должна быть факультативной витриной, а должна входить в канонический реестр по тем же ключам, что и authority decisions. citeturn8academia2turn19academia0turn19academia1

Литература по borrowing historical information также хорошо ложится на acceptance C25. Исторические данные можно использовать для prior-updates только при явно заданной exchangeability/discounting логике; если источник частично неэквивалентен текущему случаю, его нужно ослаблять или отбрасывать. Это очень близко к тому, что C25 просит для future priors: история может влиять на confidence in process, но только через формализованный слой exchangeability, а не как скрытое объединение с current-run evidence. citeturn14academia0turn14academia3

Для contamination policy внешние сигналы тоже однозначны. Работы о benchmark contamination и search-time contamination показывают, что leakage может возникать не только на train/test boundary, но и на retrieval boundary: если система во время ответа или оценки подбирает источник с самим benchmark item и ответом, она может искусственно завысить performance и исказить lessons. Это поддерживает уже существующие guards в PolicyOS против hidden refs, hidden suites и canary tokens и делает разумным расширение этих guards на memory entries, evaluation traces и imported summaries. citeturn9academia0turn9academia1

Наконец, внешние предложения по model cards и datasheets подтверждают, что любая управляемая retrospective memory должна быть документированной и slice-aware: intended use, subgroup performance, limitations, provenance и recommended/non-recommended uses должны быть обязательными полями, иначе память становится непрозрачным источником неявных предубеждений. Это хорошо поддерживает идею applicability scope, lift-and-shift constraints и explicit expiry/decay в C25. citeturn16academia1turn16academia2

## Продольный калибровочный реестр

### Принцип разделения

Для C25 я бы рекомендовал ввести не один, а два разных журнала с общей ссылочной связью. Первый — **benchmark/backtest ledger**, который хранит результаты adversarial suites, historical replays, stratified backtests и pre-deployment evaluation. Второй — **longitudinal calibration ledger**, который хранит только те случаи, где позже появился реализованный outcome, lifecycle update, DDM event, supersession/refutation/retraction или иная проверка исхода в реальном времени либо в governance-grade replay. Такое разделение согласуется и с формулировкой C25, и с ADR-0163, и с уже существующим разделением между backtesting/adversarial surfaces и DDM/lifecycle calibration. fileciteturn12file0 fileciteturn29file0 fileciteturn35file0

Главное правило должно звучать так: **backtesting measures anticipated behavior under controlled or replayed conditions; calibration ledger measures realized reliability after commitment or after governance-significant verification**. Если смешать их, система начнёт считать хорошо прошедший benchmark частичной заменой ex-post reliability, а это именно тот вид laundering, который C25 пытается запретить. fileciteturn12file0 fileciteturn29file0

### Минимальная схема реестра

Ниже — минимальная каноническая запись, которую имеет смысл использовать как conceptual contract для будущего E20:

| Поле | Смысл |
|---|---|
| `ledger_entry_id` | стабильный id продольной записи |
| `source_case_id` / `run_id` / `claim_id` | ссылка на кейс, запуск и при необходимости конкретный claim |
| `event_kind` | `forecast_realized`, `claim_confirmed`, `claim_refuted`, `case_superseded`, `case_withdrawn`, `case_retracted`, `ddm_shift`, `post_release_incident`, `review_override_confirmed`, `review_override_reversed` |
| `domain`, `method_family`, `jurisdiction`, `data_class`, `evidence_mode`, `authority_level` | обязательные ключи C25 |
| `group_keys` | affected population, geography, institution, time-band, fairness slice |
| `forecast_horizon` / `observation_window` | когда ожидался и когда измерен outcome |
| `predicted_object` | вероятность, interval, ordinal verdict, blocker, approval, uncertainty band, recommended action |
| `realized_object` | наблюдённый outcome или lifecycle transition |
| `calibration_metrics` | coverage, bias, Brier/log/CRPS-like scores, ENCE, error width |
| `decision_metrics` | blocker TP/FP/FN/TN, override correctness, escalation necessity |
| `evidence_portfolio_signature` | агрегированный fingerprint evidence classes и method mix |
| `exchangeability_signature` | пригодность записи для будущих priors |
| `status` | `active`, `revoked`, `contested`, `superseded` |
| `provenance_refs` | refs на lifecycle/DDM/audit/ex-post artifacts |
| `expiry_at` / `review_after` | когда запись нужно заново перепроверить |

Эта структура опирается на уже существующие в репозитории lifecycle semantics, DDM expiration/invalidation, governance calibration artifacts, lesson registry metadata и NIST-style lifecycle monitoring, но intentionally не включает текущие evidence lines как «подмешиваемый» payload для новых claim-support решений. fileciteturn29file0 fileciteturn33file0 fileciteturn28file0 fileciteturn25file0 citeturn13view2turn13view3

### Канонические метрики

Я бы рекомендовал закрепить шесть обязательных семейств метрик.

Во-первых, **interval coverage**: по каждому nominal level фиксируется empirical coverage, width и miscoverage direction. Для sparse slices лучше публиковать confidence bounds, а не «точечную правду»; внутренний DDM уже использует Wilson intervals для false-positive certification, что даёт хороший внутренний precedent для rate-like calibration metrics. Для interval-producing subsystems можно использовать conformal-style guarantees как эталонный baseline, а не только ad hoc percentile bands. fileciteturn34file0 citeturn19academia1turn19academia2turn19academia0

Во-вторых, **bias**. Здесь нужен не один scalar, а как минимум signed bias, absolute error и bias direction by slice. Для probabilistic outputs bias должен отражать систематическое overprediction vs underprediction; для causal/policy claims — signed realized-versus-predicted effect error; для approval/blocker decisions — systematic overblocking vs underblocking. Литература по calibration подчёркивает, что calibration и discrimination/accuracy — разные свойства; поэтому bias надо хранить отдельно от общей «успешности». citeturn8academia1turn8academia3

В-третьих, **reversal rate** и **retraction rate**. Для PolicyOS полезно различать: reversal — когда более поздняя проверка или governance review системно изменила итоговый judgment без утверждения, что прежняя запись была недопустимой; retraction — когда кейс или claim были withdrawn/retracted/invalidated как неприемлемые. ADR-0163 уже задаёт lifecycle vocabulary `superseded`, `withdrawn`, `recalled`, `retracted`, `confirmed`, `refuted`, `inconclusive`, поэтому эти rates естественно вычислять именно по lifecycle transitions, а не по informal commentary. fileciteturn29file0

В-четвёртых, **blocker precision/recall**. Это ключевой анти-«fear bias» блок. Precision блокеров — доля блокеров, которые позже оказались оправданными через real incident, refutation, retraction, severe miss или необходимую эскалацию. Recall блокеров — доля реально провалившихся случаев, которые были заранее заблокированы или хотя бы подняты до human gate. Текущая repo-логика уже знает blocker-oriented governance passes, adversarial failures, override packets и review calibration; C25 должен просто связать это с ex-post outcome layer. fileciteturn28file0 fileciteturn41file0

В-пятых, **evidence-class reliability**. Здесь единицей измерения должен быть не один source, а portfolio signature: например, `legal_anchor + admin_data + scholarly_context`, `simulation_only`, `proxy_with_limitation`, `direct_observational + weak_academic`, и так далее. ADR-0163 уже требует калибровку по domain, jurisdiction, method family, data class, evidence mode и authority profile; значит reliability надо хранить не только «по модели», а и по типу доказательного портфеля. fileciteturn29file0

В-шестых, **calibration by group**. Минимально — по affected population, geography, institution type, jurisdictional layer и времени. При наличии person-group semantics добавляется intersectional sliceing. Это должно быть hard requirement для high-authority surfaces, потому что multivalid/group-conditional literature показывает: хорошая общая coverage может скрывать систематическую undercoverage в отдельных группах. citeturn8academia2turn19academia0turn16academia2

### Метрики консервативного уклона

Чтобы система не «училась бояться», нужен отдельный блок conservative-bias metrics, который никогда не растворяется в общих accuracy numbers.

**Risk overprediction** — насколько часто система систематически завышает вероятность плохого исхода или тяжесть ограничений относительно realized outcomes. Для uncertainty-producing systems это видно как persistent overcoverage и чрезмерно широкие intervals; для governance decisions — как high blocker precision failure in reverse, то есть много блокеров, не подтвердившихся ex post. citeturn8academia1turn19academia1

**Opportunity suppression** — доля случаев, где высокий quality floor был достигнут, но candidate policy была отсеяна из-за чрезмерно консервативного priors/memory/gating path и позже аналогичный класс решений показал успех. Внутренне это можно считать через pairwise counterfactual ledger: `blocked_or_deprioritized` против `later_successful_similar_case`. Этот показатель не стандартизован во внешней литературе как готовая metric, поэтому он остаётся policy synthesis поверх risk-management и lifecycle guidance, а не прямой «готовой» академической нормы. fileciteturn12file0 citeturn12view0turn13view2

**Excessive blocker rate** — доля high-authority blocks в slice при отсутствии соответствующего роста prevented-failure rate. **Under-selection of ambitious policies** — доля случаев, где система стабильно предпочитает низко-variance conservative options, хотя later ex-post data показывает, что более ambitious options в схожих slices были successful и governable. **Domain imbalance** — когда память и calibration penalties disproportionately накапливаются в domains с лучшей instrumentability или более активным monitoring, а менее измеряемые domains искусственно выглядят «лучше». Эти три показателя лучше считать на dashboard как fairness-of-governance layer, а не как backend-only diagnostics. fileciteturn12file0 fileciteturn29file0 citeturn13view2turn13view3

## Политика сбалансированной памяти

### Что считать памятью

Balanced memory в PolicyOS должна состоять минимум из пяти типов записей: **failure lessons**, **success patterns**, **opportunity patterns**, **lift-and-shift constraints** и **recovery evaluations**. Внутри репозитория это не гипотеза: success lessons уже поддерживаются на уровне `LessonKind.SUCCESS`, governance calibration already publishes success or failure lesson cards, а `ReflexionRecoveryEvalReport` already measures whether memory-assisted recovery beats baseline. Следовательно, задача C25 не в том, чтобы изобрести positive memory с нуля, а в том, чтобы довести частично существующие механизмы до governed, authority-safe режима. fileciteturn25file0 fileciteturn28file0 fileciteturn20file0

**Failure lesson** должен отвечать на вопрос: «какой тип провала, на каком этапе, при каких scope assumptions, с какой remediation tip, в каком authority context». **Success pattern** — «какой класс решения, при каком evidence portfolio и governance path сработал надёжно». **Opportunity pattern** — «какие классы вариантов система раньше системно недоисследовала, но позже они оказались viable». **Lift-and-shift constraint** — «в каких условиях нельзя переносить прошлый успех или прошлую неудачу на новый run». **Recovery evaluation** — «насколько memory действительно улучшила future runs, а не просто увеличила консервативность». fileciteturn12file0 fileciteturn20file0 fileciteturn25file0

### Как память может влиять

Ключевое правило должно быть жёстким: **никакая memory entry не является current-run evidence**. Это полностью согласуется и с ADR-0163, и с текущей retrieval-реализацией, которая формирует memory context как warning-only anti-pattern surface, explicitly not claim evidence. Следовательно, memory может менять только: search ranking, VOI priority, evidence budget, reviewer escalation, required uncertainty width, candidate diversity pressure и scope warnings. Она не может закрыть admissibility gap, доказать claim support, заменить legal anchor или подтвердить factual assertion. fileciteturn23file0 fileciteturn29file0 fileciteturn40file0

Негативная память должна влиять преимущественно как **warning** или **human gate**, а не как auto-block. Auto-block допустим только при сочетании нескольких условий: достаточный sample size в подходящем slice, устойчиво плохой track record, высокая exchangeability с текущим run и authority level не ниже governed/production. В противном случае плохая история должна повышать scrutiny, но не «цементировать страх». Это соответствует и внутреннему намерению C25, и общему risk practice NIST, который требует risk monitoring and response over time, а не безусловного отказа по одному прошлому паттерну. fileciteturn12file0 citeturn13view2turn13view3

Позитивная память тоже нельзя делать привилегированным shortcut. Success patterns могут повышать prior trust в process family, сужать search space, снижать acquisition cost и предлагать candidate structures, но не могут автоматически считать текущий policy admissible or supported. Иначе получится симметричное загрязнение: вместо «страха» возникнет неправомерный optimism laundering. Поэтому для positive memory должен действовать тот же firewall, что и для negative memory. fileciteturn29file0 fileciteturn28file0

### Scope, decay, revocation, contamination

Scope already partially exists in code and should become mandatory. Каждая memory entry должна иметь visibility, domain, tenant, workflow, method_family, task_family, applicability reasons и expiry/degrade semantics. Текущие `MemoryVisibility`, `MemoryApplicabilityContext`, expiry parsing, optional workflow/method scope checks и revocation already form a strong baseline; C25 should simply upgrade them from implementation detail to policy contract. fileciteturn20file0 fileciteturn22file0 fileciteturn24file0

Decay policy лучше сделать двуступенчатой. После `review_after` lesson не удаляется, а демотируется в low-confidence prior; после `expiry_at` он не может influence runs без explicit revalidation. Это хорошо согласуется с уже существующим LessonRegistry, где aged entries могут демотироваться до `LOW_CONFIDENCE`, а garbage collection архивирует устаревшие или invalidated entries. fileciteturn25file0

Revocation должна быть first-class. Если later lifecycle evidence показывает, что lesson itself was based on a contaminated eval, superseded benchmark, outdated instrumentation или неверно определённый cause, записывается revocation event, а entry перестаёт быть influence-eligible. Это уже частично сделано в `revoke_lesson()` и `assert_lesson_can_influence()`. fileciteturn24file0

Contamination policy нужно закрепить жёстко и расширить. Уже сейчас reusable memory не может включать hidden benchmark ids, hidden suites, canary tokens и запрещённые metadata keys; с учётом работ о benchmark contamination и search-time contamination стоит добавить явный запрет на memory entries, содержащие benchmark question-answer pairs, private evaluation prompts, ground-truth labels hidden suites и retrieval traces, которые раскрывают held-out answers. Иначе balanced memory сама станет каналом benchmark leakage. fileciteturn21file0 citeturn9academia0turn9academia1

### Проверка, что память реально полезна

C25 должен требовать не только retrieval, но и **success evaluation**. Уже существующий `ReflexionRecoveryEvalReport` измеряет held-out recovery improvement через `baseline_recovery_rate`, `memory_recovery_rate` и `recovery_delta`; эту логику стоит расширить для positive/opportunity memory. Минимальный набор новых метрик: `recovery_delta`, `success_lift`, `opportunity_recall`, `false_warning_rate`, `false_blocker_due_to_memory_rate`. Если память повышает caution, но ухудшает success lift и opportunity recall, она считается maladaptive even при снижении incident count. fileciteturn20file0

## Правила применения для authority decisions

Рекомендую закрепить **двухканальную модель**.

**Канал текущего evidence** содержит только artefacts текущего run/case, admissibility decisions, claim support, legal anchors, data lineage, method outputs и same-input closure. Только этот канал может закрывать claim obligations и давать authority-bearing support. Это соответствует общей логике плана, ADR-0163 и текущим границам memory retrieval. fileciteturn12file0 fileciteturn29file0 fileciteturn23file0

**Канал исторических priors** содержит calibration ledger и governed memory. Этот канал может менять только meta-decisions: evidence budget, required reviewer level, required uncertainty width, mandatory second review, acquisition priority, caution notes, allowed default-enable status, escalations and de-risking requirements. Такой подход уже рифмуется с внутренним VOI calibration, где default enable блокируется без calibration/regret evidence, но сама calibration не подменяет содержательное evidence по конкретному решению. fileciteturn40file0

Для обновления priors нужны четыре условия одновременно. Во-первых, достаточная **slice similarity**: совпадение по domain, method family, jurisdiction, data class, evidence mode и authority level должно быть содержательным, а не поверхностным. Во-вторых, достаточная **sample adequacy**: маленькие slices могут генерировать warnings, но не жёсткие gating changes. В-третьих, положительная **exchangeability assessment**: если условия применения существенно изменились, historical borrowing резко дисконтируется. В-четвёртых, чистая **contamination status**: contested, revoked или leakage-risk entries не участвуют в prior updates. Это следует из C25, ADR-0163 и borrowing literature про exchangeability-aware discounting. fileciteturn12file0 fileciteturn29file0 citeturn14academia0

Практически authority-policy я бы зафиксировал так. Для **research** history creates notes only. Для **governed** poor reliability at matching slice raises review level or widens required uncertainty. Для **production/high-authority** sustained poor reliability, high reversal/retraction or poor blocker precision can temporarily disable default-enable paths, require human review or demand stronger evidence classes — но всё ещё не считаются доказательством против текущего claim сами по себе. Это — самый прямой способ удовлетворить acceptance критерию C25. fileciteturn12file0 fileciteturn29file0 fileciteturn41file0

## Вывод и открытые ограничения

Наиболее сильный вывод исследования такой: **для PolicyOS C25 должен оформляться как policy of strict channel separation** — current-run evidence graph отдельно, longitudinal calibration ledger отдельно, balanced reflexive memory отдельно, а связь между ними допускается только через governed prior effects и review/evidence-budget controls. Этот вывод не является внешней абстракцией; он уже почти полностью предзадан внутренними документами и текущим кодом, особенно ADR-0163, текущей warning-only memory retrieval, DDM calibration validity checks и governance calibration lesson publishing. fileciteturn29file0 fileciteturn23file0 fileciteturn33file0 fileciteturn28file0

Самая полезная проектная развилка — не строить memory вокруг одних failure cards. Репозиторий уже умеет хранить success lessons, а план C25 прямо требует opportunity patterns и recovery/success evaluation. Если это не сделать, система almost certainly будет смещаться к fear-based governance: она научится помнить, чего избегать, но не чему доверять и что исследовать активнее. fileciteturn12file0 fileciteturn25file0 fileciteturn20file0

Ограничения исследования тоже важны. В репозитории уже есть сильная база для failure memory, contamination, revocation и calibration artifacts, но явная governed retrieval policy для success/opportunity memory пока не реализована на той же зрелости, что failure path. Кроме того, такие метрики, как opportunity suppression и under-selection of ambitious policies, являются в большей степени policy synthesis поверх имеющихся внутренних нужд и risk-management literature, чем готовым внешним стандартом. Поэтому их стоит вводить как audited experimental metrics с обязательным review, а не как немедленные hard blockers. fileciteturn23file0 fileciteturn25file0 fileciteturn13file0 citeturn13view2turn13view3

# Политика эволюции правил и вывода legacy для PolicyOS

## Рамка C21 и уже существующий baseline

Активный исследовательский план ставит C21 в ядро lifecycle/self-correction и формулирует задачу предельно жестко: нужно сохранить смысл уже закрытого кейса, когда меняются схемы, правила, таксономии или legacy-поведение; отдельно требуется развести ABI/schema versioning и rule-semantics evolution, ввести `rule_version_ref` и `taxonomy_version_ref` на ключевых поверхностях кейса, определить режимы replay и grandfathering, а также критерии retirement для shim-слоя. У acceptance-критерия нет двусмысленности: изменения правил не должны незаметно переинтерпретировать прошлый PDC. План дополнительно закрепляет это как один из общих success criteria всей программы: rule-semantics evolution должна отслеживаться отдельно от schema compatibility. fileciteturn20file0L3-L3 fileciteturn23file0L3-L3

Эта работа не должна вестись “с нуля”. Тот же план задает reuse-first режим: сначала `wire-existing`, затем `extend-existing`, затем `consolidate-existing`, и только потом `build-new`; исследователь обязан стартовать от уже существующих модулей и контрактов, а не проектировать параллельную систему. Для C21 это особенно важно, потому что в репозитории уже есть сильные механизмы для schema compatibility, replay, append-only lifecycle и shim-governance, но еще нет унифицированного слоя rule-lineage поверх всех PDC-поверхностей. fileciteturn16file0L3-L3 fileciteturn17file0L3-L3

При этом PolicyOS уже проводит важную для C21 линию поведения: историческая authority не должна переписываться молча. `AppendOnlyClaimLedger` требует append-only ordering для lifecycle events, а переходы запрещают тихо удалять publishable claims или понижать их без допустимого lifecycle action. Принятая ADR по lifecycle/DDM/ex-post/calibration говорит то же самое на уровне кейса: lifecycle events никогда не переписывают historical authority records, publication packets, claims или approval events. Это хороший фундамент для C21: запрет на silent reinterpretation уже есть на уровне claim/lifecycle semantics, его нужно поднять на уровень rule semantics и PDC closeout. fileciteturn37file0L3-L3 fileciteturn44file0L3-L3

## Где проходит граница между схемой и смыслом

Текущий репозиторий уже очень хорошо умеет работать именно с **schema/ABI evolution**. В `schema_compat.py` зафиксирована явная taxonomy решений: `compatible`, `compatible_with_migration`, `legacy_quarantined`, `unknown_schema_blocked`, `incompatible_blocked`, `stale_schema_blocked`; production closeout разрешается только для совместимых решений. Для migration-based compatibility код проверяет hash-идентичность source/target payload, соответствие target current schema, отсутствие declared semantic loss и наличие required semantic fields. То есть уже сегодня runtime защищает читателя от “прочитали как-то, а что именно это значило — неважно” в плоскости payload/schema. fileciteturn24file0L3-L3 fileciteturn25file0L3-L3 fileciteturn26file0L3-L3 fileciteturn27file0L3-L3

Тот же паттерн виден в Fabric и IR. Fabric `SchemaEvolution` классифицирует изменения как compatible additions/relaxations, breaking changes и metadata-only updates с ожидаемыми `minor`/`major`/`patch` bump’ами; breaking changes требуют governance metadata — owner, reviewer, `approved_major_bump`, `migration_note`, downstream impact summary, ADR refs и ненулевой migration status. IR migrations, в свою очередь, ограничены каноническим Trinity-era Policy IR, fail-closed для legacy non-Trinity payloads, требуют deterministic/version-stamped migrations и различают direct-read compatibility от compatibility via migration path. Иначе говоря, в коде уже есть зрелая практика для evolution **формата** и **reader/writer compatibility**, но не для evolution **policy meaning**. fileciteturn28file0L3-L3 fileciteturn29file0L3-L3 fileciteturn45file0L3-L3 fileciteturn49file0L3-L3 fileciteturn51file0L3-L3 fileciteturn31file0L3-L3 fileciteturn32file0L3-L3 fileciteturn33file0L3-L3 fileciteturn34file0L3-L3 fileciteturn46file0L3-L3

Внешние первоисточники подтверждают, что это разные вопросы. SemVer определяет `MAJOR.MINOR.PATCH` через совместимость публичного API и прямо требует, чтобы содержимое уже выпущенной версии не модифицировалось; несовместимые API-изменения требуют major bump. Спецификация Avro в разделе Schema Resolution объясняет, как reader и writer schemas согласуются при добавлении/удалении полей, default values и type promotion. Confluent Schema Registry определяет `BACKWARD`, `BACKWARD_TRANSITIVE`, `FULL` и `FULL_TRANSITIVE` как свойства того, какие версии схемы умеют читать/писать данные друг друга. Все три источника говорят о **совместимости чтения/записи и версионировании интерфейса**, а не о гарантии, что одна и та же evidence bundle приведет к той же admissibility/authority/closeout-оценке. Именно поэтому rule-semantics evolution нельзя “спрятать” внутрь schema compatibility. citeturn4view0turn9view0turn9view1

Практический вывод для PolicyOS такой: **schema version** отвечает на вопрос “может ли consumer корректно прочитать artifact?”, а **rule version** — на вопрос “сохранится ли тот же policy meaning, тот же severity outcome и та же authority truthfulness на тех же входах?”. План C21 именно это и требует, а существующие replay/closeout artifacts уже несут существенную часть execution provenance — `git_sha`, `code_revision`, dependency/prompt/provider fingerprints, data/source/norm refs и schema compatibility decisions. Не хватает не еще одного replay-механизма, а первого класса для semantic lineage rules/taxonomies поверх уже существующих provenance surfaces. fileciteturn20file0L3-L3 fileciteturn39file0L3-L3 fileciteturn40file0L3-L3

## Предлагаемая модель rule lineage для PolicyOS

Центральным объектом C21 должна стать **неизменяемая семантическая closeout-связка** закрытого кейса. Для каждого закрытого PDC она должна фиксировать не только `git_sha` и input provenance, но и полный semantic envelope: `authority_profile_version`, `replay_manifest_ref`, input/data refs, `rule_version_ref[]`, `taxonomy_version_ref[]`, `logic_hash[]`, `code_revision`, а также версии reader/gate surfaces, которые участвовали в closeout. Это естественное продолжение уже существующих replay и closeout contracts, а с точки зрения provenance соответствует модели W3C PROV: конкретная версия сущности должна существовать как отдельная entity, связанная с более общей сущностью через `specializationOf` и `wasRevisionOf`, а не как молча переписанная “та же самая” штука. fileciteturn39file0L3-L3 fileciteturn40file0L3-L3 citeturn9view2turn9view3

**Rule family** я бы определял как устойчивое управленческое намерение, которое не меняется от версии к версии: например, “оценка legal admissibility”, “обязательство по evidence independence”, “method-claim compatibility”, “PDC gate for publication”. **Rule version** — это человечески читаемая, монотонно растущая версия внутри family. Но в качестве окончательного идентификатора past-case meaning она недостаточна: нужен еще **logic hash**, то есть digest от канонизированной семантики правила — AST/decision table, bound thresholds, comparator semantics, referenced constants/defaults и зафиксированных taxonomy bindings. Это нужно потому, что репозиторий уже различает hash-идентичность payload’ов, `git_sha`/`code_revision` и migration evidence; а SemVer отдельно требует неизменяемости выпущенной версии. Следовательно, refactor-only коммит может менять `code_revision`, не меняя `logic_hash`, а пороговое изменение admissibility должно менять оба. fileciteturn26file0L3-L3 fileciteturn29file0L3-L3 fileciteturn39file0L3-L3 fileciteturn40file0L3-L3 citeturn4view0

**Owner**, **authority level** и **migration policy** тоже должны быть обязательной частью rule identity. В репозитории уже есть зрелый образец такой дисциплины в Fabric governance metadata: owner, reviewer, migration status, downstream impact summary, migration note, ADR refs и явное одобрение breaking major bump. Для C21 это стоит перенести на все rule families, но адаптировать под PolicyOS authority modes: правило должно явно указывать максимальный authority level, на котором оно может блокировать или понижать кейс (`research`, `governed`, `production`), своего владельца и допустимую политику миграции (`lossless_auto`, `replay_only`, `partial_revalidate`, `public_revalidation_required`). Как governance-аналог это хорошо согласуется и с SR 11-7, который требует детальной governance-документации, ongoing monitoring и inventory моделей в работе, разработке или недавнем retirement. fileciteturn51file0L3-L3 fileciteturn20file0L3-L3 fileciteturn39file0L3-L3 citeturn6view0turn9view4

`taxonomy_version_ref` нужно трактовать не как декоративный label version, а как отдельный semantic object. Для C21 это критично, потому что именно taxonomy drift часто выглядит “неопасным” на уровне payload, но реально меняет смысл кейса. Я бы различал как минимум четыре класса: `alias_only` — изменилось только имя/представление; `refinement` — категория расщепилась или агрегировалась при полном mapping-preservation; `boundary_change` — изменилась фактическая граница включения/исключения; `authority_change` — категория стала вести к другим admissibility, obligation или gate rules. Только первые два класса можно считать мигрируемыми без переинтерпретации прошлого кейса; два последних — уже semantic change и должны жить на одной оси с rule evolution. Это прямо следует из того, что план C21 требует stamping `taxonomy_version_ref` на claim records, evidence portfolios, admissibility decisions и PDC gates, а не только на “справочники”. fileciteturn20file0L3-L3

Наконец, импортные пути и shim-пути не должны быть каноническим semantic identity rules. План требует retirement policy для `architecture/shims.toml`, а сам shim-registry говорит, что это compatibility and file-relocation records с owner, sunset и migration target. Значит, import path — это временная операционная привязка, а не историческая сущность. Историческая сущность должна быть `rule_family + rule_version + logic_hash (+ taxonomy refs)`, а путь до Python-модуля — лишь локатор исполнения на момент closeout. Иначе с удалением shim’а мы теряем не только runtime path, но и исторический смысл, что прямо противоречит acceptance C21. fileciteturn38file0L3-L3 fileciteturn20file0L3-L3

## Режимы replay, grandfathering и revalidation

Для C21 PolicyOS нужен не один replay, а **несколько разных режимов**, у каждого из которых свой epistemic status. `audit_old_logic` должен быть каноническим ответом на вопрос “что именно означал этот кейс в момент closeout?”; здесь используются pinned inputs, старые rule/taxonomy refs, старый `logic_hash`, старый `code_revision` и существующие replay artifacts. `old_logic_with_lossless_schema_migration` допускается тогда, когда старый payload нужно мигрировать ради чтения, но schema migration доказанно lossless по существующим runtime rules. `current_logic_shadow` нужен отдельно: он отвечает уже на другой вопрос — “что сказала бы сегодняшняя система на тех же входах?”. `partial_revalidation` нужен для rerun только затронутой подграфом части кейса, а `public_revalidation` — для обновленного публичного состояния PDC. Такая развилка хорошо ложится и на текущие Research DAG replay modes (`audit_reconstruction`, `pinned_input_replay`, `variance_envelope`), и на append-only claim lifecycle. fileciteturn20file0L3-L3 fileciteturn36file0L3-L3 fileciteturn43file0L3-L3 fileciteturn37file0L3-L3

Ключевое правило здесь простое: **только old-logic replay может объяснять прошлый closeout как исторический факт**. Research DAG replay уже сегодня запрещает live web/provider fetch в `audit_reconstruction`, а public replay exports убирают hidden/private refs; claim lifecycle и ADR-0163 запрещают переписывать historical authority records. Поэтому current-logic replay не должен подменять historical meaning даже тогда, когда новая логика “лучше”. Он должен создавать новый derived artifact — delta, review packet, supersession proposal или revalidation record — но не изменять оригинальный closed case in place. fileciteturn36file0L3-L3 fileciteturn43file0L3-L3 fileciteturn37file0L3-L3 fileciteturn44file0L3-L3

**Stricter-rule detection** стоит формализовать как отдельную governance-функцию. Новая версия правила считается stricter, если она хотя бы в одном допустимом домене делает decision менее permissive: поднимает authority floor, сокращает freshness windows, увеличивает required evidence independence, ужесточает thresholds, сужает legal/time/geography match, убирает defaults/aliases, вводит новые blocker classes или переводит outcome по severity-решетке вниз — например, из `admissible` в `context_only`, из `publishable` в `blocked`, из `ready` в `review_required`. Это хорошо согласуется с уже существующей Fabric taxономией изменений: там отдельно выделяются `BOUNDS_TIGHTENED`, `ALLOWED_VALUES_RESTRICTED`, `REQUIRED_COMPLETENESS_TIGHTENED`, `TIME_*_CHANGED`, `GEO_*_CHANGED` как семантически ужесточающие изменения. Внешняя governance-логика тоже совпадает с этим: SR 11-7 требует ongoing monitoring и пересмотра/замены модели, если изменившиеся условия или расширение scope делают старую валидацию недостаточной. fileciteturn28file0L3-L3 fileciteturn29file0L3-L3 fileciteturn45file0L3-L3 citeturn9view4

Операционно stricter detection я бы делал в три шага. Сначала — owner-declared diff class в rule manifest. Затем — static diff на operators, thresholds, allowed sets, defaults и taxonomy boundary mappings. Затем — frozen-corpus replay по закрытым кейсам и representative negative controls. Если хотя бы один шаг показывает ужесточение, либо если diff неоднозначен, change должен маркироваться как `potentially_stricter` и попадать в review queue. Для C21 лучше ложноположительный review, чем ложное “совместимо”: acceptance специально запрещает silent reinterpretation, а не только silent breakage. fileciteturn20file0L3-L3 fileciteturn17file0L3-L3 citeturn9view4

Из этого вытекает и политика **grandfathering**. Grandfathering должен быть узким и историческим: он сохраняет право старого кейса оставаться исторически валидным как факт публикации и closeout под прежними правилами, но не дает права автоматически считаться валидным по нынешним правилам для активного governance use. Если rule/taxonomy change лишь loosens constraints, старый PDC нельзя молча “улучшать”; нужен явный amended/reissued case. Если change stricter и затрагивает активный `governed` или `production` PDC, нужен не grandfathering, а `mandatory public revalidation`. Если drift локальный, должен сработать `partial_revalidation`, потому что и план C20, и Research DAG invalidation, и claim lifecycle уже ориентированы на mapping event → affected claims, а не на wholesale reissue всего кейса. fileciteturn20file0L3-L3 fileciteturn43file0L3-L3 fileciteturn37file0L3-L3 fileciteturn44file0L3-L3

Обязательная публичная revalidation должна срабатывать минимум в пяти случаях: когда stricter-rule detection затронул admissibility/support/readiness/publication outcome; когда taxonomy boundary or authority meaning changed; когда schema migration для historical inputs не доказана как lossless; когда source/DDM/calibration invalidation затрагивает опубликованные claims; и когда case продолжает использоваться как active basis для governed/production decisions. Во всех этих случаях historical case остается в архиве неизменным, а наружу публикуется уже новое lifecycle/public state: `review_required`, `amended`, `superseded`, `withdrawn` или эквивалентное typified state — но не “тихо переписанная правда”. fileciteturn20file0L3-L3 fileciteturn37file0L3-L3 fileciteturn43file0L3-L3 fileciteturn44file0L3-L3

## Политика retirement для shims и legacy behavior

Для **import-path shims** PolicyOS уже имеет хороший зачаток политики. `architecture/shims.toml` требует, чтобы каждый active shim имел owner, sunset, migration target, test и release note; CI следит за sunset; а removal rule прямо говорит, что shim можно убирать только когда `caller_count` равен нулю или все оставшиеся callers — это примеры/тесты, которые сознательно упражняют compatibility. Это почти готовая retirement policy, но C21 должен добавить одно недостающее ограничение: ни один активный closed case не должен зависеть для своей semantic identity от shim path. После closeout исторический rule identity должен ссылаться на family/version/hash, а не на re-export path. Тогда shim можно убирать из hot runtime path, не теряя historical reproducibility. fileciteturn38file0L3-L3

Для **behavioral legacy modes** репозиторий уже еще жестче. `legacy_migration_sandbox.py` трактует legacy payloads как `legacy_quarantined` и `diagnostic_only`, прямо фиксирует, что legacy не удовлетворяет serious gates, и вводит dual-write policy с floor в две последовательные weekly closeout baselines перед cutover. Это хороший шаблон для C21: старый behavioral mode может существовать только как audit/diagnostic substrate; он не должен оставаться authority-bearing для serious runs. Retirement допустим только после dual-write доказательства без semantic loss, без blocking failure codes и с явным cutover decision. После retirement старое поведение можно и нужно сохранить только как offline/audit-restorable environment. fileciteturn41file0L3-L3

При этом окно deprecation должно оставаться **surface-specific**, а не универсальным. `migration-contracts.toml` уже различает окна и governance для runtime state, API schemas, IR и DB surfaces, а `ops/migrations/ir/README.md` требует deterministic, schema-versioned migrations, owner approval для major transitions и fail-closed behavior для legacy payloads без reviewed migration contract. Следовательно, C21 policy должна брать максимум строгости из трех источников одновременно: explicit sunset из `shims.toml`, deprecation window/compatibility policy relevant migration class и retention lifetime любого кейса, который еще ссылается на старую rule logic для audit replay. Это не замедлит cleanup, но не даст cleanup’у сломать historical meaning. fileciteturn42file0L3-L3 fileciteturn46file0L3-L3

## Приемочный критерий и итоговая policy

Если собрать все above в одну policy, acceptance C21 достигается не абстрактным “будем осторожны”, а конкретной архитектурой исторической истины. У прошлой PDC появляется неизменяемый semantic tuple; append-only lifecycle и accepted ADR уже запрещают тихое переписывание authority history; replay разделяется на authoritative historical replay и comparative current replay; stricter changes поднимают review/revalidation events вместо silent reinterpretation; а shims и legacy modes выводятся из активного runtime только после доказуемого dual-write и без потери audit-restorability. В таком режиме система может одновременно честно сказать, **почему кейс был закрыт тогда**, и **что о нем думают нынешние правила**, не смешивая эти два ответа. fileciteturn20file0L3-L3 fileciteturn37file0L3-L3 fileciteturn43file0L3-L3 fileciteturn44file0L3-L3 fileciteturn38file0L3-L3 fileciteturn41file0L3-L3

В сжатой нормативной форме я бы зафиксировал policy так:

- **Исторический смысл закрытого PDC определяется immutable набором refs**: `rule_version_ref[]`, `taxonomy_version_ref[]`, `logic_hash[]`, `code_revision`, input/replay/closeout provenance. Эти refs нельзя переписывать после closeout; новые оценки создаются как новые revision artifacts. fileciteturn20file0L3-L3 fileciteturn39file0L3-L3 fileciteturn40file0L3-L3 citeturn9view2turn9view3

- **Schema compatibility и rule semantics — разные оси управления.** Первая отвечает за deserialize/read/migrate, вторая — за decision meaning. Выпуск новой schema version никогда сам по себе не может считаться доказательством semantic equivalence rules. fileciteturn24file0L3-L3 fileciteturn25file0L3-L3 fileciteturn45file0L3-L3 citeturn4view0turn9view0turn9view1

- **Old-logic replay обязателен для audit, current-logic replay — только сравнительный.** Historical replay не может требовать live fetch и не может подменяться актуальной логикой; если новая логика дает другой результат, это оформляется как delta/revalidation/supersession, а не как переписывание прошлого. fileciteturn36file0L3-L3 fileciteturn43file0L3-L3 fileciteturn44file0L3-L3

- **Любое потенциально stricter semantic change требует явной классификации и review.** Если change может понизить admissibility/support/readiness/publication outcome, сузить допустимый scope, повысить required evidence burden или изменить taxonomy boundary, он должен считаться semantic change, а не “совместимой миграцией”. fileciteturn28file0L3-L3 fileciteturn29file0L3-L3 fileciteturn20file0L3-L3 citeturn9view4

- **Grandfathering допустим только как историческая архивная валидность.** Для active `governed`/`production` кейсов stricter changes, taxonomy boundary shifts и invalidation events должны вести к `partial_revalidation` или `mandatory public revalidation`, а не к молчаливому сохранению видимости актуальности. fileciteturn20file0L3-L3 fileciteturn37file0L3-L3 fileciteturn43file0L3-L3 fileciteturn44file0L3-L3

- **Shims и behavioral legacy modes не являются каноническим semantic identity.** Import-path shims можно удалять только по правилам registry/sunset/caller-count, а behavioral legacy — только после dual-write доказательства без semantic loss; после retirement старое поведение должно оставаться audit-restorable, но больше не может быть authority-bearing. fileciteturn38file0L3-L3 fileciteturn41file0L3-L3 fileciteturn42file0L3-L3 fileciteturn46file0L3-L3

Главный вывод исследования такой: у репозитория уже есть сильный **ABI/schema/replay/governance substrate**, поэтому C21 не требует строить новый механизм “версий вообще”. Он требует добавить **первоклассный semantic lineage layer для правил и таксономий** поверх уже существующих replay, lifecycle, closeout, migration и shim surfaces. Именно этот слой и делает возможным главный acceptance-тест: прошлый PDC остается исторически воспроизводимым, а новый policy meaning появляется только как новый, явно записанный revision — никогда как тихая подмена старого решения. fileciteturn20file0L3-L3 fileciteturn23file0L3-L3 fileciteturn39file0L3-L3 fileciteturn40file0L3-L3


# Historical Priors Firewall для PolicyOS

## Рамка задачи и вывод в одном предложении

Внутри фреймворка PolicyOS задача C41 сформулирована предельно ясно: нужно определить, как калибровка и память влияют на VOI, неопределенность, выбор модели и глубину ревью, **не превращаясь в admissible evidence текущего запуска**; выходом должны стать policy для historical priors firewall и schema для influence record; приемка требует, чтобы будущие запуски становились умнее за счет прошлых, но каждый текущий claim закрывался только текущим admissible evidence или явными typed deficits. fileciteturn17file0L3-L3

Из репозиторного контекста следует еще один важный constraint: исследование нельзя вести как “blank slate”. План прямо требует reuse-first подхода и перечисляет уже существующие опорные поверхности — Research DAG, Claim Ledger/Claim Registry, calibration, DDM, VOI scheduler, reflexive memory, provider/model quality, human review, public projection и closeout. Это означает, что C41 должен быть не новой параллельной системой памяти, а **типизированным governance-слоем поверх уже существующих артефактов**. fileciteturn14file0L3-L3

Короткий вывод исследования такой: **historical prior в PolicyOS должен быть оформлен как second-order governance evidence о риске процесса, а не как first-order substantive evidence о самом claim**. Иными словами, историческая память может менять то, *как* система ищет, проверяет, эскалирует и ограничивает текущий запуск, но не то, *чем* текущий claim считается доказанным. Это прямо согласуется и с внутренними контрактами репозитория, и с внешними требованиями к provenance, traceability, uncertainty documentation и post-deployment monitoring. fileciteturn18file0L3-L3 fileciteturn20file0L3-L3 fileciteturn21file0L3-L3 citeturn3view0turn14view0turn14view3

## Что уже зафиксировано в репозитории

В репозитории уже есть почти все базовые принципы, из которых C41 должен быть собран. Документ по reflexive memory говорит, что retrieved lessons являются warnings/anti-patterns, а не claim support; reusable memory не является evidence для публичных claims и не может сама по себе продвинуть claim readiness; влияние памяти должно быть видимо в Research DAG через `memory_influence_visible = true`; кроме того, reusable memory защищена fail-closed contamination checks против hidden eval, hidden suite, canary и др. fileciteturn18file0L3-L3

ADR-0163 закрепляет то же правило для calibration ledger: calibration — это case-system track-record ledger, а не substitute для текущего case; слабая calibration может менять будущие evidence budgets, eligibility authority profile, reviewer escalation и требуемую ширину uncertainty, но не может “backfill missing evidence in the current case”. Там же сказано, что learning records из ex-post reassessment обязаны иметь scope, applicability, revocation conditions и memory-contamination controls до влияния на будущие запуски. fileciteturn20file0L3-L3

VOI scheduler в текущей архитектуре тоже уже проводит нужную границу: он может приоритизировать candidate evaluation, source verification, human escalation, adversarial challenge и stop-search, но **не может waive required evidence or release gates**. Для required gates позволены только такие действия, как defer, reject, stop_search, request_human_review, run_required_gate или blocked_by_mandatory_gate. Это очень сильный внутренний прецедент для C41: historical priors могут менять маршрут и бюджет запуска, но не отменять обязательную текущую доказательную работу. fileciteturn21file0L3-L3

Runtime Claim Registry, в свою очередь, специально требует claim-bound binding к `scenario_requirement_refs`, `data_refs`, `selected_norm_refs`, `method_output_refs`, `portfolio_refs`, `argument_refs`, `warrant_refs`, `rebuttal_refs`, `counter_evidence_refs`, `limitation_refs` и `accepted_deficit_refs`, а текст ошибки прямо говорит, что global evidence pools не являются claim-bound authority. Значит, исторический prior не должен попадать ни в одно из слотов, которыми claim закрывается по существу. fileciteturn23file0L3-L3

Дополнительно внутренние документы уже дают нужные семантики для advisory-only сигналов и time-sensitivity. Source quality calibration названа deterministic and auditable, но advisory до принятого calibration set; high score не может override lifecycle blockers. Provider/model quality ledger отслеживает drift и допускает outcomes `approve`, `require_review`, `demote` и `block_production_approval`, причем default production model choices должны иметь recent evidence. Lesson registry уже типизирует и failure, и success lessons, ведет trust levels, provenance weight, transfer-aware reuse и TTL-понижение доверия. Это означает, что PolicyOS уже в целом различает advisory history, runtime evidence и operational gating; C41 должен их только жестко связать нормой одного firewall. fileciteturn19file0L3-L3 fileciteturn22file0L3-L3 fileciteturn28file0L3-L3

## Внешние принципы, на которые должен опираться firewall

W3C PROV-DM полезен здесь не как статистическая теория, а как модель provenance. Он определяет provenance как информацию об entities, activities и agents, участвующих в производстве данных, пригодную для оценки качества, надежности и trustworthiness; отдельно вводит relation of influence; и, что особенно важно для C41, вводит bundles как механизм provenance of provenance. Для historical priors это означает: каждое историческое влияние должно быть оформлено как явно прослеживаемая сущность с источником, действием применения и связью влияния, а не как невидимый “умный коэффициент” где-то внутри оркестратора. citeturn3view0turn13view0turn13view2turn13view3

NIST AI RMF 1.0 усиливает именно ту часть, которая нужна firewall: измерение риска должно включать measures of uncertainty, comparisons to performance benchmarks, formalized reporting, documentation of results и independent review; tradeoffs должны иметь traceable basis; то, что не измеряется или не может быть измерено, должно быть documented; риски должны отслеживаться во времени, включая emergent risks и feedback from affected actors. Для C41 это означает, что влияние исторических priors допустимо только как traceable management input в decision-making и review routing, а не как скрытая замена текущих evidence gaps. citeturn14view0turn14view1

NIST AI 600-1 для generative AI еще ближе к задаче: он требует periodic review of content provenance and incident monitoring, retention of TEVV history, inventory entries с data provenance и human oversight roles, real-time monitoring с human intervention, post-deployment monitoring, escalation, transparency reporting и post-mortem analyses. Это практически готовый внешний аргумент за то, что historical priors должны жить в слое monitoring/governance/provenance, а не в claim closure layer. citeturn14view2turn14view3

С точки зрения статистики и decision analytics, внешняя литература поддерживает раздельность ролей. Guo et al. показывают, что современные нейросети часто плохо calibrated, а calibration itself требует специальной оценки и исправления; поэтому track record калибровки уместно использовать для осторожности, re-calibration и review intensity, но не как замену текущему подтверждению конкретного вывода. Jackson et al. описывают VOI как способ оценивать ожидаемое снижение loss от изучения определенных параметров или сбора данных определенного дизайна, то есть как механизм приоритизации acquisition, а не как substitute for evidence already required. citeturn4view6turn4view7turn9academia0

Наконец, литература по benchmark contamination полезна для contamination part of the firewall. Современные обзоры и papers по contamination в LLM evaluation показывают, что contamination systematically inflates apparent performance, а простые n-gram методы decontamination недостаточны, потому что paraphrases и переводы легко обходят naïve checks. Это поддерживает репозиторное правило fail-closed memory contamination: historical prior нельзя переносить в reusable memory, если есть риск, что он утащит hidden eval, benchmark internals или contaminated success signals. citeturn12academia1turn12academia2turn12academia4

## Нормативная политика Historical Priors Firewall

### Базовое правило

**Historical prior — это процессный, а не содержательный сигнал.** В PolicyOS он должен трактоваться как typed input для orchestration, calibration governance, provider routing, review routing и uncertainty governance. Он не должен трактоваться как admissible support, admissible rebuttal, admissible counterevidence или authority envelope для текущего claim. Это напрямую продолжает текущие правила reflexive memory, calibration ledger, VOI scheduler и claim registry. fileciteturn18file0L3-L3 fileciteturn20file0L3-L3 fileciteturn21file0L3-L3 fileciteturn23file0L3-L3

### Допустимые источники priors

Для C41 разумно фиксировать семь families historical priors: calibration metrics; failure lessons; success patterns; provider/model quality history; method performance history; reviewer outcomes; acquisition success rates. Все они уже либо прямо названы в постановке C41, либо имеют опорные поверхности в репозитории: calibration governance, lessons registry, provider/model quality ledger, human review/VOI escalation, evidence acquisition planning. fileciteturn17file0L3-L3 fileciteturn31file0L3-L3 fileciteturn22file0L3-L3

Для каждого такого source family prior должен быть привязан не к “миру вообще”, а к **scope cell**: tenant/visibility, domain, jurisdiction, authority profile, workflow, claim family, method family, provider/model, source family, benchmark/eval family, time window и code/rule version. Без scope cell prior может существовать как raw history, но не как applicable prior. Это следует и из reflexive memory (`tenant_hash`, `domain`, `workflow_id`, `method_family`, `visibility`, `expires_at`), и из требований provenance/traceability у PROV и NIST. fileciteturn18file0L3-L3 citeturn3view0turn14view2

### Допустимые эффекты

Допустимые эффекты priors должны быть **односторонне governance-facing**. Historical priors могут менять search ranking, VOI estimate, acquisition priority, evidence budget, uncertainty widening, review escalation, provider/model selection, default enablement и benchmark priority. В некоторых случаях prior может auto-disable default path или auto-require human review, но только как routing/gating of the process, не как adjudication of the claim merits. Это полностью согласуется с ADR-0163 и VOI scheduler: track record может влиять на budgets, eligibility и review; VOI может менять spending/order of checks; required gates при этом не исчезают. fileciteturn20file0L3-L3 fileciteturn21file0L3-L3

Практически это означает следующие нормы. Если historical prior плохой, система может: поднять приоритет independent verification; расширить uncertainty envelope; снизить automatic readiness ceiling; выбрать более надежного provider; потребовать second-reader или human review; отправить run в richer benchmark pack; увеличить budget на counterevidence search. Если historical prior хороший, система может: ранжировать методы выше, быстрее выбирать provider по умолчанию, меньше тратить на явную redundancy в low-risk workflows. Но и в хорошем случае prior **не может** сам закрыть ни один evidence obligation. fileciteturn17file0L3-L3 fileciteturn18file0L3-L3 fileciteturn23file0L3-L3

### Запрещенные эффекты

Firewall должен запрещать четыре класса действий.

Во-первых, historical prior не может засчитываться как `data_ref`, `selected_norm_ref`, `method_output_ref`, `counter_evidence_ref`, `warrant_ref` или любой другой claim-closing ref. Во-вторых, он не может “опровергать” текущее admissible evidence: если текущий run собрал допустимое подтверждение, плохой track record может заставить шире раскрыть uncertainty или повысить review depth, но не превратить admissible evidence в inadmissible автоматически. В-третьих, prior не может mint authority для law, data, method, participation или public legitimacy. В-четвертых, prior не может скрывать текущие deficits: отсутствие current-run evidence должно проявляться как accepted deficit, limitation или blocker, а не маскироваться фразой вроде “но historically мы обычно правы”. fileciteturn17file0L3-L3 fileciteturn20file0L3-L3 fileciteturn23file0L3-L3

На уровне архитектуры это лучше всего закрепить как **двухканальную модель**. Канал доказательства заполняет Claim Registry и проходит через admissibility calculus. Канал priors производит advisory/governance actions и visible influence records в Research DAG/PDC. Переход из второго канала в первый должен быть формально запрещен validator-ом: если `prior_ref` оказался в claim evidence slots, это schema violation и closeout blocker. Такая граница хорошо соответствует и внутренней структуре Claim Registry, и внешней логике provenance/influence у PROV-DM. fileciteturn23file0L3-L3 citeturn13view0turn13view2

### Decay, scope, revocation, contamination и balance

**Decay.** Priors должны затухать по-разному. Provider/model quality и acquisition success rates — самые короткоживущие; для них разумен короткий half-life и требование recent evidence, потому что репозиторий уже требует свежесть для default production choices. Calibration metrics тоже должны быстро стареть при code/model/provider/rule changes. Failure lessons и reviewer outcomes могут жить дольше, но только с explicit expiry или после repeated hits across independent runs. Success patterns должны затухать быстрее, чем failure lessons, чтобы не встраивать survivorship bias в defaulting logic. fileciteturn22file0L3-L3 fileciteturn18file0L3-L3 fileciteturn28file0L3-L3

**Scope.** Prior применим только при явном scope match. Минимальный match-set для action-grade influence я рекомендую такой: domain, authority profile и одна из claim family / method family / provider-model / source family. Для high-authority actions нужен более строгий match, включая jurisdiction и rule/version compatibility. Если match слабый, prior может попасть только в warning-only path. Это согласуется с repo emphasis на scope/applicability/revocation и с NIST requirement документировать deployment context и knowledge limits. fileciteturn18file0L3-L3 fileciteturn20file0L3-L3 citeturn14view0turn14view1

**Revocation.** Prior должен быть немедленно revoked или quarantined, если меняется rule logic, обнаруживается contamination, возникает ex-post refutation соответствующей pattern family, ломается provenance chain, или выясняется, что prior был построен на не-complete exposure set. Revocation должна быть отдельным append-only событием, а не молчаливым перезаписыванием history, потому что и Claim Ledger, и ADR-0163 уже закрепляют append-only lifecycle semantics. fileciteturn27file0L3-L3 fileciteturn20file0L3-L3

**Contamination.** Любой prior, который происходит из hidden benchmark, private eval, hidden suite, canary token, leaked answer, contaminated synthetic benchmark или иной evaluation artifact, должен быть либо rejected, либо rendered as non-reusable. Это уже реализовано для reflexive memory и дополнительно поддержано внешней contamination literature. Для C41 я бы сделал contamination status hard prerequisite для любого reuse beyond local-run debug. fileciteturn18file0L3-L3 citeturn12academia1turn12academia2turn12academia4

**Success/failure balance.** Самая опасная ошибка historical priors — строить решение на ярких failure anecdotes или на “winning streak” успехов. Поэтому любой aggregated prior должен быть exposure-complete: он обязан хранить не только failures, но и denominator, successes, warnings, reviews и no-effect runs внутри scope cell. Failure lesson без denominator может поднимать review depth, но не должен auto-demote default path на широком scope. Success pattern без denominators и recent failures не должен auto-enable default. Это направление уже подсказано самим lessons registry, который поддерживает и `FAILURE`, и `SUCCESS`, и provenance weights, и TTL-based trust downgrades. fileciteturn28file0L3-L3

## Схема influence record для Research DAG и PDC

Ниже — schema proposal, который естественно встраивается в существующие repo surfaces. Он следует внутренним требованиям видимости memory influence, claim-bound separation и append-only governance, а концептуально совместим с PROV-DM entity/activity/agent/influence/bundle model. fileciteturn18file0L3-L3 fileciteturn24file0L3-L3 fileciteturn27file0L3-L3 citeturn3view0turn13view0turn13view2

### Предлагаемая запись influence record

```json
{
  "historical_prior_influence_id": "hpi_...",
  "schema_version": "policyos.historical_prior_influence.v1",
  "prior_family": "calibration_metric | failure_lesson | success_pattern | provider_quality | method_track_record | reviewer_outcome | acquisition_success_rate",
  "source_refs": ["artifact://..."],
  "source_bundle_refs": ["artifact://..."],
  "source_event_refs": ["event://..."],

  "scope": {
    "tenant_hash": "...",
    "visibility": "local_run | tenant | domain | global_public",
    "domain": "...",
    "jurisdiction": "...",
    "authority_profile": "...",
    "workflow_id": "...",
    "claim_family": "...",
    "method_family": "...",
    "provider_model": "...",
    "source_family": "...",
    "benchmark_family": "...",
    "rule_version": "...",
    "code_revision": "..."
  },

  "applicability": {
    "matched_fields": ["domain", "authority_profile", "method_family"],
    "mismatched_fields": [],
    "applicability_reasons": ["..."],
    "applicability_score": 0.0,
    "human_override": false
  },

  "influence": {
    "target": "search_ranking | voi | evidence_budget | uncertainty_width | review_depth | provider_selection | default_enablement | benchmark_priority",
    "direction": "increase | decrease | widen | escalate | demote | disable_default | prioritize",
    "magnitude": 0.0,
    "reason_code": "..."
  },

  "balance": {
    "exposure_count": 0,
    "success_count": 0,
    "failure_count": 0,
    "warning_count": 0,
    "review_count": 0,
    "sample_sufficiency_state": "sparse | usable | strong"
  },

  "time": {
    "observation_window_start": "...",
    "observation_window_end": "...",
    "recorded_at": "...",
    "decay_half_life_days": 0,
    "staleness_state": "fresh | aging | stale"
  },

  "firewall": {
    "not_claim_evidence": true,
    "cannot_refute_current_evidence": true,
    "cannot_mint_authority": true,
    "cannot_hide_current_deficit": true
  },

  "contamination": {
    "screened": true,
    "status": "clean | quarantined | rejected",
    "reasons": []
  },

  "revocation": {
    "status": "active | revoked | superseded",
    "revoked_by_ref": null,
    "revocation_reason": null
  },

  "visibility": {
    "research_dag_node_ref": "artifact://...",
    "pdc_projection_ref": "artifact://...",
    "visible_in_current_run": true
  },

  "affected_claim_ids": ["claim_..."],
  "resulting_action_refs": ["artifact://..."]
}
```

### Обязательные поля в Research DAG

В текущем Research DAG historical priors лучше представлять отдельным `governance` или `critique` node subtype, а не прятать их в opaque metadata. Минимальный набор полей на DAG-node уровне: `node_type = historical_prior_influence`, `prior_family`, `source_refs`, `scope`, `applicability_reasons`, `influence.target`, `influence.direction`, `magnitude`, `contamination.status`, `revocation.status`, `affected_claim_ids`, `memory_influence_visible = true`, `not_claim_evidence = true`. Это продолжает текущую projection logic для reflexive memory events, где уже используются memory critique nodes с visible influence metadata. fileciteturn18file0L3-L3 fileciteturn24file0L3-L3

### Обязательные поля в PDC

В PDC historical priors должны быть видимы не как доказательства claim-а, а как **объяснение process posture**. Я рекомендую два уровня проекции. На run-level — `historical_prior_summary`, где видны примененные prior families, их scope, contamination/revocation status, и какие governance actions они вызвали. На claim-level — `prior_influence_ids`, но без попадания этих refs в claim evidence graph. Если prior увеличил review depth или widened uncertainty, это должно быть видно в claim explanation, но отдельно от claim support graph. Иначе public/reviewer surfaces начнут путать “история повлияла на осторожность” с “история доказала содержание”. Это особенно важно с учетом уже существующих правил projection-only authority и public export guardrails в репозитории. fileciteturn17file0L3-L3 fileciteturn24file0L3-L3 fileciteturn27file0L3-L3

## Тестовые сценарии и критерии приемки

Хороший firewall должен проходить не только положительные, но и anti-laundering cases. Ниже — минимальный набор семантических тестов, который логически следует из C41 и уже существующих repo contracts. fileciteturn17file0L3-L3 fileciteturn18file0L3-L3

### Сценарий с плохим provider track record

У провайдера historically высокий grounding failure rate и citation faithfulness failure rate. Текущий run из-за этого автоматически получает more conservative provider selection, widened uncertainty и required human review. Но если текущий run собрал admissible current-run refs и прошел все claim-bound gates, claim может быть закрыт. Prior здесь изменил scrutiny, а не merits. Это соответствует и provider quality ledger, и calibration ADR, и VOI rules. fileciteturn22file0L3-L3 fileciteturn20file0L3-L3 fileciteturn21file0L3-L3

### Сценарий с сильным success pattern

Есть серия past runs, где определенный method family хорошо работал в близком domain. Исторический prior ставит этот method family выше в search ranking и делает его default candidate. Но если в текущем run method output refs не получены, generic method ref остается inadmissible, а claim registry фиксирует missing method evidence. Success history не может заменить текущий method output. fileciteturn28file0L3-L3 fileciteturn23file0L3-L3

### Сценарий с contamination

В lesson card обнаружен hidden suite id или benchmark contamination. Такой prior должен быть rejected или quarantined до применения и все равно оставить auditable event, что попытка была. Это прямо соответствует reflexive memory contamination posture и внешней benchmark contamination literature. fileciteturn18file0L3-L3 citeturn12academia1turn12academia2turn12academia4

### Сценарий с sparse history

Для новой domain/method/provider cell эффективная история мала. В этом случае prior может только warn, widen uncertainty, request added evidence или require human review; он не должен auto-demote claim or auto-enable provider default on its own. Это логически продолжает C35 sparse-history posture, NIST emphasis на uncertainty documentation и documentation того, что cannot be measured yet. fileciteturn16file0L3-L3 citeturn14view0turn14view1

### Минимальные критерии приемки

С практической точки зрения C41 можно считать закрытым, если выполняются четыре условия. Во-первых, ни один `historical_prior_influence` ref не проходит validator в claim evidence slots. Во-вторых, каждый примененный prior оставляет visible DAG node и PDC summary. В-третьих, contamination и revocation способны выключить reuse без стирания истории. В-четвертых, есть тест-кейсы, где prior увеличивает review depth, budget или uncertainty, но **не закрывает и не блокирует claim сам по себе**; claim закрывается либо current-run evidence, либо typed blocker/limitation/accepted deficit. Это ровно тот acceptance intent, который заявлен в постановке C41. fileciteturn17file0L3-L3 fileciteturn18file0L3-L3 fileciteturn23file0L3-L3

## Открытые вопросы и ограничения

Самое важное ограничение этого исследования в том, что **точные blocking-thresholds для calibration metrics находятся на границе C35 и C41**. В этом отчете я сознательно провел более строгую норму: historical priors не блокируют substantive claim by themselves; они блокируют only default paths, automatic promotion paths или automatic low-review modes. Детальная численная политика порогов по authority levels должна быть согласована с C35, а затем встроена в C41 как источник governance actions, а не как новый route для claim adjudication. fileciteturn16file0L3-L3 fileciteturn17file0L3-L3

Второе ограничение — exact decay constants и sample sufficiency thresholds здесь заданы концептуально, а не эмпирически. Репозиторий уже подсказывает форму решения — recent evidence, expiry, TTL-like decay, held-out recovery, longitudinal calibration, TEVV retention — но окончательные числа нужно подбирать на corpus of closed runs и фиксировать вместе с calibration governance reports и benchmark packs. fileciteturn18file0L3-L3 fileciteturn20file0L3-L3 fileciteturn22file0L3-L3 citeturn14view2turn14view3

Итоговая рекомендация для PolicyOS поэтому выглядит так: **вводить “historical priors firewall” не как запрет памяти, а как строгий typed membrane между memory/calibration governance и claim evidence closure**. Это наилучшим образом соответствует и текущей архитектуре репозитория, и внешним стандартам provenance/traceability/monitoring, и acceptance criterion самой задачи C41. fileciteturn17file0L3-L3 fileciteturn18file0L3-L3 fileciteturn20file0L3-L3 fileciteturn21file0L3-L3 citeturn3view0turn14view0turn14view3


# Модель живучести координации продюсеров для PolicyOS

## Что уже закреплено в коде и планах

Задача C40 в активном плане уже сформулирована предельно конкретно: нужно определить, как Lex, Fabric, Scholar, Foundry, Data Forge, Scientist и runtime quality координируются через общий spine без deadlock и circular waiting; заданы требуемые состояния handshake, правила живучести, взаимодействие с VOI, acquisition, cost budget, closeout и public projection, а критерием приёмки прямо названо требование завершать координацию узкими typed blockers, а не взаимной блокировкой, тихим пропуском требований или подменой binding-артефактов generic context-only артефактами. fileciteturn12file0L3-L3 fileciteturn13file0L3-L3

Сводный фреймворк репозитория задаёт для этого правильную оптику: PolicyOS описан как component-rich, bridge-thin architecture, а слой L4 прямо отведён под producer handshake, evidence acquisition, VOI, run cost и degradation SLA. Тот же сводный документ фиксирует, что ключевой ремонт — не «изобрести новый policy engine», а построить bridge-контракты, которые переносят producer evidence в claim-bound runtime records и дальше — в closeout substrate и внешние проекции. fileciteturn58file0L3-L3

В репозитории уже есть почти все низкоуровневые примитивы, поверх которых можно построить работоспособную модель живучести. `EvidenceSpineCarrier` уже несёт `scenario_evidence_contract_id`, `requirement_ids`, `producer_component`, `reader_contract`, `authority_profile`, `trace_id`/`spine_id` и входные/выходные refs; `build_evidence_spine_graph()` уже фейлит граф, если продюсер уронил contract ID или requirement IDs; а async handoff ledger уже требует именованных границ вроде `nl_request_creation`, `control_plane_job_lease`, `workflow_state_persistence`, `cas_artifact_write`, `canary_bundle_assembly` и `readiness_result`, проверяя также отсутствие `parent_spine_ref`, `carrier_ref`, input/output refs, ошибки redaction и integrity. Иными словами, система уже мыслит не абстрактными «шагами», а typed carriers, typed bindings и typed handoffs. fileciteturn17file0L3-L3 fileciteturn18file0L3-L3 fileciteturn20file0L3-L3 fileciteturn21file0L3-L3

Важно и то, что runtime quality уже начал проводить жёсткую границу между «прогрессом есть» и «авторитетная привязка состоялась». Boundary record concept spine специально фейлит случай, когда продюсер пытается скрыть blockers за `status=pass`, а boundary record Scholar требует либо полноценное academic/grey-literature evidence, либо typed literature-deficit blocker; если отчёт отсутствует, это не мягкая недостача, а fail, а если есть blockers — это отдельное blocked-состояние. Это очень сильная подсказка для C40: система уже движется к fail-closed живучести, а не к «лучше что-то выдать». fileciteturn50file0L3-L3 fileciteturn39file0L3-L3

Снаружи эта форма тоже имеет хорошие опоры. W3C Trace Context стандартизует перенос trace context между сервисами через переносимые идентификаторы запроса, а OpenTelemetry определяет propagation как механизм переноса контекста между сервисами и процессами и отдельно различает messaging-семантику `create` / `send` / `receive` / `process`, включая ссылки на message creation context, если обработка идёт в другой ambient context. Для C40 это означает, что explicit wait-state и explicit handoff — не «лишняя бюрократия», а нормальная практика для распределённых оркестраций, где надо сохранять причинность, границы и replayability. citeturn4view0turn8view0turn8view2turn8view3

## Где реально образуются циклы ожидания

Самый опасный цикл — это Lex ↔ Scientist. Lex нужен хотя бы минимальный legal scope, claim scope и нормализованные legal concepts, чтобы поискать релевантные нормы и не уехать в wrong jurisdiction или wrong policy domain; одновременно Scientist не может довести major claims до claim-bound authority, пока у claim registry нет selected/rejected norm refs, а policy grounding для major claims требует не только сами claim IDs, но и argument, warrant, rebuttal/counter-evidence и limitation/deficit refs. Если заставить Lex ждать «полного claim decomposition», а Scientist — «полного legal anchoring», получится симметричный wait. Репозиторий уже подсказывает разрыв этого цикла: сценарный контракт может нести `claim_scope`, `authority_scope`, `jurisdiction` и `temporal_scope`, а Lex умеет выдавать typed blockers вроде `no_relevant_norm_found`, `lex_retrieval_failed` и `lex_legal_store_missing`, не притворяясь, что binding состоялся. Значит, Scientist должен уметь стартовать с provisional claim seed, а не требовать окончательного Lex-binding до первого прохода. fileciteturn56file0L3-L3 fileciteturn32file0L3-L3 fileciteturn42file0L3-L3 fileciteturn43file0L3-L3

Второй опасный цикл — Fabric ↔ Foundry ↔ Data Forge. Foundry для серьёзных claims уже мыслит в терминах method obligations и candidate method families: в файле method quality перечислены load-bearing методические ожидания вроде `causal_effect_estimation`, `distributional_evidence`, `implementation_feasibility`, `uncertainty_interval`, `sensitivity_or_transportability_diagnostic` и т.д. Но выбрать метод окончательно Foundry может только если понимает data capability envelope. В то же время Fabric, чтобы авторитетно выбрать источник, должен знать не только source family и relevance, но и schema/dictionary/field/unit/geography/time coverage/quality/missingness/freshness/lineage/transformation/Data Forge snapshot refs. А Data Forge binding для серьёзного пути требует роли `legal`, `catalog`, `academic`, `domain`, требует manifests, artifact IDs, freshness и read API surface, и если binding заблокирован, отчёт обязан сохранить typed runtime blocker. Если заставить Fabric ждать final method selection, Foundry ждать final Fabric source set, а Data Forge ждать выбора Fabric, получится трёхсторонняя петля. Правильный разрыв здесь — отделить предварительный obligation seed от окончательного binding. fileciteturn34file0L3-L3 fileciteturn27file0L3-L3 fileciteturn45file0L3-L3 fileciteturn56file0L3-L3

Третий цикл — Scholar ↔ Scientist. Scholar нужен хотя бы query graph или literature intent; Scientist, в свою очередь, не может честно закрыть спорные или major claims без support/conflict literature, потому что policy grounding требует rebuttal/counter-evidence и limitation/deficit refs, а Scholar boundary прямо требует либо evidence, либо typed blocker. Здесь цикл легче, чем у Lex, потому что Scholar может работать по concept spine и provisional claim intents, не дожидаясь окончательного claim registry. Но если этого не разрешить, система застрянет на уровне «сначала сформируйте perfect claim graph, чтобы я поискал литературу; сначала найдите мне литературу, чтобы я доопределил claims». fileciteturn38file0L3-L3 fileciteturn39file0L3-L3 fileciteturn42file0L3-L3

Четвёртый цикл — producers ↔ semantic binding ↔ runtime quality. `semantic_binding.py` уже вводит общий producer spine context и типы статусов `pass`, `blocked`, `fail`, `warn`, `degraded`; однако если продюсеры начнут ждать итогового semantic binding перед своей первой авторитетной эмиссией, validator превратится в upstream dependency, хотя по смыслу он downstream reader. Это нарушит сам wiring evidence spine: сначала producer artifact, затем reader gate, а не наоборот. Поэтому runtime quality надо расколоть на bootstrap-функции и closure-функции: bootstrap даёт `ProducerSpineReadContext` и carrier, closure валидирует уже после producer emission. fileciteturn40file0L3-L3 fileciteturn17file0L3-L3 fileciteturn18file0L3-L3

Пятый цикл на самом деле вообще не должен существовать: closeout и public projection не должны быть upstream-зависимостями для продюсеров. Handoff ledger помещает `public_export_projection` и `dashboard_api_export` только после `readiness_result`, а `can_i_closeout` compatibility matrix уже мыслит продюсеро-ридерскими парами как downstream verification against active reader gates. Следовательно, projection — это sink, а не peer producer. Если projection блокирует primary producer emission, это уже не liveness model, а authority laundering через UI/API слой, что репозиторий отдельно запрещает. fileciteturn21file0L3-L3 fileciteturn54file0L3-L3 fileciteturn56file0L3-L3

## Предлагаемая модель состояний координации

Предлагаемая модель должна быть не заменой существующих runtime statuses, а операционным слоем поверх них. Уже имеющиеся примитивы — `EvidenceSpineCarrier`, `EvidenceRequirementBinding`, общий producer spine context и runtime status lattice (`pass`, `blocked`, `fail`, `warn`, `degraded`) — позволяют разделить **прогресс оркестрации** и **authority outcome**. Именно этого и требует C40: перечисленные handshake states — это не статусы качества, а статусы координации. fileciteturn12file0L3-L3 fileciteturn17file0L3-L3 fileciteturn40file0L3-L3

Ключевое правило здесь такое: `emitted_context_only` и `emitted_binding` обязаны быть разными состояниями не только по названию, но и по authority semantics. Репозиторий уже начал это требовать через concept spine boundary, Scholar boundary, claim registry и общий запрет на то, чтобы public/API/dashboard projection mint authority. Поэтому context-only emission может быть полезной для bootstrap-а peer-продюсера, но она никогда не может считаться закрытием requirement или claim-bound authority. fileciteturn50file0L3-L3 fileciteturn39file0L3-L3 fileciteturn43file0L3-L3 fileciteturn56file0L3-L3

| Состояние | Смысл | Минимальный обязательный артефакт | Что разрешено дальше |
| --- | --- | --- | --- |
| `requested` | Требование назначено продюсеру, carrier получен, локальная проверка ещё не завершена | run/scenario IDs, requirement IDs, owner, deadline slice | `preflighted`, `blocked`, `abandoned` |
| `preflighted` | Проверены authority profile, обязательные входы, допустимость запуска, бюджетный срез | preflight report с перечислением missing prerequisites | `waiting_on_spine`, `waiting_on_peer`, `emitted_context_only`, `emitted_binding`, `blocked` |
| `waiting_on_spine` | Не хватает общего spine-артефакта: concept/jurisdiction/time/authority/scenario seed | typed dependency token с именем missing spine ref и expiry | `preflighted`, `emitted_context_only`, `timed_out` |
| `waiting_on_peer` | Не хватает конкретного peer-output | typed peer token: producer, expected artifact kind, field contract, expiry | `emitted_context_only`, `rerun_required`, `blocked`, `timed_out` |
| `emitted_context_only` | Выпущен полезный, но не authority-bearing контекст: candidates, hints, preliminary scope | non-authoritative artifact + `may_not_use_for=binding/closeout`-эквивалент | `waiting_on_peer`, `waiting_on_spine`, `rerun_required`, `abandoned` |
| `emitted_binding` | Выпущен authority-bearing binding на уровне requirement или claim-local refs | selected/rejected/blocker rows, authority envelope, emitted requirement IDs | терминал, кроме `rerun_required` |
| `blocked` | Продюсер не может продолжать без typed blocker | `blocker_code`, `missing_facets`, `next_action`, affected refs | `rerun_required`, `abandoned` |
| `timed_out` | Ожидание или выполнение вышло за дедлайн | timeout blocker с сохранённым dependency token | `degraded`, `blocked`, `abandoned` |
| `degraded` | Продолжение возможно только при сужении scope, authority или claim set | degrade reason refs, reduced scope, revised authority envelope | `emitted_binding`, `blocked`, `abandoned` |
| `rerun_required` | Входной spine или peer artifact изменился так, что текущий artefact устарел | invalidation/supersession ref + причина rerun | `requested`, `preflighted` |
| `abandoned` | Система сознательно прекращает работу по этому producer-path | terminal record с owner decision и budget reason | closeout читает как unresolved deficit |

На практике это даёт ещё одно полезное различие: верхнеуровневый producer outcome может быть `degraded` или `blocked`, но requirement-level binding внутри него всё равно обязан быть typed. То есть вопрос всегда не «успешен ли продюсер в целом», а «что ровно случилось с каждым scenario requirement и может ли downstream reader на это безопасно опереться». Это хорошо согласуется и с `EvidenceRequirementBinding`, и с claim-bound registry, который запрещает подменять claim-local authority глобальным pool of evidence. fileciteturn17file0L3-L3 fileciteturn43file0L3-L3

## Правила живучести и деградации

### Базовые инварианты

Первый инвариант: продюсер не имеет права ждать «вообще чего-то от peers». `waiting_on_peer` должен содержать один точный dependency token: имя peer producer, ожидаемый artifact family, обязательные поля и дедлайн. Это прямо следует из логики evidence spine и handoff ledger: там уже нормализованы producer/consumer ids, parent refs, input refs, output refs и typed findings для mismatch/omission. Если в системе допускается безымянное или множественное peer waiting, она теряет возможность различать узкий blocker и orchestration fog. fileciteturn18file0L3-L3 fileciteturn21file0L3-L3

Второй инвариант: `waiting_on_spine` допустим только для truly shared artifacts — scenario evidence contract, concept/jurisdiction spine, authority profile, run-level semantic signatures. Нельзя относить сюда ожидание финального semantic binding, final closeout или projection, потому что это downstream validation/projection layers, а не shared producer input. Иначе система нарушает как P12 producer fragmentation, так и уже существующую bridge-first логику репозитория. fileciteturn49file0L3-L3 fileciteturn15file0L3-L3 fileciteturn40file0L3-L3

Третий инвариант: если продюсер может выдать полезный bootstrap-контекст без authority-bearing binding, он обязан сделать это до первого peer wait. Это особенно важно для Lex, Fabric, Scholar и Foundry, потому что именно их first-pass context позволяет разорвать циклы со Scientist и Data Forge. Но такой контекст должен быть помечен как non-authoritative и недопустимый для closeout. Иначе система воспроизведёт anti-patterns P05, P12 и P15: authority dilution, producer fragmentation и candidate-to-authority laundering. fileciteturn49file0L3-L3 fileciteturn56file0L3-L3

### Таймауты, ретраи и эскалация

Для C40 я бы рекомендовал не «бесконечные умные ретраи», а bounded waiting с экспоненциальным backoff и общим ceiling, привязанным к lease/run budget. Temporal в официальной документации подчёркивает, что retry policy должна иметь initial interval/backoff coefficient/maximum interval/maximum attempts, а верхнюю границу длительности лучше задавать execution timeout-ом; отдельно Workflow Task Timeout нужен именно для обнаружения dead worker и переноса работы на другой worker. Для C40 это означает простое правило: peer wait не может жить дольше budget slice продюсера, а потеря worker/lease должна переводить job не в silent stall, а в `timed_out` или `rerun_required`. citeturn6view0turn6view1turn6view2

Ровно здесь полезна и SRE-логика. Google SRE рекомендует в условиях overload не продолжать накапливать очередь, а либо выдавать degraded results, либо fail early and cheaply, чтобы не раскрутить cascading failure. Для продюсерной координации вывод прямой: если peer wait или acquisition wait перевалил за safe budget, правильная реакция — не ещё один «тихий» круг ожидания, а переход в `degraded`, `blocked` или `abandoned` с typed reason. Это делает систему менее «гладкой», но намного более живой и диагностируемой. citeturn7view0turn7view1

Практически это даёт такую политику. У каждого продюсера должен быть один короткий preflight budget, один bounded bootstrap-wait, затем либо first-pass emission, либо typed blocker. После first-pass emission допускается один rerun cycle, если upstream spine или peer-output materially changed. Дальше решение должно приниматься уже на уровне coordination policy: либо открыть acquisition/VOI ветку, либо сузить claim set, либо поднять human review. Повторяющиеся peer-waits без изменения входного мира — это не liveness, а busy deadlock. Такая политика не продиктована буквальным кодом, но она прямо поддерживается существующими contracts, Temporal-style bounded retries и SRE-practice graceful degradation. fileciteturn17file0L3-L3 fileciteturn21file0L3-L3 citeturn6view1turn6view2turn7view0turn7view1

Human review нужен не «всегда, когда тяжело», а в трёх узких случаях. Первый — когда цикл носит authority-semantic характер, например правовая неоднозначность юрисдикции или конфликт между legal competence и claim scope. Второй — когда возможная деградация меняет допустимый audience surface, например надо решить, можно ли выпускать reviewer-only diagnostic bundle, но нельзя выпускать public recommendation. Третий — когда стоимость acquisition или rerun переваливает VOI-порог и система уже не может рационально решать автоматически. Это соответствует и C40, и общему разделению coordination layer на evidence acquisition, VOI, cost и degradation SLA. fileciteturn12file0L3-L3 fileciteturn58file0L3-L3

## Стадийный порядок исполнения

Репозиторий уже подсказывает правильный staged order. В active evidence-binding plan сценарный контракт течёт в Data Index, Lex normalization, Foundry binding, Scientist claim registry, общую evidence binding graph, затем в Policy Design Case records, scorecard и только потом — в API/dashboard/public export. В remediation plan canonical flow тоже идёт через request → concept alignment → preflight legal/data/method obligations → producer coordination → acquisition/retrieval with VOI and cost/degradation implications → claim-bound synthesis → closeout → projection. Поэтому правильная модель для C40 — не один огромный общий DAG и не свободный peer-to-peer туман, а staged orchestration с разрешёнными first-pass cycles и строго downstream closeout/projection. fileciteturn56file0L3-L3 fileciteturn16file0L3-L3

OpenLineage даёт полезную внешнюю аналогию: lineage event раскладывается на Run, Job и Dataset facets. Для C40 это почти идеальная ментальная модель. Run-level слой должен владеть trace/spine/lease/budget/handoff. Dataset-level слой — это Data Forge и Fabric source/snapshot bindings. Job-level слой — это Lex, Scholar, Foundry и Scientist artifacts. Тогда циклы видны сразу: producer job не должен ждать projection job, dataset-binding не должен ждать final policy artifact, а run-level orchestration обязан хранить причинность и deadlines. citeturn8view4turn8view5

Предлагаемый стадийный порядок выглядит так.

| Стадия | Что происходит | Какие выходы допустимы |
| --- | --- | --- |
| Создание run-контракта | NL request creation, trace/spine carrier, scenario evidence contract, authority profile, initial deadlines | `requested` |
| Bootstrap spine | Concept/jurisdiction/time spine и общие semantic signatures | `preflighted`, `waiting_on_spine`, `blocked` |
| Параллельный preflight доменов | Data Forge availability matrix; Lex query seed; Foundry method-obligation seed; Scholar research intent; Fabric source-family seed | `preflighted`, `emitted_context_only`, `blocked` |
| Первый проход producer emission | Lex/Fabric/Scholar/Foundry выпускают candidate/context/blocker artifacts без претензии на final binding | `emitted_context_only`, `blocked` |
| Seed claim registry | Scientist формирует provisional claims и связывает их с scenario requirements и first-pass refs | `preflighted`, `emitted_context_only`, `waiting_on_peer` |
| Второй проход authoritative binding | Lex/Fabric/Scholar/Foundry доизлучают selected/rejected/blocked rows; Scientist становится claim-bound | `emitted_binding`, `blocked`, `degraded` |
| Semantic closure | Semantic binding, policy grounding, evidence spine propagation, residual boundary checks | `pass`, `blocked`, `degraded`, `fail`, `rerun_required` |
| Closeout и projection | can_i_closeout, readiness, dashboard/API/public export projection | closeout decision и audience-scoped projection |

Смысл этой схемы в том, что explicit cycles разрешены только между первым и вторым проходом. До второго прохода допустим `emitted_context_only` как bootstrap surface. После второго прохода допустимы только `emitted_binding`, `blocked`, `degraded` или `rerun_required`. Иначе `can_i_closeout` и public/export surfaces начинают смотреть не на authority-bearing graph, а на полуфабрикаты. Это прямо противоречит как claim registry, так и closeout compatibility matrix, так и non-negotiable principle «serious policy output cannot pass without claim-bound legal, data, method, semantic, and limitation bindings». fileciteturn43file0L3-L3 fileciteturn54file0L3-L3 fileciteturn56file0L3-L3

## Таблица разрешения циклов

Ниже — рекомендуемая cycle-resolution table для C40.

| Цикл | Что реально нужно одной стороне | Что разрешено как первый выход | Когда ожидание надо прекратить | Корректный терминальный исход |
| --- | --- | --- | --- | --- |
| Lex ↔ Scientist | Lex нужен legal intent seed, jurisdiction, temporal scope и provisional claim scope; Scientist нужен selected/rejected norm surface | Scientist выпускает provisional claim seed; Lex выпускает query-normalization/context-only или typed no-norm blocker | После одного bootstrap-round без новых legal/concept refs | `emitted_binding` у Lex или `blocked`; Scientist либо `rerun_required`, либо claim set с `legal_scope_pending`, но не final normative closure |
| Fabric ↔ Foundry | Fabric нужны method-shape hints; Foundry нужен data capability envelope | Foundry выпускает method-obligation seed; Fabric выпускает candidate source coverage/context-only | Когда candidate coverage не улучшает method admissibility или budget slice исчерпан | либо Foundry final method binding, либо Fabric data-gap blocker, либо controlled degradation of claim set |
| Fabric ↔ Data Forge | Fabric нужны snapshot roles/manifest/freshness/read API; Data Forge не должен ждать final source choice для baseline availability | Data Forge выпускает role availability matrix; Fabric — source search/context-only | Если отсутствует хотя бы один обязательный role binding для serious lane | `blocked` с missing role / missing snapshot binding; optional acquisition only through VOI decision |
| Scholar ↔ Scientist | Scholar нужен research intent и concept seed; Scientist нужны support/conflict literature refs | Scholar выпускает search intent, provider trace, preliminary literature refs или literature blocker | После одного search rerun без изменения concept spine или claim seed | `emitted_binding` со support/conflict refs либо `blocked`; Scientist не закрывает major claims без явно отражённого literature deficit |
| Producers ↔ semantic binding | Semantic binding нужны producer outputs; producers не должны ждать final validator | Producers выпускают first-pass artifacts; semantic binding only reads and may emit targeted rerun-required | Сразу после выявления конкретного cross-producer mismatch | targeted `rerun_required` конкретному producer-path, а не глобальный restart |
| Producers ↔ closeout/projection | Closeout и projection ничего не должны «нуждаться назад», кроме already emitted artifacts | Никакого upstream wait не разрешено | Немедленно: projection не peer producer | closeout либо допускает audience-scoped result, либо fail/blocked; projection лишь показывает outcome |
| Budget ↔ acquisition | Координация хочет ещё данные, но run budget конечен | context-only artefacts могут кормить VOI, но не closeout | Когда expected value acquisition ниже cost/deadline risk | `abandoned`, `degraded` или human review, но не бесконечный acquisition loop |

Первые три строки таблицы напрямую следуют из сценарного контракта, Lex blockers, method-obligation registry, Fabric source facet obligations и Data Forge snapshot binding rules. Четвёртая и пятая строки опираются на Scholar boundary, semantic binding и policy grounding/claim registry. Последние строки вытекают из того, что coordination layer в сводном фреймворке уже объединяет acquisition, VOI, cost и degradation SLA, а closeout/projection формально downstream относительно producer artifacts. fileciteturn56file0L3-L3 fileciteturn32file0L3-L3 fileciteturn34file0L3-L3 fileciteturn27file0L3-L3 fileciteturn45file0L3-L3 fileciteturn39file0L3-L3 fileciteturn40file0L3-L3 fileciteturn42file0L3-L3 fileciteturn43file0L3-L3 fileciteturn58file0L3-L3 fileciteturn54file0L3-L3

Критическая оговорка для всей таблицы: `emitted_context_only` должен иметь жёсткий reader-side запрет на использование для closeout/public authority. Иначе система воспроизведёт ровно тот провал, против которого написаны P05 и P15, а acceptance C40 не будет выполнен: формально deadlock исчезнет, но его место займёт stealth laundering partial context into authority. fileciteturn49file0L3-L3 fileciteturn50file0L3-L3 fileciteturn56file0L3-L3

## Итоговый вывод

Наиболее надёжный путь для C40 — не писать «с чистого листа» новый глобальный оркестратор, а наложить явный liveness envelope на уже существующие артефакты: scenario evidence contract, concept/jurisdiction spine, `EvidenceSpineCarrier`, handoff ledger, claim registry, semantic binding и `can_i_closeout`. В таком дизайне продюсерная координация становится не очередью с молчаливыми зависаниями, а конечным автоматом с узкими blocker codes, bounded waits, claim-bound reruns и аудитируемыми handoff boundaries. fileciteturn17file0L3-L3 fileciteturn20file0L3-L3 fileciteturn43file0L3-L3 fileciteturn40file0L3-L3 fileciteturn54file0L3-L3

Если сформулировать это совсем жёстко, то правильная модель живучести для PolicyOS должна принуждать каждый producer-path к одному из трёх честных исходов: **authoritative binding**, **narrow typed blocker**, либо **explicitly degraded non-public outcome**. Всё остальное — бесконечное ожидание, скрытый soft-fail, или context-only laundering — должно считаться дефектом координации. Именно такая форма одновременно соответствует active plan C40, текущему fail-closed направлению runtime quality и внешним практикам распределённой оркестрации, tracing и overload control. fileciteturn13file0L3-L3 fileciteturn50file0L3-L3 fileciteturn39file0L3-L3 citeturn4view0turn8view0turn6view1turn7view0


# C39 Внешняя поверхность легитимности для PolicyOS

## Контекст и опорные якоря

Внутренний baseline у PolicyOS уже довольно жестко задает направление для C39: внешняя поверхность не должна «изобретать» новую власть, а должна быть типизированной проекцией уже существующего authority-core. В репозитории это видно сразу по нескольким якорям. Во-первых, `PolicyDesignCaseProjection` должен оставаться `projection_only`, иметь явный список `may_not_be_used_for`, а любая попытка сделать проекцию источником approval, claim authority или runtime closeout authority должна завершаться fail-closed ошибкой. Во-вторых, `DecisionGradeExport` уже строится как audience-specific export из одного и того же Claim Ledger и Research DAG, причем public/reviewer/expert/machine выводы обязаны сохранять общие `claims_ref` и `research_dag_ref`, а намеренные omissions должны быть записаны явно. В-третьих, runtime assurance case уже мыслится как structured assurance case с различимыми claim/argument/warrant/evidence/rebuttal/counter-evidence/deficit узлами и с SACM/CAE-мэппингом, а публикация и аудит уже привязаны к replayable public audit archive, verifier status, PROV/SLSA surface и public/private boundary. fileciteturn20file0L3-L3 fileciteturn21file0L3-L3 fileciteturn19file0L3-L3 fileciteturn25file0L3-L3 fileciteturn26file0L3-L3 fileciteturn28file0L3-L3 fileciteturn32file0L3-L3

Это хорошо совпадает с внешними стандартами. NIST AI RMF Playbook требует, чтобы legal and regulatory requirements были understood, managed, and documented; чтобы AI governance policies были transparent; чтобы documentation покрывала business justification, scope and usage, risks and impacts, assumptions and limitations, training data, methodology, alternative approaches, testing and validation, dependencies, monitoring, stakeholder engagement и public disclosure of impact assessments, audits, model documentation and validation/testing results; а также чтобы существовали механизмы feedback, contestability, recourse и opt-out для затронутых лиц и сообществ. W3C PROV определяет interoperable provenance model через entities, activities, agents и qualified relations, специально как основу для обмена provenance information across systems. SACM, в свою очередь, определяет assurance case как набор auditable claims, arguments and evidence, служащий для ясного и defendable information exchange между supplier и acquirer, operator и regulator. citeturn11view0turn9view0turn19view0

Из этого следует основной тезис для C39: **внешняя легитимность у PolicyOS должна строиться не как красивый public summary, а как набор audience-specific surfaces, каждая из которых показывает ровно столько типизированной информации, сколько нужно, чтобы оспорить, реконструировать, проверить или машинно-валидировать решение, но не превращает projection в authority**. Это также прямо согласуется с внутренним C16/C17/C18/C19 syntheses: система уже различает projection-only semantics, contestability как отдельный слой, tradeoff/value choice как отдельную семантику и participation provenance как отдельный record family, а failure register отдельно предупреждает против “internal richness with poor external surface” и “authority dilution.” fileciteturn18file0L3-L3 fileciteturn11file0L3-L3 fileciteturn12file0L3-L3 fileciteturn31file0L3-L3

## Принципы проектирования поверхности легитимности

Предлагаемая таксономия должна строиться вокруг пяти кросс-аудиторных принципов.

Первый принцип — **preserve authority boundaries**. Любая внешняя поверхность обязана явно говорить, авторитетна она или нет, для каких целей ее можно использовать и для каких нельзя. Это не декоративный warning, а часть контракта: в `projection_semantics.py` запрет на использование projection для `approval_authority`, `claim_authority`, `runtime_closeout_authority` и `scorecard_authority` уже задан на уровне семантики, а в dashboard/public packet UI отдельно закреплены caveat’ы о том, что badges, labels, frontend signatures и projections не являются closeout authority. Поэтому C39 не должен допускать ни одной аудитории, у которой surface «звучит» как власть, но не содержит authority chain. fileciteturn20file0L3-L3 fileciteturn21file0L3-L3 fileciteturn23file0L3-L3 fileciteturn24file0L3-L3

Второй принцип — **contestability is contrastive, not merely descriptive**. Для затронутого внешнего пользователя полезно не только «что система решила», но и «почему не прошел этот claim», «что именно contested», «кто вправе решить спор», «что осталось неразрешенным», и «какое изменение могло бы изменить статус». Внутренний C17 прямо требует, чтобы public contested records показывали what is contested, positions, evidence per side, who may decide, what was decided and what was not, limitations, reopening triggers. А внешняя explainability literature отдельно подчеркивает, что хорошее объяснение должно помогать понять, оспорить и получить ориентир, что должно измениться для другого исхода. fileciteturn18file0L3-L3 citeturn15academia0

Третий принцип — **reconstructability for entitled reviewers**. Reviewer и expert поверхности должны позволять не просто читать summary, а восстанавливать claim lineage. Это следует и из `DecisionGradeExport`, где reviewer/expert tiers обязаны сохранять blocked claims, evidence/counterevidence counts, replay summary и trust provenance, и из assurance-case semantics, где claim/argument/warrant/evidence/rebuttal/counter-evidence/deficit должны быть inspectable как отдельные узлы. NIST снаружи поддерживает ту же логику, требуя documentation inventory, assumptions/limitations, methods, alternative approaches, testing and validation results, dependencies и public disclosure policies для audits и impact assessments. fileciteturn19file0L3-L3 fileciteturn26file0L3-L3 fileciteturn32file0L3-L3 citeturn11view0

Четвертый принцип — **privacy-aware visibility, not privacy-as-eraser**. Внутренний C19 уже задает нужную форму: public projection по participation provenance должна показывать source kind, consultation mode, affected-group summary, representativeness class, dates, geography, safe participant band, aggregation method, dissent presence, participation gaps, claim links, limitations и review summary, но не должна раскрывать raw transcripts, direct identifiers, linkage keys, sensitive quotes или комбинации, ведущие к re-identification. Аналогично, public export может скрывать blocked claim details, benchmark/eval internals, raw transcripts и prompt tokens, но только с явным omission record и без скрытого превращения redaction в стирание blocker’а или dissent. fileciteturn18file0L3-L3 fileciteturn19file0L3-L3

Пятый принцип — **machine-verifiable truthfulness**. Для external auditors недостаточно human-readable dashboard’а. Нужны стабильные schema IDs, refs на source objects, machine-readable provenance, digests, verification status, public/private boundary и explicit mapping между projection field и source artifact. На это одновременно указывают `DecisionGradeExport` consistency checks, `external_audit.py`, W3C PROV и SLSA/in-toto: provenance должно быть representable и interchangeable across systems; consumers должны иметь возможность сверять artifact с ожидаемой provenance; а цепочка шагов, исполнителей и порядка должна быть прозрачной и проверяемой. fileciteturn19file0L3-L3 fileciteturn28file0L3-L3 citeturn9view0turn10view0turn10view1

## Матрица аудиторий и минимально обязательные поля

Ниже — предлагаемая **матрица entitlement**, нормализованная из внутренних C16–C19, DecisionGradeExport, external audit surface, assurance-case mapping и внешних требований к documentation, recourse и provenance. Легенда: **Сводка** — краткое, но contestable раскрытие; **Клейм-уровень** — видимость по каждому claim; **Полно** — реконструируемая, проверяемая глубина; **Вериф.** — поля, нужные прежде всего для внешнего audit/automation. fileciteturn18file0L3-L3 fileciteturn19file0L3-L3 fileciteturn28file0L3-L3 citeturn11view0turn9view0turn19view0

| Аудитория | Claim graph | Legal authority | Data basis | Method basis | Uncertainty | Tradeoff and value choice | Participation provenance | Deficits and dissent | Redactions | Audit refs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Public | Сводка + клейм-уровень для ключевых claims | Сводка | Сводка по evidence families | Сводка по method families | Сводка | Сводка обязательна | Сводка обязательна | Существование и тип обязательны | Обязателен redaction notice | Сводка + public audit ref |
| Dashboard consumer | Клейм-уровень для triage | Клейм-уровень | Клейм-уровень | Клейм-уровень | Клейм-уровень | Сводка + alerting | Сводка + gaps | Полно для block/contest/deficit | Полно по omission codes | Operational + verification refs |
| Reviewer | Полно | Полно | Полно | Полно | Полно | Полно | Полно в privacy-safe форме | Полно | Полно | Полно |
| Expert | Полно + assumptions/warrants | Полно | Полно + lineage/scope | Полно + assumptions/alternatives | Полно + limits | Полно + frontier + chosen rule | Полно + admissibility class | Полно + residual dissent | Полно | Полно |
| Audit consumer | Полно, но verifier-oriented | Полно | Полно | Полно | Полно | Полно, если влияло на выбор | Полно в boundary-safe форме | Полно | Полно + justification | Полно + digests + verifier metadata |
| Machine consumer | Вериф. | Вериф. | Вериф. | Вериф. | Вериф. | Вериф. | Вериф. | Вериф. | Вериф. | Вериф. |

Для **public** недостаточен просто “headline + verdict”. Public surface должна содержать: идентификатор case/run/projection; явный статус `projection_only` или уже publishable/published state без authority laundering; список опубликованных claims с их статусом; для каждого не-продвинутого claim — краткий `why_not`; summary legal basis; summary evidence families; summary method families; uncertainty class; если выбор делался через tradeoff, то summary frontier и явное указание, был ли decisive value choice; summary participation quality and gaps; presence of dissent; redaction summary; public audit reference. Иначе public не сможет ни понять пределы, ни оспорить claim, ни отличить доказанный факт от ограниченной проекции. fileciteturn18file0L3-L3 fileciteturn19file0L3-L3 fileciteturn20file0L3-L3 fileciteturn23file0L3-L3 citeturn11view0turn15academia0

Для **dashboard consumers** ключевая обязанность иная: не полная публичная легитимация, а fail-closed operational truth. Уже сейчас validators и response shaping показывают, что dashboard нуждается в `authoritative_runtime_state`, `first_blocking_cause`, owner, phase, authority refs, evidence refs и projection labels, а `policy_design_case_projection` пока еще нормализуется из generic record rather than rich typed object. Поэтому dashboard surface должна быть не более «красивой витриной», а triage surface, где всегда видно отличие runtime authority от projection, где отсутствующий projection не превращается в `None`, и где blocked/contested/stale/draft состояния нельзя перепутать с approved authority. fileciteturn22file0L3-L3 fileciteturn33file0L3-L3 fileciteturn18file0L3-L3

Для **reviewer** entitlement должен быть reconstructive: reviewer обязан уметь восстановить, как claim был сформирован, чем поддержан, чем опровергнут, какие есть blockers, какие omissions были сделаны и почему. Это означает видимость full claim graph, legal refs, data refs, method refs, warrants, counterevidence, deficits, dissent, source-truth conflicts, readiness and publication state, replay summary, redaction log и ссылки на audit bundle. Иначе reviewer surface будет informationally thinner, чем внутренняя система, и потеряет право называться contestable. fileciteturn19file0L3-L3 fileciteturn26file0L3-L3 fileciteturn32file0L3-L3 fileciteturn31file0L3-L3

Для **expert** entitlement должен быть не просто “more details”, а доступ к тому, что меняет epistemic status claim’а: assumptions, applicability predicates, method family, alternative rejected approaches, uncertainty profile, boundedness/partial identification, distributional reversals, frontier and nondominated alternatives, social-weight provenance, participation admissibility class и residual dissent. Внутренние C15, C17, C18 и C19 прямо требуют typed warrants, conflict and contest formalism, three-layer tradeoff representation и audience-aware participation provenance; NIST аналогично требует документировать assumptions, limitations, alternative approaches, methodology, testing, dependencies и stakeholder engagement plans. fileciteturn18file0L3-L3 citeturn11view0turn13view0

Для **audit consumers** entitlement должен быть verifier-first: не только human-readable packet, но и replayable trace. Они должны видеть claim/evidence/method/legal refs, publication trust record, public/private boundary, public archive metadata, verifier result, failures/warnings, exported refs с digest’ами, standalone verifier path/command, provenance package metadata и redaction list. Внутренний ADR-0162 прямо требует, чтобы external audit evidence было replayable без private operator context, кроме явно redacted or access-controlled evidence; `external_audit.py` делает обязательными public archive, PASS verification, exported public refs с SHA-256 и explicit boundary metadata. fileciteturn25file0L3-L3 fileciteturn28file0L3-L3

Для **machine consumers** минимальное entitlement еще уже, но жестче: им не нужны prose-пояснения как primary source, зато нужны стабильные enums, schema versions, immutable refs, digests, lineage objects, omission manifests, redaction reason codes, verifier outcomes и field-to-source mappings. Иначе machine surface не сможет доказать, что public/reviewer/expert projections truthfully derived from the same authority core. Здесь внутренние `claims_ref`/`research_dag_ref` invariants, PROV categories entity/activity/agent и SLSA/in-toto verification semantics складываются в один и тот же вывод: machine surface должен быть designed for comparison, replay and falsification, а не просто для JSON serialization. fileciteturn19file0L3-L3 fileciteturn28file0L3-L3 citeturn9view0turn10view0turn10view1

## Правила редактирования и публичное объяснение why not

Ключевой критерий redaction в C39 должен быть не «можно ли это скрыть», а **останется ли claim contestable после скрытия**. С этой точки зрения без разрушения contestability можно скрывать raw transcripts, direct identifiers, linkage keys, full sensitive quotes, raw benchmark assets, private eval internals, system/developer prompt tokens и иные поля, раскрытие которых нарушает privacy, rights, security или evaluation integrity. Внутренний public export уже прямо запрещает скрытые benchmark/eval/holdout/private-eval/raw-transcript/prompt-token surfaces на public tier, а C19 отдельно требует скрывать raw participation materials и любые комбинации, ведущие к re-identification. fileciteturn19file0L3-L3 fileciteturn18file0L3-L3

Но нельзя редактировать то, что ломает право понять пределы и основания решения. Поэтому **нередактируемым минимумом** для entitled audience должен считаться сам факт blocker’а, claim status, blocker family or contest category, existence of dissent, existence of participation gaps, наличие redaction itself, summary legal basis, summary method/data basis, uncertainty class, and who may decide/reopen. Иначе redaction превращается в способ скрыть substantive weakness, а не в защиту прав. Это ровно тот failure mode, от которого внутренний register уже предостерегает в P03 и P05, а C17/C19 прямо требуют не стирать contestability/dissent/gaps даже тогда, когда underlying materials private. fileciteturn31file0L3-L3 fileciteturn18file0L3-L3

Для public users я бы рекомендовал единый typed объект **`why_not`**, который обязателен для claims со статусами `blocked`, `limited`, `contested` и `out_of_scope`. У него должны быть как минимум такие поля: `claim_id`, `status`, `reason_code`, `reason_family`, `public_explanation`, `what_is_missing_or_contested`, `what_remains_supported`, `who_can_decide`, `what_could_change_status`, `reopening_triggers`, `redaction_notice`, `audit_ref`. Это не должен быть «LLM-friendly summary», а именно contrastive object: what failed, why it failed, and what would have to change. Такой дизайн согласуется и с внутренним требованием C17 показывать what is contested / positions / evidence per side / who may decide / limitations / reopening triggers, и с explainability literature, где объяснение должно помогать понять исход, contest его и увидеть путь к изменению статуса. fileciteturn18file0L3-L3 citeturn15academia0

Практически это означает четыре публичных паттерна. Для **blocked** claim виден blocker family, governance effect и путь эскалации, но не обязательно весь скрытый материал. Для **limited** claim видно, какой именно limitation cap действует: scope mismatch, proxy evidence, uncertainty, participation weakness или недостаточная authority. Для **contested** claim видны обе стороны спора, есть ли резолюция и осталось ли residual dissent. Для **out_of_scope** claim публично сообщается не «данных нет», а что claim вышел за semantic, legal, temporal, jurisdictional или authority scope case’а. Без такого typed contrast у public surface не будет реальной contestability, а будет только PR-explanation. fileciteturn34file0L3-L3 fileciteturn18file0L3-L3

## Машиночитаемые обязательства для внешнего аудита

Чтобы external auditor мог проверить **truthfulness of projection**, одной схемы `PolicyDesignCaseProjection` недостаточно. Нужен слой machine-readable commitments, который связывает projection с authority core и делает ложную или неполную проекцию проверяемо ложной. Минимальный набор обязательств, который логически вытекает из текущего кода и внешних provenance standards, такой.

Во-первых, нужен **stable identity contract**: `schema_version`, `projection_id`, `audience`, `case_id`, `run_id`, `generated_at`, `claims_ref`, `research_dag_ref`, `source_ref`, `source_ref_fingerprint`, `authority_role`, `projection_policy`, `may_be_used_for`, `may_not_be_used_for`. Без этого нельзя доказать ни происхождение поверхности, ни ее пределы использования. Внутренний `DecisionGradeExport` уже закрепляет invariants по `claims_ref` и `research_dag_ref`, а `projection_semantics.py` — boundary fields типа `authority_role=projection_only` и `may_not_be_used_for`. fileciteturn19file0L3-L3 fileciteturn20file0L3-L3

Во-вторых, нужен **field-level derivation manifest**. Для каждого externally visible field auditor должен уметь ответить: поле скопировано, агрегировано, redacted, derived, normalized или omitted; из каких source refs оно получено; какой transformation class применялся; есть ли semantic-loss notice. Это прямо соответствует внутренней проблеме C16 — current API/dashboard surfaces are too generic and heuristic — и внешней логике PROV, где provenance умеет связывать entity, activity и agent, включая qualified relations. Если projection не умеет объяснить, как именно каждое поле возникло, machine audit truthfulness невозможен. fileciteturn18file0L3-L3 fileciteturn22file0L3-L3 citeturn9view0

В-третьих, нужен **omission and redaction ledger**, а не просто список скрытых полей. Каждый omission должен иметь `reason_code`, `audience_scope`, `claim_ids_affected`, `evidence_rights_basis`, `privacy_or_security_basis`, `public_summary_present`, `reconstructable_for_reviewer`, `audit_visibility`, и `challengeable_by`. Внутренний `OutputOmissionRecord` уже задает принцип, что omission должен быть intentional and recorded, а ADR-0162 и `external_audit.py` требуют explicit public/private boundary и list of redacted or access-controlled evidence. fileciteturn19file0L3-L3 fileciteturn25file0L3-L3 fileciteturn28file0L3-L3

В-четвертых, нужен **verifier-ready provenance envelope**: PROV-style entity/activity/agent relations, exported public refs с SHA-256, signed provenance where available, verification status, standalone verifier command, safe archive path, and downstream authenticity checks. Внутренний external audit record уже почти полностью задает этот паттерн: public archive metadata, PROV JSON status, SLSA attestation/signature/transparency metadata, verifier module, standalone verifier command, exported refs with digests, PASS/FAIL report и запрет на private operator context as prerequisite для проверки. SLSA и in-toto снаружи описывают ту же задачу: provenance must exist, be distributed to consumers, ideally be signed and tied to dedicated infrastructure, and verification must check authenticity and ordered steps. fileciteturn28file0L3-L3 citeturn10view0turn10view1turn9view0

В-пятых, нужен **semantic-preservation commitment**: auditor должен видеть не только что пакет подписан, но и что projection не promoted beyond source truth. Для этого machine surface должна содержать explicit comparisons: claim counts, blocked claim counts, approved claim IDs, blocked claim IDs, research replay status, governance status, and a projection masking check. Внутренний `frontend_trust_view`, dashboard fail-closed normalization и публикационный trust framing already point exactly here: truthfulness problem у C39 не только в подлинности bytes, но и в том, не скрыла ли projection blocker, conflict, uncertainty или non-authority status. fileciteturn19file0L3-L3 fileciteturn22file0L3-L3 fileciteturn23file0L3-L3 fileciteturn24file0L3-L3

## Сбойные режимы и защитные инварианты

**Скрытый blocker на public surface.** Это самый опасный failure mode для внешней легитимности: public видит publishable-looking narrative, но не видит, что claim blocked by legal authority, contested evidence, participation gap или stale validity. Внутренние материалы уже квалифицируют это как сочетание P03 и P05: poor external surface плюс authority dilution. Защитный инвариант здесь такой: public tier может скрывать детали blocker’а, но не сам факт blocker’а, не его family и не его effect on promotability. fileciteturn31file0L3-L3 fileciteturn19file0L3-L3

**Reviewer surface cannot reconstruct claim.** Если reviewer получает prose summary вместо claim-bound graph, он не может independently contest или verify case. C15 и ADR-0156 прямо требуют inspectable argument structure и assurance-case mapping; `DecisionGradeExport` reviewer/expert tiers уже предполагают full claim export. Защитный инвариант: reviewer tier обязан быть reconstructable back to claim, warrant, evidence, counterevidence, deficit and authority refs, even if some raw artifacts remain access-controlled. fileciteturn18file0L3-L3 fileciteturn26file0L3-L3 fileciteturn32file0L3-L3

**Machine surface lacks refs or digests.** Тогда projection может быть syntactically well-formed, но non-verifiable. Внешний auditor в этом случае имеет только «правдоподобный JSON». Защитный инвариант: ни один machine/audit export не считается sufficient без source refs, digests, verification status и explicit provenance boundary. Это поддерживается и `external_audit.py`, и SLSA/in-toto provenance logic. fileciteturn28file0L3-L3 citeturn10view0turn10view1turn9view0

**Redaction masks dissent or participation gaps.** Это особый риск для policy legitimacy, потому что именно dissent и uncovered groups чаще всего неудобны политически. Внутренний C19 прямо запрещает делать privacy поводом для стирания самой структуры спора: public должен видеть dissent presence, participation gaps, representativeness class и limitations, даже когда персоналии и raw transcripts скрыты. Защитный инвариант: privacy may hide identity and raw expression, but may not hide the existence, category and governance effect of dissent or missing groups. fileciteturn18file0L3-L3

**Dashboard promotes projection as authority.** Внутренний код уже частично защищается от этого через `projection_only`, `may_not_be_used_for`, fail-closed label normalization и explicit trust-framing caveats, но C16 сам признает, что API/dashboard surfaces still rely too much on generic dicts and heuristic consumers. Защитный инвариант: dashboard обязан одновременно показывать authoritative runtime state и projection state, never collapsing them into one badge or verdict. Любой consumer, который читает projection как approval/closeout authority, должен считаться broken consumer. fileciteturn18file0L3-L3 fileciteturn20file0L3-L3 fileciteturn22file0L3-L3 fileciteturn23file0L3-L3

**Projection fails to disclose value choice.** Для policy systems это не менее критично, чем data or method omission. C18 показывает, что scalar welfare alone is insufficient when rights, subgroup reversals, non-convex frontier or explicit value choices are decisive. Поэтому, если public/reviewer/expert surface показывает selected option, но не раскрывает whether the decisive move came from factual frontier or from evaluative transform / governance choice, это тоже legitimacy failure. Защитный инвариант: whenever value choice is decision-relevant, surface must disclose that the chosen outcome is not uniquely compelled by facts alone. fileciteturn18file0L3-L3

## Итоговая рекомендация для C39

Итоговый дизайн я бы формулировал так: **external legitimacy surface у PolicyOS должен быть не одним DTO и не одним public packet, а семейством typed projections над одним authority core, с единым claim-bound identity layer, разными entitlement profiles и общим verifier envelope**. Это семейство должно включать как минимум шесть first-class audience profiles: `public`, `dashboard`, `reviewer`, `expert`, `audit`, `machine`. Во всех шести профилях обязательны identity, non-authority/authority boundary, claim status semantics, omissions/redactions ledger и audit linkage; различается только глубина reconstruction и access to sensitive detail. fileciteturn18file0L3-L3 fileciteturn19file0L3-L3 fileciteturn25file0L3-L3

Если свести C39 к одной фразе: **каждая аудитория должна получать достаточно typed information, чтобы contest or audit то, на что она имеет право, но ни одна аудитория не должна получать projection, которую можно принять за authority без просмотра authority core**. Это прямо соответствует acceptance criterion задачи и уже встроено в лучшие части репозитория — осталось довести это до законченной audience requirement matrix, field-level derivation manifest и verifier-ready omission/redaction contract. fileciteturn20file0L3-L3 fileciteturn21file0L3-L3 fileciteturn31file0L3-L3

## Открытые вопросы и ограничения

Самые важные открытые вопросы после этого исследования остаются не в базовой логике, а в границах реализации. Первое: в репозитории уже есть strong projection guards, DecisionGradeExport tiers и external audit record, но `policy_design_case_projection` на API/dashboard уровне все еще выглядит слишком generic и partly heuristic; это делает C39 не только conceptual, но и bridge task. Второе: participation provenance внутри C19 хорошо проработан концептуально, но сам файл consolidation прямо говорит, что эта поверхность в кодовой базе пока mostly missing; значит, audience matrix для participation придется проектировать чуть более нормативно, чем для projection/audit tiers. Третье: я сознательно опирался прежде всего на внутренние PolicyOS-якоря, NIST, W3C PROV, SLSA/in-toto и SACM; я не делал основным основанием обзор EU AI Act, потому что официальный EUR-Lex текст был технически недоступен в этом окружении. fileciteturn18file0L3-L3 fileciteturn22file0L3-L3 citeturn11view0turn9view0turn10view0turn10view1turn19view0


# Контроль взрыва обязательств для PolicyOS

Я прочитал указанный файл рамки и рассматриваю C38 не как попытку заново изобрести policy engine, а как задачу по управлению уже существующими ядрами PolicyOS. В консолидированном документе прямо сказано, что система уже имеет сильные опорные поверхности — универсальную facet-grammar, temporal logic для rule body, challenge factory, VOI scheduler, статусные и authority firewalls, complexity budget, append-only lifecycle и критерии semantic false pass; пробел находится не в отсутствии формализма, а в тонкой оркестрации между кандидатами, claim-bound evidence, closeout и projection. fileciteturn4file0fileciteturn15file0fileciteturn16file0fileciteturn17file0fileciteturn18file0

Из этого следует основной вывод исследования: **PolicyOS должен разрешать неограниченное порождение сырых candidate obligations, но обязан жестко ограничивать число obligations, которые вообще могут влиять на closeout**. Это совпадает и с внутренней логикой системы, и с внешними практиками управления риском: в RFC 2119 императивы `MUST`/`SHOULD` должны применяться аккуратно и sparingly, только там, где это действительно необходимо или где нужно ограничить вредное поведение; NIST AI RMF требует приоритизировать действия по уровню риска и потенциальному воздействию, а NIST SP 800-61r3 рекомендует фильтровать большие потоки событий до объема, пригодного для человеческого анализа, и не обрабатывать все по принципу first-come, first-served. citeturn4view0turn7view1turn7view3turn24view1turn23view0

## Контекст и рамка C38

Внутренний backlog уже задает почти все концептуальные границы, внутри которых должна жить C38. C4 говорит о конечном реестре risk types и об объединении critic risks с challenge classes; C5 говорит, что obligations уже имеют формальный язык и governed lifecycle; C12 запрещает LLM выдавать authority-bearing outputs; C13 требует collapse shared sources and prompts before aggregation; C22 вводит net-VOI для выбора следующего безопасного шага; C23 отделяет run-cost и degradation-SLA от quality; C24 требует complexity ledger и soft-gate lifecycle; C25 запрещает истории становиться доказательством в текущем run; C26 требует ловить omission, overgeneration и unsupported authority; C27 прямо предупреждает не hardcode’ить saturation stopping rules без общей политики. fileciteturn15file0fileciteturn16file0fileciteturn17file0fileciteturn18file0

Во внешнем governance-контексте эти внутренние ограничения выглядят не исключением, а зрелой практикой. NIST AI RMF подчеркивает, что попытка устранить весь негативный риск целиком часто контрпродуктивна, потому что это делает triage неэффективным и тратит scarce resources; highest-risk contexts требуют наиболее срочной приоритизации и наиболее тщательного процесса управления риском, а при unacceptable negative risk развитие и deployment должны безопасно остановиться до тех пор, пока риск не будет управляем. Европейская Комиссия на текущей странице AI Act описывает риск-ориентированную модель, где high-risk AI uses несут строгие обязательства по risk assessment, logging, documentation, human oversight, robustness, cybersecurity и accuracy. citeturn7view1turn7view3turn13view0

Поэтому C38 не должна подавлять candidate generation. Ее задача уже уже более узкая и более инженерная: не дать candidate stream превратиться в бесконечный список hard gates, не позволить authority laundering из LLM или historical memory, и не допустить “тихого” удаления неудобных обязательств из reviewer/public surfaces. Именно так сформулированы внутренние firewalls PolicyOS: LLM output не может mint authority, historical learning может менять priors и budgets, но не закрывать current-run obligations, а projections и packaging summaries не должны становиться closeout evidence. fileciteturn4file0fileciteturn16file0fileciteturn17file0

## Главный архитектурный вывод

Я рекомендую для C38 **трехслойную модель хранения и gating**:

| Слой | Кардинальность | Может блокировать closeout | Что в нем хранится |
|---|---:|---|---|
| Candidate ledger | Неограниченная | Нет | Все сырые obligations, включая LLM, critics, public contestation, historical lessons |
| Bundle ledger | Ограниченная по family × scope × authority | Только после promotion | Нормализованные bundles с child_count, exemplars, independent clusters, VOI и next_action |
| Blocking frontier | Явно ограниченная complexity budget | Да | Лишь promoted bundles с blocking effect или readiness/publication cap |

Эта модель прямо следует из того, что PolicyOS уже различает candidate evidence и authority-bearing artifacts, а также хранит append-only claim lifecycle и typed deficits вместо тихого исчезновения проблемных объектов. Она также хорошо согласуется с NIST: высокий поток событий должен сначала фильтроваться и коррелироваться, а только затем попадать на человеческий triage; риск и ресурсы должны распределяться purposefully, а не по сырым счетчикам. fileciteturn4file0fileciteturn17file0fileciteturn19file0citeturn24view1turn7view1turn23view0

Ключевой принцип здесь можно сформулировать как норму C38: **сырые кандидаты дешевы и обратимы; блокирующие obligations дороги, редки и governance-bound**. Иными словами, PolicyOS MAY генерировать сотни candidate obligations, но closeout engine MUST видеть только конечный, family-scoped и authority-scoped blocking frontier. Это и есть механизм, который одновременно сохраняет исследовательскую полноту и не допускает explosion on the closeout path. citeturn4view0turn4view1turn24view1turn23view0fileciteturn15file0fileciteturn16file0

Практически это лучше делать не через один “магический” глобальный score, а через **лексикографический promotion funnel**. Сначала идут категориальные ограничения: authority allowance, legal competence, current-run admissibility, privacy legality и conflict with existing firewalls. Уже потом — сравнительные факторы: policy impact, urgency, public risk, net-VOI, marginal assurance value, cost и complexity burden. Такой порядок нужен потому, что часть внутренних правил PolicyOS — не оптимизационные, а запретительные: LLM firewall, legal competence, historical-learning firewall и data-minimization limits нельзя “перебить” просто высоким сырым score. fileciteturn16file0fileciteturn17file0fileciteturn19file0citeturn12view0turn13view0turn27view0

## Таксономия источников и матрица приоритетов

Ниже — рекомендуемая таксономия source classes для C38. Она синтезирует внутренние C5/C12/C17/C19/C22/C25 и внешнюю risk-based практику NIST/AI Act. Важная идея: **каждый source class имеет priority ceiling**. Это предотвращает ситуацию, в которой слабый источник внезапно порождает hard gate только из-за большого количества или громкой формулировки. fileciteturn15file0fileciteturn16file0fileciteturn17file0fileciteturn19file0citeturn7view3turn13view0turn27view0

| Source class | Дефолтный ceiling | Что нужно для promotion выше ceiling |
|---|---|---|
| Governed rule | `mandatory` или `authority_level_mandatory` | Уже governed; нужен scope, owner, evidence basis, authority profile |
| Legal requirement | `authority_level_mandatory` | Доказанная competence, jurisdiction, temporal validity, instrument fit, claim-level anchor |
| Deterministic critic | `conditional` | Репродуцируемость, same-input closure, связь с governed family или validated blocker |
| Producer blocker | `mandatory` в пределах зависимого scope | Typed blocker packet, affected refs, next action, authority target |
| Historical failure | `review_required` | Самостоятельно выше не поднимается; может только усиливать escalation, VOI и reviewer depth |
| LLM candidate | `candidate` | Никогда не поднимается напрямую; только через deterministic/governed validation |
| Human reviewer | `review_required` | Может стать `mandatory` лишь при явной authority envelope и typed rationale |
| Public contestation | `review_required` | Поднимается при material public risk, legal relevance или claim-linked admissible contest record |

Эта матрица соответствует внутренним firewall-правилам: LLM output не имеет права mint authority; historical memory не заменяет current-run evidence; participation и contestation должны быть typed, claim-linked и privacy-aware; legal anchors требуют competence chain, а producer blockers должны приходить как typed packets. Внешне это также согласуется с AI Act и NIST AI RMF: high-risk contexts и legally material obligations имеют другой вес, чем эвристические или exploratory сигналы. fileciteturn16file0fileciteturn17file0fileciteturn19file0citeturn13view0turn7view1turn7view3

Приоритетные классы я рекомендую задавать так:

| Priority class | Closeout effect | Видимость | Нормальный выход |
|---|---|---|---|
| `authority_level_mandatory` | Блокирует matching authority profile и public release | reviewer / expert / machine; public — как material limitation | satisfied, superseded, scope-changed, or case blocked |
| `mandatory` | Блокирует closeout в текущем scope | reviewer / expert / machine | satisfied, superseded, scoped away |
| `conditional` | Блокирует только если predicate истинна | reviewer / expert / machine | resolved, predicate-false, demoted |
| `review_required` | Не hard-block, но режет readiness/publication | reviewer / expert / machine | reviewed, accepted deficit, deferred |
| `candidate` | Не влияет на closeout | reviewer / expert / machine | promoted, deferred, rejected |
| `optional` | Улучшает assurance, но не gate | reviewer / expert / machine | completed or ignored |
| `deferred` | Не блокирует, но требует revisit trigger | reviewer / expert / machine; public — если material | reopened, expired, superseded |
| `rejected` | Не блокирует, но остается в audit trail | reviewer / expert / machine; public — если rejection material to outcome | reopened only by new evidence or new authority |

Эта матрица специально сделана близкой к BCP 14 логике RFC 2119/8174: только clearly-declared, uppercase-like статусные классы должны иметь специальное поведение, а императивы должны использоваться sparingly. Для PolicyOS это означает, что “обязательной” становится не красивая фраза и не количество кандидатов, а только объект с четкой нормализованной семантикой, lifecycle и authority effect. citeturn4view0turn4view1fileciteturn15file0fileciteturn17file0

## Правила сдерживания взрыва

Первое правило — **канонический identity tuple**. Я рекомендую нормализовать obligation до ключа вида `(obligation_family, target_scope, claim_or_case_ref, jurisdiction, authority_profile, temporal_window, affected_population, remedy_type, triggering_evidence_cluster)`. Это прямо использует внутренние concept spine, semantic signature, legal competence и evidence-line collapse. Если эти компоненты не нормализованы, PolicyOS начнет путать дубликаты с независимыми обязательствами и будет искусственно раздувать mandatory frontier. fileciteturn15file0fileciteturn16file0

Второе правило — **deduplication до promotion**. Exact duplicate — это один и тот же family/scope/remedy/trigger cluster; он сливается в одну запись с несколькими origins. Но еще важнее не exact dedup, а collapse shared lineage: если десять кандидатных obligations происходят из одного и того же dataset root, prompt/model path, legal source или transform lineage, они не должны считаться десятью независимыми причинами для gate. Внутренний C13 именно этого и требует: считать evidence strength по evidence lines, а не по raw count. Внешне NIST SP 800-61r3 рекомендует correlation across multiple sources и фильтрацию больших наборов событий до subset, пригодного для человека. fileciteturn16file0citeturn24view1turn24view0

Третье правило — **subsumption**. Обязательство A subsumes B только если удовлетворение A механически закрывает B на том же scope и authority profile, а не просто “в целом похоже”. Здесь важно использовать строгие внутренние distinction rules: scope-shifted, authority-shifted и unresolved concepts не subsume’ятся свободно. Например, `OBL-CITATION-INTEGRITY` может subsume LLM-candidate “verify references” для того же claim и того же evidence cluster, но не может subsume obligation, относящуюся к другому jurisdiction window или к другому population predicate. fileciteturn15file0fileciteturn16file0

Четвертое правило — **dominance**. A dominates B, если A дает не меньший assurance effect на том же scope, сохраняет или повышает authority truthfulness и требует не большего remediation burden. На практике dominance почти всегда должна проверяться **внутри одной obligation family**, а не поперек разных families. Иначе PolicyOS начнет делать опасные обмены вида “один сильный legal blocker заменяет несколько privacy blockers”. Между families допустим не dominance, а contest set и human triage. Это соответствует внутреннему разделению conflict, contestability, tradeoff и participation provenance. fileciteturn16file0fileciteturn19file0

Пятое правило — **grouping into bundles**. Bundle — это не потеря информации, а change of granularity. Я рекомендую делать bundle по ключу `(family, scope, authority_profile, temporal_window, remedy_path)` и разрешать только **один active bundle на один такой ключ**. Это и есть главный structural bound на blocking frontier: даже если LLM или critic сгенерировали 200 child obligations об evidence freshness, в closeout они могут превратиться максимум в один `OBL-SOURCE-FRESHNESS` bundle на заданный scope. Количество child obligations остается видимым, но количество gating objects становится конечным. fileciteturn15file0fileciteturn17file0citeturn24view1

Шестое правило — **promotion only by stop rules**. Я рекомендую такие stop rules располагать в следующем порядке.

**Authority gate.** Если source class не имеет права mint authority, obligation не может стать blocking. Это автоматически удерживает historical_failure на уровне priors/escalation и LLM_candidate на уровне candidate. fileciteturn16file0fileciteturn17file0

**Impact and public-risk gate.** Promotion допустим, когда unresolved obligation materially влияет на claim support, legal competence, public safety, rights, or publication truthfulness. NIST AI RMF прямо советует prioritise based on assessed risk and potential impact, а highest-risk contexts — urgency first. Европейская Комиссия по AI Act описывает high-risk uses как несущие strict obligations до market placement. citeturn7view1turn7view3turn13view0

**VOI and marginal-assurance gate.** Если дополнительное действие не дает положительного net value, bundle не должен расти до hard gate. Внутренний C22 уже задает `net_voi = decision_gain + falsification_value + governance_value + authority_gain - direct_cost - latency_penalty - privacy_legal_penalty - degradation_penalty - calibration_debt`, а C24 требует вести marginal assurance value в complexity ledger. Во внешней decision-analysis литературе EVSI как раз и используется, чтобы сравнивать benefit and cost of additional information-gathering strategies и выбирать те дизайны, которые дают greatest net benefit. fileciteturn17file0citeturn17academia0turn17academia4

**Privacy and legality gate.** Если remediation требует собирать персональные данные сверх необходимого, PolicyOS не должен автоматически эскалировать obligation в blocking acquisition step. ICO формулирует data minimisation как требование держать personal data adequate, relevant and limited to what is necessary, и прямо говорит, что нельзя собирать данные “на всякий случай”. Это делает часть candidate obligations не blocking, а demand-for-justification obligations: сначала докажи necessity, потом собирай. citeturn12view0

**Complexity-budget gate.** Когда blocking frontier переполнен, новый bundle должен либо вытеснить менее ценный active bundle, либо остаться `review_required`/`deferred`. Это не простая оптимизация UX; внутренний C24 прямо считает false-block rate, ceremonial compliance risk и authority-level optionality load-bearing policy fields. NIST SP 800-61r3 при ресурсных ограничениях тоже требует triage, а не FIFO. fileciteturn17file0citeturn23view0turn24view1

**Time-window gate.** Если полезная remediation не успевает до decision window, obligation не должно множить бессмысленные gates. Оно должно конвертироваться либо в `deferred` с reopen trigger, либо в lifecycle/revalidation obligation, либо в explicit closeout block, если без него case был бы authority-laundered. Это соответствует внутренним C20/C21 правилам про revalidation и prohibition on silently reinterpreting a closed case later. fileciteturn19file0fileciteturn17file0

Для overflow handling я рекомендую такую матрицу:

| Overflow condition | Автоматическое действие | Когда обязателен human triage |
|---|---|---|
| Много exact duplicates | Merge into one child set | Никогда, если scope/authority identical |
| Много детей одной family с одним remedy path | Auto-bundle | Если bundle задевает public-risk or legal authority |
| Bundle гетерогенен по jurisdiction/time/population | Narrow scope into sibling bundles | Если scope split меняет public meaning |
| Много низко-VOI детей внутри bundle | Keep exemplars, sample the rest, preserve counts | Если sampling может скрыть material dissent |
| Complexity budget исчерпан | Defer/displace lowest-value bundle | Если вытеснение затрагивает mandatory or public-risk bundle |
| Конфликт privacy vs evidence acquisition, legal vs implementation, public contestation vs current evidence | Create contest set | Всегда |

Как стартовые implementation defaults я бы рекомендовал: auto-bundle при `>=5` нормализованных детей в одном ключе; sample after dedupe при `>20` children или `>5` independent evidence clusters в bundle; human triage при `>7` unresolved active bundles на один claim или `>12` на весь case. Это **не внешние стандарты**, а стартовые инженерные значения, выведенные из C24 complexity budget и внешнего требования сводить high-volume streams к human-viewable subset; их нужно калибровать на false-block rate и reviewer burden telemetry. fileciteturn17file0citeturn24view1turn24view0

## Рекомендуемая политика C38

Ниже — рекомендуемая формулировка самой политики.

1. **PolicyOS MUST принимать все obligation candidates в append-only candidate ledger и MUST NOT позволять raw candidates напрямую влиять на closeout.** В blocking pipeline входят только promoted bundles. fileciteturn17file0fileciteturn19file0

2. **PolicyOS MUST применять priority ceilings по source class.** `llm_candidate` никогда не поднимается выше `candidate`; `historical_failure` не поднимается выше `review_required`; `public_contestation` и `human_reviewer` требуют claim-linked typed record; `legal_requirement` требует competence, jurisdiction и temporal validity; `governed_rule` и `producer_blocker` являются единственными обычными путями к immediate blocking effect. fileciteturn15file0fileciteturn16file0fileciteturn17file0fileciteturn19file0

3. **PolicyOS MUST canonicalize, deduplicate, collapse shared lineage and group before promotion.** Count of raw children MUST NEVER be used as a proxy for independent support or for gate multiplicity. fileciteturn16file0citeturn24view1turn24view0

4. **PolicyOS MUST permit at most one active bundle per `(family, scope, authority_profile, temporal_window, remedy_path)` key, and SHOULD bound the total active frontier by the complexity budget rather than by raw candidate count.** Это делает насыщение конечным, не уничтожая visibility. fileciteturn15file0fileciteturn17file0

5. **PolicyOS MUST use lexicographic promotion rules.** Сначала: authority allowance, legality, current-run admissibility, privacy legality, material public risk. Затем: policy impact, urgency, VOI, marginal assurance value, cost, degradation и reviewer burden. Это предотвращает ситуации, где prohibited source или privacy-violating acquisition “выигрывает” только из-за большого score. fileciteturn16file0fileciteturn17file0citeturn7view3turn12view0turn13view0

6. **PolicyOS SHOULD treat `review_required` as a readiness/publication cap, а не как слабый pass.** Внутренние soft gates должны иметь owner, TTL, escalation path и publication effect; они не должны превращаться в shelf-ware. fileciteturn14file0fileciteturn17file0

7. **PolicyOS MUST keep `deferred` and `rejected` obligations visible.** Для каждой такой записи нужны reason code, resolver role, time, supporting refs, reopen trigger и supersedes/superseded-by. Они не блокируют closeout, но остаются в reviewer/expert/machine projections, а material entries должны быть отражены и в public limitation surface. fileciteturn17file0fileciteturn18file0fileciteturn19file0

8. **PolicyOS MUST track C38 with explicit telemetry.** Минимальный набор: `candidate_count`, `bundle_count`, `active_frontier_count`, `candidate_to_blocking_ratio`, `silent_drop_rate`, `llm_authority_leakage_rate`, `deferred_visibility_rate`, `rejected_reason_coverage`, `mandatory_bundle_false_positive_rate`, `reviewer_minutes_per_case`, `ceremonial_compliance_risk`, `false_block_rate`. `silent_drop_rate` и `llm_authority_leakage_rate` должны стремиться к нулю. fileciteturn16file0fileciteturn17file0fileciteturn18file0

## Стресс-тесты и критерии приемки

Ниже — сценарии, на которых C38 нужно проверять раньше внедрения.

| Стресс-сценарий | Что приходит на вход | Что должна сделать C38 | Ожидаемый итог |
|---|---|---|---|
| LLM burst | 120 LLM-кандидатов про freshness, legality и fairness | Оставить все в candidate ledger, collapse by family/scope, показать child_count и exemplars, запретить direct promotion | 0 raw hard gates; максимум несколько candidate/review bundles |
| Deterministic critic swarm | 60 critic warnings из двух evidence clusters | Collapse shared lineage, group by remedy path, поднять только validated bundles | 1–2 bundles вместо 60 gates |
| History overload | 40 historical failures + 8 current-run gaps | Использовать history только для VOI/escalation | Блокируют только current-run bundles |
| Public contestation overload | 30 public objections, часть без representativeness, часть privacy-sensitive | Split by claim use, keep contest records visible, restrict inappropriate generalization, cap publication where needed | Нет silent deletion; нет population-level overclaim |
| Producer outage cascade | 1 upstream data outage порождает 25 dependent missing-evidence signals | Emit one producer blocker bundle + dependent context-only children | Один clear blocker с next action, а не 25 gates |
| Multi-jurisdiction legal burst | 15 legal obligations across dates and jurisdictions | Split by competence/time window, reject weak matches, promote only competent anchors | Блокируют только legally applicable bundles |

Эти стресс-тесты напрямую продолжают внутренние требования PolicyOS: claim-bound evidence, concept/time/geography matching, effective independence collapse, public contestability, typed blocker packets, complexity budgeting и semantic-false-pass evaluation. Во внешнем плане они также соответствуют NIST: large adverse-event volumes должны фильтроваться и correlate’иться; triage должен учитывать impact, scope, time-critical nature и resource availability; GenAI risks должны ранжироваться по severity и likelihood, а risk management resources — перераспределяться accordingly. fileciteturn16file0fileciteturn17file0fileciteturn18file0fileciteturn19file0citeturn24view1turn23view1turn23view0turn27view0

С точки зрения acceptance criterion C38, предлагаемая схема делает именно то, что нужно. Она **разрешает богатую генерацию candidates**, потому что candidate ledger не ограничивается и не обрезает неудобные сигналы. Она **не допускает unbounded mandatory gates**, потому что blocking effect получает только конечный набор promoted bundles, а не raw children. И она **не допускает hidden deletion of inconvenient obligations**, потому что deferred/rejected entries остаются в append-only visibility path и могут быть reopened только через новое evidence или новую authority basis. Поэтому LLM может быть продуктивным генератором идей и рисков, но не сможет сам превратить идеи в обязательные closeout gates; а человек или governed subsystem сможет уменьшать шум, не скрывая следов принятого решения. fileciteturn16file0fileciteturn17file0fileciteturn18file0citeturn4view0turn7view1turn24view1


# C35 Политика временных порогов блокировки по калибровке для PolicyOS

## Что уже зафиксировано в framework PolicyOS

В репозитории PolicyOS уже задана очень важная рамка для C35: калибровка должна рассматриваться как **ledger исторического трек-рекорда**, а не как суррогат текущего доказательства по кейсу. В ADR-0163 прямо сказано, что ledger калибровки хранит coverage интервалов, bias прогноза, ошибки realized-versus-predicted, reversal/retraction rates и причины severe misses по доменам, юрисдикциям, семействам методов, классам данных, mode evidence и authority profile; слабая калибровка может менять будущие evidence budgets, eligibility authority profile, reviewer escalation и required uncertainty width, но **не может** “backfill” отсутствующие доказательства в текущем кейсе. Это хорошо согласуется и с reflexive-memory слоем, где прошлые уроки разрешены как warnings/anti-patterns, но не как claim support. fileciteturn13file0L3-L3 fileciteturn22file0L3-L3

Внутренние поверхности уже дают почти все нужные опоры для временной политики. Calibration governance у вас уже выводит Brier score, log score, reliability bins, ENCE, calibration-by-group, fairness gaps, tail-risk drift и human-escalation triggers; missing evidence должен отражаться как explicit gaps, а не как «молчаливо хорошая калибровка». Отдельно source-quality calibration прямо объявляет композитный score **advisory** до тех пор, пока не принят эмпирический calibration set, а publication gates не должны опираться только на числовой score. Human-review calibration уже использует pass/warn/fail и делает `fail` blocking quality evidence для serious production approval. VOI default-enable уже fail-closed: если safety хуже статического baseline, cost targeting не улучшается или есть regret/blockers, default enable запрещён. А Wave 31 best-in-class benchmarking уже требует reversal rate, retraction rate и calibration error как обязательные метрики. fileciteturn9file0L3-L3 fileciteturn11file0L3-L3 fileciteturn10file0L3-L3 fileciteturn20file0L3-L3 fileciteturn24file0L3-L3 fileciteturn25file0L3-L3

Есть и полезный внутренний шаблон для того, **как** превращать историческую калибровку в gating-решение: DDM audit уже использует empirical false-positive rate, верхнюю границу 95% доверительного интервала, explicit `pass`, а также expiration и invalidation triggers. Это хорошая модель для C35 в целом: не блокировать по «голой» точечной оценке, а блокировать только когда и point estimate, и консервативная bound-логика показывают проблему в достаточно релевантном bucket. fileciteturn15file0L3-L3 fileciteturn16file0L3-L3

## Что исследование подсказывает о применении калибровки к authority

Внешние рамки подтверждают, что C35 должен быть **context-specific**, а не глобальным. NIST AI RMF пишет, что риск должен оцениваться как функция вероятности и масштаба вреда, что метрики могут быть oversimplified или gamed, что harms различаются по группам и контекстам применения, а измерения в лаборатории могут не совпадать с рисками в реальном deployment. NIST GenAI Profile добавляет, что нужно документировать acceptable context of use, risk measurement plans, учитывать past incidents and failure modes, не переоценивать количественные метрики вне контекста, проверять репрезентативность benchmark’ов и делать continuous monitoring impacts across sub-populations. Это прямо толкает к политике, где: не существует одной универсальной calibration score; блок должен быть scoped; sparse history должен сначала повышать scrutiny, а не делать вид, будто истина уже установлена. citeturn5view0turn6view0turn6view3

SR 11-7 даёт почти тот же нормативный вывод, но в языке model governance: model risk растёт с complexity, input uncertainty, extent of use и potential impact; validation должна включать conceptual soundness, ongoing monitoring и outcomes analysis; когда данные для сильной валидации ограничены, организация должна не «забывать» про риск, а, наоборот, усиливать внимание к ограничениям, ограничивать model use, добавлять compensating controls и информировать senior management. Для C35 это означает простое правило: **недостаток истории не отменяет риск, а переводит систему в более консервативный operational posture**. citeturn18view0

Техническая литература тоже поддерживает именно такую структуру. Работы по calibration показывают, что probabilistic outputs часто бывают плохо откалиброваны и что calibration нельзя сводить к accuracy. Работы по selective classification показывают, что при высокой неопределённости или слабом confidence signal разумный ответ — **снижать coverage/authority**, то есть abstain или narrow scope, а не делать лишне смелый pass. Conformal-prediction литература подчёркивает, что coverage и ширина uncertainty sets связаны trade-off’ом: если history говорит, что under-coverage систематична, безопасная реакция — widening uncertainty и tightening authority. Работы о fairness/calibration показывают, что calibration across groups не сводится к одному общему агрегату и что group-level behavior нужно отслеживать отдельно. citeturn15academia1turn15academia0turn16academia0turn13academia0

Из этого следует практический вывод для C35: метрики надо делить не только по названию, но и по **типу управленческого последствия**. Есть метрики safety-critical, которые оправдывают scoped caps или blocks на будущие high-authority runs; есть метрики, которые должны влиять на review depth, budgets и provider selection, но не быть самостоятельным blocker; и есть метрики control-quality, которые, если плохи, должны прежде всего отключать автоматизм самого blocking-механизма. Именно поэтому false-pass rate и severe under-coverage важнее как blocker-метрики, чем, например, low blocker precision; low blocker precision говорит скорее о том, что **автоматический блокировщик сам плохо откалиброван** и его надо переводить в human-adjudicated mode, а не усиливать им власть по умолчанию. citeturn18view0turn6view0turn6view3

## Предлагаемая политика порогов блокировки

Ниже — **предлагаемая временная политика** для C35, совместимая с уже существующим design language репозитория.

Прежде всего должен действовать жёсткий separation rule:

> **Историческая калибровка ограничивает будущую authority и controls; она не закрывает и не опровергает текущий claim.**  
> История может только: повысить review depth, расширить uncertainty envelope, увеличить evidence budget, сузить publication scope, запретить определённый provider/method/domain bucket или понизить maximum authority level. Она не может заменить текущие evidence lines, current-run validation, current-case synthesis или human oversight. fileciteturn13file0L3-L3 fileciteturn22file0L3-L3

Второй принцип — **scope-first blocking**. Базовый bucket для исторической калибровки я рекомендую определить как:

`claim family × domain × jurisdiction × method family × provider × authority level`

Ограничение должно начинаться с **самого узкого bucket**, для которого есть достаточная история. Расширять блок с узкого bucket на provider-wide, method-wide, domain-wide или jurisdiction-wide уровень можно только тогда, когда проблема воспроизводится минимум в двух смежных bucket’ах или когда есть убедимый common-cause механизм. Например, systematic under-coverage только у одного provider в causal-claims / UA-jurisdiction не даёт права глобально банить provider everywhere; а вот повторяющаяся проблема одного и того же provider в нескольких доменах при сходном режиме использования уже оправдывает provider-level restriction. Такой scoped подход лучше соответствует и NIST, и SR 11-7, и внутреннему ADR-0163, где calibration ledger уже проектируется по domain / jurisdiction / method / authority dimensions. citeturn5view0turn18view0 fileciteturn13file0L3-L3

Третий принцип — деление метрик на три класса.

**Класс, который может cap/block high-authority future runs при зрелой истории:**

- severe interval under-coverage;
- false-pass rate;
- reversal rate;
- retraction rate;
- material group/domain calibration gap;
- persistent decision-direction bias, если он уже проявляется в reversals/retractions или несёт явный direction-of-decision harm. fileciteturn13file0L3-L3 fileciteturn24file0L3-L3 fileciteturn25file0L3-L3

**Класс, который должен влиять на review depth, budgets, provider ranking и uncertainty, но не быть solitary blocker без дополнительного adverse evidence:**

- Brier score;
- reliability / bin calibration;
- log score;
- ENCE / uncertainty-quality diagnostics;
- generic forecast bias без observed harmful consequence. fileciteturn9file0L3-L3 citeturn15academia1

**Класс, который должен прежде всего калибровать сам control layer, а не блокировать future runs:**

- blocker precision;
- false-block rate.

Если эти две метрики плохие, правильный ответ — не “блокировать сильнее”, а: отключать auto-block, переводить соответствующий blocker в reviewer-adjudicated mode, публиковать warning о low blocker trust и пересобирать threshold registry. Это особенно важно, потому что NIST прямо предупреждает об over-reliance on metrics and methodologies without sufficient awareness of their limitations in context of use. citeturn6view0turn6view3

Для временных tolerance bands я рекомендую вот такую консервативную схему:

| Метрика | Warn | Mandatory review | Readiness cap | High-authority block |
|---|---:|---:|---:|---:|
| Under-coverage gap к номиналу | > 5 п.п. | > 8 п.п. | > 10 п.п. | > 10 п.п. при зрелой истории и сохранении breach по 95% bound |
| False-pass rate | > 5% | > 8% | > 10% | > 10% при зрелой истории |
| Reversal rate | > 2% | > 4% | > 5% | > 5% при зрелой истории |
| Retraction rate | любая повторяемая ненулевая серия | > 2% | > 3% | > 3% при зрелой истории |
| Material subgroup / domain gap | > 5 п.п. | > 8 п.п. | > 10 п.п. | > 10 п.п. в самом subgroup bucket при зрелой истории |
| Reliability error / Brier degradation | хуже baseline на 10% | хуже baseline на 15% | хуже baseline на 20% | только вместе с adverse realized-outcome metric |
| Blocker precision | < 0.70 | < 0.65 | auto-block off | auto-block off; review only |
| False-block rate | > 25% | > 30% | auto-block off | auto-block off; review only |

Это именно **interim governance tolerances**, а не утверждение, что такие числа универсально оптимальны для всей науки о calibration. Их смысл — дать рабочий fail-closed operating rule до накопления собственной истории в PolicyOS. Логика выбора такая: safety-critical realized-outcome metrics могут ограничивать authority; score-like diagnostics в основном меняют scrutiny; control-quality metrics должны сдерживать автоматизм блокировщика. Такая иерархия лучше согласуется с вашими существующими surfaces — best-in-class benchmarking, calibration governance, DDM pass/fail by confidence bound, human-review calibration и VOI default-enable gating. fileciteturn9file0L3-L3 fileciteturn10file0L3-L3 fileciteturn15file0L3-L3 fileciteturn16file0L3-L3 fileciteturn20file0L3-L3 fileciteturn24file0L3-L3

Отдельно отвечая на пункт “which metrics require longitudinal evidence before becoming blockers”: **все исторические C35-blockers требуют longitudinal resolved-outcome evidence**. То есть interval coverage, Brier/reliability, bias, reversal, retraction, false-pass, group/domain calibration не должны становиться blockers на основании thin or pre-outcome evidence. Blocker precision и false-block требуют ещё и adjudicated label о том, был ли block действительно justified. Исключение — не C35-history, а уже существующие current-run governance surfaces: например, DDM empirical false-positive audit, mandatory adversarial suite failures, human-review calibration fail. Они могут блокировать текущую поставку как live validation evidence, но это уже не “poor history closes the case”, а обычный current-run control. fileciteturn10file0L3-L3 fileciteturn15file0L3-L3 fileciteturn28file0L3-L3

## Временная таблица решений при sparse history

Главная цель sparse-history policy — сделать недостаток истории **видимым и управляемым**, но не позволить ему притворяться доказанным adverse track record.

| Состояние истории | Минимум данных в relevant bucket | Что разрешено делать | Что запрещено делать |
|---|---|---|---|
| Недостаточная история | < 30 resolved cases **или** < 10 error opportunities | Пометить `insufficient calibration history`; показать warning; немного расширить uncertainty; потребовать дополнительную evidence line для high-authority run | Любой automatic block только по истории; provider/domain blacklist |
| Тонкая история | 30–99 resolved cases **и** 10–19 error opportunities | Mandatory reviewer note; +дополнительная независимая проверка; narrower publication scope; shadow / advisory posture вместо default high authority | Полный production/public block только из-за history |
| Формирующаяся история | 100–199 resolved cases **и** ≥ 20 error opportunities в минимум двух review windows / release windows | Mandatory review; readiness cap на один authority level ниже; widened uncertainty; provider/method downgrade; запрет best-in-class claim в affected bucket | Широкий global block без replication across adjacent buckets |
| Зрелая неблагоприятная история | ≥ 200 resolved cases **и** ≥ 50 error opportunities, либо эквивалентная длинная история в нескольких окнах, **и** breach сохраняется по 95% bound | Scoped high-authority block; fallback на lower authority / narrower scope / другой provider / другой method family; remediation plan обязателен | Представлять историю как refutation текущего claim или как substitute for current evidence |

Здесь `error opportunity` нужно считать отдельно по каждой метрике. Для interval coverage это resolved forecasts with realized outcomes; для reversal/retraction — опубликованные или approved high-authority decisions, дошедшие до observation window; для false-pass — случаи, которые прошли gate, но потом получили confirmed material failure; для blocker precision / false-block — случаи, где блок был потом adjudicated как justified или unjustified. Такой design предотвращает типичную ошибку: когда dashboard показывает много “runs”, но на самом деле у метрики мало реальных разрешённых outcome-opportunities. fileciteturn13file0L3-L3 fileciteturn15file0L3-L3 fileciteturn16file0L3-L3

Эта таблица совместима и с существующей policy language репозитория. Она сохраняет явную разницу между gap, warn, fail и block; позволяет reflect missing evidence as explicit gap, а не как inflation of trust; и хорошо сочетается с calibration leaderboard, где missing evidence channels уже должны становиться `gap_flags`, а не silently improve rank. fileciteturn9file0L3-L3 fileciteturn26file0L3-L3

## Как калибровка должна менять VOI, evidence budgets, uncertainty, provider selection и review depth

Самый важный operational effect C35 — калибровка должна менять **resource allocation и authority posture**, но не превращаться в current-case evidence. Внутренний VOI calibration слой уже требует, чтобы learned/shadow scheduling не было хуже static baseline по safety и cost targeting, а при наличии blockers default enable запрещался. Это означает, что calibration history естественным образом должна входить в VOI не как “доказательство за claim”, а как **penalty on automation and confidence in scheduling policy**. fileciteturn20file0L3-L3

Практически я рекомендую такую связь:

- при `warn`: увеличить evidence budget на 15–25%, расширить uncertainty envelope примерно на 10–20%, добавить хотя бы один independent evidence strand или один adversarial / counterevidence pass, но authority level не понижать автоматически;
- при `mandatory review`: увеличить evidence budget на 25–50%, расширить uncertainty envelope на 25–50%, потребовать более глубокий human review и явно показать calibration note в packet;
- при `readiness cap`: запретить best-in-class or public high-authority posture в affected bucket, перевести run на one-step-lower authority profile, отключить default-enable VOI и auto-promotion;
- при `block`: не запускать requested high-authority route в affected bucket, а требовать alternate provider, alternate method family, narrower jurisdiction/domain scope или explicit remediation cycle. fileciteturn20file0L3-L3 fileciteturn24file0L3-L3 fileciteturn25file0L3-L3

Для provider selection нужна отдельная оговорка. Ваш source-quality слой уже правильно фиксирует, что numeric source-quality composite advisory-only до принятия empirical calibration set. Поэтому provider quality и source quality нельзя использовать как hard truth score. Зато их можно и нужно использовать как **routing signal**: при thin history провайдер не должен быть единственным источником high-authority run; при adverse mature history провайдер должен быть disallowed именно в affected bucket; при ambiguous history — paired-provider corroboration и deeper review вместо blacklist-by-score. Это будет намного чище и epistemically safer, чем разрешать advisory numeric score silently decide authority. fileciteturn11file0L3-L3

Review depth тоже должен расти не “вообще”, а по типу проблемы. Если проблема в under-coverage, review должен проверять uncertainty construction и whether the case is overclaiming precision. Если проблема в reversals/retractions, review должен идти в warrant reliability, case lifecycle и post-publication monitoring. Если проблема в low blocker precision / high false-block, review должен верифицировать сам control regime и отключать auto-block. Если проблема subgroup/domain-specific, review должен ограничивать publication scope этой группой или context of use, а не искать глобальный verdict. Такой context-specific review лучше совпадает и с NIST guidance, и с тем, что у вас уже есть human-review calibration, adversarial challenge factory и governance layering. citeturn6view0turn6view3turn18view0 fileciteturn10file0L3-L3 fileciteturn23file0L3-L3 fileciteturn28file0L3-L3

В терминах acceptance condition пользователя это означает следующее: **PolicyOS сможет использовать плохую историческую калибровку, чтобы ограничивать будущие runs, но не будет делать вид, будто эта история “закрывает” или “опровергает” текущий claim.** История меняет permissions, penalties, scrutiny, width of uncertainty и allowed authority scope; истина по текущему кейсу всё равно решается текущими evidence lines, synthesis, oversight и runtime quality surfaces. fileciteturn13file0L3-L3 fileciteturn22file0L3-L3

## Открытые вопросы и ограничения

Самая большая неопределённость здесь не концептуальная, а **численная**: внешняя литература хорошо поддерживает context-specific governance, ongoing monitoring, subgroup-aware evaluation, abstention/reduced coverage under uncertainty и fail-closed posture при ограниченной валидации, но не даёт одного универсального, общепринятого набора чисел для policy-authority gating в таких системах, как PolicyOS. Поэтому проценты и sample-sufficiency cutoffs выше надо понимать как **interim policy choices**, а не как окончательную научную константу. citeturn5view0turn6view0turn18view0

Вторая граница: найденные внешние источники были особенно сильны по governance principles и calibration-as-risk-management, но менее полны по domain-agnostic sample-size canon именно для каждого из ваших metric families. Поэтому я бы рекомендовал зафиксировать эту C35 policy как временную, а затем после накопления собственных ledger данных провести внутренний backtest по buckets и обновить thresholds через отдельный calibration-threshold tuning ADR. Это как раз хорошо укладывается в то, как у вас уже устроены DDM audit, calibration governance, leaderboard gap flags и append-only lifecycle learning. fileciteturn15file0L3-L3 fileciteturn16file0L3-L3 fileciteturn26file0L3-L3 fileciteturn13file0L3-L3


# Политика эволюции правил и публичной переоценки для PolicyOS

## Исходная рамка и то, что уже есть в PolicyOS

Эта задача в репозитории не является greenfield. Внутри текущего исследовательского каркаса она уже разложена как связка **C20 lifecycle/revalidation** и **C21 rule evolution/replay/legacy retirement**: backlog прямо фиксирует, что жизненный цикл кейса должен оставаться «живым» объектом, а rule evolution не должен молча переинтерпретировать закрытый PDC. В том же consolidated backlog rule evolution названа частично готовой областью: стабильное ядро уже включает claim lifecycle, temporal logic, schema compatibility, Data Forge snapshot/source contract primitives и projection guardrails, но недостающим мостом остается **semantic rule lineage and stricter-rule detection**. fileciteturn11file0L3-L3 fileciteturn39file0L3-L3 fileciteturn40file0L3-L3 fileciteturn43file0L3-L3

Кодовая база уже дает важные опорные механизмы, на которые разумно опереться, а не изобретать новый слой с нуля. `schema_compat.py` и registry TOML уже различают шесть решений совместимости — `compatible`, `compatible_with_migration`, `legacy_quarantined`, `unknown_schema_blocked`, `incompatible_blocked`, `stale_schema_blocked` — и верифицируют lossless migration через хэши исходного и целевого payload, соответствие target current schema и отсутствие semantic loss; Research DAG уже умеет audit/pinned replay и comparison report; append-only claim lifecycle запрещает тихое удаление и тихий downgrade publishable claims; continuous governance уже выводит публичные статусы `valid`, `monitoring`, `stale`, `review_required`, `superseded`, `reissued`, `withdrawn`; closeout compatibility уже требует `git_sha`, `code_revision`, schema-compatibility validation refs для serious closeout; Fabric `SourceContract` уже имеет `draft/active/deprecated/sunset` и deprecation policy с replacement/migration_note/sunset_at; Data Forge уже хранит deterministic migration paths; shims уже управляются owner/sunset/migration target и CI-проверками. Это означает, что новая политика должна не заменить эти элементы, а связать их единым semantic-lineage слоем. fileciteturn14file0L3-L3 fileciteturn27file0L3-L3 fileciteturn28file0L3-L3 fileciteturn30file0L3-L3 fileciteturn15file0L3-L3 fileciteturn17file0L3-L3 fileciteturn18file0L3-L3 fileciteturn20file0L3-L3 fileciteturn21file0L3-L3 fileciteturn22file0L3-L3 fileciteturn25file0L3-L3 fileciteturn26file0L3-L3 fileciteturn38file0L3-L3

Мой главный вывод такой: для PolicyOS надо жестко разделить **две оси изменения**. Первая ось — **schema/ABI readability**: может ли consumer прочитать старый артефакт или доказуемо мигрировать его без semantic loss. Вторая ось — **rule/taxonomy semantics**: будет ли тот же набор входов означать то же самое с точки зрения admissibility, scope, authority truthfulness, readiness и publication. Первая ось уже хорошо покрыта кодом; вторая — именно тот policy gap, который нужно закрыть публичной политикой эволюции правил. fileciteturn43file0L3-L3 fileciteturn14file0L3-L3 fileciteturn27file0L3-L3

## Нормативные принципы политики

Базовое правило PolicyOS должно звучать так: **закрытый PDC исторически неизменяем по смыслу, но не автоматически сохраняет статус текущего guidance**. Это уже соответствует внутреннему синтезу C21: historical meaning closed case определяется semantic refs, old-logic replay обязателен для аудита, current-logic replay носит сравнительный характер, а grandfathering сохраняет архивный статус, а не current validity. fileciteturn43file0L3-L3

Из этого следуют пять policy-принципов.

**Первый принцип — historical meaning is immutable.** Если кейс был закрыт под V1, то его исходный смысл должен оставаться воспроизводимым через audit replay и неизменяемый semantic tuple. Новые правила не переписывают старое решение «задним числом»; они могут только породить review, revalidation, supersession или withdrawal record поверх него. Этот подход хорошо согласуется и с внутренним C21, и с осторожным отношением публичного административного права к ретроактивному rulemaking: даже вне буквального правового контекста это сильный design signal против молчаливой обратной силы. fileciteturn43file0L3-L3 citeturn11view0

**Второй принцип — schema migration never implies semantic equivalence.** Если старый payload читается или losslessly migrated, это еще не значит, что его claim admissibility, blocker logic, freshness window или taxonomy boundary остались теми же. Именно поэтому semantic rule lineage должен жить отдельно от schema lineage. Внутренний C21 это формулирует прямо, а `schema_compat.py` уже реализует fail-closed модель именно на schema-уровне, а не на уровне policy meaning. fileciteturn43file0L3-L3 fileciteturn14file0L3-L3 fileciteturn27file0L3-L3

**Третий принцип — public effect must scale with public reliance.** Если изменение касается только внутренней сериализации и не меняет смысл опубликованного guidance, достаточно internal migration или тихой архивной перегенерации. Но если меняется external reliance posture — например, claim был publishable, а стал review-required или blocked, либо изменилась taxonomic boundary, по которой общественность понимает scope кейса, — тогда нужен не просто rerun, а публичный след: annotation, reissue review, supersede или withdrawal review. Как design analogy это хорошо совпадает с OMB Good Guidance Practices: significant guidance должны быть публично индексированы с issuance/revision dates, на них должен быть канал для comments и requests to reconsider/modify/rescind, а economically significant guidance требуют Federal Register notice, public comment и response-to-comments document. fileciteturn20file0L3-L3 fileciteturn43file0L3-L3 citeturn20view0turn21view1turn21view2turn22view1

**Четвертый принцип — provenance must be first-class, not narrative.** Для публичной воспроизводимости нужен не рассказ «какая была версия правил», а машиночитаемый provenance bundle: entities, activities, agents, derivations, versioning and reproducibility artifacts. Это соответствует и внутреннему намерению C21 хранить immutable semantic tuple, и более общему подходу W3C PROV, где provenance, reproducibility, versioning и derivation входят в ядро модели. fileciteturn43file0L3-L3 citeturn14view0

**Пятый принцип — taxonomy moves must be explicitly typed.** Простое «обновили taxonomy version» недостаточно. Для public policy критично различать alias/equivalence, refinement, broadening/narrowing и authority-changing remap. Это хорошо согласуется с рекомендацией C21 различать `alias_only`, `refinement`, `boundary_change`, `authority_change` и с SKOS-моделью, где `exactMatch`, `closeMatch`, `broadMatch` и `narrowMatch` имеют разные свойства и не могут считаться взаимозаменяемыми. fileciteturn43file0L3-L3 citeturn16view0turn16view1turn16view2

## Классы изменений и публичные эффекты

Ниже — рекомендуемая политика классификации. Она опирается на C20/C21 synthesis, существующий schema compatibility слой, append-only claim lifecycle, governance statuses и публичные notice/comment ориентиры для materially consequential guidance. fileciteturn43file0L3-L3 fileciteturn14file0L3-L3 fileciteturn18file0L3-L3 fileciteturn20file0L3-L3 citeturn21view2turn22view1

Сначала полезно зафиксировать значения публичных эффектов:

- **No notice** — изменение чисто внутреннее и не меняет public meaning.
- **Internal migration** — перепаковываем/мигрируем хранилище, но public semantics не меняются.
- **Public annotation** — текущий публичный артефакт получает явную пометку о version drift, revision date и ссылку на comparison/revalidation record.
- **Reissue review** — открывается review packet на частичный или полный reissue, но старый кейс пока не заменен.
- **Supersede** — публикуется новый current PDC, а старый остается архивно-действительным.
- **Withdrawal review** — открывается review о прекращении использования кейса как current guidance.
- **Mandatory revalidation** — кейс нельзя продолжать использовать как active governed/production basis, пока не завершена назначенная revalidation.

| Класс изменения | По умолчанию считать | Replay и оценка | Публичный эффект | Правило grandfathering |
| --- | --- | --- | --- | --- |
| Editorial | Несемантическим | Replay не нужен; при желании checksum refresh | No notice | Полное grandfathering, current guidance сохраняется |
| Schema-compatible при доказанном lossless migration | ABI-only | `audit_old_logic` или `old_logic_with_lossless_schema_migration` | Internal migration; public annotation только если внешне меняется сериализованный public artifact | Да, и historical, и current-use сохраняются |
| Threshold change | Семантическим, пока frozen-corpus replay не докажет нулевой delta | Old logic + current shadow + comparison report | Если delta нет — internal migration / annotation; если delta есть — как stricter или weaker | Grandfather только для historical validity |
| Stricter admissibility | Строже по смыслу | Current shadow + comparison + affected-claim replay | Минимум public annotation; для active governed/production — mandatory revalidation; далее reissue/supersede/withdrawal review по исходу | Historical validity сохраняется, current-use ставится под review |
| Weaker admissibility | Мягче по смыслу | Current shadow + comparison; без auto-upgrade | Обычно annotation не срочная; если владелец хочет расширить guidance — reissue review | Старый кейс не обновляется автоматически; новый favorable вывод требует нового артефакта |
| New blocker | Строже по смыслу | Current shadow + targeted replay | Reissue review или withdrawal review; для активных опубликованных claim basis — mandatory revalidation | Historical validity да, current-use — только после review |
| Retired blocker | Мягче по смыслу | Current shadow + optional targeted replay | Optional annotation или reissue review; silent upgrade запрещен | Архивный статус сохраняется, current uplift только через новый кейс |
| Taxonomy split/merge | Зависит от mapping class | Mapping analysis + affected-claim replay | `alias_only`/доказанный refinement — annotation/internal migration; `boundary_change` или `authority_change` — reissue review и часто mandatory revalidation | Historical validity да; current-use зависит от mapping class |
| Authority-profile change | Семантическим, если меняется blocking/downgrade power | Re-evaluate только кейсы под затронутым profile | Public annotation для profile drift; mandatory revalidation при active governed/production reliance | Архив сохраняет old profile, current guidance требует latest profile |

Самое важное практическое следствие этой таблицы: **изменения weaker logic никогда не должны silently upgrade старые PDC**, а изменения stricter logic никогда не должны silently downgrade их исторический смысл. Старый кейс остается историческим фактом; новый режим формирует либо comparison record, либо revalidation record, либо superseding case. Это полностью совпадает с внутренней линией C21. fileciteturn43file0L3-L3

## Replay, revalidation и граница между исторической действительностью и current guidance

Для PolicyOS стоит ввести очень четкое различие между двумя вопросами: **«был ли кейс корректно закрыт тогда?»** и **«можно ли сегодня показывать его как актуальное guidance?»**. Внутренний C21 уже задает replay modes `audit_old_logic`, `old_logic_with_lossless_schema_migration`, `current_logic_shadow`, `partial_revalidation`, `public_revalidation`, а Research DAG код уже умеет audit reconstruction, pinned-input replay и comparison of trajectories. На моей оценке, именно эти механизмы надо соединить в публичную политику, а не создавать отдельный параллельный workflow. fileciteturn43file0L3-L3 fileciteturn15file0L3-L3 fileciteturn17file0L3-L3

Закрытый PDC должен считаться **historically valid**, если одновременно выполняются четыре условия. Во-первых, его old logic воспроизводим через pinned inputs и semantic tuple. Во-вторых, все использованные schema migrations либо отсутствуют, либо доказаны как lossless. В-третьих, source/data/norm refs и closeout provenance сохранились. В-четвертых, нет признаков того, что исторический record был переписан вместо того, чтобы быть superseded новым record. Это хорошо согласуется с уже существующими требованиями к replay, append-only claim lifecycle и serious closeout compatibility. fileciteturn43file0L3-L3 fileciteturn15file0L3-L3 fileciteturn18file0L3-L3 fileciteturn38file0L3-L3

Но тот же самый кейс должен считаться **no longer publishable as current guidance**, если текущая логика или текущая таксономия меняют хотя бы одно из следующего: admissibility, support status, readiness/publication posture, authoritative scope, affected population boundary или authority profile, under which the case may still be relied upon. Для таких случаев внутренний governance слой уже имеет подходящие статусы — `stale`, `review_required`, `superseded`, `reissued`, `withdrawn` — и именно они должны стать публичной жизненной оболочкой для «исторически валиден, но не current». Иными словами, historical validity и current publishability — это не один флаг, а два разных измерения статуса. fileciteturn20file0L3-L3 fileciteturn43file0L3-L3

Практическое правило я бы закрепил так. Если кейс остается только архивным объяснением прошлого решения, достаточно historical replay и public annotation. Если же кейс продолжает служить основанием для governed или production decision, то stricter-rule detection, authority drift, taxonomy boundary drift, source invalidation, calibration drift или DDM-root-cause impact должны переводить его в mandatory revalidation. C20 уже перечисляет ровно такие revalidation trigger families и требует partial-scope reissue, а не бессмысленного полного rerun там, где граф воздействия можно ограничить affected claim ids. fileciteturn43file0L3-L3

## Что должно быть зафиксировано в каждом закрытом PDC

Минимальный набор доказательств для закрытого PDC в этой политике должен быть не просто «версия схемы», а **immutable semantic tuple плюс execution tuple**.

Обязательный **semantic tuple** должен включать: `rule_family`, `rule_version_ref`, `taxonomy_version_ref`, `logic_hash`, `authority_profile_version`, `migration_policy`, `owner`, `reviewer`, `ADR refs`, а также ссылку на comparison/revalidation policy, по которой этот rule family эволюционирует. Внутренний C21 уже прямо требует `rule_version_ref[]`, `taxonomy_version_ref[]`, `logic_hash[]`, `code_revision`, `authority_profile_version`, `replay_manifest_ref`, input refs, reader/gate surface versions и closeout provenance refs на closed PDCs и связанные claim/evidence/obligation/gate records. fileciteturn11file0L3-L3 fileciteturn43file0L3-L3

Обязательный **execution tuple** должен включать: `git_sha`, `code_revision`, `replay_manifest_ref`, pinned input/data/source/norm refs, producer-reader compatibility decisions, validation refs и, где релевантно, migration record для lossless schema upgrade. Это уже в заметной степени соответствует существующему `closeout_compatibility.py`, который требует `git_sha`, `code_revision`, producer-reader matrix, `reader_gate_version` и `validation_ref` для serious closeout bundles. Мой вывод: **logic_hash — это недостающий semantic twin к уже существующему code_revision**, а не совсем новый класс доказательства. fileciteturn38file0L3-L3 fileciteturn15file0L3-L3 fileciteturn14file0L3-L3

На уровне claim и public artifact эта lineage-информация должна жить рядом с уже существующими evidence refs, а не в отдельном приложении «для аудита». `decision_compiler.py` уже требует структурированные claim refs по policy concepts, legal norms, source/data, methods, portfolios, independence, disconfirming evidence, synthesis, uncertainty и monitoring, а также обязательный public section `withdrawal_reissue_triggers`. Правильный архитектурный ход — **добавить rule/taxonomy lineage в тот же claim-bound contract**, а не держать его в sidecar, который внешний читатель может потерять. fileciteturn37file0L3-L3

Наконец, `logic_hash` должен считаться не по произвольному кодовому файлу, а по **canonicalized semantics**: decision table or AST, thresholds, comparator semantics, defaults/aliases, blocker set, taxonomy bindings и authority-profile bindings, влияющим на admissibility/readiness/publication outcome. Именно так внутренний C21 описывает смысл logic hash: refactor может поменять `code_revision` без изменения смысла, а threshold tweak обязан менять `logic_hash`, даже если schema не изменилась. fileciteturn43file0L3-L3

## Два тестовых сценария

### Каузальный claim закрыт под V1, но становится inadmissible под V2

Представим закрытый causal claim: «Policy X снизила выселения на 15%». Под V1 правило admissibility разрешало закрытие при двух независимых empirical lines и freshness window 24 месяца. Под V2 rule family tightening поднимает independence threshold до трех линий и сокращает freshness window до 12 месяцев. Это типичный случай **stricter admissibility**: по C21 такое изменение должно быть помечено как potentially stricter, пройти owner-declared diff, static diff и frozen-corpus replay, а затем вызвать current-logic shadow для affected historical cases. Если under current logic claim переходит из `admissible/publishable` в `context_only`, `blocked` или `review_required`, старый PDC остается исторически воспроизводимым, но перестает быть current guidance до partial revalidation или superseding reissue. Для активного governed/production reliance здесь нужен не просто comparison report, а mandatory revalidation; если от этого claim зависит публичный headline, нужно либо reissue review, либо withdrawal review. fileciteturn43file0L3-L3 fileciteturn17file0L3-L3 fileciteturn18file0L3-L3 fileciteturn20file0L3-L3

### Taxonomy split меняет scope затронутых claims

Теперь другой кейс: старый claim был закрыт по population taxonomy `rural_households`. В новой taxonomy этот класс split на `remote_rural_households` и `peri_urban_fringe_households`, причем только первая ветка сохраняет прежний policy obligation, а вторая получает иной authority implication. Это уже не `alias_only`; это либо `refinement`, либо `boundary_change/authority_change`. Внутренний C21 прямо говорит, что только `alias_only` и осторожно доказанный `refinement` можно мигрировать без переинтерпретации; `boundary_change` и `authority_change` — semantic changes. В terms of mapping это хорошо ложится на SKOS: `exactMatch` не равен `broadMatch`/`narrowMatch`, и exact-hierarchical clash вообще несовместим. Поэтому автоматический перенос старого claim на обе новые категории запрещен. Правильное действие — append-only `SPLIT` event в claim ledger, сохранение source claim id, создание target claim ids, targeted replay только affected subgraph и public diff/annotation о том, что старый claim исторически корректен лишь для старой taxonomy boundary. Если кейс остается active guidance по затронутой группе, нужен reissue review; если кейс уже только архивный, достаточно historical banner и scope warning. fileciteturn18file0L3-L3 fileciteturn43file0L3-L3 citeturn16view0turn16view1turn16view2

## Открытые вопросы и ограничения

В репозитории уже есть очень сильные локальные механизмы эволюции, но нет единого production-enforced rule registry, который бы материализовал `rule_family / rule_version / logic_hash / taxonomy_version_ref` как обязательный closed-PDC contract. Это не догадка, а прямой вывод внутреннего C21 и normalized backlog: rule lineage registry и stricter-rule revalidation перечислены как bridge-new work, а не как завершенная capability. fileciteturn40file0L3-L3 fileciteturn43file0L3-L3

Research DAG replay сегодня хорошо покрывает pinned artifacts и trajectory comparison, но еще не отслеживает полноценно rule/taxonomy evolution как first-class replay axis. Аналогично, obligation-rule promotion workflow из C5 пока концептуально определен лучше, чем технически зацементирован. Поэтому моя таблица — это high-confidence policy proposal, глубоко опирающаяся на текущий код и backlog, но не утверждение о том, что все эти поля и transitions уже полностью реализованы end-to-end. fileciteturn15file0L3-L3 fileciteturn17file0L3-L3 fileciteturn33file0L3-L3

Если свести все к одной фразе, то рекомендованная публичная политика для PolicyOS такова: **старые кейсы должны оставаться аудируемыми под старой логикой, но любое materially stricter или scope-changing изменение должно порождать новый публичный жизненный акт — annotation, reissue, supersession, withdrawal review или mandatory revalidation — вместо тихой переинтерпретации прошлого**. fileciteturn43file0L3-L3


# C31 Допустимые дефициты по уровню полномочий в PolicyOS

## Исходная рамка и главное наблюдение

После чтения консолидированного фреймворка и связанных ADR картина выглядит так: C31 не должен придумывать новую философию качества “с нуля”, а должен довести до единой матрицы уже существующие в репозитории fail-closed правила для authority envelopes, semantic binding, claim support, readiness, approval и public export. В самой консолидации C31 прямо помечен как открытое, еще не зафиксированное решение, при том что соседние ядра уже стабильны: authority firewalls, claim-bound evidence, closeout substrate, typed projections и lifecycle semantics уже описаны как опорные элементы системы. fileciteturn15file0L3-L3 fileciteturn16file0L3-L3 fileciteturn17file0L3-L3

Самое важное исследовательское заключение: **дефицит в PolicyOS должен стать не “заметкой на полях”, а claim-bound, audience-aware, authority-aware record с детерминированным эффектом на четыре вещи одновременно** — на силу поддержки, на потолок readiness, на максимально допустимую аудиторию публикации и на closeout-статус. Иначе один и тот же пробел сегодня будет читаться как limitation в projection, а завтра как blocker в approval, что прямо противоречит цели C31. Эта необходимость уже просматривается в коде: major claims обязаны иметь видимые surfaces для argument, warrant, rebuttal, counter-evidence и deficit; accepted deficits уже разрешаются в отдельных подсистемах только явно и по профилю; а public export и dashboard не имеют права “доманить” authority, которой нет у runtime case. fileciteturn29file0L3-L3 fileciteturn54file0L3-L3 fileciteturn51file0L3-L3 fileciteturn52file0L3-L3 fileciteturn53file0L3-L3 fileciteturn32file0L3-L3 fileciteturn50file0L3-L3

## Что уже задает репозиторий и что именно в нем пока не хватает

Внутренняя логика репозитория уже задает несколько жестких пределов. Во-первых, serious authority может исходить только из authority-bearing runtime-emitted или runtime-blocker артефактов с same-input closure; projection-only, packaging-only, diagnostic-only и redacted public bundles не могут удовлетворять authority duties. Во-вторых, approval уже различает non-overridable blockers — прежде всего schema/identity/replay-class failures. В-третьих, claim support сейчас слишком груб: при отсутствии нужных предикатов слабые и вовсе неподдержанные claims маршрутизируются в `review_required`, а не в семейство более тонких deficit outcomes; при этом `ClaimRecord` пока хранит только `blocked_reasons` и `metadata`, то есть общей дефицитной модели на уровне claim spine еще нет. fileciteturn40file0L3-L3 fileciteturn41file0L3-L3 fileciteturn49file0L3-L3 fileciteturn26file0L3-L3 fileciteturn43file0L3-L3 fileciteturn45file0L3-L3

Иными словами, PolicyOS уже умеет говорить “это не authority”, “это не overrides”, “это projection only”, “это надо review”, но еще не умеет системно говорить **какой именно дефицит**, **при каком authority profile**, **для какого audience**, **с каким ceiling на readiness/support** допустим как accepted deficit, а где он должен переводиться в reissue или hard block. Именно это и должен закрыть C31. Такой подход хорошо согласуется и с внешними governance-ориентирами: AQuA требует proportionate assurance, независимого assurers/reviewers, явного сообщения known limitations и lifespan/conditions of validity; OMB требует более строгого peer review для influential и especially highly influential scientific information; SR 11-7 требует независимой валидации, учета ограничений, ongoing monitoring и ограничений на использование моделей, если ограничения существенны. fileciteturn36file0L3-L3 fileciteturn37file0L3-L3 fileciteturn38file0L3-L3 fileciteturn39file0L3-L3 fileciteturn29file0L3-L3 fileciteturn30file0L3-L3 fileciteturn31file0L3-L3 citeturn13view0turn13view1turn13view3turn13view4turn13view5turn11view2turn11view0turn12view3

## Каноническая семантика дефицитов

Ниже — рекомендуемая семантика одиннадцати семейств дефицитов. Это **предлагаемая матрица нормализации**, а не описание уже полностью реализованного состояния кода. Она синтезирует внутренние контракты репозитория и внешние правила пропорциональной assurance, независимого review, explicit limitations и ongoing monitoring. fileciteturn15file0L3-L3 fileciteturn17file0L3-L3 fileciteturn18file0L3-L3 fileciteturn29file0L3-L3 fileciteturn32file0L3-L3 citeturn13view0turn13view1turn13view3turn13view4turn12view3turn11view2

| Семейство | Нормализованное значение | Потолок поддержки | Потолок readiness | Максимальная аудитория | Closeout-эффект по умолчанию |
| --- | --- | --- | --- | --- | --- |
| Missing evidence | Отсутствуют обязательные producer-owned refs или support predicates | `unsupported` / максимум `weak` | `research_artifact` | internal / reviewer | block вне research |
| Stale evidence | Доказательство или источник вышли за freshness/lifecycle window | максимум `weakly_supported` до revalidation | `analyst_advisory` | reviewer; public только как stale historical artifact | reissue или block на новом closeout |
| Proxy evidence | Claim опирается на косвенное, surrogate, transformed или context-only evidence | максимум `weakly_supported` или `context_only` | `external_briefing` | reviewer; иногда public-limited для контекста, но не для решающего claim | no production closeout |
| Weak independence | Эффективная независимость недостаточна, raw count завышает силу портфеля | максимум `supported`, но не `strong` | `simulation_ready` или `recommendation_ready` только после review | reviewer / expert | escalation or block for high-stakes claims |
| Unresolved concept | Нет closure по concept/time/geography/jurisdiction spine | `not_evaluable` | `none` | internal only | hard block |
| Contested evidence | Есть admissible unresolved conflict/counterevidence | `contested` | максимум `external_briefing`; выше только через explicit adjudication | reviewer/expert; иногда public-limited | review or block depending authority |
| Legal uncertainty | Не закрыты competence/delegation/hierarchy/temporal applicability | `contested` или `not_evaluable` | `none` для public/prod | reviewer/expert only | hard block for public/prod |
| Method limitation | Слабая концептуальная soundness, assumptions, uncertainty, severe tests или validation | максимум `weakly_supported`, иногда `supported_with_limitation` для низкостатусных descriptive claims | `simulation_ready` | reviewer / expert | review or block |
| Participation gap | Неполная provenance/representativeness/affected-group coverage | для legitimacy/preference claims только `context_only` | `analyst_advisory`/`external_briefing` | reviewer; public только с жестким limitation note и без overclaim | review, иногда block |
| Cost/degradation limit | Budget/SLA/degradation сужают assurance depth | support cap не меняется сам по себе; если выпали обязательные evidence duties, дефицит перекодируется в missing/proxy | cap по профилю | reviewer / limited public | review; block если задет non-overridable duty |
| Lifecycle staleness | Current case/claim утратил действительность, drift/revalidation unresolved | historical only, не “current guidance” | `none` для нового current closeout | public только как stale/superseded/withdrawn label | reissue / withdraw / hard block |

Ключевое различие трех близких статусов должно быть таким. **Accepted deficit** — это явно записанный и provenance-bound governance decision, который разрешает продолжить внутреннюю работу в ограниченном authority profile, но не повышает сам по себе ни support, ни readiness, ни publication scope. **Publish with limitation** — это право вынести claim наружу только в названную аудиторию и только при adjacent disclosure of limitation, без сокрытия scope loss. **Closeout block** — это отсутствие права закрыть case заново в запрошенном authority profile; исторический или draft artifact при этом может существовать, но не считается новым publishable/operational basis. Именно такой смысл логически вытекает из ADR о explicit deficits, visibility to downstream surfaces, publication authority derivation from runtime case, и default-ограничения accepted deficits исследовательскими профилями. fileciteturn29file0L3-L3 fileciteturn32file0L3-L3 fileciteturn51file0L3-L3 fileciteturn52file0L3-L3 fileciteturn53file0L3-L3

## Матрица по уровню полномочий и публикации

Матрица ниже предполагает, что речь идет о **материальном дефиците на major claim**, а не о второстепенном background-context note. Колонки означают: `Research internal`, `Research external`, `Governed internal`, `Governed public`, `Production`. Коды: `A` — accepted deficit, `L` — publish with limitation, `I` — internal only, `H` — human review required, `E` — expert review required, `R` — reissue required, `B` — hard block. Для уже опубликованных cases `R` имеет приоритет над `B`; для нового closeout без истории действует `B`, если матрица указывает `R/B`. Эта схема — рекомендуемая детерминированная нормализация поверх уже существующих внутренних fail-closed правил. fileciteturn15file0L3-L3 fileciteturn29file0L3-L3 fileciteturn31file0L3-L3 fileciteturn32file0L3-L3 fileciteturn49file0L3-L3 fileciteturn50file0L3-L3 citeturn13view0turn13view1turn13view3turn13view4turn11view2turn12view3

| Дефицит | Research internal | Research external | Governed internal | Governed public | Production |
| --- | --- | --- | --- | --- | --- |
| Missing evidence | A | H | H | B | B |
| Stale evidence | A/L | L/H | H | R/B | R/B |
| Proxy evidence | A | L/H | H | E | B |
| Weak independence | A | L/H | H | E | B |
| Unresolved concept | I | I | E | B | B |
| Contested evidence | A/L | L/H | H/E | E | B |
| Legal uncertainty | I | I | E | B | B |
| Method limitation | A/L | L/H | H | E | B |
| Participation gap | A/I | I/H | H/E | E | B |
| Cost/degradation limit | A | L/H | H | H/B | B |
| Lifecycle staleness | I/A | I | H/R | R/B | R/B |

Из этой матрицы следуют три системных правила. Во-первых, **governed public и production не должны принимать unresolved concept, legal uncertainty и material missing evidence как limitation**; эти дефициты должны быть non-overridable. Во-вторых, **proxy evidence, weak independence и method limitation могут жить как visible limitation только до reviewer/expert boundary**, но не как бесшумный мост к operational claim. В-третьих, **stale evidence и lifecycle staleness — это не просто warning, а trigger на reissue/revalidation**, потому что AQuA требует explicit lifespan/conditions of validity, а SR 11-7 требует ongoing monitoring и ограничения использования при существенных limitations. fileciteturn37file0L3-L3 fileciteturn38file0L3-L3 fileciteturn31file0L3-L3 fileciteturn33file0L3-L3 citeturn13view3turn13view5turn12view1turn12view3

Рекомендуемое правило при смешанных дефицитах простое: сначала берется **наиболее узкий audience cap**, затем **наименьший readiness cap**, затем **наиболее сильный closeout outcome** по приоритету `B > R > E > H > I > L > A`. Это хорошо согласуется с предложенной в C1 идеей lattice-типа композиции, где composed result должен брать не среднее, а наиболее ограничивающее значение по blockingness, publication scope, readiness cap и closeout effect. fileciteturn17file0L3-L3

## Непереопределяемые дефициты для governed и production

Для governed и production режимов стоит закрепить отдельный список **non-overridable C31 deficits**, по аналогии с уже существующими non-overridable schema/identity/replay blockers в approval. Иначе система останется fail-closed по техническим артефактам, но fail-open по смысловым дырам — а это плохой обмен. fileciteturn49file0L3-L3

Практически этот список должен включать: unresolved concept; legal uncertainty на claim-bearing legal basis; missing required evidence для legal/causal/forecast/distributional/welfare/implementation major claims; proxy evidence как единственную опору для production claim; material weak independence, если major claim требует именно portfolio-strength closure; unresolved contested evidence для public recommendation или operational decision; lifecycle staleness без reissue/revalidation; а также любой cost/degradation case, где budget pressure фактически пытается отменить non-overridable duty. Последний пункт уже прямо поддерживается ADR-0164: proportionality может сокращать optional depth, но не может waiv’ить non-overridable substrate, producer, claim, publication, lifecycle или invariant duties. fileciteturn30file0L3-L3 fileciteturn31file0L3-L3 fileciteturn32file0L3-L3 fileciteturn33file0L3-L3 fileciteturn37file0L3-L3 fileciteturn38file0L3-L3

Отдельно важно не путать **non-overridable deficit** и **review-required deficit**. Если еще возможен осмысленный спор экспертов о том, как ограничить claim, сузить scope или сделать explicit limitation, это ветка `H`/`E`. Если же claim уже потерял semantic closure, legal competence или minimal evidence floor, review может менять только маршрут ремонта, но не итог “можно публиковать/использовать”. Такое различие хорошо поддерживается и AQuA, где insufficent assurance должно быть explicitly acknowledged and reported, а для более сложного анализа может потребоваться external peer review, и OMB, где high-impact dissemination требует более формализованного peer review plan и прозрачности reviewer expertise/public comment. citeturn13view1turn13view4turn11view0turn11view2

## Фикстуры смешанных кейсов

Ниже — минимальный набор case fixtures, который делает матрицу проверяемой и исключает скрытое раздвоение логики между readers.

| Кейс | Материальные дефициты | Ожидаемый результат |
| --- | --- | --- |
| Strong data + weak legal authority | Данные сильные, но competence/delegation/temporal applicability не закрыты | `Governed internal = E`, `Governed public = B`, `Production = B`; claim не может быть “publish_with_limitation”, потому что legal uncertainty здесь не cosmetic, а authority-bearing gap |
| Strong method + stale source | Хорошая методология, но ключевой источник/норма stale | `Research internal = A/L`; `Governed internal = H`; `Governed public` и `Production` для current guidance = `R/B`; если case уже опубликован, обязателен reissue/revalidation marker |
| Contested evidence + public recommendation | Есть admissible counterevidence, спор не закрыт | Для reviewer/expert потоков допустим `H/E`; для public recommendation — только `E` с explicit contested record и limitation note; для production — `B`, если спор влияет на decision-bearing claim |
| Proxy data + production claim | Есть только surrogate/proxy evidence для major operational claim | `Research internal = A`; `Governed internal = H`; `Governed public = E` только для context/descriptive surface; `Production = B` |
| Participation gap + legitimacy claim | Не все affected groups mapped, representativeness слабая | Claim о legitimacy/preference понижается до `context_only`; internal review допустим, public legitimacy claim требует `E`, production basis — `B` |
| Lifecycle staleness + existing published case | Case ранее был published, но drift/revalidation unresolved | Не “warning”, а `R`; public surface должен стать stale/superseded/review-needed, а не оставаться quietly current |

Эти fixtures напрямую вытекают из внутренних тезисов репозитория: legal competence не равна простому jurisdiction match; contested evidence — отдельный слой, не сводимый к citation failure; accepted deficits допустимы только явно и в ограниченных профилях; public projection не может выдать authority, которой нет в runtime case; lifecycle обязан быть append-only и не переписывать исторический authority. fileciteturn18file0L3-L3 fileciteturn19file0L3-L3 fileciteturn20file0L3-L3 fileciteturn21file0L3-L3 fileciteturn29file0L3-L3 fileciteturn31file0L3-L3 fileciteturn32file0L3-L3

## Минимальное решение для фиксации C31 в framework

Чтобы C31 действительно закрыл acceptance criterion, PolicyOS стоит нормализовать дефициты в один тип записи, условно `DeficitRecord`, с полями: `deficit_family`, `deficit_code`, `claim_id[]`, `authority_profile`, `audience_scope`, `decision` (`accepted`, `limitation`, `human_review`, `expert_review`, `reissue`, `blocked`), `support_cap`, `readiness_cap`, `max_audience`, `override_policy`, `owner`, `expires_at`, `runtime_event_ref`, `evidence_ref`, `public_limitation_note`, `review_refs`, `closeout_effect`. Это уже практически просится из разрыва между `ClaimRecord` без нормализованных deficit fields, обязательными assurance-deficit surfaces в claim_argument validator, и частной accepted-deficit логикой в disconfirming evidence. fileciteturn26file0L3-L3 fileciteturn54file0L3-L3 fileciteturn51file0L3-L3 fileciteturn52file0L3-L3

На уровне runtime decision rule я бы закрепил следующую норму: **каждый consumer — scorecard, readiness, approval, public export, dashboard/API projection — обязан читать не локальные ad hoc warnings, а одну и ту же C31 matrix evaluation**. Тогда одна и та же missing evidence дыра больше не сможет быть “всего лишь limitation” в одном surface и “blocker” в другом без явного и тестируемого правила матрицы. Это в точности соответствует и логике консолидированного фреймворка, и формуле acceptance задачи C31. fileciteturn15file0L3-L3 fileciteturn16file0L3-L3

## Открытые вопросы и ограничения

Главное ограничение текущего состояния репозитория в том, что C31 еще не реализован как общая runtime matrix: часть логики уже зашита в authority envelopes, approval, disconfirming ledgers, claim argument validators и public export, но она fragmented. Это означает, что предложенная выше матрица — **высокодостоверный синтез по framework и коду**, а не существующая “as-is” таблица из одного файла. fileciteturn15file0L3-L3 fileciteturn26file0L3-L3 fileciteturn49file0L3-L3

Остаются три вопроса, которые лучше зафиксировать как открытые, а не зашивать догадкой. Во-первых, для каких claim families proxy evidence и weak independence в governed public могут еще давать `E`, а не сразу `B`; я выше исхожу из material major claims, но для purely contextual public claims ceiling может быть мягче. Во-вторых, нужны численные thresholds для freshness, independence и participation quality — иначе matrix будет каноничной по outcome, но не по detection threshold. В-третьих, lifecycle-семейство должно отличать новый closeout от already-published artifact, иначе reissue и hard-block будут смешиваться. Эти вопросы не отменяют матрицу C31; они только указывают, где после принятия матрицы потребуется дополнительная спецификация порогов и детекторов. fileciteturn17file0L3-L3 fileciteturn19file0L3-L3 fileciteturn20file0L3-L3 fileciteturn21file0L3-L3


# C30 Семантический рубрикатор бенчмарка для PolicyOS

## Исходная рамка и что уже задаёт репозиторий

Внутренняя рамка для C30 уже достаточно жёсткая. В активном исследовательском плане C26 требует, чтобы оценка ловила не только ошибки формы, но и случаи, где структурно корректный пакет всё равно семантически неверен: неверно интерпретирует источник, выходит за пределы допустимого объёма вывода, опирается на неподходящую правовую опору, маскирует дефицит участия, путает время и роль данных или превращает projection/export в «авторитет». C30 прямо требует рубрикатор экспертной панели, метки adjudication, топологию рецензентов, gold-sheet и benchmark governance с hidden/public splits, calibration, leakage controls и anti-overfitting. fileciteturn23file0L3-L3 fileciteturn24file0L3-L3

Ключевой внутренний термин уже нормализован: **semantic false pass** — это «структурно полный кейс, чьё содержимое неверно, недостаточно, устарело, scope-mismatched, artificially inflated или authority-laundered». В той же консолидации закреплено, что evaluation must target semantic false passes, а capability, у которой нет semantic/e2e test, не должна считаться реализованной. В реестре паттернов P10 прямо сформулирован анти-паттерн structural-only validation, а `semantic_test_missing` не может «выпуститься» в implemented. fileciteturn37file0L3-L3 fileciteturn38file0L3-L3 fileciteturn34file0L3-L3

Из кода видно, что PolicyOS уже имеет сильные структурные и предсемантические блоки, но они не закрывают C30 сами по себе. `challenge_factory.py` уже задаёт review-before-hidden, leakage risk, lineage, public/private/hidden admission и реестр challenge classes; значит, C30 не должен заново изобретать инфраструктуру паков, а должен добавить именно **semantic adjudication layer** над уже существующими challenge packs. `citation_faithfulness.py` уже умеет различать `supports`, `partially_supports`, `scope_limited`, `contradicts`, `irrelevant`, `fabricated`, `unverifiable`, но сама же честно фиксирует residual risk: offline checks не доказывают full semantic entailment, а `semantic_paraphrase_not_proven` входит в пределы false-pass risk. `claim_support.py` уже проверяет claim-family predicates, но это предикатная, а не экспертно-содержательная проверка. `AuditPackageVerifier` валидирует целостность пакета, checksums, подписи, provenance и completeness, но не доказывает, что кейс реконструирует trustworthy recommendation. fileciteturn36file0L3-L3 fileciteturn25file0L3-L3 fileciteturn26file0L3-L3 fileciteturn27file0L3-L3 fileciteturn28file0L3-L3 fileciteturn29file0L3-L3 fileciteturn30file0L3-L3

Тесты репозитория уже показывают, какие structural false-pass seeds наиболее важны для C30. `test_authority_spoofing.py` ловит случаи, где projection/dashboard/benchmark/dashboard-like surfaces пытаются притвориться authority-bearing evidence. `test_policy_design_case_false_passes.py` ловит wrong jurisdiction, prose backfill вместо producer refs, non-runtime producer evidence и другие формы формально заполненного, но недопустимого кейса. Это очень важно: семантический рубрикатор должен не дублировать эти unit-тесты, а разбирать те **оставшиеся** случаи, где все эти тесты уже прошли, но смысл всё ещё плохой. fileciteturn31file0L3-L3 fileciteturn32file0L3-L3 fileciteturn33file0L3-L3

Внешние стандарты подтверждают именно такой дизайн: PRISMA 2020 требует явно документировать selection process, число независимых рецензентов, независимость screening/data collection/risk-of-bias assessment и причины исключений; GRADE требует отдельно оценивать уверенность в evidence и силу рекомендации, а также системно смотреть на risk of bias, inconsistency, indirectness, imprecision и publication bias; NIST AI RMF закрепляет, что trustworthy AI нельзя сводить к accuracy и что нужны valid/reliable, accountable/transparent и другие trustworthiness characteristics. Для benchmark governance HELM показывает ценность multi-metric, scenario-based и transparent evaluation, Dynabench — пользу динамических challenge-oriented benchmark loops, а LiveBench и LiveCodeBench — практику contamination-resistant, регулярно обновляемых тестовых наборов. Datasheets и Model Cards добавляют, что любой benchmark должен иметь машино- и человекочитаемую документацию о мотивации, составе, intended use, limits и revision history. citeturn20view0turn21view0turn7view0turn0academia2turn0academia1turn25academia0turn25academia2turn22academia0turn24academia1

## Что именно должен проверять семантический рубрикатор

Мой главный вывод: **единицей семантической оценки в C30 должен быть не весь PDC целиком, а каждый load-bearing claim/recommendation unit с последующей case-level агрегацией**. Это согласуется с внутренней ориентацией PolicyOS на claim-bound evidence и с внешней evidence-synthesis практикой, где уверенность и bias оцениваются по outcomes/body-of-evidence, а не только «по документу в среднем». fileciteturn37file0L3-L3 fileciteturn21file0L3-L3 citeturn21view0turn20view0

Для C30 я рекомендую восьмимерный semantic rubric. Его не надо сводить к одному числу: PolicyOS уже явно предупреждает против ложной редукции сложных governance-решений к scalar score, а HELM и NIST тоже поддерживают multi-metric evaluation вместо единственного показателя. fileciteturn21file0L3-L3 citeturn0academia2turn7view0

**Интерпретационная верность.** Проверяется, следует ли claim из источника по смыслу, а не только по наличию faithful snippet. Это измерение специально нужно, потому что текущий citation-faithfulness модуль сам признаёт пределы deterministic checking и semantic paraphrase risk. Типичный провал: дословно верный фрагмент не поддерживает более широкий claim. fileciteturn27file0L3-L3 fileciteturn24file0L3-L3

**Scope fit.** Проверяется совпадение юрисдикции, институционального уровня, обсуждаемого policy instrument, населения, географии и допустимого обобщения. Здесь C30 должен брать внутренние провалы wrong jurisdiction, source-scope mismatch и projection laundering как seed-категории. В терминах GRADE это ближе всего к indirectness, но в PolicyOS scope fit должен быть строже, потому что legal/policy claims ломаются при малом scope drift. fileciteturn33file0L3-L3 fileciteturn34file0L3-L3 citeturn21view0

**Правовая компетенция и компетентность источника.** Проверяется не подлинность документа сама по себе, а то, имеет ли он достаточную юридическую силу и уместность для данного claim и authority level. Аутентичный, но юридически некомпетентный источник должен валиться семантически. Это прямо вытекает из C30 и из внутренних authority-boundary patterns P05 и P15. fileciteturn24file0L3-L3 fileciteturn34file0L3-L3

**Causal support и method fit.** Для причинных, прогностических, численных и implementation claims reviewers должны спрашивать, соответствует ли используемый метод типу утверждения. Внутренний `claim_support.py` уже знает, что causal claims требуют data + method + identification strategy, а forecast claims — horizon + uncertainty; рубрикатор C30 должен поверх этого спрашивать, действительно ли применённый метод отвечает вопросу, а не просто формально присутствует в пакете. GRADE даёт здесь хорошую методологическую опору через indirectness, inconsistency, imprecision и risk of bias. fileciteturn28file0L3-L3 fileciteturn29file0L3-L3 citeturn21view0

**Time-role alignment и freshness.** Reviewer должен различать legal effective time, observation time, publication time, forecast horizon и freshness window. Внутренняя консолидация уже считает fragmented time semantics системным риском, а C30 прямо требует stale but structurally valid probes. Поэтому устаревшие, но корректно подписанные и воспроизводимые данные — это полноценный semantic failure, а не просто minor warning. fileciteturn24file0L3-L3 fileciteturn37file0L3-L3

**Participation attribution.** Все claims про preferences, legitimacy, acceptability, feasibility through affected-person input и public contestability должны проверяться на происхождение, representativeness, form of consultation и attribution chain. Внутренняя программа C19 и P15 уже запрещает превращать speculation или summary в authority; C30 должен иметь явный review question: «Есть ли здесь реальная participation provenance, или это консультационное/LLM/narrative laundering?» fileciteturn22file0L3-L3 fileciteturn34file0L3-L3

**Independence and evidence inflation.** Reviewer должен проверять, не выросла ли сила поддержки только потому, что несколько линий доказательств на деле сводятся к одному исходному dataset, sponsor, method family или lineage. Это прямое продолжение P14. На внешней стороне это соответствует good evidence-synthesis practice, где одинаково опасны и publication bias, и ложная независимость источников. fileciteturn34file0L3-L3 fileciteturn37file0L3-L3 citeturn21view0

**Public-surface truthfulness.** Даже когда runtime artefacts сильные, public/reviewer/machine export не должен скрывать limitation, deficit, contestation, downgrade или non-authoritative status. Внутренний репозиторий многократно подчёркивает projection firewall и surface poverty; NIST AI RMF отдельно делает accountable/transparent trustworthiness cross-cutting characteristic. Следовательно, C30 должен оценивать не только «правоту кейса внутри», но и честность его внешней проекции. fileciteturn37file0L3-L3 fileciteturn38file0L3-L3 citeturn7view0

Практически это означает такой минимальный semantic review prompt для каждого load-bearing claim: что именно claim утверждает, что именно источник действительно подтверждает, что claim умалчивает, на какой scope/time/jurisdiction он законно распространяется, каким методом подтверждён, насколько независимы supporting lines, была ли корректно вынесена contestation/limitation наружу, и какой status should have been emitted instead. fileciteturn24file0L3-L3 fileciteturn34file0L3-L3

## Метки adjudication и правила перехода к финальному вердикту

Для C30 я рекомендую использовать **семь итоговых меток**, которые просил план, но с чёткой иерархией применения.

**`semantic_pass`** ставится, когда у всех load-bearing claims нет material semantic defects, а любые ограничения уже честно артикулированы как limitations/accepted deficits/contestations и публичная поверхность не завышает уверенность. Это не означает «идеально», а означает «семантически достаточно для заявленного authority level». fileciteturn24file0L3-L3 fileciteturn21file0L3-L3

**`limitation_required`** ставится, когда основной смысл не ложен, но claim или export требуют обязательного сужения, красной маркировки, status downgrade, explicit caveat или audience restriction. Это метка для исправимого семантического дефицита, который ещё не уничтожает саму рекомендацию, но запрещает текущую форму публикации. Такой дизайн соответствует внутренним soft-gate и accepted-deficit семантикам, а также практике GRADE/PRISMA, где limits of evidence и limits of process должны быть вынесены явно. fileciteturn37file0L3-L3 citeturn21view0turn20view0

**`contested`** ставится, когда есть реальный, документируемый, добросовестный конфликт в трактовке evidence, legal reading, tradeoff valuation или expert judgment, и этот конфликт сам по себе должен жить в публичной поверхности. Важный принцип: contested — это не reviewer failure; это содержательная характеристика кейса. Внутренний план прямо запрещает скрывать substantive disagreement под одним «золотым» ответом. fileciteturn21file0L3-L3

**`unsupported`** ставится на уровне claim, когда evidence package structurally present, но по существу не поддерживает утверждение с требуемой силой. Это типичный исход для faithful-but-insufficient snippets, method mismatch, слабой независимости или недотянутого participation support. Если такой claim material для итогового recommendation state, case-level label поднимается до `false_pass`. fileciteturn24file0L3-L3 fileciteturn27file0L3-L3

**`false_pass`** — главный system-level label C30. Его нужно ставить тогда, когда structurally complete PDC или claim был бы выпущен как pass/supported/approval-ready/publicly trustworthy, но expert panel показывает материальную semantic defect в interpretation, scope, legal competence, causal support, time-role alignment, participation attribution, independence или public truthfulness. Другими словами, unsupported становится false_pass, если система уже попыталась представить это как достаточное основание для решения или публикации. fileciteturn24file0L3-L3 fileciteturn37file0L3-L3

**`fabricated_unverifiable`** ставится, когда reviewer не может установить источник, provenance, цитату, temporal validity или другой базовый verification anchor. Сюда входят fabricated refs, unverifiable sources, broken provenance chains и случаи, где audit/citation package есть, но факт support невозможно восстановить. Здесь полезно переиспользовать внутренние labels из `citation_faithfulness.py` и отделять эту метку от обычного unsupported. fileciteturn27file0L3-L3

**`reviewer_disagreement`** ставится только после формального tie-break protocol, если расхождение остаётся substantive и не сводится к ошибке невнимательности. Такая метка должна оставаться частью gold benchmark, а не уничтожаться «административным усреднением». Для PolicyOS это особенно важно, потому что contested public-policy cases нередко действительно имеют несколько defensible expert readings. fileciteturn21file0L3-L3

Рекомендованное правило агрегации такое: на claim-level допустимы все семь меток; на case-level действует precedence order `fabricated_unverifiable > false_pass > unsupported > contested > limitation_required > semantic_pass`, а `reviewer_disagreement` используется как специальный terminal state, если tie-break не дал устойчивого merge. Это позволяет не прятать грубые semantic defects за средним баллом и в то же время не делать contested кейсы искусственно «ложными». fileciteturn24file0L3-L3 fileciteturn37file0L3-L3

## Топология рецензентов и протокол разбора

Рекомендованная topology почти совпадает с тем, что уже просит C30, но её нужно сделать операциональной. На каждый кейс нужен **кворум из четырёх ролей**: domain reviewer, method/evidence reviewer, legal/governance reviewer и public-surface reviewer. Но не все роли должны иметь одинаковый вес по каждому claim. Рецензирование должно происходить **по релевантности роли к claim family**, а не конвейерно «все про всё». fileciteturn24file0L3-L3

**Domain reviewer** отвечает за problem framing, intervention logic, policy plausibility, practical scope и скрытую подмену вопроса. Он особенно важен для distinction между «источник о похожей политике» и «источник о той же policy question». **Method/evidence reviewer** отвечает за causal adequacy, uncertainty, independence, counterevidence, evidentiary closure и inflation risks. **Legal/governance reviewer** отвечает за legal competence, jurisdiction/time validity, authority profile, procedural legitimacy и возможность publication under stated authority level. **Public-surface reviewer** проверяет, сохранились ли в export все contestations, limitations, deficits, redactions и non-authoritative boundaries, и не стал ли projection притворяться authority. fileciteturn24file0L3-L3 fileciteturn34file0L3-L3 fileciteturn31file0L3-L3

Протокол должен быть трёхступенчатым. Сначала идёт **blind independent review** хотя бы двумя тематически релевантными reviewers на один claim unit; это соответствует внешней evidence-synthesis норме независимого review/assessment. Затем — **structured reconciliation**, где reviewers видят только claim sheet, cited evidence context, runtime status и rubric prompts, но не «итог системы», чтобы не якориться на structural pass. Если расхождение сохраняется по material dimension, включается **tie-break reviewer** с правом выбрать одну из позиций или оставить `reviewer_disagreement`, но только с письменным rule-bound justification. Такой процесс хорошо сочетается с PRISMA-требованием явно фиксировать, сколько reviewers работали independently, и с внутренним запретом скрывать substantive disagreement. citeturn20view0 fileciteturn21file0L3-L3

Я рекомендую дополнительно вводить **role-triggered обязательность**. Для legal claims юридический reviewer обязателен; для causal/predictive claims обязателен method reviewer; для claims о stakeholder preferences обязателен governance/participation-capable reviewer; для всего, что идёт в public-facing benchmark, обязателен public-surface reviewer. Это лучше, чем единый «универсальный» панелист, потому что GRADE, NIST и внутренний PolicyOS все исходят из того, что trustworthiness складывается из разных видов компетенции, а не из одной общей эрудиции. citeturn21view0turn7view0 fileciteturn24file0L3-L3

В tie-break protocol нельзя разрешать арбитру придумывать новую третью позицию, не совместимую с исходными evidence notes. Он может сделать только одно из трёх: подтвердить reviewer A, подтвердить reviewer B, либо зафиксировать `reviewer_disagreement`. Это резко повышает воспроизводимость gold labels и уменьшает риск «административной редактуры», которая красиво сглаживает реальные epistemic fractures. fileciteturn21file0L3-L3

## Золотая карточка семантической адъюдикации

Чтобы C30 выполнял своё acceptance criterion, для каждого отклонённого structural pass нужен не просто итоговый label, а **reproducible failure explanation packet**. Я рекомендую обязательную gold-card структуру ниже.

Карточка должна содержать: `benchmark_case_id`, `claim_id` или `recommendation_id`, `authority_level_requested`, `audience_surface`, `benchmark_split`, `benchmark_version`, `runtime_structural_status`, `validators_passed`, `evidence_refs_reviewed`, `review_roles_present`, `dimension_ratings`, `final_label`, `status_should_have_been`, `minimal_remediation`, `review_confidence`, `disagreement_category`, `tie_break_note`, `reviewer_conflict_flags`, `created_at`, `supersedes_gold_ref` и `item_lineage_key`. Такой набор делает gold-case не просто verdict, а версионируемый adjudication artifact. fileciteturn24file0L3-L3 fileciteturn36file0L3-L3

Для каждого **rejected structural pass** я бы сделал обязательными ещё четыре поля-доказательства. Первое — **claim as surfaced**: точная формулировка того, что система хотела выдать наружу. Второе — **evidence context actually reviewed**: не только cited snippet, но и минимальный surrounding context, потому что snippet-only review сам по себе является frequent false-pass source. Третье — **mismatch explanation** в формате «что именно не сходится и по какой dimension». Четвёртое — **counterfactual repair**: достаточно ли было бы limitation, или claim нужно переводить в unsupported/withdrawn/contested. Это делает adjudication полезным и для benchmark, и для последующей remediation. fileciteturn27file0L3-L3 fileciteturn33file0L3-L3

Хорошая gold card для C30 должна давать воспроизводимое объяснение формата:

`<claim_id, dimension_id, evidence_ref, excerpt_or_context_ref, failure_mode, why_structural_checks_missed_it, status_should_have_been, required_surface_change>`.

Именно этот tuple позволит PolicyOS выполнить формулировку acceptance: не просто «завалить» structurally complete PDC, а сделать это с объяснением, которое потом можно регрессионно воспроизводить и сравнивать между версиями benchmark. fileciteturn24file0L3-L3

Отдельно рекомендую поле **`false_pass_trigger_type`** со строго контролируемым словарём: `interpretation`, `scope`, `legal_competence`, `causal_support`, `method_fit`, `time_role`, `participation`, `independence`, `public_truthfulness`, `fabrication_unverifiable`. Это позволит потом строить failure analytics по классам и не путать «ложный pass» с «contested, но честно surfaced case». fileciteturn24file0L3-L3 fileciteturn34file0L3-L3

## Управление бенчмарком и анти-оверфитинг

С точки зрения benchmark governance PolicyOS уже имеет хороший фундамент: challenge factory требует review-before-hidden, отслеживает leakage risk и lineage, а hidden cases нельзя регистрировать без reviewed hidden admission. Это следует сохранить и для C30, а сам semantic benchmark оформить как новый слой поверх существующего benchmark registry, а не как отдельный самодельный спредшит. fileciteturn36file0L3-L3 fileciteturn25file0L3-L3 fileciteturn26file0L3-L3

Я рекомендую трёхконтурную схему наборов. **Public exemplars** должны показывать rubric logic, типы labels и repair expectations, но содержать ограниченное число fully worked examples. **Hidden holdout** должен быть главным release gate. **Rotating semantic challenge set** должен обновляться чаще, чтобы система не выучивала фиксированный канон ошибок. Это полностью согласуется с внутренней challenge-factory логикой и с идеями Dynabench/LiveBench/LiveCodeBench про динамическое обновление и contamination resistance. fileciteturn36file0L3-L3 citeturn0academia1turn25academia0turn25academia2

Versioning должно идти на трёх уровнях: benchmark-level version, item-level version и gold-adjudication version. Если меняется rubric logic, это **не** должно тихо переписывать старые кейсы; PolicyOS сам уже подчёркивает importance of rule lineage and replay under old semantics. Поэтому у каждой semantic item должны быть `item_version`, `gold_version`, `rubric_version`, а retired items должны оставаться доступными для regression history, но не для primary score. fileciteturn22file0L3-L3 fileciteturn37file0L3-L3

Leakage controls я бы делил на содержательные и операционные. Содержательные: canary tokens, paraphrase variants, partial evidence hiding, delayed public release и lineaged pack registration. Операционные: запрет использовать hidden rationales in fine-tuning, запрет публиковать full gold on fresh hidden sets, audit-log всех обращений к hidden materials, и отдельный contamination review при подозрительно резком росте score. Внутренняя infrastructure для canary/leakage уже есть; LiveBench и LiveCodeBench показывают, что частое обновление и привязка к недавним источникам реально снижают contamination. fileciteturn26file0L3-L3 citeturn25academia0turn25academia2

Reviewer calibration должна быть formalized. Минимум нужен small calibration pack с already-adjudicated items, затем short reconciliation workshop и периодическая переаттестация при drift. PRISMA подчёркивает важность прозрачного review process, а внутренний план прямо требует disagreement tracking и calibration. Я бы ещё добавил правило: рост disagreement по одной dimension более заданного порога инициирует не переоценку моделей, а пересмотр самого rubric wording. Это защищает C30 от превращения в расплывчатый «вкус reviewer’а». citeturn20view0turn17view0 fileciteturn24file0L3-L3

Наконец, C30 нужен собственный **benchmark card** по духу Datasheets и Model Cards: мотивация, scope, out-of-scope uses, target claim families, review topology, known blind spots, version policy, leakage policy, update cadence, licensing/redaction rules и intended use for release gating versus research diagnostics. Без такого документа бенчмарк сам рискует нарушить требования прозрачности, которые он предъявляет системе. citeturn22academia0turn24academia1

## Набор обязательных семантических проб

Ниже — тот probe inventory, который я считаю обязательным для C30. Это не исчерпывающий список всех challenge classes PolicyOS, а именно минимальный набор проб, без которых semantic rubric будет недоопределён.

**Faithful snippet, but unsupported claim.** Система цитирует реальный фрагмент без fabrication, но фрагмент поддерживает только узкий факт, а claim делает более сильный causal, legal или policy-design вывод. Это важнейшая проба, потому что именно её current citation-faithfulness layer честно не закрывает до конца. fileciteturn27file0L3-L3

**Authentic, but legally incompetent source.** Источник подлинный, релевантный тематически и даже хорошо процитирован, но не обладает нужной norm hierarchy, jurisdictional competence или procedural status для данного legal/policy claim. Это отдельная probe family, а не частный случай scope mismatch. fileciteturn24file0L3-L3 fileciteturn33file0L3-L3

**Stale but structurally valid evidence.** Snapshot и audit package корректны, freshness metadata есть, package verifies, но claim использует материал вне нужного temporal role или beyond validity window. C30 должен фейлить такие cases семантически, особенно для legal and operational claims. fileciteturn24file0L3-L3 fileciteturn30file0L3-L3

**Audit-valid, but untrustworthy case reconstruction.** Все signatures/checksums/provenance шаги проходят, однако support chain не собирает trustworthy recommendation. Это критически важно, потому что иначе benchmark спутает package hygiene с truthfulness. Внутренний P10 именно это и предупреждает. fileciteturn30file0L3-L3 fileciteturn34file0L3-L3

**Projection/public export laundering.** Runtime evidence, dashboard surface, public export или package summary выдают более сильный статус, чем допускают authority-bearing artifacts. Внутренние authority-spoofing tests уже дают сильные seeds; C30 должен доводить их до human-semantic adjudication на уровне public truthfulness. fileciteturn31file0L3-L3 fileciteturn32file0L3-L3

**Participation attribution laundering.** Система утверждает stakeholder preference, legitimacy или implementation acceptability на основании consultation summary без provenance, единичной цитаты, нерепрезентативного testimony или LLM-generated synthesis. Для public-policy cases это должно быть отдельным hard semantic failure mode. fileciteturn22file0L3-L3 fileciteturn24file0L3-L3

**Independence inflation.** Портфель выглядит богатым по raw count, но collapses through shared dataset, institutional origin, sponsor, method family или model-generated lineage. Это прямая operationalization P14 и must-have for C30 because otherwise structurally rich cases systematically over-score. fileciteturn34file0L3-L3

**Method mismatch.** Descriptive evidence подаётся как causal support; simulation assumptions выдаются за empirical closure; implementation feasibility claim опирается только на generic narrative. Внутренний `claim_support.py` уже задаёт family-specific predicate expectations — C30 должен добавить экспертный вопрос «а этот method действительно отвечает на этот claim?». fileciteturn28file0L3-L3 fileciteturn29file0L3-L3

**Case-level ceremony without semantic substance.** PDC содержит весь required record furniture, но reviewers видят box-ticking, repeated empty sections, limitations that never change outcome, or synthetic maturity inflation. Это особенно важно для PolicyOS, потому что внутренняя консолидация отдельно предупреждает: complexity without semantic value снижает доверие. fileciteturn38file0L3-L3 fileciteturn34file0L3-L3

Если нужен один канонический acceptance example для C30, то я бы использовал такой тип кейса: пакет проходит audit verification; citation snippets подлинные; структурные fields заполнены; recommendation оформлена как supported; но legal source — consultation memo, causal вывод сделан из descriptive trend, data stale относительно policy horizon, а public export скрывает limitation. Такой кейс должен получать `false_pass`, а gold card должна объяснять, какие dimension failures сделали structural pass недействительным. Это и есть минимально убедительная демонстрация того, что C30 работает. fileciteturn24file0L3-L3 fileciteturn30file0L3-L3 fileciteturn27file0L3-L3

## Вывод и рекомендуемая спецификация для принятия

В сжатом виде я рекомендую утвердить C30 как **claim-level, multi-reviewer, non-scalar semantic adjudication system**, который sits above structural validators и использует их результаты лишь как вход, а не как финальный verdict. Это полностью соответствует внутренней архитектурной логике PolicyOS: claim-bound evidence, authority firewalls, semantic false pass as explicit research concern, review-before-hidden benchmark management и запрет на structural-only completion как критерий зрелости. fileciteturn37file0L3-L3 fileciteturn38file0L3-L3 fileciteturn34file0L3-L3

Минимально рекомендуемая нормативная формулировка для спецификации звучит так: **структурный pass является необходимым, но не достаточным условием benchmark pass; любой materially load-bearing claim, получивший semantic label `unsupported`, `false_pass` или `fabricated_unverifiable`, должен блокировать case-level semantic pass, а unresolved substantive expert split должен фиксироваться как `reviewer_disagreement`, а не скрываться.** Такая формулировка лучше всего переводит C30 из абстрактной research task в реально применимый benchmark governance artifact. fileciteturn24file0L3-L3

## Открытые вопросы и ограничения

Есть несколько мест, где без дальнейшей внутренней спецификации останется пространство для донастройки. Во-первых, я не нашёл в уже собранных материалах готового отдельного internal schema для «semantic fixtures» как законченного артефакта; в исследовании выше я опирался на plan/consolidation, challenge factory, failure-pattern register и тесты false-pass/authority-spoofing как на strongest available anchors. Во-вторых, конкретные пороги reviewer calibration и disagreement rate сейчас логичнее задавать отдельным benchmark governance ADR, а не жёстко вшивать в сам рубрикатор. В-третьих, если PolicyOS захочет использовать LLM-as-judge anywhere in C30, это лучше делать только как triage/support tool, но не как final gold adjudicator; на собранных источниках хорошо обоснована именно human-led adjudication model, а не fully automated semantic judging. fileciteturn24file0L3-L3 fileciteturn34file0L3-L3 citeturn0academia1turn25academia0turn25academia2


# Effective Independence Function for PolicyOS

## Executive synthesis

Я прочитал указанный каркас и исследовал задачу в контексте текущего репозитория, а не как greenfield-дизайн. Внутренние документы прямо требуют для этой темы: определить identity evidence-line, каналы collapse, функцию `effective_independence(line_a, line_b) -> [0,1]`, правила агрегации против inflation by raw count, минимумы по claim family и authority level, а также fixture pack. Активный research plan привязывает эту работу не только к C29, но и к уже существующим C13/C14/C25/C26: independence, conflict, longitudinal calibration и evaluation. fileciteturn14file0L3-L3 fileciteturn13file0L3-L3

Главный вывод из репозитория такой: PolicyOS уже имеет fail-closed baseline для independence, но пока почти целиком в форме **exact collapse by cluster signature**, а не **graded partial dependence**. Текущий runtime строит independence map из evidence lines, считает `raw_evidence_line_count`, `effective_independent_evidence_count`, использует фиксированный набор collapse dimensions и объединяет method ids через Foundry consensus/equivalence reports; схема independence map также требует явные `collapse_clusters` и их dimensions. Это хорошая база для hard-collapse, но она пока не выражает частичную зависимость, strand-specific weighting, singularity deficits и полярность counterevidence. fileciteturn15file0L3-L3 fileciteturn16file0L3-L3

Репозиторный ADR-0160 уже задает нормативное направление: major empirical policy claims должны опираться на predeclared evidence portfolios; сила evidence измеряется не raw line count, а **effective independent evidence count**; линии должны collapse при shared primary source lineage, corpus ancestry, author/institution pool, preprocessing, assumptions, identification strategy, equivalent method family и other common failure modes; severe tests и disconfirming lines не опциональны для serious closeout. Failure-pattern register закрепляет это как анти-паттерн P14: raw evidence count inflation. fileciteturn17file0L3-L3 fileciteturn41file0L3-L3

Внешняя литература подтверждает, что зависимость между ostensibly separate lines реально искажает synthesis: robust variance estimation создана именно потому, что meta-regression плохо работает при complex correlations among non-independent effect sizes; shared subjects across studies порождают dependence и могут создавать spurious associations, если overlap не учтен; publication selection bias способна существенно уменьшать apparent effect evidence after adjustment; а в simulation ensembles предположение независимости моделей считается слишком сильным и ухудшает uncertainty quantification. Даже в duplicate-reporting задачах для adverse-event databases дубликаты признаны помехой статистическому анализу и клинической оценке. citeturn22view0turn22view1turn23view0turn22view2turn23view1

Мой итоговый вывод: для PolicyOS не нужна замена текущей independence map. Нужен **двухслойный режим**. Слой первый — сохранить нынешний strict cluster collapse как fail-closed contract. Слой второй — добавить к нему **graded effective independence calculus**: pairwise score, strand-aware channel weights, novelty-based aggregation, explicit singularity deficits и separate accounting for support versus counterevidence. Это даст совместимость с текущей схемой и одновременно решит именно ту conceptual gap, которую ставят C13 и C29. fileciteturn15file0L3-L3 fileciteturn16file0L3-L3 fileciteturn14file0L3-L3

## Repository-grounded baseline

Текущий evidence-line contract уже требует больше, чем просто “источник и метод”. Для каждой линии обязательны: binding к portfolio и claim ids, `evidence_strand`, `method_id`, `source_lineage`, `method_assumptions`, `specification_id`, `producer_identity` и `execution_context`. Поддерживаемые strands уже включают `legal`, `data`, `literature`, `method`, `simulation`, `distributional`, `feasibility` и `monitoring`. Это означает, что C29 не должен вводить новую primitive сущность; он должен расширять уже существующий evidence-line record дополнительной identity semantics и pairwise scoring logic. fileciteturn20file0L3-L3

Текущий runtime independence map collapse-ит линии по десяти параметрам: `claim_ids`, `evidence_strand`, `method_cluster_id`, `source_lineage_cluster_id`, `corpus_ancestry_cluster_id`, `author_institution_pool_id`, `preprocessing_cluster_id`, `assumption_cluster_id`, `identification_strategy_id` и `shared_failure_mode_cluster_id`. Method clusters канонизируются через Foundry consensus/equivalence reports. По сути, существующая логика уже формализует жесткое правило: если signature по этим dimensions совпадает, новая линия не должна увеличивать effective independent count. fileciteturn15file0L3-L3 fileciteturn16file0L3-L3

Репозиторий также уже содержит соседние surfaces, без которых C29 был бы неполным. Proof composability в IR различает безопасный replay и broken dependence через статусы `REUSABLE`, `REVALIDATE`, `REDERIVE` и `UNKNOWN`; это полезно как готовый язык для method-line reuse versus collapse. Fabric `SourceContract` требует schema evidence, quality contract, replay evidence, lineage seed, trust tier и SLA; Data Forge binding делает runtime-visible snapshot id, manifest identity, artifact ids, freshness и read API surfaces обязательной частью snapshot binding evidence. Иными словами, pipeline/lineage/snapshot identity уже partially typed и не должны быть придуманы заново. fileciteturn26file0L3-L3 fileciteturn30file0L3-L3 fileciteturn32file0L3-L3 fileciteturn34file0L3-L3

Еще один важный baseline: репозиторий уже умеет отдельно хранить disconfirming evidence и participation provenance. Disconfirming evidence ledger требует disconfirming lines, IR falsification reports, adversarial plans и severe tests; consultation records требуют stakeholder map, consultation plan, public comments, objections и response-to-comment reasoning. Следовательно, новая independence function должна не только “сжимать поддержку”, но и **не съедать контр-линию** и **не смешивать participation evidence с observed data**. fileciteturn39file0L3-L3 fileciteturn40file0L3-L3

## External research implications

Из внешних источников я бы взял четыре практически полезных урока. Первый: зависимость нельзя игнорировать даже если точная covariance structure неизвестна. Именно для этого в meta-analysis применяют robust variance estimation — чтобы point estimates, standard errors и hypothesis tests оставались валидными при non-independent effect sizes. Для PolicyOS это означает: pairwise dependence не обязана быть идеально идентифицирована, чтобы ее нужно было учитывать; допускается conservative approximation. citeturn22view0

Второй урок: shared underlying subjects — это не “малая корреляция”, а реальный риск spurious association. Работа по overlapping subjects в association mapping показывает, что когда studies share the same individuals, treating them as independent может искажать вывод; authors буквально предлагают “decoupling” для возврата к independent-analysis assumptions. В PolicyOS это прямо переводится в правило hard-collapse для общих primary subjects, общего case universe или общего response pool. citeturn22view1

Третий урок: apparent plurality evidence может быть структурно смещенной даже без формальных duplicates. Большое исследование publication selection bias на десятках тысяч meta-analyses показывает, что adjustment materially lowers both apparent probability of an effect and median effect sizes. Для C29 отсюда следует важное различение: overlap sponsor/institution/publication channel не обязан автоматически делать `I=0`, но он обязан понижать independence score и требовать explicit limitation, потому что correlated dissemination can inflate the visible evidence base. citeturn23view0

Четвертый урок: simulation evidence нельзя считать независимой только потому, что моделей несколько. В работе по climate-model ensembles авторы прямо называют oversimplified предположение statistical independence проблемой и показывают выигрыш от явного моделирования inter-model dependence. Для PolicyOS это означает: разные random seeds внутри одного DGP, близкие model families или calibration against the same observations — это не независимые evidential lines в production-grade portfolios. citeturn22view2

## Proposed effective-independence calculus

Предлагаю разделить расчет на три шага: **identity normalization**, **pairwise dependence scoring**, **portfolio novelty aggregation**.

### Identity normalization

`evidence_line_identity` должен расширять текущий runtime record до следующего минимального набора полей:

```yaml
line_identity:
  line_id: string
  claim_ids: [string]
  evidence_strand: one_of[legal, data, literature, method, simulation, participation, distributional, feasibility, monitoring]
  polarity: one_of[support, counter, mixed, context_only]
  source:
    source_refs: [string]
    primary_source_refs: [string]
    retrieval_path_refs: [string]
    source_contract_refs: [string]
    legal_authority_refs: [string]
  authorship:
    author_pool_ids: [string]
    institution_pool_ids: [string]
    sponsor_ids: [string]
  data:
    dataset_ids: [string]
    corpus_ids: [string]
    snapshot_ids: [string]
    subject_pool_ids: [string]
    preprocessing_cluster_ids: [string]
    transformation_lineage_refs: [string]
  method:
    method_id: string
    method_family_id: string
    identification_strategy_id: string
    assumption_cluster_ids: [string]
    proof_reuse_status: one_of[reusable, revalidate, rederive, unknown]
  model_generation:
    model_family_id: string | null
    model_snapshot_id: string | null
    prompt_chain_id: string | null
    llm_context_bundle_id: string | null
  simulation:
    dgp_id: string | null
    calibration_source_ids: [string]
    sensitivity_family_id: string | null
  participation:
    sample_frame_id: string | null
    elicitation_event_id: string | null
    facilitator_id: string | null
    coding_pipeline_id: string | null
  semantics:
    concept_spine_refs: [string]
    jurisdiction_refs: [string]
    time_role_refs: [string]
```

Это не конфликтует с текущими contracts. Напротив, оно обобщает уже имеющиеся `source_lineage`, `method_assumptions`, `specification_id`, `producer_identity`, SourceContract lineage/replay/trust, Data Forge snapshot binding и consultation provenance до единой identity surface для C29. fileciteturn20file0L3-L3 fileciteturn32file0L3-L3 fileciteturn34file0L3-L3 fileciteturn40file0L3-L3

### Pairwise scoring

Определим для каждой пары линий вектор overlap severities `o_c(a,b) ∈ [0,1]` по каналам:

- `primary_source`
- `shared_corpus`
- `shared_data_pipeline`
- `method_family`
- `assumptions`
- `author_pool`
- `sponsor_or_institution`
- `llm_generation_path`
- `legal_authority`
- `simulation_dgp`

Дальше:

```text
if hard_collapse(a, b):
    I(a, b) = 0.0
else:
    D(a, b) = min(0.95, Σ_c w_family(c) * o_c(a, b))
    I(a, b) = 1.0 - D(a, b)
```

Где `w_family(c)` — веса, зависящие от claim family / strand, а не только от строки как таковой. Это лучше, чем единый global score, потому что shared legal authority для legal claim — критическая зависимость, а для data claim — просто context; наоборот, shared dataset/pipeline для empirical claim критичны, а для legal claim практически нерелевантны. Такое family-aware weighting также согласуется с тем, что existing plan различает admissibility and authority by claim type, а не через одну глобальную шкалу. fileciteturn13file0L3-L3 fileciteturn14file0L3-L3

### Hard-collapse rules

Я рекомендую следующие hard-collapse случаи:

| Случай | `I(a,b)` | Обоснование |
|---|---:|---|
| Один и тот же primary source / subject pool / consultation event, просто перепакованный в другой артефакт | 0.0 | Это дубль, а не новый evidential line |
| Один и тот же Data Forge snapshot + тот же preprocessing cluster + тот же identification strategy | 0.0 | Новый analytical wrapper не создает новую independence |
| Один и тот же controlling legal instrument для той же proposition, jurisdiction и time slice | 0.0 | Несколько quote-слоев не создают новую legal independence |
| Тот же DGP + та же calibration source + та же assumption family | 0.0 | New seeds are variance exploration, not independent support |
| Тот же LLM model snapshot + та же prompt chain + тот же retrieval bundle для той же claim | 0.0 | Это один generation lineage |
| Один и тот же study reported as preprint, journal article, policy brief, press release | 0.0 | Multiple reports of one study cannot be counted repeatedly |

Такой набор согласуется с текущим repo emphasis на primary lineage, assumptions, equivalent methods и common failure modes, а внешняя литература отдельно подтверждает, что non-independence из overlapping subjects, shared generation lineages и inter-model dependence materially matters for synthesis. fileciteturn15file0L3-L3 fileciteturn17file0L3-L3 citeturn22view1turn22view2turn23view1

### Partial-collapse rules

Partial collapse нужен там, где линии не identical, но явно не orthogonal. Я бы использовал следующие default bands:

| Условие | Рекомендуемый диапазон `I(a,b)` | Комментарий |
|---|---:|---|
| Общий dataset, но иная method family и частично иные assumptions | 0.20–0.45 | Данные зависимы, методическая новизна есть |
| Иная data source lineage, но один method family и один identification strategy | 0.35–0.60 | Методическая ошибка может быть общей |
| Общий author/institution pool без общего dataset | 0.55–0.80 | Partial dependence, не auto-collapse |
| Общий sponsor без общего author pool или dataset | 0.70–0.90 | Сигнал dissemination bias, но слабее data overlap |
| Общий legal hierarchy, но разные instruments и разные propositions | 0.60–0.85 | Есть institutional dependence, но не тождество |
| Один DGP family, но иные calibration sources и sensitivity family | 0.25–0.50 | DGP dependence dominates |
| Разные participation channels, но один sample frame | 0.30–0.55 | Channel differs, people do not |
| Разные lines, общая только high-level concept spine | 0.90–1.00 | Концептуальная соотнесенность не означает collapse |

Эти диапазоны — не эмпирическая истина “из литературы”, а design defaults для PolicyOS. Их правильное место — в calibrated lookup table, которую потом должны обучать и проверять на C25/C26 корпусах и fixture packs, а не зашивать как неоспоримую константу. Именно так repo и ставит вопрос: C29 должен дать calculus и fixtures, а C25/C26 — calibration and semantic evaluation. fileciteturn14file0L3-L3

## Aggregation rules and decision table

Предлагаю считать не “сумму источников”, а **effective support mass** через novelty contribution каждой новой линии. Для каждого claim и polarity строится independence matrix `I`. Затем линии сортируются по admissibility/authority quality, а вклад каждой новой линии считается так:

```text
quality(a) ∈ {1.00 admissible, 0.75 proxy_with_limitation, 0.50 context_only}
novelty(a | S) = 1, если S пусто
novelty(a | S) = max(0, min_{b in S} I(a,b)), если S непусто

effective_mass(S) = Σ_{a in ordered(S)} quality(a) * novelty(a | accepted_before)
```

Это intentionally submodular: первая сильная линия дает почти весь вес, точный дубль дает ноль, частично зависимая линия добавляет только fraction, а реально orthogonal line почти целую единицу. Такой ход согласуется и с runtime aim “effective count cannot exceed raw count”, и с внешней meta-analytic практикой работы с dependent evidence, где correlation требует correction rather than naive counting. fileciteturn15file0L3-L3 citeturn22view0turn22view1

Counterevidence нельзя неттировать “в тишине”. Для каждого claim должны отдельно считаться:

- `effective_support_mass`
- `effective_counter_mass`
- `effective_context_mass`
- `largest_hard_collapse_cluster`
- `dominant_collapse_reason`
- `singularity_deficits`

Дальше synthesis принимает решение не по одному числу, а по вектору вида:

```yaml
claim_synthesis:
  support_mass: float
  counter_mass: float
  balance_status: one_of[support_dominant, mixed, counter_dominant, insufficient]
  independence_status: one_of[sufficient, weak, singular, inflated_raw_count]
  limiting_deficits: [string]
```

Это необходимо, потому что ADR-0160 и disconfirming-evidence ledger прямо требуют severe tests, divergence clusters и explicit disagreement output; PolicyOS не должен превращать independent counter-line в “минус 1 к support” и тем самым скрывать конфликт. fileciteturn17file0L3-L3 fileciteturn39file0L3-L3

### Practical decision table

| Пара линий | Решение | Что объяснить пользователю |
|---|---|---|
| Один и тот же study в preprint и journal | Hard-collapse | “Это один и тот же empirical event в двух оболочках” |
| Один dataset, два разных estimators | Partial-collapse | “Методическая независимость частичная, data lineage нет” |
| Один statute и agency FAQ, повторяющий его смысл | Hard-collapse | “FAQ не создает новый legal authority” |
| Два court decisions разного уровня по одному statute | Partial-collapse или conflict | “Есть shared authority chain, но есть самостоятельная interpretive surface” |
| 20 Monte Carlo seeds одного simulator | Hard-collapse | “Это uncertainty exploration, не 20 независимых evidential lines” |
| Две surveys, но один sampling frame и один sponsor | Partial-collapse | “Есть новый observation wave, но population dependence существенна” |
| Одна public-hearing transcript и LLM-coded summary той же hearing | Hard-collapse | “Summary не добавляет новый participation evidence” |
| New dataset + new method + new institution, но тот же sponsor | Mostly independent | “Sponsor overlap noted as limitation, но core evidential lineage различна” |

## Threshold matrix and fixture pack

Ни репозиторий, ни внешняя evidence-synthesis литература не дают единственно “научно верных” минимальных чисел для всех доменов. Поэтому ниже — **PolicyOS design defaults**, которые должны использоваться как operator-facing and readiness-facing policy, а не как универсальный философский закон. Их задача — сделать deficits explicit. Это соответствует plan logic: authority-level gates, acceptable deficits и calibration must be explicit. fileciteturn14file0L3-L3

### Recommended minimum effective independent support mass

| Claim family | Exploratory | Research | Governed | Production |
|---|---:|---:|---:|---:|
| Data / empirical / causal | 1.0 | 2.0 + counter mass ≥ 0.5 | 3.0 + counter mass ≥ 1.0 | 3.5 + at least two distinct source lineages + counter mass ≥ 1.0 |
| Scholar / literature synthesis | 1.0 | 2.0 | 3.0 | 4.0 or explicit sparse-field deficit |
| Method / analytic / proof | 1.0 | 1.5 | 2.0 with at least one non-equivalent method cluster | 2.5 with replay/composability evidence |
| Legal / competence / applicability | 1 controlling line | 1 controlling + conflict scan | 1 controlling + 1 independent interpretive or implementation line where available | same as governed, or singularity deficit if world has only one controlling source |
| Simulation / forecast / implementation behavior | 1.0 | 1.5 | 2.0 with at least two DGP or calibration families | 2.5 plus non-zero sensitivity/counter mass |
| Participation / legitimacy / preference | 1 provenance-backed line | 1.5 | 2.0 with at least two channels or one channel plus representativeness deficit | 2.5 with distinct channels/pools and response-to-objection coverage |

Эта матрица делает две вещи, которых обычно не хватает raw-count heuristics. Во-первых, она требует больше для higher authority only where extra independence is meaningful. Во-вторых, она допускает **singularity deficits** там, где сама реальность не предоставляет нескольких truly independent lines — особенно в legal claims и узких domain literatures. Это лучше, чем искусственно раздувать “независимость” за счет paraphrase artifacts, FAQ pages и same-study republishes. fileciteturn14file0L3-L3 fileciteturn41file0L3-L3

### Explicit deficit vocabulary

Я рекомендую завести типизированные deficits:

- `single_authority_singularity_deficit`
- `single_source_singularity_deficit`
- `shared_dataset_inflation_deficit`
- `equivalent_method_cluster_deficit`
- `shared_dgp_deficit`
- `participation_representativeness_deficit`
- `counterevidence_missing_deficit`
- `publication_channel_dependence_limitation`

Они лучше, чем неявный fail, потому что сочетаются с existing admissibility / authority / disconfirming-evidence surfaces и позволяют PolicyOS сказать не только “мало evidence”, но и **почему именно независимость не может быть честно достигнута**. fileciteturn39file0L3-L3 fileciteturn14file0L3-L3

### Fixture pack

Ниже — минимальный fixture pack, закрывающий acceptance criterion.

| Fixture | Line types | Raw count | Effective result | Why |
|---|---|---:|---:|---|
| Same snapshot different wrappers | data | 3 | 1.2 | one snapshot/pipeline duplicated; only one line adds limited method novelty |
| Statute plus FAQ plus agency memo | legal | 3 | 1.0 | same controlling authority, no new independent legal anchor |
| Preprint plus journal plus press summary | scholar | 3 | 1.0 | one study, three publication shells |
| Equivalent estimators in same Foundry cluster | method | 4 | 1.6 | three methods collapse by equivalence, fourth only partially novel |
| Same simulator, new seeds | simulation | 20 | 1.0 | stochastic variation, not new evidential lineage |
| Hearing transcript plus analyst summary plus LLM coding | participation | 3 | 1.0 | same event and participant pool |
| Independent negative study | scholar/data | 1 counter line | counter mass +1.0 | must remain visible as counterevidence, not cancel silently |
| Shared sponsor, distinct data and methods | data/scholar | 2 | 1.6–1.8 | sponsor overlap reduces but does not erase independence |

Эти fixtures хорошо согласуются и с current repo surfaces, и с empirical literature: duplicate reports mislead assessment, overlapping subjects create dependence, non-independent effect sizes need correction, publication selection distorts apparent evidence bases, and inter-model dependence matters in multi-model synthesis. fileciteturn15file0L3-L3 fileciteturn39file0L3-L3 citeturn23view1turn22view1turn22view0turn23view0turn22view2

## Open questions and implementation notes

Самое важное открытое место — calibration. Весовые коэффициенты по каналам и пороги effective mass должны жить не как “магические числа”, а как tested policy table, проверяемая на challenge packs и semantic false-pass probes. Именно поэтому я считаю правильным sequence: сначала утвердить described calculus and fixture pack, потом прогнать его через C25/C26 corpora и только после этого превращать его в strict readiness policy. fileciteturn14file0L3-L3

Второе ограничение: я исследовал в глубину именно те repo surfaces, которые непосредственно несут C29-смысл — research plan, consolidation task, ADR-0160, runtime independence map, evidence-line contract, SourceContract/Data Forge bindings, proof composability, disconfirming evidence и consultation records. Я не проходил весь dense-context universe по каждому смежному модулю, поэтому некоторые вторичные anchors из broader portfolio/synthesis chain здесь использованы через их load-bearing contracts, а не через полный code-pass по всем файлам. Это не меняет основной рекомендации, потому что для C29 критические invariants уже видны в examined surfaces. fileciteturn3file0L1-L3 fileciteturn14file0L3-L3 fileciteturn15file0L3-L3 fileciteturn17file0L3-L3

Практически я бы формулировал итоговую рекомендацию так: **сохранить current cluster-based independence map как fail-closed integer baseline; добавить поверх него strand-aware pairwise score, novelty-based effective mass, explicit singularity deficits и separate counterevidence accounting; публиковать both raw and effective counts, но authority decisions принимать only on effective mass plus deficit matrix.** Это наилучшим образом соответствует уже принятым ADR и failure-pattern logic PolicyOS. fileciteturn17file0L3-L3 fileciteturn41file0L3-L3


# Концептуальная форма concept spine для PolicyOS

## Контекст в кодовой базе

Внутри текущего фреймворка PolicyOS вопрос уже частично «заземлён» в коде и принятых ADR, поэтому C28 нельзя решать как чистый greenfield. Активный research plan прямо фиксирует, что существующие модули покрывают парные сопоставления, cross-graph аналитику, semantic binding и частично producer-spine hooks, но **не** решают «shared cross-producer concept authority» как самостоятельную поверхность; именно поэтому `C6-C8` вынесены как отдельный conceptual kernel. В consolidated backlog C6 уже свёл промежуточный вывод к **runtime-owned per-run reconciled authority artifact**, а ADR-0158 закрепил, что первый ход — это проекция **per-run concept and jurisdiction spine over existing reconciliation surfaces**, а не создание нового монолитного master registry. При этом schema для `policy_design_concept_spine_v1` уже требует `run_id`, `job_id`, `tenant_id`, `canonical_concepts`, `reconciliation_trace`, `normalization_trace`, `unresolved_concepts`, `conflicting_concepts`, `claim_numerical_semantics_refs`, `blockers` и статус `pass|blocked`; boundary-record дополнительно fail-closed, если продюсер пытается скрыть blockers за `status=pass`. `semantic_binding.py` уже задаёт общий producer-spine read context для `lex`, `fabric`, `scholar`, `foundry`, `scientist`, `final_compiler`, а также поля для consumed refs, candidate bindings, blocker refs и локальных labels. Тесты и fixtures уже проверяют synonym collision, unit/geography/time/legal mismatches и reject статических инвентарей как неавторитетных для closeout. Всё это означает: у репозитория уже есть сильный уклон в пользу **run-scoped authority surface**, но ему всё ещё не хватает аккуратной модели глобально управляемых namespaces и lifecycle semantics. fileciteturn35file0L3-L3 fileciteturn38file0L3-L3 fileciteturn39file0L3-L3 fileciteturn42file0L3-L3 fileciteturn40file0L3-L3 fileciteturn43file0L3-L3 fileciteturn44file0L3-L3 fileciteturn45file0L3-L3 fileciteturn67file0L3-L3 fileciteturn62file0L3-L3 fileciteturn63file0L3-L3 fileciteturn70file0L3-L3 fileciteturn72file0L3-L3

## Сравнение вариантов и решение

Ниже — сжатое сравнение трёх кандидатных физических форм.

| Форма | Что даёт | Что ломает | Совместимость с PolicyOS |
| --- | --- | --- | --- |
| Глобальный governed registry | Стабильные IDs, централизованный lifecycle, удобные миграции и public notice | Форсирует преждевременный консенсус, перегружает governance, плохо переносит case-specific populations, columns, legal applicability и method scopes | Низкая |
| Per-run reconciled artifact | Отлично выражает case closure, same-input discipline, typed blockers, run-specific scope | Слабее для cross-run reuse, deprecation notice, public migration и долговременных namespaces | Средняя |
| Гибрид | Долговечные namespaces там, где они реально нужны; per-run reconciliation — там, где смысл зависит от случая | Требует двух уровней дисциплины: namespace governance и run-time reconciliation | Высокая |

**Решение:** выбрать **гибридную форму**:  
**governed namespaces + per-run reconciliation records**, где **authoritative closeout surface всегда остаётся per-run concept spine artifact**.

Это решение лучше всего согласуется с уже принятыми ограничениями репозитория. С одной стороны, ADR-0158 прямо отвергает немедленный переход к «another standalone registry by default» и говорит, что новый монолитный registry допустим только после доказательства провала существующих reconciliation surfaces. С другой стороны, чисто per-run подход плохо отвечает на требования lifecycle, versioning, replacement, public notice и replay under old semantics, которые в репозитории уже появляются через deprecation/migration поля SourceContract, same-input closure и runtime authority envelopes. Гибрид сохраняет главный принцип репозитория — **не делать global consensus там, где оправдана только run-time reconciliation** — и при этом добавляет минимально необходимую глобальную управляемость. fileciteturn67file0L3-L3 fileciteturn60file0L3-L3 fileciteturn74file0L3-L3

Внешние стандарты поддерживают именно такую форму, а не «всё в один registry». SKOS различает `ConceptScheme`, иерархические связи (`broader`/`narrower`) и mapping properties (`closeMatch`, `exactMatch`) между **разными схемами**; при этом W3C отдельно предупреждает, что `owl:sameAs` обычно **неподходящ** для связывания концептов из разных схем из-за нежелательных формальных последствий. Это ровно тот случай, где гибрид сильнее: глобально управляются scheme-level namespaces и relation vocabulary, а конкретная equivalence/bridge authority фиксируется на уровне run artifact, а не насаждается как universal truth. citeturn5view0turn6view0turn6view1turn6view2turn18view0

## Что должно быть глобально управляемым, а что — разрешаться per run

Практическое правило здесь такое: **глобально управляется только то, что остаётся устойчивым across runs без знания конкретного claim scope**. Всё остальное должно замыкаться в per-run reconciliation record.

| Класс концепта | Рекомендуемая форма | Почему |
| --- | --- | --- |
| policy term | в основном per-run, с optional governed namespace для зрелых терминов | смысл почти всегда зависит от jurisdiction, beneficiary class, legal instrument и policy intent |
| metric | гибрид | metric family и stable metric ID можно управлять глобально, но denominator, aggregation, coverage и operationalization часто run-specific |
| data column | per-run / source-local | колонка принадлежит source contract или snapshot; её binding к концепту не должен считаться глобальной истиной |
| norm | гибрид | citation/issuer IDs глобально устойчивы, но applicability, competence, delegation и effective-time — run-specific |
| method requirement | гибрид | family/contract глобальны, а достаточность для claim и relation `satisfies_method_obligation` — per-run |
| population | per-run | почти всегда compositional и claim-scoped |
| geography | глобально versioned + per-run crosswalk | нужны стабильные кодовые системы, но boundary version и crosswalk — отдельная run-time обязанность |
| time | глобально управляемы `time roles`, calendars и axis IDs; интервалы — per-run | роль времени должна быть общей, конкретный interval и effective/as-of binding — контекстные |
| unit | глобально | unit/currency/tax-base vocabularies должны быть стабильны |
| legal authority type | глобально | `enabling`, `delegating`, `implementing`, `funding`, `oversight`, `appeals_or_contestability` — это общая taxonomy |

Эта разметка соответствует тому, как сама кодовая база уже разносит ответственность. В C6/C7/C11 backlog consolidation policy terms, metrics, dataset columns, legal concepts, method requirements, populations, geographies и time predicates перечислены как объекты reconciliation, а schema concept spine уже несёт поля для geography, population, time, units, currency, price bases, exchange rates, inflation adjustments, calendars и freshness. `SourceFacetBinding` и `SourceContract v2` показывают, что schema/field/source/quality/lineage/freshness/deprecation принадлежат producer-side contracts, а не абстрактному мировому ontology layer. Следовательно, глобально стоит управлять только reference frames и stable vocabularies, а не всеми final bindings. fileciteturn38file0L3-L3 fileciteturn39file0L3-L3 fileciteturn42file0L3-L3 fileciteturn44file0L3-L3 fileciteturn59file0L3-L3 fileciteturn60file0L3-L3

Практически это означает, что **глобально управляемый namespace** должен быть маленьким и предсказуемым: unit IDs, currency IDs, calendar IDs, time-role taxonomy, geography scheme/version IDs, legal authority type taxonomy, relation taxonomy, stable norm citation schemes, stable method-family IDs. А вот **run-local reconciliation layer** должен отвечать на вопросы: «этот policy term в этом кейсе к какому metric/legal/population/time object действительно относится?», «какой scope tuple допустим?», «какой bridge authority есть между схемами?», «какие mismatches acceptable как limitation, а какие block closeout?». Это и есть тот минимальный компромисс, который выполняет acceptance criterion C28. fileciteturn36file0L3-L3 fileciteturn38file0L3-L3 fileciteturn67file0L3-L3

## Таксономия отношений и контур полномочий

### Базовая relation taxonomy

Для C28 я рекомендую следующую таксономию как research artifact.

| Отношение | Смысл | Эффект на closeout |
| --- | --- | --- |
| `identity` | тот же governed concept ID и та же version lineage | допускает прямое closure |
| `equivalence` | разные IDs, но interchangeable в пределах явно объявленного scope tuple и authority bridge | допускает closure только с bridge evidence |
| `broader` / `narrower` | иерархическое включение без полной взаимозаменяемости | discovery/traceable rationale, но не auto-closure |
| `scope_shifted` | близкий referent, но изменён population/geography/time/unit/aggregation/instrument | limitation, split claim или blocker |
| `authority_shifted` | близкий referent, но другой issuer/scheme owner/competence lineage | требует authority bridge; иначе blocker |
| `conflicting` | позитивная несовместимость смыслов для данного claim | blocker |
| `deprecated` | термин исторически валиден, но заменён/снят с будущего использования | требует replacement/migration policy |
| `unresolved` | есть несколько кандидатов или недостаточно evidence для выбора | blocker |
| `operationalizes` | source column / feature operationalizes metric or policy term | не `same_concept`, а support edge |
| `governs` | norm governs policy term / requirement | не `same_concept`, а normative edge |
| `satisfies_method_obligation` | method requirement закрывает obligation | не identity |
| `measures` | metric measures a policy outcome or latent construct | support edge |
| `supports_claim` / `conflicts_with_claim` | relation between concept-bound evidence and claim | support/conflict edge |

Это расширяет уже существующий в backlog C6 набор (`same_concept`, `related_concept`, `conflicting_concept`, `unresolved_concept`, `scope_shifted_concept`, `authority_shifted_concept`) и делает его более операбельным для C28. Самое важное различие — **развести identity и equivalence**. W3C SKOS прямо различает `exactMatch`/`closeMatch` и предупреждает, что `owl:sameAs` для concept linking across schemes обычно порождает нежелательные следствия; это хороший внешний аргумент, почему PolicyOS не должен сводить всё «похожее» к одному canonical ID. `broader` тоже не является transitive as-is, а `closeMatch`/`exactMatch` не влекут произвольные chain entailments, что хорошо соответствует fail-closed архитектуре для semantic binding. fileciteturn38file0L3-L3 citeturn6view0turn6view2turn6view3turn18view0

### Authority envelope

Минимальный authority envelope для concept relation должен включать:

- `namespace_kind`
- `scheme_owner`
- `local_or_governed_id`
- `concept_version`
- `definition_ref`
- `relation_type`
- `relation_provenance_ref`
- `jurisdiction_scope`
- `temporal_scope`
- `population_scope`
- `geography_scope`
- `unit_semantics`
- `instrument_type`
- `data_source_scope`
- `method_scope`
- `authority_profile`
- `generated_at`
- `supersedes_ref` или `replacement_ref`, если применимо

Это не случайный список. C6 требует namespace/owner/authority/scheme/local id/version/jurisdiction/validity/language/definition ref/provenance. C7 требует competence, hierarchy, delegation, pre-emption и legal time. C11 требует unit, currency, price base, exchange-rate ref, inflation-adjustment ref, calendar, geography ref/level, temporal role/interval, freshness и transformation lineage. Поэтому единица authority здесь — не просто «concept id», а **concept plus scope envelope**. Для production-профиля concept без такого envelope не должен считаться authority-bearing. fileciteturn38file0L3-L3 fileciteturn39file0L3-L3

### Правила по authority profile

Для `research`-профиля можно допускать `equivalence` и часть `scope_shifted` связей при условии typed limitation и сохранения trace. Для `governed`-профиля `equivalence` допустима только при явном authority bridge, transform spec и указанных lossiness/reversibility. Для `production`-профиля допустимы только `identity` или `equivalence` с проверенным bridge; `scope_shifted`, `authority_shifted`, `conflicting` и `unresolved` должны либо разветвлять claim, либо блокировать closeout. Это напрямую согласуется с тем, что current schema concept spine несёт `blockers`, а boundary record и semantic binding fail-closed при неполном closure. fileciteturn42file0L3-L3 fileciteturn40file0L3-L3 fileciteturn45file0L3-L3

## Producer handshake и lifecycle semantics

### Producer handshake

Рекомендуемая handshake-семантика должна расширять уже существующие `ProducerSpineReadContext`, `ProducerSpineBindingFields` и Producer contracts в ADR-0152/0159, а не заменять их. Минимально каждый producer должен **перед emission** объявить:

- какие concept IDs он **consume**-ит;
- какие requirement IDs и scope assumptions он consume-ит;
- какие candidate bindings он рассмотрел;
- какие IDs он выбрал и какие **reject**-нул;
- какие typed blockers он создаёт;
- какой relation type он утверждает (`identity`, `equivalence`, `operationalizes`, `governs`, `satisfies_method_obligation` и т.д.);
- какой authority envelope и какой claim impact у этого решения.

C8 уже даёт структуру `prepare -> offer -> coordinate -> commit -> closeout` и перечисляет обязательные случаи pre-emission coordination: закрытие requirement/claim/obligation, emission blocker-а, выбор или отклонение кандидатов, изменение shared assumptions и генерация артефакта, который питается в scorecard/readiness/approval/publication. Для C28 это означает: **концепт-решение не может быть чисто постфактум меткой в semantic binding; оно должно быть producer-declared event**. fileciteturn39file0L3-L3 fileciteturn43file0L3-L3 fileciteturn44file0L3-L3 fileciteturn45file0L3-L3 fileciteturn68file0L3-L3 fileciteturn69file0L3-L3

### Lifecycle semantics

Для lifecycle предлагаю следующую семантику:

- **supersede** — новый governed concept/version заменяет старый для будущих runs, но старый остаётся реплеябельным;
- **split** — старый concept распадается на несколько narrower successors; past runs сохраняют старый ID, future runs обязаны выбрать successor;
- **merge** — несколько concept IDs сводятся к одному successor, но historical provenance сохраняет исходные IDs;
- **invalidate** — concept или bridge признан ошибочным / non-authoritative; future use blocked, historical runs помечаются affected;
- **migrate** — фиксируется официальная migration path с replacement IDs, logic hash и public note;
- **replay under old semantics** — воспроизведение прошлого run должно использовать зафиксированный per-run spine ref и rule/taxonomy version refs, а не «последнее состояние registry»;
- **public notice** — для governed namespaces и published cases требуется notice о deprecation/sunset/replacement и перечень affected record families.

Здесь естественный внешний каркас даёт PROV-O: `wasDerivedFrom` описывает производность нового entity от старого, `wasRevisionOf` — именно revision lineage, `alternateOf` и `specializationOf` — разные аспекты того же объекта, `generatedAtTime` и `invalidatedAtTime` — временные точки появления и прекращения валидности. OBO Foundry, в свою очередь, жёстко рекомендует: если смена definition меняет referents, нужно создавать **новый term с новым IRI**, а старый — deprecated/obsolete; также нужно заранее объявлять replacement guidance. Это почти идеально накладывается на C28: governed namespace должен быть versioned и conservative, а per-run spine — фиксировать, под какими semantics был закрыт case. citeturn6view5turn17view0turn17view1turn17view2turn17view3turn19view0

В самой кодовой базе уже есть элементы этой дисциплины: accepted overrides в Fabric entity resolution требуют `provenance_ref` и `merge_governance_ref`, но по умолчанию не мутируют canonical facts; `SourceContract` имеет `deprecated_at`, `sunset_at`, `replacement_contract_id`, `migration_note`; fixtures и runtime authority envelopes уже различают `runtime_emitted`, `runtime_blocker` и `not_authoritative`, а same-input closure отдельно фиксирует, можно ли воспроизвести прошлую семантику. Поэтому C28 не должен выдумывать новую lifecycle-модель с нуля — ему достаточно обобщить уже существующие patterns на concept layer. fileciteturn46file0L3-L3 fileciteturn48file0L3-L3 fileciteturn60file0L3-L3 fileciteturn70file0L3-L3 fileciteturn72file0L3-L3

## Рекомендуемый fixture set

Ниже — fixture set, который лучше всего проверяет выбранную физическую форму.

| Fixture | Что проверяет | Ожидаемый результат |
| --- | --- | --- |
| `concept_jurisdiction_spine_pass` | per-run spine как runtime authority | pass |
| `concept_jurisdiction_spine_static_inventory_rejected` | запрет подмены per-run authority статическим inventory | rejected |
| `jurisdiction_spine_multi_jurisdiction_pass` | hierarchy/delegation/pre-emption/temporal validity | pass |
| `jurisdiction_spine_unresolved_competence_rejected` | unresolved legal competence | blocker |
| `concept_synonym_collision_rejected` | один label указывает на два concept IDs | blocker |
| `concept_scope_shift_population_rejected` | одинаковый label, но population differs | blocker или split-claim |
| `concept_scope_shift_geography_version_rejected` | boundary/version shift | transform_required или blocker |
| `concept_scope_shift_time_effective_rejected` | old norm term vs amended norm term | deprecated+superseded или blocker |
| `concept_unit_or_aggregation_conflict_rejected` | rate vs count / annual vs monthly | conflicting |
| `column_operationalizes_metric_pass` | column-to-metric как `operationalizes`, а не `identity` | pass |

Часть этого набора уже существует в репозитории. Fixtures README фиксирует, что contract fixtures — это **не production schemas yet**, а contract-shaped examples, где pass-fixtures имеют runtime event ref, CAS ref и closed same-input closure, а rejected fixtures подтверждают, что static inventory не может сам по себе удовлетворять authority. Тесты current concept spine уже сегодня проверяют synonym collision, unit mismatch, geography mismatch, time mismatch, legal mismatch и claim-level numerical semantic mismatches. Это даёт хороший baseline: C28 не нужно начинать с нуля, нужно только расширить набор на population shift, aggregation shift, legal instrument shift и boundary-version crosswalk. fileciteturn74file0L3-L3 fileciteturn62file0L3-L3 fileciteturn63file0L3-L3 fileciteturn75file0L3-L3

Для внешне узнаваемых кейсов я бы добавил как минимум два официально опирающихся сценария. Во-первых, **same label, different geography/population/tax base** на статистическом материале: Eurostat HICP определяется как harmonized measure of inflation по расходам household sector в экономических территориях стран/агрегатов; при этом reference area может быть EU/EA/EEA или отдельная страна, а HICP-CT считается по тем же принципам, но с tax rates декабря предыдущего года. Следовательно, «consumer inflation» для EA aggregate, national HICP и HICP-CT — не один и тот же concept без явного scope tuple по geography и tax basis. Во-вторых, **same label, different legal authority**: U.S. Department of Labor прямо указывает, что федеральный minimum wage задаётся FLSA, но многие штаты имеют собственные minimum wage laws, и тогда действует более высокое из требований. Значит, label «minimum wage» без jurisdiction+instrument+authority chain не должен резолвиться в один global concept. citeturn12view2turn15view2turn15view3turn15view4turn15view0turn15view1

## Итоговое решение

**Итог:** для PolicyOS следует выбрать **гибридную физическую форму**:

> **Минимально governed namespaces для устойчивых reference frames + per-run reconciled concept spine artifact как единственная authoritative surface для closeout, replay и publication.**

Это решение одновременно:
- согласуется с уже принятым направлением C6 и ADR-0158;
- не ломает существующие schema/tests/semantic binding contracts;
- поддерживает lifecycle, migration, replay и public notice лучше, чем чисто per-run модель;
- не форсирует глобальный консенсус там, где смысл зависит от population, geography, time, unit, legal instrument, source contract или method applicability. fileciteturn38file0L3-L3 fileciteturn67file0L3-L3 fileciteturn42file0L3-L3 fileciteturn45file0L3-L3

Коротко это можно сформулировать так: **глобально управляются системы координат смысла; per run управляется их фактическое согласование для конкретного policy case**. Именно такая форма лучше всего проходит acceptance C28: она репрезентирует legal, data, method, population, geography и time примеры, но не требует универсального master truth там, где PolicyOS по своей природе должен оставаться case-bounded и fail-closed. fileciteturn36file0L3-L3 fileciteturn39file0L3-L3 citeturn18view0turn17view1turn19view0

## Открытые вопросы и ограничения

Остаются три действительно открытых границы. Первая — где именно провести черту между «governed metric family» и «run-local metric operationalization»: кодовая база уже показывает необходимость этого различия, но финальная taxonomy ещё не стабилизирована. Вторая — как именно оформлять public notice и migration surfaces для published Policy Design Cases: lifecycle primitives в репозитории уже есть, но единый public contract ещё не сформирован. Третья — нужна ли в будущем отдельная lightweight registry service для governed namespaces; по текущему состоянию evidence этого **недостаточно**, и ADR-0158 правильно требует сначала доказать провал существующих reconciliation surfaces, а не строить новый монолит заранее. fileciteturn67file0L3-L3 fileciteturn60file0L3-L3 fileciteturn74file0L3-L3


# C34 Семантика легитимности участия для PolicyOS

## Контекст внутри PolicyOS

Эта спецификация должна читаться не как абстрактная теория участия, а как продолжение уже существующей архитектуры PolicyOS. В активном плане исследований C34 прямо завязан на C19 participation provenance, claim registry, public projection, Scholar evidence, human review, stakeholder fields in policy design и P15 LLM speculation firewall; сам план требует решить, когда участие может поддерживать preference, acceptability, legitimacy, contestability, implementation feasibility или только context claims. fileciteturn23file0L1-L3

Внутренний каркас уже достаточно жесткий. Во-первых, structured judgement and consultation — это не факультативная заметка, а минимальная record family Policy Design Case наряду с human oversight; следовательно, C34 должен давать правила, которые реально могут быть проверены рантаймом, а не только написаны в исследовательском отчете. fileciteturn33file0L1-L3 Во-вторых, для final major claims рантайм уже требует consultation records или явных blocker records; высокосерьезные unresolved objections не могут исчезать из финальных claims и должны сопровождаться response-to-comment reasoning. fileciteturn27file0L1-L3 fileciteturn28file0L1-L3 В-третьих, внутренний failure pattern P15 уже запрещает laundering LLM-спекуляции в authoritative participation claims. fileciteturn34file0L1-L3

Отсюда главный принцип C34: **участие — это не один общий вид “социального доказательства”, а набор разных evidentiary objects с разным максимумом допустимого использования**. Именно это уже заложено в C19, где participation provenance описана как typed, claim-linked, audience-aware и fail-closed, а в качестве blocker codes прямо перечислены `nonrepresentative_for_claim_scope`, `summary_without_underlying_method`, `llm_speculation_not_participation` и `dissent_not_recorded`. fileciteturn14file0L1-L3

## Семантика типов утверждений

Для C34 полезно жестко развести девять claim types. Это различение следует из самой постановки задачи C34 и из C19, но ниже я довожу его до операционального уровня. fileciteturn23file0L1-L3 fileciteturn14file0L1-L3

**Preference** — это утверждение о том, чего хотят затронутые люди между опциями или в отношении конкретного дизайна политики.  
**Lived experience** — это утверждение о пережитом опыте, бремени, барьерах, вреде или выгоде “изнутри”.  
**Acceptability** — это утверждение о том, воспринимается ли опция как терпимая, приемлемая или социально/практически допустимая для затронутых групп.  
**Legitimacy** — это не общий “мандат народа”, а более узкое утверждение, что процесс Policy Design Case дал materially affected groups осмысленную и видимую возможность повлиять на решение.  
**Procedural fairness** — это утверждение о честности самого процесса: кто был приглашен, кто пропущен, когда проходило участие, как велась фасилитация, как обрабатывались возражения и как был дан feedback.  
**Implementation feasibility** — это утверждение о выполнимости решения для implementers, administrators, regulated entities и иных operational actors.  
**Objection** — конкретное оспаривание, адресованное к claim, design choice, implementation path или legitimacy of process.  
**Dissent** — не устраненное несогласие, сохраняемое в записи без принудительного усреднения.  
**Context** — background signal, issue-spotting, hypothesis generation или environmental scanning, не претендующий на affected-person preference или legitimacy. fileciteturn23file0L1-L3

Для PolicyOS особенно важно различать **preference**, **acceptability** и **legitimacy**. Они часто смешиваются в практических консультациях, но по смыслу это разные вещи. IAP2 Spectrum прямо различает режимы inform, consult, involve, collaborate и empower, и у каждого режима разный “promise to the public”: от простого информирования до обратной связи о том, как input повлиял на решение, и, в крайнем случае, до передачи решения публике. Значит, сам факт “были комментарии” еще не доказывает ни предпочтение, ни легитимность в одном и том же смысле. citeturn7view0

Наконец, внутри PolicyOS нужно проводить жесткую границу между **judgement** и **data**. В consultation/legitimacy коде structured expert judgement требует явной классификации `judgement_not_data`, а попытка masquerade-as-observed-data считается ошибкой. Это правило я предлагаю распространить и на analyst interpretation of participation: аналитическая интерпретация может быть пояснением, но не наблюдаемым participation fact. fileciteturn26file0L1-L3 fileciteturn27file0L1-L3

## Матрица допустимого использования участия

Ниже — рекомендуемая participation legitimacy matrix. Это **нормативный синтез** внутренней логики PolicyOS, IAP2-уровней участия, AAPOR-требований к survey provenance и Stanford Deliberative Polling как эталона deliberative mini-public. fileciteturn23file0L1-L3 fileciteturn14file0L1-L3 fileciteturn34file0L1-L3 citeturn7view0turn7view1turn13view0

| Source kind | Что может поддерживать напрямую | Что может поддерживать только ограниченно | Что не должно поддерживать |
| --- | --- | --- | --- |
| **Survey** | Preference и acceptability, **если** есть достаточная frame/sampling provenance и claim scope совпадает с population scope | Implementation feasibility, если респонденты — роль-совпадающие implementers/regulatees; context через open responses | Procedural fairness и legitimacy **сами по себе**; survey alone не доказывает честность процесса |
| **Consultation** | Objection, dissent, context, issue salience, participation gaps | Procedural fairness и limited legitimacy of process, если есть affected-group map, timing, response-to-comment и visible missing groups | Population preference/prevalence claims |
| **Deliberative panel** | Considered preference, considered acceptability, trade-off reasoning | Limited legitimacy claim о качестве мини-публичного процесса; broader legitimacy только при сильной recruitment provenance | Raw population prevalence без отдельной survey basis |
| **Hearing** | Attributable objection, dissent, organized contestation | Procedural fairness of hearing process, если доступ и responses documented | Population preference |
| **Administrative complaint** | Implementation failures, harms signals, contestability, lived experience fragments | Feasibility warnings и subgroup-specific acceptability concerns | General preference or legitimacy of policy as a whole |
| **Civil-society submission** | Organized position, normative objection, stakeholder contestation | Inclusion of stakeholder voice and context of organized affected interests | Representative preference of affected persons in general |
| **Expert interview** | Implementation feasibility, operational context, system constraints | Acceptability only for the expert’s role-bound domain, не “от имени affected persons” | Affected-person preference или democratic legitimacy |
| **Affected-person testimony** | Lived experience, harms, barriers, concrete objection, subgroup context | Case-level acceptability or subgroup concern, если attribution and consent suffice | Population prevalence or majority preference |
| **LLM / analyst speculation** | Candidate context, hypothesis generation, issue spotting | Ничего authority-bearing | Preference, acceptability, legitimacy, feasibility, objection или dissent как “реальные” participation facts |

Ключевой смысл матрицы такой. **Consultation, hearing и testimony почти всегда богаты для objection, dissent, lived experience и context, но почти никогда не дают population preference.** Напротив, **survey может поддерживать prevalence claims, но не закрывает procedural fairness или legitimacy without process evidence**. Deliberative panel занимает промежуточное положение: он лучше обычной консультации для considered judgment, потому что включает balanced briefing materials, competing experts, trained moderators и pre/post process, но даже он не должен автоматически переименовываться в “волю населения” без доказанной representativeness scope. citeturn13view0turn7view1turn7view0

Отдельно фиксирую жесткое правило C34: **LLM/analyst speculation никогда не может поддерживать affected-person preference или legitimacy claims**. Для PolicyOS это не просто хороший принцип, а прямое продолжение P15 и C34 acceptance criterion. fileciteturn34file0L1-L3 fileciteturn23file0L1-L3

## Рубрика provenance и пороги допустимости

### Классы provenance

Вместо одного универсального численного порога я рекомендую использовать четыре provenance classes. Это лучше согласуется и с AAPOR disclosure logic, и с C19 blocker model, и с тем, что разные source kinds несут разную epistemic нагрузку. fileciteturn14file0L1-L3 citeturn7view1turn13view0turn7view0

| Provenance class | Минимум, который должен быть известен | Верхний предел допустимого использования |
| --- | --- | --- |
| **A — population-representative** | Who was asked; target population; frame; probability or strongly governed stratified design; recruitment; field dates; mode; sample size; precision/weighting logic; sponsor; limitations | Population preference, population acceptability, subgroup comparisons в пределах дизайна |
| **B — structured subgroup or role coverage** | Affected-group map; role mapping; recruitment logic; who is missing; facilitation/briefing design when relevant; dates; sponsor; limitations | Subgroup preference, considered judgment, legitimacy/process claims, implementation feasibility |
| **C — attributable but nonrepresentative** | Speaker identity or protected attributable class; how captured; when; why included; consent/redaction; limitations | Lived experience, objection, dissent, case-level feasibility/context |
| **D — unverifiable or speculative** | Missing identity/method/frame or LLM/analyst-generated | Context candidates only; no authority-bearing participation claim |

### Пороги по типу claim use

| Claim use | Минимальный provenance class | Дополнительные условия |
| --- | --- | --- |
| **Population preference** | A | Sample scope должен совпадать с claimed population; open/self-selected participation не подходит |
| **Subgroup preference** | A или strong B | Группа должна быть заранее определена в stakeholder map; нельзя обобщать за ее пределы |
| **Considered preference / acceptability after deliberation** | B, желательно A-like recruitment | Balanced materials, visible facilitation, dissent logging, panel composition disclosed |
| **Legitimacy** | B | Нужны affected-group mapping, invited/missing groups, timing before decision lock-in, consultation mode, response-to-comment, dissent visibility, sponsor/facilitation disclosure |
| **Procedural fairness** | B | Нужны process records, а не только outcome tallies |
| **Implementation feasibility** | B | Источники должны быть role-matched: implementers, administrators, regulated entities, service providers, frontline staff |
| **Objection / dissent** | C | Достаточны attributable and verified records; representativeness не требуется, но hiding is forbidden |
| **Lived experience** | C | Требуются consent/redaction and release constraints |
| **Context** | C или D | Явная маркировка `context_only`; нельзя использовать для preference or legitimacy promotion |

### Минимальные provenance fields

Вот минимальная рубрика, которую я рекомендую прикрутить к каждому participation record в PolicyOS. Она синтезирована из C19/C34, из consultation runtime code и из AAPOR disclosure elements. AAPOR отдельно требует раскрывать sponsor, measurement instrument wording, study population, sample generation/recruitment, modes, dates, sizes/precision, weighting, quality checks и limitations; для nonprobability samples precision claims допустимы только при явной модели и ее валидации. fileciteturn14file0L1-L3 fileciteturn26file0L1-L3 citeturn7view1

| Field | Зачем нужен | Обязательность |
| --- | --- | --- |
| **claim_ids / intended claim use** | Чтобы reader знал, для чего именно пытаются использовать participation evidence | Всегда |
| **source_kind** | Чтобы задать max allowed use | Всегда |
| **consultation_mode** | To distinguish inform/consult/involve/collaborate/empower | Для consultation-like records |
| **who was asked / who spoke** | Без атрибуции нельзя утверждать, чьи preferences или harms зафиксированы | Всегда |
| **affected_group_map** | Без group mapping нельзя делать affected-person claims | Для всех claims, кроме сугубо общего context |
| **how captured** | Survey, interview, hearing, complaint, panel и т.д. меняют evidentiary ceiling | Всегда |
| **when** | Политический и implementation context быстро устаревают | Всегда |
| **sampling / recruitment / frame** | От этого зависит representativeness class | Для preference, acceptability, legitimacy, feasibility |
| **representativeness_class** | Явно ограничивает claim use | Для всех, кроме D |
| **instrument / briefing / facilitation** | Нужны для deliberative and consultation fairness | Для panel/consultation/hearing |
| **sponsor / organizer / conflicts** | Иначе legitimacy and acceptability are contestable by design | Для legitimacy/procedural fairness |
| **consent / redaction / release state** | Иначе testimony и complaints могут быть unusable publicly | Для testimony/interview/complaint |
| **aggregation method** | Скрытое усреднение разрушает dissent semantics | Если есть synthesis |
| **dissent log** | Без него legitimacy overclaims risk high | Для legitimacy, procedural fairness, contestability |
| **response-to-comment reasoning** | Нужен не просто input, а видимый effect trace | Для consultation/hearing |
| **limitations** | Fail-closed boundary for downstream use | Всегда |

Практически это означает простое правило компилятора: **каждый participation record должен иметь `max_claim_use[]`, вычисляемый из `source_kind + provenance_class + process_fields`; попытка использовать record выше этого потолка должна давать `context_only`, `nonrepresentative_for_claim_scope`, `summary_without_underlying_method` или другой typed blocker, а не молчаливую promotion to support.** Это прямо соответствует и внутреннему blocker vocabulary C19, и общей PolicyOS логике claim-bound evidence. fileciteturn14file0L1-L3 fileciteturn10file0L1-L3

## Публичная проекция, несогласие и отсутствие участия

### Как показывать unresolved dissent

PolicyOS уже движется к тому, чтобы contested records были first-class. C17 требует, чтобы public contested records показывали, **что** contested, **какие позиции** существуют, **какие evidence lines** стоят за каждой стороной, **кто может решать**, **что решено и что не решено**, **какие ограничения остаются** и **когда вопрос должен быть reopened**. C19 дополнительно требует, чтобы public projection of participation показывала source kind, consultation mode, affected-group summary, representativeness class, dates, geography, safe participant band, aggregation method, dissent presence, participation gaps, claim links, limitations и review summary, не раскрывая raw transcripts, direct identifiers и re-identification vectors. fileciteturn14file0L1-L3

Эта логика хорошо совпадает с claim-ledger rules: publishable claims нельзя silently downgrade or delete; blocked claims должны оставаться видимыми в reviewer and machine exports, а public export должен хотя бы показывать, что claims были omitted rather than never existed. fileciteturn29file0L1-L3 Значит, для C34 правильное правило такое: **unresolved dissent не агрегируется в один “балл поддержки”, а проектируется как отдельный contested surface с позициями, масштабом покрытия, severity и response trace**. Для high-severity objections consultation runtime уже требует visibility and response-to-comment reasoning в final claims. fileciteturn28file0L1-L3

### Матрица дефицита, ограничения и блокировки

Ниже — моя рекомендуемая матрица для случаев, когда participation missing or thin. Это design inference из внутреннего authority model PolicyOS: research, governed и production profiles; accepted deficit; publish-with-limitation; closeout block. fileciteturn23file0L1-L3 fileciteturn15file0L1-L3

| Authority / impact profile | Если participation отсутствует, но affected-person claims **не** делаются | Если пытаются делать preference / acceptability / legitimacy claims |
| --- | --- | --- |
| **Research, low impact, reversible** | **Accepted deficit** допустим; публично — limitation note | **Blocker** для этих конкретных claims; остальная аналитика может жить |
| **Research, medium/high impact** | **Public limitation** обязательна; нужен acquisition plan | **Blocker** для preference/legitimacy claims |
| **Governed, low/medium impact** | Возможен **public limitation** при явном participation gap | **Blocker** для legitimacy; preference только при достаточном provenance |
| **Governed, high impact or concentrated harms** | Отсутствие meaningful participation почти всегда **review-required or blocker** | **Blocker** |
| **Production / high-authority, rights-affecting, coercive, hard-to-reverse** | Только узкий emergency-style exception: **accepted deficit + narrow publication scope + mandatory revalidation/participation plan** | **Hard blocker** |

Из этой таблицы следует простое правило для C34. **Недостаток участия не всегда блокирует весь Policy Design Case, но он всегда блокирует именно тот класс claim, для которого provenance недостаточен.** Это важно: отсутствие participation не должно превращаться в blanket veto на любой policy analysis, но и не должно тихо превращаться в “social legitimacy claimed by omission.” fileciteturn23file0L1-L3 fileciteturn14file0L1-L3

## Рекомендуемая спецификация C34

Ниже — сжатая спецификация, которую, на мой взгляд, уже можно положить в decision memo или ADR draft.

**Правило о типе участия.** Каждый participation artifact в PolicyOS должен иметь минимум такие поля: `source_kind`, `consultation_mode`, `affected_group_map`, `representativeness_class`, `claim_use_requested[]`, `claim_use_allowed[]`, `consent_redaction_state`, `dissent_state`, `response_to_comment_ref`, `limitations[]`. Это напрямую продолжает C19 provenance schema и существующие consultation/human oversight record families. fileciteturn14file0L1-L3 fileciteturn33file0L1-L3

**Правило о максимуме допустимого использования.** `claim_use_allowed[]` не должен определяться человеком “на глаз”; он должен вычисляться детерминированно из source kind и provenance class. Survey с A-class provenance может поддерживать population preference; testimony никогда не может поддерживать prevalence; consultation summary без underlying method не может поддерживать legitimacy or preference; expert interview — judgement, а не observed affected-person data. fileciteturn14file0L1-L3 fileciteturn26file0L1-L3 citeturn7view1turn13view0

**Правило о legitimacy.** Legitimacy claim должен быть составным. Он требует не только evidence that people spoke, но и evidence that the process was fair enough to count: affected-group mapping, inclusion/exclusion strategy, timing before policy lock-in, visible feedback on how input influenced the decision, sponsor/facilitation disclosure, and preserved dissent. Здесь IAP2 полезен как внешний ориентир: consult/involve/collaborate/empower несут разные public promises, и PolicyOS не должен приписывать consultation более сильный legitimacy meaning, чем обещал сам процесс. citeturn7view0

**Правило о dissent.** Никакого forced aggregation unresolved dissent into a single score. Если есть materially unresolved objection, он должен жить как distinct contested object, особенно в reviewer and machine surfaces, а в public surface — как visible limitation/contest record. Это уже поддерживается claim ledger visibility rules и consultation legitimacy validation. fileciteturn29file0L1-L3 fileciteturn28file0L1-L3

**Правило о stakeholder attribution.** Preference, acceptability и legitimacy claims должны быть привязаны не к абстрактному “обществу”, а к stakeholder-scoped groups. Это соответствует самому ProblemFrame, где stakeholder scope уже описывается через `StakeholderSpec` с role, impact direction, priority и attributes. Иначе PolicyOS будет делать не affected-person claims, а rhetorical crowd claims. fileciteturn35file0L1-L3

**Правило о speculation firewall.** Любой LLM- или analyst-generated participation summary должен иметь фиксированный потолок `context_only` до тех пор, пока не появится real participation provenance. Для C34 это не частный safety rule, а acceptance rule задачи. fileciteturn34file0L1-L3 fileciteturn23file0L1-L3

Если свести все к одной строке, то итог C34 такой: **реальное participation evidence может поддерживать только те claim uses, которые оправданы его provenance; все остальное должно быть limitation, contestation, blocker или context-only, но не скрытая authority promotion.** fileciteturn23file0L1-L3 fileciteturn14file0L1-L3

## Открытые вопросы и границы решения

Это решение сознательно **не** вводит один глобальный численный порог по sample size, response rate или “доле охвата групп”. Для PolicyOS лучше сначала зафиксировать provenance classes и authority-level rules, а калибровку numeric thresholds делать отдельно по domain and authority profile; внутренний research plan как раз предупреждает не hardcode-ить participation legitimacy thresholds до conceptual closure. fileciteturn10file0L1-L3 fileciteturn17file0L1-L3

Также важно не переоценивать термин **legitimacy**. В этой спецификации это **case-level evidentiary legitimacy for a Policy Design Case**, а не полная демократическая или конституционная легитимность государственной политики. Для большого публичного решения участие может быть необходимым условием legitimacy claim внутри PDC, но оно не исчерпывает всех grounds of legitimacy. Это ограничение согласуется с тем, что внутри PolicyOS legitimacy already sits alongside legal authority, contestability, tradeoffs, public projection and human oversight, а не заменяет их. fileciteturn20file0L1-L3 fileciteturn10file0L1-L3


# Политика бюджета сложности и рубрика церемониальности для Policy Design Case

## Рамка PolicyOS и исходные ограничения

Внутренний consolidation-документ для универсального Policy Design Case прямо задает две важные рамки для C32. Во-первых, PolicyOS уже **не является blank slate**: в системе есть сильные ядра, включая registry record-family, authority envelopes, formal invariants, phase barriers, source truth, VOI primitives и public projection guardrails. Во-вторых, именно **пороговые значения complexity budget по authority level** остаются открытым концептуальным решением, а сама сложность уже названа backlog-темой первого класса: дополнительные gates и controls могут не повышать доверие, а снижать его, если становятся церемониальными, экономически невозможными или превращаются в «warning-only shelf-ware». fileciteturn5file0L3-L3 fileciteturn6file0L3-L3 fileciteturn17file0L3-L3

Документ также уже содержит те внутренние anchors, на которые и должен опираться C32. C23 разводит **run cost**, performance observability и degradation-SLA как отдельные плоскости состояния; C24 предлагает отдельный complexity ledger и принцип «каждый новый контроль должен платить аренду» реальным снижением риска, recovery cost или ростом auditability; C1 требует для soft gates владельца, TTL, escalation path, publication effect и closeout effect; C3 требует единой runtime-owned функции `can_i_closeout(run_id)`, а не разрозненных локальных pass/fail полей. Следовательно, бюджет сложности в PolicyOS должен жить не как “документационная гигиена”, а как часть статуса, self-FMEA и closeout semantics. fileciteturn20file0L3-L3 fileciteturn17file0L3-L3

Из этого следует главный внутренний тезис для C32: **“слишком тяжелый”** и **“церемониальный”** — не одно и то же. Тяжелый PDC может все еще содержать полезные и decision-coupled controls, но быть плохо смодулированным или чрезмерно фронтально нагруженным. Церемониальный PDC — это уже случай, когда records, gates, reviews или controls перестают materially влиять на admissibility, authority, routing, public limitation, rerun decisions или closeout. Эта развилка полностью соответствует внутренней картине “component-rich, bridge-thin architecture”, где проблема часто не в полном отсутствии контроля, а в неправильной упаковке и orchestration. fileciteturn4file0L3-L3 fileciteturn5file0L3-L3

## Что подсказывают внешние практики пропорциональной гарантии

Внешняя литература довольно согласованно поддерживает идею **risk-based, authority-sensitive assurance**, а не линейного наращивания церемоний. NIST SP 800-53B строит baseline selection вокруг разных уровней impact и прямо говорит о baselines, tailoring guidance и overlays для конкретных сред и сообществ. NIST SP 800-37 Rev. 2, в свою очередь, описывает structured but flexible RMF, который связывает control selection, assessment, authorization и **continuous monitoring**, чтобы решения оставались “near real-time” и “cost-effective”, а не упирались в исключительно фронтально собранный пакет проверки. Это сильный аргумент в пользу того, что часть assurance нужно переносить в lifecycle monitoring и revalidation, а не заставлять каждый authority level нести одинаковый upfront burden. citeturn12view0turn12view1

Операционные практики Google SRE дают вторую опору: **человеческое внимание — ограниченный ресурс**, поэтому complex control system обязан быть action-oriented. Их alerting guidance рекомендует уведомлять людей только о **significant** и **actionable** событиях, оценивая alerting strategy по precision, recall, detection time и reset time; они даже показывают, что плохо настроенные правила могут генерировать множество сигналов, которые на деле не угрожают error budget и быстро становятся игнорируемыми. В workbook по toil Google также рекомендует ставить **верхнюю границу** на operational/toil work, измерять его объективно — в минутах, часах и с учетом context switching — и проверять, что выгода автоматизации или дополнительного контроля действительно перекрывает его стоимость. В главе про simplicity Google отдельно подчеркивает, что простота коррелирует с надежностью, а proxies системной сложности включают training time, explanation time, administrative diversity и diversity of deployed configurations. Для C32 это означает, что reviewer minutes, warning backlog, artifact size и explanation time — не “второстепенные бытовые параметры”, а load-bearing assurance metrics. citeturn13view1turn13view2turn13view3turn30view0turn31view0

Исследования по assurance cases и human review усиливают этот вывод. В работе о modular assurance отмечается, что assurance cases на complex systems легко становятся **слишком строгими и трудными в разработке и поддержке**, а модульность — практический способ не потерять качество аргумента при росте масштаба. Исследование modern code review на 230 тысячах patches показало, что **16–66%** patches имели хотя бы одного приглашенного reviewer, который вообще не ответил; отдельное исследование Meta показывает, что review latency заметно зависит от workload balancing и bystander effects, а явное назначение конкретного reviewer уменьшает время review по сравнению с “командной” ответственностью. Наконец, controlled experiment по IDS alarms показал, что при росте false alarm rate с 50% до 86% медианная precision у аналитиков падала на **47%**, а time-on-task росло на **40%**. Для PolicyOS это прямой довод в пользу метрик reviewer load, false-block rate, warning backlog и явного owner semantics: высокий signal volume без decision value не нейтрален, он ухудшает human performance. citeturn26view3turn26view4turn25view1turn25view0turn26view0turn26view1turn26view2

Наконец, даже в regulatory safety practice пропорциональность формулируется как функция **риска и серьезности нарушения**, а не как механическое следование одинаковому процессу для всех случаев. HSE прямо пишет, что enforcement action должно быть proportionate to the risks to people and to the seriousness of the breach. Это не делает complexity budget “мягкой” темой; наоборот, это поддерживает позицию, что burden должен быть обоснован authority level и residual-risk picture, а не количеством привычных форм и approvals. citeturn17view1

## Предлагаемая модель метрик и бюджетов

Ниже — **стартовая синтезированная политика**, а не уже существующий внутренний стандарт репозитория. Она выводится из внутренних anchors PolicyOS по C1/C3/C22/C23/C24 и из внешних risk-based frameworks, actionable alerting, toil measurement, MODULAR assurance и VOI literature. Главное нововведение — считать не только “сколько у нас controls”, но и **какую предельную прибавку гарантии они дают за единицу человеческой и вычислительной сложности**. Внутренний C22 уже предлагает формулу `net_voi(strategy)`, а C24 требует, чтобы каждый новый контроль “pay rent”; внешняя VOI-литература определяет value of information как ожидаемое уменьшение loss или uncertainty от нового знания. Поэтому для C32 естественно ввести `Net-MAV` — net marginal assurance value. fileciteturn17file0L3-L3 citeturn32view0

Рекомендуемая формула такая:

```text
Net-MAV(item) =
  decision_gain
  + falsification_value
  + authority_gain
  + auditability_gain
  - human_time_cost
  - latency_penalty
  - rerun_penalty
  - false_block_penalty
```

Если `Net-MAV` устойчиво меньше либо равен нулю, family/gate/review/control становится кандидатом на removal, scope-down или authority-gating вверх. Если он положителен, но item выводит кейс за budget cap, это признак не церемонии как таковой, а **избыточно фронтальной упаковки**: обычно item надо модульно перенести, агрегировать или разнести по lifecycle. Если item negative-value, но формально обязателен, его нельзя просто убрать — его надо **пересобрать** так, чтобы он перестал быть пустой формой. fileciteturn17file0L3-L3 citeturn26view3turn26view4turn30view0

Перед бюджетами нужен **minimum assurance floor**, ниже которого simplification запрещен. Для PolicyOS в этот floor должны входить: authority-binding для решающих артефактов, decisive claim support, source truth и semantic binding, разрешение конфликтов и counterevidence для решающих утверждений, accepted deficits и public limitations там, где они влияют на decision meaning, а также единый closeout decision object. Внешний аналог этому — NIST guidance on minimum standards for verification: не вся проверка обязана быть максимальной, но существует базовый набор broadly applicable techniques, ниже которого просто начинается under-assurance. fileciteturn20file0L3-L3 fileciteturn17file0L3-L3 citeturn26view5turn26view6turn26view7

В таблицах ниже `D` означает число **решающих claims**: утверждений, каждое из которых само по себе может изменить legality, authority, closeout, public limitation, rerun decision или итоговое policy recommendation. Для структурированных объектов размер артефакта лучше считать не в байтах, а в **human-reviewed words** или page-equivalents, потому что именно читаемость, explanation time и cognitive load предсказывают, где сложность перестает быть управляемой. citeturn31view0turn30view0

| Метрика | Операционное определение |
| --- | --- |
| Required record count | Число **обязательных** authority-bearing или closeout-relevant records после удаления projections и пустых placeholders |
| Gate count | Число уникальных decision points, которые могут block, cap, reroute или require review |
| Reviewer load | Сумма human prep, review, re-review и coordination minutes, включая context switching |
| Run cost | Прогноз и факт использования approved budget envelope по compute, API, search, acquisition и retry families |
| Wall-clock time | Прошедшее бизнес-время от старта кейса до requested authority closeout, включая очереди и ожидание reviewers |
| Artifact size | Суммарный объем human-reviewed words или page-equivalents, необходимый для closeout |
| Rerun cost | Дополнительная стоимость и задержка, вызванные reruns из-за machinery/assurance constraints |
| Warning backlog | Число unresolved soft gates, переживших свой TTL |
| False-block rate | Доля blocks, waivers или escalations, позже признанных ненужными через replay, appeal или postmortem |
| Marginal assurance value | Ожидаемое уменьшение residual decision loss или рост authority/auditability от одного нового item |

| Метрика | Research | Governed | Production |
| --- | --- | --- | --- |
| Required record count | `4 + 2D` | `6 + 3D` | `8 + 4D` |
| Gate count | `2 + ceil(D/3)` | `3 + ceil(D/2)` | `4 + ceil(2D/3)` |
| Reviewer load | `30 + 20D` мин | `60 + 45D` мин | `120 + 90D` мин |
| Run cost vs approved envelope | amber `>110%`, red `>125%` | amber `>110%`, red `>120%` | amber `>105%`, red `>115%` |
| Wall-clock time | `1 + 0.5D` раб. дней | `3 + D` раб. дней | `5 + 2D` раб. дней |
| Artifact size | `1500 + 500D` слов | `3000 + 750D` слов | `5000 + 1000D` слов |
| Cumulative rerun cost | `<=0.5x` original run | `<=0.75x` | `<=1.0x`, дальше только по approved budget change |
| Warnings older than TTL | `<=3`, unowned = `0` | `<=2`, unowned = `0` | `<=1`, unowned = `0` |
| False-block rate | `<10%` | `<5%` | `<2%` |
| Net-MAV for each added item | `>0`, либо item явно exploratory | `>0`, либо governance-required | `>0`, либо legally/safety required |

Рабочее правило простое. **Зеленая зона** — до 80% cap; **желтая** — 81–100%, где item требует явного MAV-обоснования; **красная** — все, что выходит за cap, либо нарушает hard-fail trigger. Hard-fail triggers здесь такие: любой unowned warning после TTL, отсутствие minimum floor family, cumulative rerun cost выше cap, либо production false-block rate выше target. Эти пороги надо пересчитывать после каждых 20 “similar runs” — то есть runs с тем же authority level, сопоставимым D-band, тем же domain и схожим deadline class — потому что NIST и Google одинаково подчеркивают необходимость ongoing monitoring и объективной телеметрии, а внутренний C24 уже рассматривает complexity как ledger, а не как разовое мнение. citeturn12view1turn30view0 fileciteturn17file0L3-L3

## Когда семейство записей можно сокращать

Внутренняя логика PolicyOS и внешние risk-based frameworks сходятся в том, что сокращение должно идти не “по желанию”, а через явные операции: sampling, defer, scope-down, authority-gating и out-of-scope declaration. NIST baselines допускают tailoring и overlays; risk-based testing прямо использует risk assessments, чтобы перераспределять усилие тестирования под ограниченные ресурсы; внутренний PolicyOS уже отделяет current-run evidence от historical learning и связывает решающие claims с authority-bearing artifacts. Следовательно, record families можно сокращать только там, где сокращение **не ломает minimum floor и не меняет смысл requested authority**. citeturn12view0turn29view0turn12view1 fileciteturn20file0L3-L3 fileciteturn17file0L3-L3

| Режим | Когда допустим | Когда недопустим | Стартовое правило |
| --- | --- | --- | --- |
| Sampling | Family однородна, variance низкая, unsampled universe replayable, ни один элемент не является decisive/exception item | Family несет authority, legal competence, unresolved conflict, accepted deficit, human override или decisive claim support | Research: `max(3, 10%)`; Governed: `max(5, 15%)`; Production: `max(10, 20%)` + 100% exception items |
| Defer | Family не влияет на текущий admissibility/closeout, но нужна позже для monitoring, publication pack или revalidation | Без нее меняется legal/authority/public meaning текущего решения | Разрешать только с owner, due date, explicit closeout note и escalation path |
| Scope-down | Можно перейти с item-level на family-level summary без скрытия variance, которая может менять outcome | Summary маскирует subgroup difference, legal nuance, counterevidence, stale item или routing difference | Preserve worst-case, edge-case и exception strata полностью |
| Authority-gating | Family полезна лишь на более высоком authority level | Запрошенный authority уже делает family floor-relevant | По умолчанию поднимать вверх, а не распространять вниз |
| Out of scope | Нет правдоподобного пути, по которому family может повлиять на claim support, legality, authority, conflict handling, public limitation или lifecycle obligation | Есть хотя бы один credible path к изменению decision meaning | Нужны explicit rationale и reviewer-visible out-of-scope note |

Практический negative list должен быть жестким. **Нельзя** sampling/defer/out-of-scope для authority envelopes, decisive claim support, source-truth/semantic-binding families, unresolved conflict/counterevidence, accepted deficits/limitations, closeout decision family и любых families, без которых projection risk превращается в authority laundering. Для production также нельзя откладывать rule lineage и lifecycle/revalidation obligations, потому что closeout там порождает долгоживущий объект, а не одноразовый аналитический пакет. fileciteturn20file0L3-L3 fileciteturn17file0L3-L3

Отдельно важно, что часть сложности надо **переносить вправо по жизненному циклу**, а не фронтально добавлять в initial closeout. Если family в основном нужна для drift detection, post-publication monitoring или future revalidation, а не для сегодняшнего admissibility decision, ее detail-level content следует переносить в lifecycle ledger с explicit trigger conditions. Это лучше согласуется и с RMF continuous monitoring, и с внутренним разграничением current-run evidence versus historical learning. citeturn12view1 fileciteturn4file0L3-L3 fileciteturn17file0L3-L3

## Рубрика церемониальности

Церемониальность в C32 стоит определять не через эстетическое “слишком много бумажек”, а через **утрату decision-coupling**. Внутренний C24 уже включает box-ticking failure как machinery failure mode, а внешняя SRE-практика требует, чтобы human-facing signals были actionable и significant, иначе они создают toil и отвлекают от реальной работы. Поэтому “ceremony” — это режим, где records, reviews, controls или gates продолжают требовать человеко-время, но перестают менять claim state, authority, publication, rerun или closeout. fileciteturn17file0L3-L3 citeturn13view1turn13view2turn13view3turn30view0

| Сигнал | Желтая зона | Красная зона | Реакция по умолчанию |
| --- | --- | --- | --- |
| Repeated empty records | >10% mandatory records в run пусты или boilerplate-only | >20% mandatory records пусты **или** одна и та же family пустая 3 consecutive runs | Merge, retire, authority-gate up или convert to summary |
| Warnings with no owner | Warning создан без owner, но исправлен в течение суток | Любой warning пережил TTL без owner | Immediate self-FMEA; governed/production closeout cap или block |
| Controls never affect decisions | 0 material deltas в 10 eligible runs | 0 material deltas в 20 eligible runs | Remove, convert to monitor-only or redesign |
| Reviews with no deltas | <20% reviews меняют evidence, scope, limitation, routing или claim state | <10% таких reviews на окне 20 runs **и** review text шаблонен/несодержателен | Collapse reviewer layer, reduce reviewers, assign named accountable reviewer |
| Gates always waived | >20% waivers в research/governed | >30% waivers в research/governed **или** >10% в production | Redesign or retire gate |
| False-block rate | Single rolling window above authority target | Two windows above target **или** severe block incident | Refit criteria before retaining gate |
| Waiting dominates cycle time | Reviewer waits >40% elapsed time | >50% два цикла подряд | Parallelize, cut reviewers, simplify package |

Здесь **material delta** нужно считать строго: это изменение admissibility state, authority ceiling, public limitation, rerun outcome, accepted deficit, dispute status, closeout status или набора decisive evidence refs. Простое “посмотрел и согласился” без изменения объекта не считается положительным сигналом эффективности review само по себе. Исключение — controls и gates, которые адресуют **редкие, но катастрофические** failure modes или юридически обязательны; для них отсутствие срабатываний само по себе не делает механизм церемониальным, но все равно требует периодической design review и доказательства, что control действительно защищает от low-frequency/high-severity risk, а не просто существует по инерции. fileciteturn17file0L3-L3 citeturn26view3turn26view4turn12view0

TTL должен следовать внутренней C1-политике по классу soft gate, а не быть единым числом на все случаи. Citation/publication warnings должны triage’иться в день появления, эскалироваться через 7 дней и жестко эскалироваться через 14; transport/proof degradations требуют immediate triage в governed/production и более мягкого окна в research; projection/source-truth mismatches не имеют grace period. Поэтому backlog нужно считать именно как **warnings older than class-specific TTL**, а не просто как “все warnings в системе”. fileciteturn20file0L3-L3

## Как сложность становится self-FMEA и влияет на closeout

Внутренний C24 совершенно справедливо рассматривает complexity risk как **machinery-level failure**, а не как доменную “слабость доказательств”. Если PDC перегружен control layers, reviewer queues, rework loops или ritual records, это failure mode самой assurance machinery. Внутренний C24 уже предлагает machinery-FMEA record с fields вроде failure mode id, machinery surface, authority level, containment state, review owner, expiry, override policy, false-block candidate и ceremony cost estimate. Следовательно, C32 должен не изобретать новый процесс, а добавить типизированные complexity failure modes в уже задуманную self-FMEA схему. fileciteturn17file0L3-L3

Рекомендуемый минимальный набор failure modes для C32 такой: `complexity_over_budget`, `reviewer_bottleneck`, `non_actionable_gate`, `perpetual_waiver`, `warning_orphaning`, `rerun_spiral`, `artifact_bloat`, `projection_pack_inflation`. Severity надо считать по requested authority level: одинаковый церемониальный review loop в research — это throughput risk; в governed — governance distortion; в production — риск illegitimate or delayed authoritative decision. Occurrence нужно брать из rolling telemetry по similar runs, а detectability — из того, насколько явны метрики и owners. Это соответствует и FMEA-логике C24, и внешней практике объективного toil measurement вместо интуитивных жалоб на “слишком много процесса”. fileciteturn17file0L3-L3 citeturn30view0

| Complexity state | Триггер | Эффект на closeout |
| --- | --- | --- |
| `complexity_watch` | 1 yellow ceremony signal **или** 1 amber budget metric | Annotate only; closeout допустим |
| `complexity_capped` | 2 yellow signals, 1 red-ish budget breach, либо `RPN 25–39` | Closeout cap: public/recommendation ceiling ниже requested authority; mitigation plan обязателен |
| `complexity_blocked` | Любой hard-fail trigger, red ceremony signal, либо `RPN >= 40` | Governed/production closeout blocked до simplification or approved redesign |

Такой state должен читаться единым closeout substrate рядом с `performance_budget.within_policy()`, `phase_barriers.closed()`, `source_truth.no_conflicts()` и `semantic_binding.closed()`. То есть итоговая функция `can_i_closeout(run_id)` должна проверять не только “достаточно ли доказательств”, но и “не превратилась ли сама machinery в источник illegitimate blocking, false precision или authority laundering”. Но важнейшая симметрия такая: complexity block **не может** легитимировать падение ниже minimum floor. Если уменьшение сложности убирает authority floor, decisive conflict handling или minimum verification coverage, это уже не simplification, а under-assurance. fileciteturn20file0L3-L3 fileciteturn17file0L3-L3 citeturn26view5turn26view6turn26view7

## Правило классификации готового PDC

Итоговое решение для acceptance лучше делать не бинарным, а четырехсостоянийным. Это прямо соответствует формулировке задачи C32: нужно уметь различать **слишком тяжелый**, **церемониальный**, **соразмерный** и, дополнительно, **недостаточно обеспеченный** PDC. Внутренний framework уже требует сравнивать complexity budget с риском under-assurance, а внешние risk-based frameworks показывают, что повышение burden без роста decision value столь же вредно, как и избыточная экономия на проверках. fileciteturn17file0L3-L3 citeturn12view0turn12view1turn30view0

| Итоговый класс | Критерии | Действие по умолчанию |
| --- | --- | --- |
| **Соразмерный** | Minimum floor выполнен; red ceremony signals нет; hard-fail trigger нет; budget caps не нарушены; для обязательных items `Net-MAV > 0` или есть явная legal/safety necessity | Requested authority closeout допустим |
| **Слишком тяжелый** | Floor выполнен; controls decision-coupled; но >1 amber metric, либо cap breach без явной ceremony; package сложно поддерживать, но value есть | Не удалять бездумно; modularize, scope-down, defer to lifecycle, reduce reviewer fan-out |
| **Церемониальный** | Есть red ceremony signal, sustained zero-delta controls/reviews, perpetual waivers, orphan warnings, inflated artifact size без decision deltas | Retire, merge, redesign or authority-gate upward; closeout cap/block до исправления |
| **Недостаточно обеспеченный** | Budget соблюден или даже “легкий”, но проседает minimum floor: missing decisive evidence, authority gaps, unresolved conflicts, source-truth/semantic-binding gap, missing minimum verification coverage | Добавить assurance, even if complexity rises |

На практике decision test для любого item должен идти в таком порядке. Сначала **floor test**: сломает ли removal minimum floor. Затем **decision-change test**: менял ли этот item admissibility, authority, limitation, rerun или closeout хотя бы на релевантном окне similar runs, либо защищает ли он от low-frequency/high-severity failure. Затем **Net-MAV test**: дает ли он положительное чистое снижение residual decision loss. И только потом **ownership/latency test**: есть ли owner, TTL и приемлемый human burden. Если item проходит floor, но проваливает остальное, он не “ненужный” — он **плохо собран**. Если item не проходит даже decision-change и Net-MAV tests, он церемониален. Если item нужен по floor, но выталкивает кейс за budget, кейс слишком тяжелый и требует redesign, а не механического удаления. fileciteturn17file0L3-L3 fileciteturn20file0L3-L3 citeturn32view0turn26view3turn30view0

В таком виде acceptance для C32 становится проверяемым: **полный PDC можно формально признать чрезмерно тяжелым, церемониальным или соразмерным для запрошенного authority level по явным метрикам, порогам, MAV-логике, rubric signals и closeout effects**, не скатываясь ни в “больше форм — значит лучше”, ни в “экономим все, что можно”. fileciteturn17file0L3-L3


# Алгебра долга capability для PolicyOS

Этот синтез исходит не из «чистого листа», а из уже существующей рамки PolicyOS. Внутренние документы и кодовые якоря уже фиксируют, что capability нельзя считать реальной только потому, что есть контракт или схема: для статуса «реально существует» должна быть собрана цепочка `typed contract/artifact -> producer -> persisted artifact/event -> orchestration bridge -> consumer -> verification -> external surface or explicit out_of_scope -> semantic/e2e test`. Тот же корпус прямо описывает PolicyOS как систему с сильными внутренними kernels, но с повторяющейся слабостью в мостах, оркестрации и typed external surfaces. Значит, задача C36 состоит не в том, чтобы придумать новую степень зрелости, а в том, чтобы превратить уже различаемые системой разрывы в сопоставимый и управляемый долг. fileciteturn3file0L3-L3 fileciteturn6file0L3-L3 fileciteturn8file0L3-L3

## Опорная рамка PolicyOS

В самом репозитории уже есть почти все элементы, на которые должна опираться алгебра. Во внутреннем failure-pattern register capability reality check перечислены именно те состояния, которые пользователь просит для C36: `contract_only`, `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`, `verification_missing`, `implemented_but_not_orchestrated`, `surface_missing`, `surface_out_of_scope`, `semantic_test_missing`, а также паттерны `compatibility_shim` и `projection_only` как особые формы риска. Этот же документ явно запрещает считать capability реализованной, если отсутствует любой элемент цепочки или если нет semantic-level proof of adequacy. Отдельно сказано, что `semantic_test_missing` capability не может «выпуститься» в `implemented`. fileciteturn6file0L3-L3

Pattern register P01–P15 делает важное различие между разными типами неполноты. P01 фиксирует «contract-only capability» как самостоятельный анти-паттерн; P02 — тонкую оркестрацию при богатых компонентах; P03 — бедность внешней поверхности при богатом внутреннем состоянии; P04 и P09 — смешение статусов и неуправляемые soft gates; P05 и P15 — размывание authority через projections и LLM-кандидатов; P14 — ложное усиление доказательств сырым подсчётом источников. Это означает, что C36 действительно не должен сводить всё к общему «не готово»: разные дефициты ломают систему разными механизмами и по-разному влияют на релизный риск. fileciteturn6file0L3-L3

Scorecard, honest diagnostics и closeout-compatibility уже задают fail-closed поведение, на которое алгебра должна замыкаться. Для серьёзных профилей (`research`, `governed`, `production`) scorecard не разрешает `quality_status: pass`, если отсутствуют runtime-owned refs; honest diagnostics прямо разделяет runtime truth и projections и запрещает scorecard, readiness, dashboard или export «дочеканивать» отсутствующую authority truth; compatibility record строит producer-reader matrix и превращает несовместимость в readiness blockers; wave-40 readiness validator требует `passes_all=true`, ноль serious closeout failures и ноль component failures. Значит, C36 должен не подменять эти механизмы, а давать им общую метрику сравнения и приоритизации. fileciteturn16file0L3-L3 fileciteturn19file0L3-L3 fileciteturn24file0L3-L3 fileciteturn25file0L3-L3 fileciteturn27file0L3-L3 fileciteturn26file0L3-L3

Наконец, репозиторий уже содержит governance substrate для ratchet policy. Quality gates описывают локальные, CI- и release-gates, а ratchet policy требует для новых surfaces явного owner, docs entry point, test strategy, compatibility stance, ops/rollout impact и управляемых исключений. Иными словами, PolicyOS уже мыслит долг как управляемое отклонение с владельцем, сроком и проверкой, а не как «потом доделаем». C36 должен встроиться именно в эту модель. fileciteturn17file0L3-L3 fileciteturn18file0L3-L3

## Что добавляет внешнее исследование

Внешняя литература даёт три полезные коррекции к внутренней рамке. Первая — debt надо понимать не как моральное осуждение качества, а как управленческую метафору principal и interest. У Мартина Фаулера extra effort на будущие изменения — это «interest», а paydown principal имеет смысл там, где код и архитектура часто трогаются; он же предлагает различать долг `prudent`/`reckless` и `deliberate`/`inadvertent`, а не пытаться делить мир на «настоящий долг» и «не долг». Это прямо поддерживает различие между planned debt, accepted debt и блокирующим debt в PolicyOS. citeturn17view1turn17view0

Вторая коррекция — архитектурный и orchestration debt действительно ведут себя не как локальные дефекты, а как системный тормоз эволюции. В longitudinal study по architectural debt он измерялся и через количество, и через severity архитектурных flaws, а его paydown дал измеримые улучшения в maintainability и changeability. Более новые работы по ATD principal и repayment effort показывают, что разные типы долга требуют разного усилия на погашение; единый bucket искажает приоритизацию, потому что requirement/design/test debt и подобные классы repayятся по-разному. Для C36 это важный аргумент в пользу typed debt units и purpose-weighted severity, а не одного общего счётчика «сколько осталось недоделок». citeturn14academia0turn20academia1turn20academia3

Третья коррекция — нельзя полагаться на наивную heatmap-логику, где порядок рисков получается из произвольного перемножения ordinal levels. Сводки по Cox и последующей критике risk matrices показывают poor resolution, arbitrary rankings и проблемы с resource allocation, когда qualitative bins трактуются как будто это точные количественные шкалы. Для C36 из этого следует практический вывод: матрица release/readiness может быть полезной как decision view, но основой должна быть не «вероятность × тяжесть», а комбинация fail-closed predicates, calibrated debt points и graph-aware count thresholds. citeturn13search0turn12academia1

От assurance-case literature полезно взять ещё одну мысль. Assurance case — это structured argument, где claims поддерживаются arguments и evidence; assurance weakeners обычно выражаются как недостаток evidence, knowledge или reasoning gaps, которые подрывают confidence даже при видимой структурной завершённости. Для PolicyOS это особенно важно, потому что `projection_only`, `compatibility_shim`, `verification_missing` и `semantic_test_missing` опасны не только отсутствием functionality, но и возможностью создать semantic false pass — видимость закрытого кейса без настоящей authority truth. citeturn19academia1turn19academia3

Наконец, практики release-governance снаружи хорошо усиливают внутреннюю логику PolicyOS. Google SRE описывает error-budget policy, где при превышении error budget изменения и релизы, кроме P0/security fixes, останавливаются, а крупный single incident обязан вести к postmortem и P0 action item. NIST RMF, в свою очередь, описывает risk management как disciplined, structured, flexible process с continuous monitoring, ongoing authorization и явной связкой между system-level и organization-level accountability. Для C36 это означает: accepted debt допустим только там, где есть owner, наблюдаемость, срок пересмотра и понятный trigger для freeze или remediation. citeturn8view0turn9view3turn8view1

## Предлагаемая алгебра единиц долга

Предлагаемая алгебра должна считать не «степень незавершённости вообще», а **типизированный principal** по capability. Каждая запись долга должна быть отдельным объектом вида:

```text
CapabilityDebtRecord {
  capability_id
  reality_state
  purpose
  authority_scope
  local_points
  local_severity
  blocker_predicate
  debt_class
  owner
  expiry
  burn_down_signals[]
  mitigation_refs[]
}
```

Такой record прямо продолжает репозиторную логику ownership, gates, runtime evidence и closeout semantics. fileciteturn17file0L3-L3 fileciteturn18file0L3-L3 fileciteturn24file0L3-L3

Ниже — **предлагаемые** базовые значения principal по состояниям. Это управленческие points для приоритизации, а не вероятностная оценка инцидента; именно поэтому они используются вместе с blocker predicates и chain rules, а не вместо них. Такая оговорка важна, чтобы не повторить ошибки наивных risk matrices. citeturn13search0

| Reality state | Алгебраический смысл | Базовые points | Автоэскалация |
| --- | --- | ---: | --- |
| `surface_out_of_scope` | Осознанное отсутствие внешней поверхности | 0 | Если нет rationale, owner, review date или inspection path — переходит в `surface_missing` |
| `compatibility_shim` | Временная совместимость, удерживающая старый путь | 1 | На authority/closeout path без sunset и dual-read verification повышается до blocker |
| `projection_only` | Есть отображение, но нет authority-bearing artifact | 1 | Если projection способен быть ошибочно использован как evidence/approval input — blocker |
| `contract_only` | Есть форма, но нет живого capability chain | 2 | На authority/closeout/lifecycle critical path быстро эскалирует |
| `consumer_missing` | Что-то производится, но никто не читает и не действует | 2 | На closeout/public/reviewer paths минимум High |
| `surface_missing` | Внутри capability есть, снаружи она не наблюдаема | 2 | Если поверхность обещана, нужна оператору или аудитору — blocker |
| `producer_missing` | Потребитель ожидает capability, но producer не эмитит её | 3 | На evidence/authority paths — blocker |
| `artifact_missing` | Логика есть, но нет persisted/queryable/replayable artifact | 3 | На closeout/replay/attestation paths — blocker |
| `bridge_missing` | Producer и consumer есть, но нет связующей оркестрации | 4 | На authority/closeout paths — blocker |
| `implemented_but_not_orchestrated` | Компонент работает локально, но не встроен в runtime chain | 4 | На lifecycle/approval paths минимум Critical cluster risk |
| `verification_missing` | Цепочка якобы собрана, но end-to-end proof отсутствует | 5 | На serious profiles обычно blocker |
| `semantic_test_missing` | Есть структурные тесты, но нет semantic adequacy proof | 5 | Не может считаться `implemented`; на serious profiles blocker |

Таблица выше опирается на внутреннюю таксономию capability reality и failure patterns, а также на внешние данные о том, что debt principal и repayment effort различаются по типам и severity, а architectural/orchestration flaws влияют на maintainability и evolution сильнее локальных косметических gaps. fileciteturn6file0L3-L3 fileciteturn3file0L3-L3 citeturn14academia0turn20academia1turn20academia3

Далее нужен purpose-weighting. Один и тот же gap по-разному опасен в зависимости от того, для чего capability вообще существует.

| Purpose | Коэффициент purpose |
| --- | ---: |
| `internal_helper` | 0.5 |
| `diagnostic_only` | 0.75 |
| `public_surface` | 1.0 |
| `lifecycle_trigger` | 1.25 |
| `evidence_producer` | 1.5 |
| `closeout_input` | 1.75 |
| `authority_gate` | 2.0 |

Если `diagnostic_only` capability является **единственным** inspection path для оператора или пост-мортема, её нужно поднимать как минимум до коэффициента `1.25`, потому что она перестаёт быть «просто диагностикой» и становится governance-critical view. Это согласуется и с внутренним honest diagnostics substrate, и с внешней практикой continuous monitoring и release freeze по error budget. fileciteturn19file0L3-L3 citeturn8view0turn9view3

Формула локального долга capability может быть такой:

```text
local_points =
  base_state_points * purpose_factor
  + serious_profile_premium
  + sole_path_premium
  + ownerless_or_expired_premium
  + chain_cluster_premium
  - mitigation_credit
```

Где `serious_profile_premium = +1` для `research/governed/production`, `sole_path_premium = +1`, `ownerless_or_expired_premium = +1`, а `mitigation_credit = -1` разрешён только если mitigation реально наблюдаем и consumer-side enforced. Это не «объективная вероятность сбоев», а калиброванный decision score; решение о релизе принимает комбинация `blocker_predicate + thresholds + score`, а не одна сумма сама по себе. fileciteturn16file0L3-L3 fileciteturn19file0L3-L3 citeturn13search0

Из `local_points` удобно получать bands: `0 = none/waived`, `>0–<2 = low`, `2–4 = medium`, `>4–7 = high`, `>7 = critical`. Для глобальной приоритизации релизного scope полезно считать `AuthorityWeightedDebt` как сумму `local_points` по всем capabilities, которые лежат на путях `evidence -> claim binding -> authority gate -> closeout -> projection`. Именно такой путь PolicyOS и так пытается валидировать через scorecards, closeout compatibility и wave-40/41 readiness. fileciteturn8file0L3-L3 fileciteturn24file0L3-L3 fileciteturn27file0L3-L3

## Правила агрегации и границы допустимости

Чтобы C36 действительно различал неполноту, а не превращал всё в один score, aggregation rules лучше сформулировать как набор независимых правил.

| Правило | Как считать | Зачем это нужно |
| --- | --- | --- |
| `max_severity` | Максимальный band по capability и по цепочке не усредняется | Один critical gap на authority path нельзя «размазать» десятком low gaps |
| `count_thresholds` | `3 medium+` в одной цепочке повышают её на один band; `2 high` в одной цепочке делают её как минимум critical | Несколько «нестрашных» gaps в одном producer→consumer path дают системный разрыв |
| `authority_weighted_debt` | Сумма `local_points` только по authority-bearing paths | Нужен для сравнения competing debts между capability families |
| `release_blocker` | Boolean predicate поверх states и purposes | PolicyOS уже требует fail-closed, значит blocker должен быть явным |
| `accepted_debt` | Временное разрешение ship-риска без снятия самого debt | Долг остаётся видимым; снимается только запрет на конкретный релиз |
| `planned_debt` | Известный debt с владельцем и burn-down plan, но без права ship по умолчанию | План не равен приемке риска; это только backlog discipline |

Эта логика нужна потому, что PolicyOS уже отделяет local status, closeout authority и projections, а внешняя литература предупреждает, что агрегировать сложные риски одним грубым heatmap небезопасно. fileciteturn16file0L3-L3 fileciteturn19file0L3-L3 citeturn13search0turn19academia3

**Release blocker** в C36 лучше определять жёстко. Для serious profiles debt становится blocker, если выполняется хотя бы одно из условий: `producer_missing`, `artifact_missing`, `bridge_missing`, `verification_missing` или `semantic_test_missing` лежит на `authority_gate` либо `closeout_input`; `projection_only` или `compatibility_shim` оказывается единственным authority-bearing path; `surface_missing` скрывает состояние, обещанное public/reviewer/expert/machine/API/dashboard audience; либо `surface_out_of_scope` заявлен без документации, owner-а и inspection path. Такой fail-closed дизайн уже согласован и с internal scorecard/readiness, и с honest diagnostics. fileciteturn16file0L3-L3 fileciteturn19file0L3-L3 fileciteturn24file0L3-L3

**Accepted debt** допустим только как временное исключение и только там, где нет blocker predicate. Минимальный набор условий для accepted debt: owner, expiry, mitigation evidence, monitoring signal, explicit `may_not_use_for` boundary для projections/shims, и конкретный burn-down trigger. На `authority_gate` и `closeout_input` accepted debt должен быть почти невозможен: здесь правильная реакция обычно blocker или scope downgrade, а не «временная приемка». Это согласуется с NIST-подходом к structured risk management и ongoing monitoring, а также с внутренним ratchet policy, который требует owner-а и expiry для исключений. fileciteturn18file0L3-L3 citeturn9view3turn8view1

**Planned debt** — это более слабый режим. У planned debt должен быть roadmap, но сам по себе он не даёт право ship. Практическое правило здесь такое: всякий accepted debt обязан быть planned, но не всякий planned debt может быть accepted. Иначе backlog начинает скрытно превращаться в канал для релизной амнистии. Этой ловушки PolicyOS уже старается избегать в quality gates и closeout governance. fileciteturn17file0L3-L3 fileciteturn18file0L3-L3

Особое правило нужно для `surface_out_of_scope`. Этот label допустим только тогда, когда отсутствие поверхности **осознанно** выбрано и не маскирует незавершённость. Минимальный тест валидности такой: capability не нужна для promised public/reviewer/operator contract; её отсутствие не ломает closeout, readiness или audit inspection; существует альтернативный runtime inspection path; rationale, owner и review date записаны; negative test подтверждает, что downstream code не предполагает наличие этой поверхности. Если хотя бы одно из этих условий не выполняется, состояние должно автоматически реклассифицироваться в `surface_missing`, а для обещанной или governance-critical поверхности — в blocker. Именно в этом и состоит разница между «нет поверхности по дизайну» и «поверхность не успели доделать». fileciteturn6file0L3-L3 fileciteturn18file0L3-L3 fileciteturn19file0L3-L3

## Сигналы выгорания долга и ratchet policy

Burn-down в C36 должен измеряться не словами и не новой диаграммой, а переходами по capability chain. Если debt зафиксирован как `contract_only`, сигнал погашения — появление реального producer-а; если `producer_missing` или `artifact_missing` — появление persisted/queryable/replayable runtime artifact или event ref; если `bridge_missing` или `implemented_but_not_orchestrated` — появление работающего consumer effect в runtime path; если `consumer_missing` — downstream gate начинает реально читать и действовать; если `verification_missing` — появляется automated end-to-end proof; если `semantic_test_missing` — добавлены content-level adequacy checks; если `surface_missing` — surfaced audience contract либо валидный `surface_out_of_scope`; если `compatibility_shim` — usage старого пути падает к нулю по sunset metric и dual-read evidence. Именно так внутренние документы уже мыслят readiness, diagnostics и compatibility. fileciteturn6file0L3-L3 fileciteturn16file0L3-L3 fileciteturn24file0L3-L3 fileciteturn25file0L3-L3

Для ratchet policy я бы рекомендовал пять жёстких правил.

- Capability не может перейти в более сильное reality-state по словам в PR или dashboard; переход считается валидным только при наличии runtime evidence и соответствующих tests/gates. fileciteturn17file0L3-L3 fileciteturn18file0L3-L3
- Любой accepted debt на serious profile обязан иметь owner, expiry и monitoring trigger; исключение без срока автоматически эскалирует на один band. fileciteturn18file0L3-L3 citeturn9view3
- `compatibility_shim` без sunset date или `projection_only` без consumer-side denial of authority автоматически становятся High, а на authority/closeout path — blocker. fileciteturn6file0L3-L3 fileciteturn19file0L3-L3
- Повторное принятие одного и того же debt два релизных цикла подряд без видимого burn-down должно повышать его минимум на один band, потому что краткосрочный debt превращается в structural debt. Это соответствует debt-as-interest логике и внешним данным о затяжном unresolved ATD. citeturn17view1turn14academia3
- Если aggregate debt budget исчерпан по аналогии с error budget policy, фичевые изменения должны замораживаться до возврата в допустимую зону; исключения — только security/P0/remediation work. Это делает ratchet реальным, а не purely documentary. citeturn8view0

Эти правила хорошо согласуются с внутренней maturity-моделью, где движение к более высоким уровням требует воспроизводимых evidence bundles, scorecards, approval packets и continuous acceptance, а не просто благоприятной интерпретации локальных статусов. fileciteturn22file0L3-L3

## Матрица риска release/readiness и проверочные сценарии

Ниже — decision matrix для **serious profiles**. Для `dev` и части `staging` один band можно смягчать до warning-only, но только не там, где речь идёт об authority spoofing, projection laundering, tenant conflicts, attestation gaps или closeout truth. Внутренние документы уже проводят именно такое различие между серьёзными и несерьёзными профилями. fileciteturn16file0L3-L3 fileciteturn19file0L3-L3 fileciteturn22file0L3-L3

| Зона | Условия | Состояние readiness | Решение по релизу |
| --- | --- | --- | --- |
| **Зелёная** | `max_severity <= medium`, blocker predicates не сработали, `AuthorityWeightedDebt < 12`, нет chain promotion | Ready | closeout/release допустим |
| **Жёлтая** | один `high` только вне authority/closeout path, либо `AuthorityWeightedDebt = 12–20`, все долги planned/accepted с owner и expiry | Conditionally ready | допустимо только с явным acceptance record; для governed/production — как исключение |
| **Оранжевая** | сработал cluster rule (`3 medium+` или `2 high` в одной цепочке), либо `AuthorityWeightedDebt = 20–30` без жёсткого blocker | Not ready | remediation до closeout; наружный релиз не выпускать |
| **Красная** | любой blocker predicate, projection/shim laundering, или `AuthorityWeightedDebt > 30` | Blocked | freeze релиза; разрешены только remediation/security/P0 changes |

Эта матрица — именно decision view, а не попытка probabilistic risk quantification; поэтому она строится сверху на typed deficits, fail-closed predicates и cluster thresholds, а не на грубом перемножении ordinal axes. citeturn13search0turn8view0turn9view3

Проверочный сценарий, где **несколько средних долгов дают высокий релизный риск**, выглядит так. Допустим, у нас есть `contract_only` для evidence producer-а, который должен поддерживать claim; `consumer_missing` для closeout input, который должен читать этот producer output; и `surface_missing` для reviewer/expert surface, через который этот claim должен быть проверяем. По предлагаемой шкале это примерно `2×1.5 + 1 = 4.0`, `2×1.75 + 1 = 4.5` и `2×1.0 + 1 = 3.0`. По отдельности это похоже на «неприятно, но не катастрофа». Но все три долга сидят в одной цепочке `producer -> claim binding -> reviewer visibility`, поэтому срабатывает cluster premium и цепочка переходит в красную зону: система знает, какой evidence ей нужен, но не умеет ни замкнуть его в authority path, ни сделать его наблюдаемым снаружи. Именно такие assurance gaps литература описывает как weakeners, подрывающие confidence без одного явного «фатального» дефекта. fileciteturn6file0L3-L3 fileciteturn19file0L3-L3 citeturn19academia3turn14academia0

Второй сценарий показывает, почему `compatibility_shim` и `projection_only` опасны даже при маленьком nominal principal. Пусть authority gate всё ещё сидит на `compatibility_shim`, dashboard/approval packet содержит только `projection_only` representation, а для semantic closure отсутствует content-level proof. Базовый долг shim и projection маленький, но внутренние firewalls прямо запрещают делать их источником truth: projection не может заместить runtime evidence, а shim без verified producer-reader compatibility не должен скрывать несовместимость. В такой конфигурации маленькие nominal debts дают не просто medium risk, а **false-pass risk**, поэтому состояние должно считаться blocker, даже если суммарные points выглядели бы умеренно. fileciteturn3file0L3-L3 fileciteturn19file0L3-L3 fileciteturn24file0L3-L3

Третий сценарий нужен, чтобы показать, что C36 не превращает любой gap в generic «not done». Если capability является `internal_helper`, для неё есть runtime inspection path, внешняя surface никогда не обещалась, есть owner, rationale и дата ревью, а downstream code не зависит от этой поверхности, тогда корректная классификация — `surface_out_of_scope` с нулевым principal, а не blocker. Но если позже появляется docs claim, runbook, API expectation или reviewer contract, тот же самый gap должен немедленно реклассифицироваться в `surface_missing`. Это и есть главная практическая ценность алгебры: она различает «нет по дизайну», «нет пока» и «нет там, где уже нельзя выпускать». fileciteturn6file0L3-L3 fileciteturn17file0L3-L3 fileciteturn18file0L3-L3

В таком виде C36 выполняет своё acceptance condition: неполные capability claims становятся сравнимыми и приоритизируемыми без потери смысла. `contract_only` больше не равен `verification_missing`; `surface_out_of_scope` больше не путается с `surface_missing`; `compatibility_shim` и `projection_only` не выглядят «почти готово», если они искажают authority path; а несколько low/medium debts на одной цепочке перестают маскироваться под безопасный backlog и становятся видимым release/readiness risk. fileciteturn3file0L3-L3 fileciteturn6file0L3-L3 fileciteturn27file0L3-L3 citeturn17view0turn19academia3turn13search0


# Семантика авторитетности orchestration bridge в PolicyOS

## Исходная рамка задачи

Внутри самого framework задача C37 уже поставлена очень узко и не как «общая теория логов», а как решение конкретной границы: когда orchestration bridge может быть authority-bearing evidence, а когда он является только transport или diagnostic metadata. В кодо- и плано-ориентированной постановке C37 прямо названы якоря, от которых нельзя отрываться: `evidence_spine`, `evidence_spine_handoff`, producer handshake, semantic binding, claim registry, authority envelopes, CAS writes, canary bundle assembly, replay, inspection, readiness и public export surfaces. Acceptance-критерий тоже уже зафиксирован: orchestration records допустимы для closeout только там, где их authority role эксплицитен и не смешивается с producer evidence. fileciteturn13file0L3-L3

Консолидация исследований и активный research plan дополнительно фиксируют четыре рамочных свойства, без которых C37 нельзя решать корректно. Во-первых, PolicyOS не является blank slate: в системе уже есть authority envelopes, claim-bound registry, projection guardrails, closeout-совместимость и evidence-spine bridge-слой. Во-вторых, повторяющийся системный дефект описан как *component-rich, bridge-thin architecture*: сильные producer-модули уже есть, но между ними не хватает общей spine- и bridge-семантики. В-третьих, projection surfaces не могут mint authority. В-четвёртых, closeout должен опираться на единый honest-diagnostics substrate, а не на случайные локальные `pass`-флаги. fileciteturn3file0L3-L3fileciteturn8file0L3-L3fileciteturn36file0L3-L3

Это уже сильно ограничивает допустимый ответ по C37: «bridge = proof» как дефолтный режим не совместим с действующей архитектурой PolicyOS. В системе уже зафиксировано, что public/dashboard/API projections не mint authority, packaging evidence не равно producer authority, а serious closeout обязан проверять exact producer/reader/authority combination и same-input closure. Следовательно, bridge по умолчанию должен считаться **не producer evidence**, а отдельным слоем доказательств о переносе, связности, маршруте и в некоторых случаях — о проверенном boundary event. fileciteturn14file0L3-L3fileciteturn15file0L3-L3fileciteturn22file0L3-L3fileciteturn34file0L3-L3

## Нормативный принцип для C37

Лучший внешний аналог для `evidence_spine` и `handoff` — это не «документ-доказательство», а стандартизированный provenance-and-tracing carrier. W3C PROV-DM определяет provenance как информацию об entities, activities и agents, которая помогает оценивать качество, надёжность и trustworthiness, и специально различает сущности, активности, ответственность, derivation и bundles как provenance of provenance. Это даёт хороший conceptual baseline: bridge может быть хорошим доказательством о происхождении, передаче и отношениях между артефактами, не становясь автоматически доказательством предметной истинности содержания. citeturn1view0

OpenTelemetry и W3C Trace Context ещё сильнее подталкивают к этому выводу. Context propagation определён как механизм, который *moves context between services and processes* и сериализует/десериализует context object для передачи между сервисами. То есть transport-carrier по дизайну существует ради переноса контекста и корреляции, а не ради semantic attestation. Более того, OTel baggage прямо предупреждает, что baggage может распространяться к unintended resources и что у baggage **нет built-in integrity checks**; значит, carrier сам по себе не должен считаться authoritative. W3C Trace Context тоже описывает `traceparent`/`tracestate` как стандарт передачи trace context между сервисами для distributed tracing, а не как криптографически доверенное доказательство предметного вывода. citeturn9view6turn12view0turn12view1turn12view2turn11view0

В то же время supply-chain attestation стандарты показывают, когда bridge-подобный record уже может стать authority-bearing. SLSA provenance определяет provenance как **attestation**, что конкретная build platform произвела набор artifacts через выполнение `buildDefinition`; при этом внешние параметры должны быть включены в provenance и verified downstream, а control-plane communication само по себе не считается напрямую captured provenance, если только оно не отражено как dependency. in-toto аналогично описывает модель, где integrity обеспечивается прозрачностью того, какие шаги были выполнены, кем и в каком порядке. Это очень сильная аналогия для PolicyOS: bridge становится authority-bearing не потому, что он «есть», а потому что он является **attested, scoped, downstream-verified record**, привязанным к конкретному subject/artifact и проверяемому reader contract. citeturn2view6turn9view2turn12view5turn12view6turn10view0turn10view1

OpenLineage полезен как граничный пример между runtime-фактами и design-time metadata. Его `RunEvent` описывает исполнение job at runtime, тогда как `JobEvent` и `DatasetEvent` — это design-time metadata и они **not associated with a Run**. Для C37 отсюда следует очень практичное правило: если bridge record не привязан к конкретному run/input/output/reader boundary, он максимум design-time or diagnostic metadata; если привязан, он может доказывать boundary event, но всё равно не заменяет producer artifact и его content-level validation. citeturn9view3turn9view4turn9view5

Внутренние PolicyOS-модули уже формулируют почти такую же границу. `EvidenceSpineCarrier` несёт `scenario_evidence_contract_id`, `requirement_ids`, `producer_component`, `reader_contract`, `authority_profile`, `input_refs`, `output_refs` и redaction policy; `EvidenceSpineHandoff` фиксирует boundary crossing с `parent_spine_ref`, `input_refs`, `output_refs`, `carrier_ref`, redaction/integrity status и обязательными handoff kinds. Но authority-модель PolicyOS отдельно требует authority envelope, same-input closure, runtime event, CAS identity, schema/reader compatibility и запрещает projection-only, packaging-only и borrowed envelopes как источник серьёзной authority. Следовательно, bridge должен трактоваться как **контекстно-связующее доказательство**, а не как самостоятельный authority-bearing producer fact, пока не выполнены дополнительные envelope и verification conditions. fileciteturn16file0L3-L3fileciteturn19file0L3-L3fileciteturn20file0L3-L3fileciteturn22file0L3-L3fileciteturn23file0L3-L3

## Таблица решений по авторитетности bridge records

Ниже — предлагаемая decision table для C37. Это синтез внутренних PolicyOS-контрактов, honest-diagnostics substrate, authority envelopes, evidence-spine/handoff кода и внешних provenance/attestation стандартов. fileciteturn13file0L3-L3fileciteturn15file0L3-L3fileciteturn16file0L3-L3fileciteturn19file0L3-L3fileciteturn22file0L3-L3citeturn1view0turn9view6turn2view6turn9view3

| Класс bridge-артефакта | Что это такое | Что он может доказывать | Чего он не может доказывать | Closeout-статус по умолчанию |
|---|---|---|---|---|
| **Transport carrier** | Перенос `contract_id`, `requirement_ids`, `trace_id`, `input/output refs` между сервисами | Что некоторый context был передан, и что boundary имел carrier | Что producer реально **понял**, **использовал** или **корректно интерпретировал** requirement | **Нет**, только diagnostic/transport, пока нет attested producer/reader record |
| **Handoff ledger** | Запись о переходе async/batch boundary: producer, consumer, parent spine, input/output refs, integrity/redaction | Causality at boundary, existence of handoff, path continuity, missing boundary | Предметную корректность producer output, claim support, method validity | **Условно**, только как closeout evidence о boundary completeness/integrity |
| **Binding assertion** | Typed disposition по requirement: selected/rejected/blocked/failed + refs | Что producer **заявил** конкретную disposition по obligation | Что эта disposition валидна без producer artifact и reader validation | **Условно**, только если assertion producer-owned, envelope-backed и reader-checkable |
| **Producer attestation** | Runtime-owned, CAS-backed, same-input-closed bridge record, выпущенный producer | Что producer consumed requirement, emitted binding, preserved artifact identity, либо blocked законно | Что downstream reader принял это без отдельной reader attestation | **Да**, если envelope и compatibility проходят |
| **Reader attestation** | Gate/readiness/inspection/semantic-binding record о том, что consumer проверил artifact под конкретным contract/version | Что конкретный reader verified/blocked artifact при данной версии contract/gate | Что producer content сам по себе истинен или достаточен без underlying artifact | **Да**, но только как reader/closeout evidence, не как domain evidence |
| **Diagnostic projection** | Dashboard/API/public/export/projection surface | Что на поверхности отображено состояние/label/summary | Любую authority over claim, scorecard, closeout или producer evidence | **Никогда**, projection-only |
| **Closeout evidence** | `can_i_closeout`, inspection, readiness, compatibility record | Что closeout/substrate verdict был достигнут под конкретным schema/reader/code combination | Что policy claim предметно верен без producer evidence beneath it | **Да**, но только для closure/compatibility, не для domain truth |

Ключевой rule-of-thumb для всей таблицы такой: **bridge record authoritative only about the boundary it owns**. Он не наследует авторитет содержательного producer artifact автоматически и не может «перевести» diagnostic transport в claim evidence. Если нужно доказать предметный факт, нужен producer artifact; если нужно доказать, что artifact был проверен, нужен reader attestation; если нужно доказать общий verdict о выпуске, нужен closeout record. fileciteturn14file0L3-L3fileciteturn15file0L3-L3fileciteturn26file0L3-L3fileciteturn34file0L3-L3

## Таксономия handoff evidence

Для C37 полезно разделить handoff evidence не только по месту в pipeline, но и по **видимости authority**. PolicyOS-код уже помогает это сделать: `EvidenceSpineCarrier` занимается propagation, `EvidenceSpineHandoff` — async boundary bookkeeping, `claim_registry` — claim-bound evidence binding, `authority.py` — envelope semantics, а `projection_semantics.py` жёстко запрещает projection mint authority. fileciteturn16file0L3-L3fileciteturn19file0L3-L3fileciteturn27file0L3-L3fileciteturn22file0L3-L3fileciteturn26file0L3-L3

| Таксон | Носитель | Кто его «владеет» | Основная функция | Допустимое доказательное использование |
|---|---|---|---|---|
| **Carrier evidence** | `EvidenceSpineCarrier` | Orchestration/runtime boundary | Propagation of IDs and refs | Requirement propagation, correlation, initial causality |
| **Boundary evidence** | `EvidenceSpineHandoff` | Boundary owner | Recording async/batch crossing | Handoff completeness, path continuity, missing-link detection |
| **Disposition evidence** | `EvidenceRequirementBinding` | Producer | Typed satisfied/blocked/rejected statement | Producer-declared obligation handling |
| **Identity-preservation evidence** | Envelope + `same_input_closure` + matching refs | Runtime authority | Same-run / same-input closure | Same-input closure and identity continuity |
| **Verification evidence** | Inspection, semantic binding, readiness, compatibility | Reader/gate owner | Reader-side validation under contract version | Closeout and gate verdicts |
| **Projection evidence** | Dashboard/API/public export | Projection owner | Rendering and explanation | Operator/public understanding only |
| **Anti-authority evidence** | Borrowed/mismatched/stale/redaction-failed bridge | Runtime diagnostics | Detecting laundering or loss of authority | Typed blocker or integrity incident |

Из этой таксономии следует важный design rule: **handoff evidence лучше читать как typed evidence of orchestration state, а не как substitute for producer semantics**. Иными словами, bridge record может поддерживать causality, provenance, same-input continuity и obligation propagation, но content-уровневая admissibility остаётся у producer/reader pair, а не у bridge itself. Это согласуется и с PROV-DM, и с OpenTelemetry, и с OpenLineage distinction между runtime run observations и design-time metadata. citeturn1view0turn9view6turn9view3turn9view4

## Условия, при которых bridge record может стать closeout input

PolicyOS уже задаёт почти полный набор минимальных требований. Для серьёзного профиля authority-bearing envelope должен проходить: `evidence_class=authority_bearing`; authority role не должен быть projection/packaging/diagnostic-only; для serious profiles provenance должен быть `runtime_emitted` или `runtime_blocker`; runtime-emitted evidence должно быть CAS-backed, с `artifact_ref == cas_ref`, а `cas_ref` должно входить в `output_refs`; same-input closure должен быть `closed` и консистентен по `run_id`, `job_id`, `tenant_id`; envelope должен нести schema identity, reader contract/version, runtime event ref и governance metadata. Отдельно handoff ledger требует `parent_spine_ref`, `carrier_ref`, `input_refs`, `output_refs`, redaction pass, integrity pass и producer/consumer mismatch check. fileciteturn22file0L3-L3fileciteturn23file0L3-L3fileciteturn19file0L3-L3fileciteturn20file0L3-L3

Из этого следует строгий C37-rule: **bridge record может стать closeout input только если он attested, scope-bound и reader-verifiable**. В практическом PolicyOS-виде это значит не «любой handoff JSON», а bridge record, у которого есть:  
1) runtime-owned emitter;  
2) immutable or CAS-addressed artifact identity;  
3) explicit authority envelope;  
4) same-input closure;  
5) schema/reader compatibility;  
6) redaction and integrity success;  
7) понятный authority purpose, ограниченный boundary, а не domain truth. fileciteturn15file0L3-L3fileciteturn34file0L3-L3fileciteturn36file0L3-L3

Поэтому для C37 я бы зафиксировал простое нормативное разграничение. **Carrier** и **handoff ledger** без envelope — это diagnostic-supporting evidence. **Binding assertion** без envelope и reader-check — это producer declaration, но ещё не closeout-grade fact. **Producer attestation** и **reader attestation** могут быть closeout-grade, если проходят envelope and compatibility checks. **Projection artifacts** никогда не могут перейти эту границу, даже если внешне выглядят богаче, чем underlying producer record. fileciteturn26file0L3-L3fileciteturn34file0L3-L3

## Асинхронные handoff-примеры для NL request, lease, workflow, CAS, bundle, replay, inspection, readiness и export

Ниже — practical matrix именно по тем async boundaries, которые C37 требует протестировать. Она опирается на текущие PolicyOS handoff kinds, validator logic и projection/closeout boundaries. `EvidenceSpineHandoff` уже перечисляет `nl_request_creation`, `control_plane_job_lease`, `workflow_state_persistence`, `cas_artifact_write`, `canary_bundle_assembly`, `replay_result`, `inspection_result`, `readiness_result`, `public_export_projection`, `dashboard_api_export`; validator делает отсутствие required handoff kinds и отсутствие refs fail-closed. Unit tests дополнительно подтверждают, что handoff ledger должен связывать job progress с CAS bundle and readiness, а redaction/integrity failures считаются ошибками. fileciteturn19file0L3-L3fileciteturn20file0L3-L3fileciteturn28file0L3-L3fileciteturn30file0L3-L3

| Async boundary | Что bridge может доказать | Authority status |
|---|---|---|
| **NL request creation** | Что исходный request получил `scenario_evidence_contract_id`, `requirement_ids` и первоначальный spine context | Transport + causal evidence only |
| **Control-plane job lease** | Что control plane передал job конкретному worker и сохранил continuity of refs | Handoff evidence only |
| **Workflow state persistence** | Что pipeline persisted state/output refs и не потерял requirement lineage на boundary persistence | Boundary evidence; closeout-relevant только для continuity |
| **CAS artifact write** | Что конкретный runtime-owned artifact был записан в CAS и связан с output refs; при envelope может стать сильным identity/persistence proof | Может быть authority-bearing, если envelope/CAS/same-input closure проходят |
| **Canary bundle assembly** | Что authoritative artifacts были собраны в bundle и packaged together | Packaging/diagnostic; не producer authority |
| **Replay result** | Что replay reconstructed or re-evaluated path under known refs/version | Reader-side verification evidence |
| **Inspection result** | Что inspection tool обнаружил или не обнаружил structural/bridge defects | Reader attestation for completeness/integrity |
| **Readiness result** | Что readiness gate under active reader versions выдал closeout-oriented verdict | Closeout evidence, но не domain evidence |
| **Public export / dashboard export** | Что projection был построен и в каком состоянии он находится | Projection only; never closeout authority |

Самая важная строка здесь — `cas_artifact_write`. Именно на этом boundary bridge впервые может перейти из «просто учётной записи маршрута» в реальный closeout-grade support, потому что тут можно привязать output к CAS identity, runtime event, same-input closure и authority envelope. Но даже здесь bridge всё ещё не доказывает предметную истину claim; он доказывает **идентичность и сохранность authority-bearing artifact**, а не его substantive adequacy. Это хорошо согласуется и с внутренним `assert_runtime_emitted`, и с SLSA-style provenance, где attestation подтверждает, что платформа произвела subject through execution, а не что произведённый content автоматически истинен для внешнего policy claim. fileciteturn23file0L3-L3citeturn2view6turn9view0turn9view2

## Failure modes, правило разрешения конфликтов и итоговое решение

Для C37 полезно различать не просто «bridge bad / bridge good», а класс поломки и его effect on authority. Внутренние планы и authority-model уже перечисляют root-cause-семейства: missing provenance, spoofed provenance, packaging-only projection, borrowed authority envelope, same-input closure failure, schema contract failure, producer/reader status divergence, bridge dropped requirement IDs и handoff redaction/integrity failure. Honest-diagnostics substrate дополнительно подчёркивает, что unknown or contradictory provenance должно fail closed, а dashboards/readiness/public artifacts may read and project authority, but must not mint it. fileciteturn15file0L3-L3fileciteturn17file0L3-L3fileciteturn20file0L3-L3fileciteturn22file0L3-L3fileciteturn36file0L3-L3

Из этого выходит следующий rule set.

Если **bridge missing**, он может быть просто diagnostic defect для несерious surface, но для required async boundaries serious bundle должен fail closed. Если **bridge contradicts producer artifact**, побеждает не bridge и не projection, а authoritative producer artifact плюс reader validation; противоречие классифицируется как integrity incident и closeout blocker. Если **bridge has stale ids** или schema/version drift, такой bridge нельзя использовать как authority, пока нет явной compatibility/migration attestation. Если **bridge leaks raw content**, он должен быть отбракован как carrier safety failure и исключён из authority path. Если **bridge borrows authority** у чужого report kind или projection surface, это нужно считать отдельным authority failure, а не «просто несовпадением метаданных». Если **bridge masks producer failure**, то closeout должен опираться на strictest producer/reader closure, а не на позитивный projection state. fileciteturn23file0L3-L3fileciteturn26file0L3-L3fileciteturn28file0L3-L3fileciteturn30file0L3-L3fileciteturn34file0L3-L3

Итоговое решение для C37 можно сформулировать так:

**Bridge records in PolicyOS should default to non-substantive authority.** Они могут иметь evidence value, но эта value по умолчанию ограничена четырьмя вещами: transport continuity, boundary causality, provenance path и requirement propagation. Они становятся closeout-usable only when explicitly elevated into an attested runtime-owned evidence role through authority envelope, same-input closure, CAS identity, reader compatibility and integrity/redaction success. Они никогда не должны заменять producer evidence и никогда не должны позволять projection, packaging или orchestration metadata выглядеть как claim-level legal/data/method authority. fileciteturn13file0L3-L3fileciteturn15file0L3-L3fileciteturn22file0L3-L3fileciteturn26file0L3-L3

### Открытые вопросы и ограничения

В текущем материале остаются несколько точек, которые C37 должна закрыть decision-log’ом, а не кодом по умолчанию. Не до конца определено, должен ли PolicyOS ввести отдельный authority role специально для bridge-closeout evidence или использовать существующие `producer_authority` и `runtime_blocker`; как именно versioned remapping stale `requirement_ids` превращается из blocker в compatible migration; и должна ли reader attestation ссылаться на bridge record напрямую или только на underlying producer artifact. Эти вопросы соответствуют общей рамке research-only decisions в consolidation и не должны silently harden into runtime API до отдельного ADR. fileciteturn3file0L3-L3fileciteturn13file0L3-L3
