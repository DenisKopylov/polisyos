import {
  evidenceFabricItemToProvenance,
  provenanceFromFabricItems,
} from "./provenance-adapter";

describe("provenance adapter", () => {
  it("emits freshness from fresh_at", () => {
    const items = evidenceFabricItemToProvenance({
      fresh_at: new Date().toISOString(),
    });
    expect(items.find((i) => i.id === "freshness")).toMatchObject({
      glyph: "freshness",
      intent: "verified",
    });
  });

  it("maps stale fresh_at to blocked", () => {
    const stale = new Date(Date.now() - 60 * 60_000).toISOString();
    const items = evidenceFabricItemToProvenance({ fresh_at: stale });
    expect(items.find((i) => i.id === "freshness")).toMatchObject({
      intent: "blocked",
    });
  });

  it("emits blocker when governance_pass=false", () => {
    const items = evidenceFabricItemToProvenance({ governance_pass: false });
    expect(items.find((i) => i.id === "governance")).toMatchObject({
      glyph: "blocker",
      intent: "blocked",
    });
  });

  it("emits governance-pass when governance_pass=true", () => {
    const items = evidenceFabricItemToProvenance({ governance_pass: true });
    expect(items.find((i) => i.id === "governance")).toMatchObject({
      glyph: "governance-pass",
      intent: "verified",
    });
  });

  it("resolves intervention from intervention_type", () => {
    const items = evidenceFabricItemToProvenance({
      intervention_type: "policy-action",
    });
    expect(items.find((i) => i.id === "intervention")).toMatchObject({
      glyph: "intervention",
    });
  });

  it("emits evidence with dashed stroke for weak strength", () => {
    const items = evidenceFabricItemToProvenance({
      evidence_strength: "weak",
    });
    expect(items.find((i) => i.id === "evidence")).toMatchObject({
      glyph: "evidence",
      strokeStyle: "dashed",
      intent: "pending",
    });
  });

  it("dedupes ids across a collection of fabric items", () => {
    const collection = provenanceFromFabricItems([
      { governance_pass: true },
      { governance_pass: false },
    ]);
    const governanceEntries = collection.filter((i) => i.id === "governance");
    expect(governanceEntries).toHaveLength(1);
  });

  it("respects maxItems option", () => {
    const items = evidenceFabricItemToProvenance(
      {
        fresh_at: new Date().toISOString(),
        governance_pass: true,
        intervention_type: "policy-action",
        evidence_strength: "strong",
      },
      { maxItems: 2 },
    );
    expect(items).toHaveLength(2);
  });
});
