"""Replay the existing CR5 owners and remove one decisive property per fresh process."""

from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import subprocess
import textwrap
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[5]
VERIFIER_TEST = "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py"
SUBJECT_TEST = (
    "tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_subject_binding.py"
)
CONSUMER_TEST = (
    "tests/unit/data_forge/domains/academic/batch/test_admitted_claim_adjudication_consumers.py"
)
PIPELINE_TEST = (
    "tests/integration/data_forge/domains/academic/batch/test_claim_adjudication_pipeline.py"
)
RUNTIME_TEST = "tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py"
NODES = [
    VERIFIER_TEST + "::test_signed_observations_drive_runtime_and_direct_materialization",
    VERIFIER_TEST + "::test_self_issued_or_incoherent_evidence_is_refused_at_both_intakes",
    VERIFIER_TEST + "::test_empty_deployment_appointment_cannot_publish",
    VERIFIER_TEST + "::test_valid_champion_does_not_authorize_fabricated_run_result",
    VERIFIER_TEST + "::test_appointment_cannot_name_its_producer_as_evaluator",
    VERIFIER_TEST + "::test_graph_rejects_raw_or_unminted_verified_rows_before_writing",
    VERIFIER_TEST + "::test_verified_rows_recheck_current_champion_at_graph_use",
    VERIFIER_TEST + "::test_retained_promotion_basis_requires_actual_incumbent_observations",
    VERIFIER_TEST
    + "::test_legacy_pointer_has_no_inferred_genesis_and_manual_replacement_is_refused",
    VERIFIER_TEST + "::test_claim_transition_rejects_alternate_policy_without_changing_basis",
    SUBJECT_TEST + "::test_every_current_input_field_is_required_and_content_bound",
    SUBJECT_TEST + "::test_full_subject_reaches_both_consumers_without_borrowed_grades",
    CONSUMER_TEST + "::test_verified_receipt_drives_graph_and_conflict_consumers",
    CONSUMER_TEST
    + "::test_constant_receipt_rejects_false_to_true_projection_flip_in_both_consumers",
    CONSUMER_TEST + "::test_invalid_replacement_receipt_cannot_erase_existing_admitted_pointer",
    PIPELINE_TEST + "::test_rich_producer_subject_survives_admission_and_both_consumers",
    RUNTIME_TEST + "::test_raw_input_excludes_producer_publish_authority_and_freezes_bytes",
    RUNTIME_TEST + "::test_missing_champion_blocks_without_emitting_result",
    RUNTIME_TEST + "::test_promoted_champion_executes_and_publishes_strong_fulltext",
    RUNTIME_TEST + "::test_model_positive_cannot_publish_abstract_only_claim",
    RUNTIME_TEST + "::test_evaluation_candidate_mismatch_blocks_admission",
    RUNTIME_TEST + "::test_required_guardrail_false_blocks_admission",
    RUNTIME_TEST + "::test_tampered_raw_blob_is_rejected_before_execution",
    RUNTIME_TEST + "::test_execution_result_cannot_be_presented_as_validity_evidence",
    RUNTIME_TEST + "::test_scientist_cli_route_executes_real_transport_and_materializes_receipt",
]
SOURCE_PATHS = [
    "src/polisyos/data_forge/domains/academic/batch/claim_adjudication_verifier.py",
    "src/polisyos/data_forge/domains/academic/batch/claim_adjudication_policy.py",
    "src/polisyos/data_forge/domains/academic/batch/admitted_claim_adjudications.py",
    "src/polisyos/data_forge/domains/academic/batch/claim_adjudicator.py",
    "src/polisyos/data_forge/domains/academic/batch/graph_builder.py",
    "src/polisyos/data_forge/domains/academic/batch/conflict_resolve.py",
    "src/polisyos/scientist/methods/autotune/claim_adjudication_runtime.py",
    "src/polisyos/scientist/methods/autotune/registry.py",
    "src/polisyos/ir/analytics/literature.py",
]


