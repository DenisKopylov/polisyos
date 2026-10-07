"""Move the enumerated repeatable C3 environments to native macOS Trash."""

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
RAW = ROOT / ".tmp/e02-C3/raw"
OUT = RAW / "cleanup"
PLAN1 = RAW / "cleanup-plan/final-eligibility-v2.json"
PLAN2 = RAW / "cleanup-plan/final-env-node-modules-v3.json"
NATIVE = OUT / "trash-exact"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def command(argv):
    started = time.monotonic()
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=60)
    return {"argv": argv, "cwd": str(ROOT), "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr,
            "wall_seconds": round(time.monotonic() - started, 4)}


def candidates():
    first = json.loads(PLAN1.read_text())
    second = json.loads(PLAN2.read_text())
    rows = [{"kind": x["kind"], "path": x["path"], "identity": x["lstat"],
             "basis": str(PLAN1.relative_to(ROOT)), "group": x["group"]}
            for x in first["candidates"]]
    for x in second["report_checkout_node_modules_candidates"]:
        rows.append({"kind": "repeatable_node_modules", "path": x["path"],
                     "identity": x, "basis": str(PLAN2.relative_to(ROOT))})
    env = second["root_fresh_venv"]
    rows.append({"kind": "fresh_root_test_environment", "path": env["path"],
                 "identity": env, "basis": str(PLAN2.relative_to(ROOT))})
    for x in second["derived_tmp_json_candidates"]:
        rows.append({"kind": "derived_tracked_json_copy", "path": x["path"],
                     "identity": x["current_lstat_only"],
                     "expected_sha256": x["prior_content_sha256"],
                     "basis": str(PLAN2.relative_to(ROOT))})
    resolved = [str(Path(x["path"]).resolve()) for x in rows]
    if len(resolved) != len(set(resolved)):
        raise RuntimeError("duplicate cleanup candidate")
    for a in resolved:
        for b in resolved:
            if a != b and a.startswith(b + "/"):
                raise RuntimeError("overlapping cleanup candidates")
    return rows


def check(row):
    path = Path(row["path"])
    observed = path.lstat()
    old = row["identity"]
    if stat.S_ISLNK(observed.st_mode):
        raise RuntimeError(f"symlink candidate: {path}")
    if (observed.st_dev, observed.st_ino) != (old["device"], old["inode"]):
        raise RuntimeError(f"candidate identity changed: {path}")
    if not (stat.S_ISDIR(observed.st_mode) or stat.S_ISREG(observed.st_mode)):
        raise RuntimeError(f"unsupported candidate type: {path}")
    if "production_data" in path.parts:
        raise RuntimeError(f"production candidate rejected: {path}")
    argv = ["/usr/sbin/lsof", "-nP", "-Fpc"]
    argv += ["+D", str(path)] if path.is_dir() else ["--", str(path)]
    opened = command(argv)
    if opened["exit_code"] != 1 or opened["stdout"] or opened["stderr"]:
        raise RuntimeError(f"candidate has open handles or inconclusive lsof: {path}: {opened}")
    result = {"path": str(path), "device": observed.st_dev, "inode": observed.st_ino,
              "type": "directory" if path.is_dir() else "regular_file",
              "lsof": opened, "checked_at_utc": dt.datetime.now(dt.UTC).isoformat()}
    if "expected_sha256" in row:
        actual = digest(path)
        if actual != row["expected_sha256"]:
            raise RuntimeError(f"derived copy no longer matches preserved tracked input: {path}")
        result["sha256"] = actual
    return result


def main():
    if sys.argv[1:] not in (["prepare"], ["execute"]):
        raise RuntimeError("use prepare or execute")
    action = sys.argv[1]
    rows = candidates()
    receipt = {"schema": "policyos.e02.c3.native-trash.v1", "action": action,
               "captured_at_utc": dt.datetime.now(dt.UTC).isoformat(),
               "plan_refs": [{"path": str(p.relative_to(ROOT)), "sha256": digest(p)}
                             for p in (PLAN1, PLAN2)],
               "source": {"path": str(Path(__file__).relative_to(ROOT)),
                          "sha256": digest(Path(__file__))},
               "native_source_sha256": digest(OUT / "TrashExact.swift"),
               "native_binary_sha256": digest(NATIVE),
               "space_before": command(["/bin/df", "-k", str(ROOT)]),
               "candidates": rows, "records": [],
               "preservation": "Production data, useful tracked code/docs/refs, shared caches, wheels/sdists, CAS fixtures, probes and complete deciding outputs stay in place; native Trash is not emptied. No immediate free-space claim."}
    destination = OUT / ("final-preflight.json" if action == "prepare" else "final-native-trash.json")
    if destination.exists():
        raise RuntimeError(f"receipt already exists; append-only stop: {destination}")
    try:
        for row in rows:
            checked = check(row)
            record = {"kind": row["kind"], "preflight": checked}
            receipt["records"].append(record)
            if action == "execute":
                call = command([str(NATIVE), row["path"], str(checked["device"]), str(checked["inode"])])
                record["native_command"] = call
                if call["exit_code"] != 0:
                    raise RuntimeError(f"native Trash failed: {row['path']}")
                native = json.loads(call["stdout"])
                target = Path(native["destination"])
                after = target.lstat()
                if (after.st_dev, after.st_ino) != (checked["device"], checked["inode"]):
                    raise RuntimeError("readback destination identity mismatch")
                if os.path.lexists(row["path"]):
                    raise RuntimeError("readback source still exists")
                record["readback"] = {"destination": str(target), "source_absent": True,
                                      "same_device_inode": True, "device": after.st_dev, "inode": after.st_ino}
            destination.write_text(json.dumps(receipt, indent=2) + "\n")
        receipt["space_after"] = command(["/bin/df", "-k", str(ROOT)])
        receipt["completed_count"] = len(receipt["records"])
        receipt["result"] = "preflight_complete" if action == "prepare" else "native_trash_complete"
    except Exception as error:
        receipt["result"] = "stopped"
        receipt["error"] = str(error)
        raise
    finally:
        destination.write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps({"path": str(destination), "sha256": digest(destination),
                          "result": receipt.get("result"), "records": len(receipt["records"])}))


if __name__ == "__main__":
    main()
