from __future__ import annotations

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.foundry import (
    AttractorAnalysisResult,
    AttractorCertificate,
    AttractorObservableSummary,
    AttractorStateProjection,
    AttractorStateRepresentation,
    AttractorSummary,
    CompileRequest,
    CompileResult,
    DerivedArtifact,
    ExecPlanRef,
    ExecuteRequest,
    ExecuteResult,
    FoundryCompileConfig,
    FoundryExecConfig,
    FoundryInputBindingsRef,
    FoundryValidationFlags,
    MetricsRef,
    ObservedRange,
    ObservedRangeBundle,
    ObservedRangeBundleRef,
    PeriodicOrbitDiagnostics,
    SimulationResult,
    SimulationResultRef,
    StateSnapshotRef,
    WelfareBoundReport,
    WelfareBoundReportRef,
)


def test_route_constraint_facade_reuses_actual_input_contract_owner() -> None:
    """The stable boundary exports the existing candidate owner without wrappers."""
    from polisyos.foundry import MethodRouteConstraint, method_accepts_input_contract
    from polisyos.foundry.methods.catalog.ml.survival import SurvivalAnalysisEstimator
    from polisyos.foundry.methods.selection import advisor

    assert MethodRouteConstraint is advisor.MethodRouteConstraint
    assert method_accepts_input_contract is advisor.method_accepts_input_contract
    assert method_accepts_input_contract(
        SurvivalAnalysisEstimator, "foundry.ml.survival_data.v1",
    )
    assert not method_accepts_input_contract(
        SurvivalAnalysisEstimator, "foundry.ml.nonexistent_survival_data.v1",
    )


