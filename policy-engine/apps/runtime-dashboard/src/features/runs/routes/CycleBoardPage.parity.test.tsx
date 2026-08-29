/* eslint-disable testing-library/no-container, testing-library/no-node-access -- real-page DOM mutation is the parity falsifier */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { AvailableConfidenceLedgerRiskSpendPacket } from "@polisyos/runtime-api-client";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { queryKeys } from "@/api/queryKeys";
import { packetToVisibleCycleBoard } from "@/features/runs/components/cycleBoardPresentation";
import { decodeCycleBoardDom } from "@/test/cycleBoardDomTwin";
import { TEST_AUTH_ME_RESPONSE } from "@/test/fixtures/authMe";
import { cycleBoardProjectionPacketFixture } from "@/test/fixtures/depthNCycleBoard";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/render";

import { evaluateConfidenceLedgerRiskSpendTwin } from "../export/confidenceLedgerRiskSpendTwin";
import { CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET } from "../domain/confidenceLedgerRiskSpend";
import { withConfidenceLedgerTestVisibilityPlatform } from "@/test/confidenceLedgerVisibilityPlatform";

import CycleBoardPage from "./CycleBoardPage";

const CYCLE_BOARD_ENDPOINT =
  "*/api/v1/exports/governed-projections/depth-n-cycle-board";
const RISK_SPEND_ENDPOINT =
  "*/api/v1/exports/governed-projections/confidence-ledger-risk-spend";

const NativeRequest = globalThis.Request;

class AbsoluteTestRequest extends NativeRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    super(
      typeof input === "string"
        ? new URL(input, "http://localhost").toString()
        : input,
      init,
    );
  }
}

function required(container: HTMLElement, selector: string): HTMLElement {
  // The mutation falsifier intentionally edits the rendered DOM after mount.
  const element = container.querySelector(selector);
  if (!(element instanceof HTMLElement)) {
    throw new Error(`Missing Cycle Board test region: ${selector}`);
  }
  return element;
}

async function openRiskSpendDialog(root: HTMLElement): Promise<void> {
  const trigger = required(root, "figure button");
  const user = userEvent.setup();
  await user.click(trigger);
}

function readBlobBytes(blob: Blob): Promise<Uint8Array> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () =>
      reject(reader.error ?? new Error("Failed to read Cycle Board export"));
    reader.onload = () => {
      if (!(reader.result instanceof ArrayBuffer)) {
        reject(new TypeError("Cycle Board export was not an ArrayBuffer"));
        return;
      }
      resolve(new Uint8Array(reader.result));
    };
    reader.readAsArrayBuffer(blob);
  });
}

function availableRiskPacket(): AvailableConfidenceLedgerRiskSpendPacket {
  const openApi = JSON.parse(
    readFileSync(
      resolve(process.cwd(), "../../schemas/runtime_api_v1.openapi.json"),
      "utf8",
    ),
  ) as {
    paths: Record<
      string,
      {
        get: {
          responses: Record<
            string,
            {
              content: Record<
                string,
                {
                  examples: {
                    default: {
                      value: AvailableConfidenceLedgerRiskSpendPacket;
                    };
                  };
                }
              >;
            }
          >;
        };
      }
    >;
  };
  return structuredClone(
    openApi.paths[
      "/api/v1/exports/governed-projections/confidence-ledger-risk-spend"
    ].get.responses["200"].content["application/json"].examples.default.value,
  );
}

function installPacketResponse() {
  const packet = cycleBoardProjectionPacketFixture();
  const wireText = `\n${JSON.stringify(packet, null, 2)}\n`;
  const wireBytes = new TextEncoder().encode(wireText);
  const riskPacket = availableRiskPacket();
  const riskWireText = `\n${JSON.stringify(riskPacket, null, 2)}\n`;
  const riskWireBytes = new TextEncoder().encode(riskWireText);
  let authRequests = 0;
  let requests = 0;
  let riskRequests = 0;
  server.use(
    http.get("*/api/v1/auth/me", () => {
      authRequests += 1;
      return HttpResponse.json(TEST_AUTH_ME_RESPONSE);
    }),
    http.get(CYCLE_BOARD_ENDPOINT, () => {
      requests += 1;
      return new HttpResponse(wireText, {
        headers: { "content-type": "application/json" },
        status: 200,
      });
    }),
    http.get(RISK_SPEND_ENDPOINT, () => {
      riskRequests += 1;
      return new HttpResponse(riskWireText, {
        headers: { "content-type": "application/json" },
        status: 200,
      });
    }),
  );
  return {
    authRequests: () => authRequests,
    packet,
    requests: () => requests,
    riskPacket,
    riskRequests: () => riskRequests,
    riskWireBytes,
    riskWireText,
    wireBytes,
    wireText,
  };
}

