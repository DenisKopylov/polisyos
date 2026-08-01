/* eslint-disable testing-library/prefer-screen-queries */
import { render } from "@testing-library/react";

import { AsyncSection } from "@polisyos/atlas-ui";
import { renderApiErrorAlert } from "./ApiErrorAlert";

describe("AsyncSection", () => {
  it("renders loading state first", () => {
    const view = render(
      <AsyncSection
        query={{ isLoading: true, isError: false }}
        renderError={renderApiErrorAlert}
        loading={<div>Loading section</div>}
      >
        <div>Loaded content</div>
      </AsyncSection>,
    );

    expect(view.getByText("Loading section")).toBeInTheDocument();
    expect(view.queryByText("Loaded content")).not.toBeInTheDocument();
  });

  it("renders empty state when data is absent", () => {
    const view = render(
      <AsyncSection
        query={{ isLoading: false, isError: false }}
        renderError={renderApiErrorAlert}
        empty
        emptyState={<div>Nothing to show</div>}
      >
        <div>Loaded content</div>
      </AsyncSection>,
    );

    expect(view.getByText("Nothing to show")).toBeInTheDocument();
  });
});
