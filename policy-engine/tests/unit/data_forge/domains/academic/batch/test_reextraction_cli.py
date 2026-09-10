"""A full campaign requires actual immutable source and explicit run admission."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
from pathlib import Path

import duckdb
import pytest

MODULE = "polisyos.data_forge.domains.academic.batch.reextraction_cli"
MODEL = "deepseek-ai/DeepSeek-V4-Flash-0731"


def _owner():
    assert importlib.util.find_spec(MODULE) is not None, "campaign_run_cli_missing"
    return importlib.import_module(MODULE)


def _source(path: Path, *, claim_key: str = "work_id") -> Path:
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE ac_works(id VARCHAR, title VARCHAR, abstract VARCHAR, "
            "year INTEGER, cited_by_count INTEGER, doi VARCHAR, synthetic BOOLEAN)"
        )
        con.execute(
            "INSERT INTO ac_works VALUES "
            "('synthetic:1','Constructed study','Tax changes employment.',2024,2,'',true),"
            "('synthetic:2','Constructed study','Procurement changes output.',2024,2,'',true),"
            "('synthetic:blank','Blank','  ',2024,0,'',true)"
        )
        con.execute(f'CREATE TABLE ac_causal_claims_raw("{claim_key}" VARCHAR)')
        con.execute(
            "INSERT INTO ac_causal_claims_raw VALUES "
            "('synthetic:2'),('synthetic:2'),('synthetic:missing')"
        )
    return path


def _prepare(owner, source: Path, root: Path, **changes):
    args = {
        "source": source,
        "output_root": root,
        "selector": "primary",
        "synthetic": True,
        "campaign_id": "synthetic:cli",
        "screening_model": MODEL,
        "extraction_model": MODEL,
        "concurrency": 1,
        "max_attempts": 8,
        "max_attempts_per_phase": 1,
        "credential_prefix": "TEST_ONLY_",
        "min_free_disk_bytes": 1,
    }
    args.update(changes)
    return owner.prepare_plan(**args)


def _authorize(plan):
    return plan.model_copy(
        update={
            "full_pass_authorized": True,
            "authorization_ref": "synthetic:external-test-authorization",
        }
    )


def _never(*args, **kwargs):
    del args, kwargs  # A failing spy must not render a passed environment in pytest output.
    raise AssertionError("credential_or_provider_boundary_reached")


def test_cli_refuses_unauthorized_before_credentials_source_or_outputs(tmp_path, monkeypatch):
    owner = _owner()
    source = _source(tmp_path / "source.duckdb")
    output = tmp_path / "run"
    plan = _prepare(owner, source, output)
    assert plan.full_pass_authorized is False and plan.authorization_ref is None
    monkeypatch.setattr(owner, "_file_hash", _never)  # No pin/source read before authorization.
    monkeypatch.setattr(owner, "_load_credential", _never)
    monkeypatch.setattr(owner, "SDKExtractionTransport", _never)
    with pytest.raises(ValueError, match="campaign_full_pass_not_authorized"):
        asyncio.run(owner.run_plan(plan))
    assert not output.exists()


@pytest.mark.parametrize("key", ["work_id", "openalex_id"])
def test_prepare_reconciles_complete_source_and_distinct_secondary(tmp_path, key):
    owner = _owner()
    source = _source(tmp_path / "source.duckdb", claim_key=key)
    primary = _prepare(owner, source, tmp_path / "primary")
    secondary = _prepare(owner, source, tmp_path / "secondary", selector="secondary")
    assert primary.frame.input_count == 2
    assert secondary.frame.input_count == 1
    assert secondary.frame.claim_identity_column == key
    assert primary.frame.identity_reconciliation == "equal_complete_ordered_identity_streams"
    assert primary.campaign.input_digest == primary.frame.input_digest
    assert not (tmp_path / "primary").exists()
    assert not (tmp_path / "secondary").exists()


@pytest.mark.parametrize("mutation", ["source_growth", "frame", "owner", "provider"])
def test_run_recomputes_bindings_before_credential_or_output(tmp_path, monkeypatch, mutation):
    owner = _owner()
    source = _source(tmp_path / "source.duckdb")
    output = tmp_path / "run"
    plan = _authorize(_prepare(owner, source, output))
    if mutation == "source_growth":
        with duckdb.connect(str(source)) as con:
            con.execute(
                "INSERT INTO ac_works VALUES "
                "('novel:3','New data','A new held abstract.',2025,0,'',true)"
            )
    elif mutation == "frame":
        plan = plan.model_copy(
            update={
                "frame": plan.frame.model_copy(
                    update={
                        "input_digest": "sha256:" + "0" * 64,
                    }
                )
            }
        )
    elif mutation == "owner":
        plan = plan.model_copy(update={"cli_source_hash": "sha256:" + "0" * 64})
    else:
        plan = plan.model_copy(
            update={
                "provider": plan.provider.model_copy(
                    update={
                        "base_url": "https://unapproved.invalid/v1",
                    }
                )
            }
        )
    monkeypatch.setattr(owner, "_load_credential", _never)
    monkeypatch.setattr(owner, "SDKExtractionTransport", _never)
    with pytest.raises(ValueError):
        asyncio.run(owner.run_plan(plan))
    assert not output.exists()


def test_data_only_source_growth_gets_new_complete_frame(tmp_path):
    owner = _owner()
    source = _source(tmp_path / "source.duckdb")
    first = _prepare(owner, source, tmp_path / "first")
    with duckdb.connect(str(source)) as con:
        con.execute(
            "INSERT INTO ac_works VALUES "
            "('novel:3','New data','A new held abstract.',2025,0,'',true)"
        )
    grown = _prepare(owner, source, tmp_path / "grown")
    assert grown.frame.input_count == first.frame.input_count + 1
    assert grown.frame.input_digest != first.frame.input_digest
    assert grown.cli_source_hash == first.cli_source_hash


def test_oversized_and_ambiguous_source_never_becomes_a_frame(tmp_path):
    owner = _owner()
    source = _source(tmp_path / "source.duckdb")
    with pytest.raises(ValueError, match="campaign_source_record_exceeds_bound"):
        _prepare(owner, source, tmp_path / "large", max_work_bytes=32)
    with duckdb.connect(str(source)) as con:
        con.execute("INSERT INTO ac_works SELECT * FROM ac_works WHERE id='synthetic:1'")
    with pytest.raises(ValueError, match="campaign_source_identity_ambiguous"):
        _prepare(owner, source, tmp_path / "duplicate")


def test_credential_selection_is_unique_and_explicit(tmp_path):
    owner = _owner()
    dotenv = tmp_path / "provided.env"
    dotenv.write_text("UNRELATED=value\nPROVIDER=TEST_ONLY_alpha\n")
    assert owner._load_credential("TEST_ONLY_", {}, dotenv) == "TEST_ONLY_alpha"
    with pytest.raises(ValueError, match="campaign_credential_ambiguous"):
        owner._load_credential("TEST_ONLY_", {"A": "TEST_ONLY_beta"}, dotenv)
    with pytest.raises(ValueError, match="campaign_credential_absent"):
        owner._load_credential("TEST_ONLY_", {}, None)


def test_run_uses_existing_campaign_and_completed_resume(tmp_path, monkeypatch):
    owner = _owner()
    from polisyos.data_forge.domains.academic.batch.reextraction_transport import SafeJsonWriter

    source = _source(tmp_path / "source.duckdb")
    output = tmp_path / "run"
    plan = _authorize(_prepare(owner, source, output))
    calls = []

    class SyntheticTransport:
        synthetic = True

        def __init__(self, **kwargs):
            self.safe_write_json = SafeJsonWriter(kwargs["api_key"])

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def bind(self, context):
            calls.append(context)
            return self

        async def chat(self, **kwargs):
            return {"relevant": False, "reason": "synthetic control"}, {
                "prompt_tokens": 1,
                "completion_tokens": 1,
            }

    monkeypatch.setattr(owner, "SDKExtractionTransport", SyntheticTransport)
    monkeypatch.setattr(owner, "_load_credential", lambda *args: "TEST_ONLY_alpha")
    first = asyncio.run(owner.run_plan(plan))
    assert first["works"] == {"complete": 2}
    assert len(calls) == 2
    again = asyncio.run(owner.run_plan(plan))
    assert len(calls) == 2
    assert again["graph_finalization"] == "not_started_separate_owner_stage"
    assert json.loads((output / "plan.json").read_text())["synthetic"] is True


def test_frame_identity_mismatch_is_recomputed_before_credentials(tmp_path, monkeypatch):
    owner = _owner()
    source = _source(tmp_path / "source.duckdb")
    output = tmp_path / "run"
    plan = _authorize(_prepare(owner, source, output))
    # Keep the real source, work digest and count; falsify only the complete identity claim.
    plan = plan.model_copy(
        update={
            "frame": plan.frame.model_copy(
                update={
                    "identity_digest": "sha256:" + "0" * 64,
                }
            )
        }
    )
    monkeypatch.setattr(owner, "_load_credential", _never)
    with pytest.raises(ValueError, match="campaign_source_frame_mismatch"):
        asyncio.run(owner.run_plan(plan))
    assert not output.exists()


def test_independent_complete_enumeration_disagreement_refuses(tmp_path, monkeypatch):
    owner = _owner()
    source = _source(tmp_path / "source.duckdb")
    original = owner._independent_ids

    def omit_one(*args):
        rows = original(*args)
        next(rows)
        yield from rows

    monkeypatch.setattr(owner, "_independent_ids", omit_one)
    with pytest.raises(ValueError, match="campaign_source_identity_reconciliation_failed"):
        _prepare(owner, source, tmp_path / "run")


@pytest.mark.parametrize(
    "override",
    [
        {"concurrency": 33},
        {"max_attempts": 0},
        {"max_attempts_per_phase": 9},
        {"screening_model": "unapproved:model"},
    ],
)
def test_invalid_dispatch_configuration_never_produces_plan(tmp_path, override):
    owner = _owner()
    source = _source(tmp_path / "source.duckdb")
    with pytest.raises(ValueError):
        _prepare(owner, source, tmp_path / "run", **override)


def test_source_provenance_cannot_be_unmarked_by_plan(tmp_path):
    owner = _owner()
    source = _source(tmp_path / "source.duckdb")
    # Output is in the real allowed lane scratch; refusal must be the actual source marker.
    root = Path(owner.__file__).resolve().parents[6] / ".tmp" / "synthetic-cli-not-created"
    with pytest.raises(ValueError, match="campaign_synthetic_source_requires_marked_plan"):
        _prepare(owner, source, root, synthetic=False)
    assert not root.exists()


def test_prompt_context_cap_refuses_before_sdk_chat():
    owner = _owner()
    called = []

    class Bound:
        synthetic = True

        async def chat(self, **kwargs):
            called.append(kwargs)
            return {}, {}

    client = owner._LimitedClient(Bound(), 4)
    with pytest.raises(ValueError, match="campaign_context_exceeds_bound"):
        asyncio.run(client.chat(model=MODEL, temperature=0.0, prompt="longer"))
    assert called == []
    assert asyncio.run(client.chat(model=MODEL, temperature=0.0, prompt="okay")) == ({}, {})
    assert len(called) == 1


def test_command_prepare_and_run_unauthorized(tmp_path, capsys):
    owner = _owner()
    source = _source(tmp_path / "source.duckdb")
    path = tmp_path / "prepared.json"
    argv = [
        "prepare",
        "--source",
        str(source),
        "--output-root",
        str(tmp_path / "run"),
        "--plan-output",
        str(path),
        "--campaign-id",
        "synthetic:command",
        "--screening-model",
        MODEL,
        "--extraction-model",
        MODEL,
        "--credential-prefix",
        "TEST_ONLY_",
        "--synthetic",
        "--max-attempts",
        "8",
        "--min-free-disk-bytes",
        "1",
    ]
    assert owner.main(argv) == 0
    payload = json.loads(path.read_text())
    assert payload["full_pass_authorized"] is False and payload["synthetic"] is True
    assert owner.main(["run", "--plan", str(path)]) == 1
    streams = capsys.readouterr()
    assert '"error_kind":"campaign_cli_refused"' in streams.err
    assert not (tmp_path / "run").exists()


def test_complete_identity_stream_crosses_pages_without_code_change(tmp_path, monkeypatch):
    owner = _owner()
    source = _source(tmp_path / "source.duckdb")
    with duckdb.connect(str(source)) as con:
        con.execute(
            "INSERT INTO ac_works SELECT 'synthetic:grown:'||i,'Constructed',"
            "'Held abstract.',2025,0,'',true FROM range(130) t(i)"
        )
        expected = {
            row[0]
            for row in con.execute(
                "SELECT id FROM ac_works WHERE length(trim(abstract))>0",
            ).fetchall()
        }
    observed = []
    original = owner._work_rows

    def retain_identities(*args):
        for ordinal, work, size in original(*args):
            observed.append(work["id"])
            yield ordinal, work, size

    monkeypatch.setattr(owner, "_work_rows", retain_identities)
    plan = _prepare(owner, source, tmp_path / "run")
    assert set(observed) == expected
    assert len(observed) == len(expected) == plan.frame.input_count


def test_full_work_hash_preserves_native_float_source_values(tmp_path):
    import hashlib

    owner = _owner()
    source = _source(tmp_path / "source.duckdb")
    with duckdb.connect(str(source)) as con:
        con.execute("ALTER TABLE ac_works ADD COLUMN trust_score FLOAT DEFAULT 0.85")
        columns = [row[0] for row in con.execute("DESCRIBE ac_works").fetchall()]
        expected = hashlib.sha256()
        for row in con.execute(
            "SELECT * FROM ac_works WHERE length(trim(abstract))>0 ORDER BY rowid",
        ).fetchall():
            work = dict(zip(columns, row, strict=True))
            expected.update((owner._digest(work) + "\n").encode())
    plan = _prepare(owner, source, tmp_path / "run")
    assert plan.frame.input_digest == "sha256:" + expected.hexdigest()


def test_recover_cli_delegates_exact_stop_without_provider_calls(tmp_path, monkeypatch):
    owner = _owner()
    from polisyos.data_forge.domains.academic.batch.reextraction_transport import (
        ExtractionRequestError,
    )

    source = _source(tmp_path / "source.duckdb")
    output = tmp_path / "run"
    plan = _authorize(_prepare(owner, source, output, max_attempts_per_phase=2))
    calls = []

    class SyntheticTransport:
        synthetic = True

        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def bind(self, context):
            calls.append(context)
            return self

        async def chat(self, **kwargs):
            if len(calls) == 1:
                raise ExtractionRequestError("authentication_error", False, 401)
            return {"relevant": False, "reason": "synthetic control"}, {}

    monkeypatch.setattr(owner, "SDKExtractionTransport", SyntheticTransport)
    monkeypatch.setattr(owner, "_load_credential", lambda *args: "TEST_ONLY_alpha")
    first = asyncio.run(owner.run_plan(plan))
    assert first["execution_status"] == "stopped_fatal" and len(calls) == 1
    stop = first["fatal_stop_ref"]
    stop_bytes = (output / stop["path"]).read_bytes()
    plan_path = tmp_path / "authorized.json"
    plan_path.write_text(plan.model_dump_json())
    monkeypatch.setattr(owner, "SDKExtractionTransport", _never)
    assert owner.main(
        [
            "recover",
            "--plan",
            str(plan_path),
            "--stop-path",
            stop["path"],
            "--stop-sha256",
            stop["sha256"],
            "--acknowledgment-ref",
            "synthetic:operator",
            "--reason",
            "Synthetic credential repaired; retain consumed budget",
        ]
    ) == 0
    assert len(calls) == 1 and (output / stop["path"]).read_bytes() == stop_bytes
    monkeypatch.setattr(owner, "SDKExtractionTransport", SyntheticTransport)
    resumed = asyncio.run(owner.run_plan(plan))
    assert resumed["works"] == {"complete": 2} and len(calls) == 3


def test_finalize_cli_replays_historical_input_and_refuses_incomplete(tmp_path, monkeypatch, capsys):
    owner = _owner()
    assert hasattr(owner, "finalize_plan"), "campaign_graph_cli_bridge_missing"
    from polisyos.data_forge.domains.academic.batch import reextraction_campaign as campaign
    from polisyos.data_forge.domains.academic.batch.reextraction_transport import SafeJsonWriter

    source = _source(tmp_path / "source.duckdb")
    output = tmp_path / "run"
    plan = _authorize(_prepare(owner, source, output))
    writer = SafeJsonWriter("TEST_ONLY_alpha")
    owner._invocation_plan(plan, writer, create=True)
    with owner._source_connection(source, 128) as con:
        works = [work for _, work, _ in owner._work_rows(con, None, plan.max_work_bytes)]
    with campaign.CampaignCheckpoint(output, plan.campaign, writer) as checkpoint:
        checkpoint.prepare_inputs(iter(works))
    monkeypatch.setattr(owner, "_load_credential", _never)
    monkeypatch.setattr(owner, "SDKExtractionTransport", _never)
    with pytest.raises(ValueError, match="campaign_graph_inputs_incomplete"):
        owner.finalize_plan(plan)
    assert not (output / "graphs").exists() and not (output / "graph-builds").exists()
    with campaign.CampaignCheckpoint(output, plan.campaign, writer) as checkpoint:
        for key in checkpoint.iter_work_keys():
            checkpoint.commit_work(key, status="screening_rejected", record=None)
    # Historical graph input is valid even after current execution code changes.
    monkeypatch.setattr(campaign, "campaign_owner_projection", lambda: {"content_hash": "changed"})
    plan_path = tmp_path / "authorized.json"
    plan_path.write_text(plan.model_dump_json())
    assert owner.main(["finalize", "--plan", str(plan_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["synthetic"] is True and result["authority_status"] == "candidate_only"
    assert result["graph_finalization"] == "completed_candidate_graph"
    ref = result["graph_ref"]
    packet = json.loads((output / ref["path"]).read_text())
    assert packet["work_outcomes"] == {"screening_rejected": len(works)}
    assert packet["input_owner_source_hash"] == plan.campaign.owner_source_hash
    assert packet["input_mode"] == "historical_source_epoch"
    assert packet["graph_metrics"]["works"] == 0
