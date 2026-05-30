#!/usr/bin/env python3
"""Grand PolicyOS MSME experiment for the 2026-05-01 thesis deadline.

The runner is intentionally ambitious but claim-safe.  It uses the real
production data catalog, Lex/Fabric/Foundry surfaces and the Ukraine agent
simulation baseline where available, while clearly labelling deadline adapters
and proxy simulations.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import contextlib
import dataclasses
import hashlib
import io
import json
import os
import random
import re
import shutil
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

EXPERIMENT_ID = "msme_grand_tournament_v2"
DATASETS_BUNDLE_NAME = "datasets_full_phase3full_20260327_183054"
DEFAULT_INTENT = (
    "Design and stress-test wartime Ukrainian SME support policies for 2026, "
    "balancing firm survival, employment preservation, fiscal discipline, "
    "fairness, conflict-sensitive targeting, implementation feasibility, and "
    "legal/evidence traceability."
)

POLICY_ROLES = [
    "resilience planner",
    "fiscal conservative",
    "fairness and recourse reviewer",
    "regional procurement strategist",
    "anti-fraud implementation reviewer",
    "credit-market and banking-channel designer",
]

MSME_KEYWORDS = [
    "business",
    "sme",
    "msme",
    "enterprise",
    "entrepreneur",
    "employment",
    "credit",
    "loan",
    "grant",
    "tax",
    "procurement",
    "war",
    "conflict",
    "displacement",
    "veteran",
    "підприєм",
    "підприємниц",
    "бізнес",
    "мсп",
    "кредит",
    "грант",
    "подат",
    "закупів",
    "ветеран",
    "переміщ",
    "воєн",
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def datasets_bundle_root(production_data: Path) -> Path:
    bundled = production_data / DATASETS_BUNDLE_NAME
    if (bundled / "dataset_catalog.duckdb").exists():
        return bundled
    return production_data


def dataset_catalog_db(production_data: Path) -> Path:
    return datasets_bundle_root(production_data) / "dataset_catalog.duckdb"


def json_default(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
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
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


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


def run_cmd(
    cmd: list[str], *, cwd: Path | None = None, timeout: int | None = None
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-5000:],
            "stderr_tail": proc.stderr[-5000:],
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
    except Exception as exc:
        return {
            "cmd": cmd,
            "returncode": -1,
            "error_type": type(exc).__name__,
            "error": str(exc)[:2000],
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }


def sync_to_gcs(local_path: Path, gcs_uri: str | None) -> dict[str, Any]:
    if not gcs_uri:
        return {"enabled": False}
    if not local_path.exists():
        return {"enabled": True, "ok": False, "reason": "local_path_missing"}
    result = run_cmd(["gcloud", "storage", "rsync", "-r", str(local_path), gcs_uri], timeout=7200)
    result["enabled"] = True
    result["ok"] = result["returncode"] == 0
    result["gcs_uri"] = gcs_uri
    return result


def stage_dir(ctx: dict[str, Any], name: str) -> Path:
    return ensure_dir(ctx["output_dir"] / name)


def sync_stage(ctx: dict[str, Any], name: str) -> dict[str, Any]:
    if not ctx.get("sync_enabled"):
        return {"enabled": False}
    gcs_prefix = str(ctx["gcs_prefix"]).rstrip("/")
    result = sync_to_gcs(ctx["output_dir"] / name, f"{gcs_prefix}/{name}")
    sync_log = ctx["output_dir"] / "_sync_logs"
    ensure_dir(sync_log)
    write_json(sync_log / f"{name}.json", result)
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


def add_repo_to_path(repo_root: Path) -> None:
    src = repo_root / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))


def discover_first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def discover_llm_config(repo_root: Path, workdir: Path, model: str | None) -> dict[str, Any]:
    candidates: dict[str, str] = {}
    for key, value in os.environ.items():
        if (
            value
            and "KEY" in key.upper()
            and any(token in key.upper() for token in ("GONKA", "OPENAI"))
        ):
            candidates.setdefault(key, value)
    server_env_paths = sorted(
        (repo_root / "ops" / "cloud" / "deploy" / "assets").glob(".env.server_*")
    )
    for env_path in [
        repo_root / ".env",
        workdir / ".env",
        *server_env_paths,
    ]:
        if candidates or not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip().removeprefix("export ").strip()
            value = value.strip().strip("'\"")
            if (
                value
                and "KEY" in key.upper()
                and any(token in key.upper() for token in ("GONKA", "OPENAI"))
            ):
                candidates.setdefault(key, value)
    key_name = next((name for name in candidates if "GONKA" in name.upper()), None)
    key_name = key_name or next((name for name in candidates if "OPENAI" in name.upper()), None)
    return {
        "available": bool(key_name),
        "key_name": key_name,
        "api_key": candidates.get(key_name or "", ""),
        "candidate_key_names": sorted(candidates),
        "base_url": os.environ.get("GONKA_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.gonkagate.com/v1",
        "model": model or os.environ.get("GONKA_MODEL") or "qwen/qwen3-235b-a22b-instruct-2507-fp8",
    }


def call_llm(
    llm: dict[str, Any], *, system: str, prompt: str, max_tokens: int = 3000
) -> dict[str, Any]:
    if not llm.get("available"):
        return {"used": False, "status": "llm_unavailable"}
    try:
        from openai import OpenAI

        started = time.perf_counter()
        client = OpenAI(api_key=llm["api_key"], base_url=llm["base_url"], timeout=120.0)
        response = client.chat.completions.create(
            model=llm["model"],
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            temperature=0.35,
            max_tokens=max_tokens,
        )
        return {
            "used": True,
            "status": "ok",
            "model": llm["model"],
            "base_url": llm["base_url"],
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "content": response.choices[0].message.content or "",
        }
    except Exception as exc:
        return {
            "used": False,
            "status": "llm_call_failed",
            "model": llm.get("model"),
            "base_url": llm.get("base_url"),
            "error_type": type(exc).__name__,
            "error": str(exc)[:1200],
        }


def extract_json_array(text: str) -> list[dict[str, Any]]:
    if not text:
        return []
    fence = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, flags=re.DOTALL)
    candidates = [fence.group(1)] if fence else []
    first, last = text.find("["), text.rfind("]")
    if first != -1 and last > first:
        candidates.append(text[first : last + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def fabric_db(ctx: dict[str, Any]) -> Path:
    return dataset_catalog_db(ctx["production_data"])


def query_duckdb_rows(
    db_path: Path, sql: str, params: list[Any] | None = None
) -> list[dict[str, Any]]:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        cur = con.execute(sql, params or [])
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]
    finally:
        con.close()


def build_relevance_clause() -> str:
    haystack = (
        "lower(coalesce(cast(title as varchar),'') || ' ' || "
        "coalesce(cast(description as varchar),'') || ' ' || "
        "coalesce(cast(keywords as varchar),'') || ' ' || "
        "coalesce(cast(themes as varchar),''))"
    )
    clauses = []
    for keyword in MSME_KEYWORDS:
        safe_keyword = keyword.lower().replace("'", "''")
        clauses.append(f"{haystack} like '%{safe_keyword}%'")
    return " or ".join(clauses)


def dataset_quality_expr() -> str:
    return (
        "("
        "coalesce(quality_description_score, 0)"
        " + coalesce(quality_machine_readable_score, 0)"
        " + coalesce(quality_parser_support_score, 0)"
        " + coalesce(quality_freshness_score, 0)"
        " + coalesce(quality_execution_readiness_score, 0)"
        ") / 5.0"
    )


def collect_legal_snippets(runs_dir: Path, limit: int = 160) -> list[dict[str, Any]]:
    candidates = [
        runs_dir / "H1_formalization/legal_source_pack.jsonl",
        runs_dir / "H1_formalization/retrieval_evidence.jsonl",
        runs_dir / "S1_policy_intent_agent_loop/retrieval_evidence.jsonl",
    ]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    keywords = ["власна справа", "5-7-9", "підприєм", "мсп", "єдиний податок", "воєнний", "ветеран"]
    for path in candidates:
        for row in iter_jsonl(path, limit=30000):
            text = json.dumps(row, ensure_ascii=False).lower()
            if not any(keyword in text for keyword in keywords):
                continue
            source_id = str(row.get("source_id") or row.get("doc_id") or sha256_text(text)[:18])
            if source_id in seen:
                continue
            seen.add(source_id)
            rows.append(
                {
                    "source_path": str(path),
                    "source_id": source_id,
                    "doc_id": row.get("doc_id"),
                    "doc_name": row.get("doc_name"),
                    "snippet": str(row.get("text") or row.get("snippet") or row)[:1200],
                }
            )
            if len(rows) >= limit:
                return rows
    return rows


def method_catalog_snapshot(ctx: dict[str, Any]) -> dict[str, Any]:
    try:
        from polisyos.foundry.methods.catalog import ensure_all_methods_registered
        from polisyos.foundry.methods.registry import MethodRegistry

        ensure_all_methods_registered()
        registry = MethodRegistry.get_instance()
        signatures = registry.list_all()
        by_family: Counter[str] = Counter()
        by_backend: Counter[str] = Counter()
        rows: list[dict[str, Any]] = []
        for sig in signatures:
            fqn = sig.fqn
            family = str(sig.namespace).split(".", 1)[0] if sig.namespace else fqn.split(".", 1)[0]
            by_family[family] += 1
            backend = getattr(sig.execution_backend, "value", str(sig.execution_backend))
            by_backend[backend] += 1
            entry = registry.get_entry(fqn)
            rows.append(
                {
                    "fqn": fqn,
                    "namespace": sig.namespace,
                    "name": sig.name,
                    "version": sig.version,
                    "backend": backend,
                    "tags": sorted(str(tag) for tag in entry.metadata.tags) if entry else [],
                }
            )
        return {
            "status": "ok",
            "method_count": len(signatures),
            "by_family": dict(sorted(by_family.items())),
            "by_backend": dict(sorted(by_backend.items())),
            "sample_methods": rows[:300],
        }
    except Exception as exc:
        return {"status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:2000]}


def fabric_catalog_counts(ctx: dict[str, Any]) -> dict[str, Any]:
    db = fabric_db(ctx)
    if not db.exists():
        return {"status": "missing", "path": str(db)}
    con = duckdb.connect(str(db), read_only=True)
    try:
        tables = [
            row[0]
            for row in con.execute(
                "select table_name from information_schema.tables where table_schema='main' order by table_name"
            ).fetchall()
        ]
        counts = {}
        for table in tables:
            try:
                counts[table] = int(con.execute(f"select count(*) from {table}").fetchone()[0])
            except Exception as exc:
                counts[table] = f"error:{type(exc).__name__}"
        return {"status": "ok", "path": str(db), "tables": counts}
    finally:
        con.close()


def graph_inventory(ctx: dict[str, Any]) -> dict[str, Any]:
    root = ctx["production_data"] / "ukraine_agent_simulation_baseline_20260410"
    files = []
    for path in sorted((root / "heavy_graph_addon").glob("*.npz")) if root.exists() else []:
        info: dict[str, Any] = {
            "path": str(path),
            "name": path.name,
            "size_bytes": path.stat().st_size,
            "load_mode": "metadata_only",
        }
        try:
            with np.load(path, allow_pickle=False) as npz:
                info["npz_keys"] = list(npz.files)
        except Exception as exc:
            info["npz_error"] = f"{type(exc).__name__}: {exc}"
        files.append(info)
    manifest = read_json(root / "FINAL_ARTIFACTS_MANIFEST.json", {})
    return {
        "status": "ok" if root.exists() else "missing",
        "root": str(root),
        "manifest_created_at": manifest.get("created_at_local_hint"),
        "heavy_graph_files": files,
    }


def scientist_workflow_inventory(ctx: dict[str, Any]) -> dict[str, Any]:
    try:
        from polisyos.scientist.orchestration.workflows.policy_design import (
            policy_design_workflow_spec,
        )

        spec = policy_design_workflow_spec()
        return {
            "status": "ok",
            "workflow_id": spec.workflow_id,
            "error_policy": spec.error_policy,
            "required_binds": list(spec.required_binds),
            "nodes": [
                {
                    "alias": node.alias,
                    "node_id": node.node_id,
                    "depends_on": list(node.depends_on),
                }
                for node in spec.nodes
            ],
            "node_count": len(spec.nodes),
        }
    except Exception as exc:
        return {"status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:2000]}


def run_t1_capability_snapshot(ctx: dict[str, Any]) -> dict[str, Any]:
    name = "T1_capability_snapshot"
    out = stage_dir(ctx, name)
    started = utc_now()
    method_summary = method_catalog_snapshot(ctx)
    fabric_counts = fabric_catalog_counts(ctx)
    graphs = graph_inventory(ctx)
    scientist = scientist_workflow_inventory(ctx)
    runtime = {
        "started_at": started,
        "python": sys.version,
        "platform": sys.platform,
        "cpu_count": os.cpu_count(),
        "threads": ctx["threads"],
        "repo_root": str(ctx["repo_root"]),
        "workdir": str(ctx["workdir"]),
        "production_data": str(ctx["production_data"]),
        "runs_dir": str(ctx["runs_dir"]),
        "env_thread_profile": ctx["thread_profile"],
        "disk_usage_output_dir": shutil.disk_usage(ctx["output_dir"])._asdict(),
    }
    write_json(out / "method_catalog_summary.json", method_summary)
    write_json(out / "fabric_catalog_counts.json", fabric_counts)
    write_json(out / "agent_baseline_graph_inventory.json", graphs)
    write_json(out / "scientist_workflow_inventory.json", scientist)
    write_json(out / "runtime_environment.json", runtime)
    write_markdown(
        out / "capability_snapshot_summary.md",
        f"""
