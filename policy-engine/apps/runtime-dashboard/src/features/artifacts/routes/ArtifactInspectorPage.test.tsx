import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { components } from "@/api/types";
import { artifactContentSchema } from "@/api/validators";
import {
  evidenceArtifactRefKey,
  type EvidenceArtifactRef,
} from "@/shared/lib/domain/evidence";
import { renderRouteWithProviders } from "@/test/routes";

const DEFAULT_PROFILE = `sha256:${"c".repeat(64)}`;
const DEFAULT_ARTIFACT_REF = {
  artifact_id: "artifact-1",
  kind: "decision_packet",
  media_type: "application/json",
  manifest_profile_sha256: null,
};
const UNQUALIFIED_ARTIFACT_REF = { artifact_id: "artifact-1" };

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
  renderArtifactViewer: (...args: unknown[]) =>
    renderArtifactViewerMock(...args),
}));

vi.mock("@/features/artifacts/bureaucratic/BureaucraticArtifactView", () => ({
  BureaucraticArtifactView: ({
    artifactRef,
  }: {
    artifactRef: {
      artifact_id: string;
      manifest_profile_sha256?: string | null;
    };
  }) => (
    <div data-testid="bureaucratic-artifact-view">
      {JSON.stringify(artifactRef)}
    </div>
  ),
}));

vi.mock("@/shared/i18n/LocaleProvider", async () => {
  const actual = await vi.importActual<
    typeof import("@/shared/i18n/LocaleProvider")
  >("@/shared/i18n/LocaleProvider");
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

const predictiveCoverageApiResponseFixture = {
  meta: {
    generated_at: "2026-02-11T12:00:00Z",
    request_id: "req_0123456789abcdef",
    source_kinds: [],
  },
  artifact: {
    artifact_id:
      "sha256:0842d275aa73d47d96580633444cc0a3b11697f86520fcf155c2ab7c7a33f047",
    canon_read_status: "declared_bytes_conformant",
    kind: "ir.backtest_report",
    manifest_profile_sha256:
      "sha256:7bdf7798abb83b6463e4b672f4b388730f442965f1fef930d3504b1eeef7f123",
    max_bytes: 4096,
    media_type: "application/json",
    mode: "json",
    predictive_coverage_diagnostic: {
      assessment: "limited",
      canon_read_status: "declared_bytes_conformant",
      causal_effect_status: "not_established",
      counterfactual_credibility_status: "not_established",
      effective_time_status: "not_established",
      issuer_status: "not_established",
      may_not_use_for: [
        "promotion",
        "publication",
        "policy_selection",
        "causal_effect_claim",
      ],
      measurement_status: "not_measured",
      metric: "predictive_interval_coverage",
      producer_attestation_status: "not_established",
      reason_code: "no_evaluated_intervals",
      s10_metric_mapping_status: "not_established",
      s10_threshold_status: "not_established",
      scenarios: [
        {
          interval_available_count: 0,
          interval_evaluated_count: 0,
          interval_hit_count: 0,
          interval_requested_count: 1,
          interval_type: "prediction",
          metric_name: "outcome",
          nominal_confidence_level: 0.9,
          observed_hit_rate: null,
          scenario_id: "openapi-no-intervals",
        },
      ],
      source_artifact_id:
        "sha256:0842d275aa73d47d96580633444cc0a3b11697f86520fcf155c2ab7c7a33f047",
      source_manifest_profile_sha256:
        "sha256:7bdf7798abb83b6463e4b672f4b388730f442965f1fef930d3504b1eeef7f123",
      source_materialization: "reader_materialized",
      source_schema_version: "1.0",
    },
    preview: { schema_version: "1.0" },
    size_bytes: 1024,
    truncated: false,
  },
} satisfies components["schemas"]["ArtifactContentResponse"];

function mutableRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("expected mutable fixture record");
  }
  return value as Record<string, unknown>;
}

