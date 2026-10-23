# IR owner/version decisions — red-team R2

## Disposition

**No remaining architecture blocker in the reviewed revisions.** R1’s two findings are closed at the design/acceptance level: the actual ABM typed-reader escape is named and given a wrong-family discriminator; resource growth is now explicitly separated from representation/law registration and tested without per-resource admission edits. The revisions also preserve ADR-0107’s public `FULL` planning contract while forbidding that result from serving as typed EvidenceBundle admission.

This is a document-level disposition, not source acceptance or proof the mechanism is implemented. The handoff says tests/imports/builds and source acceptance were not performed. Do not turn this GO into a capability-complete claim.

## R1 closure check

| Prior concern | Updated evidence | Disposition |
|---|---|---|
| ABM typed consumer could decode a same-kind/same-media artifact with a different manifest schema, then DTO-validate it | Q1 L65 covers wrong schema name/version; L67 names `phase4_dynamics.py`’s `get_json_artifact` → `ABMResult.model_validate` route and requires ABM-shaped bytes from another family to fail. Q2 L15 separately requires EvidenceBundle to use strict owner admission from the selected manifest. | Closed in the spec. Keep the paired wrong-manifest and property-removal tests on the real loaders. This is the same P27/P31/P32/P38 owner-bypass class from R1, not a new class. |
| Extension registration could become per-resource capability gating | Q1 L52 distinguishes a resource using an admitted grammar/adapter from a new representation/law; L68 requires two new resources to be found without descriptor, family-list, dispatcher or per-resource approval edits. Handoff L22/L26 requires zero admission-core changes and a third unseen resource under the same grammar. | Closed in the spec. Resource discovery and representation registration now have distinct acceptance tests. |
| Legacy `FULL` could be globally redefined or remain the typed EvidenceBundle gate | Q2 L11-15 preserves the public planning API and explicitly forbids the current EvidenceBundle negotiation → generic-read sequence from remaining its authority path. | Closed in the spec. A paired test must retain advisory `FULL` behavior while the owner-bound loader refuses unknown equal/same-major versions. |
| Owner descriptor could become a second compatibility/family catalog | Q1 L24 says capabilities derive from the same records; Q2 L21 makes the existing registry the single compatibility source; handoff L24 uses ADR-0108’s catalog to expose/generated views, forbids a second inventory, and keeps trusted declaration snapshots out of the hot path. | Acceptable if implemented literally as one declaration source plus derived views. No separate editable family dispatch table. |

## Extensibility and historical boundary

“One contract” is a reusable resolution mechanism, not a frozen list of today’s default versions. Q1 L7 rejects freezing the universe to defaults; L48 allows an exact new representation with existing validators and reserves review for a genuinely new decoder/semantic law; L52 identifies resource versus representation changes. Q2 L7/L43 authorize a finite current set per snapshot while treating defaults as candidates to reconcile, not as the full supported universe. Handoff L22/L26 supplies the free-growth discriminator. The resulting rule is appropriately narrow: every *schema representation* needs an exact owner declaration, but a new method/dataset/jurisdiction under an already admitted grammar does not need a new declaration or approval.

Historical preservation also has no wildcard route. Q1 L23 requires exact representation pairs and explicit aliases; L56 keeps unknown old artifacts inspectable while withholding typed meaning until an exact contract/decoder is established. Q2 L33/L35 requires explicit manifest/payload tuples and aliases, L43 requires evidence for any retained historical reader, and L47 separates archival preservation from typed candidate use. Q2 L55 requires replay for standing claims/cases where custody/retention demands it, not indiscriminate readability of every old version. Unknown bytes can remain preserved/opaque; admission still requires an exact source representation and validator. No wildcard, same-major, or numeric-order compatibility follows from retention.

One implementation guardrail: ADR-0108’s `IRSchemaCatalog` is reflection/documentation metadata built from importable IR types, ABI entries, schema defaults and compatibility records. It is useful as a **derived view**, not by itself proof that a default is an admitted owner representation or that a type’s `ClassVar` binds a manifest. Keep the admission source as the trusted owner declaration/registry described in Q1/Q2; generate catalog views from it rather than promoting reflection or model defaults to authority. This is already consistent with handoff L24 and does not block the design.

## Pinned sources

Reviewed draft snapshots (SHA-256):

- `01-ir-owner-contract.md`: `566a8b50dd0443722612fc8dcdb4c9d62250744dd0e68b422efe1418ba14053b`
- `02-ir-version-compatibility.md`: `9283e1d809841ed60e7af9d6ade20f3942a116ee759b589c5749bfc378e475fd`
- `05-implementation-and-inputs.md`: `82c90408c94baf9073703d76f258147809484ce5dba66ecfa3634640b6da3312`

Question source is `f12fb9895a4009ce77828554f4c5c18d83e6ec15`. Relevant code anchors at that source: ABM ref `refs.py@fb421c0e7175e2119f31a4b5f7bb0aa87966774f`, generic IO `io.py@c3da682f0c6a274dd81abfb05f3f9c59a4bb1192`, ABM loader/DTO `phase4_dynamics.py@50782e3e5a172770458aa43b0140cef6f5a59326`, EvidenceBundle `evidence_bundle.py@832447e9d21200a283e4b7b9b1dc5ffd766dacca`. ADR-0108 is `0108-ir-schema-catalog-and-reflection.md@50ac08a588ba0cd4dfa6b6d857aa9edfa2395da5`; its catalog implementation is `schemas/catalog.py@35ff7c75cb3a6ec3e2362eb0c619678d23b8a80d`.

## Pattern pass

Relevant patterns remain P27/P31/P32/P38 for the actual typed admission boundary, P07 for compatibility replay, P13/Rule 12 for registry gravity versus resource discovery, and P01/P02/P10 for end-to-end capability claims. R1 findings are same-class closed in the design revisions; no additional escape was established here. Acceptance still needs real loader and discovery behavior, including the removal probe and an unseen third resource. Until that work is done, the proposed capability remains design-only with bridge/verification/semantic-test work outstanding.
