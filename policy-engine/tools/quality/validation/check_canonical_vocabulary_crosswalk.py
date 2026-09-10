"""Recompute the VC1 reference from complete source owners and exercise its gates.

This checker has no ledger dependency. ``--check`` compares the tracked artifact;
``--write`` emits the first version or a reviewed revision. Corruption probes
supply an alternate artifact with ``--artifact`` and must exit nonzero.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from polisyos.runtime.quality import vocabulary_crosswalk as runtime

ROOT = Path(__file__).resolve().parents[3]
REFERENCE = Path("docs/reference/canonical-vocabulary-crosswalk.v1.json")
RESEARCH = "docs/research/policy-operations/"
OWNER = "polisyos.runtime.quality.vocabulary_crosswalk"


def _read(root: Path, relative: str) -> str:
    try:
        return (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"source_unreadable:{relative}") from exc


def _section(text: str, heading: str) -> str:
    lines = text.splitlines()
    positions = [i for i, line in enumerate(lines) if line == heading]
    if len(positions) != 1:
        raise ValueError(f"source_section_ambiguous:{heading}")
    start = positions[0] + 1
    level = len(heading) - len(heading.lstrip("#"))
    end = next(
        (i for i in range(start, len(lines)) if re.match(rf"#{{1,{level}}} ", lines[i])), len(lines)
    )
    return "\n".join(lines[start:end])


def _block(section: str) -> str:
    blocks = re.findall(r"```(?:text|yaml)?\n(.*?)```", section, flags=re.S)
    if len(blocks) != 1:
        raise ValueError("source_block_ambiguous")
    return blocks[0]


def _class(root: Path, relative: str, name: str) -> ast.ClassDef:
    tree = ast.parse(_read(root, relative))
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name]
    if len(classes) != 1:
        raise ValueError(f"source_class_ambiguous:{relative}:{name}")
    return classes[0]


def _enum(root: Path, relative: str, name: str) -> list[str]:
    return [
        str(ast.literal_eval(node.value))
        for node in _class(root, relative, name).body
        if isinstance(node, ast.Assign)
    ]


def _literal(root: Path, relative: str, name: str, field: str) -> list[str]:
    fields = [
        node
        for node in _class(root, relative, name).body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == field
    ]
    if len(fields) != 1 or not isinstance(fields[0].annotation, ast.Subscript):
        raise ValueError(f"source_field_ambiguous:{name}.{field}")
    value = fields[0].annotation.slice
    members = value.elts if isinstance(value, ast.Tuple) else [value]
    return [str(ast.literal_eval(node)) for node in members]


def source_vocabularies(root: Path) -> list[dict[str, Any]]:
    """Enumerate complete declared sections/types, refusing an unreadable denominator."""
    result: list[dict[str, Any]] = []

    def add(
        identity: str,
        owner: str,
        paths: list[str],
        terms: list[str],
        role: str,
        meanings: dict[str, str] | None = None,
    ) -> None:
        if not terms or len(terms) != len(set(terms)):
            raise ValueError(f"source_terms_empty_or_duplicate:{identity}")
        result.append(
            {
                "vocabulary_id": identity,
                "source_owner": owner,
                "source_version": identity.rsplit("@", 1)[1],
                "semantic_role": role,
                "terms": sorted(terms),
                "meanings": meanings or {},
                "source_paths": paths,
            }
        )

    int4 = RESEARCH + "int-r4-performative-effect-update-diagnosis.md"
    movement = _section(_read(root, int4), "### 4.3 Seven terminal primary classes")
    rows = [line.split("|")[1:5] for line in movement.splitlines() if line.startswith("| `")]
    add(
        "SMDV-1@1",
        OWNER + ".MovementClass",
        [int4],
        [row[0].strip().strip("`") for row in rows],
        "movement_source",
        {row[0].strip().strip("`"): row[1].strip() for row in rows},
    )
    ops = RESEARCH + "ops-r5-monitoring-diagnosis-and-adaptation.md"
    coordinate = _block(_section(_read(root, ops), "### 4.3 Governed response coordinates"))
    for prefix, name, enum in [
        ("E", "epistemic", "EpistemicFactor"),
        ("X", "exposure", "ExposureFactor"),
        ("V", "intervention", "InterventionFactor"),
        ("C", "claim", "ClaimFactor"),
    ]:
        pairs = re.findall(rf"\b({prefix}\d+) ([a-z_]+)", coordinate)
        add(
            f"ops.{name}@1",
            OWNER + "." + enum,
            [ops],
            [code for code, _ in pairs],
            "response_coordinate",
            dict(pairs),
        )
    ceiling = "src/polisyos/fabric/evidence/ceiling_relations.py"
    add(
        "fabric.ceiling-dimension@1",
        "polisyos.fabric.evidence.ceiling_relations.CeilingDimension",
        [ceiling, "src/polisyos/fabric/evidence/ceiling_vocabulary.json"],
        _enum(root, ceiling, "CeilingDimension"),
        "scope_relation",
    )
    int2 = RESEARCH + "int-r2-gap-acquisition-cases.md"
    process = _block(_section(_read(root, int2), "### 7.1 Process state machine"))
    add(
        "int-r2.process@candidate-1",
        "INT-R2 demanding-gate process",
        [int2],
        re.findall(r"\b[A-Z][A-Z_]+\b", process),
        "acquisition_process",
    )
    acquisition = "src/polisyos/fabric/evidence/non_data_acquisition.py"
    add(
        "fabric.acquisition-process@1",
        "polisyos.fabric.evidence.non_data_acquisition.NonDataReceipt",
        [acquisition],
        _literal(root, acquisition, "NonDataReceipt", "resolution_state"),
        "acquisition_process",
    )
    int6 = RESEARCH + "int-r6/05-red-first-fixtures-and-phased-deployment.md"
    text6 = _read(root, int6)
    first = re.findall(r"^(?:status|restriction)_id: ([a-z_]+)$", text6, flags=re.M)
    negatives = _section(text6, "### FX-003 — distinct negative states collapsed")
    negative_block = re.search(r"\*\*Source IDs\*\*\s+```text\n(.*?)```", negatives, flags=re.S)
    if negative_block is None:
        raise ValueError("int_r6_negative_ids_missing")
    add(
        "int-r6.semantic@candidate-1",
        "INT-R6 F-013 system semantic identities",
        [int6],
        first + negative_block.group(1).split(),
        "semantic_identity",
    )
    int5 = RESEARCH + "int-r5-decision-authority-validity.md"
    text5 = _read(root, int5)
    section = _section(text5, "### 4.8 `DelegationValidityCertificate`")
    match = re.search(r"local result `([^`]+)`", section)
    if match is None:
        raise ValueError("int_r5_result_union_missing")
    add(
        "int-r5.result@0.1.0-candidate",
        "INT-R5 candidate certificate reducer",
        [int5],
        [x.strip() for x in match.group(1).split("|")],
        "authority_candidate_result",
    )
    lifecycle = _block(_section(text5, "### 8.4 Lifecycle and typed outcomes"))
    lifecycle = lifecycle.replace("PAO_R4_required/received", "PAO_R4_required PAO_R4_received")
    terms = set(re.findall(r"\b[A-Za-z][A-Za-z0-9_]+\b", lifecycle)) - {"where", "applicable"}
    add(
        "int-r5.lifecycle@0.1.0-candidate",
        "INT-R5 candidate certificate reducer",
        [int5],
        sorted(terms),
        "authority_candidate_process",
    )
    cure = _section(text5, "### 4.11 Cure and historical replay")
    add(
        "int-r5.cure@0.1.0-candidate",
        "INT-R5 jurisdiction cure profile",
        [int5],
        [x.strip() for x in _block(cure).strip().split("|")],
        "authority_candidate_result",
    )
    directory = root / RESEARCH / "int-r5"
    if not directory.is_dir():
        raise ValueError("source_unreadable:int-r5-directory")
    reason_paths = [int5] + sorted(
        str(p.relative_to(root)) for p in directory.iterdir() if p.is_file() and p.suffix == ".md"
    )
    reasons = set()
    for path in reason_paths:
        reasons.update(
            re.findall(r"polisyos\.int_r5\.reason\.[^\s`<>@]+@0\.1\.0-candidate", _read(root, path))
        )
    add(
        "int-r5.reason@0.1.0-candidate",
        "INT-R5 candidate reason namespace",
        reason_paths,
        sorted(reasons),
        "authority_candidate_reason",
    )
    return result


def independently_tokenized_sources(root: Path) -> dict[str, set[str]]:
    """Use line/token parsing independently of the primary regex/AST extraction.

    The source coordinates and process tokens have digits (including PAO_R4),
    so alphabetic-only token patterns cannot silently shrink their denominator.
    """
    from typing import get_args

    from polisyos.fabric.evidence.ceiling_relations import CeilingDimension
    from polisyos.fabric.evidence.non_data_acquisition import NonDataReceipt

    def between(path: str, heading: str) -> list[str]:
        lines = _read(root, path).splitlines()
        start = lines.index(heading) + 1
        level = len(heading.split(" ", 1)[0])
        stop = len(lines)
        for index in range(start, len(lines)):
            line = lines[index]
            if line.startswith("#") and len(line.split(" ", 1)[0]) <= level:
                stop = index
                break
        return lines[start:stop]

    def fenced(lines: list[str]) -> list[str]:
        inside = False
        output = []
        for line in lines:
            if line.startswith("```"):
                inside = not inside
            elif inside:
                output.append(line)
        return output

    result = {}
    int4 = RESEARCH + "int-r4-performative-effect-update-diagnosis.md"
    lines = between(int4, "### 4.3 Seven terminal primary classes")
    result["SMDV-1@1"] = set(re.findall(r"^\| `([^`]+)`", "\n".join(lines), flags=re.M))
    ops = RESEARCH + "ops-r5-monitoring-diagnosis-and-adaptation.md"
    words = " ".join(fenced(between(ops, "### 4.3 Governed response coordinates"))).split()
    for prefix, axis in [
        ("E", "epistemic"),
        ("X", "exposure"),
        ("V", "intervention"),
        ("C", "claim"),
    ]:
        result[f"ops.{axis}@1"] = {w for w in words if w[0] == prefix and w[1:].isdigit()}
    result["fabric.ceiling-dimension@1"] = {v.value for v in CeilingDimension}
    result["fabric.acquisition-process@1"] = set(
        get_args(NonDataReceipt.model_fields["resolution_state"].annotation)
    )
    int2 = RESEARCH + "int-r2-gap-acquisition-cases.md"
    words = " ".join(fenced(between(int2, "### 7.1 Process state machine"))).split()
    result["int-r2.process@candidate-1"] = {
        w for w in words if w.isupper() and w.replace("_", "").isalpha()
    }
    int6 = RESEARCH + "int-r6/05-red-first-fixtures-and-phased-deployment.md"
    result["int-r6.semantic@candidate-1"] = {
        line.split(":", 1)[1].strip()
        for line in _read(root, int6).splitlines()
        if line.startswith(("status_id: ", "restriction_id: "))
    }
    lines = between(int6, "### FX-003 — distinct negative states collapsed")
    first_fence = lines.index("```text")
    for line in lines[first_fence + 1 :]:
        if line.startswith("```"):
            break
        result["int-r6.semantic@candidate-1"].add(line.strip())
    int5 = RESEARCH + "int-r5-decision-authority-validity.md"
    lines = between(int5, "### 4.8 `DelegationValidityCertificate`")
    result_line = next(line for line in lines if line.startswith("- local result `"))
    result["int-r5.result@0.1.0-candidate"] = {
        word.strip() for word in result_line.split("`")[1].split("|")
    }
    lines = fenced(between(int5, "### 8.4 Lifecycle and typed outcomes"))
    lifecycle = set()
    for line in lines:
        for word in line.replace("->", " ").split():
            if word == "PAO_R4_required/received":
                lifecycle.update(("PAO_R4_required", "PAO_R4_received"))
            elif word not in {"where", "applicable", "|"}:
                lifecycle.add(word)
    result["int-r5.lifecycle@0.1.0-candidate"] = lifecycle
    lines = fenced(between(int5, "### 4.11 Cure and historical replay"))
    result["int-r5.cure@0.1.0-candidate"] = {
        word for word in " ".join(lines).split() if word != "|"
    }
    # Discover the full file set independently with glob; extraction uses token
    # delimiters instead of the primary qualified-reason regex.
    paths = [root / int5, *(root / RESEARCH / "int-r5").glob("*.md")]
    reasons = set()
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for tail in text.split("polisyos.int_r5.reason.")[1:]:
            slug = tail.split("@", 1)[0]
            if slug and not any(char.isspace() or char in "`<>" for char in slug):
                remainder = tail[len(slug) :]
                if remainder.startswith("@0.1.0-candidate"):
                    reasons.add("polisyos.int_r5.reason." + slug + "@0.1.0-candidate")
    result["int-r5.reason@0.1.0-candidate"] = reasons
    return result


def _rulings() -> dict[str, Any]:
    owner = "polisyos.fabric.evidence.ceiling_relations.CeilingVocabulary"
    return {
        "relation_claim_strength": {
            "mapping": "maximum_claim_strength",
            "comparison_owner": owner + ".strength_order",
            "semantic_owner": None,
            "registered_terms": [],
            "ruling": "conditional_correspondence",
            "reason": "Maximum support language, not evidence class or numeric confidence.",
            "owner_must_supply": [
                "versioned nodes and justified order edges",
                "claim scope",
                "provenance and independent implication verification",
            ],
        },
        "capacity_stages": {
            "mapping": "maximum_commitment_stage",
            "comparison_owner": owner + ".stage_order",
            "semantic_owner": None,
            "registered_terms": [],
            "ruling": "conditional_correspondence",
            "reason": "Commitment stage under capacity; load remains a separate constraint.",
            "owner_must_supply": [
                "versioned stage nodes and justified order edges",
                "load semantics",
                "scope/time and independent capacity evidence",
            ],
        },
        "estimand_binding_strength": {
            "mapping": None,
            "semantic_owner": None,
            "registered_terms": [],
            "ruling": "absent/unallocated",
            "owner_must_supply": [
                "population/contrast/outcome/horizon/intercurrent-event/regime identity",
                "partial order or incomparability",
                "equivalence/transport evidence",
                "provenance/currentness and negative use cases",
            ],
        },
        "legal_normative_write_operations": {
            "mapping": None,
            "semantic_owner": None,
            "registered_terms": [],
            "ruling": "absent/unallocated",
            "owner_must_supply": [
                "separate legal, normative and write-operation namespaces",
                "resource/subject/scope/time",
                "mandate/delegation/value authority",
                "current verifier evidence and cross-plane conjunctions",
            ],
        },
        "assurance_levels": {
            "mapping": None,
            "semantic_owner": None,
            "registered_terms": [],
            "ruling": "absent/unallocated",
            "owner_must_supply": [
                "engagement/subject/criteria/period",
                "level definitions and order",
                "scope/exclusions",
                "issuer independence and negative cases",
                "agreed-upon procedures remain distinct from assurance",
            ],
        },
    }


def _families() -> dict[str, Any]:
    adaptation = "src/polisyos/runtime/quality/adaptation_transition.py"
    acquisition = "src/polisyos/fabric/evidence/non_data_acquisition.py"
    comprehension = "src/polisyos/runtime/quality/operator_comprehension.py"
    multilingual = "src/polisyos/lex/knowledge/multilingual_assurance.py"
    rows = {}
    for name in (
        "AdaptationTransitionRequest",
        "AdaptationDecisionRecord",
        "RestartEvidenceRecord",
        "KPIControlStateSnapshot",
    ):
        rows[name] = {
            "source_path": adaptation,
            "delivered_symbols": [name],
            "relationship": "same_contract_name",
            "equivalence_claimed": False,
        }
    for name, path, symbols in [
        (
            "GapAcquisitionCase",
            acquisition,
            ["GapShapeAssessment", "AcquisitionType", "NonDataRequest"],
        ),
        ("NonDataAcquisition", acquisition, ["NonDataAcquisitionRuntime", "NonDataReceipt"]),
        ("human_comprehension_established", comprehension, ["ComprehensionResult"]),
        (
            "OperatorComprehension",
            comprehension,
            ["ComprehensionCorpus", "TrialEvent", "ComprehensionResult", "InstrumentReceipt"],
        ),
        ("MAEP", multilingual, ["AssurancePacket", "CandidateAssuranceResult", "AssuranceReceipt"]),
        ("MultilingualAuthority", multilingual, ["CandidateAssuranceResult"]),
        ("AuthorityEquivalence", multilingual, ["CandidateAssuranceResult"]),
        ("CoAuthentic", multilingual, ["RTLSourcePack", "CandidateSourceContent"]),
    ]:
        rows[name] = {
            "source_path": path,
            "delivered_symbols": symbols,
            "relationship": "bounded_candidate_mechanism_different_vocabulary",
            "equivalence_claimed": False,
        }
    rows["CoAuthentic"]["relationship"] = "not_equivalent_source_pack_is_not_coauthentic_authority"
    return rows


def _correspondence(identity: str, term: str) -> dict[str, Any]:
    """Name the semantic seam and why a nearest label is not an alias."""
    if identity == "SMDV-1@1":
        mappings = {
            "expected_variation": (
                [],
                "No S13 divergence; only separate predeclared routine assimilation.",
            ),
            "observation_process_change": (
                ["evidence_error"],
                "Preserve policy-caused selection/ascertainment.",
            ),
            "intervention_delivery_or_version": (
                ["implementation_failure"],
                "Planned version change need not be failure.",
            ),
            "behavioral_response": (
                ["strategic_response"],
                "Non-adversarial and intended mediation remain distinct.",
            ),
            "context_or_interference": (
                ["world_change", "regime_error", "coupling_error"],
                "Several accountable destinations may remain; do not choose one from the source class.",
            ),
            "prediction_error": (
                [],
                "S13 attribution is subsequent; diagnosis alone never grants update authority.",
            ),
            "diagnosis_unresolved": (
                ["unattributable", "pending"],
                "Preserve missing discriminator, clock, next evidence and learning freeze.",
            ),
        }
        destinations, limitation = mappings[term]
        return {
            "owner": "polisyos.runtime.quality.design_axes.post_deploy_accountability",
            "nearest_members": destinations,
            "relation": "source_before_destination_not_alias",
            "blocking_noncollapse": limitation,
        }
    if identity.startswith("ops."):
        return {
            "owner": "polisyos.runtime.quality.constrained_response.ResponseFactors",
            "member": term,
            "relation": "exact_versioned_coordinate",
            "blocking_noncollapse": "Axis, exact claim/version and required co-transitions survive.",
        }
    if identity == "fabric.ceiling-dimension@1":
        return {
            "owner": "polisyos.fabric.evidence.ceiling_relations",
            "member": term,
            "relation": "exact_registered_field_relation",
            "blocking_noncollapse": "Unknown terms and incomparable order nodes never become equal.",
        }
    if identity == "int-r2.process@candidate-1":
        delivered = {
            "SHAPE_NOT_ESTABLISHED": "shape_not_established",
            "ADMISSION_REFUSED": "admission_refused",
            "REENTRY_CLOSED": "reentry_closed",
            "REENTRY_PROVISIONAL_REFUSAL": "reentry_provisional_refusal",
        }
        return {
            "owner": "polisyos.fabric.evidence.non_data_acquisition.NonDataReceipt",
            "member": delivered.get(term),
            "relation": "scoped_process_correspondence"
            if term in delivered
            else "producer_missing",
            "blocking_noncollapse": "Process closure never means publication; an absent process receipt is not inferred.",
        }
    if identity == "fabric.acquisition-process@1":
        return {
            "owner": "polisyos.fabric.evidence.non_data_acquisition.NonDataReceipt.resolution_state",
            "member": term,
            "relation": "exact_candidate_process_identity",
            "blocking_noncollapse": "Demanding-gate result remains candidate_process_only.",
        }
    if identity == "int-r6.semantic@candidate-1":
        remedies = {
            "limited": "Retain exact limitation; never confirmed with caveat.",
            "may_not_use_for": "Binding prohibited purpose; never a recommendation.",
            "stale": "Reacquire/revalidate freshness before current use.",
            "superseded": "Identify and follow the successor; preserve historical version.",
            "withdrawn": "Current use is excluded by withdrawal; do not infer simple expiry.",
        }
        return {
            "owner": "INT-R6 F-013 / owning source semantic frame",
            "member": term,
            "relation": "semantic_id_preserved_not_localized",
            "blocking_noncollapse": remedies[term],
        }
    if identity == "int-r5.reason@0.1.0-candidate":
        sibling = (
            "polisyos.eval_safety.certificate_stale@1.0.0"
            if ".certificate_stale@" in term
            else None
        )
        return {
            "owner": "INT-R5 reason family; DS4 consumes registered owner projections",
            "member": term,
            "relation": "semantic_sibling_not_alias" if sibling else "unmapped_candidate_identity",
            "semantic_sibling": sibling,
            "blocking_noncollapse": "Keep namespace/version and issuer/purpose; no bare-slug fallback.",
        }
    return {
        "owner": "INT-R5 competent profile and certificate producer (not appointed here)",
        "member": term,
        "relation": "candidate_identity_only",
        "blocking_noncollapse": "No positive authority, historical rewrite or legal relation-back follows from a candidate term.",
    }


def build_reference(root: Path) -> dict[str, Any]:
    """Derive the reference, with full source hashes and no embedded source copies."""
    vocabularies = source_vocabularies(root)
    entries = []
    for vocabulary in vocabularies:
        for term in vocabulary["terms"]:
            entry = runtime.CrosswalkEntry(
                vocabulary_id=vocabulary["vocabulary_id"],
                source_term=term,
                source_owner=vocabulary["source_owner"],
                source_version=vocabulary["source_version"],
                target_owner=runtime.TARGET_OWNER,
            ).model_dump()
            entries.append(
                {
                    **entry,
                    "target_status_rule": "preserve_existing_owner_value",
                    "correspondence": _correspondence(vocabulary["vocabulary_id"], term),
                    "losses": {"source_identity": "blocking", "display_label": "tolerable"},
                }
            )
    paths = sorted({p for vocabulary in vocabularies for p in vocabulary["source_paths"]})
    return {
        "schema_version": "policyos.canonical_vocabulary_crosswalk.v1",
        "authority_purpose": "candidate_semantic_conservation_only",
        "institutional_signer": None,
        "lane_merge_base": "992aa493f",
        "target_owner": runtime.TARGET_OWNER,
        "target_statuses": sorted(runtime.target_statuses()),
        "loss_policy": {
            **dict.fromkeys(runtime.BLOCKING_DIMENSIONS, "blocking"),
            "display_label": "tolerable",
        },
        "source_sha256": {p: hashlib.sha256(_read(root, p).encode()).hexdigest() for p in paths},
        "vocabularies": vocabularies,
        "row_count": len(entries),
        "entries": entries,
        "movement_registry": runtime.movement_registry(),
        "ceiling_vocabulary_rulings": _rulings(),
        "institutional_family_reconciliation": _families(),
        "unallocated_semantic_identifiers": {
            "int_r6_rendition_relation_ids": "Research prose is not registered legal-source IDs; "
            "jurisdiction owner must supply namespace, terms, source evidence and equality rule.",
        },
        "production_callers": {
            "movement_admission": "polisyos.runtime.quality.constrained_response",
            "projection": "tools.quality.validation.check_canonical_vocabulary_crosswalk",
            "atlas_surface": "deferred to DS12; new dashboard UI surface_out_of_scope",
            "live_monitoring_learning": "deferred to GY-O1/GY-O3; posterior assertion GY-AS3",
        },
    }


def read_reference(root: Path, artifact_path: Path | None = None) -> dict[str, Any]:
    """Read the declared reference or a supplied corrupt-field probe artifact."""
    return json.loads((artifact_path or root / REFERENCE).read_text(encoding="utf-8"))


def runtime_probe_failures() -> list[str]:
    """Remove-property-sensitive probes run real admission and projection code."""
    failures = []
    registry = deepcopy(runtime.movement_registry())
    registry.append({**registry[0], "vocabulary_id": "arbitrary-name-with-no-cause-spelling@1"})
    try:
        runtime.validate_movement_registry(registry)
    except ValueError as exc:
        if str(exc) != "movement_vocabulary_fork":
            failures.append("movement_fork_wrong_reason")
    else:
        failures.append("movement_fork_admitted")
    entry = runtime.CrosswalkEntry(
        vocabulary_id="int-r6.semantic@candidate-1",
        source_term="withdrawn",
        source_owner="INT-R6",
        source_version="candidate-1",
        target_owner=runtime.TARGET_OWNER,
    )
    for loss in runtime.BLOCKING_DIMENSIONS:
        try:
            runtime.project_term(entry, current_status="failed_safe", losses=(loss,))
        except ValueError as exc:
            if str(exc) != f"blocking_loss:{loss}":
                failures.append(f"blocking_loss_wrong_reason:{loss}")
        else:
            failures.append(f"blocking_loss_admitted:{loss}")
    return failures


def production_probe_failures() -> list[str]:
    """Exercise CR2's real consumer with a candidate carrying a forged namespace."""
    from polisyos.runtime.quality import constrained_response as consumer

    failures = []
    if consumer.ResponseEvent.model_fields["movement"].annotation is not runtime.MovementClass:
        failures.append("production_movement_type_fork")
    for field, owner in [
        ("E", runtime.EpistemicFactor),
        ("X", runtime.ExposureFactor),
        ("V", runtime.InterventionFactor),
        ("C", runtime.ClaimFactor),
    ]:
        if consumer.ResponseFactors.model_fields[field].annotation is not owner:
            failures.append(f"production_factor_type_fork:{field}")
    payload = {
        "event_id": "crosswalk-fork-probe",
        "aggregate_id": "crosswalk-probe",
        "sequence": 0,
        "observed_at": "2026-09-10T09:00:00Z",
        "valid_at": "2026-09-10T09:00:00Z",
        "contract_ref": "candidate-contract",
        "claim_ref": "candidate-claim",
        "population_ref": "candidate-population",
        "intervention_version": "candidate-v1",
        "measurement_epoch": "candidate-m1",
        "current": {"E": "E0", "X": "X0", "V": "V0", "C": "C0"},
        "requested": {"E": "E0", "X": "X0", "V": "V0", "C": "C0"},
        "operation": "observe",
        "movement": "expected_variation",
        "movement_vocabulary": "independent-spelling@1",
        "observation": {
            "movement": 0.0,
            "maturity": "mature",
            "health": "valid",
            "expected_denominator": 10,
            "observed_denominator": 10,
        },
    }
    event = consumer.ResponseEvent.model_validate(payload)
    try:
        consumer.assess_response(event)
    except ValueError as exc:
        if str(exc) != "movement_namespace_refused":
            failures.append("production_namespace_wrong_reason")
    else:
        failures.append("production_namespace_fork_admitted")
    return failures


