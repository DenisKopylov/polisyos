"""Merge benchmark JSON artifacts into a contour-aware release summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_suite_payloads(json_dir: Path) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in sorted(json_dir.rglob("*.json")):
        if path.name in {
            "summary.json",
            "run_summary.json",
            "last_suite_summary.json",
            "release_summary.json",
        }:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict) and payload.get("suite_id"):
            payloads.append(payload)
    return payloads


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _merge_leaderboards(target: dict[str, Any], tables: dict[str, Any], *, suite_id: str) -> None:
    for table_name, rows in (tables or {}).items():
        table_entry = target.setdefault(table_name, {})
        for row_name, metrics in (rows or {}).items():
            row_entry = table_entry.setdefault(row_name, {"sources": []})
            if suite_id not in row_entry["sources"]:
                row_entry["sources"].append(suite_id)
            for metric_name, value in (metrics or {}).items():
                metric_entry = row_entry.setdefault(metric_name, [])
                if _is_number(value):
                    metric_entry.append(float(value))


def _finalize_leaderboards(raw: dict[str, Any]) -> dict[str, Any]:
    finalized: dict[str, Any] = {}
    for table_name, rows in raw.items():
        finalized[table_name] = {}
        for row_name, payload in rows.items():
            row = {"sources": list(payload.get("sources", []))}
            for metric_name, values in payload.items():
                if metric_name == "sources":
                    continue
                row[metric_name] = float(sum(values) / len(values)) if values else 0.0
            finalized[table_name][row_name] = row
    return finalized


def _merge_gate_results(target: dict[str, Any], payload: dict[str, Any]) -> None:
    contour = str(payload.get("validation_contour") or "legacy")
    family = str(payload.get("benchmark_family") or payload.get("suite_id") or "unknown")
    suite_id = str(payload.get("suite_id") or "")
    gate_payload = dict(payload.get("release_gate_results") or {})
    family_entry = target.setdefault(contour, {}).setdefault(
        family,
        {"n_suites": 0, "n_passing": 0, "suite_results": {}},
    )
    family_entry["n_suites"] += 1
    overall_status = str(payload.get("overall_status") or "")
    passes = bool(
        gate_payload.get(
            "passes_all",
            overall_status in {"passed", "over_budget"} or payload.get("pass_rate", 0.0) == 1.0,
        )
    )
    if passes:
        family_entry["n_passing"] += 1
    family_entry["suite_results"][suite_id] = {
        "passes_all": passes,
        "overall_status": overall_status,
        "checks": gate_payload.get("checks", {}),
        "visibility": payload.get("visibility"),
    }


def _merge_comparator_execution(target: dict[str, Any], payload: dict[str, Any]) -> None:
    contour = str(payload.get("validation_contour") or "legacy")
    suite_id = str(payload.get("suite_id") or "")
    for label, run_payload in (payload.get("comparator_runs") or {}).items():
        entry = target.setdefault(contour, {}).setdefault(
            label,
            {
                "n_suites": 0,
                "n_available": 0,
                "n_executed": 0,
                "n_cases": 0,
                "n_supported": 0,
                "suite_ids": [],
                "failure_reasons": [],
            },
        )
        entry["n_suites"] += 1
        entry["n_available"] += 1 if run_payload.get("available") else 0
        entry["n_executed"] += 1 if run_payload.get("executed") else 0
        entry["n_cases"] += int(run_payload.get("n_cases") or 0)
        entry["n_supported"] += int(run_payload.get("n_supported") or 0)
        if suite_id not in entry["suite_ids"]:
            entry["suite_ids"].append(suite_id)
        for reason in run_payload.get("failure_reasons", []):
            text = str(reason)
            if text and text not in entry["failure_reasons"]:
                entry["failure_reasons"].append(text)


def _build_shadow_evidence_status(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    status: dict[str, Any] = {"n_shadow_suites": 0, "suites": {}}
    for payload in payloads:
        if str(payload.get("visibility") or "") != "prod_shadow":
            continue
        suite_id = str(payload.get("suite_id") or "")
        selection_manifest = dict(payload.get("selection_manifest") or {})
        status["n_shadow_suites"] += 1
        status["suites"][suite_id] = {
            "benchmark_family": payload.get("benchmark_family"),
            "validation_contour": payload.get("validation_contour"),
            "passes_all": bool(
                (payload.get("release_gate_results") or {}).get("passes_all", False)
            ),
            "manifest_source": selection_manifest.get("source"),
            "manifest_revision": selection_manifest.get("revision"),
            "manifest_placeholder": selection_manifest.get("placeholder"),
        }
    return status


def build_release_summary(json_dir: Path) -> dict[str, Any]:
    payloads = _load_suite_payloads(json_dir)
    contour_matrix: dict[str, dict[str, Any]] = {}
    comparator_completeness: dict[str, dict[str, str]] = {}
    ablation_status: dict[str, dict[str, Any]] = {}
    contour_leaderboards_raw: dict[str, Any] = {}
    academic_public_raw: dict[str, Any] = {}
    academic_hidden_raw: dict[str, Any] = {}
    shadow_raw: dict[str, Any] = {}
    release_gate_results: dict[str, Any] = {}
    comparator_execution_summary: dict[str, Any] = {}

    for payload in payloads:
        contour = str(payload.get("validation_contour") or "legacy")
        visibility = str(payload.get("visibility") or "public")
        suite_id = str(payload.get("suite_id"))
        contour_entry = contour_matrix.setdefault(
            contour,
            {
                "n_suites": 0,
                "n_passing": 0,
                "visibilities": {},
                "suite_results": {},
            },
        )
        contour_entry["n_suites"] += 1
        overall_status = str(payload.get("overall_status") or "")
        passes = bool(
            (payload.get("release_gate_results") or {}).get(
                "passes_all",
                overall_status in {"passed", "over_budget"} or payload.get("pass_rate", 0.0) == 1.0,
            )
        )
        if passes:
            contour_entry["n_passing"] += 1
        contour_entry["visibilities"].setdefault(visibility, 0)
        contour_entry["visibilities"][visibility] += 1
        contour_entry["suite_results"][suite_id] = {
            "passes_all": passes,
            "overall_status": overall_status,
            "pass_rate": payload.get("pass_rate"),
            "benchmark_family": payload.get("benchmark_family"),
            "gate_results": (payload.get("release_gate_results") or {}).get("checks", {}),
        }
        comparator_completeness[suite_id] = dict(payload.get("comparator_status") or {})
        ablation_status[suite_id] = dict(payload.get("ablation_matrix") or {})
        _merge_leaderboards(
            contour_leaderboards_raw.setdefault(contour, {}),
            dict(payload.get("leaderboard_tables") or {}),
            suite_id=suite_id,
        )
        if contour == "academic" and visibility == "public":
            _merge_leaderboards(
                academic_public_raw,
                dict(payload.get("leaderboard_tables") or {}),
                suite_id=suite_id,
            )
        if contour == "academic" and visibility == "hidden_release":
            _merge_leaderboards(
                academic_hidden_raw,
                dict(payload.get("leaderboard_tables") or {}),
                suite_id=suite_id,
            )
        if visibility == "prod_shadow":
            _merge_leaderboards(
                shadow_raw, dict(payload.get("leaderboard_tables") or {}), suite_id=suite_id
            )
        _merge_gate_results(release_gate_results, payload)
        _merge_comparator_execution(comparator_execution_summary, payload)

    return {
        "json_dir": str(json_dir),
        "n_payloads": len(payloads),
        "legacy_floor": contour_matrix.get("legacy", {}),
        "production_contour": contour_matrix.get("production", {}),
        "academic_contour": contour_matrix.get("academic", {}),
        "contour_matrix": contour_matrix,
        "comparator_completeness": comparator_completeness,
        "ablation_status": ablation_status,
        "leaderboard_tables": {
            contour: _finalize_leaderboards(raw)
            for contour, raw in contour_leaderboards_raw.items()
        },
        "public_claim_tables": _finalize_leaderboards(academic_public_raw),
        "hidden_holdout_tables": _finalize_leaderboards(academic_hidden_raw),
        "shadow_monitoring_tables": _finalize_leaderboards(shadow_raw),
        "release_gate_results": release_gate_results,
        "comparator_execution_summary": comparator_execution_summary,
        "shadow_evidence_status": _build_shadow_evidence_status(payloads),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a contour-aware benchmark release summary")
    parser.add_argument("--json-dir", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    json_dir = Path(args.json_dir).resolve()
    summary = build_release_summary(json_dir)
    output = json.dumps(summary, indent=2, sort_keys=True)
    out_path = Path(args.out).resolve() if args.out else json_dir / "release_summary.json"
    out_path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
