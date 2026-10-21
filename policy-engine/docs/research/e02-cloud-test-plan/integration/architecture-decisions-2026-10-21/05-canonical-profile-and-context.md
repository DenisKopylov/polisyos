# AD-E02-05 / LA-021-1: canonical bytes, contextual meaning and producer origin

Status: G architecture selection for implementation, 2026-10-21. This selects the contract; it is not acceptance of a source implementation, an attestation of a historical producer, or finding closure. AD01–03 remain unchanged.

## Selection and rejected alternatives

Select **A: shared canonical byte/profile/hash mechanics, strict owner-specific tag policies**. `polisyos.canon.json@0.2.0` does not promise that every Core value is an IR value. Core acceptance of `array_digest` and IR refusal of that tag are compatible with this decision. No universal tag registry, runtime negotiation, CAS rewrite or readdressing is required.

Reject widening IR's accepted grammar to whatever Core can decode. Reject inferring a facade from payload content, falling back to another facade after refusal, or treating a manifest-profile digest as evidence that raw `canon` was present. A future universal value grammar would require a separately versioned semantic contract and migration; it is not needed for this repair.

This is a bounded interpretation of the existing profile, not a claim that its name alone is a sufficient portable semantic identity. A consumer must know the expected artifact contract and its decoder policy before interpreting a value. An external consumer receiving only bytes and the common profile cannot infer the intended semantic facade.

## Four separate identities

| Identity | Owner and meaning | Does not establish |
|---|---|---|
| Payload content ID | Existing Core CAS/hash owner; exact payload bytes | Which manifest view, producer, permission, meaning or currentness |
| Selected manifest-profile digest | Existing `ArtifactRef` / manifest selection; selected metadata view | Presence of a valid raw `canon` declaration or truth of metadata |
| Canonical representation declaration | Existing `CanonInfo` and common parser; name/version/options | Artifact schema or universal tag grammar |
| Semantic reader context | Existing artifact owner and selected decoder/contract revision | Scientific adequacy or authority to publish |

The complete selected ref remains the existing tuple including artifact ID, kind, media type and manifest-profile digest. A semantic admission/cache additionally binds artifact schema, caller purpose, concrete reader policy/version and relevant governance epoch. Reuse requires the exact resolved selected-manifest association and every semantic fact the admission consumes, including reconciled origin and audience/time roles where relevant. A changed manifest association, purpose, origin or epoch forces fresh lookup/reconciliation; excluded projection fields cannot sneak into a cached claim. This need not create a new raw-manifest identity where existing resolution already guarantees the property. Do not reuse a Core-decoded cache entry as an IR-admitted value.

Name the fixed reader policies `core-tag-policy@1` and `ir-tag-policy@1` in documentation and verification receipts. These are owner policy identities, not new payload tags or a second registry. Pin their source/implementation revision. Do not add a field to historical manifests merely to record these names: doing so changes the selected view. Any future persisted reader-admission record carries its own version independently.

## Reader and writer rule

The authoritative path is:

`expected owner contract → exact selected raw manifest → strict raw profile parse → payload identity → contextual decode and canonical conformance → typed artifact validation → purpose-specific admission`.

1. Fix the expected owner from the consumer's contract, never from a producer-controlled `facade` string. Where the caller has only an untyped artifact, inspection remains untyped/candidate; no semantic acceptance is inferred.
2. Resolve the selected raw manifest bytes once. Verify the selected identity and raw/typed agreement. Preserve missing versus explicit null, malformed, unsupported version and conflicting declarations.
3. Validate profile options under the common mechanical policy. Decode using the expected contextual tag set and verify canonical byte conformance. Unknown/malformed/reserved tags refuse; a decoder must not quietly treat them as ordinary dictionaries.
4. Validate artifact kind/media/schema and shape with the owner model, including numeric finiteness and paired optional fields where required. Canonical bytes can still contain a semantically invalid artifact. In particular, Core's recognized `array_digest` mapping is not evidence of a validated array descriptor, referenced array existence, shape or digest semantics. A consumer needing those properties must use the actual array/descriptor owner; absence of that owner is a limitation, not permission to trust the tag.
5. Writers use the corresponding context and must emit values their same-policy reader can read. Cross-facade transfer is allowed only for the explicitly shared subset and matching artifact contract. Equal bytes do not erase distinct contract roles.

Use the existing bounded readers and resource limits. Failure due to selected byte/depth/element limits is an explicit resource refusal, not malformed scientific data. Do not bypass limits to complete a proof and do not run reserialization or large payload scans inside ordinary cold HTTP GET. Existing admission workers may persist a bounded verified projection; GET checks the selected association, reader compatibility and access epoch.

### Profileless history

