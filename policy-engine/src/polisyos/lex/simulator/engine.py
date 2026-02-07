from __future__ import annotations

from collections import defaultdict
from typing import Any

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.ir.norm_pack import NormPack, RuleType
from polisyos.ir.world.ids import stable_world_id_from_canon
from polisyos.scientist.governance.passes.base import PassContext
from polisyos.scientist.governance.passes.legal_pass import LegalPass
from polisyos.scientist.governance.passes.safety_pass import SafetyPass
from polisyos.scientist.governance.profiles import ValidationProfile

from .diff import NormDiff, NormChangeType, diff_norm_packs
from .report import AffectedKPI, ComplianceDelta, ComplianceTransition, NormImpactReport


class NormImpactAnalyzer:
    DEFAULT_PASSES: tuple[str, ...] = ("legal", "safety")

    def __init__(
        self,
        cas: FileSystemCAS,
        *,
        profile: ValidationProfile | None = None,
        passes: tuple[str, ...] | None = None,
        legal_backend: object | None = None,
    ):
        self._cas = cas
        self._profile = profile or ValidationProfile.strict()
        self._pass_ids = passes or self.DEFAULT_PASSES
        self._legal_backend = legal_backend

    def analyze(
        self,
        old_pack: NormPack,
        new_pack: NormPack,
        *,
        context: dict[str, Any] | None = None,
        decision_packet_ref: str | None = None,
        persist: bool = True,
    ) -> NormImpactReport:
        runtime_context = context or {}
        diff = diff_norm_packs(old_pack, new_pack)
        old_issues = self._run_passes(old_pack, runtime_context)
        new_issues = self._run_passes(new_pack, runtime_context)
        deltas = self._compute_compliance_delta(old_issues, new_issues, diff)
        affected_kpis = self._infer_affected_kpis(diff)

        report = NormImpactReport(
            report_id=self._generate_report_id(old_pack, new_pack, diff),
            old_pack_id=old_pack.pack_id,
            new_pack_id=new_pack.pack_id,
            jurisdiction=old_pack.jurisdiction,
            norms_added=diff.added_count,
            norms_removed=diff.removed_count,
            norms_modified=diff.modified_count,
            compliance_deltas=deltas,
            new_blockers=_count_transition(deltas, ComplianceTransition.PASS_TO_FAIL, IssueSeverity.BLOCKER)
            + _count_transition(deltas, ComplianceTransition.NEW_ISSUE, IssueSeverity.BLOCKER),
            resolved_blockers=_count_transition(
                deltas, ComplianceTransition.FAIL_TO_PASS, IssueSeverity.BLOCKER
            )
            + _count_transition(deltas, ComplianceTransition.RESOLVED_ISSUE, IssueSeverity.BLOCKER),
            new_warnings=_count_transition(deltas, ComplianceTransition.PASS_TO_FAIL, IssueSeverity.WARNING)
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
            },
        )

        if persist:
            diff_ref = self._persist_diff(diff)
            report_ref = self._persist_report(report)
            report.norm_diff_ref = str(diff_ref.artifact_id)
            report.cas_artifact_id = str(report_ref.artifact_id)

        return report

    def _run_passes(self, norm_pack: NormPack, context: dict[str, Any]) -> list[ComplianceIssue]:
        issues: list[ComplianceIssue] = []
        pass_context = PassContext(
            ir=context.get("ir"),
            state={"norm_pack": norm_pack, **context},
            registry_bundle=context.get("registry_bundle"),
            profile=self._profile,
            run_id=f"impact-{norm_pack.pack_id[:20]}",
        )

        for pass_id in self._pass_ids:
            if pass_id == "legal":
                issues.extend(LegalPass(backend=self._legal_backend, enabled=True).validate(pass_context))
            elif pass_id == "safety":
                issues.extend(SafetyPass().validate(pass_context))
        return issues

    def _compute_compliance_delta(
        self,
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
        aggregate: dict[str, AffectedKPI] = {}
        for change in norm_diff.changes:
            if change.change_type == NormChangeType.UNCHANGED:
                continue
            rule = change.new_rule if change.new_rule is not None else change.old_rule
            if rule is None:
                continue

            if rule.rule_type == RuleType.OBLIGATION:
                kpi_id = "compliance_cost"
                description = "Operational and reporting costs needed to maintain compliance."
            elif rule.rule_type == RuleType.PROHIBITION:
                kpi_id = "operational_restrictions"
                description = "Direct restrictions on operational policy space."
            else:
                kpi_id = "regulatory_flexibility"
                description = "Available discretionary actions under permissions."

            if kpi_id not in aggregate:
                aggregate[kpi_id] = AffectedKPI(kpi_id=kpi_id, description=description)
            aggregate[kpi_id].affected_norm_ids.append(change.norm_id)

        for item in aggregate.values():
            item.affected_norm_ids = sorted(set(item.affected_norm_ids))
        return sorted(aggregate.values(), key=lambda item: item.kpi_id)

    def _persist_diff(self, diff: NormDiff):
        return self._cas.put_json(
            diff.model_dump(mode="json"),
            PutOptions(
                kind="lex.norm_diff",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.lex.NormDiff", version="1.0"),
            ),
        )

    def _persist_report(self, report: NormImpactReport):
        return self._cas.put_json(
            report.model_dump(mode="json"),
            PutOptions(
                kind="lex.norm_impact_report",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.lex.NormImpactReport", version="1.0"),
            ),
        )

    def _generate_report_id(self, old_pack: NormPack, new_pack: NormPack, norm_diff: NormDiff) -> str:
        return stable_world_id_from_canon(
            prefix="lex.impact_report",
            payload={
                "old_pack_id": old_pack.pack_id,
                "new_pack_id": new_pack.pack_id,
                "diff_stats": {
                    "added": norm_diff.added_count,
                    "removed": norm_diff.removed_count,
                    "modified": norm_diff.modified_count,
                },
                "passes": list(self._pass_ids),
            },
        )


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