# T1 Capability Snapshot

Foundry method catalog status: `{method_summary.get("status")}`, methods:
`{method_summary.get("method_count", "unknown")}`.

Fabric catalog status: `{fabric_counts.get("status")}`.

Scientist workflow status: `{scientist.get("status")}`, nodes:
`{scientist.get("node_count", "unknown")}`.

Ukraine agent baseline status: `{graphs.get("status")}`, graph files:
`{len(graphs.get("heavy_graph_files", []))}`.
""",
    )
    result = {
        "experiment_id": name,
        "status": "completed",
        "started_at": started,
        "finished_at": utc_now(),
        "method_count": method_summary.get("method_count"),
        "fabric_tables": fabric_counts.get("tables"),
        "graph_file_count": len(graphs.get("heavy_graph_files", [])),
    }
    write_json(out / "experiment_result.json", result)
    sync_stage(ctx, name)
    return result


def deterministic_policy_designs(count: int, legal_refs: list[str]) -> list[dict[str, Any]]:
    rng = random.Random(20260501)  # noqa: S311 - deterministic fixture generation.
    designs = []
    archetypes = [
        ("resilience_grant_credit", "Resilience grants plus subsidized credit"),
        ("fast_microgrant", "Fast microgrant restart channel"),
        ("tax_admin_relief", "Tax and administrative relief package"),
        ("procurement_anchor", "Procurement-anchor demand support"),
        ("veteran_idp_priority", "Veteran and IDP entrepreneurship priority"),
        ("frontline_relocation", "Frontline relocation and restart voucher"),
        ("digital_export", "Digital/export voucher and credit guarantee"),
        ("anti_fraud_review", "Human-review high-integrity grant channel"),
    ]
    sectors = [
        "retail",
        "manufacturing",
        "services",
        "agri-food",
        "logistics",
        "IT",
        "repair",
        "construction",
    ]
    regions = ["frontline", "deoccupied", "high_idp", "national", "industrial", "rural"]
    for i in range(count):
        archetype, label = archetypes[i % len(archetypes)]
        conflict_weight = round(0.25 + 0.7 * ((i * 37) % 100) / 100, 3)
        grant_cap = int([100_000, 150_000, 250_000, 400_000, 600_000][i % 5])
        loan_cap = int([0, 500_000, 1_000_000, 2_000_000, 5_000_000][(i // 2) % 5])
        subsidy = round([0.00, 0.03, 0.05, 0.07, 0.09][(i // 3) % 5], 3)
        tax_relief = round([0.00, 0.02, 0.04, 0.06][(i // 5) % 4], 3)
        procurement = round([0.00, 0.05, 0.10, 0.15, 0.20][(i // 7) % 5], 3)
        human_review = round([0.05, 0.10, 0.15, 0.22, 0.30][(i // 11) % 5], 3)
        budget_cap = int(
            [1_000_000_000, 1_750_000_000, 2_500_000_000, 3_500_000_000][(i // 13) % 4]
        )
        designs.append(
            {
                "policy_id": f"gtv2_policy_{i:03d}",
                "label": f"{label} #{i + 1}",
                "archetype": archetype,
                "target_population": {
                    "region_priority": regions[i % len(regions)],
                    "sector_priority": sectors[(i * 3) % len(sectors)],
                    "firm_size": ["micro", "small", "micro_and_small", "small_and_medium"][i % 4],
                    "priority_groups": {
                        "veteran": bool(i % 3 == 0),
                        "idp": bool(i % 4 in {0, 1}),
                        "women_owned": bool(i % 5 in {0, 2}),
                        "youth": bool(i % 7 == 0),
                    },
                },
                "levers": {
                    "grant_cap_uah": grant_cap,
                    "loan_cap_uah": loan_cap,
                    "interest_subsidy_rate": subsidy,
                    "tax_relief_rate": tax_relief,
                    "credit_guarantee_rate": round(min(0.85, 0.15 + loan_cap / 7_000_000), 3),
                    "procurement_preference": procurement,
                    "relocation_grant_uah": int(grant_cap * (0.2 + 0.4 * conflict_weight)),
                    "digital_voucher_uah": int([0, 25_000, 50_000, 75_000][(i // 17) % 4]),
                    "training_subsidy_uah": int([0, 15_000, 30_000, 45_000][(i // 19) % 4]),
                    "conflict_weight": conflict_weight,
                    "human_review_share": human_review,
                    "admin_relief": round(rng.uniform(0.05, 0.55), 3),
                    "budget_cap_uah": budget_cap,
                },
                "monitoring_metrics": [
                    "firm_survival_12m",
                    "employment_preserved",
                    "budget_cost_uah",
                    "conflict_region_coverage",
                    "fraud_risk_proxy",
                    "recourse_rate",
                ],
                "legal_evidence_refs": legal_refs[
                    i % max(1, len(legal_refs)) : i % max(1, len(legal_refs)) + 6
                ],
                "assumptions": [
                    "No applicant-level treatment/outcome microdata available in this deadline run.",
                    "Effects are proxy/simulation outputs calibrated from production-data priors.",
                ],
                "fallback_variant": "reduce grant cap and increase human review if budget or fraud risk gate fails",
            }
        )
    return designs


def normalize_llm_design(row: dict[str, Any], index: int, legal_refs: list[str]) -> dict[str, Any]:
    levers = row.get("levers") if isinstance(row.get("levers"), dict) else {}
    base = deterministic_policy_designs(index + 1, legal_refs)[-1]
    base["policy_id"] = f"llm_policy_{index:03d}"
    base["label"] = str(row.get("label") or row.get("name") or base["label"])[:160]
    base["archetype"] = str(row.get("archetype") or row.get("type") or base["archetype"])[:80]
    base["llm_raw_summary"] = str(row.get("summary") or row.get("rationale") or row)[:1200]
    for key in list(base["levers"]):
        if key in levers:
            try:
                base["levers"][key] = float(levers[key])
            except Exception:
                pass
    return base


def run_t2_policy_design_factory(ctx: dict[str, Any]) -> dict[str, Any]:
    name = "T2_policy_design_factory"
    out = stage_dir(ctx, name)
    started = utc_now()
    snippets = collect_legal_snippets(ctx["runs_dir"])
    legal_refs = [str(row["source_id"]) for row in snippets[:60]]
    write_jsonl(out / "legal_evidence_snippets.jsonl", snippets)

    llm_rows: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    prompt_evidence = "\n".join(
        f"- {row.get('doc_name')}: {row.get('snippet')[:350]}" for row in snippets[:12]
    )
    for _batch_index, role in enumerate(POLICY_ROLES):
        prompt = f"""
