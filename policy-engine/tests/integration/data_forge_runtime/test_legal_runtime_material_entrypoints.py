from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from urllib.parse import urlencode

import duckdb
import httpx
import pytest

from polisyos.data_forge.domains.legal.batch.graph_builder import build_graph
from polisyos.data_forge.domains.legal.batch.postprocess import ground_spo_quotes
from polisyos.data_forge.domains.legal.batch.provisions_io import write_provisions
from polisyos.lex.knowledge import LegalKnowledgeGraph

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("POLISYOS_RUN_LEGAL_PROFILED_ENTRYPOINTS") != "1",
        reason="Set POLISYOS_RUN_LEGAL_PROFILED_ENTRYPOINTS=1 for the cached-model entrypoint proof.",
    ),
]

POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = (
    POLICY_ENGINE_ROOT
    / "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/c12-real-encoder-profile"
)
CONTROLLED_DOC_ID = "controlled-legal-fixture"
SOURCE_BOUND_PROVISION_ANCHOR = "body:1/item:0001"
SOURCE_BOUND_PROVISION_TEXT = "The Ministry shall publish the annual budget report by March."
SOURCE_BOUND_CANDIDATE_TEXT = "The Ministry must publish the annual budget report by March."


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")


def _prepare_graph_database(path: Path) -> list[str]:
    """Build a real Legal graph from controlled source-bound and forged candidates."""
    output_root = path.parent
    doc_id = CONTROLLED_DOC_ID
    anchor = SOURCE_BOUND_PROVISION_ANCHOR
    provision_text = SOURCE_BOUND_PROVISION_TEXT
    provisions_dir = output_root / "fixture-provisions"
    raw_spo_dir = output_root / "fixture-spo-raw"
    grounded_spo_dir = output_root / "fixture-spo-grounded"
    write_provisions(
        provisions_dir=provisions_dir,
        doc_id=doc_id,
        provisions=[
            {
                "anchor_path": anchor,
                "kind": "point",
                "text": provision_text,
                "is_fallback_chunk": False,
                "struct_kind": "enumeration_item",
                "section_role": "normative_unit",
                "fallback_allowed_for_reasoning": True,
            }
        ],
    )
    _write_jsonl(
        raw_spo_dir / doc_id[:2] / f"{doc_id}.jsonl",
        [
            {
                "doc_id": doc_id,
                "provision_anchor": anchor,
                "provision_citation": "controlled test source; not legal authority",
                "extraction_source": "rule_auto",
                "statements": [
                    {
                        "statement_id": "source-bound-candidate",
                        "subject_en": "Ministry",
                        "subject_uk": "Міністерство",
                        "predicate": "requires",
                        "object_en": "annual budget report",
                        "object_uk": "річний бюджетний звіт",
                        "fact_text": SOURCE_BOUND_CANDIDATE_TEXT,
                        "confidence": 0.99,
                        "norm_type": "obligation",
                        "norm_type_canon": "obligation",
                        "action_canon": "requires",
                        "canonical_status": "canonicalized",
                        "source_quote_uk": SOURCE_BOUND_PROVISION_TEXT,
                        "source_quote_start": None,
                        "source_quote_end": None,
                        "grounding_status": "exact_quote",
                        "trust_tier": "normative_fact",
                    },
                    {
                        "statement_id": "forged-quote-control",
                        "subject_en": "Ministry",
                        "subject_uk": "Міністерство",
                        "predicate": "requires",
                        "object_en": "annual budget report",
                        "object_uk": "річний бюджетний звіт",
                        "fact_text": "The Ministry has a forged reporting deadline.",
                        "confidence": 0.99,
                        "norm_type": "obligation",
                        "norm_type_canon": "obligation",
                        "action_canon": "requires",
                        "canonical_status": "canonicalized",
                        "source_quote_uk": "This quotation is absent from the selected provision.",
                        "source_quote_start": 0,
                        "source_quote_end": 1,
                        "grounding_status": "exact_quote",
                        "trust_tier": "normative_fact",
                    },
                ],
            }
        ],
    )
    ground_spo_quotes(
        spo_results_dir=raw_spo_dir,
        provisions_dir=provisions_dir,
        output_dir=grounded_spo_dir,
    )
    build_graph(
        spo_results_dir=grounded_spo_dir,
        provisions_dir=provisions_dir,
        references_dir=None,
        domains_dir=None,
        doc_metadata={},
        db_path=path,
    )

    connection = duckdb.connect(str(path), read_only=True)
    try:
        normative = connection.execute("SELECT fact_id FROM lex_normative_facts").fetchall()
        candidates = connection.execute("SELECT fact_id FROM lex_fact_candidates").fetchall()
    finally:
        connection.close()
    assert normative == []
    assert len(candidates) == 2
    return [str(row[0]) for row in candidates]


