import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { useComposerDraftStore } from "@/features/composer/state/useComposerDraftStore";
import { renderRouteWithProviders } from "@/test/routes";

const {
  composerLabelMock,
  composerTMock,
  deleteComposerDraftMock,
  loadComposerDraftMock,
  saveComposerDraftMock,
  useCapabilitiesMock,
  useLaunchNlRunMock,
  useLaunchRunMock,
  useLlmProfilesMock,
} = vi.hoisted(() => ({
  composerLabelMock: vi.fn(
    (_namespace: string, value: string | null | undefined, fallback: string) =>
      fallback ?? value ?? "",
  ),
  composerTMock: vi.fn((key: string, payload?: Record<string, unknown>) =>
    payload ? `${key}:${JSON.stringify(payload)}` : key,
  ),
  deleteComposerDraftMock: vi.fn(),
  loadComposerDraftMock: vi.fn(),
  saveComposerDraftMock: vi.fn(),
  useCapabilitiesMock: vi.fn(),
  useLaunchNlRunMock: vi.fn(),
  useLaunchRunMock: vi.fn(),
  useLlmProfilesMock: vi.fn(),
}));

vi.mock("@/api/hooks/useCapabilities", () => ({
  useCapabilities: (...args: unknown[]) => useCapabilitiesMock(...args),
}));

vi.mock("@/api/hooks/useLlmProfiles", () => ({
  useLlmProfiles: (...args: unknown[]) => useLlmProfilesMock(...args),
}));

vi.mock("@/api/hooks/useLaunchRun", () => ({
  useLaunchRun: (...args: unknown[]) => useLaunchRunMock(...args),
}));

vi.mock("@/api/hooks/useLaunchNlRun", () => ({
  useLaunchNlRun: (...args: unknown[]) => useLaunchNlRunMock(...args),
}));

vi.mock("@/features/composer/state/composerDraftRepository", () => ({
  buildComposerDraftKey: (mode: string, fromRunId: string | null) =>
    `${mode}:${fromRunId ?? "new"}`,
  deleteComposerDraft: (...args: unknown[]) => deleteComposerDraftMock(...args),
  loadComposerDraft: (...args: unknown[]) => loadComposerDraftMock(...args),
  saveComposerDraft: (...args: unknown[]) => saveComposerDraftMock(...args),
}));

vi.mock("@/i18n/LocaleProvider", async () => {
  const actual = await vi.importActual<typeof import("@/i18n/LocaleProvider")>(
    "@/i18n/LocaleProvider",
  );
  return {
    ...actual,
    useI18n: () => ({
      label: composerLabelMock,
      locale: "en",
      t: composerTMock,
    }),
  };
});

import LaunchRunPage from "@/features/composer/routes/LaunchRunPage";

function renderLaunchRunPage(initialEntry = "/compose") {
  return renderRouteWithProviders({
    element: <LaunchRunPage />,
    path: "/compose",
    initialEntry,
    extraRoutes: [
      {
        path: "/runs/:runId/overview",
        element: <div>Run detail page</div>,
      },
    ],
  });
}