Policy intent: {DEFAULT_INTENT}

Role: {role}

Legal/evidence snippets:
{prompt_evidence}

Return a JSON array of 12 Ukrainian wartime MSME policy designs. Each object
must include: label, archetype, target_population, levers, monitoring_metrics,
assumptions, fallback_variant. Keep numbers realistic in UAH.
"""
        response = call_llm(
            ctx["llm"],
            system=(
                "You are a careful PolicyOS policy-design agent. Return only JSON. "
                "Never claim real causal effects without microdata."
            ),
            prompt=prompt,
            max_tokens=4500,
        )
        llm_rows.append({k: v for k, v in response.items() if k != "content"} | {"role": role})
        parsed = extract_json_array(response.get("content", ""))
        for row in parsed:
            normalized.append(normalize_llm_design(row, len(normalized), legal_refs))
    target = int(ctx["policy_count"])
    if len(normalized) < target:
        deterministic = deterministic_policy_designs(target - len(normalized), legal_refs)
        for i, row in enumerate(deterministic):
            row["policy_id"] = f"det_policy_{i:03d}"
            row["source"] = "deterministic_variant_factory"
            normalized.append(row)
    normalized = normalized[:target]
    for row in normalized:
        row.setdefault("source", "llm_policy_factory")
        row["schema_compatibility"] = {
            "has_target_population": bool(row.get("target_population")),
            "has_levers": bool(row.get("levers")),
            "has_budget_cap": "budget_cap_uah" in row.get("levers", {}),
            "has_monitoring_metrics": bool(row.get("monitoring_metrics")),
            "has_assumptions": bool(row.get("assumptions")),
        }

    compat = {
        "policy_count": len(normalized),
        "valid_schema_lite": sum(
            1 for row in normalized if all(row["schema_compatibility"].values())
        ),
        "llm_batches": llm_rows,
        "llm_available": bool(ctx["llm"].get("available")),
        "llm_key_name": ctx["llm"].get("key_name"),
    }
    write_jsonl(out / "llm_policy_batches.jsonl", llm_rows)
    write_jsonl(out / "normalized_policy_designs.jsonl", normalized)
    write_json(out / "policy_schema_compatibility_report.json", compat)
    write_markdown(
        out / "policy_design_factory_summary.md",
        f"""
# T2 Policy Design Factory

Generated `{len(normalized)}` normalized policy designs.

LLM available: `{ctx["llm"].get("available")}`. Key variable:
`{ctx["llm"].get("key_name")}`. The key value is intentionally not logged.

Schema-lite valid policies: `{compat["valid_schema_lite"]}`.
""",
    )
    result = {
        "experiment_id": name,
        "status": "completed",
        "started_at": started,
        "finished_at": utc_now(),
        "policy_count": len(normalized),
        "llm_batches": llm_rows,
        "schema_lite_valid": compat["valid_schema_lite"],
    }
    write_json(out / "experiment_result.json", result)
    sync_stage(ctx, name)
    return result


def load_policy_designs(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    path = ctx["output_dir"] / "T2_policy_design_factory/normalized_policy_designs.jsonl"
    rows = list(iter_jsonl(path))
    if rows:
        return rows
    return deterministic_policy_designs(ctx["policy_count"], [])


def run_t3_fabric_evidence_matrix(ctx: dict[str, Any]) -> dict[str, Any]:
    name = "T3_fabric_evidence_matrix"
    out = stage_dir(ctx, name)
    started = utc_now()
    db = fabric_db(ctx)
    policies = load_policy_designs(ctx)
    relevant: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    observation_summary: list[dict[str, Any]] = []
    if db.exists():
        clause = build_relevance_clause()
        quality_expr = dataset_quality_expr()
        limit = int(ctx["fabric_dataset_limit"])
        relevant = query_duckdb_rows(
            db,
            f"""
            select id, source, agency, dataset_id, title, publisher, spatial,
                   temporal_start, temporal_end,
                   {quality_expr} as quality_score,
                   quality_machine_readable_score,
                   quality_parser_support_score,
                   execution_tier,
                   preferred_distribution_id
            from ds_datasets
            where {clause}
            order by coalesce(quality_score, 0) desc
            limit {limit}
            """,
        )
        metric_rows = query_duckdb_rows(
            db,
            f"""
            with relevant as (
              select id, {quality_expr} as quality_score
              from ds_datasets
              where {clause}
              order by coalesce(quality_score, 0) desc
              limit {limit}
            )
            select mb.metric_id, mb.dataset_id, mb.distribution_id,
                   mb.confidence, mb.metric_inference_confidence, mb.execution_tier,
                   va.canonical_var, va.confidence as variable_alignment_confidence,
                   d.format, d.machine_readable, d.parser_supported, d.quality_score as distribution_quality
            from ds_metric_bindings mb
            left join ds_variable_alignments va on va.dataset_id = mb.dataset_id
            left join ds_distributions d on d.dataset_id = mb.dataset_id
            where mb.dataset_id in (select id from relevant)
            limit {limit * 4}
            """,
        )
        observation_summary = query_duckdb_rows(
            db,
            f"""
            with relevant as (
              select id, {quality_expr} as quality_score
              from ds_datasets
              where {clause}
              order by coalesce(quality_score, 0) desc
              limit {limit}
            )
            select canonical_var, count(*) as observation_count,
                   min(year) as min_year, max(year) as max_year,
                   avg(value) as avg_value
            from ds_observations
            where dataset_id in (select id from relevant)
            group by canonical_var
            order by observation_count desc
            limit 200
            """,
        )

    by_dataset_quality = {
        str(row.get("id")): float(row.get("quality_score") or 0.0) for row in relevant
    }
    avg_quality = float(np.mean(list(by_dataset_quality.values()))) if by_dataset_quality else 0.0
    metric_conf = [float(row.get("confidence") or 0.0) for row in metric_rows]
    avg_metric_conf = float(np.mean(metric_conf)) if metric_conf else 0.0
    evidence_matrix = []
    for policy in policies:
        levers = policy.get("levers", {})
        conflict = float(levers.get("conflict_weight", 0.5))
        budget = float(levers.get("budget_cap_uah", 1.0))
        evidence_score = float(
            np.clip(0.45 * avg_quality + 0.35 * avg_metric_conf + 0.2 * conflict, 0.0, 1.0)
        )
        evidence_matrix.append(
            {
                "policy_id": policy["policy_id"],
                "dataset_candidates_considered": len(relevant),
                "metric_links_considered": len(metric_rows),
                "avg_dataset_quality": avg_quality,
                "avg_metric_confidence": avg_metric_conf,
                "budget_cap_uah": budget,
                "fabric_evidence_score": evidence_score,
                "execution_mode": "fabric_catalog_query",
            }
        )

    runtime_quantities, fabric_decision_data, fabric_coverage = build_runtime_fabric_payloads(
        evidence_matrix=evidence_matrix,
        ctx=ctx,
    )
    write_jsonl(out / "relevant_datasets.jsonl", relevant)
    write_jsonl(out / "metric_binding_rows.jsonl", metric_rows)
    write_json(out / "observation_summary.json", observation_summary)
    write_jsonl(out / "evidence_matrix.jsonl", evidence_matrix)
    write_json(out / "runtime_quantities.json", runtime_quantities)
    write_json(out / "fabric_decision_data.json", fabric_decision_data)
    write_json(out / "fabric_coverage.json", fabric_coverage)
    write_markdown(
        out / "fabric_evidence_matrix_summary.md",
        f"""
