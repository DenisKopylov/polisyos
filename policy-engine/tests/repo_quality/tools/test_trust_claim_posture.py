"""Repository-semantic tests for DS11 trust-claim posture tooling."""

from __future__ import annotations

import importlib
import json
import shutil
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from polisyos.runtime.quality.claim_registry import build_runtime_claim_registry

REPO_ROOT = Path(__file__).resolve().parents[3]
FROZEN_AS_OF = date(2026, 8, 26)
IDENTITY_PATH = "docs/system-design-decisions/policyos-identity-and-custody-boundary.md"
A11Y_PATH = "docs/compliance/A11Y_AUDIT_2026Q2.md"
PAGE_RECEIPT_PATH = "docs/plans/active/atlas-slices/receipts/ds11-page-a11y-base"
GENERATED_MANIFEST_PATH = "architecture/generated_artifacts.toml"


def _owner(module_name: str) -> Any:
    """Load one required C01 owner or fail at the intended missing seam."""
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name or (
            exc.name is not None and module_name.startswith(f"{exc.name}.")
        ):
            pytest.fail(f"C01 owner module is absent: {module_name}")
        raise


def _sources() -> Any:
    return _owner("tools.quality.validation.trust_claim_posture_sources")


def _checker() -> Any:
    return _owner("tools.quality.validation.check_trust_claim_posture")


def _copy_compiler_inputs(destination: Path, *, full_source: bool = False) -> None:
    source_root = REPO_ROOT / "src"
    target_source = destination / "src"
    if full_source:
        shutil.copytree(source_root, target_source)
    else:
        probe = target_source / "polisyos/example.py"
        probe.parent.mkdir(parents=True)
        probe.write_text(
            '"""Scratch posture source."""\n\n'
            "class ExampleClaim:\n"
            '    authoritative_for = ("example_claim",)\n'
            '    may_not_use_for = ("publication_authority",)\n',
            encoding="utf-8",
        )
    identity = destination / IDENTITY_PATH
    identity.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO_ROOT / IDENTITY_PATH, identity)


def _valid_runtime_registry(binding_ref: str) -> dict[str, object]:
    """Build a real full-axis runtime registry binding for CC09 probes."""
    return build_runtime_claim_registry(
        claims=[
            {
                "claim_id": "runtime-final-claim",
                "claim_family": "recommendation",
                "major": True,
                "text": "Bind a runtime-only final claim to its complete evidence axes.",
                "scenario_requirement_refs": ["scenario.req.credit_support"],
                "data_refs": ["source.msme_panel"],
                "selected_norm_refs": ["norm.ua.credit_guarantee"],
                "rejected_norm_refs": ["norm.ua.unrelated"],
                "method_output_refs": ["foundry.did.msme_survival"],
                "portfolio_refs": ["portfolio.rec_credit_guarantee"],
                "argument_refs": ["argument.rec_credit_guarantee"],
                "warrant_refs": ["warrant.rec_credit_guarantee"],
                "rebuttal_refs": ["rebuttal.rec_credit_guarantee"],
                "counter_evidence_refs": ["counter.rec_credit_guarantee"],
                "limitation_refs": ["limitation.rec_credit_guarantee"],
                "accepted_deficit_refs": [binding_ref],
                "assumption_gate_refs": ["assumption-gate.runtime-final-claim"],
                "independence_refs": ["independence.runtime-final-claim"],
                "synthesis_refs": ["synthesis.runtime-final-claim"],
                "scholar_deficit_refs": ["scholar-deficit.runtime-final-claim"],
                "objective_tradeoff_refs": ["objective-tradeoff.runtime-final-claim"],
                "uncertainty_refs": ["uncertainty.runtime-final-claim"],
                "numerical_semantics_refs": ["num-semantics.runtime-final-claim"],
                "monitoring_refs": ["monitoring.runtime-final-claim"],
                "specification_curve_refs": ["spec-curve.runtime-final-claim"],
                "claim_ref": "sha256:" + "d" * 64,
                "runtime_event_ref": "event://runtime_claim_registry/runtime-final-claim",
            }
        ],
        run_id="ds11-cc09-probe",
    )


