"""Exercise the operator's persisted AQ1 source through its canonical reader."""

from __future__ import annotations

import importlib
import json
from contextlib import suppress
from datetime import UTC, datetime

import pytest

CENSUS = "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
BUNDLE = "architecture/policy_design_case/gy_aq1_non_data_projection/receipt-bundle.json"
AT = datetime(2026, 9, 13, tzinfo=UTC)
DEMAND = {
    "act": {
        "jurisdiction": "UA",
        "office": "office:education",
        "action": "act:fund",
        "delegation_chain": [None],
    }
}


def setup_source(tmp_path, *, demand=None):
    bridge = importlib.import_module("polisyos.runtime.quality.non_data_acquisition")
    census = {
        "schema_version": "policyos.policy_design_case.gy_n13a.acquisition_census.v1",
        "route_evidence": [
            {
                "route": {
                    "route_id": "education",
                    "candidate_ref": "claim:education",
                    "requirement_gap_id": "gap:mandate",
                    "missing_link": "owner:missing",
                },
                "declared_supply": {"row_count": 1},
            }
        ],
    }
    path = tmp_path / CENSUS
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(census))
    request = bridge.NonDataRequest(
        request_id="request:mandate",
        claim_ref="claim:education",
        gap_id="gap:mandate",
        demand=DEMAND if demand is None else demand,
    )
    gap = bridge.AcquisitionGap(
        gap_id=request.gap_id,
        claim_ref=request.claim_ref,
        gap_type="legal_competence_authority",
        authority_level="governed",
    )
    return bridge, census, request, gap


def publish(bridge, root, request, gap):
    producer = getattr(bridge, "publish_non_data_refusal", None)
    assert callable(producer), "AQ1 source producer must call the real canonical bridge"
    return producer(
        governed_root=root,
        request=request,
        gap=gap,
        route_id="education",
        run_id="run:operator",
        at=AT,
    )


def test_operator_cli_persists_planner_and_refusal_for_canonical_readback(tmp_path):
    bridge, census, request, gap = setup_source(tmp_path)
    request_path, gap_path = tmp_path / "request.json", tmp_path / "gap.json"
    request_path.write_text(request.model_dump_json())
    gap_path.write_text(gap.model_dump_json())
    main = getattr(bridge, "main", None)
    assert callable(main), "AQ1 operator production caller is missing"
    assert (
        main(
            [
                "--governed-root",
                str(tmp_path),
                "--request",
                str(request_path),
                "--gap",
                str(gap_path),
                "--route-id",
                "education",
                "--run-id",
                "run:operator",
                "--at",
                AT.isoformat(),
            ]
        )
        == 0
    )
    source = bridge.load_non_data_projection_source(governed_root=tmp_path, census=census)
    receipt = source.routes[0].receipt
    assert source.routes[0].route_id == "education"
    assert receipt.resolution_state == "admission_refused"
    assert receipt.reason_codes == ("non_data_object_missing",)
    assert tuple(receipt.shape.acquisition_types) == ("legal_mandate",)
    assert receipt.authority_granted is False
    assert receipt.planner_report_ref is not None
    assert receipt.request.planner_report_ref == receipt.planner_report_ref
    paths = dict(source.component_bindings)
    assert CENSUS in paths and BUNDLE in paths
    assert sum(path.endswith(".blob") for path in paths) == 2
    assert sum(path.endswith(".manifest.json") for path in paths) == 2


@pytest.mark.parametrize("field", ["claim_ref", "gap_id"])
def test_foreign_request_cannot_publish_into_census_route(tmp_path, field):
    bridge, _, request, gap = setup_source(tmp_path)
    with pytest.raises(ValueError, match="binding"):
        publish(bridge, tmp_path, request.model_copy(update={field: "foreign:value"}), gap)
    assert not (tmp_path / BUNDLE).exists()


