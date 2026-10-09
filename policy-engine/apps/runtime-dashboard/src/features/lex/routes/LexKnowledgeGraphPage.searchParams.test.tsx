import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const {
  resetSearchParamsMock,
  setSearchParamsMock,
  useSearchParamsMock,
  useCapabilitiesMock,
  useLexGraphStatsMock,
  useLexPipelineStatusMock,
  useLexSearchProfileMock,
  refetchLexSearchProfileMock,
  useLexSearchMock,
  useLexTriggerMock,
  useTelemetryReadyMarkMock,
} = vi.hoisted(() => {
  let currentSearchParams = new URLSearchParams();
  const setSearchParamsMock = vi.fn(
    (next: ConstructorParameters<typeof URLSearchParams>[0]) => {
      currentSearchParams = new URLSearchParams(next);
    },
  );

  return {
    resetSearchParamsMock: (initial = "") => {
      currentSearchParams = new URLSearchParams(initial);
      setSearchParamsMock.mockClear();
    },
    setSearchParamsMock,
    useCapabilitiesMock: vi.fn(),
    useLexGraphStatsMock: vi.fn(),
    useLexPipelineStatusMock: vi.fn(),
    useLexSearchProfileMock: vi.fn(),
    refetchLexSearchProfileMock: vi.fn(),
    useLexSearchMock: vi.fn(),
    useLexTriggerMock: vi.fn(),
    useTelemetryReadyMarkMock: vi.fn(),
    useSearchParamsMock: () =>
      [currentSearchParams, setSearchParamsMock] as const,
  };
});

vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return {
    ...actual,
    useSearchParams: () => useSearchParamsMock(),
  };
});

vi.mock("@/api/hooks/useCapabilities", () => ({
  useCapabilities: (...args: unknown[]) => useCapabilitiesMock(...args),
}));

vi.mock("@/api/hooks/useLexGraphStats", () => ({
  useLexGraphStats: (...args: unknown[]) => useLexGraphStatsMock(...args),
}));

vi.mock("@/api/hooks/useLexPipelineStatus", () => ({
  useLexPipelineStatus: (...args: unknown[]) =>
    useLexPipelineStatusMock(...args),
}));

vi.mock("@/api/hooks/useLexSearch", () => ({
  useLexSearch: (...args: unknown[]) => useLexSearchMock(...args),
}));

vi.mock("@/api/hooks/useLexSearchProfile", () => ({
  useLexSearchProfile: (...args: unknown[]) => useLexSearchProfileMock(...args),
}));

vi.mock("@/api/hooks/useLexTrigger", () => ({
  useLexTrigger: (...args: unknown[]) => useLexTriggerMock(...args),
}));

vi.mock("@/app/providers/TelemetryProvider", async () => {
  const actual = await vi.importActual<
    typeof import("@/app/providers/TelemetryProvider")
  >("@/app/providers/TelemetryProvider");
  return {
    ...actual,
    useTelemetryReadyMark: (...args: unknown[]) =>
      useTelemetryReadyMarkMock(...args),
  };
});

vi.mock("@/app/routes/PrefetchButton", () => ({
  PrefetchButton: ({ children }: { children: React.ReactNode }) => (
    <button type="button">{children}</button>
  ),
}));

vi.mock("@/shared/i18n/LocaleProvider", async () => {
  const actual = await vi.importActual<
    typeof import("@/shared/i18n/LocaleProvider")
  >("@/shared/i18n/LocaleProvider");
  return {
    ...actual,
    useI18n: () => ({
      t: (key: string, payload?: Record<string, unknown>) =>
        payload ? `${key}:${JSON.stringify(payload)}` : key,
    }),
  };
});

import LexKnowledgeGraphPage from "@/features/lex/routes/LexKnowledgeGraphPage";
import { createQueryHookWrapper } from "@/test/queryHook";

describe("LexKnowledgeGraphPage search param behavior", () => {
  beforeEach(() => {
    resetSearchParamsMock();
    useCapabilitiesMock.mockReset();
    useCapabilitiesMock.mockReturnValue({
      data: {
        features: [{ key: "lex_pipeline", label: "Lex pipeline" }],
      },
    });
    useLexGraphStatsMock.mockReset();
    useLexGraphStatsMock.mockReturnValue({
      data: {
        db_exists: false,
        top_entity_types: [],
        top_predicates: [],
        total_entities: 0,
        total_facts: 0,
        total_provisions: 0,
      },
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    });
    useLexPipelineStatusMock.mockReset();
    useLexPipelineStatusMock.mockReturnValue({ data: undefined });
    useLexSearchProfileMock.mockReset();
    useLexSearchProfileMock.mockImplementation((outputDir: string) => ({
      data: {
        output_dir: outputDir,
        query_generation_intent: [],
        status: "available",
      },
      error: null,
      refetch: refetchLexSearchProfileMock,
    }));
    refetchLexSearchProfileMock.mockReset();
    refetchLexSearchProfileMock.mockResolvedValue({
      data: {
        output_dir: "data/lex_knowledge",
        query_generation_intent: [
          {
            basis_kind: "legal_lex_facts_embedding",
            generation_id: "generation-facts-1",
            inventory_json:
              '{"basis":{"basis_kind":"legal_lex_facts_embedding"}}',
          },
        ],
        status: "available",
      },
      error: null,
    });
    useLexSearchMock.mockReset();
    useLexSearchMock.mockReturnValue({
      data: undefined,
      error: null,
      isPending: false,
      mutate: vi.fn(),
    });
    useLexTriggerMock.mockReset();
    useLexTriggerMock.mockReturnValue({
      data: undefined,
      error: null,
      isPending: false,
      mutate: vi.fn(
        (
          _payload: Record<string, unknown>,
          options?: {
            onSuccess?: (data: {
              message: string;
              pipeline_id: string;
              status: string;
            }) => void;
          },
        ) => {
          options?.onSuccess?.({
            message: "accepted",
            pipeline_id: "pipe-1",
            status: "accepted",
          });
        },
      ),
    });
    useTelemetryReadyMarkMock.mockReset();
  });

  it("uses replace semantics for typing-driven URL sync and push semantics for explicit actions", async () => {
    const user = userEvent.setup();

    render(<LexKnowledgeGraphPage />, { wrapper: createQueryHookWrapper() });

    await user.type(screen.getByLabelText("pages.lex.outputDirectory"), "next");
    expect(setSearchParamsMock).toHaveBeenLastCalledWith(
      expect.any(URLSearchParams),
      expect.objectContaining({ replace: true }),
    );

    await user.type(
      screen.getByLabelText("pages.lex.knowledgeSearch"),
      "transportability",
    );
    expect(setSearchParamsMock).toHaveBeenLastCalledWith(
      expect.any(URLSearchParams),
      expect.objectContaining({ replace: true }),
    );

    await user.click(screen.getByRole("button", { name: "pages.lex.search" }));
    await waitFor(() => {
      expect(setSearchParamsMock).toHaveBeenLastCalledWith(
        expect.any(URLSearchParams),
        expect.objectContaining({ replace: false }),
      );
    });

    await user.click(screen.getByTestId("lex-resume-toggle"));
    expect(setSearchParamsMock).toHaveBeenLastCalledWith(
      expect.any(URLSearchParams),
      expect.objectContaining({ replace: true }),
    );

    await user.click(
      screen.getByRole("button", { name: "pages.lex.launchPipeline" }),
    );
    expect(setSearchParamsMock).toHaveBeenLastCalledWith(
      expect.any(URLSearchParams),
      expect.objectContaining({ replace: false }),
    );
  });
});
