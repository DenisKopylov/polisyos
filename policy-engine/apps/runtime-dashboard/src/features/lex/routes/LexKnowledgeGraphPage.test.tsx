import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const {
  useCapabilitiesMock,
  useLexGraphStatsMock,
  useLexPipelineStatusMock,
  useLexSearchProfileMock,
  refetchLexSearchProfileMock,
  useLexSearchMock,
  useLexTriggerMock,
  useTelemetryReadyMarkMock,
} = vi.hoisted(() => ({
  useCapabilitiesMock: vi.fn(),
  useLexGraphStatsMock: vi.fn(),
  useLexPipelineStatusMock: vi.fn(),
  useLexSearchProfileMock: vi.fn(),
  refetchLexSearchProfileMock: vi.fn(),
  useLexSearchMock: vi.fn(),
  useLexTriggerMock: vi.fn(),
  useTelemetryReadyMarkMock: vi.fn(),
}));

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

function renderLexPage() {
  return render(
    <MemoryRouter>
      <LexKnowledgeGraphPage />
    </MemoryRouter>,
    { wrapper: createQueryHookWrapper() },
  );
}

describe("LexKnowledgeGraphPage", () => {
  beforeEach(() => {
    useCapabilitiesMock.mockReset();
    useCapabilitiesMock.mockReturnValue({
      data: {
        features: [{ key: "lex_pipeline", label: "Lex pipeline" }],
      },
    });
    useLexGraphStatsMock.mockReset();
    useLexGraphStatsMock.mockReturnValue({
      data: {
        db_exists: true,
        top_entity_types: [{ count: 3, entity_type: "statute" }],
        top_predicates: [{ count: 5, predicate: "cites" }],
        total_entities: 14,
        total_facts: 22,
        total_provisions: 7,
      },
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    });
    useLexPipelineStatusMock.mockReset();
    useLexPipelineStatusMock.mockImplementation(
      (pipelineId: string | null) => ({
        data: pipelineId
          ? {
              error_message: null,
              progress_summary: { parse: 12 },
              state: "running",
            }
          : undefined,
      }),
    );
    useLexSearchMock.mockReset();
    useLexSearchProfileMock.mockReset();
    useLexSearchProfileMock.mockImplementation((outputDir: string) => ({
      data: {
        output_dir: outputDir,
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
    useLexSearchMock.mockReturnValue({
      data: {
        query: "transportability",
        results: [
          {
            confidence: 0.91,
            doc_name: "Directive",
            fact_id: "fact-1",
            fact_text: "Transport rules apply.",
            norm_type: "obligation",
            object_name: "citizens",
            predicate: "applies_to",
            provision_citation: "Art. 1",
            subject_name: "policy",
          },
        ],
        search_mode: "vector",
        total: 1,
        vector_refusal_code: null,
      },
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
          payload: Record<string, unknown>,
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

  it("renders graph metrics, search results, and pipeline status after launch", async () => {
    const user = userEvent.setup();
    renderLexPage();

    expect(screen.getByTestId("lex-page")).toBeInTheDocument();
    expect(screen.getByText("pages.lex.heroTitle")).toBeInTheDocument();
    expect(screen.getByText("cites")).toBeInTheDocument();
    expect(screen.getByText("statute: 3")).toBeInTheDocument();
    expect(screen.getByText("Transport rules apply.")).toBeInTheDocument();

    await user.click(screen.getByTestId("lex-stage-parse"));
    await user.click(screen.getByTestId("lex-resume-toggle"));

    await user.click(
      screen.getByRole("button", { name: "pages.lex.launchPipeline" }),
    );

    expect(
      useLexTriggerMock.mock.results[0]?.value.mutate,
    ).toHaveBeenCalledWith(
      expect.objectContaining({
        cards_path: "data/data_lex/edrnpa_cards_2026-04-05.xml",
        output_dir: "data/lex_knowledge",
        resume: true,
        stages: expect.objectContaining({
          parse: false,
        }),
      }),
      expect.any(Object),
    );
    expect(screen.getByText("pipe-1")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(useTelemetryReadyMarkMock).toHaveBeenCalledWith(
      "lex.knowledge.page",
      { routeId: "lex.knowledge" },
    );
  });

  it("renders empty and error states for graph stats and search", () => {
    useLexGraphStatsMock.mockReturnValueOnce({
      data: {
        db_exists: false,
        top_entity_types: [],
        top_predicates: [],
        total_entities: 0,
        total_facts: 0,
        total_provisions: 0,
      },
      error: new Error("stats failed"),
      isFetching: false,
      refetch: vi.fn(),
    });
    useLexSearchMock.mockReturnValue({
      data: {
        query: "missing",
        results: [],
        total: 0,
      },
      error: new Error("search failed"),
      isPending: false,
      mutate: vi.fn(),
    });

    renderLexPage();

    expect(
      screen.getByText(
        'pages.lex.noKnowledgeGraph:{"outputDir":"data/lex_knowledge"}',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/stats failed/)).toBeInTheDocument();
    expect(screen.getByText(/search failed/)).toBeInTheDocument();
    expect(
      screen.getByText('pages.lex.noResults:{"query":"missing"}'),
    ).toBeInTheDocument();
  });

  it("posts the click-framed selected profile and displays returned retrieval mode", async () => {
    const user = userEvent.setup();
    const mutate = vi.fn();
    refetchLexSearchProfileMock.mockResolvedValueOnce({
      data: {
        output_dir: "data/lex_knowledge",
        query_generation_intent: [
          {
            basis_kind: "legal_lex_facts_embedding",
            generation_id: "generation-facts-click-time",
            inventory_json:
              '{"basis":{"basis_kind":"legal_lex_facts_embedding"}}',
          },
        ],
        status: "available",
      },
      error: null,
    });
    useLexSearchMock.mockReturnValue({
      data: {
        query: "transportability",
        results: [],
        search_mode: "vector",
        total: 0,
        vector_refusal_code: null,
      },
      error: null,
      isPending: false,
      mutate,
    });
    renderLexPage();

    await user.type(
      screen.getByLabelText("pages.lex.knowledgeSearch"),
      "transportability",
    );
    await user.click(screen.getByRole("button", { name: "pages.lex.search" }));

    await waitFor(() => {
      expect(refetchLexSearchProfileMock).toHaveBeenCalled();
      expect(mutate).toHaveBeenCalledWith({
        query: "transportability",
        top_k: 20,
        output_dir: "data/lex_knowledge",
        query_generation_intent: [
          {
            basis_kind: "legal_lex_facts_embedding",
            generation_id: "generation-facts-click-time",
            inventory_json:
              '{"basis":{"basis_kind":"legal_lex_facts_embedding"}}',
          },
        ],
      });
    });
    expect(screen.getByTestId("lex-search-result-mode")).toHaveTextContent(
      "pages.lex.vectorSearchMode",
    );
  });

  it("keeps a typed no-profile refusal visible with text results", async () => {
    const user = userEvent.setup();
    const mutate = vi.fn();
    useLexSearchProfileMock.mockReturnValue({
      data: {
        output_dir: "data/lex_knowledge",
        refusal_code: "selected_generation_unavailable",
        status: "refused",
      },
      error: null,
      refetch: refetchLexSearchProfileMock,
    });
    refetchLexSearchProfileMock.mockResolvedValue({
      data: {
        output_dir: "data/lex_knowledge",
        refusal_code: "selected_generation_unavailable",
        status: "refused",
      },
      error: null,
    });
    useLexSearchMock.mockReturnValue({
      data: {
        query: "missing generation",
        results: [],
        search_mode: "text",
        total: 0,
        vector_refusal_code: "query_profile_unavailable",
      },
      error: null,
      isPending: false,
      mutate,
    });
    renderLexPage();

    await user.type(
      screen.getByLabelText("pages.lex.knowledgeSearch"),
      "missing generation",
    );
    await user.click(screen.getByRole("button", { name: "pages.lex.search" }));

    await waitFor(() => {
      expect(mutate).toHaveBeenCalledWith({
        query: "missing generation",
        top_k: 20,
        output_dir: "data/lex_knowledge",
      });
    });
    expect(screen.getByTestId("lex-search-profile-status")).toHaveTextContent(
      "pages.lex.selectedProfileUnavailable",
    );
    expect(screen.getByTestId("lex-search-profile-status")).toHaveTextContent(
      "selected_generation_unavailable",
    );
    expect(screen.getByTestId("lex-search-result-mode")).toHaveTextContent(
      "pages.lex.textSearchMode pages.lex.vectorSearchRefused query_profile_unavailable",
    );
  });
});
