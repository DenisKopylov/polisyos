#!/usr/bin/env python3
"""Compare LA-021's historical independent codecs with the shared codec.

This instrument reads the complete tracked JSON tree at a pinned integration
commit and a small, named set of immutable non-JSON vectors copied from the
codec characterization tests. Historical source is loaded from pinned Git
blobs into isolated module namespaces; current source is imported only after
its blob identities are checked. The receipt contains digests and outcomes,
never payload data.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import decimal
import hashlib
import importlib
import json
import subprocess
import sys
import time
import types
import warnings
from collections import Counter
from pathlib import Path
from typing import Any, Callable

sys.dont_write_bytecode = True

import pydantic
from pydantic import BaseModel

INTEGRATION_COMMIT = "73c656744f051d9f40667da7f8bc91c61d8b4ebf"
LEGACY_COMMIT = "9948c1e8f66be38f6c15d54a1c5df43f185a6864"
RELOCATION_COMMIT = "f655b8141a1a8a0ab4dce56873ab4fa6a34b1df7"

LEGACY_SOURCE_BLOBS = {
    "policy-engine/src/polisyos/core/canon/canon_json.py": "c5e12ae96e28383258902cf2a9f23ef4bcd6ba77",
    "policy-engine/src/polisyos/core/canon/hashing.py": "a9afa86dc00340bee32bc2667c72efd9d518f75d",
    "policy-engine/src/polisyos/ir/model_layer/canon.py": "aba79b0e033e09dc4568c5928f61acd00a9ca295",
}
CURRENT_SOURCE_BLOBS = {
    "policy-engine/src/polisyos/__init__.py": "a1b746537b78f1e2e6c5e8f288df8174fb936906",
    "policy-engine/src/polisyos/common/__init__.py": "696045bd775c9a9fe4023217628e686bf76b78f3",
    "policy-engine/src/polisyos/common/canonical.py": "25fa43311ba8a04a25845a1863898399a7eed958",
    "policy-engine/src/polisyos/common/hashing.py": "796af1b64e6ae530cb6d880bbff54803e8298a47",
    "policy-engine/src/polisyos/core/__init__.py": "5964150861173fd27143d44363fda0ddd1b6f7e4",
    "policy-engine/src/polisyos/core/canon/__init__.py": "a0b19b5ce6a9bfd9f5d4149fbdbe76429d14fe29",
    "policy-engine/src/polisyos/core/canon/canon_json.py": "ca14a6bf9cec51292cf457243f38191892c5828a",
    "policy-engine/src/polisyos/core/canon/hashing.py": "0007ba9acac60ad77c58f85355eacece9150df56",
    "policy-engine/src/polisyos/ir/__init__.py": "66068a49645b226700ae797f41c8b9d8b3049a44",
    "policy-engine/src/polisyos/ir/model_layer/__init__.py": "aa2c8ac5e927963512184cb84e6c5b29ff55b6b1",
    "policy-engine/src/polisyos/ir/model_layer/canon.py": "02167bbe1c34c7b6501c37a122186a5aa0ea9d90",
}
VECTOR_SOURCE_BLOBS = {
    "policy-engine/tests/unit/remediation/test_can_01.py": "d4cb77099597b0888b4a68c065ff2ca74dc9a222",
    "policy-engine/tests/unit/core/phase0/test_canon_json.py": "4f17806692164a475bbef1d8a5e6c076e50750c6",
    "policy-engine/tests/unit/ir/test_canon_hardening.py": "457b8b829e3d2ed87e657cb84bece2a05bcd63b6",
    "policy-engine/tests/unit/ir/test_canon_hash_parity.py": "5599b9182fd14489ce83718652d68285817f863d",
}

SHARED_GOLDEN = (
    '{"bool":true,"bytes":{"_type":"bytes","data":"AAH+","encoding":"base64"},'
    '"date":{"_type":"date","iso":"2024-01-02"},'
    '"datetime":{"_type":"datetime","iso_utc":"2024-01-02T03:04:05Z"},'
    '"decimal":{"_type":"decimal","value":"12.30"},"integer":7,'
    '"nested":[null,{"a":0,"z":"café"}]}'
).encode("utf-8")
CORE_EXTRA_WIRES = {
    "float_hex": b'{"_type":"float_hex","value":"0x1.8p+1"}',
    "bytes_hex": b'{"_type":"bytes_hex","value":"00ff"}',
    "array_digest": b'{"_type":"array_digest","digest":"sha256:abc","length":2}',
}
EXPECTED_CANONICAL_HASHES = {
    "core.phase0.golden-hash": "898ed85a304051f6dcaac5cb2718d9fca1b853ab50b026936ea1721d092f0c08",
    "ir.hash.ordered-mapping": "fd7a343733fe0b599596ed704b17818dea7844ceee589ac794859213c2df74bc",
    "ir.hash.typed-scalars": "4ad72c5572f5f8aaf7a44f44b772dad65bfbd7c71f10ee0bc8922f553a30d9a9",
    "ir.hash.analytics-float": "f3a9cec0b4cc76042b10304051904a5646d26794d27cd8b7d535adac11f5cc93",
}


class MeasurementError(RuntimeError):
    """A required input could not be established, so the run is UNRUN."""


class DuplicateJSONKeyError(ValueError):
    """A selected JSON document has duplicate object member names."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateJSONKeyError(f"duplicate object key: {key!r}")
        value[key] = item
    return value


class _NestedModel(BaseModel):
    value: int
    optional: str | None = None


@dataclasses.dataclass(frozen=True)
class _DataclassEnvelope:
    name: str
    nested: _NestedModel
    optional: str | None = None