def _write_accessibility_document(repo: Path) -> bytes:
    body = (
        b"# Accessibility Audit 2026 Q2\n"
        b"- Audit type: Internal pre-audit evidence packet and external audit handoff\n"
        b"- Audit status: Internal pre-audit complete\n"
        b"- Internal completion date: 2026-04-22\n"
        b"- External audit status: Scheduled for Q2 2026, vendor countersign pending\n"
        b"- Product under review: `@polisyos/runtime-dashboard@0.1.0`\n"
        b"- Evaluation scope: `policy-engine/apps/runtime-dashboard`\n"
        b"- Assessment owner: Denis Kopylov\n\n"
        b"It does not replace the planned third-party countersign.\n"
    )
    body_digest = sha256(body).hexdigest()
    selectors = {
        "audit_type": (
            "Internal pre-audit evidence packet and external audit handoff",
            "- Audit type: Internal pre-audit evidence packet and external audit handoff",
        ),
        "internal_pre_audit_status": (
            "Internal pre-audit complete",
            "- Audit status: Internal pre-audit complete",
        ),
        "source_as_of": ("2026-04-22", "- Internal completion date: 2026-04-22"),
        "external_countersign_status": (
            "Scheduled for Q2 2026, vendor countersign pending",
            "- External audit status: Scheduled for Q2 2026, vendor countersign pending",
        ),
        "product_under_review": (
            "@polisyos/runtime-dashboard@0.1.0",
            "- Product under review: `@polisyos/runtime-dashboard@0.1.0`",
        ),
        "evaluation_scope": (
            "policy-engine/apps/runtime-dashboard",
            "- Evaluation scope: `policy-engine/apps/runtime-dashboard`",
        ),
        "assessment_owner": ("Denis Kopylov", "- Assessment owner: Denis Kopylov"),
    }
    binding_lines = "\n".join(
        f"    {key}:\n      value: {json.dumps(value)}\n"
        f"      exact_text: {json.dumps(exact_text)}\n      occurrence: 1"
        for key, (value, exact_text) in selectors.items()
    )
    frontmatter = (
        "---\n"
        "ds11_projection_index:\n"
        "  schema_version: policyos.trust.document_projection_index.v1\n"
        f"  body_sha256: {body_digest}\n"
        "  bindings:\n"
        f"{binding_lines}\n"
        "  authoritative_for:\n"
        "    - purpose: historical_internal_accessibility_pre_audit\n"
        "      basis: [audit_type, internal_pre_audit_status, source_as_of]\n"
        "  may_not_use_for:\n"
        "    - purpose: current_accessibility_conformance\n"
        "      basis: [source_as_of]\n"
        "    - purpose: external_accessibility_certification\n"
        "      basis: [external_countersign_status]\n"
        "---\n"
    ).encode()
    path = repo / A11Y_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(frontmatter + body)
    return body


def _copy_page_receipt(repo: Path) -> Path:
    destination = repo / PAGE_RECEIPT_PATH
    shutil.copytree(REPO_ROOT / PAGE_RECEIPT_PATH, destination)
    return destination


def _write_generated_manifest(repo: Path) -> Path:
    path = repo / GENERATED_MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """[generated_artifacts]
version = 1

[[family]]
id = "trust-claim-posture-register"
label = "Trust claim posture register"
owner = "team-architecture"
approval_owner = "team-architecture"
lifecycle = "generated_committed"
generator = "DS11 trust claim posture compiler write mode"
verifier = "DS11 trust claim posture checker and architecture guardrails"
promotion_target = "static trust posture artifact consumed by the public /trust surface"
stale_output_behavior = "fail"
source_of_truth = "tracked posture sources"
outputs = ["apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json"]
regenerate_commands = ["uv run python tools/quality/validation/check_trust_claim_posture.py --repo-root . --write"]
commit_policy = "committed"
freshness_rule = "Regenerate on source change."
drift_gate = "automated"
workflow = "tools/quality/validation/check_trust_claim_posture.py"
check_cwd = "."
check_command = ["uv", "run", "python", "tools/quality/validation/check_trust_claim_posture.py", "--repo-root", ".", "--check"]
default_freshness_check = true
output_probe_command = ["uv", "run", "python", "tools/quality/validation/check_trust_claim_posture.py", "--repo-root", ".", "--write", "--output-root", "{output_root}"]
""",
        encoding="utf-8",
    )
    return path


