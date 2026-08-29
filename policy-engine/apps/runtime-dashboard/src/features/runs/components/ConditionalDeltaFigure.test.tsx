import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { AvailableConfidenceLedgerRiskSpendPacket } from "@polisyos/runtime-api-client";
import { fireEvent, render, screen, within } from "@testing-library/react";

import {
  CONFIDENCE_LEDGER_DECLARED_SET_RIDER,
  CONFIDENCE_LEDGER_LOCALITY_RIDER,
} from "@/features/runs/domain/confidenceLedgerRiskSpend";

import { ConditionalDeltaFigure } from "./ConditionalDeltaFigure";

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    t: (key: string) =>
      ({
        "common.close": "Close",
        "pages.cycleBoard.confidenceLedger.figure.canonicalDecimal":
          "Canonical decimal",
        "pages.cycleBoard.confidenceLedger.figure.dialogDescription":
          "The complete producer-issued conditionality envelope for this amount.",
        "pages.cycleBoard.confidenceLedger.figure.dialogTitle":
          "Conditional envelope",
      })[key] ?? key,
  }),
}));

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

describe("ConditionalDeltaFigure", () => {
  it("renders exact rational accounting through one two-rider disclosure chip", () => {
    const packet = availablePacket();
    const amount = packet.payload.obligation_class_risk_spend[6].allocation;

    render(
      <ConditionalDeltaFigure
        amount={amount}
        coverageEnvelope={packet.payload.coverage_envelope}
        label="Effect allocation"
      />,
    );

    expect(screen.getByText("Effect allocation")).toBeVisible();
    expect(screen.getByText("1/1500")).toBeVisible();
    expect(screen.getByText("0.000(6)")).toBeVisible();
    const disclosure = screen.getByRole("button", {
      name: new RegExp(
        `${CONFIDENCE_LEDGER_DECLARED_SET_RIDER}.*${CONFIDENCE_LEDGER_LOCALITY_RIDER}`,
        "u",
      ),
    });
    expect(disclosure).toBeVisible();
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("opens one accessible dialog that resolves the complete envelope", () => {
    const packet = availablePacket();
    const envelope = packet.payload.coverage_envelope;

    render(
      <ConditionalDeltaFigure
        amount={packet.payload.scope_total_risk_spend.allocation}
        coverageEnvelope={envelope}
        label="Scope allocation"
      />,
    );

    const trigger = screen.getByRole("button");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(trigger);

    const dialog = screen.getByRole("dialog", {
      name: /scope allocation.*conditional envelope/iu,
    });
    expect(dialog).toBeVisible();
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(trigger).toHaveAttribute("aria-controls", dialog.id);
    expect(trigger).toHaveAttribute(
      "aria-label",
      `Scope allocation: ${CONFIDENCE_LEDGER_DECLARED_SET_RIDER} — ${CONFIDENCE_LEDGER_LOCALITY_RIDER}`,
    );
    expect(dialog).toHaveAccessibleDescription(
      "The complete producer-issued conditionality envelope for this amount.",
    );
    expect(dialog).toHaveAttribute(
      "data-confidence-dialog-trigger-id",
      trigger.id,
    );
    expect(dialog).toHaveAttribute(
      "data-confidence-amount-hash",
      packet.payload.scope_total_risk_spend.allocation.amount_hash,
    );
    expect(dialog).toHaveAttribute(
      "data-confidence-scope-id",
      packet.payload.scope_total_risk_spend.allocation.scope_id,
    );
    expect(dialog).toHaveAttribute(
      "data-confidence-declared-classes-hash",
      packet.payload.scope_total_risk_spend.allocation
        .declared_obligation_classes_hash,
    );
    expect(dialog).toHaveAttribute(
      "data-confidence-semantic-role",
      packet.payload.scope_total_risk_spend.allocation.semantic_role,
    );
    expect(within(dialog).getByText(envelope.envelope_ref)).toBeVisible();
    expect(within(dialog).getByText(envelope.envelope_hash)).toBeVisible();
    expect(within(dialog).getByText(envelope.scope_id)).toBeVisible();
    expect(
      within(dialog).getAllByText(envelope.owner_scope_key)[0],
    ).toBeVisible();
    for (const obligationClass of envelope.declared_obligation_classes) {
      expect(within(dialog).getByText(obligationClass)).toBeVisible();
    }
    for (const reasonCode of envelope.reason_codes) {
      expect(within(dialog).getByText(reasonCode)).toBeVisible();
    }
    expect(
      within(dialog).getByText(CONFIDENCE_LEDGER_DECLARED_SET_RIDER),
    ).toBeVisible();
    expect(
      within(dialog).getByText(CONFIDENCE_LEDGER_LOCALITY_RIDER),
    ).toBeVisible();
  });

  it("never emits a family, sequence, cumulative, or narrowed-satisfaction claim", () => {
    const packet = availablePacket();

    render(
      <ConditionalDeltaFigure
        amount={packet.payload.scope_total_risk_spend.spent}
        coverageEnvelope={packet.payload.coverage_envelope}
        label="Scope spent"
      />,
    );

    expect(
      screen.queryByText(
        /parent total|family total|sequence total|cumulative total/iu,
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/narrowed claim.*satisfied/iu),
    ).not.toBeInTheDocument();
  });
});
