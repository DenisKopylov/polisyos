import { fireEvent, render, screen, within } from "@testing-library/react";
import { vi } from "vitest";

const { useCapabilitySearchMock } = vi.hoisted(() => ({
  useCapabilitySearchMock: vi.fn(),
}));

vi.mock("@/api/hooks/useCapabilitySearch", async () => {
  const actual = await vi.importActual<
    typeof import("@/api/hooks/useCapabilitySearch")
  >("@/api/hooks/useCapabilitySearch");
  return { ...actual, useCapabilitySearch: useCapabilitySearchMock };
});

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import { createCapabilitySearchRequest } from "@/api/hooks/useCapabilitySearch";

import { CapabilityDiscoveryPanel } from "./CapabilityDiscoveryPanel";

describe("CapabilityDiscoveryPanel", () => {
  it.each(["REVIEWER", "EXPERT"] as const)(
    "renders typed negative reasons for the %s audience",
    (audience) => {
      useCapabilitySearchMock.mockReturnValue({
        data: {
          rawBytes: new Uint8Array(),
          response: {
            frontier: {
              candidates: [],
              completeness_status: "complete",
              evaluated_count: 1,
              index_version_refs: [],
              indexes_used: [],
              incompleteness_reasons: [],
              no_hit_frontier: [],
              rejected_candidates: [],
              requested_count: 1,
              returned_count: 1,
            },
            request: {
              audience,
              resource_kinds: ["agent"],
              search: { allowed_modes: ["lexical"], query_text: "candidate" },
            },
            results: [
              {
                authority_result: {
                  producer_ref: "authority-owner",
                  provenance_refs: ["authority-receipt"],
                  reason_codes: ["not_established"],
                  state: "bridge_missing",
                  time: {
                    freshness: "current",
                    observed_at: "2026-08-26T00:00:00Z",
                  },
                },
                capability_ref: "test-capability",
                description: "A generic candidate",
                discovery_result: {
                  producer_ref: "index-owner",
                  provenance_refs: ["index-receipt"],
                  reason_codes: ["index_stale"],
                  state: "index_stale",
                  time: {
                    freshness: "stale",
                    observed_at: "2026-08-26T00:00:00Z",
                  },
                },
                execution_result: {
                  producer_ref: "execution-owner",
                  provenance_refs: ["execution-receipt"],
                  reason_codes: ["operation_missing"],
                  state: "operation_missing",
                  time: {
                    freshness: "current",
                    observed_at: "2026-08-26T00:00:00Z",
                  },
                },
                label: "Candidate",
                resource_kind: "agent",
              },
            ],
          },
        },
        isError: false,
        isLoading: false,
      });

      render(
        <LocaleProvider>
          <CapabilityDiscoveryPanel
            request={{
              ...createCapabilitySearchRequest("candidate", "panel-test"),
              audience,
            }}
          />
        </LocaleProvider>,
      );

      expect(
        within(
          screen.getByRole("region", { name: "Capability request" }),
        ).getByText(audience, {
          selector: "[data-capability-request-audience]",
        }),
      ).toBeVisible();

      const reasons = screen.getByRole("list", {
        name: "Capability posture proofs",
      });
      expect(reasons).toHaveTextContent("discovery: index_stale");
      expect(reasons).toHaveTextContent("execution: operation_missing");
      expect(reasons).toHaveTextContent("authority: bridge_missing");
      expect(reasons).toHaveTextContent("reasons: not_established");
      expect(screen.getByText("Candidate · bridge_missing")).toBeVisible();

      fireEvent.change(screen.getByLabelText("Search capabilities"), {
        target: { value: "new owner term" },
      });
      expect(useCapabilitySearchMock).toHaveBeenLastCalledWith(
        expect.objectContaining({
          search: expect.objectContaining({
            construct_refs: ["new owner term"],
            query_text: "new owner term",
          }),
        }),
        undefined,
      );
    },
  );

  it("fails closed instead of retaining a stale executable packet after an error", () => {
    useCapabilitySearchMock.mockReturnValue({
      data: {
        rawBytes: new Uint8Array([1]),
        response: {
          frontier: {
            candidates: [],
            completeness_status: "complete",
            evaluated_count: 1,
            incompleteness_reasons: [],
            index_version_refs: ["stale-epoch"],
            indexes_used: ["owner"],
            no_hit_frontier: [],
            rejected_candidates: [],
            requested_count: 1,
            returned_count: 1,
          },
          results: [
            {
              authority_result: { state: "bridge_missing" },
              capability_ref: "stale-executable",
              discovery_result: { state: "discoverable" },
              execution_result: { state: "executable" },
              label: "Stale executable",
            },
          ],
        },
      },
      isError: true,
      isLoading: false,
    });

    render(
      <LocaleProvider>
        <CapabilityDiscoveryPanel
          request={createCapabilitySearchRequest("candidate", "panel-error")}
        />
      </LocaleProvider>,
    );

    expect(
      screen.getByText("Capability discovery is unavailable."),
    ).toBeVisible();
    expect(screen.queryByText("Stale executable")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Download MACHINE JSON" }),
    ).not.toBeInTheDocument();
  });

  it("rebinds an already-mounted panel to a palette-selected owner ref", () => {
    useCapabilitySearchMock.mockReturnValue({
      data: undefined,
      isError: false,
      isLoading: false,
    });
    const view = render(
      <LocaleProvider>
        <CapabilityDiscoveryPanel
          request={createCapabilitySearchRequest("evidence", "panel-rebind")}
        />
      </LocaleProvider>,
    );

    view.rerender(
      <LocaleProvider>
        <CapabilityDiscoveryPanel
          request={createCapabilitySearchRequest(
            "capability:generated:owner-row",
            "panel-rebind",
          )}
        />
      </LocaleProvider>,
    );

    expect(screen.getByLabelText("Search capabilities")).toHaveValue(
      "capability:generated:owner-row",
    );
    expect(useCapabilitySearchMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        search: expect.objectContaining({
          construct_refs: ["capability:generated:owner-row"],
          query_text: "capability:generated:owner-row",
        }),
      }),
      undefined,
    );

    fireEvent.change(screen.getByLabelText("Search capabilities"), {
      target: { value: "" },
    });
    expect(useCapabilitySearchMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        search: expect.objectContaining({
          budget: expect.objectContaining({ match_all: true }),
          construct_refs: ["*"],
          query_text: "*",
        }),
      }),
      undefined,
    );
  });
});
