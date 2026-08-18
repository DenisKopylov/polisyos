# Atlas surface-readiness claim bases

Freshness: 2026-08-18

Owner: `team-frontend`

Closed producer:
`apps/runtime-dashboard/scripts/reconcile_atlas_surface_readiness.mjs`

Persistence operation: `persist_atlas_surface_readiness_claims`

DS6-C10-R1 reports the basis of each gated top-level claim in the canonical
surface-readiness ledger. It does not issue a reconciliation verdict, grant
`stable`, or compose several rows into a stronger claim.

## Gated claim population

The gated unit is one row for each `readiness_state=implemented` claim and one
separate row for each `maturity=stable` claim. A complete read of the canonical
ledger currently enumerates 261 readiness entries, five `implemented` claims,
and zero `stable` claims. Those counts are `recomputed` relative to the
full-schema-validated ledger, not sampled.

The governed projection currently exposes these five rows:

| Claim | Declared value | P37 predicate provenance | Basis observation |
| --- | --- | --- | --- |
| `route-redirect-launch:readiness_state:implemented` | `implemented` | `recomputed` | `observed` by the canonical `/launch` route assertion |
| `route-redirect-sources:readiness_state:implemented` | `implemented` | `recomputed` | `observed` by the canonical `/sources` route assertion |
| `route-redirect-data:readiness_state:implemented` | `implemented` | `recomputed` | `observed` by the canonical `/data` route assertion |
| `route-redirect-lex:readiness_state:implemented` | `implemented` | `recomputed` | `observed` by the canonical `/lex` route assertion |
| `route-redirect-health:readiness_state:implemented` | `implemented` | `recomputed` | `observed` by the canonical `/health` route assertion |

This table reports five independent rows. It is not a five-row PASS, a receipt
outcome, or authority for any other ledger entry.

## Exactly one basis per claim

Each row has one discriminated basis, never both.

`observed_by_reconciler` is admitted only through the closed operation below.
Its observation has three values:

- `observed`: the canonical check completed and positively witnessed the
  declared claim; the row predicate is `recomputed`;
- `not_observed`: the canonical check completed and negatively witnessed the
  claim; the row predicate remains `recomputed`;
- `observation_unavailable`: the owner, registered check, runner, or report
  could not provide an observation. Its reason is mandatory and the row
  predicate is `not_established`.

An unavailable observation is not a negative observation and is never
described as reconciled. No canonical `stable` observer is registered today;
if a live row declares `maturity=stable`, its own row therefore reports
`observation_unavailable/canonical_stable_observer_not_registered` and CI
fails closed. A synthetic stable negative control exercises that otherwise
empty gate arm on every test run.

`consistent_with_cited_report` is the reportable alternative. It binds the
cited artifact ID to its SHA-256 digest and records media/schema identity,
distinct producer and verifier identities, their P37 provenance, execution
status, and the complete finding array. The cited producer predicate is
`institutionally_supplied`; the verifier's consistency check is `recomputed`.
A cited row is never observation-eligible, even when internally consistent.

Cited status and facts constrain each other in both directions:

- `pass` requires zero findings; `pass` with findings is
  `cited_pass_with_findings`;
- `fail` or `incomplete` requires at least one finding; either status with zero
  findings is `cited_nonpass_without_findings`.

Those are contract errors, not silent downgrades to a reportable row.

## Closed observation and admission path

The only public request is:

```json
{ "operation": "persist_atlas_surface_readiness_claims" }
```

Any report, exit code, basis, root, script, or other request field is rejected.
The Python adapter resolves Node from its module-owned absolute allowlist and
launches the fixed MJS producer with no stdin and a fixed minimal environment.
`PATH`, `NODE_OPTIONS`, `NODE_PATH`, `PYTHON*`, `VITE*`, npm, and pnpm process
selection are not inherited.

The fixed producer accepts no arguments. It runs the unchanged full Draft
2020-12 canonical-owner validator and then runs the real
`src/app/routes/routes.test.tsx` matrix through the installed Vitest entry.
The reconciler observes the runner termination and JSON report internally,
but emits only the assertion fact belonging to each gated claim. Vitest's
suite-level `success` value and process exit are not copied into a claim
artifact.

The Python admission process independently reruns the same full owner
validator before it accepts producer output. It derives the complete gated set
from the validated ledger, binds every claim identity/title/dimension/value,
checks every observation/provenance pair, executable and source digest, and
rejects missing, extra, duplicate, reordered, or mismatched rows before any
CAS write. The validator's required, extra-property, unique-array, date/time,
enum, stable-evidence, and duplicate-identity corruption probes remain the
canonical owner witness.

## Core CAS audit projection

The closed operation stores two governed Core CAS artifacts:

1. `atlas_surface_readiness_claim_report` is the exact per-row producer stdout
   and has no input artifact;
2. `atlas_surface_readiness_claim_projection` has the report as its sole input
   with role `claim_report`, binds its artifact identity and digest, and repeats
   every claim and its exact basis for audit consumption.

Both artifacts use the existing internal CAS governance, integrity
verification, content addressing, and lineage checks. The projection is
authoritative only for `surface_readiness_claim_basis_audit`. It explicitly
denies aggregate reconciliation, component maturity, design/policy/runtime
authority, promotion, publication, and `stable`.

The projection contains no result, outcome, success Boolean, row count,
aggregate status, aggregate ranking, or independently reconciled label. Core
CAS integrity checks occur before the adapter returns, but their integrity
Boolean is not repurposed as readiness evidence.

## CI boundary and falsifier

The CI exit code is the **only** place a conjunction over rows may exist. It is
a gate, not a claim. It is never written to an artifact, never given a field
name, never surfaced in this projection or reference, and never carried as a
receipt outcome, provenance label, or aggregate status.

Existing Vitest discovery runs the semantic test. The test obtains the closed
projection, applies the gate separately to every row, and rejects a missing
gated owner row at admission/list comparison. A cited basis, completed
negative, and unavailable observation have distinct row-level failure codes.

The required falsifier serializes the report and projection before the CI gate
is called, calls the gate, and compares the bytes afterward. Removing the gate
call leaves every artifact byte unchanged. Therefore the exit calculation is
not carrying artifact information under another name.

From `apps/runtime-dashboard`, the focused acceptance command is:

```bash
corepack pnpm exec vitest run \
  src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts \
  --maxWorkers=1
```

The witnesses cover the closed current path, complete row set, Core CAS
integrity and lineage, owner corruption, denied request and environment
intake, both cited-status mismatch directions, valid cited evidence, distinct
negative/unavailable states, the zero-instance stable arm, exactly-one-basis
shape, aggregate-field absence, and the CI/artifact-independence falsifier.
