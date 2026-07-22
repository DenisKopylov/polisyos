import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ProjectionFreshness } from "@polisyos/runtime-api-client";

import { Badge } from "@polisyos/atlas-ui";
import {
  DataFreshnessBadge,
  DataTable,
  DecisionCard,
  EvidenceChain,
  MetricCard,
  StatusTimeline,
} from "@/shared/ui";

const meta = {
  title: "Design System/Compounds",
  tags: ["autodocs"],
  parameters: {
    docs: {
      description: {
        component:
          "Compound components capture recurring runtime-dashboard domain patterns. Prefer these before creating feature-local metric, decision, timeline, or evidence chrome.",
      },
    },
  },
} satisfies Meta;

export default meta;

type Story = StoryObj<typeof meta>;

const runRows = [
  {
    blockers: 0,
    confidence: "91%",
    runId: "run-2026-03-10-17",
    status: "approved",
  },
  {
    blockers: 2,
    confidence: "48%",
    runId: "run-2026-03-10-12",
    status: "review",
  },
];

const storyFreshness: ProjectionFreshness = {
  basis: "source_timestamp",
  observed_at: "2026-03-10T20:00:00Z",
  source_as_of: "2026-03-10T19:55:00Z",
  state: "observed",
};

export const OperationalOverview: Story = {
  render: () => (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Active runs"
          value="17"
          meta="4 awaiting evidence promotion"
          badge={<Badge kind="info">Live</Badge>}
        />
        <MetricCard
          label="Governance blockers"
          value="3"
          meta="2 require legal sign-off"
          badge={<Badge kind="warn">Review</Badge>}
        />
        <MetricCard
          label="Evidence freshness"
          value={<DataFreshnessBadge freshness={storyFreshness} />}
          meta="Producer-recorded source and observation times"
        />
      </section>

      <DecisionCard
        title="Decision packet: Food price shock intervention"
        subtitle="Workflow policy.v3 · runtime sample backed"
        verdict="Approve with revisions"
        confidence="0.82 confidence"
        summary="Budget exposure is acceptable, but the transportability note should be reviewed before final publish."
        diagnostics={[
          { kind: "ok", label: "Evidence verified" },
          { kind: "warn", label: "Governance review" },
          { kind: "neutral", label: "2 assumptions" },
        ]}
        meta={[
          { label: "Owner", value: "Policy Ops" },
          { label: "Run", value: "run-2026-03-10-17" },
          { label: "Artifact", value: "decision_packet_v3" },
          { label: "Updated", value: "5 minutes ago" },
        ]}
      />

      <div className="grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
        <StatusTimeline
          emptyBody="No events"
          emptyTitle="Timeline empty"
          items={[
            {
              body: "ExploreLane promoted a higher-confidence inflation series.",
              id: "timeline-1",
              meta: <Badge kind="ok">Approved</Badge>,
              timestamp: "2026-03-10 19:48 UTC",
              title: "Promotion candidate accepted",
              recordedState: "accepted",
            },
            {
              body: "Human gate paused publish while legal review was requested.",
              id: "timeline-2",
              meta: <Badge kind="warn">Human gate</Badge>,
              timestamp: "2026-03-10 19:31 UTC",
              title: "Governance waiting state entered",
              recordedState: "human_gate_waiting",
            },
            {
              body: "Run recovered after polling fallback while SSE stream reconnected.",
              id: "timeline-3",
              meta: <Badge kind="info">Transport</Badge>,
              timestamp: "2026-03-10 19:12 UTC",
              title: "Live transport degraded",
              recordedState: "transport_degraded",
            },
          ]}
        />

        <EvidenceChain
          title="Evidence chain"
          emptyBody="Attach source artifacts to build an auditable chain."
          emptyTitle="No evidence linked"
          items={[
            {
              artifactId: "artifact://bundle/source-summary",
              label: "Source summary",
              meta: "World Bank CPI + IMF fiscal snapshot",
              badge: <Badge kind="ok">Verified</Badge>,
              href: "https://example.com/source-summary",
            },
            {
              artifactId: "artifact://bundle/legal-note",
              label: "Legal note",
              meta: "Jurisdictional constraints for subsidy rollout",
              badge: <Badge kind="warn">Review</Badge>,
              href: "https://example.com/legal-note",
            },
          ]}
        />
      </div>

      <DataTable
        label="Promotion queue"
        rows={runRows}
        rowKey={(row) => row.runId}
        columns={[
          {
            header: "Run",
            key: "runId",
            render: (row) => row.runId,
          },
          {
            header: "Status",
            key: "status",
            render: (row) => (
              <Badge kind={row.status === "approved" ? "ok" : "warn"}>
                {row.status}
              </Badge>
            ),
          },
          {
            header: "Confidence",
            key: "confidence",
            render: (row) => row.confidence,
          },
          {
            header: "Blockers",
            key: "blockers",
            render: (row) => row.blockers,
          },
        ]}
      />
    </div>
  ),
};