def unchanged_base() -> None:
    """Read every selected source/test from the lane base and compare actual bytes."""
    paths = SOURCE_PATHS + sorted({node.split("::")[0] for node in NODES})
    paths.append("tests/unit/data_forge/domains/academic/batch/_claim_evidence.py")
    for relative in paths:
        current = (ROOT / relative).read_bytes()
        base = subprocess.run(  # noqa: S603 - constant git/base/owned-path inputs
            ["/usr/bin/git", "show", "992aa493f:policy-engine/" + relative],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        if base != current:
            raise ValueError("closed_task_source_changed:" + relative)
        print("BASE_UNCHANGED\t" + relative + "\t" + hashlib.sha256(current).hexdigest())  # noqa: T201
    test_files = sorted({node.split("::")[0] for node in NODES})
    found = set()
    for relative in test_files:
        tree = ast.parse((ROOT / relative).read_text())
        found.update(
            relative + "::" + node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        )
    if found != set(NODES):
        raise ValueError("complete_selected_file_test_node_mismatch")
    print("EXPLICIT_NODE_DENOMINATOR\t" + json.dumps(NODES))  # noqa: T201


def _replace_method(cls: type, name: str, mode: str) -> None:
    original = getattr(cls, name)
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    changed = 0
    if mode == "authentication":
        for node in ast.walk(tree):
            if isinstance(node, ast.Try) and any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "verify"
                for child in ast.walk(node)
            ):
                node.body = [ast.Pass()]
                changed += 1
    else:
        reason = (
            "claim_adjudication_batch_observation_replay_mismatch"
            if mode == "observation"
            else "claim_adjudication_current_subject_binding_mismatch"
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and any(
                isinstance(child, ast.Constant) and child.value == reason
                for statement in node.body
                for child in ast.walk(statement)
            ):
                node.test = ast.Constant(False)
                changed += 1
    if changed != 1:
        raise ValueError("removal_target_not_unique:" + str(changed))
    ast.fix_missing_locations(tree)
    scope = dict(original.__globals__)
    # Execute only the inspected lane-base function with one process-local predicate removed.
    exec(compile(tree, inspect.getfile(original) + ":process-local-removal", "exec"), scope)  # noqa: S102
    setattr(cls, name, scope[name])
    print("REMOVED_PROPERTY\t" + mode + "\t" + cls.__name__ + "." + name)  # noqa: T201


def unfavorable_consumers() -> None:
    """Replay an authentic unfavorable grade through both actual publication consumers."""
    from polisyos.data_forge.domains.academic.batch.admitted_claim_adjudications import (
        load_verified_claim_adjudication_rows,
    )
    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
    from polisyos.data_forge.domains.academic.batch.conflict_resolve import run_conflict_resolve
    from polisyos.data_forge.domains.academic.batch.graph_builder import build_graph
    from tests.unit.data_forge.domains.academic.batch import (
        test_admitted_claim_adjudication_consumers as fixture,
    )

    scratch = Path(__file__).with_name("raw")
    scratch.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="unfavorable-", dir=scratch) as directory:
        config = AcademicBatchConfig(snapshot_root=Path(directory) / "snapshot")
        _, receipt, verifier = fixture._receipt(config, publishable=False)
        rows = load_verified_claim_adjudication_rows(config, verifier=verifier)
        current = fixture._current_subject()
        if rows.for_current_subject(current)["publishable_edge"] is not False:
            raise ValueError("unfavorable_grade_not_preserved")
        stats = build_graph(
            records=iter([fixture._work_record()]),
            db_path=config.db_path,
            admitted_claim_adjudications=rows,
        )
        if stats.claims != 0:
            raise ValueError("unfavorable_graph_publication_escape")
        fixture._write_jsonl(config.raw_claim_candidates_final_path, [current])
        run_conflict_resolve(config, verifier=verifier)
        results = [json.loads(line) for line in config.claim_sets_path.read_text().splitlines()]
        if not results or sum(row["publishable_claims"] for row in results) != 0:
            raise ValueError("unfavorable_conflict_publication_escape")
        if rows.for_current_subject(current)["publishable_edge"] is not False:
            raise ValueError("unfavorable_grade_not_preserved")
        print("UNFAVORABLE_ADMITTED\tgraph=0\tconflict=0\treceipt=" + receipt)  # noqa: T201


def main() -> int:
    """Return the actual pytest status; a removal must be pytest-red, never a crash."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=(
            "collect",
            "baseline",
            "authentication",
            "observation",
            "current_subject",
            "unfavorable",
        ),
    )
    args = parser.parse_args()
    unchanged_base()
    if args.mode == "unfavorable":
        unfavorable_consumers()
        unchanged_base()
        return 0
    nodes = NODES
    if args.mode in ("authentication", "observation"):
        from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
            ClaimAdjudicationVerifier,
        )

        _replace_method(
            ClaimAdjudicationVerifier,
            "_authenticate" if args.mode == "authentication" else "verify_batch",
            args.mode,
        )
        if args.mode == "authentication":
            name = "::test_self_issued_or_incoherent_evidence_is_refused_at_both_intakes"
            nodes = [
                VERIFIER_TEST + name + "[" + corruption + "-" + entry + "]"
                for corruption in ("signature", "unappointed_signer")
                for entry in ("scientist", "data_forge")
            ]
        else:
            nodes = [
                VERIFIER_TEST
                + "::test_valid_champion_does_not_authorize_fabricated_run_result"
                + "["
                + entry
                + "]"
                for entry in ("scientist", "data_forge")
            ]
    elif args.mode == "current_subject":
        from polisyos.data_forge.domains.academic.batch.admitted_claim_adjudications import (
            VerifiedClaimAdjudicationRows,
        )

        _replace_method(VerifiedClaimAdjudicationRows, "for_current_subject", args.mode)
        name = "::test_full_subject_reaches_both_consumers_without_borrowed_grades"
        nodes = [
            SUBJECT_TEST + name + "[" + changed + "-" + consumer + "]"
            for changed in ("cause_variable", "direction", "scope_conditions")
            for consumer in ("graph", "conflict")
        ]
    import pytest

    selected = [*nodes, "-o", "addopts=", "-q"]
    if args.mode == "collect":
        selected.append("--collect-only")
    result = int(pytest.main(selected))
    unchanged_base()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
