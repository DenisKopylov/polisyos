# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: runtime-dashboard.visual.spec.ts >> runtime-dashboard visual baselines >> DS8 governed run paper >> semantic DOM closes overview and report paper egress
- Location: e2e/runtime-dashboard.visual.spec.ts:1142:5

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

```
Error: page.waitForResponse: Test ended.
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
        - main [active] [ref=e19]
  - region "Notifications"
  - status [ref=e33]
  - alert [ref=e34]
```

# Test source

```ts
  21  |   installDashboardTestState,
  22  |   readFixtureMetadata,
  23  |   requireRunPaperFixtureMetadata,
  24  |   type RunPaperFixtureMetadata,
  25  |   waitForDashboardSurface,
  26  | } from "./helpers/runtime-dashboard";
  27  | 
  28  | const STORYBOOK_BASE_URL = "http://127.0.0.1:6006";
  29  | const FIXTURE_API_BASE_URL = "http://127.0.0.1:8000";
  30  | const VISUAL_CLOCK_TIME = "2026-01-01T00:00:00.000Z";
  31  | const BUREAUCRATIC_GENERATED_LINE =
  32  |   "Дата формування: 2026-01-01T00:00:00+00:00";
  33  | const VISUAL_CONNECTOR_ID = "worldbank.wdi@1.0.0";
  34  | const A4_WIDTH_POINTS = 595.2756;
  35  | const A4_HEIGHT_POINTS = 841.8898;
  36  | const A4_TOLERANCE_POINTS = 0.5;
  37  | type RunPaperPacket = components["schemas"]["RunPaperPacket"];
  38  | type HumanDecisionGateResponse =
  39  |   components["schemas"]["HumanDecisionGateResponse"];
  40  | let fixtureMetadata: RunPaperFixtureMetadata;
  41  | 
  42  | async function waitForVisualFonts(page: Page) {
  43  |   await page.evaluate(async () => {
  44  |     await document.fonts.ready;
  45  |   });
  46  | }
  47  | 
  48  | async function waitForStableRender(locator: Locator, timeout = 15_000) {
  49  |   let consecutiveEqualSignatures = 0;
  50  |   let previousSignature: string | null = null;
  51  |   await expect
  52  |     .poll(
  53  |       async () => {
  54  |         const signature = await locator.evaluateAll((elements) =>
  55  |           JSON.stringify(
  56  |             elements.map((element) => {
  57  |               const bounds = element.getBoundingClientRect();
  58  |               const style = getComputedStyle(element);
  59  |               return {
  60  |                 fontFamily: style.fontFamily,
  61  |                 fontSize: style.fontSize,
  62  |                 height: bounds.height,
  63  |                 markup: element.innerHTML,
  64  |                 width: bounds.width,
  65  |               };
  66  |             }),
  67  |           ),
  68  |         );
  69  |         consecutiveEqualSignatures =
  70  |           signature === previousSignature ? consecutiveEqualSignatures + 1 : 0;
  71  |         previousSignature = signature;
  72  |         return consecutiveEqualSignatures;
  73  |       },
  74  |       { timeout },
  75  |     )
  76  |     .toBeGreaterThanOrEqual(1);
  77  | }
  78  | 
  79  | async function horizontalOverflowOffenders(locator: Locator) {
  80  |   return locator.evaluate((root) =>
  81  |     [root, ...root.querySelectorAll("*")]
  82  |       .filter((element) => element.scrollWidth > element.clientWidth + 1)
  83  |       .map((element) => ({
  84  |         className: String(element.className),
  85  |         clientWidth: element.clientWidth,
  86  |         scrollWidth: element.scrollWidth,
  87  |         tagName: element.tagName,
  88  |         text: element.textContent?.trim().slice(0, 160) ?? "",
  89  |       })),
  90  |   );
  91  | }
  92  | 
  93  | async function documentHorizontalOverflow(page: Page) {
  94  |   return page.evaluate(() => {
  95  |     const scrollWidth = Math.max(
  96  |       document.documentElement.scrollWidth,
  97  |       document.body.scrollWidth,
  98  |     );
  99  |     const zoom =
  100 |       Number.parseFloat(getComputedStyle(document.documentElement).zoom) || 1;
  101 |     return {
  102 |       normalizedScrollWidth: scrollWidth / zoom,
  103 |       scrollWidth,
  104 |       viewportWidth: document.documentElement.clientWidth,
  105 |       zoom,
  106 |     };
  107 |   });
  108 | }
  109 | 
  110 | function isRecord(value: unknown): value is Record<string, unknown> {
  111 |   return typeof value === "object" && value !== null && !Array.isArray(value);
  112 | }
  113 | 
  114 | function isRunPaperResponse(url: string, runId: string) {
  115 |   return (
  116 |     new URL(url).pathname === `/api/v1/runs/${encodeURIComponent(runId)}/paper`
  117 |   );
  118 | }
  119 | 
  120 | async function openRunPaper(page: Page, runId: string) {
> 121 |   const responsePromise = page.waitForResponse(
      |                                ^ Error: page.waitForResponse: Test ended.
  122 |     (response) =>
  123 |       isRunPaperResponse(response.url(), runId) && response.status() === 200,
  124 |   );
  125 |   await page.goto(`/runs/${encodeURIComponent(runId)}/report`);
  126 |   await expect(page.getByTestId("run-report-page")).toBeVisible();
  127 |   const response = await responsePromise;
  128 |   const rawBytes = await response.body();
  129 |   const packet = (await response.json()) as RunPaperPacket;
  130 |   expect(packet.packet_schema_version).toBe(
  131 |     "policyos.runtime.run_paper_packet.v1",
  132 |   );
  133 |   expect(packet.run.run_id).toBe(runId);
  134 |   return { packet, rawBytes };
  135 | }
  136 | 
  137 | async function waitForRunPaperPdfReady(page: Page) {
  138 |   await waitForVisualFonts(page);
  139 |   await waitForStableRender(page.getByTestId("run-paper-document"));
  140 | }
  141 | 
  142 | async function censusVisiblePrintEgress(page: Page) {
  143 |   return page.evaluate(() => {
  144 |     const visible = (element: Element) => {
  145 |       const bounds = element.getBoundingClientRect();
  146 |       const style = getComputedStyle(element);
  147 |       return (
  148 |         style.display !== "none" &&
  149 |         style.visibility !== "hidden" &&
  150 |         bounds.width > 0 &&
  151 |         bounds.height > 0
  152 |       );
  153 |     };
  154 |     const controls = Array.from(
  155 |       document.querySelectorAll(
  156 |         'button, input, select, textarea, [role="slider"], [contenteditable]:not([contenteditable="false"])',
  157 |       ),
  158 |     )
  159 |       .filter(visible)
  160 |       .map((element) => element.outerHTML);
  161 |     const hudAndCraft = Array.from(
  162 |       document.querySelectorAll(
  163 |         '[data-testid="operator-craft-panel"], [data-testid="ambient-telemetry-hud"]',
  164 |       ),
  165 |     )
  166 |       .filter(visible)
  167 |       .map((element) => element.outerHTML);
  168 |     const links = Array.from(document.querySelectorAll("a[href]"))
  169 |       .filter(visible)
  170 |       .map((element) => ({
  171 |         artifactId: element.getAttribute("data-run-paper-artifact-link"),
  172 |         href: element.getAttribute("href"),
  173 |         paperEligible: element.getAttribute("data-paper-link-eligible"),
  174 |         printedTarget: getComputedStyle(element, "::after").content,
  175 |       }));
  176 |     return {
  177 |       controls,
  178 |       hudAndCraft,
  179 |       links,
  180 |       text: document.body.innerText,
  181 |     };
  182 |   });
  183 | }
  184 | 
  185 | function expectedRunPaperFields(packet: RunPaperPacket) {
  186 |   const fields: Array<[string, string]> = [
  187 |     ["packet.schema_version", packet.packet_schema_version],
  188 |     ["packet.projection_rule_version", packet.projection_rule_version],
  189 |     ["packet.projection_hash", packet.projection_hash],
  190 |     ["packet.intended_audiences", packet.intended_audiences.join(", ")],
  191 |     ["replay.manifest_artifact_id", packet.replay_pins.manifest_artifact_id],
  192 |     [
  193 |       "replay.manifest_schema_version",
  194 |       packet.replay_pins.manifest_schema_version,
  195 |     ],
  196 |     [
  197 |       "replay.paper_projection_rule_version",
  198 |       packet.replay_pins.paper_projection_rule_version,
  199 |     ],
  200 |     ["replay.paper_projection_hash", packet.replay_pins.paper_projection_hash],
  201 |     ["run.status", packet.run.status],
  202 |     ["run.run_terminality", packet.run.run_terminality],
  203 |     ["run.source_kind", packet.run.source_kind],
  204 |     ["run.tenant_id", packet.run.tenant_id],
  205 |     ["case.availability", packet.case_record.availability],
  206 |     ["stage_trace.availability", packet.stage_trace.availability],
  207 |     ["stage_trace.owner_route", packet.stage_trace.owner_route],
  208 |     [
  209 |       "source.manifest_schema",
  210 |       `${packet.source.manifest_schema_name}@${packet.source.manifest_schema_version}`,
  211 |     ],
  212 |     ["source.registry_bundle", packet.source.registry_bundle.artifact_id],
  213 |     ["packet.replay_address", packet.replay_address],
  214 |   ];
  215 |   if (packet.run.started_at) {
  216 |     fields.push(["run.started_at", packet.run.started_at]);
  217 |   }
  218 |   if (packet.run.cell_id) {
  219 |     fields.push(["run.cell_id", packet.run.cell_id]);
  220 |   }
  221 |   if (packet.run.finished_at) {
```