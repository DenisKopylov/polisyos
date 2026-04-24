import { expectNoA11yViolations } from "@/test/a11y";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./DropdownMenu";

describe("DropdownMenu accessibility", () => {
  it("has no detectable accessibility violations when open", async () => {
    await expectNoA11yViolations(
      <main>
        <DropdownMenu open>
          <DropdownMenuTrigger asChild>
            <button type="button">Open actions</button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Open report</DropdownMenuItem>
            <DropdownMenuItem>Download packet</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem>Archive run</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </main>,
      {
        includeDocumentBody: true,
      },
    );
  });
});
