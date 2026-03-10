import type { Meta, StoryObj } from "@storybook/react-vite";

import { RuntimeApiRequestError } from "@/api/http";
import { ApiErrorAlert } from "@/shared/ui/ApiErrorAlert";
import { Button } from "@/shared/ui/Button";
import { EmptyState } from "@/shared/ui/EmptyState";

const meta = {
  title: "Shared UI/Feedback",
  component: EmptyState,
  tags: ["autodocs"],
  args: {
    title: "No promotion candidates",
    body: "The current evidence queue is clear. New candidates will appear when source exploration completes.",
  },
} satisfies Meta<typeof EmptyState>;

export default meta;

type Story = StoryObj<typeof meta>;

const sampleError = new RuntimeApiRequestError(
  {
    type: "about:blank",
    title: "Unauthorized",
    status: 403,
    status_code: 403,
    detail: "Legal review access is required for this workspace.",
    code: "authz_denied",
    instance: null,
    request_id: "req-storybook",
    error: null,
  },
  403,
  "Unable to load governance queue",
);

export const Empty: Story = {
  args: {
    title: "No promotion candidates",
    body: "The current evidence queue is clear. New candidates will appear when source exploration completes.",
  },
  render: () => (
    <EmptyState
      title="No promotion candidates"
      body="The current evidence queue is clear. New candidates will appear when source exploration completes."
      actions={<Button variant="ghost">Open evidence fabric</Button>}
    />
  ),
};

export const ErrorAlert: Story = {
  args: {
    title: "Governance queue unavailable",
    body: "Runtime access failed.",
  },
  render: () => (
    <ApiErrorAlert title="Governance queue unavailable" error={sampleError} />
  ),
};
