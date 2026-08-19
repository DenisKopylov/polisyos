# Atlas Evidence Artifact

Freshness: 2026-08-13
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

The three-artifact C08 flow is:

1. Persist the exact real runner bytes through `ArtifactStore.put_bytes(...)`
   as an internal `atlas_evidence_raw_runner_report`, resolve them, and run the
   Core integrity verifier. The normalized payload's recomputed raw-report
   SHA-256 must equal this artifact's content address.
2. Normalize and strictly parse those runner bytes as the verification
   payload. Persist it through `ArtifactStore.put_json(...)` with the raw report
   as its sole `runner_report` input and with the recorded
   `polisyos.canon.json` 0.2.0 spec: floats admitted, NaN/Infinity rejected,
   `exclude_none=true`, depth 128, keys sorted, separators `,`/`:`, and
   `ensure_ascii=false`.
   This explicit spec is required because Core's default rejects numeric
   contrast ratios. The returned `ArtifactRef` binds the payload by the stable
   `sha256:<64hex>` `ArtifactID`.
3. Construct and strictly parse the receipt with that payload reference. Call
   `ArtifactStore.put_json(...)` for the receipt with one `PutOptions.inputs`
   edge to the payload using role
   `verification_payload`. Set manifest retention to 365 days with
   `delete_on_expiry=false`; cleanup remains manual. The receipt's returned
   `ArtifactRef` is external to its payload to avoid a circular self-hash.
4. Resolve and integrity-verify the normalized payload and receipt, verify both
   lineage edges, then run C07's semantic binding comparator. A valid digest
   with another subject/rule/result fails.

All three manifests classify the diagnostic material as `internal` and state
the observed local posture exactly: encryption mode `none`, not enforced, and
not verified. The receipt excludes the public audience. This is an honest local
evidence posture, not a publication/export contract.

The default filesystem backend lives at `.polisyos/cas` and uses the stable
sharded blob/manifest ABI documented in `docs/reference/operations/cas-storage.md`.
Remote backends remain valid because callers depend on `ArtifactStore`, not a
hand-built local path. `architecture/runtime_state_layout.toml` and
`architecture/generated_artifacts.toml` already register this ignored runtime
state; C07 adds no parallel state slot or generated-artifact family.

## Current capability state

C08 adds a strict automated-report producer and an explicit capture bridge for
two closed profiles: the keyboard-only Playwright journey and the seven-source
opaque-background Storybook/Vitest probe. Runner summary, exact test
population, result, findings, and raw-report SHA-256 are recomputed from the
machine report; a caller does not supply the evidence outcome. A passing
receipt requires every declared test to pass, while negative evidence remains
negative and retains its exact finding.

`scripts/persist_atlas_evidence.py` is a thin app-local consumer of Core's
public `ArtifactStore` contract. It does not construct a content address,
manifest, filesystem layout, or integrity result. It persists and verifies the
raw report, persists and verifies the normalized payload with that raw input,
then persists and verifies the receipt with the sole `verification_payload`
lineage edge. The TypeScript bridge applies this module's semantic payload
comparator after that Core result returns. Core canonical JSON must be decoded
with `from_canonical_bytes`; a generic `json.loads` is not equivalent when
finite floats use canonical tags.

The capture implementation is itself evidence. An ordered five-path set covers
the C07 schema owner, normalizer, executable bridge, MJS loader, and Python Core
adapter. TypeScript hashes every file and its aggregate; the fixed Python
adapter independently recomputes them before writing. All manifests carry the
implementation Git revision and repository dirty bit. A dirty capture therefore
has exact byte provenance but is not described as a clean-revision replay.

The capture command is explicit rather than automatically invoked by either
runner, and no readiness or maturity consumer is wired. After a real report is
persisted, resolved, integrity-verified, and semantically rebound, the honest
state is `implemented_but_not_orchestrated`, with `consumer_missing` and
`surface_missing`. Evidence-artifact integrity being green does not change the
captured runner outcome: a persisted failing browser observation remains a
failure. C10 owns reconciliation; manual AT remains C09's separate protocol.

Run the app-local launcher from `apps/runtime-dashboard`. It requires the exact
observation revision and command argv because neither value is encoded in the
runner JSON; both stay `institutionally_supplied` in payload details while the
runner population, outcome, findings, and raw-report digest are `recomputed`.
Playwright's reported version is recomputed; Vitest's JSON has no version, so
that profile version and the declared rule identity are also explicitly
`institutionally_supplied` and do not decide the observed result.
The CAS root is explicit for an isolated capture:

```bash
node scripts/capture_atlas_evidence.mjs \
  --profile keyboard_playwright \
  --report ../../_build/apps/runtime-dashboard/ds6-c08-keyboard-playwright-run2.json \
  --revision 8a9e320588ba3378b4596a609bca3762501e577f \
  --command-json '["/usr/bin/time","-p","corepack","pnpm","exec","playwright","test","e2e/a11y/keyboard-journeys.spec.ts","--project=chromium","--reporter=json"]' \
  --cas-root ../../_build/apps/runtime-dashboard/ds6-c08-cas-admitted \
  > ../../_build/apps/runtime-dashboard/ds6-c08-keyboard-capture-admitted.json
```

Focused non-browser verification:

```bash
cd apps/runtime-dashboard
corepack pnpm exec vitest run \
  src/test/evidence/atlasEvidenceArtifact.test.ts \
  src/test/evidence/atlasAutomatedEvidenceCapture.test.ts \
  --maxWorkers=2 --reporter=default
```