# T3 Fabric Evidence Matrix

Datasets considered: `{len(relevant)}`.

Metric/distribution/alignment rows considered: `{len(metric_rows)}`.

Policies scored: `{len(evidence_matrix)}`.

Average dataset quality proxy: `{avg_quality:.3f}`.
Average metric confidence proxy: `{avg_metric_conf:.3f}`.
""",
    )
    result = {
        "experiment_id": name,
        "status": "completed",
        "started_at": started,
        "finished_at": utc_now(),
        "datasets_considered": len(relevant),
        "metric_rows_considered": len(metric_rows),
        "policies_scored": len(evidence_matrix),
    }
    write_json(out / "experiment_result.json", result)
    sync_stage(ctx, name)
    return result


def build_runtime_fabric_payloads(
    *, evidence_matrix: list[dict[str, Any]], ctx: dict[str, Any]
) -> tuple[Any, Any, Any]:
    top = sorted(evidence_matrix, key=lambda row: row["fabric_evidence_score"], reverse=True)[:8]
    fallback_quantities = [
        {
            "metric_id": f"fabric_evidence_score:{row['policy_id']}",
            "point": row["fabric_evidence_score"],
            "unit": "score",
            "lineage": "T3_fabric_evidence_matrix",
        }
        for row in top
    ]
    try:
        from polisyos.fabric.evidence.decision_data import (
            coverage_from_decision_data,
            from_runtime_quantities,
        )

        from polisyos.core.contracts.runtime import (
            LineageRef,
            QuantityUncertainty,
            QuantityValue,
            TemporalRef,
            UnitRef,
            VerificationMetadata,
        )

        now = datetime.now(UTC).replace(microsecond=0)
        quantities = []
        for row in top:
            digest = sha256_text(json.dumps(row, ensure_ascii=False, default=json_default))
            quantities.append(
                QuantityValue(
                    point=float(row["fabric_evidence_score"]),
                    unit=UnitRef(code="1", display="score"),
                    metric_id=f"fabric_evidence_score:{row['policy_id']}",
                    label=f"Fabric evidence score for {row['policy_id']}",
                    lineage=LineageRef(
                        id=f"T3:{row['policy_id']}",
                        hash=digest,
                        status="pending",
                        freshness="current",
                        trust_metadata=VerificationMetadata(
                            hash=digest,
                            verification_status="pending",
                            freshness="current",
                        ),
                    ),
                    time=TemporalRef(valid_at=now, tx_at=now, snapshot_id=EXPERIMENT_ID),
                    uncertainty=QuantityUncertainty(
                        method="catalog_proxy", identifiability="proxy"
                    ),
                )
            )
        decision_data = from_runtime_quantities(quantities, source_contracts=[])
        coverage = coverage_from_decision_data(decision_data)
        return (
            [q.model_dump(mode="json") for q in quantities],
            [
                row.model_dump(mode="json") if hasattr(row, "model_dump") else row
                for row in decision_data
            ],
            coverage.model_dump(mode="json") if hasattr(coverage, "model_dump") else coverage,
        )
    except Exception as exc:
        return (
            fallback_quantities,
            {
                "status": "fabric_projection_failed",
                "error_type": type(exc).__name__,
                "error": str(exc)[:1000],
            },
            {"status": "fallback", "quantity_count": len(fallback_quantities)},
        )


def make_causal_panel(rows: int, seed: int = 20260501) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    conflict = rng.beta(2.0, 4.0, size=rows)
    firm_size = rng.lognormal(mean=1.0, sigma=0.7, size=rows)
    pre_revenue = rng.lognormal(mean=12.0, sigma=0.9, size=rows)
    idp = rng.binomial(1, 0.18 + 0.25 * conflict)
    veteran = rng.binomial(1, 0.08 + 0.08 * conflict)
    female_owned = rng.binomial(1, 0.32, size=rows)
    procurement_exposure = rng.beta(1.5, 4.0, size=rows)
    features = np.column_stack(
        [
            conflict,
            np.log1p(firm_size),
            np.log1p(pre_revenue) / 15.0,
            idp,
            veteran,
            female_owned,
            procurement_exposure,
        ]
    )
    logits = -0.35 + 1.1 * conflict + 0.25 * idp + 0.18 * veteran - 0.12 * np.log1p(firm_size)
    propensity = np.clip(1 / (1 + np.exp(-logits)), 0.05, 0.95)
    treatment = rng.binomial(1, propensity)
    true_effect = 0.035 + 0.05 * conflict + 0.015 * procurement_exposure - 0.02 * (firm_size > 6)
    noise = rng.normal(0.0, 0.08, size=rows)
    outcome = np.clip(
        0.48
        - 0.12 * conflict
        + 0.02 * np.log1p(firm_size)
        + 0.04 * procurement_exposure
        + true_effect * treatment
        + noise,
        0.0,
        1.0,
    )
    selected = rng.binomial(1, np.clip(0.92 - 0.12 * conflict + 0.03 * treatment, 0.55, 0.99))
    return {
        "X": features.astype(np.float64),
        "treatment": treatment.astype(np.float64),
        "outcome": outcome.astype(np.float64),
        "selected": selected.astype(np.float64),
        "true_effect": true_effect.astype(np.float64),
        "propensity": propensity.astype(np.float64),
    }


def run_foundry_method(
    method_cls: Any, state: dict[str, Any], params: dict[str, Any], method_id: str
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = method_cls.pure_step(state, params)
        return {
            "method_id": method_id,
            "execution_mode": "foundry_pure_step",
            "status": "ok",
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "result": result.get("result", result),
            "stdout_tail": stdout.getvalue()[-2000:],
            "stderr_tail": stderr.getvalue()[-2000:],
        }
    except Exception as exc:
        return {
            "method_id": method_id,
            "execution_mode": "foundry_pure_step",
            "status": "failed",
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "error_type": type(exc).__name__,
            "error": str(exc)[:2000],
        }


def run_t4_causal_gauntlet(ctx: dict[str, Any]) -> dict[str, Any]:
    name = "T4_causal_gauntlet"
    out = stage_dir(ctx, name)
    started = utc_now()
    rows = int(ctx["causal_panel_rows"])
    panel = make_causal_panel(rows)
    direct_n = min(5000, max(1500, rows // 24))
    rng = np.random.default_rng(17)
    sample_idx = rng.choice(rows, size=direct_n, replace=False)
    state = {
        "X": panel["X"][sample_idx],
        "treatment": panel["treatment"][sample_idx],
        "outcome": panel["outcome"][sample_idx],
        "selected": panel["selected"][sample_idx],
    }
    method_runs: list[dict[str, Any]] = []
    try:
        from polisyos.foundry.methods.catalog.causal.bounds import (
            LeeBoundsEstimator,
            ManskiBoundsEstimator,
        )
        from polisyos.foundry.methods.catalog.causal.treatment_effects import (
            AIPWEstimator,
            IPWEstimator,
            PropensityScoreMatchingEstimator,
            TMLEEstimator,
        )

        ate_params = {
            "propensity_backend": "logistic",
            "outcome_backend": "linear",
            "crossfit_folds": 3,
            "n_repeats": 1,
            "bootstrap_draws": 80,
            "parallel_folds": True,
            "max_parallel_folds": min(ctx["threads"], 3),
            "propensity_clipping": 0.02,
            "propensity_trimming": 0.02,
            "verbosity": -1,
        }
        for method_id, cls, params in [
            ("causal.treatment_effects.aipw@1.0.0", AIPWEstimator, ate_params),
            ("causal.treatment_effects.tmle@1.0.0", TMLEEstimator, ate_params),
            ("causal.treatment_effects.ipw@1.0.0", IPWEstimator, {"trimming": 0.02}),
            (
                "causal.treatment_effects.propensity_matching@1.0.0",
                PropensityScoreMatchingEstimator,
                {"n_matches": 1, "caliper": 0.25},
            ),
            ("causal.bounds.manski@1.0.0", ManskiBoundsEstimator, {"y_lower": 0.0, "y_upper": 1.0}),
            ("causal.bounds.lee@1.0.0", LeeBoundsEstimator, {}),
        ]:
            method_runs.append(run_foundry_method(cls, state, params, method_id))
    except Exception as exc:
        method_runs.append(
            {
                "method_id": "foundry_import_bundle",
                "execution_mode": "foundry_import",
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc)[:2000],
            }
        )

    treated = panel["treatment"] > 0.5
    naive = float(np.mean(panel["outcome"][treated]) - np.mean(panel["outcome"][~treated]))
    true_avg = float(np.mean(panel["true_effect"]))
    overlap_ntv = float(np.mean(np.abs(panel["propensity"] - 0.5) / 0.5))
    proxy_runs = [
        {
            "method_id": "deadline_adapter.full_panel_naive_difference",
            "execution_mode": "deadline_adapter",
            "status": "ok",
            "result": {"ate_proxy": naive, "n_obs": rows},
        },
        {
            "method_id": "deadline_adapter.overlap_ntv",
            "execution_mode": "deadline_adapter",
            "status": "ok",
            "result": {
                "overlap_ntv": overlap_ntv,
                "min_propensity": float(np.min(panel["propensity"])),
                "max_propensity": float(np.max(panel["propensity"])),
            },
        },
        {
            "method_id": "synthetic_truth.avg_true_effect",
            "execution_mode": "proxy_simulation",
            "status": "ok",
            "result": {"avg_true_effect_known_only_because_synthetic": true_avg},
        },
    ]
    method_runs.extend(proxy_runs)
    consensus = {
        "full_panel_rows": rows,
        "direct_foundry_subsample_rows": direct_n,
        "known_synthetic_true_effect": true_avg,
        "naive_difference": naive,
        "overlap_ntv": overlap_ntv,
        "successful_foundry_methods": [
            r["method_id"]
            for r in method_runs
            if r["status"] == "ok" and r["execution_mode"] == "foundry_pure_step"
        ],
        "failed_foundry_methods": [
            r
            for r in method_runs
            if r["status"] != "ok" and r["execution_mode"] == "foundry_pure_step"
        ],
        "claims_boundary": "semi_synthetic_panel_for_method_validation_not_real_program_effect",
    }
    write_json(
        out / "causal_panel_manifest.json",
        {
            "rows": rows,
            "direct_foundry_subsample_rows": direct_n,
            "features": [
                "conflict",
                "firm_size",
                "pre_revenue",
                "idp",
                "veteran",
                "female_owned",
                "procurement_exposure",
            ],
            "outcome": "firm_survival_proxy_12m",
            "treatment": "policy_exposure_proxy",
        },
    )
    write_jsonl(out / "causal_method_runs.jsonl", method_runs)
    write_json(out / "causal_consensus_table.json", consensus)
    write_markdown(
        out / "causal_gauntlet_summary.md",
        f"""
