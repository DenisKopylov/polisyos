"""Report every actual method-report representation difference after test failure."""

import json


def pytest_exception_interact(node, call, report):
    if "test_real_method_report_is_reconciled" not in node.nodeid:
        return
    from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes

    frames = [entry.frame.f_locals for entry in call.excinfo.traceback]
    local = next(row for row in reversed(frames) if "report_calls" in row and "report" in row)
    persisted = local["report"]
    original = local["report_calls"][-1][1]
    differences = []

    def walk(left, right, path):
        if type(left) is not type(right):
            differences.append({"path": path, "persisted_type": type(left).__name__,
                                "owner_type": type(right).__name__, "persisted": repr(left),
                                "owner": repr(right)})
        elif isinstance(left, dict):
            for key in sorted(left.keys() | right.keys()):
                if key not in left or key not in right:
                    differences.append({"path": path + [key], "persisted_present": key in left,
                                        "owner_present": key in right})
                else:
                    walk(left[key], right[key], path + [key])
        elif isinstance(left, (tuple, list)):
            if len(left) != len(right):
                differences.append({"path": path, "persisted_length": len(left), "owner_length": len(right)})
            for index, (a, b) in enumerate(zip(left, right)):
                walk(a, b, path + [index])
        elif left != right:
            differences.append({"path": path, "persisted": repr(left), "owner": repr(right)})

    walk(persisted, original, [])
    encoded = from_canonical_bytes(to_canonical_bytes(
        original, CanonSpec(forbid_floats=False, exclude_none=False)))
    node.config.pluginmanager.get_plugin("terminalreporter").write_line(json.dumps({
        "complete_representation_differences": differences,
        "whole_owner_canonical_roundtrip_equal": persisted == encoded,
        "canon_contract": "CanonSpec(forbid_floats=False, exclude_none=False)",
    }, sort_keys=True))
