import { render, screen, waitFor } from "@testing-library/react";
import { axe } from "vitest-axe";

import {
  CommandDialog,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  Popover,
  PopoverContent,
  PopoverTrigger,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../src/index";

const WCAG_AA_OPTIONS = {
  runOnly: {
    type: "tag" as const,
    values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22a", "wcag22aa"],
  },
};

describe("overlay primitive accessibility", () => {
  it("has no detectable command or dialog accessibility violations", async () => {
    render(
      <CommandDialog open title="Policy commands">
        <CommandInput aria-label="Search policy commands" />
        <CommandList>
          <CommandGroup heading="Navigation">
            <CommandItem value="open report">Open report</CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>,
    );
    expect((await axe(document.body, WCAG_AA_OPTIONS)).violations).toHaveLength(
      0,
    );
  });

  it("has no detectable standalone dialog accessibility violations", async () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogTitle>Confirm action</DialogTitle>
          <DialogDescription>
            Review the consequence before continuing.
          </DialogDescription>
        </DialogContent>
      </Dialog>,
    );
    expect((await axe(document.body, WCAG_AA_OPTIONS)).violations).toHaveLength(
      0,
    );
  });

  it("has no detectable popover accessibility violations", async () => {
    render(
      <Popover open>
        <PopoverTrigger asChild>
          <button type="button">Open provenance</button>
        </PopoverTrigger>
        <PopoverContent aria-label="Provenance details">
          Verified source
        </PopoverContent>
      </Popover>,
    );
    expect((await axe(document.body, WCAG_AA_OPTIONS)).violations).toHaveLength(
      0,
    );
  });

  it("has no detectable tooltip accessibility violations", async () => {
    render(
      <main>
        <TooltipProvider>
          <Tooltip open>
            <TooltipTrigger asChild>
              <button type="button">Why limited?</button>
            </TooltipTrigger>
            <TooltipContent>Evidence is stale</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </main>,
    );
    await screen.findByRole("tooltip");
    await waitFor(() =>
      expect(document.querySelector("[data-side]")).toBeInTheDocument(),
    );
    expect((await axe(document.body, WCAG_AA_OPTIONS)).violations).toHaveLength(
      0,
    );
  });
});
