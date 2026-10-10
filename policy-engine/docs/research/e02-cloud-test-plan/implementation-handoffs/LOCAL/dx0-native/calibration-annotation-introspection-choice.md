# Calibration annotation-introspection choice

Date: 2026-10-10

## Property and counterfactual

The public `polisyos.calibration` functions expose runtime-resolvable annotations. A direct
`typing.get_type_hints` call succeeds for `evaluate_binary`, `evaluate_multiclass`, and
`to_validation_report` when `Mapping`, `Sequence`, and `CalibrationDiagnosticsReport` remain
imported at runtime. `CalibrationDiagnosticIssue` is only used by the private
`_diagnostic_issues` helper's annotation; moving that import under `TYPE_CHECKING` preserves the
three public functions' runtime hints without keeping an unnecessary runtime binding.

The repo uses runtime annotation resolution in its validation and API tooling. It also already has
line-local TC001/TC003 exceptions whose comments state that Pydantic, FastAPI, or public API
introspection needs runtime-bound types. The new mirrored test
`tests/unit/calibration/test_adapters.py::test_public_calibration_annotations_resolve_at_runtime`
pins the calibration-specific property.

## Disposition

Keep `Mapping`, `Sequence`, and `CalibrationDiagnosticsReport` available at runtime with line-local,
reasoned TC001/TC003 comments. Import `CalibrationDiagnosticIssue` under `TYPE_CHECKING`: it is
needed for static checking of a private helper but not for runtime resolution of any exported
signature. The exported Python annotations and runtime behavior stay intact while the package-wide
six-code Ruff ignore is retired. Runtime `get_type_hints` resolution is not promised for the private
`_diagnostic_issues` helper.

The exact no-package-ignore selection honors the remaining documented line exceptions and passes.
After moving the private issue type to `TYPE_CHECKING`, the `--ignore-noqa` falsifier returns six
import diagnostics (TC001=1, TC003=5), all from runtime dependencies of the public annotations. The
historical seven-diagnostic removal output remains unchanged under
`LOCAL/raw/ruff-calibration-review-current/`; the fresh six-diagnostic result is captured under
`LOCAL/raw/calibration-annotation-followup/`.

## Evidence

- Current no-ignore pre-repair selection: `raw/calibration-no-ignore-6-codes.json` (18 diagnostics;
  ANN401=2, B905=2, E501=6, RUF005=1, TC001=2, TC003=5).
- Historical pre-fix removal control ignoring even line-local reasons:
  `raw/calibration-six-codes-ignore-noqa.json` (7 type-import diagnostics on its captured source
  bytes); it is retained as historical evidence and is not the current post-fix count.
- The original row-14 Ruff, format, compile, annotation, and package-unit outputs remain under
  `checks/calibration-row14/`; the focused post-fix adapter test and Ruff outputs are under
  `LOCAL/raw/calibration-annotation-followup/`.
- The complete post-fix source denominator is nine Python files and 4,133 physical lines under
  `src/polisyos/calibration`; the changed slice comprises `adapters.py`, `diagnostics.py`, and
  `multiclass.py`, with six remaining source files enumerated in
  `LOCAL/dx0-native/calibration-source-denominator-current.json`. That manifest records every
  source and mirrored test path, line count, byte count, and SHA-256. The unit mirror remains seven
  Python files and 624 physical lines under `tests/unit/calibration`.
