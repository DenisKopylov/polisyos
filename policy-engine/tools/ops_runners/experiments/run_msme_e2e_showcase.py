#!/usr/bin/env python3
"""End-to-end PolicyOS showcase experiments for the MSME thesis deadline.

This runner complements the H1-H6 deadline suite.  H1-H6 produced useful
artifacts quickly; this runner exercises the composition story: policy intent,
retrieval, Fabric trust envelopes, Foundry compile/execute, a CPU-heavy policy
optimization arena, and a thesis-facing decision packet.

The script is deliberately conservative about claims.  When LLM credentials are
not available it writes deterministic agent outputs and records that fallback in
the machine-readable manifest instead of pretending that an LLM loop ran.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import dataclasses
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import time
import traceback
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

PROGRAMS = {
    "vlasna_sprava": "Власна справа",
    "five_seven_nine": "Доступні кредити 5-7-9%",
    "tax_relief": "Податкові та регуляторні полегшення для МСП / ФОП",
}

DEFAULT_POLICY_INTENT = (
    "Design an optimal wartime Ukrainian SME support policy for 2026 that "
    "balances business survival, employment preservation, regional resilience, "
    "fiscal responsibility, fairness, and conflict-sensitive targeting under "
    "incomplete applicant-level microdata."
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def json_default(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
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


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path, limit: int | None = None) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for index, line in enumerate(f):
            if limit is not None and index >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(block_size):
            digest.update(chunk)
    return digest.hexdigest()


def run_cmd(
    cmd: list[str], *, cwd: Path | None = None, timeout: int | None = None
) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return {
        "cmd": [cmd[0], *cmd[1:]],
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def sync_to_gcs(local_path: Path, gcs_uri: str | None) -> dict[str, Any]:
    if not gcs_uri:
        return {"enabled": False}
    if not local_path.exists():
        return {
            "enabled": True,
            "ok": False,
            "reason": "local_path_missing",
            "local_path": str(local_path),
        }
    result = run_cmd(["gcloud", "storage", "rsync", "-r", str(local_path), gcs_uri], timeout=3600)
    result["enabled"] = True
    result["ok"] = result["returncode"] == 0
    result["gcs_uri"] = gcs_uri
    result["local_path"] = str(local_path)
    return result


def env_thread_profile(threads: int) -> dict[str, str]:
    profile = {
        "POLISYOS_EXPERIMENT_THREADS": str(threads),
        "OMP_NUM_THREADS": str(threads),
        "MKL_NUM_THREADS": str(threads),
        "OPENBLAS_NUM_THREADS": str(threads),
        "NUMEXPR_MAX_THREADS": str(threads),
        "JAX_PLATFORMS": "cpu",
        "JAX_PLATFORM_NAME": "cpu",
        "XLA_FLAGS": f"--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads={threads}",
    }
    os.environ.update(profile)
    return profile


def safe_env_file_values(patterns: list[str]) -> dict[str, str]:
    """Read possible key values without ever printing them.

    Returned values are used only in-process for optional LLM calls.  Artifacts
    record variable names and availability, not values.
    """
    result: dict[str, str] = {}
    for pattern in patterns:
        for path in sorted(
            Path("/").glob(pattern.lstrip("/"))
            if pattern.startswith("/")
            else Path(".").glob(pattern)
        ):
            if not path.is_file():
                continue
            try:
                for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#") or "=" not in stripped:
                        continue
                    key, value = stripped.split("=", 1)
                    key = key.strip().replace("export ", "")
                    value = value.strip().strip("'\"")
                    if (
                        key
                        and value
                        and any(token in key.upper() for token in ("GONKA", "OPENAI", "LLM"))
                    ):
                        result.setdefault(key, value)
            except OSError:
                continue
    return result


def discover_llm_config(repo_root: Path, workdir: Path, model: str | None) -> dict[str, Any]:
    candidates: dict[str, str] = {}
    for key, value in os.environ.items():
        if (
            value
            and any(token in key.upper() for token in ("GONKA", "OPENAI"))
            and "KEY" in key.upper()
        ):
            candidates.setdefault(key, value)
    if not candidates:
        candidates.update(
            safe_env_file_values(
                [
                    str(repo_root / "ops/cloud/deploy/assets/.env.server_*"),
                    str(repo_root / ".env"),
                    str(workdir / ".env"),
                ]
            )
        )
    key_name = next((name for name in candidates if "GONKA" in name.upper()), None)
    if key_name is None:
        key_name = next((name for name in candidates if "OPENAI" in name.upper()), None)
    api_key = candidates.get(key_name or "", "")
    base_url = (
        os.environ.get("GONKA_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.gonkagate.com/v1"
    )
    return {
        "available": bool(api_key),
        "key_name": key_name,
        "api_key": api_key,
        "base_url": base_url,
        "model": model or os.environ.get("GONKA_MODEL") or "qwen/qwen3-235b-a22b-instruct-2507-fp8",
        "candidate_key_names": sorted(candidates.keys()),
    }


def call_llm_if_available(
    llm: dict[str, Any],
    *,
    system: str,
    prompt: str,
    max_tokens: int = 1200,
) -> dict[str, Any]:
    if not llm.get("available"):
        return {"used": False, "status": "llm_unavailable"}
    try:
        from openai import OpenAI

        client = OpenAI(api_key=llm["api_key"], base_url=llm["base_url"], timeout=90.0)
        started = time.perf_counter()
        response = client.chat.completions.create(
            model=llm["model"],
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        return {
            "used": True,
            "status": "ok",
            "model": llm["model"],
            "base_url": llm["base_url"],
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "content": content,
        }
    except Exception as exc:
        return {
            "used": False,
            "status": "llm_call_failed",
            "model": llm.get("model"),
            "base_url": llm.get("base_url"),
            "error_type": type(exc).__name__,
            "error": str(exc)[:1000],
        }


def legal_evidence_keywords() -> list[str]:
    return [
        "мікрогрант",
        "єробота",
        "власна справа",
        "5-7-9",
        "доступні кредити",
        "фонд розвитку підприємництва",
        "малого та середнього підприємництва",
        "спрощена система",
        "єдиний податок",
        "воєнний стан",
        "ветеран",
        "внутрішньо переміщ",
        "деокупован",
    ]


def collect_retrieval_evidence(
    runs_dir: Path, lex_db: Path, output_dir: Path
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    keywords = legal_evidence_keywords()
    h1_pack = runs_dir / "H1_formalization/legal_source_pack.jsonl"
    seen: set[str] = set()
    for row in iter_jsonl(h1_pack, limit=20000):
        text = f"{row.get('doc_name', '')} {row.get('citation', '')} {row.get('text', '')}".lower()
        if not any(keyword.lower() in text for keyword in keywords):
            continue
        source_id = str(row.get("source_id") or row.get("doc_id") or len(rows))
        if source_id in seen:
            continue
        seen.add(source_id)
        rows.append(
            {
                "source": "H1_legal_source_pack",
                "source_id": source_id,
                "doc_id": row.get("doc_id"),
                "doc_name": row.get("doc_name"),
                "doc_type": row.get("doc_type"),
                "doc_status": row.get("doc_status"),
                "citation": row.get("citation"),
                "snippet": str(row.get("text", ""))[:1200],
                "keyword_hits": [keyword for keyword in keywords if keyword.lower() in text],
            }
        )
        if len(rows) >= 80:
            break

    if lex_db.exists() and len(rows) < 120:
        try:
            con = duckdb.connect(str(lex_db), read_only=True)
            tables = {name for (name,) in con.execute("show tables").fetchall()}
            if "lex_doc_domains" in tables:
                sample = con.execute("select * from lex_doc_domains limit 40").fetchall()
                columns = [desc[0] for desc in con.description]
                for item in sample:
                    payload = dict(zip(columns, item, strict=False))
                    rows.append(
                        {
                            "source": "lex_knowledge_graph.lex_doc_domains",
                            "source_id": sha256_text(
                                json.dumps(payload, ensure_ascii=False, default=str)
                            )[:20],
                            "snippet": json.dumps(payload, ensure_ascii=False, default=str)[:1200],
                            "keyword_hits": [],
                        }
                    )
            con.close()
        except Exception as exc:
            rows.append(
                {
                    "source": "lex_knowledge_graph",
                    "source_id": "duckdb_sample_failed",
                    "snippet": f"{type(exc).__name__}: {exc}",
                    "keyword_hits": [],
                }
            )
    write_jsonl(output_dir / "retrieval_evidence.jsonl", rows)
    return rows


def deterministic_candidate_designs(evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    legal_sources = [
        row.get("source_id")
        for row in evidence_rows[:30]
        if row.get("source") == "H1_legal_source_pack"
    ]
    return [
        {
            "policy_id": "resilience_grant_plus_credit_guarantee",
            "label": "Resilience grant + 5-7-9 credit guarantee",
            "target": "micro and small firms in frontline/deoccupied/high-displacement regions",
            "levers": {
                "microgrant_cap_uah": 250_000,
                "loan_cap_uah": 2_000_000,
                "interest_subsidy_rate": 0.09,
                "conflict_weight": 0.75,
                "veteran_idp_priority": True,
                "job_preservation_condition": "soft",
            },
            "expected_strength": "high resilience and employment preservation under moderate fiscal cost",
            "main_risks": [
                "requires anti-fraud screening",
                "real applicant-level data is missing in current experiment",
                "credit channel may underserve informal micro-firms",
            ],
            "legal_evidence_refs": legal_sources[:10],
        },
        {
            "policy_id": "fast_microgrant_admin_relief",
            "label": "Fast microgrant with administrative relief",
            "target": "new or interrupted microbusinesses needing rapid restart",
            "levers": {
                "microgrant_cap_uah": 150_000,
                "loan_cap_uah": 0,
                "interest_subsidy_rate": 0.0,
                "conflict_weight": 0.9,
                "tax_relief_rate": 0.04,
                "paperwork_cut": 0.55,
            },
            "expected_strength": "fast uptake, good for deadline/public-value scenarios",
            "main_risks": [
                "lower capital depth than credit-supported variant",
                "outcome measurement requires later registry linkage",
            ],
            "legal_evidence_refs": legal_sources[10:20],
        },
        {
            "policy_id": "tax_relief_with_targeted_recourse",
            "label": "Tax relief plus targeted recourse for rejected applicants",
            "target": "FOP and SMEs under wartime liquidity stress",
            "levers": {
                "microgrant_cap_uah": 100_000,
                "loan_cap_uah": 1_000_000,
                "interest_subsidy_rate": 0.05,
                "conflict_weight": 0.55,
                "tax_relief_rate": 0.06,
                "human_review_share": 0.12,
            },
            "expected_strength": "fairness and recourse, especially when automated eligibility is uncertain",
            "main_risks": [
                "budget revenue loss is hard to estimate with available data",
                "protected attributes are proxy/synthetic in current run",
            ],
            "legal_evidence_refs": legal_sources[20:30],
        },
    ]


def run_s1_policy_design(ctx: dict[str, Any]) -> dict[str, Any]:
    output_dir = ensure_dir(ctx["output_dir"] / "S1_policy_intent_agent_loop")
    started = utc_now()
    intent = {
        "question": DEFAULT_POLICY_INTENT,
        "domain": "wartime Ukraine MSME support policy",
        "deadline_context": "qualification thesis experiments due 2026-05-01",
        "required_claim_posture": "bounded/proxy-aware/no overclaiming",
        "created_at": started,
    }
    write_json(output_dir / "policy_intent.json", intent)

    evidence_rows = collect_retrieval_evidence(ctx["runs_dir"], ctx["lex_db"], output_dir)
    designs = deterministic_candidate_designs(evidence_rows)

    prompt_evidence = "\n\n".join(
        f"- {row.get('doc_name') or row.get('source')}: {row.get('snippet', '')[:500]}"
        for row in evidence_rows[:12]
    )
    llm_prompt = (
        f"Policy intent:\n{DEFAULT_POLICY_INTENT}\n\n"
        f"Evidence snippets:\n{prompt_evidence}\n\n"
        "Return a concise policy design memo with candidate policies, assumptions, "
        "risks, and evidence limitations. Do not claim real causal effects."
    )
    llm_result = call_llm_if_available(
        ctx["llm"],
        system=(
            "You are a careful public-policy design agent for PolicyOS. "
            "You must distinguish verified evidence, proxy evidence, and missing data."
        ),
        prompt=llm_prompt,
        max_tokens=1800,
    )
    transcript_rows = [
        {
            "role": "policy_planner",
            "status": llm_result["status"],
            "used_llm": bool(llm_result.get("used")),
            "content": llm_result.get("content")
            or "Deterministic fallback generated candidate designs from Lex/H1/H4 artifacts.",
        },
        {
            "role": "data_scout",
            "status": "deterministic_retrieval",
            "used_llm": False,
            "content": f"Collected {len(evidence_rows)} legal/dataset evidence snippets.",
        },
        {
            "role": "governance_reviewer",
            "status": "deterministic_caveat",
            "used_llm": False,
            "content": (
                "Real applicant-level treatment/outcome microdata is absent; "
                "recommendations are proxy/simulation outputs."
            ),
        },
    ]
    write_jsonl(output_dir / "agent_transcript.jsonl", transcript_rows)
    write_json(
        output_dir / "agent_plan.json",
        {
            "planner_mode": "llm" if llm_result.get("used") else "deterministic_fallback",
            "llm_status": {k: v for k, v in llm_result.items() if k != "content"},
            "steps": [
                "retrieve legal evidence",
                "retrieve dataset/proxy evidence",
                "construct candidate policy designs",
                "score designs in S4 optimization arena",
                "produce governance decision packet",
            ],
        },
    )
    write_json(output_dir / "candidate_policy_designs.json", {"designs": designs})
    write_markdown(
        output_dir / "s1_policy_design_summary.md",
        f"""
