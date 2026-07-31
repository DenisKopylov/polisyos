import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

import { normalizeWorkflow } from "@/shared/lib/domain/workflow";

describe("workflow domain", () => {
  it("source flips reject every C22d return vocabulary revival", () => {
    const repositoryRoot = resolve(process.cwd(), "../..");
    const script = String.raw`
import json
from pathlib import Path
from architecture.atlas_surfaces import check_status_retirement_inventory as checker

inventory = json.loads(Path("architecture/atlas_surfaces/status-retirement-inventory.json").read_text())
debt = json.loads(Path("architecture/atlas_surfaces/ds4-waist-debt-register.json").read_text())
paths = {
    "semantic-simulation-to-severity": [
        "apps/runtime-dashboard/src/shared/lib/domain/simulation.ts",
        "apps/runtime-dashboard/src/features/artifacts/components/simulation/MetricsPanel.tsx",
    ],
    "semantic-composer-resolve-launch-badge-kind": [
        "apps/runtime-dashboard/src/features/composer/domain/launchPresentation.ts",
        "apps/runtime-dashboard/src/features/composer/routes/ComposerModeSections.tsx",
    ],
    "semantic-launch-run-resolve-status-kind": [
        "apps/runtime-dashboard/src/features/composer/domain/launchPresentation.ts",
        "apps/runtime-dashboard/src/features/composer/routes/LaunchRunPage.tsx",
    ],
    "semantic-workflow-dag-status-kind": [
        "apps/runtime-dashboard/src/features/runs/components/WorkflowDagPanel.tsx",
    ],
}
rows = {}
for row in inventory["semantic_exemptions"]:
    candidate_id = row["candidate_id"]
    if candidate_id in paths:
        row["current_definition_state"] = "retired"
        row["protected_source_paths"] = paths[candidate_id]
        rows[candidate_id] = row

failures = []
live_errors = checker.validate_inventory(inventory, debt)
if live_errors:
    failures.append("live source: " + "; ".join(live_errors))

for candidate_id, row in rows.items():
    members = ", ".join(repr(member) for member in row["literal_members"])
    source = f"export const REVIVED = [{members}] as const;\n"
    errors = checker.validate_inventory(
        inventory,
        debt,
        source_overrides={row["source_span"]["path"]: source},
        live_probes=False,
    )
    expected = f"retired_semantic_definition_survives:{candidate_id}"
    if expected not in errors and not any(
        error.startswith("unregistered_semantic_definition:") for error in errors
    ):
        failures.append(candidate_id + ": source flip escaped")

fake_owner = "apps/runtime-dashboard/src/features/composer/domain/launchPresentation.ts"
fake_consumer = "apps/runtime-dashboard/src/features/composer/routes/LaunchRunPage.tsx"
lookalike_errors = checker.validate_inventory(
    inventory,
    debt,
    source_overrides={
        fake_owner: (
            "export interface RunLaunchResponse { status: 'accepted' | 'rejected' }\n"
            "export type BadgeTone = 'ok' | 'fail';\n"
            "export function launchStatusTone(status: RunLaunchResponse['status']): BadgeTone {\n"
            "  return status === 'accepted' ? 'ok' : 'fail';\n}\n"
        ),
        fake_consumer: (
            "import { launchStatusTone, type RunLaunchResponse } from '../domain/launchPresentation';\n"
            "import { Badge } from '@polisyos/atlas-ui';\n"
            "export const Probe = ({ status }: { status: RunLaunchResponse['status'] }) => "
            "<Badge kind={launchStatusTone(status)}>x</Badge>;\n"
        ),
    },
    live_probes=False,
)
if not any(error.startswith("retired_semantic_definition_survives:") for error in lookalike_errors):
    failures.append("local generated-looking launch owner escaped symbol-origin guard")

if failures:
    print("\n".join(failures))
    raise SystemExit(1)
`;
    const result = spawnSync("python3", ["-c", script], {
      cwd: repositoryRoot,
      encoding: "utf8",
      timeout: 60_000,
    });

    expect(`${result.stdout}${result.stderr}`).toBe("");
    expect(result.status).toBe(0);
  }, 65_000);

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
