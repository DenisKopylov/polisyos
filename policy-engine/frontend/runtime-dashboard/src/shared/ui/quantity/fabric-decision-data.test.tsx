import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TrustViewProvider } from "@/app/providers/TrustViewProvider";
import { runFabricDecisionDataSchema } from "@/api/validators";
import { renderWithProviders } from "@/test/render";
import { TrustInspector } from "@/shared/ui/trust-view";

import {
  fabricDecisionDataPayloadToQuantities,
  fabricDecisionDataToQuantityValue,
} from "./fabric-decision-data";
import { Quantity } from "./Quantity";

const payload = {
  meta: {
    generated_at: "2026-02-11T12:00:00Z",
    request_id: "req_fixture",
    source_kinds: ["core_run"],
  },
  run_id: "R_core_api_001",
  source_kind: "core_run",
  temporal_scope: {
    valid_at: "2026-02-11T12:00:00Z",
    tx_at: "2026-02-11T12:01:00Z",
    branch: "main",
    snapshot_id: null,
    scenario_id: null,
  },
  decision_data: [
    {
      id: "fabric_decision_data:policy_cost",
      kind: "quantity",
      value: {
        label: "Policy cost",
        metric_id: "policy_cost",
        point: 100,
        semantic_type: "policy_cost",
        unit: { code: "[USD]", display: "USD", system: "ucum" },
      },
      source_contract: { id: "worldbank.wdi.generic", version: "1.1.0" },
      quality: {
        status: "passed",
        score: 1,
        report_ref: "runtime://quantity-quality/policy_cost",
      },
      lineage: {
        id: "artifact:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        status: "verified",
        hash: "sha256:abc",
        compact_summary_ref:
          "/api/v1/lineage/artifact:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        full_graph_ref:
          "/api/v1/lineage/artifact:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa?view=full",
        raw_evidence_refs: [
          "cas://sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        ],
        export_links: {
          openlineage:
            "/api/v1/lineage/artifact:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/export/openlineage",
          prov: "/api/v1/lineage/artifact:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/export/prov",
        },
      },
      access: {
        classification: "public",
        pii_tier: "none",
        tenant_scope: "shared_public",
        redaction: "none",
      },
      time: {
        valid_at: "2026-02-11T12:00:00Z",
        tx_at: "2026-02-11T12:01:00Z",
        branch: "main",
        snapshot_id: null,
        scenario_id: null,
      },
      replay: {
        status: "replayable",
        manifest_ref:
          "cas://sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      },
      gaps: [],
      metadata: {
        quantity_class: "decision",
        runtime_metric_id: "policy_cost",
      },
    },
  ],
};

describe("Fabric decision data quantity adapter", () => {
  it("maps Fabric trust envelopes into renderable QuantityValue objects", () => {
    const parsedPayload = runFabricDecisionDataSchema.parse(payload);
    const [quantity] = fabricDecisionDataPayloadToQuantities(parsedPayload);

    expect(quantity?.point).toBe(100);
    expect(quantity?.unit.display).toBe("USD");
    expect(quantity?.lineage.status).toBe("verified");
    expect(quantity?.lineage.summary?.source_contract).toBe(
      "worldbank.wdi.generic@1.1.0",
    );
    expect(quantity?.lineage.trust_metadata?.verification_method).toBe(
      "fabric_trust_envelope",
    );
  });

  it("renders provenance and Trust View from Fabric-backed payloads", async () => {
    const user = userEvent.setup();
    window.history.replaceState(
      null,
      "",
      "/runs/R_core_api_001?trust=expanded",
    );
    const parsedPayload = runFabricDecisionDataSchema.parse(payload);
    const quantity = fabricDecisionDataToQuantityValue(
      parsedPayload.decision_data![0],
    );

    renderWithProviders(
      <TrustViewProvider>
        <>
          <Quantity value={quantity!} provenanceMode="always" />
          <TrustInspector />
        </>
      </TrustViewProvider>,
    );

    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("USD")).toBeInTheDocument();
    expect(screen.getByText(/sha256:abc/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "verified" }));
    expect(
      screen.getByRole("dialog", { name: "Trust inspector" }),
    ).toHaveTextContent("fabric_trust_envelope");
  });

  it("does not convert non-quantity Fabric rows into naked decision values", () => {
    const parsedPayload = runFabricDecisionDataSchema.parse(payload);
    expect(
      fabricDecisionDataToQuantityValue({
        ...parsedPayload.decision_data![0],
        kind: "authored_text",
      }),
    ).toBeNull();
  });
});