# S1 Policy Intent and Agentic Design Loop

Status: `completed_with_{"llm" if llm_result.get("used") else "deterministic_fallback"}`

The run converted the natural-language MSME policy question into {len(designs)}
candidate policy designs and attached {len(evidence_rows)} evidence snippets.

LLM status: `{llm_result["status"]}`. If this is a fallback run, it remains
useful for the thesis as an auditable design-loop demonstration, but it should
not be described as a Gonka/LLM-agent run.
""",
    )
    result = {
        "experiment_id": "S1_policy_intent_agent_loop",
        "status": "completed_with_llm"
        if llm_result.get("used")
        else "completed_with_deterministic_fallback",
        "started_at": started,
        "finished_at": utc_now(),
        "evidence_rows": len(evidence_rows),
        "candidate_designs": len(designs),
        "llm_status": {k: v for k, v in llm_result.items() if k != "content"},
    }
    write_json(output_dir / "experiment_result.json", result)
    ctx["sync"](output_dir, "S1_policy_intent_agent_loop")
    return result


def build_runtime_quantities_from_prior_outputs(ctx: dict[str, Any]) -> list[Any]:
    from polisyos.core.contracts.runtime import (
        LineageRef,
        QuantityUncertainty,
        QuantityValue,
        TemporalRef,
        UnitRef,
        VerificationMetadata,
    )

    now = datetime.now(UTC).replace(microsecond=0)
    h4 = read_json(ctx["runs_dir"] / "H4_mechanism_welfare/welfare_table.json", {})
    frontier = read_json(ctx["runs_dir"] / "H4_mechanism_welfare/pareto_frontier.json", {})
    h1 = read_json(ctx["runs_dir"] / "H1_formalization/experiment_result.json", {})
    h2 = read_json(ctx["runs_dir"] / "H2_causal_stack/experiment_result.json", {})
    h5 = read_json(ctx["runs_dir"] / "H5_fairness_recourse/experiment_result.json", {})
    top = (h4.get("top_scenarios") or [{}])[0]
    lineage_base = LineageRef(
        id="msme_deadline_harness:H4_mechanism_welfare",
        hash=sha256_text(json.dumps(top, ensure_ascii=False, default=str)),
        status="pending",
        freshness="current",
        summary={"artifact": "runs/H4_mechanism_welfare/welfare_table.json"},
        trust_metadata=VerificationMetadata(
            hash=sha256_text(json.dumps(top, ensure_ascii=False, default=str)),
            verification_status="pending",
            freshness="current",
        ),
    )
    temporal = TemporalRef(valid_at=now, tx_at=now, snapshot_id="msme_deadline_20260430")
    quantities = [
        QuantityValue(
            point=float(top.get("employment_gain_mean", 0.0)),
            unit=UnitRef(code="1", display="share"),
            metric_id="employment_gain_mean",
            label="Expected employment preservation proxy",
            lineage=lineage_base,
            time=temporal,
            uncertainty=QuantityUncertainty(
                method="simulation", identifiability="estimated", ci_95=(0.0, 0.02)
            ),
        ),
        QuantityValue(
            point=float(top.get("fiscal_cost", 0.0)),
            unit=UnitRef(code="UAH", system="currency", display="UAH"),
            metric_id="fiscal_cost_uah",
            label="Fiscal cost proxy",
            lineage=lineage_base,
            time=temporal,
            uncertainty=QuantityUncertainty(method="simulation", identifiability="estimated"),
        ),
        QuantityValue(
            point=float(top.get("coverage_conflict_high", 0.0)),
            unit=UnitRef(code="1", display="share"),
            metric_id="conflict_sensitive_coverage",
            label="High-conflict-region coverage proxy",
            lineage=lineage_base,
            time=temporal,
            uncertainty=QuantityUncertainty(method="simulation", identifiability="estimated"),
        ),
        QuantityValue(
            point=float(frontier.get("frontier_size") or 0),
            unit=UnitRef(code="1", display="count"),
            metric_id="pareto_frontier_size",
            label="Pareto frontier size",
            lineage=lineage_base,
            time=temporal,
            uncertainty=QuantityUncertainty(method="none", identifiability="assumed"),
        ),
        QuantityValue(
            point=float(len(h1.get("outputs", []))),
            unit=UnitRef(code="1", display="count"),
            metric_id="h1_artifact_count",
            label="Formalization artifact count",
            lineage=LineageRef(
                id="msme_deadline_harness:H1_formalization",
                status="pending",
                freshness="current",
                summary={"artifact": "runs/H1_formalization/experiment_result.json"},
            ),
            time=temporal,
            uncertainty=QuantityUncertainty(method="none", identifiability="assumed"),
        ),
        QuantityValue(
            point=float(len(h2.get("limitations", [])) + len(h5.get("limitations", []))),
            unit=UnitRef(code="1", display="count"),
            metric_id="identified_limitations_count",
            label="Known limitations from causal/fairness runs",
            lineage=LineageRef(
                id="msme_deadline_harness:limitations",
                status="pending",
                freshness="current",
                summary={"artifact": "runs/H2_causal_stack and runs/H5_fairness_recourse"},
            ),
            time=temporal,
            uncertainty=QuantityUncertainty(method="none", identifiability="assumed"),
        ),
    ]
    return quantities


def run_s2_fabric_trust_flow(ctx: dict[str, Any]) -> dict[str, Any]:
    output_dir = ensure_dir(ctx["output_dir"] / "S2_fabric_runtime_trust_flow")
    started = utc_now()
    try:
        from polisyos.core.contracts.runtime import QuantityCoverageSummary, TemporalScope
        from polisyos.fabric.decision_data import (
            SourceContractRef,
            coverage_from_decision_data,
            from_runtime_quantities,
        )
        from polisyos.fabric.product_integration import evidence_paths_from_fabric_decision_data

        quantities = build_runtime_quantities_from_prior_outputs(ctx)
        coverage = QuantityCoverageSummary(
            total=len(quantities),
            decision=len(quantities),
            traced=0,
            untraced=0,
        )
        temporal_scope = TemporalScope(
            valid_at=datetime.now(UTC).replace(microsecond=0),
            tx_at=datetime.now(UTC).replace(microsecond=0),
            snapshot_id="msme_deadline_20260430",
        )
        source_contract = SourceContractRef(
            id="policyos.msme.deadline.showcase", version="2026-05-01"
        )
        decision_data = from_runtime_quantities(
            quantities,
            source_contract=source_contract,
            temporal_scope=temporal_scope,
            owner="@policyos-msme-thesis",
        )
        fabric_coverage = coverage_from_decision_data(decision_data)
        evidence_paths = evidence_paths_from_fabric_decision_data(
            decision_data, source_trust_tier="medium"
        )
        foundry_context = [
            {
                "metric_id": row.value.metric_id,
                "calibration_weight": path.calibration_weight,
                "uncertainty_inflation": path.uncertainty_inflation,
                "quality_status": path.quality_status,
                "replay_status": path.replay_status,
            }
            for row, path in zip(decision_data, evidence_paths, strict=False)
        ]
        write_json(
            output_dir / "runtime_quantities.json", [q.model_dump(mode="json") for q in quantities]
        )
        write_json(
            output_dir / "fabric_decision_data.json",
            [row.model_dump(mode="json") for row in decision_data],
        )
        write_json(output_dir / "fabric_coverage.json", fabric_coverage.model_dump(mode="json"))
        write_json(
            output_dir / "fabric_evidence_paths.json",
            [path.model_dump(mode="json") for path in evidence_paths],
        )
        write_json(output_dir / "fabric_to_foundry_context.json", foundry_context)
        status = "completed"
        error = None
    except Exception as exc:
        status = "failed_with_diagnostics"
        error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc()[-6000:],
        }
        write_json(output_dir / "fabric_error.json", error)
        quantities = []
        decision_data = []
        evidence_paths = []
        foundry_context = []
    write_markdown(
        output_dir / "s2_fabric_trust_flow_summary.md",
        f"""
