from __future__ import annotations

import importlib
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any, get_type_hints

from polisyos.ir.analytics import causal as causal_module
from polisyos.ir.analytics.causal import (
    _IdentificationResultLike,
    build_data_readiness_report,
    build_dynamic_proof_bundle,
    build_forecast_intervention_proof_bundle,
    proof_bundle_from_identification_result,
    proof_bundle_from_negative_certificate,
)
from polisyos.ir.analytics.cross_graph import CompositionCertificate, SCMFragment
from polisyos.ir.analytics.estimand import EstimandAST
from polisyos.ir.analytics.negative_certificate import NegativeCertificate
from polisyos.ir.governance.phase1 import Phase1GateSummary
from polisyos.ir.kernel.method_metrics import apply_registered_direct_output_law


def test_public_dynamic_ir_argument_annotations_resolve_at_runtime() -> None:
    assert (
        get_type_hints(proof_bundle_from_identification_result)["result"]
        is _IdentificationResultLike
    )
    assert (
        get_type_hints(proof_bundle_from_negative_certificate)["certificate"] is NegativeCertificate
    )
    assert get_type_hints(_IdentificationResultLike)["estimand_ast"] == (
        EstimandAST | dict[str, Any] | None
    )
    assert get_type_hints(build_dynamic_proof_bundle)["estimand_ast"] == (
        EstimandAST | dict[str, Any] | None
    )
    assert get_type_hints(build_forecast_intervention_proof_bundle)["estimand_ast"] == (
        EstimandAST | dict[str, Any] | None
    )
    assert get_type_hints(build_data_readiness_report)["phase1_gate_summary"] == (
        Phase1GateSummary | dict[str, Any] | None
    )
    assert get_type_hints(SCMFragment._backfill_cycle_contract_defaults)["payload"] is object
    assert get_type_hints(CompositionCertificate._backfill_status_fields)["payload"] is object
    assert get_type_hints(apply_registered_direct_output_law)["value"] is object


