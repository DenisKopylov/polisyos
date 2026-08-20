from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest
from polisyos.runtime.http.services.cycle_board_projection import (
    load_n13b_global_movement_signal,
)

from tests.unit.runtime.http.test_cycle_board_projection_service import (
    N10_ORDER,
    REPO_ROOT,
    _service,
)

_N13B_RELATIVE_PATH = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_executor_contract.json"
)
_EXPECTED_SCHEMA_VERSION = "policyos.layer3.gy.n13b.acquisition_executor_contract.v4"
_EXPECTED_RULE_VERSION = "GY-plan-rev18+3.5.12-D1-D6"
_EXPECTED_PRODUCER = (
    "tools.quality.validation.layer3_gy_n13b_acquisition_contract."
    "derive_n13b_acquisition_executor_contract"
)
_DENIED_ROW_USES = ("per_row_movement", "row_enumeration", "exhaustiveness")


def _content_hash(raw_bytes: bytes) -> str:
    return f"sha256:{sha256(raw_bytes).hexdigest()}"


def _write_owner_bytes(repository_root: Path, raw_bytes: bytes) -> Path:
    target = repository_root / _N13B_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw_bytes)
    return target


def _n13b_manifest_entry(packet):
    entries = [
        entry
        for entry in packet.composition_manifest
        if entry.source_id == "n13b-global-deeper-terminal"
    ]
    assert len(entries) == 1
    return entries[0]


def _assert_unavailable_source_is_renderable(source, *, expected: str) -> None:
    dumped = source.model_dump(mode="json")
    assert source.availability == expected
    assert "demonstration_status" not in dumped
    assert "value" not in dumped

    service, _, _ = _service(n13b_global_signal=source)
    packet = service.get()
    entry = _n13b_manifest_entry(packet)

    assert packet.payload.rows
    assert entry.source_kind == "control_plane_evidence"
    assert entry.availability == expected
    assert entry.artifact_content_hash == source.source_content_hash
    assert entry.authoritative_for == ()
    assert entry.may_not_use_for == _DENIED_ROW_USES


def test_n13b_loader_binds_exact_raw_bytes_and_declared_owner_identity(tmp_path: Path) -> None:
    owner_path = REPO_ROOT / _N13B_RELATIVE_PATH
    raw_bytes = owner_path.read_bytes()
    raw_payload = json.loads(raw_bytes)

    source = load_n13b_global_movement_signal(REPO_ROOT)

    assert source.availability == "available"
    assert source.source_ref == _N13B_RELATIVE_PATH.as_posix()
    assert source.source_content_hash == _content_hash(raw_bytes)
    assert source.schema_version == _EXPECTED_SCHEMA_VERSION
    assert source.rule_version == _EXPECTED_RULE_VERSION
    assert source.producer == _EXPECTED_PRODUCER
    assert source.demonstration_status == raw_payload["demonstration_status"]

    whitespace_bytes = raw_bytes + b"\n"
    _write_owner_bytes(tmp_path, whitespace_bytes)
    whitespace_source = load_n13b_global_movement_signal(tmp_path)

    assert whitespace_source.availability == "available"
    assert whitespace_source.source_content_hash == _content_hash(whitespace_bytes)
    assert whitespace_source.source_content_hash != source.source_content_hash
    assert whitespace_source.schema_version == source.schema_version
    assert whitespace_source.rule_version == source.rule_version
    assert whitespace_source.producer == source.producer
    assert whitespace_source.demonstration_status == source.demonstration_status

    crlf_bytes = raw_bytes.replace(b"\n", b"\r\n")
    assert crlf_bytes != raw_bytes
    _write_owner_bytes(tmp_path, crlf_bytes)
    crlf_source = load_n13b_global_movement_signal(tmp_path)

    assert crlf_source.availability == "available"
    assert crlf_source.source_content_hash == _content_hash(crlf_bytes)
    assert crlf_source.source_content_hash != source.source_content_hash
    assert crlf_source.schema_version == source.schema_version
    assert crlf_source.rule_version == source.rule_version
    assert crlf_source.producer == source.producer
    assert crlf_source.demonstration_status == source.demonstration_status


@pytest.mark.parametrize(
    ("mutation", "expected_availability"),
    [
        ("missing", "artifact_missing"),
        ("malformed_json", "invalid_source"),
        ("valid_array", "invalid_source"),
        ("valid_null", "invalid_source"),
        ("schema_version", "invalid_source"),
        ("rule_version", "invalid_source"),
        ("producer", "invalid_source"),
    ],
)
def test_n13b_loader_types_optional_source_failures_without_failing_the_board(
    tmp_path: Path,
    mutation: str,
    expected_availability: str,
) -> None:
    raw_payload = json.loads((REPO_ROOT / _N13B_RELATIVE_PATH).read_bytes())
    written_bytes: bytes | None = None
    if mutation == "malformed_json":
        written_bytes = b'{"schema_version":'
    elif mutation == "valid_array":
        written_bytes = b"[]"
    elif mutation == "valid_null":
        written_bytes = b"null"
    elif mutation != "missing":
        raw_payload[mutation] = f"substituted:{mutation}"
        written_bytes = json.dumps(raw_payload, sort_keys=True, separators=(",", ":")).encode()
    if written_bytes is not None:
        _write_owner_bytes(tmp_path, written_bytes)

    source = load_n13b_global_movement_signal(tmp_path)

    _assert_unavailable_source_is_renderable(source, expected=expected_availability)
    assert source.source_ref == _N13B_RELATIVE_PATH.as_posix()
    assert source.source_content_hash == (
        _content_hash(written_bytes) if written_bytes is not None else None
    )


def test_unreadable_n13b_source_is_artifact_missing_and_nonfatal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _write_owner_bytes(
        tmp_path,
        (REPO_ROOT / _N13B_RELATIVE_PATH).read_bytes(),
    )
    original_read_bytes = Path.read_bytes

    def refused_read(path: Path) -> bytes:
        if path == target:
            raise OSError("owner artifact is unreadable")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", refused_read)

    source = load_n13b_global_movement_signal(tmp_path)

    _assert_unavailable_source_is_renderable(source, expected="artifact_missing")
    assert source.source_ref == _N13B_RELATIVE_PATH.as_posix()
    assert source.source_content_hash is None


def test_loaded_n13b_stays_control_plane_only_and_ds8_absence_has_no_value() -> None:
    source = load_n13b_global_movement_signal(REPO_ROOT)
    service, _, _ = _service(n13b_global_signal=source)

    packet = service.get()
    entry = _n13b_manifest_entry(packet)

    assert entry.source_kind == "control_plane_evidence"
    assert entry.availability == "available"
    assert entry.artifact_content_hash == source.source_content_hash
    assert entry.authoritative_for == ("global_demonstration_status",)
    assert entry.may_not_use_for == _DENIED_ROW_USES
    for role in N10_ORDER:
        row = next(item for item in packet.payload.rows if item.domain_role == role)
        assert row.stage_trace_href.availability == "not_established"
        assert "DS8" in row.stage_trace_href.owner_route
        assert "value" not in row.stage_trace_href.model_dump()
    legacy = next(row for row in packet.payload.rows if row.cohort == "legacy_fixture")
    assert legacy.stage_trace_href.availability == "artifact_missing"
    assert "value" not in legacy.stage_trace_href.model_dump()
