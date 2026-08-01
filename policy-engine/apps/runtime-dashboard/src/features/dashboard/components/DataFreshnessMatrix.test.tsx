import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import { createInteractionState } from "@/shared/lib/domain/statusOwnership";

import { DataFreshnessMatrix } from "./DataFreshnessMatrix";

describe("DataFreshnessMatrix", () => {
  it("keeps telemetry display state outside authority status slots", () => {
    render(
      <LocaleProvider>
        <DataFreshnessMatrix
          sources={[
            {
              displayState: createInteractionState("fresh", "telemetry"),
              label: "Current source",
              lastUpdated: "2026-04-20T00:00:00Z",
              sourceId: "current",
            },
            {
              displayState: createInteractionState(
                "novel-owner-label",
                "telemetry",
              ),
              label: "Novel source",
              lastUpdated: "2026-04-19T00:00:00Z",
              sourceId: "novel",
            },
          ]}
        />
      </LocaleProvider>,
    );

    expect(screen.getByText("1 fresh")).toBeInTheDocument();
    expect(screen.getByText("0 stale")).toBeInTheDocument();
    expect(screen.getByText("1 unknown")).toBeInTheDocument();
    expect(screen.getByTestId("data-freshness-source-novel")).toHaveAttribute(
      "data-display-state",
      "novel-owner-label",
    );
  });
});
