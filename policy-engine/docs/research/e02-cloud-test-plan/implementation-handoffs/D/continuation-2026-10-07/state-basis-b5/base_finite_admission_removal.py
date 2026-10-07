"""Remove the shared finite conversion while retaining the real state markers."""


def pytest_runtest_call(item):
    if item.originalname != "test_unrepresentable_base_numeric_state_refuses_atomically":
        return
    from polisyos.scientist.methods.search.strategies import base

    base.finite_real_scalar = float
