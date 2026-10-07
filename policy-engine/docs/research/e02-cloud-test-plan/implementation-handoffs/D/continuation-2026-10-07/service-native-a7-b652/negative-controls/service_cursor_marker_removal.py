"""Bounded removal control: marker state retained, actual cursor restore removed."""


def pytest_runtest_call(item):
    if item.originalname != "test_public_factory_checkpoint_fault_fresh_process_resume_preserves_next_subject":
        return
    module = item.module
    admission = "service = runner.create_service(spec, suite_ref=suite, max_iterations=3)"
    removal = admission + """
# The checkpoint markers/corpus remain present and the visible cursor stays1.
# Actual set_state does nothing, so the live next subject is3 instead of2.
generator = service.controller._generator
actual_state = generator.get_state

def retained_marker_state():
    state = actual_state()
    state["index"] = min(state["index"], 1)
    return state

generator.get_state = retained_marker_state
generator.set_state = lambda state: None
"""
    original = getattr(module, "_removal_control_original_script", module._WRITE_SCRIPT)
    module._removal_control_original_script = original
    assert original.count(admission) == 1
    module._WRITE_SCRIPT = original.replace(admission, removal, 1)
