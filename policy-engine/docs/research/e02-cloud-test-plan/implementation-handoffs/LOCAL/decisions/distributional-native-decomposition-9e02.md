# Distributional analysis native decomposition

## Scope and compatibility

The assigned source baseline was a 2,218-logical-line distributional analysis module with a C901 finding in `_resolve_distributional_bounds`. The node remains registered and implemented by `RunDistributionalAnalysisNode` in `run_distributional_analysis.py`; `_SPEC`, `_resolve_baseline_snapshot_ref`, and the canonical module import path also remain there. Existing private helper names are re-exported from the canonical module so its current callers continue resolving them. The baseline resolver still uses the canonical module's `StateSnapshotRef` symbol, preserving the existing monkeypatch seam.

The extracted code is grouped by existing responsibility: ordinal analysis, causal justification, bounds, artifact persistence, and subgroup calculation. Bounds request admission was factored into a private preparation helper while preserving validation order and skip reasons. No estimator, calibration, artifact schema, status, error, or persistence semantics were intentionally changed.

## Complete module denominator

The repository module-size counter ignores blank and comment-only lines. The final count was run over all six implementation files:

| Module | Logical lines |
| --- | ---: |
| `run_distributional_analysis.py` | 588 |
| `distributional_analysis_ordinal.py` | 296 |
| `distributional_analysis_justification.py` | 686 |
| `distributional_analysis_bounds.py` | 514 |
| `distributional_analysis_artifacts.py` | 335 |
| `distributional_analysis_subgroups.py` | 129 |

Each module is below the existing 1,000-line threshold. Ruff C901 at the existing maximum complexity of 12 passes across the complete six-module set; no threshold or expiry was changed.

## Verification

- Baseline focused suite before extraction: 15 passed. Receipt: `LOCAL/decisions/raw/distributional-native-decomposition-9e02-baseline.stdout.txt` and `.xml`.
- Final focused suite: 16 passed in 8.80 seconds. The added test asserts the node class and baseline resolver retain the canonical module identity. Receipt: `LOCAL/decisions/raw/distributional-native-decomposition-9e02-final.stdout.txt` and `.xml`.
- Native Ruff over all six source modules and both mirrored test modules: passed. Receipt: `LOCAL/decisions/raw/distributional-native-decomposition-9e02-ruff.stdout.txt`.
- Ruff format check over the six source modules and both mirrored test modules: passed (8 files). Receipt: `LOCAL/decisions/raw/distributional-native-decomposition-9e02-format.stdout.txt`.
- Ruff C901 check at complexity 12 over the complete six-module source denominator: passed. Receipt: `LOCAL/decisions/raw/distributional-native-decomposition-9e02-c901.stdout.txt`.
- Exact module counts: `LOCAL/decisions/raw/distributional-native-decomposition-9e02-module-counts.stdout.txt`.

The focused pytest command emitted one environment warning because this invocation disables the pytest cache plugin while repository configuration still contains `cache_dir`; all selected tests passed.

## P40 classification

This is one maintainability class: an oversized canonical node module and a high-complexity helper inside it. The bounds request-preparation extraction addresses the deeper expression of that same class, and the final C901 check covers the whole extracted implementation. It is not a new statistical or authority class. Independent review has not yet returned; if it finds another over-budget helper or module, classify it in this same bucket and test against the complete module set rather than lowering the existing threshold.

## Footprint

Tracked changes are limited to the canonical module, five adjacent private helper modules, its mirrored test, this release fragment, and this note. The nearest `scientist/nodes/README.md` is owned elsewhere; the suggested paragraph was sent to the root owner and was not edited here.