def test_source_partition_matches_ast_and_tokenize_file_for_file() -> None:
    """Catch incomplete walks, count-only agreement, or hidden derivation disagreement."""
    sources = _sources()
    checker = _checker()
    ast_result = sources.derive_ast_sources(REPO_ROOT)
    token_result = checker.derive_token_sources(REPO_ROOT)
    reconciled = checker.reconcile_source_derivations(ast_result, token_result)

    assert ast_result.receipt.scanned_python_count == 2580
    assert token_result.receipt.scanned_python_count == 2580
    assert ast_result.receipt.raw_candidate_count == 105
    assert token_result.receipt.raw_candidate_count == 105
    assert (
        ast_result.receipt.role_counts
        == token_result.receipt.role_counts
        == {
            "declares_only": 66,
            "carries_only": 5,
            "consumes_only": 5,
            "declares_and_consumes": 28,
            "substring_collision": 1,
            "ambiguous": 0,
        }
    )
    assert ast_result.receipt.exact_field_file_count == 104
    assert ast_result.receipt.declaring_file_count == 94
    assert ast_result.receipt.consuming_file_count == 33
    assert not reconciled.disagreements
    posture = next(row for row in reconciled.rows if row.path.endswith("claims/posture.py"))
    assert posture.role == "declares_and_consumes"
    assert posture.declaration_coordinates[0].line > 0
    entry_roles = dict(ast_result.receipt.role_counts)
    entry_roles["declares_and_consumes"] -= 1
    assert entry_roles == {
        "declares_only": 66,
        "carries_only": 5,
        "consumes_only": 5,
        "declares_and_consumes": 27,
        "substring_collision": 1,
        "ambiguous": 0,
    }
    assert ast_result.receipt.scanned_python_count - 1 == 2579
    assert ast_result.receipt.raw_candidate_count - 1 == 104
    assert ast_result.receipt.exact_field_file_count - 1 == 103
    collision = next(row for row in reconciled.rows if row.role == "substring_collision")
    assert collision.path.endswith("data_forge/domains/academic/batch/best_snapshot.py")
    assert collision.issue_codes == ("DS11-SOURCE-COLLISION",)
    witness = next(row for row in token_result.rows if row.role == "declares_only")
    mutated_rows = tuple(
        row.model_copy(update={"role": "carries_only"}) if row.path == witness.path else row
        for row in token_result.rows
    )
    disagreement = checker.reconcile_source_derivations(
        ast_result,
        token_result.model_copy(update={"rows": mutated_rows}),
    )
    ambiguous = next(row for row in disagreement.rows if row.path == witness.path)
    assert disagreement.disagreements == (witness.path,)
    assert ambiguous.role == "ambiguous"
    assert ambiguous.resolution == "ambiguous"
    assert ambiguous.issue_codes == ("DS11-SOURCE-DERIVATION-DISAGREEMENT",)
    assert (
        min(
            coordinate.line
            for coordinate in (
                *ambiguous.declaration_coordinates,
                *ambiguous.carrier_coordinates,
                *ambiguous.consumer_coordinates,
            )
        )
        > 0
    )


