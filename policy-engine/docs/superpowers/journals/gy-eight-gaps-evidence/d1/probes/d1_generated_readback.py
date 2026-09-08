"""Read back the complete explicit generated-client command output set."""
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    receipts = ["client-types-generation", "client-generation", "client-canonicalization", "dashboard-types-generation"]
    outputs = set()
    for name in receipts:
        packet = json.loads(Path(f"_build/gy-gaps/d1/root/{name}.json").read_text())
        assert packet["returncode"] == 0 and not packet["timed_out"]
        args = packet["command"]
        for flag in ("--output", "--out-ts", "--out-js"):
            if flag in args:
                target = Path(args[args.index(flag) + 1])
                if "--dir" in args:
                    target = Path(args[args.index("--dir") + 1]) / target
                outputs.add(target.resolve().relative_to(Path.cwd()).as_posix())
    expected = {"packages/runtime-api-client/types.ts", "packages/runtime-api-client/runtimeApiClient.ts",
                "packages/runtime-api-client/runtimeApiClient.js", "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
                "packages/runtime-api-client/canonicalRuntimeApiClient.js", "apps/runtime-dashboard/src/api/types.ts"}
    assert outputs == expected
    rows = []
    changed = set()
    for path in sorted(outputs):
        old = subprocess.check_output(["git", "show", f"HEAD:policy-engine/{path}"])
        new = Path(path).read_bytes()
        if old != new:
            changed.add(path)
        rows.append({"path": path, "before": hashlib.sha256(old).hexdigest(),
                     "after": hashlib.sha256(new).hexdigest(), "unchanged": old == new})
    diff = set(subprocess.check_output(["git", "diff", "--name-only", "--relative", "HEAD", "--", *sorted(outputs)], text=True).splitlines())
    assert changed == diff
    print(json.dumps({"denominator": {"type": "generated files emitted by the complete four generating commands",
                                      "command_outputs": len(outputs), "independent_declared_outputs": len(expected)},
                      "unreadable": [], "readback": rows, "changed_by_bytes": sorted(changed),
                      "changed_by_git": sorted(diff)}, indent=2))


if __name__ == "__main__":
    main()
