# Research basis and selected tradeoffs

Research access date: 2026-10-23. These sources inform design choices; no comparison benchmark, deployed backend validation or claim of a universally best implementation is made. PolicyOS's owned semantics and ratified boundaries decide the transfer. New method/library adoption still needs pinned implementation conformance, licensing/deployment compatibility and actual installed-consumer evidence.

## One interpretation law, many representations and resources

| Primary source | Reusable idea | Selected PolicyOS use / limit |
|---|---|---|
| [Avro 1.12 specification — schema resolution](https://avro.apache.org/docs/1.12.0/specification/) | Writer and reader schemas are distinct inputs to explicit resolution; a reader default serves a defined decoding purpose | Bind the real writer representation and a trusted reader contract. Do not infer supported history or authority from DTO defaults. Do not change PolicyOS's existing codec to Avro |
| [Iceberg specification — schema evolution](https://iceberg.apache.org/spec/#schema-evolution) | Stable identities and explicit evolution prevent renamed/reused fields from acquiring old meaning | Stable owner/contract mapping and immutable lineage; no stripping a suffix to infer an ABI owner, no identity rewrite on migration. No table-format/platform adoption |
| [Confluent schema evolution](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html) | Compatibility is directional and depends on the versions being compared; transitive history is a distinct promise | Exact declared source/target law and consumer-cohort rollout, not an automatic same-major promise. Reuse the local registry instead of installing a registry service |
| [Protocol Buffers evolution guidance](https://protobuf.dev/best-practices/dos-donts/) | Producers and consumers roll out at different times; rollback and old data survive a change | Readers first; preserve old object meaning and access to capable readers after writer rollback. A successful new reader does not prove old clients work |
| [Protocol Buffers unknown fields](https://protobuf.dev/programming-guides/editions/) | Intermediate projections can lose information even when the binary representation preserves it | Reject silent unknown-field dropping through JSON/DTO projections; explicitly label limited exports. This does not require globally permissive DTOs |
| [JSON Schema 2020-12 core](https://json-schema.org/draft/2020-12/json-schema-core) | Dialect/vocabulary identity and required processing capabilities are explicit | Unknown semantic vocabulary cannot select executable code or silently fall back. This is a draft specification, not an IETF RFC. Schema IDs are identities, not instructions to fetch arbitrary network schemas |
| [TUF 1.0.28 specification](https://theupdateframework.github.io/specification/v1.0.28/) | Version, signature, expiry and rollback/freeze protections answer different questions | Keep owner-policy snapshots, source bytes, issuer competence and current-use eligibility distinct. Do not claim that a pinned schema or signed receipt proves ongoing authority. No new TUF subsystem is proposed |
| [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html) | Representation semantics depend on declared metadata; sniffing can reinterpret content unsafely | The consumer establishes its expected family/profile before semantic decoding. Identical bytes under different manifests are not automatically the same admitted input |

The choice is **one interpreter mechanism, extensible owner declarations, discovered resources**. This differs from both a central list of today's defaults and an untyped plugin system. Existing grammar/adapter reuse costs no owner-core change. A new wire/semantic law has a single owner declaration and conformance work; its new meaning cannot honestly be added by a string alone.

An exact admitted version set is not a manually enumerated domain ontology. Reuse compatibility primitives and derive views/tests from declarations. Do not create a separate `supported_versions` list at each loader, cross-product of family×domain×jurisdiction policies, or resource-by-resource approval workflow. The tests distinguish these failure modes directly.

## Partial graph science and candidate usefulness

[Jaber, Zhang and Bareinboim, ICML 2019](https://proceedings.mlr.press/v97/jaber19a.html) studies complete identification with partial causal knowledge represented by PAGs. [Jaber et al., NeurIPS 2022](https://proceedings.neurips.cc/paper_files/paper/2022/hash/17a9ab4190289f0e1504bbb98d1d111a-Abstract-Conference.html) addresses conditional identification. These justify taking endpoint/equivalence semantics seriously, not converting each ambiguous edge independently and treating acyclic output as a class member. Neither is evidence that the current PolicyOS cross-population transport solver implements the theorem.

[Perković et al., JMLR 2018](https://jmlr.csail.mit.edu/beta/papers/v18/16-319.html) gives a complete generalized adjustment criterion across graph classes; [Bellot, UAI 2024](https://proceedings.mlr.press/v244/bellot24a.html) investigates partial identification under Markov equivalence. Exact identification, an adjustment criterion, bounds, and sensitivity over selected models are distinct products. A useful future algorithm may provide one without providing all the others. Their result profiles belong to the existing method/IR owner, with explicit domain and result semantics.

For E02 select a finite validated family, with structural membership checking separate from proposal generation, and retain direct scalar refusal for unresolved partial graphs. [06](06-validated-partial-graph-profile.md) names the existing optional causal-learn seam, a concrete construction and its resource limits. Independent pcalg/small-graph oracles support future conformance; no R deployment or new full PAG transport engine is required to wire the current candidate channel.

This selection trades completeness for a precise useful result: conditional outcomes over named validated members. It does **not** trade correctness of membership for speed. Incomplete validation yields no admitted member. No sampled fraction becomes posterior probability or all-class proof. A future complete method can attach through the same profile interface after its actual domain and proof are admitted.

The access/authority split follows PolicyOS S0-K06, not an external library convention. Unknown policy-level law may remain a declared candidate limitation; actual source access/disclosure still follows the relevant owner. No schema, graph paper or architecture decision can produce a missing operative legal fact.

## Alternatives explicitly rejected

- Default-string allowlist: small today, freezes extensions and misclassifies historical artifacts.
- Arbitrary override plus same-major/equal-string acceptance: convenient, permits schema identity laundering.
- Whole-repository migration before any repair: creates a serial bottleneck without improving a completed independent family.
- New global schema service, evidence subsystem, graph representation or scheduler: duplicates existing ownership for this scope.
- Run the old PAG sampler with a warning: loses graph meaning before the warning is emitted.
- Require legal-positive evidence or a universal PAG theorem before any candidate output: prevents useful permitted conditional exploration and conflicts with the candidate band.
- Promote candidate fraction/formula into old top-level fields: lets existing consumers silently change protected behavior.
- A false positive-free implementation that refuses every candidate: does not meet the selected productive capability.
