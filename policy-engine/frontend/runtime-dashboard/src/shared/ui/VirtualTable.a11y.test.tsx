import { expectNoA11yViolations } from "@/test/a11y";

import { VirtualTable } from "./VirtualTable";

describe("VirtualTable accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <VirtualTable
        ariaLabel="Recent runs"
        rows={[
          { id: "run-1", status: "running" },
          { id: "run-2", status: "completed" },
        ]}
        rowKey={(row) => row.id}
        columns={[
          {
            key: "id",
            header: "Run",
            render: (row) => row.id,
          },
          {
            key: "status",
            header: "Status",
            render: (row) => row.status,
          },
        ]}
      />,
    );
  });
});
