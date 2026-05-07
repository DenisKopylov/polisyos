import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const { useI18nMock } = vi.hoisted(() => ({
  useI18nMock: vi.fn(),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => useI18nMock(),
}));

import NodeDebugPanel from "@/features/runs/components/debug/NodeDebugPanel";

describe("NodeDebugPanel", () => {
  beforeEach(() => {
    useI18nMock.mockReset();
    useI18nMock.mockReturnValue({
      t: (key: string, payload?: Record<string, unknown>) =>
        payload ? `${key}:${JSON.stringify(payload)}` : key,
    });
  });

  it("renders the unavailable state without debug data", () => {
    render(
      <MemoryRouter>
        <NodeDebugPanel
          debugData={null}
          nodes={[{ alias: "planner", duration_ms: 10, status: "ok" }]}
          onSelectAlias={vi.fn()}
          selectedAlias={null}
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByText("panels.nodeDebug.unavailable"),
    ).toBeInTheDocument();
  });

  it("renders node details, timeline metrics, and artifact links", async () => {
    const user = userEvent.setup();
    const onSelectAlias = vi.fn();

    render(
      <MemoryRouter>
        <NodeDebugPanel
          debugData={{
            alias: "planner",
            cache_bypasses: 1,
            cache_hits: 4,
            cache_stores: 2,
            record: {
              alias: "planner",
              duration_ms: 2_300,
              error_code: "E_TIMEOUT",
              error_details: { reason: "timeout" },
              error_message: "Planner exceeded latency budget.",
              input_artifact_ids: ["artifact-input"],
              node_id: "node-1",
              output_artifact_ids: ["artifact-output"],
              status: "ok",
            },
            run_id: "run-1",
            source_kind: "core_run",
            timeline_events: [
              {
                event: "running",
                index: 1,
                metrics: { cacheHit: 3 },
                phase: "planner",
                timestamp: "2026-03-10T10:00:00Z",
              },
              {
                event: "failed",
                index: 2,
                metrics: {},
                phase: "planner",
                timestamp: "2026-03-10T10:00:30Z",
              },
              {
                event: "queued",
                index: 3,
                metrics: {},
                phase: "planner",
                timestamp: "2026-03-10T10:00:45Z",
              },
            ],
          }}
          nodes={[
            { alias: "planner", duration_ms: 10, status: "ok" },
            { alias: "judge", duration_ms: 12, status: "fail" },
          ]}
          onSelectAlias={onSelectAlias}
          selectedAlias="planner"
        />
      </MemoryRouter>,
    );

    await user.selectOptions(
      screen.getByLabelText("panels.nodeDebug.alias"),
      "judge",
    );

    expect(onSelectAlias).toHaveBeenCalledWith("judge");
    expect(screen.getByText("node-1")).toBeInTheDocument();
    expect(screen.getByText("E_TIMEOUT")).toBeInTheDocument();
    expect(
      screen.getByText("Planner exceeded latency budget."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "artifact-input" }),
    ).toHaveAttribute("href", "/artifacts/artifact-input");
    expect(
      screen.getByRole("link", { name: "artifact-output" }),
    ).toHaveAttribute("href", "/artifacts/artifact-output");
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText("queued")).toBeInTheDocument();
    expect(screen.getByText(/"cacheHit": 3/)).toBeInTheDocument();
    expect(screen.getByText(/"reason": "timeout"/)).toBeInTheDocument();
  });
});
