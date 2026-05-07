import { expectNoA11yViolations } from "@/test/a11y";

import { Popover, PopoverContent, PopoverTrigger } from "./Popover";

describe("Popover accessibility", () => {
  it("has no detectable accessibility violations when open", async () => {
    await expectNoA11yViolations(
      <main>
        <Popover open>
          <PopoverTrigger asChild>
            <button type="button">Open help</button>
          </PopoverTrigger>
          <PopoverContent aria-label="Evidence summary">
            <p className="font-semibold">Evidence summary</p>
            <p className="mt-2 text-sm">
              Promotions remain blocked until provenance is refreshed.
            </p>
          </PopoverContent>
        </Popover>
      </main>,
      {
        includeDocumentBody: true,
      },
    );
  });
});
