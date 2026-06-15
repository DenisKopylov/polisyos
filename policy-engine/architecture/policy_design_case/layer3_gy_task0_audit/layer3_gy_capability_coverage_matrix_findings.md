# GY Repo-Wide Capability Coverage Matrix

Date: 2026-06-14
Scope: audit-order item #1 — synthesize all 14 GY Task 0 audits into one capability × chain-stage grid.
Mode: audit-only synthesis. Every cell is cited to a source audit; statuses are claims those audits proved.

Artifacts: `layer3_gy_capability_coverage_matrix.json` (machine), this file.
Validator: `tools/quality/validation/check_layer3_gy_capability_coverage_matrix.py` (recomputes the summary from rows; fails on drift, bad status, or uncited rows).

## The chain

Each capability is scored along the producer→authority chain:

`contract → producer → artifact_or_event → bridge → consumer → surface → semantic_test`

Cell status vocabulary: `proven`, `partial`, `bridge_missing`, `surface_missing`, `absent`, `not_audited`, `out_of_route`, `n/a`.

A capability is route-authority-safe only when its whole chain is `proven`/`partial` with no `absent` / `bridge_missing` / `surface_missing` in a route-bearing stage.

## Headline: where the repo actually breaks

29 capabilities scored. Status counts per stage:

| Stage | proven | partial | bridge_missing | surface_missing | absent | not_audited | n/a | out_of_route |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| contract | 26 | 3 | – | – | – | – | – | – |
| producer | 15 | 14 | – | – | – | – | – | – |
| artifact_or_event | 3 | 14 | – | 4 | 3 | 2 | 2 | 1 |
| **bridge** | 1 | 1 | **20** | 1 | 3 | – | 3 | – |
| consumer | – | 11 | 5 | 7 | – | – | 5 | 1 |
| surface | – | 1 | – | 10 | 1 | 5 | 11 | 1 |
| **semantic_test** | – | 8 | – | – | **16** | 4 | 1 | – |

**Fully green chains: 1 / 29** (only `foundry data plane / build_input_bindings`).

This is the empirical answer to "if everything exists, why doesn't it work":

- **Contracts exist (26/29 proven).** The type/interface layer is real almost everywhere.
- **Producers exist (29/29 proven-or-partial).** The engines run.
- **The break is the bridge: 20/29 `bridge_missing`.** Capabilities are not orchestrated into the pinned route.
- **There is almost no authority surface (10 `surface_missing`, 11 `n/a`).**
- **There is almost no route-admissibility test (16/29 `semantic_test: absent`).**

So the dominant gap classes are `wired_but_ungoverned` (8), `partial` (9), `wired_but_rotten` (4), `contract_without_producer` (4). `missing` does not appear. The system's defect is **integration + governance + verification, not absent capability** — exactly the trap GY-0 exists to name.

## The "diagonal" reading

Reading left-to-right, coverage collapses as you move down the chain. Almost everything is green at `contract`, mostly green at `producer`, then falls off a cliff at `bridge` and never recovers at `surface`/`semantic_test`. The repo is **rich in components, poor in seams and in proof-of-authority** — which is the GX/GY thesis, now measured.

## What this means for the GY plan (per stage)

- **Bridges are the work (20 rows).** GY-1 (catalog→fetch→measurement-root, source-contract admission, connector route-binding), GY-2 (DAG output→waist authority; control-worker job→authority), GY-3 (RequiredDataSpec→DataNeedSpec), GY-4 (agent role-events), GY-6 (OpenAlex provider) are all `bridge_missing` rows. None is `missing` (build-from-scratch). The verbs are overwhelmingly **wire/govern**, not **build**.
- **Surfaces are unguarded (10 rows).** Runtime API/dashboard/public export, CAS authority backing, time-envelope, secret/PII gate, S12 refs, generated-artifact lifecycle all lack an authority surface. This is the cross-cutting laundering axis GY-2 must own; it is not engine wiring.
- **Semantic tests barely exist (16 absent).** Catalog precision@5 (construct+scope) = 0.0, Scholar NL 0/5, connector real-fetch unproven, governance judge-stack fails fatally. GY cannot accept any "wired" row as authority without a route-admissibility test added alongside.
- **Only 4 genuine build-new items.** `contract_without_producer`: catalog measurement-root producer, time-admission envelope, generated GY family, RequiredDataSpec→DataNeed bridge. Everything else is integrate-or-repair.

## Repair-order implication

The matrix orders the work by chain depth, not by package:

1. **Spine-first repair** (the `wired_but_rotten` rows): governance/validation judge stack, workflow-mode resolver, lex optional-bounds, KnowledgeToolkit registration. Governance of a rotten asset is forbidden (plan stop-rule).
2. **Bridges** (the 20 `bridge_missing`): wire catalog→fetch→root, source-contract admission, DataNeed bridge, agent role-events.
3. **Surfaces** (the 10 `surface_missing`): one authority boundary that DAG CAS output, time envelope, secret/PII gate, and S12 refs all pass through before any API/dashboard/public surface.
4. **Semantic tests** added at every step so no "wired" row becomes authority without route-admissibility proof.

## Caveats

- The matrix is a synthesis of audits, not a fresh execution pass; each cell cites the audit that proved it.
- Status is route-scoped (pinned UA-MSME). `out_of_route` rows (DDM) are real capability, just not on this route.
- `not_audited` cells (e.g., several `surface` stages) are honest unknowns, not green.
