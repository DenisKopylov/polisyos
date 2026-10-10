# Independent review: Q2 installed-consumer supplement

Review is read-only and is not G acceptance. I reviewed the exact committed source snapshot `f1cc10a350171622cd40615be6cb3800079b0f53` (tree `69658b269c1473bc3b06b6c37849f08a174dc870`, parent `b52e0900b9959742b646c8cfdf596d0f7a70a2ae`). The installed-consumer test is `tests/unit/core/contracts/test_e02_installed_composition.py@c0fd081284c63f547193b5a49f8e3bf09d79904f12b51ee5af473871011add26`. The producer and consumer source are respectively `src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py@60a20f807e892ab374c9b2feb87ed8b1a97f2e631eff04b45b438e98c6048530` and `src/polisyos/ir/analytics/uncertainty.py@a550ae6d9523930c3b03cbc1a722f6eb50bcbc7739b1c1d046319ca1b8ab0526`.

## Deciding source test

From `policy-engine/`, I ran the six-case source suite in the candidate's product venv, with modules loaded from `src:.`:

```text
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=src:. E02_SOURCE_ROOT="$PWD" .venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/core/contracts/test_e02_installed_composition.py
```

Complete deciding output:

```text
......                                                                   [100%]
=============================== warnings summary ===============================
.venv/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/.venv/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: cache_dir

    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

tests/unit/core/contracts/test_e02_installed_composition.py::test_public_surface_entrypoints_resolve_declared_exports
tests/unit/core/contracts/test_e02_installed_composition.py::test_public_surface_entrypoints_resolve_declared_exports
  /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/.venv/lib/python3.14/site-packages/torch/jit/_script.py:1474: DeprecationWarning: `torch.jit.script` is not supported in Python 3.14+ and may break. Please switch to `torch.compile` or `torch.export`.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
```

This is a source-path run, not an installed wheel proof. The actual installed supplemental wave was not run as part of this review.

