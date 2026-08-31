from __future__ import annotations

import ast
import subprocess
from datetime import UTC, datetime
from pathlib import Path

_MECHANISMS = frozenset(
    {
        "apps/runtime-dashboard/src/features/clerk/components/ControlFailurePanel.tsx",
        "src/polisyos/core/contracts/control.py",
        "src/polisyos/runtime/http/openapi_contract.py",
        "src/polisyos/runtime/http/routes/runs.py",
        "src/polisyos/runtime/http/services/control/nl_pipeline.py",
        "src/polisyos/runtime/http/services/control/response_shapes.py",
        "src/polisyos/runtime/http/services/control/run_lifecycle.py",
        "src/polisyos/runtime/http/services/control_plane_store.py",
        "src/polisyos/runtime/quality/__init__.py",
        "src/polisyos/runtime/quality/approval.py",
        "src/polisyos/runtime/quality/external_client_surface.py",
        "src/polisyos/runtime/quality/schema_compat.py",
        "src/polisyos/runtime/quality/status_deficits.py",
        "src/polisyos/runtime/quality/tenant_cas_approval_governance.py",
        "src/polisyos/scientist/artifacts/decision_compiler.py",
        "src/polisyos/scientist/validation/decision_artifact_quality.py",
        "tools/ops_runners/runtime/canary_evidence.py",
        "tools/ops_runners/runtime/replay_canary_bundle.py",
    }
)
_RETAINED = frozenset(
    {
        "src/polisyos/runtime/http/services/control/workspace_loop_transition.py",
        "src/polisyos/runtime/quality/assurance_case.py",
        "src/polisyos/runtime/quality/attestation.py",
        "src/polisyos/runtime/quality/diagnostic_events.py",
        "src/polisyos/runtime/quality/invariants.py",
        "src/polisyos/runtime/quality/projection_semantics.py",
        "src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py",
        "src/polisyos/runtime/quality/run_state.py",
        "src/polisyos/runtime/quality/scorecard.py",
        "src/polisyos/scientist/orchestration/engine/executor.py",
        "tools/ci/check_policyos_production_quality_best_in_class.py",
        "tools/quality/validation/build_policy_design_case_pass2_diagnostics.py",
        "tools/quality/validation/build_policy_design_case_wave35a.py",
        "tools/quality/validation/build_policy_design_case_wave35e.py",
        "tools/quality/validation/check_runtime_quality_schema_compatibility.py",
        "tools/quality/validation/pass2_wave34_common.py",
    }
)
_GENERATED = frozenset(
    {
        "apps/runtime-dashboard/src/api/types.ts",
        "packages/runtime-api-client/runtimeApiClient.ts",
        "packages/runtime-api-client/types.ts",
    }
)
_VERIFIER_PATH = "tests/repo_quality/tools/test_ds9_approval_semantic_strangle.py"


def _tracked_raw_approval_paths() -> frozenset[str]:
    pattern = "|".join(
        (
            "approval_ready",
            "approval_state",
            "approval_decision",
            "approval_packet_ref",
            "approval_packet",
            "approvalReady",
            "approvalState",
            "approvalDecision",
            "approvalPacketRef",
            "approvalPacket",
        )
    )
    completed = subprocess.run(
        [
            "git",
            "grep",
            "-l",
            "-E",
            pattern,
            "--",
            "*.py",
            "*.ts",
            "*.tsx",
            "*.js",
            "*.mjs",
            "*.cjs",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    # This verifier names raw tokens to derive the complete product denominator;
    # it is proof machinery, not an approval producer, bridge, or consumer.
    return frozenset(
        line for line in completed.stdout.splitlines() if line and line != _VERIFIER_PATH
    )


def _is_companion(path: str) -> bool:
    return (
        path in _GENERATED
        or path.startswith("tests/")
        or "/e2e/" in path
        or Path(path).name.endswith((".test.ts", ".test.tsx"))
    )


def test_raw_approval_semantic_denominator_classifies_complete_tracked_set() -> None:
    tracked = _tracked_raw_approval_paths()
    companions = frozenset(path for path in tracked if _is_companion(path))
    classified = _MECHANISMS | _RETAINED | companions

    assert tracked == classified
    assert not (_MECHANISMS & _RETAINED)
    assert not ((_MECHANISMS | _RETAINED) & companions)
    assert (len(_MECHANISMS), len(companions), len(_RETAINED), len(tracked)) == (
        18,
        48,
        16,
        82,
    )


def test_currentness_projection_direct_construction_cannot_satisfy_resolver() -> None:
    from polisyos.runtime.quality.approval import (
        ProductionApprovalCurrentnessProjection,
        ProductionApprovalPacketResolver,
    )

    projection = ProductionApprovalCurrentnessProjection(
        status="current",
        packet_ref="sha256:" + "a" * 64,
        checked_at=datetime(2026, 8, 24, tzinfo=UTC),
        expected_consumer="polisyos.scientist.decision_compiler",
        expected_audience="polisyos-runtime",
    )

    assert projection.operational_authority is False
    assert type(projection) is not ProductionApprovalPacketResolver


def _resolver_issuer_calls(source: str) -> tuple[tuple[str, int], ...]:
    tree = ast.parse(source)
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for imported in node.names:
                aliases[imported.asname or imported.name] = imported.name
    found: list[tuple[str, int]] = []
    targets = {
        "ProductionApprovalPacketResolver",
        "_issue_production_approval_currentness_receipt",
        "_issue_production_decision_packet_resolver",
        "_register_production_approval_resolver_installation",
        "_persist_production_decision_packet",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            called = aliases.get(node.func.id, node.func.id)
        elif isinstance(node.func, ast.Attribute):
            called = node.func.attr
        else:
            continue
        if called in targets:
            found.append((called, node.lineno))
    return tuple(sorted(found))


def test_production_packet_resolver_has_single_attested_issuer() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "src/**/*.py"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    calls = {
        (path, called)
        for path in tracked
        for called, _line in _resolver_issuer_calls(Path(path).read_text(encoding="utf-8"))
    }

    assert calls == {
        (
            "src/polisyos/runtime/http/container.py",
            "_issue_production_decision_packet_resolver",
        ),
        (
            "src/polisyos/runtime/http/container.py",
            "_register_production_approval_resolver_installation",
        ),
        (
            "src/polisyos/runtime/quality/approval.py",
            "ProductionApprovalPacketResolver",
        ),
        (
            "src/polisyos/runtime/quality/approval.py",
            "_issue_production_approval_currentness_receipt",
        ),
        (
            "src/polisyos/runtime/quality/approval.py",
            "_persist_production_decision_packet",
        ),
    }
    quality_facade = Path("src/polisyos/runtime/quality/__init__.py").read_text(encoding="utf-8")
    assert "_issue_production_decision_packet_resolver" not in quality_facade
    assert _resolver_issuer_calls(
        "from polisyos.runtime.quality.approval import "
        "_issue_production_decision_packet_resolver as issue\nissue(service)\n"
    )
    assert _resolver_issuer_calls(
        "import polisyos.runtime.quality.approval as approval\n"
        "approval.ProductionApprovalPacketResolver(service)\n"
    )
    assert _resolver_issuer_calls(
        "from polisyos.runtime.http.deployment_security_attestation import "
        "_register_production_approval_resolver_installation as register\n"
        "register(app, container=container, service=service, custody=custody, "
        "verifier_epoch='epoch', resolver=resolver)\n"
    )
