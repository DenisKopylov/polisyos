import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { SearchableList } from "@/shared/ui/patterns/SearchableList";

const items = [
  { id: "alpha", label: "Alpha policy" },
  { id: "beta", label: "Beta report" },
];

function SearchableListHarness() {
  const [query, setQuery] = useState("");

  return (
    <SearchableList
      items={items}
      query={query}
      onQueryChange={setQuery}
      getItemKey={(item) => item.id}
      getSearchText={(item) => item.label}
      renderItem={(item) => <span>{item.label}</span>}
      emptyTitle="No matches"
      emptyBody="Try a broader query."
      placeholder="Search records"
      className="searchable-list"
    />
  );
}

describe("SearchableList", () => {
  it("renders and filters matching items", async () => {
    const user = userEvent.setup();
    render(<SearchableListHarness />);

    expect(screen.getByPlaceholderText("Search records")).toBeInTheDocument();
    expect(screen.getByText("Alpha policy")).toBeInTheDocument();
    expect(screen.getByText("Beta report")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("Search records"), "alp");

    await waitFor(() => {
      expect(screen.getByText("Alpha policy")).toBeInTheDocument();
      expect(screen.queryByText("Beta report")).not.toBeInTheDocument();
    });
  });

  it("shows the empty state when no items match the query", async () => {
    const user = userEvent.setup();
    render(<SearchableListHarness />);

    await user.type(screen.getByPlaceholderText("Search records"), "zzz");

    await waitFor(() => {
      expect(screen.getByText("No matches")).toBeInTheDocument();
      expect(screen.getByText("Try a broader query.")).toBeInTheDocument();
    });
  });
});
