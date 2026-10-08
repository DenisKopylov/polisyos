# E02 Parallel Execution Plan

> Для agentic workers: применяй существующие execution/verification skills к конкретным task cards. Прямые specialists не создают детей; user-owned orchestrator делегирует один уровень. Начинай с [COMMON.md](COMMON.md).

**Goal:** одновременно выполнить независимые residual mechanisms и их доказательства, оставив authentic production checks локально и единственного integration publisher G.

**Architecture:** роли распределены по canonical write paths и producer/consumer boundary. Candidate-local подготовка и checks параллельны; composed verdict требует конкретных upstream inputs. Production payload не переносится в cloud; heavy portable replay, numerical/package/frontend проверки выполняются в cloud.

**Tech stack:** существующие PolicyOS Python/Node/locked worker и CAS/runtime profiles, без нового scheduler/registry/statistical framework.

**Spec:** [связанный closeout plan](../../integration/connected-closeout-plan-2026-10-08/README.md), его 23 карточки задач и 282 исходных findings; exact data/context — [dispatch.json](dispatch.json).

## Конфигурации

**Рекомендуемый запуск:** четыре cloud orchestrators + два local исполнителя + существующий G. Cloud orchestrators распределяют 13 specialist roles (12 code-owner roles и1 independent conformance role) по своим direct helpers. Это не четыре последовательных writers: независимые leases исполняются параллельно внутри каждого root.

**Если доступны отдельные cloud environments:** запускай13 specialist prompts как самостоятельные roots вместо четырёх orchestrators. Не запускай оба режима одновременно: иначе два root претендуют на один lease. Число ролей не означает гарантированную VM capacity или concurrency limit; доступность environments не установлена данным планом.

**Локально:** L01 собирает минимальные read-only inputs/owner facts и custody receipts; L02 выполняет exact authentic-data consumers. G сохраняет Q0/Q1, source acceptance, canonical generation, последовательную интеграцию и publication. На local machine один общий heavy slot для L02/G; metadata/rights/source review L01 параллелен. Cloud roots не получают CPU quotas.

## Что действительно параллельно

- [ ] Сразу: source/input review и candidate-local discriminators всех ролей; I1 effective profile basis; I2 census; три отдельные S1 subject/graph/refinement decisions; T1 owner/API/data inventory; G Q0/Q1.
- [ ] Authoring начинается только на свободном exact lease и определённом собственном contract. Missing соседний factual input ограничивает его positive, не generic refusal/fixture работу.
- [ ] Composed proof ждёт конкретные partner input blobs, а не весь root/bundle: B/C stream; CAS→D/F; money→A/D; subject/law→A; DFI→CAT/Legal; forecast→S10.
- [ ] После независимых reviews и source freeze: C13 heavy portable replay; L02/G проводят один final authentic closeout и original-criterion adjudication. Узкие affected authentic checks L02 разрешены раньше на exact admitted candidate и actual input, как указано в L02.md. Ни одна роль не делает свой общий replay после каждого commit.

## Review focus

1. Один и тот же source path или test/README/facade/lockfile назначен двум specialists.
2. Predictive/profile/simulation evidence повышается до causal/public authority без actual admitted producer.
3. При reference-preserving mutation effective profile/subject/tenant/cursor gate остаётся положительным.
4. Wrong-host/missing backend/source-reported summary превращается в runtime PASS.
5. Task/local-data boundary потеряна при split producer/consumer либо all23 cards ошибочно считаются новым full-bundle циклом.

Проверки этих пяти классов распределены между owner positive/negative controls, C13 независимым review и L02 exact actual-data consumers. Полная машинная карта roles/tasks/leases — dispatch.json; готовые промпты перечислены ниже.

## Готовые промпты

Рекомендуемый набор для запуска — четыре облачных root промпта и два локальных:

