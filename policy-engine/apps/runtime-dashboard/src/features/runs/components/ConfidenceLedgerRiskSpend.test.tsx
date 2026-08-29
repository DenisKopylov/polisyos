/* eslint-disable testing-library/no-node-access -- ordered visible DOM is the independent semantic oracle */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { AvailableConfidenceLedgerRiskSpendPacket } from "@polisyos/runtime-api-client";
import { fireEvent, render, screen, within } from "@testing-library/react";

import type { ConfidenceLedgerRiskSpendProjection } from "@/features/runs/api/useConfidenceLedgerRiskSpend";
import type { ConfidenceLedgerRiskSpendPacket } from "@/features/runs/domain/confidenceLedgerRiskSpend";

import { ConfidenceLedgerRiskSpend } from "./ConfidenceLedgerRiskSpend";

const { exportCapturedResponseBytesMock } = vi.hoisted(() => ({
  exportCapturedResponseBytesMock: vi.fn(),
}));

vi.mock("@/shared/ui/dataExport", () => ({
  exportCapturedResponseBytes: (...args: unknown[]) =>
    exportCapturedResponseBytesMock(...args),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

function availableProjection(): ConfidenceLedgerRiskSpendProjection {
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
  const packet = structuredClone(
    openApi.paths[
      "/api/v1/exports/governed-projections/confidence-ledger-risk-spend"
    ].get.responses["200"].content["application/json"].examples.default.value,
  );
  return {
    packet: packet as unknown as ConfidenceLedgerRiskSpendPacket,
    rawPacketBytes: new TextEncoder().encode("exact MACHINE packet"),
  };
}

describe("ConfidenceLedgerRiskSpend", () => {
  beforeEach(() => exportCapturedResponseBytesMock.mockReset());

  it("renders the complete available packet in the mandated semantic order", () => {
    const projection = availableProjection();
    render(<ConfidenceLedgerRiskSpend projection={projection} />);

    const sections = [
      ...document.querySelectorAll<HTMLElement>("[data-confidence-section]"),
    ];
    expect(
      sections.map((section) => section.dataset.confidenceSection),
    ).toEqual([
      "actual-rows",
      "risk-accounting",
      "instrument-denominators",
      "positive-register",
      "good-event-source-replay",
      "machine-export",
    ]);

    const actualRows = sections[0].querySelectorAll("ol > li");
    expect(actualRows).toHaveLength(3);
    expect(actualRows[0]).toHaveTextContent("refusal");
    expect(actualRows[1]).toHaveTextContent("acquisition");
    expect(actualRows[2]).toHaveTextContent("acquisition");

    expect(
      document.querySelectorAll('[data-confidence-list="class-spend"] > li'),
    ).toHaveLength(15);
    expect(
      document.querySelectorAll(
        '[data-confidence-list="instrument-definitions"] > li',
      ),
    ).toHaveLength(13);
    expect(
      document.querySelectorAll(
        '[data-confidence-list="certificate-routes"] > li',
      ),
    ).toHaveLength(6);
    expect(document.querySelectorAll("figure")).toHaveLength(67);
    expect(sections[3]).toHaveTextContent("valid_zero");
    expect(sections[3]).toHaveTextContent(
      "institutional_authority_unappointed",
    );
    expect(sections[3]).toHaveTextContent("open_world_unresolved");
  });

  it("downloads only the captured owner-response bytes from the final MACHINE section", () => {
    const projection = availableProjection();
    render(<ConfidenceLedgerRiskSpend projection={projection} />);

    const exportSection = document.querySelector<HTMLElement>(
      '[data-confidence-section="machine-export"]',
    );
    expect(exportSection).not.toBeNull();
    fireEvent.click(
      within(exportSection as HTMLElement).getByRole("button", {
        name: /machine/iu,
      }),
    );

    expect(exportCapturedResponseBytesMock).toHaveBeenCalledTimes(1);
    expect(exportCapturedResponseBytesMock).toHaveBeenCalledWith(
      "confidence-ledger-risk-spend.machine.json",
      projection.rawPacketBytes,
      "application/json",
    );
  });

  it("limits source-blocked rendering to blocker and source/validator/replay identities", () => {
    const available = availableProjection();
    const sourceArtifactContentHash = `sha256:${"2".repeat(64)}`;
    const packet = {
      absence_reason: null,
      as_of: "2026-02-11T12:00:00Z",
      availability: "source_blocked",
      projection_hash: `sha256:${"1".repeat(64)}`,
      replay_address: "/replay/blocked",
      replay_pins: {
        artifact_content_hash: `sha256:${"2".repeat(64)}`,
        projection_hash: `sha256:${"1".repeat(64)}`,
        projection_rule_version:
          "policyos.runtime.confidence_ledger_risk_spend.v1",
        source_as_of: "2026-02-11T12:00:00Z",
        source_dependency_hash: `sha256:${"3".repeat(64)}`,
      },
      source_artifact_content_hash: sourceArtifactContentHash,
      source_blocked_reason: "over_spend",
      source_dependency_hash: `sha256:${"3".repeat(64)}`,
      source_rule_version: null,
      source_schema_version: "policyos.runtime.confidence_ledger.v1",
      worker_validation_receipt_hash: `sha256:${"4".repeat(64)}`,
      worker_validation_receipt_ref: `owner-validation:sha256:${"4".repeat(64)}`,
      rejected_details: "REJECTED SOURCE ROW MUST NOT LEAK",
    } as unknown as ConfidenceLedgerRiskSpendPacket;

    render(<ConfidenceLedgerRiskSpend projection={{ ...available, packet }} />);

    expect(screen.getByText("over_spend")).toBeVisible();
    expect(screen.getAllByText(sourceArtifactContentHash)[0]).toBeVisible();
    expect(
      screen.getByText(packet.worker_validation_receipt_ref as string),
    ).toBeVisible();
    expect(screen.getByText(packet.replay_address as string)).toBeVisible();
    expect(
      screen.queryByText("REJECTED SOURCE ROW MUST NOT LEAK"),
    ).not.toBeInTheDocument();
    expect(document.querySelector("figure")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /machine/iu }),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["artifact_missing", "governed confidence-ledger source is absent"],
    ["invalid_source", "confidence-ledger source failed owner admission"],
  ])(
    "renders the typed %s arm without inventing packet detail",
    (availability, absenceReason) => {
      const projection = availableProjection();
      const packet = {
        absence_reason: absenceReason,
        as_of: "2026-02-11T12:00:00Z",
        availability,
      } as unknown as ConfidenceLedgerRiskSpendPacket;

      render(
        <ConfidenceLedgerRiskSpend projection={{ ...projection, packet }} />,
      );

      expect(screen.getByText(absenceReason)).toBeVisible();
      expect(
        screen.queryByRole("button", { name: /machine/iu }),
      ).not.toBeInTheDocument();
    },
  );

  it("does not emit parent/family/sequence totals or a satisfied narrowed claim", () => {
    render(<ConfidenceLedgerRiskSpend projection={availableProjection()} />);

    expect(
      screen.queryByText(
        /parent total|family total|sequence total|cross-scope total|cumulative total/iu,
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/narrowed claim.*satisfied/iu),
    ).not.toBeInTheDocument();
  });
});
