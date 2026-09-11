"""Behavioral regressions for the bounded production-invocation instrument."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _owner():
    # This stdlib-only owner is independent of the eager runtime quality facade.
    # The real registered command is also exercised in the lane integration gate.
    name = "_production_invocation_under_test"
    if name not in sys.modules:
        path = Path(__file__).resolve().parents[4] / (
            "src/polisyos/runtime/quality/production_invocation.py"
        )
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def _invoke(args, capsys):
    result = _owner().main(args)
    captured = capsys.readouterr()
    return subprocess.CompletedProcess(args, result, captured.out, captured.err)


def _write(repo: Path, files: dict[str, str]) -> None:
    for name, source in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def test_cli_reports_test_only_verifier_and_persists_negative(tmp_path, capsys):
    _git(tmp_path, "init", "-q")
    _write(tmp_path, {"src/pkg/seed.py": "# base\n"})
    _git(tmp_path, "add", ".")
    _git(
        tmp_path,
        "-c",
        "user.name=Invocation test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "base",
    )
    base = _git(tmp_path, "rev-parse", "HEAD")
    _write(
        tmp_path,
        {
            "src/pkg/check.py": "def verify(value):\n    return value != 'bad'\n",
            "tests/test_check.py": "from pkg.check import verify\nverify('bad')\n",
        },
    )
    _git(tmp_path, "add", ".")
    receipt = tmp_path / "receipt.json"
    result = _invoke(
        [
            "--repo-root",
            str(tmp_path),
            "--base",
            base,
            "--receipt",
            str(receipt),
        ],
        capsys,
    )
    assert receipt.exists(), result.stderr
    observed = json.loads(receipt.read_text())
    assert result.returncode == 1
    assert observed["regressions"] == ["pkg.check.verify"]
    assert observed["mechanisms"]["pkg.check.verify"]["status"] == "uninvoked"
    assert observed["mechanisms"]["pkg.check.verify"]["test_callers"]

    # Recompute through the canonical CLI main, then corrupt a deciding denominator.
    rerun = _invoke(
        [
            "--repo-root",
            str(tmp_path),
            "--base",
            base,
            "--receipt",
            str(receipt),
            "--check",
            str(receipt),
        ],
        capsys,
    )
    assert rerun.returncode == 1  # The unchanged orphan is still a negative.
    corrupt = tmp_path / "corrupt.json"
    observed["denominator"]["source_files"] += 1
    corrupt.write_text(json.dumps(observed))
    rejected = _invoke(
        [
            "--repo-root",
            str(tmp_path),
            "--base",
            base,
            "--receipt",
            str(receipt),
            "--check",
            str(corrupt),
        ],
        capsys,
    )
    assert rejected.returncode == 2
    assert json.loads(rejected.stdout)["reason"] == "invocation_receipt_drift"


def test_import_annotation_and_orphan_helper_do_not_supply_a_runnable_caller():
    files = {
        "src/pkg/owner.py": "def verify(value):\n    return bool(value)\n",
        "src/pkg/helper.py": (
            "from pkg.owner import verify as inspect\n"
            "def wrapper(value: inspect):\n    return inspect(value)\n"
        ),
        "tests/test_owner.py": "from pkg.helper import wrapper\nwrapper(False)\n",
    }
    result = _owner().audit_sources(files, {})
    assert set(result["regressions"]) == {"pkg.owner.verify", "pkg.helper.wrapper"}
    files["src/pkg/cli.py"] = (
        "from pkg.helper import wrapper as run\n"
        "def main():\n    return run(False)\n"
        "if __name__ == '__main__':\n    main()\n"
    )
    result = _owner().audit_sources(files, {})
    assert result["regressions"] == []
    assert result["mechanisms"]["pkg.owner.verify"]["status"] == "static_path"
    assert result["mechanisms"]["pkg.owner.verify"]["terminus"] == "pkg.cli:<entry>"


def test_class_construction_does_not_invoke_its_verification_method():
    files = {
        "src/pkg/owner.py": "class Verifier:\n    def verify(self):\n        return False\n",
        "src/pkg/cli.py": (
            "from pkg.owner import Verifier as V\n"
            "def main():\n    candidate = V()\n    return candidate\n"
            "if __name__ == '__main__':\n    main()\n"
        ),
    }
    result = _owner().audit_sources(files, {})
    assert result["regressions"] == ["pkg.owner.Verifier.verify"]
    files["src/pkg/cli.py"] = files["src/pkg/cli.py"].replace(
        "return candidate", "return candidate.verify()"
    )
    assert _owner().audit_sources(files, {})["regressions"] == []


def test_removing_a_call_from_a_previously_reached_mechanism_is_a_regression():
    before = {
        "src/pkg/owner.py": "def verify():\n    return False\n",
        "src/pkg/cli.py": (
            "from pkg.owner import verify\nif __name__ == '__main__':\n    verify()\n"
        ),
    }
    after = {**before, "src/pkg/cli.py": "from pkg.owner import verify\n"}
    result = _owner().audit_sources(after, before)
    assert result["regressions"] == ["pkg.owner.verify"]


def test_named_deferral_is_explicit_and_never_a_static_path():
    sources = {"src/pkg/owner.py": "def study():\n    return False\n"}
    decision = {"pkg.owner.study": {"task": "GY-CB2", "reason": "Real study intake absent"}}
    result = _owner().audit_sources(sources, {}, deferrals=decision)
    assert result["regressions"] == []
    assert result["mechanisms"]["pkg.owner.study"]["status"] == "deferred"
    assert result["mechanisms"]["pkg.owner.study"]["terminus"] is None


def test_parameter_shadowing_does_not_turn_an_import_into_a_production_call():
    sources = {
        "src/pkg/owner.py": "def verify():\n    return False\n",
        "src/pkg/cli.py": (
            "from pkg.owner import verify\n"
            "def main(verify):\n    return verify()\n"
            "if __name__ == '__main__':\n    main(lambda: True)\n"
        ),
    }
    assert "pkg.owner.verify" in _owner().audit_sources(sources, {})["regressions"]


def test_recursion_and_literal_false_entry_do_not_establish_invocation():
    sources = {
        "src/pkg/owner.py": "def verify():\n    return verify()\n",
        "src/pkg/cli.py": (
            "from pkg.owner import verify\n"
            "if __name__ == '__main__':\n    if False:\n        verify()\n"
        ),
    }
    assert _owner().audit_sources(sources, {})["regressions"] == ["pkg.owner.verify"]


def test_executable_script_registration_is_a_root_but_test_script_is_not():
    sources = {"src/pkg/owner.py": "def verify():\n    return False\n"}
    result = _owner().audit_sources(sources, {}, entry_points=["pkg.owner:verify"])
    assert result["regressions"] == []


def test_lexical_definitions_survive_entry_and_statement_containers():
    for source in (
        "if __name__ == '__main__':\n    def run():\n        return False\n    run()\n",
        "match 1:\n    case _:\n        def run():\n            return False\n"
        "if __name__ == '__main__':\n    run()\n",
    ):
        result = _owner().audit_sources({"src/pkg/cli.py": source}, {})
        assert result["regressions"] == []
        assert result["mechanisms"]["pkg.cli.run"]["status"] == "static_path"


def test_registration_receivers_are_uncertain_without_hiding_a_direct_orphan():
    sources = {
        "src/pkg/owner.py": (
            "from unknown_framework import router, Depends, registry, container\n"
            "from typing import Annotated\n"
            "def orphan():\n    return False\n"
            "def downstream():\n    return False\n"
            "def dependency():\n    return False\n"
            "def default_dependency():\n    return False\n"
            "def callback():\n    return False\n"
            "def installed_route():\n    return False\n"
            "class Receiver:\n    def consume(self):\n        return False\n"
            "class Service:\n    def inspect(self):\n        return False\n"
            "@router.get('/value')\n"
            "async def route(value: Annotated[str, Depends(dependency)], "
            "other=Depends(default_dependency)):\n    return downstream()\n"
            "router.add_api_route('/other', installed_route)\n"
            "receiver = Receiver()\n"
            "registry.any_opaque_name({'listeners': [callback, receiver.consume]})\n"
            "container.provide(Service)\n"
        ),
    }
    result = _owner().audit_sources(sources, {})
    uncertain = {
        "pkg.owner.route",
        "pkg.owner.installed_route",
        "pkg.owner.dependency",
        "pkg.owner.default_dependency",
        "pkg.owner.callback",
        "pkg.owner.Receiver.consume",
        "pkg.owner.Service.inspect",
        "pkg.owner.downstream",
    }
    assert {result["mechanisms"][name]["status"] for name in uncertain} == {
        "unresolved_by_construction"
    }
    assert set(result["unresolved_by_construction"]) == uncertain
    assert set(result["new_unresolved_by_construction"]) == uncertain
    assert result["regressions"] == ["pkg.owner.orphan"]
    assert result["mechanisms"]["pkg.owner.orphan"]["status"] == "uninvoked"
    assert result["runtime_invocation_established"] is False


def test_test_registration_and_plain_annotations_do_not_exempt_orphans():
    sources = {
        "src/pkg/owner.py": (
            "def verify():\n    return False\ndef wrapper(value: verify):\n    return False\n"
        ),
        "tests/test_owner.py": (
            "from pkg.owner import verify\nfrom framework import bus\nbus.subscribe(verify)\n"
        ),
    }
    result = _owner().audit_sources(sources, {})
    assert result["regressions"] == ["pkg.owner.verify", "pkg.owner.wrapper"]
    assert result["unresolved_by_construction"] == []


def test_removed_direct_call_cannot_be_replaced_by_callback_registration():
    before = {
        "src/pkg/owner.py": (
            "from unknown_framework import event_bus\n"
            "def verify():\n    return False\n"
            "event_bus.subscribe(verify)\n"
            "if __name__ == '__main__':\n    verify()\n"
        ),
    }
    after = {name: source.replace("    verify()", "    pass") for name, source in before.items()}
    original = _owner().audit_sources(before, {})
    assert original["mechanisms"]["pkg.owner.verify"]["status"] == "static_path"
    assert original["mechanisms"]["pkg.owner.verify"]["indirect_boundary_evidence"]
    result = _owner().audit_sources(after, before)
    assert result["mechanisms"]["pkg.owner.verify"]["status"] == "unresolved_by_construction"
    assert result["mechanisms"]["pkg.owner.verify"]["lost_path"] is True
    assert result["new_unresolved_by_construction"] == ["pkg.owner.verify"]
    assert result["regressions"] == []


def test_dynamic_receiver_site_is_unmeasured_without_inventing_its_target():
    sources = {
        "src/pkg/owner.py": (
            "from unknown_framework import router\n"
            "@router.get('/value')\n"
            "def route(request):\n    return request.container.service.verify()\n"
        ),
    }
    result = _owner().audit_sources(sources, {})
    assert result["mechanisms"]["pkg.owner.route"]["status"] == "unresolved_by_construction"
    assert result["unresolved_receiver_calls"] == [
        {
            "path": "src/pkg/owner.py",
            "line": 4,
            "column": 11,
            "scope": "pkg.owner.route",
            "expression": "request.container.service.verify",
            "reason": "receiver_identity_not_resolved",
            "target": None,
        }
    ]


def test_cli_discloses_partial_coverage_and_unrun(tmp_path, capsys):
    _git(tmp_path, "init", "-q")
    _write(tmp_path, {"src/pkg/owner.py": "# base\n"})
    _git(tmp_path, "add", ".")
    _git(
        tmp_path,
        "-c",
        "user.name=Invocation test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "base",
    )
    base = _git(tmp_path, "rev-parse", "HEAD")
    receipt = tmp_path / "receipt.json"
    args = ["--repo-root", str(tmp_path), "--base", base, "--receipt", str(receipt)]
    clean = _invoke(args, capsys)
    assert clean.returncode == 0, clean.stdout
    observed = json.loads(receipt.read_text())
    output = json.loads(clean.stdout)
    assert output["coverage"] == observed["coverage"] == "partial"
    assert output["unmeasured"] == observed["unmeasured"]
    assert set(output["unmeasured"]) >= {
        "HTTP router dispatch",
        "dependency injection/container dispatch",
        "event-bus dispatch",
        "registered callback invocation",
        "reflection and dynamic receiver/factory resolution",
    }
    assert "Unmeasured:" in output["summary"]

    _write(
        tmp_path,
        {
            "src/pkg/owner.py": (
                "from unknown_framework import router\n"
                "@router.get('/value')\nasync def receive():\n    return False\n"
            )
        },
    )
    uncertain = _invoke(args, capsys)
    assert uncertain.returncode == 3, uncertain.stdout
    assert json.loads(uncertain.stdout)["new_unresolved_by_construction"] == ["pkg.owner.receive"]
    assert json.loads(receipt.read_text())["mechanisms"]["pkg.owner.receive"]["status"] == (
        "unresolved_by_construction"
    )

    _write(tmp_path, {"src/pkg/orphan.py": "def verify():\n    return False\n"})
    _git(tmp_path, "add", "src")
    mixed = _invoke(args, capsys)
    assert mixed.returncode == 1, mixed.stdout
    assert json.loads(mixed.stdout)["regressions"] == ["pkg.orphan.verify"]
    assert json.loads(mixed.stdout)["new_unresolved_by_construction"] == ["pkg.owner.receive"]

    corrupt = tmp_path / "corrupt.json"
    damaged = json.loads(receipt.read_text())
    damaged["denominator"]["source_files"] += 1
    corrupt.write_text(json.dumps(damaged))
    drift = _invoke([*args, "--check", str(corrupt)], capsys)
    assert drift.returncode == 2, drift.stdout
    assert json.loads(drift.stdout)["reason"] == "invocation_receipt_drift"

    _write(tmp_path, {"src/pkg/owner.py": "def malformed(:\n"})
    unrun = _invoke(args, capsys)
    assert unrun.returncode == 2, unrun.stdout
    incomplete = json.loads(unrun.stdout)
    assert incomplete["status"] == "UNRUN"
    assert incomplete["complete_verdict"] is False
    assert incomplete["unmeasured"] == observed["unmeasured"]
    assert "Traceback" not in unrun.stdout


def test_unified_cli_discovers_the_production_invocation_command():
    from tools.registry import get_spec

    spec = get_spec("validation", "check-production-invocation")
    assert spec.module == "tools.quality.validation.check_production_invocation"
    assert spec.callable_name == "main"


def test_deferred_expression_bodies_do_not_supply_direct_invocation_paths():
    for deferred in ("lambda: verify()", "(verify() for item in [1])"):
        sources = {
            "src/pkg/owner.py": (
                "from unknown_framework import event_bus\n"
                "def verify():\n    return False\n"
                "if __name__ == '__main__':\n"
                f"    event_bus.register({deferred})\n"
            )
        }
        result = _owner().audit_sources(sources, {})
        assert result["mechanisms"]["pkg.owner.verify"]["status"] == (
            "unresolved_by_construction"
        ), deferred
        assert result["new_unresolved_by_construction"] == ["pkg.owner.verify"]
        assert result["indirect_boundaries"]


def test_deferred_function_bodies_stop_direct_paths_with_lexical_yield_detection():
    for declaration in (
        "def deferred():\n    yield verify()\n",
        "async def deferred():\n    return verify()\n",
    ):
        sources = {
            "src/pkg/owner.py": (
                "def verify():\n    return False\n"
                + declaration
                + "if __name__ == '__main__':\n    deferred()\n"
            )
        }
        result = _owner().audit_sources(sources, {})
        assert result["mechanisms"]["pkg.owner.verify"]["status"] == (
            "unresolved_by_construction"
        ), declaration
        assert result["mechanisms"]["pkg.owner.deferred"]["status"] == (
            "unresolved_by_construction"
        )
    normal = {
        "src/pkg/owner.py": (
            "def verify():\n    return False\n"
            "def normal():\n    def nested():\n        yield 1\n    return verify()\n"
            "if __name__ == '__main__':\n    normal()\n"
        )
    }
    assert _owner().audit_sources(normal, {})["mechanisms"]["pkg.owner.verify"]["status"] == (
        "static_path"
    )
