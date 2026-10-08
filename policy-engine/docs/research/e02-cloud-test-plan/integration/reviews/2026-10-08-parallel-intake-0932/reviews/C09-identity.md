# C09 source identity and receipt audit

Scope: read-only ancestry, exact source footprint, receipt/manifests, and admission-origin identity. No tests, environments, source edits, or ref changes were performed for this audit.

## Source identity

- Slice base `f00dd7661a8d3329fb1fa1b049decb0d1d2f277b` (tree `d9a4e73a0e85fa11f865bf643c1b63fbe66c2767`) is an ancestor of candidate `ee0b2c85289d8c5537ba4e01713d9be71e2f557e` (tree `072e8906ac69f5b3589550a8bd9d57b4cb41b4a3`). Candidate parent is `d095dbd5527ae8462f85c382a40877f16574c58a`; base, d095, and ee ancestry checks passed.
- Handoff receipt commit `514f90058104f7dd8ada1c83b8bf5f62bfc33b88` has parent ee and branch `origin/codex/e02-E-c09-20261008` resolves to that exact commit. The handoff adds 43 files, all under `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/parallel-20261008-c09/`; it changes no implementation paths. Handoff is not an ancestor of the current integration HEAD `f00dd7661a8d3329fb1fa1b049decb0d1d2f277b`.
- The exact base-to-ee source footprint is five paths: added release fragment `policy-engine/release-fragments/unreleased/2026-10-08-c09-backtest-interval-admission.toml`; modified backtesting `README.md`, `evaluator.py`, and `orchestrator.py`; and added `tests/unit/scientist/methods/backtesting/test_evaluator_interval_admission.py`. This is 2 production Python files, 1 unit test, 1 README, and 1 release companion. Recorded base/candidate blob IDs in the receipt were checked against Git for all five paths and match.
- The only d095-to-ee delta is the release-fragment compatibility value correction, `generated_client_compatibility = "not_required"` to `"not_applicable"` (blob `23291a90ee93d0d12a1aec194e3031a2c8a71660` → `68acb8d97ec90984e5fe9a47384bae6878ff0b96`). No source or test path changed in that correction.

## Receipt and evidence

The committed receipt is `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/parallel-20261008-c09/interval-admission.json` at 514f900. It binds base f00, candidate ee, and their trees above; lists the five-path full footprint; and sets `source_acceptance_G` and `formal_finding_closure` to `not_issued` with `closed_ids=[]`. The receipt therefore does not claim G acceptance or finding closure, and its implementation commit list contains d095 and ee, not the later handoff commit.

The receipt's `artifact-manifest.json` has 40 payload entries. A Git tree walk of the exact `.../interval-admission/` subtree at 514f900 found 41 tracked files: the 40 payloads plus the manifest itself. All 40 listed payloads were present and their byte lengths and SHA-256 values matched the manifest (40/40; denominator is the 40 manifest entries, with the self-manifest excluded). The receipt and manifest are source-reported evidence; this audit verified identity and hashes, not the reported test executions.

Admission origin is explicitly cross-referenced: carrier `de7b08ebbac72232c98d96ea74c3c0410864a7ba` and manifest `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/ORCH03/parallel-20261008-admission/manifest.json` resolve via `origin/codex/e02-F-closeout-20261006`. The carrier is not an ancestor of the C09 base or handoff. The manifest's create/resume compressed payloads decode to the two SHA-256 values recorded in the C09 receipt; their raw sizes and hashes also match that manifest. Treat this as hash-verified, cross-branch referenced admission evidence, not ancestry-bound C09 evidence.

The receipt reports baseline and candidate suites, removal probes, and an independent review, with explicit limitations. They were not rerun here and are not fresh execution receipts. This audit establishes commit/receipt/evidence identity only; it makes no claim that the C09 behavior passed local or production verification.