def validate(root: Path, *, artifact: dict[str, Any] | None = None) -> list[str]:
    """Recompute all source sets and every projection, plus structural removal probes."""
    try:
        expected = build_reference(root)
    except (ValueError, OSError, SyntaxError) as exc:
        return [str(exc)]
    try:
        actual = artifact if artifact is not None else read_reference(root)
    except (OSError, ValueError) as exc:
        return [f"reference_unreadable:{exc}"]
    failures = [] if actual == expected else ["reference_drift"]
    source_by_id = {item["vocabulary_id"]: set(item["terms"]) for item in expected["vocabularies"]}
    independent = independently_tokenized_sources(root)
    if independent != source_by_id:
        failures.append("independent_source_denominator_mismatch")
    for identity, enum in [
        ("SMDV-1@1", runtime.MovementClass),
        ("ops.epistemic@1", runtime.EpistemicFactor),
        ("ops.exposure@1", runtime.ExposureFactor),
        ("ops.intervention@1", runtime.InterventionFactor),
        ("ops.claim@1", runtime.ClaimFactor),
    ]:
        live = {member.value for member in enum}
        if live != source_by_id[identity]:
            failures.append(
                f"source_owner_terms_drift:{identity}:"
                f"missing={sorted(source_by_id[identity] - live)}:"
                f"extra={sorted(live - source_by_id[identity])}"
            )
    ceiling_path = "src/polisyos/fabric/evidence/ceiling_vocabulary.json"
    ceiling = json.loads(_read(root, ceiling_path))
    if set(ceiling["relations"]) != source_by_id["fabric.ceiling-dimension@1"]:
        failures.append("ceiling_field_relation_denominator_drift")
    # The second denominator is counted by walking the actual emitted objects,
    # independently of the producer's row_count and the source lists' lengths.
    grouped: dict[str, set[str]] = {}
    for row in actual.get("entries", []):
        grouped.setdefault(row["vocabulary_id"], set()).add(row["source_term"])
    if grouped != source_by_id or sum(map(len, grouped.values())) != actual.get("row_count"):
        failures.append("source_reference_denominator_mismatch")
    for row in expected["entries"]:
        entry = runtime.CrosswalkEntry.model_validate(
            {k: row[k] for k in runtime.CrosswalkEntry.model_fields}
        )
        for status in runtime.target_statuses():
            projection = runtime.project_term(
                entry, current_status=status, losses=("display_label",)
            )
            if projection.target_status != status or projection.source_term != entry.source_term:
                failures.append(
                    f"projection_identity_changed:{entry.vocabulary_id}:{entry.source_term}"
                )
    for family in expected["institutional_family_reconciliation"].values():
        for symbol in family["delivered_symbols"]:
            try:
                _class(root, family["source_path"], symbol)
            except ValueError as exc:
                failures.append(str(exc))
    failures.extend(runtime_probe_failures())
    failures.extend(production_probe_failures())
    return failures


def main() -> int:
    """Run one explicit check/write operation and return the deciding exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--artifact", type=Path)
    args = parser.parse_args()
    if args.write and (args.check or args.artifact):
        parser.error("--write cannot be combined with --check or --artifact")
    if args.write:
        payload = build_reference(ROOT)
        (ROOT / REFERENCE).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    failures = validate(
        ROOT, artifact=read_reference(ROOT, args.artifact) if args.artifact else None
    )
    payload = read_reference(ROOT)
    report = {
        "result": "fail" if failures else "pass",
        "reference": str(REFERENCE),
        "row_count": payload["row_count"],
        "vocabulary_counts": {v["vocabulary_id"]: len(v["terms"]) for v in payload["vocabularies"]},
        "failures": failures,
    }
    print(json.dumps(report, indent=2))  # noqa: T201
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
