from __future__ import annotations

DEFAULT_SELECTION_POLICY_ID = "lex.versioning_v1.effective_range_then_published_at"
DEFAULT_CONFLICT_POLICY_ID = "policy.conflicts.default_v1"
DEFAULT_TRUST_POLICY_ID = "policy.trust.default_v1"

DEFAULT_EXTRACTOR_ID = "lex.norm_extractor.regex_v1@1.0.0"

NORM_PACK_KIND = "lex.norm_pack"
NORM_CLAIM_SET_KIND = "lex.norms.claim_set"

ASSEMBLY_PIPELINE_ID = "lex.normpack.assembly_v1"
NORM_CLAIM_EXTRACT_PIPELINE_ID = "lex.normpack.extract_norm_claims_v1"

CLAIMS_NORMALIZE_VERSION = "normalize_v1"
CONFLICT_TRUST_ALGORITHM_VERSION = "trust_v1"
CONFLICT_RESOLUTION_ALGORITHM_VERSION = "resolve_v1"

DEFAULT_PREVIEW_LIMIT = 800

DEFAULT_INCLUDE_PART_PROVISIONS = False
DEFAULT_INCLUDE_PARAGRAPH_PROVISIONS = False

DEFAULT_INCLUDED_PROVISION_KINDS: set[str] = {
    "article",
    "point",
    "subpoint",
}
if DEFAULT_INCLUDE_PART_PROVISIONS:
    DEFAULT_INCLUDED_PROVISION_KINDS.add("part")
if DEFAULT_INCLUDE_PARAGRAPH_PROVISIONS:
    DEFAULT_INCLUDED_PROVISION_KINDS.add("paragraph")

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "roads": [
        "дорог",
        "дорога",
        "road",
        "lane",
        "speed",
        "швидк",
        "рух",
        "transport",
        "traffic",
    ],
    "tax": [
        "подат",
        "tax",
        "пдв",
        "vat",
        "income",
        "profit",
    ],
    "labor": [
        "праці",
        "труд",
        "labor",
        "employment",
        "wage",
        "salary",
    ],
}

__all__ = [
    "ASSEMBLY_PIPELINE_ID",
    "CLAIMS_NORMALIZE_VERSION",
    "CONFLICT_RESOLUTION_ALGORITHM_VERSION",
    "CONFLICT_TRUST_ALGORITHM_VERSION",
    "DEFAULT_CONFLICT_POLICY_ID",
    "DEFAULT_EXTRACTOR_ID",
    "DEFAULT_INCLUDE_PARAGRAPH_PROVISIONS",
    "DEFAULT_INCLUDE_PART_PROVISIONS",
    "DEFAULT_INCLUDED_PROVISION_KINDS",
    "DEFAULT_PREVIEW_LIMIT",
    "DEFAULT_SELECTION_POLICY_ID",
    "DEFAULT_TRUST_POLICY_ID",
    "DOMAIN_KEYWORDS",
    "NORM_CLAIM_EXTRACT_PIPELINE_ID",
    "NORM_CLAIM_SET_KIND",
    "NORM_PACK_KIND",
]
