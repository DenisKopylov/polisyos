"""Declare an outcome-blind held-abstract subset without any provider calls.

Research only. The held database is opened read-only; no abstract text is copied
into the receipt. SQL and Python independently derive the complete eligible set.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import duckdb


def digest(value: object) -> str:
    """Hash a complete canonical JSON value."""
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def main() -> None:
    """Enumerate every held work, reconcile eligibility, and freeze six IDs."""
    source = Path(
        "production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/"
        "scholar_knowledge.duckdb"
    )
    output = Path("docs/superpowers/journals/corr-evidence/c/abstract-subset-manifest.json")
    if output.exists():
        raise ValueError("existing_subset_manifest_must_not_be_overwritten")
    con = duckdb.connect(str(source), read_only=True)
    rows = con.execute("SELECT id, abstract FROM ac_works ORDER BY id").fetchall()
    all_ids = [str(row[0]) for row in rows]
    independently_all = [
        str(row[0])
        for row in con.execute("SELECT DISTINCT id FROM ac_works ORDER BY id").fetchall()
    ]
    if all_ids != independently_all:
        raise ValueError("work_identity_duplicate_or_denominator_mismatch")
    python_eligible: dict[str, tuple[int, str]] = {}
    absent_ids: list[str] = []
    blank_ids: list[str] = []
    ambiguous_ids: list[str] = []
    for work_id, abstract in rows:
        if abstract is None:
            absent_ids.append(str(work_id))
        elif not isinstance(abstract, str):
            ambiguous_ids.append(str(work_id))
        elif not abstract.strip():
            blank_ids.append(str(work_id))
        else:
            python_eligible[str(work_id)] = (
                len(abstract.strip()),
                "sha256:" + hashlib.sha256(abstract.encode()).hexdigest(),
            )
    sql_eligible = {
        str(row[0])
        for row in con.execute(
            "SELECT id FROM ac_works WHERE abstract IS NOT NULL AND regexp_matches(abstract, '\\S')"
        ).fetchall()
    }
    differences = {
        "python_only": sorted(set(python_eligible) - sql_eligible),
        "sql_only": sorted(sql_eligible - set(python_eligible)),
    }
    if any(differences.values()) or ambiguous_ids:
        raise ValueError(json.dumps({"differences": differences, "ambiguous": ambiguous_ids}))
    ordered = sorted(python_eligible, key=lambda key: (python_eligible[key][0], key))
    selected: list[dict[str, object]] = []
    strata: list[dict[str, object]] = []
    for index in range(3):
        members = ordered[len(ordered) * index // 3 : len(ordered) * (index + 1) // 3]
        hash_order = sorted(
            members,
            key=lambda key: hashlib.sha256(
                f"corr-held-abstract-pilot.v1|{key}".encode()
            ).hexdigest(),
        )
        if len(hash_order) < 2:
            raise ValueError("declared_stratum_cannot_supply_two_members")
        strata.append(
            {
                "stratum": index,
                "member_count": len(members),
                "member_identity_digest": digest(sorted(members)),
            }
        )
        for key in hash_order[:2]:
            selected.append(
                {
                    "work_id": key,
                    "stratum": index,
                    "abstract_length": python_eligible[key][0],
                    "abstract_content_hash": python_eligible[key][1],
                    "synthetic": False,
                    "scope": "subset",
                }
            )
    con.close()
    result = {
        "schema_version": "corr.abstract_subset_declaration.v1",
        "scope": "subset",
        "synthetic": False,
        "provider_run_status": "not_started",
        "selection_rule": (
            "nonblank-held-abstract; length-terciles; "
            "two lowest fixed salted ID hashes per tercile; no outcome-based replacement"
        ),
        "source_path": str(source),
        "source_table": "ac_works",
        "source_open_mode": "read_only",
        "source_row_basis_digest": digest(rows),
        "complete_work_count": len(all_ids),
        "complete_work_identity_digest": digest(all_ids),
        "eligible_count": len(python_eligible),
        "eligible_identity_digest": digest(sorted(python_eligible)),
        "independent_sql_eligible_count": len(sql_eligible),
        "identity_differences": differences,
        "null_ids": absent_ids,
        "blank_ids": blank_ids,
        "ambiguous_ids": ambiguous_ids,
        "strata": strata,
        "selected_members": selected,
        "execution_limits": {
            "concurrency": 1,
            "max_phase_calls": 18,
            "transport_attempts_per_call": 1,
            "per_call_timeout_seconds": 120,
        },
        "credential_environment_present": any(
            key == "GONKA_API_KEY"
            or (key.startswith("GONKA_API_KEY_") and key.removeprefix("GONKA_API_KEY_").isdigit())
            for key, value in os.environ.items()
            if value.strip()
        ),
    }
    result["declaration_digest"] = digest(result)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))  # noqa: T201 - capture receipt output


if __name__ == "__main__":
    main()
