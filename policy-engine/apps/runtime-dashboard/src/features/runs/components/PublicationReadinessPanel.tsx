import { useMemo } from "react";

import type { RunInspectorSummary } from "@/features/runs/context/RunInspectorContext";
import { buildSignedPublicDecisionPacket } from "@/features/runs/domain/publicationPacket";

import { PublicationPacketPanel } from "./PublicationPacketPanel";

export function PublicationReadinessPanel({
  runId,
  summary,
}: {
  runId: string;
  summary: RunInspectorSummary;
}) {
  const packet = useMemo(
    () =>
      buildSignedPublicDecisionPacket({
        decisionScore: summary.decisionScore,
        decisionView: summary.decisionView,
        evidenceContext: summary.evidenceContext,
        governanceIssues: summary.governanceIssues,
        policyDesignCaseProjection: summary.run?.policy_design_case_projection,
        runId,
      }),
    [
      runId,
      summary.decisionScore,
      summary.decisionView,
      summary.evidenceContext,
      summary.governanceIssues,
      summary.run?.policy_design_case_projection,
    ],
  );

  return <PublicationPacketPanel packet={packet} />;
}
