import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState, type ReactElement } from "react";

import { useComposerDraftStore } from "@/features/composer/state/useComposerDraftStore";
import { renderRouteWithProviders } from "@/test/routes";

const {
  composerLabelMock,
  composerTMock,
  deleteComposerDraftMock,
  loadComposerDraftMock,
  saveComposerDraftMock,
  useAuthzMock,
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
  useAuthzMock: vi.fn(),
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

vi.mock("@/app/authz/AuthzProvider", async () => {
  const actual = await vi.importActual<
    typeof import("@/app/authz/AuthzProvider")
  >("@/app/authz/AuthzProvider");
  return { ...actual, useAuthz: () => useAuthzMock() };
});

vi.mock("@/features/composer/state/composerDraftRepository", () => ({
  buildComposerDraftKey: (mode: string, fromRunId: string | null) =>
    `${mode}:${fromRunId ?? "new"}`,
  deleteComposerDraft: (...args: unknown[]) => deleteComposerDraftMock(...args),
  loadComposerDraft: (...args: unknown[]) => loadComposerDraftMock(...args),
  saveComposerDraft: (...args: unknown[]) => saveComposerDraftMock(...args),
}));

vi.mock("@/shared/i18n/LocaleProvider", async () => {
  const actual = await vi.importActual<
    typeof import("@/shared/i18n/LocaleProvider")
  >("@/shared/i18n/LocaleProvider");
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

function renderLaunchRunPage(
  initialEntry = "/compose",
  element: ReactElement = <LaunchRunPage />,
) {
  return renderRouteWithProviders({
    element,
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

function ComposerIdentityRerenderHarness() {
  const [, rerender] = useState(0);
  return (
    <>
      <button type="button" onClick={() => rerender((value) => value + 1)}>
        Refresh identity
      </button>
      <LaunchRunPage />
    </>
  );
}

function deferred<Value>() {
  let resolve: (value: Value) => void = () => undefined;
  const promise = new Promise<Value>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
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
    saveComposerDraftMock.mockResolvedValue(true);
    useAuthzMock.mockReset();
    useAuthzMock.mockReturnValue({
      status: "ready",
      user: {
        tenant_id: "tenant-a",
        user_id: "reviewer-a",
      },
    });
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

  it("renders the atlas briefing chrome with runtime capability tiles", () => {
    renderLaunchRunPage();

    expect(screen.getByTestId("composer-page")).toBeInTheDocument();
    expect(
      screen.getAllByText("pages.composer.runtimeSignalsTitle").length,
    ).toBeGreaterThan(0);

    const capabilityTiles = screen.getByTestId("composer-capability-tiles");
    expect(capabilityTiles).toBeInTheDocument();
    expect(
      within(capabilityTiles).getByText("Multi-model"),
    ).toBeInTheDocument();
    expect(within(capabilityTiles).getByText("Preflight")).toBeInTheDocument();
  });

  it("passes only settled Authz tenant-user scope to composer hydration", async () => {
    renderLaunchRunPage();

    await waitFor(() => {
      expect(loadComposerDraftMock).toHaveBeenCalledWith(
        { tenantId: "tenant-a", userId: "reviewer-a" },
        "nl:new",
      );
    });
  });

  it("clears a prior in-memory draft and avoids hydration while identity is unsettled", async () => {
    useComposerDraftStore.getState().upsertDraft({
      fromRunId: null,
      key: "nl:new",
      mode: "nl",
      updatedAt: 1_710_000_000_000,
      values: {
        checkpointPolicy: "strict",
        domainHint: "custom",
        executionIntent: "",
        expectedOutputs: [{ description: "Decision packet", kind: "decision_packet" }],
        governanceConstraints: [
          { rule: "legal review", scope: "legal", severity: "warning" },
        ],
        maxIterations: 3,
        maxParallelModels: 2,
        nlDataSourceRef: "",
        nlRequest: "",
        perModelBudgetUsd: "",
        runBudgetUsd: "",
        selectedLlmModels: [],
      },
    });
    useAuthzMock.mockReturnValue({ status: "loading", user: undefined });
    loadComposerDraftMock.mockReturnValue(new Promise(() => undefined));

    renderLaunchRunPage();

    await waitFor(() => {
      expect(useComposerDraftStore.getState().drafts).toEqual({});
    });
    expect(loadComposerDraftMock).not.toHaveBeenCalled();
    expect(
      screen.queryByText("pages.composer.restoredDraftTitle"),
    ).not.toBeInTheDocument();
  });

  it("clears tenant A before tenant B rehydrates and rejects tenant A's late draft", async () => {
    const tenantALoad = deferred<unknown>();
    const tenantBLoad = deferred<unknown>();
    loadComposerDraftMock.mockImplementation(
      (draftScope: { userId: string }, _key: string) =>
        draftScope.userId === "reviewer-a"
          ? tenantALoad.promise
          : tenantBLoad.promise,
    );
    const tenantADraft = {
      ...useComposerDraftStore.getState().drafts["nl:new"],
      fromRunId: null,
      key: "nl:new",
      mode: "nl" as const,
      updatedAt: 1_710_000_000_000,
      values: {
        checkpointPolicy: "strict" as const,
        domainHint: "custom",
        executionIntent: "",
        expectedOutputs: [{ description: "Decision packet", kind: "decision_packet" }],
        governanceConstraints: [
          { rule: "legal review", scope: "legal", severity: "warning" },
        ],
        maxIterations: 3,
        maxParallelModels: 2,
        nlDataSourceRef: "",
        nlRequest: "",
        perModelBudgetUsd: "",
        runBudgetUsd: "",
        selectedLlmModels: [],
      },
    };
    const tenantBDraft = { ...tenantADraft, updatedAt: 1_710_000_000_001 };

    const user = userEvent.setup();
    renderLaunchRunPage("/compose", <ComposerIdentityRerenderHarness />);
    await waitFor(() => {
      expect(loadComposerDraftMock).toHaveBeenCalledWith(
        { tenantId: "tenant-a", userId: "reviewer-a" },
        "nl:new",
      );
    });
    useComposerDraftStore.getState().upsertDraft(tenantADraft);
    useAuthzMock.mockReturnValue({
      status: "ready",
      user: { tenant_id: "tenant-b", user_id: "reviewer-b" },
    });

    await user.click(screen.getByRole("button", { name: "Refresh identity" }));

    expect(useComposerDraftStore.getState().drafts).toEqual({});
    await waitFor(() => {
      expect(loadComposerDraftMock).toHaveBeenCalledWith(
        { tenantId: "tenant-b", userId: "reviewer-b" },
        "nl:new",
      );
    });
    await act(async () => {
      tenantALoad.resolve(tenantADraft);
      await Promise.resolve();
    });
    expect(useComposerDraftStore.getState().drafts).toEqual({});

    await act(async () => {
      tenantBLoad.resolve(tenantBDraft);
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(useComposerDraftStore.getState().drafts).toEqual({
        "nl:new": tenantBDraft,
      });
    });
  });

  it("clears tenant A restored form state before tenant B hydration resolves", async () => {
    const tenantBDraft = deferred<unknown>();
    const tenantADraft = {
      fromRunId: null,
      key: "nl:new",
      mode: "nl" as const,
      updatedAt: 1_710_000_000_000,
      values: {
        checkpointPolicy: "strict" as const,
        domainHint: "custom",
        executionIntent: "Tenant A intent",
        expectedOutputs: [{ description: "Decision packet", kind: "decision_packet" }],
        governanceConstraints: [
          { rule: "legal review", scope: "legal", severity: "warning" },
        ],
        maxIterations: 3,
        maxParallelModels: 2,
        nlDataSourceRef: "artifact-a",
        nlRequest: "Tenant A request",
        perModelBudgetUsd: "",
        runBudgetUsd: "",
        selectedLlmModels: ["openai/gpt-5.4"],
      },
    };
    loadComposerDraftMock.mockImplementation(
      (draftScope: { userId: string }) =>
        draftScope.userId === "reviewer-a"
          ? Promise.resolve(tenantADraft)
          : tenantBDraft.promise,
    );

    const user = userEvent.setup();
    renderLaunchRunPage("/compose", <ComposerIdentityRerenderHarness />);
    expect(await screen.findByDisplayValue("Tenant A request")).toBeInTheDocument();
    expect(
      screen.getByText("pages.composer.restoredDraftTitle"),
    ).toBeInTheDocument();
    useAuthzMock.mockReturnValue({
      status: "ready",
      user: { tenant_id: "tenant-b", user_id: "reviewer-b" },
    });

    await user.click(screen.getByRole("button", { name: "Refresh identity" }));

    expect(screen.queryByDisplayValue("Tenant A request")).not.toBeInTheDocument();
    expect(
      screen.queryByText("pages.composer.restoredDraftTitle"),
    ).not.toBeInTheDocument();
    expect(useComposerDraftStore.getState().drafts).toEqual({});
    await waitFor(() => {
      expect(loadComposerDraftMock).toHaveBeenCalledWith(
        { tenantId: "tenant-b", userId: "reviewer-b" },
        "nl:new",
      );
    });
  });

  it("does not restore a deferred save after the operator discards the draft", async () => {
    const save = deferred<boolean>();
    saveComposerDraftMock.mockReturnValue(save.promise);
    const user = userEvent.setup();
    renderLaunchRunPage();

    await user.type(screen.getByTestId("composer-nl-brief"), "Discard this draft");
    await waitFor(() => expect(saveComposerDraftMock).toHaveBeenCalled());
    await user.click(
      screen.getByRole("button", { name: "pages.composer.reset" }),
    );

    expect(useComposerDraftStore.getState().drafts).toEqual({});
    await act(async () => {
      save.resolve(true);
      await Promise.resolve();
    });
    expect(useComposerDraftStore.getState().drafts).toEqual({});
  });

  it("does not report a failed composer write as restored local state", async () => {
    saveComposerDraftMock.mockResolvedValue(false);
    const user = userEvent.setup();
    renderLaunchRunPage();

    await user.type(screen.getByTestId("composer-nl-brief"), "Do not persist");
    await waitFor(() => expect(saveComposerDraftMock).toHaveBeenCalled());

    expect(useComposerDraftStore.getState().drafts).toEqual({});
    expect(
      screen.queryByText("pages.composer.restoredDraftTitle"),
    ).not.toBeInTheDocument();
  });

  it("does not restore tenant A when its save completes after switching to tenant B", async () => {
    const tenantASave = deferred<boolean>();
    const tenantBLoad = deferred<unknown>();
    saveComposerDraftMock.mockReturnValue(tenantASave.promise);
    loadComposerDraftMock.mockImplementation(
      (draftScope: { userId: string }) =>
        draftScope.userId === "reviewer-a"
          ? Promise.resolve(null)
          : tenantBLoad.promise,
    );
    const user = userEvent.setup();
    renderLaunchRunPage("/compose", <ComposerIdentityRerenderHarness />);
    await user.type(screen.getByTestId("composer-nl-brief"), "Tenant A draft");
    await waitFor(() => expect(saveComposerDraftMock).toHaveBeenCalled());
    useAuthzMock.mockReturnValue({
      status: "ready",
      user: { tenant_id: "tenant-b", user_id: "reviewer-b" },
    });

    await user.click(screen.getByRole("button", { name: "Refresh identity" }));
    await waitFor(() => {
      expect(loadComposerDraftMock).toHaveBeenCalledWith(
        { tenantId: "tenant-b", userId: "reviewer-b" },
        "nl:new",
      );
    });
    await act(async () => {
      tenantASave.resolve(true);
      await Promise.resolve();
    });

    expect(useComposerDraftStore.getState().drafts).toEqual({});
    expect(
      screen.queryByText("pages.composer.restoredDraftTitle"),
    ).not.toBeInTheDocument();
  });

  it("allows a new save after reset invalidates a pending hydration", async () => {
    const load = deferred<unknown>();
    loadComposerDraftMock.mockReturnValue(load.promise);
    const user = userEvent.setup();
    renderLaunchRunPage();

    await user.click(
      screen.getByRole("button", { name: "pages.composer.reset" }),
    );
    await user.type(screen.getByTestId("composer-nl-brief"), "New draft");
    await waitFor(() => expect(saveComposerDraftMock).toHaveBeenCalled());
    await waitFor(() => {
      expect(
        useComposerDraftStore.getState().drafts["nl:new"]?.values,
      ).toMatchObject({ nlRequest: "New draft" });
    });

    await act(async () => {
      load.resolve({
        fromRunId: null,
        key: "nl:new",
        mode: "nl",
        updatedAt: 1_710_000_000_000,
        values: { nlRequest: "Prior draft" },
      });
      await Promise.resolve();
    });
    expect(useComposerDraftStore.getState().drafts["nl:new"]?.values).toMatchObject({
      nlRequest: "New draft",
    });
  });

  it("feature enabled state cannot select Glyph authority clothing", () => {
    loadComposerDraftMock.mockReturnValue(new Promise(() => undefined));
    const features = [
      {
        category: "governance",
        description: "Multi-model natural language runs",
        key: "multimodel_nl",
        label: "Multi-model",
      },
      {
        category: "governance",
        description: "Required preflight checks",
        key: "required_preflight",
        label: "Preflight",
      },
      {
        category: "governance",
        description: "Automatic materialization",
        key: "auto_materialization",
        label: "Auto materialization",
      },
      {
        category: "governance",
        description: "Promotion lane",
        key: "promotion_lane",
        label: "Promotion lane",
      },
    ];
    const capabilities = (enabled: boolean) => ({
      data: {
        constraints: {
          max_nl_iterations: 4,
          max_parallel_models: 3,
        },
        features: features.map((feature) => ({ ...feature, enabled })),
      },
    });
    const clothing = (tiles: HTMLElement) => ({
      badges: within(tiles)
        .getAllByText("governance")
        .map((badge) => badge.className),
      glyphs: within(tiles)
        .getAllByRole("presentation", { hidden: true })
        .map((glyph) => ({
          color: glyph.style.color,
          intent: glyph.getAttribute("data-glyph-intent"),
        })),
    });

    useCapabilitiesMock.mockReturnValue(capabilities(true));
    const enabledView = renderLaunchRunPage();
    const enabledClothing = clothing(
      screen.getByTestId("composer-capability-tiles"),
    );
    enabledView.unmount();

    useCapabilitiesMock.mockReturnValue(capabilities(false));
    renderLaunchRunPage();
    const disabledClothing = clothing(
      screen.getByTestId("composer-capability-tiles"),
    );

    expect(enabledClothing).toEqual(disabledClothing);
    expect(
      enabledClothing.glyphs.every(
        ({ color, intent }) => color === "" && intent === null,
      ),
    ).toBe(true);
    expect(
      enabledClothing.badges.every(
        (className) =>
          className.includes("bg-white/65") &&
          className.includes("text-muted"),
      ),
    ).toBe(true);
  });

  it("does not raise readiness from local model-count scoring", () => {
    useLlmProfilesMock.mockReturnValue({
      data: {
        profiles: Array.from({ length: 12 }, (_, index) => ({
          description: `Model ${index}`,
          display_name: `Model ${index}`,
          input_cost_per_mtoken_usd: 0.4,
          model_id: `provider/model-${index}`,
          output_cost_per_mtoken_usd: 1.2,
          profile_id: `profile-${index}`,
          provider: "Provider",
        })),
      },
      error: null,
      isError: false,
      isLoading: false,
    });

    renderLaunchRunPage();

    expect(
      screen.queryByTestId("composer-readiness-score"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("pages.composer.readinessTitle"),
    ).not.toBeInTheDocument();
  });

  it("hydrates and discards a saved workflow draft for replans", async () => {
    loadComposerDraftMock.mockImplementation(async (_scope: unknown, key: string) => {
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

    expect(
      await screen.findByDisplayValue("Saved operator intent"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("pages.composer.restoredDraftTitle"),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "pages.composer.discardDraft" }),
    );

    expect(deleteComposerDraftMock).toHaveBeenCalledWith(
      { tenantId: "tenant-a", userId: "reviewer-a" },
      "workflow:run-42",
    );
  });

  it("persists NL drafts, builds a launch request, and navigates to the created run", async () => {
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
      screen.getByPlaceholderText("pages.composer.modelPlaceholder"),
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
    expect(deleteComposerDraftMock).toHaveBeenCalledWith(
      { tenantId: "tenant-a", userId: "reviewer-a" },
      "nl:new",
    );
  }, 15_000);

  it("keeps one editable required output and governance constraint when removing rows", async () => {
    const user = userEvent.setup();
    renderLaunchRunPage("/compose?mode=workflow");

    await screen.findAllByPlaceholderText(
      "pages.composer.expectedOutputKindPlaceholder",
    );

    await user.click(
      screen.getByRole("button", {
        name: /common.remove pages\.composer\.expectedOutputs 1/,
      }),
    );
    expect(
      screen.getAllByPlaceholderText(
        "pages.composer.expectedOutputKindPlaceholder",
      ),
    ).toHaveLength(1);

    await user.click(
      screen.getByRole("button", {
        name: /common.remove pages\.composer\.expectedOutputs 1/,
      }),
    );
    expect(
      screen.getAllByPlaceholderText(
        "pages.composer.expectedOutputKindPlaceholder",
      ),
    ).toHaveLength(1);
    expect(
      screen.getByPlaceholderText(
        "pages.composer.expectedOutputKindPlaceholder",
      ),
    ).toHaveValue("");

    await user.click(
      screen.getByRole("button", {
        name: /common.remove pages\.composer\.governanceConstraints 1/,
      }),
    );
    expect(
      screen.getAllByPlaceholderText(
        "pages.composer.constraintScopePlaceholder",
      ),
    ).toHaveLength(1);

    await user.click(
      screen.getByRole("button", {
        name: /common.remove pages\.composer\.governanceConstraints 1/,
      }),
    );
    expect(
      screen.getAllByPlaceholderText(
        "pages.composer.constraintScopePlaceholder",
      ),
    ).toHaveLength(1);
    expect(
      screen.getByPlaceholderText("pages.composer.constraintScopePlaceholder"),
    ).toHaveValue("");
  });

  it("keeps one editable required output and governance constraint in NL mode", async () => {
    const user = userEvent.setup();
    renderLaunchRunPage("/compose?mode=nl");

    await screen.findAllByPlaceholderText(
      "pages.composer.expectedOutputKindPlaceholder",
    );

    await user.click(
      screen.getByRole("button", {
        name: /common.remove pages\.composer\.expectedOutputs 1/,
      }),
    );
    await user.click(
      screen.getByRole("button", {
        name: /common.remove pages\.composer\.expectedOutputs 1/,
      }),
    );
    expect(
      screen.getAllByPlaceholderText(
        "pages.composer.expectedOutputKindPlaceholder",
      ),
    ).toHaveLength(1);
    expect(
      screen.getByPlaceholderText(
        "pages.composer.expectedOutputKindPlaceholder",
      ),
    ).toHaveValue("");

    await user.click(
      screen.getByRole("button", {
        name: /common.remove pages\.composer\.governanceConstraints 1/,
      }),
    );
    await user.click(
      screen.getByRole("button", {
        name: /common.remove pages\.composer\.governanceConstraints 1/,
      }),
    );
    expect(
      screen.getAllByPlaceholderText(
        "pages.composer.constraintScopePlaceholder",
      ),
    ).toHaveLength(1);
    expect(
      screen.getByPlaceholderText("pages.composer.constraintScopePlaceholder"),
    ).toHaveValue("");
  });

  it("submits workflow launches and surfaces runtime API errors", async () => {
    const workflowMutateMock = vi.fn();
    useLaunchRunMock.mockReturnValue({
      error: new Error("Launch failed"),
      isPending: false,
      mutate: workflowMutateMock,
    });

    const user = userEvent.setup();
    renderLaunchRunPage("/compose?mode=workflow");

    await user.click(screen.getByTestId("composer-mode-workflow"));
    await user.click(
      screen.getByRole("radio", {
        name: "pages.composer.dataSource.bindings",
      }),
    );
    await user.type(
      screen.getByPlaceholderText("pages.composer.placeholders.sha256"),
      "sha256:workflow",
    );

    const launchButton = screen.getByTestId("composer-launch-workflow");
    await waitFor(() => expect(launchButton).toBeEnabled());
    await user.click(launchButton);

    expect(workflowMutateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        checkpoint_policy: "strict",
        data_source: {
          input_bindings_ref: "sha256:workflow",
        },
        mode: "workflow",
      }),
      expect.any(Object),
    );
    expect(screen.getByText(/Launch failed/)).toBeInTheDocument();
  }, 10_000);
});
