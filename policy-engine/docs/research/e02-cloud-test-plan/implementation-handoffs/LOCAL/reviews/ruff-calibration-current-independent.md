# Independent Ruff caller-root and calibration review

## Scope and source identity

Read-only review of the source supplied by the author at the parent-provided
candidate anchor `4699fdf8419dd2c89609f68a3edf5f3bfb7c851a` plus its working-tree
changes. Git was not invoked, so this note does not independently attest the
branch, tree, parents, or cleanliness at that anchor. The reviewed source bytes
are pinned below; the complete calibration `.py` source and test inventories,
including their per-file hashes, are retained in
`LOCAL/raw/ruff-calibration-review-current/input-hashes.json`
@ `b02ddbc43462b46fcf0996cb8c81cc5a08029cb5ffb19df58acdeec1f2d5bcf8`.

Decision inputs read:

- `LOCAL/decisions/ruff-product-caller-path-resolution.md`
  @ `07a6bb3e39ce6140ab3b23c657c68c3f168e6f60c54d322994a5b22e6ec1a2a2`.
- `LOCAL/decisions/ruff-dead-override-reader-root-resolution.md`
  @ `d6d3826c4c729dc9be78e8ebf8c13803b3bccbfe374d388a74baee18dac21da1`.
- `LOCAL/dx0-native/calibration-annotation-introspection-choice.md`
  @ `42f51e2f3fdbc6f2d0c68d6e5fa953a1e04b11ed69905183fb6d66e18d406684`.

Current implementation and complete source-set identity:

- `tools/devx/workspace/tool_configs.py` @
  `34579a6679603d150324760e7cccfd71a4c6da2834f6c33206eda7476579df65`;
  `tools/ops_runners/reports/dead_overrides.py` @
  `f15fa5f5ff9740f120ef97f7d59e65adc7e53df56c9896b762284833c7b6067d`.
- `tests/repo_quality/tools/test_tool_config_split.py` @
  `9dd1a6804ba71f20a524f2a94c76b3e9b228695d15ed1ecf6f7f11dad5af2ea2`;
  `tests/repo_quality/tools/test_dead_override_report.py` @
  `a4382aed52b0ed5b74cfe7191caa8488f9ba856dddd30ae09fcba7fe9751d7e4`.
- `architecture/tooling/tool_config_split.toml` @
  `719a3ecc341ce589d48faeb3a3d5b54e57eabb7f9b7b12fb4471c106c5f87946`;
  `architecture/tooling/static_analysis_overrides.toml` @
  `f4d240df5fd51f962a4769e6b045e11d9394430cdae49a119cc902af92dd536e`.
- `architecture/tooling/ruff/generated.toml` @
  `20a05c3aa3150bc8badcdab238c03704eba5ef24b6d72ed7ca3b795991fc733c`;
  `architecture/tooling/ruff/workspace_root.toml` @
  `725cd3e08b68a17321e98eb1f073a3b81d1152a54bdb19e9eb36d3a2d21dfb2a`;
  `architecture/tooling/ruff/base.toml` @
  `bb92ee9ba8633aef08fdefbf829f324d18755f499e1c95d26eb2c0fce266dff8`.
- Calibration source reviewed: `adapters.py` @
  `17965e5a8ba0adc4a5065308e1db73f3b2bc8bd4745e24cfaa3fbfec6f06d1d4`,
  `diagnostics.py` @
  `87736e2f931721b24d13cc6c6eb0d5e15cb668e54da2e770a32311559d416e80`, and
  `multiclass.py` @
  `a441c41418e6e39d8604689affd5eb3f64f5a6f4d6d0938e4cbd8263a250376e`.
  The calibration adapter test is @
  `c1fa0e1daf9caded0b4e8a63bfe6104969352a1ceed19daa59ecbd2da9edd345`.

## Caller-root review

The renderer and mandatory dead-override reader now agree on the two modes
declared by the split manifest. The product renderer keeps selectors relative
to `policy-engine`; the workspace renderer prefixes each of the same source
selectors with `policy-engine`, and also prefixes its declared Ruff path/glob
settings. The reader identifies the workspace-generated config through the
static-analysis manifest pointer and split manifest, resolves its project root
from the declared prefix, then normalizes the selected matcher to product-root
terms before liveness and exception-metadata checks. The product config remains
product-rooted. Corrupt Ruff inputs raise before the report can return an empty
selector set, and `tool-configs --check` consumes that report.

