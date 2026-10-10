# Ruff dead-override reader root resolution

Date: 2026-10-10  
Owner: team-devx  
State: implementation and focused verification complete; awaiting root review/commit.

## P40 disposition

This is the **same caller-root resolution class one level deeper**, and the second
finding in that class. The earlier repair aligned emitted product/workspace Ruff
patterns. The report reader still treated the generated config's directory as the
matcher root. I widened the mechanism across the two declared generated modes:
product config → product caller root, and workspace config → the workspace root
derived from the manifest's `workspace_root_prefix`. Both resolve to product-root
subjects before liveness and lifecycle-metadata checks. Further path-root reports
for these two declared modes are covered by this mechanism rather than another
one-field repair round.

The bounded residual is arbitrary, non-manifest Ruff config paths: the report
command treats those as product-root caller paths. The smallest extension would
be an explicit caller-root option for arbitrary configs; that option does not
exist in this command, and no such third mode is declared by the current split
manifest.

## P38 property and divergence

The property is that the report evaluates the same file matcher Ruff applies for
the selected caller mode. The old implementation joined the matcher to
`config_path.parent`. A generated workspace matcher such as
`policy-engine/src/polisyos/...` therefore became
`architecture/tooling/ruff/policy-engine/src/polisyos/...`, even though Ruff's
actual workspace project root is the Git root. That is the divergent case that
produced phantom stale-path and missing-metadata findings.

The reader now identifies the workspace-generated config through the
`static_analysis_overrides.toml` manifest pointer and
`tool_config_split.toml`'s declared workspace config/prefix. It resolves each
matcher from that caller root, then normalizes it to the product root used by
the repository index and exception metadata. `configs.ruff_project_root` records
the resolved root. Missing configs, invalid TOML, invalid `[lint]` or
`[lint].per-file-ignores` shapes, and non-list rule-code values fail closed. The
standalone report writes `status = "failed"` and exits 2; the generator's
programmatic report consumer propagates the error and cannot turn it into an
empty selector set.

## Complete selector denominator

The denominator is the nine `.toml` fragments declared by
`architecture/tooling/tool_config_split.toml` (SHA-256
`719a3ecc341ce589d48faeb3a3d5b54e57eabb7f9b7b12fb4471c106c5f87946`):

- `architecture/tooling/ruff/per-file-ignores/10-tests-ir.toml` @
  `e6a9a107b15f46ead1037d523c959a26184652ccf4f4753d68fbbc189386a37e`
- `architecture/tooling/ruff/per-file-ignores/20-core.toml` @
  `c698be7d58b79075bb3f694f6d837fbf95884559e5f93484383ea34dcefd0627`
- `architecture/tooling/ruff/per-file-ignores/30-foundry.toml` @
  `9fa270ceace16dd90dd58526e5291db0379374cbe86c36ffe00787cfbc8198e5`
- `architecture/tooling/ruff/per-file-ignores/40-data-forge.toml` @
  `c977c0ec941c01a16401382ba885207757982e29e802ad045928c43bd824d2a5`
- `architecture/tooling/ruff/per-file-ignores/50-fabric.toml` @
  `28bd69ad56701716e34661b64726c6c909d464ea761f9502ac338508474fbbaf`
- `architecture/tooling/ruff/per-file-ignores/60-lex-scholar.toml` @
  `a398854b0b7967295f51942732a8dd572e980c72e76be61373f14dc664bcc058`
- `architecture/tooling/ruff/per-file-ignores/70-scientist.toml` @
  `eac3321bd9360e14af47d443cf7d573046ba884b213850b05d651c6e98ee9796`
- `architecture/tooling/ruff/per-file-ignores/80-runtime-core-ir.toml` @
  `625018f94f8b1a7a2c46061f09d8666e93da7e39f744553df7dca40f85312b71`
- `architecture/tooling/ruff/per-file-ignores/90-repository-tools.toml` @
  `cfd8522cf3c6ee9ea46873d6f9a7954eaeb079eaacefdc8b43bc964286b77d95`

