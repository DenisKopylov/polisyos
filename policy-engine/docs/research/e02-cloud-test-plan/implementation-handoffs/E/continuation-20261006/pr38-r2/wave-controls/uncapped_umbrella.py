"""Keep canonical umbrella steps, uncapped numerical threads, and exact fail-fast receipts."""

from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--gate", choices=("verify", "ci-parity"), required=True)
    parser.add_argument("--stages-output", type=Path, required=True)
    parser.add_argument("--temp-root", type=Path, required=True)
    args, gate_args = parser.parse_known_args()
    if args.stages_output.exists() or args.temp_root.exists():
        raise RuntimeError("refuse overwrite/reused pytest scratch")
    args.temp_root.mkdir(parents=True)
    sys.path.insert(0, str(args.repo / "policy-engine"))
    from tools.devx.workspace import ci_parity, verify
    from tools.devx.workspace._common import CommandSpec, run_command as canonical_run

    verify.PYTEST_NUMERICAL_ENV = {}
    scopes: list[dict[str, object]] = []
    active_scopes: list[dict[str, object]] = []
    invocation = 0

    def plan(gate: str, argv: list[str]) -> list[CommandSpec]:
        module = verify if gate == "verify" else ci_parity
        parsed = module._build_parser().parse_args(argv)
        commands = []
        if not parsed.skip_doctor:
            commands.append(
                CommandSpec(
                    label="doctor",
                    argv=module._doctor_command(parsed.surface),
                    cwd=module.PRODUCT_ROOT,
                )
            )
        if not parsed.frontend_only:
            if gate == "verify":
                commands.extend(
                    verify._backend_commands(
                        pytest_workers=verify._resolve_pytest_workers(
                            parsed.pytest_workers
                        ),
                        pytest_dist=verify._resolve_pytest_dist(),
                    )
                )
            else:
                commands.extend(
                    ci_parity._backend_commands(
                        skip_runtime_http=parsed.skip_runtime_http,
                        skip_docs=parsed.skip_docs,
                    )
                )
        if not parsed.backend_only:
            if gate == "verify":
                commands.extend(verify._frontend_commands())
            else:
                commands.extend(
                    ci_parity._frontend_commands(
                        skip_browser=parsed.skip_browser,
                        include_e2e_smoke=parsed.include_e2e_smoke,
                        include_visual=parsed.include_visual,
                    )
                )
        return commands

    def recorded_run(spec: CommandSpec) -> None:
        nonlocal invocation
        scope = active_scopes[-1]
        row = next(item for item in scope["steps"] if item["outcome"] == "UNRUN")
        if row["label"] != spec.label:
            raise RuntimeError("canonical planned/executed umbrella step order drift")
        invocation += 1
        argv = list(spec.argv)
        if (
            len(argv) > 1
            and Path(argv[0]).name == "uv"
            and argv[1] == "run"
            and "--no-sync" not in argv
        ):
            argv.insert(2, "--no-sync")
        if "pytest" in argv:
            temporary = args.temp_root / (str(invocation) + "-pytest")
            if temporary.exists():
                raise RuntimeError(
                    "pytest basetemp already exists; do not delete evidence"
                )
            argv.extend(["--basetemp", str(temporary), "-p", "no:cacheprovider"])
        row.update(
            command=argv,
            cwd=str(spec.cwd),
            env=dict(spec.env or {}),
            started_unix=time.time(),
        )
        try:
            if "tools.devx.workspace.verify" in argv:
                child_args = argv[argv.index("tools.devx.workspace.verify") + 1 :]
                code = run_scope("verify", child_args)
                if code:
                    raise subprocess.CalledProcessError(code, argv)
            else:
                canonical_run(dataclasses.replace(spec, argv=tuple(argv)))
        except BaseException as exc:
            row.update(
                outcome="FAIL",
                error_type=type(exc).__name__,
                reason=str(exc),
                exit_code=getattr(exc, "returncode", 1),
            )
            raise
        else:
            row.update(outcome="PASS", exit_code=0)
        finally:
            row["wall_seconds"] = time.time() - row["started_unix"]

    def run_scope(gate: str, argv: list[str]) -> int:
        commands = plan(gate, argv)
        scope = {
            "gate": gate,
            "argv": argv,
            "steps": [
                {
                    "label": item.label,
                    "command": list(item.argv),
                    "cwd": str(item.cwd),
                    "outcome": "UNRUN",
                }
                for item in commands
            ],
        }
        scopes.append(scope)
        active_scopes.append(scope)
        try:
            for command in commands:
                recorded_run(command)
        except subprocess.CalledProcessError as exc:
            return exc.returncode
        finally:
            active_scopes.pop()
        return 0

    # Match canonical factory ordering rather than bypassing failed umbrella steps.
    verify.run_command = recorded_run
    ci_parity.run_command = recorded_run
    code = 1
    try:
        code = run_scope(args.gate, gate_args)
        return code
    finally:
        for scope in scopes:
            failed = next(
                (row["label"] for row in scope["steps"] if row["outcome"] == "FAIL"),
                None,
            )
            for row in scope["steps"]:
                if row["outcome"] == "UNRUN":
                    row["reason"] = (
                        "actual fail-fast after " + str(failed)
                        if failed
                        else "scope aborted before step"
                    )
        args.stages_output.parent.mkdir(parents=True, exist_ok=True)
        args.stages_output.write_text(
            json.dumps(
                {
                    "schema": "policyos.e02.umbrella_stages.v1",
                    "gate": args.gate,
                    "exit_code": code,
                    "numerical_thread_caps": None,
                    "scopes": scopes,
                    "required_steps_preserved": True,
                    "doctor_is_full_ci": False,
                    "finding_closure": False,
                },
                indent=2,
            )
            + "\n"
        )


if __name__ == "__main__":
    raise SystemExit(main())
