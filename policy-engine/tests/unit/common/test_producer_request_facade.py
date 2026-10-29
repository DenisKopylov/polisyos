"""Governed facade routes retain exact canonical candidate implementation identity."""

from polisyos.common import producer_request
from polisyos.common._producer_request import _producer_payload, _ProducerBinding
from polisyos.core import llm
from polisyos.core.llm.response import _replay_usage_payload, _usage_quantity
from polisyos.core.llm.traced_client import PreparedLLMInput
from polisyos.scientist import create_n4_producer_binding, validate_n4_producer_context
from polisyos.scientist.orchestration.llm._n4_request import _check_n4_context, _n4_binding


def test_supported_request_and_quantity_routes_are_exact_owner_aliases():
    assert producer_request.ProducerRequestBinding is _ProducerBinding
    assert producer_request.producer_payload is _producer_payload
    assert llm.parse_llm_usage_quantity is _usage_quantity
    assert llm.replay_llm_usage_payload is _replay_usage_payload
    assert llm.PreparedLLMInput is PreparedLLMInput
    assert create_n4_producer_binding is _n4_binding
    assert validate_n4_producer_context is _check_n4_context
