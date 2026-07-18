import { expectNoA11yViolations } from "@/test/a11y";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@polisyos/atlas-ui";

describe("Dialog accessibility", () => {
  it("has no detectable accessibility violations when open", async () => {
    await expectNoA11yViolations(
      <Dialog open>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm action</DialogTitle>
            <DialogDescription>
              This dialog explains the consequence before submission.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button type="button">Cancel</button>
            <button type="button">Continue</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>,
      {
        includeDocumentBody: true,
      },
    );
  });
});
