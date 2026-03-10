"""Topic/run-aware SKG query helpers for SCM stages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np

from polisyos.academic.knowledge.store import ScholarKnowledgeStore
from polisyos.academic.knowledge.types import (
    BoundaryConditionResult,
    CausalClaimResult,
    ParameterEstimateResult,
    ParameterPrior,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.literature import (
    EvidenceParameter,
    EvidenceStrength,
    ParameterType,
)


@dataclass(frozen=True)
class LiteraturePriorResult:
    variable: str
    prior: ParameterPrior | None
    estimates: list[ParameterEstimateResult]


@dataclass(frozen=True)
class ParameterCandidate:
    parameter: EvidenceParameter
    source_context: ContextProfile | None
    transport_penalty: float = 0.0
    transport_notes: tuple[str, ...] = ()
    requires_expert_review: bool = False


class SKGQuery:
    """Read-only query API for SKG tables in academic DuckDB."""

    def __init__(self, db_path: Path, index_dir: Path) -> None:
        self._db_path = Path(db_path)
        self._store = ScholarKnowledgeStore(db_path, index_dir)
        self._con = duckdb.connect(str(db_path), read_only=True)

    def query_prior(
        self,
        *,
        variable: str,
        domain: str | None = None,
        country: str | None = None,
    ) -> LiteraturePriorResult:
        estimates = self._store.get_parameter_estimates(variable, domain=domain, country=country)
        if not estimates:
            return LiteraturePriorResult(variable=variable, prior=None, estimates=[])

        values = np.array([e.estimate for e in estimates])
        weights = np.array([max(0.01, e.trust_score) for e in estimates])
        weights = weights / weights.sum()

        weighted_mean = float(np.average(values, weights=weights))
        weighted_std = float(np.sqrt(np.average((values - weighted_mean) ** 2, weights=weights)))
        weighted_std = max(weighted_std, 0.01)
        prior_low = float(np.percentile(values, 10))
        prior_high = float(np.percentile(values, 90))

        best_design = sorted(estimates, key=lambda e: e.trust_score, reverse=True)[0].study_design if estimates else ""
        prior = ParameterPrior(
            variable=variable,
            prior_mean=weighted_mean,
            prior_std=weighted_std,
            prior_low=prior_low,
            prior_high=prior_high,
            n_studies=len(estimates),
            best_design=best_design,
            as_calibration_prior={
                "distribution": "normal",
                "mean": weighted_mean,
                "std": weighted_std,
            },
        )
        return LiteraturePriorResult(variable=variable, prior=prior, estimates=estimates)

    def query_claims(
        self,
        *,
        cause: str,
        effect: str,
        min_trust: float = 0.5,
    ) -> list[CausalClaimResult]:
        return self._store.get_causal_claims(cause, effect, min_trust=min_trust)

    def query_boundary_conditions(self, *, work_id: str) -> list[BoundaryConditionResult]:
        return self._store.get_boundary_conditions_for_work(work_id)

    def query_parameters(
        self,
        parameter_name: str,
        *,
        target_context: ContextProfile | None = None,
        limit: int = 256,
    ) -> list[ParameterCandidate]:
        clean_name = str(parameter_name).strip()
        if not clean_name:
            return []

        rows = self._con.execute(
            """
            SELECT parameter_json, context_json
            FROM ac_skg_parameters
            WHERE canonical_name = ?
            LIMIT ?
            """,
            [clean_name, int(limit)],
        ).fetchall()

        result: list[ParameterCandidate] = []
        for parameter_json, context_json in rows:
            payload = self._parse_json_dict(parameter_json)
            if payload is None:
                continue
            parameter = self._to_evidence_parameter(clean_name, payload)
            if parameter is None:
                continue

            source_context = None
            context_payload = self._parse_json_dict(context_json)
            if context_payload is not None:
                try:
                    source_context = ContextProfile.model_validate(context_payload)
                except Exception:
                    source_context = None

            transport_penalty, transport_notes, requires_expert_review = (
                self._transport_metadata_for_parameter(
                    clean_name,
                    source_context=source_context,
                    target_context=target_context,
                )
            )

            result.append(
                ParameterCandidate(
                    parameter=parameter,
                    source_context=source_context,
                    transport_penalty=transport_penalty,
                    transport_notes=tuple(transport_notes),
                    requires_expert_review=requires_expert_review,
                )
            )
        return result

    def _transport_metadata_for_parameter(
        self,
        parameter_name: str,
        *,
        source_context: ContextProfile | None,
        target_context: ContextProfile | None,
    ) -> tuple[float, list[str], bool]:
        notes: list[str] = []
        penalty = 0.0
        requires_expert_review = False

        if source_context is None:
            penalty += 0.15
            notes.append("source_context_missing")
            requires_expert_review = True
        elif not self._context_profile_exists(source_context.context_id):
            penalty += 0.10
            notes.append("source_context_profile_missing")

        if target_context is not None:
            if not self._context_profile_exists(target_context.context_id):
                penalty += 0.10
                notes.append("target_context_profile_missing")
                requires_expert_review = True
            elif not self._has_transport_scores_for_target(target_context.context_id):
                penalty += 0.05
                notes.append("transport_score_unavailable")

        moderation_edges = self._moderation_signal_count(parameter_name)
        if moderation_edges > 0:
            penalty += min(0.25, 0.05 * moderation_edges)
            notes.append(f"moderation_edges:{moderation_edges}")

        return min(0.5, penalty), notes, requires_expert_review

    def _context_profile_exists(self, context_id: str | None) -> bool:
        clean_context_id = str(context_id or "").strip()
        if not clean_context_id or not self._table_exists("ac_skg_context_profiles"):
            return False
        try:
            row = self._con.execute(
                """
                SELECT 1
                FROM ac_skg_context_profiles
                WHERE context_id = ? OR profile_id = ?
                LIMIT 1
                """,
                [clean_context_id, clean_context_id],
            ).fetchone()
        except Exception:
            return False
        return bool(row)

    def _moderation_signal_count(self, parameter_name: str) -> int:
        if not self._table_exists("ac_skg_moderation_edges"):
            return 0
        clean_name = str(parameter_name).strip()
        if not clean_name:
            return 0
        try:
            row = self._con.execute(
                """
                SELECT COUNT(*)
                FROM ac_skg_moderation_edges
                WHERE moderator = ?
                   OR moderator ILIKE ?
                   OR moderator ILIKE ?
                """,
                [clean_name, f"%.{clean_name}", f"{clean_name}.%"],
            ).fetchone()
        except Exception:
            return 0
        return int(row[0]) if row and row[0] is not None else 0

    def _has_transport_scores_for_target(self, target_context_id: str | None) -> bool:
        clean_context_id = str(target_context_id or "").strip()
        if not clean_context_id or not self._table_exists("ac_skg_transport_scores"):
            return False
        try:
            row = self._con.execute(
                """
                SELECT 1
                FROM ac_skg_transport_scores
                WHERE target_context_id = ?
                LIMIT 1
                """,
                [clean_context_id],
            ).fetchone()
        except Exception:
            return False
        return bool(row)

    def _table_exists(self, table_name: str) -> bool:
        try:
            row = self._con.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = ?
                LIMIT 1
                """,
                [str(table_name)],
            ).fetchone()
        except Exception:
            return False
        return bool(row)

    def _column_exists(self, table_name: str, column_name: str) -> bool:
        try:
            row = self._con.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = ? AND column_name = ?
                LIMIT 1
                """,
                [str(table_name), str(column_name)],
            ).fetchone()
        except Exception:
            return False
        return bool(row)

    def query_edge_priors(
        self,
        *,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> list[dict]:
        has_candidate_layer = self._column_exists("ac_skg_edges", "candidate_layer")
        has_quality_json = self._column_exists("ac_skg_edges", "quality_signals_json")
        extra_select = ""
        if has_candidate_layer:
            extra_select += ", candidate_layer"
        if has_quality_json:
            extra_select += ", quality_signals_json"
        rows = self._con.execute(
            f"""
            SELECT edge_id, src, dst, direction, n_articles, article_refs, evidence_strength, confidence
            {extra_select}
            FROM ac_skg_edges
            WHERE confidence >= ?
            ORDER BY confidence DESC
            LIMIT ?
            """,
            [float(min_confidence), int(limit)],
        ).fetchall()
        result: list[dict] = []
        for row in rows:
            payload = {
                "edge_id": str(row[0]),
                "src": str(row[1]),
                "dst": str(row[2]),
                "direction": str(row[3]),
                "n_articles": int(row[4]),
                "article_refs_json": str(row[5]),
                "article_refs": self._parse_json_list(row[5]),
                "evidence_strength": str(row[6]),
                "confidence": float(row[7]),
            }
            idx = 8
            if has_candidate_layer:
                payload["candidate_layer"] = str(row[idx])
                idx += 1
            if has_quality_json:
                payload["quality_signals"] = self._parse_json_dict(row[idx]) or {}
            result.append(payload)
        return result

    @staticmethod
    def _parse_json_list(value: object) -> list[str]:
        try:
            payload = json.loads(str(value or "[]"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        result: list[str] = []
        for item in payload:
            text = str(item).strip()
            if text:
                result.append(text)
        return result

    @staticmethod
    def _parse_json_dict(value: object) -> dict | None:
        if value in (None, ""):
            return None
        if isinstance(value, dict):
            return dict(value)
        try:
            payload = json.loads(str(value))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    @staticmethod
    def _to_evidence_parameter(name: str, payload: dict) -> EvidenceParameter | None:
        try:
            return EvidenceParameter.model_validate(payload)
        except Exception:
            pass

        raw_value = payload.get("value", payload.get("estimate"))
        if raw_value is None:
            return None

        try:
            value = float(raw_value)
        except Exception:
            return None

        confidence_interval: tuple[float, float] | None = None
        ci_low = payload.get("ci_low")
        ci_high = payload.get("ci_high")
        if ci_low is not None and ci_high is not None:
            try:
                confidence_interval = (float(ci_low), float(ci_high))
            except Exception:
                confidence_interval = None

        std_error_raw = payload.get("std_error")
        try:
            std_error = None if std_error_raw is None else float(std_error_raw)
        except Exception:
            std_error = None

        evidence_strength_raw = payload.get("evidence_strength")
        try:
            evidence_strength = EvidenceStrength(str(evidence_strength_raw))
        except Exception:
            evidence_strength = EvidenceStrength.UNKNOWN

        try:
            return EvidenceParameter(
                name=name,
                display_name=str(payload.get("display_name") or name),
                parameter_type=ParameterType.QUANTITATIVE,
                value=value,
                confidence_interval=confidence_interval,
                std_error=std_error,
                unit=(
                    str(payload.get("unit")).strip()
                    if payload.get("unit") not in (None, "")
                    else None
                ),
                evidence_strength=evidence_strength,
                time_period=str(payload.get("time_period") or ""),
            )
        except Exception:
            return None

    def latest_skg_version_id(self) -> int | None:
        try:
            row = self._con.execute("SELECT MAX(version_id) FROM ac_skg_versions").fetchone()
        except Exception:
            return None
        if not row or row[0] is None:
            return None
        return int(row[0])

    def skg_snapshot_ref(self, *, version_id: int | None = None) -> str | None:
        resolved_version = version_id if version_id is not None else self.latest_skg_version_id()
        if resolved_version is None:
            return None
        return f"duckdb://{self._db_path}#v{int(resolved_version)}"

    def query_prior_for_variables(
        self,
        variables: list[str],
        *,
        min_confidence: float = 0.0,
        limit: int = 256,
        domain: str | None = None,
    ) -> list[dict[str, object]]:
        clean_variables = sorted({str(item).strip() for item in variables if str(item).strip()})
        if not clean_variables:
            return []

        placeholders = ", ".join(["?"] * len(clean_variables))
        filters = [f"(src IN ({placeholders}) OR dst IN ({placeholders}))", "confidence >= ?"]
        params: list[object] = [*clean_variables, *clean_variables, float(min_confidence)]
        if domain:
            filters.append("(src ILIKE ? OR dst ILIKE ?)")
            domain_pattern = f"{domain.strip()}.%"
            params.extend([domain_pattern, domain_pattern])
        params.append(int(limit))
        has_candidate_layer = self._column_exists("ac_skg_edges", "candidate_layer")
        has_quality_json = self._column_exists("ac_skg_edges", "quality_signals_json")
        extra_select = ""
        if has_candidate_layer:
            extra_select += ", candidate_layer"
        if has_quality_json:
            extra_select += ", quality_signals_json"

        rows = self._con.execute(
            (
                "SELECT edge_id, src, dst, direction, n_articles, article_refs, "
                "evidence_strength, confidence, scope_conditions "
                f"{extra_select} "
                "FROM ac_skg_edges "
                f"WHERE {' AND '.join(filters)} "
                "ORDER BY confidence DESC, edge_id ASC "
                "LIMIT ?"
            ),
            params,
        ).fetchall()

        result: list[dict[str, object]] = []
        for row in rows:
            article_refs = self._parse_json_list(row[5])
            scope_conditions = self._parse_json_list(row[8])
            result.append(
                {
                    "edge_id": str(row[0]),
                    "src": str(row[1]),
                    "dst": str(row[2]),
                    "direction": str(row[3]),
                    "n_articles": int(row[4] or len(article_refs)),
                    "article_refs": article_refs,
                    "scope_conditions": scope_conditions,
                    "evidence_strength": str(row[6]),
                    "confidence": float(row[7]),
                }
            )
            idx = 9
            if has_candidate_layer:
                result[-1]["candidate_layer"] = str(row[idx])
                idx += 1
            if has_quality_json:
                result[-1]["quality_signals"] = self._parse_json_dict(row[idx]) or {}
        return result

    def close(self) -> None:
        self._store.close()
        self._con.close()


__all__ = ["SKGQuery", "LiteraturePriorResult", "ParameterCandidate"]
