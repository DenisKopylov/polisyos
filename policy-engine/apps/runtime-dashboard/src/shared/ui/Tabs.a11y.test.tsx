import { expectNoA11yViolations } from "@/test/a11y";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "./Tabs";

describe("Tabs accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <Tabs defaultValue="overview">
        <TabsList aria-label="Run detail sections">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="evidence">Evidence</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">Overview content</TabsContent>
        <TabsContent value="evidence">Evidence content</TabsContent>
      </Tabs>,
    );
  });
});
