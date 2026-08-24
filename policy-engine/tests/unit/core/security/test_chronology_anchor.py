"""Behavioral tests for chronology anchor contracts and verification."""

from __future__ import annotations

import ast
import hashlib
import importlib
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import BaseModel, ValidationError

from polisyos.core.artifacts import ArtifactID, ArtifactRef


def _digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def _ref(label: str, kind: str = "fixture") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(_digest(label)),
        kind=kind,
        media_type="application/octet-stream",
    )


def test_verified_acceptance_requires_every_final_lineage_binding() -> None:
    """Dropping the append receipt must make a positive acceptance unrepresentable."""
    from polisyos.core.contracts.chronology import VerifiedAnchorAcceptance

    fields = {
        "acceptance_digest": _digest("acceptance"),
        "acceptance_record_ref": _ref("record"),
        "acceptance_record_content_hash": _digest("record-content"),
        "acceptance_receipt_record_ref": _ref("receipt"),
        "acceptance_receipt_record_content_hash": _digest("receipt-content"),
        "lineage_append_receipt_ref": None,
        "lineage_append_receipt_content_hash": _digest("append-content"),
        "lineage_state_content_hash": _digest("lineage-state"),
        "lineage_position": "current",
        "accepting_owner_ref": "epoch-owner",
        "statement_content_hash": _digest("statement"),
        "signed_statement_evidence_ref": _ref("evidence"),
        "acceptance_appointment_ref": _ref("appointment"),
        "acceptance_appointment_content_hash": _digest("appointment-content"),
        "verifier_provenance_ref": _ref("verifier"),
        "requested_query_context_ref": _digest("query"),
        "admission_cutoff_ref": _digest("cutoff"),
        "prior_acceptance_record_refs": (),
        "predicate_class": "independently_reconciled",
    }
    try:
        VerifiedAnchorAcceptance.model_validate(fields)
    except ValidationError:
        return
    raise AssertionError("positive acceptance admitted without a lineage append receipt")


def test_custody_product_derives_status_from_both_roles() -> None:
    """A caller-supplied aggregate status must not override role outcomes."""
    from polisyos.core.contracts.chronology import (
        AnchorCustodyVerification,
        RetentionUnavailableNonReceipt,
        UnavailableRetentionOutcome,
        VerifiedAcceptanceOutcome,
        VerifiedAnchorAcceptance,
    )

    accepted = VerifiedAnchorAcceptance(
        acceptance_digest=_digest("acceptance"),
        acceptance_record_ref=_ref("record"),
        acceptance_record_content_hash=_digest("record-content"),
        acceptance_receipt_record_ref=_ref("receipt"),
        acceptance_receipt_record_content_hash=_digest("receipt-content"),
        lineage_append_receipt_ref=_ref("append"),
        lineage_append_receipt_content_hash=_digest("append-content"),
        lineage_state_content_hash=_digest("lineage-state"),
        lineage_position="current",
        accepting_owner_ref="epoch-owner",
        statement_content_hash=_digest("statement"),
        signed_statement_evidence_ref=_ref("evidence"),
        acceptance_appointment_ref=_ref("appointment"),
        acceptance_appointment_content_hash=_digest("appointment-content"),
        verifier_provenance_ref=_ref("verifier"),
        requested_query_context_ref=_digest("query"),
        admission_cutoff_ref=_digest("cutoff"),
        prior_acceptance_record_refs=(),
        predicate_class="independently_reconciled",
    )
    retention = UnavailableRetentionOutcome(
        status="not_established",
        non_receipts=(
            RetentionUnavailableNonReceipt(
                status="not_established",
                component="retention",
                code="anchor_holder_not_established",
                subject_artifact_ref=_ref("bundle"),
                requested_query_context_ref=_digest("query"),
                appointment_key_ref=_digest("appointment-key"),
                resolved_appointment_ref=None,
                appointment_evidence_ref=None,
                resolver_provenance_ref=_ref("resolver"),
                predicate_class="not_established",
            ),
        ),
    )
    result = AnchorCustodyVerification(
        status="limited",
        acceptance=VerifiedAcceptanceOutcome(status="verified", value=accepted),
        retention=retention,
    )
    assert result.status == "limited"
    try:
        result.model_copy(update={"status": "verified"}, deep=True)
    except ValidationError:
        return
    # model_copy does not revalidate in Pydantic; round-trip must.
    try:
        AnchorCustodyVerification.model_validate(
            result.model_dump(mode="python") | {"status": "verified"}
        )
    except ValidationError:
        return
    raise AssertionError("aggregate status was accepted independently of role outcomes")


def _accepted_outcome():
    from polisyos.core.contracts.chronology import (
        VerifiedAcceptanceOutcome,
        VerifiedAnchorAcceptance,
    )

    return VerifiedAcceptanceOutcome(
        status="verified",
        value=VerifiedAnchorAcceptance(
            acceptance_digest=_digest("acceptance"),
            acceptance_record_ref=_ref("record"),
            acceptance_record_content_hash=_digest("record-content"),
            acceptance_receipt_record_ref=_ref("receipt"),
            acceptance_receipt_record_content_hash=_digest("receipt-content"),
            lineage_append_receipt_ref=_ref("append"),
            lineage_append_receipt_content_hash=_digest("append-content"),
            lineage_state_content_hash=_digest("lineage-state"),
            lineage_position="current",
            accepting_owner_ref="epoch-owner",
            statement_content_hash=_digest("statement"),
            signed_statement_evidence_ref=_ref("evidence"),
            acceptance_appointment_ref=_ref("acceptance-appointment"),
            acceptance_appointment_content_hash=_digest("acceptance-appointment-content"),
            verifier_provenance_ref=_ref("acceptance-verifier"),
            requested_query_context_ref=_digest("query"),
            admission_cutoff_ref=_digest("cutoff"),
            prior_acceptance_record_refs=(),
            predicate_class="independently_reconciled",
        ),
    )


