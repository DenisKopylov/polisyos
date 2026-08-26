import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import {
  createCapabilitySearchRequest,
  type CapturedCapabilitySearch,
} from "@/api/hooks/useCapabilitySearch";
import {
  capabilityDiscoveryTwin,
  decodeCapabilityDiscoveryDom,
} from "@/features/evidence/export/capabilityDiscoveryTwin";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import { server } from "@/test/msw/server";

import { CapabilityDiscoveryPanel } from "./CapabilityDiscoveryPanel";

const baseUrl = process.env.DS10_CAPABILITY_BASE_URL;
const generatedCapabilityId = process.env.DS10_CAPABILITY_GENERATED_ID;
const describeLive =
  baseUrl && generatedCapabilityId ? describe : describe.skip;

function LivePanel({
  onCaptured,
}: {
  onCaptured: (value: CapturedCapabilitySearch) => void;
}) {
  const request = createCapabilitySearchRequest(
    generatedCapabilityId as string,
    "ds10-free-growth-dashboard",
  );
  return (
    <CapabilityDiscoveryPanel
      baseUrl={baseUrl}
      onCaptured={onCaptured}
      request={request}
    />
  );
}

describeLive("DS10 capability discovery free growth", () => {
  beforeAll(() => {
    // This identity must reach the real FastAPI server, never an MSW handler.
    server.close();
  });
  afterEach(() => vi.restoreAllMocks());

  it("renders the owner-index result without a dashboard identifier branch", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    let captured: CapturedCapabilitySearch | null = null;
    let downloaded: Blob | null = null;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => undefined,
    );
    vi.spyOn(URL, "createObjectURL").mockImplementation((value) => {
      downloaded = value as Blob;
      return "blob:ds10-capability-discovery";
    });
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);

    const view = render(
      <QueryClientProvider client={queryClient}>
        <LocaleProvider>
          <LivePanel onCaptured={(value) => (captured = value)} />
        </LocaleProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(captured).not.toBeNull());
    const settled = captured as CapturedCapabilitySearch;
    expect(settled.response.results).toHaveLength(1);
    expect(settled.response.results[0]?.capability_ref).toBe(
      generatedCapabilityId,
    );
    expect(settled.response.results[0]?.authority_result.state).toBe(
      "bridge_missing",
    );
    expect(settled.response.results[0]?.authority_result.state).not.toBe(
      "admitted_authority",
    );

    const result = screen
      .getByTestId("capability-discovery-panel")
      .querySelector("[data-capability-ref]");
    expect(result).toHaveAttribute(
      "data-capability-ref",
      generatedCapabilityId,
    );
    expect(result).toHaveTextContent("Candidate");
    expect(result).toHaveTextContent("not_established");
    expect(result).toHaveTextContent(
      settled.response.results[0]?.execution_result.state ?? "",
    );

    expect(decodeCapabilityDiscoveryDom(view.container)).toEqual(
      capabilityDiscoveryTwin(settled),
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Download MACHINE JSON" }),
    );
    await waitFor(() => expect(downloaded).not.toBeNull());
    const machineBytes = await new Promise<Uint8Array>((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () =>
        reject(reader.error ?? new Error("Failed to read capability export"));
      reader.onload = () =>
        resolve(new Uint8Array(reader.result as ArrayBuffer));
      reader.readAsArrayBuffer(downloaded as Blob);
    });
    expect(machineBytes).toEqual(settled.rawBytes);
  });
});