I independently exercised the malformed report boundary against the source consumer with:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -c 'from polisyos.ir.analytics.uncertainty import _check_propagation_report; report={"schema_version":"1.1","output_envelopes":{"workers":{}},"diagnostics":{"output_coverage_complete":True,"draw_outcome_provenance":{"schema_version":"1.0","requested_draw_count":100,"attempted_draw_count":100,"successful_draw_count":100,"failure_records":[]}}}; limitations=[]; _check_propagation_report(report,None,metric_id="workers",limitations=limitations); print(limitations)'
```

Output: `['propagation_report_diagnostics_missing']` (exit 0). This is the diagnostic shape supplied by supplement case 5.

## Finding

**SAME_CLASS_DEEPER — blocking for the supplement's real producer-to-consumer claim.** Case 5 constructs a producer output envelope, but creates its `foundry.propagation_report` by hand and sets `diagnostics=produced.diagnostics`; it then reads raw CAS JSON and validates an envelope. It does not call `PropagateUncertaintyNode.execute`, persist the actual report and updated `SimulationResult` through that node, or call the fresh normative consumer. The hand-built report's top-level `diagnostics` is a dict with producer-level markers, while `_check_propagation_report` requires a list of per-metric rows `{metric_id, method, diagnostics}` and the shared draw ledger at report top level. Therefore the new test does not demonstrate the claimed persisted producer → typed references/lineage → fresh consumer chain. The direct boundary probe above confirms the real reader refuses this report with `propagation_report_diagnostics_missing`.

This is the same report/admission composition class one level deeper, not a new class. Widen the test mechanism to the actual node, persisted report and `SimulationResultRef`, then read them through a fresh `FileSystemCAS` and `load_simulation_result_uncertainty_admission`. The source consumer correctly has no numeric positive today: even a complete declared denominator returns a typed limited result with `draw_success_ledger_missing` and `draw_basis_verifier_missing`, because successful draw-to-input identity rows and a linked trusted verifier receipt are absent. The honest positive for this installed test is therefore the correctly bound, persisted typed limitation, not an admitted numeric envelope. An adversarial companion should preserve producer identity and completeness markers while falsifying the persisted denominator, then prove the fresh consumer rejects it. Existing source test `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_normative_admission_recomputes_denominator_while_markers_stay_true` is a useful actual-node/denominator-falsification reference, but it is not part of this installed six-case selector.

## Other case boundaries

- Public-surface case imports configured runtime entrypoints and distinguishes the AST inventory's 20 unresolved rows from runtime `__all__` resolution (3,197 names in this source run). These are separate denominators; this does not prove every static contract row is resolved.
- Workflow request case proves runtime rejection of wrong kind/media and acceptance of the valid kind/media pair. This six-case supplement does not exercise JSON Schema validation or a profile-bearing/conflicting legacy-reference intake through the installed wheel; source tests elsewhere cover related schema behavior. Treat that as a limit on this installed evidence, not a demonstrated source defect.
- Gate case proves version-1.2 selected-ref presence and legacy-1.1 compatibility, but the current positive uses an empty mapping rather than a non-empty profile-bound ref through serialization and consumption. The supplement therefore has a narrower installed gate-ref proof than the source tests.
- Generic CAS case verifies equal bytes under two selected profiles through the direct Core CAS writer and a fresh reader. It does not exercise CAN Core→IR `Mapping` option coercion, raw-content/profile conformance, or profileless history rollout. No failure in that adapter is established by this test.
- Scholar case is a meaningful fixture-backed consumer path: raw HTML bytes are extracted and sanitized, cached, persisted as a bundle, reopened in a fresh CAS, and checked against citation binding; a fabricated snippet is rejected. It supports that fixture path only and makes no live-source/currentness claim.

## Installed driver review and status

The supplemental runner was reviewed statically: `implementation-handoffs/LOCAL/q2-packaging/raw/supplemental_run.py@1e43531fce5d5ceb643349612823366f42702258efca598dec1d20feb524637e`, manifest `.../supplemental-manifest.json@bfb7120b1f728f1dd112368f2d2d6eb68894e12cd37f32d874464eddc29a03aa`, recipe `.../supplemental-wave-recipe.md@2b01a72d946e1d213e6f8bbc20f16cd3135c6281d9cc0e1fc5538529cf8c4853`. Its declared controls include source/tree preflight, exact primary-run receipt and 100-ID/JUnit reconciliation, three profiles installed sequentially in one consumer venv, isolated pytest invocation and origin checks, six exact selectors, measured timeout derivation, and stream/command hashing on return and failure. I found no additional static driver blocker in this scope. The primary runner and manifest inputs cited by the supplement are `q2-packaging/raw/runner.py@5d54bce877979e82e3a7f95d451b6f076fcc318037868e329f26908065d80932` and `q2-packaging/raw/manifest.json@ab7cf774e1c6805e9b1812472e5b8357af1a6a43d50a994a7488f29442d06eb7`.

The actual primary and installed supplemental receipts were not independently replayed here, and no installed-wheel result is claimed. Re-run the supplement only after the case-5 source test is repaired and source/input freeze is approved. G formal closure proposals from this review: none.

## Delta-only review: case 5 repair

The author replaced case 5 with test source `tests/unit/core/contracts/test_e02_installed_composition.py@8f3c269537b8f42b583fcaee4bc5ad7b29fe7456e95dd11a43fd7cb080c1ada7`; the matching supplemental manifest is `implementation-handoffs/LOCAL/q2-packaging/raw/supplemental-manifest.json@614013d0c2f3761012782405dbb1aa67abe16e15c37e849939de94ae6dd24b57`. The runner remains unchanged at `supplemental_run.py@1e43531fce5d5ceb643349612823366f42702258efca598dec1d20feb524637e`. This is a test-only delta atop the previously reviewed source snapshot; it is not an installed wheel run.

I read the full changed test and reran its actual case from `policy-engine/` in the candidate product venv, with source imports explicitly selected:

```text
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=src:. E02_SOURCE_ROOT="$PWD" .venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/core/contracts/test_e02_installed_composition.py::test_small_monte_carlo_report_is_consumed_from_fresh_cas
```

Complete output:

```text
.                                                                        [100%]
=============================== warnings summary ===============================
.venv/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/.venv/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: cache_dir
  
    self._warn_or_fail_if_strict(f"{key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
```

The prior case-5 composition blocker is resolved in this test delta. It now invokes the real `PropagateUncertaintyNode`, persists the actual report and updated simulation-result refs, opens a new `FileSystemCAS` reader, and calls `load_simulation_result_uncertainty_admission`; it then feeds the persisted simulation result to `RunNormativeArbitrationNode`. The positive outcome is correctly limited: no numeric envelope, `draw_success_ledger_missing` and `draw_basis_verifier_missing`, PARTIAL normative completeness, absent `workers_uncertainty` binding, and UNEVALUATED rights audit. The negative control removes `diagnostics` from the actual producer report while retaining its remaining report payload and complete draw-ledger markers; the fresh consumer returns `propagation_report_diagnostics_missing`, no envelope, and the normative consumer remains PARTIAL without the binding. This is a behavioral property-removal control, not a declaration-string assertion.

The test's count claims are bounded and honest when described precisely. It fixes 100 requested draws, observes 100 values consumed by the sample stub, verifies the producer report's requested/attempted/successful counts are each 100 with zero unattempted and no terminal failure records, and independently counts 102 calls to its controlled evaluator: one nominal evaluation plus 100 attempted draws plus one transient retry. Its arithmetic check is `simulation_attempt_count == 1 + attempted_draw_count + retry_attempt_count`; the duplicate `-1.0` callback input verifies one transient retry. This is not an independently reconciled successful draw-to-input identity ledger: the consumer continues to deny numeric admission for that exact reason. Do not describe this as a full B194 ledger, a normative independent verification of all 100 successes, or an institutional/legal authority fact. The test makes none of those claims.

Delta disposition: no remaining blocker found in case 5's source-level producer → artifact → fresh consumer path. The earlier note's statement that the six-case supplement does not use that path is historical and superseded by this section. The six-case source run/JUnit, Ruff/format checks, primary 100-case receipt, and three-profile installed supplemental wave were not independently rerun here; the installed-consumer claim remains pending those source-bound receipts. Unchanged limits above still apply to installed JSON Schema/profile-intake evidence, non-empty selected gate refs, CAN Core→IR Mapping/profileless history behavior, and live-source/currentness. No new G formal closure proposal.