The full source denominator is nine `.toml` fragments, 239 unique selectors,
and 741 selector/rule-code pairs, with zero duplicate selectors. The manifest
hash above and each fragment hash/count are recorded in
`LOCAL/raw/ruff-calibration-review-current/source-denominator.json`
@ `ab766114fc751b5f380c3c8a569610ca32341bc2789c9b7097d5c1402002412e`. The
source/test split test compares the complete parsed fragment set against the
reader in both generated modes; its actual output is retained at
`tool-config-denominator-tests.txt` @
`99db33d5c94c6f7da021687c7391181685cc33299c5435b1c861e2db3be3ec87`.

Independent real-Ruff settings probes ran from the product root and workspace
root for three representative paths: calibration source, its unit test, and
the renderer module. All six runs used Ruff 0.14.10, resolved 148 settings and
239 matchers, and normalized to identical settings and matcher/code maps. The
complete commands, per-run streams, hashes, and comparisons are in
`caller-settings-summary.json` @
`4d4b96ba80251ec74a4a1bcd1ee66f1f932e77c72aaf768f142d9412357dcccd` and its
six `settings-{product,workspace}-*.txt` siblings. A separate real-Ruff lint
run checked the calibration package, adapter unit test, both config/reader
repository tests, and both implementation files under each caller. Both
returned exit 0 and `[]`: product output @
`product-ruff-independent.json` and workspace output @
`workspace-ruff-independent.json`, each SHA-256
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.

The complete caller-mode and denominator tests passed (2 tests); the targeted
malformed/missing-config reader tests passed (5 parameterized cases). The
registered read-only generator check exited 0. Their output files are
`tool-config-denominator-tests.txt`, `dead-override-failclosed-tests.txt`
@ `4d2df7a96ce4a667da3ccf295f2d16c728a65ed0e861a3baa919f7bb469b02b5`, and
`tool-configs-check.txt` @
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Malformed TOML, malformed `[lint]`/`per-file-ignores` tables, invalid rule-code
values, missing Ruff config, and missing Mypy config fail closed through the
tested reader/CLI paths. The zero-byte generator output is consistent with a
clean `--check`, not a standalone capability proof.

**P40 bucket:** these root-resolution escapes are the same class at the
renderer and reader layers, as the two author decisions describe. The current
mechanism covers both declared generated caller roots and the full current
selector set; I found no further escape in that bounded family and request no
third one-field repair. Arbitrary non-manifest Ruff config paths are still
treated as product-root by design. That is the decision's explicit residual;
there is no declared third generated mode or current evidence requiring an
arbitrary-config caller-root option.

One initial workspace lint invocation mistakenly addressed `.venv` from the
workspace root and failed with shell status 127 before Ruff started. Its exact
51-byte output is preserved as `workspace-ruff.json` @
`e85b0cf43d10e96fca984acdc22f6a26f0cf5842e74c048865aa30307745d6b3`; it is a
tooling invocation error, not a product result. The corrected command uses
`policy-engine/.venv/bin/python` and produced the empty result above.

## Calibration Ruff-scope review

The whole-package census walks all nine `src/polisyos/calibration/**/*.py`
files and all seven `tests/unit/calibration/**/*.py` files. It finds zero
selectors rooted at `src/polisyos/calibration/`, zero calibration package
scopes in `static_analysis_overrides.toml`, and zero duplicate selectors in
the nine-fragment input. The one selector containing the word `calibration`
targets `src/polisyos/data_forge/domains/ukraine/builders/calibration.py`; it
is not a package-level calibration exception. The census output and all input
hashes are the raw files cited above, not a sampled search result.

The three scoped source changes remove the six-code package suppression by
typing report `expected`/`actual` values as `object` and adding strict parallel
array zips at the relevant calibration boundaries. With `lint.per-file-ignores`
overridden to `{}`, the exact six-rule selection
`ANN401,B905,E501,RUF005,TC001,TC003` passes across the full calibration source
tree. All 66 unit tests pass. The `--ignore-noqa --select TC001,TC003` removal
control returns seven type-import diagnostics, so the current line-local type
exceptions are material to that broader selection. Ruff no-package-ignore
output: `calibration-no-package-ignore-independent.txt` @
`82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`; removal
control: `runtime-import-removal-independent.txt` @
`8c60d7bc592e907874e572eb5cbdd7a2dab1907eba64a1967af1b2111de1ec70`; package
unit output: `calibration-unit-tests.txt` @
`c3f10a075adace0c7a32194c3773838ef13ba5e6a0b346089fcca6d53d5fb848`.
The eight-file formatting check reported `8 files already formatted` in
`format-check.txt` @
`8e93d18ae56550d4eef2feac77e6630617c7e169246e56e39c75d58b46167985`.

