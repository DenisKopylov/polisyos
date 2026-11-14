import { fireEvent, screen, waitFor, within } from "@testing-library/react";

import actualModelInputUseCurrentC from "@/api/__fixtures__/model-input-use-current-c.json";
import actualModelInputUseRetainedB from "@/api/__fixtures__/model-input-use-retained-b.json";
import { useRunModelInputUseN5Result } from "@/api/hooks/useRunModelInputUseN5Result";
import {
  runModelInputUseN5SuccessorResponseSchema,
  type RunModelInputUseActionsProjection,
} from "@/api/validators";
import { renderWithProviders } from "@/test/render";
import { ModelInputUseN5ResultHistory } from "./ModelInputUseN5ResultHistory";

const apiState = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock("@/api/client", () => ({
  runtimeApiClient: {
    GET: (...args: unknown[]) => apiState.get(...args),
  },
}));

function actionInventory(count = 128): RunModelInputUseActionsProjection {
  return {
    run_id: "control-run-owner-id",
    source_job_id: "source-job-owner-id",
    scope: "discovery_only",
    actions: Array.from({ length: count }, (_, index) => ({
      action_job_id: `action-job-${String(index).padStart(3, "0")}`,
      job_state: "completed" as const,
    })),
    inventory_status: "complete",
    inventory_truncated: false,
    limitation_codes: [],
  };
}

function ForeignActionQueryProbe() {
  const query = useRunModelInputUseN5Result(
    actionInventory(1),
    "foreign-action-job",
  );
  return <p>{query.isFetching ? "fetching" : "idle"}</p>;
}

function actualV2Projection(value: unknown) {
  const projection =
    runModelInputUseN5SuccessorResponseSchema.parse(value).result;
  if (
    projection.schema_version !==
    "policyos.runtime.run_model_input_use_n5_successor_projection.v2"
  ) {
    throw new Error("Expected a captured V2 model-input use projection");
  }
  return projection;
}

function capturedActionInventory() {
  const currentResponse = runModelInputUseN5SuccessorResponseSchema.parse(
    actualModelInputUseCurrentC,
  );
  const retainedResponse = runModelInputUseN5SuccessorResponseSchema.parse(
    actualModelInputUseRetainedB,
  );
  const current = actualV2Projection(actualModelInputUseCurrentC);
  const retained = actualV2Projection(actualModelInputUseRetainedB);
  const responsesByActionId = new Map([
    [current.action_job_id, currentResponse],
    [retained.action_job_id, retainedResponse],
  ]);
  const actions = [current, retained]
    .map((result) => ({
      action_job_id: result.action_job_id,
      job_state:
        result.action_status === "not_established"
          ? ("completed" as const)
          : result.action_status,
    }))
    .sort((left, right) =>
      left.action_job_id < right.action_job_id
        ? -1
        : left.action_job_id > right.action_job_id
          ? 1
          : 0,
    );

  return {
    current,
    retained,
    responsesByActionId,
    inventory: {
      run_id: current.run_id,
      source_job_id: "source-job-from-run-details",
      scope: "discovery_only" as const,
      actions,
      inventory_status: "complete" as const,
      inventory_truncated: false,
      limitation_codes: [],
    } satisfies RunModelInputUseActionsProjection,
  };
}

function buttonForAction(actionJobId: string) {
  const button = screen
    .getAllByTestId("model-input-use-action-selector")
    .find((item) => item.getAttribute("data-action-job-id") === actionJobId);
  if (!button) {
    throw new Error(`Missing discovered action selector ${actionJobId}`);
  }
  return button;
}

