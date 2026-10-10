# Independent Q2/Linux delta review

## Assessment

The Q2 selector delta repairs the stale 100-ID primary denominator at the runner and
manifest level. The selected set now names all 125 current source-qualified node IDs,
keeps the historical 100-ID subset, and uses the same `current_primary_suite` contract
through the timeout driver and six-selector supplement. The runner’s content and
transitive-fixture checks reject a stale digest, a removed ID, and changed selected
test-source bytes. The current transport script pins these updated inputs and its
tracked-versus-ignored copy decision still passes its eight pure state checks.

This is **not a transport or installed-Q2 READY receipt**. At review time, candidate
HEAD was `d12ae0a32d09d2ec7303008c7f853ef93de72aab`, tree
`6299f3c00f7d88507d72efe0acf64ba1196d2dda`, on branch
`codex/e02-unified-local-20261009`, with shared worktree changes. The new manifest is
tracked but modified in the worktree: HEAD’s Git blob is
`34c084a608c3091d70f4b2df84289868fe6780b8`, while the required current manifest
content hashes to `26f415a50704a8f555be7c10676e5f427178b150152630140e22b8df054086c6`.
The transport script requires both the target file and the frozen Git blob to match
that expected hash, so the manifest must be included in root’s source-boundary commit
before transport. The final source SHA/tree and live worker/capacity checks are still
unassigned/recheckable preconditions.

## Q2 set and source binding

The current manifest binds 125 sorted, unique source-qualified IDs to SHA-256
`61189a3b41592600556a7d63dff970fd05358a406ee8598b7211f0f6535aafd8`. The required
historical subset is 91 original JUnit IDs plus nine named installed consumers: 100
IDs with SHA-256
`a1da373ad502cb17fe1932757cae15fd91450063587720e1ec727e32676f751b`. The supplement
is independently bound to six IDs; the locally recomputed canonical ID digest is
`59c15d426dd18da7aeaf691ec0d59cdb3a4386eba9576ec59f7cb1b97ae1ba1c`.

I imported the current `run.py` with bytecode writes disabled and called its
`baseline_node_ids`, `verify_current_primary_suite_sources`,
`historical_baseline_subset_ids`, and `verify_transitive_test_bindings` helpers against
the current product tree. They recomputed 91, 125, and 100 IDs and the expected two
primary digests; the current set contains the historical subset. The manifest’s
seven source-hash entries exactly cover the selected test paths:

- `docs/research/e02-cloud-test-plan/implementation-handoffs/F/installed-default-resource-final-20261007/test_installed_catalog_defaults.py`
- `tests/unit/foundry/methods/catalog/causal/test_graph_reconciliation.py`
- `tests/unit/foundry/methods/catalog/causal/test_installed_worker_profile.py`
- `tests/unit/foundry/methods/test_dependency_profile.py`
- `tests/unit/scientist/methods/causal/test_graph_intake_current_content.py`
- `tests/unit/scientist/methods/causal/test_reconcile_causal_graph_node.py`
- `tests/unit/scientist/nodes/builtins/causal/test_reconcile_causal_graph.py`

The runner checks the exact path set, sorted/unique ID list, count, digest, required
historical subset, mandatory additional selectors, and each selected file’s current
bytes. Its transitive binding pass resolves every ID to one unique test body, follows
local helper calls, and verifies the dynamic DoWhy/GCM fixture loaders, declared kind
set, callback uniqueness, and call arity. The current closure resolves 82 selected
test functions and the declared `dowhy` and `gcm` fixture kinds.

The retained source-only `pytest --collect-only` preflight reports 125/125 exact
primary IDs and 6/6 supplement IDs, with no missing, extra, or duplicate IDs. Its
recorded command explicitly says no test bodies, package build, archive, wheel, or
install ran. The result and complete collection streams are retained at
`LOCAL/q2-packaging/raw/final-preflight-20261010-r6/`: `results.json` SHA-256
`f048a16cc23a3d18c1557b64b6faf558debc3ce1a54940d29ef7a478439983f8`, `stdout.txt`
SHA-256 `7a846f4b9e13f8c45b43b032bae32bc77f5eda8880f26b066ad678d9f7fc2c02`, and empty
`stderr.txt`. The seven selected source hashes in that receipt match the current
manifest and passed the independent runner-helper check above. It also records the
current fixture callbacks and their source hashes; this does not substitute for
execution of the installed consumers.

The timeout driver derives its expected set from the reviewed runner and manifest,
then checks collection and JUnit sets, count, zero skips/failures/errors, return code,
set digest, installed-origin proof, command evidence, and captured stream sizes and
hashes before authorizing a later profile timeout. The retained owner harness reports
12/12 passing controls, including a same-count wrong node set and removal with a stale
manifest digest. Its complete output is retained at
`LOCAL/q2-packaging/raw/timeout-driver-harness/latest-run.stdout.txt` SHA-256
`ddd9839b927997562245ff6dcab21421eb7395655d3fbf6cb816580b254632db`, and
`latest-run.stderr.txt` SHA-256
`773e42a503bf6493be2d7f084a71eaf3a84cd9f1905ea216404bb996e1bfcc2e`; the JSON report
is SHA-256 `f4b80eb95653256849fb34f08de772c2a158b632eace23ad2f59044c60b5ac20`. I
reviewed these retained results but did not rerun the harness.

