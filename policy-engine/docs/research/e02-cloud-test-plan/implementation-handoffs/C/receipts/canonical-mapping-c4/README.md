# CAN C4 JSON-mode Mapping handoff receipts

These receipts support the bounded C-owned Mapping compatibility change in
current-canonical-json-mapping-20261007.json. They bind to source candidate
`e3cb3fafc847b94a5d4b3adc03b814b4c711920c` / tree
`2d27c9c182cf550088c5a8c072dc2f36df84e20d`. The original criterion base remains
`198076863e143dea9f89f02734b13d50dae3eed5`; the immediate C4 source base is
`79cbb05c90026973a32022ca02c63877b2cde1a5`.

The implementation accepts a JSON-mode manifest Mapping whose separators value
is exactly a two-string list, normalizing only that field before strict profile
validation. The complete manifest remains unchanged. The candidate's final
frozen-source selector passed 46 tests, and the independent review returned GO
for this Mapping-intake property. The full LA-021 criterion remains HELD with
`closure_ids: []`.

The B-owned Core-to-IR byte boundary is unresolved: no ratified byte-emission /
admission supplier contract or profile decision was found in the reviewed
inputs, and no cross-boundary proof establishes that all Core writes consumed
as IR JSON pass through the shared canonical writer or are intercepted. A
direct Core `put_json` path can persist `float_hex` metadata under the same
canon name/version while the IR decoder refuses that profile. The typed
`verification_missing` state refers to the absent cross-boundary proof; it does
not imply that a supplier contract already exists. Historical profileless
support also remains unestablished. C4 changed no B-owned paths and did not
update the C54/closure ledger.

Receipt groups:

- `final46/` contains the frozen-candidate command, pre/post source and selector
  input snapshots, complete stdout/stderr, exit code, and JUnit XML.
- `mapping-red/` contains the test-first positive reproduction against the
  pre-fix source; the expected failure shows strict tuple validation rejected
  the actual JSON list before payload bytes were read.
- `independent/` contains the original reviewer report, focused 14-test output,
  actual temporary-CAS oracle source/output, and normalizer-removal control. The
  original reviewer did not emit JUnit XML or separate stderr captures for its
  focused tests or oracle; `capture-status.json` records that boundary rather
  than fabricating outputs. `independent/root-capture/` separately contains the
  complete root-side replay of the exact oracle at docs-only HEAD `519b6739`:
  exit 0, empty stderr, unchanged source/probe hashes, and stdout matching the
  original oracle output SHA-256
  `86d1657265d680b6ad226db794e3d80dd5b9f9f43240563d874b057acac30ba0`.
- `diagnostic/default-docs-diff-check.json` preserves the full default
  `git diff --check` result for `519b6739^..519b6739`: exit 2 with 17 captured
  output whitespace warnings across 34 stdout lines. The payload captures remain byte-exact. Root
  separately reported the frozen source candidate check at `e3cb3faf` as exit
  0. A supplemental check with blank-at-end-of-line whitespace disabled is not
  a default full diff-check pass.
- `author/` preserves the earlier author Ruff and release-fragment TOML
  wrapper output, which did not preserve separate stderr or numeric exit-code
  fields. `author/root-ruff.json` is a distinct complete Root capture of the
  scoped Ruff check: exit 0, full stdout/stderr, and equal before/after source
  hashes for the frozen e3 candidate. It did not rerun tests.
- `diagnostic/production-invocation.*` holds only the compact
  production-invocation command/stdout/stderr. The 170,895,992-byte JSON
  diagnostic stays in ignored local raw storage at
  `.tmp/e02-C4/raw/canon/production-invocation.json` (SHA-256
  `85080d3fdc1cac8b4d9d675f2a9c04f7fda64f2fd80738966dcf7cdf240cac26`). Its
  captured CLI exit is unknown; stderr includes an interrupted XLA GC callback;
  its source digest differs from the frozen candidate. It is not candidate-bound
  acceptance evidence and does not establish runtime invocation.

The earlier author 43-test run plus later three-case test run is not used as a
frozen-candidate result. The final 46-test run is the bound author result.