# T4 Foundry Causal Gauntlet

Full semi-synthetic panel rows: `{rows}`.

Direct Foundry subsample rows: `{direct_n}`. This is deliberate: several direct
methods are O(N²), so the full panel is used for vectorized diagnostics while
O(N²) estimators run on a safe subsample.

Successful direct Foundry methods: `{len(consensus["successful_foundry_methods"])}`.

Known synthetic true effect: `{true_avg:.5f}`.
Naive observed difference: `{naive:.5f}`.

Claim boundary: this validates causal machinery under disclosed synthetic data;
it is not a real effect estimate for Ukrainian programs.
""",
    )
    result = {
        "experiment_id": name,
        "status": "completed",
        "started_at": started,
        "finished_at": utc_now(),
        "full_panel_rows": rows,
        "direct_foundry_subsample_rows": direct_n,
        "successful_foundry_methods": len(consensus["successful_foundry_methods"]),
    }
    write_json(out / "experiment_result.json", result)
    sync_stage(ctx, name)
    return result


def graph_prior_summary(ctx: dict[str, Any]) -> dict[str, float]:
    inv = read_json(
        ctx["output_dir"] / "T1_capability_snapshot/agent_baseline_graph_inventory.json", {}
    )
    files = inv.get("heavy_graph_files", [])
    total = sum(float(row.get("size_bytes") or 0.0) for row in files)
    priors = {}
    for row in files:
        name = str(row.get("name", "")).replace("_graph_sparse.npz", "")
        priors[name] = float(row.get("size_bytes") or 0.0) / max(total, 1.0)
    defaults = {
        "budget": 0.75,
        "procurement": 0.12,
        "distress": 0.08,
        "trade": 0.04,
        "public_service": 0.03,
    }
    for key, value in defaults.items():
        priors.setdefault(key, value)
    return priors


def simulate_policy_worker(
    payload: tuple[dict[str, Any], list[int], int, int, dict[str, float]],
) -> dict[str, Any]:
    policy, seeds, agent_count, months, graph_priors = payload
    levers = policy.get("levers", {})
    grant = float(levers.get("grant_cap_uah", 0.0))
    loan = float(levers.get("loan_cap_uah", 0.0))
    subsidy = float(levers.get("interest_subsidy_rate", 0.0))
    tax_relief = float(levers.get("tax_relief_rate", 0.0))
    procurement = float(levers.get("procurement_preference", 0.0))
    conflict_weight = float(levers.get("conflict_weight", 0.5))
    human_review = float(levers.get("human_review_share", 0.1))
    budget_cap = float(levers.get("budget_cap_uah", 1_000_000_000.0))
    admin_relief = float(levers.get("admin_relief", 0.2))
    rows = []
    for seed in seeds:
        rng = np.random.default_rng(
            seed + int(hashlib.sha256(policy["policy_id"].encode()).hexdigest()[:8], 16)
        )
        conflict = rng.beta(2.0, 4.0, size=agent_count).astype(np.float32)
        revenue = rng.lognormal(11.4, 0.9, size=agent_count).astype(np.float32)
        employees = rng.poisson(4.0 + np.log1p(revenue) / 5.0).astype(np.float32)
        liquidity = rng.beta(2.2, 5.0, size=agent_count).astype(np.float32)
        alive = np.ones(agent_count, dtype=bool)
        uptake = np.zeros(agent_count, dtype=np.float32)
        base_uptake = np.clip(
            0.08 + grant / 2_000_000 + loan / 20_000_000 + 0.35 * subsidy + 0.12 * admin_relief,
            0.02,
            0.75,
        )
        for _month in range(months):
            shock = rng.normal(0.0, 0.025, size=agent_count).astype(np.float32)
            policy_access = np.clip(
                base_uptake
                + conflict_weight * conflict * 0.28
                + procurement * graph_priors.get("procurement", 0.1)
                - human_review * 0.12
                + shock,
                0.0,
                0.95,
            )
            new_uptake = (rng.random(agent_count) < policy_access).astype(np.float32)
            uptake = np.maximum(uptake, new_uptake)
            support = (
                0.035 * uptake
                + 0.12 * subsidy
                + 0.08 * tax_relief
                + 0.06 * procurement
                + 0.025 * admin_relief
                - 0.045 * human_review
            )
            monthly_hazard = np.clip(
                0.030
                + 0.10 * conflict
                + 0.035 * (liquidity < 0.2)
                - support
                + graph_priors.get("distress", 0.05) * conflict * 0.06,
                0.002,
                0.35,
            )
            alive &= rng.random(agent_count) > monthly_hazard
            liquidity = np.clip(
                liquidity + 0.015 * uptake + 0.004 * tax_relief - 0.010 * conflict + shock, 0.0, 1.0
            )
        survival = float(np.mean(alive))
        employment_preserved = float(np.sum(employees * alive) / max(np.sum(employees), 1.0))
        uptake_rate = float(np.mean(uptake))
        fiscal_cost = float(
            uptake_rate
            * agent_count
            * (0.35 * grant + 0.025 * loan * subsidy + 35_000 * tax_relief)
        )
        fraud_risk = float(
            np.clip(0.08 + 0.18 * uptake_rate - 0.20 * human_review + 0.04 * admin_relief, 0.0, 1.0)
        )
        fairness_proxy = float(
            np.clip(
                0.45 + 0.35 * conflict_weight + 0.15 * admin_relief - 0.12 * fraud_risk, 0.0, 1.0
            )
        )
        conflict_coverage = float(
            np.mean((conflict > 0.55) & (uptake > 0.0)) / max(np.mean(conflict > 0.55), 1e-6)
        )
        budget_pressure = float(fiscal_cost / max(budget_cap, 1.0))
        rows.append(
            {
                "seed": seed,
                "survival_rate": survival,
                "employment_preserved": employment_preserved,
                "uptake_rate": uptake_rate,
                "fiscal_cost_uah": fiscal_cost,
                "fraud_risk_proxy": fraud_risk,
                "fairness_proxy": fairness_proxy,
                "conflict_coverage": conflict_coverage,
                "budget_pressure": budget_pressure,
            }
        )
    aggregate = {}
    for key in rows[0]:
        if key == "seed":
            continue
        values = np.asarray([row[key] for row in rows], dtype=float)
        aggregate[f"{key}_mean"] = float(np.mean(values))
        aggregate[f"{key}_p10"] = float(np.quantile(values, 0.10))
        aggregate[f"{key}_p90"] = float(np.quantile(values, 0.90))
    score = (
        2.0 * aggregate["survival_rate_mean"]
        + 1.4 * aggregate["employment_preserved_mean"]
        + 0.8 * aggregate["fairness_proxy_mean"]
        + 0.6 * aggregate["conflict_coverage_mean"]
        - 1.2 * aggregate["budget_pressure_mean"]
        - 0.7 * aggregate["fraud_risk_proxy_mean"]
    )
    return {
        "policy_id": policy["policy_id"],
        "label": policy.get("label"),
        "execution_mode": "proxy_simulation",
        "agent_count_per_seed": agent_count,
        "months": months,
        "seeds": seeds,
        "aggregate": aggregate,
        "utility_score": float(score),
    }


def run_t5_agent_sim_arena(ctx: dict[str, Any]) -> dict[str, Any]:
    name = "T5_agent_sim_arena"
    out = stage_dir(ctx, name)
    started = utc_now()
    policies = load_policy_designs(ctx)
    graph_priors = graph_prior_summary(ctx)
    seeds = list(range(int(ctx["simulation_seeds"])))
    chunks: list[tuple[dict[str, Any], list[int], int, int, dict[str, float]]] = []
    for policy in policies:
        chunks.append(
            (policy, seeds, int(ctx["agent_count"]), int(ctx["simulation_months"]), graph_priors)
        )
    write_json(
        out / "simulation_input_manifest.json",
        {
            "policy_count": len(policies),
            "agent_count_per_seed": ctx["agent_count"],
            "simulation_months": ctx["simulation_months"],
            "simulation_seeds": ctx["simulation_seeds"],
            "graph_priors": graph_priors,
            "threads": ctx["threads"],
        },
    )
    results = []
    with futures.ProcessPoolExecutor(max_workers=int(ctx["threads"])) as pool:
        for index, row in enumerate(pool.map(simulate_policy_worker, chunks), start=1):
            results.append(row)
            if index % 12 == 0 or index == len(chunks):
                write_jsonl(out / "policy_simulation_scores.partial.jsonl", results)
                sync_stage(ctx, name)
    results.sort(key=lambda row: row["utility_score"], reverse=True)
    write_jsonl(out / "policy_simulation_scores.jsonl", results)
    write_json(out / "spillover_prior_summary.json", graph_priors)
    write_json(out / "top_simulation_policies.json", {"top": results[:20]})
    write_markdown(
        out / "agent_sim_arena_summary.md",
        f"""
