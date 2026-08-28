import { describe, expect, it } from "vitest";

import {
  EPOCH_PERTURBATION_CLASSES,
  epochProjection,
  epochStalenessPositiveFixture,
  epochStalenessSixClassFixture,
  withServerSemanticHash,
} from "@/test/fixtures/epochStaleness";

import {
  admitEpochStalenessResponse,
  computeEpochStalenessSemanticHash,
} from "./epochStaleness";

describe("epoch staleness semantic admission", () => {
  it("preserves all six perturbation classes as distinct admitted values", async () => {
    const candidate = epochStalenessSixClassFixture();

    const admitted = await admitEpochStalenessResponse(candidate);

    expect(
      admitted.projection.perturbations.map((row) => row.source_class),
    ).toEqual(EPOCH_PERTURBATION_CLASSES);
    expect(admitted.projection.perturbations[1]?.scope).toBe("instance");
    expect(await computeEpochStalenessSemanticHash(admitted.projection)).toBe(
      admitted.projection.projection_semantic_hash,
    );
  });

  it("admits the owner-derived positive fixture without weakening absence admission", async () => {
    const admitted = await admitEpochStalenessResponse(
      epochStalenessPositiveFixture(),
    );

    expect(admitted.projection.status).toBe("current");
    expect(admitted.projection.fixture_only).toBe(true);
    expect(admitted.projection.institutional_absences).toEqual([]);
  });

  it("rejects an unknown nested field even when the semantic hash is recomputed", async () => {
    const candidate = epochStalenessSixClassFixture();
    const denominator = epochProjection(candidate).denominator as Record<
      string,
      unknown
    >;
    denominator.shape_marker = "still looks like a denominator";

    await expect(
      admitEpochStalenessResponse(withServerSemanticHash(candidate)),
    ).rejects.toThrow(/contract_error/);
  });

  it("rejects a generic changed class and a class-wide appeal", async () => {
    const generic = epochStalenessSixClassFixture();
    const genericRows = epochProjection(generic).perturbations as Array<
      Record<string, unknown>
    >;
    genericRows[0]!.source_class = "changed";
    await expect(
      admitEpochStalenessResponse(withServerSemanticHash(generic)),
    ).rejects.toThrow(/contract_error/);

    const appeal = epochStalenessSixClassFixture();
    const appealRows = epochProjection(appeal).perturbations as Array<
      Record<string, unknown>
    >;
    appealRows[1]!.scope = "dependency_descendants";
    await expect(
      admitEpochStalenessResponse(withServerSemanticHash(appeal)),
    ).rejects.toThrow(/contract_error/);
  });

  it("rejects denominator mutation when every shape marker remains", async () => {
    const candidate = epochStalenessSixClassFixture();
    const denominator = epochProjection(candidate).denominator as Record<
      string,
      unknown
    >;
    denominator.source_count = 9;

    await expect(admitEpochStalenessResponse(candidate)).rejects.toThrow(
      /semantic hash/i,
    );
  });

  it("derives the OpenWorldRisk freeze instead of trusting its boolean", async () => {
    const candidate = epochStalenessSixClassFixture();
    const risk = epochProjection(candidate).open_world_risk as Record<
      string,
      unknown
    >;
    risk.promotion_frozen = false;

    await expect(
      admitEpochStalenessResponse(withServerSemanticHash(candidate)),
    ).rejects.toThrow(/OpenWorldRisk/);
  });
});
