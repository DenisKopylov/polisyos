"""Reconcile terminal C1 pilot evidence without importing or rerunning the pipeline.

This finite read-only analysis consumes the campaign's existing persisted schema.
It grants no authority and does not replace the owner's runtime verifier. Primary
responses are archived once through the caller's secret-scanning immutable writer.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
import sqlite3
import stat
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Protocol


class _SafeWriter(Protocol):
    def check_payload(self, payload: object) -> None: ...
    def __call__(self, path: Path, payload: object) -> None: ...


def digest(value: object) -> str:
    """Use the persisted owner's canonical JSON content binding."""
    return raw_digest(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()
    )


def raw_digest(value: bytes) -> str:
    """Bind actual file bytes without replacing absent fields with null."""
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("pilot_artifact_not_object")
    return value


def _sealed(path: Path) -> dict[str, Any]:
    value = _json(path)
    if digest({key: item for key, item in value.items() if key != "content_hash"}) != value.get(
        "content_hash"
    ):
        raise ValueError("pilot_declaration_content_mismatch")
    return value


def _require_identity(actual: object, expected: object, reason: str) -> None:
    if actual != expected:
        raise ValueError(reason)


def _family(root: Path, name: str) -> dict[str, Path]:
    path = root / name
    if not path.exists():
        return {}
    entries = list(path.iterdir())
    if any(item.is_symlink() or not item.is_file() or item.suffix != ".json" for item in entries):
        raise ValueError("pilot_artifact_family_ambiguous:" + name)
    return {item.stem: item for item in entries}


def _integer(value: object) -> bool:
    return type(value) is int and value >= 0


def _usage(value: object) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    first, second = value.get("prompt_tokens"), value.get("completion_tokens")
    if not _integer(first) or not _integer(second):
        return None
    total = value.get("total_tokens")
    if total is not None and (not _integer(total) or total != first + second):
        return None
    return first, second


def _aggregate_usage(attempts: list[dict[str, Any]], rates: dict[str, float]) -> dict[str, Any]:
    known = [row for row in attempts if row["provider_usage"] is not None]
    unknown = [row["attempt_id"] for row in attempts if row["provider_usage"] is None]
    prompt = sum(row["provider_usage"][0] for row in known)
    completion = sum(row["provider_usage"][1] for row in known)
    gaps = [row["local_token_gap"] for row in attempts if row["local_token_gap"] is not None]
    checkpoint_unknown = [row for row in attempts if not row["checkpoint_usage_known"]]
    durations = [row["transport_elapsed_seconds"] for row in attempts]
    known_durations = [
        value
        for value in durations
        if type(value) in (float, int) and math.isfinite(value) and value >= 0
    ]
    return {
        "provider_service_seconds": sum(known_durations),
        "unknown_provider_duration_attempts": len(durations) - len(known_durations),
        "provider_service_time_scope": (
            "serial sum of measured request latency; excludes startup, queues, "
            "owner CPU and graph finalization"
        ),
        "attempt_denominator": len(attempts),
        "known_provider_usage_attempts": len(known),
        "unknown_provider_usage_attempts": len(unknown),
        "unknown_attempt_ids": unknown,
        "checkpoint_unknown_attempts": len(checkpoint_unknown),
        "checkpoint_unknown_provider_known": sum(
            row["provider_usage"] is not None for row in checkpoint_unknown
        ),
        "known_prompt_tokens": prompt,
        "known_completion_tokens": completion,
        "known_total_tokens": prompt + completion,
        "total_tokens": None if unknown else prompt + completion,
        "observed_cost_usd": prompt * rates["input"] + completion * rates["output"],
        "cost_status": "observed_lower_bound" if unknown else "all_reserved_attempt_usage_known",
        "billing_status": "frozen_declared_rate_times_observed_usage; not provider billing proof",
        "local_prompt_gap_count": len(gaps),
        "local_prompt_gap_sum": sum(gaps) if gaps else None,
        "local_prompt_gap_mean": sum(gaps) / len(gaps) if gaps else None,
    }


