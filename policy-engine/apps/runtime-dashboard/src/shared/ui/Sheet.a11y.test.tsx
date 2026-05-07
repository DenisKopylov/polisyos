import { expectNoA11yViolations } from "@/test/a11y";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "./Sheet";

describe("Sheet accessibility", () => {
  it("has no detectable accessibility violations when open", async () => {
    await expectNoA11yViolations(
      <Sheet open>
        <SheetTrigger asChild>
          <button type="button">Open details</button>
        </SheetTrigger>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Decision packet</SheetTitle>
            <SheetDescription>
              Review the summary before sharing it with the operator.
            </SheetDescription>
          </SheetHeader>
          <SheetFooter>
            <button type="button">Close</button>
            <button type="button">Download JSON</button>
          </SheetFooter>
        </SheetContent>
      </Sheet>,
      {
        includeDocumentBody: true,
      },
    );
  });
});