def test_literal_censuses_reconcile_for_both_complete_walks() -> None:
    """Catch a compiler mutation that drops wrappers, empty sites, or denied purposes."""
    ast_receipt = _sources().derive_ast_sources(REPO_ROOT).receipt
    token_receipt = _checker().derive_token_sources(REPO_ROOT).receipt

    for receipt in (ast_receipt, token_receipt):
        assert (
            receipt.direct_literal_site_count,
            receipt.direct_literal_file_count,
            receipt.direct_literal_subject_count,
            receipt.direct_empty_site_count,
        ) == (35, 13, 21, 5)
        assert (
            receipt.wrapper_literal_site_count,
            receipt.wrapper_literal_file_count,
            receipt.wrapper_literal_subject_count,
        ) == (59, 24, 28)
        assert (
            receipt.may_not_use_for_raw_file_count,
            receipt.may_not_use_for_literal_site_count,
            receipt.may_not_use_for_literal_file_count,
            receipt.may_not_use_for_literal_subject_count,
        ) == (117, 34, 22, 44)
        assert receipt.may_not_use_for_raw_file_count - 1 == 116


def test_all_declaration_forms_survive_and_ambiguity_never_invents_subject(
    tmp_path: Path,
) -> None:
    """Catch parameter promotion, declaration-site loss, or guessed ambiguity subjects."""
    repo = tmp_path / "repo"
    _copy_compiler_inputs(repo)
    probe = repo / "src/polisyos/declaration_forms.py"
    probe.write_text(
        "def carrier(authoritative_for=('parameter_default',)):\n"
        "    return authoritative_for\n\n"
        "class Producer:\n"
        "    pass\n\n"
        "keyword = Producer(authoritative_for=('keyword_claim',))\n"
        "mapping = {'authoritative_for': ('dict_claim',)}\n"
        "dynamic_value = tuple(value for value in ('dynamic_claim',))\n"
        "dynamic = Producer(authoritative_for=dynamic_value)\n",
        encoding="utf-8",
    )
    sources = _sources()
    checker = _checker()
    ast_result = sources.derive_ast_sources(repo)
    token_result = checker.derive_token_sources(repo)
    reconciled = checker.reconcile_source_derivations(ast_result, token_result)
    assert not reconciled.disagreements
    row = next(item for item in reconciled.rows if item.path.endswith("declaration_forms.py"))
    assert any(
        coordinate.line == 1 and coordinate.use_kind == "carrier"
        for coordinate in row.carrier_coordinates
    )
    sites = {
        (site.declaration_form, site.coordinate.line): (site.values, site.resolution)
        for site in row.authoritative_sites
    }
    assert sites[("keyword", 7)] == (("keyword_claim",), "resolved")
    assert sites[("dict_key", 8)] == (("dict_claim",), "resolved")
    assert sites[("keyword", 10)] == ((), "runtime_bound")
    assert all(site.coordinate.line != 1 for site in row.authoritative_sites)

    token_row = next(item for item in token_result.rows if item.path == row.path)
    target = next(site for site in token_row.authoritative_sites if site.coordinate.line == 7)
    changed_site = target.model_copy(update={"values": ("different_claim",)})
    changed_row = token_row.model_copy(
        update={
            "authoritative_sites": tuple(
                changed_site if site == target else site for site in token_row.authoritative_sites
            )
        }
    )
    changed_token = token_result.model_copy(
        update={
            "rows": tuple(
                changed_row if item.path == row.path else item for item in token_result.rows
            )
        }
    )
    ambiguous = checker.reconcile_source_derivations(ast_result, changed_token)
    ambiguous_row = next(item for item in ambiguous.rows if item.path == row.path)
    assert ambiguous_row.role == "ambiguous"
    bindings = sources.compile_source_claim_bindings(ambiguous, package_owners={})
    affected = [item for item in bindings if item.coordinate.path == row.path]
    assert affected
    assert all(item.subject is None for item in affected)
    assert all(item.resolution == "ambiguous" for item in affected)


