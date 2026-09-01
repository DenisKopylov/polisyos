import { readFile } from "node:fs/promises";

import {
  expect,
  test,
  type APIRequestContext,
  type Locator,
  type Page,
} from "@playwright/test";

import type { components } from "../src/api/types";
import { buildSignedPublicDecisionPacket } from "../src/features/runs/domain/publicationPacket";
import { epochNonreceipt } from "../src/shared/lib/domain/epochSemantics";
import {
  availableHumanDecisionGate,
  humanDecisionReviewEffectivenessFixture,
  humanDecisionSourceRef,
} from "../src/test/fixtures/humanDecision";
import { openCapabilityDiscovery } from "./helpers/capabilityDiscovery";
import { readPdfPageGeometry } from "./helpers/pdfGeometry";
import {
  installDashboardTestState,
  readFixtureMetadata,
  requireRunPaperFixtureMetadata,
  type RunPaperFixtureMetadata,
  waitForDashboardSurface,
} from "./helpers/runtime-dashboard";

const STORYBOOK_BASE_URL = "http://127.0.0.1:6006";
const FIXTURE_API_BASE_URL = "http://127.0.0.1:8000";
const VISUAL_CLOCK_TIME = "2026-01-01T00:00:00.000Z";
const BUREAUCRATIC_GENERATED_LINE =
  "Дата формування: 2026-01-01T00:00:00+00:00";
const VISUAL_CONNECTOR_ID = "worldbank.wdi@1.0.0";
const A4_WIDTH_POINTS = 595.2756;
const A4_HEIGHT_POINTS = 841.8898;
const A4_TOLERANCE_POINTS = 0.5;
type RunPaperPacket = components["schemas"]["RunPaperPacket"];
type HumanDecisionGateResponse =
  components["schemas"]["HumanDecisionGateResponse"];
let fixtureMetadata: RunPaperFixtureMetadata;

async function waitForVisualFonts(page: Page) {
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
}

async function waitForStableRender(locator: Locator, timeout = 15_000) {
  let consecutiveEqualSignatures = 0;
  let previousSignature: string | null = null;
  await expect
    .poll(
      async () => {
        const signature = await locator.evaluateAll((elements) =>
          JSON.stringify(
            elements.map((element) => {
              const bounds = element.getBoundingClientRect();
              const style = getComputedStyle(element);
              return {
                fontFamily: style.fontFamily,
                fontSize: style.fontSize,
                height: bounds.height,
                markup: element.innerHTML,
                width: bounds.width,
              };
            }),
          ),
        );
        consecutiveEqualSignatures =
          signature === previousSignature ? consecutiveEqualSignatures + 1 : 0;
        previousSignature = signature;
        return consecutiveEqualSignatures;
      },
      { timeout },
    )
    .toBeGreaterThanOrEqual(1);
}

async function horizontalOverflowOffenders(locator: Locator) {
  return locator.evaluate((root) =>
    [root, ...root.querySelectorAll("*")]
      .filter((element) => element.scrollWidth > element.clientWidth + 1)
      .map((element) => ({
        className: String(element.className),
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
        tagName: element.tagName,
        text: element.textContent?.trim().slice(0, 160) ?? "",
      })),
  );
}