# S2 Fabric Runtime Trust Flow

Status: `{status}`

Runtime-style quantities: {len(quantities)}

Fabric decision-data envelopes: {len(decision_data)}

Product evidence paths: {len(evidence_paths)}

This stage is the bridge from experiment numbers to Fabric-governed decision
data. It is intentionally strict about typed envelopes; if it fails, the error
diagnostic is preserved instead of silently returning naked numbers.
""",
    )
    result = {
        "experiment_id": "S2_fabric_runtime_trust_flow",
        "status": status,
        "started_at": started,
        "finished_at": utc_now(),
        "runtime_quantities": len(quantities),
        "fabric_decision_data": len(decision_data),
        "foundry_context_rows": len(foundry_context),
        "error": error,
    }
    write_json(output_dir / "experiment_result.json", result)
    ctx["sync"](output_dir, "S2_fabric_runtime_trust_flow")
    return result


def run_s3_foundry_compile_execute(ctx: dict[str, Any]) -> dict[str, Any]:
    output_dir = ensure_dir(ctx["output_dir"] / "S3_foundry_compile_execute")
    cas_root = ensure_dir(output_dir / "cas")
    started = utc_now()
    results: dict[str, Any] = {}
    try:
        from polisyos.foundry._quickstart import (
            run_feedback_compile_execute,
            run_feedback_multiplicity_demo,
            run_trivial_compile_execute,
        )

        calls = [
            ("trivial_compile_execute", run_trivial_compile_execute),
            ("feedback_compile_execute", run_feedback_compile_execute),
            ("feedback_multiplicity_demo", run_feedback_multiplicity_demo),
        ]
        for name, fn in calls:
            stage_started = time.perf_counter()
            try:
                value = fn(cas_root=cas_root / name)
                results[name] = {
                    "status": "completed",
                    "elapsed_seconds": round(time.perf_counter() - stage_started, 3),
                    "result": dataclasses.asdict(value),
                }
            except Exception as exc:
                results[name] = {
                    "status": "failed",
                    "elapsed_seconds": round(time.perf_counter() - stage_started, 3),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc()[-6000:],
                }
        completed = sum(1 for row in results.values() if row["status"] == "completed")
        status = (
            "completed" if completed == len(results) else "completed_with_partial_foundry_failures"
        )
    except Exception as exc:
        status = "failed_to_import_foundry_quickstart"
        results["import_error"] = {
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc()[-6000:],
        }
    cas_files = []
    if cas_root.exists():
        for path in cas_root.rglob("*"):
            if path.is_file():
                cas_files.append(
                    {"path": str(path.relative_to(cas_root)), "bytes": path.stat().st_size}
                )
    write_json(output_dir / "foundry_quickstart_results.json", results)
    write_json(
        output_dir / "foundry_cas_manifest.json",
        {"cas_root": str(cas_root), "file_count": len(cas_files), "files": cas_files[:2000]},
    )
    artifact_refs = {
        name: payload.get("result", {})
        for name, payload in results.items()
        if isinstance(payload, Mapping) and payload.get("status") == "completed"
    }
    write_json(output_dir / "foundry_artifact_refs.json", artifact_refs)
    write_markdown(
        output_dir / "s3_foundry_compile_execute_summary.md",
        f"""
