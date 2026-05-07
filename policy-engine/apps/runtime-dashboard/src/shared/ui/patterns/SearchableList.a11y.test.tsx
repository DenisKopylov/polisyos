import { vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { SearchableList } from "./SearchableList";

describe("SearchableList accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <SearchableList
        items={[{ id: "evidence", label: "Evidence registry" }]}
        query=""
        onQueryChange={vi.fn()}
        getItemKey={(item) => item.id}
        getSearchText={(item) => item.label}
        renderItem={(item) => <article>{item.label}</article>}
        emptyTitle="No matches"
        emptyBody="Try a different search."
        placeholder="Search evidence"
      />,
    );
  });
});