def test_same_stream_row_growth_does_not_resolve_non_data_refusal(tmp_path):
    bridge, census, request, gap = setup_source(tmp_path)
    publish(bridge, tmp_path, request, gap)
    before = bridge.load_non_data_projection_source(governed_root=tmp_path, census=census)
    census["route_evidence"][0]["declared_supply"]["row_count"] = 100_000_000
    (tmp_path / CENSUS).write_text(json.dumps(census))
    after = bridge.load_non_data_projection_source(governed_root=tmp_path, census=census)
    assert before.routes == after.routes
    assert dict(before.component_bindings)[CENSUS] != dict(after.component_bindings)[CENSUS]


@pytest.mark.parametrize(
    ("field", "value"),
    [("missing_link", "owner:changed"), ("generated_at", "2026-09-14"), ("note", "é")],
)
def test_selected_route_change_refuses_until_explicit_operator_replacement(tmp_path, field, value):
    bridge, census, request, gap = setup_source(tmp_path)
    publish(bridge, tmp_path, request, gap)
    census["route_evidence"][0]["route"][field] = value
    (tmp_path / CENSUS).write_text(json.dumps(census))
    with pytest.raises(ValueError, match="route_binding"):
        bridge.load_non_data_projection_source(governed_root=tmp_path, census=census)
    publish(bridge, tmp_path, request, gap)
    assert bridge.load_non_data_projection_source(governed_root=tmp_path, census=census).routes


@pytest.mark.parametrize(
    ("demand", "state", "types"),
    [
        ({"unresolved": "shape"}, "shape_not_established", ()),
        (
            {
                **DEMAND,
                "mutation": {
                    "system": "a",
                    "object": "b",
                    "field": "c",
                    "operation": "correct",
                    "purpose": "d",
                },
            },
            "split_required",
            ("owner_writability", "legal_mandate"),
        ),
    ],
)
def test_all_portless_refusal_shapes_reach_source_reader(tmp_path, demand, state, types):
    bridge, census, request, gap = setup_source(tmp_path, demand=demand)
    publish(bridge, tmp_path, request, gap)
    receipt = (
        bridge.load_non_data_projection_source(
            governed_root=tmp_path,
            census=census,
        )
        .routes[0]
        .receipt
    )
    assert receipt.resolution_state == state
    assert tuple(receipt.shape.acquisition_types) == types
    assert receipt.authority_granted is False


@pytest.mark.parametrize("suffix", [".blob", ".manifest.json"])
def test_changed_receipt_bytes_or_manifest_cannot_be_projected(tmp_path, suffix):
    bridge, census, request, gap = setup_source(tmp_path)
    result = publish(bridge, tmp_path, request, gap)
    artifact_hex = result.receipt.artifact_ref.removeprefix("sha256:")
    path = (tmp_path / BUNDLE).parent / "cas" / "artifacts" / "sha256"
    path = path / artifact_hex[:2] / artifact_hex[2:4] / (artifact_hex + suffix)
    path.write_text("{}")
    with pytest.raises(ValueError):
        bridge.load_non_data_projection_source(governed_root=tmp_path, census=census)


def test_present_receipt_ref_from_foreign_cas_refuses_without_reading_it(tmp_path):
    bridge, census, request, gap = setup_source(tmp_path)
    publish(bridge, tmp_path, request, gap)
    bundle_path = tmp_path / BUNDLE
    payload = json.loads(bundle_path.read_text())
    payload["entries"][0]["receipt_ref"] = "sha256:" + "f" * 64
    bundle_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        bridge.load_non_data_projection_source(governed_root=tmp_path, census=census)


def test_missing_bundle_is_empty_and_new_bundle_is_seen(tmp_path):
    bridge, census, request, gap = setup_source(tmp_path)
    loader = getattr(bridge, "load_non_data_projection_source", None)
    assert callable(loader), "canonical DS15 source reader is missing"
    assert loader(governed_root=tmp_path, census=census).routes == ()
    publish(bridge, tmp_path, request, gap)
    assert len(loader(governed_root=tmp_path, census=census).routes) == 1