def reconcile_pilot(binding_path: Path, *, project_root: Path) -> dict[str, Any]:
    """Reconcile the complete frozen frame and every reserved attempt on disk/SQL."""
    binding = _sealed(binding_path)
    declaration = _sealed(project_root / binding["pilot_declaration_path"])
    plan = binding["campaign_plan"]
    synthetic = binding["synthetic"]
    if (
        type(synthetic) is not bool
        or plan["synthetic"] is not synthetic
        or declaration["synthetic"] is not synthetic
    ):
        raise ValueError("pilot_synthetic_binding_mismatch")
    if (
        binding["full_pass_authorized"] is not False
        or declaration["full_pass_authorized"] is not False
    ):
        raise ValueError("pilot_full_pass_scope_invalid")
    if (
        binding["pilot_declaration_hash"] != declaration["content_hash"]
        or plan["provider_profile_hash"] != declaration["content_hash"]
    ):
        raise ValueError("pilot_declaration_binding_mismatch")
    if any(
        plan[name] != declaration["model_id"] for name in ("screening_model", "extraction_model")
    ):
        raise ValueError("pilot_declared_model_mismatch")
    root = project_root / binding["output_root"]
    bound = digest(plan)
    primaries: dict[str, Path] = {}

    def packet(path: Path, kind: str, expected_hash: str | None = None) -> dict[str, Any]:
        if expected_hash is not None and raw_digest(path.read_bytes()) != expected_hash:
            raise ValueError("pilot_artifact_byte_binding_mismatch")
        value = _json(path)
        if (
            value.get("schema_version") != "policyos.academic.extraction_campaign.v1"
            or value.get("artifact_kind") != kind
            or value.get("campaign_binding") != bound
            or value.get("synthetic") is not synthetic
            or value.get("scope") != "candidate_only"
        ):
            raise ValueError("pilot_artifact_provenance_mismatch")
        return value

    if packet(root / "plan.json", "plan")["plan"] != plan:
        raise ValueError("pilot_plan_mismatch")
    families = {
        name: _family(root, name)
        for name in (
            "inputs",
            "intents",
            "attempts",
            "provider_attempts",
            "works",
            "observations",
            "strangles",
        )
    }
    with sqlite3.connect(
        (root / "checkpoint.sqlite3").resolve().as_uri() + "?mode=ro", uri=True
    ) as con:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        works = [dict(row) for row in con.execute("SELECT * FROM works ORDER BY ordinal")]
        attempts = [
            dict(row)
            for row in con.execute("SELECT * FROM attempts ORDER BY work_key,phase,ordinal")
        ]
        identity_rows = {
            (row[0], row[1])
            for row in con.execute("SELECT identity_hash,work_key FROM work_identities")
        }
        metadata = dict(con.execute("SELECT key,value FROM metadata"))
        sql_works = dict(con.execute("SELECT state,COUNT(*) FROM works GROUP BY state"))
        sql_attempts = dict(con.execute("SELECT state,COUNT(*) FROM attempts GROUP BY state"))
    _require_identity(
        dict(Counter(row["state"] for row in works)),
        sql_works,
        "pilot_work_state_reconciliation_mismatch",
    )
    _require_identity(
        dict(Counter(row["state"] for row in attempts)),
        sql_attempts,
        "pilot_attempt_state_reconciliation_mismatch",
    )
    members = declaration["execution_members"]
    member_map = {row["work_id"]: row for row in members}
    if len(members) != 6 or len(member_map) != 6 or len(works) != 6 or plan["input_count"] != 6:
        raise ValueError("pilot_complete_six_not_established")
    _require_identity(
        set(families["inputs"]),
        {row["work_key"][7:] for row in works},
        "pilot_input_identity_mismatch",
    )
    key_to_id: dict[str, str] = {}
    for row in works:
        key = row["work_key"]
        source = packet(families["inputs"][key[7:]], "input", row["source_hash"])
        work = source["work"]
        if source["work_key"] != key or digest(work) != key:
            raise ValueError("pilot_source_content_mismatch")
        identifier = work["id"]
        if (
            identifier not in member_map
            or raw_digest(work["abstract"].encode())
            != member_map[identifier]["abstract_content_hash"]
        ):
            raise ValueError("pilot_input_identity_mismatch")
        key_to_id[key] = identifier
    _require_identity(
        list(key_to_id.values()), [row["work_id"] for row in members], "pilot_input_order_mismatch"
    )
    _require_identity(
        identity_rows,
        {(digest(value), key) for key, value in key_to_id.items()},
        "pilot_identity_index_mismatch",
    )
    frame_hash = raw_digest("".join(row["work_key"] + "\n" for row in works).encode())
    if frame_hash != plan["input_digest"] or metadata.get("frame_admitted") != frame_hash:
        raise ValueError("pilot_frame_admission_mismatch")
    by_id = {row["attempt_id"]: row for row in attempts}
    if len(by_id) != len(attempts):
        raise ValueError("pilot_attempt_identity_mismatch")
    _require_identity(set(families["intents"]), set(by_id), "pilot_intent_identity_mismatch")
    _require_identity(
        set(families["attempts"]),
        {row["attempt_id"] for row in attempts if row["output_hash"] is not None},
        "pilot_attempt_identity_mismatch",
    )
    if set(families["provider_attempts"]) - set(by_id):
        raise ValueError("pilot_unbound_provider_observation")
    observed: list[dict[str, Any]] = []
    parsed_by_work: dict[str, dict[str, Any]] = defaultdict(dict)
    for row in attempts:
        attempt_id, key = row["attempt_id"], row["work_key"]
        if key not in key_to_id:
            raise ValueError("pilot_attempt_work_unbound")
        intent = packet(families["intents"][attempt_id], "attempt_intent", row["intent_hash"])
        context = intent["context"]
        expected_model = (
            plan["screening_model"] if row["phase"] == "screening" else plan["extraction_model"]
        )
        for name, expected in {
            "campaign_id": plan["campaign_id"],
            "work_id": key_to_id[key],
            "work_key": key,
            "phase": row["phase"],
            "phase_key": row["phase_key"],
            "attempt_id": attempt_id,
            "attempt_ordinal": row["ordinal"],
            "model_id": expected_model,
            "synthetic": synthetic,
            "scope": "candidate_only",
        }.items():
            if context.get(name) != expected or (
                name == "synthetic" and context.get(name) is not synthetic
            ):
                raise ValueError("pilot_attempt_context_mismatch")
        expected_phase = digest((bound, key, row["phase"], expected_model, context["prompt_hash"]))
        if (
            row["phase_key"] != expected_phase
            or digest((expected_phase, row["ordinal"]))[7:] != attempt_id
        ):
            raise ValueError("pilot_attempt_reservation_mismatch")
        result = None
        if row["output_hash"] is not None:
            result = packet(families["attempts"][attempt_id], "attempt_result", row["output_hash"])
            if result["context"] != context or result["status"] != row["state"]:
                raise ValueError("pilot_attempt_result_mismatch")
            primaries["attempts/" + attempt_id + ".json"] = families["attempts"][attempt_id]
        observation = None
        if attempt_id in families["provider_attempts"]:
            path = families["provider_attempts"][attempt_id]
            observation = _json(path)
            if (
                observation.get("schema_version") != binding["transport_observation_epoch"]
                or observation.get("synthetic") is not synthetic
                or observation.get("authority_status") != "candidate_only"
                or observation.get("context") != context
                or observation.get("model_id") != expected_model
                or observation.get("reported_model_id") not in (None, expected_model)
                or observation.get("prompt_hash") != context["prompt_hash"]
            ):
                raise ValueError("pilot_provider_attribution_mismatch")
            if (
                result is not None
                and result["status"] == "returned"
                and observation.get("parsed_response_hash") != digest(result["parsed"])
            ):
                raise ValueError("pilot_parsed_response_binding_mismatch")
            primaries["provider_attempts/" + attempt_id + ".json"] = path
        provider_usage = _usage(observation.get("usage")) if observation is not None else None
        recorded_usage = _usage(result.get("usage")) if result is not None else None
        if (
            provider_usage is not None
            and recorded_usage is not None
            and provider_usage != recorded_usage
        ):
            raise ValueError("pilot_usage_owner_transport_mismatch")
        estimate = (
            observation.get("local_prompt_token_estimate") if observation is not None else None
        )
        gap = (
            provider_usage[0] - estimate
            if provider_usage is not None and _integer(estimate)
            else None
        )
        observed.append(
            {
                "attempt_id": attempt_id,
                "work_id": key_to_id[key],
                "phase": row["phase"],
                "state": row["state"],
                "provider_usage": provider_usage,
                "checkpoint_usage_known": row["usage_known"] == 1,
                "local_token_gap": gap,
                "error_kind": observation.get("error_kind")
                if observation is not None
                else "observation_absent",
                "transport_elapsed_seconds": observation.get("transport_elapsed_seconds")
                if observation is not None
                else None,
            }
        )
        if result is not None and result["status"] == "returned":
            if row["phase"] in parsed_by_work[key_to_id[key]]:
                raise ValueError("pilot_multiple_returned_phase_results_ambiguous")
            parsed_by_work[key_to_id[key]][row["phase"]] = {
                "parsed": result["parsed"],
                "prompt_hash": context["prompt_hash"],
            }
    _require_identity(
        set(families["works"]),
        {row["work_key"][7:] for row in works if row["state"] == "complete"},
        "pilot_outcome_identity_mismatch",
    )
    judgments, work_costs = {}, []
    rates = declaration["live_pricing_usd_per_token"]
    if any(
        type(rates.get(key)) not in (float, int) or not math.isfinite(rates[key]) or rates[key] < 0
        for key in ("input", "output")
    ):
        raise ValueError("pilot_rate_invalid")
    for row in works:
        key, identifier = row["work_key"], key_to_id[row["work_key"]]
        if row["state"] != "complete":
            raise ValueError("pilot_work_completion_not_established")
        outcome = packet(families["works"][key[7:]], "work_outcome", row["output_hash"])
        phase_refs = [
            {
                field: attempt[field]
                for field in ("attempt_id", "intent_hash", "output_hash", "state")
            }
            for attempt in attempts
            if attempt["work_key"] == key
        ]
        if (
            outcome["work_key"] != key
            or outcome["status"] != row["output_status"]
            or outcome["phase_artifacts"] != phase_refs
            or digest(outcome) != row["intended_output_hash"]
        ):
            raise ValueError("pilot_work_phase_binding_mismatch")
        phases = parsed_by_work[identifier]
        screen = phases.get("screening")
        extraction = phases.get("extraction")
        judgments[identifier] = {
            "input_hash": member_map[identifier]["abstract_content_hash"],
            "screening": screen["parsed"].get("relevant") if screen else None,
            "screening_prompt_hash": screen["prompt_hash"] if screen else None,
            "extraction_hash": digest(extraction["parsed"])
            if extraction
            and outcome["status"] in ("extracted", "verification_unavailable", "no_claim_artifact")
            else None,
        }
        usage = _aggregate_usage(
            [attempt for attempt in observed if attempt["work_id"] == identifier], rates
        )
        work_costs.append(
            {
                "work_id": identifier,
                "stratum": member_map[identifier]["stratum"],
                "status": outcome["status"],
                "usage": usage,
            }
        )
    summary_events = []
    for family, kind in (("observations", "summary"), ("strangles", "strangle")):
        for name, path in families[family].items():
            value = packet(path, kind)
            if kind == "summary":
                summary_events.append(
                    {
                        "path": str(path),
                        "sha256": raw_digest(path.read_bytes()),
                        "matches_terminal_checkpoint": value.get("works") == sql_works
                        and value.get("attempts") == sql_attempts,
                        "reported_unknown_usage_attempts": value.get("unknown_usage_attempts"),
                    }
                )
            primaries[family + "/" + name + ".json"] = path
    report = {
        "schema_version": "corr.pilot_analysis.v1",
        "synthetic": synthetic,
        "authority_status": "candidate_measurement",
        "authority_granted": False,
        "binding_path": str(binding_path),
        "binding_hash": binding["content_hash"],
        "model_id": declaration["model_id"],
        "work_count": len(works),
        "attempt_count": len(attempts),
        "status": "complete_frame_reconciled",
        "work_states": sql_works,
        "attempt_states": sql_attempts,
        "outcomes": dict(Counter(row["output_status"] for row in works)),
        "phase_counts": dict(Counter(row["phase"] for row in attempts)),
        "error_counts": dict(
            Counter(row["error_kind"] for row in observed if row["error_kind"] is not None)
        ),
        "summary_events": summary_events,
        "provider_observation_count": len(families["provider_attempts"]),
        "usage": _aggregate_usage(observed, rates),
        "work_costs": work_costs,
        "phase_usage": {
            phase: _aggregate_usage([row for row in observed if row["phase"] == phase], rates)
            for phase in sorted({row["phase"] for row in observed})
        },
        "checkpoint_usage_limitation": (
            "failed attempt checkpoints may mark usage unknown while transport "
            "retains observed usage; cost uses transport"
        ),
        "source_root": str(root),
        "complete_file_identity_reconciliation": "equal",
    }
    return {
        "synthetic": synthetic,
        "report": report,
        "judgments": judgments,
        "primaries": primaries,
        "root": root,
    }