# S3 Foundry Compile/Execute

Status: `{status}`

Completed quickstart calls: {sum(1 for row in results.values() if isinstance(row, Mapping) and row.get("status") == "completed")} / {len(results)}

CAS files observed: {len(cas_files)}

This is the strongest system-level smoke stage in the showcase because it uses
the repository's real CAS-backed Foundry compile/execute path rather than the
deadline harness' proxy calculations.
""",
    )
    result = {
        "experiment_id": "S3_foundry_compile_execute",
        "status": status,
        "started_at": started,
        "finished_at": utc_now(),
        "quickstart_results": results,
        "cas_file_count": len(cas_files),
    }
    write_json(output_dir / "experiment_result.json", result)
    ctx["sync"](output_dir, "S3_foundry_compile_execute")
    return result


def generate_policy_candidates(count: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    candidates: list[dict[str, Any]] = []
    for index in range(count):
        grant_cap = rng.choice([0, 75_000, 150_000, 250_000, 400_000])
        loan_cap = rng.choice([0, 250_000, 500_000, 1_000_000, 2_000_000, 5_000_000])
        subsidy_rate = rng.choice([0.0, 0.03, 0.05, 0.07, 0.09, 0.12])
        conflict_weight = round(rng.uniform(0.0, 1.0), 3)
        veteran_priority = round(rng.uniform(0.0, 1.0), 3)
        idp_priority = round(rng.uniform(0.0, 1.0), 3)
        admin_relief = round(rng.uniform(0.0, 0.7), 3)
        tax_relief = rng.choice([0.0, 0.02, 0.04, 0.06, 0.08])
        human_review_share = rng.choice([0.02, 0.05, 0.08, 0.12, 0.18])
        budget_cap = rng.choice(
            [1_000_000_000, 2_500_000_000, 5_000_000_000, 8_000_000_000, 12_000_000_000]
        )
        candidates.append(
            {
                "candidate_id": f"pol_{index:05d}",
                "grant_cap_uah": grant_cap,
                "loan_cap_uah": loan_cap,
                "interest_subsidy_rate": subsidy_rate,
                "conflict_weight": conflict_weight,
                "veteran_priority": veteran_priority,
                "idp_priority": idp_priority,
                "admin_relief": admin_relief,
                "tax_relief_rate": tax_relief,
                "human_review_share": human_review_share,
                "budget_cap_uah": budget_cap,
            }
        )
    return candidates


def _evaluate_candidate_chunk(args: tuple[list[dict[str, Any]], int, int]) -> list[dict[str, Any]]:
    candidates, panel_size, seed = args
    rng = np.random.default_rng(seed)
    # One synthetic/proxy panel per chunk keeps runtime heavy enough to exercise
    # CPU while avoiding a huge memory footprint.
    firm_size = rng.gamma(shape=2.0, scale=8.0, size=panel_size).clip(1, 250)
    conflict = rng.beta(2.2, 3.4, size=panel_size)
    liquidity_gap = rng.lognormal(mean=11.0, sigma=0.85, size=panel_size).clip(20_000, 8_000_000)
    baseline_survival = (
        0.42 + 0.28 * np.exp(-conflict) + 0.12 * np.log1p(firm_size) / np.log(251)
    ).clip(0.05, 0.95)
    veteran = rng.binomial(1, 0.08, size=panel_size)
    idp = rng.binomial(1, 0.16, size=panel_size)
    female_led = rng.binomial(1, 0.34, size=panel_size)
    frontline = conflict > 0.72
    micro = firm_size <= 10
    results: list[dict[str, Any]] = []
    for c in candidates:
        capital_support = np.minimum(liquidity_gap, c["grant_cap_uah"] + 0.55 * c["loan_cap_uah"])
        support_ratio = capital_support / np.maximum(liquidity_gap, 1.0)
        priority_score = (
            0.35 * support_ratio
            + c["conflict_weight"] * conflict
            + c["veteran_priority"] * veteran * 0.25
            + c["idp_priority"] * idp * 0.22
            + c["admin_relief"] * micro * 0.18
        )
        treated = priority_score >= np.quantile(priority_score, 0.86)
        treated_share = float(treated.mean())
        survival_lift = treated * (
            0.018 * support_ratio
            + 0.012 * c["interest_subsidy_rate"] / 0.12
            + 0.010 * c["admin_relief"]
            + 0.006 * c["tax_relief_rate"] / 0.08
        )
        survival = (baseline_survival + survival_lift).clip(0.0, 0.99)
        employment_preserved = float(np.mean((survival - baseline_survival) * np.sqrt(firm_size)))
        survival_gain = float(np.mean(survival - baseline_survival))
        fiscal_cost = float(
            treated.sum()
            * (
                0.44 * c["grant_cap_uah"]
                + 0.018 * c["loan_cap_uah"] * c["interest_subsidy_rate"] * 100
            )
            + panel_size * c["tax_relief_rate"] * 900.0
            + treated.sum() * c["human_review_share"] * 1200.0
        )
        fiscal_cost = min(fiscal_cost, float(c["budget_cap_uah"]))
        conflict_coverage = float(treated[frontline].mean()) if frontline.any() else 0.0
        micro_coverage = float(treated[micro].mean()) if micro.any() else 0.0
        female_gap = abs(float(treated[female_led == 1].mean() - treated[female_led == 0].mean()))
        idp_gap = abs(float(treated[idp == 1].mean() - treated[idp == 0].mean()))
        fairness_penalty = 0.55 * female_gap + 0.45 * max(
            0.0, 0.20 - float(treated[idp == 1].mean())
        )
        budget_pressure = fiscal_cost / max(float(c["budget_cap_uah"]), 1.0)
        robustness = (
            float(np.percentile(survival_lift[treated], 25) if treated.any() else 0.0)
            - 0.04 * budget_pressure
            - 0.03 * fairness_penalty
        )
        welfare_score = (
            220.0 * survival_gain
            + 8.0 * employment_preserved
            + 0.65 * conflict_coverage
            + 0.25 * micro_coverage
            - 0.85 * fairness_penalty
            - 0.35 * budget_pressure
        )
        results.append(
            {
                **c,
                "treated_share": treated_share,
                "survival_gain_mean": survival_gain,
                "employment_preserved_proxy": employment_preserved,
                "fiscal_cost_proxy_uah": fiscal_cost,
                "budget_pressure": budget_pressure,
                "conflict_coverage": conflict_coverage,
                "micro_coverage": micro_coverage,
                "fairness_penalty": fairness_penalty,
                "robustness_score": robustness,
                "welfare_score": float(welfare_score),
            }
        )
    return results


def pareto_frontier(rows: list[dict[str, Any]], max_rows: int = 100) -> list[dict[str, Any]]:
    sorted_rows = sorted(
        rows,
        key=lambda r: (
            -r["welfare_score"],
            -r["survival_gain_mean"],
            -r["employment_preserved_proxy"],
            r["fairness_penalty"],
            r["budget_pressure"],
        ),
    )
    frontier: list[dict[str, Any]] = []
    for row in sorted_rows:
        dominated = False
        for other in frontier:
            if (
                other["welfare_score"] >= row["welfare_score"]
                and other["survival_gain_mean"] >= row["survival_gain_mean"]
                and other["employment_preserved_proxy"] >= row["employment_preserved_proxy"]
                and other["fairness_penalty"] <= row["fairness_penalty"]
                and other["budget_pressure"] <= row["budget_pressure"]
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(row)
        if len(frontier) >= max_rows:
            break
    return frontier


def run_s4_policy_optimization(ctx: dict[str, Any]) -> dict[str, Any]:
    output_dir = ensure_dir(ctx["output_dir"] / "S4_policy_optimization_arena")
    started = utc_now()
    threads = ctx["threads"]
    candidate_count = ctx["candidate_count"]
    panel_size = ctx["panel_size"]
    chunk_size = max(50, math.ceil(candidate_count / max(1, threads * 3)))
    candidates = generate_policy_candidates(candidate_count, ctx["seed"])
    write_json(
        output_dir / "optimization_input_manifest.json",
        {
            "candidate_count": candidate_count,
            "panel_size_per_chunk": panel_size,
            "threads": threads,
            "chunk_size": chunk_size,
            "seed": ctx["seed"],
            "claim_posture": "proxy_simulation_not_real_causal_effect",
        },
    )
    write_jsonl(output_dir / "candidate_grid.jsonl", candidates)
    chunks = [candidates[i : i + chunk_size] for i in range(0, len(candidates), chunk_size)]
    results: list[dict[str, Any]] = []
    with futures.ProcessPoolExecutor(max_workers=threads) as pool:
        jobs = [
            pool.submit(_evaluate_candidate_chunk, (chunk, panel_size, ctx["seed"] + i * 997))
            for i, chunk in enumerate(chunks)
        ]
        for index, job in enumerate(futures.as_completed(jobs), start=1):
            batch = job.result()
            results.extend(batch)
            if index % max(1, len(chunks) // 6) == 0:
                write_json(
                    output_dir / "optimization_progress.json",
                    {
                        "completed_chunks": index,
                        "total_chunks": len(chunks),
                        "completed_candidates": len(results),
                        "updated_at": utc_now(),
                    },
                )
    results.sort(key=lambda row: row["welfare_score"], reverse=True)
    write_jsonl(output_dir / "optimization_results.jsonl", results)
    frontier = pareto_frontier(results, max_rows=120)
    top_recommendations = []
    for rank, row in enumerate(results[:12], start=1):
        recommendation = {
            "rank": rank,
            "candidate_id": row["candidate_id"],
            "label": (
                "grant+credit balanced package"
                if row["grant_cap_uah"] and row["loan_cap_uah"]
                else "single-channel support package"
            ),
            "headline": {
                "welfare_score": row["welfare_score"],
                "survival_gain_mean": row["survival_gain_mean"],
                "employment_preserved_proxy": row["employment_preserved_proxy"],
                "fiscal_cost_proxy_uah": row["fiscal_cost_proxy_uah"],
                "conflict_coverage": row["conflict_coverage"],
                "fairness_penalty": row["fairness_penalty"],
                "robustness_score": row["robustness_score"],
            },
            "levers": {
                k: row[k]
                for k in [
                    "grant_cap_uah",
                    "loan_cap_uah",
                    "interest_subsidy_rate",
                    "conflict_weight",
                    "veteran_priority",
                    "idp_priority",
                    "admin_relief",
                    "tax_relief_rate",
                    "human_review_share",
                    "budget_cap_uah",
                ]
            },
            "interpretation": "proxy/simulation recommendation requiring real applicant and outcome microdata before operational adoption",
        }
        top_recommendations.append(recommendation)
    sensitivity = {
        "candidate_count": len(results),
        "frontier_size": len(frontier),
        "welfare_score_quantiles": {
            "p10": float(np.percentile([r["welfare_score"] for r in results], 10)),
            "p50": float(np.percentile([r["welfare_score"] for r in results], 50)),
            "p90": float(np.percentile([r["welfare_score"] for r in results], 90)),
            "p99": float(np.percentile([r["welfare_score"] for r in results], 99)),
        },
        "top_lever_frequency": Counter(
            f"grant={r['grant_cap_uah']};loan={r['loan_cap_uah']};subsidy={r['interest_subsidy_rate']}"
            for r in results[:200]
        ).most_common(20),
    }
    write_json(
        output_dir / "pareto_frontier.json", {"frontier_size": len(frontier), "frontier": frontier}
    )
    write_json(output_dir / "robustness_sensitivity.json", sensitivity)
    write_json(
        output_dir / "top_policy_recommendations.json", {"recommendations": top_recommendations}
    )
    write_markdown(
        output_dir / "s4_policy_optimization_summary.md",
        f"""
