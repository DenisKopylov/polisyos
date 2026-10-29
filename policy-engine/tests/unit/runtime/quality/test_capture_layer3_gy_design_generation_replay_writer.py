"""Behavioral controls for candidate capture destination and CLI usage scope."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from polisyos.core.llm.response import extract_llm_response_data
from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.design_generation import RecordingLLMClient
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient
from tools.quality.validation import capture_layer3_gy_design_generation_replay as capture_cli
from tools.quality.validation.check_layer3_gy_design_generation_contract import (
    RecordedGenerationReplayClient,
)
from tools.quality.validation.generation_replay_input import read_replay_capture


def _require_nofollow_dirfd_support() -> None:
    if (
        os.name != "posix"
        or not hasattr(os, "O_NOFOLLOW")
        or not hasattr(os, "O_DIRECTORY")
        or os.open not in os.supports_dir_fd
        or os.stat not in os.supports_dir_fd
    ):
        pytest.skip("capture destination requires POSIX no-follow dirfd support")


def test_capture_destination_rejects_preexisting_dangling_leaf_without_touching_target(
    tmp_path,
):
    _require_nofollow_dirfd_support()
    owner = tmp_path / "owned"
    owner.mkdir()
    preserved = owner / "preserved.bin"
    preserved.write_bytes(b"owner bytes stay unchanged")
    outside_target = tmp_path / "outside.json"
    dangling = owner / "capture.json"
    dangling.symlink_to(outside_target)

    with pytest.raises(ValueError, match="versioned_capture_destination_must_be_fresh"):
        capture_cli._admit_owned_capture_destination(str(owner), "capture.json")

    assert dangling.is_symlink()
    assert not outside_target.exists()
    assert preserved.read_bytes() == b"owner bytes stay unchanged"


def test_capture_destination_rejects_existing_file_without_changing_any_bytes(tmp_path):
    _require_nofollow_dirfd_support()
    owner = tmp_path / "owned"
    owner.mkdir()
    existing = owner / "capture.json"
    existing.write_bytes(b"original output bytes")
    sibling = owner / "preserved.bin"
    sibling.write_bytes(b"sibling bytes")

    with pytest.raises(ValueError, match="versioned_capture_destination_must_be_fresh"):
        capture_cli._admit_owned_capture_destination(str(owner), "capture.json")

    assert existing.read_bytes() == b"original output bytes"
    assert sibling.read_bytes() == b"sibling bytes"


def test_capture_destination_rejects_symlink_in_the_owner_parent_chain(tmp_path):
    _require_nofollow_dirfd_support()
    real_parent = tmp_path / "real-parent"
    owner = real_parent / "owned"
    owner.mkdir(parents=True)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    aliased_owner = linked_parent / "owned"

    with pytest.raises(
        ValueError, match="versioned_capture_owner_path_must_be_real_directory_chain"
    ):
        capture_cli._admit_owned_capture_destination(str(aliased_owner), "capture.json")

    assert not (owner / "capture.json").exists()


def test_capture_destination_rejects_mutable_parent_without_sticky_mode(tmp_path):
    _require_nofollow_dirfd_support()
    mutable_parent = tmp_path / "mutable-parent"
    mutable_parent.mkdir()
    mutable_parent.chmod(0o777)
    owner = mutable_parent / "owned"
    owner.mkdir()

    with pytest.raises(
        ValueError, match="versioned_capture_owner_parent_must_be_sticky_or_private"
    ):
        capture_cli._admit_owned_capture_destination(str(owner), "capture.json")

    assert not (owner / "capture.json").exists()


@pytest.mark.parametrize(
    ("owner_suffix", "output_name", "message"),
    [
        ("/./owned", "capture.json", "owner_root_must_be_absolute_canonical_path"),
        ("/owned", "../outside.json", "output_must_be_single_relative_filename"),
        ("/owned", "nested/capture.json", "output_must_be_single_relative_filename"),
    ],
)
def test_capture_destination_rejects_lexical_alias_and_outside_names(
    tmp_path, owner_suffix, output_name, message
):
    _require_nofollow_dirfd_support()
    owner = tmp_path / "owned"
    owner.mkdir()
    raw_owner = str(tmp_path) + owner_suffix if owner_suffix.startswith("/") else owner_suffix

    with pytest.raises(ValueError, match=message):
        capture_cli._admit_owned_capture_destination(raw_owner, output_name)

    assert list(owner.iterdir()) == []


def test_capture_destination_writes_only_one_fresh_leaf_and_preserves_siblings(tmp_path):
    _require_nofollow_dirfd_support()
    owner = tmp_path / "owned"
    owner.mkdir()
    preserved = owner / "preserved.bin"
    preserved.write_bytes(b"before")

    destination = capture_cli._admit_owned_capture_destination(str(owner), "capture.json")
    try:
        destination.write_text_exclusive('{"candidate": true}\n')
        with pytest.raises(FileExistsError):
            destination.write_text_exclusive('{"candidate": false}\n')
    finally:
        destination.close()

    assert {path.name for path in owner.iterdir()} == {"preserved.bin", "capture.json"}
    assert (owner / "capture.json").read_bytes() == b'{"candidate": true}\n'
    assert preserved.read_bytes() == b"before"


def test_capture_destination_final_exclusive_open_refuses_an_admission_race(tmp_path):
    _require_nofollow_dirfd_support()
    owner = tmp_path / "owned"
    owner.mkdir()
    destination = capture_cli._admit_owned_capture_destination(str(owner), "capture.json")
    raced_file = owner / "capture.json"
    raced_file.write_bytes(b"concurrent bytes")
    try:
        with pytest.raises(FileExistsError):
            destination.write_text_exclusive("replacement")
    finally:
        destination.close()

    assert raced_file.read_bytes() == b"concurrent bytes"


class _Span:
    def set_attribute(self, *args):
        pass

    def set_status(self, *args):
        pass

    def record_exception(self, *args):
        pass


class _Tracer:
    @contextmanager
    def start_as_current_span(self, *args, **kwargs):
        yield _Span()


class _Metrics:
    def record_llm_call(self, **kwargs):
        pass


class _Provider:
    async def generate(self, **kwargs):
        return GatewayLLMClient(
            base_url="http://127.0.0.1:1/v1",
            api_key="",
            model="moonshotai/Kimi-K2.6",
        )._parse_completion_payload(
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1},
            }
        )


def test_real_cli_writer_emits_raw_candidate_usage_but_no_store_replay_is_missing(
    tmp_path, monkeypatch, capsys
):
    owner = tmp_path / "owned"
    owner.mkdir()
    model_id = "moonshotai/Kimi-K2.6"

    class _Contract:
        def _resolve_current_wmr_owner_projection(self, repo_root):
            return {"world_model_record_id": "fixture-wmr"}

        def _design_problem(self, payload):
            return SimpleNamespace(model_dump=lambda mode="json": dict(payload))

    async def _capture_one_call_without_settlement_store(problem, *, model_id, **kwargs):
        traced = TracedLLMClient(
            _Provider(),
            model_name=model_id,
            provider_name="declared-fixture",
            tracer=_Tracer(),
            metrics=_Metrics(),
        )
        assert traced._producer_settlement_store is None
        recorder = RecordingLLMClient(traced, model_id=model_id)
        await recorder.generate(user="candidate-only writer boundary")
        raise RuntimeError("controlled_abort_after_recorded_provider_response")

    monkeypatch.setattr(capture_cli, "_load_runtime_symbols", lambda: None)
    monkeypatch.setattr(capture_cli, "contract", _Contract(), raising=False)
    monkeypatch.setattr(
        capture_cli,
        "generate_design_candidate_bundle_under_a",
        _capture_one_call_without_settlement_store,
        raising=False,
    )
    monkeypatch.setattr(capture_cli, "gy_content_hash", gy_content_hash, raising=False)
    monkeypatch.setattr(
        capture_cli,
        "_resolve_capture_world_model_record_ref",
        lambda projection, requested: "fixture-wmr",
    )
    monkeypatch.setattr(capture_cli, "_model_plan", lambda models, attempts: [model_id])
    monkeypatch.setattr(capture_cli, "_timestamp_id", lambda: "fixed")
    monkeypatch.setattr(capture_cli, "_now_iso", lambda: "2026-10-29T00:00:00Z")
    monkeypatch.setattr(capture_cli, "DEFAULT_ENV", {})

    exit_code = capture_cli.main(
        [
            "--repo-root",
            str(tmp_path),
            "--attempts",
            "1",
            "--models",
            model_id,
            "--capture-v3-owner-root",
            str(owner),
            "--capture-v3-output",
            "capture.json",
        ]
    )

    # The writer preserves a valid candidate input, but the producer task did
    # not complete and the unmanaged settlement does not establish acceptance.
    assert exit_code == 1
    capture = read_replay_capture(owner / "capture.json")
    assert capture.metadata["capture_status"] == "capture_exception"
    observation = capture.call_usage[0].observation
    assert observation.provider_usage == {"prompt_tokens": 2, "completion_tokens": 1}
    assert observation.provider_usage_status == "known"
    assert observation.settlement is not None
    assert observation.settlement.ack_status == "unmanaged"
    assert observation.settlement.cost_origin == "estimated"

    replayed = asyncio.run(RecordedGenerationReplayClient(capture).generate())
    assert extract_llm_response_data(replayed).usage_status == "missing"

    output_lines = capsys.readouterr().out.splitlines()
    write_line = next(
        line for line in output_lines if line.startswith("CAPTURE_V3_WRITE_CANDIDATE_INPUT ")
    )
    qualification = json.loads(write_line.removeprefix("CAPTURE_V3_WRITE_CANDIDATE_INPUT "))
    assert qualification["authority"] == "candidate_input_only"
    assert qualification["usage_qualification"] == (
        "candidate_quantity_only_committed_settlement_required"
    )
    assert qualification["runtime_acceptance"] == "not_asserted"


@pytest.mark.parametrize("destination_kind", ["dangling", "existing", "parent_link"])
def test_actual_cli_refuses_unadmitted_path_before_runtime_or_provider_work(
    tmp_path, monkeypatch, destination_kind
):
    _require_nofollow_dirfd_support()
    real_owner = tmp_path / "owned"
    real_owner.mkdir()
    preserved = real_owner / "preserved.bin"
    preserved.write_bytes(b"owner-sibling")
    owner = real_owner
    target = tmp_path / "unadmitted-target.json"
    if destination_kind == "dangling":
        (owner / "capture.json").symlink_to(target)
    elif destination_kind == "existing":
        (owner / "capture.json").write_bytes(b"existing-capture")
    else:
        owner = tmp_path / "owner-link"
        owner.symlink_to(real_owner, target_is_directory=True)
    invoked = []
    monkeypatch.setattr(
        capture_cli, "_load_runtime_symbols", lambda: invoked.append("runtime_load")
    )
    with pytest.raises(ValueError):
        capture_cli.main(
            [
                "--repo-root",
                str(tmp_path),
                "--attempts",
                "1",
                "--capture-v3-owner-root",
                str(owner),
                "--capture-v3-output",
                "capture.json",
            ]
        )
    assert invoked == []
    assert not target.exists()
    assert preserved.read_bytes() == b"owner-sibling"
    if destination_kind == "existing":
        assert (real_owner / "capture.json").read_bytes() == b"existing-capture"
    elif destination_kind == "parent_link":
        assert not (real_owner / "capture.json").exists()
    else:
        assert (real_owner / "capture.json").is_symlink()
