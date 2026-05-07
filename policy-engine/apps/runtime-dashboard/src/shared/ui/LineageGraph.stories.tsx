import type { Meta, StoryObj } from "@storybook/react-vite";

import LineageGraph from "@/shared/ui/LineageGraph";

const nodes = [
  {
    artifact_id: "artifact-root",
    depth: 0,
    kind: "decision.packet",
    status: "ok",
  },
  {
    artifact_id: "artifact-plan",
    depth: 1,
    kind: "workflow.plan",
    status: "partial",
  },
  {
    artifact_id: "artifact-gov",
    depth: 1,
    kind: "governance.report",
    status: "ok",
  },
  {
    artifact_id: "artifact-trace",
    depth: 2,
    kind: "trace.timeline",
    status: "ok",
  },
];

const edges = [
  {
    parent_artifact_id: "artifact-root",
    child_artifact_id: "artifact-plan",
    role: "plan",
  },
  {
    parent_artifact_id: "artifact-root",
    child_artifact_id: "artifact-gov",
    role: "governance",
  },
  {
    parent_artifact_id: "artifact-plan",
    child_artifact_id: "artifact-trace",
    role: "trace",
  },
];

const meta = {
  title: "Shared UI/LineageGraph",
  component: LineageGraph,
  tags: ["autodocs"],
  args: {
    rootArtifactIds: ["artifact-root"],
    nodes,
    edges,
  },
} satisfies Meta<typeof LineageGraph>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    rootArtifactIds: ["artifact-root"],
    nodes,
    edges,
  },
  render: () => (
    <LineageGraph
      rootArtifactIds={["artifact-root"]}
      nodes={nodes}
      edges={edges}
    />
  ),
};