# S4 Policy Optimization Arena

Status: `completed`

Evaluated candidate policies: {len(results)}

Synthetic/proxy panel size per chunk: {panel_size}

Worker processes: {threads}

Top recommendation: `{top_recommendations[0]["candidate_id"]}` with welfare
score `{top_recommendations[0]["headline"]["welfare_score"]:.4f}`.

Interpretation: this is a high-throughput proxy/simulation arena. It is useful
for selecting promising policy designs for the thesis and for later real-data
validation, but it is not a real treatment-effect estimate.
""",
    )
    result = {
        "experiment_id": "S4_policy_optimization_arena",
        "status": "completed",
        "started_at": started,
        "finished_at": utc_now(),
        "candidate_count": len(results),
        "frontier_size": len(frontier),
        "threads": threads,
        "panel_size": panel_size,
        "best_candidate": top_recommendations[0],
    }
    write_json(output_dir / "experiment_result.json", result)
    ctx["sync"](output_dir, "S4_policy_optimization_arena")
    return result


def run_s5_governance_packet(
    ctx: dict[str, Any], prior_results: list[dict[str, Any]]
) -> dict[str, Any]:
    output_dir = ensure_dir(ctx["output_dir"] / "S5_governance_review_packet")
    started = utc_now()
    s4_top = read_json(
        ctx["output_dir"] / "S4_policy_optimization_arena/top_policy_recommendations.json", {}
    )
    top_recs = s4_top.get("recommendations", [])
    prompt = (
        "Review the following PolicyOS MSME policy recommendations for a Ukrainian "
        "wartime SME thesis experiment. Separate actionable recommendation from "
        "limitations. Do not overclaim real causal effects.\n\n"
        + json.dumps(top_recs[:3], ensure_ascii=False, indent=2)[:12000]
    )
    llm_result = call_llm_if_available(
        ctx["llm"],
        system="You are a governance reviewer. Be precise, skeptical, and thesis-ready.",
        prompt=prompt,
        max_tokens=1600,
    )
    if llm_result.get("used"):
        review_body = llm_result.get("content", "")
        review_status = "completed_with_llm"
    else:
        review_status = "completed_with_deterministic_fallback"
        review_body = """