def _run_cold_causal_public_annotation_probe() -> subprocess.CompletedProcess[str]:
    """Resolve the causal public API in a clean interpreter and pin its source origin."""
    repo_root = Path(__file__).resolve().parents[4]
    expected_module_path = (repo_root / "src/polisyos/ir/analytics/causal.py").resolve()
    assert Path(causal_module.__file__).resolve() == expected_module_path
    source_root = repo_root / "src"
    env = os.environ.copy()
    inherited_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(source_root), inherited_pythonpath] if inherited_pythonpath else [str(source_root)]
    )
    probe = textwrap.dedent(
        """        import importlib
        import sys
        from inspect import isclass, isfunction
        from pathlib import Path
        from typing import get_args, get_type_hints

        dependency = "polisyos.ir.analytics.proof_composability"
        assert dependency not in sys.modules
        causal = importlib.import_module("polisyos.ir.analytics.causal")
        assert Path(causal.__file__).resolve() == Path(sys.argv[1]).resolve()
        assert dependency not in sys.modules

        resolved_names = []
        for name in causal.__all__:
            value = getattr(causal, name)
            if isclass(value) or isfunction(value):
                get_type_hints(value)
                resolved_names.append(name)
        assert resolved_names

        hints = get_type_hints(causal.proof_bundle_from_identification_result)
        composability_input = hints["composability_certificate"]
        assert causal._ProofComposabilityCertificateLike in get_args(composability_input)
        assert dependency not in sys.modules
        print(f"resolved {len(resolved_names)} public annotations from {causal.__file__}")
        """
    )
    return subprocess.run(
        [sys.executable, "-c", probe, str(expected_module_path)],
        cwd=repo_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_causal_public_surface_annotations_resolve_without_importing_proof_composability() -> None:
    result = _run_cold_causal_public_annotation_probe()
    assert result.returncode == 0, result.stderr or result.stdout
    assert "resolved " in result.stdout


def test_cold_causal_annotation_probe_is_independent_of_warm_parent_import_state() -> None:
    proof_module = importlib.import_module("polisyos.ir.analytics.proof_composability")
    assert sys.modules["polisyos.ir.analytics.proof_composability"] is proof_module

    result = _run_cold_causal_public_annotation_probe()
    assert result.returncode == 0, result.stderr or result.stdout
    assert "resolved " in result.stdout


def test_composability_certificate_model_revalidation_and_rederivation_are_projected() -> None:
    from polisyos.ir.analytics.proof_composability import (
        ProofComposabilityCertificate,
        ProofComposabilityStatus,
    )
    from polisyos.ir.registry.refs import ProofWitnessIndexRef

    witness_ref = ProofWitnessIndexRef(artifact_id="sha256:" + "0" * 64)
    identification_result = SimpleNamespace(
        status="identified",
        algorithm_version="id_v1",
        estimand_ast=None,
        trace=["identify"],
        query_str="P(Y|do(X))",
        required_distributions=[],
        metadata={},
    )
    revalidate_certificate = ProofComposabilityCertificate(
        status=ProofComposabilityStatus.REVALIDATE,
        source_fragment_id="fragment-a",
        checked_query="P(Y|do(X))",
        witness_index_ref=witness_ref,
        proof_support_projection_hash="projection-a",
        invalidated_by_graph_hashes=("graph-a",),
    )
    revalidation = proof_bundle_from_identification_result(
        identification_result,
        composability_certificate=revalidate_certificate,
    )
    assert revalidation.composability_status == "revalidate"
    assert revalidation.witness_index_ref == witness_ref
    assert revalidation.proof_support_projection_hash == "projection-a"
    assert revalidation.invalidated_by_graph_hashes == ["graph-a"]

    rederive_certificate = ProofComposabilityCertificate(
        status=ProofComposabilityStatus.REDERIVE,
        source_fragment_id="fragment-b",
        checked_query="P(Y|do(X))",
        witness_index_ref=witness_ref,
        broken_witness_ids=("witness-broken",),
        invalidation_reasons=("composed graph changed",),
        proof_support_projection_hash="projection-b",
        invalidated_by_graph_hashes=("graph-b",),
    )
    rederivation = proof_bundle_from_identification_result(
        identification_result,
        composability_certificate=rederive_certificate,
    )
    assert rederivation.composability_status == "rederive"
    assert rederivation.witness_index_ref == witness_ref
    assert rederivation.proof_support_projection_hash == "projection-b"
    assert rederivation.invalidated_by_graph_hashes == ["graph-b"]


def test_public_ir_annotations_resolve_for_cold_runtime_consumers() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    source_root = repo_root / "src"
    probe = textwrap.dedent(
        """\
        import importlib
        import sys
        from collections.abc import Iterable, Sequence
        from pathlib import Path
        from types import SimpleNamespace
        from typing import get_type_hints

        root = Path(sys.argv[1]).resolve()
        module_names = (
            "polisyos.ir.analytics.abm_bridge",
            "polisyos.ir.analytics.causal_run_snapshot",
            "polisyos.ir.analytics.transportability",
            "polisyos.ir.observation.causal_readiness",
            "polisyos.ir.analytics.dual_certificate",
            "polisyos.ir.analytics.hte",
        )
        assert all(name not in sys.modules for name in module_names)
        from polisyos.ir.artifacts import ArtifactStore, InputRef
        from polisyos.ir.artifacts._lineage import InputRefLike

        modules = {name: importlib.import_module(name) for name in module_names}
        assert all(Path(module.__file__).resolve().is_relative_to(root) for module in modules.values())

        abm = modules["polisyos.ir.analytics.abm_bridge"]
        abm_hints = get_type_hints(abm.persist_abm_alignment_report)
        assert abm_hints["store"] is ArtifactStore
        assert abm_hints["inputs"] == list[InputRef] | None

        snapshot = modules["polisyos.ir.analytics.causal_run_snapshot"]
        build_hints = get_type_hints(snapshot.CausalRunSnapshot.build)
        assert build_hints["graph"] == snapshot._JsonModelDump | None
        assert build_hints["estimation_steps"] == Iterable[object]
        assert build_hints["compilation_steps"] == Sequence[object]
        assert "run_id" in snapshot.CausalRunSnapshot.model_json_schema()["properties"]

        transportability = modules["polisyos.ir.analytics.transportability"]
        transport_hints = get_type_hints(transportability.persist_transportability_result)
        assert transport_hints["store"] is ArtifactStore
        assert transport_hints["inputs"] == Sequence[InputRefLike] | None

        readiness = modules["polisyos.ir.observation.causal_readiness"]
        readiness_hints = get_type_hints(readiness.persist_causal_readiness_bundle)
        assert readiness_hints["store"] is ArtifactStore
        assert readiness_hints["inputs"] == Sequence[InputRefLike] | None
        assert readiness.CausalReadinessBundle.model_json_schema()["properties"]

        dual = modules["polisyos.ir.analytics.dual_certificate"]
        solver_hints = get_type_hints(dual._build_single_certificate)
        assert solver_hints["result"] is dual._LPResultLike
        result = SimpleNamespace(
            x=dual.np.asarray([1.0, 0.0]),
            eqlin=SimpleNamespace(marginals=dual.np.asarray([1.0])),
            lower=SimpleNamespace(marginals=dual.np.asarray([0.0, 0.0])),
            status=0,
            message="optimal",
        )
        certificate = dual._build_single_certificate(
            problem_fingerprint="test-fingerprint",
            bound_direction="lower",
            objective=dual.np.asarray([1.0, 0.0]),
            result=result,
            b_eq=dual.np.asarray([1.0]),
        )
        assert certificate.solver_status == "optimal"
        assert certificate.objective_primal == certificate.objective_dual == 1.0

        status_only_result = SimpleNamespace(
            x=dual.np.asarray([1.0, 0.0]),
            eqlin=SimpleNamespace(marginals=dual.np.asarray([1.0])),
            lower=SimpleNamespace(marginals=dual.np.asarray([0.0, 0.0])),
            status=0,
        )
        fallback_certificate = dual._build_single_certificate(
            problem_fingerprint="status-only-fingerprint",
            bound_direction="lower",
            objective=dual.np.asarray([1.0, 0.0]),
            result=status_only_result,
            b_eq=dual.np.asarray([1.0]),
        )
        assert fallback_certificate.solver_status == "0"

        hte = modules["polisyos.ir.analytics.hte"]
        assert get_type_hints(hte._get_hte_owned_json_artifact)["ref"] == hte.ArtifactSelector
        print("resolved IR runtime annotations, Pydantic schemas, and LP result protocol consumer")
        """
    )
    env = os.environ.copy()
    inherited_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(source_root), inherited_pythonpath] if inherited_pythonpath else [str(source_root)]
    )
    result = subprocess.run(
        [sys.executable, "-c", probe, str(source_root)],
        cwd=repo_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "resolved IR runtime annotations" in result.stdout
