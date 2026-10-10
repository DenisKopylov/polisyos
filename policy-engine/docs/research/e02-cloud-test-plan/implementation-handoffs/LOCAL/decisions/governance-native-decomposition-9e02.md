# Governance decomposition and IR artifact bridge

## Scope and classification

Implementation base: `9e02a9f49c8b01026327a9f7c7e18711b13a96f2` (tree `881a950dccb7cdefacc636515aa7dd2bceadf928`). The source changes separate two repairs:

1. **Same-class P40 module-complexity repair.** `run_normative_arbitration.py` and `run_governance.py` were over the registered 1,000-logical-line boundary and contained mixed responsibilities. The second module is the same class at a deeper point, so the repair widened into responsibility-level helpers rather than a branch-specific extraction. Normative calculations moved to `normative_arbitration_calculations.py`; gate request/replay helpers moved to `governance_gate_requests.py`. The original modules retain their public paths, node entry points, and imports for the former helper names. Ordering, verdict selection, persisted payloads, and the existing state-branching seam remain in place.
2. **Separate shared-boundary runtime defect.** The exact-base focused run had five real downstream failures because `_run_governance_checks` put the Core CAS in pass state and the generic optional-IR resolver passed it straight to IR loaders. The common resolver now calls the existing `ensure_ir_artifact_store` immediately before `load_model`. Core `_store` stays a Core store everywhere else. This fixes the shared property at one boundary; it does not change any governance rule or expected outcome.

Pattern pass: P27/P31/P38/P40/P41. P38 divergence was concrete: the resolver selected the correct persisted ref but supplied an object that did not implement the IR `ArtifactStore` protocol; the loader failed at that boundary. The existing adapter is the distinguishing bridge. P41 provenance is bounded to the exact 9e02 baseline and the pre-edit source hashes below. No new law, authority, status, or G semantic choice is introduced; formal G acceptance/closure is not claimed.

## Result and verification

The unchanged six-file governance baseline moved from 5 failures / 27 passes to **32 passed**. The failing assertions were preserved. The complete post-repair output is `LOCAL/raw/governance-focused-post-bridge-final.txt`; pre-edit output and source hashes remain in the existing `LOCAL/raw/governance-baseline-9e02/` and `LOCAL/raw/governance-pre-edit-source-shas.txt` receipts.

Persisted-reference coverage now exercises semantic consumption for normative arbitration, human review, refutation, SUTVA, and cross-graph evidence. The existing equity test already exercised a persisted report. The generic resolver test covers a valid Core-store-to-IR load, wrong kind, a syntactically valid but unavailable profile hash, corrupt persisted content, and an absent optional ref. The Core-only confidence path continues to use the raw Core store. Results:

- Six-file baseline: 32 passed; `LOCAL/raw/governance-focused-post-bridge-final.txt`.
- Resolver, all six helper consumers, equity, and Core confidence: 53 passed; `LOCAL/raw/governance-ir-consumers-final.txt`.
- Incentive compatibility plus calibration governance/leaderboard controls: 19 passed; `LOCAL/raw/governance-core-control-positive.txt`.
- The first additional confidence/calibration control run exposed three test-input defects and is retained as `LOCAL/raw/governance-core-control-known-failures.txt`. The test-only companion repair now uses the actual `CalibrationRunRunner` to create and persist the selected `scientist.calibration_candidate`; it leaves the downstream calibration selection and row-effect assertions unchanged. For confidence, the empty-envelope case remains a passing empty-result positive, the metadata-only “healthy” envelope is asserted as typed admission-limited, and a real `PropagateUncertaintyNode` output is checked through CAS and `ConfidencePass`; the real producer remains limited because the current code has no admitted draw/verifier chain. The exact 35-test repaired output is `LOCAL/raw/governance-core-control-fixture-repair.txt`.
- Expanded final confidence, incentive, and calibration control suite: **62 passed**, output in `LOCAL/raw/governance-core-controls-final.txt`. The control tests include both repaired files and remain focused; no numerical fit or full suite was run.
- There is no existing genuine admitted-positive propagated-envelope fixture/API. A bounded G decision packet describes the authority and producer/verifier work required for one: `LOCAL/decisions/confidence-propagation-admission-g-choice.md`. No new evidence law or fake verifier was added.
- Ruff check, Ruff formatting check, explicit C901 probe, and `py_compile` passed over the original source slice. Ruff check/format/C901 and `py_compile` also pass over the two test-only companion files.
- Ruff check, Ruff formatting check, explicit C901 probe, and `py_compile` over changed source: exit 0.