The public runtime annotation property is demonstrated for
`evaluate_binary`, `evaluate_multiclass`, and `to_validation_report`; the
existing public test and direct hint probe both resolve all three. However,
`adapters.py` also keeps `CalibrationDiagnosticIssue` at runtime with the
comment “public report annotations,” while its sole annotation use is the
private `_diagnostic_issues` helper. Removing that one binding in an isolated
process leaves public `get_type_hints` at 3/3 but makes
`get_type_hints(_diagnostic_issues)` raise `NameError`. The actual removal
probe is `public-hint-removal-control-independent.txt` @
`2f004e7885efdf9e63adaa41aaeb802ee8ba9c527d49c855b2cb784eba536c9e`; direct
public hint output is `runtime-public-type-hints.txt` @
`2fc01efec89663402205d6dc6420537983efaf396a3751c86013d72adf7ce1fa`.

**P40 bucket: NEW_CLASS, low/non-blocking.** This is a scope mismatch in the
stated runtime-introspection exception, not a caller-root escape or a reason
to restore any package suppression. The current public contract needs
`Mapping`, `Sequence`, and `CalibrationDiagnosticsReport`; it does not need
the private helper's `CalibrationDiagnosticIssue` binding. The owner should
either narrow that import to type-checking-only or explicitly declare and test
private-helper runtime hint resolution. No second finding of this class was
observed, so this does not trigger a repair ladder.

The source census currently reports 4,131 physical lines across the same nine
calibration source files. The calibration annotation decision records 4,115
lines for its earlier state. This is a **P35 stale denominator** in that
decision evidence; update its current count/hash before using it as a freeze
denominator. It does not invalidate the full-directory lint or 9-file census.

## Exact commands and evidence limits

All commands ran with the candidate product `.venv`, Ruff 0.14.10, and the
stated working directories. Full stdout/stderr or JSON is under
`LOCAL/raw/ruff-calibration-review-current/`; the raw files are ignored and
remain local.

```sh
# Product root
.venv/bin/python -m ruff check --config ruff.toml --no-cache --output-format=json \
  src/polisyos/calibration \
  tests/unit/calibration/test_adapters.py \
  tests/repo_quality/tools/test_tool_config_split.py \
  tests/repo_quality/tools/test_dead_override_report.py \
  tools/devx/workspace/tool_configs.py \
  tools/ops_runners/reports/dead_overrides.py

# Workspace root
policy-engine/.venv/bin/python -m ruff check \
  --config policy-engine/architecture/tooling/ruff/workspace_root.toml \
  --no-cache --output-format=json \
  policy-engine/src/polisyos/calibration \
  policy-engine/tests/unit/calibration/test_adapters.py \
  policy-engine/tests/repo_quality/tools/test_tool_config_split.py \
  policy-engine/tests/repo_quality/tools/test_dead_override_report.py \
  policy-engine/tools/devx/workspace/tool_configs.py \
  policy-engine/tools/ops_runners/reports/dead_overrides.py

# Complete split-config caller/selector checks
PYTHONPATH=src:. .venv/bin/python -m pytest -q \
  tests/repo_quality/tools/test_tool_config_split.py::test_phase5_5_tool_config_split_generated_files_are_current \
  tests/repo_quality/tools/test_tool_config_split.py::test_phase5_5_dead_override_report_covers_both_generated_ruff_roots

# Malformed/missing reader controls
PYTHONPATH=src:. .venv/bin/python -m pytest -q \
  tests/repo_quality/tools/test_dead_override_report.py::test_dead_override_cli_fails_closed_for_corrupt_ruff_config \
  tests/repo_quality/tools/test_dead_override_report.py::test_dead_override_cli_fails_closed_when_ruff_config_is_missing \
  tests/repo_quality/tools/test_dead_override_report.py::test_dead_override_cli_fails_closed_when_mypy_config_is_missing

# Read-only generated-file and override validation
PYTHONPATH=src:. .venv/bin/python -m tools.cli workspace tool-configs --check

# Whole calibration tree with package/per-file ignores removed for this selection
.venv/bin/python -m ruff check --config ruff.toml \
  --config 'lint.per-file-ignores={}' --no-cache \
  --select ANN401,B905,E501,RUF005,TC001,TC003 --output-format=concise \
  src/polisyos/calibration

# Removal control: prove which imports are suppressed only by line-local noqa
.venv/bin/python -m ruff check --config ruff.toml \
  --config 'lint.per-file-ignores={}' --no-cache --ignore-noqa \
  --select TC001,TC003 --output-format=concise src/polisyos/calibration

PYTHONPATH=src:. .venv/bin/python -m pytest -q -ra tests/unit/calibration
```

