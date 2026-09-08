"""Measure current CG2 per-decision spend on a declared synthetic exercise."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


def main() -> None:
    """Run the real current binder over existing owner-shaped test controls."""
    root = Path.cwd()
    path = root / "tests/unit/runtime/quality/test_grounding_bind.py"
    spec = importlib.util.spec_from_file_location("corr_a_baseline_fixture", path)
    assert spec is not None and spec.loader is not None
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    reference = fixture._reference()
    engine = fixture.GroundingRelationEngine(reference)
    positive = engine.certificate_for(fixture._pure_synonym_probe(engine), proposal_id="baseline-exact")
    negative = engine.certificate_for(fixture._false_analog_probe(), proposal_id="baseline-mismatch")
    gate = fixture.GroundingBindGate.for_contract_testing(reference, calibration_seed_anchor=True)
    observed = []
    for label, certificate in [("mismatch", negative)] * 5 + [("exact", positive)] * 5:
        decision = gate.certificate_for(certificate)
        observed.append({
            "input": label,
            "decision": decision.decision,
            "reason": decision.decisive_reason,
            "production_promotable": decision.production_promotable,
            "spend": decision.risk_ledger.total_spend,
            "budget": decision.risk_ledger.delta_ground_budget,
            "content_hash": decision.content_hash,
        })
    production = fixture.GroundingBindGate(reference).certificate_for(positive)
    source_paths = [path, root / "src/polisyos/runtime/quality/grounding_bind.py"]
    print(json.dumps({
        "synthetic": True,
        "purpose": "existing_cg2_accounting_baseline_not_calibration",
        "sources": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
        "complete_invocation_denominator": observed,
        "production_control": {
            "decision": production.decision,
            "reason": production.decisive_reason,
            "spend": production.risk_ledger.total_spend,
            "promotable": production.production_promotable,
        },
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
