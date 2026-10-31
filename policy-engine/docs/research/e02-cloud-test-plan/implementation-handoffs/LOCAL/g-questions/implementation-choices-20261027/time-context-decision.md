# G decision note: request time scope and exact-view closure identity

Date: 2026-10-27  
Status: pending G. architecture_selection=pending_G; code_acceptance=false; closure_ids=[].  
Scope: semantic contract selection only. This does not accept the prototype as production behavior or authorize code changes.

## Question

Does ADR-0148's time_context_ref refer to the existing runtime API's bitemporal TemporalScope cursor for a request, or does the runtime require a new exhaustive bundle containing every time role relevant to a run?

## Recommendation: reuse TemporalScope, preserve role boundaries

Use the existing strict TemporalScope type for an explicit top-level NaturalLanguageRunRequest temporal_scope. Carry its valid_at and tx_at as distinct request cursor components. Do not infer either from context.as_of, an LLM-extracted date, CAS created_at, or wall-clock now. If a consumer needs a role that was not supplied, keep that consumer's gate blocked; do not fabricate a date or turn this decision into a universal completeness rule.

Keep the existing roles separate:

- PolicyIntentEnvelope.policy_time is policy time.
- DataRequirementScope.time and time_role are claim-bound data time.
- TemporalScope.valid_at and tx_at are the request's bitemporal cursor.
- Legal valid time and a selected legal snapshot remain owned by Lex/legal evidence.
- Publication as_of_time/generated_at are publication timing, not substitutes for the request cursor or legal currentness.

Option B, a new exhaustive role bundle, is not supported by the current source: it does not define which roles are mandatory for every NL run and would appoint a new producer obligation. Requiring a legal snapshot merely to close same-input identity is also rejected as an interpretation: ADR-0148 separates binding inputs from blocking when unavailable, while the Lex legal-compatibility barrier independently requires legal snapshot and legal evidence. Do not ask G to invent a legal fact.

## Shared exact-view invariant

Whichever time-scope option G selects, SameInputClosure must identify the exact selected CAS view for every closure member that is a CAS pointer. Use one typed owner/wire contract across those pointers: preserve the selected ArtifactRef identity, including artifact ID, kind, media type, and manifest_profile_sha256; resolve the exact selected manifest and payload through the existing owner admission, and apply that artifact's declared schema and owner checks. Producer metadata remains metadata, not producer attestation. Keep non-CAS references in their own typed identity domains. The closure identity/hash and consumers must compare the exact selected views. Do not add a profile field only to time_context_ref while leaving sibling CAS pointers as bare IDs.

This is a class-wide owner/consumer invariant. Current SameInputClosure stores string references and identity_tuple compares those strings. The temporary profile-drift falsifier used the same payload artifact ID with two verified manifest profiles; the consumer accepted the bare-ID identity even though the exact selected views differed. That is a P38 property/code divergence at the prototype boundary, not evidence that a published authority claim escaped. Close the class at shared typed intake and closure identity; do not repair one field instance at a time.

For P37, strict request-field parsing and exact owner-resolved CAS view/profile/payload comparison can be labeled recomputed. The requested time value itself is consumer_asserted and establishes caller intent only; its truth as a legal as-of time or claim-adequate data time is not established by the ref. Without the separate Lex/legal or data evidence required by the claim, that predicate stays not_established and the relevant authority gate remains blocked.

## Evidence and boundary

The existing readiness record is implementation-readiness.md (`../../raw/root-ir-transport-composition-20261024-r1/g-native-priority-20261025-r1/time-context-existing-contract-prototype-20261027-r1/implementation-readiness.md`; unavailable in this checkout) at SHA256 51cba6139db7b704781c0f535cab29dde46ba6b7369fbb89ff8a01ef297b503a. Its source hashes were revalidated against this R worktree. The four files that were owned WIP when the oracle ran are now committed in 647ec5df; all 13 source pins match the publication-preparation branch. This source-byte rebind does not turn the old prototype into an ordinary POST or authority receipt.

The prototype-02 stdout/receipt records a temporary local CAS compatibility path: typed DataRequirementScope times composed into TemporalScope; selected-profile readback; RunIntentBinding completeness; closure agreement; and negative missing-binding/substituted-member refusals. It reports authority_role=runtime_blocker, legal_snapshot_ref=null, source_freeze=false, closure_ids=[]. Prototype-05 varies producer version so the same payload ID has two selected manifest profiles, then records that the SameInputClosure consumer accepts the bare ID. Both runs are compatibility/falsifier evidence only. Neither exercised the ordinary POST producer path nor proved authority.

Current source has a strict top-level request model, but context remains dict[str, Any]; lifecycle queues that context without a typed TemporalScope; the NL closure builder currently writes time_context_ref=None and status=not_closed. RunIntentBinding requires a nonempty time_context_ref. The repository already defines TemporalScope, separate policy/data time contracts, profile-aware ArtifactRef, and the independent legal phase barrier. This is a missing producer/artifact/bridge/verification chain for the NL request path, not a missing time-role type.

## Acceptance signal after G

A later implementation is admissible only after one actual ordinary POST path carries the explicitly supplied TemporalScope through request validation, queued job, owner producer, persisted selected CAS view, and the real SameInputClosure reader. Re-resolve exact selected CAS views at admission and at consumer use; recompute the closure identity from those views rather than trusting a nonempty digest or a bare reference string. Show a positive controlled fixture and negatives for absent/malformed input, role/ref substitution, and identical payload ID with changed selected manifest profile. If a legal-dependent claim has legal_snapshot_ref=null, the Lex barrier must remain blocked.

Pattern pass: P08 time-role algebra; P29 actual-path evidence; P31 class-wide closure rather than field patch; P32 resolve/bind/verify; P37 recomputed admission predicates; P38 exact selected view versus bare-ID proxy; P40 same producer/bridge class one level deeper, requiring a widened shared mechanism. Capability state for this NL chain: producer_missing, artifact_missing, bridge_missing, verification_missing, and semantic_test_missing; the typed request input surface is also absent, while the blocker/report surface already exists.

## Limits

No ordinary POST ran. No tests ran in this handoff. No production CAS data was written. No source change, legal as-of fact, producer authority, publication claim, G closure, or code acceptance is asserted. Existing evidence links are reused; source and receipt contents are not copied here.
