from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.foundry.methods import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodRegistry,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.scientist.compute.job_spec import JobKey, JobSpec
from polisyos.scientist.compute.runner import run_job


@pytest.fixture(autouse=True)
def _reset_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


class _MethodJobIncrement:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="method_job_increment",
        namespace="tests.scientist",
        version="1.0.0",
        input_slots=frozenset({SlotSpec("state", SlotType.VECTOR, Unit("dimensionless", "array"))}),
        output_slots=frozenset({SlotSpec("values", SlotType.VECTOR, Unit("dimensionless", "array"))}),
        parameters=(ParameterSpec(name="delta", default=1.0),),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="method job increment")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        values = np.asarray(state["state"])
        return {"values": values + float(params["delta"])}


def test_job_spec_kind_validation():
    with pytest.raises(ValueError):
        JobSpec(job_kind="unknown")


def test_job_key_legacy_ignores_polyglot_fields():
    spec_a = JobSpec(
        job_kind="legacy_program",
        program_ref={
            "artifact_id": "sha256:" + ("a" * 64),
            "kind": "x",
            "media_type": "application/json",
        },
    )
    spec_b = JobSpec(
        job_kind="legacy_program",
        program_ref={
            "artifact_id": "sha256:" + ("a" * 64),
            "kind": "x",
            "media_type": "application/json",
        },
        method_fqn="tests.scientist.method_job_increment@1.0.0",
    )
    assert JobKey.from_spec(spec_a) == JobKey.from_spec(spec_a)
    assert JobKey.from_spec(spec_a) != JobKey.from_spec(spec_b)


def test_run_job_method_flow(tmp_path):
    registry = MethodRegistry.get_instance()
    registry.register(_MethodJobIncrement, override=True)

    cas = FileSystemCAS(tmp_path)
    input_ref = cas.put_json(
        [1, 2],
        PutOptions(
            kind="tests.input",
            media_type="application/json",
            schema=SchemaInfo(name="tests.Input", version="0.1.0"),
        ),
    )

    spec = JobSpec(
        job_kind="method",
        method_fqn=_MethodJobIncrement.signature.fqn,
        input_refs={"state": input_ref},
        method_params={"delta": 3},
    )
    result = run_job(spec, cas_root=tmp_path)

    assert not result.issues
    assert result.simulation_results_ref is not None
    assert result.method_result_ref is not None
    assert result.method_evidence_ref is not None
    assert result.final_state is not None
    assert np.allclose(np.asarray(result.final_state["values"]), np.array([4.0, 5.0]))


def test_run_job_method_without_fqn_returns_issue(tmp_path):
    spec = JobSpec(job_kind="method")
    result = run_job(spec, cas_root=tmp_path)
    assert result.issues