The direct `--show-settings` commands, all six complete settings streams, the
three exact representative targets and normalized comparisons are recorded in
`caller-settings-summary.json`. The removal-hint probe and its full output are
also retained as described above. No full-repository Ruff run or expensive
native/backend wave was performed. This is an independent scoped code review,
not G acceptance, integration publication, or formal closure adjudication;
no formal closure IDs are proposed here.

## Independent delta review: generated-root discovery and package source input

This section is a separate read-only review of later WIP source at the
parent-provided candidate anchor `4699fdf8419dd2c89609f68a3edf5f3bfb7c851a`.
The earlier two-mode review above predates this delta; its caller-root evidence
does not cover the newly root-colocated generated config or automatic
product-root discovery. Git was not invoked, and no G decision or acceptance
is inferred from earlier review/checkpoint state.

Current byte identities read for this delta:

- `ruff.toml` @ `8887d0a15457d44ebb1a5b5aee8110dd5101dc9e952649cd0490b845af2d933e`;
  root-colocated `ruff.generated.toml` @
  `51dd7d4fb4937537d815e7b791541c9f09b0b9f413ec06e6c69b221c0096d64f`.
- `tools/devx/workspace/tool_configs.py` @
  `a22695d7ccaca53944507c0d4488f7d93da0464266555ed394da150499996cec`;
  `tools/ops_runners/reports/dead_overrides.py` @
  `f15fa5f5ff9740f120ef97f7d59e65adc7e53df56c9896b762284833c7b6067d`.
- `architecture/tooling/tool_config_split.toml` @
  `17d19ddf53af4e7489e1a93425cd5eff578e9c08644652f934bc4163462b41db`;
  `architecture/tooling/static_analysis_overrides.toml` @
  `12f3aca9f1471287ffc16264ab3e234eaa1437db917a35607b08218a7ad3db29`.
- `architecture/generated_artifacts.toml` @
  `0a79005a1d37c38ea759509215205284698b4bb12ecabb42c29e70196486eb6a`;
  `architecture/gates/report_only.toml` @
  `02971152f582939d9db782406d08544b5b1120005a57f709e548af6ca839a281`.
- `tools/ops_runners/README.md` @
  `529fbb135c2c7f93c7e96ad85b9f0e8e67a356e9d6225eaf764fce939dc21c9d`;
  `tests/repo_quality/tools/test_tool_config_split.py` @
  `bef087036c1b22696ecbaa2e5492a611843554e65fbaf1647f58a026ff4be3da`.

The current manifest says `root_config = "ruff.toml"` and
`generated_config = "ruff.generated.toml"`. The renderer now rejects a
non-colocated generated path and emits the root stub extending that generated
file. That constraint addresses Ruff's caller-root matcher behavior at the
structural boundary: discovery and explicit product-root calls see the same
product-relative selector basis, while the separately generated workspace
config keeps its workspace prefix.

The source-bound mode witness covers all three actual invocations:

1. Product-root automatic discovery, with no `--config`.
2. Product-root explicit `--config ruff.toml`.
3. Workspace-root explicit
   `--config policy-engine/architecture/tooling/ruff/workspace_root.toml`.

