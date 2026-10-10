# Core CAS intake and ownership receipt

This receipt covers the `core/artifacts/store.py` and
`core/artifacts/_transfer_ops.py` slice on `codex/e02-unified-local-20261009`,
initially continued from admission-only HEAD `9e89dddfbcc3d8c44a421cc1fc143ec84f3753ae`.
The root has since advanced the branch; this follow-up changes only the scoped
Core README paragraph, a pathwise B148 test port, and LOCAL receipts. The
Q1-owned `test_bound_import_preservation.py` remains unmodified.

## Source-bound change

- Directory, archive, and exact imports snapshot actual member bytes and validate
  the transfer inventory, blob digest, manifest identity, selected profile, and
  signature binding before `.cas-import-*` staging or publication.
- `_admit_import_members` holds artifact leases over source lineage and target
  views. It admits new unclaimed artifacts for the active owner, and returns a
  no-op only for exact bytes and a default/profile view already owned by that
  same tenant/cell. A supplied manifest tenant/cell context must match the
  active owner; an absent context does not defeat first-claim imports or an
  exact already-owned unbound view. An existing foreign owner still cannot be
  replaced or gain a reader/view claim.
- Directory/archive staging is a second read of the pinned transfer source; each
  staged member must match the intake digest and size. Publication re-reads and
  re-admits staged members at its own boundary.
- `get_manifest_bytes(ArtifactRef)` already returns verified original selected
  manifest bytes. No new raw-manifest protocol or adapter API was needed.
- Added a fresh-process reader test that reads imported bytes and original
  manifest bytes, then detects persisted blob corruption in a separate process.
- Ported the prepared B148 `test_import_admission_noop.py` source pathwise from
  `1e18a965` / `a0ee451f` (same source hash `44b8e5d3…14a3`). Its one
  unclaimed-unbound refusal case contradicted the explicit first-claim
  compatibility behavior, so its three consumer variants are represented by a
  positive adoption test asserting unchanged absent producer context and a
  receiver-local ownership claim. The remaining prepared cases and fixtures are
  retained.
- Reconciled the Core README to describe the implemented receiver-local
  first-claim behavior and left strict-bound first-claim authority as an open
  G-level decision; see `g-decision.md`.

## Pattern pass and capability state

Relevant patterns: P05/P32 (ownership and content-bound evidence), P29/P31
(behavioral removal probe and shared structural admission), P37/P38 (admission
uses measured bytes and current owner claims, not member names or declarations),
and P40 (the unbound-import compatibility finding was the same admission class;
the correction applies at both intake and publication). The property gate was
removed with all test markers intact; the negative probe then persisted a new
selected manifest and owner generation, gave tenant B a blob-reader/view-owner
claim, and successfully read tenant A's bytes. See `property-removal.log`.

The verified chain is import input -> measured CAS members -> owner transaction
and persisted refs/manifests -> existing CAS read/verify consumers, including a
new reader process. The public CAS import/read API is the relevant surface; no
claim is made about a downstream HTTP, audit, or dashboard projection.

## Verification

`prepared-b148-verification.log` records the adapted prepared property at 34
passed in 1.02 seconds. `b148-composed-verification.log` records 99 passing
tests in 18.39 seconds:
the complete adapted B148 property module (34 cases), Q1 foreign-owner
preservation, fresh-process/corruption, existing multi-tenant CAS,
artifact-ref serialization, and caching-store regressions. Ruff checks pass on
the production and focused test files, and `git diff --check` passes for the
leased source and README; Ruff format-check also passes for the two added test
modules. The B148 removal probe in
`b148-property-removal.log` is expected to fail: with admission removed, the
foreign-directory case creates `.cas-import-*` before refusal. It demonstrates
the semantic gate rather than a product test failure. The original Q1 removal
probe remains in `property-removal.log`.

Ruff format-check at the original source base also reported the two production
modules already needed reformatting; the Q1-owned test has its own formatter
finding. I avoided whole-module or peer-test reformatting. The new process and
pathwise B148 tests are formatted; see `ruff.log` and `head-format-probe.log`.

The working tree contains other agents' changes. No files were staged, and no
commit or branch movement was performed.

The earlier async-store `unbounded` dependency note is superseded in current
HEAD: `AsyncArtifactStoreAdapter` exposes the field and checkpoint budgeting
reads it. This CAS receipt does not claim that separate async contract is
verified.
