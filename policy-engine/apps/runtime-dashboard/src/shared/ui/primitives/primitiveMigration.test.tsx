import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Search } from "lucide-react";
import { useState } from "react";
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

  it("preserves overlay focus dismissal and portal behavior after direct package migration", async () => {
    const user = userEvent.setup();

    expect(Object.keys(atlasUi)).toEqual(
      expect.arrayContaining([
        "CommandDialog",
        "Dialog",
        "DialogContent",
        "DialogTitle",
        "Popover",
        "PopoverContent",
        "PopoverTrigger",
        "Tooltip",
        "TooltipContent",
        "TooltipProvider",
        "TooltipTrigger",
      ]),
    );

    function OverlayHarness() {
      const [dialogOpen, setDialogOpen] = useState(false);
      const [popoverOpen, setPopoverOpen] = useState(false);

      return (
        <atlasUi.TooltipProvider delayDuration={0}>
          <atlasUi.Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <atlasUi.DialogTrigger asChild>
              <button type="button">Open decision</button>
            </atlasUi.DialogTrigger>
            <atlasUi.DialogContent aria-describedby={undefined}>
              <atlasUi.DialogTitle>Decision evidence</atlasUi.DialogTitle>
              <button type="button">Review evidence</button>
            </atlasUi.DialogContent>
          </atlasUi.Dialog>

          <atlasUi.Popover open={popoverOpen} onOpenChange={setPopoverOpen}>
            <atlasUi.PopoverTrigger asChild>
              <button type="button">Open provenance</button>
            </atlasUi.PopoverTrigger>
            <atlasUi.PopoverContent aria-label="Provenance details">
              Verified source
            </atlasUi.PopoverContent>
          </atlasUi.Popover>

          <atlasUi.Tooltip>
            <atlasUi.TooltipTrigger asChild>
              <button type="button">Why limited?</button>
            </atlasUi.TooltipTrigger>
            <atlasUi.TooltipContent>Evidence is stale</atlasUi.TooltipContent>
          </atlasUi.Tooltip>
        </atlasUi.TooltipProvider>
      );
    }

    const { container } = render(<OverlayHarness />);
    const dialogTrigger = screen.getByRole("button", {
      name: "Open decision",
    });
    await user.click(dialogTrigger);

    const dialog = screen.getByRole("dialog", { name: "Decision evidence" });
    expect(document.body).toContainElement(dialog);
    expect(container).not.toContainElement(dialog);
    expect(
      screen.getByRole("button", { name: "Review evidence" }),
    ).toHaveFocus();

    await user.keyboard("{Escape}");
    await waitFor(() => expect(dialog).not.toBeInTheDocument());
    expect(dialogTrigger).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Open provenance" }));
    const popover = screen.getByLabelText("Provenance details");
    expect(document.body).toContainElement(popover);
    expect(container).not.toContainElement(popover);
    await user.click(document.body);
    await waitFor(() => expect(popover).not.toBeInTheDocument());

    const tooltipTrigger = screen.getByRole("button", { name: "Why limited?" });
    await user.hover(tooltipTrigger);
    const tooltip = await screen.findByRole("tooltip");
    expect(document.body).toContainElement(tooltip);
    expect(container).not.toContainElement(tooltip);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(tooltip).not.toBeInTheDocument());
  });
});