As an additional read-only probe, I passed in-memory bad manifests to the real runner
helpers. A stale ID digest was refused with “current primary suite digest differs from
its complete node-ID list”; removing one ID was refused with “current primary suite
count differs from its complete node-ID list”; replacing one selected-source SHA with
zeros was refused with “current primary suite source changed; reconcile ID manifest
first”. No source or manifest bytes were changed for these probes.

The supplement no longer has a second hard-coded primary denominator: it consumes the
`current_primary_suite` field, verifies all 125 primary IDs and the historical subset,
and separately verifies its six selectors. Its input manifest pins the current
runner/primary-manifest hashes and the supplemental test file hash. The 11 declared
force-included assets are unchanged; the retained source preflight checked their
manifest byte counts and hashes against the current Hatch/sdist configuration. Actual
wheel/archive contents and installed asset bytes remain unverified until the package
wave.

## Linux transport delta

The updated transport script is
`LOCAL/linux-profile/raw/final-source-linux-wave.sh` SHA-256
`2549209718b0cbff2ee0a637b96338164d3701a1b71e6dbb4e111d08d4db3a82`. The updated
final transport plan is SHA-256
`b78ad4fffe4c386aa759bf25b7bc0dbb6b9df9bd1f377d980abd5e924a63e327`. The script’s
five current input pins match the inspected files:

| Input | SHA-256 |
|---|---|
| `LOCAL/q2-packaging/raw/run.py` | `c8604c1d0f130cbdb11b4b30814e226df61cc272cf8f2f5a10fa0aeae378d4bf` |
| `LOCAL/q2-packaging/raw/timeout_driver.py` | `7c3413ea3735a8d9732431cd9ca1a3b16e8ac735c2d82a9614479379fa33b073` |
| `LOCAL/q2-packaging/installed-wave-manifest.json` | `26f415a50704a8f555be7c10676e5f427178b150152630140e22b8df054086c6` |
| `LOCAL/q2-packaging/raw/supplemental_run.py` | `4a80f59032665607ff139bf8ed8fbf73e05432f03297b3c82ff78d07d49e5f49` |
| `LOCAL/q2-packaging/raw/supplemental-manifest.json` | `ae2854d95dd2a36283f9bc2a2fcdd24caf0b8712bca92a811ff401112fb4e7df` |

The plan’s opening worker snapshot still names an earlier candidate HEAD/tree
(`7b1b50d…` / `9bad815…`) and explicitly says those are not execution identities. It
is historical resource/preparation evidence, not the current `d12ae0a…` candidate or
a live-worker check at this review point.

The tracked manifest is admitted only when the cloned checkout’s file and frozen Git
blob both match exactly. The other four `raw/` inputs are Git-ignored: the script
copies only absent ignored files, verifies their hashes, reuses exact existing
ignored files, and refuses changed, symlinked, non-file, or non-ignored untracked
destinations. The existing shallow bare-clone → worker object-store copy → attached
`--shared` checkout path checks the requested branch, full SHA/tree, shallow state,
tracked cleanliness, and alternates path; it has no source bind mount or cleanup path.
The worker context/container/image/memory/mount checks remain in the script, but I did
not query Docker or refresh live worker state in this review.

I ran the two permitted shell checks at this candidate: `bash -n` exited 0, and
`self-test-copy-decisions` exited 0 with “Q2 copy decision self-test passed: 8 cases;
no Git/Docker/filesystem changes”. Exact command/exit/stdout/stderr capture is retained
at `LOCAL/linux-profile/raw/independent-q2-delta-checks-20261010.txt`, SHA-256
`970dbc6d54778f87dbae5393175bf0f7ae650e1643dee0b46c0707f0486c09bb`.

P40 classification remains the same transport-input admission class: the 125-ID
manifest expands the bounded current selection while the same tracked-manifest and
ignored-tool admission mechanism handles exact reuse/copy/refusal. The old
`LOCAL/q2-packaging/installed-wave-recipe.md` still describes a 100-ID execution set;
use the current manifest/runner and updated Linux plan as the controlling delta, and
reconcile that older procedure text before treating it as current guidance.

## Remaining boundary

The static selection and transport-input delta is internally coherent at the current
candidate content, but the modified primary manifest is not yet in the frozen Git
blob. The final source freeze must include it and bind the listed five input hashes;
then recheck the live isolated worker and capacity before transport. No transport,
package build, wheel/sdist/GCP archive install, or installed consumer body ran here or
in the retained source-only collection. Actual installed-Q2 verification remains
pending, and no package/runtime closure is claimed.