def _run_git(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        error = proc.stderr.decode("utf-8", "replace").strip()
        raise MeasurementError(f"git {' '.join(args)} failed ({proc.returncode}): {error}")
    return proc.stdout


def _blob_at(repo: Path, commit: str, path: str) -> str:
    return _run_git(repo, "rev-parse", f"{commit}:{path}").decode().strip()


def _verify_pins(repo: Path) -> dict[str, Any]:
    parent = _run_git(repo, "rev-parse", f"{RELOCATION_COMMIT}^").decode().strip()
    if parent != LEGACY_COMMIT:
        raise MeasurementError("relocation commit parent does not equal the pinned legacy commit")

    legacy_actual = {path: _blob_at(repo, LEGACY_COMMIT, path) for path in LEGACY_SOURCE_BLOBS}
    current_actual = {path: _blob_at(repo, INTEGRATION_COMMIT, path) for path in CURRENT_SOURCE_BLOBS}
    vector_actual = {path: _blob_at(repo, INTEGRATION_COMMIT, path) for path in VECTOR_SOURCE_BLOBS}
    if legacy_actual != LEGACY_SOURCE_BLOBS:
        raise MeasurementError("legacy source blob identity mismatch")
    if current_actual != CURRENT_SOURCE_BLOBS:
        raise MeasurementError("integration source blob identity mismatch")
    if vector_actual != VECTOR_SOURCE_BLOBS:
        raise MeasurementError("fixed-vector source blob identity mismatch")

    for path, expected in CURRENT_SOURCE_BLOBS.items():
        actual = _run_git(repo, "hash-object", path).decode().strip()
        if actual != expected:
            raise MeasurementError(f"working-tree source differs from pinned integration blob: {path}")

    return {
        "integration_commit": INTEGRATION_COMMIT,
        "legacy_commit": LEGACY_COMMIT,
        "relocation_commit": RELOCATION_COMMIT,
        "legacy_source_blobs": legacy_actual,
        "current_source_blobs": current_actual,
        "fixed_vector_source_blobs": vector_actual,
        "source_check": "pass",
    }


def _tracked_json_blobs(repo: Path) -> list[tuple[str, str]]:
    raw = _run_git(repo, "ls-tree", "-r", "-z", "--full-tree", INTEGRATION_COMMIT)
    selected: list[tuple[str, str]] = []
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, object_type, oid = metadata.decode("ascii").split()
        if object_type != "blob" or mode not in {"100644", "100755"}:
            continue
        if not raw_path.endswith(b".json"):
            continue
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MeasurementError("tracked JSON path is not UTF-8") from exc
        selected.append((path, oid))
    return sorted(selected)


def _test_caller_census(repo: Path) -> dict[str, Any]:
    output = _run_git(
        repo,
        "grep",
        "-l",
        "-E",
        "to_canonical_bytes|from_canonical_bytes|from_canonical_obj",
        INTEGRATION_COMMIT,
        "--",
        "policy-engine/tests",
    )
    paths = sorted(line.decode("utf-8") for line in output.splitlines() if line)
    manifest = hashlib.sha256()
    for path in paths:
        manifest.update(path.encode("utf-8") + b"\n")
    return {
        "selector": "git grep -l -E 'to_canonical_bytes|from_canonical_bytes|from_canonical_obj' at the pinned integration commit under policy-engine/tests",
        "caller_file_denominator": len(paths),
        "caller_path_manifest_sha256": manifest.hexdigest(),
        "executed": False,
    }


def _read_blob_batch(repo: Path, object_ids: list[str]) -> dict[str, bytes]:
    if not object_ids:
        raise MeasurementError("tracked JSON selector returned no files")
    request = "".join(f"{oid}\n" for oid in object_ids).encode("ascii")
    output = _run_git(repo, "cat-file", "--batch", input_bytes=request)
    offset = 0
    blobs: dict[str, bytes] = {}
    for expected_oid in object_ids:
        line_end = output.find(b"\n", offset)
        if line_end < 0:
            raise MeasurementError("truncated git cat-file batch header")
        header = output[offset:line_end].decode("ascii").split()
        offset = line_end + 1
        if len(header) != 3 or header[0] != expected_oid or header[1] != "blob":
            raise MeasurementError(f"unexpected git cat-file response for {expected_oid}")
        size = int(header[2])
        end = offset + size
        if end >= len(output) or output[end : end + 1] != b"\n":
            raise MeasurementError(f"truncated git blob {expected_oid}")
        blobs[expected_oid] = output[offset:end]
        offset = end + 1
    if offset != len(output):
        raise MeasurementError("unconsumed bytes in git cat-file batch output")
    return blobs


def _load_module(name: str, source: bytes, origin: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = origin
    module.__package__ = name.rpartition(".")[0]
    sys.modules[name] = module
    exec(compile(source, origin, "exec"), module.__dict__)
    return module


def _load_legacy(repo: Path) -> dict[str, types.ModuleType]:
    core_package = types.ModuleType("la021_legacy_core")
    core_package.__path__ = []  # type: ignore[attr-defined]
    sys.modules[core_package.__name__] = core_package
    core_json = _load_module(
        "la021_legacy_core.canon_json",
        _run_git(repo, "cat-file", "blob", LEGACY_SOURCE_BLOBS["policy-engine/src/polisyos/core/canon/canon_json.py"]),
        f"git:{LEGACY_COMMIT}:policy-engine/src/polisyos/core/canon/canon_json.py",
    )
    core_hash = _load_module(
        "la021_legacy_core.hashing",
        _run_git(repo, "cat-file", "blob", LEGACY_SOURCE_BLOBS["policy-engine/src/polisyos/core/canon/hashing.py"]),
        f"git:{LEGACY_COMMIT}:policy-engine/src/polisyos/core/canon/hashing.py",
    )
    ir = _load_module(
        "la021_legacy_ir",
        _run_git(repo, "cat-file", "blob", LEGACY_SOURCE_BLOBS["policy-engine/src/polisyos/ir/model_layer/canon.py"]),
        f"git:{LEGACY_COMMIT}:policy-engine/src/polisyos/ir/model_layer/canon.py",
    )
    return {"legacy_core": core_json, "legacy_core_hash": core_hash, "legacy_ir": ir}


def _stable_value_digest(value: Any) -> str:
    """Hash a decoded value without serializing it through the codec under test."""
    def token(item: Any) -> bytes:
        if item is None:
            return b"none"
        if isinstance(item, bool):
            return b"bool:1" if item else b"bool:0"
        if isinstance(item, int):
            return f"int:{item}".encode()
        if isinstance(item, float):
            return f"float:{item.hex()}".encode()
        if isinstance(item, str):
            return b"str:" + item.encode("utf-8")
        if isinstance(item, bytes):
            return b"bytes:" + item
        if isinstance(item, decimal.Decimal):
            return b"decimal:" + str(item).encode()
        if isinstance(item, dt.datetime):
            return b"datetime:" + item.isoformat().encode()
        if isinstance(item, dt.date):
            return b"date:" + item.isoformat().encode()
        if isinstance(item, dict):
            pairs = sorted(((token(k), token(v)) for k, v in item.items()), key=lambda p: p[0])
            return b"dict{" + b"".join(k + b"=" + v + b";" for k, v in pairs) + b"}"
        if isinstance(item, (list, tuple)):
            return b"list[" + b";".join(token(v) for v in item) + b"]"
        return f"{type(item).__module__}.{type(item).__qualname__}:{item!r}".encode("utf-8")

    return hashlib.sha256(token(value)).hexdigest()


def _attempt(call: Callable[[], Any], output_kind: str) -> dict[str, Any]:
    try:
        value = call()
    except Exception as exc:  # A failure is evidence, not an instrument crash.
        message = str(exc)
        return {
            "ok": False,
            "error_type": type(exc).__name__,
            "error_fqn": f"{type(exc).__module__}.{type(exc).__qualname__}",
            "error_message": message,
            "error_message_sha256": hashlib.sha256(message.encode("utf-8", "replace")).hexdigest(),
        }
    if output_kind == "bytes":
        return {"ok": True, "sha256": hashlib.sha256(value).hexdigest(), "value": value}
    return {"ok": True, "sha256": _stable_value_digest(value), "value": value}


def _same_result(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left["ok"] != right["ok"]:
        return False
    if not left["ok"]:
        return left["error_type"] == right["error_type"] and left["error_message"] == right["error_message"]
    return left["value"] == right["value"]


def _safe_result(result: dict[str, Any]) -> dict[str, Any]:
    if not result["ok"]:
        return {
            "ok": False,
            "error_type": result["error_type"],
            "error_fqn": result["error_fqn"],
            "error_message_sha256": result["error_message_sha256"],
        }
    return {"ok": True, "sha256": result["sha256"]}


def _update_aggregate(aggregate: Any, case_id: str, result: dict[str, Any]) -> None:
    encoded = json.dumps(_safe_result(result), sort_keys=True, separators=(",", ":")).encode()
    aggregate.update(case_id.encode("utf-8") + b"\0" + encoded + b"\n")


def _counter_row(counter: Counter[str], aggregate: Any) -> dict[str, Any]:
    denominator = counter["success"] + counter["error"]
    return {
        "denominator": denominator,
        "success": counter["success"],
        "error": counter["error"],
        "aggregate_sha256": aggregate.hexdigest(),
    }


def _json_corpus(repo: Path, implementations: dict[str, types.ModuleType]) -> dict[str, Any]:
    selected = _tracked_json_blobs(repo)
    unique_oids = sorted({oid for _, oid in selected})
    blob_data = _read_blob_batch(repo, unique_oids)
    path_byte_count = sum(len(blob_data[oid]) for _, oid in selected)
    unique_byte_count = sum(len(blob_data[oid]) for oid in unique_oids)
    manifest = hashlib.sha256()
    for path, oid in selected:
        manifest.update(path.encode("utf-8") + b"\0" + oid.encode("ascii") + b"\n")

    names = ["legacy_core", "current_core", "legacy_ir", "current_ir"]
    modes = {"default": {}, "floats-enabled": {"forbid_floats": False}}
    counters: dict[str, Counter[str]] = {
        f"{name}.{op}": Counter()
        for name in names
        for op in ("encode-default", "encode-floats-enabled", "decode-source", "decode-object")
    }
    aggregates = {key: hashlib.sha256() for key in counters}
    comparisons: Counter[str] = Counter()
    differences: list[dict[str, Any]] = []
    parse_errors: list[dict[str, str]] = []
    files_containing_floats = 0
    typed_tags: Counter[str] = Counter()

    def mismatch(case_id: str, operation: str, left_name: str, right_name: str, left: dict[str, Any], right: dict[str, Any]) -> None:
        comparisons[f"{left_name}__vs__{right_name}.{operation}.mismatch"] += 1
        differences.append({
            "case": case_id,
            "operation": operation,
            "left": left_name,
            "right": right_name,
            "left_result": _safe_result(left),
            "right_result": _safe_result(right),
        })

    for path, oid in selected:
        try:
            source_text = blob_data[oid].decode("utf-8")
            value = json.loads(
                source_text,
                object_pairs_hook=_unique_object,
                parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"non-standard JSON constant {token}")),
            )
        except Exception as exc:
            message = str(exc)
            parse_errors.append({
                "path": path,
                "blob": oid,
                "error_type": type(exc).__name__,
                "error_message_sha256": hashlib.sha256(message.encode("utf-8", "replace")).hexdigest(),
            })
            continue
        if _has_float(value):
            files_containing_floats += 1
        _collect_tags(value, typed_tags)
        case_id = f"{path}@{oid}"
        outcomes: dict[str, dict[str, dict[str, Any]]] = {}
        for mode_name, spec_options in modes.items():
            operation = "encode-default" if mode_name == "default" else "encode-floats-enabled"
            outcomes[mode_name] = {}
            for name in names:
                module = implementations[name]
                spec = module.CanonSpec(**spec_options)
                result = _attempt(lambda m=module, s=spec: m.to_canonical_bytes(value, s), "bytes")
                outcomes[mode_name][name] = result
                key = f"{name}.{operation}"
                counters[key]["success" if result["ok"] else "error"] += 1
                _update_aggregate(aggregates[key], case_id, result)
            for old_name, new_name in (("legacy_core", "current_core"), ("legacy_ir", "current_ir")):
                left, right = outcomes[mode_name][old_name], outcomes[mode_name][new_name]
                if _same_result(left, right):
                    comparisons[f"{old_name}__vs__{new_name}.{operation}.equal"] += 1
                else:
                    mismatch(case_id, operation, old_name, new_name, left, right)

        raw = blob_data[oid]
        decoded: dict[str, dict[str, Any]] = {}
        for name in names:
            module = implementations[name]
            result = _attempt(lambda m=module: m.from_canonical_bytes(raw), "value")
            decoded[name] = result
            key = f"{name}.decode-source"
            counters[key]["success" if result["ok"] else "error"] += 1
            _update_aggregate(aggregates[key], case_id, result)
            if result["ok"] and result["value"] != value:
                mismatch(case_id, "decode-source-roundtrip", "parsed-json", name, {"ok": True, "value": value, "sha256": _stable_value_digest(value)}, result)
        for old_name, new_name in (("legacy_core", "current_core"), ("legacy_ir", "current_ir")):
            if _same_result(decoded[old_name], decoded[new_name]):
                comparisons[f"{old_name}__vs__{new_name}.decode-source.equal"] += 1
            else:
                mismatch(case_id, "decode-source", old_name, new_name, decoded[old_name], decoded[new_name])

        decoded_objects: dict[str, dict[str, Any]] = {}
        for name in names:
            module = implementations[name]
            result = _attempt(lambda m=module: m.from_canonical_obj(value), "value")
            decoded_objects[name] = result
            key = f"{name}.decode-object"
            counters[key]["success" if result["ok"] else "error"] += 1
            _update_aggregate(aggregates[key], case_id, result)
            if result["ok"] and result["value"] != value:
                mismatch(case_id, "decode-object-roundtrip", "parsed-json", name, {"ok": True, "value": value, "sha256": _stable_value_digest(value)}, result)
        for old_name, new_name in (("legacy_core", "current_core"), ("legacy_ir", "current_ir")):
            if _same_result(decoded_objects[old_name], decoded_objects[new_name]):
                comparisons[f"{old_name}__vs__{new_name}.decode-object.equal"] += 1
            else:
                mismatch(case_id, "decode-object", old_name, new_name, decoded_objects[old_name], decoded_objects[new_name])

        for mode_name, per_name in outcomes.items():
            for profile_old, profile_new in (("legacy_core", "current_core"), ("legacy_ir", "current_ir")):
                old_encoded, new_encoded = per_name[profile_old], per_name[profile_new]
                if not old_encoded["ok"] or not new_encoded["ok"]:
                    continue
                old_reader = implementations[profile_old]
                new_reader = implementations[profile_new]
                for reader_name, reader, encoded_name, encoded in (
                    (profile_old, old_reader, profile_new, new_encoded),
                    (profile_new, new_reader, profile_old, old_encoded),
                ):
                    result = _attempt(lambda r=reader, e=encoded: r.from_canonical_bytes(e["value"]), "value")
                    if result["ok"] and result["value"] == value:
                        comparisons[f"{profile_old}__vs__{profile_new}.{mode_name}.cross-decode.equal"] += 1
                    else:
                        mismatch(case_id, f"{mode_name}.cross-decode.{reader_name}-reads-{encoded_name}", reader_name, encoded_name, {"ok": True, "value": value, "sha256": _stable_value_digest(value)}, result)

    profile_rows = {}
    for name in names:
        profile_rows[name] = {
            "encode_default": _counter_row(counters[f"{name}.encode-default"], aggregates[f"{name}.encode-default"]),
            "encode_floats_enabled": _counter_row(counters[f"{name}.encode-floats-enabled"], aggregates[f"{name}.encode-floats-enabled"]),
            "decode_source_bytes": _counter_row(counters[f"{name}.decode-source"], aggregates[f"{name}.decode-source"]),
            "decode_source_object": _counter_row(counters[f"{name}.decode-object"], aggregates[f"{name}.decode-object"]),
        }
    return {
        "selector": "every regular Git blob with a case-sensitive .json suffix in the pinned integration tree",
        "path_denominator": len(selected),
        "unique_blob_denominator": len(unique_oids),
        "duplicate_path_occurrences": len(selected) - len(unique_oids),
        "path_bytes": path_byte_count,
        "unique_blob_bytes_read": unique_byte_count,
        "parsed_case_denominator": len(selected) - len(parse_errors),
        "input_manifest_sha256": manifest.hexdigest(),
        "successful_blob_reads": len(unique_oids),
        "strict_json_parse_successes": len(selected) - len(parse_errors),
        "parse_errors": parse_errors,
        "files_containing_floats": files_containing_floats,
        "typed_tag_occurrences": dict(sorted(typed_tags.items())),
        "per_profile": profile_rows,
        "comparison_counts": dict(sorted(comparisons.items())),
        "discrepancies": differences,
    }


def _has_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_has_float(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_float(item) for item in value)
    return False


def _collect_tags(value: Any, tags: Counter[str]) -> None:
    if isinstance(value, dict):
        if "_type" in value:
            tags[repr(value["_type"])] += 1
        for nested in value.values():
            _collect_tags(nested, tags)
    elif isinstance(value, list):
        for nested in value:
            _collect_tags(nested, tags)


def _fixed_cases() -> list[dict[str, Any]]:
    golden = {
        "bool": True,
        "bytes": b"\x00\x01\xfe",
        "date": dt.date(2024, 1, 2),
        "datetime": dt.datetime(2024, 1, 2, 3, 4, 5, tzinfo=dt.UTC),
        "decimal": decimal.Decimal("12.30"),
        "integer": 7,
        "nested": [None, {"z": "café", "a": 0}],
    }
    key_order_a = {"b": 1, "a": "x", "nested": {"z": 9, "y": 8}}
    key_order_b = {"nested": {"y": 8, "z": 9}, "a": "x", "b": 1}
    envelope = _DataclassEnvelope(name="outer", nested=_NestedModel(value=7))
    phase0 = {
        "b": 1,
        "a": "test",
        "d": {"x": decimal.Decimal("1.2300")},
        "t": dt.datetime(2026, 1, 10, 12, 0, 0, tzinfo=dt.UTC),
    }
    plus_two = dt.timezone(dt.timedelta(hours=2))
    parity_payload = {
        "text": "policy",
        "num": 42,
        "decimal": decimal.Decimal("12.34"),
        "ts": dt.datetime(2026, 2, 9, 20, 0, tzinfo=dt.UTC),
        "date": dt.date(2026, 2, 9),
        "bytes": b"abc",
        "float": 1.25,
        "nested": {"b": 2, "a": 1},
        "items": [1, {"z": 3, "y": 2}],
    }
    ir_ordered = {"b": 2, "a": 1, "nested": {"z": "last", "m": None}}
    ir_typed = {
        "when": dt.datetime(2026, 4, 12, 15, 30, tzinfo=dt.timezone(dt.timedelta(hours=3))),
        "amount": decimal.Decimal("12.3400"),
        "blob": b"policy",
    }
    ir_float = {"effect": -0.0, "estimate": 0.125}

    cases = [
        {"id": "can01.mixed-golden", "value": golden, "expected_bytes": SHARED_GOLDEN, "decode_expected": golden},
        {"id": "core.phase0.key-order-a", "value": key_order_a, "decode_expected": key_order_a},
        {"id": "core.phase0.key-order-b", "value": key_order_b, "decode_expected": key_order_b},
        {"id": "core.phase0.golden-hash", "value": phase0, "expected_sha256": EXPECTED_CANONICAL_HASHES["core.phase0.golden-hash"], "decode_expected": phase0},
        {"id": "ir.hardening.dataclass-default", "value": envelope, "expected_bytes": b'{"name":"outer","nested":{"value":7}}', "decode_expected": {"name": "outer", "nested": {"value": 7}}},
        {"id": "ir.hardening.dataclass-include-null", "value": envelope, "spec": {"exclude_none": False}, "expected_bytes": b'{"name":"outer","nested":{"optional":null,"value":7},"optional":null}', "decode_expected": {"name": "outer", "nested": {"optional": None, "value": 7}, "optional": None}},
        {"id": "ir.hardening.raw-mapping-null", "value": {"optional": None}, "expected_bytes": b'{"optional":null}', "decode_expected": {"optional": None}},
        {"id": "ir.hardening.timezone-local", "value": {"t": dt.datetime(2026, 4, 12, 14, 30, tzinfo=plus_two)}, "expected_bytes": b'{"t":{"_type":"datetime","iso_utc":"2026-04-12T12:30:00Z"}}', "decode_expected": {"t": dt.datetime(2026, 4, 12, 12, 30, tzinfo=dt.UTC)}},
        {"id": "ir.hardening.float-enabled", "value": {"negative_zero": -0.0, "estimate": 0.125}, "spec": {"forbid_floats": False}, "expected_bytes": b'{"estimate":{"_type":"float","repr":"0.125"},"negative_zero":{"_type":"float","repr":"0"}}', "decode_expected": {"negative_zero": 0.0, "estimate": 0.125}},
        {"id": "ir.parity.payload", "value": parity_payload, "spec": {"forbid_floats": False}, "decode_expected": parity_payload},
        {"id": "ir.hash.ordered-mapping", "value": ir_ordered, "expected_sha256": EXPECTED_CANONICAL_HASHES["ir.hash.ordered-mapping"], "decode_expected": ir_ordered},
        {"id": "ir.hash.typed-scalars", "value": ir_typed, "expected_sha256": EXPECTED_CANONICAL_HASHES["ir.hash.typed-scalars"], "decode_expected": ir_typed},
        {"id": "ir.hash.analytics-float", "value": ir_float, "spec": {"forbid_floats": False}, "expected_sha256": EXPECTED_CANONICAL_HASHES["ir.hash.analytics-float"], "decode_expected": {"effect": 0.0, "estimate": 0.125}},
        {"id": "negative.float-default", "value": {"x": 0.1}},
        {"id": "negative.nan-with-floats-enabled", "value": {"x": float("nan")}, "spec": {"forbid_floats": False}},
        {"id": "negative.infinity-with-floats-enabled", "value": {"x": float("inf")}, "spec": {"forbid_floats": False}},
        {"id": "negative.unknown-tag", "value": {"_type": "future_tag", "value": "x"}, "wire": b'{"_type":"future_tag","value":"x"}'},
        {"id": "negative.nonstring-tag-list", "value": {"_type": [], "value": "list-tag"}, "wire": b'{"_type":[],"value":"list-tag"}'},
        {"id": "negative.nonstring-tag-object", "value": {"_type": {}, "value": "object-tag"}, "wire": b'{"_type":{},"value":"object-tag"}'},
        {"id": "negative.nonstring-key", "value": {1: "not-json-key"}},
        {"id": "negative.unsupported-set", "value": {"x": {1, 2}}},
        {"id": "negative.encode-depth", "value": {"outer": {"inner": 1}}, "spec": {"max_depth": 1}},
        {"id": "negative.decode-depth", "value": None, "wire": b'{"outer":{"inner":1}}', "decode_kwargs": {"max_depth": 1}},
        {"id": "negative.malformed-json", "value": None, "wire": b'{"broken":'},
    ]
    expected_core_tag_values = {
        "float_hex": 3.0,
        "bytes_hex": b"\x00\xff",
        "array_digest": {"_type": "array_digest", "digest": "sha256:abc", "length": 2},
    }
    for tag, wire in CORE_EXTRA_WIRES.items():
        cases.append({"id": f"core-only-tag.{tag}", "value": json.loads(wire), "wire": wire, "decode_expected": expected_core_tag_values[tag], "core_only": True})
    return cases


def _fixed_vectors(implementations: dict[str, types.ModuleType]) -> dict[str, Any]:
    names = ["legacy_core", "current_core", "legacy_ir", "current_ir"]
    comparisons: Counter[str] = Counter()
    differences: list[dict[str, Any]] = []
    expected_differences: list[dict[str, Any]] = []
    operations: dict[str, dict[str, Counter[str]]] = {
        name: {"encode": Counter(), "decode": Counter(), "decode_object": Counter()} for name in names
    }

    for case in _fixed_cases():
        outcomes: dict[str, dict[str, Any]] = {}
        spec_options = case.get("spec", {})
        for name in names:
            module = implementations[name]
            spec = module.CanonSpec(**spec_options)
            result = _attempt(lambda m=module, s=spec, c=case: m.to_canonical_bytes(c["value"], s), "bytes")
            outcomes[name] = result
            operations[name]["encode"]["success" if result["ok"] else "error"] += 1

        for old_name, new_name in (("legacy_core", "current_core"), ("legacy_ir", "current_ir")):
            old, current = outcomes[old_name], outcomes[new_name]
            if _same_result(old, current):
                comparisons[f"{old_name}__vs__{new_name}.encode.equal"] += 1
            elif case["id"] in {"negative.nonstring-tag-list", "negative.nonstring-tag-object"} and old.get("error_type") == "TypeError" and current.get("error_type") == "CanonViolation":
                expected_differences.append({
                    "case": case["id"],
                    "operation": "encode",
                    "profile": "core" if old_name == "legacy_core" else "ir",
                    "historical": _safe_result(old),
                    "current": _safe_result(current),
                    "reason": "current gate checks the tag type before set membership; historical encoder leaked TypeError for unhashable tags",
                })
            else:
                differences.append({"case": case["id"], "operation": "encode", "left": old_name, "right": new_name, "left_result": _safe_result(old), "right_result": _safe_result(current)})

        if not case.get("core_only"):
            for old_name, current_name in (("legacy_core", "legacy_ir"), ("current_core", "current_ir")):
                left, right = outcomes[old_name], outcomes[current_name]
                if _same_result(left, right):
                    comparisons[f"{old_name}__vs__{current_name}.shared-profile-encode.equal"] += 1
                else:
                    differences.append({"case": case["id"], "operation": "shared-profile-encode", "left": old_name, "right": current_name, "left_result": _safe_result(left), "right_result": _safe_result(right)})

        expected_bytes = case.get("expected_bytes")
        expected_sha = case.get("expected_sha256")
        for name, result in outcomes.items():
            if expected_bytes is not None and (not result["ok"] or result["value"] != expected_bytes):
                differences.append({"case": case["id"], "operation": "independent-expected-bytes", "profile": name, "expected_sha256": hashlib.sha256(expected_bytes).hexdigest(), "actual": _safe_result(result)})
            if expected_sha is not None and (not result["ok"] or result["sha256"] != expected_sha):
                differences.append({"case": case["id"], "operation": "independent-expected-sha256", "profile": name, "expected_sha256": expected_sha, "actual": _safe_result(result)})

        decode_inputs: list[tuple[str, bytes]] = []
        if "wire" in case:
            decode_inputs.append(("fixed-wire", case["wire"]))
        decode_inputs.extend(
            (f"encoded-by-{writer}", result["value"])
            for writer, result in outcomes.items()
            if result["ok"]
        )
        for input_id, encoded in decode_inputs:
            decode_outcomes: dict[str, dict[str, Any]] = {}
            for name in names:
                module = implementations[name]
                result = _attempt(
                    lambda m=module, c=case, data=encoded: m.from_canonical_bytes(
                        data, **c.get("decode_kwargs", {})
                    ),
                    "value",
                )
                decode_outcomes[name] = result
                operations[name]["decode"]["success" if result["ok"] else "error"] += 1
                expected_decode = case.get("decode_expected")
                if expected_decode is not None and result["ok"] and result["value"] != expected_decode:
                    differences.append({
                        "case": case["id"],
                        "operation": f"decode-expected.{input_id}",
                        "profile": name,
                        "expected_sha256": _stable_value_digest(expected_decode),
                        "actual": _safe_result(result),
                    })
            for old_name, current_name in (("legacy_core", "current_core"), ("legacy_ir", "current_ir")):
                old, current = decode_outcomes[old_name], decode_outcomes[current_name]
                if _same_result(old, current):
                    comparisons[f"{old_name}__vs__{current_name}.decode.equal"] += 1
                else:
                    differences.append({"case": case["id"], "operation": f"decode.{input_id}", "left": old_name, "right": current_name, "left_result": _safe_result(old), "right_result": _safe_result(current)})
            if case.get("core_only"):
                for name in ("legacy_core", "current_core"):
                    result = decode_outcomes[name]
                    if not result["ok"] or result["value"] != case["decode_expected"]:
                        differences.append({"case": case["id"], "operation": f"core-profile-decode.{input_id}", "profile": name, "actual": _safe_result(result)})
                for name in ("legacy_ir", "current_ir"):
                    result = decode_outcomes[name]
                    if result["ok"] or result.get("error_type") != "CanonViolation":
                        differences.append({"case": case["id"], "operation": f"ir-profile-decode-rejection.{input_id}", "profile": name, "actual": _safe_result(result)})

        object_input = None
        object_input_id = None
        if "wire" in case:
            try:
                object_input = json.loads(
                    case["wire"],
                    parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"non-standard JSON constant {token}")),
                )
                object_input_id = "fixed-wire-object"
            except Exception:
                pass
        if object_input_id is None and outcomes["legacy_core"]["ok"]:
            object_input = json.loads(outcomes["legacy_core"]["value"])
            object_input_id = "legacy-core-encoded-object"
        if object_input_id is None and case["id"] in {
            "negative.nonstring-tag-list",
            "negative.nonstring-tag-object",
            "negative.unknown-tag",
        }:
            object_input = case["value"]
            object_input_id = "direct-invalid-tag-object"
        if object_input_id is not None:
            object_outcomes: dict[str, dict[str, Any]] = {}
            for name in names:
                module = implementations[name]
                result = _attempt(
                    lambda m=module, c=case, obj=object_input: m.from_canonical_obj(
                        obj, **c.get("decode_kwargs", {})
                    ),
                    "value",
                )
                object_outcomes[name] = result
                operations[name]["decode_object"]["success" if result["ok"] else "error"] += 1
                if result["ok"] and case.get("decode_expected") is not None and result["value"] != case["decode_expected"]:
                    differences.append({
                        "case": case["id"],
                        "operation": f"decode-object-expected.{object_input_id}",
                        "profile": name,
                        "expected_sha256": _stable_value_digest(case["decode_expected"]),
                        "actual": _safe_result(result),
                    })
            for old_name, current_name in (("legacy_core", "current_core"), ("legacy_ir", "current_ir")):
                old, current = object_outcomes[old_name], object_outcomes[current_name]
                if _same_result(old, current):
                    comparisons[f"{old_name}__vs__{current_name}.decode-object.equal"] += 1
                else:
                    differences.append({
                        "case": case["id"],
                        "operation": f"decode-object.{object_input_id}",
                        "left": old_name,
                        "right": current_name,
                        "left_result": _safe_result(old),
                        "right_result": _safe_result(current),
                    })
            if case["id"] in {"negative.nonstring-tag-list", "negative.nonstring-tag-object", "negative.unknown-tag"}:
                for name in names:
                    expected_class = implementations[name].CanonViolation
                    result = object_outcomes[name]
                    if result["ok"] or result.get("error_fqn") != f"{expected_class.__module__}.{expected_class.__qualname__}":
                        differences.append({
                            "case": case["id"],
                            "operation": f"decode-object-facade-exception-identity.{object_input_id}",
                            "profile": name,
                            "expected_fqn": f"{expected_class.__module__}.{expected_class.__qualname__}",
                            "actual": _safe_result(result),
                        })

        if case.get("core_only"):
            for name in ("legacy_core", "current_core"):
                if not outcomes[name]["ok"] or outcomes[name]["value"] != case["wire"]:
                    differences.append({"case": case["id"], "operation": "core-profile-acceptance", "profile": name, "actual": _safe_result(outcomes[name])})
            for name in ("legacy_ir", "current_ir"):
                if outcomes[name]["ok"] or outcomes[name].get("error_type") != "CanonViolation":
                    differences.append({"case": case["id"], "operation": "ir-profile-rejection", "profile": name, "actual": _safe_result(outcomes[name])})

    return {
        "fixed_case_denominator": len(_fixed_cases()),
        "per_profile": {
            name: {
                "encode": {
                    "denominator": row["encode"]["success"] + row["encode"]["error"],
                    "success": row["encode"]["success"],
                    "error": row["encode"]["error"],
                },
                "decode": {
                    "denominator": row["decode"]["success"] + row["decode"]["error"],
                    "success": row["decode"]["success"],
                    "error": row["decode"]["error"],
                },
                "decode_object": {
                    "denominator": row["decode_object"]["success"] + row["decode_object"]["error"],
                    "success": row["decode_object"]["success"],
                    "error": row["decode_object"]["error"],
                },
            }
            for name, row in operations.items()
        },
        "comparison_counts": dict(sorted(comparisons.items())),
        "expected_historical_differences": expected_differences,
        "discrepancies": differences,
        "profile_identity_checks": {
            "legacy_core_ir_exception_classes_distinct": implementations["legacy_core"].CanonViolation is not implementations["legacy_ir"].CanonViolation,
            "current_core_ir_exception_classes_distinct": implementations["current_core"].CanonViolation is not implementations["current_ir"].CanonViolation,
            "current_core_exception_fqn": f"{implementations['current_core'].CanonViolation.__module__}.{implementations['current_core'].CanonViolation.__qualname__}",
            "current_ir_exception_fqn": f"{implementations['current_ir'].CanonViolation.__module__}.{implementations['current_ir'].CanonViolation.__qualname__}",
        },
    }


