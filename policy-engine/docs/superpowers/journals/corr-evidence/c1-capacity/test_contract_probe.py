"""Pin the real owner's structural check before normalized typed extraction."""
# ruff: noqa: S101 - diagnostic pytest falsifiers.

import importlib
from typing import Any

import pytest


@pytest.mark.asyncio
async def test_empty_object_is_a_contract_failure() -> None:
    probe = importlib.import_module(
        "docs.superpowers.journals.corr-evidence.c1-capacity.contract_probe"
    )

    class SyntheticClient:
        async def chat(self, **kwargs: object) -> tuple[dict[str, Any], dict[str, Any]]:
            return {}, {}

    client = probe._ObservedClient(SyntheticClient())
    with pytest.raises(probe.ExtractionRequestError, match="contract_violation"):
        await client.chat(model="synthetic", temperature=0.0, prompt="synthetic")


@pytest.mark.asyncio
async def test_known_extraction_shape_stays_valid() -> None:
    probe = importlib.import_module(
        "docs.superpowers.journals.corr-evidence.c1-capacity.contract_probe"
    )

    class SyntheticClient:
        async def chat(self, **kwargs: object) -> tuple[dict[str, Any], dict[str, Any]]:
            return {"causal_claims": []}, {}

    client = probe._ObservedClient(SyntheticClient())
    assert await client.chat(model="synthetic", temperature=0.0, prompt="synthetic") == (
        {"causal_claims": []}, {},
    )
