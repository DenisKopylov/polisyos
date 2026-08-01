import { render } from "@testing-library/react";
import { axe } from "vitest-axe";

import { JsonPreview, VirtualList, VirtualTable } from "../src/index";

describe("compound component accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    const { container } = render(
      <div>
        <JsonPreview
          data={{ blockers: 1, decision: "approve_with_conditions" }}
        />
        <div aria-label="Runs" role="list">
          <VirtualList
            items={[
              { id: "run-1", label: "Run 1" },
              { id: "run-2", label: "Run 2" },
            ]}
            itemKey={(item) => item.id}
            renderItem={(item) => <div role="listitem">{item.label}</div>}
          />
        </div>
        <VirtualTable
          ariaLabel="Recent runs"
          rows={[
            { id: "run-1", status: "running" },
            { id: "run-2", status: "completed" },
          ]}
          rowKey={(row) => row.id}
          columns={[
            { key: "id", header: "Run", render: (row) => row.id },
            {
              key: "status",
              header: "Status",
              render: (row) => row.status,
            },
          ]}
        />
      </div>,
    );

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