def _hash_vectors(implementations: dict[str, types.ModuleType]) -> dict[str, Any]:
    hashers = {
        "legacy_core": implementations["legacy_core_hash"],
        "current_core": implementations["current_core"],
        "legacy_ir": implementations["legacy_ir"],
        "current_ir": implementations["current_ir"],
    }
    raw_inputs = [
        ("bytes", b"legacy-canon-payload"),
        ("utf8-string", "canonical café"),
        ("bytearray", bytearray(b"canonical-bytes")),
        ("memoryview", memoryview(b"canonical-memoryview")),
    ]
    comparisons: Counter[str] = Counter()
    discrepancies: list[dict[str, Any]] = []
    per_profile: dict[str, Counter[str]] = {name: Counter() for name in hashers}

    def raw_bytes(value: bytes | bytearray | memoryview | str) -> bytes:
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, memoryview):
            return value.tobytes()
        return value.encode("utf-8")

    def digest(value: bytes, algorithm: str, digest_size: int | None) -> str:
        if algorithm == "sha256":
            return hashlib.sha256(value).hexdigest()
        if algorithm == "sha1":
            return hashlib.sha1(value).hexdigest()
        if digest_size is None:
            return hashlib.blake2b(value).hexdigest()
        return hashlib.blake2b(value, digest_size=digest_size).hexdigest()

    def call_quietly(call: Callable[[], Any]) -> Any:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return call()

    for input_id, payload in raw_inputs:
        source = raw_bytes(payload)
        variants = [("sha256", None), ("blake2b", None), ("blake2b", 16), ("sha1", None)]
        for algorithm, digest_size in variants:
            kwargs = {"algorithm": algorithm, "prefix": True, "digest_size": digest_size}
            expected = f"{algorithm}:{digest(source, algorithm, digest_size)}"
            results = {}
            for name, module in hashers.items():
                result = _attempt(
                    lambda m=module, p=payload, kw=kwargs: call_quietly(lambda: m.content_hash(p, **kw)),
                    "value",
                )
                results[name] = result
                per_profile[name]["success" if result["ok"] else "error"] += 1
                if not result["ok"] or result["value"] != expected:
                    discrepancies.append({"case": f"raw-hash.{input_id}.{algorithm}.{digest_size or 'default'}", "profile": name, "expected": expected, "actual": _safe_result(result)})
            for old_name, current_name in (("legacy_core", "current_core"), ("legacy_ir", "current_ir")):
                if _same_result(results[old_name], results[current_name]):
                    comparisons[f"{old_name}__vs__{current_name}.content_hash.equal"] += 1
                else:
                    discrepancies.append({"case": f"raw-hash.{input_id}.{algorithm}.{digest_size or 'default'}", "left": old_name, "right": current_name, "left_result": _safe_result(results[old_name]), "right_result": _safe_result(results[current_name])})

    golden_value = _fixed_cases()[0]["value"]
    golden_digest = hashlib.sha256(SHARED_GOLDEN).hexdigest()
    for name, module in (("legacy_core", hashers["legacy_core"]), ("current_core", hashers["current_core"])):
        result = _attempt(lambda m=module: m.fingerprint(golden_value), "value")
        per_profile[name]["fingerprint_success" if result["ok"] else "fingerprint_error"] += 1
        if not result["ok"] or result["value"] != golden_digest:
            discrepancies.append({"case": "core.fingerprint.shared-golden", "profile": name, "expected": golden_digest, "actual": _safe_result(result)})

    payload = b"streamed legacy canonical data"
    chunks = [payload[:8], payload[8:17], payload[17:]]
    expected = hashlib.sha256(payload).hexdigest()
    core_extra_results: dict[str, dict[str, dict[str, Any]]] = {
        "truncated_hash": {},
        "streaming_hash": {},
    }
    for name, module in (("legacy_core", hashers["legacy_core"]), ("current_core", hashers["current_core"])):
        truncated = _attempt(lambda m=module: m.truncated_hash(payload, length=16), "value")
        streaming = _attempt(lambda m=module: m.streaming_hash(chunks), "value")
        core_extra_results["truncated_hash"][name] = truncated
        core_extra_results["streaming_hash"][name] = streaming
        per_profile[name]["truncated_success" if truncated["ok"] else "truncated_error"] += 1
        per_profile[name]["streaming_success" if streaming["ok"] else "streaming_error"] += 1
        if not truncated["ok"] or truncated["value"] != expected[:16]:
            discrepancies.append({"case": "core.truncated_hash", "profile": name, "expected": expected[:16], "actual": _safe_result(truncated)})
        if not streaming["ok"] or streaming["value"] != expected:
            discrepancies.append({"case": "core.streaming_hash", "profile": name, "expected": expected, "actual": _safe_result(streaming)})
    for operation in ("truncated_hash", "streaming_hash"):
        equal = _same_result(
            core_extra_results[operation]["legacy_core"],
            core_extra_results[operation]["current_core"],
        )
        comparisons[f"legacy_core__vs__current_core.{operation}.equal"] = int(equal)
        if not equal:
            discrepancies.append({
                "case": f"core.{operation}",
                "left": "legacy_core",
                "right": "current_core",
                "left_result": _safe_result(core_extra_results[operation]["legacy_core"]),
                "right_result": _safe_result(core_extra_results[operation]["current_core"]),
            })

    return {
        "raw_hash_case_denominator_per_profile": len(raw_inputs) * 4,
        "raw_hash_expected_oracle": "Python hashlib over explicit bytes/UTF-8 encoding; no codec hash implementation used as oracle",
        "per_profile": {
            name: {
                "raw_content_hash_denominator": len(raw_inputs) * 4,
                "raw_content_hash_success": row["success"],
                "raw_content_hash_error": row["error"],
                "core_fingerprint_calls": row["fingerprint_success"] + row["fingerprint_error"],
                "core_truncated_hash_calls": row["truncated_success"] + row["truncated_error"],
                "core_streaming_hash_calls": row["streaming_success"] + row["streaming_error"],
            }
            for name, row in per_profile.items()
        },
        "comparison_counts": dict(sorted(comparisons.items())),
        "discrepancies": discrepancies,
    }