def test_fixed_family_cannot_alias_another_governed_directory(tmp_path):
    bridge, _, request, gap = setup_source(tmp_path)
    private = tmp_path / "private-run-cas"
    private.mkdir()
    (tmp_path / BUNDLE).parent.symlink_to(private, target_is_directory=True)
    with pytest.raises(ValueError, match="namespace"):
        publish(bridge, tmp_path, request, gap)
    assert list(private.iterdir()) == []


@pytest.mark.parametrize("target", ["cas", "receipt-bundle.json"])
def test_descendant_symlinks_including_dangling_bundle_refuse(tmp_path, target):
    bridge, census, request, gap = setup_source(tmp_path)
    family = (tmp_path / BUNDLE).parent
    family.mkdir()
    destination = tmp_path / "private-cas"
    if target == "cas":
        destination.mkdir()
    (family / target).symlink_to(destination, target_is_directory=target == "cas")
    with pytest.raises(ValueError, match="namespace"):
        publish(bridge, tmp_path, request, gap)
    if target == "receipt-bundle.json":
        with pytest.raises(ValueError, match="namespace"):
            bridge.load_non_data_projection_source(governed_root=tmp_path, census=census)
    assert not destination.exists() or list(destination.iterdir()) == []


def test_missing_candidate_dependency_cannot_become_unbound_projected_refusal(tmp_path):
    bridge, _, request, gap = setup_source(tmp_path)
    request = request.model_copy(update={"candidate_ref": "sha256:" + "e" * 64})
    with pytest.raises(ValueError, match="unresolved_dependency"):
        publish(bridge, tmp_path, request, gap)
    assert not (tmp_path / BUNDLE).exists()


def test_content_valid_fabricated_refusal_must_recompute(tmp_path):
    bridge, census, request, gap = setup_source(tmp_path)
    result = publish(bridge, tmp_path, request, gap)
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.fabric.data_plane import canonical_json_bytes

    store = FileSystemCAS((tmp_path / BUNDLE).parent / "cas")
    forged = result.receipt.model_dump(mode="json", exclude={"artifact_ref"})
    forged["reason_codes"] = ["object:no_longer_required"]
    ref = store.put_bytes(
        canonical_json_bytes(forged),
        opts=PutOptions(
            kind="fabric.non_data_acquisition.receipt",
            media_type="application/json",
            schema=SchemaInfo(name="fabric.non_data_acquisition.receipt", version="1"),
        ),
    )
    path = tmp_path / BUNDLE
    bundle = json.loads(path.read_text())
    bundle["entries"][0]["receipt_ref"] = str(ref.artifact_id)
    path.write_text(json.dumps(bundle))
    with pytest.raises(ValueError, match="receipt_recomputation_mismatch"):
        bridge.load_non_data_projection_source(governed_root=tmp_path, census=census)


@pytest.mark.parametrize("existing_artifacts", [False, True])
def test_reading_incomplete_source_does_not_create_cas_base(tmp_path, existing_artifacts):
    bridge, census, _, _ = setup_source(tmp_path)
    family = (tmp_path / BUNDLE).parent
    cas = family / "cas"
    cas.mkdir(parents=True)
    if existing_artifacts:
        (cas / "artifacts").mkdir()
    (tmp_path / BUNDLE).write_text(
        json.dumps(
            {
                "schema_version": "policyos.runtime.non_data_refusal_bundle.v1",
                "entries": [],
            }
        )
    )
    # A typed source refusal is allowed; a filesystem write is not.
    with suppress(ValueError):
        bridge.load_non_data_projection_source(governed_root=tmp_path, census=census)
    assert (cas / "artifacts").exists() is existing_artifacts
    assert not (cas / "artifacts" / "sha256").exists(), "read-only load created CAS storage"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_route_is_not_admitted_as_json_content(tmp_path, value):
    bridge, census, request, gap = setup_source(tmp_path)
    census["route_evidence"][0]["route"]["nonfinite"] = value
    (tmp_path / CENSUS).write_text(json.dumps(census))
    with pytest.raises(ValueError, match="not_finite_json"):
        publish(bridge, tmp_path, request, gap)
    assert not (tmp_path / BUNDLE).exists()
