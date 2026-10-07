import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_executable(name: str) -> str:
    "Resolve an admitted executable and refuse an unavailable program before invocation."
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


observed_o = Path(__file__).parent
R = Path("/workspace/e02-E-continuation-20261006")
F = observed_o / "fixture-current"
ref = "8486baad6fdef8063cfaad80b15f6b6d8532460a"
paths = [
    "policy-engine/src/polisyos/calibration/__init__.py",
    "policy-engine/src/polisyos/calibration/forecast_bridge.py",
    ("policy-engine/src/polisyos/scientist/methods/backtesting/forecast_owner.py"),
]
rows = []
for p in paths:
    b = subprocess.check_output([_resolve_executable("git"), "show", ref + ":" + p], cwd=R)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    old = (F / p).read_bytes()
    (F / p).write_bytes(b)
    rows.append(
        {
            "path": p,
            "overlay_source_sha": ref,
            "before_sha256": hashlib.sha256(old).hexdigest(),
            "after_sha256": hashlib.sha256(b).hexdigest(),
            "bytes": len(b),
        }
    )
p = "policy-engine/architecture/production_quality/method_catalog_dependency_digest_domains.toml"
refbase = "31059ec77f9add8651667967a4b1a51acfab6d24"
b = subprocess.check_output([_resolve_executable("git"), "show", refbase + ":" + p], cwd=R)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
(F / p).parent.mkdir(parents=True, exist_ok=True)
(F / p).write_bytes(b)
rows.append(
    {
        "path": p,
        "overlay_source_sha": refbase,
        "sha256": hashlib.sha256(b).hexdigest(),
        "bytes": len(b),
        "reason": "native execution producer imports tracked method digest registry",
    }
)
(observed_o / "future-fixture-inputs.json").write_text(
    json.dumps(
        {
            "is_git_candidate": False,
            "fixture_base_sha": refbase,
            "overlay_rows": rows,
            "source_history_not_modified": True,
        },
        indent=2,
    )
    + "\n"
)
_write_stdout(json.dumps(rows, indent=2))