def _load_current(repo: Path) -> dict[str, types.ModuleType]:
    sys.path.insert(0, str(repo / "policy-engine" / "src"))
    return {
        "current_core": importlib.import_module("polisyos.core.canon"),
        "current_ir": importlib.import_module("polisyos.ir.model_layer.canon"),
    }


def _receipt(repo: Path) -> dict[str, Any]:
    start = time.perf_counter()
    pins = _verify_pins(repo)
    caller_census = _test_caller_census(repo)
    legacy = _load_legacy(repo)
    current = _load_current(repo)
    implementations = {**legacy, **current}
    corpus = _json_corpus(repo, implementations)
    fixed = _fixed_vectors(implementations)
    hashes = _hash_vectors(implementations)

    parse_incomplete = bool(corpus["parse_errors"])
    unexpected = bool(corpus["discrepancies"] or fixed["discrepancies"] or hashes["discrepancies"])
    if parse_incomplete:
        verdict = "UNRUN"
    elif unexpected:
        verdict = "fail"
    else:
        verdict = "pass"
    elapsed = time.perf_counter() - start
    return {
        "schema": "PolicyOS_E02R2.LA021CanonicalizationRecheck.v1",
        "verdict": verdict,
        "exit_code": {"pass": 0, "fail": 1, "UNRUN": 2}[verdict],
        "elapsed_seconds": round(elapsed, 3),
        "runtime": {"python": sys.version.split()[0], "pydantic": pydantic.__version__, "platform": sys.platform},
        "pins": pins,
        "inputs_read": {
            "json_selector": corpus["selector"],
            "json_paths": corpus["path_denominator"],
            "json_unique_git_blobs": corpus["unique_blob_denominator"],
            "json_duplicate_path_occurrences": corpus["duplicate_path_occurrences"],
            "json_path_bytes": corpus["path_bytes"],
            "git_blob_bytes_read": corpus["unique_blob_bytes_read"],
            "json_input_manifest_sha256": corpus["input_manifest_sha256"],
            "json_blobs_successfully_read": corpus["successful_blob_reads"],
            "strict_json_documents_parsed": corpus["strict_json_parse_successes"],
            "tracked_vector_sources": pins["fixed_vector_source_blobs"],
            "historical_codec_source_blobs": pins["legacy_source_blobs"],
            "current_codec_source_blobs": pins["current_source_blobs"],
            "codec_test_caller_census": caller_census,
        },
        "json_corpus": {
            "files_containing_floats": corpus["files_containing_floats"],
            "typed_tag_occurrences": corpus["typed_tag_occurrences"],
            "per_profile": corpus["per_profile"],
            "comparison_counts": corpus["comparison_counts"],
            "discrepancies": corpus["discrepancies"],
            "parse_errors": corpus["parse_errors"],
        },
        "fixed_non_json_vectors": fixed,
        "hashing_vectors": hashes,
        "unresolved_by_construction": [
            {"class": "architect_418_input_set", "not_measured": "No immutable manifest for the architect's 418 input cases was found; this is a new exhaustive tracked-JSON denominator plus pinned codec vectors, not a replay of that unidentified selector."},
            {"class": "non_json_tracked_inputs", "not_measured": "Tracked YAML, TOML, CSV, source-defined dynamic objects outside the fixed vectors, and non-JSON binary fixtures."},
            {"class": "runtime_generated_persisted_artifacts", "not_measured": "Ignored E02 scratch CAS blobs, production_data, and every historical CAS object are not enumerated by the tracked-JSON selector."},
            {"class": "dynamic_test_inputs", "not_measured": f"{caller_census['caller_file_denominator']} tracked test files call the codec API; this instrument uses its named fixed vectors but does not execute those callers or enumerate runtime-created values."},
            {"class": "typed_tag_shape_space", "not_measured": "The complete JSON corpus has no _type tags. Fixed vectors cover the common tags and the three known Core-only tags, not every arbitrary tag payload or nested adversarial shape."},
            {"class": "runtime_matrix", "not_measured": "One Python/Pydantic runtime is measured; compatibility across supported interpreter and Pydantic versions is not established."},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, help="repository root; defaults to the current Git worktree")
    args = parser.parse_args()
    try:
        repo = args.repo_root or Path(__file__).resolve()
        if repo.is_file():
            repo = repo.parent
        root_bytes = _run_git(repo, "rev-parse", "--show-toplevel")
        repo = Path(root_bytes.decode().strip())
        result = _receipt(repo)
    except Exception as exc:
        message = str(exc)
        result = {
            "schema": "PolicyOS_E02R2.LA021CanonicalizationRecheck.v1",
            "verdict": "UNRUN",
            "exit_code": 2,
            "runtime": {"python": sys.version.split()[0], "pydantic": pydantic.__version__, "platform": sys.platform},
            "declared_inputs": {
                "integration_commit": INTEGRATION_COMMIT,
                "legacy_commit": LEGACY_COMMIT,
                "relocation_commit": RELOCATION_COMMIT,
                "tracked_json_selector": "every regular Git blob with a case-sensitive .json suffix in the pinned integration tree",
                "fixed_vector_source_blobs": VECTOR_SOURCE_BLOBS,
                "current_codec_source_blobs": CURRENT_SOURCE_BLOBS,
                "historical_codec_source_blobs": LEGACY_SOURCE_BLOBS,
            },
            "failure": {
                "error_type": type(exc).__name__,
                "error_fqn": f"{type(exc).__module__}.{type(exc).__qualname__}",
                "error_message_sha256": hashlib.sha256(message.encode("utf-8", "replace")).hexdigest(),
            },
            "unresolved_by_construction": [
                {"class": "measurement_setup_or_input_read", "not_measured": "The required source pins, Git tree inputs, parser, or codec import could not be established."}
            ],
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
