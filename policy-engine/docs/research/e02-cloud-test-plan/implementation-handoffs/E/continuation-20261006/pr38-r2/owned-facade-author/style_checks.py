import json
import subprocess
import sys
from pathlib import Path


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


OUT = Path(__file__).parent
POST = OUT / "postimage"
PRODUCT = Path("/workspace/e02-E-continuation-20261006/policy-engine")
PY = PRODUCT / ".venv/bin/python"
paths = list(POST.rglob("*.py"))
results = []
for path in sorted(paths):
    relative = str(path.relative_to(POST / "policy-engine"))
    for mode, args in [("lint", ["check", "--no-cache"]), ("format", ["format", "--check"])]:
        argv = [str(PY), "-m", "ruff", *args, "--stdin-filename", relative, "-"]
        run = subprocess.run(argv, input=path.read_bytes(), cwd=PRODUCT, capture_output=True)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        label = relative.replace("/", "_") + "-" + mode
        (OUT / ("style-" + label + ".stdout")).write_bytes(run.stdout)
        (OUT / ("style-" + label + ".stderr")).write_bytes(run.stderr)
        results.append(
            {
                "path": relative,
                "mode": mode,
                "argv": argv,
                "cwd": str(PRODUCT),
                "exit_code": run.returncode,
                "stdout": run.stdout.decode(),
                "stderr": run.stderr.decode(),
            }
        )
(OUT / "style-receipt.json").write_text(json.dumps(results, indent=2) + "\n")
_write_stdout(
    json.dumps(
        {
            "files": len(paths),
            "checks": len(results),
            "failed": [r for r in results if r["exit_code"]],
        },
        indent=2,
    )
)
raise SystemExit(bool(any(r["exit_code"] for r in results)))
