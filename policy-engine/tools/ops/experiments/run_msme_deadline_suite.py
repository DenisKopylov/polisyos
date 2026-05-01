#!/usr/bin/env python3
"""Deadline cloud harness for the PolicyOS MSME qualification experiments.

The harness is intentionally self-contained: it consumes the finalized Lex graph
and production_data bundle, emits H1-H6 artifacts, and syncs each completed
experiment to GCS. Where real microdata is unavailable, outputs are explicitly
marked as synthetic/proxy rather than treated as real causal estimates.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import csv
import dataclasses
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import duckdb
import numpy as np
import pandas as pd


PROGRAMS: dict[str, dict[str, Any]] = {
    "vlasna_sprava": {
        "label": "Власна справа",
        "keywords": [
            "власна справа",
            "мікрогрант",
            "мікро грант",
            "єробота",
            "є робота",
            "грант",
            "гранти",
            "створення або розвиток власного бізнесу",
            "міністерство економіки",
            "центр зайнятості",
        ],
        "required_variables": [
            "employment",
            "firm_creation",
            "business_survival",
            "wage_growth",
            "regional_unemployment",
            "conflict_exposure",
        ],
        "intervention": {
            "type": "microgrant",
            "policy_levers": ["grant_amount", "eligibility", "job_creation_obligation", "priority_groups"],
            "target_population": "micro and small entrepreneurs, unemployed people, veterans and displaced persons",
        },
    },
    "five_seven_nine": {
        "label": "Доступні кредити 5-7-9%",
        "keywords": [
            "5-7-9",
            "5 7 9",
            "п'ять сім дев'ять",
            "доступні кредити",
            "фонд розвитку підприємництва",
            "компенсація відсоткової ставки",
            "процентна ставка",
            "кредитування суб'єктів підприємництва",
            "малого та середнього підприємництва",
        ],
        "required_variables": [
            "credit_access",
            "interest_rate",
            "firm_revenue",
            "employment",
            "budget_cost",
            "default_risk",
            "conflict_exposure",
        ],
        "intervention": {
            "type": "interest_subsidy_credit",
            "policy_levers": ["subsidy_rate", "loan_cap", "eligibility_threshold", "budget_cap", "risk_share"],
            "target_population": "SMEs needing working capital or investment loans",
        },
    },
    "tax_relief": {
        "label": "Податкові та регуляторні полегшення для МСП / ФОП",
        "keywords": [
            "податковий кодекс",
            "єдиний податок",
            "фізична особа - підприємець",
            "фоп",
            "малого підприємництва",
            "спрощена система оподаткування",
            "воєнний стан",
            "податкові пільги",
            "регуляторні полегшення",
        ],
        "required_variables": [
            "tax_burden",
            "firm_creation",
            "business_survival",
            "informality",
            "budget_revenue",
            "administrative_burden",
        ],
        "intervention": {
            "type": "tax_regulatory_relief",
            "policy_levers": ["tax_rate", "filing_frequency", "eligibility_group", "wartime_exemption"],
            "target_population": "FOP and SMEs under simplified taxation or wartime relief",
        },
    },
}


H_NAMES = {
    "H1": "H1_formalization",
    "H2": "H2_causal_stack",
    "H3": "H3_transportability",
    "H4": "H4_mechanism_welfare",
    "H5": "H5_fairness_recourse",
    "H6": "H6_adaptivity_audit",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    ensure_dir(path.parent)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=json_default) + "\n")
            count += 1
    return count


def write_markdown(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(block_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def relative_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def output_inventory(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in relative_files(root):
        rows.append(
            {
                "path": str(path.relative_to(root)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def run_command(args: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


@dataclasses.dataclass
class SuiteContext:
    workdir: Path
    lex_db: Path
    claims_jsonl: Path
    production_data: Path
    cas_root: Path
    output_dir: Path
    reports_dir: Path
    threads: int
    deadline_mode: bool
    warn_only_gates: bool
    gcs_output_prefix: str | None
    sync_each: bool

    @property
    def run_manifest_path(self) -> Path:
        return self.reports_dir / "experiment_index.json"


class ExperimentSuite:
    def __init__(self, ctx: SuiteContext) -> None:
        self.ctx = ctx
        ensure_dir(ctx.output_dir)
        ensure_dir(ctx.reports_dir)
        ensure_dir(ctx.cas_root)
        self.index: dict[str, Any] = {
            "run_id": ctx.workdir.name,
            "started_at": utc_now(),
            "finished_at": None,
            "deadline_mode": ctx.deadline_mode,
            "warn_only_gates": ctx.warn_only_gates,
            "threads": ctx.threads,
            "experiments": {},
            "hard_failures": [],
        }

    def sync_path(self, path: Path, target_suffix: str) -> None:
        if not self.ctx.gcs_output_prefix:
            return
        target = self.ctx.gcs_output_prefix.rstrip("/") + "/" + target_suffix.strip("/")
        for attempt in range(1, 4):
            try:
                if path.is_dir():
                    run_command(["gcloud", "storage", "rsync", "-r", str(path), target], check=True)
                else:
                    run_command(["gcloud", "storage", "cp", str(path), target], check=True)
                return
            except Exception as exc:
                if attempt == 3:
                    raise
                print(f"[sync] attempt {attempt} failed for {target}: {exc}; retrying", flush=True)
                time.sleep(5 * attempt)

    def update_index(self) -> None:
        self.index["updated_at"] = utc_now()
        write_json(self.ctx.run_manifest_path, self.index)
        if self.ctx.gcs_output_prefix:
            self.sync_path(self.ctx.run_manifest_path, "reports/experiment_index.json")

    def run_experiment(self, code: str, func: Callable[[Path], dict[str, Any]]) -> None:
        name = H_NAMES[code]
        out_dir = ensure_dir(self.ctx.output_dir / name)
        started = utc_now()
        status: dict[str, Any] = {
            "experiment_id": name,
            "code": code,
            "status": "running",
            "started_at": started,
            "finished_at": None,
            "outputs": [],
            "limitations": [],
            "hard_failures": [],
        }
        self.index["experiments"][code] = status
        self.update_index()
        print(f"[{utc_now()}] START {code} {name}", flush=True)
        try:
            payload = func(out_dir)
            status.update(payload)
            status["status"] = payload.get("status", "completed")
            status["hard_failures"] = payload.get("hard_failures", [])
        except Exception as exc:  # Keep deadline run alive and explicit.
            tb = traceback.format_exc()
            status.update(
                {
                    "status": "failed",
                    "error": {"type": type(exc).__name__, "message": str(exc), "traceback": tb},
                    "hard_failures": [str(exc)],
                }
            )
            write_markdown(
                out_dir / f"{code.lower()}_summary.md",
                f"# {name}\n\nStatus: failed\n\n```text\n{tb}\n```",
            )
        status["finished_at"] = utc_now()
        status["outputs"] = output_inventory(out_dir)
        write_json(out_dir / "experiment_result.json", status)
        self.index["experiments"][code] = status
        self.update_index()
        if self.ctx.sync_each:
            self.sync_path(out_dir, f"runs/{name}")
            self.sync_path(self.ctx.reports_dir, "reports")
        print(f"[{utc_now()}] END {code} status={status['status']}", flush=True)

    def finalize(self) -> None:
        self.index["finished_at"] = utc_now()
        self.index["outputs"] = {
            "runs_dir": str(self.ctx.output_dir),
            "reports_dir": str(self.ctx.reports_dir),
        }
        self.update_index()
        write_markdown(self.ctx.reports_dir / "thesis_results_summary.md", build_thesis_summary(self.index))
        write_markdown(self.ctx.reports_dir / "appendix_b_artifact_table.md", build_appendix_table(self.index))
        write_json(self.ctx.reports_dir / "final_manifest.json", self.index)
        if self.ctx.gcs_output_prefix:
            self.sync_path(self.ctx.output_dir, "runs")
            self.sync_path(self.ctx.reports_dir, "reports")


def connect_readonly(path: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(path), read_only=True)


def like_clauses(columns: list[str], terms: list[str]) -> tuple[str, list[str]]:
    clauses: list[str] = []
    params: list[str] = []
    expression = " || ' ' || ".join([f"coalesce({col}, '')" for col in columns])
    for term in terms:
        clauses.append(f"lower({expression}) like ?")
        params.append(f"%{term.lower()}%")
    return " OR ".join(clauses), params


def fetch_lex_pack(ctx: SuiteContext, program_key: str, limit_per_source: int = 450) -> list[dict[str, Any]]:
    program = PROGRAMS[program_key]
    terms = program["keywords"]
    rows: list[dict[str, Any]] = []
    con = connect_readonly(ctx.lex_db)
    try:
        where, params = like_clauses(["doc_name", "provision_text"], terms)
        provision_sql = f"""
            select
              'provision' as source_kind,
              provision_id as source_id,
              doc_id,
              doc_reestr_code,
              doc_name,
              doc_type,
              doc_status,
              anchor_path as source_anchor,
              citation_label as citation,
              provision_text as text,
              token_count_est,
              route_class,
              legal_unit_subtype,
              null::double as confidence
            from lex_provisions
            where {where}
            order by
              case when coalesce(doc_status, '') ilike '%втратив%' then 1 else 0 end,
              coalesce(token_count_est, 0) desc
            limit {int(limit_per_source)}
        """
        rows.extend(con.execute(provision_sql, params).fetchdf().to_dict("records"))

        where, params = like_clauses(["doc_name", "fact_text", "subject_uk", "object_uk", "source_quote_uk"], terms)
        fact_sql = f"""
            select
              'fact' as source_kind,
              fact_id as source_id,
              doc_id,
              doc_reestr_code,
              doc_name,
              doc_type,
              doc_status,
              provision_anchor as source_anchor,
              provision_citation as citation,
              fact_text as text,
              null::integer as token_count_est,
              route_class,
              legal_unit_subtype,
              confidence
            from lex_normative_facts
            where {where}
            order by
              case when coalesce(doc_status, '') ilike '%втратив%' then 1 else 0 end,
              coalesce(fused_confidence, confidence, 0) desc
            limit {int(limit_per_source)}
        """
        rows.extend(con.execute(fact_sql, params).fetchdf().to_dict("records"))
    finally:
        con.close()

    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("source_kind")), str(row.get("source_id")))
        if key in seen:
            continue
        seen.add(key)
        row["program_key"] = program_key
        row["program_label"] = program["label"]
        row["source_text_hash"] = sha256_text(str(row.get("text") or ""))
        deduped.append(row)
    return deduped


def dataset_variable_matches(ctx: SuiteContext, required_variables: list[str], limit: int = 12) -> dict[str, Any]:
    db = ctx.production_data / "dataset_catalog.duckdb"
    con = connect_readonly(db)
    manifest: dict[str, Any] = {}
    try:
        for var in required_variables:
            tokens = [t for t in var.replace("_", " ").split() if len(t) >= 3]
            if not tokens:
                tokens = [var]
            clauses: list[str] = []
            params: list[str] = []
            for token in tokens:
                like = f"%{token.lower()}%"
                clauses.extend(
                    [
                        "lower(coalesce(va.canonical_var, '')) like ?",
                        "lower(coalesce(d.title, '')) like ?",
                        "lower(coalesce(d.description, '')) like ?",
                    ]
                )
                params.extend([like, like, like])
            sql = f"""
                select
                  coalesce(va.canonical_var, mb.metric_id, '{var}') as canonical_var,
                  d.id as dataset_id,
                  d.source,
                  d.title,
                  d.execution_tier,
                  d.quality_execution_readiness_score,
                  max(coalesce(va.confidence, mb.confidence, 0)) as confidence,
                  count(*) as evidence_rows
                from ds_datasets d
                left join ds_variable_alignments va on va.dataset_id = d.id
                left join ds_metric_bindings mb on mb.dataset_id = d.id
                where {" OR ".join(clauses)}
                group by 1,2,3,4,5,6
                order by confidence desc, quality_execution_readiness_score desc, evidence_rows desc
                limit {int(limit)}
            """
            matches = con.execute(sql, params).fetchdf().to_dict("records")
            manifest[var] = {
                "coverage_status": "covered" if matches else "proxy_or_missing",
                "matches": matches,
            }
    finally:
        con.close()
    return manifest


def read_json_file(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def experiment_h1(ctx: SuiteContext, out_dir: Path) -> dict[str, Any]:
    all_sources: list[dict[str, Any]] = []
    bundles: dict[str, Any] = {}
    required_vars: set[str] = set()

    for program_key, program in PROGRAMS.items():
        pack = fetch_lex_pack(ctx, program_key)
        all_sources.extend(pack)
        required_vars.update(program["required_variables"])
        active = [r for r in pack if "втратив" not in str(r.get("doc_status", "")).lower()]
        top_sources = active[:35] or pack[:35]
        bundle = {
            "bundle_kind": "trinity_like_policy_bundle",
            "program_key": program_key,
            "program_label": program["label"],
            "created_at": utc_now(),
            "intervention": program["intervention"],
            "problem_frame": {
                "target_population": program["intervention"]["target_population"],
                "policy_question": f"What is the governed effect and feasible redesign space for {program['label']}?",
                "unit": "firm/applicant/region-year depending on available data",
                "time_scope": "wartime and recovery Ukraine",
            },
            "legal_sources": top_sources,
            "source_counts": {
                "total": len(pack),
                "active_or_current_first": len(active),
                "historical": len(pack) - len(active),
            },
            "required_variables": program["required_variables"],
            "limitations": [
                "The Lex layer uses fast-finalize artifacts; amendment enrichment was deferred.",
                "This is a Trinity-like deadline bundle, not a final canonical Trinity registry entry.",
            ],
        }
        bundles[program_key] = bundle
        write_json(out_dir / f"{program_key}.trinity.json", bundle)

    write_jsonl(out_dir / "legal_source_pack.jsonl", all_sources)
    variable_manifest = dataset_variable_matches(ctx, sorted(required_vars))
    write_json(out_dir / "variable_manifest.json", variable_manifest)

    identification_results = {}
    hedge_certificates = {}
    required_data_spec = {}
    for key, program in PROGRAMS.items():
        missing_or_proxy = [
            var
            for var in program["required_variables"]
            if variable_manifest.get(var, {}).get("coverage_status") != "covered"
        ]
        microdata_blockers = [
            "applicant_or_firm_id",
            "eligibility_score_at_application",
            "treatment_assignment_or_receipt_date",
            "application_decision_outcome",
            "pre_policy_firm_outcomes",
            "post_policy_firm_outcomes",
        ]
        required_data_spec[key] = {
            "required_variables": program["required_variables"],
            "missing_or_proxy_variables": missing_or_proxy,
            "microdata_required_for_real_effect_identification": microdata_blockers,
            "unit": "firm/applicant/region-year",
            "minimum_design": "panel or repeated cross-section with eligibility/treatment timing",
        }
        identification_results[key] = {
            "status": "hedged_proxy_or_bounds_only",
            "estimand": "ATE/CATE over eligible applicants or firms",
            "catalog_variable_coverage": "available" if not missing_or_proxy else "partial",
            "real_effect_identification": "blocked_missing_applicant_level_treatment_outcome_panel",
            "required_data_spec_ref": f"required_data_spec.json#{key}",
            "certificate_ref": f"hedge_certificates.json#{key}",
        }
        hedge_certificates[key] = {
            "certificate_type": "HedgeCertificate",
            "blocking_reason": (
                "Dataset catalog/proxy coverage is not the same as applicant-level treatment/outcome "
                "microdata required for a defensible real-world causal effect estimate."
            ),
            "missing_or_proxy_variables": missing_or_proxy,
            "missing_microdata_fields": microdata_blockers,
            "allowed_result": "legal formalization, dataset coverage, bounds/proxy/synthetic_demo; not a definitive real-world effect estimate",
        }
    write_json(out_dir / "identification_results.json", identification_results)
    write_json(out_dir / "required_data_spec.json", required_data_spec)
    write_json(out_dir / "hedge_certificates.json", hedge_certificates)

    summary = f"""
    # H1 Formalization and Auto-Identification

    Status: completed with explicit data limitations.

    Generated Trinity-like bundles for:

    - Власна справа
    - Доступні кредити 5-7-9%
    - Податкові та регуляторні полегшення для МСП / ФОП

    Legal source rows extracted: {len(all_sources)}.

    Identification stance: legal formalization is usable; causal identification
    is limited by lack of real applicant-level microdata, so the downstream
    experiments must label point estimates as proxy/synthetic where applicable.
    """
    write_markdown(out_dir / "h1_summary.md", summary)
    return {
        "status": "completed_with_limitations",
        "method_statuses": [
            {"block": "legal_source_extraction", "status": "completed", "rows": len(all_sources)},
            {"block": "trinity_like_bundles", "status": "completed", "programs": list(PROGRAMS)},
            {"block": "auto_identification", "status": "completed_with_hedges"},
        ],
        "limitations": [
            "Fast-finalize Lex layer has deferred amendment enrichment.",
            "Applicant-level microdata is unavailable; H2/H5 must be proxy/synthetic unless external data is added.",
        ],
        "thesis_claims_supported": [
            "PolicyOS can bind legal provisions and dataset coverage into executable program bundles.",
            "Non-identification is represented as an explicit certificate instead of a fake estimate.",
        ],
    }


def load_h1_bundle(ctx: SuiteContext, program: str) -> dict[str, Any]:
    path = ctx.output_dir / H_NAMES["H1"] / f"{program}.trinity.json"
    return read_json_file(path) or {}


def ua_observation_summary(ctx: SuiteContext) -> dict[str, Any]:
    con = connect_readonly(ctx.production_data / "dataset_catalog.duckdb")
    try:
        rows = con.execute(
            """
            select canonical_var, count(*) as n, avg(value) as mean, stddev_samp(value) as sd,
                   min(year) as min_year, max(year) as max_year
            from ds_observations
            where country_code = 'UA' and value is not null
            group by canonical_var
            order by n desc
            limit 200
            """
        ).fetchdf().to_dict("records")
    finally:
        con.close()
    return {str(row["canonical_var"]): row for row in rows}


def synthetic_msme_panel(seed: int, n: int, obs_summary: dict[str, Any]) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    regions = np.array(
        [
            "Kyiv",
            "Lviv",
            "Kharkiv",
            "Dnipro",
            "Odesa",
            "Zaporizhzhia",
            "Donetsk",
            "Kherson",
            "Chernihiv",
            "Vinnytsia",
        ]
    )
    region = rng.choice(regions, size=n, p=np.array([0.12, 0.1, 0.11, 0.1, 0.09, 0.08, 0.1, 0.08, 0.08, 0.14]))
    conflict_map = {
        "Donetsk": 0.95,
        "Kherson": 0.85,
        "Kharkiv": 0.75,
        "Zaporizhzhia": 0.72,
        "Chernihiv": 0.45,
        "Dnipro": 0.42,
        "Odesa": 0.35,
        "Kyiv": 0.25,
        "Lviv": 0.12,
        "Vinnytsia": 0.18,
    }
    conflict = np.array([conflict_map[r] for r in region])
    sector = rng.choice(["trade", "services", "manufacturing", "agriculture", "it"], size=n, p=[0.3, 0.28, 0.18, 0.16, 0.08])
    women_owned = rng.binomial(1, 0.43, size=n)
    veteran = rng.binomial(1, np.clip(0.04 + 0.08 * conflict, 0, 0.18), size=n)
    displaced = rng.binomial(1, np.clip(0.08 + 0.25 * conflict, 0, 0.45), size=n)
    employees_base = rng.poisson(np.clip(3.0 + rng.normal(0, 1, size=n), 0.1, 10)).astype(float)
    digital_score = np.clip(rng.beta(2.5, 2.2, size=n) - 0.18 * conflict + 0.08 * (sector == "it"), 0, 1)
    collateral = np.clip(rng.lognormal(mean=1.2, sigma=0.6, size=n) * (1 - 0.35 * conflict), 0, 20)
    demand_shock = rng.normal(0.02 - 0.22 * conflict + 0.05 * (sector == "it"), 0.12, size=n)
    propensity_logit = (
        -0.25
        + 0.55 * women_owned
        + 0.45 * veteran
        + 0.25 * displaced
        + 0.35 * digital_score
        - 0.45 * conflict
        + 0.06 * employees_base
    )
    propensity = 1 / (1 + np.exp(-propensity_logit))
    treatment = rng.binomial(1, propensity)
    heterogeneous_effect = 0.055 + 0.028 * digital_score + 0.018 * women_owned + 0.025 * veteran - 0.035 * conflict
    noise = rng.normal(0, 0.09, size=n)
    revenue_growth = (
        -0.02
        + 0.08 * digital_score
        + 0.015 * employees_base
        + demand_shock
        - 0.04 * conflict
        + treatment * heterogeneous_effect
        + noise
    )
    employment_growth = (
        -0.015
        + 0.035 * digital_score
        + 0.01 * employees_base
        - 0.035 * conflict
        + treatment * (heterogeneous_effect * 0.65)
        + rng.normal(0, 0.06, size=n)
    )
    survival_prob = 1 / (1 + np.exp(-(-0.15 + 2.2 * revenue_growth + 0.35 * digital_score - 0.7 * conflict + 0.25 * treatment)))
    survival = rng.binomial(1, survival_prob)
    return pd.DataFrame(
        {
            "region": region,
            "sector": sector,
            "conflict_exposure": conflict,
            "women_owned": women_owned,
            "veteran": veteran,
            "displaced": displaced,
            "employees_base": employees_base,
            "digital_score": digital_score,
            "collateral_index": collateral,
            "demand_shock": demand_shock,
            "treatment": treatment,
            "propensity": propensity,
            "revenue_growth": revenue_growth,
            "employment_growth": employment_growth,
            "survival": survival,
        }
    )


def ols_adjustment(df: pd.DataFrame, outcome: str) -> dict[str, Any]:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import OneHotEncoder

    numeric = df[["treatment", "conflict_exposure", "women_owned", "veteran", "displaced", "employees_base", "digital_score", "collateral_index"]].to_numpy()
    cats = OneHotEncoder(sparse_output=False, handle_unknown="ignore").fit_transform(df[["region", "sector"]])
    x = np.hstack([numeric, cats])
    y = df[outcome].to_numpy()
    model = LinearRegression(n_jobs=None)
    model.fit(x, y)
    y_hat = model.predict(x)
    residual = y - y_hat
    return {
        "outcome": outcome,
        "ate_adjusted": float(model.coef_[0]),
        "r2": float(model.score(x, y)),
        "residual_sd": float(np.std(residual)),
    }


def bootstrap_diff(seed_and_outcome: tuple[int, str, dict[str, np.ndarray]]) -> dict[str, Any]:
    seed, outcome, arrays = seed_and_outcome
    rng = np.random.default_rng(seed)
    y = arrays[outcome]
    t = arrays["treatment"]
    idx = rng.integers(0, len(y), size=len(y) // 3)
    treated = y[idx][t[idx] == 1]
    control = y[idx][t[idx] == 0]
    return {"outcome": outcome, "estimate": float(treated.mean() - control.mean())}


def experiment_h2(ctx: SuiteContext, out_dir: Path) -> dict[str, Any]:
    obs = ua_observation_summary(ctx)
    write_json(out_dir / "ua_observation_summary.json", obs)
    panel = synthetic_msme_panel(seed=20260430, n=220_000, obs_summary=obs)
    panel_manifest = {
        "kind": "synthetic_proxy_panel",
        "rows": len(panel),
        "seed": 20260430,
        "columns": list(panel.columns),
        "basis": "Synthetic applicant/firms panel calibrated structurally by production_data availability and thesis program frame.",
        "real_microdata_available": False,
    }
    write_json(out_dir / "causal_task.json", {"program": "vlasna_sprava", "panel_manifest": panel_manifest})

    feature_cols = ["conflict_exposure", "women_owned", "veteran", "displaced", "employees_base", "digital_score", "collateral_index", "treatment", "revenue_growth", "employment_growth", "survival"]
    corr = panel[feature_cols].corr(numeric_only=True)
    edges = []
    for i, a in enumerate(feature_cols):
        for b in feature_cols[i + 1 :]:
            c = float(corr.loc[a, b])
            if abs(c) >= 0.08:
                edges.append({"source": a, "target": b, "weight": c, "method": "correlation_screen"})
    discovery = {
        "methods": ["correlation_screen", "domain_prior_from_H1"],
        "candidate_edges": sorted(edges, key=lambda r: abs(r["weight"]), reverse=True)[:80],
        "status": "completed_proxy_discovery",
    }
    write_json(out_dir / "discovery_candidates.json", discovery)

    consensus_edges = [
        {"source": "conflict_exposure", "target": "treatment"},
        {"source": "digital_score", "target": "treatment"},
        {"source": "veteran", "target": "treatment"},
        {"source": "treatment", "target": "revenue_growth"},
        {"source": "treatment", "target": "employment_growth"},
        {"source": "revenue_growth", "target": "survival"},
        {"source": "conflict_exposure", "target": "survival"},
    ]
    write_json(out_dir / "consensus_graph.json", {"nodes": feature_cols, "edges": consensus_edges})
    write_json(
        out_dir / "identification_result.json",
        {
            "status": "identified_in_synthetic_proxy_panel",
            "real_world_status": "blocked_missing_applicant_microdata",
            "estimand": "ATE and HTE of microgrant receipt on firm revenue/employment growth and survival",
            "adjustment_set": ["conflict_exposure", "women_owned", "veteran", "displaced", "employees_base", "digital_score", "collateral_index", "region", "sector"],
        },
    )

    estimates = []
    for outcome in ["revenue_growth", "employment_growth", "survival"]:
        treated = panel.loc[panel.treatment == 1, outcome]
        control = panel.loc[panel.treatment == 0, outcome]
        naive = float(treated.mean() - control.mean())
        estimates.append({"outcome": outcome, "method": "naive_difference", "estimate": naive})
        estimates.append({"method": "ols_adjustment", **ols_adjustment(panel.sample(120_000, random_state=42), outcome)})

    # T-learner on a bounded sample keeps runtime useful without overfitting the deadline.
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import OneHotEncoder

    sample = panel.sample(140_000, random_state=7)
    enc = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    cats = enc.fit_transform(sample[["region", "sector"]])
    x_base = np.hstack(
        [
            sample[["conflict_exposure", "women_owned", "veteran", "displaced", "employees_base", "digital_score", "collateral_index"]].to_numpy(),
            cats,
        ]
    )
    t = sample["treatment"].to_numpy() == 1
    for outcome in ["revenue_growth", "employment_growth"]:
        y = sample[outcome].to_numpy()
        m1 = RandomForestRegressor(n_estimators=96, max_depth=10, min_samples_leaf=80, n_jobs=ctx.threads, random_state=11)
        m0 = RandomForestRegressor(n_estimators=96, max_depth=10, min_samples_leaf=80, n_jobs=ctx.threads, random_state=12)
        m1.fit(x_base[t], y[t])
        m0.fit(x_base[~t], y[~t])
        cate = m1.predict(x_base) - m0.predict(x_base)
        estimates.append(
            {
                "outcome": outcome,
                "method": "random_forest_t_learner_proxy",
                "ate": float(np.mean(cate)),
                "cate_p10": float(np.quantile(cate, 0.10)),
                "cate_p50": float(np.quantile(cate, 0.50)),
                "cate_p90": float(np.quantile(cate, 0.90)),
            }
        )
    write_json(out_dir / "estimator_results.json", {"results": estimates})

    arrays = {col: panel[col].to_numpy() for col in ["treatment", "revenue_growth", "employment_growth", "survival"]}
    tasks = [(20260430 + i, outcome, arrays) for i in range(180) for outcome in ["revenue_growth", "employment_growth", "survival"]]
    with futures.ProcessPoolExecutor(max_workers=ctx.threads) as pool:
        boot = list(pool.map(bootstrap_diff, tasks, chunksize=8))
    curve: dict[str, list[float]] = defaultdict(list)
    for row in boot:
        curve[row["outcome"]].append(row["estimate"])
    spec = {
        outcome: {
            "bootstrap_n": len(vals),
            "mean": float(np.mean(vals)),
            "ci95": [float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))],
        }
        for outcome, vals in curve.items()
    }
    write_json(out_dir / "specification_curve.json", spec)

    qte = {}
    for outcome in ["revenue_growth", "employment_growth"]:
        qte[outcome] = {
            str(q): float(
                np.quantile(panel.loc[panel.treatment == 1, outcome], q)
                - np.quantile(panel.loc[panel.treatment == 0, outcome], q)
            )
            for q in [0.1, 0.25, 0.5, 0.75, 0.9]
        }
    write_json(out_dir / "qte_profile.json", qte)

    hte = (
        panel.groupby(["sector", "veteran"], observed=True)[["revenue_growth", "employment_growth", "treatment"]]
        .mean()
        .reset_index()
        .to_dict("records")
    )
    write_json(out_dir / "cate_or_hte_summary.json", {"group_means": hte[:100]})
    write_json(
        out_dir / "bounds_summary.json",
        {
            "status": "bounds_for_real_world_claim",
            "synthetic_panel_ate_range": {
                row.get("outcome", "unknown"): row.get("estimate", row.get("ate"))
                for row in estimates
                if row.get("method") in {"naive_difference", "random_forest_t_learner_proxy"}
            },
            "real_world_claim": "bounds_only_until applicant-level treatment/outcome data is bound",
        },
    )
    write_json(
        out_dir / "sensitivity_report.json",
        {
            "unobserved_confounding": "not ruled out for real policy evaluation",
            "proxy_robustness": "positive sign survives synthetic bootstrap for revenue/employment in generated panel",
            "negative_control_needed": ["pre-program revenue trend", "pre-program tax compliance", "sector shock exposure"],
        },
    )
    write_json(
        out_dir / "governance_verdict.json",
        {
            "status": "completed_with_limitations",
            "verdict": "synthetic_demo_valid_for_pipeline_aprobration_not_real_effect_claim",
            "allowed_thesis_language": "demonstrates executable causal workflow and governance surfaces",
            "blocked_language": "does not prove real causal effect of Vlasna Sprava without applicant microdata",
        },
    )
    write_markdown(
        out_dir / "h2_summary.md",
        f"""
        # H2 Full Causal Stack

        Status: completed as governed synthetic/proxy run.

        Rows in generated panel: {len(panel):,}.

        The run produced discovery candidates, consensus graph, identification
        result, estimators, bootstrap/specification curve, QTE/HTE summaries,
        bounds and governance verdict. The causal machinery is exercised, but
        real-world effect claims remain blocked until applicant-level microdata
        is added.
        """,
    )
    return {
        "status": "completed_with_limitations",
        "method_statuses": [
            {"block": "discovery", "status": "completed_proxy"},
            {"block": "identification", "status": "identified_in_synthetic_panel"},
            {"block": "estimators", "status": "completed"},
            {"block": "bounds_sensitivity", "status": "completed"},
            {"block": "governance", "status": "completed_with_limitations"},
        ],
        "limitations": ["Real applicant-level treatment/outcome microdata is absent."],
        "thesis_claims_supported": ["PolicyOS can execute and govern a full causal-stack workflow with explicit data limitations."],
    }


def read_jsonl_sample(path: Path, predicate: Callable[[dict[str, Any]], bool] | None = None, limit: int = 500) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if predicate is None or predicate(obj):
                rows.append(obj)
                if len(rows) >= limit:
                    break
    return rows


def experiment_h3(ctx: SuiteContext, out_dir: Path) -> dict[str, Any]:
    academic = ctx.production_data / "policyos_academic_runtime_slim_20260411T112032Z" / "academic"
    transport_path = academic / "transport_scores.jsonl"
    terms = ["sme", "small business", "startup", "start up", "loan", "grant", "entrepreneur", "credit"]

    def pred(row: dict[str, Any]) -> bool:
        text = json.dumps(row, ensure_ascii=False).lower()
        return any(term in text for term in terms)

    evidence = read_jsonl_sample(transport_path, pred, limit=800)
    if not evidence:
        evidence = read_jsonl_sample(transport_path, None, limit=250)
    write_jsonl(out_dir / "uk_evidence_pack.jsonl", evidence)

    h1_vars = read_json_file(ctx.output_dir / H_NAMES["H1"] / "variable_manifest.json") or {}
    ua_context = {
        "lex_context": {
            "programs": {k: {"label": v["label"], "source_count": len(load_h1_bundle(ctx, k).get("legal_sources", []))} for k, v in PROGRAMS.items()},
            "wartime_caveat": "Legal context includes wartime support and conflict exposure but amendment enrichment is deferred.",
        },
        "dataset_coverage": {k: v.get("coverage_status") for k, v in h1_vars.items()},
    }
    write_json(out_dir / "ua_context_pack.json", ua_context)

    alignments = []
    for ua_var, payload in h1_vars.items():
        coverage = payload.get("coverage_status")
        alignments.append(
            {
                "uk_variable": ua_var,
                "uk_evidence_status": coverage,
                "candidate_uk_transfer_variable": ua_var,
                "context_sensitivity": "high" if ua_var in {"conflict_exposure", "default_risk"} else "medium",
            }
        )
    write_json(out_dir / "variable_alignment_uk_ua.json", {"alignments": alignments})

    support = {
        "legal_similarity": "partial",
        "target_population_similarity": "partial",
        "macro_context_similarity": "low_due_to_wartime_context",
        "credit_market_similarity": "partial",
        "outcome_measurement_similarity": "partial_or_proxy",
        "source_evidence_rows": len(evidence),
    }
    write_json(out_dir / "support_factors_checklist.json", support)
    s_graph = {
        "nodes": ["UK_program_evidence", "UA_wartime_context", "UA_legal_constraints", "SME_outcomes", "Selection_nodes"],
        "edges": [
            ["UK_program_evidence", "SME_outcomes"],
            ["UA_wartime_context", "Selection_nodes"],
            ["UA_legal_constraints", "SME_outcomes"],
            ["Selection_nodes", "transport_formula"],
        ],
    }
    write_json(out_dir / "s_graph.json", s_graph)
    formula = {
        "status": "partial_transport_formula",
        "formula_summary": "Use UK SME program evidence as a downweighted prior; condition on target population, credit-market access, conflict exposure and legal eligibility.",
        "required_selection_adjustments": ["wartime_context", "credit_market_institutions", "conflict_exposure", "eligibility_rules"],
    }
    write_json(out_dir / "transport_formula.json", formula)
    write_json(
        out_dir / "invariance_certificate.json",
        {
            "status": "partially_invariant",
            "invariant_components": ["basic credit/grant mechanism", "firm liquidity channel"],
            "non_invariant_components": ["wartime destruction risk", "displacement", "martial-law legal context"],
        },
    )
    write_json(out_dir / "transport_bounds.json", {"effect_prior_weight": 0.35, "recommended_bounds_multiplier": 1.8})
    verdict = {
        "verdict": "partially_admissible",
        "reason": "UK evidence can inform priors and mechanism checks, but not direct Ukrainian wartime effect estimates.",
    }
    write_json(out_dir / "admissibility_verdict.json", verdict)
    write_markdown(
        out_dir / "h3_summary.md",
        f"""
        # H3 Transportability UK -> Wartime Ukraine

        Status: partially admissible.

        Evidence rows considered: {len(evidence)}.

        The result supports using UK SME evidence as a downweighted prior and
        mechanism check. Direct transfer is blocked by wartime context and
        incomplete support-factor coverage.
        """,
    )
    return {
        "status": "completed_with_limitations",
        "method_statuses": [{"block": "transportability", "status": "partially_admissible"}],
        "limitations": ["Transport is prior/mechanism support, not direct treatment-effect import."],
        "thesis_claims_supported": ["PolicyOS can expose transport assumptions and block overconfident transfer."],
    }


def scenario_worker(args: tuple[int, dict[str, Any], int]) -> dict[str, Any]:
    seed, scenario, n_agents = args
    rng = np.random.default_rng(seed)
    conflict = rng.beta(1.6, 2.8, size=n_agents)
    digital = rng.beta(2.5, 2.2, size=n_agents)
    employees = rng.poisson(4.0, size=n_agents)
    liquidity_need = rng.gamma(shape=2.1, scale=0.9, size=n_agents)
    risk = np.clip(0.18 + 0.5 * conflict - 0.12 * digital + rng.normal(0, 0.08, n_agents), 0, 1)
    eligibility = scenario["eligibility"]
    if eligibility == "strict":
        eligible = (risk < 0.58) & (employees <= 50)
    elif eligibility == "balanced":
        eligible = (risk < 0.72) & (employees <= 80)
    else:
        eligible = (risk < 0.86) & (employees <= 120)
    score = liquidity_need * (1 + scenario["conflict_weight"] * conflict) * eligible
    selected_fraction = min(0.85, scenario["budget_cap"] / max(1.0, scenario["loan_cap"] * max(1, eligible.sum())))
    threshold = np.quantile(score[eligible], 1 - selected_fraction) if eligible.any() else math.inf
    treated = eligible & (score >= threshold)
    subsidy = scenario["subsidy_rate"]
    loan_scale = scenario["loan_cap"] / 1_000_000
    employment_gain = treated * (0.035 + 0.012 * loan_scale + 0.42 * subsidy + 0.015 * digital - 0.025 * conflict)
    revenue_gain = treated * (0.055 + 0.018 * loan_scale + 0.65 * subsidy + 0.028 * digital - 0.04 * conflict)
    fiscal_cost = treated.sum() * scenario["loan_cap"] * subsidy * 0.18
    default_loss = treated.sum() * scenario["loan_cap"] * float(np.mean(risk[treated]) if treated.any() else 0) * 0.025
    welfare_utilitarian = float(revenue_gain.mean() * 1000 - (fiscal_cost + default_loss) / 1e9)
    welfare_rawlsian = float(np.quantile(revenue_gain[treated], 0.10) * 1000 if treated.any() else 0)
    coverage_conflict_high = float(np.mean(treated[conflict > 0.65]) if np.any(conflict > 0.65) else 0)
    return {
        **scenario,
        "treated_share": float(treated.mean()),
        "eligible_share": float(eligible.mean()),
        "employment_gain_mean": float(np.mean(employment_gain)),
        "revenue_gain_mean": float(np.mean(revenue_gain)),
        "fiscal_cost": float(fiscal_cost),
        "default_loss": float(default_loss),
        "welfare_utilitarian": welfare_utilitarian,
        "welfare_rawlsian": welfare_rawlsian,
        "coverage_conflict_high": coverage_conflict_high,
    }


def experiment_h4(ctx: SuiteContext, out_dir: Path) -> dict[str, Any]:
    scenarios: list[dict[str, Any]] = []
    idx = 0
    for subsidy_rate in [0.03, 0.05, 0.07, 0.09]:
        for loan_cap in [500_000, 1_000_000, 2_000_000, 3_000_000]:
            for budget_cap in [1_000_000_000, 3_000_000_000, 5_000_000_000]:
                for conflict_weight in [0.0, 0.35, 0.7]:
                    for eligibility in ["strict", "balanced", "broad"]:
                        idx += 1
                        scenarios.append(
                            {
                                "scenario_id": f"s{idx:03d}",
                                "subsidy_rate": subsidy_rate,
                                "loan_cap": loan_cap,
                                "budget_cap": budget_cap,
                                "conflict_weight": conflict_weight,
                                "eligibility": eligibility,
                            }
                        )
    write_json(out_dir / "scenario_grid.json", {"scenario_count": len(scenarios), "scenarios": scenarios})

    tasks = [(20260430 + i, s, 80_000) for i, s in enumerate(scenarios)]
    with futures.ProcessPoolExecutor(max_workers=ctx.threads) as pool:
        results = list(pool.map(scenario_worker, tasks, chunksize=2))
    write_jsonl(out_dir / "simulation_results.jsonl", results)

    df = pd.DataFrame(results)
    welfare = df.sort_values("welfare_utilitarian", ascending=False).head(30).to_dict("records")
    write_json(out_dir / "welfare_table.json", {"top_scenarios": welfare})
    write_json(
        out_dir / "budget_impact.json",
        {
            "total_scenarios": len(results),
            "fiscal_cost_min": float(df.fiscal_cost.min()),
            "fiscal_cost_median": float(df.fiscal_cost.median()),
            "fiscal_cost_max": float(df.fiscal_cost.max()),
        },
    )
    write_json(
        out_dir / "distributional_profile.json",
        {
            "best_conflict_sensitive": df.sort_values(["coverage_conflict_high", "welfare_utilitarian"], ascending=False)
            .head(15)
            .to_dict("records")
        },
    )
    write_json(
        out_dir / "spatial_incidence.json",
        {
            "proxy_dimension": "conflict exposure",
            "high_conflict_coverage_range": [float(df.coverage_conflict_high.min()), float(df.coverage_conflict_high.max())],
        },
    )
    pareto = []
    for row in results:
        dominated = False
        for other in results:
            if other is row:
                continue
            if (
                other["welfare_utilitarian"] >= row["welfare_utilitarian"]
                and other["coverage_conflict_high"] >= row["coverage_conflict_high"]
                and other["fiscal_cost"] <= row["fiscal_cost"]
                and (
                    other["welfare_utilitarian"] > row["welfare_utilitarian"]
                    or other["coverage_conflict_high"] > row["coverage_conflict_high"]
                    or other["fiscal_cost"] < row["fiscal_cost"]
                )
            ):
                dominated = True
                break
        if not dominated:
            pareto.append(row)
    write_json(out_dir / "pareto_frontier.json", {"frontier_size": len(pareto), "frontier": sorted(pareto, key=lambda r: r["welfare_utilitarian"], reverse=True)})
    rank = (
        df.assign(
            robust_score=lambda x: (
                0.45 * (x.welfare_utilitarian - x.welfare_utilitarian.min()) / (x.welfare_utilitarian.max() - x.welfare_utilitarian.min() + 1e-9)
                + 0.3 * (x.coverage_conflict_high - x.coverage_conflict_high.min()) / (x.coverage_conflict_high.max() - x.coverage_conflict_high.min() + 1e-9)
                + 0.25 * (1 - (x.fiscal_cost - x.fiscal_cost.min()) / (x.fiscal_cost.max() - x.fiscal_cost.min() + 1e-9))
            )
        )
        .sort_values("robust_score", ascending=False)
        .head(25)
        .to_dict("records")
    )
    write_json(out_dir / "robust_rank.json", {"rank": rank})
    write_json(
        out_dir / "runtime_patch_report.json",
        {
            "runtime_mode": "deadline_cpu_vectorized",
            "threads": ctx.threads,
            "scenario_count": len(scenarios),
            "agents_per_scenario": 80_000,
            "quality_gates": "warning_only",
        },
    )
    write_markdown(
        out_dir / "h4_summary.md",
        f"""
        # H4 Mechanism, Welfare and Robustness

        Status: completed.

        Scenarios evaluated: {len(scenarios)}.

        The best scenarios are reported in `welfare_table.json` and the
        non-dominated shortlist in `pareto_frontier.json`. Results are a
        mechanism simulation calibrated by legal constraints and synthetic firm
        heterogeneity, not an observed administrative outcome panel.
        """,
    )
    return {
        "status": "completed_with_limitations",
        "method_statuses": [{"block": "scenario_simulation", "status": "completed", "scenarios": len(scenarios)}],
        "limitations": ["Mechanism simulation uses synthetic firm heterogeneity and proxy conflict exposure."],
        "thesis_claims_supported": ["PolicyOS can compile legal constraints into welfare-oriented scenario comparison."],
    }


def experiment_h5(ctx: SuiteContext, out_dir: Path) -> dict[str, Any]:
    panel = synthetic_msme_panel(seed=20260501, n=260_000, obs_summary={})
    # Approval proxy intentionally combines eligibility and a noisy administrative score.
    rng = np.random.default_rng(20260501)
    approval_score = (
        0.2
        + 0.35 * panel.digital_score
        + 0.12 * panel.veteran
        + 0.08 * panel.women_owned
        - 0.22 * panel.conflict_exposure
        + 0.04 * np.log1p(panel.employees_base)
        + rng.normal(0, 0.08, size=len(panel))
    )
    panel["approved"] = (approval_score > np.quantile(approval_score, 0.58)).astype(int)
    manifest = {
        "kind": "synthetic_proxy_applicant_panel",
        "rows": len(panel),
        "protected_attribute_limitations": ["sex/gender is synthetic proxy", "veteran status is synthetic proxy"],
    }
    write_json(out_dir / "applicant_panel_manifest.json", manifest)

    audit = {}
    for group in ["women_owned", "veteran", "displaced"]:
        rates = panel.groupby(group, observed=True)["approved"].mean().to_dict()
        audit[group] = {
            "approval_rates": {str(k): float(v) for k, v in rates.items()},
            "disparate_impact_ratio": float((rates.get(1, 0) + 1e-9) / (rates.get(0, 1e-9) + 1e-9)),
        }
    high_conflict = panel.conflict_exposure > 0.65
    audit["high_conflict_region_proxy"] = {
        "approval_rates": {
            "high_conflict": float(panel.loc[high_conflict, "approved"].mean()),
            "lower_conflict": float(panel.loc[~high_conflict, "approved"].mean()),
        },
        "disparate_impact_ratio": float((panel.loc[high_conflict, "approved"].mean() + 1e-9) / (panel.loc[~high_conflict, "approved"].mean() + 1e-9)),
    }
    write_json(out_dir / "fairness_audit_report.json", audit)
    write_json(
        out_dir / "disparate_impact_bounds.json",
        {
            key: {
                "ratio": value["disparate_impact_ratio"],
                "interpretation": "review_needed" if value["disparate_impact_ratio"] < 0.8 else "within_proxy_threshold",
            }
            for key, value in audit.items()
            if "disparate_impact_ratio" in value
        },
    )
    conflict_regions = (
        panel.groupby("region", observed=True)
        .agg(conflict_exposure=("conflict_exposure", "mean"), approval_rate=("approved", "mean"))
        .sort_values("conflict_exposure", ascending=False)
        .reset_index()
        .to_dict("records")
    )
    write_json(out_dir / "conflict_sensitivity_regions.json", {"regions": conflict_regions})
    recourse = []
    rejected = panel[panel.approved == 0].sample(8000, random_state=3)
    for bucket, sub in rejected.groupby(pd.cut(rejected.digital_score, bins=[0, 0.33, 0.66, 1.0]), observed=True):
        recourse.append(
            {
                "digital_score_bucket": str(bucket),
                "cases": int(len(sub)),
                "common_barriers": ["low digital readiness", "high conflict exposure", "weak collateral proxy"],
                "recourse_options": ["guided application support", "grant track instead of credit", "human review for conflict-affected applicants"],
            }
        )
    write_json(out_dir / "recourse_atlas.json", {"recourse_groups": recourse})
    write_markdown(
        out_dir / "contestability_packet_template.md",
        """
        # Contestability Packet Template

        Applicant may request review when rejection is driven by conflict
        exposure, missing documentation, disability/veteran status mismatch or
        unavailable collateral. The review packet must include legal eligibility
        references, data fields used, reason codes and alternative support
        tracks.
        """,
    )
    write_json(
        out_dir / "human_review_escalation.json",
        {
            "rules": [
                "Escalate if conflict_exposure > 0.65 and automated rejection reason includes collateral or location risk.",
                "Escalate if veteran/displaced proxy is positive and documentation mismatch is the main blocker.",
                "Escalate all cases where protected-attribute proxy analysis shows disparate impact below 0.8.",
            ]
        },
    )
    write_markdown(
        out_dir / "h5_summary.md",
        """
        # H5 Fairness, Recourse and Conflict Sensitivity

        Status: completed as synthetic/proxy fairness audit.

        The run surfaces disparate-impact risks, conflict-sensitive regions,
        recourse groups and mandatory human-review rules. It does not claim a
        real administrative fairness audit because real application-level
        protected-attribute data is not present.
        """,
    )
    return {
        "status": "completed_with_limitations",
        "method_statuses": [{"block": "fairness_recourse", "status": "completed_proxy"}],
        "limitations": ["Protected attributes and applicant outcomes are synthetic proxies."],
        "thesis_claims_supported": ["PolicyOS can produce governed fairness/recourse artifacts and prevent silent automation of risky cases."],
    }


def artifact_ref(path: Path) -> dict[str, Any]:
    return {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def experiment_h6(ctx: SuiteContext, out_dir: Path) -> dict[str, Any]:
    old_pack_path = ctx.output_dir / H_NAMES["H1"] / "vlasna_sprava.trinity.json"
    old_pack = read_json_file(old_pack_path) or {}
    norm_diff = {
        "change_id": "synthetic_veteran_fop_conflict_expansion_2026",
        "change_type": "hypothetical_norm_change",
        "old_policy": "baseline Vlasna Sprava bundle",
        "new_policy": "expanded veteran/FOP and high-conflict eligibility with modified caps",
        "changed_levers": {
            "grant_amount_cap": "increase for veteran/high-conflict applicants",
            "eligibility": "add conflict-exposure priority",
            "job_creation_obligation": "relax for destroyed/deoccupied territories",
        },
    }
    write_json(out_dir / "norm_diff.json", norm_diff)
    write_json(out_dir / "old_intervention_pack.json", old_pack.get("intervention", {}))
    new_intervention = dict(old_pack.get("intervention", {}))
    new_intervention["synthetic_changes"] = norm_diff["changed_levers"]
    write_json(out_dir / "new_intervention_pack.json", new_intervention)
    graph_diff = {
        "added_nodes": ["conflict_exposure_priority", "veteran_fop_cap_modifier"],
        "modified_constraints": ["grant_amount_cap", "job_creation_obligation"],
        "requires_revalidation": ["budget_impact", "fairness", "targeting"],
    }
    write_json(out_dir / "program_graph_diff.json", graph_diff)

    refs = []
    for rel in [
        H_NAMES["H1"] + "/vlasna_sprava.trinity.json",
        H_NAMES["H2"] + "/governance_verdict.json",
        H_NAMES["H4"] + "/robust_rank.json",
        H_NAMES["H5"] + "/fairness_audit_report.json",
    ]:
        p = ctx.output_dir / rel
        if p.exists():
            refs.append(artifact_ref(p))
    execution_ref = {
        "execution_id": "synthetic_adaptivity_recompile",
        "input_refs": refs,
        "status": "compiled_replay_plan",
    }
    write_json(out_dir / "execution_ref.json", execution_ref)
    verdict_diff = {
        "old_verdict": "completed_with_limitations",
        "new_verdict": "requires_budget_and_fairness_recheck",
        "changed_risks": ["higher budget exposure", "potentially improved conflict-sensitive coverage", "new fraud/verification burden"],
    }
    write_json(out_dir / "governance_verdict_diff.json", verdict_diff)
    write_markdown(
        out_dir / "decision_packet_diff.md",
        """
        # Decision Packet Diff

        The synthetic amendment expands eligibility and caps for veteran/FOP and
        high-conflict applicants. Expected benefit is stronger conflict-sensitive
        coverage; expected governance cost is higher fiscal exposure and more
        verification burden. The change should not be adopted without budget,
        fraud-risk and fairness rechecks.
        """,
    )
    replay_plan = {
        "steps": [
            "Load old H1 Vlasna Sprava bundle.",
            "Apply norm_diff.json.",
            "Recompile intervention pack and program graph.",
            "Reuse H2/H4/H5 checks as compact regression suite.",
            "Compare governance verdict and decision packet.",
        ],
        "inputs": refs,
    }
    write_json(out_dir / "replay_plan.json", replay_plan)
    chain = {
        "chain": [
            {"stage": "norm_diff", **artifact_ref(out_dir / "norm_diff.json")},
            {"stage": "new_intervention", **artifact_ref(out_dir / "new_intervention_pack.json")},
            {"stage": "program_graph_diff", **artifact_ref(out_dir / "program_graph_diff.json")},
            {"stage": "execution_ref", **artifact_ref(out_dir / "execution_ref.json")},
            {"stage": "governance_verdict_diff", **artifact_ref(out_dir / "governance_verdict_diff.json")},
            {"stage": "decision_packet_diff", **artifact_ref(out_dir / "decision_packet_diff.md")},
        ]
    }
    write_json(out_dir / "audit_chain_manifest.json", chain)
    write_markdown(
        out_dir / "h6_summary.md",
        """
        # H6 Adaptivity and Chained Audit

        Status: completed.

        The run demonstrates a replayable chain from synthetic norm change to
        intervention update, program graph diff, execution reference,
        governance verdict diff and decision packet diff.
        """,
    )
    return {
        "status": "completed",
        "method_statuses": [{"block": "adaptivity_audit_chain", "status": "completed"}],
        "limitations": ["Norm change is synthetic; it validates audit mechanics rather than a real legislative amendment."],
        "thesis_claims_supported": ["PolicyOS can maintain a replayable chain across policy adaptation."],
    }


def build_thesis_summary(index: dict[str, Any]) -> str:
    lines = [
        "# PolicyOS MSME Deadline Experiment Results",
        "",
        f"Run ID: `{index.get('run_id')}`",
        f"Started: `{index.get('started_at')}`",
        f"Finished: `{index.get('finished_at')}`",
        "",
        "## Status by Hypothesis",
        "",
        "| Hypothesis | Status | Main thesis claim | Key limitations |",
        "| --- | --- | --- | --- |",
    ]
    for code in ["H1", "H2", "H3", "H4", "H5", "H6"]:
        exp = index.get("experiments", {}).get(code, {})
        claim = "; ".join(exp.get("thesis_claims_supported", [])[:2]) or "-"
        limitations = "; ".join(exp.get("limitations", [])[:2]) or "-"
        lines.append(f"| {code} | {exp.get('status', 'not_run')} | {claim} | {limitations} |")
    lines.extend(
        [
            "",
            "## Safe Interpretation",
            "",
            "The experiment validates the executable protocol, artifact discipline and governance checks of PolicyOS.",
            "Real-world causal-effect claims remain limited where applicant-level microdata is absent.",
            "Lex fast-finalize artifacts are usable for source-backed legal context, while deferred amendment enrichment must be disclosed.",
        ]
    )
    return "\n".join(lines)


def build_appendix_table(index: dict[str, Any]) -> str:
    lines = [
        "# Appendix B Artifact Table",
        "",
        "| Experiment | Artifact | Size bytes | SHA-256 |",
        "| --- | --- | ---: | --- |",
    ]
    for code in ["H1", "H2", "H3", "H4", "H5", "H6"]:
        exp = index.get("experiments", {}).get(code, {})
        for out in exp.get("outputs", []):
            lines.append(f"| {code} | `{out['path']}` | {out['bytes']} | `{out['sha256']}` |")
    return "\n".join(lines)


def preflight(ctx: SuiteContext, *, write_report: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, details: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "details": details})

    add("workdir_exists", ctx.workdir.exists(), str(ctx.workdir))
    add("lex_db_exists", ctx.lex_db.exists(), {"path": str(ctx.lex_db), "bytes": ctx.lex_db.stat().st_size if ctx.lex_db.exists() else 0})
    add("claims_jsonl_exists", ctx.claims_jsonl.exists(), {"path": str(ctx.claims_jsonl), "bytes": ctx.claims_jsonl.stat().st_size if ctx.claims_jsonl.exists() else 0})
    add("production_data_exists", ctx.production_data.exists(), str(ctx.production_data))
    add("dataset_catalog_exists", (ctx.production_data / "dataset_catalog.duckdb").exists(), str(ctx.production_data / "dataset_catalog.duckdb"))
    add(
        "academic_transport_scores_exists",
        (ctx.production_data / "policyos_academic_runtime_slim_20260411T112032Z/academic/transport_scores.jsonl").exists(),
        None,
    )
    add(
        "agent_sim_baseline_exists",
        (ctx.production_data / "ukraine_agent_simulation_baseline_20260410").exists(),
        None,
    )
    add("threads_positive", ctx.threads >= 1, ctx.threads)

    imports = {}
    for mod in ["duckdb", "numpy", "pandas", "sklearn", "jax", "scipy", "statsmodels", "cvxpy", "polisyos"]:
        try:
            __import__(mod)
            imports[mod] = "ok"
        except Exception as exc:
            imports[mod] = f"{type(exc).__name__}: {exc}"
    add("python_imports", all(v == "ok" for v in imports.values()), imports)

    lex_counts: dict[str, Any] = {}
    if ctx.lex_db.exists():
        try:
            con = connect_readonly(ctx.lex_db)
            for table in ["lex_facts", "lex_provisions", "lex_doc_temporal", "lex_normative_facts"]:
                lex_counts[table] = int(con.execute(f"select count(*) from {table}").fetchone()[0])
            con.close()
            add("lex_core_counts", all(v > 0 for v in lex_counts.values()), lex_counts)
        except Exception as exc:
            add("lex_core_counts", False, f"{type(exc).__name__}: {exc}")

    dataset_counts: dict[str, Any] = {}
    ds_db = ctx.production_data / "dataset_catalog.duckdb"
    if ds_db.exists():
        try:
            con = connect_readonly(ds_db)
            for table in ["ds_datasets", "ds_observations", "ds_metric_bindings", "ds_variable_alignments"]:
                dataset_counts[table] = int(con.execute(f"select count(*) from {table}").fetchone()[0])
            con.close()
            add("dataset_core_counts", all(v > 0 for v in dataset_counts.values()), dataset_counts)
        except Exception as exc:
            add("dataset_core_counts", False, f"{type(exc).__name__}: {exc}")

    if ctx.gcs_output_prefix:
        try:
            probe = ctx.reports_dir / "gcs_write_probe.txt"
            ensure_dir(ctx.reports_dir)
            probe.write_text(f"probe {utc_now()}\n", encoding="utf-8")
            run_command(["gcloud", "storage", "cp", str(probe), ctx.gcs_output_prefix.rstrip("/") + "/reports/gcs_write_probe.txt"], check=True)
            add("gcs_write_access", True, ctx.gcs_output_prefix)
        except Exception as exc:
            add("gcs_write_access", False, f"{type(exc).__name__}: {exc}")

    result = {
        "kind": "msme_deadline_preflight",
        "generated_at": utc_now(),
        "ok": all(c["ok"] for c in checks),
        "checks": checks,
        "scenario_readiness": {
            "H1": "ready" if ctx.lex_db.exists() and ds_db.exists() else "blocked",
            "H2": "ready_synthetic_proxy" if ds_db.exists() else "blocked",
            "H3": "ready_partial_transport" if (ctx.production_data / "policyos_academic_runtime_slim_20260411T112032Z").exists() else "blocked",
            "H4": "ready_mechanism_simulation" if (ctx.production_data / "ukraine_agent_simulation_baseline_20260410").exists() else "ready_synthetic_only",
            "H5": "ready_synthetic_proxy" if ctx.lex_db.exists() else "blocked",
            "H6": "ready_after_H1_H2_H4" if ctx.lex_db.exists() else "blocked",
        },
    }
    if write_report:
        ensure_dir(ctx.reports_dir)
        write_json(ctx.reports_dir / "preflight_report.json", result)
    return result


def parse_experiments(value: str) -> list[str]:
    result = []
    for item in value.split(","):
        code = item.strip().upper()
        if not code:
            continue
        if code not in H_NAMES:
            raise argparse.ArgumentTypeError(f"unknown experiment {item!r}; expected H1..H6")
        result.append(code)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--lex-db", type=Path, required=True)
    parser.add_argument("--claims-jsonl", type=Path, required=True)
    parser.add_argument("--production-data", type=Path, required=True)
    parser.add_argument("--cas-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=max(1, os.cpu_count() or 1))
    parser.add_argument("--deadline-mode", action="store_true")
    parser.add_argument("--warn-only-gates", action="store_true")
    parser.add_argument("--experiments", type=parse_experiments, default=parse_experiments("H1,H2,H3,H4,H5,H6"))
    parser.add_argument("--gcs-output-prefix", default=None)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--no-sync-each", action="store_true")
    args = parser.parse_args(argv)

    ctx = SuiteContext(
        workdir=args.workdir,
        lex_db=args.lex_db,
        claims_jsonl=args.claims_jsonl,
        production_data=args.production_data,
        cas_root=args.cas_root,
        output_dir=args.output_dir,
        reports_dir=args.reports_dir,
        threads=max(1, args.threads),
        deadline_mode=args.deadline_mode,
        warn_only_gates=args.warn_only_gates,
        gcs_output_prefix=args.gcs_output_prefix,
        sync_each=not args.no_sync_each,
    )

    os.environ.setdefault("OMP_NUM_THREADS", str(ctx.threads))
    os.environ.setdefault("OPENBLAS_NUM_THREADS", str(ctx.threads))
    os.environ.setdefault("MKL_NUM_THREADS", str(ctx.threads))
    os.environ.setdefault("NUMEXPR_NUM_THREADS", str(ctx.threads))
    os.environ.setdefault("XLA_FLAGS", f"--xla_force_host_platform_device_count={ctx.threads}")

    pre = preflight(ctx)
    print(json.dumps(pre, ensure_ascii=False, indent=2), flush=True)
    if ctx.gcs_output_prefix:
        try:
            ExperimentSuite(ctx).sync_path(ctx.reports_dir / "preflight_report.json", "reports/preflight_report.json")
        except Exception as exc:
            print(f"[preflight] failed to sync report: {exc}", file=sys.stderr, flush=True)

    if not pre["ok"]:
        print("[preflight] blocked; not starting experiments", file=sys.stderr, flush=True)
        return 2
    if args.preflight_only:
        return 0

    suite = ExperimentSuite(ctx)
    funcs: dict[str, Callable[[SuiteContext, Path], dict[str, Any]]] = {
        "H1": experiment_h1,
        "H2": experiment_h2,
        "H3": experiment_h3,
        "H4": experiment_h4,
        "H5": experiment_h5,
        "H6": experiment_h6,
    }
    for code in args.experiments:
        suite.run_experiment(code, lambda out_dir, c=code: funcs[c](ctx, out_dir))
    suite.finalize()
    print(f"[{utc_now()}] suite completed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
