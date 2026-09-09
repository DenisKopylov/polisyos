"""Report the complete real OpenAPI delta without exporting or storing schemas."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

BASELINE = "8a9b92b416aaf5b2bc68fc6901fc5dbe098ced11"
SCHEMA = "policy-engine/schemas/runtime_api_v1.openapi.json"
PRODUCT = Path.cwd().resolve()
REPO = PRODUCT.parent


class Number(str):
    """An exact JSON number token, distinct from an ordinary JSON string."""


def parse(raw: bytes) -> object:
    def pairs(items: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate_json_key:{key!r}")
            result[key] = value
        return result

    def invalid(value: str) -> None:
        raise ValueError(f"nonfinite_json_number:{value}")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                      parse_int=Number, parse_float=Number, parse_constant=invalid)


def recursive_nodes(value: object) -> dict[str, dict]:
    result = {}

    def visit(item: object, segments: tuple[str, ...]) -> None:
        path = "".join("/" + key.replace("~", "~0").replace("/", "~1") for key in segments)
        if isinstance(item, dict):
            result[path] = {"type": "object", "empty": not item}
            for key, child in item.items():
                visit(child, (*segments, key))
        elif isinstance(item, list):
            result[path] = {"type": "array", "empty": not item}
            for index, child in enumerate(item):
                visit(child, (*segments, str(index)))
        else:
            kind = "number" if isinstance(item, Number) else (
                "null" if item is None else "boolean" if isinstance(item, bool) else "string")
            result[path] = {"type": kind, "value": item}
    visit(value, ())
    return result


def iterative_nodes(value: object) -> dict[str, dict]:
    # Derive paths and classifications independently; do not call the first walk.
    result = {}
    stack = [("", value)]
    while stack:
        path, item = stack.pop()
        cls = type(item)
        if cls is dict:
            result[path] = {"empty": len(item) == 0, "type": "object"}
            for key in item:
                escaped = key.replace("~", "~0").replace("/", "~1")
                stack.append((path + "/" + escaped, item[key]))
        elif cls is list:
            result[path] = {"empty": len(item) == 0, "type": "array"}
            stack.extend((path + "/" + str(i), item[i]) for i in range(len(item)))
        else:
            kinds = {Number: "number", str: "string", bool: "boolean", type(None): "null"}
            result[path] = {"value": item, "type": kinds[cls]}
    return result


def identity(path: str, value: dict) -> str:
    return json.dumps([path, value], sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compare(before: object, after: object) -> tuple[dict, list[dict]]:
    left, right = recursive_nodes(before), recursive_nodes(after)
    other_left, other_right = iterative_nodes(before), iterative_nodes(after)
    assert left == other_left and right == other_right, "independent_tree_walk_disagreement"
    removed = {identity(p, v) for p, v in left.items()} - {identity(p, v) for p, v in right.items()}
    added = {identity(p, v) for p, v in right.items()} - {identity(p, v) for p, v in left.items()}
    # This independent path/value derivation does not use the serialized sets.
    changes = []
    for path in sorted(other_left.keys() | other_right.keys()):
        if path in other_left and path in other_right and other_left[path] == other_right[path]:
            continue
        change = {"path": path, "before_present": path in other_left, "after_present": path in other_right}
        if path in other_left:
            change["before"] = other_left[path]
        if path in other_right:
            change["after"] = other_right[path]
        changes.append(change)
    assert removed == {identity(c["path"], c["before"]) for c in changes if c["before_present"]}
    assert added == {identity(c["path"], c["after"]) for c in changes if c["after_present"]}
    counts = {"before_node_identities": len(left), "after_node_identities": len(right),
              "before_independent_nodes": len(other_left), "after_independent_nodes": len(other_right),
              "changed_paths": len(changes), "removed_identities": len(removed), "added_identities": len(added)}
    return counts, changes


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=REPO, stderr=subprocess.PIPE)


def self_test() -> None:
    left = parse(b'{"null":null,"emptyObject":{},"emptyArray":[],"number":1.0,"a/b~":false}')
    right = parse(b'{"added":null,"emptyObject":[],"emptyArray":{},"number":1,"a/b~":"false"}')
    counts, changes = compare(left, right)
    assert {c["path"] for c in changes} == {"/null", "/added", "/emptyObject", "/emptyArray", "/number", "/a~1b~0"}
    assert next(c for c in changes if c["path"] == "/null")["after_present"] is False
    assert next(c for c in changes if c["path"] == "/added")["after"]["type"] == "null"
    assert compare(parse(b'{"a":[]}'), parse(b'{"a":[null]}'))[0]["changed_paths"] == 2
    rejected = []
    invalid = [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{', b'\xff']
    for index, raw in enumerate(invalid):
        try:
            parse(raw)
        except (UnicodeError, ValueError):
            rejected.append(index)
        else:
            raise AssertionError(f"invalid_input_admitted:{index}")
    assert rejected == list(range(len(invalid)))
    print(json.dumps({"self_test": "pass", "changed_identity_controls": counts,
                      "invalid_input_denominator": len(invalid), "rejected_identities": rejected,
                      "schema_files_read": False}, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        instrument_path = Path(__file__).resolve()
        instrument_before = instrument_path.read_bytes()
        if PRODUCT.name != "policy-engine" or not (PRODUCT / "pyproject.toml").is_file():
            raise ValueError(f"invocation_cwd_not_product_root:{PRODUCT}")
        actual_repo = Path(git("rev-parse", "--show-toplevel").decode().strip()).resolve()
        if actual_repo != REPO or PRODUCT != actual_repo / "policy-engine":
            raise ValueError(f"invocation_product_git_root_mismatch:{PRODUCT}")
        head = git("rev-parse", "HEAD").decode().strip()
        branch = git("symbolic-ref", "--short", "HEAD").decode().strip()
        if branch != "codex/gy-eight-gaps":
            raise ValueError(f"unexpected_branch:{branch}")
        old_raw = git("show", f"{BASELINE}:{SCHEMA}")
        current = REPO / SCHEMA
        new_raw = current.read_bytes()
        before, after = parse(old_raw), parse(new_raw)
        if not isinstance(before, dict) or not isinstance(after, dict):
            raise ValueError("openapi_document_not_mapping")
        counts, changes = compare(before, after)
        if current.read_bytes() != new_raw or git("rev-parse", "HEAD").decode().strip() != head:
            raise ValueError("source_changed_during_delta_readback")
        instrument_after = instrument_path.read_bytes()
        if instrument_after != instrument_before:
            raise ValueError("delta_instrument_changed_during_comparison")
        print(json.dumps({"station": {"cwd": str(PRODUCT), "python": sys.executable,
                                       "python_version": platform.python_version(), "branch": branch,
                                       "head": head, "observed_utc": datetime.now(timezone.utc).isoformat()},
                          "source": {"before": f"{SCHEMA}@{BASELINE}", "after": str(current),
                                     "before_sha256": hashlib.sha256(old_raw).hexdigest(),
                                     "after_sha256": hashlib.sha256(new_raw).hexdigest(),
                                     "before_bytes": len(old_raw), "after_bytes": len(new_raw),
                                     "current_bytes_stable_during_readback": True},
                          "instrument": {"path": str(instrument_path),
                                         "before_sha256": hashlib.sha256(instrument_before).hexdigest(),
                                         "after_sha256": hashlib.sha256(instrument_after).hexdigest(),
                                         "source_bytes_unchanged": instrument_before == instrument_after},
                          "complete_denominator": counts,
                          "identity_semantics": "Every JSON node path/type; every scalar exact value (number token exact); every empty/nonempty container. Container children are represented at their paths, never copied as whole subtrees. Missing is a presence bit distinct from null or empty. No excluded path.",
                          "raw_bytes_equal": old_raw == new_raw,
                          "independent_identity_sets_equal": True}, sort_keys=True))
        for change in changes:
            print(json.dumps({"changed_identity": change}, sort_keys=True, ensure_ascii=False))
        print(json.dumps({"comparison_complete": True, "classification": "observed_schema_delta_only",
                          "export_or_contract_check_claimed": False, "files_written": False}, sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError, AssertionError, RecursionError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"comparison_complete": False, "classification": "unreadable_or_unreconciled_input",
                          "reason": f"{type(exc).__name__}:{exc}", "no_zero_or_empty_delta_claim": True}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
