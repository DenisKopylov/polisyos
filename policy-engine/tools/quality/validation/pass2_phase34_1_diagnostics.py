"""Complete Phase 34.1 PDD report calculations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tools.quality.validation.pass2_diagnostics_support import Pass2DiagnosticBindings


def _build_pdd037_report(
    *,
    contracts: Mapping[str, Mapping[str, Any]],
    observed: Mapping[str, Any],
    input_issues: Sequence[Mapping[str, Any]],
    wave33_dir: Path,
    repo_root: Path,
    bindings: Pass2DiagnosticBindings,
) -> dict[str, Any]:
    _finding = bindings.finding
    _mapping = bindings.mapping
    _pdd_report = bindings.pdd_report
    _rel = bindings.rel
    _strings = bindings.strings
    build_cross_domain_control_report = bindings.build_cross_domain_control_report
    build_scenario_semantic_binding_report = bindings.build_scenario_semantic_binding_report
    observed_scenarios = set(_strings(observed.get("observed_scenario_ids")))
    scenarios: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = list(input_issues)
    for scenario_id, contract in contracts.items():
        expected = _mapping(contract.get("expected_evidence_contract"))
        runtime_present = scenario_id in observed_scenarios
        contract_controls = build_cross_domain_control_report(dict(contract))
        semantic_binding = build_scenario_semantic_binding_report(dict(contract))
        scenario_row = {
            "scenario_id": scenario_id,
            "title": contract.get("title"),
            "runtime_evidence_status": "present" if runtime_present else "missing",
            "domain_hint": contract.get("domain_hint"),
            "context": contract.get("context") or {},
            "expected_contract": {
                "normative_fact_classes": expected.get("normative_fact_classes") or [],
                "admissible_data_source_families": expected.get("admissible_data_source_families")
                or [],
                "foundry_method_expectations": expected.get("foundry_method_expectations") or [],
                "conflict_checks": expected.get("conflict_checks") or [],
            },
            "contract_control_report": contract_controls,
            "semantic_binding_report": semantic_binding,
        }
        if not runtime_present:
            findings.append(
                _finding(
                    pdd_id="PDD-037",
                    code="pass2_wave33_cross_domain_bundle_missing",
                    severity="PDC-CRITICAL",
                    title="Wave 33 lacks required cross-domain runtime bundle",
                    message=(
                        "No Wave 33 runtime bundle was observed for the required "
                        f"cross-domain scenario {scenario_id}."
                    ),
                    owner="team-runtime-quality",
                    missing_input=(f"runtime-owned research-profile bundle for {scenario_id}"),
                    upstream_cause=(
                        "Wave 33 emitted a single research-profile baseline, not "
                        "the five Pass 2 cross-domain scenarios."
                    ),
                    downstream_impact=(
                        "PolicyOS cannot yet prove Lex/Fabric/Foundry/Scientist "
                        "bindings adapt across materially different policy domains."
                    ),
                    scenario_id=scenario_id,
                    refs=[_rel(wave33_dir, repo_root)],
                    next_command=(
                        "Run the research-profile canary lane for this scenario, "
                        "then rebuild Phase 34.1 diagnostics."
                    ),
                )
            )
        scenarios.append(scenario_row)
    missing = [row for row in scenarios if row["runtime_evidence_status"] != "present"]
    acceptance = "blocked" if input_issues else ("failed" if missing else "satisfied")
    return _pdd_report(
        pdd_id="PDD-037",
        acceptance_gate_status=acceptance,
        findings=findings,
        summary={
            "required_domain_count": len(scenarios),
            "runtime_domain_count": len(scenarios) - len(missing),
            "missing_runtime_domain_count": len(missing),
            "contract_control_pass_count": sum(
                1 for row in scenarios if row["contract_control_report"].get("status") == "pass"
            ),
            "semantic_binding_pass_count": sum(
                1 for row in scenarios if row["semantic_binding_report"].get("status") == "pass"
            ),
        },
        details={"scenarios": scenarios},
        observed=observed,
    )


def _build_pdd055_report(
    *,
    contracts: Mapping[str, Mapping[str, Any]],
    observed: Mapping[str, Any],
    input_issues: Sequence[Mapping[str, Any]],
    wave33_dir: Path,
    repo_root: Path,
    bindings: Pass2DiagnosticBindings,
) -> dict[str, Any]:
    _control_by_id = bindings.control_by_id
    _finding = bindings.finding
    _pdd_report = bindings.pdd_report
    _rel = bindings.rel
    _strings = bindings.strings
    build_metamorphic_prompt_report = bindings.build_metamorphic_prompt_report
    build_negative_control_report = bindings.build_negative_control_report
    observed_scenarios = set(_strings(observed.get("observed_scenario_ids")))
    scenarios: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = list(input_issues)
    total_variants = 0
    present_variants = 0
    missing_data_removal = 0
    for scenario_id, contract in contracts.items():
        metamorphic = build_metamorphic_prompt_report(dict(contract))
        negative = build_negative_control_report(dict(contract))
        runtime_variants: list[dict[str, Any]] = []
        for variant in metamorphic.get("variants") or []:
            if not isinstance(variant, dict):
                continue
            variant_id = str(variant.get("variant_id") or "variant")
            present = scenario_id in observed_scenarios and variant_id == "en_direct"
            total_variants += 1
            present_variants += 1 if present else 0
            runtime_variants.append(
                {
                    "variant_id": variant_id,
                    "locale": variant.get("locale"),
                    "expected": variant.get("expected"),
                    "contract_status": variant.get("status"),
                    "runtime_evidence_status": ("present_baseline" if present else "missing"),
                }
            )
        missing_count = sum(
            1 for variant in runtime_variants if variant["runtime_evidence_status"] == "missing"
        )
        if missing_count:
            findings.append(
                _finding(
                    pdd_id="PDD-055",
                    code="pass2_wave33_metamorphic_variant_bundle_missing",
                    severity="PDC-CRITICAL",
                    title="Wave 33 lacks paired metamorphic runtime variants",
                    message=(
                        f"{scenario_id} has {missing_count} missing runtime "
                        "variant bundles for paraphrase, language, jurisdiction, "
                        "time, data-family, or method perturbations."
                    ),
                    owner="team-runtime-quality",
                    missing_input="paired runtime bundles for metamorphic variants",
                    upstream_cause=(
                        "Wave 33 generated only the baseline research-profile case evidence."
                    ),
                    downstream_impact=(
                        "A serious closeout would still be based on a single happy-path scenario."
                    ),
                    scenario_id=scenario_id,
                    refs=[_rel(wave33_dir, repo_root)],
                )
            )
        irrelevant = _control_by_id(negative, "irrelevant_data")
        data_removal_present = False
        if not data_removal_present:
            missing_data_removal += 1
            findings.append(
                _finding(
                    pdd_id="PDD-055",
                    code="pass2_wave33_metamorphic_data_removal_probe_missing",
                    severity="PDC-CRITICAL",
                    title="Wave 33 lacks irrelevant-data/data-removal runtime probe",
                    message=(
                        "The scenario contract declares an irrelevant-data control, "
                        "but Wave 33 has no paired runtime probe for it."
                    ),
                    owner="team-runtime-quality",
                    missing_input="runtime irrelevant-data or data-removal perturbation",
                    upstream_cause="Wave 33 did not execute perturbation lanes.",
                    downstream_impact=(
                        "The diagnostics cannot prove that removing relevant data "
                        "or adding irrelevant evidence changes readiness correctly."
                    ),
                    scenario_id=scenario_id,
                    refs=[_rel(wave33_dir, repo_root)],
                )
            )
        scenarios.append(
            {
                "scenario_id": scenario_id,
                "contract_metamorphic_report": metamorphic,
                "contract_negative_control_report": negative,
                "irrelevant_data_contract_control": irrelevant,
                "runtime_variants": runtime_variants,
                "missing_runtime_variant_count": missing_count,
                "data_removal_runtime_status": ("present" if data_removal_present else "missing"),
            }
        )
    missing_variants = total_variants - present_variants
    acceptance = (
        "blocked"
        if input_issues
        else "failed"
        if missing_variants or missing_data_removal
        else "satisfied"
    )
    return _pdd_report(
        pdd_id="PDD-055",
        acceptance_gate_status=acceptance,
        findings=findings,
        summary={
            "scenario_count": len(scenarios),
            "contract_metamorphic_pass_count": sum(
                1 for row in scenarios if row["contract_metamorphic_report"].get("status") == "pass"
            ),
            "total_variant_count": total_variants,
            "runtime_variant_count": present_variants,
            "missing_runtime_variant_count": missing_variants,
            "missing_data_removal_probe_count": missing_data_removal,
        },
        details={"scenarios": scenarios},
        observed=observed,
    )


def _build_pdd056_report(
    *,
    contracts: Mapping[str, Mapping[str, Any]],
    observed: Mapping[str, Any],
    input_issues: Sequence[Mapping[str, Any]],
    wave33_dir: Path,
    repo_root: Path,
    bindings: Pass2DiagnosticBindings,
) -> dict[str, Any]:
    _finding = bindings.finding
    _pdd_report = bindings.pdd_report
    _rel = bindings.rel
    _strings = bindings.strings
    build_metamorphic_prompt_report = bindings.build_metamorphic_prompt_report
    observed_scenarios = set(_strings(observed.get("observed_scenario_ids")))
    scenarios: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = list(input_issues)
    runtime_pair_count = 0
    transliteration_variant_count = 0
    mixed_language_variant_count = 0

    for scenario_id, contract in contracts.items():
        metamorphic = build_metamorphic_prompt_report(dict(contract))
        variants = [
            variant for variant in metamorphic.get("variants") or [] if isinstance(variant, dict)
        ]
        en_equivalent = [
            variant
            for variant in variants
            if variant.get("locale") == "en" and variant.get("expected") == "pass"
        ]
        uk_equivalent = [
            variant
            for variant in variants
            if variant.get("locale") == "uk" and variant.get("expected") == "pass"
        ]
        transliteration = [
            variant
            for variant in variants
            if "translit" in str(variant.get("variant_id") or "").casefold()
            or "latn" in str(variant.get("locale") or "").casefold()
        ]
        mixed_language = [
            variant
            for variant in variants
            if "mixed" in str(variant.get("variant_id") or "").casefold()
        ]
        transliteration_variant_count += len(transliteration)
        mixed_language_variant_count += len(mixed_language)
        runtime_pair_present = scenario_id in observed_scenarios and bool(
            en_equivalent and uk_equivalent
        )
        runtime_pair_count += 1 if runtime_pair_present else 0

        if not runtime_pair_present:
            findings.append(
                _finding(
                    pdd_id="PDD-056",
                    code="pass2_wave33_multilingual_runtime_pair_missing",
                    severity="PDC-HIGH",
                    title="Wave 33 lacks paired English/Ukrainian runtime bundles",
                    message=(
                        "No paired Wave 33 runtime evidence proves that English "
                        f"and Ukrainian requests bind equivalently for {scenario_id}."
                    ),
                    owner="team-policy-semantics",
                    missing_input="paired English and Ukrainian runtime bundles",
                    upstream_cause="Wave 33 executed only one baseline prompt lane.",
                    downstream_impact=(
                        "Multilingual production support remains unproved for "
                        "concept, norm, dataset, method, grounding, and claim bindings."
                    ),
                    scenario_id=scenario_id,
                    refs=[_rel(wave33_dir, repo_root)],
                )
            )
        if not transliteration:
            findings.append(
                _finding(
                    pdd_id="PDD-056",
                    code="pass2_transliteration_variant_contract_missing",
                    severity="PDC-HIGH",
                    title="No transliteration variant is declared for runtime probing",
                    message=(
                        f"{scenario_id} has English and Ukrainian variants, but no "
                        "transliterated Ukrainian variant."
                    ),
                    owner="team-policy-semantics",
                    missing_input="Ukrainian transliteration prompt variant",
                    upstream_cause=(
                        "The Pass 2 scenario contract does not yet encode a transliteration pair."
                    ),
                    downstream_impact=(
                        "PDD-056 cannot prove equivalence for transliterated user requests."
                    ),
                    scenario_id=scenario_id,
                    refs=["tools/ops_runners/runtime/golden_quality_scenarios.json"],
                )
            )
        if not mixed_language:
            findings.append(
                _finding(
                    pdd_id="PDD-056",
                    code="pass2_mixed_language_variant_contract_missing",
                    severity="PDC-MEDIUM",
                    title="No mixed-language variant is declared for runtime probing",
                    message=(f"{scenario_id} has no mixed Ukrainian/English prompt variant."),
                    owner="team-policy-semantics",
                    missing_input="mixed-language prompt variant",
                    upstream_cause=(
                        "The Pass 2 scenario contract covers en/uk but not mixed-language input."
                    ),
                    downstream_impact=("PDD-056 cannot detect mixed-language binding divergence."),
                    scenario_id=scenario_id,
                    refs=["tools/ops_runners/runtime/golden_quality_scenarios.json"],
                )
            )
        scenarios.append(
            {
                "scenario_id": scenario_id,
                "contract_metamorphic_report": metamorphic,
                "english_equivalent_variants": en_equivalent,
                "ukrainian_equivalent_variants": uk_equivalent,
                "transliteration_variants": transliteration,
                "mixed_language_variants": mixed_language,
                "runtime_pair_status": ("present" if runtime_pair_present else "missing"),
            }
        )

    findings.append(
        _finding(
            pdd_id="PDD-056",
            code="pass2_wave33_hardcoded_language_path_audit_missing",
            severity="PDC-HIGH",
            title="Wave 33 has no hardcoded-language-path runtime audit",
            message=(
                "Wave 33 evidence does not contain a runtime audit proving that "
                "language, country, or topic detection avoids hardcoded paths."
            ),
            owner="team-policy-semantics",
            missing_input="hardcoded-language-path detection report",
            upstream_cause="Phase 33 produced real-domain baseline evidence only.",
            downstream_impact=(
                "Equivalent multilingual requests may silently bind to different "
                "concepts, norms, datasets, methods, or claims."
            ),
            refs=[_rel(wave33_dir, repo_root)],
        )
    )
    acceptance = (
        "blocked"
        if input_issues
        else "failed"
        if len(scenarios) != runtime_pair_count
        or transliteration_variant_count == 0
        or mixed_language_variant_count == 0
        else "satisfied"
    )
    return _pdd_report(
        pdd_id="PDD-056",
        acceptance_gate_status=acceptance,
        findings=findings,
        summary={
            "scenario_count": len(scenarios),
            "runtime_multilingual_pair_count": runtime_pair_count,
            "missing_runtime_multilingual_pair_count": len(scenarios) - runtime_pair_count,
            "transliteration_variant_count": transliteration_variant_count,
            "mixed_language_variant_count": mixed_language_variant_count,
            "contract_ukrainian_variant_count": sum(
                len(row["ukrainian_equivalent_variants"]) for row in scenarios
            ),
        },
        details={"scenarios": scenarios},
        observed=observed,
    )