async function documentHorizontalOverflow(page: Page) {
  return page.evaluate(() => {
    const scrollWidth = Math.max(
      document.documentElement.scrollWidth,
      document.body.scrollWidth,
    );
    const zoom =
      Number.parseFloat(getComputedStyle(document.documentElement).zoom) || 1;
    return {
      normalizedScrollWidth: scrollWidth / zoom,
      scrollWidth,
      viewportWidth: document.documentElement.clientWidth,
      zoom,
    };
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isRunPaperResponse(url: string, runId: string) {
  return (
    new URL(url).pathname === `/api/v1/runs/${encodeURIComponent(runId)}/paper`
  );
}

async function openRunPaper(page: Page, runId: string) {
  const responsePromise = page.waitForResponse(
    (response) =>
      isRunPaperResponse(response.url(), runId) && response.status() === 200,
  );
  await page.goto(`/runs/${encodeURIComponent(runId)}/report`);
  await expect(page.getByTestId("run-report-page")).toBeVisible();
  const response = await responsePromise;
  const rawBytes = await response.body();
  const packet = (await response.json()) as RunPaperPacket;
  expect(packet.packet_schema_version).toBe(
    "policyos.runtime.run_paper_packet.v1",
  );
  expect(packet.run.run_id).toBe(runId);
  return { packet, rawBytes };
}

async function waitForRunPaperPdfReady(page: Page) {
  await waitForVisualFonts(page);
  await waitForStableRender(page.getByTestId("run-paper-document"));
}

async function censusVisiblePrintEgress(page: Page) {
  return page.evaluate(() => {
    const visible = (element: Element) => {
      const bounds = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return (
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        bounds.width > 0 &&
        bounds.height > 0
      );
    };
    const controls = Array.from(
      document.querySelectorAll(
        'button, input, select, textarea, [role="slider"], [contenteditable]:not([contenteditable="false"])',
      ),
    )
      .filter(visible)
      .map((element) => element.outerHTML);
    const hudAndCraft = Array.from(
      document.querySelectorAll(
        '[data-testid="operator-craft-panel"], [data-testid="ambient-telemetry-hud"]',
      ),
    )
      .filter(visible)
      .map((element) => element.outerHTML);
    const links = Array.from(document.querySelectorAll("a[href]"))
      .filter(visible)
      .map((element) => ({
        artifactId: element.getAttribute("data-run-paper-artifact-link"),
        href: element.getAttribute("href"),
        paperEligible: element.getAttribute("data-paper-link-eligible"),
        printedTarget: getComputedStyle(element, "::after").content,
      }));
    return {
      controls,
      hudAndCraft,
      links,
      text: document.body.innerText,
    };
  });
}

function expectedRunPaperFields(packet: RunPaperPacket) {
  const fields: Array<[string, string]> = [
    ["packet.schema_version", packet.packet_schema_version],
    ["packet.projection_rule_version", packet.projection_rule_version],
    ["packet.projection_hash", packet.projection_hash],
    ["packet.intended_audiences", packet.intended_audiences.join(", ")],
    ["replay.manifest_artifact_id", packet.replay_pins.manifest_artifact_id],
    [
      "replay.manifest_schema_version",
      packet.replay_pins.manifest_schema_version,
    ],
    [
      "replay.paper_projection_rule_version",
      packet.replay_pins.paper_projection_rule_version,
    ],
    ["replay.paper_projection_hash", packet.replay_pins.paper_projection_hash],
    ["run.status", packet.run.status],
    ["run.run_terminality", packet.run.run_terminality],
    ["run.source_kind", packet.run.source_kind],
    ["run.tenant_id", packet.run.tenant_id],
    ["case.availability", packet.case_record.availability],
    ["stage_trace.availability", packet.stage_trace.availability],
    ["stage_trace.owner_route", packet.stage_trace.owner_route],
    [
      "source.manifest_schema",
      `${packet.source.manifest_schema_name}@${packet.source.manifest_schema_version}`,
    ],
    ["source.registry_bundle", packet.source.registry_bundle.artifact_id],
    ["packet.replay_address", packet.replay_address],
  ];
  if (packet.run.started_at) {
    fields.push(["run.started_at", packet.run.started_at]);
  }
  if (packet.run.cell_id) {
    fields.push(["run.cell_id", packet.run.cell_id]);
  }
  if (packet.run.finished_at) {
    fields.push(["run.finished_at", packet.run.finished_at]);
  }
  if (packet.run.duration_ms !== null && packet.run.duration_ms !== undefined) {
    fields.push(["run.duration_ms", String(packet.run.duration_ms)]);
  }
  if (packet.source.producer) {
    fields.push([
      "source.producer",
      `${packet.source.producer.component}@${packet.source.producer.version}`,
    ]);
  }
  if (packet.source.environment) {
    fields.push(
      ["source.environment.python", packet.source.environment.python],
      ["source.environment.platform", packet.source.environment.platform],
      [
        "source.environment.deps_lock_hash",
        packet.source.environment.deps_lock_hash,
      ],
    );
  }
  if (packet.case_record.availability === "artifact_missing") {
    fields.push(
      ["case.capability_state", packet.case_record.capability_state],
      ["case.reason_code", packet.case_record.reason_code],
      ["case.owner_route", packet.case_record.owner_route],
      ["case.closure_signal", packet.case_record.closure_signal],
    );
  }
  if (
    packet.case_record.availability === "record_available_authority_abstaining"
  ) {
    const caseRecord = packet.case_record;
    fields.push(
      ["case.authority_projection", caseRecord.authority_projection],
      ["case.case_id", caseRecord.case_id],
      ["case.binding_id", caseRecord.design_record_binding.binding_id],
      ["case.design_record_id", caseRecord.design_record.record_id],
      [
        "case.design_record_ref",
        caseRecord.design_record_binding.design_record_ref.artifact_id,
      ],
      [
        "case.search_ledger_ref",
        caseRecord.design_record_binding.search_ledger_ref.artifact_id,
      ],
      ["case.binding_run_id", caseRecord.design_record_binding.run_id],
      ["case.binding_tenant_id", caseRecord.design_record_binding.tenant_id],
      [
        "case.binding_cell_id",
        caseRecord.design_record_binding.cell_id ?? "null",
      ],
    );
    for (const [role, receipt] of [
      ["grounding", caseRecord.grounding_nonreceipt],
      ["admission", caseRecord.admission_nonreceipt],
      ["promotion", caseRecord.promotion_nonreceipt],
    ] as const) {
      fields.push(
        [`case.${role}.missing_authority`, receipt.missing_authority],
        [`case.${role}.status`, receipt.status],
        [`case.${role}.authority_state`, receipt.authority_state],
        [`case.${role}.owner_route`, receipt.owner_route],
      );
    }
  }
  if (packet.stage_trace.availability === "available") {
    fields.push([
      "stage_trace.artifact_id",
      packet.stage_trace.trace_ref.artifact_id,
    ]);
  } else {
    fields.push(["stage_trace.reason", packet.stage_trace.reason]);
  }
  return fields;
}

function expectAuthorityAbstainingRunPaper(packet: RunPaperPacket) {
  const caseRecord = packet.case_record;
  expect(caseRecord.availability).toBe("record_available_authority_abstaining");
  if (caseRecord.availability !== "record_available_authority_abstaining") {
    throw new Error("governed fixture did not produce a verified case record");
  }
  expect(caseRecord.authority_projection).toBe("abstained");
  expect(caseRecord.design_record_binding.run_id).toBe(packet.run.run_id);
  expect(caseRecord.design_record_binding.tenant_id).toBe(packet.run.tenant_id);
  expect(caseRecord.design_record_binding.cell_id).toBe(packet.run.cell_id);

  const nonreceipts = [
    caseRecord.grounding_nonreceipt,
    caseRecord.admission_nonreceipt,
    caseRecord.promotion_nonreceipt,
  ];
  expect(nonreceipts.map((receipt) => receipt.missing_authority)).toEqual([
    "generation_cycle_grounding_authority",
    "hypothesis_ledger_admission_authority",
    "layer3_g4_promotion_authority",
  ]);
  for (const receipt of nonreceipts) {
    expect(receipt.kind).toBe("run_paper_authority_nonreceipt");
    expect(receipt.status).toBe("not_established");
    expect(receipt.authority_state).toBe("absent/unallocated");
    expect(receipt.denied_uses.length).toBeGreaterThan(0);
  }

  const artifactKinds = packet.artifact_links.map(
    (link) => link.artifact_ref.kind,
  );
  for (const requiredKind of [
    "policyos.layer2_s2.design_record_v0",
    "policyos.layer2_s2.search_ledger",
    "policyos.pdc.run_bound_design_record_binding",
  ]) {
    expect(artifactKinds.filter((kind) => kind === requiredKind)).toHaveLength(
      1,
    );
  }
}

function expectEveryPdfPageToBeA4(
  geometries: Awaited<ReturnType<typeof readPdfPageGeometry>>,
) {
  for (const geometry of geometries) {
    for (const [boxName, box] of [
      ["MediaBox", geometry.mediaBox],
      ["CropBox", geometry.cropBox],
    ] as const) {
      expect(
        Math.abs(box.width - A4_WIDTH_POINTS),
        `page ${geometry.pageNumber} ${boxName} width`,
      ).toBeLessThanOrEqual(A4_TOLERANCE_POINTS);
      expect(
        Math.abs(box.height - A4_HEIGHT_POINTS),
        `page ${geometry.pageNumber} ${boxName} height`,
      ).toBeLessThanOrEqual(A4_TOLERANCE_POINTS);
    }
  }
}

async function loadedConnectorIds(request: APIRequestContext) {
  const response = await request.get(
    `${FIXTURE_API_BASE_URL}/api/v1/control/data/connectors`,
  );
  expect(response.ok()).toBe(true);
  const payload: unknown = await response.json();
  if (!isRecord(payload) || !Array.isArray(payload.connectors)) {
    throw new TypeError("visual fixture expected connectors array");
  }
  return payload.connectors
    .filter(
      (connector): connector is Record<string, unknown> =>
        isRecord(connector) && connector.loaded === true,
    )
    .map((connector) => connector.connector_id)
    .filter(
      (connectorId): connectorId is string => typeof connectorId === "string",
    )
    .sort();
}

async function ensureDeterministicConnectorFixture(request: APIRequestContext) {
  const initiallyLoaded = await loadedConnectorIds(request);
  if (initiallyLoaded.length === 0) {
    const previewResponse = await request.post(
      `${FIXTURE_API_BASE_URL}/api/v1/control/data/preview`,
      {
        data: {
          allow_fallback: false,
          fetch_plan: {
            connector_id: "worldbank.wdi",
            dataset_id: "../unsafe",
            filters: {},
            max_preview_rows: 10,
            metric_id: "probe.metric",
            plan_id: "visual_fixture_worldbank_load",
            profile_id: "worldbank_wdi",
            quality_min: 0.6,
            source_lane: "fastlane",
          },
        },
      },
    );
    expect(previewResponse.ok()).toBe(true);
    const previewPayload: unknown = await previewResponse.json();
    if (!isRecord(previewPayload) || !isRecord(previewPayload.preview)) {
      throw new TypeError("visual fixture expected preview result");
    }
    expect(previewPayload.preview.status).toBe("error");
    expect(previewPayload.preview.message).toBe(
      "Unsafe World Bank indicator id: slash characters are not allowed",
    );
  } else {
    expect(initiallyLoaded).toEqual([VISUAL_CONNECTOR_ID]);
  }

  await expect
    .poll(() => loadedConnectorIds(request), { timeout: 15_000 })
    .toEqual([VISUAL_CONNECTOR_ID]);
}

function visualResponseMetadataPaths(coreRunId: string) {
  return [
    `/api/v1/runs/${encodeURIComponent(coreRunId)}/evidence-context`,
    "/api/v1/control/data/promotion/candidates",
    "/api/v1/control/data/connectors",
  ];
}

async function installVisualResponseMetadataFixture(
  page: Page,
  coreRunId: string,
) {
  for (const responsePath of visualResponseMetadataPaths(coreRunId)) {
    await page.route(`**${responsePath}`, async (route) => {
      const request = route.request();
      const pathname = decodeURIComponent(new URL(request.url()).pathname);
      if (request.method() !== "GET" || pathname !== responsePath) {
        await route.fallback();
        return;
      }

      const response = await route.fetch();
      const payload: unknown = await response.json();
      if (
        !isRecord(payload) ||
        !isRecord(payload.meta) ||
        typeof payload.meta.generated_at !== "string" ||
        payload.meta.generated_at.length === 0
      ) {
        throw new TypeError(
          `visual fixture expected nonempty meta.generated_at at ${responsePath}`,
        );
      }

      await route.fulfill({
        response,
        json: {
          ...payload,
          meta: {
            ...payload.meta,
            generated_at: VISUAL_CLOCK_TIME,
          },
        },
      });
    });
  }
}

function humanDecisionCasePath(runId: string) {
  const query = new URLSearchParams({
    action_kind: "data_request",
    source_kind: "agent_action_authority",
    source_ref: humanDecisionSourceRef,
  });
  return `/runs/${encodeURIComponent(runId)}/case?${query.toString()}`;
}

function bindHumanDecisionGateToRun(
  gate: HumanDecisionGateResponse,
  runId: string,
): HumanDecisionGateResponse {
  const bound = structuredClone(gate);
  const contestability = bound.contestability;
  return {
    ...bound,
    contestability: contestability
      ? {
          ...contestability,
          href:
            `/runs/${encodeURIComponent(runId)}/case?` +
            new URLSearchParams({
              appeal_case_id: contestability.case_id,
              source_kind: "agent_action_authority",
              source_ref: humanDecisionSourceRef,
            }).toString(),
        }
      : null,
    run_id: runId,
  };
}

function blockedHumanDecisionGate(runId: string): HumanDecisionGateResponse {
  const longRef = `pdc://s7/${"delegation-provenance-".repeat(10)}terminal`;
  const longDecisionClass = `decision-class-${"x".repeat(100)}`;
  const longOperation = `operation-${"y".repeat(185)}`;
  const longRightPerson = `reviewer-role-${"z".repeat(280)}`;
  const gate = bindHumanDecisionGateToRun(availableHumanDecisionGate(), runId);
  if (!gate.decision_request || !gate.mandate) {
    throw new TypeError("DS9 visual fixture requires request and mandate");
  }
  return {
    ...gate,
    decision_request: {
      ...gate.decision_request,
      decidable_until: "2026-08-24T11:59:57Z",
      decision_due_at: "2026-08-24T11:59:56Z",
      decision_rights_matrix_ref: `${longRef}/rights`,
      delegation_contract_ref: `${longRef}/contract`,
      five_rights_binding: {
        ...gate.decision_request.five_rights_binding,
        decision_class_id: longDecisionClass,
        decision_rights_matrix_ref: `${longRef}/rights`,
      },
      five_rights_requirements: {
        ...gate.decision_request.five_rights_requirements,
        right_person: longRightPerson,
      },
      requested_at: "2026-08-24T11:30:00Z",
    },
    mandate: {
      ...gate.mandate,
      mandate_owner_ref: `${longRef}/owner`,
      mandate_record_ref: `${longRef}/mandate`,
      operation_id: longOperation,
      valid_until: "2026-08-24T11:59:59Z",
    },
    reason_codes: [
      "DS9-WRONG-ROLE",
      "DS9-DECISION-TTL-EXPIRED",
      "DS9-AUTHORITY-CROSS-USE",
    ],
    reasons: [
      {
        code: "DS9-WRONG-ROLE",
        message:
          "The signed reviewer role does not authorize this decision and cannot be substituted by a matching display label.",
        status: "blocked",
      },
      {
        code: "DS9-DECISION-TTL-EXPIRED",
        message:
          "The mandate-bounded decision interval expired before this pre-action gate was resolved; a fresh signed packet is required.",
        status: "blocked",
      },
      {
        code: "DS9-AUTHORITY-CROSS-USE",
        message:
          "Search authority cannot be reused for a data_request action, even when every projected reference is present. " +
          "This deliberately long reason proves that typed refusal, provenance, and the next revalidation boundary remain readable without horizontal clipping.",
        status: "blocked",
      },
    ],
    status: "blocked",
    submission: null,
  };
}

async function installHumanDecisionVisualFixture(
  page: Page,
  runId: string,
  gate: HumanDecisionGateResponse,
) {
  await page.route("**/api/v1/auth/me", async (route) => {
    const requestUrl = new URL(route.request().url());
    if (
      route.request().method() !== "GET" ||
      requestUrl.pathname !== "/api/v1/auth/me"
    ) {
      await route.fallback();
      return;
    }
    const response = await route.fetch();
    const payload: unknown = await response.json();
    if (!isRecord(payload) || !Array.isArray(payload.permissions)) {
      throw new TypeError("DS9 visual fixture expected auth permissions");
    }
    const permissions = payload.permissions.filter(
      (permission): permission is string => typeof permission === "string",
    );
    await route.fulfill({
      response,
      json: {
        ...payload,
        permissions: [
          ...new Set([...permissions, "runs.human_decisions.create"]),
        ],
      },
    });
  });

  await page.route(
    `**/api/v1/runs/${encodeURIComponent(runId)}/human-decision-gate*`,
    async (route) => {
      const requestUrl = new URL(route.request().url());
      if (
        route.request().method() !== "GET" ||
        requestUrl.pathname !==
          `/api/v1/runs/${encodeURIComponent(runId)}/human-decision-gate`
      ) {
        await route.fallback();
        return;
      }
      await route.fulfill({ json: gate, status: 200 });
    },
  );

  await page.route(
    `**/api/v1/runs/${encodeURIComponent(runId)}/human-decisions/review-effectiveness`,
    async (route) => {
      const requestUrl = new URL(route.request().url());
      if (
        route.request().method() !== "GET" ||
        requestUrl.pathname !==
          `/api/v1/runs/${encodeURIComponent(runId)}/human-decisions/review-effectiveness`
      ) {
        await route.fallback();
        return;
      }
      await route.fulfill({
        json: humanDecisionReviewEffectivenessFixture({ run_id: runId }),
        status: 200,
      });
    },
  );
}

async function openHumanDecisionCase(
  page: Page,
  runId: string,
  gate: HumanDecisionGateResponse,
) {
  await installHumanDecisionVisualFixture(page, runId, gate);
  await page.goto(humanDecisionCasePath(runId));
  await expect(page.getByTestId("case-workspace-page")).toBeVisible();
  await expect(
    page.getByTestId("case-inspection-authority-abstaining"),
  ).toHaveAttribute(
    "data-case-availability",
    "record_available_authority_abstaining",
  );
  const surface = page.getByTestId("human-decision-gate");
  await expect(surface).toBeVisible();
  await expect(
    page.getByTestId("human-decision-review-effectiveness"),
  ).toBeVisible();
  await waitForVisualFonts(page);
  await waitForStableRender(surface);
  return surface;
}

async function installBureaucraticTimestampFixture(
  page: Page,
  artifactId: string,
) {
  const artifactPath = `/api/v1/artifacts/${artifactId}`;
  const renderPath = `${artifactPath}/render`;

  await page.route("**/api/v1/artifacts/**", async (route) => {
    const pathname = decodeURIComponent(
      new URL(route.request().url()).pathname,
    );
    if (pathname !== artifactPath && pathname !== renderPath) {
      await route.fallback();
      return;
    }

    const response = await route.fetch();
    const payload: unknown = await response.json();
    if (!isRecord(payload)) {
      throw new TypeError(
        `visual fixture expected object payload at ${pathname}`,
      );
    }

    if (pathname === artifactPath) {
      if (
        !isRecord(payload.artifact) ||
        typeof payload.artifact.created_at !== "string"
      ) {
        throw new TypeError("visual fixture expected artifact.created_at");
      }
      await route.fulfill({
        response,
        json: {
          ...payload,
          artifact: {
            ...payload.artifact,
            created_at: VISUAL_CLOCK_TIME,
          },
        },
      });
      return;
    }

    if (
      !isRecord(payload.document) ||
      typeof payload.document.render_timestamp !== "string"
    ) {
      throw new TypeError("visual fixture expected document.render_timestamp");
    }
    if (!Array.isArray(payload.document.blocks)) {
      throw new TypeError("visual fixture expected document.blocks");
    }
    let generatedLineCount = 0;
    const blocks = payload.document.blocks.map((block) => {
      if (!isRecord(block) || !Array.isArray(block.items)) {
        return block;
      }
      const items = block.items.map((item) => {
        if (typeof item === "string" && item.startsWith("Дата формування: ")) {
          generatedLineCount += 1;
          return BUREAUCRATIC_GENERATED_LINE;
        }
        return item;
      });
      return { ...block, items };
    });
    if (generatedLineCount !== 1) {
      throw new TypeError(
        `visual fixture expected one bureaucratic generated-at line, received ${generatedLineCount}`,
      );
    }
    await route.fulfill({
      response,
      json: {
        ...payload,
        document: {
          ...payload.document,
          blocks,
          render_timestamp: VISUAL_CLOCK_TIME,
        },
      },
    });
  });
}

async function waitForDashboardCharts(page: Page) {
  const charts = page.locator(
    '[data-testid="dashboard-page"] .recharts-responsive-container',
  );
  await expect(charts).toHaveCount(2);
  await expect(
    page
      .locator('[data-testid="dashboard-page"] .recharts-bar-rectangle')
      .first(),
  ).toBeVisible();
  await expect(
    page.locator('[data-testid="dashboard-page"] .recharts-line-curve').first(),
  ).toHaveAttribute("d", /^M.+L/);
  await expect
    .poll(() =>
      charts.evaluateAll((elements) =>
        elements.every((element) => {
          const bounds = element.getBoundingClientRect();
          return bounds.width > 0 && bounds.height > 0;
        }),
      ),
    )
    .toBe(true);
  await expect(page.locator("html")).toHaveAttribute(
    "data-reduced-motion",
    "reduce",
  );
  await waitForVisualFonts(page);

  await waitForStableRender(charts);
}

async function openEvidencePrimitiveStory(page: Page, storyId: string) {
  await page.goto(
    `${STORYBOOK_BASE_URL}/iframe.html?id=${encodeURIComponent(storyId)}&viewMode=story`,
  );
  const story = page.locator("#storybook-root");
  await expect(story).toBeVisible({ timeout: 15_000 });
  await waitForVisualFonts(page);
  return story;
}

async function openPrintSurface(
  page: Page,
  {
    path,
    readySelector,
    readyTestId,
    selector,
  }: {
    path: string;
    readySelector?: string;
    readyTestId: string;
    selector: string;
  },
): Promise<Locator> {
  await page.setViewportSize({ width: 794, height: 1123 });
  await page.emulateMedia({ media: "print" });
  await page.goto(path);
  await expect(page.getByTestId(readyTestId)).toBeVisible();
  await expect(page.locator(selector)).toBeVisible();
  if (readySelector) {
    await expect(page.locator(readySelector)).toBeVisible();
    await waitForStableRender(page.locator(readySelector));
  }
  await waitForVisualFonts(page);
  const surface = page.locator(selector);
  await waitForStableRender(surface);
  return surface;
}

test.describe("runtime-dashboard visual baselines", () => {
  test.use({
    viewport: { width: 1440, height: 1200 },
  });

  test.beforeAll(async ({ request }) => {
    const metadata = readFixtureMetadata();
    requireRunPaperFixtureMetadata(metadata);
    fixtureMetadata = metadata;
    await ensureDeterministicConnectorFixture(request);
  });

  test.beforeEach(async ({ page }) => {
    await page.clock.setFixedTime(VISUAL_CLOCK_TIME);
    await installDashboardTestState(page);
    await installVisualResponseMetadataFixture(
      page,
      fixtureMetadata.core_run_id,
    );
    await page.emulateMedia({ reducedMotion: "reduce" });
  });

  test("binds visual response metadata to the visual clock", async ({
    page,
  }) => {
    const responsePaths = visualResponseMetadataPaths(
      fixtureMetadata.core_run_id,
    );

    await page.goto("/");
    const visualTimeBeforeWait = await page.evaluate(() =>
      new Date().toISOString(),
    );
    await page.waitForTimeout(50);
    const visualTimeAfterWait = await page.evaluate(() =>
      new Date().toISOString(),
    );
    expect(visualTimeBeforeWait).toBe(VISUAL_CLOCK_TIME);
    expect(visualTimeAfterWait).toBe(VISUAL_CLOCK_TIME);

    const generatedTimes = await page.evaluate(async (paths) => {
      return Promise.all(
        paths.map(async (path) => {
          const response = await fetch(path);
          if (!response.ok) {
            throw new Error(
              `visual fixture request failed at ${path}: ${response.status}`,
            );
          }
          const payload: unknown = await response.json();
          if (
            typeof payload !== "object" ||
            payload === null ||
            !("meta" in payload) ||
            typeof payload.meta !== "object" ||
            payload.meta === null ||
            !("generated_at" in payload.meta)
          ) {
            throw new TypeError(
              `visual fixture expected meta.generated_at at ${path}`,
            );
          }
          return payload.meta.generated_at;
        }),
      );
    }, responsePaths);

    for (const generatedAt of generatedTimes) {
      expect(generatedAt).toBe(VISUAL_CLOCK_TIME);
    }
  });

  test("command center shell", async ({ page }) => {
    await page.goto("/");
    await waitForDashboardSurface(page, "dashboard");
    await waitForDashboardCharts(page);
    await expect(page.locator(".workspace-frame").first()).toHaveScreenshot(
      "command-center-shell.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("scenario composer dark theme", async ({ page }) => {
    await installDashboardTestState(page, { theme: "dark" });
    await page.goto("/compose");
    await expect(
      page.getByRole("heading", { name: "Scenario Composer" }),
    ).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.locator(".workspace-frame").first()).toHaveScreenshot(
      "scenario-composer-dark.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("run detail overview", async ({ page }) => {
    await page.goto(`/runs/${fixtureMetadata.core_run_id}/overview`);
    await expect(page.getByTestId("run-detail-page")).toBeVisible();
    await expect(page.getByTestId("run-detail-summary")).toHaveScreenshot(
      "run-detail-summary.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("evidence promotion focus", async ({ page }) => {
    const catalogResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        response.request().method() === "GET" &&
        url.pathname === "/api/v1/control/data/catalog/search"
      );
    });
    await page.goto(
      `/evidence?runId=${fixtureMetadata.core_run_id}&focus=promotion&promotionId=${fixtureMetadata.promotion_candidate_id}`,
    );
    await expect(
      page.getByTestId(
        `promotion-approve-${fixtureMetadata.promotion_candidate_id}`,
      ),
    ).toBeVisible();
    const catalogResponse = await catalogResponsePromise;
    expect(catalogResponse.ok()).toBe(true);
    const catalogPayload: unknown = await catalogResponse.json();
    if (
      !isRecord(catalogPayload) ||
      typeof catalogPayload.query !== "string" ||
      typeof catalogPayload.total_matches !== "number"
    ) {
      throw new TypeError(
        "visual fixture expected a typed catalog search response",
      );
    }
    await expect(
      page.getByTestId("evidence-knowledge-weave-panel"),
    ).toContainText(
      `Catalog matches: ${catalogPayload.total_matches} for query \`${catalogPayload.query}\``,
    );
    const surface = page.getByTestId("evidence-page");
    await waitForVisualFonts(page);
    await waitForStableRender(surface);
    await expect(surface).toHaveScreenshot("evidence-promotion-focus.png", {
      animations: "disabled",
      caret: "hide",
    });
  });

  test("clerk chat shell-lite", async ({ page }) => {
    await installDashboardTestState(page, { interfaceMode: "clerk" });
    await page.goto("/");
    await expect(
      page.getByText("What policy would you like to analyze?"),
    ).toBeVisible();
    await expect(page.locator(".workspace-frame").first()).toHaveScreenshot(
      "clerk-chat-shell-lite.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("dark evidence fabric", async ({ page }) => {
    await installDashboardTestState(page, { theme: "dark" });
    await page.goto("/evidence");
    await expect(page.getByTestId("evidence-page")).toBeVisible();
    await expect(page.getByTestId("evidence-source-atlas-panel")).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    const surface = page.getByTestId("evidence-page");
    await waitForVisualFonts(page);
    await waitForStableRender(surface);
    await expect(surface).toHaveScreenshot("dark-evidence-fabric.png", {
      animations: "disabled",
      caret: "hide",
    });
  });

  test.describe("DS10 capability discovery", () => {
    test("DS10 capability discovery executable candidate", async ({ page }) => {
      const surface = await openCapabilityDiscovery(page, "executable");
      await expect(surface).toContainText("Generated legal-norm candidate");
      await expect(surface).toContainText("Candidate · bridge_missing");
      await expect(surface).toContainText("selected:");
      await expect(surface).toContainText("rejected:");
      await waitForVisualFonts(page);
      await waitForStableRender(surface);
      await expect(surface).toHaveScreenshot(
        "ds10-capability-discovery-executable-candidate.png",
        {
          animations: "disabled",
          caret: "hide",
        },
      );
    });

    test("DS10 capability discovery incomplete no-hit", async ({ page }) => {
      const surface = await openCapabilityDiscovery(page, "incomplete-no-hit");
      await expect(surface).toContainText("No capability matched this search.");
      await expect(surface).toContainText("recall_unmeasured");
      await expect(surface).toContainText("budget_cutoff");
      await expect(surface).toContainText("legal_norm:index_stale");
      await expect(surface).toContainText("case:producer_missing");
      await expect(surface).toContainText("rejected:");
      await waitForVisualFonts(page);
      await waitForStableRender(surface);
      await expect(surface).toHaveScreenshot(
        "ds10-capability-discovery-incomplete-no-hit.png",
        {
          animations: "disabled",
          caret: "hide",
        },
      );
    });
  });

  test("mobile command center", async ({ page }) => {
    await page.setViewportSize({ width: 393, height: 852 });
    await page.goto("/");
    await waitForDashboardSurface(page, "dashboard");
    await waitForDashboardCharts(page);
    await expect(page.locator(".workspace-frame").first()).toHaveScreenshot(
      "mobile-command-center.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("mobile run detail overview", async ({ page }) => {
    await page.setViewportSize({ width: 393, height: 852 });
    await page.goto(`/runs/${fixtureMetadata.core_run_id}/overview`);
    await expect(page.getByTestId("run-detail-page")).toBeVisible();
    await expect(page.getByTestId("run-detail-summary")).toHaveScreenshot(
      "mobile-run-detail-overview.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("logo mark sizes", async ({ page }) => {
    await page.goto("/");
    await page.setContent(`
      <main style="display:grid;place-items:center;min-height:100vh;background:#f4f0e5;">
        <div id="logo-mark-grid" style="display:flex;align-items:flex-end;gap:24px;padding:32px;border:1px solid rgba(41,43,43,0.12);border-radius:24px;background:rgba(255,255,255,0.76);">
          <img alt="logo-16" src="http://127.0.0.1:5173/atlas/favicon.svg" width="16" height="16" />
          <img alt="logo-32" src="http://127.0.0.1:5173/atlas/logo-mark.svg" width="32" height="32" />
          <img alt="logo-48" src="http://127.0.0.1:5173/atlas/logo-mark.svg" width="48" height="48" />
        </div>
      </main>
    `);
    await expect(page.locator("#logo-mark-grid")).toHaveScreenshot(
      "logo-mark-16-32-48.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("run deck content slide", async ({ page }) => {
    await page.goto(`/runs/${fixtureMetadata.core_run_id}/deck`);
    await expect(page.getByTestId("run-deck-page")).toBeVisible();
    await expect(page.getByTestId("run-deck-slide-evidence")).toHaveScreenshot(
      "run-deck-content-slide.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("renders candidate output in candidate clothing", async ({ page }) => {
    const story = await openEvidencePrimitiveStory(
      page,
      "ds4-evidence-primitives--candidate-clothing",
    );
    const candidate = story.getByTestId("candidate-frame");
    const ownerProjection = story.getByTestId("owner-projection-unavailable");
    await expect(candidate).toHaveAttribute(
      "data-authority-posture",
      "candidate",
    );
    await expect(ownerProjection).toHaveAttribute(
      "data-interaction-state",
      "unavailable",
    );
    await expect(
      story.locator('[data-authority-posture="owner-projection"]'),
    ).toHaveCount(0);
    const [candidateBorder, ownerBorder] = await Promise.all([
      candidate.evaluate((element) => getComputedStyle(element).borderStyle),
      ownerProjection.evaluate(
        (element) => getComputedStyle(element).borderStyle,
      ),
    ]);
    expect(candidateBorder).toBe("dashed");
    expect(ownerBorder).not.toBe(candidateBorder);
    await expect(story).toHaveScreenshot("ds4-candidate-clothing.png", {
      animations: "disabled",
      caret: "hide",
    });
  });

  test("marks fixture-only content and bars it from authority slots", async ({
    page,
  }) => {
    const story = await openEvidencePrimitiveStory(
      page,
      "ds4-evidence-primitives--fixture-only",
    );
    await expect(story.locator("#story-fixture-envelope")).toHaveAttribute(
      "data-fixture-authority",
      "fixture_only",
    );
    await expect(story.locator("#story-fixture-evidence")).toHaveAttribute(
      "data-fixture-authority",
      "fixture_only",
    );
    await expect(
      story.getByTestId("authority-badge-fixture-rejection"),
    ).toHaveAttribute("data-fixture-rejection", /fixture provenance/i);
    await expect(story.locator("[data-authority-recognition]")).toHaveCount(0);
    await expect(story).toHaveScreenshot("ds4-fixture-only-boundary.png", {
      animations: "disabled",
      caret: "hide",
    });
  });

  test("renders every DS4 evidence primitive", async ({ page }) => {
    const story = await openEvidencePrimitiveStory(
      page,
      "ds4-evidence-primitives--all-primitives",
    );
    for (const locator of [
      story.getByTestId("authority-badge-fixture-rejection"),
      story.getByTestId("candidate-frame"),
      story.getByTestId("blocker-card"),
      story.locator("#story-envelope-chip"),
      story.locator("#story-evidence-link"),
      story.getByTestId("provenance-popover-content"),
      story.getByTestId("time-semantics-source-state"),
      story.getByTestId("weakest-link-explainer"),
    ]) {
      await expect(locator).toBeVisible();
    }
    await expect(
      story.getByTestId("authority-badge-fixture-rejection"),
    ).toHaveAttribute("data-fixture-rejection", /fixture provenance/i);
    await expect(story.locator("[data-authority-recognition]")).toHaveCount(0);
    await expect(story.getByTestId("candidate-frame")).toHaveAttribute(
      "data-authority-posture",
      "candidate",
    );
    await expect(story.getByTestId("blocker-card")).toHaveAttribute(
      "data-producer-blocker-code",
      "fixture_missing_grounded_effect",
    );
    await expect(story.locator("#story-envelope-chip")).toHaveAttribute(
      "data-fixture-authority",
      "fixture_only",
    );
    await expect(story.locator("#story-evidence-link")).toHaveAttribute(
      "data-evidence-claim",
      "reference-only",
    );
    await expect(story).toHaveScreenshot("ds4-evidence-primitives.png", {
      animations: "disabled",
      caret: "hide",
    });
    await page.setViewportSize({ width: 393, height: 852 });
    await expect(story.getByTestId("weakest-link-explainer")).toBeVisible();
    await page.emulateMedia({
      forcedColors: "active",
      reducedMotion: "reduce",
    });
    await expect(story.locator("#story-evidence-link")).toBeVisible();
    await page.emulateMedia({ media: "print" });
    await expect(story.getByTestId("candidate-frame")).toBeVisible();
  });

  test("decision packet reading view A4 print", async ({ page }) => {
    const surface = await openPrintSurface(page, {
      path: `/artifacts/${fixtureMetadata.decision_packet_artifact_id}?tab=content&view=reading`,
      readyTestId: "artifact-page",
      selector: ".monograph-layout",
    });
    await expect(surface).toHaveScreenshot(
      "decision-reading-view-a4-print.png",
      {
        animations: "disabled",
        caret: "hide",
        maxDiffPixels: 100,
      },
    );
  });

  test.describe("DS8 governed run paper", () => {
    test("semantic DOM closes overview and report paper egress", async ({
      page,
    }) => {
      const browserLocalSentinel = "DS8-BROWSER-LOCAL-MUST-NOT-PRINT";
      let paperResponseCount = 0;
      const epochSettlementPromise = page.waitForResponse((response) => {
        const url = new URL(response.url());
        return (
          url.pathname ===
            `/api/v1/temporal/runs/${encodeURIComponent(fixtureMetadata.core_run_id)}/epoch-staleness` &&
          url.searchParams.has("valid_at") &&
          url.searchParams.has("tx_at")
        );
      });
      page.on("response", (response) => {
        if (isRunPaperResponse(response.url(), fixtureMetadata.core_run_id)) {
          paperResponseCount += 1;
        }
      });

      await page.goto(
        `/runs/${fixtureMetadata.core_run_id}/overview?trust=expanded`,
      );
      await expect(page.getByTestId("run-detail-page")).toBeVisible();
      const epochSettlement = await epochSettlementPromise;
      expect(await epochSettlement.finished()).toBeNull();
      await waitForStableRender(page.getByTestId("run-decision-packet"));
      const annotationPanel = page.getByTestId("annotation-surface-panel");
      await expect(annotationPanel).toBeVisible();
      await annotationPanel.locator("textarea").fill(browserLocalSentinel);
      await annotationPanel.locator('form button[type="submit"]').click();
      await expect(
        annotationPanel.getByText(browserLocalSentinel),
      ).toBeVisible();

      await page.emulateMedia({ media: "print" });
      await expect(page.getByTestId("run-detail-page")).toBeHidden();
      await expect(
        page.locator('[data-paper-payload="run-paper"]'),
      ).toHaveCount(0);
      await expect(page.getByText(browserLocalSentinel)).toBeHidden();
      const overviewEgress = await censusVisiblePrintEgress(page);
      expect(overviewEgress.controls).toEqual([]);
      expect(overviewEgress.hudAndCraft).toEqual([]);
      expect(overviewEgress.links).toEqual([]);
      expect(overviewEgress.text).not.toContain(browserLocalSentinel);

      const { packet, rawBytes } = await openRunPaper(
        page,
        fixtureMetadata.core_run_id,
      );
      const documentRoot = page.getByTestId("run-paper-document");
      await expect(documentRoot).toBeVisible();
      await expect(documentRoot.getByText(browserLocalSentinel)).toHaveCount(0);
      await expect(
        documentRoot.locator(
          'button, input, select, textarea, [role="slider"], [contenteditable]:not([contenteditable="false"])',
        ),
      ).toHaveCount(0);
      await expect(
        documentRoot.getByTestId("operator-craft-panel"),
      ).toHaveCount(0);
      await expect(
        documentRoot.getByTestId("ambient-telemetry-hud"),
      ).toHaveCount(0);
      await expect(
        documentRoot.locator('a[href^="/public/decisions/"]'),
      ).toHaveCount(0);
      expect(new TextDecoder().decode(rawBytes)).not.toContain(
        browserLocalSentinel,
      );

      for (const [field, expectedValue] of expectedRunPaperFields(packet)) {
        const fact = documentRoot.locator(`[data-run-paper-field="${field}"]`);
        await expect(fact, `paper field ${field}`).toHaveCount(1);
        await expect(fact.locator("dd"), `paper field ${field}`).toHaveText(
          expectedValue,
        );
      }
      expectAuthorityAbstainingRunPaper(packet);
      await expect(
        documentRoot.getByTestId("run-paper-case-authority-abstaining"),
      ).toBeVisible();
      await expect(
        documentRoot.locator("[data-run-paper-authority-nonreceipt]"),
      ).toHaveCount(3);

      const reportEgress = await censusVisiblePrintEgress(page);
      expect(reportEgress.controls).toEqual([]);
      expect(reportEgress.hudAndCraft).toEqual([]);
      expect(reportEgress.text).not.toContain(browserLocalSentinel);
      expect(
        reportEgress.links.filter((link) =>
          link.href?.startsWith("/public/decisions/"),
        ),
      ).toEqual([]);
      expect(reportEgress.links).toEqual(
        packet.artifact_links.map((link) => ({
          artifactId: link.artifact_ref.artifact_id,
          href: link.href,
          paperEligible: "true",
          printedTarget: expect.stringContaining(link.href),
        })),
      );

      await page.emulateMedia({ media: "screen" });
      const downloadPromise = page.waitForEvent("download");
      await page.getByRole("button", { name: "Export MACHINE packet" }).click();
      const download = await downloadPromise;
      const downloadPath = await download.path();
      if (!downloadPath) {
        throw new Error("MACHINE packet download did not produce a local file");
      }
      expect(await readFile(downloadPath)).toEqual(rawBytes);
      expect(paperResponseCount).toBe(1);
    });

    test("PDF keeps every page A4 and admitted growth adds pages", async ({
      page,
    }, testInfo) => {
      await page.emulateMedia({ media: "print" });
      const empty = await openRunPaper(
        page,
        fixtureMetadata.run_paper_empty_run_id,
      );
      await waitForRunPaperPdfReady(page);
      expectAuthorityAbstainingRunPaper(empty.packet);
      expect(empty.packet.artifact_links).toHaveLength(3);
      await expect(page.locator("[data-run-paper-artifact-link]")).toHaveCount(
        empty.packet.artifact_links.length,
      );
      expect((await censusVisiblePrintEgress(page)).links).toEqual(
        empty.packet.artifact_links.map((link) => ({
          artifactId: link.artifact_ref.artifact_id,
          href: link.href,
          paperEligible: "true",
          printedTarget: expect.stringContaining(link.href),
        })),
      );
      const emptyPdf = await page.pdf({
        preferCSSPageSize: true,
        printBackground: true,
      });
      const emptyGeometry = await readPdfPageGeometry(emptyPdf);
      expectEveryPdfPageToBeA4(emptyGeometry);
      await testInfo.attach("run-paper-empty.pdf", {
        body: emptyPdf,
        contentType: "application/pdf",
      });
      await testInfo.attach("run-paper-empty-geometry.json", {
        body: Buffer.from(JSON.stringify(emptyGeometry, null, 2)),
        contentType: "application/json",
      });

      const growth = await openRunPaper(
        page,
        fixtureMetadata.run_paper_growth_run_id,
      );
      await waitForRunPaperPdfReady(page);
      expectAuthorityAbstainingRunPaper(growth.packet);
      expect(growth.packet.artifact_links).toHaveLength(
        empty.packet.artifact_links.length + 64,
      );
      expect(
        growth.packet.artifact_links.filter(
          (link) => link.artifact_ref.kind === "test.run_paper_growth_output",
        ),
      ).toHaveLength(64);
      expect((await censusVisiblePrintEgress(page)).links).toEqual(
        growth.packet.artifact_links.map((link) => ({
          artifactId: link.artifact_ref.artifact_id,
          href: link.href,
          paperEligible: "true",
          printedTarget: expect.stringContaining(link.href),
        })),
      );
      const growthPdf = await page.pdf({
        preferCSSPageSize: true,
        printBackground: true,
      });
      const growthGeometry = await readPdfPageGeometry(growthPdf);
      expectEveryPdfPageToBeA4(growthGeometry);
      expect(growthGeometry.length).toBeGreaterThan(emptyGeometry.length);
      await testInfo.attach("run-paper-growth.pdf", {
        body: growthPdf,
        contentType: "application/pdf",
      });
      await testInfo.attach("run-paper-growth-geometry.json", {
        body: Buffer.from(JSON.stringify(growthGeometry, null, 2)),
        contentType: "application/json",
      });
    });

    test("bounded identity A4 print", async ({ page }) => {
      const identity = await openPrintSurface(page, {
        path: `/runs/${fixtureMetadata.run_paper_empty_run_id}/report`,
        readyTestId: "run-report-page",
        selector: '[data-testid="run-paper-identity"]',
      });
      const bounds = await identity.boundingBox();
      expect(bounds).not.toBeNull();
      expect(bounds?.width).toBeGreaterThan(0);
      expect(bounds?.height).toBeGreaterThan(0);
      expect(bounds?.width).toBeLessThanOrEqual(794);
      expect(bounds?.height).toBeLessThanOrEqual(1123);
      await expect(identity).toHaveScreenshot(
        "run-report-identity-a4-print.png",
        {
          animations: "disabled",
          caret: "hide",
          maxDiffPixels: 100,
        },
      );
    });
  });

  test.describe("DS9 human decision gate", () => {
    test("available pre-action gate retains readable hierarchy", async ({
      page,
    }) => {
      const runId = fixtureMetadata.core_run_id;
      const gate = bindHumanDecisionGateToRun(
        availableHumanDecisionGate(),
        runId,
      );
      const surface = await openHumanDecisionCase(page, runId, gate);
      const request = gate.decision_request;
      const mandate = gate.mandate;
      expect(request).not.toBeNull();
      expect(mandate).not.toBeNull();
      if (!request || !mandate) {
        throw new TypeError("DS9 available fixture lost its signed inputs");
      }

      await expect(
        surface
          .getByText(request.delegation_contract_ref, { exact: true })
          .first(),
      ).toBeVisible();
      await expect(
        surface
          .getByText(request.decision_rights_matrix_ref, { exact: true })
          .first(),
      ).toBeVisible();
      for (const right of [
        request.five_rights_requirements.right_decision,
        request.five_rights_requirements.right_person,
        request.five_rights_requirements.right_information,
        request.five_rights_requirements.right_format_channel,
        request.five_rights_requirements.right_time,
      ]) {
        await expect(
          surface.getByText(right, { exact: true }).first(),
        ).toBeVisible();
      }
      await expect(
        surface.getByText(mandate.mandate_record_ref, { exact: true }).first(),
      ).toBeVisible();
      await expect(
        surface
          .getByText(gate.exposure.required_artifact_digests[1], {
            exact: true,
          })
          .first(),
      ).toBeVisible();
      await expect(
        surface
          .getByText(gate.exposure.exposure_session_ref ?? "", {
            exact: true,
          })
          .first(),
      ).toBeVisible();
      await expect(
        surface.getByText(request.decidable_until, { exact: true }).first(),
      ).toBeVisible();

      const appeal = surface.locator('a[href*="appeal_case_id"]');
      expect(gate.contestability).not.toBeNull();
      if (!gate.contestability) {
        throw new TypeError("DS9 available fixture lost contestability");
      }
      await expect(appeal).toHaveAttribute("href", gate.contestability.href);
      for (const id of [
        "#human-decision-accountability",
        "#human-decision-dissent",
        "#human-decision-override",
        "#human-decision-blocking",
      ]) {
        await expect(surface.locator(id)).toBeVisible();
      }
      for (const action of ["approve", "reject", "request_evidence"]) {
        await expect(
          surface.locator(`#human-decision-mode-${action}`),
        ).toBeVisible();
      }
      await expect(surface).not.toContainText(
        "DS9-HUMAN-DECISION-PERMISSION-REQUIRED",
      );
      await surface.locator("summary").click();
      await expect(
        surface.getByTestId("human-decision-fact").first(),
      ).toBeVisible();
      await waitForStableRender(surface);
      await expect(surface).toHaveScreenshot(
        "ds9-human-decision-gate-available.png",
        {
          animations: "disabled",
          caret: "hide",
          maxDiffPixels: 100,
        },
      );
    });

    test("blocked pre-action gate retains readable hierarchy with long reason TTL and provenance", async ({
      page,
    }) => {
      const runId = fixtureMetadata.core_run_id;
      const gate = blockedHumanDecisionGate(runId);
      const surface = await openHumanDecisionCase(page, runId, gate);

      for (const code of [
        "DS9-WRONG-ROLE",
        "DS9-DECISION-TTL-EXPIRED",
        "DS9-AUTHORITY-CROSS-USE",
      ]) {
        await expect(
          surface.getByText(code, { exact: true }).first(),
        ).toBeVisible();
      }
      await expect(
        surface
          .getByText(gate.decision_request?.decidable_until ?? "", {
            exact: true,
          })
          .first(),
      ).toBeVisible();
      await expect(
        surface
          .getByText(gate.mandate?.mandate_record_ref ?? "", {
            exact: true,
          })
          .first(),
      ).toBeVisible();
      await expect(
        surface.locator("textarea, select, button[type='button']"),
      ).toHaveCount(0);
      await expect(surface).not.toContainText(
        "DS9-HUMAN-DECISION-PERMISSION-REQUIRED",
      );
      await surface.locator("summary").click();
      await expect(
        surface.getByTestId("human-decision-fact").first(),
      ).toBeVisible();
      await waitForStableRender(surface);
      expect(await horizontalOverflowOffenders(surface)).toEqual([]);
      const documentOverflow = await documentHorizontalOverflow(page);
      expect(documentOverflow.normalizedScrollWidth).toBeLessThanOrEqual(
        documentOverflow.viewportWidth + 1,
      );
      await expect(surface).toHaveScreenshot(
        "ds9-human-decision-gate-blocked.png",
        {
          animations: "disabled",
          caret: "hide",
          maxDiffPixels: 100,
        },
      );
    });

    test("reflows at 320px and 200% zoom and preserves keyboard contestability", async ({
      page,
    }) => {
      await page.setViewportSize({ width: 320, height: 900 });
      const runId = fixtureMetadata.core_run_id;
      const gate = bindHumanDecisionGateToRun(
        availableHumanDecisionGate(),
        runId,
      );
      const surface = await openHumanDecisionCase(page, runId, gate);
      await page.evaluate(() => {
        document.documentElement.style.setProperty("zoom", "200%");
      });
      await waitForStableRender(surface);

      expect(await horizontalOverflowOffenders(surface)).toEqual([]);
      const documentOverflow = await documentHorizontalOverflow(page);
      expect(documentOverflow.normalizedScrollWidth).toBeLessThanOrEqual(
        documentOverflow.viewportWidth + 1,
      );
      const appeal = surface.locator('a[href*="appeal_case_id"]');
      await appeal.focus();
      await expect(appeal).toBeFocused();
      await page.keyboard.press("Tab");
      await expect(
        surface.locator("#human-decision-accountability"),
      ).toBeFocused();

      await appeal.focus();
      await page.keyboard.press("Enter");
      await expect(page).toHaveURL(/appeal_case_id=case\.fixture/u);
      const url = new URL(page.url());
      expect(url.searchParams.get("appeal_case_id")).toBe("case.fixture");
      expect(url.searchParams.get("source_kind")).toBe(
        "agent_action_authority",
      );
      expect(url.searchParams.get("source_ref")).toBe(humanDecisionSourceRef);
      await expect(page.getByTestId("case-workspace-page")).toBeVisible();
      await expect(page.getByTestId("human-decision-gate")).toBeVisible();
    });

    test("remains absent from the public decision route", async ({ page }) => {
      const humanDecisionRequests: string[] = [];
      page.on("request", (request) => {
        const pathname = new URL(request.url()).pathname;
        if (/^\/api\/v1\/.*human-decision/u.test(pathname)) {
          humanDecisionRequests.push(pathname);
        }
      });
      const packet = buildSignedPublicDecisionPacket({
        epochSemantics: epochNonreceipt(),
        runId: fixtureMetadata.core_run_id,
      });

      await page.goto(packet.publicUrlPath);
      await expect(page.getByTestId("publication-packet-panel")).toBeVisible();
      await expect(page.getByTestId("signed-public-summary")).toBeVisible();
      const signedEpoch = page
        .getByTestId("signed-epoch-semantics")
        .locator("[data-epoch-presentation]");
      await expect(signedEpoch).toHaveAttribute(
        "data-epoch-presentation",
        "nonreceipt",
      );
      await expect(signedEpoch).toHaveAttribute(
        "data-epoch-status",
        "not_established",
      );
      await expect(page.getByTestId("human-decision-gate")).toHaveCount(0);
      await expect(
        page.getByTestId("human-decision-machine-export"),
      ).toHaveCount(0);
      expect(humanDecisionRequests).toEqual([]);
    });
  });

  test("bureaucratic document A4 print", async ({ page }) => {
    await installBureaucraticTimestampFixture(
      page,
      fixtureMetadata.decision_packet_artifact_id,
    );
    const surface = await openPrintSurface(page, {
      path: `/artifacts/${fixtureMetadata.decision_packet_artifact_id}?tab=bureaucratic&genre=postanova_kmu&trust=expanded`,
      readySelector: ".bureaucratic-document",
      readyTestId: "artifact-page",
      selector: '[data-testid="artifact-page"]',
    });
    await expect(surface).toHaveScreenshot(
      "bureaucratic-document-a4-print.png",
      {
        animations: "disabled",
        caret: "hide",
        maxDiffPixels: 100,
      },
    );
  });

  test("policy compare A4 print", async ({ page }) => {
    const surface = await openPrintSurface(page, {
      path: `/runs/compare?base=${fixtureMetadata.core_run_id}&target=${fixtureMetadata.core_run_id_secondary}&trust=compact`,
      readyTestId: "policy-diff-view",
      selector: '[data-testid="policy-diff-view"]',
    });
    await expect(surface).toHaveScreenshot("policy-compare-a4-print.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 100,
    });
  });

  test("counterfactual scenario A4 print", async ({ page }) => {
    const surface = await openPrintSurface(page, {
      path: `/compose?scenario_id=scn_rate_cut_25bps&cf_mode=actual_vs_scenario`,
      readyTestId: "composer-page",
      selector: '[data-testid="composer-page"]',
    });
    await expect(surface).toHaveScreenshot("scenario-a4-print.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 100,
    });
  });
});