function renderArtifactPage(
  initialEntry = "/artifacts/artifact-1?tab=content",
) {
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
      relatedRefs: [
        {
          artifactId: "related-1",
          artifactRef: {
            artifact_id: "related-1",
            kind: "input",
            media_type: "application/json",
            manifest_profile_sha256: null,
          },
          label: "input",
        },
      ],
    });
    renderArtifactViewerMock.mockReset();
    renderArtifactViewerMock.mockReturnValue(
      <div data-testid="artifact-viewer">Rendered viewer</div>,
    );
    useArtifactManifestMock.mockReset();
    useArtifactManifestMock.mockReturnValue({
      data: {
        artifact: {
          artifact_id: "artifact-1",
          byte_size: 1024,
          created_at: "2026-03-10T09:00:00Z",
          kind: "decision_packet",
          manifest_profile_sha256: DEFAULT_PROFILE,
          media_type: "application/json",
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
      (
        artifactRef: EvidenceArtifactRef | string | undefined,
        options?: {
          maxBytes?: number | null;
          manifestProfileSha256?: string | null;
        },
      ) => ({
        data: {
          artifact: {
            artifact_id:
              typeof artifactRef === "string"
                ? artifactRef
                : (artifactRef?.artifact_id ?? "artifact-1"),
            manifest_profile_sha256:
              (typeof artifactRef === "string"
                ? options?.manifestProfileSha256
                : artifactRef?.manifest_profile_sha256) ?? DEFAULT_PROFILE,
            kind: "decision_packet",
            max_bytes: options?.maxBytes ?? 65536,
            media_type: "application/json",
            mode: "json",
            canon_read_status: "not_evaluated",
            decision_packet_preview: {
              document_outline: [
                {
                  section_id: "policy_answer",
                  section_type: "policy",
                  title: "Recommendation",
                },
              ],
              verdict: "APPROVE",
            },
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
          artifact_id: "artifact-1",
          kind: "decision_packet",
          media_type: "application/json",
          canon_read_status: "not_evaluated",
          manifest_profile_sha256: DEFAULT_PROFILE,
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
          root_artifact_refs: [
            {
              ...DEFAULT_ARTIFACT_REF,
              manifest_profile_sha256: DEFAULT_PROFILE,
            },
          ],
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
    expect(screen.getByTestId("artifact-canon-read-status")).toHaveTextContent(
      "not_evaluated",
    );
    expect(screen.getByRole("link", { name: "input" })).toHaveAttribute(
      "href",
      `/artifacts/related-1?tab=content&artifactRefKey=${encodeURIComponent(
        evidenceArtifactRefKey({
          artifact_id: "related-1",
          kind: "input",
          media_type: "application/json",
          manifest_profile_sha256: null,
        }),
      )}`,
    );

    await user.click(
      screen.getByRole("button", { name: "common.loadLargerPreview" }),
    );

    expect(useArtifactContentMock).toHaveBeenLastCalledWith(
      UNQUALIFIED_ARTIFACT_REF,
      {
        enabled: true,
        maxBytes: 262144,
      },
    );
    expect(renderArtifactViewerMock).toHaveBeenLastCalledWith({
      kind: "decision_packet",
      onViewChange: expect.any(Function),
      preview: {
        document_outline: [
          {
            section_id: "policy_answer",
            section_type: "policy",
            title: "Recommendation",
          },
        ],
        verdict: "APPROVE",
      },
      view: "default",
    });
  });

  it("shows validated reader and producer status from a predictive content response", () => {
    const parsedResponse = artifactContentSchema.parse(
      predictiveCoverageApiResponseFixture,
    );
    const artifactId = parsedResponse.artifact.artifact_id;
    const profile = parsedResponse.artifact.manifest_profile_sha256;
    useArtifactManifestMock.mockReturnValue({
      data: {
        artifact: {
          artifact_id: artifactId,
          byte_size: parsedResponse.artifact.size_bytes,
          created_at: "2026-02-11T12:00:00Z",
          kind: parsedResponse.artifact.kind,
          manifest_profile_sha256: profile,
          media_type: parsedResponse.artifact.media_type,
          producer_component: "artifact-inspector",
          schema_name: "ir.backtest_report",
          schema_version: "1.0",
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useArtifactContentMock.mockReturnValue({
      data: parsedResponse,
      error: null,
      isError: false,
      isLoading: false,
    });

    renderArtifactPage(`/artifacts/${artifactId}?tab=content`);

    expect(screen.getByTestId("artifact-canon-read-status")).toHaveTextContent(
      "declared_bytes_conformant",
    );
    const diagnostic = screen.getByTestId(
      "artifact-predictive-coverage-diagnostic",
    );
    expect(diagnostic).toHaveTextContent("limited");
    expect(diagnostic).toHaveTextContent("reader_materialized");
    expect(diagnostic).toHaveTextContent("not_established");
    expect(diagnostic).toHaveTextContent(
      "promotion, publication, policy_selection, causal_effect_claim",
    );
    expect(renderArtifactViewerMock).toHaveBeenCalledWith(
      expect.objectContaining({ preview: parsedResponse.artifact.preview }),
    );
  });

  it.each([
    ["mode", "text", "application/json"],
    ["media type", "json", "text/plain"],
  ] as const)(
    "withholds predictive previews when the selected source %s is not JSON",
    (_label, mode, mediaType) => {
      const parsed = artifactContentSchema.parse(
        predictiveCoverageApiResponseFixture,
      );
      const content = structuredClone(parsed.artifact);
      const contentRecord = mutableRecord(content);
      contentRecord.mode = mode;
      contentRecord.media_type = mediaType;
      const manifest = {
        artifact_id: content.artifact_id,
        byte_size: content.size_bytes,
        created_at: "2026-02-11T12:00:00Z",
        kind: content.kind,
        manifest_profile_sha256: content.manifest_profile_sha256,
        media_type: mediaType,
        producer_component: "artifact-inspector",
        schema_name: "ir.backtest_report",
        schema_version: "1.0",
      };

      useArtifactManifestMock.mockReturnValue({
        data: { artifact: manifest },
        error: null,
        isError: false,
        isLoading: false,
      });
      useArtifactContentMock.mockReturnValue({
        data: { artifact: content },
        error: null,
        isError: false,
        isLoading: false,
      });

      renderArtifactPage(`/artifacts/${content.artifact_id}?tab=content`);

      expect(
        screen.getByTestId("artifact-profile-mismatch-content"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("artifact-predictive-coverage-diagnostic"),
      ).not.toBeInTheDocument();
      expect(screen.queryByTestId("artifact-viewer")).not.toBeInTheDocument();
    },
  );

  it("withholds a schema response whose schema version differs from the manifest", () => {
    const schema = {
      artifact_id: "artifact-1",
      canon_read_status: "not_evaluated",
      kind: "decision_packet",
      media_type: "application/json",
      manifest_profile_sha256: DEFAULT_PROFILE,
      schema_name: "decision",
      schema_version: "2.0.0",
      top_level_keys: ["summary", "verdict"],
    };
    useArtifactSchemaMock.mockReturnValue({
      data: { schema },
      error: null,
      isError: false,
      isLoading: false,
    });

    renderArtifactPage("/artifacts/artifact-1?tab=schema");

    expect(
      screen.getByTestId("artifact-profile-mismatch-schema"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("artifact-schema-canon-read-status"),
    ).not.toBeInTheDocument();
  });

  it("renders schema keys and lineage warnings across tabs", async () => {
    const user = userEvent.setup();
    renderArtifactPage("/artifacts/artifact-1?tab=schema");

    expect(screen.getByText("summary")).toBeInTheDocument();
    expect(screen.getByText("verdict")).toBeInTheDocument();
    expect(
      screen.getByTestId("artifact-schema-canon-read-status"),
    ).toHaveTextContent("not_evaluated");

    await user.click(
      screen.getByRole("button", { name: "pages.artifacts.lineage" }),
    );

    expect(
      screen.getByText(
        'pages.artifacts.missingArtifacts:{"artifacts":"missing-1"}',
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'pages.artifacts.corruptedArtifacts:{"artifacts":"corrupted-1"}',
      ),
    ).toBeInTheDocument();
  });

  it("passes the reading view mode through artifact search params", () => {
    renderArtifactPage("/artifacts/artifact-1?tab=content&view=reading");

    expect(renderArtifactViewerMock).toHaveBeenLastCalledWith({
      kind: "decision_packet",
      onViewChange: expect.any(Function),
      preview: {
        document_outline: [
          {
            section_id: "policy_answer",
            section_type: "policy",
            title: "Recommendation",
          },
        ],
        verdict: "APPROVE",
      },
      view: "reading",
    });
  });

  it("uses the exact selected profile for manifest and content reads", () => {
    const profile = `sha256:${"a".repeat(64)}`;
    useArtifactManifestMock.mockReturnValue({
      data: {
        artifact: {
          artifact_id: "artifact-1",
          byte_size: 1024,
          created_at: "2026-03-10T09:00:00Z",
          kind: "decision_packet",
          manifest_profile_sha256: profile,
          media_type: "application/json",
          producer_component: "atlas",
          schema_name: "decision",
          schema_version: "1.0.0",
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });

    renderArtifactPage(
      `/artifacts/artifact-1?tab=content&manifest_profile_sha256=${encodeURIComponent(profile)}`,
    );

    const selectedRef = {
      artifact_id: "artifact-1",
      manifest_profile_sha256: profile,
    };
    expect(useArtifactManifestMock).toHaveBeenCalledWith(selectedRef);
    expect(useArtifactContentMock).toHaveBeenCalledWith(selectedRef, {
      enabled: true,
      maxBytes: 65536,
    });
    expect(useArtifactSchemaMock).toHaveBeenCalledWith(selectedRef, false);
    expect(useArtifactLineageMock).toHaveBeenCalledWith(selectedRef, false);
    expect(screen.getByTestId("bureaucratic-artifact-view")).toHaveTextContent(
      JSON.stringify(selectedRef),
    );
    expect(
      screen.getByTestId("artifact-reference-selection"),
    ).toHaveTextContent(profile);
    expect(screen.getByTestId("artifact-resolved-profile")).toHaveTextContent(
      profile,
    );
  });

  it("propagates the exact full selected ref through every consumer hook", () => {
    const selectedRef = {
      artifact_id: "artifact-1",
      kind: "decision_packet",
      media_type: "application/json",
      manifest_profile_sha256: DEFAULT_PROFILE,
    };

    renderArtifactPage(
      `/artifacts/artifact-1?tab=content&artifactRefKey=${encodeURIComponent(evidenceArtifactRefKey(selectedRef))}`,
    );

    expect(useArtifactManifestMock).toHaveBeenCalledWith(selectedRef);
    expect(useArtifactContentMock).toHaveBeenCalledWith(selectedRef, {
      enabled: true,
      maxBytes: 65536,
    });
    expect(useArtifactSchemaMock).toHaveBeenCalledWith(selectedRef, false);
    expect(useArtifactLineageMock).toHaveBeenCalledWith(selectedRef, false);
    expect(screen.getByTestId("artifact-viewer")).toBeInTheDocument();
  });

  it.each([
    ["malformed", "manifest_profile_sha256=unknown"],
    [
      "conflicting duplicates",
      `manifest_profile_sha256=sha256:${"a".repeat(64)}&manifest_profile_sha256=sha256:${"b".repeat(64)}`,
    ],
    [
      "duplicate identical selectors",
      `manifest_profile_sha256=sha256:${"a".repeat(64)}&manifest_profile_sha256=sha256:${"a".repeat(64)}`,
    ],
    [
      "duplicate identical full refs",
      `artifactRefKey=${encodeURIComponent(evidenceArtifactRefKey(DEFAULT_ARTIFACT_REF))}&artifactRefKey=${encodeURIComponent(evidenceArtifactRefKey(DEFAULT_ARTIFACT_REF))}`,
    ],
    [
      "conflicting duplicate full refs",
      `artifactRefKey=${encodeURIComponent(evidenceArtifactRefKey(DEFAULT_ARTIFACT_REF))}&artifactRefKey=${encodeURIComponent(evidenceArtifactRefKey({ ...DEFAULT_ARTIFACT_REF, kind: "other.kind" }))}`,
    ],
  ])(
    "refuses %s profile selection instead of choosing a query value",
    (_label, query) => {
      renderArtifactPage(`/artifacts/artifact-1?tab=content&${query}`);

      expect(
        screen.getByTestId("artifact-profile-invalid-selection"),
      ).toBeInTheDocument();
      expect(useArtifactManifestMock).toHaveBeenCalledWith(undefined);
      expect(useArtifactContentMock).toHaveBeenCalledWith(undefined, {
        enabled: true,
        maxBytes: 65536,
      });
      expect(useArtifactSchemaMock).toHaveBeenCalledWith(undefined, false);
      expect(useArtifactLineageMock).toHaveBeenCalledWith(undefined, false);
      expect(screen.queryByTestId("artifact-viewer")).not.toBeInTheDocument();
    },
  );

  it.each([
    ["schema", "summary"],
    ["lineage", 'pages.artifacts.missingArtifacts:{"artifacts":"missing-1"}'],
  ] as const)(
    "withholds stale %s data for malformed profile selection",
    (tab, staleResult) => {
      renderArtifactPage(
        `/artifacts/artifact-1?tab=${tab}&manifest_profile_sha256=unknown`,
      );

      expect(useArtifactManifestMock).toHaveBeenCalledWith(undefined);
      expect(useArtifactContentMock).toHaveBeenCalledWith(undefined, {
        enabled: false,
        maxBytes: 65536,
      });
      expect(useArtifactSchemaMock).toHaveBeenCalledWith(
        undefined,
        tab === "schema",
      );
      expect(useArtifactLineageMock).toHaveBeenCalledWith(
        undefined,
        tab === "lineage",
      );
      expect(screen.queryByText(staleResult)).not.toBeInTheDocument();
      expect(
        screen.getByTestId("artifact-profile-invalid-selection"),
      ).toBeInTheDocument();
    },
  );

  it("refuses a response whose selected manifest profile differs", () => {
    const selectedProfile = `sha256:${"a".repeat(64)}`;
    const responseProfile = `sha256:${"b".repeat(64)}`;
    useArtifactContentMock.mockReturnValue({
      data: {
        artifact: {
          artifact_id: "artifact-1",
          manifest_profile_sha256: responseProfile,
          kind: "decision_packet",
          max_bytes: 65536,
          media_type: "application/json",
          mode: "json",
          canon_read_status: "not_evaluated",
          decision_packet_preview: { verdict: "APPROVE" },
          preview: { verdict: "APPROVE" },
          size_bytes: 2048,
          truncated: false,
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });

    renderArtifactPage(
      `/artifacts/artifact-1?tab=content&manifest_profile_sha256=${encodeURIComponent(selectedProfile)}`,
    );

    expect(
      screen.getByTestId("artifact-profile-mismatch-content"),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("artifact-viewer")).not.toBeInTheDocument();
  });

  it("keeps an unqualified request distinct from the reader-resolved default view", () => {
    renderArtifactPage("/artifacts/artifact-1?tab=content");

    expect(
      screen.getByTestId("artifact-reference-selection"),
    ).toHaveTextContent("pages.artifacts.profileUnqualified");
    expect(screen.getByTestId("artifact-resolved-profile")).toHaveTextContent(
      DEFAULT_PROFILE,
    );
    expect(screen.getByTestId("artifact-viewer")).toBeInTheDocument();
  });

  it("withholds predictive diagnostics whose schema differs from the selected manifest", () => {
    const parsedResponse = artifactContentSchema.parse(
      predictiveCoverageApiResponseFixture,
    );
    const artifact = parsedResponse.artifact;
    useArtifactManifestMock.mockReturnValue({
      data: {
        artifact: {
          artifact_id: artifact.artifact_id,
          byte_size: artifact.size_bytes,
          created_at: "2026-02-11T12:00:00Z",
          kind: artifact.kind,
          manifest_profile_sha256: artifact.manifest_profile_sha256,
          media_type: artifact.media_type,
          producer_component: "artifact-inspector",
          schema_name: "different_schema",
          schema_version: "1.0",
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useArtifactContentMock.mockReturnValue({
      data: parsedResponse,
      error: null,
      isError: false,
      isLoading: false,
    });

    renderArtifactPage(`/artifacts/${artifact.artifact_id}?tab=content`);

    expect(
      screen.getByTestId("artifact-profile-mismatch-content"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("pages.artifacts.predictiveCoverage.limitedNotice"),
    ).not.toBeInTheDocument();
  });

  it("withholds a same-profile response whose kind differs from the full ref", () => {
    const expectedRef = {
      artifact_id: "artifact-1",
      kind: "decision_packet",
      media_type: "application/json",
      manifest_profile_sha256: DEFAULT_PROFILE,
    };
    useArtifactContentMock.mockReturnValue({
      data: artifactContentSchema.parse({
        meta: {
          generated_at: "2026-03-10T09:00:00Z",
          request_id: "req-artifact-kind-mismatch",
          source_kinds: [],
        },
        artifact: {
          artifact_id: "artifact-1",
          canon_read_status: "not_evaluated",
          manifest_profile_sha256: DEFAULT_PROFILE,
          kind: "different.kind",
          max_bytes: 65536,
          media_type: "application/json",
          mode: "json",
          preview: { verdict: "APPROVE" },
          size_bytes: 2048,
          truncated: false,
        },
      }),
      error: null,
      isError: false,
      isLoading: false,
    });

    renderArtifactPage(
      `/artifacts/artifact-1?artifactRefKey=${encodeURIComponent(evidenceArtifactRefKey(expectedRef))}`,
    );

    expect(useArtifactContentMock).toHaveBeenCalledWith(expectedRef, {
      enabled: true,
      maxBytes: 65536,
    });
    expect(
      screen.getByTestId("artifact-profile-mismatch-content"),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("artifact-viewer")).not.toBeInTheDocument();
  });
});
