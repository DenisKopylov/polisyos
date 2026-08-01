import { render, screen } from "@testing-library/react";

import { DetailLayout, FilterPanel } from "../src/index";

describe("pattern components", () => {
  it("exports both migrated presentation patterns from the package owner", () => {
    expect(DetailLayout).toBeTypeOf("function");
    expect(FilterPanel).toBeTypeOf("function");
  });

  it("renders every supplied detail region", () => {
    const { container } = render(
      <DetailLayout
        className="consumer-layout"
        header={<header>Decision header</header>}
        sidebar={<aside>Evidence navigation</aside>}
        content={<main>Decision content</main>}
        footer={<footer>Decision footer</footer>}
      />,
    );

    expect(screen.getByText("Decision header")).toBeInTheDocument();
    expect(screen.getByText("Evidence navigation")).toBeInTheDocument();
    expect(screen.getByText("Decision content")).toBeInTheDocument();
    expect(screen.getByText("Decision footer")).toBeInTheDocument();
    expect(container.firstElementChild).toHaveClass("consumer-layout");
  });

  it("uses the single-column detail posture when no sidebar is supplied", () => {
    const { container } = render(<DetailLayout content="Only content" />);

    expect(container.querySelector(".grid")).toHaveClass("grid-cols-1");
    expect(container.querySelector(".grid")).not.toHaveClass(
      "xl:grid-cols-[280px,1fr]",
    );
  });

  it("renders filter presentation copy, actions, and children", () => {
    render(
      <FilterPanel
        title="Evidence filters"
        description="Narrow the evidence set."
        actions={<button type="button">Reset filters</button>}
      >
        <label>
          Status
          <select aria-label="Status">
            <option>All</option>
          </select>
        </label>
      </FilterPanel>,
    );

    expect(
      screen.getByRole("heading", { name: "Evidence filters" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Narrow the evidence set.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Reset filters" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Status" })).toBeInTheDocument();
  });
});
