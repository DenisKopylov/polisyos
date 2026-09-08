"""Read-only L6 law-status projection probe using an existing real WMR CAS blob."""

from dataclasses import replace
import hashlib
import inspect
import json
from pathlib import Path

from polisyos.pdc import WorldModelRecord
from polisyos.core.canon import from_canonical_bytes
from polisyos.runtime.quality import credal_reference as reference_owner
from polisyos.runtime.quality import grounding_relation as atom_owner
from polisyos.runtime.quality import intervention_substrate as law_owner
from polisyos.lex.knowledge.store import LegalKnowledgeStore


ROOT = Path.cwd()
PATH = ROOT / ".tmp/gy-s-composed-wmr-cas/artifacts/sha256/8b/96/8b96b3761b471ab0d05fb6f7ecd17ebeba9812abcc703b353bdbb70563f494b4.blob"
raw = PATH.read_bytes()
if hashlib.sha256(raw).hexdigest() != PATH.stem:
    raise RuntimeError("wmr CAS bytes mismatch")
wmr = WorldModelRecord.model_validate(from_canonical_bytes(raw))
bundle = law_owner.load_l6_intervention_substrate(ROOT)
paths = law_owner.default_l6_bundle_paths(ROOT)
raw_map = json.loads(paths["lex_intervention_map"].read_text())
source_ids = sorted(bundle.lex_intervention_map)
raw_ids = sorted(raw_map)
if source_ids != raw_ids:
    raise RuntimeError((source_ids, raw_ids))
lex = LegalKnowledgeStore(
    ROOT / reference_owner.DEFAULT_L3_LEX_KG_PATH,
    (ROOT / reference_owner.DEFAULT_L3_LEX_KG_PATH).parent,
    canonical_db_ref_path=reference_owner.DEFAULT_L3_LEX_KG_PATH,
)
resolved = []
for token in source_ids:
    knobs = reference_owner._knob_ids_from_lex_map(bundle.lex_intervention_map[token])
    for knob in knobs:
        result = law_owner.resolve_law_bound_lever(
            bundle, law_token=token, knob_id=knob,
            parameter_value=reference_owner._representative_knob_value(bundle.knob_dictionary[knob]),
            legal_store=lex, world_model_record=wmr,
        )
        resolved.append(result.model_dump(mode="json"))
edges = list(reference_owner._iter_l6_edges(ROOT, world_model_record=wmr))
wmr_edges = list(reference_owner._iter_wmr_edges(wmr))
map_edges = [row for row in edges if row.modality == "L6_LEX_INTERVENTION_MAP"]
if sorted(row.edge_id for row in map_edges) != source_ids:
    raise RuntimeError("L6 map edge denominator mismatch")


def projection(rows):
    index = {row.key: row for row in [*rows, *wmr_edges]}
    versions = reference_owner._component_versions(index, world_model_record=wmr)
    content_hash = reference_owner._reference_hash(
        component_versions=versions, edge_index=index, as_of=reference_owner.DEFAULT_REFERENCE_AS_OF,
    )
    ref = reference_owner.CredalReference(
        schema_version=reference_owner.CREDAL_REFERENCE_SCHEMA_VERSION,
        reference_epoch=f"kref:{content_hash.removeprefix('sha256:')[:16]}",
        reference_hash=content_hash, as_of=reference_owner.DEFAULT_REFERENCE_AS_OF,
        component_versions=versions, essential_edges=index,
    )
    atoms = atom_owner._reference_atoms_from_cg0(ref)
    # Independently enumerate the raw knob-owner × WMR-slot relation, rather than
    # counting the consumer's constructed atoms or its filtered edge dictionaries.
    knob_rows = {row["knob"]["operator_kind"]: row["knob"] for row in resolved}
    if set(knob_rows) != set(bundle.knob_dictionary):
        raise RuntimeError("raw knob owner denominator not covered")
    expected = sorted(
        (operator, (slot.slot_id,))
        for operator, knob in knob_rows.items()
        for slot in wmr.policy_slot_map
        if atom_owner._operator_target_compatible(
            ref, op_id=operator, domain=knob["domain"], target_slot=slot.slot_id,
            explicit_slots=knob["target_world_slots"],
        )
    )
    actual = sorted((atom.signature.op, atom.signature.X_do) for atom in atoms)
    if actual != expected:
        raise RuntimeError({"consumer":actual,"independent_source_product":expected})
    return {
        "semantic_atom_identity_set": actual,
        "independent_raw_knob_x_wmr_slot_identities": expected,
        "identity_sets_equal": True,
        "all_law_scope_confirmed": ref.all_essential_confirmed([row.key for row in map_edges]),
        "map_edges": [row.to_payload() for row in rows if row.modality == "L6_LEX_INTERVENTION_MAP"],
        "atoms": [
            {"atom_id":atom.atom_id,"operator":atom.signature.op,"targets":atom.signature.X_do,
             "admissibility":atom.signature.admissibility,"edge_scope":atom.edge_scope}
            for atom in atoms
        ],
    }


def uncertain(row, *, preserve_association):
    if row.modality != "L6_LEX_INTERVENTION_MAP":
        return row
    reason = "law_mapping_correspondence_not_established"
    completions = reference_owner._incomplete_completions(reason)
    if preserve_association:
        value = row.admissible_completions[0].value
        completions = (
            reference_owner.AdmissibleCompletion("may_exist", value, reason),
            reference_owner.AdmissibleCompletion("may_not_exist", {}, reason),
        )
    return replace(row,status="incomplete",admissible_completions=completions).with_content_hash()


print(json.dumps({
    "scope": "Actual L6 and WMR edge extraction and actual CG0 atom consumer in an isolated L6+WMR view; this is not a complete K_ref and creates no authority/certificate/promotion receipt. L2 forwarding restriction is not changed or bypassed for any production claim.",
    "wmr_blob":str(PATH),"wmr_bytes_sha256":hashlib.sha256(raw).hexdigest(),"wmr_content_hash":wmr.content_hash,
    "source_denominator":str(paths["lex_intervention_map"]),"owner_law_ids":source_ids,"raw_law_ids":raw_ids,
    "law_resolutions":resolved,
    "current":projection(edges),
    "counterfactual_status_only_empty_completion":projection([uncertain(row,preserve_association=False) for row in edges]),
    "counterfactual_incomplete_with_declared_association":projection([uncertain(row,preserve_association=True) for row in edges]),
    "consumer_source":inspect.getsource(atom_owner._reference_atoms_from_cg0),
    "all_essential_confirmed_source":inspect.getsource(reference_owner.CredalReference.all_essential_confirmed),
},indent=2,sort_keys=True,default=str))
