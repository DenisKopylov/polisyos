# Polisyos Tools Reference

Generated from `tools.registry` command metadata.

## D1-L5 Source Phase Map

| Source phase | Focus | Current evidence |
| ------------ | ----- | ---------------- |
| Phase 0 | SQL/shell injection, shell safety, destructive operation guardrails | `tools.lib.runner`, `tools.lib.sql`, `tools.lib.fs` |
| Phase 1 | atomicity, rollback, resource/I/O validation, degraded mode, legacy quarantine | `tools.lib.fs`, `tools.lib.http`, `tools.lib.preflight`, lifecycle status metadata |
| Phase 2 | unified CLI, shared runtime, packaging/import normalization, dependency graph, docs metadata | `polisyos-tools`, `tools.registry`, `tools.cli`, compatibility package shims |
| Phase 3 | critical tool test program, structured CI output, timing telemetry | `tests/repo_quality/tools/**`, `tools.lib.output`, `tools.lib.timing`, workspace gates |
| Phase 4 | cloud, benchmarks, scripts, and duplicate namespace consolidation | `tools/ops_runners/**`, `tools/research/**`, final topology and retired wrapper evidence |
| Phase 5 | incremental execution, cache, autofix/rule registry, hot-path maintainability | `tools.lib.cache`, `tools/quality/lint/**`, targeted `--fix` and changed-file modes |

## Validation Contract

- Regenerate this page with `uv run polisyos-tools docs --output docs/reference/tools.md`.
- `polisyos-tools workspace ci-parity` includes docs accuracy, strict MkDocs build, and semantic docstring checks unless `--skip-docs` is set.
- Deprecated and quarantined commands must keep `status`, `replacement`, and `reason` metadata in `tools.registry`.

## Documentation Impact

| Output cluster | Exact files | Source of truth | Validation |
| -------------- | ----------- | --------------- | ---------- |
| Generated command reference | `docs/reference/tools.md` | `tools.registry` command metadata, dependency graph edges, lifecycle status metadata | `uv run polisyos-tools docs --output docs/reference/tools.md` |
| Tooling READMEs | `tools/README.md`, `tools/quality/validation/README.md`, `tools/devx/workspace/README.md`, `tools/devx/architecture/README.md` | canonical CLI behavior, workspace gates, validation helpers, architecture guardrails | `uv run polisyos-tools workspace ci-parity --skip-browser` |
| Shared D1-L5 how-to/reference pages | `docs/how-to/operate-ci-cd-platform.md`, `docs/how-to/manage-generated-artifacts.md`, `docs/how-to/release-policy.md`, `docs/reference/quality-gates.md`, `docs/reference/dependency-platform.md`, `docs/reference/merge-governance.md`, `docs/reference/ratchet-policy.md` | repo workflows, generated-artifact guardrails, release tooling, ratchet policy docs | `uv run polisyos-tools architecture guardrails check` |

## Backlog

| Gap | Priority | Tracking note |
| --- | -------- | ------------- |
| No missing required D1-L5 output pages | - | All required D1-L5 files listed in `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md` are present. |
| Additional per-category README expansion outside the D1 scope | P3 | Further category-local docs can land in D2 without blocking the D1 closure criteria. |

## Zones

| Zone | Categories |
| ---- | ---------- |
| `devx` | `workspace`, `architecture`, `connectors`, `foundry` |
| `quality` | `lint`, `diagnostics`, `validation`, `testing`, `ci` |
| `ops` | `calibration`, `cloud`, `data`, `deploy`, `ops-experiments`, `migrations`, `release`, `runtime`, `ukraine_data` |
| `research` | `benchmarks`, `demos`, `research-experiments` |

## Commands

### `devx`

| Category | Command | Status | Canonical | Summary | Replacement | Aliases | Dependencies |
| -------- | ------- | ------ | --------- | ------- | ----------- | ------- | ------------ |
| `workspace` | `acceptance-audit` | `active` | `polisyos-tools workspace acceptance-audit` | Run the Phase 7 platform acceptance audit for the policy-engine workspace. | - | - | - |
| `workspace` | `benchmark-surfaces` | `active` | `polisyos-tools workspace benchmark-surfaces` | Run the Phase 8 benchmark/research hygiene gate for authored assets. | - | - | - |
| `workspace` | `bootstrap` | `active` | `polisyos-tools workspace bootstrap` | Bootstrap a contributor machine for the policy-engine workspace. | - | - | `workspace.doctor` |
| `workspace` | `ci-parity` | `active` | `polisyos-tools workspace ci-parity` | Run a local validation pass that approximates the main CI surfaces. | - | - | - |
| `workspace` | `clean-local-reports` | `active` | `polisyos-tools workspace clean-local-reports` | Clean stale local reports and optional source-adjacent residue. | - | - | - |
| `workspace` | `core-runtime-basedpyright` | `active` | `polisyos-tools workspace core-runtime-basedpyright` | Run basedpyright across the full core-runtime surface plus curated extras. | - | - | - |
| `workspace` | `core-runtime-closeout` | `active` | `polisyos-tools workspace core-runtime-closeout` | Validate and render the CORE common/runtime closeout ledger. | - | - | - |
| `workspace` | `core-runtime-long-soak` | `active` | `polisyos-tools workspace core-runtime-long-soak` | Run the core-runtime long-soak evidence suite and emit machine-readable reports. | - | - | - |
| `workspace` | `core-runtime-mypy` | `active` | `polisyos-tools workspace core-runtime-mypy` | Run strict mypy over every Python file in the core runtime surface. | - | - | - |
| `workspace` | `docs-style` | `active` | `polisyos-tools workspace docs-style` | Lint authored Markdown docs and package READMEs. | - | - | - |
| `workspace` | `doctor` | `active` | `polisyos-tools workspace doctor` | Preflight validation for contributor machines and local quality gates. | - | - | - |
| `workspace` | `format-check` | `active` | `polisyos-tools workspace format-check` | Run repository-wide formatter checks for authored surfaces. | - | - | - |
| `workspace` | `lint-fast` | `active` | `polisyos-tools workspace lint-fast` | Run the fast repository-wide lint contract for authored files. | - | - | - |
| `workspace` | `lint-full` | `active` | `polisyos-tools workspace lint-full` | Run the full authored lint contract used by CI and nightly sweeps. | - | - | `workspace.lint-fast`, `workspace.format-check`, `workspace.python-base-mypy`, `workspace.python-base-basedpyright` |
| `workspace` | `python-base-basedpyright` | `active` | `polisyos-tools workspace python-base-basedpyright` | Run basedpyright across the Phase 3 Python base layers in serial order. | - | - | - |
| `workspace` | `python-base-mypy` | `active` | `polisyos-tools workspace python-base-mypy` | Run mypy across the Phase 3 Python base layers in serial order. | - | - | - |
| `workspace` | `release-build-cache-lifecycle` | `active` | `polisyos-tools workspace release-build-cache-lifecycle` | Check and clean release/build/cache lifecycle state. | - | - | - |
| `workspace` | `remote-acceptance` | `active` | `polisyos-tools workspace remote-acceptance` | Provision and drive a remote Linux runner for acceptance closeout. | - | - | - |
| `workspace` | `repository-sota-closeout` | `active` | `polisyos-tools workspace repository-sota-closeout` | Enforce the Repository SOTA Phase 5 closeout gate. | - | - | - |
| `workspace` | `runtime-surface` | `active` | `polisyos-tools workspace runtime-surface` | Run the Phase 5B runtime lint, type, boundary, and API contract gate. | - | - | - |
| `workspace` | `tool-configs` | `active` | `polisyos-tools workspace tool-configs` | Generate and verify split mypy, Ruff, and MkDocs configuration. | - | - | - |
| `workspace` | `verify` | `active` | `polisyos-tools workspace verify` | Run the standard fast local gate for policy-engine contributors. | - | - | `workspace.doctor` |
| `architecture` | `guardrails` | `active` | `polisyos-tools architecture guardrails` | architecture/guardrails | - | - | - |
| `architecture` | `scaffold` | `active` | `polisyos-tools architecture scaffold` | architecture/scaffold | - | - | - |
| `connectors` | `check-contracts` | `active` | `polisyos-tools connectors check-contracts` | connectors/check_contracts | - | - | - |
| `connectors` | `scaffold` | `active` | `polisyos-tools connectors scaffold` | CLI scaffold generator for Policy OS connectors. | - | - | - |
| `foundry` | `generate-stubs` | `active` | `polisyos-tools foundry generate-stubs` | Generate Foundry method stubs through the canonical tools surface. | - | - | - |
| `foundry` | `update-signature-baseline` | `active` | `polisyos-tools foundry update-signature-baseline` | Refresh the Foundry signature baseline through the canonical tools surface. | - | - | - |