# Governance Review

The strongest current recommendation is to use a conflict-sensitive mixed
support package combining grants, subsidized credit, administrative relief and
human-review recourse. The top candidate should be interpreted as an experiment
output, not as a final government decision.

The result is promising because it uses:

- real processed Ukrainian legal evidence through Lex/H1 artifacts;
- production-data inventory and disclosed proxy assumptions;
- Fabric trust envelopes for decision-bearing quantities;
- a real Foundry compile/execute smoke path;
- high-throughput simulation over candidate policy portfolios.

The result remains limited because:

- applicant-level treatment assignment and outcomes are missing;
- fairness attributes are synthetic/proxy;
- amendment enrichment was deferred in the Lex finalize path;
- H1-H6 and S4 are not direct estimates of real treatment effects.

Recommended thesis phrasing: PolicyOS produced an auditable, bounded and
reproducible experimental recommendation under incomplete data, and correctly
surfaced the data needed for stronger future identification.
"""
    decision_packet = f"""
# PolicyOS MSME Decision Packet

Generated at: {utc_now()}

## Recommendation

Prioritize a conflict-sensitive combined support package for Ukrainian SMEs in
wartime: targeted microgrants for rapid restart, 5-7-9 style subsidized credit
for firms that can absorb debt, administrative/tax relief for liquidity, and
human-review recourse for borderline cases.

