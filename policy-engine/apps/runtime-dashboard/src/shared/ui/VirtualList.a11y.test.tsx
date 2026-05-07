import { expectNoA11yViolations } from "@/test/a11y";

import { VirtualList } from "./VirtualList";

describe("VirtualList accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <div aria-label="Runs" role="list">
        <VirtualList
          items={[
            { id: "run-1", label: "Run 1" },
            { id: "run-2", label: "Run 2" },
          ]}
          itemKey={(item) => item.id}
          renderItem={(item) => <div role="listitem">{item.label}</div>}
        />
      </div>,
    );
  });
});
