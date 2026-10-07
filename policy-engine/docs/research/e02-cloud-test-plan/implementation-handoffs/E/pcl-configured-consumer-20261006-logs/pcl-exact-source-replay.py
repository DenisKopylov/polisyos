(
    "Replay focused assertions with exact his"  # Exact value.
    "torical module bytes, no checkout mutati"  # Exact value.
    "on."  # Exact value.
)

import hashlib
import importlib.abc
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_executable(name: str) -> str:
    (
        "Resolve an admitted executable and refus"  # Exact value.
        "e an unavailable program before invocati"  # Exact value.
        "on."  # Exact value.
    )
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact value.
        "y flush without logging side effects."  # Exact value.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


SOURCE = "58e2d97965c0826c44843a78dcb2f8698d9950a3"
PATHS = {
    (
        "polisyos.foundry.methods.backends.numpy_"  # Exact value.
        "runner"  # Exact value.
    ): (
        "policy-engine/src/polisyos/foundry/metho"  # Exact value.
        "ds/backends/numpy_runner.py"  # Exact value.
    ),
    "polisyos.foundry.methods.catalog.econometrics.advanced": (
        "policy-engine/src/polisyos/foundry/metho"  # Exact value.
        "ds/catalog/econometrics/advanced.py"  # Exact value.
    ),
    (
        "polisyos.foundry.execute._internal.graph"  # Exact value.
    ): (
        "policy-engine/src/polisyos/foundry/execu"  # Exact value.
        "te/_internal/graph/__init__.py"  # Exact value.
    ),
}
SOURCES = {
    module: subprocess.check_output(  # noqa: S603 - admitted Git argv
        [
            _resolve_executable("git"),
            "show",
            (
                f"{SOURCE}"  # Exact value.
                ":"  # Exact value.
                f"{path}"  # Exact value.
            ),
        ]
    )
    for module, path in PATHS.items()
}
_write_stdout(
    json.dumps(
        {
            "source": SOURCE,
            "mode": "exact_git_blob_import_overlay",
            "modules": {
                module: {
                    "path": PATHS[module],
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
                for module, data in SOURCES.items()
            },
        }
    ),
    flush=True,
)


class BlobLoader(importlib.abc.Loader):
    def create_module(self, spec: object) -> None:
        return None

    def exec_module(self, module: object) -> None:
        module.__file__ = f"git:{SOURCE}:{PATHS[module.__name__]}"
        if module.__name__.endswith(".graph"):
            module.__path__ = []
        exec(compile(SOURCES[module.__name__], module.__file__, "exec"), module.__dict__)  # noqa: S102 - isolated removal control executes exact Git/AST fixture, never external input


class BlobFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: object, path: object = None, target: object = None) -> object:
        if fullname in SOURCES:
            return importlib.util.spec_from_loader(
                fullname, BlobLoader(), is_package=fullname.endswith(".graph")
            )
        return None


sys.meta_path.insert(0, BlobFinder())
import pytest  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer

raise SystemExit(pytest.main(sys.argv[1:]))