Default reads refuse absent profiles. The existing explicit profile-absent inspection option may remain **candidate-only**, using one explicitly selected expected decoder, with the absent-profile limitation preserved in every derived result. It is not a portable canonical value or evidence of historical eligibility.

Explicit-null/malformed/unknown-present declarations are not absence and never enter this compatibility route. Candidate mode is not permission to read unlawfully accessible data. A compatibility read cannot create producer attestation or silently install a canonical profile onto old bytes.

A lawful migration is a new writer operation that emits a new profiled artifact/view and a lineage edge to the original, recording conversion policy, actual time and owner. Preserve the original artifact and all historical refs. Do not call migration evidence of what the predecessor producer intended.

## Attestation, authority and time

Byte integrity is `recomputed`. Execution origin is separately reconciled against the existing owned Runtime/Foundry attempt record (or an external signed receipt admitted by its existing verifier). A producer's free-text assertion, even content-hashed, is `consumer_asserted`/`institutionally_supplied` until the relevant provenance predicate is reconciled. The hash of a fabricated but internally consistent bundle cannot pass the origin check.

A successful typed read proves conformance to the selected byte and artifact contracts. It does not prove: producer event occurred, bytes were produced on the alleged date, issuer was competent, data remain current, legal permission exists, or scientific claims are adequate. The existing manifest-profile projection excludes `created_at`; never use its digest to attest creation time. Creation, observation/valid time, verification time and read time remain distinct. Use existing custody/revalidation mechanisms for claims that stand over time.

No production profileless-prevalence estimate is necessary to implement the corrected reader. Such a prevalence claim requires a named inventory and complete denominator; keep it unavailable if not supplied. Likewise, genuine historical producer facts remain external. Do not invent a new attestation service for this decision.

## Footprint and migration

Extend or consolidate only the existing owners:

- `common/canonical.py`, `common/canonical_profile.py`: common mechanics and strict raw-declaration parsing.
- `core/canon/canon_json.py`, `core/artifacts/canonical_profile.py`: Core value policy, selected/bounded readers and typed owner validation.
- `ir/model_layer/canon.py`, IR artifact readers/adapters: strict IR policy and complete forwarding of selected profiles/options.
- Existing artifact contracts, read API/HTTP refusal projection and generated consumers that expose these outcomes; package/public-surface companions and golden compatibility fixtures.

The exact contemporary writer/reader census belongs to the implementer at its source freeze. The author's 13-origin / 135-input comparison is a pinned witness, not a permanent whole-repository denominator. Preserve ABI, canonical bytes, IDs and old views. Add documentation/refusal distinctions where missing; any emitted-schema change gets its own version and readers-first migration. No silent semantic promotion on legacy aliases.

## Deciding signals

1. Common-subset value through IR writer → Core CAS → fresh Core and IR readers yields the declared values and original identities.
2. Core `array_digest` persists and reads in Core; the same bytes/profile refuse in IR. Remove IR rejection while retaining profile names: the discriminator must fail.
3. Profile missing, explicit null, malformed, unsupported, raw-float profile mismatch and wrong selected manifest are distinct cases. Only genuine absence can use the explicit limited inspection route.
4. A non-null ref-profile digest with absent raw `canon` still refuses default admission. Changing/reforging every hash cannot manufacture raw-profile presence or owned producer origin.
5. A typed artifact with valid canonical bytes but wrong kind/schema/purpose refuses. Core cache priming must not make its IR read succeed.
6. Preserve all actual write options through typed and mapping adapters; verify exact old bytes/IDs from golden fixtures, both native and installed public consumers. Test ordinary HTTP's typed refusal with fresh readers.

These are implementation obligations, all UNRUN in this document-only session. The packet's 199-case CAN result belongs to `ee2a5d9e…`; it is not a current or integrated PASS.

## Research basis and limits

[RFC 8785 §3](https://www.rfc-editor.org/rfc/rfc8785) gives a useful separation: canonical serialization establishes a repeatable representation over a defined input domain. PolicyOS's tagged format is its own protocol; this decision does not claim JCS compatibility or import JCS's numeric rules. [W3C PROV-DM](https://www.w3.org/TR/prov-dm/) separates entities, generating activities and responsible agents; that distinction supports keeping content identity separate from origin and authority. These sources support the design reasoning, not verification of PolicyOS code.

Pattern pass: P04/P05/P07/P08, P27–P32, P35/P37/P38. Property: a selected view is both byte-conformant and admissible to this specific reader; proxy divergence: the same valid Core bytes are unsupported in IR. No new capability is claimed until the producer/reader/public refusal chain is verified. Missing provenance stays `verification_missing` for that provenance claim, not a blanket ban on ordinary candidate computation.