def _boolean(value: object) -> bool:
    return type(value) is bool


def compare_models(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Bound only mutually exclusive same-prompt boolean screening judgments."""
    first, second = left["judgments"], right["judgments"]
    _require_identity(set(first), set(second), "pilot_comparison_frame_mismatch")
    paired, disagreements, joint, structural = 0, 0, 0, 0
    excluded = []
    extraction_excluded = []
    for identifier in sorted(first):
        a, b = first[identifier], second[identifier]
        if (
            a.get("input_hash") is None
            or a.get("input_hash") != b.get("input_hash")
            or not _boolean(a.get("screening"))
            or not _boolean(b.get("screening"))
            or a.get("screening_prompt_hash") is None
            or a.get("screening_prompt_hash") != b.get("screening_prompt_hash")
        ):
            excluded.append(
                {
                    "work_id": identifier,
                    "reason": "paired_same_input_prompt_boolean_not_established",
                }
            )
        else:
            paired += 1
            disagreements += a["screening"] != b["screening"]
        if (
            a.get("input_hash") is not None
            and a.get("input_hash") == b.get("input_hash")
            and a.get("screening") is True
            and b.get("screening") is True
            and a.get("extraction_hash") is not None
            and b.get("extraction_hash") is not None
        ):
            joint += 1
            structural += a["extraction_hash"] != b["extraction_hash"]
        else:
            extraction_excluded.append(identifier)
    return {
        "synthetic": left["synthetic"] or right["synthetic"],
        "authority_status": "candidate_measurement",
        "authority_granted": False,
        "complete_document_denominator": len(first),
        "paired_boolean_documents": paired,
        "disagreements": disagreements,
        "document_union_error_lower_bound": disagreements / paired if paired else None,
        "pooled_judgment_error_lower_bound": disagreements / (2 * paired) if paired else None,
        "interpretation": (
            "at least one model wrong on D/N paired documents; pooled at least "
            "D/(2N); no individual-model correctness or population claim"
        ),
        "not_established": excluded,
        "joint_extraction_documents": joint,
        "extraction_structural_differences": structural,
        "extraction_not_established_work_ids": extraction_excluded,
        "extraction_interpretation": (
            "descriptive structural inequality; not mutually exclusive judgments or error evidence"
        ),
    }


def _entry(path: Path) -> tuple[Any, ...]:
    info = path.lstat()
    kind = (
        "file"
        if stat.S_ISREG(info.st_mode)
        else "directory"
        if stat.S_ISDIR(info.st_mode)
        else "symlink"
        if stat.S_ISLNK(info.st_mode)
        else "other"
    )
    return kind, info.st_size, getattr(info, "st_blocks", None), info.st_dev, info.st_ino


def _walk_inventory(root: Path) -> tuple[dict[str, tuple[Any, ...]], list[str]]:
    values, ambiguous = {}, []

    def on_error(error: OSError) -> None:
        ambiguous.append(str(Path(error.filename).relative_to(root)))

    for directory, dirs, files in os.walk(root, followlinks=False, onerror=on_error):
        for name in dirs + files:
            path = Path(directory) / name
            try:
                values[path.relative_to(root).as_posix()] = _entry(path)
            except OSError:
                ambiguous.append(path.relative_to(root).as_posix())
    return values, ambiguous


def storage_inventory(root: Path, *, completed: int, wall_seconds: float) -> dict[str, Any]:
    """Compare full typed path/length sets independently; never confuse I/O with space."""
    if not root.is_dir() or root.is_symlink():
        raise ValueError("storage_root_not_established")
    first, ambiguous = {}, []
    for path in root.rglob("*"):
        try:
            first[path.relative_to(root).as_posix()] = _entry(path)
        except OSError:
            ambiguous.append(path.relative_to(root).as_posix())
    second, other_ambiguous = _walk_inventory(root)
    _require_identity(first, second, "storage_identity_value_mismatch")
    all_ambiguous = sorted(set(ambiguous + other_ambiguous))
    categories: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "logical_bytes": 0})
    logical = 0
    allocated_by_inode = {}
    for name, (kind, size, blocks, device, inode) in first.items():
        category = (
            "wal"
            if name.endswith("-wal")
            else "shm"
            if name.endswith("-shm")
            else "lock"
            if name.endswith(".lock")
            else kind
        )
        categories[category]["count"] += 1
        if kind == "file":
            logical += size
            categories[category]["logical_bytes"] += size
            if blocks is None:
                all_ambiguous.append(name)
            else:
                allocated_by_inode[(device, inode)] = blocks * 512
    return {
        "root": str(root),
        "status": "ambiguous" if all_ambiguous else "measured",
        "entry_count": len(first),
        "file_count": sum(value[0] == "file" for value in first.values()),
        "categories": dict(categories),
        "ambiguous_paths": sorted(set(all_ambiguous)),
        "logical_file_bytes": None if all_ambiguous else logical,
        "observed_logical_file_bytes_lower_bound": logical,
        "allocated_file_bytes": None if all_ambiguous else sum(allocated_by_inode.values()),
        "allocated_semantics": (
            "sum st_blocks*512 per unique inode; exclusive APFS physical extents not established"
        ),
        "identity_value_reconciliation": "equal",
        "excluded_paths": [],
        "logical_bytes_per_completed_work": logical / completed
        if completed and not all_ambiguous
        else None,
        "logical_bytes_per_wall_second": logical / wall_seconds
        if wall_seconds > 0 and not all_ambiguous
        else None,
        "native_write_io_is_storage_growth": False,
    }


class _Regression:
    def __init__(self) -> None:
        self.n = 0
        self.x = self.y = self.xx = self.xy = 0.0

    def add(self, x: float, y: float) -> None:
        self.n += 1
        self.x += x
        self.y += y
        self.xx += x * x
        self.xy += x * y

    def slope(self) -> float | None:
        denominator = self.n * self.xx - self.x * self.x
        return (self.n * self.xy - self.x * self.y) / denominator if denominator > 0 else None


def warm_memory(trace: Path, *, expected_count: int) -> dict[str, Any]:
    """Stream complete samples; OLS after at least one durable completion is descriptive."""
    count, warm, ambiguous = 0, 0, 0
    by_time, by_completed = _Regression(), _Regression()
    with trace.open() as stream:
        for line in stream:
            count += 1
            value = json.loads(line)
            completed, rss = value.get("completed_work_count"), value.get("summed_rss_bytes")
            if (
                value.get("measurement_status") != "measured"
                or not _integer(completed)
                or not _integer(rss)
            ):
                ambiguous += 1
                continue
            if completed >= 1:
                warm += 1
                by_time.add(value["elapsed_seconds"], rss)
                by_completed.add(completed, rss)
    with trace.open("rb") as stream:
        independent_count = sum(1 for _ in stream)
    if count != expected_count or count != independent_count:
        raise ValueError("pilot_trace_denominator_mismatch")
    return {
        "sample_count": count,
        "warm_sample_count": warm,
        "ambiguous_sample_count": ambiguous,
        "rss_slope_bytes_per_second": by_time.slope(),
        "rss_slope_bytes_per_completed": by_completed.slope(),
        "scope": (
            "samples after >=1 durable completion; six-input descriptive OLS, no "
            "complexity or knee claim"
        ),
    }


def forecast(report: dict[str, Any], target_path: Path) -> dict[str, Any]:
    """Apply the existing independently enumerated target populations conditionally."""
    target = _json(target_path)
    if (
        digest({key: value for key, value in target.items() if key != "declaration_digest"})
        != target["declaration_digest"]
    ):
        raise ValueError("pilot_forecast_target_binding_mismatch")
    rows = target["strata"]
    denominator = target["denominators"]
    if (
        sum(row["complete_eligible_member_count"] for row in rows)
        != denominator["primary_eligible_abstract_work_ids"]
        or sum(row["secondary_target_member_count"] for row in rows)
        != denominator["secondary_target_work_ids"]
        or len({row["stratum"] for row in rows}) != len(rows)
    ):
        raise ValueError("pilot_target_denominator_mismatch")
    primary = secondary = 0.0
    primary_tokens = secondary_tokens = 0.0
    primary_seconds = secondary_seconds = 0.0
    unknown_duration = False
    per_stratum = []
    unknown = False
    for row in rows:
        members = [work for work in report["work_costs"] if work["stratum"] == row["stratum"]]
        if len(members) != row["unchanged_pilot_member_count"]:
            raise ValueError("pilot_forecast_stratum_not_established")
        unknown |= any(work["usage"]["unknown_provider_usage_attempts"] for work in members)
        average = sum(work["usage"]["observed_cost_usd"] for work in members) / len(members)
        average_tokens = sum(work["usage"]["known_total_tokens"] for work in members) / len(members)
        average_seconds = sum(work["usage"]["provider_service_seconds"] for work in members) / len(
            members
        )
        unknown_duration |= any(
            work["usage"]["unknown_provider_duration_attempts"] for work in members
        )
        primary_tokens += average_tokens * row["complete_eligible_member_count"]
        secondary_tokens += average_tokens * row["secondary_target_member_count"]
        primary_seconds += average_seconds * row["complete_eligible_member_count"]
        secondary_seconds += average_seconds * row["secondary_target_member_count"]
        primary += average * row["complete_eligible_member_count"]
        secondary += average * row["secondary_target_member_count"]
        per_stratum.append(
            {
                "stratum": row["stratum"],
                "pilot_count": len(members),
                "mean_observed_cost_usd": average,
                "mean_known_tokens": average_tokens,
                "mean_provider_service_seconds": average_seconds,
                "primary_target_count": row["complete_eligible_member_count"],
                "secondary_target_count": row["secondary_target_member_count"],
            }
        )
    return {
        "target_path": str(target_path),
        "target_digest": target["declaration_digest"],
        "primary_work_count": denominator["primary_eligible_abstract_work_ids"],
        "secondary_work_count": denominator["secondary_target_work_ids"],
        "primary_known_tokens": primary_tokens,
        "secondary_known_tokens": secondary_tokens,
        "primary_provider_service_seconds": primary_seconds,
        "secondary_provider_service_seconds": secondary_seconds,
        "provider_service_time_status": "conditional_lower_bound"
        if unknown_duration
        else "conditional_serial_service_time",
        "provider_service_time_limit": (
            "sum of request latencies, not end-to-end pass wall time; concurrency "
            "and startup/owner/graph costs excluded"
        ),
        "primary_cost_usd": primary,
        "secondary_cost_usd": secondary,
        "status": "conditional_lower_bound" if unknown else "conditional_point_estimate",
        "strata": per_stratum,
        "assumption": target["conditional_forecast_assumption"],
        "unavailable_abstract_cost": target["unavailable_abstract_cost"],
        "occurrence_reextraction_cost": target["occurrence_reextraction_cost"],
        "full_pass_authorized": False,
        "billing_proof": False,
    }


def archive_primary(
    result: dict[str, Any], destination: Path, *, writer: _SafeWriter
) -> list[dict[str, Any]]:
    """Pre-scan every primary payload before copying once with exact byte readback."""
    entries = []
    for relative, path in sorted(result["primaries"].items()):
        value = _json(path)
        writer.check_payload(value)
        if value.get("synthetic") is not result["synthetic"]:
            raise ValueError("pilot_archive_synthetic_mismatch")
        entries.append((relative, path, raw_digest(path.read_bytes())))
    refs = []
    for relative, source, expected_hash in entries:
        if raw_digest(source.read_bytes()) != expected_hash:
            raise ValueError("pilot_archive_source_changed")
        target = destination / relative
        writer(target, _json(source))
        if raw_digest(target.read_bytes()) != expected_hash:
            raise ValueError("pilot_archive_bytes_changed")
        refs.append({"path": str(target), "source_path": str(source), "sha256": expected_hash})
    return refs


def main() -> int:
    """Root-only archival entrypoint; credentials are loaded only by this explicit CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", type=Path, action="append", required=True)
    parser.add_argument("--profile", type=Path, action="append", required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(args.binding) != 2 or len(args.profile) != 2:
        raise ValueError("pilot_two_complete_models_required")
    common = importlib.import_module(
        "docs.superpowers.journals.corr-evidence.c1-capacity.capacity_common"
    )
    writer = common.SafeJsonWriter(common.load_credential())
    results = [reconcile_pilot(path, project_root=Path.cwd()) for path in args.binding]
    reports = []
    for index, (result, profile_path) in enumerate(zip(results, args.profile, strict=True)):
        profile = _json(profile_path / "summary.json")
        if profile["binding_hash"] != result["report"]["binding_hash"]:
            raise ValueError("pilot_profile_binding_mismatch")
        report = result["report"]
        report["resources"] = {
            "profile_path": str(profile_path / "summary.json"),
            "profile_sha256": raw_digest((profile_path / "summary.json").read_bytes()),
            "warm_memory": warm_memory(
                profile_path / "samples.jsonl", expected_count=profile["sample_count"]
            ),
        }
        report["storage"] = storage_inventory(
            result["root"], completed=report["work_count"], wall_seconds=profile["wall_seconds"]
        )
        report["forecast"] = forecast(report, args.target)
        report["primary_archive"] = archive_primary(
            result, args.output / ("model-" + str(index)), writer=writer
        )
        reports.append(report)
    packet = {
        "schema_version": "corr.paired_pilot_analysis.v1",
        "synthetic": any(result["synthetic"] for result in results),
        "authority_status": "candidate_measurement",
        "authority_granted": False,
        "models": reports,
        "comparison": compare_models(*results),
        "full_pass_authorized": False,
        "semantics_path": str(Path(__file__).with_name("pilot-analysis-semantics.md")),
        "semantics_sha256": raw_digest(
            Path(__file__).with_name("pilot-analysis-semantics.md").read_bytes()
        ),
    }
    writer(args.output / "analysis.json", packet)
    sys.stdout.write(
        writer.encode(
            {"analysis_path": str(args.output / "analysis.json"), "authority_granted": False}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
