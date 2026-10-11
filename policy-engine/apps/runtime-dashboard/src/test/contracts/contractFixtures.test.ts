import { loadAllRuntimeContractFixtures } from "./runtimeContractFixtures";

describe("runtime contract fixtures", () => {
  it("parse every recorded fixture with the frontend runtime schemas", () => {
    for (const fixture of loadAllRuntimeContractFixtures()) {
      expect(() => fixture.schema.parse(fixture.payload)).not.toThrow();
    }
  });

  it("retains the controlled Lex source-bound text-fallback fields", () => {
    const fixture = loadAllRuntimeContractFixtures().find(
      (item) => item.key === "lex-search",
    );
    expect(fixture).toBeDefined();
    const parsed = fixture!.schema.parse(fixture!.payload) as {
      query: string;
      results: unknown[];
      search_mode: "text" | "vector";
      total: number;
      vector_refusal_code: string | null;
    };
    expect(parsed.query).toBe("governance");
    expect(parsed.results).toEqual([]);
    expect(parsed.total).toBe(0);
    expect(parsed.search_mode).toBe("text");
    expect(parsed.vector_refusal_code).toBe("query_encoder_assets_unavailable");
  });

  it("retains selected manifest profiles in run evidence refs", () => {
    const fixture = loadAllRuntimeContractFixtures().find(
      (item) => item.key === "run-evidence-context",
    );
    expect(fixture).toBeDefined();
    const parsed = fixture!.schema.parse(fixture!.payload) as {
      context: {
        data_snapshot_ref?: { manifest_profile_sha256?: string | null } | null;
        data_view_request_ref?: {
          manifest_profile_sha256?: string | null;
        } | null;
      };
    };
    expect(parsed.context.data_snapshot_ref?.manifest_profile_sha256).toMatch(
      /^sha256:[0-9a-f]{64}$/,
    );
    expect(
      parsed.context.data_view_request_ref?.manifest_profile_sha256,
    ).toMatch(/^sha256:[0-9a-f]{64}$/);
  });
});
