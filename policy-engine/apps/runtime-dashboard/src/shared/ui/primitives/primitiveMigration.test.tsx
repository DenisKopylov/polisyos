import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Search } from "lucide-react";
import * as atlasUi from "@polisyos/atlas-ui";

import { ApiErrorAlert } from "@/shared/ui/ApiErrorAlert";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

describe("foundation primitive migration", () => {
  it("renders migrated foundation primitives from the package without compatibility shims", () => {
    expect(Object.keys(atlasUi)).toEqual(
      expect.arrayContaining([
        "AsyncSection",
        "Badge",
        "Button",
        "Card",
        "EmptyState",
        "Icon",
        "PageSkeleton",
        "Text",
      ]),
    );

    render(
      <LocaleProvider>
        <atlasUi.Card data-testid="card">
          <atlasUi.AsyncSection
            query={{ isError: false, isLoading: false }}
            renderError={({ error, title }) => (
              <ApiErrorAlert error={error} title={title} />
            )}
          >
            <atlasUi.Badge kind="info">Live</atlasUi.Badge>
            <atlasUi.Button type="button">Inspect</atlasUi.Button>
            <atlasUi.EmptyState title="Empty" body="Nothing to inspect" />
            <atlasUi.Icon icon={Search} label="Search" />
            <atlasUi.PageSkeleton />
            <atlasUi.Text>Runtime evidence</atlasUi.Text>
          </atlasUi.AsyncSection>
        </atlasUi.Card>
      </LocaleProvider>,
    );

    expect(screen.getByTestId("card")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Inspect" })).toBeInTheDocument();
    expect(screen.getByLabelText("Search")).toBeInTheDocument();
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
    expect(screen.getByText("Runtime evidence")).toBeInTheDocument();
  });

  it("preserves form labels focus and validation after direct package migration", async () => {
    const user = userEvent.setup();

    expect(Object.keys(atlasUi)).toEqual(
      expect.arrayContaining([
        "Checkbox",
        "Input",
        "Label",
        "Radio",
        "SegmentedControl",
        "Select",
        "Slider",
        "Switch",
        "Textarea",
        "ToggleButton",
      ]),
    );

    render(
      <form aria-label="Policy form">
        <atlasUi.Label htmlFor="policy-title">Policy title</atlasUi.Label>
        <atlasUi.Input id="policy-title" name="title" required />
        <atlasUi.Checkbox aria-label="Include evidence" />
      </form>,
    );

    const title = screen.getByRole("textbox", { name: "Policy title" });
    expect(title).toBeInvalid();

    await user.click(screen.getByText("Policy title"));
    expect(title).toHaveFocus();

    await user.type(title, "Evidence-backed policy");
    expect(title).toBeValid();
    expect(
      screen.getByRole("checkbox", { name: "Include evidence" }),
    ).toBeInTheDocument();
  });
});
