"""Public legal evaluation transport constraints module API."""
from __future__ import annotations

import re
from collections.abc import Iterable
from enum import Enum
from pathlib import Path
from typing import Any

import duckdb
from pydantic import BaseModel, ConfigDict, Field

_ID_RE = re.compile(r"[^a-z0-9_]+")
_DURATION_RE = re.compile(r"(?P<value>\d+)\s*(?P<unit>m|mo|mon|month|months|y|yr|year|years)")


class ConstraintSeverity(str, Enum):
    """Constraint severity public type."""
    SOFT = "soft"
    HARD = "hard"


class LegalConstraint(BaseModel):
    """Legal constraint relevant for transportability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    constraint_id: str
    description: str
    jurisdiction: str
    legal_source: str
    severity: ConstraintSeverity
    affects_mechanism: bool
    quantitative_impact: str | None = None


class LegalToDAGMappingType(str, Enum):
    """Legal to DAG mapping type public type."""
    EFFECT_MODIFIER = "effect_modifier"
    MECHANISM_NODE = "mechanism_node"
    INTERVENTION_REDEF = "intervention_redef"


class LegalToDAGMapping(BaseModel):
    """Mapping from legal constraint to causal graph elements."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    legal_constraint: LegalConstraint
    mapping_type: LegalToDAGMappingType
    affected_edges: list[tuple[str, str]] = Field(default_factory=list)
    new_node_name: str | None = None
    mechanism_description: str
    confidence_penalty: float = 0.0
    requires_expert_review: bool = True
    rationale: str


