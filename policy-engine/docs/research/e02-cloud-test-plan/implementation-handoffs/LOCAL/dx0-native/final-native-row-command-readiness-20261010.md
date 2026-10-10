# Final native wave: command and row readiness

Prepared against the parent-supplied candidate revision f52809e8210714131f53c7b90bd53a9215c69d69. This is a command plan, not a test receipt; no gate was run here. The source paths and hashes below pin the recipes to recheck at final freeze.

Product root:
  /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine

## Prerequisites and receipt rule

Use the already provisioned product Python environment and Node 22. If the checkout's frontend links are not already installed, the existing prerequisite is corepack pnpm install --frozen-lockfile before generated TypeScript scanners. Root reported both provisioning steps complete; do not reinstall for this recipe.

Run from the product root. The closeout's subprocess runner is serial and uses subprocess.run without a timeout. Reserve one heavy slot for the entire command; the current wall time is unknown. Do not pre-run its children and then repeat them inside the aggregate. Do not pass --contract-only or --skip-generated-checks.

Run the canonical aggregate exactly once after source freeze:

    uv run polisyos-tools workspace repository-sota-closeout --output-json docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-sota-frozen/report.json --subprocess-receipt-dir docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-sota-frozen/children

Retain full top-level stdout, stderr, exit status, argv/cwd, and elapsed time in:

    /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-sota-frozen/

The runner writes one child directory per row under children/. Each contains stdout.bin, stderr.bin, and receipt.json with exact argv, cwd, exit code, byte lengths, and SHA-256 values. Keep these raw files: the JSON closeout finding detail truncates failed-child text at 4,000 characters. The emitted report.json and _build/.tmp/last-mile artifacts are complementary outputs, not substitutes for child receipts.

## SOTA child rows

The source calls these sequentially in _run_fail_closed_subprocess_gates, then calls the docs-freshness gate. Rows 1–17 are source-order; row 18 is the separate docs child.

| # | Row | Exact child argv from product root | Output |
| ---: | --- | --- | --- |
| 1 | generated-drift | uv run polisyos-tools architecture guardrails check --all-generated-checks | Full child receipt; no JSON output path passed |
| 2 | import-linter | uv run python tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml | Full child receipt |
| 3 | command-registry | uv run polisyos-tools docs --output docs/reference/tools.md --check | Check-only; docs/reference/tools.md must not be rewritten |
| 4 | public-polish | uv run pytest tests/repo_quality/architecture/test_repository_public_polish.py -q | Full child receipt |
| 5 | repository-structure | uv run python tools/quality/validation/repository_structure_phase0.py gate --gate all --mode fail-closed --json | JSON to stdout plus full child receipt |
| 6 | last-mile-inventory | uv run python tools/quality/validation/repository_last_mile_inventory.py --json-output _build/.tmp/last-mile/inventory.json --check | _build/.tmp/last-mile/inventory.json |
| 7 | package-import-gates | uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json | _build/.tmp/last-mile/package-import-gates.json |
| 8 | directory-health | uv run python tools/quality/validation/directory_health.py --repo-root . --json-output _build/.tmp/last-mile/directory-health.json --markdown-output _build/.tmp/last-mile/directory-health.md --fail-on-regression | JSON and Markdown under _build/.tmp/last-mile/ |
| 9 | test-ratchets-helper-topology | uv run python tools/quality/testing/report_test_ratchets.py --format json --output _build/.tmp/last-mile/test-ratchets.json --fail-on-regression | _build/.tmp/last-mile/test-ratchets.json |
| 10 | dead-overrides | uv run python tools/ops_runners/reports/dead_overrides.py --json-output _build/.tmp/last-mile/dead-overrides.json | _build/.tmp/last-mile/dead-overrides.json |
| 11 | extension-examples | uv run python tools/quality/validation/check_extension_examples.py | Full child receipt |
| 12 | adr-thematic-index | uv run python tools/quality/validation/generate_adr_index.py --check | Check-only; no intended write |
| 13 | validator-module-size | uv run python tools/quality/validation/architecture_report_only_contracts.py --report module-size --json-output _build/.tmp/last-mile/module-size.json --fail-on-contract-errors | _build/.tmp/last-mile/module-size.json |
| 14 | schema-purity | The caller executes SCHEMA_PURITY_SNIPPET from tools/devx/workspace/repository_sota_closeout.py via uv run python -c. | Writes _build/.tmp/last-mile/schemas-python-residue.txt; exits nonzero if schemas/ contains .py or __pycache__ |
| 15 | operability-release | uv run python tools/ops_runners/release/check_operability_release_gates.py --json-output _build/.tmp/last-mile/operability-release-gates.json --fail-closed | _build/.tmp/last-mile/operability-release-gates.json |
| 16 | compatibility-release | uv run python tools/ops_runners/release/check_compatibility_release_gates.py --json-output _build/.tmp/last-mile/compatibility-release-gates.json --fail-on-contract-errors | _build/.tmp/last-mile/compatibility-release-gates.json |
| 17 | acceptance-audit | uv run polisyos-tools workspace acceptance-audit --json-output _build/.tmp/last-mile/platform-acceptance.json --summary _build/.tmp/last-mile/platform-acceptance.md | JSON and Markdown under _build/.tmp/last-mile/ |
| 18 | docs-freshness | uv run polisyos-tools validation check-docs-accuracy --repo-root . | Full child receipt; on success prints one “- violations: 0” line and checked-file count |