describe("ModelInputUseN5ResultHistory", () => {
  beforeEach(() => {
    apiState.get.mockReset();
    apiState.get.mockImplementation(async () => ({
      data: undefined,
      error: {},
      response: new Response(null, { status: 403 }),
    }));
  });

  it("makes no detail requests for a 128-row inventory until one row is opened", async () => {
    renderWithProviders(
      <ModelInputUseN5ResultHistory inventory={actionInventory()} />,
    );

    expect(
      screen.getAllByTestId("model-input-use-action-selector"),
    ).toHaveLength(128);
    expect(apiState.get).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /action-job-000/i }));
    await waitFor(() => expect(apiState.get).toHaveBeenCalledTimes(1));
    expect(apiState.get.mock.calls[0]?.[0]).toBe(
      "/api/v1/runs/{run_id}/model-input-use/{job_id}/n5-result",
    );
    expect(apiState.get.mock.calls[0]?.[1]).toMatchObject({
      params: {
        path: {
          run_id: "control-run-owner-id",
          job_id: "action-job-000",
        },
      },
    });
    expect(
      await screen.findByTestId("model-input-use-result-unavailable"),
    ).toBeInTheDocument();
  });

  it("does not query a job ID outside the discovered action list", () => {
    renderWithProviders(<ForeignActionQueryProbe />);

    expect(screen.getByText("idle")).toBeInTheDocument();
    expect(apiState.get).not.toHaveBeenCalled();
  });

  it("renders actual selected C and superseded retained B projections from per-action GETs", async () => {
    const { current, retained, responsesByActionId, inventory } =
      capturedActionInventory();
    apiState.get.mockImplementation(async (...args: unknown[]) => {
      const options = args[1] as {
        params: { path: { job_id: string } };
      };
      const data = responsesByActionId.get(options.params.path.job_id);
      return data
        ? {
            data,
            error: undefined,
            response: new Response(null, { status: 200 }),
          }
        : {
            data: undefined,
            error: {},
            response: new Response(null, { status: 404 }),
          };
    });

    renderWithProviders(<ModelInputUseN5ResultHistory inventory={inventory} />);
    expect(apiState.get).not.toHaveBeenCalled();

    fireEvent.click(buttonForAction(current.action_job_id));
    const currentRow = await screen.findByTestId("model-input-use-result-row");
    expect(currentRow).toHaveAttribute("data-frontier-selection", "selected");
    expect(
      within(currentRow).getByTestId("model-input-use-frontier-selection"),
    ).toHaveTextContent("selection: selected");
    expect(
      within(currentRow).getByTestId("model-input-use-evaluation-provenance"),
    ).toHaveTextContent("new_execution");
    expect(
      within(currentRow).getByTestId("model-input-use-currentness"),
    ).toHaveTextContent("not established");
    expect(
      within(currentRow).getByTestId("model-input-use-scope"),
    ).toHaveTextContent("Candidate-only N5 evidence");
    expect(
      within(currentRow).getByTestId("model-input-use-units-not-supplied"),
    ).toHaveTextContent("Output units are not supplied by this result.");
    expect(
      within(currentRow).getByTestId("model-input-use-limitations"),
    ).toHaveTextContent("source_currentness_not_established");
    expect(apiState.get).toHaveBeenCalledTimes(1);
    expect(apiState.get.mock.calls[0]?.[1]).toMatchObject({
      params: {
        path: { run_id: current.run_id, job_id: current.action_job_id },
      },
    });

    const currentRefs = within(currentRow).getByTestId(
      "model-input-use-references",
    );
    expect(currentRefs).toHaveTextContent(
      current.current_basis_ref?.artifact_id ?? "missing-current-basis",
    );
    expect(currentRefs).toHaveTextContent(
      current.current_use_decision_ref?.artifact_id ?? "missing-current-use",
    );
    expect(currentRefs).toHaveTextContent(
      current.original_result_ref?.artifact_id ?? "missing-original-result",
    );
    fireEvent.click(
      within(currentRow).getByText("Saved N5 result body (candidate-only)"),
    );
    const currentBody = await within(currentRow).findByTestId(
      "model-input-use-result-body",
    );
    expect(currentBody).toHaveTextContent("government.balance");
    expect(currentBody).toHaveTextContent("602.5");
    expect(currentBody).toHaveTextContent("565");
    expect(currentBody).not.toHaveTextContent(/\bUSD\b/);

    fireEvent.click(buttonForAction(retained.action_job_id));
    await waitFor(() => {
      expect(screen.getByTestId("model-input-use-result-row")).toHaveAttribute(
        "data-frontier-selection",
        "superseded",
      );
    });
    const retainedRow = screen.getByTestId("model-input-use-result-row");
    expect(
      within(retainedRow).getByTestId("model-input-use-evaluation-provenance"),
    ).toHaveTextContent("retained_prior");
    expect(
      within(retainedRow).getByTestId("model-input-use-frontier-selection"),
    ).toHaveTextContent("selection: superseded");
    const retainedRefs = within(retainedRow).getByTestId(
      "model-input-use-references",
    );
    expect(retained.original_action_job_id).not.toBe(retained.action_job_id);
    expect(retainedRefs).toHaveTextContent(
      retained.original_action_job_id ?? "missing-original-action",
    );
    expect(retainedRefs).toHaveTextContent(
      retained.original_result_ref?.artifact_id ?? "missing-original-result",
    );
    expect(retainedRefs).toHaveTextContent(
      retained.current_basis_ref?.artifact_id ?? "missing-current-basis",
    );
    expect(retainedRefs).toHaveTextContent(
      retained.current_use_decision_ref?.artifact_id ?? "missing-current-use",
    );
    fireEvent.click(
      within(retainedRow).getByText("Saved N5 result body (candidate-only)"),
    );
    const retainedBody = await within(retainedRow).findByTestId(
      "model-input-use-result-body",
    );
    expect(retainedBody).toHaveTextContent("government.balance");
    expect(retainedBody).toHaveTextContent("640");
    expect(retainedBody).toHaveTextContent("602.5");
    expect(retainedBody).not.toHaveTextContent(/\bUSD\b/);
    expect(apiState.get).toHaveBeenCalledTimes(2);
  });

  it("aborts the prior request when the opened action changes", async () => {
    const signals: AbortSignal[] = [];
    apiState.get.mockImplementation(
      (_path: string, options: { signal: AbortSignal }) => {
        signals.push(options.signal);
        return new Promise((_resolve, reject) => {
          options.signal.addEventListener(
            "abort",
            () => reject(new DOMException("Request aborted", "AbortError")),
            { once: true },
          );
        });
      },
    );

    renderWithProviders(
      <ModelInputUseN5ResultHistory inventory={actionInventory(2)} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /action-job-000/i }));
    await waitFor(() => expect(apiState.get).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: /action-job-001/i }));

    await waitFor(() => expect(apiState.get).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(signals[0]?.aborted).toBe(true));
  });

  it("shows bounded inventory limits without inventing an action result", () => {
    renderWithProviders(
      <ModelInputUseN5ResultHistory
        inventory={{
          run_id: "control-run-owner-id",
          source_job_id: "source-job-owner-id",
          scope: "discovery_only",
          actions: [],
          inventory_status: "limited",
          inventory_truncated: true,
          limitation_codes: ["action_inventory_truncated"],
        }}
      />,
    );

    expect(
      screen.getByTestId("model-input-use-inventory-limited"),
    ).toHaveTextContent("action_inventory_truncated");
    expect(
      screen.getByTestId("model-input-use-history-empty"),
    ).toHaveTextContent(
      "No action result is available from this limited discovery.",
    );
    expect(screen.queryByTestId("model-input-use-result-row")).toBeNull();
    expect(
      screen.getByText(/does not establish which result is selected/i),
    ).toBeInTheDocument();
    expect(apiState.get).not.toHaveBeenCalled();
  });
});
