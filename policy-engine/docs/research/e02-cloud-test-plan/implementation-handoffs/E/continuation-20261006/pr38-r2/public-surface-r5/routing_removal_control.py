"Preserve canonical exports while removing the admitted facade routing."

import ast
import importlib.util
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


def _resolve_executable(name: str) -> str:
    (
        "Resolve an admitted executable and refus"  # Exact bound literal continuation.
        "e an unavailable program before invocati"  # Exact bound literal continuation.
        "on."  # Exact bound literal continuation.
    )
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact bound literal continuation.
        "y flush without logging side effects."  # Exact bound literal continuation.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


R = Path("/workspace/e02-E-continuation-20261006")
REF = "bf3b54c3a894d2d9d9bfb0cd13edb13177405f33"


def blob(path: object) -> object:
    return subprocess.check_output([_resolve_executable("git"), "show", REF + ":" + path], cwd=R)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit


guard_path = R / "policy-engine/tools/devx/architecture/guardrails.py"
if not (guard_path.read_bytes() == blob("policy-engine/tools/devx/architecture/guardrails.py")):
    raise AssertionError
spec = importlib.util.spec_from_file_location("e02_routing_negative_guard", guard_path)
guard = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = guard
spec.loader.exec_module(guard)
allowed = {}
for p in tomllib.loads(blob("policy-engine/architecture/public_surface/contract.toml").decode())[
    "package"
]:
    allowed.setdefault(guard._root_for_module(p["module"]), set()).update(
        p["supported_entrypoints"]
    )
from polisyos import (  # noqa: E402 - source-bound fixture
    calibration as cal,
)
from polisyos.foundry import (  # noqa: E402 - source-bound fixture
    uncertainty as uncertainty,
)
from polisyos.foundry.calibration.report import (  # noqa: E402 - source-bound fixture
    load_calibration_report,
)

if not (len(cal.__all__) == 29 and len(uncertainty.__all__) == 20):
    raise AssertionError
if not (
    cal.load_foundry_calibration_report
    is uncertainty.load_foundry_calibration_report
    is load_calibration_report
):
    raise AssertionError
path = "policy-engine/src/polisyos/calibration/__init__.py"
source = blob(path).decode()
mutant = source.replace(
    "from polisyos.foundry.uncertainty import load_foundry_calibration_report",
    (
        "from polisyos.foundry.calibration.report import load_calibra"
        "tion_report as load_foundry_calibration_report"
    ),
)
if not (mutant != source):
    raise AssertionError


def exports(text: str) -> object:
    return ast.literal_eval(
        next(
            n.value
            for n in ast.parse(text).body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets)
        )
    )


if not (exports(source) == exports(mutant)):
    raise AssertionError
edges = {}
for n in ast.walk(ast.parse(mutant)):
    if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
        guard._maybe_add_deep_import(
            edges=edges,
            allowed_entrypoints=allowed,
            source_module="polisyos.calibration",
            source_root="calibration",
            source_file=R / path,
            target_module=n.module,
        )
_write_stdout(
    json.dumps(
        {
            "control": (
                "AST property-removal of admitted routing; canonical exports/"
                "reader implementation unchanged, no source files edited"
            ),
            "exports": {"calibration": len(cal.__all__), "uncertainty": len(uncertainty.__all__)},
            "canonical_identity": True,
            "introduced_private_edges": list(edges),
            "source_sha": REF,
        }
    ),
    flush=True,
)
if edges:
    raise AssertionError(
        "names remain present but private cross-r"  # Exact bound literal continuation.
        "oot edge returns when admitted routing i"  # Exact bound literal continuation.
        "s removed"  # Exact bound literal continuation.
    )