### `quality`

| Category | Command | Status | Canonical | Summary | Replacement | Aliases | Dependencies |
| -------- | ------- | ------ | --------- | ------- | ----------- | ------- | ------------ |
| `lint` | `check-scholar-imports` | `active` | `polisyos-tools lint check-scholar-imports` | lint/check_scholar_imports | - | - | - |
| `lint` | `collect-arch-metrics` | `active` | `polisyos-tools lint collect-arch-metrics` | lint/collect_arch_metrics | - | - | - |
| `lint` | `compare-baseline` | `active` | `polisyos-tools lint compare-baseline` | lint/compare_baseline | - | - | - |
| `lint` | `lint-connector-hardening` | `active` | `polisyos-tools lint lint-connector-hardening` | Enforce P7 connector hardening invariants for production HTTP connectors. | - | - | - |
| `lint` | `lint-connectors` | `active` | `polisyos-tools lint lint-connectors` | Law A & Law B enforcement for the connectors subtree. | - | - | - |
| `lint` | `lint-foundry` | `active` | `polisyos-tools lint lint-foundry` | lint/lint_foundry | - | - | - |
| `lint` | `lint-foundry-data-plane` | `active` | `polisyos-tools lint lint-foundry-data-plane` | lint/lint_foundry_data_plane | - | - | - |
| `lint` | `lint-imports` | `active` | `polisyos-tools lint lint-imports` | lint/lint_imports | - | - | - |
| `lint` | `lint-legacy-cutover` | `active` | `polisyos-tools lint lint-legacy-cutover` | lint/lint_legacy_cutover | - | - | - |
| `diagnostics` | `abi-diff` | `active` | `polisyos-tools diagnostics abi-diff` | diagnostics/abi_diff | - | - | `diagnostics.gen-schema` |
| `diagnostics` | `capture-env` | `active` | `polisyos-tools diagnostics capture-env` | CLI tool to capture and compare environment manifests. | - | - | - |
| `diagnostics` | `check-perf-regression` | `active` | `polisyos-tools diagnostics check-perf-regression` | Performance regression checker for CI/CD. | - | - | - |
| `diagnostics` | `check-scientist-node-version-bump` | `active` | `polisyos-tools diagnostics check-scientist-node-version-bump` | diagnostics/check_scientist_node_version_bump | - | - | - |
| `diagnostics` | `check-setup` | `active` | `polisyos-tools diagnostics check-setup` | Smoke test для проверки корректной установки всех компонентов Policy Engine. | - | - | - |
| `diagnostics` | `check-state-reads` | `active` | `polisyos-tools diagnostics check-state-reads` | diagnostics/check_state_reads | - | - | - |
| `diagnostics` | `check-udf-perf` | `quarantined` | `polisyos-tools diagnostics check-udf-perf` | diagnostics/check_udf_perf | diagnostics check-setup | - | - |
| `diagnostics` | `gen-schema` | `active` | `polisyos-tools diagnostics gen-schema` | diagnostics/gen_schema | - | - | - |
| `diagnostics` | `generate-ir-reference-catalog` | `active` | `polisyos-tools diagnostics generate-ir-reference-catalog` | diagnostics/generate_ir_reference_catalog | - | - | - |
| `diagnostics` | `generate-ir-schema` | `active` | `polisyos-tools diagnostics generate-ir-schema` | diagnostics/generate_ir_schema | - | - | - |
| `diagnostics` | `scan-fabric` | `active` | `polisyos-tools diagnostics scan-fabric` | Bootstrap utility to scan DuckDB files and generate draft data contracts. | - | - | - |
| `diagnostics` | `verify-scm-v3` | `active` | `polisyos-tools diagnostics verify-scm-v3` | Run SCM v3 verification checks and emit JSON/Markdown reports. | - | - | - |
| `diagnostics` | `verify-scm-v3-fullspec` | `active` | `polisyos-tools diagnostics verify-scm-v3-fullspec` | Build detailed SCM v3 full-spec verification (DoD 162 + Laws + SL layers). | - | - | - |
| `diagnostics` | `visualize-provenance` | `active` | `polisyos-tools diagnostics visualize-provenance` | Provenance visualization / validation utility. | - | - | - |
| `validation` | `build-honest-diagnostics-coverage` | `active` | `polisyos-tools validation build-honest-diagnostics-coverage` | Build the Honest Diagnostics substrate coverage dashboard. | - | - | - |
| `validation` | `build-policy-design-case-coverage` | `active` | `polisyos-tools validation build-policy-design-case-coverage` | Build the baseline-only Policy Design Case coverage dashboard. | - | - | - |
| `validation` | `build-policy-design-case-pass2-diagnostics` | `active` | `polisyos-tools validation build-policy-design-case-pass2-diagnostics` | Build Policy Design Case Pass 2 diagnostics for Phase 34. | - | - | - |
| `validation` | `build-policy-design-case-pass2-disposition` | `active` | `polisyos-tools validation build-policy-design-case-pass2-disposition` | Build Policy Design Case Wave 35 Pass 2 disposition artifacts. | - | - | - |
| `validation` | `build-policy-design-case-wave35a` | `active` | `polisyos-tools validation build-policy-design-case-wave35a` | Build Wave 35A runtime scenario and variant remediation evidence. | - | - | - |
| `validation` | `build-policy-design-case-wave35b` | `active` | `polisyos-tools validation build-policy-design-case-wave35b` | Build Wave 35B adversarial fail-closed remediation evidence. | - | - | - |
| `validation` | `build-policy-design-case-wave35c` | `active` | `polisyos-tools validation build-policy-design-case-wave35c` | Build Wave 35C claim-authority and semantic-validity remediation evidence. | - | - | - |
| `validation` | `build-policy-design-case-wave35d` | `active` | `polisyos-tools validation build-policy-design-case-wave35d` | Build Wave 35D operational recovery, resource, parity, and archive evidence. | - | - | - |
| `validation` | `build-policy-design-case-wave35e` | `active` | `polisyos-tools validation build-policy-design-case-wave35e` | Build Wave 35E human-facing legitimacy, memory, and trust evidence. | - | - | - |
| `validation` | `build-policy-design-case-wave35f-integrity` | `active` | `polisyos-tools validation build-policy-design-case-wave35f-integrity` | Build Wave 35F remediation integrity and runtime authority artifacts. | - | - | - |
| `validation` | `build-policy-design-case-wave35g-backfill` | `active` | `polisyos-tools validation build-policy-design-case-wave35g-backfill` | Build Wave 35G backfill integration and Wave 36 release-fence artifacts. | - | - | - |
| `validation` | `build-policy-design-case-wave35g-institutional-provenance` | `active` | `polisyos-tools validation build-policy-design-case-wave35g-institutional-provenance` | Build Wave 35G.4 institutional provenance boundary ledger. | - | - | - |
| `validation` | `build-policy-design-case-wave35g-memory-authority` | `active` | `polisyos-tools validation build-policy-design-case-wave35g-memory-authority` | Build Wave 35G.2 memory authority runtime abstention trace. | - | - | - |
| `validation` | `build-policy-design-case-wave35h-provenance` | `active` | `polisyos-tools validation build-policy-design-case-wave35h-provenance` | Build Wave 35H institutional provenance runtime-ownership artifacts. | - | - | - |
| `validation` | `build-policy-design-case-wave36-closeout` | `active` | `polisyos-tools validation build-policy-design-case-wave36-closeout` | Build Policy Design Case Wave 36 deterministic canary closeout artifacts. | - | - | - |
| `validation` | `build-policy-design-case-wave40-readiness` | `active` | `polisyos-tools validation build-policy-design-case-wave40-readiness` | Build Policy Design Case Wave 40 readiness and bundle-inspection closeout. | - | - | - |
| `validation` | `build-policy-evidence-capability-index` | `active` | `polisyos-tools validation build-policy-evidence-capability-index` | Build the Policy Evidence Capability Index release artifacts. | - | - | - |
| `validation` | `build-wave5-honest-diagnostics-evidence` | `active` | `polisyos-tools validation build-wave5-honest-diagnostics-evidence` | Build runtime-backed Wave 5 Honest Diagnostics evidence reports. | - | - | - |
| `validation` | `check-can-i-closeout` | `active` | `polisyos-tools validation check-can-i-closeout` | Validate Can-I-Closeout compatibility for a selected evidence bundle. | - | - | - |
| `validation` | `check-ci-ratchets` | `active` | `polisyos-tools validation check-ci-ratchets` | Ratchet targeted CI escapes across common/core/runtime HTTP packages. | - | - | - |
| `validation` | `check-compilation-truthfulness` | `active` | `polisyos-tools validation check-compilation-truthfulness` | Audit W11.E compilation truthfulness against adjudicated corpus annotations. | - | - | - |
| `validation` | `check-critic-ensemble-diversity` | `active` | `polisyos-tools validation check-critic-ensemble-diversity` | Measure W11.F critic ensemble diversity over flagged failure modes. | - | - | - |
| `validation` | `check-docs-accuracy` | `active` | `polisyos-tools validation check-docs-accuracy` | Validate published docs against current repository reality. | - | - | - |
| `validation` | `check-docs-freshness-baseline` | `active` | `polisyos-tools validation check-docs-freshness-baseline` | Validate the fail-closed docs freshness baseline without running repo-wide gates. | - | - | - |
| `validation` | `check-docs-gate` | `active` | `polisyos-tools validation check-docs-gate` | Run the Phase D6 path-aware documentation drift gate. | - | - | - |
| `validation` | `check-docs-lifecycle` | `active` | `polisyos-tools validation check-docs-lifecycle` | Validate the Phase 6.4 documentation lifecycle conversion contract. | - | - | - |
| `validation` | `check-docstring-quality` | `active` | `polisyos-tools validation check-docstring-quality` | Fail CI when public API docstrings regress to generic placeholders. | - | - | - |
| `validation` | `check-domain-coverage-breadth` | `active` | `polisyos-tools validation check-domain-coverage-breadth` | Measure W11.F domain coverage breadth and authority useful-design rates. | - | - | - |
| `validation` | `check-evidence-spine-connectivity` | `active` | `polisyos-tools validation check-evidence-spine-connectivity` | Check scenario evidence contract propagation inside a canary evidence bundle. | - | - | - |
| `validation` | `check-evidence-spine-handoffs` | `active` | `polisyos-tools validation check-evidence-spine-handoffs` | Check evidence-spine async/batch handoff ledgers in canary bundles. | - | - | - |
| `validation` | `check-expert-adjudication-labels` | `active` | `polisyos-tools validation check-expert-adjudication-labels` | Validate W11.C expert adjudication labels for the outcome corpus. | - | - | - |
| `validation` | `check-extension-examples` | `active` | `polisyos-tools validation check-extension-examples` | Install extension examples in editable mode and verify entry-point discovery. | - | - | - |
| `validation` | `check-honest-diagnostics-proof-harness` | `active` | `polisyos-tools validation check-honest-diagnostics-proof-harness` | Prove Honest Diagnostics production invariants have executable evidence. | - | - | - |
| `validation` | `check-package-import-gates` | `active` | `polisyos-tools validation check-package-import-gates` | Fail-closed Phase 6.1 package, public-surface, and import gates. | - | - | - |
| `validation` | `check-policy-design-case-capability-ratchet` | `active` | `polisyos-tools validation check-policy-design-case-capability-ratchet` | Build and validate the Policy Design Case capability ratchet report. | - | - | - |
| `validation` | `check-policy-design-case-cluster-ownership-map` | `active` | `polisyos-tools validation check-policy-design-case-cluster-ownership-map` | Validate the Policy Design Case cluster ownership map. | - | - | - |
| `validation` | `check-policy-design-case-drift` | `active` | `polisyos-tools validation check-policy-design-case-drift` | Audit initial Policy Design Case drift guards. | - | - | - |
| `validation` | `check-policy-design-case-formal-invariants` | `active` | `polisyos-tools validation check-policy-design-case-formal-invariants` | Compatibility wrapper for the archived Policy Design Case closeout loop. | - | - | - |
| `validation` | `check-policy-design-case-layer2-readiness` | `active` | `polisyos-tools validation check-policy-design-case-layer2-readiness` | Validate the Layer 2 S0 readiness bundle. | - | - | - |
| `validation` | `check-policy-design-case-layer2-s1-graded-outcomes` | `active` | `polisyos-tools validation check-policy-design-case-layer2-s1-graded-outcomes` | Validate Layer 2 S1 graded-outcome routing and canonical corpus wiring. | - | - | - |
| `validation` | `check-policy-design-case-layer2-s2-design-search` | `active` | `polisyos-tools validation check-policy-design-case-layer2-s2-design-search` | Validate Layer 2 S2 grammar/candidate/search DesignRecord wiring. | - | - | - |
| `validation` | `check-policy-design-case-layer3-g0-readiness` | `active` | `polisyos-tools validation check-policy-design-case-layer3-g0-readiness` | Validate and persist the Layer 3 G0 grounding readiness bundle. | - | - | - |
| `validation` | `check-policy-design-case-pass1b-hardening` | `active` | `polisyos-tools validation check-policy-design-case-pass1b-hardening` | Validate Policy Design Case Pass 1B hardening coverage. | - | - | - |
| `validation` | `check-policy-design-case-pass2-disposition` | `active` | `polisyos-tools validation check-policy-design-case-pass2-disposition` | Validate Policy Design Case Wave 35 Pass 2 disposition artifacts. | - | - | - |
| `validation` | `check-policy-design-case-reuse-map` | `active` | `polisyos-tools validation check-policy-design-case-reuse-map` | Generate and validate the Policy Design Case capability reuse map. | - | - | - |
| `validation` | `check-policy-design-case-walking-skeleton` | `active` | `polisyos-tools validation check-policy-design-case-walking-skeleton` | Smoke-test Policy Design Case walking-skeleton readiness. | - | - | - |
| `validation` | `check-policy-design-case-wave34-pass2` | `active` | `polisyos-tools validation check-policy-design-case-wave34-pass2` | Validate Policy Design Case Wave 34 Pass 2 diagnostic closeout. | - | - | - |
| `validation` | `check-policy-design-case-wave35f-integrity` | `active` | `polisyos-tools validation check-policy-design-case-wave35f-integrity` | Validate Policy Design Case Wave 35F remediation integrity artifacts. | - | - | - |
| `validation` | `check-policy-design-case-wave35g-backfill` | `active` | `polisyos-tools validation check-policy-design-case-wave35g-backfill` | Validate Policy Design Case Wave 35G backfill release-fence artifacts. | - | - | - |
| `validation` | `check-policy-design-case-wave35h-provenance` | `active` | `polisyos-tools validation check-policy-design-case-wave35h-provenance` | Validate Policy Design Case Wave 35H runtime-owned institutional provenance. | - | - | - |
| `validation` | `check-policy-design-case-wave36-closeout` | `active` | `polisyos-tools validation check-policy-design-case-wave36-closeout` | Validate Policy Design Case Wave 36 deterministic canary closeout artifacts. | - | - | - |
| `validation` | `check-policy-design-case-wave40-readiness` | `active` | `polisyos-tools validation check-policy-design-case-wave40-readiness` | Validate Policy Design Case Wave 40 readiness closeout artifacts. | - | - | - |
| `validation` | `check-policy-design-formal-invariants` | `active` | `polisyos-tools validation check-policy-design-formal-invariants` | Validate Policy Design Case formal invariant specs. | - | - | - |
| `validation` | `check-production-data-scenario-contracts` | `active` | `polisyos-tools validation check-production-data-scenario-contracts` | Check that production-data contracts satisfy scenario source-family obligations. | - | - | - |
| `validation` | `check-production-invariant-registry` | `active` | `polisyos-tools validation check-production-invariant-registry` | Validate the Production Invariant Registry against runtime reader catalogs. | - | - | - |
| `validation` | `check-runtime-quality-schema-compatibility` | `active` | `polisyos-tools validation check-runtime-quality-schema-compatibility` | Report runtime-quality schema compatibility and legacy quarantine decisions. | - | - | - |
| `validation` | `check-substrate-drift` | `active` | `polisyos-tools validation check-substrate-drift` | Audit Wave 0 Honest Diagnostics substrate drift guards. | - | - | - |
| `validation` | `check-universal-corpus-annotations` | `active` | `polisyos-tools validation check-universal-corpus-annotations` | Validate W11.B universal outcome corpus claim/evidence annotations. | - | - | - |
| `validation` | `check-wave4-operational-closeout` | `active` | `polisyos-tools validation check-wave4-operational-closeout` | Validate a fresh Wave 4 Honest Diagnostics operational closeout bundle. | - | - | - |
| `validation` | `compare-honest-diagnostics-rebaseline` | `active` | `polisyos-tools validation compare-honest-diagnostics-rebaseline` | Compare Honest Diagnostics coverage rebaseline directories. | - | - | - |
| `validation` | `compare-policy-design-case-rebaseline` | `active` | `polisyos-tools validation compare-policy-design-case-rebaseline` | Compare Policy Design Case coverage rebaseline directories. | - | - | - |
| `validation` | `control-plane-supply-chain-contracts` | `active` | `polisyos-tools validation control-plane-supply-chain-contracts` | Validate the control-plane and supply-chain contract. | - | - | - |
| `validation` | `decomposition-preflight` | `active` | `polisyos-tools validation decomposition-preflight` | Phase 3A decomposition preflight inventory and gates. | - | - | - |
| `validation` | `directory-health` | `active` | `polisyos-tools validation directory-health` | Build the Phase 6.2 directory-health dashboard and ratchet report. | - | - | - |
| `validation` | `directory-hygiene-assets` | `active` | `polisyos-tools validation directory-hygiene-assets` | Report Phase 2.9 directory hygiene, asset placement, and local residue state. | - | - | - |
| `validation` | `empty-namespace-gate` | `active` | `polisyos-tools validation empty-namespace-gate` | Fail-closed gate for Foundry methods namespace cutover. | - | - | - |
| `validation` | `export-policy-evidence-capability-dcat` | `active` | `polisyos-tools validation export-policy-evidence-capability-dcat` | Export the Policy Evidence Capability Index as DCAT-compatible JSON-LD. | - | - | - |
| `validation` | `export-policy-evidence-capability-prov` | `active` | `polisyos-tools validation export-policy-evidence-capability-prov` | Export Policy Evidence Capability Index lineage as PROV-O Turtle. | - | - | - |
| `validation` | `fabric-best-in-class-inventory` | `active` | `polisyos-tools validation fabric-best-in-class-inventory` | Generate the Fabric best-in-class baseline inventory. | - | - | - |
| `validation` | `fabric-decision-data-coverage` | `active` | `polisyos-tools validation fabric-decision-data-coverage` | Validate Fabric decision-data trust-envelope coverage. | - | - | - |
| `validation` | `fabric-discovery-intelligence` | `active` | `polisyos-tools validation fabric-discovery-intelligence` | Validate Fabric Phase 9 discovery and entity-intelligence contracts. | - | - | - |
| `validation` | `fabric-processing-guarantees` | `active` | `polisyos-tools validation fabric-processing-guarantees` | Validate Fabric processing-guarantee, dedupe, CDC, and scale contracts. | - | - | - |
| `validation` | `fabric-product-integration` | `active` | `polisyos-tools validation fabric-product-integration` | Validate Fabric Phase 10 product/API integration closeout contracts. | - | - | - |
| `validation` | `fabric-schema-governance` | `active` | `polisyos-tools validation fabric-schema-governance` | Validate Fabric connector contract evolution against governance policy. | - | - | - |
| `validation` | `fabric-source-contracts` | `active` | `polisyos-tools validation fabric-source-contracts` | Validate Fabric SourceContract v2 coverage and source scorecards. | - | - | - |
| `validation` | `fabric-wave2-strict-closure` | `active` | `polisyos-tools validation fabric-wave2-strict-closure` | Validate strict Fabric Wave 2 best-in-class closure without Wave R scope. | - | - | - |
| `validation` | `generate-adr-index` | `active` | `polisyos-tools validation generate-adr-index` | Generate ADR TOML and Markdown indexes from ``docs/adr``. | - | - | - |
| `validation` | `generate-foundry-phase2-evidence` | `active` | `polisyos-tools validation generate-foundry-phase2-evidence` | Generate Phase 2 synthetic-world and judge evidence from enrolled JUnit reports. | - | - | - |
| `validation` | `generate-policy-evidence-capability-cards` | `active` | `polisyos-tools validation generate-policy-evidence-capability-cards` | Generate Markdown audit cards for active evidence capabilities. | - | - | - |
| `validation` | `inspect-evidence-bundles` | `active` | `polisyos-tools validation inspect-evidence-bundles` | Inspect selected serious evidence bundles for Phase 6.4 closeout. | - | - | - |
| `validation` | `inspect-policy-evidence-capability-index` | `active` | `polisyos-tools validation inspect-policy-evidence-capability-index` | Inspect the Policy Evidence Capability Index for operator/audit review. | - | - | - |
| `validation` | `inventory-legacy-quality-evidence` | `active` | `polisyos-tools validation inventory-legacy-quality-evidence` | Inventory and classify legacy production-quality evidence files. | - | - | - |
| `validation` | `name-collision-gate` | `active` | `polisyos-tools validation name-collision-gate` | Fail-closed Phase 1C cross-package directory-name collision gate. | - | - | - |
| `validation` | `production-quality-evidence-inventory` | `active` | `polisyos-tools validation production-quality-evidence-inventory` | Inventory production-quality evidence refs, fields, producers, and validators. | - | - | - |
| `validation` | `repository-best-in-class-phase0-7-inventory` | `active` | `polisyos-tools validation repository-best-in-class-phase0-7-inventory` | Read-only Phase 0.7 inventory for repository best-in-class remediation. | - | - | - |
| `validation` | `repository-last-mile-inventory` | `active` | `polisyos-tools validation repository-last-mile-inventory` | Read-only Phase 0.1 inventory for last-mile repository regressions. | - | - | - |
| `validation` | `repository-last-mile-shim-callers` | `active` | `polisyos-tools validation repository-last-mile-shim-callers` | Generate Phase 0.3 caller evidence for last-mile import compatibility shims. | - | - | - |
| `validation` | `repository-structure-phase0` | `active` | `polisyos-tools validation repository-structure-phase0` | Phase 0 repository-structure inventory and fail-closed gates. | - | - | - |
| `validation` | `repository-verification-inventory` | `active` | `polisyos-tools validation repository-verification-inventory` | Generate the Repository Best-In-Class Phase 0.4 verification inventory. | - | - | - |
| `validation` | `run-compilation-truthfulness-audit` | `active` | `polisyos-tools validation run-compilation-truthfulness-audit` | Run the W12.B compilation truthfulness audit over the universal corpus. | - | - | - |
| `validation` | `run-domain-coverage-critic-diversity-audit` | `active` | `polisyos-tools validation run-domain-coverage-critic-diversity-audit` | Run the W12.C domain coverage and critic diversity audit. | - | - | - |
| `validation` | `run-layer2-s14-universality-battery` | `active` | `polisyos-tools validation run-layer2-s14-universality-battery` | Run the Layer 2 S14 sealed universality assurance battery. | - | - | - |
| `validation` | `run-policy-design-case-bundle-replay-inspection` | `active` | `polisyos-tools validation run-policy-design-case-bundle-replay-inspection` | Run the W12.E bundle, replay, and inspection phase. | - | - | - |
| `validation` | `run-policy-design-case-cloud-one-lane-revalidation` | `active` | `polisyos-tools validation run-policy-design-case-cloud-one-lane-revalidation` | Run the W12.F cloud one-lane revalidation phase. | - | - | - |
| `validation` | `run-policy-design-case-local-validation-ladder` | `active` | `polisyos-tools validation run-policy-design-case-local-validation-ladder` | Run the Wave 12.A local Policy Design Case validation ladder. | - | - | - |
| `validation` | `run-policy-design-case-pass2-phase34-3` | `active` | `polisyos-tools validation run-policy-design-case-pass2-phase34-3` | Run Policy Design Case Pass 2 Phase 34.3 diagnostics. | - | - | - |
| `validation` | `run-policy-design-case-pass2-phase34-4` | `active` | `polisyos-tools validation run-policy-design-case-pass2-phase34-4` | Run Policy Design Case Pass 2 Phase 34.4 diagnostics. | - | - | - |
| `validation` | `run-policy-design-case-pass2-phase34-5` | `active` | `polisyos-tools validation run-policy-design-case-pass2-phase34-5` | Run Policy Design Case Pass 2 Phase 34.5 diagnostics. | - | - | - |
| `validation` | `run-policy-design-case-pass2-phase34-6` | `active` | `polisyos-tools validation run-policy-design-case-pass2-phase34-6` | Run Policy Design Case Pass 2 Phase 34.6 diagnostics. | - | - | - |
| `validation` | `run-policy-design-case-rollout-decision` | `active` | `polisyos-tools validation run-policy-design-case-rollout-decision` | Run the W12.G rollout decision phase. | - | - | - |
| `validation` | `run-universal-compilation-integration-realism-check` | `active` | `polisyos-tools validation run-universal-compilation-integration-realism-check` | Run I7-bis universal compilation integration realism check. | - | - | - |
| `validation` | `run-universal-outcome-corpus` | `active` | `polisyos-tools validation run-universal-outcome-corpus` | Run W12.D universal outcome corpus evidence over W6/W7/W8. | - | - | - |
| `validation` | `validate-foundry-phase0-closure` | `active` | `polisyos-tools validation validate-foundry-phase0-closure` | Emit a machine-readable closure report for Foundry Phase 0. | - | - | - |
| `validation` | `validate-foundry-phase2-closure` | `active` | `polisyos-tools validation validate-foundry-phase2-closure` | Emit a machine-readable closure report for Foundry Phase 2. | - | - | - |
| `validation` | `validate-phase-closure` | `active` | `polisyos-tools validation validate-phase-closure` | Emit a machine-readable closure report for the causal research phases. | - | - | - |
| `testing` | `check-fabric-exception-baseline` | `active` | `polisyos-tools testing check-fabric-exception-baseline` | Guard against broad exception hygiene regressions in Fabric. | - | - | - |
| `testing` | `check-playwright-quarantines` | `active` | `polisyos-tools testing check-playwright-quarantines` | Validate Playwright flaky/quarantine tags against the shared quarantine registry. | - | - | - |
| `testing` | `local-integration-stack` | `active` | `polisyos-tools testing local-integration-stack` | Run the local runtime-dashboard integration stack and smoke profile. | - | - | - |
| `testing` | `local-prod-debug-probe` | `active` | `polisyos-tools testing local-prod-debug-probe` | Run lightweight local production-debug validation probes. | - | - | - |
| `testing` | `mutation` | `active` | `polisyos-tools testing mutation` | Run canonical mutmut-based mutation suites for Foundry and Scientist. | - | - | - |
| `testing` | `repeat-pytest` | `active` | `polisyos-tools testing repeat-pytest` | Repeat one pytest invocation multiple times and fail on the first red run. | - | - | - |
| `testing` | `report-test-economics` | `active` | `polisyos-tools testing report-test-economics` | Summarize slow suites and unstable tests from JUnit XML plus quarantine metadata. | - | - | - |
| `testing` | `report-test-ratchets` | `active` | `polisyos-tools testing report-test-ratchets` | Report package-level mirror and property-test ratchets. | - | - | - |
| `testing` | `runtime-resilience-matrix` | `active` | `polisyos-tools testing runtime-resilience-matrix` | Build the deterministic runtime resilience matrix for production-quality gates. | - | - | - |
| `ci` | `check-action-freshness` | `active` | `polisyos-tools ci check-action-freshness` | Audit pinned third-party GitHub Actions against latest upstream releases. | - | - | - |
| `ci` | `check-fabric-schema-registry` | `active` | `polisyos-tools ci check-fabric-schema-registry` | CI wrapper for the Fabric schema governance gate. | - | - | - |
| `ci` | `check-foundry-domain-coverage` | `active` | `polisyos-tools ci check-foundry-domain-coverage` | Enforce Foundry coverage thresholds by domain instead of only globally. | - | - | - |
| `ci` | `check-phase7-ratchet` | `active` | `polisyos-tools ci check-phase7-ratchet` | Enforce the Phase 7 ratchet checklist for new subsystems and major surfaces. | - | - | - |
| `ci` | `check-workflow-policy` | `active` | `polisyos-tools ci check-workflow-policy` | Lightweight repo policy checks for GitHub Actions workflows. | - | - | - |
| `ci` | `check-policyos-production-quality-best-in-class` | `active` | `polisyos-tools ci check-policyos-production-quality-best-in-class` | Aggregate PolicyOS best-in-class production-quality readiness evidence. | - | - | - |
| `ci` | `check-scientist-benchmark-authority` | `active` | `polisyos-tools ci check-scientist-benchmark-authority` | Validate the Scientist Phase 1.5 benchmark authority surface. | - | - | - |
| `ci` | `check-scientist-best-in-class-phase1-0` | `active` | `polisyos-tools ci check-scientist-best-in-class-phase1-0` | Validate the Scientist best-in-class Phase 1.0 reconciliation docs. | - | - | - |
| `ci` | `check-scientist-best-in-class-phase1-1` | `active` | `polisyos-tools ci check-scientist-best-in-class-phase1-1` | Validate the Scientist best-in-class Phase 1.1 claim spine. | - | - | - |
| `ci` | `check-scientist-best-in-class-phase1-2` | `active` | `polisyos-tools ci check-scientist-best-in-class-phase1-2` | Validate the Scientist best-in-class Phase 1.2 research DAG sidecar. | - | - | - |
| `ci` | `check-scientist-best-in-class-phase1-3` | `active` | `polisyos-tools ci check-scientist-best-in-class-phase1-3` | Validate the Scientist best-in-class Phase 1.3 deep research evidence stack. | - | - | - |
| `ci` | `check-scientist-best-in-class-phase1-4` | `active` | `polisyos-tools ci check-scientist-best-in-class-phase1-4` | Validate the Scientist best-in-class Phase 1.4 agent promotion surface. | - | - | - |
| `ci` | `check-scientist-best-in-class-phase1-6` | `active` | `polisyos-tools ci check-scientist-best-in-class-phase1-6` | Validate the Scientist Phase 1.6 human oversight surface. | - | - | - |
| `ci` | `check-scientist-best-in-class-phase2-0` | `active` | `polisyos-tools ci check-scientist-best-in-class-phase2-0` | Validate the Scientist best-in-class Phase 2.0 operating contract. | - | - | - |
| `ci` | `check-scientist-best-in-class-phase2-1` | `active` | `polisyos-tools ci check-scientist-best-in-class-phase2-1` | Validate the Scientist best-in-class Phase 2.1 Claim Ledger surface. | - | - | - |
| `ci` | `check-scientist-best-in-class-phase2-2` | `active` | `polisyos-tools ci check-scientist-best-in-class-phase2-2` | Validate the Scientist best-in-class Phase 2.2 Research DAG replay surface. | - | - | - |
| `ci` | `check-scientist-best-in-class-phase2-3` | `active` | `polisyos-tools ci check-scientist-best-in-class-phase2-3` | Validate Scientist best-in-class Phase 2.3 VOI scheduler readiness. | - | - | - |
| `ci` | `check-scientist-best-in-class-phase2-4` | `active` | `polisyos-tools ci check-scientist-best-in-class-phase2-4` | Validate Scientist best-in-class Phase 2.4 reflexive-memory readiness. | - | - | - |
| `ci` | `check-scientist-best-in-class-phase2-5` | `active` | `polisyos-tools ci check-scientist-best-in-class-phase2-5` | Validate Scientist best-in-class Phase 2.5 adversarial challenge factory. | - | - | - |
| `ci` | `check-scientist-best-in-class-phase2-6` | `active` | `polisyos-tools ci check-scientist-best-in-class-phase2-6` | Validate Scientist best-in-class Phase 2.6 continuous governance. | - | - | - |
| `ci` | `check-scientist-best-in-class-phase2-7` | `active` | `polisyos-tools ci check-scientist-best-in-class-phase2-7` | Validate Scientist best-in-class Phase 2.7 decision-grade compiler. | - | - | - |
| `ci` | `check-scientist-best-in-class-wave1` | `active` | `polisyos-tools ci check-scientist-best-in-class-wave1` | Validate the Scientist Wave 1 best-in-class acceptance surface. | - | - | - |
| `ci` | `check-scientist-best-in-class-wave2` | `active` | `polisyos-tools ci check-scientist-best-in-class-wave2` | Validate the Scientist Wave 2 best-in-class closeout surface. | - | - | - |
| `ci` | `check-scientist-phase0-gate` | `active` | `polisyos-tools ci check-scientist-phase0-gate` | Validate the repo-tracked Scientist Phase 0 acceptance barrier. | - | - | - |
| `ci` | `check-scientist-phase1-gate` | `active` | `polisyos-tools ci check-scientist-phase1-gate` | Validate the repo-tracked Scientist Phase 1 acceptance barrier. | - | - | - |
| `ci` | `check-scientist-phase2-gate` | `active` | `polisyos-tools ci check-scientist-phase2-gate` | Legacy compatibility wrapper for the canonical Foundry Phase 2 closure validator. | - | - | - |
| `ci` | `check-scientist-phase2-ratchet` | `active` | `polisyos-tools ci check-scientist-phase2-ratchet` | Ratchet Phase 2 Scientist maintainability debt on targeted hot-path surfaces. | - | - | - |
| `ci` | `check-scientist-reliability` | `active` | `polisyos-tools ci check-scientist-reliability` | Assemble the Scientist Gate 2 reliability scorecard from CI evidence. | - | - | - |

