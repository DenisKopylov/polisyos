import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { queryKeys } from "@/api/queryKeys";
import { packetToVisibleCycleBoard } from "@/features/runs/components/cycleBoardPresentation";
import { decodeCycleBoardDom } from "@/test/cycleBoardDomTwin";
import { TEST_AUTH_ME_RESPONSE } from "@/test/fixtures/authMe";
import { cycleBoardProjectionPacketFixture } from "@/test/fixtures/depthNCycleBoard";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/render";

import CycleBoardPage from "./CycleBoardPage";

const ENDPOINT = "*/api/v1/exports/governed-projections/depth-n-cycle-board";

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
  // eslint-disable-next-line testing-library/no-node-access
  const element = container.querySelector(selector);
  if (!(element instanceof HTMLElement)) {
    throw new Error(`Missing Cycle Board test region: ${selector}`);
  }
  return element;
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

function installPacketResponse() {
  const packet = cycleBoardProjectionPacketFixture();
  const wireText = `\n${JSON.stringify(packet, null, 2)}\n`;
  const wireBytes = new TextEncoder().encode(wireText);
  let authRequests = 0;
  let requests = 0;
  server.use(
    http.get("*/api/v1/auth/me", () => {
      authRequests += 1;
      return HttpResponse.json(TEST_AUTH_ME_RESPONSE);
    }),
    http.get(ENDPOINT, () => {
      requests += 1;
      return new HttpResponse(wireText, {
        headers: { "content-type": "application/json" },
        status: 200,
      });
    }),
  );
  return {
    authRequests: () => authRequests,
    packet,
    requests: () => requests,
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
  } catch (error) {
    const authState = view.queryClient.getQueryState(queryKeys.authMe());
    throw new Error(
      `Cycle Board did not mount; auth requests=${String(response.authRequests())}; board requests=${String(response.requests())}; auth error=${String(authState?.error)}; auth state=${JSON.stringify(authState)}`,
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
    vi.unstubAllGlobals();
  });

  it("decodes the complete real page DOM to the packet presentation", async () => {
    const { container, packet, requests } = await renderRealBoard();

    expect(decodeCycleBoardDom(container)).toEqual(
      packetToVisibleCycleBoard(packet),
    );
    expect(requests()).toBe(1);
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
});
