import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createRef, useState } from "react";
import { vi } from "vitest";

import * as atlasUi from "../src/index";

describe("overlay primitives", () => {
  it("preserves dialog portal focus escape dismissal refs and localized copy props", async () => {
    const contentRef = createRef<HTMLDivElement>();
    const onOpenChange = vi.fn();

    function DialogHarness() {
      const [open, setOpen] = useState(false);
      return (
        <atlasUi.Dialog
          open={open}
          onOpenChange={(nextOpen) => {
            onOpenChange(nextOpen);
            setOpen(nextOpen);
          }}
        >
          <atlasUi.DialogTrigger asChild>
            <button type="button">Open review</button>
          </atlasUi.DialogTrigger>
          <atlasUi.DialogContent ref={contentRef} closeLabel="Dismiss review">
            <atlasUi.DialogTitle>Evidence review</atlasUi.DialogTitle>
            <atlasUi.DialogDescription>
              Inspect the bound evidence before continuing.
            </atlasUi.DialogDescription>
            <button type="button">Continue review</button>
          </atlasUi.DialogContent>
        </atlasUi.Dialog>
      );
    }

    const { container } = render(<DialogHarness />);
    const trigger = screen.getByRole("button", { name: "Open review" });
    fireEvent.click(trigger);

    const dialog = await screen.findByRole("dialog", {
      name: "Evidence review",
    });
    expect(contentRef.current).toBe(dialog);
    expect(document.body).toContainElement(dialog);
    expect(container).not.toContainElement(dialog);
    expect(
      screen.getByRole("button", { name: "Continue review" }),
    ).toHaveFocus();
    expect(
      screen.getByRole("button", { name: "Dismiss review" }),
    ).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(dialog).not.toBeInTheDocument());
    expect(onOpenChange).toHaveBeenLastCalledWith(false);
    expect(trigger).toHaveFocus();
  });

  it("preserves command composition dialog dependency refs and accessible title", async () => {
    const commandRef = createRef<HTMLDivElement>();
    const inputRef = createRef<HTMLInputElement>();

    render(
      <>
        <atlasUi.CommandDialog
          open
          title="Policy commands"
          closeLabel="Dismiss policy commands"
        >
          <atlasUi.CommandInput
            ref={inputRef}
            aria-label="Search policy commands"
          />
          <atlasUi.CommandList>
            <atlasUi.CommandEmpty>No commands</atlasUi.CommandEmpty>
            <atlasUi.CommandGroup heading="Navigation">
              <atlasUi.CommandItem value="open report">
                Open report
                <atlasUi.CommandShortcut>Enter</atlasUi.CommandShortcut>
              </atlasUi.CommandItem>
            </atlasUi.CommandGroup>
            <atlasUi.CommandSeparator />
          </atlasUi.CommandList>
        </atlasUi.CommandDialog>
        <atlasUi.Command ref={commandRef} aria-label="Standalone commands" />
      </>,
    );

    expect(
      await screen.findByRole("dialog", { name: "Policy commands" }),
    ).toBeInTheDocument();
    expect(commandRef.current).toHaveAttribute("cmdk-root", "");
    expect(inputRef.current).toHaveAttribute(
      "aria-label",
      "Search policy commands",
    );
    expect(inputRef.current).toHaveAttribute("role", "combobox");
    expect(
      screen.getByRole("button", { name: "Dismiss policy commands" }),
    ).toBeInTheDocument();
  });

  it("preserves popover portal outside dismissal props and forwarded ref", async () => {
    const contentRef = createRef<HTMLDivElement>();
    const onOpenChange = vi.fn();

    function PopoverHarness() {
      const [open, setOpen] = useState(false);
      return (
        <atlasUi.Popover
          open={open}
          onOpenChange={(nextOpen) => {
            onOpenChange(nextOpen);
            setOpen(nextOpen);
          }}
        >
          <atlasUi.PopoverAnchor asChild>
            <span>Evidence anchor</span>
          </atlasUi.PopoverAnchor>
          <atlasUi.PopoverTrigger asChild>
            <button type="button">Open provenance</button>
          </atlasUi.PopoverTrigger>
          <atlasUi.PopoverContent
            ref={contentRef}
            align="start"
            sideOffset={12}
            aria-label="Provenance details"
          >
            Verified source
          </atlasUi.PopoverContent>
        </atlasUi.Popover>
      );
    }

    const { container } = render(<PopoverHarness />);
    fireEvent.click(screen.getByRole("button", { name: "Open provenance" }));

    const content = await screen.findByLabelText("Provenance details");
    expect(contentRef.current).toBe(content);
    expect(content).toHaveAttribute("data-align", "start");
    expect(document.body).toContainElement(content);
    expect(container).not.toContainElement(content);

    fireEvent.pointerDown(document.body);
    fireEvent.click(document.body);
    await waitFor(() => expect(content).not.toBeInTheDocument());
    expect(onOpenChange).toHaveBeenLastCalledWith(false);
  });

  it("preserves tooltip portal props and forwarded ref", async () => {
    const contentRef = createRef<HTMLDivElement>();
    const { container } = render(
      <atlasUi.TooltipProvider delayDuration={0}>
        <atlasUi.Tooltip open>
          <atlasUi.TooltipTrigger asChild>
            <button type="button">Why limited?</button>
          </atlasUi.TooltipTrigger>
          <atlasUi.TooltipContent ref={contentRef} side="top" sideOffset={8}>
            Evidence is stale
          </atlasUi.TooltipContent>
        </atlasUi.Tooltip>
      </atlasUi.TooltipProvider>,
    );

    const tooltip = await screen.findByRole("tooltip");
    await waitFor(() =>
      expect(contentRef.current).toHaveAttribute("data-side", "top"),
    );
    expect(contentRef.current).toContainElement(tooltip);
    expect(document.body).toContainElement(contentRef.current);
    expect(container).not.toContainElement(contentRef.current);
  });
});
