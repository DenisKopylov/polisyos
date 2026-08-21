import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { axe } from "vitest-axe";

import type { QuantityValueOutput } from "@polisyos/runtime-api-client";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import { createTestQueryClient } from "@/test/queryClient";

import { OuterSetValue, OuterSetValueStateCell } from "./OuterSetValue";

function member(metricId: string, point: number | null): QuantityValueOutput {
  return {
    label: metricId,
    lineage: { freshness: "current", id: `lineage:${metricId}`, status: "verified" },
    metric_id: metricId,
    point,
    quantity_class: "decision",
    time: null,
    uncertainty: null,
    unit: { code: "1", display: "value", system: "ucum" },
  };
}

function Harness({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={createTestQueryClient()}>
      <LocaleProvider>{children}</LocaleProvider>
    </QueryClientProvider>
  );
}

describe("OuterSetValue accessibility", () => {
  it("has no violations rendering a set with a producer verdict", async () => {
    const { container } = render(
      <Harness>
        <OuterSetValue
          comparison="incomparable"
          members={[member("a", -0.3), member("b", 0.7)]}
        />
      </Harness>,
    );

    expect((await axe(container)).violations).toHaveLength(0);
  });

  it("has no violations across all three value states", async () => {
    const { container } = render(
      <Harness>
        <OuterSetValueStateCell state="zero" value={member("zero", 0)} />
        <OuterSetValueStateCell state="unknown" value={member("unknown", null)} />
        <OuterSetValueStateCell state="gap" value={member("gap", null)} />
      </Harness>,
    );

    expect((await axe(container)).violations).toHaveLength(0);
  });
});
