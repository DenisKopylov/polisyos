"""Run one read-only measurement, retaining complete output and its actual exit."""

import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stream", choices=["open", "blocked-ac", "blocked-b", "final"])
    parser.add_argument("label")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    directory = Path(__file__).parent / args.stream
    raw = directory / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    output = raw / (args.label + ".txt")
    if output.exists():
        raise RuntimeError("output label already exists; preserve it and choose a new replay label")
    with output.open("wb") as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
    receipt = {"command": shlex.join(command), "cwd": str(Path.cwd()),
               "exit_code": result.returncode, "seconds": round(time.monotonic()-started, 3),
               "complete_output": str(output.relative_to(Path.cwd())),
               "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
    index = directory / "receipts.json"
    with (raw / "receipt-index.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        receipts = json.loads(index.read_text()) if index.exists() else {}
        if args.label in receipts:
            raise RuntimeError("receipt label already exists; choose a new replay label")
        receipts[args.label] = receipt
        index.write_text(json.dumps(receipts, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
