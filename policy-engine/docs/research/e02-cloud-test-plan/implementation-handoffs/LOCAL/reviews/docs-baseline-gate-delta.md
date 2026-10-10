# Q1 docs-freshness baseline gate review

## Result

The current zero-debt path is behaviorally sound on the reviewed tree: the native accuracy checker reports exactly zero violations over 475 published Markdown pages, exits successfully, and the baseline command passes despite the baseline's historical expiry. A real broken-docs fixture with the same zero-count baseline fails. The closeout subgate also passed and retained its exact raw child streams, command, exit code, and per-stream hashes.

One bounded P38 concern remains for the *positive* baseline path: the gate hashes decoded, newline-normalized `stdout + stderr` text, rather than a framed pair of exact stream bytes. A behavioral probe shows that a changed stdout/stderr partition and changed raw CRLF bytes can still produce the expected positive-baseline digest and no findings. This does not affect today's expected-count-zero path, where the digest is not used to admit debt. I would not claim exact byte-level positive-baseline admission until the intended property is explicit and, if exact stream identity is required, the shared evaluator hashes a framed stdout/stderr pair (with a real checker counterexample test).

P40 bucket: **SAME class, second level**. The shared helper now covers the complete set of current production callers; the remaining escape is within the same observation-identity mechanism, not a new class. Bounded residual/falsifier: distinguish two raw stream pairs that normalize to the same concatenated text and require different admission outcomes when exact stream identity is the property. The actual raw closeout receipt separately preserves both streams, so this is limited to the baseline comparison, not receipt completeness.

## Current baseline and native behavior

`architecture/exceptions/docs_freshness.toml` is unchanged at `owner=team-docs`, `mode=fail_closed_baseline`, `expected_violation_count=0`, and `expires=2026-06-30` (expired on the review date, 2026-10-09). The old digest remains present but is not used to authorize findings at count zero. The shared validator rejects a positive count with an expired date; no renewal, date shift, or waiver is indicated. The TOML `reason` still describes retaining a time-bounded pre-existing-debt baseline, while its current count and `baseline_note` say the debt was burned down; this is stale explanatory text, not active exception authority.

The native checker command was run from `policy-engine/`:

```text
uv run --no-sync polisyos-tools validation check-docs-accuracy --repo-root .
```

It exited 0 and reported `- violations: 0` and `- checked files: 475`. The direct baseline command also exited 0 with `Docs freshness baseline passed.` An isolated call to `_run_docs_freshness_gate(receipt_dir=...)` returned zero findings. Its retained `stdout.bin` is 830 bytes with SHA256 `3ade69a1c5dcb121bdc60fa83268108911b28203ef7b9830fd9af85be33060f4`; `stderr.bin` is empty with the standard empty SHA256. `receipt.json` hashes match the files on disk and records the invoked command and exit code 0.

The real broken-input counterfactual is `test_docs_freshness_zero_baseline_rejects_real_checker_violations`: it builds a published page with `<repo-url>`, keeps the configured expected count at zero, invokes the real checker, and confirms the baseline fails. This is an execution test, not a marker assertion.

## Coverage and verification

The shared-helper caller census walked all `tools/**/*.py` files (447 `.py` files) and found exactly two direct callers: `tools/devx/workspace/repository_sota_closeout.py` and `tools/quality/validation/check_docs_freshness_baseline.py`. The test census walked all `tests/**/*.py` files (2,870 `.py` files); tests exercise the callers rather than importing the helper directly.

Independent focused verification:

- `uv run --no-sync pytest -o addopts= -q tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/architecture/test_repository_sota_phase5_closeout.py -k docs_freshness`: **16 passed, 38 deselected**.
- The real broken-input counterfactual alone: **1 passed**.
- The author’s broader final regression receipt: **19 passed, 35 deselected**; Ruff check passed and five edited files were already formatted.

The complete native SOTA wave was not run; it remains root-owned after source freeze. These checks validate only the docs-freshness child gate and its focused behavioral tests.

## Source identity

Reviewed source and test files at the current working-tree content:

- `tools/lib/docs_freshness.py` — `d902f2cca072a8c94b82c7c6e1eb14b924b42330fc39af34e9609eff1a81636a`
- `tools/devx/workspace/repository_sota_closeout.py` — `026fbd624e9e56cbb12f5dc59a7d2929cffca196e1272736c19e43daa9e32248`
- `tools/quality/validation/check_docs_freshness_baseline.py` — `d8c63f110ed95138f64a1cfed1fadfc46eb3a9acbed72f15c9e69931da56270b`
- `tests/repo_quality/tools/test_docs_lifecycle.py` — `c02e3c342f309f6de26aad1ac86a6bfbbc7a199f8d2c51acc6ea2ae337a73798`
- `tests/repo_quality/architecture/test_repository_sota_phase5_closeout.py` — `23787a713758a6ded2f5a268192006bb4d5997f5618f30f11cb4b0a361f62d9c`
- `architecture/exceptions/docs_freshness.toml` — `aaea4ef9cfa72d3e2b6a80c70f62ed91e0e33b03514568ffc0c1a1e8e1cc2bfe`

Full command outputs and the stream-identity probe are preserved in the adjacent ignored `raw/` directory. No source, generated file, expiry, or registry was edited for this review.
