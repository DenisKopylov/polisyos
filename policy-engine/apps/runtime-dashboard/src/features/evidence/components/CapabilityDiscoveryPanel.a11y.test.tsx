import { render, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
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

import { createCapabilitySearchRequest } from "@/api/hooks/useCapabilitySearch";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { CapabilityDiscoveryPanel } from "./CapabilityDiscoveryPanel";

describe("CapabilityDiscoveryPanel accessibility", () => {
  it("announces candidate and negative state with keyboard-focusable search and MACHINE download", async () => {
    useCapabilitySearchMock.mockReturnValue({
      data: {
        rawBytes: new Uint8Array(),
        response: {
          frontier: {
            actual_cutoff: null,
            candidates: [],
            completeness_status: "producer_missing",
            evaluated_count: 1,
            incompleteness_reasons: ["agent:producer_missing"],
            index_version_refs: [],
            indexes_used: [],
            no_hit_frontier: [],
            rejected_candidates: [],
            requested_count: 1,
            returned_count: 1,
          },
          request: {
            audience: "REVIEWER",
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
              capability_ref: "candidate",
              description: "candidate",
              discovery_result: {
                producer_ref: "index-owner",
                provenance_refs: ["index-receipt"],
                reason_codes: [],
                state: "discoverable",
                time: {
                  freshness: "current",
                  observed_at: "2026-08-26T00:00:00Z",
                },
              },
              execution_result: {
                producer_ref: "execution-owner",
                provenance_refs: ["execution-receipt"],
                reason_codes: [],
                state: "executable",
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
    const { container } = render(
      <LocaleProvider>
        <CapabilityDiscoveryPanel
          request={createCapabilitySearchRequest("candidate", "a11y")}
        />
      </LocaleProvider>,
    );
    expect((await axe(container)).violations).toHaveLength(0);
    expect(screen.getByRole("status")).toHaveTextContent("Candidate search");
    expect(screen.getByRole("status")).toHaveTextContent(
      "agent:producer_missing",
    );
    const input = screen.getByLabelText("Search capabilities");
    input.focus();
    expect(input).toHaveFocus();
    const download = screen.getByRole("button", {
      name: "Download MACHINE JSON",
    });
    download.focus();
    expect(download).toHaveFocus();
  });
});
