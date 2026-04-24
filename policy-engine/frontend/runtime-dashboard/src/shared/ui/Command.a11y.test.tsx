import { expectNoA11yViolations } from "@/test/a11y";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "./Command";

describe("Command accessibility", () => {
  it("has no detectable accessibility violations when open", async () => {
    await expectNoA11yViolations(
      <CommandDialog open>
        <CommandInput placeholder="Search runs" />
        <CommandList>
          <CommandEmpty>No results</CommandEmpty>
          <CommandGroup heading="Quick actions">
            <CommandItem value="open-run">
              Open run
              <CommandShortcut>Enter</CommandShortcut>
            </CommandItem>
            <CommandItem value="open-report">Open report</CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>,
      {
        includeDocumentBody: true,
      },
    );
  });
});