def _retained_outcome():
    from polisyos.core.contracts.chronology import (
        VerifiedAnchorRetention,
        VerifiedRetentionOutcome,
    )

    return VerifiedRetentionOutcome(
        status="verified",
        value=VerifiedAnchorRetention(
            holder_ref="epoch-holder",
            custody_receipt_record_ref=_ref("custody"),
            custody_receipt_record_raw_bytes_hash=_digest("custody-content"),
            readback_receipt_record_ref=_ref("readback"),
            readback_receipt_record_raw_bytes_hash=_digest("readback-content"),
            challenge_record_ref=_ref("challenge"),
            challenge_record_content_hash=_digest("challenge-content"),
            package_ref=_digest("package"),
            package_content_hash=_digest("package-content"),
            object_version_ref="object-version-1",
            retention_policy_ref=_ref("retention-policy"),
            holder_appointment_ref=_ref("holder-appointment"),
            holder_appointment_content_hash=_digest("holder-appointment-content"),
            verifier_provenance_ref=_ref("holder-verifier"),
            signed_evidence_record_refs=(_ref("custody-evidence"), _ref("readback-evidence")),
            requested_query_context_ref=_digest("query"),
            predicate_class="independently_reconciled",
        ),
    )


def _acceptance_outcome(status: str):
    from polisyos.core.contracts.chronology import (
        AcceptanceRejectedNonReceipt,
        RejectedAcceptanceOutcome,
        UnavailableAcceptanceOutcome,
    )

    if status == "verified":
        return _accepted_outcome()
    if status == "not_established":
        from polisyos.core.contracts.chronology import AcceptanceUnavailableNonReceipt

        return UnavailableAcceptanceOutcome(
            status="not_established",
            non_receipts=(
                AcceptanceUnavailableNonReceipt(
                    status="not_established",
                    component="acceptance",
                    code="anchor_acceptance_owner_not_established",
                    subject_artifact_ref=_ref("subject"),
                    requested_query_context_ref=_digest("query"),
                    appointment_key_ref=_digest("appointment-key"),
                    resolved_appointment_ref=None,
                    appointment_evidence_ref=None,
                    resolver_provenance_ref=_ref("resolver"),
                    predicate_class="not_established",
                ),
            ),
        )
    return RejectedAcceptanceOutcome(
        status="rejected",
        rejections=(
            AcceptanceRejectedNonReceipt(
                status="rejected",
                component="acceptance",
                code="anchor_signature_unverified",
                subject_artifact_ref=_ref("subject"),
                requested_query_context_ref=_digest("query"),
                appointment_ref=_ref("appointment"),
                verifier_provenance_ref=_ref("verifier"),
                decisive_evidence_refs=(_ref("decisive"),),
                predicate_class="independently_reconciled",
            ),
        ),
    )


def _retention_outcome(status: str):
    from polisyos.core.contracts.chronology import (
        RejectedRetentionOutcome,
        RetentionRejectedNonReceipt,
        RetentionUnavailableNonReceipt,
        UnavailableRetentionOutcome,
    )

    if status == "verified":
        return _retained_outcome()
    if status == "not_established":
        return UnavailableRetentionOutcome(
            status="not_established",
            non_receipts=(
                RetentionUnavailableNonReceipt(
                    status="not_established",
                    component="retention",
                    code="anchor_holder_not_established",
                    subject_artifact_ref=_ref("subject"),
                    requested_query_context_ref=_digest("query"),
                    appointment_key_ref=_digest("appointment-key"),
                    resolved_appointment_ref=None,
                    appointment_evidence_ref=None,
                    resolver_provenance_ref=_ref("resolver"),
                    predicate_class="not_established",
                ),
            ),
        )
    return RejectedRetentionOutcome(
        status="rejected",
        rejections=(
            RetentionRejectedNonReceipt(
                status="rejected",
                component="retention",
                code="anchor_readback_mismatch",
                subject_artifact_ref=_ref("subject"),
                requested_query_context_ref=_digest("query"),
                appointment_ref=_ref("appointment"),
                verifier_provenance_ref=_ref("verifier"),
                decisive_evidence_refs=(_ref("decisive"),),
                predicate_class="independently_reconciled",
            ),
        ),
    )


def test_all_nine_role_products_have_exact_derived_status() -> None:
    """No combination may erase the independent acceptance/retention predicate."""
    from polisyos.core.contracts.chronology import AnchorCustodyVerification

    statuses = ("verified", "not_established", "rejected")
    for acceptance_status in statuses:
        for retention_status in statuses:
            expected = (
                "rejected"
                if "rejected" in (acceptance_status, retention_status)
                else "verified"
                if (acceptance_status, retention_status) == ("verified", "verified")
                else "limited"
            )
            product = AnchorCustodyVerification(
                status=expected,
                acceptance=_acceptance_outcome(acceptance_status),
                retention=_retention_outcome(retention_status),
            )
            assert product.status == expected


def test_canonical_registry_has_frozen_seventeen_domains() -> None:
    """Trust bytes stay domain-bound without inventing authority DTOs."""
    from polisyos.core.security.chronology_anchor import C3_CANONICAL_CODECS

    assert len(C3_CANONICAL_CODECS) == 17
    assert C3_CANONICAL_CODECS["anchor-acceptance-trust-snapshot.v1"].model is None
    assert C3_CANONICAL_CODECS["anchor-holder-trust-snapshot.v1"].model is None


