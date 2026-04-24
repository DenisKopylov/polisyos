import { expectNoA11yViolations } from "@/test/a11y";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./Tooltip";

describe("Tooltip accessibility", () => {
  it("has no detectable accessibility violations when open", async () => {
    await expectNoA11yViolations(
      <main>
        <TooltipProvider>
          <Tooltip open>
            <TooltipTrigger asChild>
              <button type="button">Why blocked?</button>
            </TooltipTrigger>
            <TooltipContent>
              Governance requires one more evidence refresh.
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </main>,
      {
        includeDocumentBody: true,
      },
    );
  });
});
