# Atlas Evidence Artifact

Freshness: 2026-08-11
Owner: `team-frontend`
Contract: `apps/runtime-dashboard/src/test/evidence/atlasEvidenceArtifact.ts`
Storage owner: `polisyos.core.artifacts.ArtifactStore`

## Purpose and authority

An Atlas evidence receipt records one rule observation over one named component
state or surface. It is evidence-capture material, not a maturity decision. The
contract fixes `authoritative_for` to `atlas_evidence_capture` and fixes the
complete denied-use set to component maturity, design authority, policy
authority, promotion, publication, runtime authority, and `stable`.

The receipt preserves the P37 predicate-provenance label exactly as observed:
`recomputed`, `independently_reconciled`, `consumer_asserted`,
`institutionally_supplied`, or `not_established`. This artifact does not upgrade
the last three. A later authority-grade consumer must fail closed or degrade its
claim when one of them is decisive.

## Strict payload

The Zod runtime schema is the TypeScript DTO owner. Every governed object is
strict; unknown fields fail. A receipt requires:

- receipt schema ID/version and rule ID/version;
- exact authority purpose and denied-use tuple;
- evidence kind (`automated_browser`, `automated_keyboard`, or `manual_at`),
  subject/state identity, outcome, and outcome-consistent findings;
- separate producer and verifier identities/versions, repository revision,
  exact command argv, and predicate-provenance classification;
- a non-empty, unique audience set in the existing Atlas order
  `PUBLIC`, `REVIEWER`, `EXPERT`, `MACHINE`;
- separate UTC observation, collection, and verification instants, ordered
  `observed_at <= collected_at <= verified_at`;
- the raw verification payload's Core CAS `ArtifactRef` fields plus its schema
  ID/version; and
- `content_addressed_runtime_artifacts` retention for 365 days, with
  `retain_until` derived from collection and manual approval required for
  cleanup.

`pass` requires zero findings. `fail` and `incomplete` require at least one
typed finding. An absent violation is therefore not enough to construct a
passing receipt.

## Canonical persistence

Receipt bytes use the existing Core artifact boundary; DS6 does not implement a
second CAS. A normalized verification payload carries the same evidence kind,
subject, rule, producer/verifier provenance, times, and result as the receipt,
plus rule-versioned JSON details. The resolver-side C07 comparator rejects a
valid but unrelated payload after resolution.

The two-stage C08 flow is:

1. Normalize and strictly parse the real runner output as the verification
   payload. Persist it through `ArtifactStore.put_json(...)` with the recorded
   `polisyos.canon.json` 0.2.0 spec: floats admitted, NaN/Infinity rejected,
   `exclude_none=true`, depth 128, keys sorted, separators `,`/`:`, and
   `ensure_ascii=false`.
   This explicit spec is required because Core's default rejects numeric
   contrast ratios. The returned `ArtifactRef` binds the payload by the stable
   `sha256:<64hex>` `ArtifactID`.
2. Construct and strictly parse the receipt with that payload reference.
3. Resolve the payload, run the Core integrity verifier, then run C07's semantic
   binding comparator. A valid digest with another subject/rule/result fails.
4. Call `ArtifactStore.put_json(...)` for the receipt with one
   `ArtifactWriteOptions.inputs` edge to the payload using role
   `verification_payload`. Set manifest retention to 365 days with
   `delete_on_expiry=false`; cleanup remains manual. The second returned
   `ArtifactRef` is the receipt identity, external to the payload to avoid a
   circular self-hash.
5. Resolve and integrity-verify the receipt and its manifest lineage before any
   consumer admits it.

The default filesystem backend lives at `.polisyos/cas` and uses the stable
sharded blob/manifest ABI documented in `docs/reference/operations/cas-storage.md`.
Remote backends remain valid because callers depend on `ArtifactStore`, not a
hand-built local path. `architecture/runtime_state_layout.toml` and
`architecture/generated_artifacts.toml` already register this ignored runtime
state; C07 adds no parallel state slot or generated-artifact family.

## Current capability state

C07 supplies a strict contract and focused semantic negatives only. A
well-shaped `sha256:` value is still self-attested until C08 resolves and
verifies it through the real store. No raw payload or receipt is persisted in
C07, no browser/keyboard/manual-AT runner is wired, and no maturity/readiness
consumer acts on this contract. The current state is therefore `contract_only`
with `producer_missing`, `artifact_missing`, `bridge_missing`,
`consumer_missing`, evidence `verification_missing`, and `surface_missing`.
The focused semantic tests implement contract verification; they do not close
verification for an evidence artifact that does not yet exist.

Focused non-browser verification:

```bash
cd apps/runtime-dashboard
corepack pnpm exec vitest run src/test/evidence/atlasEvidenceArtifact.test.ts --maxWorkers=2 --reporter=default
```