## Best Current Candidate

```json
{json.dumps(top_recs[0] if top_recs else {}, ensure_ascii=False, indent=2)}
```

## Evidence Spine

- Lex/H1: legal source pack and Trinity-like formalization artifacts.
- H2-H6: causal, transportability, mechanism, fairness and adaptivity outputs.
- S2: Fabric decision-data trust envelopes and evidence paths.
- S3: Foundry compile/execute quickstart artifacts.
- S4: policy optimization arena and Pareto frontier.

## Governance Review

{review_body}

## Hard Limitations

- No claim of real causal effect without applicant-level microdata.
- No claim of complete amendment-aware legal dynamics.
- No claim that LLM agents ran unless S1/S5 report `completed_with_llm`.
"""
    write_markdown(output_dir / "governance_review.md", review_body)
    write_markdown(output_dir / "decision_packet.md", decision_packet)
    write_json(
        output_dir / "llm_review_status.json",
        {k: v for k, v in llm_result.items() if k != "content"},
    )
    write_markdown(
        output_dir / "s5_governance_review_summary.md",
        f"""
# S5 Governance Review and Decision Packet

Status: `{review_status}`

Top recommendations reviewed: {len(top_recs)}

LLM status: `{llm_result["status"]}`

The decision packet is thesis-facing and deliberately conservative about causal
and legal-temporal limitations.
""",
    )
    result = {
        "experiment_id": "S5_governance_review_packet",
        "status": review_status,
        "started_at": started,
        "finished_at": utc_now(),
        "llm_status": {k: v for k, v in llm_result.items() if k != "content"},
        "top_recommendations": len(top_recs),
    }
    write_json(output_dir / "experiment_result.json", result)
    ctx["sync"](output_dir, "S5_governance_review_packet")
    return result


def build_final_reports(ctx: dict[str, Any], results: list[dict[str, Any]]) -> None:
    reports_dir = ensure_dir(ctx["output_dir"] / "reports")
    index = {
        "run_id": ctx["run_id"],
        "created_at": utc_now(),
        "workdir": str(ctx["workdir"]),
        "gcs_prefix": ctx["gcs_prefix"],
        "thread_profile": ctx["thread_profile"],
        "llm": {
            "available": bool(ctx["llm"].get("available")),
            "key_name": ctx["llm"].get("key_name"),
            "candidate_key_names": ctx["llm"].get("candidate_key_names"),
            "model": ctx["llm"].get("model"),
            "base_url": ctx["llm"].get("base_url"),
        },
        "experiments": results,
    }
    write_json(reports_dir / "showcase_index.json", index)
    rows = []
    for result in results:
        stage = result["experiment_id"]
        stage_dir = ctx["output_dir"] / stage
        for path in sorted(stage_dir.rglob("*")) if stage_dir.exists() else []:
            if path.is_file():
                rows.append(
                    {
                        "experiment": stage,
                        "artifact": str(path.relative_to(ctx["output_dir"])),
                        "bytes": path.stat().st_size,
                        "sha256": sha256_file(path) if path.stat().st_size < 50_000_000 else None,
                    }
                )
    write_json(reports_dir / "showcase_artifact_table.json", rows)
    artifact_md = [
        "# E2E Showcase Artifact Table",
        "",
        "| Experiment | Artifact | Bytes |",
        "| --- | --- | ---: |",
    ]
    for row in rows:
        artifact_md.append(f"| {row['experiment']} | `{row['artifact']}` | {row['bytes']} |")
    write_markdown(reports_dir / "showcase_artifact_table.md", "\n".join(artifact_md))
    status_lines = "\n".join(f"- `{row['experiment_id']}`: `{row['status']}`" for row in results)
    write_markdown(
        reports_dir / "showcase_thesis_summary.md",
        f"""
# PolicyOS MSME E2E Showcase Summary

Run ID: `{ctx["run_id"]}`

Generated at: {utc_now()}

## Experiment Status

{status_lines}

## Thesis-Ready Interpretation

The showcase demonstrates that PolicyOS can compose processed legal evidence,
prior H1-H6 outputs, Fabric trust envelopes, Foundry compile/execute smoke
artifacts, and a high-throughput policy optimization arena into a single cloud
workflow. The strongest result is methodological: the system returns auditable
recommendations and explicit limitations under incomplete wartime SME data.

