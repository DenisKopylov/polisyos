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
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Grow through the canonical writer while every governed source stays unchanged."""
    scratch = tmp_path / "repo"
    _copy_compiler_inputs(scratch, full_source=True)
    sources = _sources()
    checker = _checker()
    baseline_register, baseline_bytes = checker.compile_claim_posture_register(
        scratch, register_as_of=FROZEN_AS_OF
    )
    before_ast = sources.derive_ast_sources(scratch)
    before_token = checker.derive_token_sources(scratch)
    dashboard_sources = tuple(
        sorted(
            path
            for path in (REPO_ROOT / "apps/runtime-dashboard/src").rglob("*")
            if path.is_file()
            and path.suffix in {".ts", ".tsx"}
            and not path.name.endswith(".d.ts")
            and ".stories." not in path.name
            and not any(marker in path.name for marker in (".test.", ".spec.", ".a11y.test."))
            and not ("src/test" in path.as_posix() and path.suffix == ".tsx")
        )
    )
    assert len(dashboard_sources) == 625
    governed_before = {
        path.relative_to(REPO_ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
        for path in dashboard_sources
    }
    governed_before.update(
        {
            path: sha256((REPO_ROOT / path).read_bytes()).hexdigest()
            for path in (
                "architecture/imports/policy.toml",
                "apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json",
                "apps/runtime-dashboard/src/app/routes/routes.tsx",
                "apps/runtime-dashboard/src/shared/i18n/locales/en.json",
                "apps/runtime-dashboard/src/shared/i18n/locales/uk.json",
            )
        }
    )
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

    blocked_register, _ = checker.compile_claim_posture_register(
        scratch, register_as_of=FROZEN_AS_OF
    )
    blocked_row = next(
        row for row in blocked_register.claims if row.subject == "ds11_free_growth_probe"
    )
    assert blocked_row.effective_state == "blocked"

    probe.write_text(
        probe.read_text(encoding="utf-8")
        + "    trust_claim_posture = {\n"
        + '        "schema_version": "policyos.trust.producer_posture.v1",\n'
        + '        "subject": "ds11_free_growth_probe",\n'
        + '        "source_state": "planned",\n'
        + '        "owner": "team-scientist",\n'
        + '        "closure_signal": "uv run pytest tests/example/test_growth.py -q",\n'
        + "    }\n",
        encoding="utf-8",
    )
    planned_register, planned_bytes = checker.compile_claim_posture_register(
        scratch, register_as_of=FROZEN_AS_OF
    )
    planned_row = next(
        row for row in planned_register.claims if row.subject == "ds11_free_growth_probe"
    )
    assert planned_row.effective_state == "planned"
    assert len(planned_register.admitted_sources) == len(baseline_register.admitted_sources) + 1
    assert len(planned_register.claims) == len(baseline_register.claims) + 1
    assert planned_row.source_bindings[0].owner.owner == "team-scientist"

    output_root = tmp_path / "output"
    assert (
        checker.main(
            [
                "--repo-root",
                str(scratch),
                "--output-root",
                str(output_root),
                "--write",
                "--json",
            ]
        )
        == 0
    )
    cli_report = json.loads(capsys.readouterr().out)
    assert cli_report["declared_outputs"] == [
        "apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json"
    ]
    assert cli_report["write_set"] == [
        "apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json"
    ]
    written = output_root / "apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json"
    assert written.read_bytes() == planned_bytes
    assert {
        path.relative_to(output_root).as_posix()
        for path in output_root.rglob("*")
        if path.is_file()
    } == {"apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json"}
    assert (
        REPO_ROOT / "apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json"
    ).read_bytes() != planned_bytes
    assert baseline_bytes != planned_bytes
    governed_after = {
        path.relative_to(REPO_ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
        for path in dashboard_sources
    }
    governed_after.update(
        {
            path: sha256((REPO_ROOT / path).read_bytes()).hexdigest()
            for path in (
                "architecture/imports/policy.toml",
                "apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json",
                "apps/runtime-dashboard/src/app/routes/routes.tsx",
                "apps/runtime-dashboard/src/shared/i18n/locales/en.json",
                "apps/runtime-dashboard/src/shared/i18n/locales/uk.json",
            )
        }
    )
    assert governed_after == governed_before


def test_producer_posture_metadata_is_strict_and_cannot_fabricate_support(
    tmp_path: Path,
) -> None:
    """Accept only the closed candidate/planned grammar from both derivations."""
    repo = tmp_path / "repo"
    _copy_compiler_inputs(repo)
    probe = repo / "src/polisyos/example.py"
    original = probe.read_text(encoding="utf-8")
    metadata = (
        '\n    trust_claim_posture = {"schema_version": '
        '"policyos.trust.producer_posture.v1", "subject": "example_claim", '
        '"source_state": "planned", "owner": "team-example", '
        '"closure_signal": "uv run pytest tests/example.py -q"}\n'
    )
    probe.write_text(original + metadata, encoding="utf-8")
    checker = _checker()
    register, _ = checker.compile_claim_posture_register(repo, register_as_of=FROZEN_AS_OF)
    assert (
        next(row for row in register.claims if row.subject == "example_claim").effective_state
        == "planned"
    )

    for forbidden in (
        '"effective_state": "supported"',
        '"establishment_class": "recomputed"',
        '"jurisdiction": "global"',
        '"review_on": "2026-08-26"',
        '"evidence_refs": []',
    ):
        probe.write_text(
            original + metadata.replace('"closure_signal":', f'{forbidden}, "closure_signal":'),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="DS11-PRODUCER-METADATA"):
            checker.compile_claim_posture_register(repo, register_as_of=FROZEN_AS_OF)


def test_producer_posture_metadata_ast_tokenizer_disagreement_is_blocked(
    tmp_path: Path,
) -> None:
    """A metadata mismatch cannot be silently selected from either derivation."""
    repo = tmp_path / "repo"
    _copy_compiler_inputs(repo)
    probe = repo / "src/polisyos/example.py"
    probe.write_text(
        probe.read_text(encoding="utf-8")
        + '\n    trust_claim_posture = {"schema_version": '
        + '"policyos.trust.producer_posture.v1", "subject": "example_claim", '
        + '"source_state": "planned", "owner": "team-example", '
        + '"closure_signal": "uv run pytest tests/example.py -q"}\n',
        encoding="utf-8",
    )
    sources = _sources()
    checker = _checker()
    ast_result = sources.derive_ast_sources(repo)
    token_result = checker.derive_token_sources(repo)
    token_row = token_result.rows[0]
    assert len(token_row.producer_metadata) == 1
    changed = token_row.model_copy(
        update={
            "producer_metadata": (
                token_row.producer_metadata[0].model_copy(update={"owner": "team-forged"}),
            )
        }
    )
    changed_token = token_result.model_copy(update={"rows": (changed,)})
    reconciled = checker.reconcile_source_derivations(ast_result, changed_token)
    assert reconciled.disagreements
    assert reconciled.rows[0].resolution == "ambiguous"
    assert reconciled.rows[0].producer_metadata == ()


def test_c05_corruption_matrix_is_complete_semantic_and_scratch_bounded(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Expose every named C05 mutation with a deterministic rejection receipt."""
    checker = _checker()
    assert (
        checker.main(["--repo-root", str(REPO_ROOT), "--check", "--corruption-probes", "--json"])
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    matrix = report["corruption_probes"]
    assert matrix["probe_count"] == 15
    assert matrix["rejected_count"] == 15
    assert matrix["scratch_escape_count"] == 0
    assert matrix["scratch_escape_paths"] == []
    assert [probe["probe_id"] for probe in matrix["results"]] == sorted(
        probe["probe_id"] for probe in matrix["results"]
    )
    assert {probe["probe_id"] for probe in matrix["results"]} == {
        "anti_role_removal",
        "body_fact_removal",
        "candidate_to_supported",
        "crm_omission",
        "dynamic_source_silently_dropped",
        "forbidden_purpose_removal",
        "limitation_omission",
        "machine_reserialization",
        "manages_your_cases",
        "performance_relabel",
        "planned_to_supported",
        "review_refresh_without_evidence",
        "row_reorder",
        "scope_assumption_change",
        "source_digest_rebinding",
    }
    expected_reasons = {
        "anti_role_removal": ["DS11-IDENTITY-ANTI-ROLE-DRIFT"],
        "body_fact_removal": ["DS11-A11Y-CERTIFICATION-NOT-EARNED"],
        "candidate_to_supported": ["DS11-STATUS-UPGRADE"],
        "crm_omission": ["DS11-IDENTITY-ANTI-ROLE-DRIFT"],
        "dynamic_source_silently_dropped": ["DS11-SOURCE-DERIVATION-DISAGREEMENT"],
        "forbidden_purpose_removal": ["DS11-AUTHORITY-PURPOSE-DENIED"],
        "limitation_omission": ["DS11-DOM-PARITY-DRIFT"],
        "machine_reserialization": ["DS11-MACHINE-BYTE-DRIFT"],
        "manages_your_cases": ["DS11-IDENTITY-COPY-UNBOUND"],
        "performance_relabel": ["DS11-PERFORMANCE-NOT-EARNED"],
        "planned_to_supported": ["DS11-STATUS-UPGRADE"],
        "review_refresh_without_evidence": ["DS11-REVIEW-MISSING-OR-STALE"],
        "row_reorder": ["DS11-DOM-PARITY-DRIFT"],
        "scope_assumption_change": ["DS11-GATE-PREDICATE-NOT-ESTABLISHED"],
        "source_digest_rebinding": ["DS11-SOURCE-CONTENT-NOT-BOUND"],
    }
    assert {
        probe["probe_id"]: probe["reason_codes"] for probe in matrix["results"]
    } == expected_reasons
    assert all(probe["outcome"] == "rejected" for probe in matrix["results"])
    assert all(
        probe["reason_codes"] == sorted(probe["reason_codes"]) for probe in matrix["results"]
    )
    assert all(probe["reason_codes"] for probe in matrix["results"])
    assert all(
        probe["declared_outputs"] == [] and probe["write_set"] == [] for probe in matrix["results"]
    )
    assert report["declared_outputs"] == []
    assert report["write_set"] == []


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


def test_compiler_emits_fixed_semantic_rows_and_complete_projection_membership(
    tmp_path: Path,
) -> None:
    """Catch empty semantic groups or omission of a required blocked posture family."""
    repo = tmp_path / "repo"
    _copy_compiler_inputs(repo)
    register, _ = _checker().compile_claim_posture_register(repo, register_as_of=FROZEN_AS_OF)
    assert register.rule_version == "policyos.trust.claim_posture_rules.v4"
    rows = {row.subject: row for row in register.claims}

    required = {
        "system_identity",
        "universal_custody_commitment",
        "historical_internal_accessibility_pre_audit",
        "current_accessibility_conformance",
        "external_accessibility_certification",
        "grounded_performance",
    }
    assert required <= set(rows)
    assert rows["system_identity"].effective_state == "supported"
    assert rows["universal_custody_commitment"].effective_state == "planned"
    assert {
        (binding.owner.owner, binding.prerequisite_refs, binding.closure_signal)
        for binding in rows["universal_custody_commitment"].source_bindings
    } == {
        (
            "team-runtime",
            ("DS11-PUBLISHED-SIGNATURE-WATCHER",),
            "uv run pytest tests/integration/runtime_quality/"
            "test_published_signature_custody.py::"
            "test_every_public_signature_is_watched_for_staleness -q",
        ),
        (
            "team-scientist",
            ("DS11-CLAIM-LIFECYCLE-ORCHESTRATION",),
            "uv run pytest tests/integration/scientist/governance/"
            "test_claim_lifecycle_orchestration.py::"
            "test_monitor_event_persists_claim_supersession_without_in_place_edit -q",
        ),
        (
            "team-design",
            ("DS11-PUBLIC-SIGNATURE-POPULATION",),
            "uv run pytest tests/unit/runtime/http/test_public_export.py::"
            "test_first_governed_public_signature_is_custody_bound -q",
        ),
    }
    assert rows["historical_internal_accessibility_pre_audit"].effective_state == "blocked"
    assert rows["current_accessibility_conformance"].effective_state == "blocked"
    assert rows["external_accessibility_certification"].effective_state == "blocked"
    assert rows["grounded_performance"].effective_state == "blocked"

    groups = {group.group_id: group.claim_ids for group in register.projection_groups}
    assert all(groups.values())
    memberships = {claim_id for claim_ids in groups.values() for claim_id in claim_ids}
    claim_ids = {row.claim_id for row in register.claims}
    assert memberships == claim_ids
    assert all(
        len(claim_ids_) == len(set(claim_ids_)) and set(claim_ids_) <= claim_ids
        for claim_ids_ in groups.values()
    )

    identity = rows["system_identity"].source_bindings[0]
    evidence = identity.evidence_bindings[0]
    admitted = {member.path: member.content_digest for member in register.admitted_sources}
    verifiers = {verifier.ref: verifier for verifier in register.admitted_verifiers}
    verifier = verifiers[evidence.verifier_ref]
    assert admitted[evidence.ref] == evidence.content_digest == identity.content_digest
    assert verifier.content_ref == evidence.ref
    assert verifier.content_digest == evidence.content_digest
    assert verifier.provenance_ref == evidence.verifier_provenance_ref

    orphaned = register.model_dump(mode="json")
    identity_claim_id = rows["system_identity"].claim_id
    for group in orphaned["projection_groups"]:
        group["claim_ids"] = [
            claim_id for claim_id in group["claim_ids"] if claim_id != identity_claim_id
        ]
    with pytest.raises(ValueError, match="projection_groups"):
        _owner("polisyos.scientist.evidence.claims.posture").validate_posture_register(orphaned)


def test_marker_preserving_byte_mutation_and_unknown_verifier_fail_closed(
    tmp_path: Path,
) -> None:
    """Catch prefix/nonempty marker checks that ignore admitted bytes and verifier identity."""
    repo = tmp_path / "repo"
    _copy_compiler_inputs(repo)
    checker = _checker()
    posture = _owner("polisyos.scientist.evidence.claims.posture")
    register, payload = checker.compile_claim_posture_register(repo, register_as_of=FROZEN_AS_OF)
    row = next(item for item in register.claims if item.subject == "system_identity")
    binding = row.source_bindings[0]

    changed_sources = tuple(
        member.model_copy(update={"content_digest": "sha256:" + "0" * 64})
        if member.path == binding.coordinate.path
        else member
        for member in register.admitted_sources
    )
    state, blockers, _ = posture.evaluate_claim_posture(
        (binding,),
        subject=row.subject,
        family=row.family,
        register_as_of=FROZEN_AS_OF,
        identity_boundary=register.identity_boundary,
        admitted_sources=changed_sources,
        admitted_verifiers=register.admitted_verifiers,
    )
    assert state == "blocked"
    assert {
        "DS11-SOURCE-CONTENT-NOT-BOUND",
        "DS11-EVIDENCE-NOT-INDEPENDENTLY-BOUND",
    } <= set(blockers)

    evidence = binding.evidence_bindings[0]
    unknown = evidence.model_copy(
        update={
            "verifier_ref": "verifier:unknown-but-nonempty",
            "verifier_provenance_ref": "provenance:unknown-but-nonempty",
        }
    )
    unknown_binding = binding.model_copy(
        update={"evidence_bindings": (unknown,), "evidence_refs": (unknown.ref,)}
    )
    state, blockers, _ = posture.evaluate_claim_posture(
        (unknown_binding,),
        subject=row.subject,
        family=row.family,
        register_as_of=FROZEN_AS_OF,
        identity_boundary=register.identity_boundary,
        admitted_sources=register.admitted_sources,
        admitted_verifiers=register.admitted_verifiers,
    )
    assert state == "blocked"
    assert "DS11-EVIDENCE-NOT-INDEPENDENTLY-BOUND" in blockers

    authored = register.model_dump(mode="json")
    authored_row = next(item for item in authored["claims"] if item["subject"] == row.subject)
    authored_row["source_bindings"][0]["evidence_bindings"][0]["verifier_ref"] = (
        "verifier:unknown-but-nonempty"
    )
    with pytest.raises(ValueError, match="authored effective posture"):
        posture.validate_posture_register(authored)

    identity_path = repo / IDENTITY_PATH
    identity_path.write_bytes(identity_path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="DS11-GENERATED-DRIFT"):
        checker.validate_register_against_live_sources(
            payload,
            repo_root=repo,
            register_as_of=FROZEN_AS_OF,
        )
    identity_path.write_bytes(
        identity_path.read_bytes().replace(b"epistemic custodian", b"chat assistant")
    )
    mutated, _ = checker.compile_claim_posture_register(repo, register_as_of=FROZEN_AS_OF)
    mutated_identity = next(item for item in mutated.claims if item.subject == "system_identity")
    assert mutated_identity.effective_state == "blocked"


def test_nonperformance_verifiers_cannot_mint_grounded_performance(
    tmp_path: Path,
) -> None:
    """Catch subject relabeling that turns admitted non-performance evidence into support."""
    repo = tmp_path / "repo"
    _copy_compiler_inputs(repo)
    _write_accessibility_document(repo)
    _copy_page_receipt(repo)
    checker = _checker()
    posture = _owner("polisyos.scientist.evidence.claims.posture")
    register, _ = checker.compile_claim_posture_register(repo, register_as_of=FROZEN_AS_OF)
    assert tuple(verifier.verifier_kind for verifier in register.admitted_verifiers) == (
        "accessibility_document_derivation",
        "identity_boundary_derivation",
        "page_a11y_receipt_derivation",
    )
    predicates = tuple(
        posture.SupportPredicate(
            kind=kind,
            satisfied=True,
            establishment_class="independently_reconciled",
            evidence_refs=(f"evidence:{kind}",),
            issue_code=None,
        )
        for kind in posture.REQUIRED_SUPPORT_PREDICATES
    )

    observed: dict[str, object] = {}
    for verifier in register.admitted_verifiers:
        relabeled = posture.EvidenceBinding(
            ref=verifier.content_ref,
            content_digest=verifier.content_digest,
            subject_binding="grounded_performance",
            verifier_ref=verifier.ref,
            verifier_provenance_ref=verifier.provenance_ref,
            establishment_class="independently_reconciled",
            source_as_of=FROZEN_AS_OF,
            supersession_ref=None,
        )
        observed[verifier.verifier_kind] = posture.compose_effective_state(
            ("supported",),
            support_predicates=predicates,
            family="grounded_performance",
            governed_performance_prerequisite=relabeled,
            admitted_sources=register.admitted_sources,
            admitted_verifiers=register.admitted_verifiers,
            register_as_of=FROZEN_AS_OF,
        )
    assert observed == {
        "accessibility_document_derivation": "blocked",
        "identity_boundary_derivation": "blocked",
        "page_a11y_receipt_derivation": "blocked",
    }

    identity_row = next(item for item in register.claims if item.subject == "system_identity")
    identity_binding = identity_row.source_bindings[0]
    identity_evidence = identity_binding.evidence_bindings[0].model_copy(
        update={"subject_binding": "grounded_performance"}
    )
    forged_binding = identity_binding.model_copy(
        update={
            "subject": "grounded_performance",
            "family": "grounded_performance",
            "authoritative_for": ("grounded_performance",),
            "authority_purpose": "grounded_performance",
            "evidence_refs": (identity_evidence.ref,),
            "evidence_bindings": (identity_evidence,),
            "limitation_refs": (),
        }
    )
    forged = posture.build_posture_register(
        register_as_of=FROZEN_AS_OF,
        admitted_sources=register.admitted_sources,
        ast_derivation=register.ast_derivation,
        token_derivation=register.token_derivation,
        identity_boundary=register.identity_boundary,
        accessibility_document=register.accessibility_document,
        page_a11y_receipt=register.page_a11y_receipt,
        source_inventory=register.source_inventory,
        source_bindings=(forged_binding,),
    )
    assert forged.claims[0].effective_state == "blocked"

    authored = forged.model_dump(mode="json")
    authored["claims"][0]["effective_state"] = "supported"
    digest_payload = {key: value for key, value in authored.items() if key != "payload_digest"}
    authored["payload_digest"] = (
        "sha256:"
        + sha256(
            json.dumps(
                digest_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    )
    with pytest.raises(ValueError, match="authored effective posture"):
        posture.validate_posture_register(authored)


def test_live_accessibility_projection_index_binds_the_unchanged_audit_body() -> None:
    """Catch removal, rebinding, or purpose widening of the live audit projection index."""
    binding = _checker().derive_accessibility_document(REPO_ROOT)

    assert binding.body_digest == (
        "sha256:0e4a0280ab30e1c69cb373d438906aa50d36bd9765ec36e533b6fea1a7df93f0"
    )
    assert {item.key for item in binding.bindings} == {
        "assessment_owner",
        "audit_type",
        "evaluation_scope",
        "external_countersign_status",
        "internal_pre_audit_status",
        "product_under_review",
        "source_as_of",
    }
    assert tuple(item.purpose for item in binding.authoritative_for) == (
        "historical_internal_accessibility_pre_audit",
    )
    assert tuple(item.purpose for item in binding.may_not_use_for) == (
        "current_accessibility_conformance",
        "external_accessibility_certification",
    )


def test_accessibility_limitation_ignores_markdown_wrap_but_binds_exact_words(
    tmp_path: Path,
) -> None:
    """Catch literal-line proxies or acceptance of a semantically changed limitation."""
    repo = tmp_path / "repo"
    _copy_compiler_inputs(repo)
    original_body = _write_accessibility_document(repo)
    path = repo / A11Y_PATH
    original_digest = sha256(original_body).hexdigest()
    wrapped_body = original_body.replace(
        b"It does not replace the planned third-party countersign.",
        b"It does not replace the planned\nthird-party countersign.",
    )
    wrapped_digest = sha256(wrapped_body).hexdigest()
    path.write_bytes(
        path.read_bytes()
        .replace(original_digest.encode(), wrapped_digest.encode())
        .replace(original_body, wrapped_body)
    )

    binding = _checker().derive_accessibility_document(repo)
    assert binding.limitation_refs == ("It does not replace the planned third-party countersign.",)

    mutated_body = wrapped_body.replace(b"does not replace", b"does not supersede")
    mutated_digest = sha256(mutated_body).hexdigest()
    path.write_bytes(
        path.read_bytes()
        .replace(wrapped_digest.encode(), mutated_digest.encode())
        .replace(wrapped_body, mutated_body)
    )
    with pytest.raises(ValueError, match="accessibility limitation"):
        _checker().derive_accessibility_document(repo)


def test_accessibility_frontmatter_is_strictly_bound_to_complete_body(tmp_path: Path) -> None:
    """Catch frontmatter surviving removal or duplication of its cited body fact."""
    repo = tmp_path / "repo"
    _copy_compiler_inputs(repo)
    body = _write_accessibility_document(repo)
    checker = _checker()
    binding = checker.derive_accessibility_document(repo)
    assert binding.body_digest == "sha256:" + sha256(body).hexdigest()
    assert binding.source_as_of == date(2026, 4, 22)
    assert all(item.establishment_class == "recomputed" for item in binding.bindings)
    assert all(item.byte_end > item.byte_start for item in binding.bindings)
    register, _ = checker.compile_claim_posture_register(repo, register_as_of=FROZEN_AS_OF)
    historical = next(
        row
        for row in register.claims
        if row.subject == "historical_internal_accessibility_pre_audit"
    )
    assert historical.effective_state == "blocked"
    assert "DS11-JURISDICTION-NOT-ESTABLISHED" in historical.blocker_codes
    historical_binding = historical.source_bindings[0]
    assert historical_binding.content_digest == binding.content_digest
    assert historical_binding.evidence_bindings[0].content_digest == binding.content_digest
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
    checker = _checker()
    family = checker.validate_generated_family(REPO_ROOT)
    assert family.default_freshness_check is True
    assert family.stale_output_behavior == "fail"
    assert family.outputs == ("apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json",)
    assert sum("{output_root}" in item for item in family.output_probe_command) == 1

    output_root = tmp_path / "probe"
    observed = checker.run_generated_family_output_probe(
        REPO_ROOT,
        source_root=tmp_path / "source",
        output_root=output_root,
    )
    assert observed == family.outputs
    assert (output_root / family.outputs[0]).read_bytes() == (
        REPO_ROOT / family.outputs[0]
    ).read_bytes()
    reference_root = tmp_path / "reference"
    written = checker.write_generated_reference(REPO_ROOT, output_root=reference_root)
    assert written == reference_root / "docs/reference/generated-artifacts.md"
    guardrails = _owner("tools.devx.architecture.guardrails")
    expected = guardrails.render_generated_artifacts_markdown(
        guardrails._parse_generated_artifacts(REPO_ROOT / GENERATED_MANIFEST_PATH)
    ).encode()
    assert written.read_bytes() == expected
    assert {
        path.relative_to(reference_root).as_posix()
        for path in reference_root.rglob("*")
        if path.is_file()
    } == {"docs/reference/generated-artifacts.md"}


def test_generated_family_probe_executes_the_declared_command(tmp_path: Path) -> None:
    """Catch bypassing a broken executable while retaining accepted marker arguments."""
    repo = tmp_path / "repo"
    _copy_compiler_inputs(repo)
    manifest = _write_generated_manifest(repo)
    checker = _checker()
    original_command = checker.validate_generated_family(repo).output_probe_command
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'output_probe_command = ["uv",',
            'output_probe_command = ["ds11-command-does-not-exist",',
        ),
        encoding="utf-8",
    )
    mutated_command = checker.validate_generated_family(repo).output_probe_command
    assert original_command[0] == "uv"
    assert mutated_command[0] == "ds11-command-does-not-exist"
    assert mutated_command[1:] == original_command[1:]

    with pytest.raises(ValueError, match=r"executable|command|available"):
        checker.run_generated_family_output_probe(
            repo,
            source_root=tmp_path / "source",
            output_root=tmp_path / "probe",
        )


def test_live_generated_family_is_the_default_freshness_persistence_bridge() -> None:
    """Catch removal or weakening of the live generated-committed family."""
    family = _checker().validate_generated_family(REPO_ROOT)

    assert family.family_id == "trust-claim-posture-register"
    assert family.lifecycle == "generated_committed"
    assert family.stale_output_behavior == "fail"
    assert family.default_freshness_check is True
    assert family.outputs == ("apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json",)
    assert "--write" in family.output_probe_command
    assert "--output-root" in family.output_probe_command


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