def _assert_candidate_search_response(
    body: Mapping[str, object],
    *,
    candidate_fact_ids: set[str],
    source_bound_fact_id: str | None = None,
) -> list[dict[str, object]]:
    raw_results = body.get("results")
    assert isinstance(raw_results, list) and raw_results, (
        "candidate search must project non-empty owner results"
    )
    assert all(isinstance(row, dict) for row in raw_results)
    rows = cast("list[dict[str, object]]", raw_results)
    fact_ids = [str(row.get("fact_id")) for row in rows]
    assert set(fact_ids) <= candidate_fact_ids
    assert body.get("total") == len(rows)
    assert all(row.get("trust_tier") == "search_candidate" for row in rows)
    refusal = body.get("legal_relation_refusal")
    assert isinstance(refusal, dict)
    assert refusal.get("code") == "legal_source_relation_verification_not_established"
    assert refusal.get("status") == "verification_missing"
    if source_bound_fact_id is not None:
        source_bound_rows = [row for row in rows if row.get("fact_id") == source_bound_fact_id]
        assert source_bound_rows
        assert any(row.get("fact_text") == SOURCE_BOUND_CANDIDATE_TEXT for row in source_bound_rows)
        assert any(
            row.get("source_quote_uk") == SOURCE_BOUND_PROVISION_TEXT
            and row.get("provision_anchor") == SOURCE_BOUND_PROVISION_ANCHOR
            and row.get("doc_id") == CONTROLLED_DOC_ID
            for row in source_bound_rows
        )
    return rows


def _assert_refused_text_fallback(
    body: Mapping[str, object],
    *,
    request_body: Mapping[str, object],
    expected_query_generation_intent: list[dict[str, object]],
    expected_vector_refusal_code: str,
) -> None:
    """Assert a no-hit text fallback keeps both refusal and request intent."""
    assert body.get("query") == request_body.get("query")
    assert body.get("search_mode") == "text"
    assert body.get("vector_refusal_code") == expected_vector_refusal_code
    assert request_body.get("query_generation_intent") == expected_query_generation_intent
    assert body.get("results") == []
    assert body.get("total") == 0
    relation_refusal = body.get("legal_relation_refusal")
    assert isinstance(relation_refusal, dict)
    assert relation_refusal.get("code") == "legal_source_relation_verification_not_established"
    assert relation_refusal.get("status") == "verification_missing"


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _http_json(
    url: str,
    payload: Mapping[str, object] | None = None,
    *,
    timeout: float = 10,
) -> dict[str, object]:
    response = (
        httpx.get(url, timeout=timeout)
        if payload is None
        else httpx.post(url, json=payload, timeout=timeout)
    )
    response.raise_for_status()
    result = response.json()
    assert isinstance(result, dict)
    return cast("dict[str, object]", result)


def _write_json(receipt_root: Path, name: str, payload: Mapping[str, object]) -> None:
    (receipt_root / name).write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_process_result(
    receipt_root: Path,
    stem: str,
    *,
    command: list[str],
    return_code: int,
    stdout: str,
    stderr: str,
    elapsed_seconds: float,
) -> None:
    (receipt_root / f"{stem}.stdout.txt").write_text(stdout, encoding="utf-8")
    (receipt_root / f"{stem}.stderr.txt").write_text(stderr, encoding="utf-8")
    _write_json(
        receipt_root,
        f"{stem}.process.json",
        {
            "command": command,
            "cwd": str(POLICY_ENGINE_ROOT),
            "elapsed_seconds": round(elapsed_seconds, 6),
            "return_code": return_code,
        },
    )


