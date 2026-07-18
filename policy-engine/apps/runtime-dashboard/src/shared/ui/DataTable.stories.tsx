import type { Meta, StoryObj } from "@storybook/react-vite";

import { Badge } from "@polisyos/atlas-ui";
import { DataTable } from "@/shared/ui/DataTable";

const rows = [
  { runId: "run-0101", status: "running", blockers: 0, score: "0.84" },
  {
    runId: "run-0100",
    status: "blocked_preflight",
    blockers: 2,
    score: "0.41",
  },
  { runId: "run-0098", status: "completed", blockers: 0, score: "0.92" },
];

const columns = [
  {
    key: "runId",
    header: "Run ID",
    render: (row: (typeof rows)[number]) => row.runId,
  },
  {
    key: "status",
    header: "Status",
    render: (row: (typeof rows)[number]) => (
      <Badge
        kind={
          row.status === "completed"
            ? "ok"
            : row.status === "running"
              ? "warn"
              : "fail"
        }
      >
        {row.status}
      </Badge>
    ),
  },
  {
    key: "blockers",
    header: "Blockers",
    render: (row: (typeof rows)[number]) => row.blockers,
  },
  {
    key: "score",
    header: "Score",
    render: (row: (typeof rows)[number]) => row.score,
  },
];

const meta = {
  title: "Shared UI/DataTable",
  tags: ["autodocs"],
} satisfies Meta;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: () => (
    <DataTable rows={rows} rowKey={(row) => row.runId} columns={[...columns]} />
  ),
};
