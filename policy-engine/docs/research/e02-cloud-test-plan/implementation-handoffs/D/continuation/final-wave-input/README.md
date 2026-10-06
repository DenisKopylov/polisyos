# Final broad-wave harness input snapshot

Prepared only; neither harness nor pytest has been executed for this task.

- Final harness: `/tmp/e02-D-broad-wave-final.py`, SHA256
  `02ff94cbf1f2bc01af5f9687c7a31339802f5cde36cb9829b01f0f182702cd9b`.
- Original preserved: `/tmp/e02-D-broad-wave.py`, SHA256
  `f383a1ff3bd2a22776b914e6d038d6f8883772acc78e051c27bb1db15f5a56e7`.
- Exact two-location diff: `/tmp/e02-D-broad-wave-final.diff`, SHA256
  `c0e6bcea0f82f48be798d3be7067c26b5d006b7f5f7e2b0dd0e5d85bf6241978`.
- Input-scope proof: `/tmp/e02-D-broad-wave-final-input-scope.json`, SHA256
  `776b6930dddc9c66b70ebde2f5510a0c0f795564158be04ea9e7d80ab3ac60b7`.

Both before/after snapshots now include every tracked Python file under
`policy-engine/src/` and `policy-engine/tests/`, plus every existing changed test
input, selected file, helper-subtree input and configuration. The preserved
original harness joins the final harness, original selector planner, original
observer and existing tokenizer files in external input identities.

At source `f2d5401c9cd8a02a74579e4c47b836042a12eb99`, this covers 2,701 product
Python files and 2,860 test Python files. File counts do not imply collected
cases or test outcomes. The final harness re-enumerates the actual supplied
`--source`; root must pass its eventual clean immutable HEAD after reviews and
remaining documentation merges. The original default preparation behavior and
explicit `--run` boundary remain unchanged.

The imported `_bundle` definition in
`tests/unit/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py`
is included independently of whether that module is a selector. The corrected
source-only helper locator is
`/tmp/e02-D-broad-wave-final-bundle-helper-test-only-scope.json`. Its retained
earlier attempt used overly broad OR Git pathspecs; the corrected exact glob
supersedes that locator scope. Neither attempt changed the harness or executed
product code.

Only snapshot admission changed. Selector derivation, pytest arguments,
assertions, backend/interpreter, caps policy, report/result semantics, observer
and standalone-probe boundaries remain byte-identical. No root tracked files,
Git branches, environments or fixture/cache state were changed.
