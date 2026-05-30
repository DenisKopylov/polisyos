"""Deterministic compiler for W7.B legal authority requirements."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from polisyos.legal_requirement._impl.models import (
    LEGAL_AUTHORITY_REQUIREMENT_COMPILER_RULE_VERSION,
    LegalAuthorityRequirementArtifact,
    LegalAuthorityRequirementSpec,
    LegalRequirementFallbackMode,
    LegalRequirementFallbackPolicy,
    LegalScopePredicates,
    TemporalCompetenceWindow,
    normalize_legal_authority_type,
)

_SERIOUS_AUTHORITY_PROFILES = frozenset(
    {
        "governed",
        "official",
        "production",
        "publishable",
        "regulated",
    }
)
_AUTHORITY_REQUIRED_KEYS = frozenset(
    {
        "legal_authority_required",
        "fiscal_authority_required",
        "implementation_authority_required",
        "contestability_authority_required",
    }
)


class LegalAuthorityRequirementCompiler:
    """Compile claim/facet/obligation context into Lex-consumable requirements."""

    def compile(
        self,
        *,
        run_id: str,
        target_context: Mapping[str, Any],
        claims: Sequence[Mapping[str, Any] | object],
        facets: Sequence[Mapping[str, Any] | object] = (),
        obligations: Sequence[Mapping[str, Any] | object] = (),
        jurisdiction_fallback_config: Mapping[str, Any] | None = None,
    ) -> tuple[LegalAuthorityRequirementSpec, ...]:
        """Compile one `LegalAuthorityRequirementSpec` per claim.

        Args:
            run_id: Runtime or compiler run identifier.
            target_context: Request-level jurisdiction, authority profile, and
                time context.
            claims: Claim records or mappings emitted by claim decomposition.
            facets: Optional W6.A facet snapshots.
            obligations: Optional W6.C legal obligations.
            jurisdiction_fallback_config: Governed fallback config snapshot.

        Returns:
            Tuple of strict requirement specs, including out-of-scope specs for
            non-legal claims so downstream Lex cannot mint authority implicitly.
        """

        run_ref = _required_text(run_id)
        target = _mapping(target_context) or {}
        facet_rows = tuple(_mapping(item) or {} for item in facets)
        obligation_rows = tuple(_mapping(item) or {} for item in obligations)
        config = _mapping(jurisdiction_fallback_config) or {}
        return tuple(
            self._compile_claim(
                run_id=run_ref,
                claim=_mapping(claim) or {},
                target_context=target,
                facets=facet_rows,
                obligations=obligation_rows,
                jurisdiction_fallback_config=config,
            )
            for claim in claims
        )

    def _compile_claim(
        self,
        *,
        run_id: str,
        claim: Mapping[str, Any],
        target_context: Mapping[str, Any],
        facets: Sequence[Mapping[str, Any]],
        obligations: Sequence[Mapping[str, Any]],
        jurisdiction_fallback_config: Mapping[str, Any],
    ) -> LegalAuthorityRequirementSpec:
        claim_id = _claim_id(claim)
        claim_ref = _text(claim.get("claim_ref")) or f"claim:{claim_id}"
        authority_types = _required_authority_types(claim)
        mandatory = _claim_requires_legal_authority(claim, target_context) or bool(
            authority_types
        )
        out_of_scope = not mandatory and not authority_types
        if mandatory and not authority_types:
            authority_types = ("implementing",)

        window, time_role = _temporal_window(claim, target_context)
        jurisdiction = _text(
            claim.get("jurisdiction")
            or claim.get("jurisdiction_norm")
            or target_context.get("jurisdiction")
            or target_context.get("jurisdiction_norm")
        )
        instrument_classes = _instrument_classes(claim, facets)
        required_actor_refs = _text_tuple(
            claim.get("required_actor_refs")
            or claim.get("competent_actor_ref")
            or claim.get("competent_authority")
        )
        implementation_refs = _text_tuple(
            claim.get("required_implementation_authority_refs")
            or claim.get("implementation_authority_ref")
            or claim.get("implementation_authority")
            or claim.get("implementation_agency")
        )
        fiscal_refs = _text_tuple(
            claim.get("required_fiscal_authority_refs")
            or claim.get("fiscal_authority_ref")
            or claim.get("fiscal_authority")
        )
        fallback_policy = _fallback_policy(
            mandatory=mandatory,
            out_of_scope=out_of_scope,
            config=jurisdiction_fallback_config,
        )
        return LegalAuthorityRequirementSpec(
            requirement_id=f"legal-requirement:{run_id}:{claim_id}",
            claim_ref=claim_ref,
            claim_id=claim_id,
            mandatory=mandatory,
            out_of_scope=out_of_scope,
            required_hierarchy_depth=_required_hierarchy_depth(claim, obligations),
            temporal_competence_window=TemporalCompetenceWindow(
                start=window.get("start"),
                end=window.get("end"),
                time_role=time_role,
                legal_as_of=_text(
                    claim.get("legal_as_of")
                    or target_context.get("legal_as_of")
                    or target_context.get("as_of")
                    or target_context.get("as_of_iso")
                )
                or None,
            ),
            authority_types=tuple(normalize_legal_authority_type(item) for item in authority_types),
            required_instrument_classes=instrument_classes,
            required_actor_refs=required_actor_refs,
            required_implementation_authority_refs=implementation_refs,
            required_fiscal_authority_refs=fiscal_refs,
            implementation_authority_required=_bool(
                claim.get("implementation_authority_required")
            )
            or "implementing" in authority_types
            or "delegating" in authority_types
            or "enabling" in authority_types,
            fiscal_authority_required=_bool(claim.get("fiscal_authority_required"))
            or "funding" in authority_types,
            contestability_or_appeal_required=_bool(
                claim.get("contestability_authority_required")
            )
            or "appeal_or_contestability" in authority_types
            or "appeals_or_contestability" in authority_types,
            scope_predicates=_scope_predicates(
                claim=claim,
                facets=facets,
                jurisdiction=jurisdiction,
                window=window,
            ),
            fallback_policy=fallback_policy,
            jurisdiction=jurisdiction or None,
            authority_profile_ref=_text(
                claim.get("authority_profile_ref")
                or claim.get("authority_profile")
                or target_context.get("authority_profile_ref")
                or target_context.get("authority_profile")
                or target_context.get("requested_authority_level")
            )
            or None,
            facet_refs=_claim_refs(claim, "facet_refs") or _facet_refs(facets),
            obligation_refs=_claim_refs(claim, "obligation_refs") or _legal_obligation_refs(
                obligations
            ),
            concept_spine_refs=_text_tuple(
                claim.get("concept_spine_refs")
                or claim.get("concept_refs")
                or target_context.get("concept_spine_refs")
                or target_context.get("concept_refs")
            ),
            source_claim_refs=(claim_ref,),
            provenance_refs=_text_tuple(
                claim.get("provenance_ref") or claim.get("provenance_refs")
            ),
            rule_version_ref=LEGAL_AUTHORITY_REQUIREMENT_COMPILER_RULE_VERSION,
            metadata={
                "producer": "legal_authority_requirement_compiler",
                "reuse_classification": "build_new",
                "rejected_reuse": (
                    "Existing Lex W3 adapter derived legal requirements internally; "
                    "W7.B needs a typed producer artifact consumed by Lex."
                ),
            },
        )


def compile_legal_authority_requirements(
    *,
    run_id: str,
    target_context: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any] | object],
    facets: Sequence[Mapping[str, Any] | object] = (),
    obligations: Sequence[Mapping[str, Any] | object] = (),
    jurisdiction_fallback_config: Mapping[str, Any] | None = None,
) -> tuple[LegalAuthorityRequirementSpec, ...]:
    """Compile claim-level legal authority requirements with the default compiler."""

    return LegalAuthorityRequirementCompiler().compile(
        run_id=run_id,
        target_context=target_context,
        claims=claims,
        facets=facets,
        obligations=obligations,
        jurisdiction_fallback_config=jurisdiction_fallback_config,
    )


def compile_legal_authority_requirement_artifact(
    *,
    run_id: str,
    target_context: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any] | object],
    facets: Sequence[Mapping[str, Any] | object] = (),
    obligations: Sequence[Mapping[str, Any] | object] = (),
    jurisdiction_fallback_config: Mapping[str, Any] | None = None,
) -> LegalAuthorityRequirementArtifact:
    """Compile legal requirements into a persistable Lex replay artifact."""

    requirements = compile_legal_authority_requirements(
        run_id=run_id,
        target_context=target_context,
        claims=claims,
        facets=facets,
        obligations=obligations,
        jurisdiction_fallback_config=jurisdiction_fallback_config,
    )
    return LegalAuthorityRequirementArtifact(
        run_id=run_id,
        requirements=requirements,
        target_context=dict(target_context),
        metadata={
            "producer": "legal_authority_requirement_compiler",
            "pattern_guards": list(requirements[0].pattern_refs) if requirements else [],
            "requirement_count": len(requirements),
            "jurisdiction_fallback_config_ref": _text(
                (jurisdiction_fallback_config or {}).get("config_ref")
            )
            or None,
        },
    )


def legal_authority_requirement_audit_surface(
    artifact: LegalAuthorityRequirementArtifact | Mapping[str, Any],
) -> dict[str, Any]:
    """Return an audit/API projection of legal authority requirements."""

    model = (
        artifact
        if isinstance(artifact, LegalAuthorityRequirementArtifact)
        else LegalAuthorityRequirementArtifact.model_validate(dict(artifact))
    )
    payload = model.model_dump(mode="json")
    payload["surface"] = "legal_requirement.audit_surface"
    payload["summary"] = {
        "requirement_count": len(model.requirements),
        "claim_ids": [requirement.claim_id for requirement in model.requirements],
        "mandatory_count": sum(1 for requirement in model.requirements if requirement.mandatory),
        "authority_types": sorted(
            {
                authority_type.value
                for requirement in model.requirements
                for authority_type in requirement.authority_types
            }
        ),
    }
    return payload


def write_legal_authority_requirement_artifact(
    artifact: LegalAuthorityRequirementArtifact | Mapping[str, Any],
    output_dir: str | Path,
) -> Path:
    """Persist a legal authority requirement artifact as deterministic JSON."""

    model = (
        artifact
        if isinstance(artifact, LegalAuthorityRequirementArtifact)
        else LegalAuthorityRequirementArtifact.model_validate(dict(artifact))
    )
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{_slug(model.run_id)}-legal-authority-requirements.json"
    path.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _claim_requires_legal_authority(
    claim: Mapping[str, Any],
    target_context: Mapping[str, Any],
) -> bool:
    if _explicit_false(claim.get("legal_authority_required")) and (
        _text(claim.get("no_legal_authority_rationale"))
        or _text(claim.get("no_normative_anchor_rationale"))
    ):
        return False
    for key in _AUTHORITY_REQUIRED_KEYS:
        if _bool(claim.get(key)):
            return True
    if _required_authority_types(claim):
        return True
    if _text(claim.get("no_legal_authority_rationale")) or _text(
        claim.get("no_normative_anchor_rationale")
    ):
        return False
    profile = _text(
        claim.get("authority_profile")
        or claim.get("requested_authority_level")
        or target_context.get("authority_profile")
        or target_context.get("requested_authority_level")
    ).casefold()
    return bool(profile in _SERIOUS_AUTHORITY_PROFILES and bool(claim.get("major", True)))


def _required_authority_types(claim: Mapping[str, Any]) -> tuple[str, ...]:
    if "required_authority_types" in claim:
        return _text_tuple(claim.get("required_authority_types"))
    if "authority_types" in claim:
        return _text_tuple(claim.get("authority_types"))
    raw = _text_tuple(claim.get("required_authority_types") or claim.get("authority_types"))
    if raw:
        return raw
    if _bool(claim.get("fiscal_authority_required")):
        return ("funding",)
    if _bool(claim.get("implementation_authority_required")):
        return ("implementing",)
    return ()


def _required_hierarchy_depth(
    claim: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
) -> int:
    explicit = _int_or_none(claim.get("required_hierarchy_depth"))
    if explicit is not None:
        return explicit
    depths: list[int] = []
    for obligation in obligations:
        if _text(obligation.get("family")).casefold() != "legal":
            continue
        metadata = _mapping(obligation.get("metadata")) or {}
        depth = _int_or_none(
            obligation.get("required_hierarchy_depth")
            or metadata.get("required_hierarchy_depth")
        )
        if depth is not None:
            depths.append(depth)
    return max(depths) if depths else 1


def _temporal_window(
    claim: Mapping[str, Any],
    target_context: Mapping[str, Any],
) -> tuple[dict[str, str | None], str]:
    for key in ("implementation_period", "policy_effective_window", "fiscal_period"):
        if claim.get(key):
            return _window_payload(claim.get(key)), key
    for key in ("implementation_period", "policy_effective_window"):
        if target_context.get(key):
            return _window_payload(target_context.get(key)), key
    as_of = _text(target_context.get("as_of") or target_context.get("as_of_iso"))
    return {"start": as_of or None, "end": None}, "legal_as_of"


def _instrument_classes(
    claim: Mapping[str, Any],
    facets: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    values = [
        *_text_tuple(
            claim.get("required_instrument_classes")
            or claim.get("instrument_classes")
            or claim.get("policy_instrument")
            or claim.get("instrument_type")
        )
    ]
    for facet in facets:
        if _text(facet.get("facet_type")) == "instrument_type":
            values.extend(_text_tuple(facet.get("value")))
    return _dedupe(values)


def _scope_predicates(
    *,
    claim: Mapping[str, Any],
    facets: Sequence[Mapping[str, Any]],
    jurisdiction: str,
    window: Mapping[str, str | None],
) -> LegalScopePredicates:
    population = list(
        _text_tuple(
            claim.get("population_predicate")
            or claim.get("beneficiary_class")
            or claim.get("target_population")
        )
    )
    geography = list(_text_tuple(claim.get("geography_predicate") or jurisdiction))
    times = list(_text_tuple(claim.get("time_predicate")))
    if window.get("start") or window.get("end"):
        times.append("/".join(item for item in (window.get("start"), window.get("end")) if item))
    for facet in facets:
        facet_type = _text(facet.get("facet_type"))
        value = _text(facet.get("value"))
        if not value:
            continue
        if facet_type == "population_predicate":
            population.append(value)
        elif facet_type == "geography_predicate":
            geography.append(value)
        elif facet_type == "time_predicate":
            times.append(value)
    return LegalScopePredicates(
        population=_dedupe(population),
        geography=_dedupe(geography),
        time=_dedupe(times),
    )


def _fallback_policy(
    *,
    mandatory: bool,
    out_of_scope: bool,
    config: Mapping[str, Any],
) -> LegalRequirementFallbackPolicy:
    if out_of_scope or not mandatory:
        return LegalRequirementFallbackPolicy(mode=LegalRequirementFallbackMode.NOT_APPLICABLE)
    return LegalRequirementFallbackPolicy(
        mode=LegalRequirementFallbackMode.GOVERNED_CONFIG_REQUIRED,
        config_ref=_text(config.get("config_ref")) or None,
        owner=_text(config.get("owner")) or None,
        review_ref=_text(config.get("review_ref")) or None,
    )


def _claim_refs(claim: Mapping[str, Any], key: str) -> tuple[str, ...]:
    return _text_tuple(claim.get(key))


def _facet_refs(facets: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    return _dedupe(_text(facet.get("facet_id")) for facet in facets)


def _legal_obligation_refs(obligations: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    refs = [
        _text(obligation.get("obligation_id") or obligation.get("candidate_id"))
        for obligation in obligations
        if _text(obligation.get("family")).casefold() == "legal"
    ]
    return _dedupe(refs)


def _window_payload(value: object) -> dict[str, str | None]:
    if isinstance(value, Mapping):
        return {
            "start": _text(value.get("start") or value.get("valid_from") or value.get("from"))
            or None,
            "end": _text(value.get("end") or value.get("valid_to") or value.get("to")) or None,
        }
    text = _text(value)
    if not text:
        return {"start": None, "end": None}
    if "/" in text:
        start, end = text.split("/", 1)
        return {"start": _text(start) or None, "end": _text(end) or None}
    return {"start": text, "end": None}


def _mapping(value: object) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump(mode="json")
        except TypeError:
            dumped = model_dump()
        if isinstance(dumped, Mapping):
            return {str(key): item for key, item in dumped.items()}
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        dumped = to_dict()
        if isinstance(dumped, Mapping):
            return {str(key): item for key, item in dumped.items()}
    return None


def _claim_id(claim: Mapping[str, Any]) -> str:
    return _required_text(claim.get("claim_id") or claim.get("id"))


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = _text(value)
        return (text,) if text else ()
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return _dedupe(_text(item) for item in value)
    text = _text(value)
    return (text,) if text else ()


def _dedupe(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return tuple(result)


def _int_or_none(value: object) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "required"}
    return bool(value)


def _explicit_false(value: object) -> bool:
    if isinstance(value, bool):
        return value is False
    if isinstance(value, str):
        return value.strip().casefold() in {"0", "false", "no", "not_required"}
    return False


def _required_text(value: object) -> str:
    text = _text(value)
    if not text:
        raise ValueError("value must be non-empty text")
    return text


def _text(value: object) -> str:
    return str(value or "").strip()


def _slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {".", "_", "-"} else "-" for ch in value)
    return slug.strip("-") or "run"


__all__ = [
    "LegalAuthorityRequirementCompiler",
    "compile_legal_authority_requirement_artifact",
    "compile_legal_authority_requirements",
    "legal_authority_requirement_audit_surface",
    "write_legal_authority_requirement_artifact",
]