async function renderRealBoard() {
  const response = installPacketResponse();
  const view = renderWithProviders(<CycleBoardPage />, {
    initialEntries: ["/runs/cycle-board"],
  });
  try {
    await screen.findByTestId("cycle-board", {}, { timeout: 5_000 });
    await waitFor(
      () => {
        // This is the production-twin root, not a test-only identifier.
        expect(
          view.container.querySelector(
            '[data-confidence-surface="risk-spend"]',
          ),
        ).not.toBeNull();
      },
      { timeout: 5_000 },
    );
  } catch (error) {
    const authState = view.queryClient.getQueryState(queryKeys.authMe());
    throw new Error(
      `Cycle Board did not mount; auth requests=${String(response.authRequests())}; board requests=${String(response.requests())}; risk requests=${String(response.riskRequests())}; auth error=${String(authState?.error)}; auth state=${JSON.stringify(authState)}`,
      { cause: error },
    );
  }
  return { ...response, ...view };
}

function expectDomMismatch(
  container: HTMLElement,
  expected: ReturnType<typeof packetToVisibleCycleBoard>,
) {
  let decoded: ReturnType<typeof decodeCycleBoardDom> | undefined;
  let failure: unknown;
  try {
    decoded = decodeCycleBoardDom(container);
  } catch (error) {
    failure = error;
  }
  if (failure === undefined) {
    expect(decoded).not.toEqual(expected);
  }
}

