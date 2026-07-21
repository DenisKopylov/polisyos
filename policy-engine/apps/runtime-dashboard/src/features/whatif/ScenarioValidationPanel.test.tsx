import { render, screen } from "@testing-library/react";

import { ScenarioValidationPanel } from "./ScenarioValidationPanel";

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const draftScenario = {
  known_limitations: [],
  stale_reasons: [],
  status: "draft" as const,
};

describe("ScenarioValidationPanel", () => {
  it("does not infer validation readiness from empty local issue arrays", () => {
    render(
      <ScenarioValidationPanel
        scenario={draftScenario}
        unsupportedReasons={[]}
      />,
    );

    expect(
      screen.queryByText("shared.ui.counterfactual.validationReady"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("draft")).toBeInTheDocument();
  });
});
