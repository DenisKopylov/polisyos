# Local probe hygiene boundary (2026-10-10)

This change is limited to style, annotations, and readable stdout for the existing local probes below. It does not update product source, tests, tools, or canonical reports. Probe bodies were not executed. The Python AST parse and JavaScript syntax check are syntax-only receipts, not runtime validation or evidence that a historical probe result still reproduces. The existing `sitecustomize` tracing and monkeypatch order is preserved; historical receipts are untouched.

The initial Ruff pass found 102 diagnostics across the 13 Python files. The listed Python files now pass Ruff and Ruff format. The MJS file is unchanged and passes `node --check`. Prettier was unavailable in this checkout: `corepack pnpm exec prettier --check docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/can-options/locale-counts.mjs` exited 254 with `Command "prettier" not found`. The Node syntax result does not establish MJS formatting.

The complete commands, stdout/stderr bytes, exit codes, and initial/current SHA-256 values are retained in [the ignored receipt manifest](../raw/probe-hygiene-20261010/manifest.json), alongside each command's full output. Current scope denominator: 14 nonignored untracked `.py`/`.mjs` files under `LOCAL`.

| Exact path under `LOCAL/` | Hygiene edit |
|---|---|
| `berl-persisted-law/validation/consumer_census.py` | Changed |
| `berl-persisted-law/validation/format_baseline_probe.py` | Changed |
| `berl-persisted-law/validation/property_removal_probe.py` | Changed |
| `can-options/locale-counts.mjs` | Unchanged |
| `can-options/raw_profile_probe.py` | Changed |
| `can-options/replay_producer_census.py` | Changed |
| `dx0-native/sota-trace/sitecustomize.py` | Changed |
| `i1-c05/checks/b61-child-stack/i1_c05_child_trace.py` | Changed |
| `i1-c05/checks/b61-typed-worker/spawn-task-smoke.py` | Changed |
| `i1-c05/checks/held14-source-provenance.py` | Unchanged |
| `r4-workload/outputs/source-census.py` | Changed |
| `reviews/b61-postreview-removal/sitecustomize.py` | Changed |
| `s1-law-intakes/validation/B194-source-consumer-census.py` | Unchanged |
| `shared-refs/selected_ref_census.py` | Changed |
