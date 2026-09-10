"""Compare complete declared norms under test and actual consumer store identities."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from polisyos.foundry import LegalSubjectAnnotationSource
from polisyos.lex.knowledge.store import LegalKnowledgeStore
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.intervention_substrate import DEFAULT_L3_LEX_DB_PATH


def main() -> None:
    root = Path.cwd()
    path = root / "architecture/policy_design_case/legal_subject_norm_annotations.synthetic.json"
    raw = json.loads(path.read_bytes())
    typed = LegalSubjectAnnotationSource.model_validate_json(path.read_bytes())
    identities = {row["entity_ref"] for row in raw["annotations"]}
    independently_derived = {row.entity_ref for row in typed.annotations}
    if len(raw["annotations"]) != len(identities) or identities != independently_derived:
        raise ValueError("norm_declaration_denominator_mismatch")
    absolute = LegalKnowledgeStore(root / DEFAULT_L3_LEX_DB_PATH,
                                   (root / DEFAULT_L3_LEX_DB_PATH).parent)
    canonical = LegalKnowledgeStore(root / DEFAULT_L3_LEX_DB_PATH,
                                    (root / DEFAULT_L3_LEX_DB_PATH).parent,
                                    canonical_db_ref_path=DEFAULT_L3_LEX_DB_PATH)
    deltas = []
    for identity in sorted(identities):
        threshold_id = identity.removeprefix("lex_rule_thresholds:")
        left = absolute.resolve_rule_threshold(threshold_id=threshold_id)
        right = canonical.resolve_rule_threshold(threshold_id=threshold_id)
        if left is None or right is None:
            raise ValueError("declared_norm_unreadable")
        left_payload, right_payload = left.model_dump(mode="json"), right.model_dump(mode="json")
        if set(left_payload) != set(right_payload):
            raise ValueError("threshold_field_identity_mismatch")
        changed = {key: {"test_store": left_payload[key], "actual_consumer": right_payload[key]}
                   for key in left_payload if left_payload[key] != right_payload[key]}
        deltas.append({"entity_ref": identity, "field_deltas": changed,
                       "test_content_hash": gy_content_hash(left_payload),
                       "actual_consumer_content_hash": gy_content_hash(right_payload)})
        if set(changed) != {"provision_ref"}:
            raise ValueError("store_configuration_does_not_explain_complete_difference")
    sys.stdout.write(json.dumps({
        "source": str(path.relative_to(root)),
        "denominator": "complete raw and typed norm annotations, all source threshold fields",
        "total": len(identities), "identity_hash": gy_content_hash(sorted(identities)),
        "independent_identity_hash": gy_content_hash(sorted(independently_derived)),
        "identity_difference": sorted(identities ^ independently_derived), "deltas": deltas,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