_PRE_CLUSTER3_CONTRACT_MODEL_NAMES = frozenset(
    {
        "ApplicablePredicateDenominatorArtifactFailure",
        "ApplicablePredicateDenominatorStatement",
        "ChronologyBundleHeader",
        "ChronologyBundleRequest",
        "ChronologyMemberInput",
        "ChronologyPersistenceManifestMismatch",
        "ChronologyPersistenceNotEstablished",
        "ChronologyPersistenceStoreIntegrityMismatch",
        "ChronologyPersistenceVerificationMismatch",
        "ChronologyProofDomain",
        "ChronologyProofPersistenceFailed",
        "EncodedChronologyBundle",
        "ExpectedCommitmentPrefix",
        "FullPrefixBuildRejected",
        "FullPrefixEnvelopeRejected",
        "FullPrefixEvaluationState",
        "FullPrefixExpectedPrefixRejected",
        "FullPrefixInternalConsistencyRejected",
        "FullPrefixInvocationRejected",
        "FullPrefixMemberRejected",
        "FullPrefixVerificationStatement",
        "FullPrefixVerified",
        "MemberPredicateDisposition",
        "NativeApplicablePredicateDenominatorPersistenceFailed",
        "NativeAuthorityHeadNotEstablished",
        "NativeChronologyCandidate",
        "NativeChronologyOwnerContext",
        "NativeChronologyPersistenceFailed",
        "NativeChronologyPolicyResolutionFailed",
        "NativeChronologyQualified",
        "NativeChronologyQuery",
        "NativeChronologyReconciliation",
        "NativeExteriorAndAuthorityHeadNotEstablished",
        "NativeExteriorNotEstablished",
        "NativeFullPrefixBuildRejected",
        "NativeFullPrefixProofRejected",
        "NativePredicateRejected",
        "NativeProjectionCustodyGap",
        "NativeQualificationProcessGenerationNotEstablished",
        "NativeSchemaProfileRejected",
        "OwnerQualifiedNativeCandidate",
        "PersistedApplicablePredicateDenominator",
        "PersistedChronologyProof",
        "PersistedPredicateAdmissionPolicy",
        "PersistedPredicatePolicyAdmission",
        "PolicyAdmissionAmbiguousFailure",
        "PolicyAdmissionMissingFailure",
        "PolicyBindingMismatchFailure",
        "PolicyBytesMissingFailure",
        "PolicyOwnerDenominatorMismatchFailure",
        "PolicyOwnerRelationNotEstablished",
        "PolicyOwnerRelationRejected",
        "PolicyQueryBindingMismatchFailure",
        "PredicateAdmissionPolicyStatement",
        "PredicateAdmissionRule",
        "PredicateDisposition",
        "PredicatePolicyAdmissionStatement",
        "PredicatePolicyResolutionContext",
        "PredicatePolicySelectionKey",
        "QueryPredicateDisposition",
        "ResolvedPredicatePolicyAdmission",
        "VerifiedNativeMemberIdentity",
        "VerifiedNativeSubjectIdentity",
        "VerifiedOwnerPredicateEvidence",
        "VerifiedPolicyOwnerProvenance",
        "VerifiedPredicatePolicyOwnerRelation",
    }
)


def _chronology_contract_ast() -> tuple[ast.Module, dict[str, ast.ClassDef]]:
    source = (Path(__file__).parents[4] / "src/polisyos/core/contracts/chronology.py").read_text(
        "utf-8"
    )
    tree = ast.parse(source)
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}

    def inherits_chronology_model(name: str, seen: frozenset[str] = frozenset()) -> bool:
        if name == "_ChronologyModel":
            return True
        if name in seen or name not in classes:
            return False
        return any(
            inherits_chronology_model(ast.unparse(base), seen | {name})
            for base in classes[name].bases
        )

    return tree, {
        name: node
        for name, node in classes.items()
        if not name.startswith("_") and inherits_chronology_model(name)
    }


def _assert_complete_contract_partition(
    *, ast_names: set[str], runtime_names: set[str], cluster3_names: set[str]
) -> None:
    assert ast_names == runtime_names
    assert ast_names == _PRE_CLUSTER3_CONTRACT_MODEL_NAMES | cluster3_names
    assert _PRE_CLUSTER3_CONTRACT_MODEL_NAMES.isdisjoint(cluster3_names)


def _assert_module_model_denominator(
    *, observed: dict[str, set[str]], chronology_names: set[str]
) -> None:
    assert observed["polisyos.core.contracts.chronology"] == chronology_names
    assert all(
        not names
        for module_name, names in observed.items()
        if module_name != "polisyos.core.contracts.chronology"
    )


def _task31_production_paths_from_plan(product_root: Path) -> set[str]:
    plan = (
        product_root / "docs/superpowers/plans/2026-08-20-gy-n12-epoch-chronology-implementation.md"
    )
    text = plan.read_text("utf-8")
    task = text.split("### Task 3.1 —", 1)[1].split("**Commit boundary:**", 1)[0]
    return {
        match
        for match in re.findall(r"^- `([^`]+)`$", task, flags=re.MULTILINE)
        if match.startswith("src/polisyos/") and match.endswith(".py")
    }


