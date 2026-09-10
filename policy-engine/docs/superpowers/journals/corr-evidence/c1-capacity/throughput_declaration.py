"""Predeclare a separate outcome-blind direct-extraction throughput experiment."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SALT = "corr-held-abstract-throughput.v1"
PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."


def digest(value: object) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
    )


def enumerate_frame(source: Path, old: dict[str, Any], *, synthetic: bool) -> dict[str, Any]:
    """Walk all held works and reconcile complete identity/value/tercile sets."""
    import duckdb

    python: dict[str, tuple[int, str]] = {}
    all_ids: set[str] = set()
    absent: list[str] = []
    blank: list[str] = []
    ambiguous: list[str] = []
    with duckdb.connect(str(source), read_only=True) as con:
        con.execute("SET threads=1")
        con.execute("SET memory_limit='512MB'")
        cursor = con.execute("SELECT id,abstract FROM ac_works ORDER BY id")
        while rows := cursor.fetchmany(512):
            for key, text in rows:
                if not isinstance(key, str) or key in all_ids:
                    raise ValueError("throughput_source_identity_ambiguous")
                all_ids.add(key)
                if text is None:
                    absent.append(key)
                elif not isinstance(text, str):
                    ambiguous.append(key)
                elif not text.strip():
                    blank.append(key)
                else:
                    python[key] = (
                        len(text.strip()),
                        "sha256:" + hashlib.sha256(text.encode()).hexdigest(),
                    )
        independent_ids = {
            row[0] for row in con.execute("SELECT DISTINCT id FROM ac_works").fetchall()
        }
        sql_rows = con.execute(r"""
            SELECT id,length(regexp_replace(abstract,'^\s+|\s+$','','g')),sha256(abstract)
            FROM ac_works WHERE abstract IS NOT NULL AND regexp_matches(abstract,'\S')
        """).fetchall()
        sql = {key: (length, "sha256:" + value) for key, length, value in sql_rows}
        if all_ids != independent_ids or python != sql or len(sql_rows) != len(sql) or ambiguous:
            raise ValueError("throughput_complete_frame_reconciliation_failed")
        ordered = sorted(python, key=lambda key: (python[key][0], key))
        groups = [ordered[len(ordered) * i // 3 : len(ordered) * (i + 1) // 3] for i in range(3)]
        sql_tiers = {
            row[0]: row[1]
            for row in con.execute(r"""
            WITH eligible AS (
              SELECT id,length(regexp_replace(abstract,'^\s+|\s+$','','g')) n
              FROM ac_works WHERE abstract IS NOT NULL AND regexp_matches(abstract,'\S')
            ), ranked AS (
              SELECT id,row_number() OVER (ORDER BY n,id)-1 ordinal,count(*) OVER () total
              FROM eligible
            ) SELECT id,CASE WHEN ordinal < floor(total/3.0) THEN 0
              WHEN ordinal < floor(2*total/3.0) THEN 1 ELSE 2 END FROM ranked
        """).fetchall()
        }
    if sql_tiers != {key: tier for tier, group in enumerate(groups) for key in group}:
        raise ValueError("throughput_complete_stratum_identity_mismatch")
    frozen = {row["work_id"] for row in old["selected_members"]}
    if len(frozen) != 6 or not frozen <= all_ids:
        raise ValueError("throughput_frozen_pilot_identity_ambiguous")
    strata = [
        {"stratum": i, "member_count": len(group), "member_identity_digest": digest(sorted(group))}
        for i, group in enumerate(groups)
    ]
    if "strata" in old and strata != old["strata"]:
        raise ValueError("throughput_original_input_terciles_changed")
    chosen = [
        sorted(
            set(group) - frozen,
            key=lambda key: (
                hashlib.sha256(f"{SALT}|{key}".encode()).hexdigest(),
                key,
            ),
        )[:60]
        for group in groups
    ]
    if any(len(group) != 60 for group in chosen):
        raise ValueError("throughput_stratum_cannot_supply_declared_denominator")
    selected = [
        {
            "work_id": key,
            "stratum": tier,
            "abstract_length": python[key][0],
            "abstract_content_hash": python[key][1],
            "synthetic": synthetic,
        }
        for index in range(60)
        for tier in range(3)
        for key in [chosen[tier][index]]
    ]
    return {
        "synthetic": synthetic,
        "authority_status": "candidate_only",
        "source_path": str(source),
        "source_table": "ac_works",
        "source_open_mode": "read_only",
        "complete_work_count": len(all_ids),
        "independent_sql_work_count": len(independent_ids),
        "complete_work_identity_digest": digest(sorted(all_ids)),
        "eligible_count": len(python),
        "independent_sql_eligible_count": len(sql),
        "eligible_identity_digest": digest(sorted(python)),
        "eligible_input_basis_digest": digest(sorted(python.items())),
        "absent_ids": absent,
        "blank_ids": blank,
        "ambiguous_ids": ambiguous,
        "identity_value_reconciliation": "equal_complete_python_and_sql_sets",
        "strata": strata,
        "stratum_reconciliation": "equal_complete_python_and_sql_identity_sets",
        "selected_members": selected,
        "excluded_frozen_pilot_ids": sorted(frozen),
        "selection_salt": SALT,
        "selection_rule": (
            "original input-length terciles; exclude frozen six; "
            "lowest salted ID hashes; round-robin tiers"
        ),
        "selection_uses_outcomes": False,
    }


def read_selected_work(source: Path, member: dict[str, Any]) -> dict[str, Any]:
    """Resolve one held input and independently content-bind it before dispatch."""
    import duckdb

    with duckdb.connect(str(source), read_only=True) as con:
        con.execute("SET threads=1")
        columns = [row[0] for row in con.execute("DESCRIBE ac_works").fetchall()]
        rows = con.execute("SELECT * FROM ac_works WHERE id=?", [member["work_id"]]).fetchall()
        hashes = con.execute(
            "SELECT sha256(abstract) FROM ac_works WHERE id=?", [member["work_id"]]
        ).fetchall()
    if len(rows) != 1 or len(hashes) != 1:
        raise ValueError("throughput_selected_input_binding_mismatch")
    work = dict(zip(columns, rows[0], strict=True))
    abstract = work.get("abstract")
    if not isinstance(abstract, str) or not abstract.strip():
        raise ValueError("throughput_selected_input_binding_mismatch")
    actual = "sha256:" + hashlib.sha256(abstract.encode()).hexdigest()
    if (
        actual != member["abstract_content_hash"]
        or actual != "sha256:" + hashes[0][0]
        or len(abstract.strip()) != member["abstract_length"]
    ):
        raise ValueError("throughput_selected_input_binding_mismatch")
    return work


def main() -> None:
    """Write only declarations; this command never makes an inference request."""
    common = importlib.import_module(PREFIX + "capacity_common")
    admission = importlib.import_module(PREFIX + "throughput_admission")
    from polisyos.data_forge.domains.academic.batch.reextraction_transport import SafeJsonWriter

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="2026-09-09")
    parser.add_argument("--deepseek-contract", type=Path)
    parser.add_argument("--minimax-contract", type=Path)
    parser.add_argument("--deepseek-verdict", type=Path)
    parser.add_argument("--minimax-verdict", type=Path)
    parser.add_argument("--deepseek-configuration", type=Path)
    parser.add_argument("--minimax-configuration", type=Path)
    args = parser.parse_args()
    old_path = common.OLD / "abstract-subset-manifest.json"
    old = json.loads(old_path.read_text())
    frame = enumerate_frame(Path(old["source_path"]), old, synthetic=False)
    declared_at = datetime.now(UTC).isoformat()
    frame = common.seal(
        {
            **frame,
            "schema_version": "corr.throughput_frame.v1",
            "declared_at": declared_at,
            "original_six_declaration_path": str(old_path),
            "original_six_declaration_hash": common.digest(old),
        }
    )
    frame_path = common.EVIDENCE / f"{args.date}-throughput-frame.json"
    execution_sources = admission.execution_projection(Path.cwd())
    writer = SafeJsonWriter(common.load_credential())
    writer(frame_path, frame)
    for slug in ("deepseek", "minimax"):
        contract_path = getattr(args, slug + "_contract") or (
            common.EVIDENCE / f"{args.date}-{slug}-contract-declaration.json"
        )
        contract = common.read_sealed(contract_path)
        configuration_path = getattr(args, slug + "_configuration") or contract_path
        configuration = common.read_sealed(configuration_path)
        if configuration["model_id"] != contract["model_id"]:
            raise ValueError("throughput_configuration_model_mismatch")
        profile = {
            key: configuration[key]
            for key in (
                "model_id",
                "base_url",
                "max_completion_tokens",
                "timeout_seconds",
                "metadata_observation",
                "metadata_observation_hash",
                "live_pricing_usd_per_token",
                "price_observed_at",
                "response_format",
                "temperature",
                "transport",
            )
        }
        verdict_path = getattr(args, slug + "_verdict") or (
            common.EVIDENCE / f"{slug}-contract-verdict.json"
        )
        plan = common.seal(
            {
                **profile,
                "schema_version": "corr.direct_extraction_throughput_declaration.v1",
                "declared_at": declared_at,
                "synthetic": False,
                "authority_status": "candidate_only",
                "purpose": "bounded_direct_extraction_throughput",
                "frame_path": str(frame_path),
                "frame_hash": frame["content_hash"],
                "full_pass_authorized": False,
                "contract_declaration_path": str(contract_path),
                "contract_declaration_hash": contract["content_hash"],
                "configuration_path": str(configuration_path),
                "configuration_hash": configuration["content_hash"],
                "contract_verdict_sha256": admission.bytes_digest(verdict_path.read_bytes()),
                "execution_source_projection": execution_sources,
                "contract_verdict_path": str(verdict_path),
                "response_codec": (
                    "polisyos.data_forge.domains.academic.batch.article_extractor._parse_json_object"
                ),
                "transport_observation_epoch": "policyos.academic.extraction_attempt.v3",
                "sdk_automatic_retries": 0,
                "transport_attempts_per_request": 1,
                "retry_limit": 0,
                "max_total_http_attempts": 180,
                "levels": [
                    {"concurrency": concurrency, "request_count": count, "max_wall_seconds": wall}
                    for concurrency, count, wall in (
                        (1, 12, 2400),
                        (4, 24, 1500),
                        (16, 48, 900),
                        (32, 96, 900),
                    )
                ],
                "resource_caps": {
                    "max_rss_bytes": 3 * 1024**3,
                    "max_disk_write_bytes": 2 * 1024**3,
                    "sample_interval_seconds": 0.25,
                },
                "resource_cap_scope": (
                    "owned worker tree; sampled stops with bounded shutdown; not kernel hard limits"
                ),
                "phase": "direct_extraction_only",
                "typed_owner": contract["typed_owner"],
                "stop_rule": {
                    "plateau_relative_gain_below": 0.20,
                    "error_rate_above": 0.10,
                    "denominator": "all requests in complete current level",
                    "partial_level": "not_established; stop higher levels without knee credit",
                },
                "latency_quantiles": (
                    "linear interpolation median/p95/p99; all terminal and typed successes separate"
                ),
                "memory_analysis": (
                    "OLS summed RSS versus elapsed and completed, warm active interval only"
                ),
                "scope_limitation": (
                    "No screening, self-verification, fulltext acquisition, "
                    "or end-to-end corpus extrapolation."
                ),
                "comparison_limitation": (
                    "Disjoint block sizes confound concurrency with input mix; "
                    "descriptive knee only, no causal optimum or correctness claim."
                ),
                "pricing_claim": (
                    "frozen metadata rate times observed usage; not provider billing proof"
                ),
                "level_assignment": (
                    "disjoint successive blocks 12/24/48/96; same 180 inputs across models"
                ),
                "caching_limitation": (
                    "Repeated-response caching is plausible, not_established. Disjoint blocks "
                    "prevent within-model input repetition; cross-model/provider caching "
                    "remains unknown."
                ),
            }
        )
        output = common.EVIDENCE / f"{args.date}-{slug}-throughput-declaration.json"
        writer(output, plan)
        print(json.dumps({"path": str(output), "content_hash": plan["content_hash"]}))  # noqa: T201


if __name__ == "__main__":
    main()
