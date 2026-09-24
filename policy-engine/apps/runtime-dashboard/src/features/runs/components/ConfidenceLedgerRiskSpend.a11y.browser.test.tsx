import type { AvailableConfidenceLedgerRiskSpendPacket } from "@polisyos/runtime-api-client";
import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";

import openApiDocument from "../../../../../../schemas/runtime_api_v1.openapi.json";

import type { ConfidenceLedgerRiskSpendProjection } from "@/features/runs/api/useConfidenceLedgerRiskSpend";
import {
  CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA,
  type ConfidenceLedgerProtectedAnswer,
  type ConfidenceLedgerProtectedQuery,
  type ConfidenceLedgerRiskSpendPacket,
} from "@/features/runs/domain/confidenceLedgerRiskSpend";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { ConfidenceLedgerRiskSpend } from "./ConfidenceLedgerRiskSpend";

function availablePacket(): AvailableConfidenceLedgerRiskSpendPacket {
  const openApi = openApiDocument as unknown as {
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

function exactProjection(
  packet: AvailableConfidenceLedgerRiskSpendPacket,
): Extract<ConfidenceLedgerRiskSpendProjection, { status: "exact" }> {
  return {
    capturedResponseBytes: Object.freeze({
      byteLength: 3,
      copy: () => new Uint8Array([1, 2, 3]),
    }),
    packet: packet as unknown as ConfidenceLedgerRiskSpendPacket,
    protectedQueries: Object.fromEntries(
      CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA.map((query) => [
        query,
        "denied" as const,
      ]),
    ) as Record<
      ConfidenceLedgerProtectedQuery,
      ConfidenceLedgerProtectedAnswer
    >,
    receipt: {
      observation_basis: "candidate_and_captured_bytes_independently_admitted",
      packet_availability: "available",
      packet_projection_hash: packet.projection_hash,
      protected_query_count: 9,
      schema_version:
        "policyos.runtime.confidence_ledger_protected_query_evaluation.v1",
    },
    status: "exact",
  };
}

describe("ConfidenceLedgerRiskSpend accessibility", () => {
  it("has no violations in the ordered reviewer surface or full-envelope dialog", async () => {
    const packet = availablePacket();
    render(
      <LocaleProvider>
        <main>
          <ConfidenceLedgerRiskSpend projection={exactProjection(packet)} />
        </main>
      </LocaleProvider>,
    );

    expect((await axe.run(document.body)).violations).toHaveLength(0);

    fireEvent.click(
      screen.getAllByRole("button", {
        name: /≤ δ relative to the declared obligation set/iu,
      })[0],
    );
    await expect.element(screen.getByRole("dialog")).toBeVisible();
    expect((await axe.run(document.body)).violations).toHaveLength(0);
  }, 30_000);
});
