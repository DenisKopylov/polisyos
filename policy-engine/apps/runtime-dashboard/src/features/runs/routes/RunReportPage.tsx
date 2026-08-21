import { useLocation, useParams } from "react-router-dom";

import { useAuthzDecision } from "@/app/authz/AuthzProvider";
import {
  type RunPaperPacket,
  useRunPaper,
} from "@/features/runs/api/useRunPaper";
import { downloadRunPaperPacket } from "@/features/runs/components/runPaperExport";
import {
  buildRunPaperSemanticRoster,
  presentRunPaper,
  type RunPaperSemanticNode,
} from "@/features/runs/domain/runPaperPresentation";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Button, Card, EmptyState, PanelSkeleton } from "@polisyos/atlas-ui";

function PaperFact({
  field,
  label,
  value,
}: {
  field: string;
  label: string;
  value: string | number;
}) {
  return (
    <div data-run-paper-field={field}>
      <dt className="text-muted text-xs font-semibold tracking-wide uppercase">
        {label}
      </dt>
      <dd className="mt-1 font-mono text-sm break-words">{value}</dd>
    </div>
  );
}

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

function CaseRecordSection({
  caseRecord,
}: {
  caseRecord: RunPaperPacket["case_record"];
}) {
  const { t } = useI18n();
  if (caseRecord.availability === "artifact_missing") {
    return (
      <section className="space-y-3" data-run-paper-case="artifact_missing">
        <h2 className="text-xl font-semibold">
          {t("pages.runs.report.paper.caseTitle")}
        </h2>
        <dl className="grid gap-3 sm:grid-cols-2">
          <PaperFact
            field="case.availability"
            label={t("pages.runs.report.paper.fields.availability")}
            value={caseRecord.availability}
          />
          <PaperFact
            field="case.capability_state"
            label={t("pages.runs.report.paper.fields.capabilityState")}
            value={caseRecord.capability_state}
          />
          <PaperFact
            field="case.reason_code"
            label={t("pages.runs.report.paper.fields.reason")}
            value={caseRecord.reason_code}
          />
          <PaperFact
            field="case.owner_route"
            label={t("pages.runs.report.paper.fields.ownerRoute")}
            value={caseRecord.owner_route}
          />
          <PaperFact
            field="case.closure_signal"
            label={t("pages.runs.report.paper.fields.closureSignal")}
            value={caseRecord.closure_signal}
          />
        </dl>
        <div>
          <h3 className="text-sm font-semibold">
            {t("pages.runs.report.paper.mayNotUseFor")}
          </h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 font-mono text-sm">
            {caseRecord.may_not_use_for.map((use) => (
              <li key={use} data-run-paper-case-denied-use={use}>
                {use}
              </li>
            ))}
          </ul>
        </div>
      </section>
    );
  }

  const issueGroups = [
    [
      "blockers",
      "pages.runs.report.paper.groups.blockers",
      caseRecord.blockers,
    ],
    [
      "limitations",
      "pages.runs.report.paper.groups.limitations",
      caseRecord.limitations,
    ],
    [
      "objections",
      "pages.runs.report.paper.groups.objections",
      caseRecord.objections,
    ],
    [
      "abstentions",
      "pages.runs.report.paper.groups.abstentions",
      caseRecord.abstentions,
    ],
  ] as const;
  return (
    <section className="space-y-4" data-run-paper-case="available">
      <h2 className="text-xl font-semibold">
        {t("pages.runs.report.paper.caseTitle")}
      </h2>
      <dl className="grid gap-3 sm:grid-cols-2">
        <PaperFact
          field="case.availability"
          label={t("pages.runs.report.paper.fields.availability")}
          value={caseRecord.availability}
        />
        <PaperFact
          field="case.case_id"
          label={t("pages.runs.report.paper.fields.case")}
          value={caseRecord.case_id}
        />
        <PaperFact
          field="case.design_record_id"
          label={t("pages.runs.report.paper.fields.designRecord")}
          value={caseRecord.design_record_binding.design_record_record_id}
        />
        <PaperFact
          field="case.grounding_state"
          label={t("pages.runs.report.paper.fields.grounding")}
          value={caseRecord.grounding_state.state}
        />
        <PaperFact
          field="case.admission_state"
          label={t("pages.runs.report.paper.fields.admission")}
          value={caseRecord.admission_state.state}
        />
        <PaperFact
          field="case.promotion_state"
          label={t("pages.runs.report.paper.fields.promotion")}
          value={caseRecord.promotion_state.state}
        />
      </dl>
      {issueGroups.map(([group, titleKey, issues]) => (
        <section key={group} data-run-paper-issue-group={group}>
          <h3 className="font-semibold">{t(titleKey)}</h3>
          <ul className="mt-2 space-y-2">
            {issues.map((issue) => (
              <li key={issue.issue_id} className="border-line border-l-2 pl-3">
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

function RunPaperDocument({ packet }: { packet: RunPaperPacket }) {
  const { t } = useI18n();
  const paper = presentRunPaper(packet);
  const semanticRoster = buildRunPaperSemanticRoster(paper);
  return (
    <Card
      className="run-paper-document space-y-6 print:shadow-none"
      data-paper-payload="run-paper"
      data-print-document="true"
      data-run-paper-document="true"
      data-testid="run-paper-document"
    >
      <header
        className="border-line space-y-3 border-b pb-4"
        data-print-keep-together="true"
        data-testid="run-paper-identity"
      >
        <p className="eyebrow">{t("pages.runs.report.paper.eyebrow")}</p>
        <h1 className="text-3xl font-semibold">
          {t("pages.runs.report.paper.runHeading", { runId: paper.run.run_id })}
        </h1>
      </header>

      <section data-print-keep-together="true">
        <dl className="grid gap-3 sm:grid-cols-2">
          <PaperFact
            field="packet.schema_version"
            label={t("pages.runs.report.paper.fields.packetSchema")}
            value={paper.packetSchemaVersion}
          />
          <PaperFact
            field="packet.projection_rule_version"
            label={t("pages.runs.report.paper.fields.projectionRule")}
            value={paper.projectionRuleVersion}
          />
          <PaperFact
            field="packet.projection_hash"
            label={t("pages.runs.report.paper.fields.projectionHash")}
            value={paper.projectionHash}
          />
          <PaperFact
            field="packet.intended_audiences"
            label={t("pages.runs.report.paper.fields.intendedAudiences")}
            value={paper.intendedAudiences.join(", ")}
          />
          <PaperFact
            field="replay.manifest_artifact_id"
            label={t("pages.runs.report.paper.fields.manifest")}
            value={paper.replayPins.manifest_artifact_id}
          />
          <PaperFact
            field="replay.manifest_schema_version"
            label={t("pages.runs.report.paper.fields.manifestSchemaVersion")}
            value={paper.replayPins.manifest_schema_version}
          />
          <PaperFact
            field="replay.paper_projection_rule_version"
            label={t("pages.runs.report.paper.fields.replayProjectionRule")}
            value={paper.replayPins.paper_projection_rule_version}
          />
          <PaperFact
            field="replay.paper_projection_hash"
            label={t("pages.runs.report.paper.fields.replayProjectionHash")}
            value={paper.replayPins.paper_projection_hash}
          />
        </dl>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">
          {t("pages.runs.report.paper.runState")}
        </h2>
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <PaperFact
            field="run.status"
            label={t("pages.runs.report.paper.fields.status")}
            value={paper.run.status}
          />
          <PaperFact
            field="run.run_terminality"
            label={t("pages.runs.report.paper.fields.terminality")}
            value={paper.run.run_terminality}
          />
          <PaperFact
            field="run.source_kind"
            label={t("pages.runs.report.paper.fields.sourceKind")}
            value={paper.run.source_kind}
          />
          <PaperFact
            field="run.tenant_id"
            label={t("pages.runs.report.paper.fields.tenant")}
            value={paper.run.tenant_id}
          />
          {paper.run.cell_id ? (
            <PaperFact
              field="run.cell_id"
              label={t("pages.runs.report.paper.fields.cell")}
              value={paper.run.cell_id}
            />
          ) : null}
          {paper.run.started_at ? (
            <PaperFact
              field="run.started_at"
              label={t("pages.runs.report.paper.fields.startedAt")}
              value={paper.run.started_at}
            />
          ) : null}
          {paper.run.finished_at ? (
            <PaperFact
              field="run.finished_at"
              label={t("pages.runs.report.paper.fields.finishedAt")}
              value={paper.run.finished_at}
            />
          ) : null}
          {paper.run.duration_ms !== null &&
          paper.run.duration_ms !== undefined ? (
            <PaperFact
              field="run.duration_ms"
              label={t("pages.runs.report.paper.fields.durationMs")}
              value={paper.run.duration_ms}
            />
          ) : null}
        </dl>
      </section>

      <CaseRecordSection caseRecord={paper.caseRecord} />

      <section className="space-y-3" id="stage-trace">
        <h2 className="text-xl font-semibold">
          {t("pages.runs.report.paper.stageTrace")}
        </h2>
        <dl className="grid gap-3 sm:grid-cols-2">
          <PaperFact
            field="stage_trace.availability"
            label={t("pages.runs.report.paper.fields.availability")}
            value={paper.stageTrace.availability}
          />
          <PaperFact
            field="stage_trace.owner_route"
            label={t("pages.runs.report.paper.fields.ownerRoute")}
            value={paper.stageTrace.owner_route}
          />
          {paper.stageTrace.availability === "available" ? (
            <PaperFact
              field="stage_trace.artifact_id"
              label={t("pages.runs.report.paper.fields.traceArtifact")}
              value={paper.stageTrace.trace_ref.artifact_id}
            />
          ) : (
            <PaperFact
              field="stage_trace.reason"
              label={t("pages.runs.report.paper.fields.reason")}
              value={paper.stageTrace.reason}
            />
          )}
        </dl>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">
          {t("pages.runs.report.paper.admittedOutputs")}
        </h2>
        <p
          className="font-mono text-sm"
          data-run-paper-field="artifact_links.count"
        >
          {paper.artifactLinks.length}
        </p>
        {paper.artifactLinks.length > 0 ? (
          <ol className="space-y-2">
            {paper.artifactLinks.map((link) => (
              <li key={link.artifact_ref.artifact_id}>
                <a
                  className="break-all underline"
                  data-paper-link-eligible="true"
                  data-run-paper-artifact-link={link.artifact_ref.artifact_id}
                  href={link.href}
                >
                  {link.artifact_ref.kind} · {link.artifact_ref.artifact_id}
                </a>
              </li>
            ))}
          </ol>
        ) : null}
      </section>

      <section
        className="space-y-3"
        data-run-paper-semantic-roster="true"
        data-run-paper-semantic-roster-size={semanticRoster.length}
      >
        <h2 className="text-xl font-semibold">
          {t("pages.runs.report.paper.completeFacts")}
        </h2>
        <dl className="space-y-1 font-mono text-xs">
          {semanticRoster.map((node) => (
            <div
              className="border-line grid gap-1 border-b py-1 sm:grid-cols-[minmax(12rem,1fr)_2fr]"
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

      <footer className="print-provenance-summary space-y-2">
        <PaperFact
          field="source.manifest_schema"
          label={t("pages.runs.report.paper.fields.manifestSchema")}
          value={`${paper.source.manifest_schema_name}@${paper.source.manifest_schema_version}`}
        />
        <PaperFact
          field="source.registry_bundle"
          label={t("pages.runs.report.paper.fields.registryBundle")}
          value={paper.source.registry_bundle.artifact_id}
        />
        {paper.source.producer ? (
          <PaperFact
            field="source.producer"
            label={t("pages.runs.report.paper.fields.producer")}
            value={`${paper.source.producer.component}@${paper.source.producer.version}`}
          />
        ) : null}
        {paper.source.environment ? (
          <>
            <PaperFact
              field="source.environment.python"
              label={t("pages.runs.report.paper.fields.pythonEnvironment")}
              value={paper.source.environment.python}
            />
            <PaperFact
              field="source.environment.platform"
              label={t("pages.runs.report.paper.fields.platformEnvironment")}
              value={paper.source.environment.platform}
            />
            <PaperFact
              field="source.environment.deps_lock_hash"
              label={t("pages.runs.report.paper.fields.dependenciesLock")}
              value={paper.source.environment.deps_lock_hash}
            />
          </>
        ) : null}
        <PaperFact
          field="packet.replay_address"
          label={t("pages.runs.report.paper.fields.replayAddress")}
          value={paper.replayAddress}
        />
      </footer>
    </Card>
  );
}

function AuthorizedRunReportPage({ runId }: { runId: string }) {
  const { t } = useI18n();
  const location = useLocation();
  const query = useRunPaper(runId, location.search);

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
    <div className="space-y-4" data-testid="run-report-page">
      <div className="flex flex-wrap gap-2" data-print-hidden="true">
        <Button
          type="button"
          variant="ghost"
          onClick={() =>
            downloadRunPaperPacket(runId, query.data.rawPacketBytes)
          }
        >
          {t("pages.runs.report.exportMachine")}
        </Button>
        <Button type="button" variant="primary" onClick={() => window.print()}>
          {t("pages.runs.report.printPdf")}
        </Button>
      </div>
      <RunPaperDocument packet={query.data.packet} />
    </div>
  );
}

export default function RunReportPage() {
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
      <Card data-testid="run-paper-access-unsettled">
        <EmptyState
          body={t("pages.cycleBoard.accessUnsettledBody")}
          title={t("pages.cycleBoard.accessUnsettledTitle")}
        />
      </Card>
    );
  }
  if (!authzDecision.can("runs.review")) {
    return (
      <Card data-testid="run-paper-access-denied">
        <EmptyState
          body={t("pages.cycleBoard.accessDeniedBody")}
          title={t("pages.cycleBoard.accessDeniedTitle")}
        />
      </Card>
    );
  }
  return <AuthorizedRunReportPage runId={runId} />;
}
