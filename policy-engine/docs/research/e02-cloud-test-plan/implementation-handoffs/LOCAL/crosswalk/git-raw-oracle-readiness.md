# Actual Git/raw admission oracle readiness

This receipt records a source/raw helper oracle for the committed candidate
`012b53def6aa47dba02a906242af10bb495f9b84` (tree
`5f87c7d970a970403f503ebaf228076327be05cc`), descended from the original entry
`93d6aa62a8d236667fdf322a5fc17962523b185e` (tree
`c3a38aecbab5af06c8aed1ae27d535c7e2dc8eca`). It is not a final source/input/
backend freeze and does not evaluate runtime properties.

The ignored harness is
`LOCAL/raw/q0_actual_git_raw_oracle.py`, SHA-256
`94c308e7c6e0451db4785d5d6fc4ff5c1dfa577620a9b87a7c21f28b2bf4505b`. Its exact
invocation was:

```text
/opt/homebrew/opt/python@3.14/bin/python3.14 policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/q0_actual_git_raw_oracle.py --candidate-commit 012b53def6aa47dba02a906242af10bb495f9b84 --candidate-tree 5f87c7d970a970403f503ebaf228076327be05cc
```

It required the explicit commit/tree pair, compared the worktree emitter and
self-test bytes with `git show`, derived the complete source-path census from
Git, and exercised the current validators without replacing Git/raw calls.
The candidate source hashes were:

| Candidate file | SHA-256 |
| --- | --- |
| `LOCAL/emit_proposals.py` | `4d5e70c67f62af07cdb7d3313ad3caa2a689172888b44051c13bb07e6dbbacec` |
| `LOCAL/crosswalk/test_admission_proof_bindings.py` | `fd3a83ebaa91d0e0dae384c26d06055029c4fe3ddee1aee325654f247ed0eff7` |
| `policy-engine/pyproject.toml` | `b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267` |
| `policy-engine/uv.lock` | `e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463` |
| `policy-engine/.gitignore` | `77274a4c3534450075f1a95890b59cbacb17ee2a914de3d24916ca308626723c` |

The recorded lightweight command ran the seven admission proof-binding checks
under CPython 3.14.0 on Darwin 27.0.0/arm64. Its exact argv, cwd, outputs,
hashes, import origins, candidate-bound backend manifest, and all control
results are in
[`oracle-summary.json`](../raw/q0_actual_git_raw_oracle/20261010T013210654324Z-ea5e7292/oracle-summary.json)
and sibling raw files. The test command exited 0 and wrote
`7 admission proof-binding checks passed` (stdout SHA-256
`477530e8dc0f1ddae059b589a7448a7983bc5fdb3bc09a3b98c23c22e2f30cb1`; empty
stderr SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).
That seven-check file contains fixture mocks; it is only the light self-test
command, not the basis for the actual Git/raw positive claims below.

The real helper calls accepted a canonical local environment manifest after
opening its ignored bytes and reconciling their digest, profile, command row,
configuration/lock source refs, and complete selected-input denominator. The
manifest is explicitly scoped as `python-source-checkout-oracle` /
`global-cpython-3.14-source-only`; its selected input list is empty only for
this source-only helper test. It is not evidence of the locked ML runtime or
any production-input property. The harness also accepted the actual candidate
source footprint subset, actual ordered Git parents/ancestry, and the pinned
B194 coverage locator. For B194 it recomputed the original source span at
`B_r19_original.md` lines 4792–4801 and matched the source criterion SHA
`47058d366d7ff7e11ed2348e96b2f56659a999f1f0839a02edc92804b295711e`.

Nine real mutation controls rejected as expected: incorrect raw manifest
digest; rehashed but changed profile identity; rehashed command-output hash;
rehashed candidate configuration hash; rehashed selected-input denominator;
rehashed selected-input set; unavailable raw output; path traversal; and a
symlink raw output. Full rejection text is preserved in the raw summary. These
controls exercise the current `validate_backend_environment_manifest`,
`validate_local_raw_output`, source-footprint, Git-relationship, and pinned
evidence helpers against actual Git objects and filesystem bytes.

The whole-v2 component path also passed on a transient, non-persisted object:
handoff shape, actual candidate/base/parent binding, actual footprint and
manifest checks, and the pinned B194 documentary prototype-plan source. That
row remains `UNRUN` and says no prototype result is asserted. The object has
`formal_closure_ids: []`; it was not written as a receipt and generated no
occurrence evaluation. The final `validate_typed_slice_receipt` Git/show seam
could not pass positively without a committed direct-child report. The
candidate tree contains one direct-child v2 report,
`LOCAL/native-source-b194-pilot.json`, bound to the earlier `9e02a9f...` source
boundary and lacking the now-required `environment_manifest_ref`; the actual
strict validator rejected it for that field mismatch. There are zero
committed strict v2 receipts bound to this candidate. No receipt was fabricated
to bypass that source boundary.

Raw oracle files are retained under
`LOCAL/raw/q0_actual_git_raw_oracle/20261010T013210654324Z-ea5e7292/`. Its
`oracle-summary.json` SHA-256 is
`df9a93bb884a3189b832292b2b25563d7d85618a4bf47f22e419317ef956009f`. The
directory contains exact command stdout/stderr, the canonical manifest,
loaded-import-origin record, generated runner and hashes, control outcomes,
and the invocation summary. No production payloads were read; no fits, full
suite, source mutations, proposal outcomes, or G decisions were run.
