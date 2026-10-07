"""Read exact controlled native artifacts and compare arithmetic/state witnesses."""

import base64
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon.canon_json import from_canonical_bytes
from polisyos.scientist.methods.search.service import _decode_checkpoint

POSITIVE = Path("/dev/shm/e02-D-oct07-service-start/final-native-969")
NEGATIVE = Path("/dev/shm/e02-D-B124-removal-four-exxj42mi")
OUTPUT = Path("/dev/shm/e02-D-B124-independent-tests/native969-readback-review.json")
decoder = json.JSONDecoder()
observed = []
for line in (POSITIVE / "dedup.stdout.txt").read_text().splitlines():
    if "{" in line:
        try:
            value, end = decoder.raw_decode(line[line.index("{") :])
        except ValueError:
            continue
        if isinstance(value, dict):
            observed.append(value)
receipt = json.loads((POSITIVE / "dedup.receipt.json").read_text())
assert receipt["source_sha"] == "96905636726483fdea3a98d9313871d825b54a9e"
assert receipt["same_inputs"] is True and receipt["changed_inputs"] == []
assert receipt["case_phases"] == {"PASS": 48, "FAIL": 0, "ERROR": 0, "SKIP": 0}
for suffix, binding in receipt["outputs"].items():
    data = (POSITIVE / f"dedup.{suffix}").read_bytes()
    assert len(data) == binding["bytes"]
    assert hashlib.sha256(data).hexdigest() == binding["sha256"]
assert (
    len(list(ET.parse(POSITIVE / "dedup.junit.xml").getroot().iter("testcase"))) == 48
)
for row in observed[:2]:
    assert [call["value"] for call in row["actual_calls"]] == [1, 2, 1, 2, 2, 2, 2]
    assert row["history_count"] == 4
fresh = next(row for row in observed if "fresh_returncode" in row)
assert fresh["fresh_returncode"] == 0
assert "history_values" in fresh["fresh_stdout"]
marker = next(row for row in observed if "provided_marker" in row)
assert marker["fresh_subjects"] == 2 and marker["physical_history"] == 3
assert marker["provided_marker"] == "sha256:" + "a" * 64
shared = next(row for row in observed if "A_run" in row)
assert shared["A_run"] != shared["B_run"]
assert [call["value"] for call in shared["actual_A_calls"]] == [1]
assert shared["actual_A_proposals"] == [] and shared["fresh_A_history_count"] == 1
assert shared["actual_B_calls"] == []
snapshots = []
quantity_rows = []
refs_seen = set()
snapshot_roots = {}


def read_snapshot(ref_data, fixture_root, role):
    ref = ArtifactRef.model_validate(ref_data)
    stem = str(ref.artifact_id).removeprefix("sha256:")
    if fixture_root.name == "cas":
        cas_root = fixture_root
    else:
        candidates = list(fixture_root.glob(f"**/{stem}.blob"))
        assert len(candidates) == 1, (role, len(candidates))
        blob = candidates[0]
        cas_root = next(parent for parent in blob.parents if parent.name == "cas")
    snapshot = FileSystemCAS(cas_root).get_verified_snapshot(ref)
    assert hashlib.sha256(snapshot.data).hexdigest() == stem
    qualified = (str(ref.artifact_id), ref.manifest_profile_sha256)
    snapshot_roots[qualified] = str(cas_root)
    if qualified not in refs_seen:
        refs_seen.add(qualified)
        snapshots.append(
            {
                "role": role,
                "source_fixture_cas": str(cas_root),
                "ref": ref.model_dump(mode="json"),
                "data_bytes": len(snapshot.data),
                "data_sha256": stem,
                "data_base64": base64.b64encode(snapshot.data).decode(),
                "manifest": snapshot.manifest.model_dump(mode="json"),
            }
        )
    return snapshot