### `ops`

| Category | Command | Status | Canonical | Summary | Replacement | Aliases | Dependencies |
| -------- | ------- | ------ | --------- | ------- | ----------- | ------- | ------------ |
| `calibration` | `compare-shards` | `active` | `polisyos-tools calibration compare-shards` | Compare calibration results across Lex shard hypotheses. | - | - | - |
| `cloud` | `build-priority-manifests` | `active` | `polisyos-tools cloud build-priority-manifests` | Build priority queue manifests for the Lex production pipeline. | - | - | - |
| `cloud` | `build-queue3-waves` | `active` | `polisyos-tools cloud build-queue3-waves` | Split Queue 3 current manifests into five priority waves with six shards. | - | - | - |
| `cloud` | `canonical-auto-approve` | `active` | `polisyos-tools cloud canonical-auto-approve` | Canonical variable auto-approval with preview and staged publish. | - | - | - |
| `cloud` | `check-progress` | `active` | `polisyos-tools cloud check-progress` | Inspect remote shard progress through the canonical shard helper surface. | - | - | - |
| `cloud` | `deploy-to-server` | `active` | `polisyos-tools cloud deploy-to-server` | Deploy one prepared shard bundle to a reviewed remote server workflow. | - | - | `cloud.prepare-shards`, `cloud.setup-server` |
| `cloud` | `gcp-preflight` | `active` | `polisyos-tools cloud gcp-preflight` | Validate a GCP worker without launching the Lex processing pipeline. | - | - | - |
| `cloud` | `merge-shards` | `active` | `polisyos-tools cloud merge-shards` | Merge pipeline output shards into a single unified graph snapshot. | - | - | `cloud.run-lex-from-manifest` |
| `cloud` | `prepare-shards` | `active` | `polisyos-tools cloud prepare-shards` | Prepare canonical shard assets under ``ops/cloud/deploy/assets``. | - | - | - |
| `cloud` | `run-datasets-validation` | `active` | `polisyos-tools cloud run-datasets-validation` | Run the canonical datasets validation cloud wrapper. | - | - | `cloud.run-pipeline` |
| `cloud` | `run-diagnostic` | `active` | `polisyos-tools cloud run-diagnostic` | Run the canonical diagnostic cloud pipeline wrapper. | - | - | `cloud.run-pipeline` |
| `cloud` | `run-lex-from-manifest` | `active` | `polisyos-tools cloud run-lex-from-manifest` | Run the Lex sharded pipeline from a pre-materialized JSONL.ZST shard manifest. | - | - | `cloud.gcp-preflight` |
| `cloud` | `run-pipeline` | `active` | `polisyos-tools cloud run-pipeline` | Run the canonical remote academic pipeline wrapper. | - | - | - |
| `cloud` | `run-remaining-stages` | `deprecated` | `polisyos-tools cloud run-remaining-stages` | Resume a reviewed snapshot through the canonical remaining-stages bridge. | cloud run-pipeline --resume --snapshot-root ... | - | `cloud.run-pipeline` |
| `cloud` | `setup-server` | `active` | `polisyos-tools cloud setup-server` | Run the canonical cloud host setup helper. | - | - | - |
| `data` | `build-academic-gold-candidates` | `active` | `polisyos-tools data build-academic-gold-candidates` | Build seed candidate pools for manual academic gold annotation. | - | - | - |
| `data` | `build-expert-review-bundle` | `active` | `polisyos-tools data build-expert-review-bundle` | Build a single expert-ready JSON bundle for screen and claim gold review. | - | - | - |
| `data` | `generate-wvs-registry` | `active` | `polisyos-tools data generate-wvs-registry` | Generate WVS indicator registry YAML from Excel codebook + CSV data. | - | - | - |
| `data` | `record-fixtures` | `active` | `polisyos-tools data record-fixtures` | Record API response fixtures for connector integration tests. | - | - | - |
| `ops-experiments` | `run-msme-deadline-suite` | `active` | `polisyos-tools ops-experiments run-msme-deadline-suite` | Deadline cloud harness for the PolicyOS MSME qualification experiments. | - | - | - |
| `ops-experiments` | `run-msme-discovery-addendum-20260501` | `active` | `polisyos-tools ops-experiments run-msme-discovery-addendum-20260501` | Heavy causal-discovery addendum for the MSME final experiment suite. | - | - | - |
| `ops-experiments` | `run-msme-e2e-showcase` | `active` | `polisyos-tools ops-experiments run-msme-e2e-showcase` | End-to-end PolicyOS showcase experiments for the MSME thesis deadline. | - | - | - |
| `ops-experiments` | `run-msme-final-fresg-suite` | `active` | `polisyos-tools ops-experiments run-msme-final-fresg-suite` | Final PolicyOS MSME thesis experiment suite. | - | - | - |
| `ops-experiments` | `run-msme-final-fresg-suite-v2` | `active` | `polisyos-tools ops-experiments run-msme-final-fresg-suite-v2` | Deadline-safe v2 MSME PolicyOS final experiment suite. | - | - | - |
| `ops-experiments` | `run-msme-final-fresg-suite-v3` | `active` | `polisyos-tools ops-experiments run-msme-final-fresg-suite-v3` | Corrective v3 MSME PolicyOS final experiment suite. | - | - | - |
| `ops-experiments` | `run-msme-final-v3-cloud-rerun` | `active` | `polisyos-tools ops-experiments run-msme-final-v3-cloud-rerun` | Launch the MSME final v3 full rerun on the current GCP VM and download artifacts. | - | - | - |
| `ops-experiments` | `run-msme-grand-tournament-v2` | `active` | `polisyos-tools ops-experiments run-msme-grand-tournament-v2` | Grand PolicyOS MSME experiment for the 2026-05-01 thesis deadline. | - | - | - |
| `ops-experiments` | `run-policyos-real-e2e-cloud` | `active` | `polisyos-tools ops-experiments run-policyos-real-e2e-cloud` | Launch a PolicyOS natural-language E2E run on a GCP VM. | - | - | - |
| `migrations` | `migrate` | `active` | `polisyos-tools migrations migrate` | Migrate schema artifacts to their declared target versions. | - | - | - |
| `migrations` | `migrate-duckdb-to-pg` | `active` | `polisyos-tools migrations migrate-duckdb-to-pg` | Migrate tenant-scoped data from DuckDB to PostgreSQL. | - | - | - |
| `release` | `build-release-notes` | `active` | `polisyos-tools release build-release-notes` | Render Keep-a-Changelog style release notes from structured TOML fragments. | - | - | - |
| `release` | `check-compatibility-release-gates` | `active` | `polisyos-tools release check-compatibility-release-gates` | Report Phase 5.10 compatibility release-gate readiness. | - | - | - |
| `release` | `check-operability-release-gates` | `active` | `polisyos-tools release check-operability-release-gates` | Fail-closed Phase 6.3 operability, release, and supply-chain gates. | - | - | - |
| `release` | `check-release-artifact-sizes` | `active` | `polisyos-tools release check-release-artifact-sizes` | Check release artifact sizes against repo-tracked thresholds. | - | - | - |
| `release` | `check-release-version` | `active` | `polisyos-tools release check-release-version` | Validate that a release tag matches packaged versions and fragment state. | - | - | - |
| `release` | `evaluate-vuln-report` | `active` | `polisyos-tools release evaluate-vuln-report` | Evaluate vulnerability reports against PolicyOS release policy exceptions. | - | - | - |
| `release` | `run-release-canary` | `active` | `polisyos-tools release run-release-canary` | Launch a live runtime canary from the installed release artifact and probe it. | - | - | - |
| `release` | `stage-release-snapshot` | `active` | `polisyos-tools release stage-release-snapshot` | Freeze unreleased fragments into an immutable versioned release snapshot. | - | - | `release.check-release-version`, `runtime.export-runtime-openapi` |
| `runtime` | `archive-legacy-runs` | `active` | `polisyos-tools runtime archive-legacy-runs` | runtime/archive_legacy_runs | - | - | - |
| `runtime` | `backfill-decision-validity` | `active` | `polisyos-tools runtime backfill-decision-validity` | runtime/backfill_decision_validity | - | - | - |
| `runtime` | `canary-matrix` | `active` | `polisyos-tools runtime canary-matrix` | List the PolicyOS production-quality canary matrix baseline. | - | - | - |
| `runtime` | `check-runtime-api-contract` | `active` | `polisyos-tools runtime check-runtime-api-contract` | runtime/check_runtime_api_contract | - | - | - |
| `runtime` | `export-runtime-openapi` | `active` | `polisyos-tools runtime export-runtime-openapi` | runtime/export_runtime_openapi | - | - | - |
| `runtime` | `generate-runtime-client` | `active` | `polisyos-tools runtime generate-runtime-client` | runtime/generate_runtime_client | - | - | `runtime.export-runtime-openapi` |
| `runtime` | `inventory-legacy-runs` | `active` | `polisyos-tools runtime inventory-legacy-runs` | runtime/inventory_legacy_runs | - | - | - |
| `runtime` | `local-production-canary` | `active` | `polisyos-tools runtime local-production-canary` | Run a local production-data NL canary and write a sanitized evidence bundle. | - | - | - |
| `runtime` | `provider-quality-ledger` | `active` | `polisyos-tools runtime provider-quality-ledger` | Build provider/model quality drift ledgers from canary lane evidence. | - | - | - |
| `runtime` | `replay-canary-bundle` | `active` | `polisyos-tools runtime replay-canary-bundle` | Build deterministic replay refs for a sanitized canary evidence bundle. | - | - | - |
| `runtime` | `run-canary-matrix` | `active` | `polisyos-tools runtime run-canary-matrix` | Execute real PolicyOS canary matrix lanes and emit a lane scorecard summary. | - | - | - |
| `runtime` | `runtime-state-cleanup` | `active` | `polisyos-tools runtime runtime-state-cleanup` | Clean registered .polisyos runtime-state slots with dry-run summaries. | - | - | - |
| `ukraine_data` | `build-edr-identity-seed-candidates` | `active` | `polisyos-tools ukraine_data build-edr-identity-seed-candidates` | ukraine_data/build_edr_identity_seed_candidates | - | - | - |
| `ukraine_data` | `build-p1-source-bindings` | `active` | `polisyos-tools ukraine_data build-p1-source-bindings` | Build pragmatic D1 source bindings from downloaded public raw layers. | - | - | - |
| `ukraine_data` | `build-spending-contracts-procurement-proxy` | `active` | `polisyos-tools ukraine_data build-spending-contracts-procurement-proxy` | Materialize the Spending contracts procurement proxy as a standalone source run. | - | - | - |
| `ukraine_data` | `fetch-p0-sources` | `active` | `polisyos-tools ukraine_data fetch-p0-sources` | Fetch and record official P0 source inputs for the Ukraine build stack. | - | - | - |
| `ukraine_data` | `fetch-p1-p2-public-sources` | `active` | `polisyos-tools ukraine_data fetch-p1-p2-public-sources` | Fetch and record public D1/D3 raw source inputs for the Ukraine build stack. | - | - | - |
| `ukraine_data` | `harvest-prozorro-contract-details` | `active` | `polisyos-tools ukraine_data harvest-prozorro-contract-details` | Resumable server-side harvest of detailed Prozorro contract records. | - | - | - |
| `ukraine_data` | `harvest-prozorro-contract-feed` | `active` | `polisyos-tools ukraine_data harvest-prozorro-contract-feed` | Resumable server-side harvest of the Prozorro public contracts feed. | - | - | - |
| `ukraine_data` | `harvest-spending-contracts-by-disposer` | `active` | `polisyos-tools ukraine_data harvest-spending-contracts-by-disposer` | Resumable server-side harvest for Spending contracts grouped by disposerId. | - | - | - |
| `ukraine_data` | `harvest-spending-daily` | `active` | `polisyos-tools ukraine_data harvest-spending-daily` | Resumable server-side backfill for Spending.gov.ua daily transactions. | - | - | - |
| `ukraine_data` | `pre-shard-lex-corpus` | `active` | `polisyos-tools ukraine_data pre-shard-lex-corpus` | Pre-materialize the ЄДРНПА corpus into per-pass shard JSONL.ZST manifests. | - | - | - |