For each mode, real Ruff was given a temporary source file containing an
`assert` under a source path that has no S101 exception and a test file whose
S101 exception is selected by the real per-file matcher. The source control
returned exactly S101 (exit 1); the test control returned `[]` (exit 0). The
temporary source fixture is absent on readback. Thus both rule activation and
the intended path-specific exception are exercised under each caller, rather
than inferred from config markers or a successful exit alone. Each command,
full stdout/stderr, expected exit, and code list is retained under
`LOCAL/raw/ruff-three-caller-final-verification/`; the command receipts are
the `*-source-negative.command.json` and `*-test-positive.command.json` files.
The three source-negative stdout streams share SHA-256
`1a90abd5eac755c2e7e410ff617e9cb4ef71323d87befd19cc2883f4751ded09`; the
three positive streams share SHA-256
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`. Normal
Ruff runs on the declared test input also passed in all three modes.

The complete selector census was independently rerun against the updated
manifest. It remains nine fragments, 239 unique selectors, 741 selector/code
pairs, zero duplicate selectors, zero calibration-package selectors, and zero
calibration package scopes. Current output is
`LOCAL/raw/ruff-three-caller-final-verification/selector-denominator-current.json`
@ `ac2bf7779da71d7400c3f88a25ec66a39cce355b365800b8e73440c338c53a54`; all
nine fragment hashes are in that file. The independent census command was
`.venv/bin/python docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/ruff-calibration-review-current/source-denominator.py`
from the product root; stdout was redirected to that JSON file and stderr was
empty. The dead-override report reads the new
root generated config at the product root, counts 988 entries (749 Mypy, 239
Ruff), and reports zero stale paths and zero missing metadata. Its command and
report are `dead-overrides.command.json` and `dead-overrides.json`; report SHA-256
`2982f24ed9b72882b2f2941516963fca0eb7b33ad2b21d3f118eef9782553c7c`. The
generated-config check returned 0 with empty stdout/stderr. The focused
14-test receipt passed in 2.96 seconds. Full command/output hashes are in
`focused-pytest.command.json` and `focused-pytest.stdout` @
`2f4f1502823e372d2197bb2e7e93536d6f036591a95e8d47fc98f8d6bd2adc08`.

**P40 bucket: SAME_CLASS_DEEPER, now closed for the three declared caller
modes by the root-colocation invariant and source-path controls.** This is the
root-discovery continuation of the same caller-root/path-resolution property.
I found no mode among the three exercised whose behavior lacks a distinguishing
witness. The previously documented arbitrary non-manifest config path remains
a bounded residual outside the declared split-manifest modes.

### Package archive contract

The root generated config is an operational Ruff config for product-source
checkouts and source archives. `hatch.toml` @
`7e64dca82df9308d6af77d7b329dcd93f6062dee6db90ee5ef140fa0643f1133` explicitly
includes both `ruff.toml` and `ruff.generated.toml` in the sdist. The root stub
extends the generated file by basename, so those two archived members close
the generated-config reference. `pyproject.toml` @
`b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267` keeps
Hatchling as the build backend. The wheel package list remains only
`src/polisyos` and `tools`; these root lint configs are not runtime wheel
resources. The workspace-root config and split fragments are repository
inputs, not claimed sdist or wheel consumers.

`tests/repo_quality/tools/test_hatch_packaging.py` @
`b8303c577f02208f7b04268d878a5ca8e466caa30d4c2cd32e1852bdf0d5cfa9` contains
the actual Hatch archive contract: it checks sdist inclusion of the root
generated config, rebuilds a wheel from the extracted sdist, and compares
wheel members. That builder test was not run in this delta because this review
was scoped away from archive builds. Therefore the configuration-level sdist
membership is covered, but actual wheel/sdist archive bytes and rebuilt-sdist
consumer behavior remain **UNRUN**; do not treat them as a package receipt.

### Calibration follow-up readback

The author narrowed `CalibrationDiagnosticIssue` to a `TYPE_CHECKING` import in
`adapters.py` @
`602144bdf6d7ef099a44d8b4b6f4fc0f75bc996859488d0b7d87d4b1a54df0c1`, matching
the explicitly public-only introspection property. The updated decision
`calibration-annotation-introspection-choice.md` is @
`c3f0ef48ab3c10666b546ed7abd6becd64b1bb26c3bf763785f900c00b6561fb` and now
states that the private helper's `get_type_hints` behavior is not promised.
The prior NEW_CLASS note above is resolved in this later source; the new
current-state evidence has 3/3 public hints, a passing focused six-rule
no-package-ignore selection, and 3 passing adapter tests. The six-diagnostic
`--ignore-noqa` removal control is intentionally red and consists of the six
remaining public annotation import exceptions. Full outputs and command
metadata are in `LOCAL/raw/calibration-annotation-followup/receipt.json`
@ `141c2482aa72316919a60bf3591a5ee3c71906f644c84a6d5033d845d5ee885c`.
The denominator packet `calibration-source-denominator-current.json` is @
`5fb1b7bcbf07a9eccfb1320d38697a424dc134fe81e06d0363bb9590af695345` and
records nine files / 4,133 lines; the updated decision now matches that count.
This resolves the P35 count mismatch from the earlier section.

No source changes, test edits, or heavy package builds were performed by this
reviewer. The source receipts support the three declared caller modes and the
config-level sdist member policy; they do not substitute for the still-UNRUN
byte-level archive/rebuild checks or formal G acceptance.
