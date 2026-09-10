"""Corrupt one current C1 conformance fact through the real Phase-2 CLI reader.

The real producer, its complete family, and all runtime verifiers are unchanged.
The baseline must be the final, complete, unmutated --check receipt from the same
frozen source and artifacts. A stale baseline with target drift is not usable.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

from tools.quality.validation import check_layer3_gy_phase2_artifacts as owner


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _identities(report: object, returncode: int) -> set[str]:
    if not isinstance(report, dict) or report["family_id"] != owner.FAMILY_ID:
        raise ValueError("Not a complete current Phase-2 report")
    if report["write"] is not False or report["written_artifacts"] != []:
        raise ValueError("Probe requires a read-only owner check")
    artifacts = report["checked_artifacts"]
    if not isinstance(artifacts, list) or len(artifacts) != len(set(artifacts)):
        raise ValueError("Invalid checked-artifact population")
    if set(artifacts) != set(owner.OUTPUTS):
        raise ValueError("Complete owner output denominator was not checked")
    rows = report["issues"]
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) or not isinstance(row.get("code"), str)
        for row in rows
    ):
        raise ValueError("Unreadable finding population; absence/null is not zero")
    identities = [_canonical(row) for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate complete finding identity")
    failed = bool(identities)
    if report["status"] != ("fail" if failed else "pass") or returncode != int(failed):
        raise ValueError("Process and semantic check dispositions disagree")
    return set(identities)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--step-id", default="scientist_causal_full.run_causal_evaluation"
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    baseline_bytes = args.baseline.read_bytes()
    baseline = json.loads(baseline_bytes)
    if baseline["timed_out"] is not False or baseline["returncode"] not in (0, 1):
        raise ValueError("Baseline timed out or crashed; fewer findings is not a pass")
    if Path(baseline["cwd"]).resolve() != root:
        raise ValueError("Baseline repository station differs")
    command = baseline["command"]
    module = "tools.quality.validation.check_layer3_gy_phase2_artifacts"
    if not isinstance(command, list) or not any(
        command[index:index + 2] == ["-m", module]
        for index in range(len(command) - 1)
    ) or "--check" not in command or "--write" in command:
        raise ValueError("Baseline is not the actual unmutated Phase-2 --check")
    baseline_report = json.loads(baseline["stdout"])
    before_findings = _identities(baseline_report, baseline["returncode"])
    if any(
        row.get("path") == owner.PLAYBOOK_PROOF_PATH
        and row["code"] == "phase2_artifact_drift"
        for row in baseline_report["issues"]
    ):
        raise ValueError("Baseline already has target drift; reissue/check before this probe")

    preserved_paths = set(owner.OUTPUTS) | set(owner.HISTORICAL_OUTPUTS_SHA256)
    preserved_paths.add(Path(owner.__file__).resolve().relative_to(root).as_posix())
    original = {path: (root / path).read_bytes() for path in sorted(preserved_paths)}
    target = (root / owner.PLAYBOOK_PROOF_PATH).resolve()
    payload = json.loads(original[owner.PLAYBOOK_PROOF_PATH])
    mutant = copy.deepcopy(payload)
    # Enumerate the whole actual admission set, then address one named identity.
    candidates = [
        (proof_index, admission_index, admission["candidate"]["step_id"])
        for proof_index, proof in enumerate(mutant["proofs"])
        for admission_index, admission in enumerate(proof["adapter_admissions"])
    ]
    independent = []
    for proof_index in range(len(payload["proofs"])):
        proof = payload["proofs"][proof_index]
        for admission_index in range(len(proof["adapter_admissions"])):
            item = proof["adapter_admissions"][admission_index]
            independent.append((proof_index, admission_index, item["candidate"]["step_id"]))
    if candidates != independent or len(candidates) != len(set(candidates)):
        raise ValueError("Admission identity derivations differ")
    selected = [item for item in candidates if item[2] == args.step_id]
    if len(selected) != 1:
        raise ValueError("Named current admission is absent or not unique")
    proof_index, admission_index, _ = selected[0]
    admission = mutant["proofs"][proof_index]["adapter_admissions"][admission_index]
    conformance = admission["conformance"]
    previous = conformance["passed"]
    if type(previous) is not bool:
        raise ValueError("Current conformance.passed is not a Boolean")
    conformance["passed"] = not previous
    pointer = f"/proofs/{proof_index}/adapter_admissions/{admission_index}/conformance/passed"
    changed_nodes = owner._phase2_payload_delta(payload, mutant)
    if changed_nodes != [pointer]:
        raise ValueError("Probe must change exactly the named semantic Boolean node")
    replacement = json.dumps(mutant, indent=2, sort_keys=True, allow_nan=False) + "\n"
    real_read_text = Path.read_text
    matched = []

    def read_current(path: Path, *positional: object, **keywords: object) -> str:
        if path.resolve() == target:
            matched.append(path.as_posix())
            return replacement
        return real_read_text(path, *positional, **keywords)

    captured = io.StringIO()
    try:
        with patch.object(Path, "read_text", read_current), contextlib.redirect_stdout(captured):
            returncode = owner.main([
                "--repo-root", str(root), "--check", "--output-format", "json"
            ])
    finally:
        # The complete actual report is emitted once, even if later assertions fail.
        sys.stdout.write(captured.getvalue())
        changed_files = [
            path for path, raw in original.items() if (root / path).read_bytes() != raw
        ]
        if changed_files:
            raise ValueError(f"Read-only probe changed original files: {changed_files}")
    if not matched:
        raise ValueError("Actual committed reader was not exercised")
    current_report = json.loads(captured.getvalue())
    after_findings = _identities(current_report, returncode)
    added, lost = after_findings - before_findings, before_findings - after_findings
    expected_drift = {
        "code": "phase2_artifact_drift",
        "path": owner.PLAYBOOK_PROOF_PATH,
        "changed_json_node_identities": [pointer],
    }
    print(json.dumps({  # noqa: T201 - complete probe metadata belongs in the deciding receipt
        "probe": "current_C1_conformance_boolean_corruption_via_actual_reader",
        "baseline_receipt": str(args.baseline),
        "baseline_receipt_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
        "source_ref": owner.PLAYBOOK_PROOF_PATH,
        "source_sha256": hashlib.sha256(original[owner.PLAYBOOK_PROOF_PATH]).hexdigest(),
        "replacement_sha256": hashlib.sha256(replacement.encode()).hexdigest(),
        "complete_admission_identities": candidates,
        "independent_identity_reconciliation": candidates == independent,
        "changed_json_node_identities": changed_nodes,
        "original_value": previous,
        "replacement_value": not previous,
        "actual_reader_paths": matched,
        "actual_gate_returncode": returncode,
        "complete_added_finding_identities": [json.loads(item) for item in sorted(added)],
        "complete_lost_finding_identities": [json.loads(item) for item in sorted(lost)],
        "preserved_raw_file_hashes": {
            path: hashlib.sha256(raw).hexdigest() for path, raw in original.items()
        },
        "scope": (
            "Actual full-family CLI drift enforcement; prior semantic removal witnesses "
            "establish the runtime property separately."
        ),
    }, indent=2, sort_keys=True), file=sys.stderr)
    if lost:
        raise ValueError("Baseline finding identities were lost; comparison is not a valid witness")
    if added != {_canonical(expected_drift)}:
        raise ValueError("Probe did not add exactly the decisive target drift identity")
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