### `research`

| Category | Command | Status | Canonical | Summary | Replacement | Aliases | Dependencies |
| -------- | ------- | ------ | --------- | ------- | ----------- | ------- | ------------ |
| `benchmarks` | `bench-domain` | `active` | `polisyos-tools benchmarks bench-domain` | Compatibility wrapper for the canonical JAX domain benchmark entry point. | - | - | - |
| `benchmarks` | `bench-simulation` | `active` | `polisyos-tools benchmarks bench-simulation` | Compatibility wrapper for the canonical JAX simulation benchmark entry point. | - | - | - |
| `benchmarks` | `benchmark-lex-llm-steady-state` | `active` | `polisyos-tools benchmarks benchmark-lex-llm-steady-state` | Compatibility wrapper for the Lex steady-state benchmark entry point. | - | - | - |
| `benchmarks` | `benchmark-lex-llm-sweep` | `active` | `polisyos-tools benchmarks benchmark-lex-llm-sweep` | Compatibility wrapper for the Lex sweep benchmark entry point. | - | - | - |
| `benchmarks` | `build-release-summary` | `active` | `polisyos-tools benchmarks build-release-summary` | Merge benchmark JSON artifacts into a contour-aware release summary. | - | - | - |
| `benchmarks` | `prepare-real-benchmark-data` | `active` | `polisyos-tools benchmarks prepare-real-benchmark-data` | Download a lightweight real-data benchmark pack for local execution. | - | - | - |
| `benchmarks` | `run-all` | `active` | `polisyos-tools benchmarks run-all` | Run the benchmark suite registry through the canonical tools surface. | - | - | - |
| `benchmarks` | `run-local-sota-profile` | `active` | `polisyos-tools benchmarks run-local-sota-profile` | Run the local SOTA benchmark profile through the zoned research tooling surface. | - | - | - |
| `benchmarks` | `run-parallel` | `active` | `polisyos-tools benchmarks run-parallel` | Parallel benchmark runner with worker and memory-aware scheduling. | - | - | - |
| `demos` | `run-export-demo` | `deprecated` | `polisyos-tools demos run-export-demo` | Deprecated reference stub for the removed Foundry engine export demo. | runtime export-runtime-openapi | - | - |
| `demos` | `run-foundry-ws9-frontier-demo` | `active` | `polisyos-tools demos run-foundry-ws9-frontier-demo` | demos/run_foundry_ws9_frontier_demo | - | - | - |
| `demos` | `run-laffer-demo` | `active` | `polisyos-tools demos run-laffer-demo` | demos/run_laffer_demo | - | - | - |
| `demos` | `run-mechanism-design` | `deprecated` | `polisyos-tools demos run-mechanism-design` | End-to-end demo: Mechanism Design через IR/Compiler/Foundry runtime + JAX grad. | benchmarks bench-domain | - | - |
| `demos` | `run-udf-hybrid-demo` | `quarantined` | `polisyos-tools demos run-udf-hybrid-demo` | demos/run_udf_hybrid_demo | diagnostics check-setup | - | - |
| `demos` | `run-udf-query-demo` | `quarantined` | `polisyos-tools demos run-udf-query-demo` | demos/run_udf_query_demo | diagnostics check-setup | - | - |
| `research-experiments` | `filter-topics` | `active` | `polisyos-tools research-experiments filter-topics` | Filter OpenAlex topics down to policy-relevant rows. | - | - | - |
| `research-experiments` | `organize-relevant-topics` | `active` | `polisyos-tools research-experiments organize-relevant-topics` | Theme-based ordering for relevant OpenAlex topics. | - | - | - |

