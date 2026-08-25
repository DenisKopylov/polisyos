import { screen } from "@testing-library/react";

import type { GovernanceDebugPayload } from "@/api/validators";
import { renderWithProviders } from "@/test/render";

import GovernanceReport from "./GovernanceReport";

describe("GovernanceReport", () => {
  it("keeps open owner severity opaque and runtime novelty unrecognized", () => {
    const data = {
      issues: [
        { code: "known", message: "Known blocker", severity: "fail" },
        {
          code: "novel",
          message: "Novel owner severity",
          severity: "future_owner_severity",
        },
      ],
      verdict: "candidate",
    } as GovernanceDebugPayload["debug"];

    renderWithProviders(<GovernanceReport data={data} />);

    expect(screen.getByText("fail")).toHaveAttribute(
      "data-authority-recognition",
      "unrecognized",
    );
    expect(screen.getByText("fail")).toHaveAttribute(
      "data-presentation-tone",
      "neutral",
    );
    expect(screen.getByText("future_owner_severity")).toHaveAttribute(
      "data-authority-recognition",
      "unrecognized",
    );
    expect(screen.getByText("future_owner_severity")).toHaveAttribute(
      "data-presentation-tone",
      "neutral",
    );
  });
});
