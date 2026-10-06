"""Plan or execute canonical workspace constituents with only six caps omitted.

Planning reads immutable Git source and constructs CommandSpec metadata; it runs
no gate. Execution is opt-in, checks the actual frozen HEAD, and retains every
constituent's argv/cwd and non-numerical environment. Nested ci-parity verify is
expanded instead of launching a fresh capped verify child. No canonical file is
modified, and no assertion, test selector, doctor or docs gate is removed.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import textwrap
import types
from dataclasses import dataclass
from pathlib import Path

CONFIG_SOURCE = "933a0ef4f548eaa7e3c0f1c6324a0d4fe4729022"
CAPS = {
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
}


@dataclass(frozen=True)
class CommandSpec:
    label: str
    argv: tuple[str, ...]
    cwd: Path
    env: dict[str, str] | None = None


def git(root: Path, *args: str) -> bytes:
    # The arguments below identify local immutable Git objects or HEAD only.
    return subprocess.check_output(["/usr/bin/git", *args], cwd=root)  # noqa: S603


def factories(root: Path, product: Path, uv: str, filename: str) -> dict:
    """Evaluate only canonical metadata factory definitions, not imported tool code."""
    rel = "policy-engine/tools/devx/workspace/" + filename
    raw = git(root, "show", CONFIG_SOURCE + ":" + rel)
    if (root / rel).read_bytes() != raw:
        raise RuntimeError("canonical factory changed; re-audit " + rel)
    tree = ast.parse(raw, filename=rel)
    # Module imports and its __main__ dispatch are not evaluated. Metadata
    # main below is observed with run_command intercepted, so no gate executes.
    selected = [
        node for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign, ast.FunctionDef))
    ]
    namespace = {
        "__name__": "gate_metadata",
        "CommandSpec": CommandSpec,
        "PRODUCT_ROOT": product,
        "FRONTEND_ROOT": product / "apps/runtime-dashboard",
        "sys": types.SimpleNamespace(executable=sys.executable),
        "os": os,
        "textwrap": textwrap,
        "argparse": argparse,
        "uv_command": lambda: (uv,),
    }
    # Only the pinned, byte-checked local canonical metadata definitions run;
    # every run_command callback is replaced before main is observed.
    exec(compile(ast.Module(body=selected, type_ignores=[]), rel, "exec"), namespace)  # noqa: S102
    return namespace


def require_canonical_uv_binding(root: Path, uv: str) -> str:
    """Bind the first valid canonical PATH candidate, without provisioning it."""
    rel = "policy-engine/tools/devx/workspace/_common.py"
    if (root / rel).read_bytes() != git(root, "show", CONFIG_SOURCE + ":" + rel):
        raise RuntimeError("canonical resolver changed; re-audit " + rel)
    if shutil.which("uv") != uv:
        raise RuntimeError("--uv must match the canonical first PATH candidate")
    # _common.baseline_uv_binary accepts the first PATH candidate at 0.9.21.
    version = subprocess.check_output([uv, "--version"], cwd=root, text=True).strip()  # noqa: S603
    if version != "uv 0.9.21":
        raise RuntimeError("first PATH uv candidate must report pinned uv 0.9.21")
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-root", type=Path, required=True)
    parser.add_argument("--uv", required=True)
    parser.add_argument("--suite", choices=["verify", "ci-parity"], required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--expected-source")
    args, flags = parser.parse_known_args()
    if flags[:1] == ["--"]:
        flags = flags[1:]
    product = args.product_root.absolute()
    root = product.parent
    uv_version = require_canonical_uv_binding(root, args.uv)
    verify = factories(root, product, args.uv, "verify.py")
    parity = factories(root, product, args.uv, "ci_parity.py")
    modules = {"verify": verify, "ci-parity": parity}

    def plan(suite: str, original_flags: list[str]) -> list[CommandSpec]:
        module = modules[suite]
        result = []
        module["run_command"] = result.append
        # Suppress the canonical CLI success prose: only metadata was observed,
        # and exit 0 here cannot establish any constituent gate result.
        module["print"] = lambda *values, **kwargs: None
        module["main"](original_flags)
        return result

    original = plan(args.suite, flags)
    expanded = []
    for spec in original:
        if "tools.devx.workspace.verify" in spec.argv:
            index = spec.argv.index("tools.devx.workspace.verify")
            expanded.extend(plan("verify", list(spec.argv[index + 1 :])))
        else:
            expanded.append(spec)
    current = git(root, "rev-parse", "HEAD").decode().strip()
    # Array traversal covers the full chosen canonical factory result, not a
    # sampled grep. Ambient removed vars are names only: never emit other values.
    output = {
        "schema": "policyos.e02.uncapped_gate_plan.v1",
        "config_source_sha": CONFIG_SOURCE,
        "target_source_sha": current,
        "target_tree": git(root, "rev-parse", "HEAD^{tree}").decode().strip(),
        "canonical_uv_binding": {"path": args.uv, "version": uv_version},
        "suite": args.suite,
        "canonical_flags": flags,
        "execute": args.execute,
        "factory_paths": [
            "policy-engine/tools/devx/workspace/verify.py@" + CONFIG_SOURCE,
            "policy-engine/tools/devx/workspace/ci_parity.py@" + CONFIG_SOURCE,
            "policy-engine/tools/devx/workspace/_common.py@" + CONFIG_SOURCE,
        ],
        "original_top_level_commands": len(original),
        "expanded_commands": len(expanded),
        "sole_environment_delta": {
            "omit": sorted(CAPS),
            "ambient_names_present": sorted(CAPS & os.environ.keys()),
        },
        "numerical_cap_option_exists": False,
        "commands": [
            {
                "index": i,
                "label": s.label,
                "argv": list(s.argv),
                "cwd": str(s.cwd),
                "canonical_environment_overlay": s.env or {},
                "uncapped_environment_overlay": {
                    k: v for k, v in (s.env or {}).items() if k not in CAPS
                },
            }
            for i, s in enumerate(expanded)
        ],
    }
    sys.stdout.write(json.dumps(output, indent=2) + "\n")
    sys.stdout.flush()
    if not args.execute:
        return 0
    if args.expected_source is None or current != args.expected_source:
        raise RuntimeError("execute requires exact current --expected-source")
    for spec in expanded:
        env = dict(os.environ)
        env.update(spec.env or {})
        for name in CAPS:
            env.pop(name, None)
        sys.stdout.write("[uncapped constituent] " + spec.label + "\n")
        sys.stdout.flush()
        # This explicit opt-in uses the full canonical argv after HEAD binding.
        subprocess.run(list(spec.argv), cwd=spec.cwd, env=env, check=True)  # noqa: S603
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
