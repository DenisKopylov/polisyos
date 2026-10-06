"""Original numeric amounts cannot become a false zero through float underflow."""

from decimal import Decimal
from pathlib import Path
from runpy import run_path

import pytest

_native_intake = run_path(str(Path(__file__).with_name("test_native_gateway_cost_intake.py")))
RawGateway = _native_intake["RawGateway"]
assert_no_receipt_after_invalid_intake = _native_intake["assert_no_receipt_after_invalid_intake"]
build = _native_intake["build"]
invoke = _native_intake["invoke"]
raw_payload = _native_intake["raw_payload"]


@pytest.mark.parametrize("amount", ["-1e-1000", "1e-1000", Decimal("-1e-1000"), Decimal("1e-1000")])
@pytest.mark.asyncio
async def test_native_raw_nonzero_amount_cannot_settle_underflowed_zero(tmp_path, amount):
    gateway = RawGateway(raw_payload({"cost_usd": amount}))
    path, enforcer = build(tmp_path, gateway)
    with pytest.raises(ValueError, match="provider cost"):
        await invoke(enforcer)
    assert gateway.calls == 1
    assert gateway.normalized_response.usage.cost_usd == 0
    assert gateway.normalized_response.raw["usage"]["cost_usd"] == amount
    assert_no_receipt_after_invalid_intake(path)
