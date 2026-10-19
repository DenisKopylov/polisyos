from __future__ import annotations


def test_method_selection_receipt_uses_documented_methods_facade() -> None:
    from polisyos.foundry.methods import MethodSelectionReceipt
    from polisyos.foundry.methods.selection import MethodSelectionReceipt as OwnerReceipt

    assert MethodSelectionReceipt is OwnerReceipt