The repository module-size counter excludes blank and comment-only lines. Measured physical/logical lines are:

| Module | Physical | Logical |
| --- | ---: | ---: |
| `run_normative_arbitration.py` | 630 | 583 |
| `normative_arbitration_calculations.py` | 706 | 618 |
| `run_governance.py` | 1,018 | 930 |
| `governance_gate_requests.py` | 451 | 404 |

All four are under the 1,000 logical-line boundary. Explicit C901 checking passed with the repository Ruff threshold.

## Exact source/test footprint

Current SHA-256 values are recorded as `path — sha256`:

```text
src/polisyos/scientist/nodes/builtins/governance/run_normative_arbitration.py — ec9cd1b370943f564875e91ea2c62058b06e88615699ad6533d1922039a7e9ea
src/polisyos/scientist/nodes/builtins/governance/normative_arbitration_calculations.py — d168ec331b803fc2ce01bc089e1ece4adfb9b9647c459accb3a6480fb021b623
src/polisyos/scientist/nodes/builtins/governance/run_governance.py — f0632804853a0c00747fec319b67021f635c21e5f485cea53eb2269be5efcfd9
src/polisyos/scientist/nodes/builtins/governance/governance_gate_requests.py — 14fab09e4e63427db8a6a06032d44f00952fa32eda5e13200d2a1c9ce852fbc7
src/polisyos/scientist/governance/passes/_artifact_resolution.py — c7241dd0e6333c03aaa4d102e961e11ca586db5346670bc44e778a234be6941c
tests/unit/scientist/governance/test_artifact_resolution.py — 5fa5cc53efa42802e8ccd46ffe40a2861a4855ccf89ccd9f12804de46119a784
tests/unit/scientist/governance/test_normative_arbitration_pass.py — 35f73f9e344b0e8f76989768ac3fc2ed46a95be104a82eaec78f97f781e66225
tests/unit/scientist/governance/test_human_review_pass.py — f1f1242f914459e341ef9ebbc52242918facd3c0bb325f76007b0b73215f002c
tests/unit/scientist/governance/test_refutation_pass.py — b6f948077fb5ac3c08f21fc30d7461ac85005eaf64e1427653598e825bedbc68
tests/unit/scientist/governance/test_sutva_check_pass.py — a42036725c8983cce2cf85c1ce5aca0e3ccc6efc56b29d0512807a61f23359aa
tests/unit/scientist/governance/test_cross_graph_evidence_pass.py — 70366c858b1a2d5b172b5c9612047fed356a9c18e1d6b36540c18e653bf7ee12
tests/unit/scientist/governance/test_confidence_issue_accumulation.py — e509185c535b5574e26cf1e209f0a3b7c8ed823381dc254055c0b98124863cc8
tests/unit/scientist/governance/test_calibration_validation.py — 164f842b3b62c26f75c90be9284b1b8c39adcb1ae5867a0677e06ce863ca378b
```

Pre-edit SHA-256 for the two extracted canonical modules: `run_normative_arbitration.py` `f07f57205c02b6ee9f30d3d56ec5aeb3da0ea1d8062e40beb2dc41694557d744`; `run_governance.py` `078fff82892a0041f42adf1c3ee5acb19128a76eb5cbd8d3206d63f78d8e49d3`. The pre-edit baseline test-file hashes are recorded alongside them in `LOCAL/raw/governance-pre-edit-source-shas.txt`.