A `tomllib` replay over all nine source files found **239 distinct selectors and
741 selector/rule-code pairs**. The new split test compares the complete parsed
source selector set with the reader's normalized entries from both generated
configs; it checks each live path through the report's real existence logic and
requires zero stale and zero metadata findings in both modes.

## Evidence

The pre-repair post-generation report is retained at
`LOCAL/raw/ruff-caller-root-regeneration/generated-check.report.json` (SHA-256
`d134bdd6e0f7a625bad9c9cc40c88f43c7ee77408bd59b6c686eef3d6c5244ec`): 239
`ruff-override-path` and 32 `override-metadata` findings. This was the introduced
reader companion failure in the caller-root repair batch, not an inherited red;
no P41 disjoint-base claim is made.

The post-repair report command outputs are retained under
`LOCAL/dx0-native/raw/ruff-reader-repair-closeout-20261010/`:

- Product-config report: exit 0, 988 overrides (749 mypy, 239 Ruff), zero stale
  paths and zero metadata findings; report SHA-256
  `abc2d5b901efb0e6092ab541dbf2c1d9bab484040616e48f829b4c712dd058df`.
- Workspace-config report: exit 0, same 988-entry counts and zero findings;
  its recorded `configs.ruff_project_root` is the Git workspace; report SHA-256
  `e5f1545ec7f550d20f65e9c084fc93112a7efcd3dddf21b1f2bde2b7be65533f`.
- The actual registered `polisyos-tools workspace tool-configs --check` returned
  0 with 7 generated files, zero drift findings, and zero override findings;
  report SHA-256
  `a71bc864eac8451c07c9c8241fba92372c9a02fe576fe8ce2877b8bdc024584a`.
- Product-root and workspace-root Ruff lint runs on the touched source/tests
  both returned 0. The raw command records and complete stdout/stderr are in the
  same `raw/ruff-reader-repair-closeout-20261010/` directory.
- Focused tests passed: `test_dead_override_report.py` (9 tests) and the actual
  Ruff-mode plus complete-reader-denominator selection from
  `test_tool_config_split.py` (2 tests). The report test now includes eight
  cases: malformed TOML, malformed table, invalid code-value shape, missing
  config, and the actual `tool_configs.override_report_findings` consumer all
  fail closed.

The complete command/stream hashes are recorded in
`LOCAL/dx0-native/raw/ruff-reader-repair-closeout-20261010/commands.json` (SHA-256
`ecf9b2c778758b65d50a2d57a9b1143d84db74b9b66ab70d41aec0ceb785a9eb`); tracked
source and manifest inputs are cited by path rather than copied. The independent
full-mode Ruff caller receipts are in
`LOCAL/raw/ruff-caller-root-regeneration/product-ruff.command.json` and
`workspace-ruff.command.json` (both exit 0).

Changed-file content hashes at this closeout: `tools/ops_runners/reports/dead_overrides.py`
@ `f15fa5f5ff9740f120ef97f7d59e65adc7e53df56c9896b762284833c7b6067d`;
`tests/repo_quality/tools/test_dead_override_report.py` @
`a4382aed52b0ed5b74cfe7191caa8488f9ba856dddd30ae09fcba7fe9751d7e4`;
`tests/repo_quality/tools/test_tool_config_split.py` @
`9dd1a6804ba71f20a524f2a94c76b3e9b228695d15ed1ecf6f7f11dad5af2ea2`;
`architecture/tooling/static_analysis_overrides.toml` @
`f4d240df5fd51f962a4769e6b045e11d9394430cdae49a119cc902af92dd536e`.

## Pattern and scope

Relevant rows: P38 (the reader measured config-file location instead of Ruff's
caller root), P40 (same class at the next layer; widened over both actual modes),
and P35 (the 239/741 claim comes from all nine declared TOML fragments). No
selector, rule code, expiry, exception scope, or generated Ruff file changed.

This patch does not certify a complete per-file read receipt for the report's
repository index; the report now records its selected Ruff root, but its broader
read-set disclosure remains outside this scoped caller-root repair.
