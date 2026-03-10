import { normalizeWorkflow } from "@/lib/domain/workflow";

describe("workflow domain", () => {
  it("normalizes workflow payloads and derives summary defaults", () => {
    const model = normalizeWorkflow({
      edges: [
        { from_alias: "alpha_node", to_alias: "beta_node" },
        { from_alias: "", to_alias: "skip" },
      ],
      nodes: [
        {
          alias: "beta_node",
          artifact_ids: ["artifact-1", null],
          depends_on: ["alpha_node", null],
          depth: "2",
          duration_ms: "200",
          error_code: "E_NODE",
          error_message: "Node failed",
          heat: "0.3",
          input_artifact_ids: ["input-1", false],
          node_id: 42,
          output_artifact_ids: ["output-1"],
          status: "skip",
        },
        {
          alias: "alpha_node",
          artifact_ids: [],
          depends_on: [""],
          depth: -1,
          duration_ms: -10,
          heat: -1,
          input_artifact_ids: [null, "input-a"],
          output_artifact_ids: ["output-a", 2],
          status: "PASS",
        },
        null,
      ],
      notes: ["first", null, 2],
      run_id: "run-42",
      summary: {
        critical_path_duration_ms: "200",
        edge_count: "4",
        error_policy: "halt",
        fail_count: "2",
        max_depth: "3",
        node_count: "9",
        ok_count: 1,
        skip_count: 1,
        status: "running",
        workflow_id: 123,
      },
    });

    expect(model.runId).toBe("run-42");
    expect(model.nodes).toEqual([
      expect.objectContaining({
        alias: "alpha_node",
        artifactIds: [],
        depth: 0,
        durationMs: 0,
        heat: 0,
        label: "Alpha Node",
        outputArtifactIds: ["output-a", "2"],
        status: "unknown",
      }),
      expect.objectContaining({
        alias: "beta_node",
        artifactIds: ["artifact-1"],
        dependsOn: ["alpha_node"],
        depth: 2,
        durationMs: 200,
        errorCode: "E_NODE",
        errorMessage: "Node failed",
        heat: 1,
        inputArtifactIds: ["input-1"],
        nodeId: "42",
        outputArtifactIds: ["output-1"],
        status: "skip",
      }),
    ]);
    expect(model.edges).toEqual([
      { fromAlias: "alpha_node", toAlias: "beta_node" },
    ]);
    expect(model.notes).toEqual(["first", "2"]);
    expect(model.summary).toEqual({
      criticalPathDurationMs: 200,
      edgeCount: 4,
      errorPolicy: "halt",
      failCount: 2,
      maxDepth: 3,
      nodeCount: 9,
      okCount: 1,
      skipCount: 1,
      status: "running",
      workflowId: "123",
    });
  });

  it("returns a safe empty model for invalid payloads", () => {
    expect(normalizeWorkflow(null)).toEqual({
      edges: [],
      nodes: [],
      notes: [],
      runId: "unknown",
      summary: {
        criticalPathDurationMs: null,
        edgeCount: 0,
        errorPolicy: null,
        failCount: 0,
        maxDepth: 0,
        nodeCount: 0,
        okCount: 0,
        skipCount: 0,
        status: null,
        workflowId: null,
      },
    });
  });
});
