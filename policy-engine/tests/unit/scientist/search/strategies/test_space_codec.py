from __future__ import annotations

from polisyos.scientist.methods.search.strategies.codec import ScalarParameterCodec
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds, ParameterType


def test_search_space_roundtrip_mixed_types(mixed_space: SearchSpace) -> None:
    params = {"tax_rate": 0.22, "budget_steps": 3, "regime": "B"}
    normalized = mixed_space.normalize(params)
    assert len(normalized) == mixed_space.dim

    restored = mixed_space.denormalize(normalized)
    assert abs(restored["tax_rate"] - 0.22) < 1e-6
    assert restored["budget_steps"] == 3
    assert restored["regime"] == "B"


def test_sobol_sampling_is_deterministic(simple_space: SearchSpace) -> None:
    samples_a = simple_space.sample_sobol(5, seed=123)
    samples_b = simple_space.sample_sobol(5, seed=123)
    assert samples_a == samples_b
    assert len(samples_a) == 5


def test_scalar_codec_path_encode_decode() -> None:
    codec = ScalarParameterCodec(
        parameter_paths={
            "tax_rate": "semantic.interventions.0.parameters.tax_rate",
            "capex": "semantic.interventions.0.parameters.capex",
        }
    )
    candidate = {
        "semantic": {
            "interventions": [
                {"parameters": {"tax_rate": 0.18, "capex": 120.0}},
            ]
        }
    }
    encoded = codec.encode(candidate)
    assert encoded["tax_rate"] == 0.18
    assert encoded["capex"] == 120.0

    decoded = codec.decode(encoded)
    params = decoded["semantic"]["interventions"][0]["parameters"]
    assert params["tax_rate"] == 0.18
    assert params["capex"] == 120.0


def test_categorical_requires_categories() -> None:
    try:
        ParameterBounds(name="kind", dtype=ParameterType.CATEGORICAL)
    except ValueError as exc:
        assert "requires at least two categories" in str(exc)
    else:
        raise AssertionError("Expected ValueError for categorical without categories")
