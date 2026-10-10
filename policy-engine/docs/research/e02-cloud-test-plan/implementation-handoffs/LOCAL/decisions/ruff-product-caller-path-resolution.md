# Ruff product-root caller path resolution

Base: `4699fdf8419dd2c89609f68a3edf5f3bfb7c851a`. Ruff is 0.14.10. This
authoring slice changes only `tools/devx/workspace/tool_configs.py` and
`tests/repo_quality/tools/test_tool_config_split.py`; generated Ruff files stay
with the root owner.

## Diagnosis and P40 bucket

**P40: SAME caller-root path-resolution class, one level deeper.** The earlier
repair normalized operational settings such as `src`, `cache-dir`, `include`,
and `exclude` for the workspace caller. The remaining escape was the complete
family of per-file-ignore globs: the product renderer still translated them
relative to the generated TOML's directory. Ruff resolves these patterns
against the caller's project root. With the documented product invocation
(`--config ruff.toml`), the generated `../../../tests/**` therefore pointed
outside `policy-engine`; the workspace form `policy-engine/tests/**` pointed
at the correct directory. The distinction was masked by automatic product
config discovery, which remained green.

The root's retained exact selector run shows workspace-root Ruff exit 0 and
product-root Ruff exit 1 with 11 `S101` diagnostics in
`tests/unit/calibration/test_adapters.py`. Its complete command and output
receipts are under
`LOCAL/raw/calibration-selector-retirement/canonical-{workspace,product}-ruff.*`.
My additional current-file reproduction used the same four inputs from both
callers: calibration source, its unit test, the tool-config repository test,
and `tools/devx/workspace/tool_configs.py`. Before the change, product-root
Ruff emitted 67 diagnostics (56 `S101`, one `S603`, one `S607`, eight `T201`,
and one `TC003`); workspace-root Ruff emitted none. The two-test comparison
also showed product auto-discovery clean, explicit `--config ruff.toml` with
58 diagnostics, and workspace-root with none. Full streams and argv are in
`LOCAL/raw/ruff-caller-path-resolution-4699/`.

`--show-settings` located the mismatch: the product command's effective
matcher for the tests glob resolved outside the product tree, while the
workspace command resolved it to `policy-engine/tests`. Existing settings
coverage compared auto-discovery with workspace mode, so it missed the
documented explicit product caller.

## Repair and behavioral proof

The renderer now passes an explicit caller-project-root prefix to the common
per-file-ignore fragment renderer. Product-root patterns keep their
product-relative spelling; the workspace caller prefixes the same patterns
with `policy-engine`. The old generated-directory-relative conversion was
removed. This applies uniformly to all nine declared ignore fragments.

The added `test_explicit_ruff_callers_preserve_settings_and_lint_behavior`
uses the real `tool_configs.render_files` output in temporary sibling config
files, so it verifies the implementation without writing root-owned generated
files. It compares Ruff's normalized complete settings and matcher/code maps
for representative source, test, and tool modules, then invokes real Ruff on
the same calibration source/test plus repository-tool test and tool source
under both project roots. Both actual Ruff reports must be empty. The existing
source/test collection comparison remains intact.

The complete selector denominator is nine source fragments, 239 unique
per-file selectors, and 741 selector/code pairs. The retained audit confirms
product and workspace renderings preserve every original selector and code:
`LOCAL/raw/ruff-caller-path-resolution-final/rendered-selector-audit.json`,
SHA-256 `f954a3f34d69197979fad13740444185e81e92de5ffaaf8df1359a52d3d9f293`.
No fragment, rule code, selector, or lint selection changed.

## Verification and root-owned follow-up

The focused new behavioral test and the existing product/workspace settings
and collection test both pass. Ruff check, Ruff format check, and Python
compilation pass for the two changed files. Complete outer command streams,
statuses, and hashes are retained under
`LOCAL/raw/ruff-caller-path-resolution-final/`; the final pytest stdout SHA-256
is `99db33d5c94c6f7da021687c7391181685cc33299c5435b1c861e2db3be3ec87`, Ruff
check stdout SHA-256 is
`82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`, Ruff
format stdout SHA-256 is
`3bc53bf3e981a98a34a852e175bf9b77af841edea74fca595d9aedcbaf9a4938`, and
compile stdout/stderr are empty.

The temp-config Ruff run after the change passed in both callers (each stdout
was `[]`, SHA-256 `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`).
Six complete `--show-settings` streams and their command metadata are also
retained in that raw directory. The tracked generated files remain the
root-owned pre-regeneration versions; after this source slice is accepted,
regenerate them and run `uv run polisyos-tools workspace tool-configs --check`,
then replay the canonical explicit product and workspace Ruff commands against
the same four-input denominator. I did not run the full Ruff tree.

Source hashes: `tool_configs.py` is `e9df75708982521cedcc29f9b3a448054171a03df69f527a1898f5ae6a9d859c`
at base and `34579a6679603d150324760e7cccfd71a4c6da2834f6c33206eda7476579df65`
after the change. The test file is
`edf2313ece29c137a4d2d41571a4753fec4f2278f42d713bee0ed2bc4ab2b511` at base
and `1d57d3ad39ba2cdeddde5bc062ddd530d54dec6647a14a8be5016c265280c69b` after.
