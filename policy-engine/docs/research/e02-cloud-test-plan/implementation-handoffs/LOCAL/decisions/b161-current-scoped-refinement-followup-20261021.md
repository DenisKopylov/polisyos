# B161 follow-up: current-scoped refinement and historical uncertainty

**Status:** proposal for G; same existing B161 decision class as the local R8 packet, not a new question class. No source acceptance, external law, formal closure, or G adjudication is claimed.

## Decision requested

D04 resolves the common subject join and keeps uncertainty channels separate, then explicitly defers B161’s permitted refinement profile and the consumer response to independent risk or a changed basis. Choose one bounded runtime behavior:

- **A — historical-only:** keep the historical conservative maximum as the only admitted outcome. A later estimate never refines current uncertainty on this route; B161 remains limited/held against its original current-refinement acceptance.
- **B — separate current projection (recommended):** retain history unchanged and expose a separate candidate-only current result. A lower current component is admitted only when the existing uncertainty owner supplies a real, content-bound permitted relation and the fresh consumer resolves/recomputes the same subject, measured value/estimand, complete inputs, permitted procedure/profile, rule/version, and relevant valid-time/currentness. A missing, stale, foreign, or changed basis stays `not_established`/limited. Independent risk and disagreement remain in force.

Do not choose a scientific estimator law, assert independence, or grant issuer/publication authority through this architecture decision. Do not use global `min`, latest-write, or stage order.

## Evidence and boundary

The original criterion is `B_r19_original.md@9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5`, lines 4165–4176, span `f08fecf0caf482a9f2d93c1f808ea16daa2232de161e5eeb98a7995fa2d41e0a`. It requires a same-scope current update while preserving history and unrelated high risk; another population cannot replace an unknown.

Connected-plan D04 is `02-decisions.md@6c736256699df2d5283d4fca939a4d81f12a6af3a3a08c190eec08c2bc998701`, lines 39–53. It says B161 is a separate relation: choose the permitted profile and consumer reaction before wiring; no generic overwrite. G’s selected AD01–03 do not decide this profile (`06-final-decisions-and-solo-review.md@4eb1e7e966194f424d0cc1ab57e91fd664a1534367bf776d07895741b5d8939b`).

At the inspected candidate `566d194402dec721d162cff83b4bf2d16442d52e` / tree `d242c6a1c3dcc1c69d0d11cac4051056d398da98`, `uncertainty.py@5e4090d0b58ce6db4ae3566a9c6bce092487dff04790937f555cc8ae6045da38` carries content-bound subject/value/input/rule/producer refs, `valid_time`, estimand, and unit. Its loader verifies identity and routing; it does not admit a refinement law. `funnel/orchestrator.py@dd80fd13d76787cee52288146b7d140756afa26249f4e500c6d6828ca1b8409f` uses `merge_max` for history and for the separate current route, labels the latter `basis_bound_routing_only`, and always sets `producer_law_not_established`. The configured static case at `test_configured_observations.py@23643c28c41d24e65cc308a172690ecea7753aa39ad11d2f785884bfb0070629` keeps both current and historical values at 0.9 for observations 0.9 then 0.1. These are routing/refusal mechanisms, not refinement; no tests were run for this follow-up. The source review reports no product caller of the persistence writer, so the actual producer bridge is still missing.

## Reuse-first path, effects, and falsifier

Reuse the existing `SearchUncertaintyBasis`/`SearchUncertaintyObservation`, CAS reader, and uncertainty owner. Extend that owner only with the permitted relation/profile and separate current projection; consolidate an existing complete owner relation if one is found. Do not build a universal risk aggregator. Keep old history and v1.0 routing artifacts readable as historical/routing-only; use an additive version after the canonical inventory, with no backfill or relabel.

If G chooses B, the next source-frozen discriminator is: an actual producer emits an earlier not-assessed result and a later same-scope estimate; a fresh consumer may lower only the current component while preserving the historical maximum and an independent 0.8 constraint. Change subject, estimand/value, any input, procedure/profile, rule/version, or valid-time/currentness independently; each mismatched case must withhold refinement. Remove the typed relation edge while retaining labels/markers; the consumer must withhold refinement. No result from that future check is claimed here.

The actual D/scientific uncertainty owner, with E/calibration and A/evidence consumer, must provide the permitted relation and its evidence. Missing method law, independence, issuer, or currentness inputs remain held; G must not invent them. Preserve the separate historical B198 CAL-06 closure (`closure-decisions/E.md@18f509321036ba13a20fd51440f43b75b1555b05ebbb11e4bc28f74489e1eb7f`, line 75). No finding closure is proposed by this packet.

## Delivery boundary

The prior R8 packet `LOCAL/b161-s1-refinement-r8-source-basis-20261013.md@8f7c228f88839020473f48d9f0261d67f60df6338ef7d7009edb4a3657746f4f` is local/untracked and absent from the inspected `b7adafe89423bc6906a5fb86c38e579a381ad2ee` G decision commit. Repository evidence therefore does not establish that G received or disposed it. Treat this as one concise follow-up to that existing question only if G cannot confirm prior receipt; otherwise do not send another B161 item. It does not duplicate the pending CAN LA-021 question or HTE inference-unavailable packet.

`G_acceptance=false`; `closure_ids=[]`; no product/code tests or external authority evidence are claimed.