def test_route_constraint_facade_allows_same_owner_lazy_reentry() -> None:
    """Real resolver reentry completes; removing only reentrancy deadlocks."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "tests.contract.test_foundry_facade_contracts"],
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "same_owner_reentry_passed_and_nonreentrant_removal_timed_out" in result.stdout


def _facade_reentry_probe() -> None:
    import signal
    import threading

    import polisyos.foundry as facade
    from polisyos.foundry.methods.backends.protocol import EmbedderProtocol
    from polisyos.foundry.methods.selection import advisor

    # Warm the real objects before timing synchronization. The loader probe
    # makes an existing public dependency reenter the same real facade owner.
    facade._RESOLVED_EXPORTS["EmbedderProtocol"] = EmbedderProtocol
    facade._RESOLVED_EXPORTS.pop("MethodRouteConstraint", None)
    original_import = facade.importlib.import_module
    target_module = facade._LAZY_IMPORTS["MethodRouteConstraint"][0]

    def reenter(module_name: str):
        if module_name == target_module:
            assert facade._resolve_lazy_export("EmbedderProtocol") is EmbedderProtocol
        return original_import(module_name)

    def expired(_signum, _frame):
        raise TimeoutError("same_owner_lazy_reentry_deadlocked")

    facade.importlib.import_module = reenter
    signal.signal(signal.SIGALRM, expired)

    def check_real_export() -> None:
        facade._RESOLVED_EXPORTS.pop("MethodRouteConstraint", None)
        signal.setitimer(signal.ITIMER_REAL, 2)
        try:
            assert facade._resolve_lazy_export("MethodRouteConstraint") is advisor.MethodRouteConstraint
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)

    try:
        check_real_export()
        facade._RESOLVE_LOCK = threading.Lock()
        try:
            check_real_export()
        except TimeoutError:
            print("same_owner_reentry_passed_and_nonreentrant_removal_timed_out")
        else:
            raise AssertionError("removing_reentrancy_did_not_break_same_owner_reentry")
    finally:
        facade.importlib.import_module = original_import


def _dummy_ref(kind: str, media_type: str = "application/json") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("0" * 64),
        kind=kind,
        media_type=media_type,
    )


def test_compile_request_canonical() -> None:
    req = CompileRequest(
        input_kind="trinity",
        policy_ref=_dummy_ref("ir.trinity_bundle"),
        registry_bundle_ref=_dummy_ref("core.registry_bundle"),
        compile_config=FoundryCompileConfig(),
        validation_flags=FoundryValidationFlags(),
    )
    to_canonical_bytes(req)


def test_compile_result_canonical() -> None:
    result = CompileResult(
        ok=True,
        exec_plan_ref=ExecPlanRef(artifact_id=ArtifactID.from_sha256_hex("1" * 64)),
        compile_report_ref=_dummy_ref("compiler.compile_report"),
        derived_refs=[
            DerivedArtifact(role="program_graph", ref=_dummy_ref("foundry.program_graph"))
        ],
    )
    to_canonical_bytes(result)


def test_execute_request_canonical() -> None:
    req = ExecuteRequest(
        exec_plan_ref=ExecPlanRef(artifact_id=ArtifactID.from_sha256_hex("2" * 64)),
        input_bindings_ref=FoundryInputBindingsRef(
            artifact_id=ArtifactID.from_sha256_hex("3" * 64)
        ),
        registry_bundle_ref=_dummy_ref("core.registry_bundle"),
        exec_config=FoundryExecConfig(),
    )
    to_canonical_bytes(req)


def test_execute_request_with_observed_range_bundle_canonical() -> None:
    req = ExecuteRequest(
        exec_plan_ref=ExecPlanRef(artifact_id=ArtifactID.from_sha256_hex("2" * 64)),
        input_bindings_ref=FoundryInputBindingsRef(
            artifact_id=ArtifactID.from_sha256_hex("3" * 64)
        ),
        observed_range_bundle_ref=ObservedRangeBundleRef(
            artifact_id=ArtifactID.from_sha256_hex("5" * 64)
        ),
        welfare_bound_mode="both",
        welfare_bound_required=True,
    )
    to_canonical_bytes(req)


def test_execute_result_canonical() -> None:
    result = ExecuteResult(
        ok=True,
        simulation_result_ref=SimulationResultRef(artifact_id=ArtifactID.from_sha256_hex("4" * 64)),
        derived_refs=[DerivedArtifact(role="metrics", ref=_dummy_ref("foundry.metrics"))],
    )
    to_canonical_bytes(result)


def test_attractor_analysis_result_canonical() -> None:
    result = AttractorAnalysisResult(
        analysis_id="analysis_a",
        simulation_result_ref=SimulationResultRef(artifact_id=ArtifactID.from_sha256_hex("4" * 64)),
        state_projection=AttractorStateProjection(
            variables=["infected", "susceptible"],
            reduced_dimension=2,
            quotient_notes=["time_step excluded"],
        ),
        attractors=[
            AttractorSummary(
                attractor_id="A1",
                kind="fixed_point",
                existence_status="numerically_confirmed",
                state_representation=AttractorStateRepresentation(
                    equilibrium={"infected": 0.0, "susceptible": 127.3}
                ),
                certificate=AttractorCertificate(
                    type="quadratic_lyapunov",
                    status="proved_local",
                    evidence_strength=0.9,
                ),
                observables=AttractorObservableSummary(terminal_residual_norm=1.0e-8),
            )
        ],
    )

    to_canonical_bytes(result, spec=CanonSpec(forbid_floats=False))


def test_periodic_orbit_diagnostics_canonical() -> None:
    diagnostics = PeriodicOrbitDiagnostics(
        period=12.0,
        section_definition="infected_dot = 0, crossing=positive",
        spectral_radius=0.73,
        transverse_certificate=AttractorCertificate(
            type="poincare_transverse",
            status="proved_local",
            evidence_strength=0.85,
        ),
    )

    to_canonical_bytes(diagnostics, spec=CanonSpec(forbid_floats=False))


def test_welfare_bound_sidecar_models_canonical() -> None:
    bundle = ObservedRangeBundle(
        ranges={
            "income_tax.eti_effective": ObservedRange(lower=0.1, upper=0.3),
        }
    )
    report = WelfareBoundReport(
        mechanism_type="income_tax",
        node_id="node_a",
        welfare_loss_lower=1.0,
        welfare_loss_upper=2.0,
        required_observables=("income_tax.eti_effective",),
        status="ok",
    )
    spec = CanonSpec(forbid_floats=False)
    to_canonical_bytes(bundle, spec=spec)
    to_canonical_bytes(report, spec=spec)


def test_simulation_result_with_welfare_bound_refs_canonical() -> None:
    result = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=ArtifactID.from_sha256_hex("2" * 64)),
        metrics_ref=MetricsRef(artifact_id=ArtifactID.from_sha256_hex("6" * 64)),
        state_snapshot_ref=StateSnapshotRef(artifact_id=ArtifactID.from_sha256_hex("7" * 64)),
        welfare_bound_refs={
            "node_a": WelfareBoundReportRef(artifact_id=ArtifactID.from_sha256_hex("8" * 64))
        },
    )
    to_canonical_bytes(result)


if __name__ == "__main__":
    _facade_reentry_probe()
