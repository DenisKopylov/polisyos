from __future__ import annotations

def pytest_runtest_setup(item):
    if item.name == "test_lower_restored_cap_refuses_before_poll_or_frontier_effects":
        from polisyos.fabric.data_plane import streaming

        def remove_admission(state, *, options, contract):
            del state, options, contract
            return None

        streaming._admit_restored_operator_state = remove_admission
        print("REMOVAL_CONTROL: restored-operator admission replaced with no-op")