def test_new_authority_producer_grows_register_without_register_edit(
    tmp_path: Path,
) -> None:
    """Catch subject-map coupling or a walk that ignores a new real Python producer."""
    scratch = tmp_path / "repo"
    _copy_compiler_inputs(scratch, full_source=True)
    sources = _sources()
    checker = _checker()
    before_ast = sources.derive_ast_sources(scratch)
    before_token = checker.derive_token_sources(scratch)
    probe = scratch / "src/polisyos/scientist/evidence/claims/ds11_growth_probe.py"
    probe.write_text(
        '"""Scratch-only free-growth producer."""\n\n'
        "class DS11GrowthProbe:\n"
        '    authoritative_for = ("ds11_free_growth_probe",)\n'
        '    may_not_use_for = ("publication_authority",)\n',
        encoding="utf-8",
    )
    after_ast = sources.derive_ast_sources(scratch)
    after_token = checker.derive_token_sources(scratch)
    reconciled = checker.reconcile_source_derivations(after_ast, after_token)
    bindings = sources.compile_source_claim_bindings(reconciled, package_owners={})

    for before, after in (
        (before_ast.receipt, after_ast.receipt),
        (before_token.receipt, after_token.receipt),
    ):
        assert after.scanned_python_count == before.scanned_python_count + 1
        assert after.raw_candidate_count == before.raw_candidate_count + 1
        assert after.exact_field_file_count == before.exact_field_file_count + 1
        assert after.declaring_file_count == before.declaring_file_count + 1
        assert after.direct_literal_site_count == before.direct_literal_site_count + 1
        assert after.direct_literal_subject_count == before.direct_literal_subject_count + 1
    assert not reconciled.disagreements
    growth = [binding for binding in bindings if binding.subject == "ds11_free_growth_probe"]
    assert len(growth) == 1
    assert growth[0].coordinate.path.endswith("ds11_growth_probe.py")
    assert growth[0].coordinate.symbol == "DS11GrowthProbe"
    assert growth[0].may_not_use_for == ("publication_authority",)
    assert growth[0].content_digest == "sha256:" + sha256(probe.read_bytes()).hexdigest()
    assert growth[0].source_state == "not_established"


def test_identity_parser_derives_seven_anti_roles_including_crm() -> None:
    """Catch a parser mutation that samples or hand-enumerates the anti-role paragraph."""
    boundary = _checker().derive_identity_boundary(REPO_ROOT)
    assert tuple(item.display_label for item in boundary.anti_roles) == (
        "administrator",
        "executor",
        "case-management system",
        "court",
        "notification channel",
        "payment system",
        "CRM",
    )
    assert boundary.paragraph_start_line <= 88 <= boundary.paragraph_end_line


def test_accessibility_frontmatter_is_strictly_bound_to_complete_body(tmp_path: Path) -> None:
    """Catch frontmatter surviving removal or duplication of its cited body fact."""
    repo = tmp_path / "repo"
    body = _write_accessibility_document(repo)
    checker = _checker()
    binding = checker.derive_accessibility_document(repo)
    assert binding.body_digest == "sha256:" + sha256(body).hexdigest()
    assert binding.source_as_of == date(2026, 4, 22)
    assert all(item.establishment_class == "recomputed" for item in binding.bindings)
    assert all(item.byte_end > item.byte_start for item in binding.bindings)
    path = repo / A11Y_PATH
    path.write_bytes(path.read_bytes().replace(b"Internal pre-audit complete", b"Removed fact"))
    with pytest.raises(ValueError, match=r"body|selector|digest"):
        checker.derive_accessibility_document(repo)


def test_page_receipt_recomputes_all_five_files_and_rejects_authored_drift(
    tmp_path: Path,
) -> None:
    """Catch trust in authored receipt counts, identities, digests, or replay claims."""
    repo = tmp_path / "repo"
    receipt_root = _copy_page_receipt(repo)
    checker = _checker()
    receipt = checker.derive_page_a11y_receipt(repo)
    assert (receipt.collected, receipt.passed, receipt.failed, receipt.skipped) == (
        24,
        20,
        4,
        0,
    )
    assert len(receipt.admitted_sources) == 5
    assert receipt.replay_establishment == "not_established"
    assert {item.issue_signature for item in receipt.failures} == {
        "axe:dlitem",
        "accessible_name:Open run",
        "accessible_name:Export JSON",
    }
    normalized_path = receipt_root / "receipt.json"
    normalized = json.loads(normalized_path.read_text())
    normalized["result"]["passed"] = 21
    normalized_path.write_text(json.dumps(normalized), encoding="utf-8")
    with pytest.raises(ValueError, match=r"receipt|passed|recompute"):
        checker.derive_page_a11y_receipt(repo)


