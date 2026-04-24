import { Link } from "react-router-dom";

import { useRunInspector } from "@/features/runs/context/RunInspectorContext";
import { useI18n } from "@/i18n/LocaleProvider";

export function RunBreadcrumbs({ runId }: { runId: string }) {
  const { t } = useI18n();
  const summary = useRunInspector();

  return (
    <nav
      aria-label={t("pages.runs.runLineage")}
      className="text-muted flex flex-wrap items-center gap-2 text-xs"
    >
      <Link to="/runs" className="decoration-line underline">
        {t("common.runs")}
      </Link>
      <span>/</span>
      <span>{runId}</span>
      {summary.primaryDecisionArtifactId ? (
        <>
          <span>/</span>
          <Link
            to={`/artifacts/${summary.primaryDecisionArtifactId}`}
            className="decoration-line underline"
          >
            {t("pages.runs.decisionArtifact")}
          </Link>
        </>
      ) : null}
      {summary.primaryIssue ? (
        <>
          <span>/</span>
          <span>{summary.primaryIssue.code}</span>
        </>
      ) : null}
    </nav>
  );
}
