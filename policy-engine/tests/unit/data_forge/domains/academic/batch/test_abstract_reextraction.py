"""Subset extraction must persist actual axes without granting publication authority."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

MODULE = "polisyos.data_forge.domains.academic.batch.abstract_reextraction"


def _owner():
    assert importlib.util.find_spec(MODULE) is not None, "abstract_subset_bridge_missing"
    return importlib.import_module(MODULE)


def _digest(value):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
    )


def _source(tmp_path: Path):
    source = tmp_path / "held.duckdb"
    con = duckdb.connect(str(source))
    con.execute(
        "CREATE TABLE ac_works (id VARCHAR, title VARCHAR, abstract VARCHAR, year INT, cited_by_count INT, doi VARCHAR)"
    )
    rows = [
        (
            f"synthetic:{index}",
            "Synthetic policy study",
            "Held evidence. " * (index + 1),
            2024,
            20,
            "",
        )
        for index in range(9)
    ]
    con.executemany("INSERT INTO ac_works VALUES (?, ?, ?, ?, ?, ?)", rows)
    con.close()
    groups = [rows[0:3], rows[3:6], rows[6:9]]
    members = [
        {
            "work_id": row[0],
            "stratum": index,
            "abstract_length": len(row[2].strip()),
            "abstract_content_hash": "sha256:" + hashlib.sha256(row[2].encode()).hexdigest(),
            "synthetic": True,
            "scope": "subset",
        }
        for index, group in enumerate(groups)
        for row in sorted(
            group,
            key=lambda row: hashlib.sha256(
                f"corr-held-abstract-pilot.v1|{row[0]}".encode()
            ).hexdigest(),
        )[:2]
    ]
    manifest = {
        "schema_version": "corr.abstract_subset_declaration.v1",
        "scope": "subset",
        "synthetic": True,
        "source_path": str(source),
        "source_table": "ac_works",
        "source_open_mode": "read_only",
        "provider_run_status": "not_started",
        "selection_rule": "nonblank-held-abstract; length-terciles; two lowest fixed salted ID hashes per tercile; no outcome-based replacement",
        "declared_at": datetime.now(UTC).isoformat(),
        "source_row_basis_digest": _digest(sorted((row[0], row[2]) for row in rows)),
        "complete_work_count": len(rows),
        "eligible_count": len(rows),
        "strata": [
            {
                "stratum": index,
                "member_count": len(group),
                "member_identity_digest": _digest(sorted(row[0] for row in group)),
            }
            for index, group in enumerate(groups)
        ],
        "selected_members": members,
        "execution_limits": {
            "concurrency": 1,
            "max_phase_calls": 18,
            "transport_attempts_per_call": 1,
            "per_call_timeout_seconds": 120,
        },
    }
    manifest["declaration_digest"] = _digest(manifest)
    path = tmp_path / "declaration.json"
    path.write_text(json.dumps(manifest))
    return source, path


class SyntheticChat:
    """Replace only the remote text generation; all ingestion remains real."""

    synthetic = True

    def __init__(self, *, fail=False):
        self.index = 0
        self.fail = fail

    async def chat(self, *, model, temperature, prompt):
        del model, temperature, prompt
        self.index += 1
        if self.fail:
            raise PermissionError("synthetic provider refusal")
        phase = (self.index - 1) % 3
        if phase == 0:
            return {"relevant": True}, {"prompt_tokens": 10, "completion_tokens": 2}
        if phase == 2:
            return {"verifications": []}, {"prompt_tokens": 20, "completion_tokens": 4}
        claims = []
        for evidence in ("structural", "unknown", None):
            claim = {
                "cause_variable": "tax rate",
                "effect_variable": "employment",
                "direction": "negative",
                "claim_extraction_confidence": 0.7,
                "design_family_hint": "ols",
                "claim_text": f"Synthetic {evidence} claim",
                "supporting_spans": [
                    {"section": "abstract", "text": "Tax rate reduced employment."}
                ],
            }
            if evidence is not None:
                claim["evidence_strength"] = evidence
            else:
                claim.pop("claim_extraction_confidence")
                claim.pop("design_family_hint")
            claims.append(claim)
        return {"causal_claims": claims, "extraction_confidence": 0.8}, {
            "prompt_tokens": 30,
            "completion_tokens": 6,
        }


@pytest.mark.asyncio
async def test_subset_persists_axes_and_refuses_unadjudicated_publication(tmp_path: Path) -> None:
    """Removing source-presence preservation or publication refusal must fail."""
    owner = _owner()
    source, manifest = _source(tmp_path)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    report = await owner.run_abstract_reextraction(
        manifest_path=manifest,
        output_root=tmp_path / "run",
        client=SyntheticChat(),
        model_id="synthetic:model",
    )
    assert report["synthetic"] is True
    assert report["authority_status"] == "candidate_only"
    assert [row["work_id"] for row in report["work_outcomes"]] == [
        row["work_id"] for row in json.loads(manifest.read_text())["selected_members"]
    ]
    assert [row["status"] for row in report["work_outcomes"]] == ["extracted"] * 6
    assert [row["phase"] for row in report["phase_calls"]] == [
        "screening",
        "extraction",
        "self_verification",
    ] * 6
    assert all(row["provider_cost_usd"] is None for row in report["phase_calls"])
    assert report["full_pass_estimate"]["provider_time_status"] == "not_established_synthetic"
    con = duckdb.connect(report["graph_path"], read_only=True)
    axes = con.execute(
        "SELECT evidence_strength,evidence_strength_status FROM ac_causal_claims_raw"
    ).fetchall()
    assert set(axes) == {
        ("structural", "candidate"),
        ("unknown", "candidate"),
        (None, "not_established"),
    }, "raw_source_presence_transport_lost:" + json.dumps(sorted(set(axes), key=str))
    missing_axes = con.execute(
        "SELECT design_family_hint,design_family_hint_status,claim_extraction_confidence,"
        "claim_extraction_confidence_status FROM ac_causal_claims_raw "
        "WHERE evidence_strength IS NULL"
    ).fetchall()
    assert missing_axes and set(missing_axes) == {
        (None, "not_established", None, "not_established")
    }
    provenance = con.execute(
        "SELECT synthetic,source_provenance_json FROM ac_causal_claims_raw"
    ).fetchall()
    assert provenance
    assert all(
        synthetic is True and json.loads(raw)["synthetic"] is True for synthetic, raw in provenance
    )
    for table in (
        "ac_causal_claims",
        "ac_skg_edges",
        "ac_skg_family_edges",
        "ac_skg_contested_edges",
    ):
        assert con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0  # noqa: S608 - fixed test tables.
    stored = json.loads(
        con.execute("SELECT extraction_json FROM ac_article_extractions LIMIT 1").fetchone()[0]
    )
    assert stored["metadata"]["synthetic"] is True
    assert stored["metadata"]["authority_status"] == "candidate_only"
    con.close()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


@pytest.mark.asyncio
async def test_bounded_chat_sends_actual_completion_cap_and_one_attempt() -> None:
    from polisyos.data_forge.domains.academic.batch.article_extractor import GonkaChatClient

    observed = []

    class Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def text(self):
            return json.dumps({"choices": [{"message": {"content": "{}"}}], "usage": {}})

    class Session:
        def post(self, url, *, json):
            observed.append((url, json))
            return Response()

    client = GonkaChatClient(
        api_key="synthetic",
        base_url="https://synthetic.invalid/v1",
        max_concurrent=1,
        rate_limit_rps=1,
        max_retries=1,
        timeout_seconds=120,
        max_completion_tokens=4096,
    )
    client._session = Session()
    await client.chat(model="synthetic:model", temperature=0.0, prompt="Synthetic control")
    assert len(observed) == 1
    assert observed[0][1]["max_tokens"] == 4096
    assert observed[0][1]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_provider_failure_preserves_complete_subset_without_retrying_known_refusal(
    tmp_path: Path,
) -> None:
    """A failed provider must not silently erase the remainder of the declared subset."""
    owner = _owner()
    _, manifest = _source(tmp_path)
    report = await owner.run_abstract_reextraction(
        manifest_path=manifest,
        output_root=tmp_path / "run",
        client=SyntheticChat(fail=True),
        model_id="synthetic:model",
    )
    assert [row["status"] for row in report["work_outcomes"]] == [
        "provider_failed",
        *(["not_attempted_provider_failed"] * 5),
    ]
    assert len(report["phase_calls"]) == 1
    assert report["full_pass_estimate"]["provider_time_status"] != "measured"


@pytest.mark.asyncio
async def test_rebound_declared_source_refuses_before_extraction(tmp_path: Path) -> None:
    """A valid declaration hash cannot authorize different source bytes."""
    owner = _owner()
    source, manifest = _source(tmp_path)
    con = duckdb.connect(str(source))
    con.execute("UPDATE ac_works SET abstract='Different source' WHERE id='synthetic:0'")
    con.close()
    with pytest.raises(ValueError, match=r"source.*mismatch"):
        await owner.run_abstract_reextraction(
            manifest_path=manifest,
            output_root=tmp_path / "run",
            client=SyntheticChat(),
            model_id="synthetic:model",
        )


@pytest.mark.asyncio
async def test_removal_of_source_presence_preservation_breaks_actual_raw_projection(
    tmp_path, monkeypatch
):
    owner = _owner()
    original = owner._SubsetExtractor.__init__

    def remove_presence(self, **kwargs):
        kwargs["preserve_source_presence"] = False
        original(self, **kwargs)

    monkeypatch.setattr(owner._SubsetExtractor, "__init__", remove_presence)
    with pytest.raises(AssertionError, match="raw_source_presence_transport_lost") as observed:
        await test_subset_persists_axes_and_refuses_unadjudicated_publication(tmp_path)
    print(json.dumps({"removed_property": "raw_source_presence", "gate_failure": str(observed.value)}))


def test_signed_synthetic_graph_reassembly_preserves_source_limit_into_cg2(tmp_path: Path) -> None:
    """Real signature verification enables mechanics; constructed source still refuses authority."""
    from dataclasses import replace

    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.data_forge.domains.academic.batch.admitted_claim_adjudications import (
        load_verified_claim_adjudication_rows,
    )
    from polisyos.data_forge.domains.academic.batch.article_extractor import _to_work_record
    from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
        materialize_claim_adjudication_result,
        produce_claim_adjudication_input,
    )
    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
    from polisyos.data_forge.domains.academic.batch.edge_synthesize import run_edge_synthesize
    from polisyos.data_forge.domains.academic.batch.graph_builder import load_graph
    from polisyos.runtime.quality import credal_reference as credal
    from polisyos.runtime.quality.grounding_bind import (
        GroundingBindGate,
        resolve_grounding_decision_promotability,
    )
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
    from polisyos.scientist.methods.autotune import ChampionRegistry
    from tests.unit.data_forge.domains.academic.batch._claim_evidence import (
        evidence_fixture,
        persist_batch,
    )
    from tests.unit.data_forge.domains.academic.batch.test_admitted_claim_adjudication_consumers import (
        _fixture_article,
    )
    from tests.unit.runtime.quality.test_grounding_bind import _pure_synonym_probe, _reference

    config = AcademicBatchConfig(snapshot_root=tmp_path / "synthetic-only")
    articles = []
    for index, direction in enumerate(("positive", "negative")):
        article = _fixture_article()
        payload = article.model_dump(mode="json")
        payload["openalex_id"] = f"synthetic:work-{index}"
        payload["title"] = f"Synthetic evidence study {index}"
        payload["causal_claims"][0].update(
            claim_id=f"synthetic:claim-{index}",
            direction=direction,
            evidence_strength="rct",
            cause_variable="tax_revenue.total",
            effect_variable="unemployment_rate.total",
        )
        article = type(article).model_validate(payload)
        articles.append(article)
    config.article_extraction_results_path.parent.mkdir(parents=True, exist_ok=True)
    config.article_extraction_results_path.write_text(
        "".join(row.model_dump_json() + "\n" for row in articles)
    )
    store = FileSystemCAS(config.claim_adjudication_cas_root)
    raw_ref = produce_claim_adjudication_input(config, store=store)
    registry = ChampionRegistry(root=config.claim_adjudication_registry_root, store=store)
    evidence = evidence_fixture(store, registry, config.claim_adjudication_registry_root, raw_ref)
    result_ref = persist_batch(evidence)
    materialize_claim_adjudication_result(
        config, result_ref, store=store, verifier=evidence.verifier
    )
    admitted = load_verified_claim_adjudication_rows(
        config, verifier=evidence.verifier, store=store
    )
    records = []
    for index, article in enumerate(articles):
        record = _to_work_record(
            result=article,
            raw_work={},
            topic_ids=[],
            topic_display_names=[],
            run_id="synthetic:reassembly",
            pass_name="synthetic",  # noqa: S106 - stage name.
        )
        # The second row is deliberately unmarked: one synthetic source must
        # conservatively limit the entire mixed snapshot, including sibling views.
        marker = {"synthetic": True, "scope": "synthetic_control"} if index == 0 else {}
        record.metadata.update(marker)
        record.causal_claims = [
            item.model_copy(
                update={
                    "occurrence": {
                        **item.occurrence,
                        **marker,
                        "source_provenance": marker,
                    }
                }
            )
            for item in record.causal_claims
        ]
        records.append(record)
    load_graph(records=records, db_path=config.db_path, admitted_claim_adjudications=admitted)
    run_edge_synthesize(config, source_provenance={"synthetic": True})
    with duckdb.connect(str(config.db_path), read_only=True) as con:
        exact = con.execute("SELECT edge_id FROM ac_skg_edges").fetchall()
        family = con.execute("SELECT family_edge_id FROM ac_skg_family_edges").fetchall()
        contested = con.execute(
            "SELECT contested_edge_id,quality_signals_json FROM ac_skg_contested_edges"
        ).fetchall()
        assert len(exact) == len(family) == 2
        assert len(contested) == 1
        assert json.loads(contested[0][1])["synthetic"] is True
    repo = tmp_path / "isolated-repo"
    link = repo / credal.DEFAULT_L2_SCHOLAR_KG_PATH
    link.parent.mkdir(parents=True)
    link.symlink_to(config.db_path)
    edges = tuple(credal._iter_l2_edges(repo))
    assert edges
    assert all(edge.provenance.get("synthetic") is True for edge in edges), (
        "snapshot_synthetic_ancestry_lost:"
        + json.dumps(
            [
                {
                    "identity": edge.key,
                    "marker_present": "synthetic" in edge.provenance,
                    "value": edge.provenance.get("synthetic", "ABSENT"),
                }
                for edge in edges
            ],
            sort_keys=True,
        )
    )
    original = _reference()
    edge_index = {**original.essential_edges, **{edge.key: edge for edge in edges}}
    digest = credal._reference_hash(
        component_versions=original.component_versions, edge_index=edge_index, as_of=original.as_of
    )
    reference = replace(
        original,
        essential_edges=edge_index,
        reference_hash=digest,
        reference_epoch="kref:" + digest.removeprefix("sha256:")[:16],
    )
    engine = GroundingRelationEngine(reference)
    proposal = engine.certificate_for(
        _pure_synonym_probe(engine), proposal_id="synthetic:graph-support"
    )
    mechanical = GroundingBindGate.for_contract_testing(
        reference, calibration_seed_anchor=True
    ).certificate_for(proposal)
    assert mechanical.decision == "bind"
    production = GroundingBindGate(reference).certificate_for(proposal)
    assert production.decisive_reason == "synthetic_input_candidate_only", (
        "synthetic_specific_refusal_lost:"
        + json.dumps(
            {
                "mechanical_decision": mechanical.decision,
                "production_decision": production.decision,
                "production_reason": production.decisive_reason,
            },
            sort_keys=True,
        )
    )
    assert (
        resolve_grounding_decision_promotability(production, reference).reason
        == "synthetic_input_cannot_grant_authority"
    )


def test_removal_of_snapshot_provenance_breaks_sibling_consumer_gate(tmp_path, monkeypatch):
    from polisyos.runtime.quality import credal_reference as credal

    monkeypatch.setattr(credal, "_iter_l2_edges", credal._iter_l2_source_edges)
    with pytest.raises(AssertionError, match="snapshot_synthetic_ancestry_lost") as observed:
        test_signed_synthetic_graph_reassembly_preserves_source_limit_into_cg2(tmp_path)
    print(json.dumps({"removed_property": "snapshot_ancestry", "gate_failure": str(observed.value)}))


def test_removal_of_synthetic_authority_refusal_breaks_downstream_gate(tmp_path, monkeypatch):
    from polisyos.runtime.quality import grounding_bind

    monkeypatch.setattr(grounding_bind, "_synthetic_reference", lambda _reference: False)
    with pytest.raises(AssertionError, match="synthetic_specific_refusal_lost") as observed:
        test_signed_synthetic_graph_reassembly_preserves_source_limit_into_cg2(tmp_path)
    print(json.dumps({"removed_property": "synthetic_refusal", "gate_failure": str(observed.value)}))


def test_price_uses_observed_tokens_preserves_missing_and_excludes_synthetic():
    owner = _owner()
    configuration = {
        "pricing": {
            "per_million_tokens": {
                "input": 0.4,
                "cached_input": 0.1,
                "output": 1.6,
            }
        }
    }
    calls = [
        {
            "status": "returned",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cached_prompt_tokens": 40,
        }
    ]
    assert owner._price(configuration, calls, synthetic=False)["usd"] == pytest.approx(0.000108)
    assert owner._price(configuration, calls, synthetic=True)["usd"] is None
    calls[0]["prompt_tokens"] = None
    assert owner._price(configuration, calls, synthetic=False)["usd"] is None


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("max_completion_tokens", 4097, "scope_mismatch"),
        ("model_id", "synthetic:other-model", "scope_mismatch"),
        ("subset_declaration_digest", "sha256:" + "0" * 64, "scope_mismatch"),
        ("max_phase_calls", 7, "limits_mismatch"),
        ("declared_at", "2100-01-01T00:00:00+00:00", "not_before_execution"),
    ],
)
def test_rehashed_provider_configuration_cannot_change_bound_scope(tmp_path, field, value, reason):
    owner = _owner()
    _, manifest_path = _source(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    configuration = {
        "schema_version": "corr.abstract_provider_configuration.v1",
        "declared_at": datetime.now(UTC).isoformat(),
        "scope": "subset",
        "synthetic": True,
        "subset_declaration_digest": manifest["declaration_digest"],
        "model_id": "synthetic:model",
        "base_url": "https://synthetic.invalid/v1",
        "api": "chat_completions",
        "json_mode": True,
        "max_completion_tokens": 4096,
        **manifest["execution_limits"],
        "provider_run_status": "not_started",
    }
    path = tmp_path / "provider.json"
    configuration["configuration_digest"] = _digest(configuration)
    path.write_text(json.dumps(configuration))
    assert owner._provider_configuration(path, manifest, "synthetic:model") == configuration
    configuration[field] = value
    configuration.pop("configuration_digest")
    configuration["configuration_digest"] = _digest(configuration)
    path.write_text(json.dumps(configuration))
    with pytest.raises(ValueError, match=reason):
        owner._provider_configuration(path, manifest, "synthetic:model")


@pytest.mark.parametrize("mutation", ["weight", "membership"])
def test_resealed_cost_strata_must_match_complete_source_frame(tmp_path, mutation):
    owner = _owner()
    _, manifest_path = _source(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    assert owner._load_declared_works(manifest)
    if mutation == "weight":
        manifest["strata"][0]["member_count"] += 100
    else:
        manifest["selected_members"][0]["stratum"] = 99
    manifest.pop("declaration_digest")
    manifest["declaration_digest"] = _digest(manifest)
    with pytest.raises(ValueError, match="stratum"):
        owner._load_declared_works(manifest)


@pytest.mark.asyncio
async def test_complete_record_ancestry_survives_missing_occurrence_marker(tmp_path):
    from polisyos.data_forge.domains.academic.batch.graph_builder import load_graph
    from polisyos.data_forge.domains.academic.knowledge.types import WorkRecord

    owner = _owner()
    _, manifest = _source(tmp_path)
    report = await owner.run_abstract_reextraction(
        manifest_path=manifest,
        output_root=tmp_path / "run",
        client=SyntheticChat(),
        model_id="synthetic:model",
    )
    record = WorkRecord.model_validate(
        json.loads(Path(report["work_outcomes"][0]["artifact_path"]).read_text())["record"]
    )
    record.causal_claims = [
        item.model_copy(
            update={
                "occurrence": {
                    key: value
                    for key, value in item.occurrence.items()
                    if key not in {"synthetic", "source_provenance"}
                }
            }
        )
        for item in record.causal_claims
    ]
    output = tmp_path / "replayed.duckdb"
    load_graph(records=[record], db_path=output)
    with duckdb.connect(str(output), read_only=True) as con:
        rows = con.execute("SELECT synthetic FROM ac_causal_claims_raw").fetchall()
        assert rows and all(value is True for (value,) in rows)


@pytest.mark.asyncio
async def test_output_write_boundary_refuses_held_ancestry_and_live_external_root(tmp_path):
    from polisyos.data_forge.domains.academic.batch.article_extractor import GonkaChatClient

    owner = _owner()
    _, manifest_path = _source(tmp_path)
    forbidden = Path("production_data") / "corr-c-refused-output"
    assert not forbidden.exists()
    with pytest.raises(ValueError, match="output_must_be_new_lane_owned"):
        await owner.run_abstract_reextraction(
            manifest_path=manifest_path,
            output_root=forbidden,
            client=SyntheticChat(),
            model_id="synthetic:model",
        )
    assert not forbidden.exists()
    manifest = json.loads(manifest_path.read_text())
    manifest["synthetic"] = False  # adversarial configuration; no provider call is allowed.
    manifest_path.write_text(json.dumps(manifest))
    client = GonkaChatClient(
        api_key="synthetic",
        base_url="https://synthetic.invalid",
        max_concurrent=1,
        rate_limit_rps=1,
        max_retries=1,
    )
    with pytest.raises(ValueError, match="output_must_be_new_lane_owned"):
        await owner.run_abstract_reextraction(
            manifest_path=manifest_path,
            output_root=tmp_path / "outside-lane-output",
            client=client,
            model_id="synthetic:model",
        )
    assert not (tmp_path / "outside-lane-output").exists()
