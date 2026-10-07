# CAN C4 JSON-mode Mapping handoff receipts

These receipts support the bounded C-owned Mapping compatibility change in
current-canonical-json-mapping-20261007.json. They bind to source candidate
e3cb3fafc847b94a5d4b3adc03b814b4c711920c / tree
2d27c9c182cf550088c5a8c072dc2f36df84e20d. The original criterion base remains
198076863e143dea9f89f02734b13d50dae3eed5; the immediate C4 source base is
79cbb05c90026973a32022ca02c63877b2cde1a5.

The implementation accepts a JSON-mode manifest Mapping whose separators value
is exactly a two-string list, normalizing only that field before strict profile
validation. The complete manifest remains unchanged. The candidate's final
frozen-source selector passed 46 tests, and the independent review returned GO
for this Mapping-intake property. The full LA-021 criterion remains HELD:
closure_ids is empty; the raw Core writer/admission boundary and historical
profileless support are not established.

Receipt groups:

- final46/ contains the frozen-candidate command, pre/post source and selector
  input snapshots, complete stdout/stderr, exit code, and JUnit XML.
- mapping-red/ contains the test-first positive reproduction against the pre-fix
  source; the expected failure shows strict tuple validation rejected the
  actual JSON list before payload bytes were read.
- independent/ contains the reviewer report, focused 14-test output, actual
  temporary-CAS oracle source/output, and the normalizer-removal control result.
  The reviewer did not emit JUnit XML or separate stderr captures for those two
  commands; capture-status.json records that boundary rather than fabricating
  files.
- author/ records the Ruff and release-fragment TOML command/output observed
  during author verification. The short command wrapper did not preserve separate
  stderr or numeric exit-code fields.
- diagnostic/ holds only the compact production-invocation command/stdout/stderr.
  The 170,895,992-byte JSON diagnostic stays in ignored local raw storage at
  .tmp/e02-C4/raw/canon/production-invocation.json (SHA-256
  85080d3fdc1cac8b4d9d675f2a9c04f7fda64f2fd80738966dcf7cdf240cac26).
  Its captured CLI exit is unknown; stderr includes an interrupted XLA GC callback;
  its source digest differs from the frozen candidate. It is not candidate-bound
  acceptance evidence and does not establish runtime invocation.

The earlier author 43-test run plus later three-case test run is not used as a
frozen-candidate result. The final 46-test run is the bound author result.
