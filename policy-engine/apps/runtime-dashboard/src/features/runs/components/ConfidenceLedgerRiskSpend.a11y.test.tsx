import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { AvailableConfidenceLedgerRiskSpendPacket } from "@polisyos/runtime-api-client";
import { fireEvent, render, screen } from "@testing-library/react";
import { axe } from "vitest-axe";

import type { ConfidenceLedgerRiskSpendPacket } from "@/features/runs/domain/confidenceLedgerRiskSpend";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { ConfidenceLedgerRiskSpend } from "./ConfidenceLedgerRiskSpend";

function availablePacket(): AvailableConfidenceLedgerRiskSpendPacket {
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

describe("ConfidenceLedgerRiskSpend accessibility", () => {
  it("has no violations in the ordered reviewer surface or full-envelope dialog", async () => {
    const packet = availablePacket();
    render(
      <LocaleProvider>
        <main>
          <ConfidenceLedgerRiskSpend
            projection={{
              packet: packet as unknown as ConfidenceLedgerRiskSpendPacket,
              rawPacketBytes: new Uint8Array([1, 2, 3]),
            }}
          />
        </main>
      </LocaleProvider>,
    );

    expect((await axe(document.body)).violations).toHaveLength(0);

    fireEvent.click(
      screen.getAllByRole("button", {
        name: /≤ δ relative to the declared obligation set/iu,
      })[0],
    );
    expect(screen.getByRole("dialog")).toBeVisible();
    expect((await axe(document.body)).violations).toHaveLength(0);
  }, 30_000);
});
