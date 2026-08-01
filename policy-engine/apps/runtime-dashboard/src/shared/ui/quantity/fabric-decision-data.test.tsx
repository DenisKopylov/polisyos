import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderWithProviders } from "@/test/render";
import {
  fabricDecisionDataPayloadToQuantities,
  fabricDecisionDataToQuantityValue,
} from "./fabric-decision-data";
import { Quantity } from "./Quantity";
import type {
  FabricDecisionData,
  FabricDecisionDataResponse,
} from "./quantity.types";

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
} satisfies FabricDecisionDataResponse;

describe("Fabric decision data quantity adapter", () => {
  it("preserves Fabric lineage without fabricating absent trust metadata", () => {
    const [quantity] = fabricDecisionDataPayloadToQuantities(payload);

    expect(quantity?.point).toBe(100);
    expect(quantity?.unit.display).toBe("USD");
    expect(quantity?.lineage.status).toBe("verified");
    expect(quantity?.lineage.summary?.source_contract).toBe(
      "worldbank.wdi.generic@1.1.0",
    );
    expect(quantity?.lineage.trust_metadata).toBeUndefined();
  });

  it("renders owner-provided provenance from Fabric-backed payloads", async () => {
    const user = userEvent.setup();
    window.history.replaceState(
      null,
      "",
      "/runs/R_core_api_001?trust=expanded",
    );
    const quantity = fabricDecisionDataToQuantityValue(
      payload.decision_data![0],
    );

    renderWithProviders(
      <>
        <Quantity value={quantity!} provenanceMode="always" />
      </>,
    );

    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("USD")).toBeInTheDocument();
    await user.click(screen.getByTestId("quantity"));
    expect(screen.getByText(/sha256:abc/)).toBeInTheDocument();
    expect(screen.queryByTestId("trust-verification-status")).toBeNull();
  });

  it("does not convert non-quantity Fabric rows into naked decision values", () => {
    expect(
      fabricDecisionDataToQuantityValue({
        ...payload.decision_data![0],
        kind: "authored_text",
      }),
    ).toBeNull();
  });

  it("does not promote opaque metadata or gap labels into freshness authority", () => {
    const quantity = fabricDecisionDataToQuantityValue({
      ...payload.decision_data![0],
      gaps: [{ reason_code: "stale_evidence", status: "unknown_quality" }],
      metadata: { freshness: "current" },
    });

    expect(quantity?.lineage.freshness).toBe("unknown");
  });

  it("does not let opaque metadata hide a decision value as layout", () => {
    const quantity = fabricDecisionDataToQuantityValue({
      ...payload.decision_data![0],
      metadata: { quantity_class: "layout" },
    });

    expect(quantity?.quantity_class).toBe("decision");
  });

  it("does not promote an opaque Fabric uncertainty extension into authority semantics", () => {
    const row = {
      ...payload.decision_data![0],
      value: {
        ...payload.decision_data![0].value,
        uncertainty: {
          ci_95: [0, 1],
          disputed: true,
          identifiability: "identified",
          method: "opaque-extension",
        },
      },
    } as unknown as FabricDecisionData;

    const quantity = fabricDecisionDataToQuantityValue(row);

    expect(quantity?.uncertainty).toBeNull();
  });
});
