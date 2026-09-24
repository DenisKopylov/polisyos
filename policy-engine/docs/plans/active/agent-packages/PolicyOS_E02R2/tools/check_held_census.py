#!/usr/bin/env python3
"""Lexically census tracked PolicyOS source for held-review owner candidates."""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
from typing import Any

EXTENSIONS = {
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".scala", ".sql", ".sh",
}
EXCLUDED_PATHS = {
    "policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/tools/check_held_census.py",
}
PATTERNS = {
    "B61": r"SKGQuery|skg_snapshot_ref|latest_skg_version_id|SourceSnapshot|SourceIdentityBundle|SourceIdentitySelection|VerifiedUkraineStageArtifacts|load_verified_stage_artifacts|SnapshotReadHandle|ReadSnapshot",
    "B194": r"PropagationResult|PosteriorSamplesCarrier|draw_id|draw_outcome|failed_draw|failure_reason|sample_identity|mc_n_failed",
    "B197": r"CalibrationReport|envelopes_from_calibration|handle_indices|group_to_field|field_to_group|group_projection|calibrated_params|hessian_parameter_names",
    "B219": r"CausalGraph|to_networkx|from_networkx|MultiDiGraph|MultiGraph|edge_key|edge_identity",
    "LA-032": r"load_verified_stage_artifacts|VerifiedUkraineStageArtifacts|demography_layout|load_demography_artifacts|inventory_digest",
}
MULTIGRAPH_CONSTRUCTOR = re.compile(r"\b(?:nx|networkx)\.(?:MultiDiGraph|MultiGraph)\s*\(")
LIMITATIONS = [
    "Lexical discovery is not semantic completeness proof.",
    "Cannot exclude differently named aliases, dynamic imports, reflection, generated runtime wiring, or external callers.",
    "A zero exact-constructor count does not prove a semantic capability is absent.",
    "Reads tracked source/code paths only; does not access production_data.",
]


def git_output(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], stderr=subprocess.PIPE)


def collect() -> dict[str, Any]:
    root = pathlib.Path(git_output("rev-parse", "--show-toplevel").decode().strip())
    tracked = git_output("ls-files", "-z", "--", "policy-engine").decode().split("\0")
    tracked_code = sorted(
        p for p in tracked
        if p and pathlib.Path(p).suffix in EXTENSIONS
    )
    code = [p for p in tracked_code if p not in EXCLUDED_PATHS]
    unreadable: list[str] = []
    contents: dict[str, str] = {}
    for path in code:
        try:
            contents[path] = (root / path).read_text(errors="ignore")
        except OSError:
            unreadable.append(path)
            contents[path] = ""

    queries: dict[str, Any] = {}
    for name, expression in PATTERNS.items():
        regex = re.compile(expression)
        hits = [path for path in code if regex.search(contents[path])]
        queries[name] = {
            "regex": expression,
            "matched_paths": hits,
            "matched_path_count": len(hits),
            "src_tests_path_count": sum(
                path.startswith(("policy-engine/src/", "policy-engine/tests/"))
                for path in hits
            ),
        }

    multigraph_hits = [
        path for path in code if MULTIGRAPH_CONSTRUCTOR.search(contents[path])
    ]
    builders = sorted(
        path for path in code
        if path.startswith("policy-engine/src/polisyos/data_forge/domains/ukraine/builders/")
        and path.endswith(".py")
    )
    common_hits = [path for path in builders if ".common" in contents[path]]
    if not code:
        verdict, detail = "FAIL", "tracked code denominator is empty"
    elif unreadable:
        verdict, detail = "UNRUN", f"could not inspect {len(unreadable)} tracked code paths"
    else:
        verdict, detail = "PASS", "complete tracked lexical scan executed"
    return {
        "census_verdict": verdict,
        "census_verdict_detail": detail,
        "semantic_verdict": "UNRUN",
        "eligible_tracked_policy_engine_code_path_count": len(tracked_code),
        "excluded_instrument_path_count": sum(
            path in EXCLUDED_PATHS for path in tracked_code
        ),
        "scanned_policy_engine_code_path_count": len(code),
        "eligible_tracked_src_tests_code_path_count": sum(
            path.startswith(("policy-engine/src/", "policy-engine/tests/"))
            for path in tracked_code
        ),
        "scanned_src_tests_code_path_count": sum(
            path.startswith(("policy-engine/src/", "policy-engine/tests/"))
            for path in code
        ),
        "extensions": sorted(EXTENSIONS),
        "git_query": "git ls-files -z -- policy-engine",
        "excluded_instrument_paths": sorted(EXCLUDED_PATHS),
        "queries": queries,
        "multigraph_constructor_query": {
            "regex": MULTIGRAPH_CONSTRUCTOR.pattern,
            "matched_paths": multigraph_hits,
            "matched_path_count": len(multigraph_hits),
        },
        "ukraine_builders": {
            "tracked_python_paths": builders,
            "tracked_python_path_count": len(builders),
            "paths_containing_literal_dot_common": common_hits,
            "dot_common_path_count": len(common_hits),
        },
        "unreadable_paths": unreadable,
        "limitations": LIMITATIONS,
    }


try:
    result = collect()
except (OSError, UnicodeError, subprocess.CalledProcessError) as exc:
    result = {
        "census_verdict": "UNRUN",
        "census_verdict_detail": f"inspection failed: {type(exc).__name__}",
        "semantic_verdict": "UNRUN",
        "limitations": LIMITATIONS,
    }
print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
if result["census_verdict"] == "PASS":
    raise SystemExit(0)
if result["census_verdict"] == "FAIL":
    raise SystemExit(1)
raise SystemExit(2)
