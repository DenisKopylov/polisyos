"""Real-owner free-growth proof for the generic capability-discovery UI."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import threading
import time
import uuid
from collections import Counter
from pathlib import Path

import duckdb
import httpx
import uvicorn
from _helpers.runtime_http import build_runtime_api_env, close_runtime_api_env

from polisyos.runtime.http.container import RuntimeContainerOverrides
from polisyos.runtime.http.services.control_registry_providers import (
    resolve_control_registry_providers,
)
from polisyos.runtime.quality.capability_discovery import LexCapabilityDiscoveryProvider
from polisyos.runtime.quality.capability_index_compiler import (
    CapabilityIndexCompilerConfig,
    build_capability_discovery_snapshot,
    compile_capability_index,
    deterministic_capability_id,
)

SLICE_BASE = "c31c8cec725727637ee986e4541ac7926a553513"
OPENING_DASHBOARD_PATH_COUNT = 1_087
FRONTEND_VITEST_IDENTITY = (
    "src/features/evidence/components/CapabilityDiscoveryPanel.free-growth.test.tsx"
)
LEX_TABLES = (
    "lex_rule_thresholds",
    "lex_normative_facts",
    "lex_temporal_audit",
    "lex_references",
    "lex_entities",
    "lex_amendments",
)


def test_new_legal_norm_owner_row_appears_without_frontend_code_change(
    tmp_path: Path,
) -> None:
    """Grow through Lex/CapabilityIndex and render without a frontend byte edit."""
    product_root = Path(__file__).resolve().parents[3]
    repository_root = Path(_git(product_root, "rev-parse", "--show-toplevel").strip())
    repository_prefix = _git(product_root, "rev-parse", "--show-prefix").strip()
    assert repository_prefix == "policy-engine/"

    opening_paths = tuple(
        line
        for line in _git(
            repository_root,
            "ls-tree",
            "-r",
            "--name-only",
            SLICE_BASE,
            "--",
            "policy-engine/apps/runtime-dashboard/src",
        ).splitlines()
        if line
    )
    assert len(opening_paths) == OPENING_DASHBOARD_PATH_COUNT
    assert "policy-engine/apps/runtime-dashboard/src/App.tsx" in opening_paths

    frontend_before = _source_snapshot(
        repository_root,
        "policy-engine/apps/runtime-dashboard/src",
    )
    backend_before = _source_snapshot(repository_root, "policy-engine/src")

    nonce = uuid.uuid4().hex
    metric = f"ds10_growth_{nonce}"
    threshold_id = f"threshold:ds10:{nonce}"
    owner_construct = f"{metric}_subject_{nonce}"
    generated_ref = deterministic_capability_id(
        owner_construct,
        "lex_norm",
        threshold_id,
        metric,
    )
    generated_bytes = generated_ref.encode("utf-8")
    assert all(generated_bytes not in payload for payload in frontend_before.bytes_by_path.values())
    assert all(generated_bytes not in payload for payload in backend_before.bytes_by_path.values())

    owner_root = tmp_path / "owner_data"
    lex_path = (
        owner_root
        / "lex"
        / "lex-amendment-only-optimized-20260501-v3"
        / "finalize"
        / "lex_knowledge_graph.duckdb"
    )
    lex_path.parent.mkdir(parents=True)
    _create_owner_database_from_real_schema(product_root, lex_path)
    with duckdb.connect(str(lex_path)) as connection:
        _insert_legal_norm(
            connection,
            nonce=nonce,
            metric=metric,
            threshold_id=threshold_id,
            canonical_status="canonicalized",
        )
        _insert_legal_norm(
            connection,
            nonce=f"rejected_{nonce}",
            metric=f"unrelated_{nonce}",
            threshold_id=f"threshold:rejected:{nonce}",
            canonical_status="canonicalized",
        )
        _insert_legal_norm(
            connection,
            nonce=f"quarantined_{nonce}",
            metric=f"quarantined_{nonce}",
            threshold_id=f"threshold:quarantined:{nonce}",
            canonical_status="quarantined",
        )
        _insert_legal_norm(
            connection,
            nonce=f"malformed_{nonce}",
            metric=f"malformed_{nonce}",
            threshold_id=f"threshold:malformed:{nonce}",
            canonical_status="canonicalized",
            hallucination_flags="not-json",
        )

    build = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=owner_root,
            output_dir=tmp_path / "capability_index",
            mode="fixture",
            generated_at="2026-08-26T09:00:00+03:00",
        )
    )
    assert build.capability_index is not None
    owner_rows = build_capability_discovery_snapshot(build.capability_index)
    owner_refs = {row.capability_ref for row in owner_rows}
    assert generated_ref in owner_refs
    assert len(owner_rows) == 2
    assert not any("quarantined" in ref or "malformed" in ref for ref in owner_refs)

    provider = LexCapabilityDiscoveryProvider(capability_index=build.capability_index)
    registry_providers = resolve_control_registry_providers(
        capability_discovery_providers=(provider,)
    )
    runtime_env = build_runtime_api_env(
        tmp_path / "runtime",
        include_test_client=False,
        app_kwargs={
            "container_overrides": RuntimeContainerOverrides(
                control_registry_providers=registry_providers
            )
        },
    )
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            runtime_env["app"],
            host="127.0.0.1",
            port=port,
            log_level="warning",
            lifespan="on",
        )
    )
    server.install_signal_handlers = lambda: None
    thread = threading.Thread(target=server.run, name="ds10-real-runtime", daemon=True)
    thread.start()
    try:
        _wait_until_started(server, thread)
        base_url = f"http://127.0.0.1:{port}"
        response_bytes = _post_search(base_url, generated_ref)
        packet = json.loads(response_bytes)
        assert [item["capability_ref"] for item in packet["results"]] == [generated_ref]
        item = packet["results"][0]
        assert item["discovery_result"]["state"] == "discoverable"
        assert item["execution_result"]["state"] == "not_established"
        assert item["authority_result"]["state"] != "admitted_authority"
        assert "not_established" in item["authority_result"]["reason_codes"]
        assert packet["frontier"]["candidates"][0]["candidate_ref"] == generated_ref
        assert packet["frontier"]["rejected_candidates"]

        frontend_env = {
            **os.environ,
            "VITE_RUNTIME_API_URL": base_url,
            "DS10_CAPABILITY_BASE_URL": base_url,
            "DS10_CAPABILITY_GENERATED_ID": generated_ref,
        }
        completed = subprocess.run(
            [
                "corepack",
                "pnpm",
                "--filter",
                "@polisyos/runtime-dashboard",
                "exec",
                "vitest",
                "run",
                FRONTEND_VITEST_IDENTITY,
            ],
            cwd=product_root,
            env=frontend_env,
            check=False,
            capture_output=True,
            text=True,
            timeout=240,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
    finally:
        server.should_exit = True
        thread.join(timeout=30)
        close_runtime_api_env(runtime_env)

    frontend_after = _source_snapshot(
        repository_root,
        "policy-engine/apps/runtime-dashboard/src",
    )
    assert frontend_after.paths == frontend_before.paths
    assert frontend_after.partition == frontend_before.partition
    assert frontend_after.digests == frontend_before.digests


class _SourceSnapshot:
    def __init__(self, *, root: Path, paths: tuple[str, ...]) -> None:
        self.paths = paths
        self.bytes_by_path = {path: (root / path).read_bytes() for path in paths}
        self.digests = {
            path: hashlib.sha256(payload).hexdigest()
            for path, payload in self.bytes_by_path.items()
        }
        self.partition = dict(
            sorted(Counter(Path(path).suffix or "<extensionless>" for path in paths).items())
        )


def _source_snapshot(repository_root: Path, pathspec: str) -> _SourceSnapshot:
    raw = subprocess.run(
        [
            "git",
            "-C",
            str(repository_root),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            pathspec,
        ],
        check=True,
        capture_output=True,
    ).stdout
    paths = tuple(sorted(path.decode("utf-8") for path in raw.split(b"\0") if path))
    assert paths
    return _SourceSnapshot(root=repository_root, paths=paths)


def _create_owner_database_from_real_schema(product_root: Path, target: Path) -> None:
    owner_indexes = tuple(
        sorted(product_root.glob("production_data/**/lex_knowledge_graph.duckdb"))
    )
    assert owner_indexes, "real Lex owner index is required for the CC15 growth witness"
    source = owner_indexes[0]
    with duckdb.connect(str(target)) as connection:
        escaped_source = source.as_posix().replace("'", "''")
        connection.execute(f"ATTACH '{escaped_source}' AS owner (READ_ONLY)")
        try:
            for table in LEX_TABLES:
                connection.execute(
                    f"CREATE TABLE {table} AS SELECT * FROM owner.{table} WHERE FALSE"  # noqa: S608 -- names come from the closed LEX_TABLES tuple.
                )
        finally:
            connection.execute("DETACH owner")


def _insert_legal_norm(
    connection: duckdb.DuckDBPyConnection,
    *,
    nonce: str,
    metric: str,
    threshold_id: str,
    canonical_status: str,
    hallucination_flags: str = "{}",
) -> None:
    fact_id = f"fact:ds10:{nonce}"
    doc_id = f"doc:ds10:{nonce}"
    subject_id = f"entity:ds10:{nonce}"
    connection.execute(
        """
        INSERT INTO lex_rule_thresholds (
            threshold_id, fact_id, metric, operator, value_decimal, value_text,
            unit, applies_to, metadata, created_at
        ) VALUES (?, ?, ?, '<=', '1', '1', 'unit', ?, '{}', current_timestamp)
        """,
        [threshold_id, fact_id, metric, f"subject_{nonce}"],
    )
    connection.execute(
        """
        INSERT INTO lex_normative_facts (
            fact_id, statement_id, subject_id, predicate, object_id, fact_text,
            confidence, norm_type, action_canon, norm_type_canon, subject_en,
            object_en, source_quote_uk, source_quote_start, source_quote_end,
            thresholds_json, trust_tier, grounding_status, canonical_status,
            reference_resolution_status, structure_quality, constraint_type_canon,
            legal_unit_subtype, route_class, empty_spo_retry_eligible,
            audit_miss_prone, reference_bearing, threshold_bearing,
            fused_confidence, confidence_breakdown_json, consistency_score,
            hallucination_flags_json, quality_band, doc_id, doc_reestr_code,
            doc_name, doc_type, doc_date_acc, doc_status, jurisdiction, top_domain,
            doc_family_id, version_id, provision_anchor, provision_citation,
            effective_from, temporal_state, temporal_resolution_status,
            temporal_source_scope, temporal_source_kind, temporal_confidence,
            temporal_provenance_json, extraction_source, gate_score,
            gate_reason_codes, metadata, created_at
        ) VALUES (
            ?, ?, ?, 'defines', ?, ?, 0.99, 'eligibility', 'define',
            'eligibility', ?, ?, 'owner-grounded quote', 0, 20, '{}',
            'high_confidence_norm', 'grounded', ?, 'resolved', '1.0',
            'threshold', 'article', 'legal_authority', false, false, true, true,
            0.99, '{}', 0.99, ?, 'high', ?, 'ds10', 'DS10 generated norm',
            'law', '2026-01-01', 'active', 'UA', 'policy', ?, ?, '1', 'Art. 1',
            '2026-01-01', 'effective', 'resolved', 'document', 'explicit', 0.99,
            '{}', 'ds10_owner_index', 0.99, '[]', '{}', current_timestamp
        )
        """,
        [
            fact_id,
            f"statement:{nonce}",
            subject_id,
            f"object:{nonce}",
            f"Generated norm {nonce}",
            f"Subject {nonce}",
            f"Object {nonce}",
            canonical_status,
            hallucination_flags,
            doc_id,
            f"doc-family:{nonce}",
            f"version:{nonce}",
        ],
    )
    connection.execute(
        """
        INSERT INTO lex_temporal_audit (
            audit_id, scope, doc_id, fact_id, temporal_state,
            temporal_resolution_status, issue_type, evidence_text_uk, metadata,
            created_at
        ) VALUES (?, 'fact', ?, ?, 'effective', 'resolved', 'none',
                  'owner temporal evidence', '{}', current_timestamp)
        """,
        [f"audit:{nonce}", doc_id, fact_id],
    )
    connection.execute(
        """
        INSERT INTO lex_references (
            reference_id, doc_id, provision_anchor, source_span_start,
            source_span_end, target_raw, ref_type, confidence, metadata, created_at
        ) VALUES (?, ?, '1', 0, 20, 'owner target', 'law', 0.99, '{}',
                  current_timestamp)
        """,
        [f"reference:{nonce}", doc_id],
    )


def _post_search(base_url: str, capability_ref: str) -> bytes:
    body = json.dumps(
        {
            "search": {
                "request_id": "search:ds10-free-growth",
                "query_text": capability_ref,
                "construct_refs": [capability_ref],
                "intent": "capability_discovery",
                "required_layers": ["L3"],
                "authority_purpose": "review_capability_candidates",
                "allowed_modes": ["exact", "lexical"],
                "budget": {"top_k": 1},
                "rule_version": "policyos.ds10.discovery.v1",
            },
            "resource_kinds": ["legal_norm"],
            "audience": "REVIEWER",
        },
        separators=(",", ":"),
    ).encode("utf-8")
    response = httpx.post(
        f"{base_url}/api/v1/control/capabilities/search",
        content=body,
        headers={"content-type": "application/json"},
        timeout=30,
    )
    assert response.status_code == 200
    return response.content


def _wait_until_started(server: uvicorn.Server, thread: threading.Thread) -> None:
    deadline = time.monotonic() + 30
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started and thread.is_alive()


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