# T5 Ukraine Graph-Aware Agent Simulation Arena

Policies simulated: `{len(results)}`.

Agent count per seed: `{ctx["agent_count"]}`.
Seeds per policy: `{ctx["simulation_seeds"]}`.
Months: `{ctx["simulation_months"]}`.

Best policy: `{results[0]["policy_id"] if results else "none"}`.

Execution mode: proxy simulation with Ukraine graph-derived priors. This stage
is designed to exercise CPU and generate scenario rankings, not real causal
effect estimates.
""",
    )
    result = {
        "experiment_id": name,
        "status": "completed",
        "started_at": started,
        "finished_at": utc_now(),
        "policies_simulated": len(results),
        "best_policy": results[0]["policy_id"] if results else None,
    }
    write_json(out / "experiment_result.json", result)
    sync_stage(ctx, name)
    return result


def run_t6_tournament(ctx: dict[str, Any]) -> dict[str, Any]:
    name = "T6_tournament"
    out = stage_dir(ctx, name)
    started = utc_now()
    policies = {row["policy_id"]: row for row in load_policy_designs(ctx)}
    sim_rows = list(
        iter_jsonl(ctx["output_dir"] / "T5_agent_sim_arena/policy_simulation_scores.jsonl")
    )
    evidence = {
        row["policy_id"]: row
        for row in iter_jsonl(ctx["output_dir"] / "T3_fabric_evidence_matrix/evidence_matrix.jsonl")
    }
    matrix_rows = []
    for row in sim_rows:
        pid = row["policy_id"]
        agg = row.get("aggregate", {})
        ev = evidence.get(pid, {})
        matrix_rows.append(
            {
                "policy_id": pid,
                "label": policies.get(pid, {}).get("label"),
                "survival": float(agg.get("survival_rate_mean", 0.0)),
                "employment": float(agg.get("employment_preserved_mean", 0.0)),
                "fairness": float(agg.get("fairness_proxy_mean", 0.0)),
                "conflict_coverage": float(agg.get("conflict_coverage_mean", 0.0)),
                "budget_pressure": float(agg.get("budget_pressure_mean", 0.0)),
                "fraud_risk": float(agg.get("fraud_risk_proxy_mean", 0.0)),
                "fabric_evidence": float(ev.get("fabric_evidence_score", 0.0)),
                "sim_utility": float(row.get("utility_score", 0.0)),
            }
        )
    decision_matrix = np.asarray(
        [
            [
                r["survival"],
                r["employment"],
                r["fairness"],
                r["conflict_coverage"],
                -r["budget_pressure"],
                -r["fraud_risk"],
                r["fabric_evidence"],
                r["sim_utility"],
            ]
            for r in matrix_rows
        ],
        dtype=float,
    )
    weights = np.asarray([0.17, 0.16, 0.14, 0.12, 0.13, 0.10, 0.08, 0.10], dtype=float)
    is_benefit = np.ones(decision_matrix.shape[1], dtype=bool)
    mcda_result: dict[str, Any]
    try:
        from polisyos.foundry.methods.catalog.policy.mcda import TOPSISEstimator

        mcda_result = TOPSISEstimator.pure_step(
            {"decision_matrix": decision_matrix, "weights": weights, "is_benefit": is_benefit},
            {},
        )["result"]
        execution_mode = "foundry_pure_step"
    except Exception as exc:
        normalized = (decision_matrix - np.min(decision_matrix, axis=0)) / (
            np.ptp(decision_matrix, axis=0) + 1e-12
        )
        scores = normalized @ weights
        mcda_result = {
            "closeness_coefficients": scores.tolist(),
            "ranking": np.argsort(-scores).tolist(),
            "best_alternative": int(np.argmax(scores)),
            "fallback_error": f"{type(exc).__name__}: {exc}",
        }
        execution_mode = "deadline_adapter"

    rng = np.random.default_rng(99)
    top_counts: Counter[str] = Counter()
    if len(matrix_rows):
        normalized = (decision_matrix - np.min(decision_matrix, axis=0)) / (
            np.ptp(decision_matrix, axis=0) + 1e-12
        )
        for _ in range(400):
            perturbed = rng.dirichlet(weights * 80 + 1)
            best = int(np.argmax(normalized @ perturbed))
            top_counts[matrix_rows[best]["policy_id"]] += 1
    ranking = mcda_result.get("ranking", [])
    top_dossiers = []
    for rank, idx in enumerate(ranking[:15], start=1):
        r = matrix_rows[int(idx)]
        top_dossiers.append(
            {
                "rank": rank,
                "policy_id": r["policy_id"],
                "label": r["label"],
                "mcda_score": mcda_result.get("closeness_coefficients", [])[int(idx)],
                "rank_stability_top_count": top_counts.get(r["policy_id"], 0),
                "metrics": r,
                "claim_boundary": "scenario ranking under proxy simulation and Fabric evidence posture",
            }
        )
    write_json(
        out / "tournament_decision_matrix.json",
        {
            "criteria": [
                "survival",
                "employment",
                "fairness",
                "conflict_coverage",
                "negative_budget_pressure",
                "negative_fraud_risk",
                "fabric_evidence",
                "sim_utility",
            ],
            "rows": matrix_rows,
        },
    )
    write_json(out / "mcda_results.json", {"execution_mode": execution_mode, "result": mcda_result})
    write_json(out / "rank_stability.json", {"top_counts": dict(top_counts), "draws": 400})
    write_json(out / "top_policy_dossiers.json", {"top": top_dossiers})
    write_markdown(
        out / "tournament_summary.md",
        f"""
