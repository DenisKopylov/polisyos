import type { GovernanceDebugPayload } from "@/api/validators";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { formatNumber } from "@/shared/lib/utils";
import {
  normalizeGovernanceIssues,
  summarizeGovernanceIssues,
  type GovernanceIssueSeverity,
} from "@/shared/lib/domain/governance";
import { Badge, JsonPreview } from "@/shared/ui";

function severityKind(severity: GovernanceIssueSeverity) {
  if (severity === "blocker") {
    return "fail" as const;
  }
  if (severity === "warning") {
    return "warn" as const;
  }
  if (severity === "info") {
    return "ok" as const;
  }
  return "neutral" as const;
}

function verdictKind(verdict: string | null | undefined) {
  const normalized = (verdict ?? "").toLowerCase();
  if (normalized.includes("approve") || normalized === "ok") {
    return "ok" as const;
  }
  if (
    normalized.includes("reject") ||
    normalized.includes("fail") ||
    normalized.includes("block")
  ) {
    return "fail" as const;
  }
  return "warn" as const;
}

type GovernanceReportProps = {
  data: GovernanceDebugPayload["debug"];
};

export default function GovernanceReport({ data }: GovernanceReportProps) {
  const { t, label } = useI18n();
  const notes = data.notes ?? [];
  const issues = normalizeGovernanceIssues(data.issues);
  const summary = summarizeGovernanceIssues(issues);
  const transportSummary = (data.transport_summary ?? null) as Record<
    string,
    unknown
  > | null;
  const contractWarnings = data.contract_warnings ?? [];
  const linkEntries = Object.entries(data.links ?? {}).filter(([, value]) =>
    Boolean(value),
  );

  return (
    <div className="space-y-3">
      <div className="border-line bg-panel flex flex-wrap items-center justify-between gap-2 rounded-xl border p-3">
        <div>
          <p className="text-muted text-xs uppercase">
            {t("panels.governance.verdict")}
          </p>
          <div className="mt-1 flex items-center gap-2">
            <Badge kind={verdictKind(data.verdict)}>
              {label(
                "evaluatorVerdicts",
                data.verdict,
                data.verdict ?? t("common.unknown"),
              )}
            </Badge>
            {data.fallback_from_decision_packet ? (
              <span className="text-warning text-xs">
                {t("panels.governance.fallbackFromDecisionPacket")}
              </span>
            ) : null}
          </div>
        </div>
        <div className="grid grid-cols-4 gap-2 text-sm">
          <div className="bg-canvas/30 border-line rounded-lg border px-2 py-1">
            <p className="text-muted text-xs">
              {t("panels.governance.blockers")}
            </p>
            <p className="text-danger font-semibold">
              {formatNumber(summary.blocker)}
            </p>
          </div>
          <div className="bg-canvas/30 border-line rounded-lg border px-2 py-1">
            <p className="text-muted text-xs">
              {t("panels.governance.warnings")}
            </p>
            <p className="text-warning font-semibold">
              {formatNumber(summary.warning)}
            </p>
          </div>
          <div className="bg-canvas/30 border-line rounded-lg border px-2 py-1">
            <p className="text-muted text-xs">{t("panels.governance.info")}</p>
            <p className="text-success font-semibold">
              {formatNumber(summary.info)}
            </p>
          </div>
          <div className="bg-canvas/30 border-line rounded-lg border px-2 py-1">
            <p className="text-muted text-xs">
              {t("panels.governance.unknown")}
            </p>
            <p className="font-semibold">{formatNumber(summary.unknown)}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-3">
        <div className="bg-canvas/30 border-line rounded-xl border p-3 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("panels.governance.legalCoverage")}
          </p>
          <p className="font-semibold">
            {data.legal_executed === true
              ? t("panels.governance.executed")
              : data.legal_executed === false
                ? t("panels.governance.notRun")
                : t("panels.governance.unknown").toLowerCase()}
          </p>
          {data.report_schema_version ? (
            <p className="text-muted text-xs">
              {t("panels.governance.reportSchema", {
                kind: data.report_kind ?? t("panels.governance.reportFallback"),
                version: data.report_schema_version,
              })}
            </p>
          ) : null}
        </div>
        <div className="bg-canvas/30 border-line rounded-xl border p-3 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("panels.governance.transport")}
          </p>
          <p className="font-semibold">
            {String(transportSummary?.status ?? "not_available")}
          </p>
          {transportSummary?.identification_engine ? (
            <p className="text-muted text-xs">
              {t("panels.governance.engine", {
                engine: String(transportSummary.identification_engine),
              })}
            </p>
          ) : null}
        </div>
        <div className="bg-canvas/30 border-line rounded-xl border p-3 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("panels.governance.issueSummary")}
          </p>
          <p className="font-semibold">
            {t("panels.governance.summaryValues", {
              blockers: formatNumber(
                data.issue_summary?.blocker_count ?? summary.blocker,
              ),
              warnings: formatNumber(
                data.issue_summary?.warning_count ?? summary.warning,
              ),
              info: formatNumber(
                data.issue_summary?.info_count ?? summary.info,
              ),
            })}
          </p>
        </div>
      </div>

      {notes.length > 0 ? (
        <div className="bg-canvas/30 border-line rounded-xl border p-3 text-sm">
          <p className="text-muted mb-1 text-xs uppercase">
            {t("panels.governance.notes")}
          </p>
          <ul className="space-y-1">
            {notes.map((note) => (
              <li key={note}>- {note}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {contractWarnings.length > 0 ? (
        <div className="bg-canvas/30 border-line rounded-xl border p-3 text-sm">
          <p className="text-muted mb-1 text-xs uppercase">
            {t("panels.governance.contractWarnings")}
          </p>
          <ul className="space-y-1">
            {contractWarnings.map((warning) => (
              <li key={warning} className="text-warning font-mono text-xs">
                {warning}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {linkEntries.length > 0 ? (
        <div className="bg-canvas/30 border-line rounded-xl border p-3 text-sm">
          <p className="text-muted mb-1 text-xs uppercase">
            {t("panels.governance.linkedArtifacts")}
          </p>
          <ul className="space-y-1">
            {linkEntries.map(([key, value]) => (
              <li key={key}>
                <span className="text-muted">{key}:</span>{" "}
                <span className="font-mono text-xs">{value?.artifact_id}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {issues.length > 0 ? (
        <div className="space-y-2">
          {issues.map((issue, index) => (
            <details
              key={`${issue.code}-${index}`}
              className="border-line bg-panel rounded-xl border p-3"
            >
              <summary className="cursor-pointer list-none">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Badge kind={severityKind(issue.severity)}>
                      {label(
                        "governanceSeverity",
                        issue.severity,
                        issue.severity,
                      )}
                    </Badge>
                    <span className="font-mono text-xs">{issue.code}</span>
                    {issue.passId ? (
                      <span className="text-muted text-xs">
                        {t("panels.governance.pass", { passId: issue.passId })}
                      </span>
                    ) : null}
                  </div>
                  {issue.durationMs !== null ? (
                    <span className="text-muted text-xs">
                      {t("panels.governance.durationMs", {
                        duration: formatNumber(issue.durationMs),
                      })}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-sm">{issue.message}</p>
                {issue.path ? (
                  <p className="text-muted text-xs">
                    {t("panels.governance.path", { path: issue.path })}
                  </p>
                ) : null}
              </summary>
              <div className="border-line mt-3 border-t pt-3">
                <JsonPreview data={issue.raw} />
              </div>
            </details>
          ))}
        </div>
      ) : (
        <div className="bg-canvas/30 border-line text-muted rounded-xl border border-dashed p-3 text-sm">
          {t("panels.governance.emptyIssues")}
        </div>
      )}

      {data.validation_trace ? (
        <div className="border-line bg-panel rounded-xl border p-3">
          <p className="text-muted mb-1 text-xs uppercase">
            {t("panels.governance.validationTrace")}
          </p>
          <JsonPreview data={data.validation_trace} />
        </div>
      ) : null}

      {data.report_ref ? (
        <p className="text-muted text-xs">
          {t("panels.governance.reportRef", {
            ref: data.report_ref.artifact_id,
          })}
        </p>
      ) : null}
    </div>
  );
}
