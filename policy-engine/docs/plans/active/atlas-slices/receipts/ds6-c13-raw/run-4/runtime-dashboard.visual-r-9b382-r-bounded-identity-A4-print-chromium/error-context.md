# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: runtime-dashboard.visual.spec.ts >> runtime-dashboard visual baselines >> DS8 governed run paper >> bounded identity A4 print
- Location: e2e/runtime-dashboard.visual.spec.ts:1316:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByTestId('run-report-page')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for getByTestId('run-report-page')

```

# Page snapshot

```yaml
- generic [ref=e2]:
  - generic [ref=e3]:
    - text: (#main-content)
    - generic [ref=e5]:
      - text: (/) (/compose) (/runs) (/evidence) (/knowledge) (/platform)
      - generic [ref=e6]:
        - banner [ref=e7]:
          - generic [ref=e8]:
            - generic [ref=e9]:
              - img [ref=e10]
              - generic [ref=e15]: Atlas analyst shell
            - paragraph [ref=e16]: Run analysis
            - heading "Decision workspace turns artifacts into one operating view" [level=2] [ref=e17]
            - paragraph [ref=e18]: Inspect run lifecycle, decisions, governance, and provenance in one workspace.
          - text: (/runs) (/compose)
        - generic [ref=e19]:
          - slider "Temporal cursor" [ref=e21] [cursor=pointer]: "1788199200000"
          - generic [ref=e26]:
            - generic [ref=e29]: Observed
            - generic [ref=e32]: Simulated
          - button "Now" [ref=e33]:
            - img [ref=e34]
            - generic [ref=e37]: Now
          - generic [ref=e39]: August 31, 2026
        - main [active] [ref=e40]
  - region "Notifications"
  - status [ref=e54]
  - alert [ref=e55]
```

# Test source

```ts
  622 |       !isRecord(payload.document) ||
  623 |       typeof payload.document.render_timestamp !== "string"
  624 |     ) {
  625 |       throw new TypeError("visual fixture expected document.render_timestamp");
  626 |     }
  627 |     if (!Array.isArray(payload.document.blocks)) {
  628 |       throw new TypeError("visual fixture expected document.blocks");
  629 |     }
  630 |     let generatedLineCount = 0;
  631 |     const blocks = payload.document.blocks.map((block) => {
  632 |       if (!isRecord(block) || !Array.isArray(block.items)) {
  633 |         return block;
  634 |       }
  635 |       const items = block.items.map((item) => {
  636 |         if (typeof item === "string" && item.startsWith("Дата формування: ")) {
  637 |           generatedLineCount += 1;
  638 |           return BUREAUCRATIC_GENERATED_LINE;
  639 |         }
  640 |         return item;
  641 |       });
  642 |       return { ...block, items };
  643 |     });
  644 |     if (generatedLineCount !== 1) {
  645 |       throw new TypeError(
  646 |         `visual fixture expected one bureaucratic generated-at line, received ${generatedLineCount}`,
  647 |       );
  648 |     }
  649 |     await route.fulfill({
  650 |       response,
  651 |       json: {
  652 |         ...payload,
  653 |         document: {
  654 |           ...payload.document,
  655 |           blocks,
  656 |           render_timestamp: VISUAL_CLOCK_TIME,
  657 |         },
  658 |       },
  659 |     });
  660 |   });
  661 | }
  662 | 
  663 | async function waitForDashboardCharts(page: Page) {
  664 |   const charts = page.locator(
  665 |     '[data-testid="dashboard-page"] .recharts-responsive-container',
  666 |   );
  667 |   await expect(charts).toHaveCount(2);
  668 |   await expect(
  669 |     page
  670 |       .locator('[data-testid="dashboard-page"] .recharts-bar-rectangle')
  671 |       .first(),
  672 |   ).toBeVisible();
  673 |   await expect(
  674 |     page.locator('[data-testid="dashboard-page"] .recharts-line-curve').first(),
  675 |   ).toHaveAttribute("d", /^M.+L/);
  676 |   await expect
  677 |     .poll(() =>
  678 |       charts.evaluateAll((elements) =>
  679 |         elements.every((element) => {
  680 |           const bounds = element.getBoundingClientRect();
  681 |           return bounds.width > 0 && bounds.height > 0;
  682 |         }),
  683 |       ),
  684 |     )
  685 |     .toBe(true);
  686 |   await expect(page.locator("html")).toHaveAttribute(
  687 |     "data-reduced-motion",
  688 |     "reduce",
  689 |   );
  690 |   await waitForVisualFonts(page);
  691 | 
  692 |   await waitForStableRender(charts);
  693 | }
  694 | 
  695 | async function openEvidencePrimitiveStory(page: Page, storyId: string) {
  696 |   await page.goto(
  697 |     `${STORYBOOK_BASE_URL}/iframe.html?id=${encodeURIComponent(storyId)}&viewMode=story`,
  698 |   );
  699 |   const story = page.locator("#storybook-root");
  700 |   await expect(story).toBeVisible({ timeout: 15_000 });
  701 |   await waitForVisualFonts(page);
  702 |   return story;
  703 | }
  704 | 
  705 | async function openPrintSurface(
  706 |   page: Page,
  707 |   {
  708 |     path,
  709 |     readySelector,
  710 |     readyTestId,
  711 |     selector,
  712 |   }: {
  713 |     path: string;
  714 |     readySelector?: string;
  715 |     readyTestId: string;
  716 |     selector: string;
  717 |   },
  718 | ): Promise<Locator> {
  719 |   await page.setViewportSize({ width: 794, height: 1123 });
  720 |   await page.emulateMedia({ media: "print" });
  721 |   await page.goto(path);
> 722 |   await expect(page.getByTestId(readyTestId)).toBeVisible();
      |                                               ^ Error: expect(locator).toBeVisible() failed
  723 |   await expect(page.locator(selector)).toBeVisible();
  724 |   if (readySelector) {
  725 |     await expect(page.locator(readySelector)).toBeVisible();
  726 |     await waitForStableRender(page.locator(readySelector));
  727 |   }
  728 |   await waitForVisualFonts(page);
  729 |   const surface = page.locator(selector);
  730 |   await waitForStableRender(surface);
  731 |   return surface;
  732 | }
  733 | 
  734 | test.describe("runtime-dashboard visual baselines", () => {
  735 |   test.use({
  736 |     viewport: { width: 1440, height: 1200 },
  737 |   });
  738 | 
  739 |   test.beforeAll(async ({ request }) => {
  740 |     const metadata = readFixtureMetadata();
  741 |     requireRunPaperFixtureMetadata(metadata);
  742 |     fixtureMetadata = metadata;
  743 |     await ensureDeterministicConnectorFixture(request);
  744 |   });
  745 | 
  746 |   test.beforeEach(async ({ page }) => {
  747 |     await page.clock.setFixedTime(VISUAL_CLOCK_TIME);
  748 |     await installDashboardTestState(page);
  749 |     await installVisualResponseMetadataFixture(
  750 |       page,
  751 |       fixtureMetadata.core_run_id,
  752 |     );
  753 |     await page.emulateMedia({ reducedMotion: "reduce" });
  754 |   });
  755 | 
  756 |   test("binds visual response metadata to the visual clock", async ({
  757 |     page,
  758 |   }) => {
  759 |     const responsePaths = visualResponseMetadataPaths(
  760 |       fixtureMetadata.core_run_id,
  761 |     );
  762 | 
  763 |     await page.goto("/");
  764 |     const visualTimeBeforeWait = await page.evaluate(() =>
  765 |       new Date().toISOString(),
  766 |     );
  767 |     await page.waitForTimeout(50);
  768 |     const visualTimeAfterWait = await page.evaluate(() =>
  769 |       new Date().toISOString(),
  770 |     );
  771 |     expect(visualTimeBeforeWait).toBe(VISUAL_CLOCK_TIME);
  772 |     expect(visualTimeAfterWait).toBe(VISUAL_CLOCK_TIME);
  773 | 
  774 |     const generatedTimes = await page.evaluate(async (paths) => {
  775 |       return Promise.all(
  776 |         paths.map(async (path) => {
  777 |           const response = await fetch(path);
  778 |           if (!response.ok) {
  779 |             throw new Error(
  780 |               `visual fixture request failed at ${path}: ${response.status}`,
  781 |             );
  782 |           }
  783 |           const payload: unknown = await response.json();
  784 |           if (
  785 |             typeof payload !== "object" ||
  786 |             payload === null ||
  787 |             !("meta" in payload) ||
  788 |             typeof payload.meta !== "object" ||
  789 |             payload.meta === null ||
  790 |             !("generated_at" in payload.meta)
  791 |           ) {
  792 |             throw new TypeError(
  793 |               `visual fixture expected meta.generated_at at ${path}`,
  794 |             );
  795 |           }
  796 |           return payload.meta.generated_at;
  797 |         }),
  798 |       );
  799 |     }, responsePaths);
  800 | 
  801 |     for (const generatedAt of generatedTimes) {
  802 |       expect(generatedAt).toBe(VISUAL_CLOCK_TIME);
  803 |     }
  804 |   });
  805 | 
  806 |   test("command center shell", async ({ page }) => {
  807 |     await page.goto("/");
  808 |     await waitForDashboardSurface(page, "dashboard");
  809 |     await waitForDashboardCharts(page);
  810 |     await expect(page.locator(".workspace-frame").first()).toHaveScreenshot(
  811 |       "command-center-shell.png",
  812 |       {
  813 |         animations: "disabled",
  814 |         caret: "hide",
  815 |       },
  816 |     );
  817 |   });
  818 | 
  819 |   test("scenario composer dark theme", async ({ page }) => {
  820 |     await installDashboardTestState(page, { theme: "dark" });
  821 |     await page.goto("/compose");
  822 |     await expect(
```