describe("CycleBoardPage MACHINE/rendered-DOM parity", () => {
  beforeEach(() => {
    vi.stubGlobal("Request", AbsoluteTestRequest);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("decodes the complete real page DOM to the packet presentation", async () => {
    const { container, packet, requests } = await renderRealBoard();

    expect(decodeCycleBoardDom(container)).toEqual(
      packetToVisibleCycleBoard(packet),
    );
    expect(requests()).toBe(1);
  });

  it("admits the real response and independently evaluates the visible risk-spend DOM", async () => {
    const { container, riskPacket, riskRequests, riskWireBytes } =
      await renderRealBoard();
    const root = required(container, '[data-confidence-surface="risk-spend"]');
    await openRiskSpendDialog(root);

    const result = await withConfidenceLedgerTestVisibilityPlatform(
      root.ownerDocument,
      () =>
        evaluateConfidenceLedgerRiskSpendTwin({
          evaluationMode: "exact_finite_schema",
          packetCandidate: riskPacket,
          rawPacketBytes: riskWireBytes,
          root,
          stepBudget: CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
        }),
    );

    expect(result.status).toBe("exact");
    expect(riskRequests()).toBe(1);
  });

  it.each([
    {
      apply: (root: HTMLElement) => {
        required(
          root,
          '[data-confidence-leaf="posture.packet_may_not_use_for.0"]',
        ).remove();
        root.dataset.callerDeclaredSafe = "true";
        root.dataset.serverSafeMarker = "verified";
      },
      name: "protected denial while caller and server-safe markers remain",
      reason: "model_observation_inconsistent",
    },
    {
      apply: (root: HTMLElement) => {
        const payload = document.createElement("script");
        payload.hidden = true;
        payload.type = "application/json";
        payload.textContent = JSON.stringify({ authority: "safe" });
        root.append(payload);
      },
      name: "hidden raw payload",
      reason: "parser_or_schema_failure",
    },
    {
      apply: (root: HTMLElement) => {
        root.dataset.testid = "confidence-ledger-parity-proved";
      },
      name: "test-only proof marker",
      reason: "parser_or_schema_failure",
    },
  ])("blocks a $name mutation", async ({ apply, reason }) => {
    const { container, riskPacket, riskWireBytes } = await renderRealBoard();
    const root = required(container, '[data-confidence-surface="risk-spend"]');
    await openRiskSpendDialog(root);

    apply(root);

    await expect(
      withConfidenceLedgerTestVisibilityPlatform(root.ownerDocument, () =>
        evaluateConfidenceLedgerRiskSpendTwin({
          evaluationMode: "exact_finite_schema",
          packetCandidate: riskPacket,
          rawPacketBytes: riskWireBytes,
          root,
          stepBudget: CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
        }),
      ),
    ).resolves.toEqual({ reason, status: "blocked" });
  });

  it.each([
    {
      apply: (container: HTMLElement) => {
        required(container, "[data-cycle-board-row]").remove();
      },
      name: "dropped row",
    },
    {
      apply: (container: HTMLElement) => {
        const row = required(container, "[data-cycle-board-row]");
        row.parentElement?.append(row.cloneNode(true));
      },
      name: "duplicate row",
    },
    {
      apply: (container: HTMLElement) => {
        required(
          container,
          '[data-cycle-board-field="lifecycleTerminality"]',
        ).setAttribute(
          "data-cycle-board-raw",
          JSON.stringify({
            availability: "available",
            source_ref: "fabricated://default",
            value: false,
          }),
        );
      },
      name: "defaulted lifecycle absence",
    },
    {
      apply: (container: HTMLElement) => {
        required(container, "[data-cycle-board-source]").remove();
      },
      name: "omitted source",
    },
    {
      apply: (container: HTMLElement) => {
        const movement = document.createElement("div");
        movement.setAttribute("data-cycle-board-movement", "");
        movement.setAttribute(
          "data-cycle-board-raw",
          JSON.stringify({ invented: true }),
        );
        required(container, "[data-cycle-board-row]").append(movement);
      },
      name: "fabricated movement",
    },
    {
      apply: (container: HTMLElement) => {
        required(container, "[data-cycle-board-source]").setAttribute(
          "data-cycle-board-raw",
          JSON.stringify("Недоступно"),
        );
      },
      name: "localized raw fact",
    },
  ])("rejects a rendered $name mutation", async ({ apply }) => {
    const { container, packet } = await renderRealBoard();
    const expected = packetToVisibleCycleBoard(packet);
    expect(decodeCycleBoardDom(container)).toEqual(expected);

    apply(container);

    expectDomMismatch(container, expected);
  });

  it("downloads the exact bytes from the one request that rendered the page", async () => {
    const user = userEvent.setup();
    const createObjectUrl = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:cycle-board");
    const revokeObjectUrl = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined);
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    const { requests, wireBytes, wireText } = await renderRealBoard();
    expect(wireText).not.toBe(
      JSON.stringify(cycleBoardProjectionPacketFixture()),
    );
    expect(requests()).toBe(1);

    await user.click(
      screen.getByRole("button", { name: /export.*cycle board/iu }),
    );

    expect(requests()).toBe(1);
    expect(click).toHaveBeenCalledTimes(1);
    const blob = createObjectUrl.mock.calls[0]?.[0];
    expect(blob).toBeInstanceOf(Blob);
    const downloadedBytes = await readBlobBytes(blob as Blob);
    expect(downloadedBytes.byteLength).toBe(wireBytes.byteLength);
    expect(
      downloadedBytes.every((value, index) => value === wireBytes[index]),
    ).toBe(true);
    expect(revokeObjectUrl).toHaveBeenCalledWith("blob:cycle-board");
  });

  it("downloads the exact risk-spend response bytes without a second request", async () => {
    const user = userEvent.setup();
    const createObjectUrl = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:confidence-ledger-risk-spend");
    const revokeObjectUrl = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined);
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    const { riskRequests, riskWireBytes, riskWireText } =
      await renderRealBoard();
    expect(riskWireText).not.toBe(JSON.stringify(availableRiskPacket()));
    expect(riskRequests()).toBe(1);

    await user.click(
      screen.getByRole("button", { name: "Download exact MACHINE packet" }),
    );

    expect(riskRequests()).toBe(1);
    expect(click).toHaveBeenCalledTimes(1);
    const blob = createObjectUrl.mock.calls[0]?.[0];
    expect(blob).toBeInstanceOf(Blob);
    const downloadedBytes = await readBlobBytes(blob as Blob);
    expect(downloadedBytes.byteLength).toBe(riskWireBytes.byteLength);
    expect(
      downloadedBytes.every((value, index) => value === riskWireBytes[index]),
    ).toBe(true);
    expect(revokeObjectUrl).toHaveBeenCalledWith(
      "blob:confidence-ledger-risk-spend",
    );
  });
});
