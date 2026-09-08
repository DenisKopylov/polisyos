"""Freeze the historical-source cost target without changing the selected pilot."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from polisyos.data_forge.domains.academic.batch.abstract_reextraction import (
    _digest,
    _load_declared_works,
)


def main() -> None:
    """Reconcile complete held/raw identity sets and persist pre-call weights once."""
    evidence = Path("docs/superpowers/journals/corr-evidence/c")
    manifest = json.loads((evidence / "abstract-subset-manifest.json").read_text())
    _load_declared_works(manifest)
    with duckdb.connect(manifest["source_path"], read_only=True) as db:
        works = db.execute("SELECT id, abstract FROM ac_works ORDER BY id").fetchall()
        raw = db.execute(
            "SELECT id, work_id FROM ac_causal_claims_raw ORDER BY id, work_id"
        ).fetchall()
        ambiguous = [
            row
            for row in raw
            if any(not isinstance(value, str) or not value.strip() for value in row)
        ]
        if ambiguous:
            raise ValueError(f"raw_identity_ambiguous:{ambiguous!r}")
        raw_pairs = set(raw)
        raw_works = {row[1] for row in raw}
        raw_ids = {row[0] for row in raw}
        independent_pairs = set(
            db.execute("SELECT DISTINCT id, work_id FROM ac_causal_claims_raw").fetchall()
        )
        independent_raw = {
            row[0]
            for row in db.execute("SELECT DISTINCT work_id FROM ac_causal_claims_raw").fetchall()
        }
        if raw_pairs != independent_pairs or raw_works != independent_raw:
            raise ValueError("raw_identity_set_mismatch")
        if len(raw_pairs) != len(raw) or len(raw_ids) != len(raw):
            raise ValueError("raw_claim_identity_not_unique")
        eligible = sorted(
            (
                (key, len(text.strip()))
                for key, text in works
                if isinstance(text, str) and text.strip()
            ),
            key=lambda row: (row[1], row[0]),
        )
        groups = [
            {
                row[0]
                for row in eligible[len(eligible) * index // 3 : len(eligible) * (index + 1) // 3]
            }
            for index in range(3)
        ]
        sql_members = set(
            db.execute(
                r"""WITH eligible AS (
                SELECT id, length(regexp_replace(abstract, '^\s+|\s+$', '', 'g')) n
                FROM ac_works WHERE abstract IS NOT NULL AND regexp_matches(abstract, '\S')
            ), numbered AS (
                SELECT id, row_number() OVER (ORDER BY n,id)-1 ordinal,
                       count(*) OVER () denominator FROM eligible
            ) SELECT id, stratum FROM numbered CROSS JOIN range(3) AS s(stratum)
              WHERE ordinal >= (denominator * stratum) // 3
                AND ordinal < (denominator * (stratum+1)) // 3"""
            ).fetchall()
        )
        python_members = {(key, index) for index, group in enumerate(groups) for key in group}
        if python_members != sql_members:
            raise ValueError("complete_stratum_identity_set_mismatch")
        target_groups = [group & raw_works for group in groups]
        independent_target = set(
            db.execute(
                r"""WITH eligible AS (
                SELECT id, length(regexp_replace(abstract, '^\s+|\s+$', '', 'g')) n
                FROM ac_works WHERE abstract IS NOT NULL AND regexp_matches(abstract, '\S')
            ), numbered AS (
                SELECT id, row_number() OVER (ORDER BY n,id)-1 ordinal,
                       count(*) OVER () denominator FROM eligible
            ) SELECT DISTINCT id, stratum FROM numbered CROSS JOIN range(3) AS s(stratum)
              WHERE ordinal >= (denominator * stratum) // 3
                AND ordinal < (denominator * (stratum+1)) // 3
                AND id IN (SELECT work_id FROM ac_causal_claims_raw)"""
            ).fetchall()
        )
        python_target = {(key, index) for index, group in enumerate(target_groups) for key in group}
        if python_target != independent_target:
            raise ValueError("target_stratum_identity_set_mismatch")
        eligible_ids = {row[0] for row in eligible}
        work_ids = {row[0] for row in works}
        target_ids = raw_works & eligible_ids
        unavailable = raw_works - eligible_ids
        no_held_work = raw_works - work_ids
        independent_unavailable = {
            row[0]
            for row in db.execute(
                r"""SELECT DISTINCT work_id FROM ac_causal_claims_raw
                EXCEPT SELECT id FROM ac_works WHERE abstract IS NOT NULL
                    AND regexp_matches(abstract, '\S')"""
            ).fetchall()
        }
        if unavailable != independent_unavailable:
            raise ValueError("unavailable_source_identity_set_mismatch")
    payload = {
        "schema_version": "corr.abstract_cost_target_declaration.v1",
        "declared_at": datetime.now(UTC).isoformat(),
        "provider_run_status": "not_started",
        "synthetic": False,
        "scope": "cost_target_only_no_extraction_authorized",
        "source_path": manifest["source_path"],
        "source_open_mode": "read_only",
        "source_row_basis_digest": manifest["source_row_basis_digest"],
        "raw_claim_id_work_basis_digest": _digest(raw),
        "subset_declaration_digest": manifest["declaration_digest"],
        "selection_change": None,
        "primary_target": "all_eligible_held_ac_works_abstracts",
        "secondary_target": "historical_raw_claim_source_works_with_held_abstracts",
        "target_identity_digest": _digest(sorted(target_ids)),
        "denominators": {
            "held_work_rows": len(works),
            "primary_eligible_abstract_work_ids": len(eligible_ids),
            "raw_claim_rows_and_unique_id_work_pairs": len(raw),
            "raw_claim_unique_ids": len(raw_ids),
            "raw_claim_unique_work_ids": len(raw_works),
            "secondary_target_work_ids": len(target_ids),
            "raw_source_works_without_held_abstract": len(unavailable),
            "eligible_works_without_raw_claim": len(eligible_ids - raw_works),
        },
        "strata": [
            {
                "stratum": index,
                "complete_eligible_member_count": len(groups[index]),
                "secondary_target_member_count": len(group),
                "secondary_target_identity_digest": _digest(sorted(group)),
                "unchanged_pilot_member_count": sum(
                    member["stratum"] == index for member in manifest["selected_members"]
                ),
            }
            for index, group in enumerate(target_groups)
        ],
        "unavailable_abstract_work_ids": sorted(unavailable),
        "raw_source_work_ids_without_held_work": sorted(no_held_work),
        "selected_members_in_raw_claim_source_set": [
            member["work_id"]
            for member in manifest["selected_members"]
            if member["work_id"] in raw_works
        ],
        "independent_complete_identity_sets": {
            "raw_id_work_pairs": "equal",
            "raw_work_ids": "equal",
            "eligible_stratum_members": "equal",
            "target_stratum_members": "equal",
            "unavailable_abstract_work_ids": "equal",
            "difference": [],
            "ambiguous": [],
        },
        "conditional_forecast_assumption": (
            "Exchangeability of provider phase frequencies, token use and wall time within "
            "the unchanged input-length tiers between the selected held-abstract frame "
            "and the historical raw-claim source works. This is an assumption, not measured "
            "exchangeability; no precision guarantee."
        ),
        "unavailable_abstract_cost": "not_established; excluded from conditional forecast",
        "occurrence_reextraction_cost": (
            "not_established; the target counts source works rather than "
            "historical claim occurrences"
        ),
    }
    payload["declaration_digest"] = _digest(payload)
    output = evidence / "historical-source-cost-target.json"
    with output.open("x") as handle:
        handle.write(json.dumps(payload, indent=2) + "\n")
    sys.stdout.write(
        json.dumps(
            {
                "declaration_path": str(output),
                "declaration_digest": payload["declaration_digest"],
                "independent_identity_differences": [],
                "ambiguous": [],
                "provider_calls": 0,
            }
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
