"""Restore only exact original J harness paths from an issued retained manifest.

No gates, imports of retained helpers, receipt rewrites, or product writes occur.
An execution binding must come from an actual retained command receipt. There is
deliberately no default manifest: final execution pins have not been measured yet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

PREFIX = "docs/superpowers/journals/gy-eight-gaps-evidence/"
ALLOWED = {
    "_build/gy_gaps/receipt.py",
    "_build/gy_gaps/l_receipt_reconcile.py",
    "_build/gy_gaps/j_l_regression_wave.py",
    "_build/gy_gaps/j_l_regression_reconcile.py",
    "_build/gy_gaps/j_removal_wave.py",
    "_build/gy_gaps/j_native_wave.py",
    "_build/gy-gaps/j/static_rederivations.py",
    "_build/gy_gaps/d1_strangle.py",
    "_build/gy_gaps/j_inventory_history.py",
    "_build/gy_gaps/refresh_m1_snapshot.py",
    "_build/gy_gaps/refresh_m1_hashes.py",
    "_build/gy_gaps/phase2_current_corruption.py",
    "_build/gy_gaps/j_pinned_harness.py",
    "_build/gy-gaps/j/removal_probes.py",
    "_build/gy-gaps/j/merge-planning/recorded_recomputation_removal.py",
    "_build/gy-gaps/j/merge-planning/witness_dependency_removal.py",
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw: bytes | str):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate_json_key:" + key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def relative(root: Path, value: str) -> Path:
    require(type(value) is str and value and not value.startswith("/")
            and all(part not in {"", ".", ".."} for part in value.split("/")),
            "noncanonical_relative_path")
    path = root
    parts = value.split("/")
    for index, part in enumerate(parts):
        path = path / part
        require(not path.is_symlink(), "symlink_path_refused:" + str(path))
        require(index == len(parts) - 1 or not path.exists() or path.is_dir(),
                "path_ancestor_not_directory:" + str(path))
    return path


def at(value, pointer: list):
    require(type(pointer) is list, "binding_pointer_not_list")
    for key in pointer:
        if type(value) is dict:
            require(type(key) is str and key in value, "binding_field_absent:" + str(key))
        elif type(value) is list:
            require(type(key) is int and 0 <= key < len(value), "binding_index_absent")
        else:
            raise ValueError("binding_parent_null_or_not_container")
        value = value[key]
    return value


def packet(receipt: dict, selector: dict):
    require(set(selector) == {"stream", "prefix", "pointer"}, "binding_selector_fields_invalid")
    stream = selector["stream"]
    require(stream in {"stdout", "stderr"} and type(receipt[stream]) is str, "binding_stream_invalid")
    prefix = selector["prefix"]
    if prefix is None:
        payload = strict_json(receipt[stream])
    else:
        require(type(prefix) is str and prefix, "binding_prefix_invalid")
        matches = []
        for line in receipt[stream].splitlines():
            # Pytest progress dots may precede a genuine owner packet.
            match = re.fullmatch(r"[.FEspxXS]*" + re.escape(prefix) + r"(.*)", line)
            if match:
                matches.append(strict_json(match.group(1)))
        require(len(matches) == 1, "binding_packet_missing_or_duplicated:" + prefix)
        payload = matches[0]
    return at(payload, selector["pointer"])


def verify_binding(root: Path, expected: str, binding: dict) -> None:
    require(set(binding) == {"receipt", "receipt_sha256", "entry_module", "hash", "unchanged"},
            "execution_binding_fields_invalid")
    require(binding["receipt"].startswith(PREFIX), "binding_receipt_not_retained")
    path = relative(root, binding["receipt"])
    raw = path.read_bytes()
    require(sha(raw) == binding["receipt_sha256"], "execution_receipt_sha_mismatch")
    receipt = strict_json(raw)
    require(type(receipt) is dict and receipt["timed_out"] is False, "execution_receipt_incomplete")
    command = receipt["command"]
    require(type(command) is list and any(command[index:index + 2] == ["-m", binding["entry_module"]]
                                        for index in range(len(command))), "execution_entry_module_mismatch")
    measured = packet(receipt, binding["hash"])
    require(type(measured) is str and measured in {expected, "sha256:" + expected},
            "actual_executed_helper_hash_mismatch")
    require(packet(receipt, binding["unchanged"]) is True, "execution_source_unchanged_not_established")
    require(path.read_bytes() == raw, "execution_receipt_changed_during_read")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    name = args.manifest.relative_to(root).as_posix() if args.manifest.is_absolute() else args.manifest.as_posix()
    require(name.startswith(PREFIX), "manifest_not_under_retained_evidence")
    manifest_path = relative(root, name)
    manifest_raw = manifest_path.read_bytes()
    require(sha(manifest_raw) == args.manifest_sha256, "issued_manifest_sha_mismatch")
    manifest = strict_json(manifest_raw)
    require(type(manifest) is dict and set(manifest) == {"schema_version", "files"}
            and manifest["schema_version"] == "gy.j.harness_replay.v1", "unissued_manifest_shape")
    rows = manifest["files"]
    require(type(rows) is list and rows, "manifest_file_population_missing")
    planned, seen = [], set()
    for row in rows:
        require(type(row) is dict and set(row) == {"destination", "source", "sha256", "execution_bindings"},
                "manifest_row_fields_invalid")
        target = row["destination"]
        require(target in ALLOWED and target not in seen, "destination_unapproved_or_duplicated")
        seen.add(target)
        require(type(row["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is not None,
                "final_execution_sha_missing")
        require(row["source"].startswith(PREFIX) and row["source"].endswith(".py"), "source_not_retained_harness")
        source = relative(root, row["source"])
        raw = source.read_bytes()
        require(sha(raw) == row["sha256"], "retained_helper_bytes_differ")
        require(type(row["execution_bindings"]) is list and row["execution_bindings"],
                "actual_execution_binding_missing")
        for binding in row["execution_bindings"]:
            verify_binding(root, row["sha256"], binding)
        destination = relative(root, target)
        if destination.exists():
            require(destination.is_file() and destination.read_bytes() == raw, "existing_harness_differs:" + target)
        planned.append((source, destination, raw))
    # Validate the entire requested population before writing the first file.
    for source, destination, raw in planned:
        require(source.read_bytes() == raw, "retained_helper_changed_before_rehydration")
        if not args.check_only:
            destination.parent.mkdir(parents=True, exist_ok=True)
            relative(root, destination.relative_to(root).as_posix())
            try:
                with destination.open("xb") as stream:
                    stream.write(raw)
            except FileExistsError:
                require(not destination.is_symlink() and destination.is_file()
                        and destination.read_bytes() == raw, "existing_harness_differs:" + str(destination))
            require(destination.read_bytes() == raw, "rehydrated_helper_readback_mismatch")
    require(manifest_path.read_bytes() == manifest_raw, "issued_manifest_changed_during_rehydration")
    print(json.dumps({"mode": "checked" if args.check_only else "rehydrated", "manifest": name,
                      "manifest_sha256": sha(manifest_raw), "destinations": sorted(seen),
                      "gates_executed": False, "product_files_written": False,
                      "receipts_rewritten": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