def test_generated_family_probe_and_narrow_reference_writer_are_scratch_bounded(
    tmp_path: Path,
) -> None:
    """Catch incomplete C02 seams, output escape, or broad reference regeneration."""
    repo = tmp_path / "repo"
    _copy_compiler_inputs(repo)
    manifest = _write_generated_manifest(repo)
    checker = _checker()
    family = checker.validate_generated_family(repo)
    assert family.default_freshness_check is True
    assert family.stale_output_behavior == "fail"
    assert family.outputs == ("apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json",)
    assert sum("{output_root}" in item for item in family.output_probe_command) == 1

    output_root = tmp_path / "probe"
    observed = checker.run_generated_family_output_probe(repo, output_root=output_root)
    assert observed == family.outputs
    reference_root = tmp_path / "reference"
    written = checker.write_generated_reference(repo, output_root=reference_root)
    assert written == reference_root / "docs/reference/generated-artifacts.md"
    guardrails = _owner("tools.devx.architecture.guardrails")
    expected = guardrails.render_generated_artifacts_markdown(
        guardrails._parse_generated_artifacts(manifest)
    ).encode()
    assert written.read_bytes() == expected
    assert {
        path.relative_to(reference_root).as_posix()
        for path in reference_root.rglob("*")
        if path.is_file()
    } == {"docs/reference/generated-artifacts.md"}


def test_c02_cli_flags_default_date_and_repo_root_writer_work_in_scratch(
    tmp_path: Path,
) -> None:
    """Catch required-date drift or missing combined writer/reference CLI flags."""
    repo = tmp_path / "repo"
    _copy_compiler_inputs(repo)
    _write_generated_manifest(repo)
    receipt_root = _copy_page_receipt(repo)
    checker = _checker()
    assert checker.main(["--repo-root", str(repo), "--check-a11y-receipt"]) == 0
    assert (
        checker.main(
            [
                "--repo-root",
                str(repo),
                "--write",
                "--write-generated-reference",
            ]
        )
        == 0
    )
    assert (repo / "apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json").is_file()
    assert (repo / "docs/reference/generated-artifacts.md").is_file()
    assert receipt_root.is_dir()


def test_unbound_manages_your_cases_copy_fails_identity_check() -> None:
    """Catch a copy mutation that accepts capability prose outside the sole renderer."""
    assert _checker().validate_claim_copy("manages your cases", source_row=None) == (
        "DS11-IDENTITY-COPY-UNBOUND",
    )
    assert _checker().validate_claim_copy("manages your cases", source_row=object()) == (
        "DS11-IDENTITY-COPY-UNBOUND",
    )


def test_internal_a11y_evidence_cannot_mint_external_certification() -> None:
    """Catch promotion of internal historical evidence to current certification."""
    result = _checker().evaluate_accessibility_evidence(
        evidence_kind="internal_pre_audit",
        requested_purpose="external_accessibility_certification",
        source_as_of=FROZEN_AS_OF,
        countersign_ref=None,
    )
    assert result.state == "blocked"
    assert "DS11-A11Y-CERTIFICATION-NOT-EARNED" in result.issue_codes
    novel = _checker().evaluate_accessibility_evidence(
        evidence_kind="self_attested_unknown",
        requested_purpose="external_accessibility_certification",
        source_as_of=date(2000, 1, 1),
        countersign_ref=None,
        register_as_of=FROZEN_AS_OF,
    )
    assert novel.state == "blocked"
    assert {
        "DS11-A11Y-EVIDENCE-KIND-UNKNOWN",
        "DS11-A11Y-EVIDENCE-STALE",
        "DS11-A11Y-CERTIFICATION-NOT-EARNED",
    } <= set(novel.issue_codes)