The docs child is not skipped by the current zero-debt contract. _run_docs_freshness_gate runs it when expected_violation_count is 0, even when the TOML expiry is in the past; the baseline validator only reports expiry when the expected count is nonzero. Current expected count is 0. Do not change/renew the date or describe that special zero-count behavior as issuer approval. At this candidate, the checker’s dynamic MkDocs published-files selection yielded 475 Markdown pages; record the final command’s checked-file count, because the selection is derived, not a hardcoded 475-file manifest. It reports measured scope and explicit omissions: prose truth, runtime behavior, external URL availability, unpublished docs, reference-style links, rendered deployment, and other listed omissions are not asserted by this gate.

## Separate repository checks

These are the four requested product-root commands, separate from the aggregate’s child receipts. Capture complete stdout/stderr, argv/cwd, exit status, and elapsed time in a distinct ignored receipt folder; do not call them results of the aggregate.

    python3 -m tools.cli workspace verify --backend-only
    python3 -m tools.cli workspace ci-parity --skip-browser
    uv run polisyos-tools architecture guardrails check
    uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract

The backend verify and CI-parity commands overlap multiple aggregate gates. Keep their independent receipts if the closeout requires them, but do not infer independent coverage from the overlap. ci-parity --skip-browser does not mean --skip-docs.

## Canonical Ruff check and format denominators

The canonical repo-hygiene source is tools/devx/workspace/_repo_hygiene.py, called by tools/devx/workspace/lint_fast.py, format_check.py, and benchmark_surfaces.py. Run at product root, where ruff.toml extends ruff.generated.toml. Do not use “ruff check .”: that broad exploratory command swept LOCAL recovery/probe scripts and legacy paths outside the authored-source scopes.

Canonical general authored-source Ruff check (lint_fast.py expansion):

    uv run ruff check --extend-exclude benchmarks --extend-exclude tools/research/benchmarks --extend-exclude tools/research/demos --extend-exclude tools/research src/polisyos tests tools schemas examples ops/cloud/gcp/upload_gonka_secrets.py jax_bootstrap.py migrate.py

Canonical Phase 8 benchmark/research Ruff check (separate limited profile):

    uv run ruff check --select E,F,I,UP --ignore E402,E501 benchmarks tools/research/benchmarks tools/research/demos tools/research

Canonical authored-source formatter check (format_check.py expansion):

    uv run ruff format --check src/polisyos tests tools benchmarks schemas examples ops/cloud/gcp/upload_gonka_secrets.py jax_bootstrap.py migrate.py

These are directory/file scopes from source, not an inferred changed-file count. If the final freeze also requires a changed/new-file delta check, retain its complete frozen repo-relative Python path manifest and SHA ledger, use the same explicit paths for check and format, and keep that delta receipt distinct from canonical lint-fast/format-check. No count is claimed here for the post-freeze delta.

## Expiry and provenance handling

The contract stage in the aggregate still reports issuer-owned exception rows from the current registries. Preserve each current owner, issue/ADR, scope, and expiry in the report; do not blanket-waive rows or shift dates. A previous 82/86-finding contract receipt is historical and not the current final denominator. No P41 inherited-red claim is established here: the earlier receipt was on another candidate/slice, and this note does not replay an exact pre-work base against each complete current gate-input denominator.

The existing LOCAL/sota-native-full-command-plan.md contains an obsolete statement that an expired docs baseline short-circuits the docs child. The source at this candidate contradicts that statement; this note supersedes that specific sentence without rewriting the historical note.

## Source pins

Candidate identity supplied by parent: f52809e8210714131f53c7b90bd53a9215c69d69.

- tools/devx/workspace/repository_sota_closeout.py — 026fbd624e9e56cbb12f5dc59a7d2929cffca196e1272736c19e43daa9e32248
- architecture/gates/repository_sota.toml — 59df71c8fa0a2344674a7e83de1e037aae61b918e8e1710b6ba691f8c5019e18
- architecture/exceptions/docs_freshness.toml — aaea4ef9cfa72d3e2b6a80c70f62ed91e0e33b03514568ffc0c1a1e8e1cc2bfe
- tools/lib/docs_freshness.py — d902f2cca072a8c94b82c7c6e1eb14b924b42330fc39af34e9609eff1a81636a
- tools/quality/validation/check_docs_accuracy.py — 2bbe2e794d089510fa2e8d86b446e1ded6b09c1eadd650fb5cc03e5a68acc26b
- mkdocs.yml — 6c0f5281f0d25246dde5a3963dfcbfa1c6f7d6e6ae9df36fd457973bb6d4e567
- tools/devx/workspace/_repo_hygiene.py — 7ed1b535f3a253e3cc53edf37429cac9a47ccd22742c7b3fa78ed0f748c65cb4
- tools/devx/workspace/lint_fast.py — 8a347c43d7f0a9a06a5fadd660b9197b0a5a67abf42b1e0bff7b6a7b6a87b061
- tools/devx/workspace/format_check.py — afa85ac3c0cce247c970c178f73f4e10cf0b37c2772f6aa7b19f14837c2dace9
- ruff.toml — 8887d0a15457d44ebb1a5b5aee8110dd5101dc9e952649cd0490b845af2d933e
- ruff.generated.toml — 51dd7d4fb4937537d815e7b791541c9f09b0b9f413ec06e6c69b221c0096d64f
- tools/devx/workspace/verify.py — 864ec1e4f463b63610986cd86b93a1b61687408b84e1a9c64cd6d6a65d587207
- tools/devx/workspace/ci_parity.py — 8ee3abda4668c4bbc24c58412b11eda51eaae9c046b98ad80ff5b17705e26619
