import { useLocation, useParams } from "react-router-dom";

import { useAuthzDecision } from "@/app/authz/AuthzProvider";
import { useCaseInspection } from "@/features/runs/api/useCaseInspection";
import type { RunPaperPacket } from "@/features/runs/api/useRunPaper";
import { downloadRunPaperPacket } from "@/features/runs/components/runPaperExport";
import {
  buildRunPaperSemanticRoster,
  presentRunPaper,
  type RunPaperSemanticNode,
} from "@/features/runs/domain/runPaperPresentation";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Button, Card, EmptyState, PanelSkeleton } from "@polisyos/atlas-ui";

function semanticNodeValue(node: RunPaperSemanticNode): string {
  switch (node.kind) {
    case "array":
      return `[array:${String(node.length)}]`;
    case "object":
      return `[object:${node.members.join(",")}]`;
    case "null":
      return "null";
    case "boolean":
    case "number":
    case "string":
      return String(node.value);
  }
}

function CaseRecordSummary({
  caseRecord,
}: {
  caseRecord: RunPaperPacket["case_record"];
}) {
  const { t } = useI18n();
  if (caseRecord.availability === "artifact_missing") {
    return (
      <section
        className="space-y-3"
        data-case-availability="artifact_missing"
        data-testid="case-inspection-unavailable"
      >
        <h2 className="text-xl font-semibold">
          {t("pages.runs.report.paper.caseTitle")}
        </h2>
        <dl className="grid gap-2 font-mono text-sm sm:grid-cols-2">
          <div>
            <dt>{t("pages.runs.report.paper.fields.availability")}</dt>
            <dd>{caseRecord.availability}</dd>
          </div>
          <div>
            <dt>{t("pages.runs.report.paper.fields.capabilityState")}</dt>
            <dd>{caseRecord.capability_state}</dd>
          </div>
          <div>
            <dt>{t("pages.runs.report.paper.fields.reason")}</dt>
            <dd>{caseRecord.reason_code}</dd>
          </div>
          <div>
            <dt>{t("pages.runs.report.paper.fields.ownerRoute")}</dt>
            <dd>{caseRecord.owner_route}</dd>
          </div>
          <div>
            <dt>{t("pages.runs.report.paper.fields.closureSignal")}</dt>
            <dd>{caseRecord.closure_signal}</dd>
          </div>
        </dl>
        <h3 className="font-semibold">
          {t("pages.runs.report.paper.mayNotUseFor")}
        </h3>
        <ul className="list-disc space-y-1 pl-5 font-mono text-sm">
          {caseRecord.may_not_use_for.map((deniedUse) => (
            <li key={deniedUse}>{deniedUse}</li>
          ))}
        </ul>
      </section>
    );
  }

  const issueGroups = [
    [
      "blocker",
      "pages.runs.report.paper.groups.blockers",
      caseRecord.blockers,
    ],
    [
      "limitation",
      "pages.runs.report.paper.groups.limitations",
      caseRecord.limitations,
    ],
    [
      "objection",
      "pages.runs.report.paper.groups.objections",
      caseRecord.objections,
    ],
    [
      "abstention",
      "pages.runs.report.paper.groups.abstentions",
      caseRecord.abstentions,
    ],
  ] as const;
  return (
    <section
      className="space-y-4"
      data-case-availability="available"
      data-testid="case-inspection-available"
    >
      <h2 className="text-xl font-semibold">
        {t("pages.runs.report.paper.caseTitle")}
      </h2>
      <dl className="grid gap-2 font-mono text-sm sm:grid-cols-2">
        <div>
          <dt>{t("pages.runs.report.paper.fields.case")}</dt>
          <dd>{caseRecord.case_id}</dd>
        </div>
        <div>
          <dt>{t("pages.runs.report.paper.fields.designRecord")}</dt>
          <dd>{caseRecord.design_record_binding.design_record_record_id}</dd>
        </div>
        <div>
          <dt>{t("pages.runs.report.paper.fields.grounding")}</dt>
          <dd>{caseRecord.grounding_state.state}</dd>
        </div>
        <div>
          <dt>{t("pages.runs.report.paper.fields.admission")}</dt>
          <dd>{caseRecord.admission_state.state}</dd>
        </div>
        <div>
          <dt>{t("pages.runs.report.paper.fields.promotion")}</dt>
          <dd>{caseRecord.promotion_state.state}</dd>
        </div>
      </dl>
      {issueGroups.map(([kind, titleKey, issues]) => (
        <section key={kind} data-case-issue-kind={kind}>
          <h3 className="font-semibold">{t(titleKey)}</h3>
          <ul className="space-y-2">
            {issues.map((issue) => (
              <li key={issue.issue_id}>
                <strong>{issue.statement}</strong>
                <div className="font-mono text-xs">
                  {issue.status} · {issue.owner_route} · {issue.code}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </section>
  );
}

function CaseWorkspaceDocument({ packet }: { packet: RunPaperPacket }) {
  const { t } = useI18n();
  const paper = presentRunPaper(packet);
  const semanticRoster = buildRunPaperSemanticRoster(paper);
  return (
    <Card
      className="space-y-6"
      data-run-paper-document="true"
      data-testid="case-workspace-document"
    >
      <header className="space-y-2">
        <p className="eyebrow">
          {t("pages.runs.report.paper.caseTitle")}
        </p>
        <h1 className="text-3xl font-semibold">
          {t("pages.runs.report.paper.runHeading", {
            runId: paper.run.run_id,
          })}
        </h1>
        <p className="font-mono text-xs break-all">{paper.projectionHash}</p>
      </header>

      <CaseRecordSummary caseRecord={paper.caseRecord} />

      <section
        className="space-y-2"
        data-testid="case-stage-trace"
        id="stage-trace"
      >
        <h2 className="text-xl font-semibold">
          {t("pages.runs.report.paper.stageTrace")}
        </h2>
        <p className="font-mono text-sm">{paper.stageTrace.availability}</p>
        <p className="font-mono text-sm">{paper.stageTrace.owner_route}</p>
        {paper.stageTrace.availability === "available" ? (
          <p className="font-mono text-sm break-all">
            {paper.stageTrace.trace_ref.artifact_id}
          </p>
        ) : (
          <p>{paper.stageTrace.reason}</p>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">
          {t("pages.runs.report.paper.admittedOutputs")}
        </h2>
        <ol className="space-y-2">
          {paper.artifactLinks.map((link) => (
            <li key={link.artifact_ref.artifact_id}>
              <a
                className="break-all underline"
                data-run-paper-artifact-link={link.artifact_ref.artifact_id}
                href={link.href}
              >
                {link.artifact_ref.kind} · {link.artifact_ref.artifact_id}
              </a>
            </li>
          ))}
        </ol>
      </section>

      <section
        className="space-y-2"
        data-run-paper-semantic-roster="true"
        data-run-paper-semantic-roster-size={semanticRoster.length}
      >
        <h2 className="text-xl font-semibold">
          {t("pages.runs.report.paper.completeFacts")}
        </h2>
        <dl className="space-y-1 font-mono text-xs">
          {semanticRoster.map((node) => (
            <div
              className="grid gap-1 py-1 sm:grid-cols-[minmax(12rem,1fr)_2fr]"
              data-run-paper-node="true"
              data-run-paper-path={node.path}
              data-run-paper-raw={JSON.stringify(node)}
              key={node.path || "/"}
            >
              <dt className="break-all">{node.path || "/"}</dt>
              <dd className="break-all">{semanticNodeValue(node)}</dd>
            </div>
          ))}
        </dl>
      </section>
    </Card>
  );
}

function AuthorizedCaseWorkspace({ runId }: { runId: string }) {
  const { t } = useI18n();
  const location = useLocation();
  const query = useCaseInspection(runId, location.search);

  if (query.isLoading) return <PanelSkeleton rows={8} />;
  if (query.isError || !query.data) {
    return (
      <Card>
        <EmptyState
          body={t("pages.runs.report.unavailableBody")}
          title={t("pages.runs.unavailableRun")}
        />
      </Card>
    );
  }
  return (
    <div className="space-y-4" data-testid="case-workspace-page">
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="ghost"
          onClick={() =>
            downloadRunPaperPacket(runId, query.data.rawPacketBytes)
          }
        >
          {t("pages.runs.report.exportMachine")}
        </Button>
      </div>
      <CaseWorkspaceDocument packet={query.data.packet} />
    </div>
  );
}

export default function CaseWorkspacePage() {
  const { t } = useI18n();
  const { runId } = useParams();
  const authzDecision = useAuthzDecision();

  if (!runId) {
    return (
      <Card>
        <EmptyState
          body={t("pages.runs.report.requiredBody")}
          title={t("pages.runs.report.requiredTitle")}
        />
      </Card>
    );
  }
  if (authzDecision.kind === "unknown") {
    return (
      <Card data-testid="case-inspection-access-unsettled">
        <EmptyState
          body={t("pages.cycleBoard.accessUnsettledBody")}
          title={t("pages.cycleBoard.accessUnsettledTitle")}
        />
      </Card>
    );
  }
  if (!authzDecision.can("runs.review")) {
    return (
      <Card data-testid="case-inspection-access-denied">
        <EmptyState
          body={t("pages.cycleBoard.accessDeniedBody")}
          title={t("pages.cycleBoard.accessDeniedTitle")}
        />
      </Card>
    );
  }
  return <AuthorizedCaseWorkspace runId={runId} />;
}