def test_metadata_without_independent_source_basis_cannot_support() -> None:
    """Catch authored P37 metadata being treated as independent establishment."""
    posture = _owner("polisyos.scientist.evidence.claims.posture")
    predicates = tuple(
        posture.SupportPredicate(
            kind=kind,
            satisfied=True,
            establishment_class="institutionally_supplied",
            evidence_refs=("metadata:self-attested",),
            issue_code=None,
        )
        for kind in posture.REQUIRED_SUPPORT_PREDICATES
    )
    assert (
        posture.compose_effective_state(("supported",), support_predicates=predicates) == "blocked"
    )


def test_declared_scope_assumption_is_limitation_not_support() -> None:
    """Catch a scope mutation that promotes an unadjudicated declaration."""
    result = _checker().evaluate_scope_assumption(
        scope_assumption="jurisdiction_neutral", adjudication_ref=None
    )
    assert result.state == "blocked"
    assert result.establishment_class == "not_established"
    assert result.limitations == ("Declared scope assumption: jurisdiction_neutral",)


def test_generator_is_byte_deterministic_and_scratch_bounded(
    tmp_path: Path,
) -> None:
    """Catch nondeterministic bytes, arbitrary filenames, or output-root escape."""
    repo = tmp_path / "repo"
    _copy_compiler_inputs(repo)
    checker = _checker()
    first, first_bytes = checker.compile_claim_posture_register(repo, register_as_of=FROZEN_AS_OF)
    second, second_bytes = checker.compile_claim_posture_register(repo, register_as_of=FROZEN_AS_OF)
    assert first == second
    assert first_bytes == second_bytes

    output_root = tmp_path / "output"
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()}
    written = checker.write_claim_posture_register(first, output_root=output_root)
    after = {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()}
    assert (
        written == output_root / "apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json"
    )
    assert after - before == {
        Path("output/apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json")
    }
    assert written.read_bytes() == first_bytes


def test_runtime_producer_evidence_binding_cannot_enter_posture_compiler(
    tmp_path: Path,
) -> None:
    """Catch admission of valid per-run producer evidence into posture rows or bytes."""
    repo = tmp_path / "repo"
    _copy_compiler_inputs(repo)
    checker = _checker()
    baseline_register, baseline_bytes = checker.compile_claim_posture_register(
        repo, register_as_of=FROZEN_AS_OF
    )
    runtime_dir = repo / "ops/migrations/runtime_state/run_records"
    runtime_dir.mkdir(parents=True)
    first = _valid_runtime_registry("deficit.first-runtime-binding")
    assert first["status"] == "pass"
    (runtime_dir / "claim-registry.json").write_text(json.dumps(first), encoding="utf-8")
    first_register, first_bytes = checker.compile_claim_posture_register(
        repo, register_as_of=FROZEN_AS_OF
    )
    second = _valid_runtime_registry("deficit.second-runtime-binding")
    assert second["status"] == "pass"
    (runtime_dir / "claim-registry.json").write_text(json.dumps(second), encoding="utf-8")
    second_register, second_bytes = checker.compile_claim_posture_register(
        repo, register_as_of=FROZEN_AS_OF
    )
    assert baseline_register == first_register == second_register
    assert baseline_bytes == first_bytes == second_bytes
    assert b"runtime-final-claim" not in second_bytes
    assert b"deficit.second-runtime-binding" not in second_bytes


def test_runtime_registry_payload_is_rejected_as_source_adapter() -> None:
    """Catch a generic-adapter mutation that accepts the distinct runtime schema."""
    runtime_registry = _valid_runtime_registry("deficit.runtime-only")
    assert runtime_registry["status"] == "pass"
    with pytest.raises(ValueError, match=r"RuntimeClaimRegistry|per-run|unsupported"):
        _sources().compile_source_adapter(runtime_registry)