class LegalConstraintSet(BaseModel):
    """Grouped legal constraints for one policy in one jurisdiction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    jurisdiction: str
    policy_domain: str
    hard_constraints: list[LegalConstraint] = Field(default_factory=list)
    soft_constraints: list[LegalConstraint] = Field(default_factory=list)
    data_license_constraints: list[LegalConstraint] = Field(default_factory=list)
    legal_dag_mappings: list[LegalToDAGMapping] = Field(default_factory=list)


def is_transport_blocked(constraint_set: LegalConstraintSet) -> bool:
    """Return True when any HARD transportability constraint is present."""
    return any(constraint.severity == ConstraintSeverity.HARD for constraint in constraint_set.hard_constraints)


class _FactContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str = ""
    fact_text: str = ""
    doc_name: str = ""
    doc_reestr_code: str = ""
    provision_citation: str = ""


class LegalConstraintBridge:
    """Bridge from current Lex KG tables to transportability constraints."""

    _DOMAIN_KEYWORDS = {
        "tax_policy": ("подат", "tax", "бюджет", "акциз", "мито"),
        "fiscal": ("подат", "tax", "бюджет", "фінанс"),
        "social": ("соці", "subsid", "допомог", "пільг"),
        "labor": ("праця", "labor", "salary", "заробіт"),
        "health": ("медич", "health", "охорон"),
    }

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path else None

    def get_constraints_for_policy(
        self,
        jurisdiction: str,
        policy_domain: str,
        policy_spec: dict[str, Any],
    ) -> LegalConstraintSet:
        jurisdiction_norm = (jurisdiction or "").strip().upper()
        policy_domain_norm = _normalize_token(policy_domain or "policy")
        facts = self._find_relevant_facts(
            jurisdiction=jurisdiction_norm,
            policy_domain=policy_domain_norm,
            policy_spec=policy_spec,
        )

        hard_constraints: list[LegalConstraint] = []
        soft_constraints: list[LegalConstraint] = []
        data_license_constraints = self._build_data_license_constraints(
            jurisdiction=jurisdiction_norm,
            policy_domain=policy_domain_norm,
            policy_spec=policy_spec,
            facts=facts,
        )

        if _is_truthy(policy_spec.get("retroactive")):
            hard_constraints.append(
                self._make_retroactive_constraint(
                    jurisdiction=jurisdiction_norm,
                    policy_domain=policy_domain_norm,
                    facts=facts,
                )
            )

        transition_months = _parse_transition_months(policy_spec.get("transition_period"))
        if transition_months is not None and transition_months < 6:
            soft_constraints.append(
                self._make_transition_constraint(
                    jurisdiction=jurisdiction_norm,
                    policy_domain=policy_domain_norm,
                    transition_months=transition_months,
                    facts=facts,
                )
            )

        constraints_for_mapping = [
            *hard_constraints,
            *soft_constraints,
            *data_license_constraints,
        ]
        legal_dag_mappings = self.map_constraints_to_dag(
            constraints=constraints_for_mapping,
            causal_graph=policy_spec.get("causal_graph"),
        )

        return LegalConstraintSet(
            jurisdiction=jurisdiction_norm,
            policy_domain=policy_domain_norm,
            hard_constraints=hard_constraints,
            soft_constraints=soft_constraints,
            data_license_constraints=data_license_constraints,
            legal_dag_mappings=legal_dag_mappings,
        )

    def map_constraints_to_dag(
        self,
        constraints: list[LegalConstraint],
        causal_graph: Any,
    ) -> list[LegalToDAGMapping]:
        edges = _extract_edges(causal_graph)
        mappings: list[LegalToDAGMapping] = []
        for constraint in constraints:
            is_mechanism = (
                constraint.affects_mechanism
                or "retroactive" in constraint.constraint_id
                or "transition_period" in constraint.constraint_id
            )
            mapping_type = (
                LegalToDAGMappingType.MECHANISM_NODE
                if is_mechanism
                else LegalToDAGMappingType.EFFECT_MODIFIER
            )
            confidence_penalty = 1.0 if constraint.severity == ConstraintSeverity.HARD else 0.1
            mappings.append(
                LegalToDAGMapping(
                    legal_constraint=constraint,
                    mapping_type=mapping_type,
                    affected_edges=edges,
                    new_node_name=(
                        f"legal_{constraint.constraint_id}_mechanism"
                        if mapping_type == LegalToDAGMappingType.MECHANISM_NODE
                        else None
                    ),
                    mechanism_description=(
                        constraint.quantitative_impact
                        or constraint.description
                        or "Legal applicability modifies target mechanism."
                    ),
                    confidence_penalty=confidence_penalty,
                    requires_expert_review=True,
                    rationale=(
                        f"Mapped from legal constraint '{constraint.constraint_id}' "
                        f"using MVP heuristic bridge."
                    ),
                )
            )
        return mappings

    def _find_relevant_facts(
        self,
        *,
        jurisdiction: str,
        policy_domain: str,
        policy_spec: dict[str, Any],
    ) -> list[_FactContext]:
        if self._db_path is None or not self._db_path.exists():
            return []
        keywords = _collect_keywords(policy_domain=policy_domain, policy_spec=policy_spec)

        try:
            with duckdb.connect(str(self._db_path), read_only=True) as con:
                fact_table = _best_fact_table(con)
                if not fact_table:
                    return []
                has_domains = _table_exists(con, "lex_doc_domains")
                domain_on_fact = _column_exists(con, fact_table, "top_domain")
                text_columns = [
                    column
                    for column in (
                        "fact_text",
                        "condition_text_uk",
                        "procedure_text_uk",
                        "temporal_text_uk",
                        "sanction_text_uk",
                        "exception_text_uk",
                    )
                    if _column_exists(con, fact_table, column)
                ]

                if not keywords and not (policy_domain and (has_domains or domain_on_fact)):
                    return []

                conditions: list[str] = []
                params: list[Any] = []
                for keyword in keywords:
                    pattern = f"%{keyword.lower()}%"
                    for column in text_columns:
                        conditions.append(f"LOWER(COALESCE(f.{column}, '')) LIKE ?")
                        params.append(pattern)

                join_sql = "LEFT JOIN lex_doc_domains d ON d.doc_id = f.doc_id" if has_domains else ""
                domain_clauses: list[str] = []
                if has_domains and policy_domain:
                    domain_clauses.append("LOWER(COALESCE(d.domain, '')) = ?")
                    params.append(policy_domain.lower())
                if domain_on_fact and policy_domain:
                    domain_clauses.append("LOWER(COALESCE(f.top_domain, '')) = ?")
                    params.append(policy_domain.lower())

                where_parts: list[str] = []
                if conditions:
                    where_parts.append(f"({' OR '.join(conditions)})")
                if domain_clauses:
                    where_parts.append(f"({' OR '.join(domain_clauses)})")
                if not where_parts:
                    return []
                where_sql = " OR ".join(where_parts)

                trust_clause = ""
                if fact_table == "lex_facts" and _column_exists(con, fact_table, "trust_tier"):
                    trust_clause = (
                        " AND COALESCE(f.trust_tier, '') "
                        "IN ('grounded_fact', 'normative_fact')"
                    )
                if _column_exists(con, fact_table, "fused_confidence"):
                    trust_clause += " AND COALESCE(f.fused_confidence, 0.0) >= 0.65"

                sql = (
                    "SELECT f.fact_id, f.fact_text, f.doc_name, "
                    "f.doc_reestr_code, f.provision_citation "
                    f"FROM {fact_table} f "
                    f"{join_sql} "
                    f"WHERE {where_sql}{trust_clause} "
                    "LIMIT 100"
                )
                rows = con.execute(sql, params).fetchall()
                return [
                    _FactContext(
                        fact_id=str(row[0] or ""),
                        fact_text=str(row[1] or ""),
                        doc_name=str(row[2] or ""),
                        doc_reestr_code=str(row[3] or ""),
                        provision_citation=str(row[4] or ""),
                    )
                    for row in rows
                ]
        except duckdb.Error:
            return []

    def _make_retroactive_constraint(
        self,
        *,
        jurisdiction: str,
        policy_domain: str,
        facts: list[_FactContext],
    ) -> LegalConstraint:
        return LegalConstraint(
            constraint_id=f"{_normalize_token(jurisdiction)}_{policy_domain}_retroactive_ban",
            description="Retroactive policy application is prohibited in target jurisdiction.",
            jurisdiction=jurisdiction,
            legal_source=_legal_source_from_facts(facts, fallback=f"{jurisdiction}:legal_kg"),
            severity=ConstraintSeverity.HARD,
            affects_mechanism=True,
            quantitative_impact="retroactive = false",
        )

    def _make_transition_constraint(
        self,
        *,
        jurisdiction: str,
        policy_domain: str,
        transition_months: int,
        facts: list[_FactContext],
    ) -> LegalConstraint:
        return LegalConstraint(
            constraint_id=f"{_normalize_token(jurisdiction)}_{policy_domain}_transition_period",
            description=(
                "Transition period appears shorter than legal recommendation "
                f"({transition_months} months)."
            ),
            jurisdiction=jurisdiction,
            legal_source=_legal_source_from_facts(facts, fallback=f"{jurisdiction}:legal_kg"),
            severity=ConstraintSeverity.SOFT,
            affects_mechanism=True,
            quantitative_impact="transition_period >= 6 months",
        )

    def _build_data_license_constraints(
        self,
        *,
        jurisdiction: str,
        policy_domain: str,
        policy_spec: dict[str, Any],
        facts: list[_FactContext],
    ) -> list[LegalConstraint]:
        raw = policy_spec.get("data_license")
        tokens = _license_tokens(raw)
        out: list[LegalConstraint] = []
        for idx, token in enumerate(tokens, start=1):
            if token in {"open", "public", "cc-by", "cc0"}:
                continue
            if token in {"restricted", "proprietary", "nda"}:
                severity = ConstraintSeverity.HARD
                desc = "Dataset license is restricted and blocks automated transport usage."
                impact = "data_license = open_or_registered"
            else:
                severity = ConstraintSeverity.SOFT
                desc = "Dataset license is unclear and requires manual review."
                impact = None
            out.append(
                LegalConstraint(
                    constraint_id=(
                        f"{_normalize_token(jurisdiction)}_{policy_domain}_data_license_{idx}"
                    ),
                    description=desc,
                    jurisdiction=jurisdiction,
                    legal_source=_legal_source_from_facts(
                        facts,
                        fallback=f"{jurisdiction}:dataset_license",
                    ),
                    severity=severity,
                    affects_mechanism=False,
                    quantitative_impact=impact,
                )
            )
        return out


def _extract_edges(causal_graph: Any) -> list[tuple[str, str]]:
    if causal_graph is None:
        return []

    candidate_edges: Iterable[Any]
    if isinstance(causal_graph, dict):
        candidate_edges = (
            causal_graph.get("edges")
            or causal_graph.get("causal_edges")
            or causal_graph.get("links")
            or []
        )
    elif isinstance(causal_graph, list):
        candidate_edges = causal_graph
    else:
        candidate_edges = (
            getattr(causal_graph, "edges", None)
            or getattr(causal_graph, "causal_edges", None)
            or []
        )

    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for edge in candidate_edges:
        pair = _coerce_edge(edge)
        if pair is None or pair in seen:
            continue
        seen.add(pair)
        out.append(pair)
    return out


def _coerce_edge(raw: Any) -> tuple[str, str] | None:
    if isinstance(raw, (tuple, list)) and len(raw) >= 2:
        source = str(raw[0] or "").strip()
        target = str(raw[1] or "").strip()
        if source and target:
            return source, target
    if isinstance(raw, dict):
        source = str(
            raw.get("source") or raw.get("cause") or raw.get("from") or ""
        ).strip()
        target = str(
            raw.get("target") or raw.get("effect") or raw.get("to") or ""
        ).strip()
        if source and target:
            return source, target
    return None


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = ? LIMIT 1",
        [table_name],
    ).fetchone()
    return row is not None


def _column_exists(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    column_name: str,
) -> bool:
    rows = con.execute(
        "SELECT name FROM pragma_table_info(?)",
        [table_name],
    ).fetchall()
    return any(str(row[0] or "") == column_name for row in rows)


def _best_fact_table(con: duckdb.DuckDBPyConnection) -> str:
    for table_name in ("lex_high_confidence_norms", "lex_normative_facts", "lex_fact_grounded", "lex_facts"):
        if _table_exists(con, table_name):
            return table_name
    return ""


def _normalize_token(value: str) -> str:
    lowered = value.strip().lower()
    normalized = _ID_RE.sub("_", lowered).strip("_")
    return normalized or "unknown"


def _collect_keywords(policy_domain: str, policy_spec: dict[str, Any]) -> list[str]:
    keywords = list(LegalConstraintBridge._DOMAIN_KEYWORDS.get(policy_domain, ()))
    raw_domain = str(policy_spec.get("domain") or "").strip().lower()
    if raw_domain and raw_domain != policy_domain:
        keywords.extend(LegalConstraintBridge._DOMAIN_KEYWORDS.get(raw_domain, ()))
    raw_keywords = policy_spec.get("keywords")
    keyword_values = raw_keywords if isinstance(raw_keywords, list) else []
    for raw in keyword_values:
        token = str(raw).strip().lower()
        if token:
            keywords.append(token)
    dedup: list[str] = []
    seen: set[str] = set()
    for token in keywords:
        if token in seen:
            continue
        seen.add(token)
        dedup.append(token)
    return dedup


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _parse_transition_months(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return max(0, int(raw))
    if isinstance(raw, str):
        text = raw.strip().lower()
        if not text:
            return None
        try:
            return max(0, int(text))
        except ValueError:
            pass
        match = _DURATION_RE.search(text)
        if match is None:
            return None
        value = int(match.group("value"))
        unit = match.group("unit")
        if unit in {"y", "yr", "year", "years"}:
            return value * 12
        return value
    return None


def _license_tokens(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        token = raw.strip().lower()
        return [token] if token else []
    if isinstance(raw, dict):
        tokens: list[str] = []
        for value in raw.values():
            tokens.extend(_license_tokens(value))
        return tokens
    if isinstance(raw, list):
        tokens: list[str] = []
        for value in raw:
            tokens.extend(_license_tokens(value))
        return tokens
    return [str(raw).strip().lower()]


def _legal_source_from_facts(facts: list[_FactContext], *, fallback: str) -> str:
    if not facts:
        return fallback
    first = facts[0]
    if first.doc_name and first.provision_citation:
        return f"{first.doc_name}, {first.provision_citation}"
    if first.doc_reestr_code and first.provision_citation:
        return f"{first.doc_reestr_code}, {first.provision_citation}"
    if first.doc_name:
        return first.doc_name
    if first.doc_reestr_code:
        return first.doc_reestr_code
    return fallback


__all__ = [
    "ConstraintSeverity",
    "LegalConstraint",
    "LegalConstraintBridge",
    "LegalConstraintSet",
    "LegalToDAGMapping",
    "LegalToDAGMappingType",
    "is_transport_blocked",
]
