from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.ir.model_layer.model_spec import ModelInputPortDeclarationRef, ModelSpec

_DATA_SNAPSHOT_REF = "sha256:" + "0" * 64
_DECLARATION_REF = "sha256:" + "1" * 64
_MANIFEST_PROFILE = "sha256:" + "2" * 64


def _model_spec(**overrides: object) -> ModelSpec:
    values: dict[str, object] = {
        "model_id": "tax_model",
        "data_snapshot_ref": _DATA_SNAPSHOT_REF,
    }
    values.update(overrides)
    return ModelSpec.model_validate(values)


def _selected_declaration_ref(**overrides: object) -> ModelInputPortDeclarationRef:
    values: dict[str, object] = {
        "artifact_id": _DECLARATION_REF,
        "kind": "ir.model_input_port_declaration",
        "media_type": "application/json",
        "manifest_profile_sha256": _MANIFEST_PROFILE,
    }
    values.update(overrides)
    return ModelInputPortDeclarationRef.model_validate(values)


def test_legacy_model_spec_bytes_are_unchanged_when_declaration_is_absent() -> None:
    model = _model_spec()

    assert model.model_dump_json() == (
        '{"schema_version":"1.0","model_id":"tax_model",'
        f'"data_snapshot_ref":"{_DATA_SNAPSHOT_REF}",'
        '"registry_bundle_ref":null,"time_semantics":null,'
        '"agent_config":{"agent_types":[],"total_agents":null,"max_agents":null,'
        '"interaction_topology":null,"network_graph_ref":null},'
        '"assumptions":[],"environment_config":{"params":[],"random_seed":null,'
        '"stochastic":true,"parallel_worlds":1},"fidelity_level":"hybrid",'
        '"calibrated":false,"calibration_ref":null,"name":null,"description":null,'
        '"labels":[],"version_tag":null,"notes":[]}'
    )
    assert "model_input_port_declaration_ref" not in model.model_dump(mode="json")


def test_model_input_port_declaration_ref_requires_model_spec_schema_1_1() -> None:
    ref = _selected_declaration_ref()

    model = _model_spec(
        schema_version="1.1",
        model_input_port_declaration_ref=ref,
    )

    assert model.model_input_port_declaration_ref == ref
    assert model.model_dump(mode="json")["model_input_port_declaration_ref"] == {
        "artifact_id": _DECLARATION_REF,
        "kind": "ir.model_input_port_declaration",
        "media_type": "application/json",
        "manifest_profile_sha256": _MANIFEST_PROFILE,
    }

    with pytest.raises(ValidationError, match="model_input_port_declaration_requires_schema_1_1"):
        _model_spec(model_input_port_declaration_ref=ref)


@pytest.mark.parametrize(
    "overrides",
    [
        {"kind": "core.model_input_port_declaration"},
        {"media_type": "application/octet-stream"},
        {"manifest_profile_sha256": None},
    ],
)
def test_model_input_port_declaration_ref_requires_exact_selected_json_artifact(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _selected_declaration_ref(**overrides)