def _captured_output(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value or ""


@contextmanager
def _runtime_server(
    *,
    python: Path,
    env: dict[str, str],
    output_root: Path,
    log_path: Path,
    profile_root: Path | None,
) -> Iterator[str]:
    port = _free_loopback_port()
    command = [
        str(python),
        "-m",
        "polisyos.runtime.http.profiled_server",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--cas-root",
        str(output_root / "cas"),
        "--core-runs-root",
        str(output_root / "core-runs"),
    ]
    if profile_root is not None:
        command.extend(["--runtime-material-profile-root", str(profile_root)])
    started = time.monotonic()
    process_receipt = log_path.with_suffix(".process.json")
    _write_json(
        process_receipt.parent,
        process_receipt.name,
        {
            "command": command,
            "cwd": str(POLICY_ENGINE_ROOT),
            "profile_root": str(profile_root) if profile_root is not None else None,
        },
    )
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=POLICY_ENGINE_ROOT,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        base_url = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                return_code = process.poll()
                if return_code is not None:
                    log_file.flush()
                    pytest.fail(f"Runtime server exited {return_code}: {log_path.read_text()}")
                try:
                    response = _http_json(f"{base_url}/ready")
                except (httpx.HTTPError, TimeoutError, OSError):
                    time.sleep(0.2)
                    continue
                if response.get("status") == "ready":
                    break
            else:
                log_file.flush()
                pytest.fail(f"Runtime server did not become ready: {log_path.read_text()}")
            yield base_url
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            _write_json(
                process_receipt.parent,
                process_receipt.name,
                {
                    "command": command,
                    "cwd": str(POLICY_ENGINE_ROOT),
                    "elapsed_seconds": round(time.monotonic() - started, 6),
                    "profile_root": str(profile_root) if profile_root is not None else None,
                    "return_code": process.returncode,
                },
            )


def test_ordinary_legal_cli_generation_preserves_candidate_default_exclusion(
    tmp_path: Path,
) -> None:
    receipt_value = os.environ.get("POLISYOS_I4_RECEIPT_DIR")
    if not receipt_value:
        pytest.fail("Set POLISYOS_I4_RECEIPT_DIR to retain the deciding I4 outputs.")
    receipt_root = Path(receipt_value).expanduser().resolve()
    receipt_root.mkdir(parents=True, exist_ok=True)
    if (
        not (PROFILE_ROOT / "hf-cache").is_dir()
        or not (PROFILE_ROOT / "asset-file-manifest.txt").is_file()
    ):
        pytest.skip("The source-qualified local C12 Legal profile is unavailable.")
    python = PROFILE_ROOT / "venv/bin/python"
    if not python.is_file():
        pytest.skip("The source-qualified C12 Python environment is unavailable.")

    manifest_path = PROFILE_ROOT / "asset-file-manifest.txt"
    manifest_bytes = manifest_path.read_bytes()
    _write_json(
        receipt_root,
        "profile-inputs.json",
        {
            "fixture": "controlled source whose unverified Legal facts remain candidates",
            "manifest_path": str(manifest_path.resolve()),
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "manifest_size_bytes": len(manifest_bytes),
            "profile_root": str(PROFILE_ROOT.resolve()),
            "python": str(python.resolve()),
            "python_invocation_path": str(python),
            "working_directory": str(POLICY_ENGINE_ROOT),
        },
    )

    output_root = receipt_root / "producer-output"
    output_root.mkdir()
    db_path = output_root / "lex_knowledge_graph.duckdb"
    candidate_fact_ids = set(_prepare_graph_database(db_path))
    with duckdb.connect(str(db_path), read_only=True) as connection:
        source_bound_row = connection.execute(
            "SELECT fact_id FROM lex_fact_candidates WHERE fact_text = ?",
            [SOURCE_BOUND_CANDIDATE_TEXT],
        ).fetchone()
    assert source_bound_row is not None
    source_bound_fact_id = str(source_bound_row[0])
    assert source_bound_fact_id in candidate_fact_ids

    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": os.pathsep.join(
                (str(POLICY_ENGINE_ROOT / "src"), str(POLICY_ENGINE_ROOT))
            ),
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "POLISYOS_EXECUTION_PROFILE": "dev",
            "POLISYOS_ENABLE_DEV_FIXTURE_IDENTITY": "true",
            "POLISYOS_OTEL_ENABLED": "false",
        }
    )
    otlp_environment_variables = (
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
        "OTEL_EXPORTER_OTLP_HEADERS",
        "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
        "OTEL_EXPORTER_OTLP_METRICS_HEADERS",
        "OTEL_EXPORTER_OTLP_LOGS_HEADERS",
    )
    for variable_name in otlp_environment_variables:
        env.pop(variable_name, None)
    _write_json(
        receipt_root,
        "selected-environment.json",
        {
            key: env[key]
            for key in (
                "HF_HUB_OFFLINE",
                "TRANSFORMERS_OFFLINE",
                "TOKENIZERS_PARALLELISM",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS",
                "PYTHONDONTWRITEBYTECODE",
                "PYTHONPATH",
                "POLISYOS_EXECUTION_PROFILE",
                "POLISYOS_ENABLE_DEV_FIXTURE_IDENTITY",
                "POLISYOS_OTEL_ENABLED",
            )
        }
        | {"otlp_environment_variables_unset": list(otlp_environment_variables)},
    )
    producer_command = [
        str(python),
        "-m",
        "polisyos.data_forge.domains.legal.batch",
        "embed-local",
        "--output-dir",
        str(output_root),
        "--db-path",
        str(db_path),
        "--runtime-material-profile-root",
        str(PROFILE_ROOT),
    ]
    producer_started = time.monotonic()
    try:
        producer = subprocess.run(
            producer_command,
            cwd=POLICY_ENGINE_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        _write_process_result(
            receipt_root,
            "producer-timeout",
            command=producer_command,
            return_code=124,
            stdout=_captured_output(exc.stdout),
            stderr=_captured_output(exc.stderr),
            elapsed_seconds=time.monotonic() - producer_started,
        )
        raise
    _write_process_result(
        receipt_root,
        "producer",
        command=producer_command,
        return_code=producer.returncode,
        stdout=producer.stdout,
        stderr=producer.stderr,
        elapsed_seconds=time.monotonic() - producer_started,
    )
    assert producer.returncode == 0, (
        f"Legal CLI failed ({producer.returncode})\n"
        f"stdout:\n{producer.stdout}\nstderr:\n{producer.stderr}"
    )

    anonymous_env = dict(env)
    anonymous_env.pop("POLISYOS_ENABLE_DEV_FIXTURE_IDENTITY", None)
    with _runtime_server(
        python=python,
        env=anonymous_env,
        output_root=receipt_root / "anonymous-server-state",
        log_path=receipt_root / "anonymous-server.log",
        profile_root=PROFILE_ROOT,
    ) as anonymous_base_url:
        anonymous_responses = (
            (
                "search-profile",
                httpx.get(
                    f"{anonymous_base_url}/api/v1/control/lex/search-profile",
                    params={"output_dir": str(output_root)},
                    timeout=10,
                ),
            ),
            (
                "search",
                httpx.post(
                    f"{anonymous_base_url}/api/v1/control/lex/search",
                    json={
                        "query": "state tax budget",
                        "top_k": 5,
                        "output_dir": str(output_root),
                    },
                    timeout=10,
                ),
            ),
        )
        for name, response in anonymous_responses:
            body = response.json()
            assert isinstance(body, dict)
            _write_json(
                receipt_root,
                f"anonymous-{name}.json",
                {"status_code": response.status_code, "body": body},
            )
            assert response.status_code == 401, body
            assert body.get("code") == "missing_access_scope", body

    profile_url = (
        f"/api/v1/control/lex/search-profile?{urlencode({'output_dir': str(output_root)})}"
    )
    with _runtime_server(
        python=python,
        env=env,
        output_root=receipt_root / "profiled-server-state",
        log_path=receipt_root / "profiled-server.log",
        profile_root=PROFILE_ROOT,
    ) as base_url:
        selected = _http_json(f"{base_url}{profile_url}")
        _write_json(receipt_root, "selected-get.json", selected)
        assert selected["status"] == "available"
        raw_intents = selected["query_generation_intent"]
        assert isinstance(raw_intents, list) and len(raw_intents) == 1
        assert isinstance(raw_intents[0], dict)
        intents = cast("list[dict[str, object]]", raw_intents)
        query = "must publish annual budget report by March"
        text_only_graph = LegalKnowledgeGraph(db_path=db_path, index_dir=output_root)
        try:
            assert (
                text_only_graph.text_search(
                    query,
                    top_k=5,
                    trust_tier="search_candidate",
                    include_candidates=True,
                )
                == []
            )
        finally:
            text_only_graph.close()

        request_body: dict[str, object] = {
            "query": query,
            "top_k": 5,
            "output_dir": str(output_root),
            "query_generation_intent": intents,
        }
        default_search = _http_json(
            f"{base_url}/api/v1/control/lex/search",
            request_body,
            timeout=120,
        )
        _write_json(receipt_root, "matching-post.json", default_search)
        assert default_search["search_mode"] == "vector"
        assert default_search["vector_refusal_code"] is None
        result_rows = _assert_candidate_search_response(
            default_search,
            candidate_fact_ids=candidate_fact_ids,
            source_bound_fact_id=source_bound_fact_id,
        )
        without_results = dict(default_search)
        without_results["results"] = []
        with pytest.raises(AssertionError, match="candidate search must project"):
            _assert_candidate_search_response(
                without_results,
                candidate_fact_ids=candidate_fact_ids,
                source_bound_fact_id=source_bound_fact_id,
            )
        _write_json(receipt_root, "matching-candidate-results.json", {"results": result_rows})

        stale_intents = [{**intents[0], "generation_id": "stale-generation"}]
        stale_body = dict(request_body)
        stale_body["query_generation_intent"] = stale_intents
        stale = _http_json(f"{base_url}/api/v1/control/lex/search", stale_body)
        _write_json(receipt_root, "stale-intent-post.json", stale)
        assert request_body["query_generation_intent"] == intents
        assert stale_body["query_generation_intent"] != request_body["query_generation_intent"]
        _assert_refused_text_fallback(
            stale,
            request_body=stale_body,
            expected_query_generation_intent=stale_intents,
            expected_vector_refusal_code="query_profile_stale_or_mismatched",
        )
        selected_after_stale = _http_json(f"{base_url}{profile_url}")
        _write_json(receipt_root, "selected-get-after-stale-post.json", selected_after_stale)
        assert selected_after_stale["status"] == "available"
        assert selected_after_stale["query_generation_intent"] == intents

        with duckdb.connect(str(db_path)) as connection:
            connection.execute(
                "UPDATE lex_facts SET fact_text = ? WHERE fact_id = ?",
                [
                    "Mutated selected Legal member for the typed drift control.",
                    source_bound_fact_id,
                ],
            )
        drift_text_graph = LegalKnowledgeGraph(db_path=db_path, index_dir=output_root)
        try:
            assert (
                drift_text_graph.text_search(
                    query,
                    top_k=5,
                    trust_tier="search_candidate",
                    include_candidates=True,
                )
                == []
            )
        finally:
            drift_text_graph.close()
        member_drift = _http_json(
            f"{base_url}/api/v1/control/lex/search",
            request_body,
        )
        _write_json(receipt_root, "selected-member-drift-post.json", member_drift)
        _assert_refused_text_fallback(
            member_drift,
            request_body=request_body,
            expected_query_generation_intent=intents,
            expected_vector_refusal_code="selected_generation_membership_mismatch",
        )

    with _runtime_server(
        python=python,
        env=env,
        output_root=receipt_root / "profileless-server-state",
        log_path=receipt_root / "profileless-server.log",
        profile_root=None,
    ) as base_url:
        removed_owner = _http_json(f"{base_url}/api/v1/control/lex/search", request_body)
        _write_json(receipt_root, "removed-owner-post.json", removed_owner)
        _assert_refused_text_fallback(
            removed_owner,
            request_body=request_body,
            expected_query_generation_intent=intents,
            expected_vector_refusal_code="query_encoder_assets_unavailable",
        )

    wrong_profile_root = tmp_path / "wrong-profile"
    (wrong_profile_root / "hf-cache").mkdir(parents=True)
    (wrong_profile_root / "asset-file-manifest.txt").write_text(
        '{"revision":"caller-selected"}\n', encoding="utf-8"
    )
    wrong_profile_command = [
        str(python),
        "-m",
        "polisyos.runtime.http.profiled_server",
        "--runtime-material-profile-root",
        str(wrong_profile_root),
    ]
    wrong_profile_started = time.monotonic()
    try:
        wrong_profile = subprocess.run(
            wrong_profile_command,
            cwd=POLICY_ENGINE_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        _write_process_result(
            receipt_root,
            "wrong-profile-server-timeout",
            command=wrong_profile_command,
            return_code=124,
            stdout=_captured_output(exc.stdout),
            stderr=_captured_output(exc.stderr),
            elapsed_seconds=time.monotonic() - wrong_profile_started,
        )
        raise
    _write_process_result(
        receipt_root,
        "wrong-profile-server",
        command=wrong_profile_command,
        return_code=wrong_profile.returncode,
        stdout=wrong_profile.stdout,
        stderr=wrong_profile.stderr,
        elapsed_seconds=time.monotonic() - wrong_profile_started,
    )
    assert wrong_profile.returncode != 0
    assert "query_encoder_runtime_material_not_established" in (
        wrong_profile.stdout + wrong_profile.stderr
    )
