# B31 independent discriminator and partner packet

Immutable research source: G `f00dd7661a8d3329fb1fa1b049decb0d1d2f277b` / tree `d9a4e73a0e85fa11f865bf643c1b63fbe66c2767`; A source `8bfea70b2e2090ad5c541b103b7521efc01b30eb`; E source `8d8e7b319e7eb6b57bc4ab3c4db5ca3070393f8c`. This is test design/source reading, not a product PASS.

Original logical owner: A / EMP-01 / B31. Original binding B_r19 lines 593–606, SHA256 `9311ba1b0fb2e6a3f180546c6118406c5781dbbfb57e27b28075b95a92fe371f`. C07 is the IR relation writer; C10 owns A producer/ValuePort adoption. E201/B202 decisions are separate, already chosen, not a new approval blocker.

## Defining property and independent oracle

Producer-owned persisted relation binds exact identification artifact, native uncertainty artifact, and resolved subject. Fresh A reader returns both channels separately: identification `[4,4]`, native statistical interval `[1,10]`. It does not collapse the interval, force its centering, synthesize 0.01 width, or change native functionals. Semantic coordinate depends on canonical estimand/outcome/contrast/population/typed unit/scale and applicable time/source/model; method FQN stays provenance. Two supported methods on one subject share the semantic coordinate.

Independent rational unit oracle: `RateUnit(percent)` -> `RateUnit(ratio)` factor `Fraction(1,100)`. Identification `[4,4] percent` becomes `[1/25,1/25] ratio`, native `[1,10] percent` becomes `[1/100,1/10] ratio`. Native width remains `9/100`, identification width remains 0. Reverse conversion round-trips exactly in the oracle. This is a supported same-quantity conversion; no FX or month/day law is inferred.

## Smallest actual-route harness

1. Use the canonical supported producer selected by C10 to resolve/normalize subject and produce identification and native uncertainty artifacts; persist both through existing CAS, with their exact subject lineage.
2. C07 relation writer persists the join through its canonical relation function. Do not manually set an authority field or use NativeValueEstimandBinding as production admission.
3. Close producer store/object cache. Reopen CAS in a fresh child process, invoke the actual A ValuePort/readback boundary with C10-provided admitted supplier and verifier context, assert both channels and matching subject.
4. Only then run matched mutations below through that same reader. If protected producer/verifier is unavailable, run generic/mechanical relation positives separately, label scientific/value admission UNRUN with packet; no mock authority PASS.

| Case | Mutation while retained labels remain | Required behavior |
| --- | --- | --- |
| P0 | Genuine exact artifacts/subject/verifier; point4 and interval1..10 | Separate channels preserved on fresh actual reader |
| P1 | Declared supported percent/ratio conversion | Exact same quantity and intervals; unit provenance retained |
| P2 | Two method FQNs for one exact subject | Same semantic coordinate; distinct method provenance |
| N1 | Missing relation / shaped nonexistent relation ID | Refusal before combined value claim |
| N2 | Caller-built NativeValueEstimandBinding or JSON `eligible=true` | No production/gating authority |
| N3 | Valid foreign resolved subject/population/outcome/contrast | Refusal despite same values, names, and markers |
| N4 | Only applicable horizon/origin/source/model basis changes | Stale relation refused; unchanged labels cannot revalidate |
| N5 | Same ID string but altered bytes/integrity or wrong content digest | Resolve/content check refuses; no hash=ID alias |
| N6 | Same bytes, different selected manifest profile/view | Complete ref identity mismatch refused |
| N7 | Missing/extra/duplicate `value_subject` lineage roles | Full declared role set rejected or reconciled exactly; no silent ignore |
| N8 | Native payload metadata claims matching subject, actual subject ref differs | Refusal; metadata strings cannot dominate resolved typed subject |
| N9 | Equivalent-looking unit string, unsupported or mismatching typed unit/domain | Typed unavailable/refusal; no clamp or guessed unit law |
| N10 | Replayed/fake/copied/mutated authority receipt, wrong current revision/challenge/context/purpose | No protected combined claim |
| R1 | Remove resolved-subject/unit/ref comparison while keeping relation/ref/diagnostic fields | At least N3/N4/N6 must FAIL |
| R2 | Remove verifier-origin/current-context check while retaining receipt labels | N10 must FAIL if actual verifier route is available |

## Existing capability map and limits

- `ir.artifacts.ArtifactStore`: `put_json`, `get_bytes`, `get_manifest`; bytes decoded by canonical `from_canonical_bytes`, not naive float-wrapper JSON interpretation.
- `core.artifacts.manifest.ArtifactRef` and InputRef carry `manifest_profile_sha256`; `artifact_ref_identity_key` includes ID/kind/media/profile; `input_ref_from_artifact_ref` preserves it. Core FileSystemCAS `get_bytes/get_manifest` accept typed refs and select manifest views.
- `ir.registry.refs.ArtifactRefModel` and `ir.artifacts.contracts.InputRef` currently omit view profile; `ir.artifacts.io.normalize_artifact_ref` strips profile. Relation must preserve/recompute selected view itself or obtain a narrow companion from C06, not silently claim exact-view binding.
- `core.contracts.ValueOuterSet.from_persisted_payload` checks serialized derived width; it has no first-class native uncertainty channel/relation at pinned G/A.
- `ir.analytics.uncertainty.NativeValueEstimandBinding` explicitly caller-constructible and contract_only_nonproduction; `foundry.components.MethodValueEvidence` is contract-only. Neither is scientific admission.
- `CausalEffectReport.to_uncertainty_envelope` intentionally emits gate_eligible=False at pinned G; `identified_estimand`, successful fit/CI or constructible ProofBundle is not a verifier.
- Existing `pdc._impl.evaluation_safety.EvalSafetyVerifierPort` / Runtime facade and `runtime.http.services.control.evaluation_safety.EvaluationSafetyAdmissionVerifier` verify execution safety against full EvaluationExecutionContext, fresh consumer challenge, current revision and private produced seal. This is an existing execution-admission capability, not automatic scientific identification authority.
- A `generation_cycle.ValueGateReceipt` holds outer set but lacks native uncertainty/relation ref; `FoundryValuePort` performs real current-context admission and currently honestly blocks at treatment_assignment_not_owner_derived. Its legacy `_value_outer_set_from_foundry_result` is not a real positive ValuePort route and still has arbitrary proxy width/method coordinate. Do not certify it by calling only that helper.

## Minimum C10 partner packet

Exact source/tree and selected maintained producer/ValuePort path; actual persisted identification+native uncertainty+relation+subject refs (complete view/hash/schema/lineage); resolved canonical EstimandAST/outcome/contrast/population/typed unit+scale/source/model/applicable time; native contract and method profile; actual existing verifier resolver/issuer revision/appointment/purpose and fresh challenge/context/currentness inputs; fresh A consumer command/selector with complete deciding output. All can be bounded synthetic supplier mechanics where supported; empirical assumptions/authority remain scoped. Missing scientific authority must be named separately from execution EvalSafety. C10 supplies the owned producer/adoption, C07 the relation/reader contract. Neither oracle nor coordinator self-issues authority.

P37: byte identity and complete lineage/subject/unit equality are recomputed; existing supported verifier provenance is independently_reconciled only after actual invocation; producer scientific assumptions remain institutionally_supplied/consumer_asserted/not_established as applicable and cannot independently open a protected gate. P40 bucket: same unverified-subject-join class; widen complete material subject/ref contract or declare supported profile, not per-method flag patches.
