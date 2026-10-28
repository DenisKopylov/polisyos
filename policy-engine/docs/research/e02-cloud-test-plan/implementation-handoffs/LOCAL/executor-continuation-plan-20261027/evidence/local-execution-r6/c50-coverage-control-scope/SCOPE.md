# C50 coverage-reconciliation control: dependency boundary

This note applies only to the single unchanged C50 test
`tests/unit/calibration/diagnostics/test_c50_receipt_consistency.py::test_positive_metadata_cannot_admit_an_empty_interval_curve`
and the `coverage_reconciliation` mutation. It refines the blanket BLAS
caveat in the earlier `C50-native-manual-r2` source-reviewed README; that older
text remains historical. This note does not weaken or modify any C43 numerical
control requirement.

The test constructs a `CalibrationDiagnosticsReport` from Python literals,
empty tuples/lists and `CalibrationMetrics`. The selected owner
`CalibrationDiagnosticsReport._interval_coverage_admission` reconciles the
recorded level lists, curve-bin count and metadata using Python control flow,
sets, primitive arithmetic and `math`; for this empty-bin input it returns an
incomplete result. `to_truthfulness_receipt` and `to_validation_report` project
the result through the actual typed receipt and adapter, including Pydantic
model construction and the source-origin cap. The unchanged test asserts the
actual adapter verdict and readiness. The mutant replaces the selected
continuous report reconciler tail with `("evaluated", 1, None)`, preserving
its noncontinuous guard; the expected failure is the same test's
`validation.verdict == "fail"` assertion. The full selected test module imports
NumPy, and other members of the eight-module positive pilot perform numerical
work, but those facts alone do not make BLAS part of this selected report and
adapter property. This is a source-bound inference, not a runtime trace.

The deciding before/mutant/restored cases must have the same admitted HEAD,
tree, test/source/config/plugin/fixture inputs, actual selection and call sets,
Python executable/runtime-library pathname bytes and actual Pydantic/Pydantic-core
module/extension pathname bytes; pathname hashes do not directly hash mapped
memory, so the environment lease must start before each child;
read the full reports, active mutated source, invocation/restoration records and
actual JUnit/assertion. `c50_child_profile.py` additionally records the actually
loaded NumPy/SciPy/JAX and Pydantic modules/extensions and threadpoolctl result.
An empty or unavailable BLAS list is a disclosed observation, **not an automatic
failure of this deterministic software property**. Compare relevant loaded
module paths and hashes; investigate unexpected differences, and if actual
execution shows the tested property depends on BLAS or another native backend,
qualify that backend separately or mark the control UNQUALIFIED. The finite
`sys.modules` set is not an exhaustive dynamic loader trace.

The test's source-origin cap is not measurement provenance and this control
cannot prove an issuer, real interval source, fresh CAS binding, untyped Mapping
admission, numerical calibration quality, G acceptance or formal E02 closure.
No product test or mutation was executed by this preparer.
