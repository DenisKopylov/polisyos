"""NormPack impact contracts and analysis owned by Lex legal evaluation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.contracts import ComplianceIssue, IssueSeverity
from polisyos.core.governance import LegalPass, PassContext, SafetyPass, ValidationProfile
from polisyos.ir import NormPack, RuleType, stable_world_id_from_canon
from polisyos.lex.normpack.diff import NormChangeType, NormDiff, diff_norm_packs


class ComplianceTransition(str, Enum):
    """How a compliance issue changed after a norm-pack mutation."""

    PASS_TO_FAIL = "pass_to_fail"
    FAIL_TO_PASS = "fail_to_pass"
    NEW_ISSUE = "new_issue"
    RESOLVED_ISSUE = "resolved_issue"
    SEVERITY_CHANGE = "severity_change"
    UNCHANGED = "unchanged"


class ComplianceDelta(BaseModel):
    """Transition record for one compliance issue across two policy states."""

    model_config = ConfigDict(extra="forbid")

    norm_id: str
    pass_id: str
    fingerprint: str
    transition: ComplianceTransition
    old_issue: ComplianceIssue | None = None
    new_issue: ComplianceIssue | None = None


class AffectedKPI(BaseModel):
    """Candidate impact topic inferred heuristically from changed norm types."""

    model_config = ConfigDict(extra="forbid")

    kpi_id: str
    description: str
    affected_norm_ids: list[str] = Field(default_factory=list)
    estimated_direction: str = "unknown"


class NormImpactReport(BaseModel):
    """Combined norm diff and compliance impact report for what-if analysis."""

    model_config = ConfigDict(extra="forbid")

    ARTIFACT_KIND: ClassVar[str] = "lex.norm_impact_report"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.lex.NormImpactReport"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.1"
    LEGACY_ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_REQUIRED_FIELDS_BY_SCHEMA_VERSION: ClassVar[dict[str, tuple[str, ...]]] = {
        "1.1": ("norm_diff_ref", "norm_diff_artifact_ref")
    }

    schema_version: Literal["1.0", "1.1"] = "1.0"
    report_id: str
    old_pack_id: str
    new_pack_id: str
    jurisdiction: str

    norm_diff_ref: str | None = None
    norm_diff_artifact_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    norms_added: int = 0
    norms_removed: int = 0
    norms_modified: int = 0

    compliance_deltas: list[ComplianceDelta] = Field(default_factory=list)
    new_blockers: int = 0
    resolved_blockers: int = 0
    new_warnings: int = 0
    resolved_warnings: int = 0
    severity_changed: int = 0

    affected_kpis: list[AffectedKPI] = Field(default_factory=list)
    passes_executed: list[str] = Field(default_factory=list)

    decision_packet_ref: str | None = None
    cas_artifact_id: str | None = None
    cas_artifact_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_selected_artifact_refs(self) -> NormImpactReport:
        if self.schema_version == "1.0":
            if self.norm_diff_artifact_ref is not None or self.cas_artifact_ref is not None:
                raise ValueError("legacy_report_cannot_claim_selected_artifact_refs")
            return self
        diff_ref = self.norm_diff_artifact_ref
        if (
            diff_ref is None
            or diff_ref.manifest_profile_sha256 is None
            or diff_ref.kind != NormDiff.ARTIFACT_KIND
            or diff_ref.media_type != NormDiff.ARTIFACT_MEDIA_TYPE
            or self.norm_diff_ref != str(diff_ref.artifact_id)
        ):
            raise ValueError("selected_norm_diff_reference_required")
        if self.cas_artifact_id is not None and self.cas_artifact_ref is None:
            raise ValueError("selected_report_reference_required")
        if self.cas_artifact_ref is not None and (
            self.cas_artifact_ref.manifest_profile_sha256 is None
            or self.cas_artifact_ref.kind != self.ARTIFACT_KIND
            or self.cas_artifact_ref.media_type != self.ARTIFACT_MEDIA_TYPE
            or self.cas_artifact_id != str(self.cas_artifact_ref.artifact_id)
        ):
            raise ValueError("selected_report_reference_mismatch")
        return self

    @property
    def has_new_blockers(self) -> bool:
        return self.new_blockers > 0


class NormImpactAnalyzer:
    """Run governance passes over two norm packs and summarize the delta."""

    DEFAULT_PASSES: tuple[str, ...] = ("legal", "safety")

    def __init__(
        self,
        cas: FileSystemCAS,
        *,
        profile: ValidationProfile | None = None,
        passes: tuple[str, ...] | None = None,
        legal_backend: object | None = None,
        report_schema_version: Literal["1.0", "1.1"] = "1.0",
    ) -> None:
        """Configure comparison, pass selection, backend, and persisted schema.

        Args:
            cas: Store used for diff and report artifacts.
            profile: Governance validation profile, defaulting to strict.
            passes: Ordered pass IDs, deduplicated at admission; ``None`` uses defaults.
            legal_backend: Existing rule backend, or ``None`` for the legacy stub.
            report_schema_version: Persisted version. Omission retains limited ``1.0``;
                select ``1.1`` only after readers are ready.

        Unpersisted comparisons return the legacy unbound shape because no view
        has been issued. Backend configuration is not an authority assertion.
        """
        self._cas = cas
        self._profile = profile or ValidationProfile.strict()
        self._pass_ids = self.DEFAULT_PASSES if passes is None else tuple(passes)
        for pass_id in self._pass_ids:
            if pass_id not in self.DEFAULT_PASSES:
                raise ValueError(f"Unsupported impact pass: {pass_id!r}")
        # A plan identifies checks, not multiplicities. Preserve the first
        # occurrence so repeated references cannot inflate compliance deltas.
        self._pass_ids = tuple(dict.fromkeys(self._pass_ids))
        self._legal_backend = legal_backend
        if report_schema_version not in ("1.0", "1.1"):
            raise ValueError("Unsupported impact report schema version")
        self._report_schema_version = report_schema_version

    def analyze(
        self,
        old_pack: NormPack,
        new_pack: NormPack,
        *,
        context: dict[str, Any] | None = None,
        decision_packet_ref: str | None = None,
        persist: bool = True,
    ) -> NormImpactReport:
        """Compare two NormPacks, run governance passes, and persist an impact report.

        Args:
            old_pack: Baseline NormPack before a proposed mutation.
            new_pack: Candidate NormPack after mutation.
            context: Optional pass context state such as IR payloads or registry bundles.
            decision_packet_ref: Optional governance artifact reference to attach to the report.
            persist: Whether to persist ``NormDiff`` and ``NormImpactReport`` artifacts in CAS.

        Returns:
            Impact report with norm changes, compliance deltas, candidate impact topics,
            backend limitations, and optional CAS artifact references.
        """
        if (
            persist
            and self._report_schema_version == "1.1"
            and old_pack.jurisdiction != new_pack.jurisdiction
        ):
            raise ValueError("selected_report_jurisdiction_mismatch")
        runtime_context = context or {}
        diff = diff_norm_packs(old_pack, new_pack)
        old_issues = self._run_passes(old_pack, runtime_context)
        new_issues = self._run_passes(new_pack, runtime_context)
        deltas = self._compute_compliance_delta(old_issues, new_issues, diff)
        affected_kpis = self._infer_affected_kpis(diff)

        if "legal" not in self._pass_ids:
            legal_backend = "not_run"
            legal_evaluation_scope = "not_run"
        elif self._legal_backend is None:
            legal_backend = "stub"
            legal_evaluation_scope = "not_implemented"
        elif isinstance(self._legal_backend, str):
            legal_backend = self._legal_backend
            if legal_backend == "stub":
                legal_evaluation_scope = "not_implemented"
            elif legal_backend == "expr_ast":
                legal_evaluation_scope = "selected_backend_rules_only"
            else:
                legal_evaluation_scope = "backend_semantics_not_established"
        else:
            # A custom backend's self-reported name is not proof of its semantics.
            legal_backend = "custom"
            legal_evaluation_scope = "backend_semantics_not_established"

        # The new version describes an issued view and is only written after
        # the diff's exact selected profile exists. In-memory-only results keep
        # the legacy, explicitly unbound shape until an artifact is issued.
        diff_ref = self._persist_diff(diff) if persist else None
        report_version: Literal["1.0", "1.1"] = self._report_schema_version if persist else "1.0"
        report = NormImpactReport(
            schema_version=report_version,
            report_id=self._generate_report_id(old_pack, new_pack, diff),
            norm_diff_ref=str(diff_ref.artifact_id) if diff_ref is not None else None,
            norm_diff_artifact_ref=diff_ref if report_version == "1.1" else None,
            old_pack_id=old_pack.pack_id,
            new_pack_id=new_pack.pack_id,
            jurisdiction=old_pack.jurisdiction,
            norms_added=diff.added_count,
            norms_removed=diff.removed_count,
            norms_modified=diff.modified_count,
            compliance_deltas=deltas,
            new_blockers=_count_transition(
                deltas, ComplianceTransition.PASS_TO_FAIL, IssueSeverity.BLOCKER
            )
            + _count_transition(deltas, ComplianceTransition.NEW_ISSUE, IssueSeverity.BLOCKER),
            resolved_blockers=_count_transition(
                deltas, ComplianceTransition.FAIL_TO_PASS, IssueSeverity.BLOCKER
            )
            + _count_transition(deltas, ComplianceTransition.RESOLVED_ISSUE, IssueSeverity.BLOCKER),
            new_warnings=_count_transition(
                deltas, ComplianceTransition.PASS_TO_FAIL, IssueSeverity.WARNING
            )
            + _count_transition(deltas, ComplianceTransition.NEW_ISSUE, IssueSeverity.WARNING),
            resolved_warnings=_count_transition(
                deltas, ComplianceTransition.FAIL_TO_PASS, IssueSeverity.WARNING
            )
            + _count_transition(deltas, ComplianceTransition.RESOLVED_ISSUE, IssueSeverity.WARNING),
            severity_changed=sum(
                1 for delta in deltas if delta.transition == ComplianceTransition.SEVERITY_CHANGE
            ),
            affected_kpis=affected_kpis,
            passes_executed=list(self._pass_ids),
            decision_packet_ref=decision_packet_ref,
            metadata={
                "old_issues_total": len(old_issues),
                "new_issues_total": len(new_issues),
                "profile": self._profile.level.value,
                "legal_backend": legal_backend,
                "legal_evaluation_scope": legal_evaluation_scope,
                "comparison_context_binding": "not_established",
                "declared_old_jurisdiction": old_pack.jurisdiction,
                "declared_new_jurisdiction": new_pack.jurisdiction,
            },
        )

        if persist:
            report_ref = self._persist_report(report)
            return NormImpactReport.model_validate(
                report.model_dump(mode="python")
                | {
                    "cas_artifact_id": str(report_ref.artifact_id),
                    "cas_artifact_ref": report_ref if report_version == "1.1" else None,
                }
            )
        return report

    def _run_passes(self, norm_pack: NormPack, context: dict[str, Any]) -> list[ComplianceIssue]:
        issues: list[ComplianceIssue] = []
        pass_context = PassContext(
            ir=context.get("ir"),
            state={**context, "norm_pack": norm_pack},
            registry_bundle=context.get("registry_bundle"),
            profile=self._profile,
            run_id=f"impact-{norm_pack.pack_id[:20]}",
        )

        for pass_id in self._pass_ids:
            if pass_id == "legal":
                issues.extend(
                    LegalPass(backend=self._legal_backend, enabled=True).validate(pass_context)
                )
            elif pass_id == "safety":
                issues.extend(SafetyPass().validate(pass_context))
        return issues

    @staticmethod
    def _compute_compliance_delta(
        old_issues: list[ComplianceIssue],
        new_issues: list[ComplianceIssue],
        norm_diff: NormDiff,
    ) -> list[ComplianceDelta]:
        changed_norm_ids = set(norm_diff.affected_norm_ids)
        old_grouped = _group_issues(old_issues)
        new_grouped = _group_issues(new_issues)
        all_keys = sorted(set(old_grouped) | set(new_grouped))

        deltas: list[ComplianceDelta] = []
        for key in all_keys:
            old_bucket = list(old_grouped.get(key, []))
            new_bucket = list(new_grouped.get(key, []))
            max_len = max(len(old_bucket), len(new_bucket))

            for idx in range(max_len):
                old_issue = old_bucket[idx] if idx < len(old_bucket) else None
                new_issue = new_bucket[idx] if idx < len(new_bucket) else None
                norm_id = key[2]
                fingerprint = _issue_fingerprint(
                    old_issue if old_issue is not None else new_issue,
                    norm_id=norm_id,
                )

                if old_issue is None and new_issue is not None:
                    transition = (
                        ComplianceTransition.NEW_ISSUE
                        if norm_id in changed_norm_ids
                        else ComplianceTransition.PASS_TO_FAIL
                    )
                    deltas.append(
                        ComplianceDelta(
                            norm_id=norm_id,
                            pass_id=new_issue.pass_id,
                            fingerprint=fingerprint,
                            transition=transition,
                            new_issue=new_issue,
                        )
                    )
                    continue

                if old_issue is not None and new_issue is None:
                    transition = (
                        ComplianceTransition.RESOLVED_ISSUE
                        if norm_id in changed_norm_ids
                        else ComplianceTransition.FAIL_TO_PASS
                    )
                    deltas.append(
                        ComplianceDelta(
                            norm_id=norm_id,
                            pass_id=old_issue.pass_id,
                            fingerprint=fingerprint,
                            transition=transition,
                            old_issue=old_issue,
                        )
                    )
                    continue

                if old_issue is None or new_issue is None:
                    continue
                if old_issue.severity == new_issue.severity:
                    continue
                deltas.append(
                    ComplianceDelta(
                        norm_id=norm_id,
                        pass_id=new_issue.pass_id,
                        fingerprint=fingerprint,
                        transition=ComplianceTransition.SEVERITY_CHANGE,
                        old_issue=old_issue,
                        new_issue=new_issue,
                    )
                )
        return deltas

    def _infer_affected_kpis(self, norm_diff: NormDiff) -> list[AffectedKPI]:
        return _infer_candidate_topics_v1_1(norm_diff)

    def _persist_diff(self, diff: NormDiff) -> ArtifactRef:
        return self._cas.put_json(
            diff.model_dump(mode="json"),
            PutOptions(
                kind=NormDiff.ARTIFACT_KIND,
                media_type=NormDiff.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=NormDiff.ARTIFACT_SCHEMA_NAME,
                    version=NormDiff.ARTIFACT_SCHEMA_VERSION,
                ),
            ),
            return_selected_profile=True,
        )

    def _persist_report(self, report: NormImpactReport) -> ArtifactRef:
        selected_diff = report.norm_diff_artifact_ref
        inputs = (
            [input_ref_from_artifact_ref(selected_diff, role="norm_diff")]
            if selected_diff is not None
            else []
        )
        return self._cas.put_json(
            report.model_dump(mode="json"),
            PutOptions(
                kind=report.ARTIFACT_KIND,
                media_type=report.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(name=report.ARTIFACT_SCHEMA_NAME, version=report.schema_version),
                inputs=inputs,
            ),
            return_selected_profile=report.schema_version == "1.1",
        )

    def _generate_report_id(
        self, old_pack: NormPack, new_pack: NormPack, norm_diff: NormDiff
    ) -> str:
        return _impact_report_id(old_pack.pack_id, new_pack.pack_id, norm_diff, self._pass_ids)


def _impact_report_id(
    old_pack_id: str, new_pack_id: str, norm_diff: NormDiff, passes: tuple[str, ...]
) -> str:
    return stable_world_id_from_canon(
        prefix="lex.impact_report",
        payload={
            "old_pack_id": old_pack_id,
            "new_pack_id": new_pack_id,
            "diff_stats": {
                "added": norm_diff.added_count,
                "removed": norm_diff.removed_count,
                "modified": norm_diff.modified_count,
            },
            "passes": list(passes),
        },
    )


def _infer_candidate_topics_v1_1(norm_diff: NormDiff) -> list[AffectedKPI]:
    aggregate: dict[str, AffectedKPI] = {}
    for change in norm_diff.changes:
        if change.change_type == NormChangeType.UNCHANGED:
            continue
        rule = change.new_rule if change.new_rule is not None else change.old_rule
        if rule is None:
            continue

        if rule.rule_type == RuleType.OBLIGATION:
            kpi_id = "compliance_cost"
            description = (
                "Candidate topic inferred from an obligation rule type; no cost or effect "
                "has been measured."
            )
        elif rule.rule_type == RuleType.PROHIBITION:
            kpi_id = "operational_restrictions"
            description = (
                "Candidate topic inferred from a prohibition rule type; no restriction or "
                "effect has been measured."
            )
        else:
            kpi_id = "regulatory_flexibility"
            description = (
                "Candidate topic inferred from a permission rule type; no flexibility or "
                "effect has been measured."
            )

        if kpi_id not in aggregate:
            aggregate[kpi_id] = AffectedKPI(kpi_id=kpi_id, description=description)
        aggregate[kpi_id].affected_norm_ids.append(change.norm_id)

    for item in aggregate.values():
        item.affected_norm_ids = sorted(set(item.affected_norm_ids))
    return sorted(aggregate.values(), key=lambda item: item.kpi_id)


@dataclass(frozen=True)
class NormImpactReadResult:
    """A decoded report and diff with a bounded view-binding disposition.

    This is a read result, not an authority token or proof of source-law
    authenticity, currentness, complete context, or issuer identity.

    Attributes:
        report: Decoded report read from the requested artifact view.
        diff: Decoded norm diff, or ``None`` if a legacy report lacks a diff.
        diff_binding: Exact selected view or the explicit legacy limitation.
    """

    report: NormImpactReport
    diff: NormDiff | None
    diff_binding: Literal["exact_selected", "legacy_unbound", "legacy_absent"]


def load_norm_impact_report(
    cas: FileSystemCAS,
    report_ref: ArtifactRef | ArtifactID | str,
) -> NormImpactReadResult:
    """Read a report and resolve its bound diff or an explicitly limited legacy view.

    Version 1.1 requires the caller's exact report profile and reconciles the
    report's selected diff ref against its manifest input before reading the
    diff. Version 1.1 also reconciles internally derivable claims against the
    diff and reported delta records. Version 1.0 stays explicitly limited.

    Args:
        cas: Store that owns the selected report and diff artifacts.
        report_ref: Selected report view, or a legacy 1.0 artifact ID.

    Returns:
        NormImpactReadResult: The decoded data and its view-binding disposition.

    Raises:
        ValueError: If a selected reference, schema, manifest edge or payload
            cannot be verified or reconciled.
        OSError: If a required artifact cannot be read.
    """
    report = validate_core_model_json_artifact(NormImpactReport, cas, report_ref)
    if report.schema_version == "1.1":
        if not isinstance(report_ref, ArtifactRef) or report_ref.manifest_profile_sha256 is None:
            raise ValueError("selected_report_profile_required")
        if report.cas_artifact_id is not None or report.cas_artifact_ref is not None:
            raise ValueError("persisted_report_cannot_self_reference")
        selected_diff = report.norm_diff_artifact_ref
        if selected_diff is None:
            raise ValueError("selected_norm_diff_reference_required")
        manifest = cas.get_manifest(report_ref)
        expected_edge = input_ref_from_artifact_ref(selected_diff, role="norm_diff")
        if manifest.inputs != [expected_edge]:
            raise ValueError("report_norm_diff_input_mismatch")
        diff = validate_core_model_json_artifact(NormDiff, cas, selected_diff)
        _reconcile_selected_report(report, diff)
        binding: Literal["exact_selected", "legacy_unbound", "legacy_absent"] = "exact_selected"
    elif report.norm_diff_ref is not None:
        diff = validate_core_model_json_artifact(NormDiff, cas, report.norm_diff_ref)
        binding = "legacy_unbound"
    else:
        return NormImpactReadResult(report=report, diff=None, diff_binding="legacy_absent")
    if (
        diff.old_pack_id != report.old_pack_id
        or diff.new_pack_id != report.new_pack_id
        or diff.jurisdiction != report.jurisdiction
    ):
        raise ValueError("report_norm_diff_scope_mismatch")
    return NormImpactReadResult(report=report, diff=diff, diff_binding=binding)


def _reconcile_selected_report(report: NormImpactReport, diff: NormDiff) -> None:
    """Recompute v1.1's locally derivable claims without asserting source authority.

    Reconstructed packs contain only rules embedded in the selected diff. This
    proves internal consistency, not that the originating packs were complete,
    authentic, current, or evaluated under a complete comparison context.
    """
    try:
        old_pack = NormPack(
            pack_id=diff.old_pack_id,
            jurisdiction=diff.jurisdiction,
            norms=[change.old_rule for change in diff.changes if change.old_rule is not None],
        )
        new_pack = NormPack(
            pack_id=diff.new_pack_id,
            jurisdiction=diff.jurisdiction,
            norms=[change.new_rule for change in diff.changes if change.new_rule is not None],
        )
        recomputed = diff_norm_packs(old_pack, new_pack)
    except ValueError as exc:
        raise ValueError("selected_norm_diff_inconsistent") from exc
    if recomputed != diff:
        raise ValueError("selected_norm_diff_inconsistent")
    if (
        report.old_pack_id != diff.old_pack_id
        or report.new_pack_id != diff.new_pack_id
        or report.jurisdiction != diff.jurisdiction
    ):
        raise ValueError("report_norm_diff_scope_mismatch")
    if (
        report.metadata.get("declared_old_jurisdiction") != report.jurisdiction
        or report.metadata.get("declared_new_jurisdiction") != report.jurisdiction
    ):
        raise ValueError("report_declared_jurisdiction_mismatch")
    if (report.norms_added, report.norms_removed, report.norms_modified) != (
        recomputed.added_count,
        recomputed.removed_count,
        recomputed.modified_count,
    ):
        raise ValueError("report_norm_diff_counts_mismatch")
    if report.affected_kpis != _infer_candidate_topics_v1_1(recomputed):
        raise ValueError("report_norm_diff_topics_mismatch")
    passes = tuple(report.passes_executed)
    if len(passes) != len(set(passes)) or any(
        pass_id not in NormImpactAnalyzer.DEFAULT_PASSES for pass_id in passes
    ):
        raise ValueError("report_pass_plan_invalid")
    if report.report_id != _impact_report_id(
        diff.old_pack_id, diff.new_pack_id, recomputed, passes
    ):
        raise ValueError("report_norm_diff_id_mismatch")

    # Replay the whole carried issue multiset through the producer's owner.
    # Unchanged issues are not present in deltas; therefore a successful replay
    # cannot establish a complete issue set, backend execution or input context.
    deltas = report.compliance_deltas
    old_issues = [delta.old_issue for delta in deltas if delta.old_issue is not None]
    new_issues = [delta.new_issue for delta in deltas if delta.new_issue is not None]
    if any(issue.pass_id not in passes for issue in (*old_issues, *new_issues)):
        raise ValueError("report_issue_pass_plan_mismatch")
    if NormImpactAnalyzer._compute_compliance_delta(old_issues, new_issues, recomputed) != deltas:
        raise ValueError("report_compliance_delta_inconsistent")
    for metadata_key, observed in (
        ("old_issues_total", len(old_issues)),
        ("new_issues_total", len(new_issues)),
    ):
        total = report.metadata.get(metadata_key)
        if type(total) is not int or total < observed:
            raise ValueError("report_issue_total_below_carried_issues")
    expected_totals = (
        _count_transition(deltas, ComplianceTransition.PASS_TO_FAIL, IssueSeverity.BLOCKER)
        + _count_transition(deltas, ComplianceTransition.NEW_ISSUE, IssueSeverity.BLOCKER),
        _count_transition(deltas, ComplianceTransition.FAIL_TO_PASS, IssueSeverity.BLOCKER)
        + _count_transition(deltas, ComplianceTransition.RESOLVED_ISSUE, IssueSeverity.BLOCKER),
        _count_transition(deltas, ComplianceTransition.PASS_TO_FAIL, IssueSeverity.WARNING)
        + _count_transition(deltas, ComplianceTransition.NEW_ISSUE, IssueSeverity.WARNING),
        _count_transition(deltas, ComplianceTransition.FAIL_TO_PASS, IssueSeverity.WARNING)
        + _count_transition(deltas, ComplianceTransition.RESOLVED_ISSUE, IssueSeverity.WARNING),
        sum(1 for delta in deltas if delta.transition == ComplianceTransition.SEVERITY_CHANGE),
    )
    if (
        report.new_blockers,
        report.resolved_blockers,
        report.new_warnings,
        report.resolved_warnings,
        report.severity_changed,
    ) != expected_totals:
        raise ValueError("report_compliance_delta_counts_mismatch")


def _group_issues(
    issues: list[ComplianceIssue],
) -> dict[tuple[str, str, str, str, str], list[ComplianceIssue]]:
    grouped: dict[tuple[str, str, str, str, str], list[ComplianceIssue]] = defaultdict(list)
    for issue in issues:
        norm_id = _extract_norm_id(issue.path)
        key = (
            issue.pass_id,
            issue.code or "",
            norm_id,
            "/".join(str(segment) for segment in issue.path),
            issue.message,
        )
        grouped[key].append(issue)
    for bucket in grouped.values():
        bucket.sort(key=lambda item: item.severity.value)
    return grouped


def _extract_norm_id(path: list[str | int]) -> str:
    for idx, segment in enumerate(path):
        if isinstance(segment, str) and segment.startswith("norm:"):
            return segment.removeprefix("norm:")
        if (
            isinstance(segment, str)
            and segment == "norm_pack"
            and idx + 1 < len(path)
            and isinstance(path[idx + 1], str)
        ):
            return path[idx + 1]
    for segment in path:
        if isinstance(segment, str) and segment:
            return segment
    return "unknown"


def _issue_fingerprint(issue: ComplianceIssue | None, *, norm_id: str) -> str:
    if issue is None:
        return stable_world_id_from_canon(prefix="issue", payload={"norm_id": norm_id})
    return stable_world_id_from_canon(
        prefix="issue",
        payload={
            "pass_id": issue.pass_id,
            "code": issue.code,
            "norm_id": norm_id,
            "path": [str(segment) for segment in issue.path],
            "message": issue.message,
        },
    )


def _count_transition(
    deltas: list[ComplianceDelta],
    transition: ComplianceTransition,
    severity: IssueSeverity,
) -> int:
    total = 0
    for delta in deltas:
        if delta.transition != transition:
            continue
        issue = delta.new_issue if delta.new_issue is not None else delta.old_issue
        if issue is not None and issue.severity == severity:
            total += 1
    return total


__all__ = [
    "AffectedKPI",
    "ComplianceDelta",
    "ComplianceTransition",
    "NormImpactAnalyzer",
    "NormImpactReadResult",
    "NormImpactReport",
    "load_norm_impact_report",
]
