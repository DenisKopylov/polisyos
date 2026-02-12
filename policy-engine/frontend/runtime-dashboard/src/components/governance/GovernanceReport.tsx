import JsonPreview from "../shared/JsonPreview";
import StatusBadge from "../shared/StatusBadge";
import type { GovernanceDebugPayload } from "../../api/validators";
import {
  normalizeGovernanceIssues,
  summarizeGovernanceIssues,
  type GovernanceIssueSeverity,
} from "../../lib/domain/governance";

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
  return "unknown" as const;
}

function verdictKind(verdict: string | null | undefined) {
  const normalized = (verdict ?? "").toLowerCase();
  if (normalized.includes("approve") || normalized === "ok") {
    return "ok" as const;
  }
  if (normalized.includes("reject") || normalized.includes("fail") || normalized.includes("block")) {
    return "fail" as const;
  }
  return "warn" as const;
}

type GovernanceReportProps = {
  data: GovernanceDebugPayload["debug"];
};

export default function GovernanceReport({ data }: GovernanceReportProps) {
  const notes = data.notes ?? [];
  const issues = normalizeGovernanceIssues(data.issues);
  const summary = summarizeGovernanceIssues(issues);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line bg-panel p-3">
        <div>
          <p className="text-xs uppercase text-muted">Governance verdict</p>
          <div className="mt-1 flex items-center gap-2">
            <StatusBadge label={data.verdict ?? "unknown"} kind={verdictKind(data.verdict)} />
            {data.fallback_from_decision_packet ? (
              <span className="text-xs text-warning">fallback from decision packet</span>
            ) : null}
          </div>
        </div>
        <div className="grid grid-cols-4 gap-2 text-sm">
          <div className="rounded-lg border border-line bg-canvas/30 px-2 py-1">
            <p className="text-xs text-muted">Blockers</p>
            <p className="font-semibold text-danger">{summary.blocker}</p>
          </div>
          <div className="rounded-lg border border-line bg-canvas/30 px-2 py-1">
            <p className="text-xs text-muted">Warnings</p>
            <p className="font-semibold text-warning">{summary.warning}</p>
          </div>
          <div className="rounded-lg border border-line bg-canvas/30 px-2 py-1">
            <p className="text-xs text-muted">Info</p>
            <p className="font-semibold text-success">{summary.info}</p>
          </div>
          <div className="rounded-lg border border-line bg-canvas/30 px-2 py-1">
            <p className="text-xs text-muted">Unknown</p>
            <p className="font-semibold">{summary.unknown}</p>
          </div>
        </div>
      </div>

      {notes.length > 0 ? (
        <div className="rounded-xl border border-line bg-canvas/30 p-3 text-sm">
          <p className="mb-1 text-xs uppercase text-muted">Notes</p>
          <ul className="space-y-1">
            {notes.map((note) => (
              <li key={note}>- {note}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {issues.length > 0 ? (
        <div className="space-y-2">
          {issues.map((issue, index) => (
            <details key={`${issue.code}-${index}`} className="rounded-xl border border-line bg-panel p-3">
              <summary className="cursor-pointer list-none">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <StatusBadge label={issue.severity} kind={severityKind(issue.severity)} />
                    <span className="font-mono text-xs">{issue.code}</span>
                    {issue.passId ? <span className="text-xs text-muted">pass={issue.passId}</span> : null}
                  </div>
                  {issue.durationMs !== null ? (
                    <span className="text-xs text-muted">{issue.durationMs} ms</span>
                  ) : null}
                </div>
                <p className="mt-1 text-sm">{issue.message}</p>
                {issue.path ? <p className="text-xs text-muted">path={issue.path}</p> : null}
              </summary>
              <div className="mt-3 border-t border-line pt-3">
                <JsonPreview data={issue.raw} />
              </div>
            </details>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-line bg-canvas/30 p-3 text-sm text-muted">
          Governance issues are empty for this run.
        </div>
      )}

      {data.validation_trace ? (
        <div className="rounded-xl border border-line bg-panel p-3">
          <p className="mb-1 text-xs uppercase text-muted">Validation trace</p>
          <JsonPreview data={data.validation_trace} />
        </div>
      ) : null}

      {data.report_ref ? (
        <p className="text-xs text-muted">Report ref: {data.report_ref.artifact_id}</p>
      ) : null}
    </div>
  );
}