| Root | Назначение | Промпт |
|---|---|---|
| ORCH01, cloud | Runtime / CAS / money / pool-stream | [ORCH01](ORCH01.md) |
| ORCH02, cloud | Catalog / DFK-CAN / Legal | [ORCH02](ORCH02.md) |
| ORCH03, cloud | IR subject / graph-TMLE / calibration | [ORCH03](ORCH03.md) |
| ORCH04, cloud | Served A / Search D / independent conformance | [ORCH04](ORCH04.md) |
| L01, local | Минимальные authentic owner inputs и custody | [L01](L01.md) |
| L02, local | Exact production-dependent consumers и Mac profiles | [L02](L02.md) |

G продолжает по [G.md](G.md). Общие требования [COMMON](COMMON.md) читаются вместе с каждым промптом. В expanded режиме вместо ORCH01–04 используй C01–C13; локальные L01/L02/G те же.

- [C01 — Runtime: producer scope, graph validation, async/SKG и общий worker admission](C01.md)
- [C02 — CAS: custody, owner/manifest, transfer/import и Core facade](C02.md)
- [C03 — Money: producer events → durable ledger → budget/cache contract](C03.md)
- [C04 — B pool + C streaming: physical cleanup, cursor/restart и progress](C04.md)
- [C05 — Catalog/DFI: effective source basis и profile serving](C05.md)
- [C06 — DFK census/retirement и CAN installed reader companions](C06.md)
- [C07 — IR uncertainty и B31 persisted subject/estimand/unit relation](C07.md)
- [C08 — F graph/query profiles и TMLE competing-study admission](C08.md)
- [C09 — Calibration/UQ/DOE/Forecast: совместимые empirical producers](C09.md)
- [C10 — A served path: N4/N5/N6/N7/WMR, S10, fresh GET и manual UI](C10.md)
- [C11 — D Search/funnel: configured consumer, history/refinement и permit bridge](C11.md)
- [C12 — Legal: generation/model/query-profile → encoded query → serving](C12.md)
- [C13 — Independent conformance: installed/backend/frontend и один frozen portable replay](C13.md)

## Предел распараллеливания

В исходном DAG **шесть безусловно стартовых task cards**: Q0/Q1/I1/I2/S1/T1; R4 дополнительно зависит от конкретного workload. После relevant Q1/S1/I1/T1 inputs потенциально доступны двенадцать следующих cards (R1/R3/V1/V5/S3/V2/V3/V4/V7/S2/I4/T2), однако conditional inputs и file leases проверяются отдельно. R1→R2→I3 и producer→fresh consumer остаются последовательными там, где меняется actual input. Q2 требует соответствующего contract freeze. Это property-level зависимости, не шесть или двенадцать одновременно свободных VMs.

До этих cuts все 13 cloud ролей могут вести разные preparation/oracle/review/environment действия; 12 code-owner ролей могут писать одновременно только при свободных exact file leases и определённых contracts. Число source writers уменьшается на горячих shared файлах (A history/S10/HTTP, C07 IR facade, C11 builtin assembly, G generators). Добавлять roots на те же paths throughput не увеличивает. Полезные direct helpers после read-only scout — независимые test designers/reviewers/consumer auditors и авторы реально выделенных непересекающихся механизмов.

Compute-heavy GP/UQ/Monte Carlo, installed wheel/sdist, Linux DoWhy, Node/frontend и portable broad replay — cloud. Локально только authentic data/provenance/asset binding и требуемые Mac-native profiles. Local slot не остановит portable checks. Actual mounts/recipes/optional backend availability в этом плане **not_established**: L01 устанавливает их, C13 — supported profile, L02 — authentic positive.

Pattern pass: P01/P02/P12 producer/bridge; P04/P05/P07/P08/P15 status/authority/time; P10/P14 genuine measured scope; P27/P31 single owner; P29/P32/P33 behavioral discriminator; P35/P37/P38 complete denominator/real predicate; P40/P41 no repair ladder or inherited-red assumption. Acceptance — exact property→persisted artifact→fresh consumer plus adversarial/removal, or named honest missing capability.

Проверка назначения: [analysis-receipt.json](analysis-receipt.json), восемь независимых [reviews](reviews/coverage.md). Все 23 task routes, 282 original rows, 15 S1 residual assignments и actual paths на 20 immutable input trees проверены; unassigned paths/source-writer overlaps — 0. Это проверка промтов и ownership, не product runtime PASS.
