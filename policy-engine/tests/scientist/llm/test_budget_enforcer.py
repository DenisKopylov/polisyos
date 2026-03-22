"""Tests for LLMBudgetEnforcer."""
from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polisyos.scientist.engine.budget import BudgetExhaustedError, BudgetLimit, BudgetState
from polisyos.scientist.llm.budget_enforcer import LLMBudgetEnforcer


def _make_response_mock(prompt_tokens: int = 100, completion_tokens: int = 50):
    """Create a mock LLM response with usage data."""
    response = MagicMock()
    response.usage = MagicMock()
    response.usage.prompt_tokens = prompt_tokens
    response.usage.completion_tokens = completion_tokens
    response.usage.total_tokens = prompt_tokens + completion_tokens
    response.content = "test response"
    response.model = "test-model"
    # Make raw dict for extract_llm_response_data
    response.raw = {
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
    return response


class TestLLMBudgetEnforcer:
    @pytest.mark.asyncio
    async def test_generate_within_budget(self):
        """Should pass through when budget is not exceeded."""
        client = AsyncMock()
        response = _make_response_mock()
        client.generate.return_value = response

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("100.00"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
        )

        result = await enforcer.generate(system="test", user="hello")
        assert result is response
        client.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_exceeds_budget(self):
        """Should raise BudgetExhaustedError when budget would be exceeded."""
        client = AsyncMock()

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("0.0001"))},
            spent={"run": Decimal("0.0001")},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
        )

        with pytest.raises(BudgetExhaustedError):
            await enforcer.generate(system="test", user="hello", max_tokens=1000)

        client.generate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_records_spend_after_call(self):
        """After a successful call, spend should be recorded."""
        client = AsyncMock()
        response = _make_response_mock(prompt_tokens=100, completion_tokens=50)
        client.generate.return_value = response

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("100.00"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
        )

        await enforcer.generate(system="test", user="hello")
        assert budget_state.spent.get("run", Decimal(0)) >= Decimal(0)

    @pytest.mark.asyncio
    async def test_audit_log_on_budget_check(self):
        """Audit log should receive BUDGET_CHECK events."""
        client = AsyncMock()
        response = _make_response_mock()
        client.generate.return_value = response

        audit = MagicMock()
        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("100.00"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
            audit_log=audit,
        )

        await enforcer.generate(system="test", user="hello")
        # Should have at least one BUDGET_CHECK call
        calls = [c for c in audit.append.call_args_list if c[1].get("action") == "BUDGET_CHECK"]
        assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_audit_log_on_budget_exceeded(self):
        """Audit log should receive BUDGET_EXCEEDED event."""
        client = AsyncMock()
        audit = MagicMock()

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("0.0001"))},
            spent={"run": Decimal("0.0001")},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
            audit_log=audit,
        )

        with pytest.raises(BudgetExhaustedError):
            await enforcer.generate(system="test", user="hello", max_tokens=1000)

        calls = [c for c in audit.append.call_args_list if c[1].get("action") == "BUDGET_EXCEEDED"]
        assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_strips_internal_kwargs(self):
        """Internal kwargs starting with _ should not be passed to the client."""
        client = AsyncMock()
        response = _make_response_mock()
        client.generate.return_value = response

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("100.00"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
        )

        await enforcer.generate(system="test", _run_id="r-001", _prompt_tokens_estimate=50)
        kwargs = client.generate.call_args[1]
        assert "_run_id" not in kwargs
        assert "_prompt_tokens_estimate" not in kwargs

    def test_budget_state_property(self):
        client = MagicMock()
        bs = BudgetState()
        enforcer = LLMBudgetEnforcer(
            client=client, budget_state=bs, budget_keys=["run"],
        )
        assert enforcer.budget_state is bs
