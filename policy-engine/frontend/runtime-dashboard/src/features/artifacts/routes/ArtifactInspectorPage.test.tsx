import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderRouteWithProviders } from "@/test/routes";

const {
  getArtifactViewerDescriptorMock,
  renderArtifactViewerMock,
  useArtifactContentMock,
  useArtifactLineageMock,
  useArtifactManifestMock,
  useArtifactSchemaMock,
} = vi.hoisted(() => ({
  getArtifactViewerDescriptorMock: vi.fn(),
  renderArtifactViewerMock: vi.fn(),
  useArtifactContentMock: vi.fn(),
  useArtifactLineageMock: vi.fn(),
  useArtifactManifestMock: vi.fn(),
  useArtifactSchemaMock: vi.fn(),
}));

vi.mock("@/api/hooks/useArtifactContent", () => ({
  useArtifactContent: (...args: unknown[]) => useArtifactContentMock(...args),
}));

vi.mock("@/api/hooks/useArtifactLineage", () => ({
  useArtifactLineage: (...args: unknown[]) => useArtifactLineageMock(...args),
}));

vi.mock("@/api/hooks/useArtifactManifest", () => ({
  useArtifactManifest: (...args: unknown[]) => useArtifactManifestMock(...args),
}));

vi.mock("@/api/hooks/useArtifactSchema", () => ({
  useArtifactSchema: (...args: unknown[]) => useArtifactSchemaMock(...args),
}));

vi.mock("@/features/artifacts/components/ArtifactViewerRegistry", () => ({
  getArtifactViewerDescriptor: (...args: unknown[]) =>
    getArtifactViewerDescriptorMock(...args),
  renderArtifactViewer: (...args: unknown[]) => renderArtifactViewerMock(...args),
}));

vi.mock("@/i18n/LocaleProvider", async () => {
  const actual = await vi.importActual<typeof import("@/i18n/LocaleProvider")>(
    "@/i18n/LocaleProvider",
  );
  return {
    ...actual,
    useI18n: () => ({
      label: (
        _namespace: string,
        value: string | null | undefined,
        fallback: string,
      ) => fallback ?? value ?? "",
      t: (key: string, payload?: Record<string, unknown>) =>
        payload ? `${key}:${JSON.stringify(payload)}` : key,
    }),
  };
});

import ArtifactInspectorPage from "@/features/artifacts/routes/ArtifactInspectorPage";

function renderArtifactPage(initialEntry = "/artifacts/artifact-1?tab=content") {
  return renderRouteWithProviders({
    element: <ArtifactInspectorPage />,
    path: "/artifacts/:artifactId",
    initialEntry,
  });
}

describe("ArtifactInspectorPage", () => {
  beforeEach(() => {
    getArtifactViewerDescriptorMock.mockReset();
    getArtifactViewerDescriptorMock.mockReturnValue({
      relatedRefs: [{ artifactId: "related-1", label: "input" }],
    });
    renderArtifactViewerMock.mockReset();
    renderArtifactViewerMock.mockReturnValue(
      <div data-testid="artifact-viewer">Rendered viewer</div>,
    );
    useArtifactManifestMock.mockReset();
    useArtifactManifestMock.mockReturnValue({
      data: {
        artifact: {
          byte_size: 1024,
          created_at: "2026-03-10T09:00:00Z",
          kind: "decision_packet",
          producer_component: "atlas",
          schema_name: "decision",
          schema_version: "1.0.0",
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useArtifactContentMock.mockReset();
    useArtifactContentMock.mockImplementation(
      (_artifactId: string, options?: { maxBytes?: number | null }) => ({
        data: {
          artifact: {
            kind: "decision_packet",
            max_bytes: options?.maxBytes ?? 65536,
            media_type: "application/json",
            mode: "preview",
            preview: { verdict: "APPROVE" },
            size_bytes: 2048,
            truncated: (options?.maxBytes ?? 65536) < 262144,
          },
        },
        error: null,
        isError: false,
        isLoading: false,
      }),
    );
    useArtifactSchemaMock.mockReset();
    useArtifactSchemaMock.mockReturnValue({
      data: {
        schema: {
          schema_name: "decision",
          schema_version: "1.0.0",
          top_level_keys: ["summary", "verdict"],
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useArtifactLineageMock.mockReset();
    useArtifactLineageMock.mockReturnValue({
      data: {
        lineage: {
          corrupted_artifact_ids: ["corrupted-1"],
          edges: [],
          is_complete: false,
          missing_artifact_ids: ["missing-1"],
          nodes: [
            {
              artifact_id: "artifact-1",
              depth: 0,
              kind: "decision_packet",
              status: "ok",
            },
          ],
          root_artifact_ids: ["artifact-1"],
          total_edges: 0,
          total_nodes: 1,
          total_size_bytes: 1024,
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
  });

  it("renders content previews, related refs, and escalates preview size", async () => {
    const user = userEvent.setup();
    renderArtifactPage();

    expect(screen.getByTestId("artifact-page")).toBeInTheDocument();
    expect(screen.getByText("pages.artifacts.title")).toBeInTheDocument();
    expect(screen.getByTestId("artifact-viewer")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "input" })).toHaveAttribute(
      "href",
      "/artifacts/related-1",
    );

    await user.click(
      screen.getByRole("button", { name: "common.loadLargerPreview" }),
    );

    expect(useArtifactContentMock).toHaveBeenLastCalledWith("artifact-1", {
      enabled: true,
      maxBytes: 262144,
    });
  });

  it("renders schema keys and lineage warnings across tabs", async () => {
    const user = userEvent.setup();
    renderArtifactPage("/artifacts/artifact-1?tab=schema");

    expect(screen.getByText("summary")).toBeInTheDocument();
    expect(screen.getByText("verdict")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "pages.artifacts.lineage" }));

    expect(
      screen.getByText('pages.artifacts.missingArtifacts:{"artifacts":"missing-1"}'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('pages.artifacts.corruptedArtifacts:{"artifacts":"corrupted-1"}'),
    ).toBeInTheDocument();
  });
});
