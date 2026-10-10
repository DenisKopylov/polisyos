# G decision packet: first claims for unbound CAS imports

**Status: open; no G-level authority policy selected.** This packet records the
runtime boundary and the decision G must make. It does not authorize a general
cross-tenant transfer.

## Decision question

When a scoped filesystem CAS receives an artifact with no existing tenant claim
and the exact source manifest has no `tenant_context`, may the receiver record a
first local owner claim under its active tenant/cell scope, or must first-claim
imports require a matching bound context or another independently verified
permission fact?

The manifest context is a producer-supplied declaration. Matching it to the
receiver scope content-binds that declaration to selected manifest bytes; it
does not independently prove the producer was entitled to transfer the bytes.
The receiver's persisted owner-index claim proves local CAS custody; it does not
prove producer identity, source ownership, consent, or permission.

## Runtime choices

**A — strict bound first claim.** Require a present `tenant_context` whose
tenant and exact cell identity match the receiving scope before a new scoped
claim. Preserve a separately specified same-owner exact no-op for any existing
unbound view if G wants that compatibility. A matching context remains only a
content-bound declaration unless G also defines and verifies trusted source or
transfer-permission evidence.

**B — receiver first-claim adoption (current behavior).** If the artifact is
unclaimed, an unbound manifest may be imported and the active receiver scope is
recorded in the local durable owner transaction. The original manifest bytes
and absent producer context remain unchanged. If a context is present, it must
match the receiver's tenant and exact cell identity. If the artifact already
has claims, an import is a no-op only when its exact bytes and selected
manifest/profile/signature view are already owned by that same receiver. This
is receiver-local custody, not a producer or transfer-permission finding.

Neither implementation choice settles the external authority question. G must
identify a typed, content-bound, independently reconciled or institutionally
supplied predicate before describing the operation as authorized transfer.

## Evidence and falsifiers

Independent review F-01 in `LOCAL/reviews/can-cas-review.md` reproduced the
divergent case at `a35aff3bc320150aa58273149db0e58ce96c5156`: an unscoped source
with absent context was imported into an empty tenant-scoped CAS; the original
manifest remained unbound and the receiving owner index gained a tenant claim.
That falsifies the old Core README sentence that all unbound scoped imports
refuse. It establishes runtime behavior, not which G policy is correct.

The adapted positive probe in `tests/unit/core/artifacts/test_import_admission_noop.py`
exercises directory, archive, and exact imports. It checks the source and
receiver manifest bytes remain identical, both retain absent producer context,
the receiver has its local owner claim, and the unscoped source has no tenant
claim. This probe falsifies either an accidental rewrite of producer context or
a claim that the receiver acquired source authority. Bound same-owner fresh-
process read/verify is covered by
`tests/unit/core/artifacts/test_transfer_import_fresh_process.py`.

The complementary refusal falsifier is a foreign bound manifest or an unbound
view aimed at an artifact already claimed by another/different view owner. The
full prepared B148 property-removal probe replaces `_admit_import_members` while
leaving its test and publication markers intact; the negative test then observes
`.cas-import-*` staging before refusal. See `b148-property-removal.log`.
Without that removed property, the focused B148 and CAS consumer tests pass and
preserve receiver bytes, manifests, signatures, owner generations and durable
retry behavior.

The prepared `test_import_admission_noop.py` bytes were sourced pathwise from
both commits `1e18a965` and `a0ee451f`; their source SHA-256 is
`44b8e5d352da4ada1cc4a66b9f824776e38582d28424c408474769a6c0bb14a3`. The only
policy-case adjustment removes its three `unclaimed_unbound` refusal variants
and replaces them with three actual first-claim adoption variants, following
the explicit compatibility instruction. The remaining prepared cases and
fixtures are retained; no branch snapshot or cherry-pick was used.

## B148 scope limit

B148 here is a local `FileSystemCAS` property: directory/archive/exact import
admission; same-owner exact no-op; existing claimed-view metadata/signature
preservation; mixed-package staging; durable-intent recovery; lease exclusion
against a competing writer; and public reads/verification, including a fresh
reader process. It does not establish cloud-backend parity, trusted producer
identity, cryptographic signer authorization, external consent, or a general
cross-tenant transfer law. Signature cases bind/preserve exact bytes; they are
not a new signature trust policy.

Relevant repairs are P05/P32/P37/P38 (separate local custody from authority,
bind evidence to bytes, and test the actual owner predicate) and P40 (same
unbound-import admission class; resolve policy rather than per-consumer
patching). The Core README now states B as existing behavior and leaves the
strict-versus-legacy authority choice open for G.
