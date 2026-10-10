# Common direct-owner mirror tests

Base was `4699fdf8419dd2c89609f68a3edf5f3bfb7c851a`. The three Common source
inputs were read but not changed: `src/polisyos/common/canonical.py`,
`src/polisyos/common/hashing.py`, and
`src/polisyos/common/migrations/_engine.py`. The source hashes before and after
authoring are recorded in the ignored full-denominator receipt.

## P40 classification

This is **NEW** relative to the earlier helper-topology finding: that finding
concerned dependency direction and consumer topology; these tests exercise
properties owned by Common implementations. It remains in the broader P38
mirror-proxy family. A mirrored filename or a facade test can suggest owner
coverage while never invoking the shared implementation with a caller-selected
profile, a heterogeneous stream, or a generic migration profile. The widened
repair is three direct behavioral tests, not three import/count sentinels.

## Added behavioral coverage

- `tests/unit/common/test_canonical.py` invokes Common encode and decode with
  an explicit consumer tag profile and error class. It round-trips nested byte
  data, then proves a nested unadmitted `date` tag is rejected by both paths
  with the caller's exact exception type. This exercises recursive profile
  propagation and does not assert a tag law beyond the API's supplied profile.
- `tests/unit/common/test_hashing.py` checks the streaming digest against
  independent `hashlib.sha256` across three partitions of the same binary
  payload, including `memoryview`, `bytearray`, and an empty chunk. This adds a
  chunk-boundary metamorphic property beyond the existing simple bytes-stream
  example.
- `tests/unit/common/migrations/test__engine.py` calls the generic engine with
  real callbacks. One case checks a two-edge traversal's lookup/apply order,
  version arguments, output, and input isolation. A negative case applies one
  real edge and then verifies that a missing later edge raises instead of
  silently returning a partial migration; the source object remains unchanged.

## Verification and denominator

No pytest command was run; behavioral execution is deferred to the root's
combined slot. The scoped Ruff check, Ruff format check, and Python compile
check passed. Complete stdout, stderr, argv, exit codes, and stream hashes are
under `LOCAL/raw/dx0-common-mirror-4699/`:

- `ruff-check-final.status.json` — exit 0, stdout SHA-256
  `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`.
- `ruff-format-check-final.status.json` — exit 0, stdout SHA-256
  `eee76f865de5a9f2456950f710ae5d5f9b5bd0ea02aa54f614c5eed6642a0bfd`.
- `py-compile-final.status.json` — exit 0, empty stdout/stderr.

The pre-authoring complete denominator contains 2,746 Python source files and
2,902 test files; its manifest SHA-256 is
`037caf84e116869f996a8e4494b0665ca890573240d1b64541cbca2428f18276`. The
post-authoring denominator contains the same 2,746 source files and 2,910 test
files; its manifest SHA-256 is
`aaa49eb90849aeb804fbabdf818900a41351d25f47965cded07e589e679a5b53`. The
baseline comparison records all 11 Python path/hash deltas; three are these
new tests and eight are concurrent worktree changes. It separately confirms
the three Common source inputs are byte-identical before and after. See
`LOCAL/raw/dx0-common-mirror-4699/authoring-delta.json` (SHA-256
`dd4605789c8fa434d01fd35e0c39114184f8947559c8f173ce27bba1edf6cb10`) for the
complete path-level comparison and the test-file hashes.
