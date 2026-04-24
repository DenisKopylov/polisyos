"""Circuit 5: Reproducibility — Every result carries a complete EvidenceBundle.

Verifies that the audit trail contract is satisfied: every causal identification
result that passes through CausalEngine.audit() produces an EvidenceBundle with
all required fields populated.

Required fields contract
------------------------
- run_id:                non-empty string
- query_str:             non-empty string
- identification_status: one of ("identified", "hedge_found", "oracle_needed", ...)
- algorithm_version:     non-empty string
- proof_steps:           non-empty tuple (at least one proof step recorded)
- created_at:            valid ISO-8601 timestamp string
- graph_fingerprint:     non-empty hex string (when graph provided)
- estimand_fingerprint:  non-empty hex string (when identified)
- estimand_ast:          non-empty dict (when identified)

Test cases
----------
1. Frontdoor: all required fields present and valid.
2. Backdoor (DAG Z→X→Y): estimand_ast and estimand_fingerprint non-empty.
3. Direct identification (direct DAG X→Y): proof_steps ≥ 1.
4. Multi-domain fusion: FusionResult.proof_steps carries algorithm trace.
5. Audit schema version: algorithm_version matches expected pattern.

Bar
---
100% — all fields present for all cases.

Usage
-----
    python benchmarks/reproducibility/test_audit_trail_complete.py
    python benchmarks/reproducibility/test_audit_trail_complete.py --json report.json
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

_BENCH_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _BENCH_ROOT / "src"
for _p in [str(_SRC), str(_BENCH_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from benchmarks.harness import (  # noqa: E402
    BenchmarkCase,
    BenchmarkCircuit,
    BenchmarkHarness,
    BenchmarkReport,
)
from benchmarks.reporting import (  # noqa: E402
    build_preflight,
    build_report_payload,
    print_preflight,
)
from benchmarks.runtime import resolve_mode  # noqa: E402

CIRCUIT = BenchmarkCircuit.REPRODUCIBILITY


# ---------------------------------------------------------------------------
# Graph builders
# ---------------------------------------------------------------------------


def _build_frontdoor():
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType

    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.ADMG,
        nodes=["M", "X", "Y"],
        edges=[
            CausalEdge(src="X", dst="M", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="M", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
        ],
    )


def _build_backdoor():
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType

    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "Z"],
        edges=[
            CausalEdge(src="Z", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
    )


def _build_direct():
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType

    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_valid_iso8601(ts: str) -> bool:
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return True
    except (ValueError, AttributeError):
        return False


def _audit(graph, treatment, outcome):
    from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
    from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationResult

    engine = CausalEngine()
    id_result = engine.identify(treatment=treatment, outcome=outcome, graph=graph)
    if not isinstance(id_result, IdentificationResult):
        raise AssertionError(
            f"Expected IdentificationResult for {treatment}->{outcome}, got {type(id_result).__name__}"
        )
    bundle = engine.audit(id_result, None, run_id=str(uuid.uuid4()), graph=graph)
    return bundle


# ---------------------------------------------------------------------------
# Benchmark cases
# ---------------------------------------------------------------------------


def _case_frontdoor_audit_fields_complete() -> BenchmarkCase:
    """Frontdoor EvidenceBundle: all required fields present."""

    def runner():
        return _audit(_build_frontdoor(), "X", "Y")

    def checker(b) -> bool:
        errors = []
        if not b.run_id:
            errors.append("run_id empty")
        if not b.query_str:
            errors.append("query_str empty")
        if not b.identification_status:
            errors.append("identification_status empty")
        if not b.algorithm_version:
            errors.append("algorithm_version empty")
        if not b.proof_steps:
            errors.append("proof_steps empty")
        if not _is_valid_iso8601(b.created_at):
            errors.append(f"created_at invalid: {b.created_at!r}")
        if not b.graph_fingerprint:
            errors.append("graph_fingerprint empty")
        if b.identification_status == "identified":
            if not b.estimand_fingerprint:
                errors.append("estimand_fingerprint empty for identified query")
            if not b.estimand_ast:
                errors.append("estimand_ast empty for identified query")
        if errors:
            raise AssertionError(f"EvidenceBundle missing fields: {errors}")
        return True

    return BenchmarkCase(
        name="repro::audit_trail::frontdoor_all_fields_present",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("audit_trail", "evidence_bundle", "frontdoor", "complete"),
        timeout_s=20.0,
    )


def _case_backdoor_estimand_fields() -> BenchmarkCase:
    """Backdoor EvidenceBundle: estimand_ast and fingerprint non-empty."""

    def runner():
        return _audit(_build_backdoor(), "X", "Y")

    def checker(b) -> bool:
        if b.identification_status != "identified":
            raise AssertionError(
                f"Backdoor Z→X→Y should be identified, got {b.identification_status!r}"
            )
        if not b.estimand_ast:
            raise AssertionError("estimand_ast must be non-empty for identified backdoor")
        if not b.estimand_fingerprint:
            raise AssertionError("estimand_fingerprint must be non-empty")
        # estimand_fingerprint should be a 16-char hex string
        fp = b.estimand_fingerprint
        if len(fp) != 16 or not all(c in "0123456789abcdef" for c in fp.lower()):
            raise AssertionError(f"estimand_fingerprint should be 16-char hex, got {fp!r}")
        return True

    return BenchmarkCase(
        name="repro::audit_trail::backdoor_estimand_fields_non_empty",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("audit_trail", "estimand", "fingerprint"),
        timeout_s=20.0,
    )


def _case_direct_proof_steps_non_empty() -> BenchmarkCase:
    """Direct DAG X→Y: EvidenceBundle.proof_steps is non-empty."""

    def runner():
        return _audit(_build_direct(), "X", "Y")

    def checker(b) -> bool:
        if not b.proof_steps:
            raise AssertionError(
                "EvidenceBundle.proof_steps must be non-empty even for trivial DAGs"
            )
        # Each proof step must have rule_name
        for step in b.proof_steps:
            if not step.rule_name:
                raise AssertionError(f"All proof steps must have rule_name; got empty: {step}")
        return True

    return BenchmarkCase(
        name="repro::audit_trail::direct_dag_proof_steps_non_empty",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("audit_trail", "proof_steps"),
        timeout_s=15.0,
    )


def _case_fusion_proof_steps_in_result() -> BenchmarkCase:
    """Multi-study fusion FusionResult: proof_steps tuple non-empty."""

    def runner():
        from polisyos.foundry.methods.catalog.causal.data_fusion import multi_study_fusion
        from polisyos.ir.analytics.causal_graph import (
            CausalEdge,
            CausalGraphModel,
            EdgeMark,
            GraphType,
        )
        from polisyos.ir.analytics.data_fusion import FusionDataset

        graph = CausalGraphModel(
            schema_version="1.0",
            graph_type=GraphType.DAG,
            nodes=["X", "Y", "Z"],
            edges=[
                CausalEdge(src="Z", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
                CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            ],
        )
        datasets = [
            FusionDataset(
                dataset_ref="obs_A",
                domain_id="domain_A",
                n_obs=1000,
                available_interventions=[],
                selection_bias_vars=["Z"],
            ),
            FusionDataset(
                dataset_ref="rct_B",
                domain_id="domain_B",
                n_obs=500,
                available_interventions=["X"],
                selection_bias_vars=[],
            ),
        ]
        result = multi_study_fusion(datasets=datasets, graph=graph, treatment="X", outcome="Y")
        return result

    def checker(r) -> bool:
        if not r.proof_steps:
            raise AssertionError("FusionResult.proof_steps must be non-empty for successful mZ-ID")
        if not r.identification_algorithm:
            raise AssertionError("FusionResult.identification_algorithm must be non-empty")
        return True

    return BenchmarkCase(
        name="repro::audit_trail::fusion_result_proof_steps_non_empty",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("audit_trail", "fusion", "proof_steps"),
        timeout_s=20.0,
    )


def _case_algorithm_version_pattern() -> BenchmarkCase:
    """EvidenceBundle.algorithm_version matches expected pattern 'id_v1' or similar."""

    def runner():
        return _audit(_build_frontdoor(), "X", "Y")

    def checker(b) -> bool:
        av = b.algorithm_version
        if not av:
            raise AssertionError("algorithm_version must be non-empty")
        # Must contain a version number hint like 'v1', 'v2', or 'experimental'
        av_lower = av.lower()
        has_version_marker = any(
            marker in av_lower for marker in ("v1", "v2", "v3", "experimental", "id_")
        )
        if not has_version_marker:
            raise AssertionError(f"algorithm_version should contain version marker, got {av!r}")
        return True

    return BenchmarkCase(
        name="repro::audit_trail::algorithm_version_has_version_marker",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("audit_trail", "algorithm_version"),
        timeout_s=15.0,
    )


# ---------------------------------------------------------------------------
# Harness builder
# ---------------------------------------------------------------------------


def build_audit_trail_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register(_case_frontdoor_audit_fields_complete())
    harness.register(_case_backdoor_estimand_fields())
    harness.register(_case_direct_proof_steps_non_empty())
    harness.register(_case_fusion_proof_steps_in_result())
    harness.register(_case_algorithm_version_pattern())
    return harness


# ---------------------------------------------------------------------------
# JSON / main
# ---------------------------------------------------------------------------


def _report_to_dict(
    report: BenchmarkReport, *, mode: str, preflight: dict[str, Any]
) -> dict[str, Any]:
    return build_report_payload(
        report,
        suite_id="reproducibility_audit",
        mode=mode,
        preflight=preflight,
        sub_circuit="audit_trail_complete",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Circuit 5 — Audit trail completeness")
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="deterministic_replay")
    print_preflight(preflight)

    harness = build_audit_trail_harness()
    report = harness.run(circuit=CIRCUIT)
    harness.print_report(report, verbose=not args.quiet)

    if args.json:
        Path(args.json).write_text(
            json.dumps(_report_to_dict(report, mode=mode, preflight=preflight), indent=2),
            encoding="utf-8",
        )
        print(f"\nJSON report written to: {args.json}")

    return 1 if report.n_total() - report.n_passed() > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