for row in observed:
    if "quantity_assessment" not in row:
        continue
    saved_snapshot = read_snapshot(
        row["checkpoint_ref"],
        POSITIVE / "dedup-fixtures",
        row["profile"] + " checkpoint",
    )
    state = _decode_checkpoint(saved_snapshot.data)["run_state"]
    checkpoint_ref = ArtifactRef.model_validate(row["checkpoint_ref"])
    case_cas = Path(
        snapshot_roots[
            (str(checkpoint_ref.artifact_id), checkpoint_ref.manifest_profile_sha256)
        ]
    )
    evaluation = from_canonical_bytes(
        read_snapshot(
            row["evaluation_ref"],
            case_cas,
            row["profile"] + " evaluation",
        ).data
    )
    history = state["history"][0]
    if row["profile"] in {"missing", "status_not_ok"}:
        assert row["quantity_assessment"]["status"] == "unavailable"
        assert history["is_promising"] is False
        assert history["stage_b_result"]["feedback"]["verdict"] == "REJECT"
        assert history["stage_b_result"]["simulation_results"]["score"] is None
        assert state["best_candidate"] is None and state["pareto_points"] == []
    else:
        expected = 0.0 if row["profile"] == "genuine_zero" else 1.0
        assert evaluation["holdout_metrics"] == {"score": expected}
        assert row["quantity_assessment"]["status"] == "available"
        assert history["is_promising"] is True
        assert history["objective_value"] == -expected
        assert state["best_objective"] == -expected
        assert len(state["pareto_points"]) == 1
    assert evaluation["promotable"] is True
    quantity_rows.append(
        {
            "profile": row["profile"],
            "actual_metrics": evaluation["holdout_metrics"],
            "actual_status": evaluation["status"],
            "promotable_marker": evaluation["promotable"],
            "observed_assessment": row["quantity_assessment"],
            "history_is_promising": history["is_promising"],
            "history_objective": history["objective_value"],
            "best_candidate": state["best_candidate"],
            "frontier_count": len(state["pareto_points"]),
        }
    )
for name in (
    "remove_trial_lookup",
    "restore_marker_override",
    "replace_nullable_primary_zero",
    "remove_run_scope",
):
    corrected = json.loads(
        (NEGATIVE / f"{name}.receipt-marker-prefix-corrected.json").read_text()
    )
    assert corrected["negative_receipt_admitted"] is True
    actual = corrected["persisted_observations"][-1]
    snapshot = read_snapshot(
        actual["checkpoint_ref"],
        NEGATIVE / f"{name}-fixtures",
        name + " actual checkpoint",
    )
    state = _decode_checkpoint(snapshot.data)["run_state"]
    checkpoint_ref = ArtifactRef.model_validate(actual["checkpoint_ref"])
    case_cas = Path(
        snapshot_roots[
            (str(checkpoint_ref.artifact_id), checkpoint_ref.manifest_profile_sha256)
        ]
    )
    for key in (
        "candidate_artifact_ref",
        "evaluation_artifact_ref",
        "suite_artifact_ref",
    ):
        data = state["history"][0]["stage_b_result"]["simulation_results"].get(key)
        if data is not None:
            read_snapshot(data, NEGATIVE / f"{name}-fixtures", name + " " + key)
OUTPUT.write_text(
    json.dumps(
        {
            "schema": "e02.D.native969.independent_runtime_readback.v1",
            "reviewer": "/root/transfer_oct07",
            "production_author": "/root/service_oct07",
            "source_sha": receipt["source_sha"],
            "source_tree": receipt["source_tree"],
            "positive_case_phases": receipt["case_phases"],
            "positive_stdout_json_rows": len(observed),
            "own_test_author_limit": "This is a production/runtime effect and arithmetic review; independent testcode review belongs Census. This reviewer authored the 40 new tests.",
            "ordinary_expected_physical_trace": [1, 2, 1, 2, 2, 2, 2],
            "fresh_child_returncode": fresh["fresh_returncode"],
            "valid_marker_consumer": marker,
            "shared_run_consumer": shared,
            "quantity_actual_readback": quantity_rows,
            "actual_ref_count": len(snapshots),
            "actual_minrefs": snapshots,
            "limitations": [
                "48 native/standalone checks on exact969; four separate counterfactual assertionFAIL. No formal closure/Gacceptance.",
                "No scientific evaluator appointment, defaultproductioncaller, distributed guarantee or generic concurrent mutation protection.",
                "Controlled native artifacts only; no production data copied.",
            ],
        },
        indent=2,
    )
    + "\n"
)
print(
    json.dumps(
        {
            "path": str(OUTPUT),
            "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
            "actual_refs": len(snapshots),
            "positive": receipt["case_phases"],
        }
    )
)  # noqa: T201