# T6 Welfare, MCDA, Robustness and Governance Tournament

Policies ranked: `{len(matrix_rows)}`.

MCDA execution mode: `{execution_mode}`.

Best policy: `{top_dossiers[0]["policy_id"] if top_dossiers else "none"}`.
""",
    )
    result = {
        "experiment_id": name,
        "status": "completed",
        "started_at": started,
        "finished_at": utc_now(),
        "ranked_policies": len(matrix_rows),
        "best_policy": top_dossiers[0]["policy_id"] if top_dossiers else None,
        "mcda_execution_mode": execution_mode,
    }
    write_json(out / "experiment_result.json", result)
    sync_stage(ctx, name)
    return result


def run_t7_shortlist_compatibility(ctx: dict[str, Any]) -> dict[str, Any]:
    name = "T7_shortlist_compatibility"
    out = stage_dir(ctx, name)
    started = utc_now()
    top = read_json(ctx["output_dir"] / "T6_tournament/top_policy_dossiers.json", {"top": []}).get(
        "top", []
    )
    quickstart_results = {}
    try:
        from polisyos.foundry._quickstart import (
            run_feedback_compile_execute,
            run_feedback_multiplicity_demo,
            run_trivial_compile_execute,
        )

        cas_root = out / "foundry_cas"
        for label, fn in [
            ("trivial_compile_execute", run_trivial_compile_execute),
            ("feedback_compile_execute", run_feedback_compile_execute),
            ("feedback_multiplicity_demo", run_feedback_multiplicity_demo),
        ]:
            try:
                started_call = time.perf_counter()
                quickstart_results[label] = {
                    "status": "completed",
                    "elapsed_seconds": round(time.perf_counter() - started_call, 3),
                    "result": fn(cas_root=cas_root / label),
                }
            except Exception as exc:
                quickstart_results[label] = {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:2000],
                }
    except Exception as exc:
        quickstart_results["import"] = {
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc)[:2000],
        }

    projections = []
    for row in top[:10]:
        projections.append(
            {
                "policy_id": row["policy_id"],
                "rank": row["rank"],
                "policy_candidate_schema_projection": {
                    "rollout_plan": "present_as_deadline_projection",
                    "target_population": "present_in_normalized_design",
                    "parameter_schedule": "present_in_levers",
                    "budget_allocation": "budget_cap_uah_checked_in_T2_T6",
                    "monitoring_metrics": "present_in_normalized_design",
                    "evidence_assumptions": "attached",
                    "transport_assumptions": "proxy_only",
                    "harm_envelope": "requires_full_schema_followup",
                    "fallback_variants": "present",
                },
                "claim_boundary": "compatibility_projection_not_full_scientist_dag_execution",
            }
        )
    write_json(out / "foundry_quickstart_results.json", quickstart_results)
    write_json(out / "shortlist_policy_candidate_projection.json", {"rows": projections})
    write_markdown(
        out / "shortlist_compatibility_summary.md",
        f"""
# T7 Foundry/Scientist Shortlist Compatibility

Shortlist projections: `{len(projections)}`.

Foundry quickstart calls completed:
`{sum(1 for row in quickstart_results.values() if isinstance(row, dict) and row.get("status") == "completed")}`.

This stage is an execution-path and schema-compatibility check. It does not
claim that every top policy was fully executed through the entire
`scientist_policy_design` production DAG.
""",
    )
    result = {
        "experiment_id": name,
        "status": "completed",
        "started_at": started,
        "finished_at": utc_now(),
        "shortlist_count": len(projections),
        "quickstart_completed": sum(
            1
            for row in quickstart_results.values()
            if isinstance(row, dict) and row.get("status") == "completed"
        ),
    }
    write_json(out / "experiment_result.json", result)
    sync_stage(ctx, name)
    return result


def run_t8_thesis_dossier(
    ctx: dict[str, Any], stage_results: list[dict[str, Any]]
) -> dict[str, Any]:
    name = "T8_thesis_dossier"
    out = stage_dir(ctx, name)
    started = utc_now()
    top = read_json(ctx["output_dir"] / "T6_tournament/top_policy_dossiers.json", {"top": []}).get(
        "top", []
    )
    index = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": utc_now(),
        "gcs_prefix": ctx["gcs_prefix"],
        "stage_results": stage_results,
        "top_policy": top[0] if top else None,
        "claims_boundary": [
            "No real applicant-level causal effect claim.",
            "Fast Lex finalize deferred amendment enrichment.",
            "Agent simulation is proxy/scenario-based.",
            "Direct O(N^2) causal estimators run on a safe subsample.",
        ],
    }
    write_json(out / "grand_tournament_index.json", index)
    top_lines = []
    for row in top[:8]:
        metrics = row.get("metrics", {})
        top_lines.append(
            f"| {row['rank']} | `{row['policy_id']}` | {row.get('label', '')} | "
            f"{row.get('mcda_score', 0):.4f} | {metrics.get('survival', 0):.3f} | "
            f"{metrics.get('employment', 0):.3f} | {metrics.get('budget_pressure', 0):.3f} |"
        )
    write_markdown(
        out / "grand_tournament_results_summary.md",
        f"""
# MSME PolicyOS Grand Tournament v2 Results

The experiment ran a broad wartime Ukrainian SME policy tournament across
policy generation, Fabric evidence retrieval, Foundry causal-method validation,
graph-aware agent simulation, MCDA ranking and compatibility checks.

## Top Policies

| Rank | Policy | Label | MCDA | Survival | Employment | Budget Pressure |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
{chr(10).join(top_lines) if top_lines else "| - | - | no results | - | - | - | - |"}

## Claims Boundary

- These are scenario/proxy rankings, not real program treatment effects.
- The causal gauntlet validates methods under semi-synthetic panels.
- The Lex layer is useful but amendment enrichment was deferred.
- Full production Scientist DAG execution remains a follow-up unless separately
  recorded in T7.
""",
    )
    artifact_lines = [
        "| Stage | Main artifacts |",
        "| --- | --- |",
    ]
    for stage in [
        "T1_capability_snapshot",
        "T2_policy_design_factory",
        "T3_fabric_evidence_matrix",
        "T4_causal_gauntlet",
        "T5_agent_sim_arena",
        "T6_tournament",
        "T7_shortlist_compatibility",
    ]:
        artifact_lines.append(
            f"| `{stage}` | `{stage}/experiment_result.json`, summaries and JSONL outputs |"
        )
    write_markdown(out / "appendix_artifact_inventory.md", "\n".join(artifact_lines))
    write_markdown(
        out / "limitations_and_claims_boundary.md",
        """
# Limitations and Claims Boundary

This run is suitable for thesis experimental evidence about system capability,
workflow composition, auditable policy ranking and scenario simulation.

It is not sufficient for a real causal estimate of Ukrainian MSME programs,
because applicant-level treatment/outcome microdata is absent in this deadline
run.
""",
    )
    result = {
        "experiment_id": name,
        "status": "completed",
        "started_at": started,
        "finished_at": utc_now(),
        "top_policy": top[0]["policy_id"] if top else None,
    }
    write_json(out / "experiment_result.json", result)
    sync_stage(ctx, name)
    sync_to_gcs(ctx["output_dir"], str(ctx["gcs_prefix"]).rstrip("/"))
    return result


def preflight(ctx: dict[str, Any]) -> dict[str, Any]:
    out = stage_dir(ctx, "preflight")
    checks = {
        "created_at": utc_now(),
        "repo_root_exists": ctx["repo_root"].exists(),
        "src_exists": (ctx["repo_root"] / "src").exists(),
        "production_data_exists": ctx["production_data"].exists(),
        "dataset_catalog_exists": fabric_db(ctx).exists(),
        "runs_dir_exists": ctx["runs_dir"].exists(),
        "output_dir": str(ctx["output_dir"]),
        "gcs_prefix": ctx["gcs_prefix"],
        "llm_available": bool(ctx["llm"].get("available")),
        "llm_key_name": ctx["llm"].get("key_name"),
    }
    import_checks = {}
    for module in [
        "duckdb",
        "numpy",
        "polisyos",
        "polisyos.foundry.methods.catalog.causal.treatment_effects",
        "polisyos.foundry.methods.catalog.policy.mcda",
        "polisyos.fabric.evidence.decision_data",
    ]:
        try:
            __import__(module)
            import_checks[module] = "ok"
        except Exception as exc:
            import_checks[module] = f"{type(exc).__name__}: {exc}"
    checks["imports"] = import_checks
    try:
        from polisyos.foundry.methods.catalog.causal.treatment_effects import AIPWEstimator

        panel = make_causal_panel(300)
        small = {"X": panel["X"], "treatment": panel["treatment"], "outcome": panel["outcome"]}
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            res = AIPWEstimator.pure_step(
                small,
                {
                    "crossfit_folds": 2,
                    "n_repeats": 1,
                    "bootstrap_draws": 20,
                    "verbosity": -1,
                },
            )
        checks["aipw_smoke"] = {
            "status": "ok",
            "result_keys": sorted(res.get("result", {}).keys())[:20],
        }
    except Exception as exc:
        checks["aipw_smoke"] = {
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc)[:2000],
        }
    write_json(out / "preflight_result.json", checks)
    write_markdown(
        out / "preflight_summary.md",
        f"""
