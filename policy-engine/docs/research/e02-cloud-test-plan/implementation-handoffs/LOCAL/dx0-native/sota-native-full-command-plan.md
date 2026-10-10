# Repository SOTA native wave plan

This is a source-derived one-shot plan for the frozen native wave. It is not an execution receipt. The fresh diagnostic receipt immediately before it is `sota-contract-after-public-polish.json` plus its sibling status/stdout/stderr/runtime-input files: contract-only took 1.654 s and produced 82 expiry findings. It did not run subprocess drift gates.

## Command to run once after source freeze

Run from `policy-engine/`:

```bash
uv run polisyos-tools workspace repository-sota-closeout --output-json docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-sota-frozen/report.json --subprocess-receipt-dir docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-sota-frozen/children
```

This is the configured `gate_command` in `architecture/gates/repository_sota.toml` with the supported JSON receipt flag. Do not add `--contract-only` or `--skip-generated-checks`. The first skips all native subprocess gates; the second changes generated-drift coverage. Capture the full top-level command output and exit status into sibling `native-sota-current.stdout.txt`, `.stderr.txt`, and `.status.txt`, while retaining the emitted JSON and the generated `_build/.tmp/last-mile/` artifacts.

## Synchronous contract checks inside the one-shot command

Before child commands, `tools/devx/workspace/repository_sota_closeout.py::main` evaluates, in order: gate registry; final topology contract; operations modes; docs-freshness metadata; time-bounded import exceptions; complexity exceptions; migration shims; Phase 6.5 exception metadata; wiring; required closeout docs; and public-polish contracts. The current fresh contract report has zero public-polish findings and 82 expiry findings. These checks do not prove an exception is still needed; they check row shape, paths, and dates.

## Exact sequential subprocess row plan

`_run_fail_closed_subprocess_gates` invokes these 17 rows serially, in this order. They are commands the top-level command itself will run; do not pre-run them and then run the aggregate if the goal is one composed wave.

| # | Gate row | Exact command / source expansion | Expected artifact |
| ---: | --- | --- | --- |
| 1 | `generated-drift` | `uv run polisyos-tools architecture guardrails check --all-generated-checks` | Guardrail output; no JSON path supplied by this caller |
| 2 | `import-linter` | `uv run python tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml` | Import-linter output |
| 3 | `command-registry` | `uv run polisyos-tools docs --output docs/reference/tools.md --check` | Check-only; no intended write |
| 4 | `public-polish` | `uv run pytest tests/repo_quality/architecture/test_repository_public_polish.py -q` | Pytest output |
| 5 | `repository-structure` | `uv run python tools/quality/validation/repository_structure_phase0.py gate --gate all --mode fail-closed --json` | JSON on stdout |
| 6 | `last-mile-inventory` | `uv run python tools/quality/validation/repository_last_mile_inventory.py --json-output _build/.tmp/last-mile/inventory.json --check` | `_build/.tmp/last-mile/inventory.json` |
| 7 | `package-import-gates` | `uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json` | `_build/.tmp/last-mile/package-import-gates.json` |
| 8 | `directory-health` | `uv run python tools/quality/validation/directory_health.py --repo-root . --json-output _build/.tmp/last-mile/directory-health.json --markdown-output _build/.tmp/last-mile/directory-health.md --fail-on-regression` | `_build/.tmp/last-mile/directory-health.json` and `.md` |
| 9 | `test-ratchets-helper-topology` | `uv run python tools/quality/testing/report_test_ratchets.py --format json --output _build/.tmp/last-mile/test-ratchets.json --fail-on-regression` | `_build/.tmp/last-mile/test-ratchets.json` |
| 10 | `dead-overrides` | `uv run python tools/ops_runners/reports/dead_overrides.py --json-output _build/.tmp/last-mile/dead-overrides.json` | `_build/.tmp/last-mile/dead-overrides.json` |
| 11 | `extension-examples` | `uv run python tools/quality/validation/check_extension_examples.py` | Checker output |
| 12 | `adr-thematic-index` | `uv run python tools/quality/validation/generate_adr_index.py --check` | Check-only; no intended write |
| 13 | `validator-module-size` | `uv run python tools/quality/validation/architecture_report_only_contracts.py --report module-size --json-output _build/.tmp/last-mile/module-size.json --fail-on-contract-errors` | `_build/.tmp/last-mile/module-size.json` |
| 14 | `schema-purity` | The caller passes `SCHEMA_PURITY_SNIPPET` from `tools/devx/workspace/repository_sota_closeout.py` to `uv run python -c`. The snippet scans `schemas/**`, writes `_build/.tmp/last-mile/schemas-python-residue.txt`, and exits 1 if any `__pycache__` or `.py` paths occur. | `_build/.tmp/last-mile/schemas-python-residue.txt` |
| 15 | `operability-release` | `uv run python tools/ops_runners/release/check_operability_release_gates.py --json-output _build/.tmp/last-mile/operability-release-gates.json --fail-closed` | `_build/.tmp/last-mile/operability-release-gates.json` |
| 16 | `compatibility-release` | `uv run python tools/ops_runners/release/check_compatibility_release_gates.py --json-output _build/.tmp/last-mile/compatibility-release-gates.json --fail-on-contract-errors` | `_build/.tmp/last-mile/compatibility-release-gates.json` |
| 17 | `acceptance-audit` | `uv run polisyos-tools workspace acceptance-audit --json-output _build/.tmp/last-mile/platform-acceptance.json --summary _build/.tmp/last-mile/platform-acceptance.md` | `_build/.tmp/last-mile/platform-acceptance.json` and `.md` |

After row 17, the runner invokes a docs-freshness subprocess only when the baseline `expires` date is current. On this tree it is already expired, so `_run_docs_freshness_gate` returns the expiry finding before executing `uv run polisyos-tools validation check-docs-accuracy --repo-root .`. The owner needs to evaluate that declared command separately before any baseline decision; the frozen full run should report the short-circuit honestly.

## Receipt limits and execution budget

The current aggregate retains complete raw stdout/stderr and command/exit/hash records for every executed child when `--subprocess-receipt-dir` is supplied. Its compact finding detail still stores only the first 4,000 combined characters of a failing child; that detail is not the deciding output. The command above selects the full child receipts. Keep the complete top-level streams and elapsed time alongside them, and cite these ignored outputs from the final direct-child LOCAL typed handoff. Do not run the children first and duplicate the expensive wave.

A recent local timing row records `architecture.guardrails` at 251.358 s but omits argv, so it is only a planning signal, not a proved duration for `--all-generated-checks`. Treat the native wave as a >30 s reservation; its full duration remains unmeasured. The 1.654 s contract-only time is not a proxy for the native wave. No native row was executed here; run it once after the source freeze.

## Provenance rule

The prior input audit is tied to candidate 9e89 and slice base 93d6; it says the full checker had a three-path changed-input intersection in a 969-path source denominator, so it explicitly rejects gate-wide P41 inheritance. The current post-repair contract scan is fresh but does not calculate a new slice-base changed-path intersection. Keep the 82 issuer-owned expiry records separate from any gate-wide inherited/debt label until the exact frozen-state audit proves zero full-denominator intersection. No blanket waiver or expiry shift is part of this plan.