## Retired Compatibility Wrappers

Legacy path-based wrappers are retained only for the Phase 1D migration window.
All wrappers emit a deprecation warning and sunset on 2026-09-01.

| Legacy path | Replacement |
| ----------- | ----------- |

## Deprecated And Quarantined Commands

| Category | Command | Status | Replacement | Reason |
| -------- | ------- | ------ | ----------- | ------ |
| `diagnostics` | `check-udf-perf` | `quarantined` | diagnostics check-setup | legacy UDF stack depends on modules that are not present in the current package |
| `cloud` | `run-remaining-stages` | `deprecated` | cloud run-pipeline --resume --snapshot-root ... | remaining-stage execution is now a compatibility bridge to the reviewed resume workflow |
| `demos` | `run-export-demo` | `deprecated` | runtime export-runtime-openapi | demo uses historical Foundry import paths and is retained only as reference material |
| `demos` | `run-mechanism-design` | `deprecated` | benchmarks bench-domain | manual research demo predates the current Foundry method registry |
| `demos` | `run-udf-hybrid-demo` | `quarantined` | diagnostics check-setup | legacy hybrid UDF demo depends on removed UDF/graph-store APIs |
| `demos` | `run-udf-query-demo` | `quarantined` | diagnostics check-setup | legacy UDF demo depends on the removed fabric.udf module family |

