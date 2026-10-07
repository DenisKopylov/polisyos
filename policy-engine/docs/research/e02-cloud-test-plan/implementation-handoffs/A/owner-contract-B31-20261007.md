# B31 owner action: bind identification and native uncertainty

**Status:** owner decision requested; B31 remains `held` / `not_adjudicated`. This note narrows the unresolved contract question. It does not change finding status, ratify scientific meaning, or authorize implementation.

## Decision requested

To the already responsible owner of `polisyos.ir.analytics.uncertainty` and its existing registry/contracts boundary:

> Can the existing typed estimand binding be used to link an A `ValueOuterSet` identification result to the existing v1.1 `UncertaintyEnvelopeRef` for native statistical/model uncertainty, with both bound to the same exact estimand and unit at the consumer readback?

If **yes**, identify the existing production-valid binding and the fields the consumer must compare. Keep the existing v1.1 envelope/ref and the two channels separate; no shared schema change is requested.

If **no**, name only the smallest typed relation needed at the existing A composition boundary to bind the identification result and the existing envelope ref to the same estimand/unit. Preserve v1.1 decoding and replay. Do not add point/quantile rules, joint-law storage rules, or a new API/signature workflow to this B31 decision.

The current record does not establish an individually appointed owner. Do not infer one from A/E implementation ownership, DS16 adjacency, or this request. Route the single question through the existing ownership process; this packet does not appoint an owner.

## B31 property and boundary

The original B31 card says the existing helper can collapse point identification to `[estimate, estimate]` and can symmetrize/widen a proxy interval; it requires retaining native statistical/model uncertainty as a separate, verifiable channel, preserving asymmetric intervals and equivalent unit conversion. A zero-width identification set alone is not an error; presenting it as total certainty or dropping the native channel is. See `B_r19_original.md@d800082eebfc12eaf647b0c0257c4f06e135d25a#L593-L605`.

The corrected G9a decision says to first test whether the existing versioned carrier/ref represents both channels with estimand, unit, and provenance; reuse it if adequate. If inadequate, ask for only the smallest contract change from its responsible owner. E B201/B202 functional, joint-law, storage, wire-version, and API decisions are separate and are not B31 prerequisites; no new signing or approval workflow is introduced. See `closure-decisions/A.md@9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7#L148` and `closure-decisions/semantic-decisions.md@432a2c10ee56ab0b60c94fdd8a6b834fd512627a#L7,L13,L21,L36`.

Root579's combined B31/B201/B202 text is a research recommendation, not an adopted owner decision. Its wider request for four combined ratifications must not be treated as a B31 prerequisite. The older public-IR review correctly leaves B31 held, but its combined owner-decision inventory predates the G9a scope correction. See `closure-decisions/semantic-decisions.md@68fcdf9337eb4b0f268d5c2c786e2900edf28a2b#L5-L13,L21,L36`; `implementation-handoffs/A/public-ir-review.json@2c0de621b9e46e8839fc4f3d53b6ceccadf8bb06#/capability_state_or_finding_state`.

## Existing pieces and the exact gap

- `ValueOuterSet` is already the identification-set carrier. Its `point` status requires tight bounds and its `proxy` status requires nonzero width. It has coordinate labels but no typed estimand/unit binding. Keep statistical intervals out of these bounds. (`core/contracts/value_outer_set.py@e73454e6b50624acc69627f48172a7612c9ccd9c#L154-L171,L277-L333`.)
- `UncertaintyEnvelope` v1.1 already carries a point, confidence interval, confidence level, interval semantics, source, optional distribution payload, provenance, and metadata. The existing typed `UncertaintyEnvelopeRef` and CAS `persist_uncertainty_envelope` / `load_uncertainty_envelope` are reusable. The envelope's metadata is an open dictionary, however; the typed ref carries artifact ID/kind/media type, not estimand or unit. v1.1 also requires its point estimate to lie within its interval, which the B31 control below satisfies. (`ir/analytics/uncertainty.py@0a2495855d707a6548da6983bdef9abed9c4b0c7#L1357-L1467,L2115-L2142`; `ir/registry/refs.py#L19-L58`.)
- `NativeValueEstimandBinding` already has typed estimand, population, unit, scale, transform, time-horizon, and content-hash fields, but is explicitly `contract_only_nonproduction` and `production_value_eligible=False`. `MethodValueEvidence` validates a binding hash against envelope metadata, but is itself contract-only and contains no `ValueOuterSet`. This is a reusable contract seam, not evidence that a production consumer can use it today. (`ir/analytics/uncertainty.py@0a2495855d707a6548da6983bdef9abed9c4b0c7#L116-L227`; `foundry/methods/components/value_evidence.py@99500dba7526c987be9e6e7bbc320ec844fb7a13#L57-L113,L188-L371`.)
- A's current `ValueGateReceipt` and `ValuePortObservation` carry the `ValueOuterSet`/value ref but no uncertainty ref or same-estimand/unit binding. The helper `_value_outer_set_from_foundry_result` returns only a `ValueOuterSet`: its point branch drops the native CI and its proxy branch derives a symmetric width. The prior exact source census found no product caller; the default N8 route blocks with `treatment_assignment_not_owner_derived`. Thus the defect is latent, not an established served public projection loss. (`runtime/quality/generation_cycle.py@a9bee33288e66aecada88a58b44fd504a33b78c7#L12341-L12399,L1266-L1344,L5166-L5197`; `public-ir-review/README.md@1184b6998001568e7b80a02fa201ec52fc8ace96#L15-L19`.)

The missing production property is therefore the **content-bound link** from the point-identification result to the native uncertainty ref through one exact estimand/unit identity. Do not mistake envelope metadata, a method name, or the presence of two refs for that link.

## Consumer-level acceptance witness after the owner answer

Use an owner-resolved estimand `E` and unit `U`:

1. Positive: `ValueOuterSet` is point-identified at `[4,4] U`; the native envelope is a statistical/model interval with point `4 U` and asymmetric interval `[1,10] U`. Persist and reload the existing v1.1 envelope/ref. The A consumer returns both distinct channels, verifies they bind to `E/U`, preserves `[1,10]` exactly, and does not add a proxy width.
2. Unit control: convert the same values by a declared factor of 100. The set becomes `[400,400]` in the converted unit and the interval `[100,1000]`; the consumer preserves their relationship and reports the same estimand. Two method FQNs for `E/U` remain method provenance, not two different value coordinates.
3. Negative controls: remove the envelope ref while retaining point/set markers; supply a foreign, unresolved, wrong-estimand, wrong-unit/scale/transform, wrong-scope, or content-mismatched ref. The consumer must return the existing typed limited/blocked state and must not present point identification as zero total uncertainty.

The finite `99×0 + 1×100` mean-1, 95%-mass `[0,0]` oracle is B201-only. It is not needed for this B31 witness and does not authorize a changed v1.1 meaning.

## Closure boundary

An owner answer only resolves the binding decision. B31 remains held until the real producer → persisted typed envelope/ref → A bridge → consumer readback demonstrates the positive and negative properties above. No current served B31 loss is claimed, and this packet does not close B31.
