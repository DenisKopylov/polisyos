import {
  createSurfaceVisualFixture,
  createVisualFixtureHarness,
} from "./visualFixtureHarness";

describe("visual fixture harness", () => {
  it("creates deterministic large graph and timeline fixtures", () => {
    const first = createVisualFixtureHarness({
      edgeCount: 16,
      eventCount: 12,
      nodeCount: 10,
      seed: 44,
    });
    const second = createVisualFixtureHarness({
      edgeCount: 16,
      eventCount: 12,
      nodeCount: 10,
      seed: 44,
    });

    expect(first).toEqual(second);
    expect(first.graph.nodes).toHaveLength(10);
    expect(first.graph.edges).toHaveLength(16);
    expect(first.timeline.events).toHaveLength(12);
  });

  it("keeps graph coordinates inside the normalized viewport", () => {
    const fixture = createVisualFixtureHarness({ nodeCount: 100, seed: 7 });

    for (const node of fixture.graph.nodes) {
      expect(node.x).toBeGreaterThanOrEqual(0);
      expect(node.x).toBeLessThanOrEqual(1);
      expect(node.y).toBeGreaterThanOrEqual(0);
      expect(node.y).toBeLessThanOrEqual(1);
    }
  });

  it("creates fixtures from registered surface visualization metadata", () => {
    expect(
      createSurfaceVisualFixture("runs.causalAtlas", {
        edgeCount: 12,
        nodeCount: 8,
      }),
    ).toMatchObject({
      graph: { edges: expect.arrayContaining([expect.any(Object)]) },
      kind: "large-graph",
      surfaceId: "runs.causalAtlas",
    });
    expect(createSurfaceVisualFixture("runs.artifacts")).toBeNull();
  });
});