def _cluster3_candidate_paths_from_git(product_root: Path) -> set[str]:
    repo_root = product_root.parent
    anchor_path = "policy-engine/src/polisyos/core/artifacts/signed_evidence.py"
    tracked = (
        subprocess.run(
            ["/usr/bin/git", "ls-files", "--error-unmatch", anchor_path],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )
    if tracked:
        introducing_commit = subprocess.run(
            [
                "/usr/bin/git",
                "log",
                "-1",
                "--format=%H",
                "--diff-filter=A",
                "--",
                anchor_path,
            ],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert introducing_commit
        output = subprocess.run(
            [
                "/usr/bin/git",
                "diff-tree",
                "--root",
                "--no-commit-id",
                "--name-only",
                "-r",
                introducing_commit,
            ],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    else:
        modified = subprocess.run(
            ["/usr/bin/git", "diff", "--name-only", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        untracked = subprocess.run(
            ["/usr/bin/git", "ls-files", "--others", "--exclude-standard"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        output = modified + untracked
    return {
        row.removeprefix("policy-engine/")
        for row in output.splitlines()
        if row.startswith("policy-engine/src/polisyos/") and row.endswith(".py")
    }


def _source_owned_model_or_codec_signals(source: str) -> set[tuple[str, str]]:
    tree = ast.parse(source)
    signals: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(
            ast.unparse(base).endswith(("BaseModel", "_ChronologyModel")) for base in node.bases
        ):
            signals.add(("model", node.name))
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            if name.endswith("_codec") and node.args:
                signals.add(("codec", ast.unparse(node.args[0])))
    return signals


def test_cluster3_module_and_model_censuses_reconcile_independently() -> None:
    """Nine modules and the complete 118-model contract stay in the denominator."""
    from polisyos.core.security.chronology_anchor import (
        C3_CONTRACT_MODEL_NAMES,
        C3_MODEL_REGISTRY,
        C3_MODULE_CLASSIFICATION,
        C3_PRODUCTION_MODULES,
    )

    _, ast_models = _chronology_contract_ast()
    ast_names = set(ast_models)
    contract_module = importlib.import_module("polisyos.core.contracts.chronology")
    runtime_names = {
        name
        for name, value in vars(contract_module).items()
        if not name.startswith("_")
        and isinstance(value, type)
        and value.__name__ == name
        and issubclass(value, BaseModel)
        and value.__module__ == contract_module.__name__
    }
    cluster3_names = set(C3_CONTRACT_MODEL_NAMES)

    assert len(C3_PRODUCTION_MODULES) == 9
    assert {
        module
        for module, classification in C3_MODULE_CLASSIFICATION.items()
        if classification == "model_owner"
    } == {
        "polisyos.core.artifacts.signed_evidence",
        "polisyos.core.contracts.chronology",
        "polisyos.core.security.anchor_lineage",
        "polisyos.core.security.chronology_anchor",
    }
    assert len(ast_names) == len(runtime_names) == 118
    assert len(cluster3_names) == len(C3_MODEL_REGISTRY) == 52
    assert cluster3_names == set(C3_MODEL_REGISTRY)
    _assert_complete_contract_partition(
        ast_names=ast_names,
        runtime_names=runtime_names,
        cluster3_names=cluster3_names,
    )
    assert {
        kind: sum(row.registry_class == kind for row in C3_MODEL_REGISTRY.values())
        for kind in ("canonical_codec", "persisted_transport", "failure_or_result")
    } == {
        "canonical_codec": 15,
        "persisted_transport": 17,
        "failure_or_result": 20,
    }
    observed_models: dict[str, set[str]] = {}
    for module_name in C3_PRODUCTION_MODULES:
        module = importlib.import_module(module_name)
        observed_models[module_name] = {
            value.__name__
            for name, value in vars(module).items()
            if not name.startswith("_")
            and isinstance(value, type)
            and value.__name__ == name
            and issubclass(value, BaseModel)
            and value.__module__ == module_name
        }
    _assert_module_model_denominator(
        observed=observed_models,
        chronology_names=runtime_names,
    )

    with pytest.raises(AssertionError):
        _assert_complete_contract_partition(
            ast_names=ast_names | {"InjectedDigestBearingModel"},
            runtime_names=runtime_names | {"InjectedDigestBearingModel"},
            cluster3_names=cluster3_names,
        )
    injected_modules = {name: set(models) for name, models in observed_models.items()}
    injected_modules["polisyos.runtime.quality.chronology_custody"].add("InjectedPersistedModel")
    with pytest.raises(AssertionError):
        _assert_module_model_denominator(
            observed=injected_modules,
            chronology_names=runtime_names,
        )


def test_cluster3_complete_source_denominator_is_plan_and_delta_derived() -> None:
    """The plan walk and Git-visible boundary independently yield nine modules."""
    from polisyos.core.security.chronology_anchor import (
        C3_MODULE_CLASSIFICATION,
        C3_PRODUCTION_MODULES,
    )

    product_root = Path(__file__).parents[4]
    declared = _task31_production_paths_from_plan(product_root)
    required_companion = {"src/polisyos/core/contracts/__init__.py"}
    candidate = _cluster3_candidate_paths_from_git(product_root)
    assert candidate == declared | required_companion
    module_paths = {
        row.removeprefix("src/")
        .removesuffix(".py")
        .replace("/", ".")
        .removesuffix(".__init__"): product_root / row
        for row in candidate
    }
    modules = set(module_paths)
    assert modules == set(C3_PRODUCTION_MODULES) == set(C3_MODULE_CLASSIFICATION)

    no_model_sources = {
        module: module_paths[module]
        for module, disposition in C3_MODULE_CLASSIFICATION.items()
        if disposition == "verified_no_cluster3_model"
    }
    for source_path in no_model_sources.values():
        assert _source_owned_model_or_codec_signals(source_path.read_text("utf-8")) == set()

    container = no_model_sources["polisyos.runtime.http.container"].read_text("utf-8")
    injected = container + "\nclass InjectedPersistedModel(BaseModel):\n    digest: Digest\n"
    assert _source_owned_model_or_codec_signals(injected) == {("model", "InjectedPersistedModel")}


def test_cluster3_hash_field_census_is_195_by_ast_and_runtime() -> None:
    """Every Digest and nested ArtifactRef identity has one generated rule."""
    from polisyos.core.security.chronology_anchor import (
        C3_CONTRACT_MODEL_NAMES,
        C3_HASH_FIELD_RULES,
    )

    _, all_ast_models = _chronology_contract_ast()
    ast_models = [all_ast_models[name] for name in C3_CONTRACT_MODEL_NAMES]
    ast_paths: set[str] = set()
    for model in ast_models:
        for statement in model.body:
            if not isinstance(statement, ast.AnnAssign) or not isinstance(
                statement.target, ast.Name
            ):
                continue
            annotation = ast.unparse(statement.annotation)
            if "ArtifactRef" in annotation:
                ast_paths.add(f"{model.name}.{statement.target.id}.artifact_id")
            elif "Digest" in annotation:
                ast_paths.add(f"{model.name}.{statement.target.id}")

    runtime_paths = set(C3_HASH_FIELD_RULES)
    runtime_field_total = sum(
        len(
            getattr(
                importlib.import_module("polisyos.core.contracts.chronology"), name
            ).model_fields
        )
        for name in C3_CONTRACT_MODEL_NAMES
    )
    assert runtime_field_total == 345
    assert len(ast_paths) == len(runtime_paths) == 195
    assert ast_paths == runtime_paths
    assert all(
        rule.self_field_exclusion == key and rule.persisting_owner and rule.exact_preimage
        for key, rule in C3_HASH_FIELD_RULES.items()
    )


def _c3_golden_payloads(tmp_path: Path, variant: int) -> dict[str, bytes]:
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.contracts import chronology as contract
    from tests._helpers.chronology_qualification import AppointedAnchorFixture

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime(2026, 1, 1, tzinfo=UTC)
            return value if tz is None else value.astimezone(tz)

    with (
        patch("polisyos.core.artifacts.manifest.datetime", _FrozenDateTime),
        patch("polisyos.core.artifacts.signing.datetime", _FrozenDateTime),
    ):
        fixture = AppointedAnchorFixture(tmp_path / str(variant))
        custody, readback, challenge, _ = fixture.build_retention(query_label=f"golden-{variant}")
    assert fixture.retained_package is not None
    graph = contract.AnchorRetentionObjectGraph.model_validate(
        from_canonical_bytes(
            contract._split_framed_records(fixture.retained_package.package_bytes)[0]
        )
    )
    key = contract.AnchorAcceptanceLineageKey(
        family="epoch",
        proof_domain="epoch",
        scope_ref=_digest("fixture-epoch-scope"),
        authority_purpose="publication",
    )
    lineage = fixture.lineage.resolve_lineage(key=key)
    return {
        "anchor-acceptance-statement.v1": (
            graph.acceptance_evidence.acceptance_statement_evidence.blob_bytes
        ),
        "anchor-acceptance-candidate.v1": graph.acceptance_evidence.acceptance_record_bytes,
        "anchor-lineage-append.v1": graph.acceptance_evidence.lineage_append_receipt_bytes,
        "anchor-acceptance-receipt.v1": graph.acceptance_evidence.acceptance_receipt_bytes,
        "anchor-retention-statement.v1": graph.retention_statement_bytes,
        "anchor-custody-receipt.v1": custody.statement_bytes,
        "anchor-readback-challenge.v1": challenge.statement_bytes,
        "anchor-readback-receipt.v1": readback.statement_bytes,
        "signed-artifact-evidence-record.v1": (
            graph.acceptance_evidence.acceptance_statement_evidence.persisted.record_bytes
        ),
        "anchor-acceptance-appointment.v1": graph.acceptance_appointment.statement_bytes,
        "anchor-acceptance-appointment-verification.v1": (
            graph.acceptance_appointment.verification_statement_bytes
        ),
        "anchor-holder-appointment.v1": graph.holder_appointment.statement_bytes,
        "anchor-holder-appointment-verification.v1": (
            graph.holder_appointment.verification_statement_bytes
        ),
        "anchor-acceptance-trust-snapshot.v1": (graph.acceptance_appointment.trust_config_bytes),
        "anchor-holder-trust-snapshot.v1": graph.holder_appointment.trust_config_bytes,
        "anchor-acceptance-lineage-state.v1": lineage.statement_bytes,
        "anchor-retention-package.v1": fixture.retained_package.package_bytes,
    }


def test_all_seventeen_codecs_reproduce_zero_and_one_vectors(tmp_path: Path) -> None:
    """The codec, strict-model, and two-vector key sets remain bijective."""
    from polisyos.core.security.chronology_anchor import (
        C3_CANONICAL_CODECS,
        C3_MODEL_REGISTRY,
        parse_canonical_statement,
        semantic_content_hash,
    )

    expected = (
        {
            "anchor-acceptance-statement.v1": "sha256:99e71eedeb419500cb6854cc16c1f2eaab286305dacf98751f3b2880c0662152",
            "anchor-acceptance-candidate.v1": "sha256:7cdafb55e2f206cafadb7e5e58b3925877bc1c5b5bfb03cbc97e93cf8c79d776",
            "anchor-lineage-append.v1": "sha256:798fcf9fb53230acaa9e28d6ed1ac5a45fddeed0980680238fc7f80b3333481d",
            "anchor-acceptance-receipt.v1": "sha256:16d0bbeefb4c4355a498d89e9164f891ed39018a3771cea19e2cb0e3243e4bd8",
            "anchor-retention-statement.v1": "sha256:4afcb448620b85276c1176b36ae2e2b271ae9137d8b3f0729f960737529a848c",
            "anchor-custody-receipt.v1": "sha256:3038a5048308f186794bb2359287589ba20751aec868a497da4777a7ff644d8e",
            "anchor-readback-challenge.v1": "sha256:b60914d54b92ea966ee098eff716ff999d25c430539c0c5983685766a54a47a6",
            "anchor-readback-receipt.v1": "sha256:f234bcd2022843e01b5163a7e2336d86689c071f7a8b4f736995d06b359cb9c7",
            "signed-artifact-evidence-record.v1": "sha256:562aff24689161035dc02b6429e9ea1418e02c10a5f215639e76574a6b2e8da2",
            "anchor-acceptance-appointment.v1": "sha256:9dfed1c01b4225cd3b4045b350628a878724120c841a462ec9e20d01e2216fb9",
            "anchor-acceptance-appointment-verification.v1": "sha256:b5dbd8ef4770e58c50e1879ad8570de687381c85f40d7ad64f36b7db48ccf67a",
            "anchor-holder-appointment.v1": "sha256:13fccc82a10560b10ce9a1d7a422e15a5609e54d00ed85e06e75d972f990cb66",
            "anchor-holder-appointment-verification.v1": "sha256:9878d51558e4c9939b4686fcfbd72e9cd59ff874d743263b118a89df7ab8a252",
            "anchor-acceptance-trust-snapshot.v1": "sha256:ed0038aee1f0922e60ddc3387e439b726ac996a315ac335d02709f1a5a7e62f6",
            "anchor-holder-trust-snapshot.v1": "sha256:837238c76fa06022bf061670285e11eb0cf31d355ff86dbcca0537b5e0cfdd1f",
            "anchor-acceptance-lineage-state.v1": "sha256:3e48de6d6dfc4b6becde639f81b945a09a9c3c0fd1fcc2dd16de3c850b61086b",
            "anchor-retention-package.v1": "sha256:8004363c7ab15932aadf688365711141032602f7a81a32f010b46cafb2ea013b",
        },
        {
            "anchor-acceptance-statement.v1": "sha256:853c92f7318f44b2542ac20cfc0c5b72fe2e11a5d9e6db9ef3ac841b3794b9ea",
            "anchor-acceptance-candidate.v1": "sha256:ff70d7aff23d4f5bd94b968bdca3eed139e7706105f49795bc95ae785f282084",
            "anchor-lineage-append.v1": "sha256:17b693fa9fa9e8e38ae9ab7eaff26ef39229c7ca54c7d9bc75ad1e3b16803b51",
            "anchor-acceptance-receipt.v1": "sha256:aa509f7067051deb4ecf7dbe0fe3e2985874ef9b088ea2cf99a6e53b99ca223a",
            "anchor-retention-statement.v1": "sha256:6964b2c0f37f7cbffe17caf3640e74d8581673d1ecaed6411852d5a2d9450bf3",
            "anchor-custody-receipt.v1": "sha256:334b9ad989f55e4f983deb38451ceed882691740104b0d38ecd14d8e24dd0ddb",
            "anchor-readback-challenge.v1": "sha256:aa91c859e69525aa986a5e7ce1cf65bbfd04294e26049fb1dd388325c9ed9208",
            "anchor-readback-receipt.v1": "sha256:eb07c00a8ab9104850f0208f7d2eeef8b3e024745afdedff830c4745b5b52d55",
            "signed-artifact-evidence-record.v1": "sha256:487d9a9b344761a2b46bb1a25cad06695dc59dfc3ec491ba2f379624e60b12f4",
            "anchor-acceptance-appointment.v1": "sha256:9dfed1c01b4225cd3b4045b350628a878724120c841a462ec9e20d01e2216fb9",
            "anchor-acceptance-appointment-verification.v1": "sha256:b5dbd8ef4770e58c50e1879ad8570de687381c85f40d7ad64f36b7db48ccf67a",
            "anchor-holder-appointment.v1": "sha256:13fccc82a10560b10ce9a1d7a422e15a5609e54d00ed85e06e75d972f990cb66",
            "anchor-holder-appointment-verification.v1": "sha256:9878d51558e4c9939b4686fcfbd72e9cd59ff874d743263b118a89df7ab8a252",
            "anchor-acceptance-trust-snapshot.v1": "sha256:ed0038aee1f0922e60ddc3387e439b726ac996a315ac335d02709f1a5a7e62f6",
            "anchor-holder-trust-snapshot.v1": "sha256:837238c76fa06022bf061670285e11eb0cf31d355ff86dbcca0537b5e0cfdd1f",
            "anchor-acceptance-lineage-state.v1": "sha256:480a468c7df9c110c04a3630f9974ee06e17942651fe7451ce6e76d03ab3de46",
            "anchor-retention-package.v1": "sha256:eac9092f1ad6beb7f9a3290d3f92b7c46337bbe6aade6b5e489cd05f4208d61d",
        },
    )
    vectors = tuple(_c3_golden_payloads(tmp_path, variant) for variant in (0, 1))
    assert set(vectors[0]) == set(vectors[1]) == set(C3_CANONICAL_CODECS)
    canonical_models = {
        row.model for row in C3_MODEL_REGISTRY.values() if row.registry_class == "canonical_codec"
    }
    assert canonical_models == {
        codec.model.__name__ for codec in C3_CANONICAL_CODECS.values() if codec.model is not None
    }
    for codec_key, codec in C3_CANONICAL_CODECS.items():
        hashes = []
        for variant, payloads in enumerate(vectors):
            payload = payloads[codec_key]
            if codec.model is not None:
                assert parse_canonical_statement(payload, codec.model)
            hashes.append(semantic_content_hash(codec_key, payload))
            assert hashes[-1] == expected[variant][codec_key]
        assert all(value.startswith("sha256:") for value in hashes)


def test_authentic_old_anchor_passes_own_query_and_fails_later_query(
    tmp_path: Path,
) -> None:
    """Authenticity at one query cannot satisfy a later requested query."""
    from tests._helpers.chronology_qualification import AppointedAnchorFixture

    fixture = AppointedAnchorFixture(tmp_path)
    receipt, evidence, lineage, verified = fixture.build_acceptance(query_label="historical")
    _, _, _, later_verified = fixture.build_acceptance(query_label="later")
    from polisyos.core.security.chronology_anchor import (
        ExactAnchorAcceptanceReceiptVerifier,
    )

    replay = ExactAnchorAcceptanceReceiptVerifier(fixture.verifier)
    original = replay.verify(
        receipt=receipt,
        appointment=fixture.acceptance_appointment,
        evidence=evidence,
        lineage=lineage,
        requested_query_context_ref=verified.requested_query_context_ref,
    )
    later = replay.verify(
        receipt=receipt,
        appointment=fixture.acceptance_appointment,
        evidence=evidence,
        lineage=lineage,
        requested_query_context_ref=_digest("later-query"),
    )
    from polisyos.core.contracts.chronology import (
        AcceptanceRejectedNonReceipt,
        VerifiedAnchorAcceptance,
    )

    assert isinstance(original, VerifiedAnchorAcceptance)
    assert original.lineage_position == "historical_for_exact_query"
    assert later_verified.lineage_position == "current"
    assert isinstance(later, AcceptanceRejectedNonReceipt)
    assert later.code == "anchor_query_or_lineage_mismatch"


def test_holder_readback_is_independent_of_writer_store_and_binds_package(
    tmp_path: Path,
) -> None:
    """Holder-returned bytes verify without CAS access and reject byte mutation."""
    from tests._helpers.chronology_qualification import AppointedAnchorFixture

    fixture = AppointedAnchorFixture(tmp_path)
    custody, readback, challenge, verified = fixture.build_retention()
    fixture.store.root.rename(tmp_path / "writer-cas-detached")
    from polisyos.core.security.chronology_anchor import ExactAnchorHolderReceiptVerifier

    fresh = ExactAnchorHolderReceiptVerifier(fixture.verifier)
    independent = fresh.verify_retention_and_readback(
        retention=custody,
        readback=readback,
        challenge=challenge,
        appointment=fixture.holder_appointment,
    )
    mutated = fresh.verify_retention_and_readback(
        retention=custody,
        readback=readback.model_copy(
            update={"package_bytes": readback.package_bytes + b"mutation"}
        ),
        challenge=challenge,
        appointment=fixture.holder_appointment,
    )
    from polisyos.core.contracts.chronology import (
        RetentionRejectedNonReceipt,
        VerifiedAnchorRetention,
    )

    assert isinstance(verified, VerifiedAnchorRetention)
    assert isinstance(independent, VerifiedAnchorRetention)
    assert isinstance(mutated, RetentionRejectedNonReceipt)
    assert mutated.code == "anchor_package_mismatch"


def test_holder_rejects_resigned_package_with_mutated_acceptance_graph(
    tmp_path: Path,
) -> None:
    """A fresh holder signature cannot bless an internally inconsistent acceptance graph."""
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.contracts import chronology as contract
    from polisyos.core.security.chronology_anchor import (
        ExactAnchorHolderReceiptVerifier,
        build_retention_package,
        canonical_statement_bytes,
        verify_retention_package,
    )
    from tests._helpers.chronology_qualification import AppointedAnchorFixture

    fixture = AppointedAnchorFixture(tmp_path)
    _, _, _, baseline = fixture.build_retention()
    assert isinstance(baseline, contract.VerifiedAnchorRetention)
    assert fixture.retained_package is not None
    graph = contract.AnchorRetentionObjectGraph.model_validate(
        from_canonical_bytes(
            contract._split_framed_records(fixture.retained_package.package_bytes)[0]
        )
    )
    append = contract.AnchorAcceptanceAppendSuccessStatement.model_validate(
        from_canonical_bytes(
            contract._split_framed_records(graph.acceptance_evidence.lineage_append_receipt_bytes)[
                0
            ]
        )
    )
    mutated_graph = graph.model_copy(
        update={
            "acceptance_evidence": graph.acceptance_evidence.model_copy(
                update={
                    "lineage_append_receipt_bytes": canonical_statement_bytes(
                        append.model_copy(
                            update={"resulting_state_content_hash": _digest("forged-state")}
                        )
                    )
                }
            )
        }
    )
    mutated_package = build_retention_package(mutated_graph)
    assert verify_retention_package(mutated_package) is True
    custody = fixture.retain_package(mutated_package)
    retention_statement = contract.AnchorRetentionStatement.model_validate(
        from_canonical_bytes(
            contract._split_framed_records(mutated_graph.retention_statement_bytes)[0]
        )
    )
    challenge = fixture.challenge_repository.persist(
        contract.AnchorReadbackChallengeStatement(
            family="epoch",
            proof_domain=retention_statement.proof_domain,
            authority_purpose=retention_statement.authority_purpose,
            lineage_key=contract.AnchorAcceptanceLineageKey(
                family="epoch",
                proof_domain=retention_statement.proof_domain,
                scope_ref=_digest("fixture-epoch-scope"),
                authority_purpose=retention_statement.authority_purpose,
            ),
            holder_appointment_ref=fixture.holder_appointment.appointment_ref,
            package_ref=mutated_package.package_ref,
            expected_package_content_hash=mutated_package.package_content_hash,
            custody_receipt_record_ref=custody.receipt_record_ref,
            custody_receipt_record_raw_bytes_hash=custody.receipt_record_raw_bytes_hash,
            expected_object_version_ref="version-1",
            requested_query_context_ref=retention_statement.requested_query_context_ref,
        )
    )
    readback = fixture.readback_challenge(challenge)

    result = ExactAnchorHolderReceiptVerifier(fixture.verifier).verify_retention_and_readback(
        retention=custody,
        readback=readback,
        challenge=challenge,
        appointment=fixture.holder_appointment,
    )

    assert isinstance(result, contract.RetentionRejectedNonReceipt)
    assert result.code == "anchor_readback_mismatch"


def test_holder_rejects_challenge_lineage_redirect_with_fresh_readback(
    tmp_path: Path,
) -> None:
    """An authentic holder response cannot redirect a package to another lineage key."""
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.contracts import chronology as contract
    from polisyos.core.security.chronology_anchor import ExactAnchorHolderReceiptVerifier
    from tests._helpers.chronology_qualification import AppointedAnchorFixture

    fixture = AppointedAnchorFixture(tmp_path)
    custody, _, challenge, _ = fixture.build_retention()
    statement = contract.AnchorReadbackChallengeStatement.model_validate(
        from_canonical_bytes(contract._split_framed_records(challenge.statement_bytes)[0])
    )
    redirected = fixture.challenge_repository.persist(
        statement.model_copy(
            update={
                "lineage_key": statement.lineage_key.model_copy(
                    update={
                        "scope_ref": _digest("another-scope"),
                        "authority_purpose": "another-purpose",
                    }
                )
            }
        )
    )
    readback = fixture.readback_challenge(redirected)

    result = ExactAnchorHolderReceiptVerifier(fixture.verifier).verify_retention_and_readback(
        retention=custody,
        readback=readback,
        challenge=redirected,
        appointment=fixture.holder_appointment,
    )

    assert isinstance(result, contract.RetentionRejectedNonReceipt)
    assert result.code == "anchor_readback_mismatch"


def test_acceptance_wrapper_fields_cannot_override_the_signed_receipt(
    tmp_path: Path,
) -> None:
    """Authentic signed bytes cannot bless a caller-mutated wrapper identity."""
    from tests._helpers.chronology_qualification import AppointedAnchorFixture

    fixture = AppointedAnchorFixture(tmp_path)
    receipt, evidence, lineage, verified = fixture.build_acceptance()
    from polisyos.core.security.chronology_anchor import (
        ExactAnchorAcceptanceReceiptVerifier,
    )

    replay = ExactAnchorAcceptanceReceiptVerifier(fixture.verifier)
    mutated = replay.verify(
        receipt=receipt.model_copy(
            update={"receipt_record_content_hash": _digest("caller-substitution")}
        ),
        appointment=fixture.acceptance_appointment,
        evidence=evidence,
        lineage=lineage,
        requested_query_context_ref=verified.requested_query_context_ref,
    )
    from polisyos.core.contracts.chronology import AcceptanceRejectedNonReceipt

    assert isinstance(mutated, AcceptanceRejectedNonReceipt)
    assert mutated.code == "anchor_query_or_lineage_mismatch"


def test_signed_receipt_with_arbitrary_lineage_key_ref_is_rejected(
    tmp_path: Path,
) -> None:
    """A valid signature cannot replace the owner-derived lineage-key preimage."""
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.contracts import chronology as contract
    from polisyos.core.security.chronology_anchor import (
        ExactAnchorAcceptanceReceiptVerifier,
        canonical_statement_bytes,
        semantic_content_hash,
    )
    from tests._helpers.chronology_qualification import AppointedAnchorFixture

    fixture = AppointedAnchorFixture(tmp_path)
    receipt, evidence, lineage, verified = fixture.build_acceptance()
    statement = contract.AnchorAcceptanceReceiptStatement.model_validate(
        from_canonical_bytes(contract._split_framed_records(receipt.statement_bytes)[0])
    ).model_copy(update={"lineage_key_ref": _digest("arbitrary-lineage-key")})
    statement_bytes = canonical_statement_bytes(statement)
    signed = fixture._issue(statement_bytes, kind="fixture.acceptance_receipt")
    signed_record = contract.SignedArtifactEvidenceRecord.model_validate(
        from_canonical_bytes(contract._split_framed_records(signed.persisted.record_bytes)[0])
    )
    substituted_receipt = contract.AnchorAcceptanceReceipt(
        receipt_record_ref=signed_record.artifact_ref,
        receipt_record_content_hash=semantic_content_hash(
            "anchor-acceptance-receipt.v1", statement_bytes
        ),
        statement_bytes=statement_bytes,
        receipt_record_bytes=statement_bytes,
        signed_receipt_evidence=signed,
    )
    substituted_evidence = evidence.model_copy(
        update={
            "acceptance_receipt_bytes": statement_bytes,
            "acceptance_receipt_signed_evidence": signed,
        }
    )
    result = ExactAnchorAcceptanceReceiptVerifier(fixture.verifier).verify(
        receipt=substituted_receipt,
        appointment=fixture.acceptance_appointment,
        evidence=substituted_evidence,
        lineage=lineage,
        requested_query_context_ref=verified.requested_query_context_ref,
    )

    assert isinstance(result, contract.AcceptanceRejectedNonReceipt)
    assert result.code == "anchor_query_or_lineage_mismatch"


def test_appointment_wrapper_cannot_override_exact_verification_evidence(
    tmp_path: Path,
) -> None:
    """An appointment ref mutation fails while every signed byte stays authentic."""
    from tests._helpers.chronology_qualification import AppointedAnchorFixture

    fixture = AppointedAnchorFixture(tmp_path)
    receipt, evidence, lineage, verified = fixture.build_acceptance()
    from polisyos.core.security.chronology_anchor import (
        ExactAnchorAcceptanceReceiptVerifier,
    )

    mutated = ExactAnchorAcceptanceReceiptVerifier(fixture.verifier).verify(
        receipt=receipt,
        appointment=fixture.acceptance_appointment.model_copy(
            update={"appointment_content_hash": _digest("different-appointment")}
        ),
        evidence=evidence,
        lineage=lineage,
        requested_query_context_ref=verified.requested_query_context_ref,
    )
    from polisyos.core.contracts.chronology import AcceptanceRejectedNonReceipt

    assert isinstance(mutated, AcceptanceRejectedNonReceipt)
    assert mutated.code == "anchor_signature_unverified"


def test_readback_nested_retention_receipt_cannot_be_substituted(
    tmp_path: Path,
) -> None:
    """The holder verifier binds the nested and separately supplied receipts."""
    from tests._helpers.chronology_qualification import AppointedAnchorFixture

    fixture = AppointedAnchorFixture(tmp_path)
    custody, readback, challenge, _ = fixture.build_retention()
    from polisyos.core.security.chronology_anchor import ExactAnchorHolderReceiptVerifier

    substituted = readback.model_copy(
        update={
            "retention_receipt": custody.model_copy(
                update={"receipt_record_raw_bytes_hash": _digest("other-custody")}
            )
        }
    )
    result = ExactAnchorHolderReceiptVerifier(fixture.verifier).verify_retention_and_readback(
        retention=custody,
        readback=substituted,
        challenge=challenge,
        appointment=fixture.holder_appointment,
    )
    from polisyos.core.contracts.chronology import RetentionRejectedNonReceipt

    assert isinstance(result, RetentionRejectedNonReceipt)
    assert result.code == "anchor_readback_mismatch"


def test_non_genesis_acceptance_derives_the_owner_prefix(
    tmp_path: Path,
) -> None:
    """A non-empty owner lineage cannot be represented as a genesis assertion."""
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.contracts import chronology as contract
    from tests._helpers.chronology_qualification import AppointedAnchorFixture

    fixture = AppointedAnchorFixture(tmp_path)
    first_receipt, _, _, first = fixture.build_acceptance(query_label="first")
    _, second_evidence, _, second = fixture.build_acceptance(query_label="second")
    statement = contract.AnchorAcceptanceStatement.model_validate(
        from_canonical_bytes(
            contract._split_framed_records(
                second_evidence.acceptance_statement_evidence.blob_bytes
            )[0]
        )
    )

    assert statement.prior_acceptance_record_refs == (first.acceptance_record_ref,)
    assert len(statement.derived_prior_prefixes) == 1
    assert statement.derived_prior_prefixes[0].acceptance_record_ref == (
        first.acceptance_record_ref
    )
    assert second.lineage_position == "current"
    assert first_receipt.receipt_record_ref != second.acceptance_receipt_record_ref
