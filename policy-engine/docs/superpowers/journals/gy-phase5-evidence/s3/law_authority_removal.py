"""Remove the authority property from an in-memory producer, retaining its markers."""
from __future__ import annotations

import ast
import copy
import inspect
import json
from pathlib import Path

from polisyos.lex.knowledge.store import LegalKnowledgeStore
from polisyos.core.artifacts import FileSystemCAS
from polisyos.runtime.quality import intervention_substrate as owner
from polisyos.runtime.quality.world_model_record import load_world_model_record


def main() -> None:
    root = Path(__file__).resolve().parents[5]
    world = load_world_model_record(FileSystemCAS(root / ".tmp/gy-s-composed-wmr-cas"),
        "sha256:8b96b3761b471ab0d05fb6f7ecd17ebeba9812abcc703b353bdbb70563f494b4")
    bundle = owner.load_l6_intervention_substrate(root)
    manifest = copy.deepcopy(bundle.lex_authority_manifest)
    entries = {row["law_token"]: row for row in manifest["intervention_map_entries"]}
    budget, tax = entries["budget_law"], entries["tax_relief_statute"]
    budget["provision_ref"], tax["provision_ref"] = tax["provision_ref"], budget["provision_ref"]
    changed = owner.replace_intervention_substrate_bundle(bundle, update={"lex_authority_manifest": manifest})
    store = LegalKnowledgeStore(root / owner.DEFAULT_L3_LEX_DB_PATH,
                               (root / owner.DEFAULT_L3_LEX_DB_PATH).parent,
                               canonical_db_ref_path=owner.DEFAULT_L3_LEX_DB_PATH)
    kwargs = dict(law_token=tax["law_token"], knob_id="tax_relief_rate", parameter_value=0.24,
                  legal_store=store, world_model_record=world)
    baseline = owner.resolve_law_bound_lever(changed, **kwargs)
    assert baseline.status == "blocked"
    model = ast.parse(inspect.getsource(owner.LawLeverResolution)).body[0]
    model.body = [node for node in model.body if not isinstance(node, ast.FunctionDef)
                  or node.name != "_current_mapping_authority_requires_evidence"]
    producer = ast.parse(inspect.getsource(owner.resolve_law_bound_lever)).body[0]
    edits = []
    for node in ast.walk(producer):
        if isinstance(node, ast.Dict):
            for index, key in enumerate(node.keys):
                if isinstance(key, ast.Constant) and key.value == "status":
                    edits.append(ast.unparse(node.values[index]))
                    node.values[index] = ast.parse(
                        "'admissible' if evaluation.status == 'admitted' else 'blocked'",
                        mode="eval").body
    assert edits == ["'blocked'"]
    module = ast.fix_missing_locations(ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        model, producer], type_ignores=[]))
    namespace = dict(vars(owner))
    exec(compile(module, "<in_memory_law_authority_removed>", "exec"), namespace)
    broken = namespace["resolve_law_bound_lever"](changed, **kwargs)
    print(json.dumps({"removed_property_source": ast.unparse(module),
                      "baseline": baseline.model_dump(mode="json"),
                      "mutated_producer_output": broken.model_dump(mode="json"),
                      "markers_retained": broken.mapping_evidence_ref is None
                      and broken.mapping_predicate_provenance == "consumer_asserted"}, indent=2))
    assert broken.status == "blocked", "law_correspondence_negative_goes_red_after_property_removal"


if __name__ == "__main__":
    main()
