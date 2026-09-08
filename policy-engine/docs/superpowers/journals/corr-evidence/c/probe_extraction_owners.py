"""Execute current intake owners without any network call or shared write."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import duckdb

from polisyos.data_forge.domains.academic.batch import article_extractor
from polisyos.data_forge.domains.academic.batch._resolve_extract_contracts import WorkItem
from polisyos.data_forge.domains.academic.batch.resolve_extract import (
    _eligibility_gate,
)


def main() -> None:
    """Report actual declared-subset eligibility and a marked source-presence probe."""
    declaration = json.loads(
        Path("docs/superpowers/journals/corr-evidence/c/abstract-subset-manifest.json").read_text()
    )
    con = duckdb.connect(declaration["source_path"], read_only=True)
    dispositions = []
    for ordinal, selected in enumerate(declaration["selected_members"]):
        row = con.execute(
            "SELECT title,abstract FROM ac_works WHERE id = ?", [selected["work_id"]]
        ).fetchone()
        if row is None:
            raise ValueError("declared_work_missing")
        item = WorkItem(
            work={"id": selected["work_id"], "title": row[0], "abstract": row[1]},
            work_id=selected["work_id"],
            topic_id="",
            topic_ids=[],
            topic_display_names=[],
            prefetch_priority=0.0,
            selected_rank=ordinal,
        )
        disposition = _eligibility_gate(
            item, text=row[1], source_kind="abstract_fallback", text_quality="abstract_only"
        )
        dispositions.append(
            {
                "work_id": selected["work_id"],
                "scope": "subset",
                "synthetic": False,
                "default_resolve_extract": asdict(disposition),
            }
        )
    con.close()
    controls = []
    for present in (False, True):
        payload = {
            "cause_variable": "tax rate",
            "effect_variable": "employment",
            "supporting_spans": [{"section": "results", "text": "Employment fell."}],
        }
        if present:
            payload["evidence_strength"] = "unknown"
        claim = article_extractor._normalize_causal_claim(
            payload,
            work_id="synthetic:corr-intake-presence",
            evidence_bundle={},
            default_source_basis="abstract_only",
        )
        if claim is None:
            raise ValueError("synthetic_presence_probe_claim_not_parsed")
        transport = article_extractor.serialize_rich_claim_occurrence_vocabulary(
            claim, record_extraction_mode="resolve_extract"
        )
        controls.append(
            {
                "synthetic": True,
                "source_field_present": present,
                "normalized_class": claim.evidence_strength.value,
                "transport_class": transport.vocabulary.evidence_strength.value,
                "transport_status": transport.vocabulary.evidence_strength_status.value,
            }
        )
    print(  # noqa: T201 - capture receipt output
        json.dumps(
            {
                "scope": "subset",
                "provider_calls": 0,
                "declaration_digest": declaration["declaration_digest"],
                "held_default_route_dispositions": dispositions,
                "synthetic_source_presence_controls": controls,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