describe("LaunchRunPage", () => {
  beforeEach(() => {
    composerLabelMock.mockClear();
    composerTMock.mockClear();
    useComposerDraftStore.getState().reset();
    deleteComposerDraftMock.mockReset();
    loadComposerDraftMock.mockReset();
    loadComposerDraftMock.mockResolvedValue(null);
    saveComposerDraftMock.mockReset();
    saveComposerDraftMock.mockResolvedValue(undefined);
    useCapabilitiesMock.mockReset();
    useCapabilitiesMock.mockReturnValue({
      data: {
        constraints: {
          max_nl_iterations: 4,
          max_parallel_models: 3,
        },
        features: [
          {
            description: "Multi-model natural language runs",
            enabled: true,
            key: "multimodel_nl",
            label: "Multi-model",
          },
          {
            description: "Required preflight checks",
            enabled: true,
            key: "required_preflight",
            label: "Preflight",
          },
          {
            description: "Automatic materialization",
            enabled: true,
            key: "auto_materialization",
            label: "Auto materialization",
          },
          {
            description: "Promotion lane",
            enabled: true,
            key: "promotion_lane",
            label: "Promotion lane",
          },
        ],
      },
    });
    useLlmProfilesMock.mockReset();
    useLlmProfilesMock.mockReturnValue({
      data: {
        profiles: [
          {
            description: "Primary reasoning model",
            display_name: "GPT-5.4",
            input_cost_per_mtoken_usd: 0.4,
            model_id: "openai/gpt-5.4",
            output_cost_per_mtoken_usd: 1.2,
            profile_id: "profile-1",
            provider: "OpenAI",
          },
        ],
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useLaunchRunMock.mockReset();
    useLaunchRunMock.mockReturnValue({
      error: null,
      isPending: false,
      mutate: vi.fn(),
    });
    useLaunchNlRunMock.mockReset();
    useLaunchNlRunMock.mockReturnValue({
      error: null,
      isPending: false,
      mutate: vi.fn(),
    });
  });

  it("hydrates and discards a saved workflow draft for replans", async () => {
    loadComposerDraftMock.mockImplementation(async (key: string) => {
      if (key === "workflow:run-42") {
        return {
          fromRunId: "run-42",
          key,
          mode: "workflow",
          updatedAt: Date.now(),
          values: {
            checkpointPolicy: "strict",
            customParams: [],
            dataSourceRef: "sha256:draft-snapshot",
            dataSourceType: "snapshot",
            executionIntent: "Saved operator intent",
            expectedOutputs: [
              { description: "Decision packet", kind: "decision_packet" },
            ],
            governanceConstraints: [
              {
                rule: "Block illegal outcomes",
                scope: "legal",
                severity: "blocker",
              },
            ],
            modelSpecRef: "",
            policySpecRef: "",
            trinityRef: "",
          },
        };
      }
      return null;
    });

    const user = userEvent.setup();
    renderLaunchRunPage("/compose?fromRun=run-42");

    expect(await screen.findByDisplayValue("Saved operator intent")).toBeInTheDocument();
    expect(screen.getByText("pages.composer.restoredDraftTitle")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "pages.composer.discardDraft" }),
    );

    expect(deleteComposerDraftMock).toHaveBeenCalledWith("workflow:run-42");
  });

  it(
    "persists NL drafts, builds a launch request, and navigates to the created run",
    async () => {
      const mutateMock = vi.fn(
        (
          payload: Record<string, unknown>,
          options?: {
            onSuccess?: (data: { run_id: string; status: string }) => void;
          },
        ) => {
          options?.onSuccess?.({
            run_id: "run-created",
            status: "accepted",
          });
        },
      );
      useLaunchNlRunMock.mockReturnValue({
        error: null,
        isPending: false,
        mutate: mutateMock,
      });

      const user = userEvent.setup();
      renderLaunchRunPage();

      await user.type(
        screen.getByTestId("composer-nl-brief"),
        "Assess inflation risks and list blockers first.",
      );
      await user.type(
        screen.getByTestId("composer-nl-data-snapshot"),
        "sha256:data-snapshot",
      );
      await user.click(screen.getByTestId("llm-profile-openai/gpt-5.4"));
      await user.type(
        screen.getByPlaceholderText("openai/gpt-5.4"),
        "custom/model",
      );
      await user.click(
        screen.getByRole("button", { name: "pages.composer.addModel" }),
      );

      await waitFor(() => expect(saveComposerDraftMock).toHaveBeenCalled(), {
        timeout: 2_000,
      });

      const launchButton = screen.getByTestId("composer-launch-nl");
      await waitFor(() => expect(launchButton).toBeEnabled());
      await user.click(launchButton);

      expect(mutateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          checkpoint_policy: "strict",
          data_source: {
            data_snapshot_ref: "sha256:data-snapshot",
          },
          llm_model: "openai/gpt-5.4",
          llm_models: ["openai/gpt-5.4", "custom/model"],
          max_parallel_models: 2,
          request: "Assess inflation risks and list blockers first.",
        }),
        expect.any(Object),
      );

      expect(await screen.findByText("Run detail page")).toBeInTheDocument();
      expect(deleteComposerDraftMock).toHaveBeenCalledWith("nl:new");
    },
    15_000,
  );

  it(
    "submits workflow launches and surfaces runtime API errors",
    async () => {
      const workflowMutateMock = vi.fn();
      useLaunchRunMock.mockReturnValue({
        error: new Error("Launch failed"),
        isPending: false,
        mutate: workflowMutateMock,
      });

      const user = userEvent.setup();
      renderLaunchRunPage("/compose?mode=workflow");

      await user.click(screen.getByTestId("composer-mode-workflow"));
      await user.type(
        screen.getByPlaceholderText("sha256:..."),
        "sha256:workflow",
      );

      const launchButton = screen.getByTestId("composer-launch-workflow");
      await waitFor(() => expect(launchButton).toBeEnabled());
      await user.click(launchButton);

      expect(workflowMutateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          checkpoint_policy: "strict",
          mode: "workflow",
        }),
        expect.any(Object),
      );
      expect(screen.getByText(/Launch failed/)).toBeInTheDocument();
    },
    10_000,
  );
});
