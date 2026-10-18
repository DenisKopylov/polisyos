"""Shared typed runtime bindings and Wave 33 diagnostic support."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Pass2DiagnosticBindings:
    """Live facade dependencies used by the Phase 34 diagnostic owners."""

    pdd038_adversarial_scenarios: Any
    pdd_questions: Any
    pdd_titles: Any
    phase34_2: Any
    phase34_2_bundle_artifacts: Any
    path_type: Any
    required_wave33_artifacts: Any
    tool_name: Any
    utc_timezone: Any
    wave: Any
    backlog_summary_for_pdd: Callable[..., Any]
    bundle_refs: Callable[..., Any]
    codes_from_items: Callable[..., Any]
    contains_key_fragment: Callable[..., Any]
    control_by_id: Callable[..., Any]
    extract_quality_scenario_ids: Callable[..., Any]
    finding: Callable[..., Any]
    first_claim: Callable[..., Any]
    first_code: Callable[..., Any]
    intent_summary: Callable[..., Any]
    issue_code_counts: Callable[..., Any]
    mapping: Callable[..., Any]
    now: Callable[..., Any]
    pdd_report: Callable[..., Any]
    readiness_summary_semantics: Callable[..., Any]
    recommendation_for_pdd: Callable[..., Any]
    rel: Callable[..., Any]
    resolve_path: Callable[..., Any]
    scenario_ids_from_command: Callable[..., Any]
    scorecard_blocking_failures: Callable[..., Any]
    scorecard_code_set: Callable[..., Any]
    scorecard_failures: Callable[..., Any]
    source_artifacts_from_observed: Callable[..., Any]
    strategic_surface_terms: Callable[..., Any]
    strings: Callable[..., Any]
    timeline_cache_events: Callable[..., Any]
    verdict_for_pdd: Callable[..., Any]
    wave33_fail_closed_summary: Callable[..., Any]
    wave33_from_observed: Callable[..., Any]
    build_cross_domain_control_report: Callable[..., Any]
    build_metamorphic_prompt_report: Callable[..., Any]
    build_negative_control_report: Callable[..., Any]
    build_scenario_semantic_binding_report: Callable[..., Any]
    datetime_module: Any
    json_module: Any
    load_quality_scenario_contract: Callable[..., Any]


def _aggregate_acceptance(
    pdds: Mapping[str, Mapping[str, Any]], *, bindings: Pass2DiagnosticBindings
) -> str:
    statuses = {str(report.get("acceptance_gate_status")) for report in pdds.values()}
    if "blocked" in statuses:
        return "not_evaluated"
    if "failed" in statuses:
        return "failed"
    return "passed"


def _backlog_summary_for_pdd(
    *,
    pdd_id: str,
    acceptance_gate_status: str,
    verdict: str,
    finding_count: int,
    bindings: Pass2DiagnosticBindings,
) -> str:
    return (
        f"Wave 34 Pass 2 ran {pdd_id} against Wave 33 real-case evidence. "
        f"The diagnostic status is diagnosed, the runtime acceptance gate is "
        f"`{acceptance_gate_status}`, and the verdict is `{verdict}` with "
        f"{finding_count} finding(s)."
    )


def _bundle_refs(
    bundle_path: str, relative_paths: Sequence[str], *, bindings: Pass2DiagnosticBindings
) -> list[str]:
    path_type = bindings.path_type
    if not bundle_path:
        return []
    return [(path_type(bundle_path) / relative_path).as_posix() for relative_path in relative_paths]


def _codes_from_items(items: object, *, bindings: Pass2DiagnosticBindings) -> set[str]:
    codes: set[str] = set()
    if not isinstance(items, list):
        return codes
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in ("code", "failure_code"):
            value = item.get(key)
            if isinstance(value, str) and value:
                codes.add(value)
    return codes


def _contains_key_fragment(
    value: object, fragments: Sequence[str], *, bindings: Pass2DiagnosticBindings
) -> bool:
    _contains_key_fragment = bindings.contains_key_fragment
    wanted = tuple(fragment.casefold() for fragment in fragments)
    if isinstance(value, dict):
        for key, nested in value.items():
            if any(fragment in str(key).casefold() for fragment in wanted):
                return True
            if _contains_key_fragment(nested, wanted):
                return True
    elif isinstance(value, list):
        return any(_contains_key_fragment(item, wanted) for item in value)
    return False


def _contract_control_status(
    pdds: Mapping[str, Mapping[str, Any]], *, bindings: Pass2DiagnosticBindings
) -> dict[str, Any]:
    _mapping = bindings.mapping
    pdd37 = _mapping(pdds.get("PDD-037"))
    pdd55 = _mapping(pdds.get("PDD-055"))
    return {
        "pdd037_contract_control_pass_count": _mapping(pdd37.get("summary")).get(
            "contract_control_pass_count",
            0,
        ),
        "pdd037_semantic_binding_pass_count": _mapping(pdd37.get("summary")).get(
            "semantic_binding_pass_count",
            0,
        ),
        "pdd055_contract_metamorphic_pass_count": _mapping(pdd55.get("summary")).get(
            "contract_metamorphic_pass_count",
            0,
        ),
    }


def _control_by_id(
    report: Mapping[str, Any], control_id: str, *, bindings: Pass2DiagnosticBindings
) -> dict[str, Any]:
    for control in report.get("controls") or []:
        if isinstance(control, dict) and control.get("control_id") == control_id:
            return dict(control)
    return {}


def _dump_json(payload: Mapping[str, Any], *, bindings: Pass2DiagnosticBindings) -> str:
    json = bindings.json_module
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _extract_quality_scenario_ids(
    matrix: Mapping[str, Any], *, bindings: Pass2DiagnosticBindings
) -> list[str]:
    _scenario_ids_from_command = bindings.scenario_ids_from_command
    scenario_ids: list[str] = []
    lanes = matrix.get("lanes")
    if isinstance(lanes, list):
        for lane in lanes:
            if not isinstance(lane, dict):
                continue
            scenario = lane.get("scenario")
            if isinstance(scenario, str) and scenario not in {"", "public_golden"}:
                scenario_ids.append(scenario)
            command = lane.get("command")
            if isinstance(command, list):
                scenario_ids.extend(_scenario_ids_from_command(command))
    selection = matrix.get("selection")
    if isinstance(selection, dict):
        scenario = selection.get("scenario")
        if isinstance(scenario, str) and scenario:
            scenario_ids.append(scenario)
    return sorted(dict.fromkeys(scenario_ids))


def _finding(
    *,
    pdd_id: str,
    code: str,
    severity: str,
    title: str,
    message: str,
    owner: str,
    missing_input: str,
    upstream_cause: str,
    downstream_impact: str,
    refs: Sequence[str],
    scenario_id: str | None = None,
    next_command: str | None = None,
    phase: str = "34.1",
    bindings: Pass2DiagnosticBindings,
) -> dict[str, Any]:
    return {
        "pdd_id": pdd_id,
        "code": code,
        "severity": severity,
        "title": title,
        "message": message,
        "owner": owner,
        "phase": phase,
        "scenario_id": scenario_id,
        "missing_input": missing_input,
        "upstream_cause": upstream_cause,
        "downstream_impact": downstream_impact,
        "refs": list(refs),
        "next_command": next_command
        or "uv run python tools/quality/validation/build_policy_design_case_pass2_diagnostics.py",
    }


def _first_claim(
    grounding: Mapping[str, Any], *, bindings: Pass2DiagnosticBindings
) -> dict[str, Any]:
    claims = grounding.get("claims")
    if isinstance(claims, list):
        for claim in claims:
            if isinstance(claim, dict):
                return dict(claim)
    claim = grounding.get("claim")
    return dict(claim) if isinstance(claim, dict) else {}


def _first_code(
    items: Sequence[Mapping[str, Any]], *, bindings: Pass2DiagnosticBindings
) -> str | None:
    for item in items:
        for key in ("code", "failure_code"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _intent_summary(
    intent: Mapping[str, Any], *, bindings: Pass2DiagnosticBindings
) -> dict[str, Any]:
    return {
        "jurisdiction": intent.get("jurisdiction"),
        "policy_time": intent.get("policy_time"),
        "data_time": intent.get("data_time"),
        "policy_problem": intent.get("policy_problem"),
        "desired_outcome": intent.get("desired_outcome"),
        "proposed_intervention": intent.get("proposed_intervention"),
        "target_population": intent.get("target_population"),
    }


def _issue_code_counts(issues: object, *, bindings: Pass2DiagnosticBindings) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not isinstance(issues, list):
        return counts
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        code = issue.get("code")
        if not isinstance(code, str) or not code:
            continue
        counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))


def _load_contracts(
    *, scenario_ids: Sequence[str], bindings: Pass2DiagnosticBindings
) -> dict[str, dict[str, Any]]:
    load_quality_scenario_contract = bindings.load_quality_scenario_contract
    contracts: dict[str, dict[str, Any]] = {}
    for scenario_id in scenario_ids:
        contracts[scenario_id] = load_quality_scenario_contract(
            scenario_id,
            include_quarantined=True,
        )
    return contracts


def _load_wave33_artifacts(
    *, repo_root: Path, wave33_dir: Path, phase: str = "34.1", bindings: Pass2DiagnosticBindings
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    required_wave33_artifacts = bindings.required_wave33_artifacts
    _finding = bindings.finding
    _rel = bindings.rel
    json = bindings.json_module
    loaded: dict[str, Any] = {}
    artifacts: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for filename in required_wave33_artifacts:
        path = wave33_dir / filename
        exists = path.exists()
        artifacts.append(
            {
                "name": filename,
                "path": _rel(path, repo_root),
                "status": "present" if exists else "missing",
            }
        )
        if not exists:
            issues.append(
                _finding(
                    pdd_id=f"PHASE-{phase}",
                    code="pass2_wave33_required_artifact_missing",
                    severity="PDC-CRITICAL",
                    title="Wave 33 required evidence artifact is missing",
                    message=f"Phase {phase} cannot evaluate Wave 33 evidence without {filename}.",
                    owner="team-runtime-quality",
                    missing_input=_rel(path, repo_root),
                    upstream_cause=(
                        "Wave 33 rebaseline evidence is incomplete or was not generated."
                    ),
                    downstream_impact=(
                        "Pass 2 behavioral diagnostics cannot distinguish real runtime "
                        "evidence from hypothetical scenario contracts."
                    ),
                    refs=[_rel(path, repo_root)],
                    phase=phase,
                )
            )
            loaded[filename] = {}
            continue
        try:
            loaded[filename] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                _finding(
                    pdd_id=f"PHASE-{phase}",
                    code="pass2_wave33_artifact_invalid_json",
                    severity="PDC-CRITICAL",
                    title="Wave 33 evidence artifact is invalid JSON",
                    message=f"{filename} could not be parsed: {exc.msg}.",
                    owner="team-runtime-quality",
                    missing_input=_rel(path, repo_root),
                    upstream_cause="Wave 33 evidence was written in an unreadable form.",
                    downstream_impact="Pass 2 diagnostics cannot consume this artifact.",
                    refs=[_rel(path, repo_root)],
                    phase=phase,
                )
            )
            loaded[filename] = {}
    return loaded, artifacts, issues


def _load_wave33_bundle_artifacts(
    *, repo_root: Path, observed: Mapping[str, Any], phase: str, bindings: Pass2DiagnosticBindings
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    phase34_2_bundle_artifacts = bindings.phase34_2_bundle_artifacts
    path_type = bindings.path_type
    _finding = bindings.finding
    _rel = bindings.rel
    _resolve_path = bindings.resolve_path
    json = bindings.json_module
    bundle_rel = observed.get("bundle_path")
    artifacts: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    loaded: dict[str, Any] = {}
    if not bundle_rel:
        issues.append(
            _finding(
                pdd_id=f"PHASE-{phase}",
                code="pass2_wave33_runtime_bundle_path_missing",
                severity="PDC-CRITICAL",
                title="Wave 33 runtime bundle path is missing",
                message=(
                    "Phase 34.2 cannot inspect runtime adversarial evidence "
                    "without the Wave 33 bundle path."
                ),
                owner="team-runtime-quality",
                missing_input="real_domain_baseline.research_profile_case.bundle_path",
                upstream_cause="Wave 33 real-domain baseline did not record its evidence bundle.",
                downstream_impact=(
                    "Bundle-level fail-closed diagnostics cannot inspect security, "
                    "cache, prompt, or source traces."
                ),
                refs=["_build/policy-design-case/rebaseline/wave-33/real_domain_baseline.json"],
                phase=phase,
            )
        )
        return loaded, artifacts, issues

    bundle_path = _resolve_path(repo_root, path_type(str(bundle_rel)))
    for name, relative_path in phase34_2_bundle_artifacts.items():
        path = bundle_path / relative_path
        exists = path.exists()
        artifacts.append(
            {
                "name": name,
                "path": _rel(path, repo_root),
                "status": "present" if exists else "missing",
            }
        )
        if not exists:
            loaded[name] = {}
            continue
        try:
            loaded[name] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                _finding(
                    pdd_id=f"PHASE-{phase}",
                    code="pass2_wave33_runtime_bundle_artifact_invalid_json",
                    severity="PDC-HIGH",
                    title="Wave 33 runtime bundle artifact is invalid JSON",
                    message=f"{relative_path.as_posix()} could not be parsed: {exc.msg}.",
                    owner="team-runtime-quality",
                    missing_input=_rel(path, repo_root),
                    upstream_cause="Runtime evidence was written in an unreadable form.",
                    downstream_impact="Phase 34.2 cannot inspect this runtime evidence surface.",
                    refs=[_rel(path, repo_root)],
                    phase=phase,
                )
            )
            loaded[name] = {}
    return loaded, artifacts, issues


def _mapping(value: object, *, bindings: Pass2DiagnosticBindings) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _now(*, bindings: Pass2DiagnosticBindings) -> str:
    utc_timezone = bindings.utc_timezone
    datetime = bindings.datetime_module
    return datetime.now(utc_timezone).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _observed_wave33_case(
    loaded: Mapping[str, Any], *, bindings: Pass2DiagnosticBindings
) -> dict[str, Any]:
    _extract_quality_scenario_ids = bindings.extract_quality_scenario_ids
    _intent_summary = bindings.intent_summary
    _mapping = bindings.mapping
    _scorecard_blocking_failures = bindings.scorecard_blocking_failures
    real = _mapping(loaded.get("real_domain_baseline.json"))
    matrix = _mapping(loaded.get("research_real_domain_matrix.json"))
    case = _mapping(loaded.get("policy_design_case_sample.json"))
    scorecard = _mapping(loaded.get("quality_scorecard.json"))
    readiness = _mapping(loaded.get("readiness.json"))
    claim_argument = _mapping(loaded.get("claim_argument.json"))
    production_data = _mapping(loaded.get("production_data_evidence.json"))

    research_case = _mapping(real.get("research_profile_case"))
    observed_scenario_ids = _extract_quality_scenario_ids(matrix)
    return {
        "wave": real.get("wave"),
        "status": real.get("status"),
        "exit_fence": real.get("exit_fence") or {},
        "case_id": case.get("case_id") or research_case.get("case_id"),
        "run_id": case.get("run_id") or research_case.get("run_id"),
        "job_id": case.get("job_id") or research_case.get("job_id"),
        "bundle_path": research_case.get("bundle_path"),
        "authority_profile": case.get("authority_profile")
        or research_case.get("authority_profile")
        or {},
        "observed_scenario_ids": observed_scenario_ids,
        "intent": _intent_summary(_mapping(case.get("intent_envelope"))),
        "scorecard": {
            "quality_status": scorecard.get("quality_status"),
            "approval_state": scorecard.get("approval_state"),
            "blocking_failures": _scorecard_blocking_failures(scorecard),
        },
        "readiness": {
            "status": readiness.get("status"),
            "passes_required": readiness.get("passes_required"),
            "minimum_closeout_gate_failures": readiness.get("minimum_closeout_gate_failures") or [],
        },
        "stage_evidence": research_case.get("stage_evidence") or {},
        "claim_argument": {
            "status": _mapping(claim_argument.get("claim")).get("status"),
            "subclaim_count": len(claim_argument.get("subclaims") or []),
        },
        "production_data": {
            "materialization_ref_count": len(_mapping(production_data.get("materialization_refs"))),
            "bundle_roles": sorted(
                _mapping(_mapping(production_data.get("context")).get("bundles")).keys()
            ),
        },
    }


def _pdd_report(
    *,
    pdd_id: str,
    acceptance_gate_status: str,
    findings: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    details: Mapping[str, Any],
    observed: Mapping[str, Any],
    phase: str = "34.1",
    verdict: str | None = None,
    bindings: Pass2DiagnosticBindings,
) -> dict[str, Any]:
    pdd_questions = bindings.pdd_questions
    pdd_titles = bindings.pdd_titles
    tool_name = bindings.tool_name
    wave = bindings.wave
    _backlog_summary_for_pdd = bindings.backlog_summary_for_pdd
    _now = bindings.now
    _recommendation_for_pdd = bindings.recommendation_for_pdd
    _source_artifacts_from_observed = bindings.source_artifacts_from_observed
    _verdict_for_pdd = bindings.verdict_for_pdd
    _wave33_from_observed = bindings.wave33_from_observed
    normalized_verdict = verdict or _verdict_for_pdd(pdd_id, acceptance_gate_status)
    report = {
        "schema_version": f"policyos.policy_design_case.pass2.{pdd_id.lower()}.v1",
        "tool": tool_name,
        "generated_at": _now(),
        "pdd_id": pdd_id,
        "title": pdd_titles[pdd_id],
        "question": pdd_questions[pdd_id],
        "wave": wave,
        "phase": phase,
        "diagnostic_status": "diagnosed",
        "acceptance_gate_status": acceptance_gate_status,
        "acceptance_gate_result": acceptance_gate_status,
        "runtime_acceptance_status": (
            "failed" if acceptance_gate_status in {"failed", "blocked"} else "passed"
        ),
        "verdict": normalized_verdict,
        "wave33": _wave33_from_observed(observed),
        "source_artifacts": _source_artifacts_from_observed(observed),
        "observed_wave33_case": observed,
        "summary": dict(summary),
        "findings": list(findings),
        "details": dict(details),
        "recommended_gate": _recommendation_for_pdd(pdd_id),
        "backlog_summary": _backlog_summary_for_pdd(
            pdd_id=pdd_id,
            acceptance_gate_status=acceptance_gate_status,
            verdict=normalized_verdict,
            finding_count=len(findings),
        ),
    }
    return report


def _readiness_summary_semantics(
    readiness: Mapping[str, Any], *, bindings: Pass2DiagnosticBindings
) -> dict[str, Any]:
    _mapping = bindings.mapping
    summary = _mapping(readiness.get("summary"))
    status_counts = _mapping(summary.get("status_counts"))
    component_results = _mapping(readiness.get("component_results"))
    readiness_aggregator = _mapping(component_results.get("readiness_aggregator"))
    failure_class_counts = _mapping(summary.get("failure_class_counts"))
    collapsed = (
        readiness.get("status") == "fail"
        and status_counts.get("fail", 0) == 0
        and readiness_aggregator.get("status") == "pass"
    )
    return {
        "status": (
            "collapses_or_hides_root_cause_in_summary" if collapsed else "preserves_root_cause"
        ),
        "readiness_status": readiness.get("status"),
        "summary_status_counts": status_counts,
        "readiness_aggregator_component_status": readiness_aggregator.get("status"),
        "component_failures": readiness.get("component_failures") or [],
        "failure_class_counts": failure_class_counts,
    }


def _recommendation_for_pdd(pdd_id: str, *, bindings: Pass2DiagnosticBindings) -> str:
    if pdd_id == "PDD-037":
        return (
            "Generate research-profile runtime bundles for the five required "
            "cross-domain scenarios and rerun Phase 34.1."
        )
    if pdd_id == "PDD-055":
        return (
            "Add paired metamorphic canary lanes for paraphrase, language, "
            "jurisdiction, time, irrelevant-evidence, and data-removal perturbations."
        )
    if pdd_id == "PDD-056":
        return (
            "Add paired English, Ukrainian, mixed-language, and transliterated runtime "
            "lanes plus a hardcoded-language-path audit."
        )
    if pdd_id == "PDD-038":
        return (
            "Add scenario-bearing no-jurisdiction, legal-conflict, irrelevant-data, "
            "insufficient-ID, hidden-token, prompt-injection, and illegal-policy probes."
        )
    if pdd_id == "PDD-064":
        return (
            "Emit cache/index fingerprint ledgers, manifest-to-index compatibility "
            "proofs, and stale/poisoned/cross-context negative tests."
        )
    if pdd_id == "PDD-065":
        return (
            "Publish a cross-component error taxonomy and make readiness summaries "
            "carry root-cause codes, next actions, and owning layers."
        )
    return (
        "Add strategic behavior ledgers and adversarial gaming, fraud, arbitrage, "
        "misreporting, threshold, enforcement, and mitigation bindings."
    )


def _rel(path: Path | str, repo_root: Path, *, bindings: Pass2DiagnosticBindings) -> str:
    path_type = bindings.path_type
    candidate = path_type(path)
    if not candidate.is_absolute():
        return candidate.as_posix()
    try:
        return candidate.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return candidate.as_posix()


def _resolve_path(repo_root: Path, path: Path, *, bindings: Pass2DiagnosticBindings) -> Path:
    return path if path.is_absolute() else repo_root / path


def _scenario_ids_from_command(
    command: Sequence[Any], *, bindings: Pass2DiagnosticBindings
) -> list[str]:
    rendered = [str(item) for item in command]
    found: list[str] = []
    for index, item in enumerate(rendered):
        if item.startswith("--quality-scenario="):
            found.append(item.split("=", 1)[1])
        elif item == "--quality-scenario" and index + 1 < len(rendered):
            found.append(rendered[index + 1])
    return [item for item in found if item]


def _scorecard_blocking_failures(
    scorecard: Mapping[str, Any], *, bindings: Pass2DiagnosticBindings
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for gate in scorecard.get("quality_gates") or []:
        if not isinstance(gate, dict):
            continue
        if gate.get("status") == "fail" and gate.get("blocking") is True:
            failures.append(
                {
                    "name": gate.get("name"),
                    "code": gate.get("code"),
                    "stage": gate.get("stage"),
                    "evidence_ref": gate.get("evidence_ref"),
                    "next_action": gate.get("next_action"),
                }
            )
    return failures


def _scorecard_code_set(
    scorecard: Mapping[str, Any], *, bindings: Pass2DiagnosticBindings
) -> set[str]:
    _codes_from_items = bindings.codes_from_items
    _scorecard_failures = bindings.scorecard_failures
    return _codes_from_items(_scorecard_failures(scorecard)) | _codes_from_items(
        scorecard.get("quality_gates") or []
    )


def _scorecard_failures(
    scorecard: Mapping[str, Any], *, bindings: Pass2DiagnosticBindings
) -> list[dict[str, Any]]:
    _scorecard_blocking_failures = bindings.scorecard_blocking_failures
    failures = scorecard.get("blocking_quality_failures")
    if isinstance(failures, list):
        return [dict(item) for item in failures if isinstance(item, dict)]
    return _scorecard_blocking_failures(scorecard)


def _source_artifacts_from_observed(
    observed: Mapping[str, Any], *, bindings: Pass2DiagnosticBindings
) -> dict[str, str]:
    source_artifacts = {
        "real_domain_baseline": "_build/policy-design-case/rebaseline/wave-33/real_domain_baseline.json",
        "research_real_domain_matrix": "_build/policy-design-case/rebaseline/wave-33/research_real_domain_matrix.json",
        "policy_design_case_sample": "_build/policy-design-case/rebaseline/wave-33/policy_design_case_sample.json",
        "quality_scorecard": "_build/policy-design-case/rebaseline/wave-33/quality_scorecard.json",
        "readiness": "_build/policy-design-case/rebaseline/wave-33/readiness.json",
        "production_data_evidence": "_build/policy-design-case/rebaseline/wave-33/production_data_evidence.json",
        "claim_argument": "_build/policy-design-case/rebaseline/wave-33/claim_argument.json",
        "policy_grounding_matrix": "_build/policy-design-case/rebaseline/wave-33/policy_grounding_matrix.json",
    }
    if observed.get("bundle_path"):
        source_artifacts["bundle"] = str(observed["bundle_path"])
    return source_artifacts


def _strategic_surface_terms(value: object, *, bindings: Pass2DiagnosticBindings) -> list[str]:
    json = bindings.json_module
    text = json.dumps(value, ensure_ascii=False).casefold()
    terms = (
        "actor",
        "incentive",
        "manipulable",
        "threshold",
        "enforcement",
        "fraud",
        "gaming",
        "arbitrage",
        "misreport",
        "mitigation",
    )
    return [term for term in terms if term in text]


def _strings(value: object, *, bindings: Pass2DiagnosticBindings) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _timeline_cache_events(
    timeline: Mapping[str, Any], *, bindings: Pass2DiagnosticBindings
) -> list[dict[str, Any]]:
    _mapping = bindings.mapping
    events = timeline.get("events")
    if not isinstance(events, list):
        return []
    cache_events: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_name = str(event.get("event") or "")
        metrics = _mapping(event.get("metrics"))
        refs = _mapping(event.get("refs"))
        if "CACHE" not in event_name and not any("cache" in str(key).casefold() for key in metrics):
            continue
        outputs = refs.get("outputs")
        outputs = outputs if isinstance(outputs, list) else []
        cache_events.append(
            {
                "phase": event.get("phase"),
                "event": event.get("event"),
                "status": event.get("status"),
                "artifact_kinds": sorted(
                    {
                        str(output.get("kind"))
                        for output in outputs
                        if isinstance(output, dict) and output.get("kind")
                    }
                ),
                "counter_keys": sorted(metrics.keys()),
            }
        )
    return cache_events


def _verdict_for_pdd(
    pdd_id: str, acceptance_gate_status: str, *, bindings: Pass2DiagnosticBindings
) -> str:
    if acceptance_gate_status == "blocked":
        return f"{pdd_id.lower()}_blocked_by_missing_wave33_input_evidence"
    if acceptance_gate_status == "satisfied":
        return f"{pdd_id.lower()}_acceptance_gate_satisfied"
    verdicts = {
        "PDD-037": "cross_domain_runtime_bundle_coverage_incomplete",
        "PDD-055": "metamorphic_runtime_variant_coverage_incomplete",
        "PDD-056": "multilingual_transliteration_equivalence_not_proven",
        "PDD-038": "adversarial_fail_closed_coverage_incomplete",
        "PDD-064": "cache_index_snapshot_poisoning_controls_not_proven",
        "PDD-065": "cross_component_error_semantics_incomplete",
        "PDD-098": "strategic_behavior_binding_missing",
    }
    return verdicts[pdd_id]


def _wave33_fail_closed_summary(
    loaded: Mapping[str, Any], observed: Mapping[str, Any], *, bindings: Pass2DiagnosticBindings
) -> dict[str, Any]:
    _mapping = bindings.mapping
    _scorecard_blocking_failures = bindings.scorecard_blocking_failures
    real = _mapping(loaded.get("real_domain_baseline.json"))
    scorecard = _mapping(loaded.get("quality_scorecard.json"))
    readiness = _mapping(loaded.get("readiness.json"))
    research_case = _mapping(real.get("research_profile_case"))
    blocking_failures = scorecard.get("blocking_quality_failures")
    if not isinstance(blocking_failures, list):
        blocking_failures = _scorecard_blocking_failures(scorecard)
    minimum_failures = readiness.get("minimum_closeout_gate_failures")
    if not isinstance(minimum_failures, list):
        minimum_failures = []
    fail_closed = bool(
        research_case.get("matrix_status") == "failed"
        or scorecard.get("quality_status") == "fail"
        or readiness.get("status") == "fail"
        or observed.get("readiness", {}).get("status") == "fail"
    )
    return {
        "status": "confirmed" if fail_closed else "not_confirmed",
        "matrix_status": research_case.get("matrix_status"),
        "failure_code": research_case.get("failure_code"),
        "scorecard_status": research_case.get("scorecard_status"),
        "quality_status": scorecard.get("quality_status"),
        "approval_state": scorecard.get("approval_state"),
        "readiness_status": readiness.get("status"),
        "passes_all": readiness.get("passes_all"),
        "passes_required": readiness.get("passes_required"),
        "blocking_quality_failure_count": len(blocking_failures),
        "minimum_closeout_gate_failure_count": len(minimum_failures),
    }


def _wave33_from_observed(
    observed: Mapping[str, Any], *, bindings: Pass2DiagnosticBindings
) -> dict[str, Any]:
    _mapping = bindings.mapping
    scorecard = _mapping(observed.get("scorecard"))
    return {
        "run_id": observed.get("run_id"),
        "job_id": observed.get("job_id"),
        "case_id": observed.get("case_id"),
        "lane_id": observed.get("lane_id"),
        "bundle_path": observed.get("bundle_path"),
        "matrix_status": observed.get("matrix_status"),
        "scorecard_status": scorecard.get("quality_status"),
        "approval_state": scorecard.get("approval_state"),
        "claim_argument_status": _mapping(observed.get("claim_argument")).get("status"),
    }
