import { expectNoA11yViolations } from "@/test/a11y";

import { DataTable } from "./DataTable";

describe("DataTable accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <DataTable
        rows={[
          { id: "run-1", status: "completed" },
          { id: "run-2", status: "running" },
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
