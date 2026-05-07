import type { Meta, StoryObj } from "@storybook/react-vite";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { queryKeys } from "@/api/queryKeys";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { PolicyDiffView } from "./PolicyDiffView";
import { policyDiffFixture } from "./fixtures";

const meta = {
  title: "Features/Runs/PolicyDiffView",
  component: PolicyDiffView,
  decorators: [
    (Story) => {
      const queryClient = new QueryClient();
      queryClient.setQueryData(
        queryKeys.runCompare("run-a", "run-b", null),
        policyDiffFixture,
      );
      return (
        <QueryClientProvider client={queryClient}>
          <LocaleProvider>
            <Story />
          </LocaleProvider>
        </QueryClientProvider>
      );
    },
  ],
} satisfies Meta<typeof PolicyDiffView>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    runAId: "run-a",
    runBId: "run-b",
  },
};