## Policy

- `tools/` is the only canonical executable surface.
- The former product-root script tree is retired; use `polisyos-tools` commands directly.
- New tools must be added to the zone/category manifest before creating any new top-level `tools/<category>` package.
- Benchmark commands live under `tools/research/benchmarks`; root `benchmarks/` is benchmark-domain support code.

## Dependency Graph

```mermaid
graph TD
  "cloud.gcp-preflight" --> "cloud.run-lex-from-manifest"
  "cloud.prepare-shards" --> "cloud.deploy-to-server"
  "cloud.run-lex-from-manifest" --> "cloud.merge-shards"
  "cloud.run-pipeline" --> "cloud.run-datasets-validation"
  "cloud.run-pipeline" --> "cloud.run-diagnostic"
  "cloud.run-pipeline" --> "cloud.run-remaining-stages"
  "cloud.setup-server" --> "cloud.deploy-to-server"
  "diagnostics.gen-schema" --> "diagnostics.abi-diff"
  "release.check-release-version" --> "release.stage-release-snapshot"
  "runtime.export-runtime-openapi" --> "release.stage-release-snapshot"
  "runtime.export-runtime-openapi" --> "runtime.generate-runtime-client"
  "workspace.doctor" --> "workspace.bootstrap"
  "workspace.doctor" --> "workspace.verify"
  "workspace.format-check" --> "workspace.lint-full"
  "workspace.lint-fast" --> "workspace.lint-full"
  "workspace.python-base-basedpyright" --> "workspace.lint-full"
  "workspace.python-base-mypy" --> "workspace.lint-full"
```

_Repo root: `/Users/deniskopylov/polisyos/policy-engine`_