The showcase does not prove real treatment effects. Applicant-level microdata,
outcome follow-up and full amendment enrichment remain required for stronger
substantive claims.
""",
    )
    ctx["sync"](reports_dir, "reports")


def preflight(ctx: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "created_at": utc_now(),
        "paths": {},
        "imports": {},
        "gcs": {},
        "llm": {
            "available": bool(ctx["llm"].get("available")),
            "key_name": ctx["llm"].get("key_name"),
            "candidate_key_names": ctx["llm"].get("candidate_key_names"),
            "model": ctx["llm"].get("model"),
            "base_url": ctx["llm"].get("base_url"),
        },
        "thread_profile": ctx["thread_profile"],
    }
    required_paths = {
        "workdir": ctx["workdir"],
        "repo_root": ctx["repo_root"],
        "runs_dir": ctx["runs_dir"],
        "lex_db": ctx["lex_db"],
        "normative_claims": ctx["normative_claims"],
        "production_data": ctx["production_data"],
    }
    for name, path in required_paths.items():
        report["paths"][name] = {
            "path": str(path),
            "exists": path.exists(),
            "is_dir": path.is_dir(),
            "bytes": path.stat().st_size if path.exists() and path.is_file() else None,
        }
    modules = [
        "duckdb",
        "numpy",
        "polisyos",
        "polisyos.fabric.decision_data",
        "polisyos.foundry.quickstart",
    ]
    for module in modules:
        try:
            __import__(module)
            report["imports"][module] = {"ok": True}
        except Exception as exc:
            report["imports"][module] = {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
    probe_path = ensure_dir(ctx["output_dir"] / "reports") / "e2e_gcs_write_probe.txt"
    probe_path.write_text(f"probe {utc_now()}\n", encoding="utf-8")
    if ctx["gcs_prefix"]:
        report["gcs"] = run_cmd(
            [
                "gcloud",
                "storage",
                "cp",
                str(probe_path),
                f"{ctx['gcs_prefix'].rstrip('/')}/reports/e2e_gcs_write_probe.txt",
            ],
            timeout=180,
        )
        report["gcs"]["ok"] = report["gcs"]["returncode"] == 0
    else:
        report["gcs"] = {"enabled": False}
    ok = (
        all(item.get("exists") for item in report["paths"].values())
        and all(item.get("ok") for item in report["imports"].values())
        and (not ctx["gcs_prefix"] or report["gcs"].get("ok"))
    )
    report["ok"] = bool(ok)
    write_json(ctx["output_dir"] / "reports/preflight_report.json", report)
    return report


def make_context(args: argparse.Namespace) -> dict[str, Any]:
    workdir = Path(args.workdir).resolve()
    repo_root = Path(args.repo_root).resolve()
    output_dir = ensure_dir(Path(args.output_dir).resolve())
    threads = int(args.threads)
    thread_profile = env_thread_profile(threads)
    llm = discover_llm_config(repo_root, workdir, args.llm_model)

    def _sync(local_path: Path, stage_name: str) -> dict[str, Any]:
        if not args.gcs_prefix:
            return {"enabled": False}
        target = f"{args.gcs_prefix.rstrip('/')}/{stage_name}"
        result = sync_to_gcs(local_path, target)
        sync_log = ensure_dir(output_dir / "sync_logs")
        write_json(sync_log / f"{stage_name}.json", result)
        return result

    return {
        "run_id": args.run_id,
        "workdir": workdir,
        "repo_root": repo_root,
        "runs_dir": Path(args.runs_dir).resolve(),
        "lex_db": Path(args.lex_db).resolve(),
        "normative_claims": Path(args.normative_claims).resolve(),
        "production_data": Path(args.production_data).resolve(),
        "output_dir": output_dir,
        "gcs_prefix": args.gcs_prefix,
        "threads": threads,
        "candidate_count": int(args.candidate_count),
        "panel_size": int(args.panel_size),
        "seed": int(args.seed),
        "thread_profile": thread_profile,
        "llm": llm,
        "sync": _sync,
    }


def run_all(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    stages = [
        run_s1_policy_design,
        run_s2_fabric_trust_flow,
        run_s3_foundry_compile_execute,
        run_s4_policy_optimization,
    ]
    for stage in stages:
        started = time.perf_counter()
        try:
            result = stage(ctx)
        except Exception as exc:
            stage_name = stage.__name__
            failed_dir = ensure_dir(ctx["output_dir"] / stage_name)
            result = {
                "experiment_id": stage_name,
                "status": "failed",
                "started_at": utc_now(),
                "finished_at": utc_now(),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc()[-8000:],
            }
            write_json(failed_dir / "experiment_result.json", result)
            ctx["sync"](failed_dir, stage_name)
        results.append(result)
    results.append(run_s5_governance_packet(ctx, results))
    build_final_reports(ctx, results)
    return results


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["preflight", "run"], default="preflight")
    parser.add_argument("--run-id", default="msme_e2e_showcase_20260430")
    parser.add_argument("--workdir", default="/mnt/experiments/msme_deadline_20260430")
    parser.add_argument("--repo-root", default="/mnt/experiments/polisyos/policy-engine")
    parser.add_argument("--runs-dir", default="/mnt/experiments/msme_deadline_20260430/runs")
    parser.add_argument(
        "--lex-db",
        default="/mnt/experiments/msme_deadline_20260430/input/lex/lex_knowledge_graph.duckdb",
    )
    parser.add_argument(
        "--normative-claims",
        default="/mnt/experiments/msme_deadline_20260430/input/lex/normative_claims.jsonl",
    )
    parser.add_argument(
        "--production-data", default="/mnt/experiments/msme_deadline_20260430/input/production_data"
    )
    parser.add_argument(
        "--output-dir", default="/mnt/experiments/msme_deadline_20260430/e2e_showcase"
    )
    parser.add_argument(
        "--gcs-prefix",
        default="gs://lex-1-494208-data/experiments/msme_deadline_20260430/e2e_showcase",
    )
    parser.add_argument(
        "--threads", type=int, default=int(os.environ.get("POLISYOS_EXPERIMENT_THREADS", "12"))
    )
    parser.add_argument("--candidate-count", type=int, default=7200)
    parser.add_argument("--panel-size", type=int, default=60000)
    parser.add_argument("--seed", type=int, default=20260501)
    parser.add_argument("--llm-model", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    ctx = make_context(args)
    ensure_dir(ctx["output_dir"] / "reports")
    report = preflight(ctx)
    if args.mode == "preflight":
        print(json.dumps(report, ensure_ascii=False, indent=2, default=json_default))
        return 0 if report.get("ok") else 2
    if not report.get("ok"):
        print(
            json.dumps(report, ensure_ascii=False, indent=2, default=json_default), file=sys.stderr
        )
        return 2
    results = run_all(ctx)
    print(
        json.dumps(
            {"status": "completed", "experiments": results},
            ensure_ascii=False,
            indent=2,
            default=json_default,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