# Grand Tournament v2 Preflight

Repo: `{checks["repo_root_exists"]}`.
Production data: `{checks["production_data_exists"]}`.
Dataset catalog: `{checks["dataset_catalog_exists"]}`.
LLM available: `{checks["llm_available"]}` via `{checks["llm_key_name"]}`.
AIPW smoke: `{checks["aipw_smoke"]["status"]}`.
""",
    )
    sync_stage(ctx, "preflight")
    checks["ok"] = (
        checks["repo_root_exists"]
        and checks["production_data_exists"]
        and checks["dataset_catalog_exists"]
        and checks["aipw_smoke"]["status"] == "ok"
    )
    return checks


def collect_existing_stage_results(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for stage in [
        "T1_capability_snapshot",
        "T2_policy_design_factory",
        "T3_fabric_evidence_matrix",
        "t3_fabric_evidence_matrix",
        "T4_causal_gauntlet",
        "T5_agent_sim_arena",
        "T6_tournament",
        "T7_shortlist_compatibility",
    ]:
        payload = read_json(ctx["output_dir"] / stage / "experiment_result.json", None)
        if not isinstance(payload, dict):
            continue
        experiment_id = str(payload.get("experiment_id") or stage)
        if experiment_id.lower() in seen:
            continue
        seen.add(experiment_id.lower())
        results.append(payload)
    return results


def run_all(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    stage_results = []
    stage_map = {
        "T1": ("T1_capability_snapshot", run_t1_capability_snapshot),
        "T2": ("T2_policy_design_factory", run_t2_policy_design_factory),
        "T3": ("T3_fabric_evidence_matrix", run_t3_fabric_evidence_matrix),
        "T4": ("T4_causal_gauntlet", run_t4_causal_gauntlet),
        "T5": ("T5_agent_sim_arena", run_t5_agent_sim_arena),
        "T6": ("T6_tournament", run_t6_tournament),
        "T7": ("T7_shortlist_compatibility", run_t7_shortlist_compatibility),
    }
    requested = ctx.get("stages") or list(stage_map)
    requested_set = {str(stage).upper() for stage in requested}
    for stage_id, (stage_name, fn) in stage_map.items():
        if stage_id not in requested_set:
            continue
        started = time.perf_counter()
        try:
            result = fn(ctx)
        except Exception as exc:
            fail_dir = stage_dir(ctx, stage_name)
            result = {
                "experiment_id": stage_name,
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc)[:3000],
                "traceback_tail": traceback.format_exc()[-5000:],
                "finished_at": utc_now(),
            }
            write_json(fail_dir / "experiment_result.json", result)
            sync_stage(ctx, stage_name)
        result["elapsed_seconds_outer"] = round(time.perf_counter() - started, 3)
        stage_results.append(result)
        write_json(ctx["output_dir"] / "grand_tournament_stage_results.partial.json", stage_results)
    dossier_inputs = collect_existing_stage_results(ctx)
    if not dossier_inputs:
        dossier_inputs = stage_results
    if not ctx.get("stages") or "T8" in requested_set:
        stage_results.append(run_t8_thesis_dossier(ctx, dossier_inputs))
    write_json(ctx["output_dir"] / "grand_tournament_stage_results.json", stage_results)
    return stage_results


def build_context(args: argparse.Namespace) -> dict[str, Any]:
    workdir = Path(args.workdir).expanduser().resolve()
    repo_root = Path(args.repo_root).expanduser().resolve()
    if not repo_root.exists():
        repo_root = Path.cwd().resolve()
    add_repo_to_path(repo_root)
    production_data = (
        Path(args.production_data).expanduser().resolve() if args.production_data else None
    )
    if production_data is None or not production_data.exists():
        production_data = discover_first_existing(
            [
                workdir / "input/production_data",
                repo_root / ".polisyos/production_data",
                repo_root / "production_data",
                Path("/mnt/experiments/msme_deadline_20260430/input/production_data"),
            ]
        ) or (repo_root / "production_data")
    runs_dir = Path(args.runs_dir).expanduser().resolve() if args.runs_dir else None
    if runs_dir is None or not runs_dir.exists():
        runs_dir = discover_first_existing(
            [
                workdir / "runs",
                workdir / "output/runs",
                workdir / "e2e_showcase_extended",
                workdir / "e2e_showcase_extended/runs",
            ]
        ) or (workdir / "runs")
    output_dir = Path(args.output_dir).expanduser().resolve()
    ensure_dir(output_dir)
    threads = int(args.threads or os.cpu_count() or 1)
    thread_profile = env_thread_profile(threads)
    llm = discover_llm_config(repo_root, workdir, args.llm_model)
    return {
        "workdir": workdir,
        "repo_root": repo_root,
        "production_data": production_data,
        "runs_dir": runs_dir,
        "output_dir": output_dir,
        "gcs_prefix": args.gcs_prefix,
        "sync_enabled": not args.no_sync,
        "threads": threads,
        "policy_count": int(args.policy_count),
        "fabric_dataset_limit": int(args.fabric_dataset_limit),
        "causal_panel_rows": int(args.causal_panel_rows),
        "agent_count": int(args.agent_count),
        "simulation_months": int(args.simulation_months),
        "simulation_seeds": int(args.simulation_seeds),
        "stages": [
            stage.strip().upper() for stage in str(args.stages or "").split(",") if stage.strip()
        ],
        "thread_profile": thread_profile,
        "llm": llm,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["preflight", "run"], default="preflight")
    parser.add_argument("--workdir", default="/mnt/experiments/msme_deadline_20260430")
    parser.add_argument("--repo-root", default="/mnt/experiments/polisyos/policy-engine")
    parser.add_argument("--production-data", default="")
    parser.add_argument("--runs-dir", default="")
    parser.add_argument(
        "--output-dir", default="/mnt/experiments/msme_deadline_20260430/msme_grand_tournament_v2"
    )
    parser.add_argument(
        "--gcs-prefix",
        default="gs://lex-1-494208-data/experiments/msme_deadline_20260430/msme_grand_tournament_v2",
    )
    parser.add_argument("--threads", type=int, default=12)
    parser.add_argument("--policy-count", type=int, default=96)
    parser.add_argument("--fabric-dataset-limit", type=int, default=1200)
    parser.add_argument("--causal-panel-rows", type=int, default=120000)
    parser.add_argument("--agent-count", type=int, default=180000)
    parser.add_argument("--simulation-months", type=int, default=24)
    parser.add_argument("--simulation-seeds", type=int, default=48)
    parser.add_argument("--stages", default="", help="Comma-separated subset, e.g. T3,T6,T8")
    parser.add_argument("--llm-model", default="")
    parser.add_argument("--no-sync", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ctx = build_context(args)
    write_json(
        ctx["output_dir"] / "grand_tournament_launch_config.json",
        {k: v for k, v in ctx.items() if k != "llm"}
        | {
            "llm": {
                "available": ctx["llm"].get("available"),
                "key_name": ctx["llm"].get("key_name"),
                "candidate_key_names": ctx["llm"].get("candidate_key_names"),
                "base_url": ctx["llm"].get("base_url"),
                "model": ctx["llm"].get("model"),
            },
            "mode": args.mode,
        },
    )
    if args.mode == "preflight":
        result = preflight(ctx)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=json_default))
        return 0 if result.get("ok") else 2
    pre = preflight(ctx)
    if not pre.get("ok"):
        write_json(ctx["output_dir"] / "grand_tournament_aborted_preflight.json", pre)
        print("Preflight failed; aborting run. See preflight/preflight_result.json")
        return 2
    results = run_all(ctx)
    print(json.dumps({"status": "completed", "stage_count": len(results)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
