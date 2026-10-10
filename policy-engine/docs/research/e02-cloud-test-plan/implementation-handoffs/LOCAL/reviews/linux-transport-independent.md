# Independent static review: Linux transport/Q2, pre-delta

## Verdict

**Not READY for transport or Q2.** This is a static review of the prepared script at
`3d45868b72f6a055c202995b7005704dc3b5fc6b` (tree
`4045a5255f4852131745b11f14cd5f514eb3cff3`) and script SHA-256
`4638c05015d80b0b39a09755fd383a179191169ecd23c68ab18f250e2659c35d`. The shared
checkout has since advanced to `c9d0941864a801e3f143b5cc2e94ec1c26f72e22`; a read-only
diff confirms the script, Q2 manifest, four raw inputs, and sitecustomize named below
are unchanged between those commits. The Q2 expected-case denominator is stale for
the current preflight: it enforces the historical 100 IDs, while the current Q2
collection covers five whole test files plus nine selectors and has additional cases.
The Q2 owner is widening that manifest/runner contract while preserving the historical
100-ID subset. The raw runner/manifest pins must then be refreshed and independently
reviewed. This review is pre-delta evidence only; it does not approve the changed
inputs or a final freeze.

No transport, Docker command, checkout, build, install, or test was run for this
review. The earlier preparation receipt reports `bash -n` and eight copy-decision
self-tests passing; I did not rerun them. Those tests exercise pure copy-action
decisions, not a real worker copy or transport.

## Frozen and ignored inputs

The primary manifest is tracked at
`docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/installed-wave-manifest.json`.
At the reviewed base its Git blob is
`34c084a608c3091d70f4b2df84289868fe6780b8`, and its file SHA-256 is
`ab7cf774e1c6805e9b1812472e5b8357af1a6a43d50a994a7488f29442d06eb7`. The script's
tracked-input path admits reuse only for an exact regular, non-symlink file; it checks
both the frozen Git blob and expected content hash before reuse.

The four host-side raw inputs are ignored and are not part of the source clone. Their
reviewed SHA-256 pins are:

| Input | SHA-256 |
|---|---|
| `LOCAL/q2-packaging/raw/run.py` | `5d54bce877979e82e3a7f95d451b6f076fcc318037868e329f26908065d80932` |
| `LOCAL/q2-packaging/raw/timeout_driver.py` | `eaa9c3f2355b05e2f55753da4ba297ca6f137a9ba7f4699e456d4ad872339a0a` |
| `LOCAL/q2-packaging/raw/supplemental_run.py` | `1e43531fce5d5ceb643349612823366f42702258efca598dec1d20feb524637e` |
| `LOCAL/q2-packaging/raw/supplemental-manifest.json` | `614013d0c2f3761012782405dbb1aa67abe16e15c37e849939de94ae6dd24b57` |

For these `tracked=no` inputs, the script checks ignore status and copies only into an
absent destination, then verifies the copied hash. An exact existing ignored file is
reused; changed bytes, a non-file, a symlink, or a non-ignored untracked target is
refused. The separately copied `sitecustomize.py` is pinned at
`4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2`.

## Transport boundary and consumers

The script selects the dedicated `colima-e02-local` context and dedicated Colima and
Docker configuration paths. Its worker check pins container
`e02-local-worker-provision` / `88c8824b3970ef929473daf73cda2e50083b2035f5b725071acf8a829fa5b0c6`
and image `sha256:dc53af52cf658aa04401244105cd63b25a7dfd42a6c5125683710b553d8d263f`.
It verifies the exact named-volume set and rejects bind mounts. This is a source-level
check in this review; I did not refresh the live Docker state. The preparation plan
records a prior live inspection with no source or production mount, but the current
worker identity and mounts remain to be checked by the actual transport run.

The host-side transport is a new shallow, single-branch `file://` clone of the
attached frozen branch. It checks branch, full commit, tree and shallow boundary,
copies the bare Git object store into the existing worker, then makes one attached
`--shared` checkout and reads back its commit/tree, clean tracked state and object
alternates. Destinations must not exist; there is no cleanup or overwrite path. This
is append-only and fail-closed on occupied or mismatched paths. The script does not
mount the source checkout into the worker or move host HEAD.

The Q2 recipe builds the source wheel and sdist, rebuilds a wheel from the sdist,
packages and rebuilds the GCP archive wheel, then installs each artifact into the
same isolated consumer environment sequentially. It checks installed import/resource
origins and asset bytes. The timeout driver binds the three profiles in order; the
supplement runs only after a passing primary receipt and reuses the primary consumer
environment. The exact test-ID receipt is the blocked point: the current prepared
runner rejects undeclared additional collected tests rather than silently accepting
them, but its expected set must be updated to the current whole-file-plus-selector
collection before this is runnable.

At the reviewed candidate, the 11 source/archive/wheel resource mappings in the
manifest reconcile with `hatch.toml`, the sdist include set, and the source bytes
(11/11; no missing sdist assets). This is a candidate-source census, not a final
freeze receipt. The manifest still names candidate baseline source
`077a572ff5880b3f50a85d3e3db6a232d277659a` and leaves its tree as
`REQUIRED_FROM_FINAL_FREEZE`; the actual source freeze and built artifacts must be
reconciled at execution.

## Property and residual

P40 classification: tracked-manifest reuse and ignored-raw-input copying are the same
transport-input admission class. The script’s exact-byte / exact-location decisions
cover the deeper tracked-versus-ignored cases, and the eight prior pure decision
self-tests reportedly cover exact reuse, missing/changed/symlink refusals, absent
ignored copy, and untracked refusal. They do not establish real Docker copy behavior,
worker readback, or Q2 consumer behavior.

Next required evidence is the Q2 owner's full expected-case manifest and refreshed
runner/manifest hashes, followed by a focused independent review of that delta. Only
after that may root pin the final source SHA/tree, recheck live worker identity and
capacity, grant the serialized slot, and run transport/Q2. Until those steps, status
is `prepared`, not transported, installed, or verified.
