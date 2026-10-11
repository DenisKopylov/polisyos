import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const { labelMock, tMock } = vi.hoisted(() => ({
  labelMock: vi.fn(
    (_mapName: string, value: string | null | undefined, fallback?: string) =>
      value ? `label:${value}` : (fallback ?? "-"),
  ),
  tMock: vi.fn((path: string, vars?: Record<string, unknown>) =>
    vars ? `${path}:${JSON.stringify(vars)}` : path,
  ),
}));

vi.mock("@/shared/i18n/LocaleProvider", async () => {
  const actual = await vi.importActual<
    typeof import("@/shared/i18n/LocaleProvider")
  >("@/shared/i18n/LocaleProvider");
  return {
    ...actual,
    useI18n: () => ({
      label: labelMock,
      t: tMock,
    }),
  };
});

vi.mock("@polisyos/atlas-ui", async () => {
  const actual =
    await vi.importActual<typeof import("@polisyos/atlas-ui")>(
      "@polisyos/atlas-ui",
    );
  return {
    ...actual,
    Badge: ({ children, kind }: { children: ReactNode; kind: string }) => (
      <span data-kind={kind}>{children}</span>
    ),
    JsonPreview: ({ data }: { data: unknown }) => (
      <pre data-testid="json-preview">{JSON.stringify(data)}</pre>
    ),
  };
});

vi.mock("@/features/artifacts/components/DecisionCardView", () => ({
  default: ({ artifactKind }: { artifactKind: string }) => (
    <div data-testid="decision-card-view">{artifactKind}</div>
  ),
}));

vi.mock(
  "@/features/artifacts/components/simulation/SimulationResultsViewer",
  () => ({
    default: ({ artifactKind }: { artifactKind: string }) => (
      <div data-testid="simulation-results-viewer">{artifactKind}</div>
    ),
  }),
);

vi.mock("@/features/artifacts/components/trinity/TrinityCard", () => ({
  default: () => <div data-testid="trinity-card-view">trinity</div>,
}));

import {
  getArtifactViewerDescriptor,
  renderArtifactViewer,
} from "@/features/artifacts/components/ArtifactViewerRegistry";
import { parseEvidenceArtifactRefKey } from "@/shared/lib/domain/evidence";

function renderViewer(kind: string, preview: unknown) {
  return render(
    <MemoryRouter>{renderArtifactViewer({ kind, preview })}</MemoryRouter>,
  );
}

describe("ArtifactViewerRegistry", () => {
  beforeEach(() => {
    labelMock.mockClear();
    tMock.mockClear();
  });

  it("extracts deduped related artifact refs from nested preview shapes", () => {
    const descriptor = getArtifactViewerDescriptor({
      kind: "scientist.preflight_report",
      preview: {
        artifacts: {
          plan: "artifact-3",
        },
        decision_packet_ref: {
          artifact_id: "artifact-1",
          manifest_profile_sha256: `sha256:${"a".repeat(64)}`,
        },
        inputs: {
          bundle: {
            artifact_id: "artifact-4",
          },
          inline: "artifact-5",
        },
        links: {
          duplicate: {
            artifact_id: "artifact-1",
            manifest_profile_sha256: `sha256:${"a".repeat(64)}`,
          },
          report: {
            artifact_id: "artifact-1",
            manifest_profile_sha256: `sha256:${"b".repeat(64)}`,
          },
          malformed: {
            artifact_id: "artifact-1",
            manifest_profile_sha256: "sha256:not-a-profile",
          },
        },
      },
    });

    expect(descriptor.title).toBe("scientist.preflight_report");
    expect(descriptor.relatedRefs.map((ref) => ref.artifactId)).toEqual([
      "artifact-3",
      "artifact-1",
      "artifact-4",
      "artifact-5",
      "artifact-1",
    ]);
    expect(
      descriptor.relatedRefs
        .filter((ref) => ref.artifactId === "artifact-1")
        .map((ref) => ref.artifactRef.manifest_profile_sha256),
    ).toEqual([`sha256:${"a".repeat(64)}`, `sha256:${"b".repeat(64)}`]);
  });

  it("keeps same-blob related manifest profiles separately navigable", () => {
    renderViewer("scientist.preflight_report", {
      decision_packet_ref: {
        artifact_id: "artifact-shared",
        manifest_profile_sha256: `sha256:${"a".repeat(64)}`,
      },
      links: {
        sibling: {
          artifact_id: "artifact-shared",
          manifest_profile_sha256: `sha256:${"b".repeat(64)}`,
        },
      },
    });

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(2);
    const firstUrl = new URL(
      links[0]!.getAttribute("href")!,
      "http://localhost",
    );
    const secondUrl = new URL(
      links[1]!.getAttribute("href")!,
      "http://localhost",
    );
    const selectedRefs = [firstUrl, secondUrl].map((url) =>
      parseEvidenceArtifactRefKey(url.searchParams.get("artifactRefKey") ?? ""),
    );
    expect(firstUrl.pathname).toBe("/artifacts/artifact-shared");
    expect(secondUrl.pathname).toBe("/artifacts/artifact-shared");
    expect(firstUrl.searchParams.get("tab")).toBe("content");
    expect(secondUrl.searchParams.get("tab")).toBe("content");
    expect(selectedRefs).toEqual([
      {
        artifact_id: "artifact-shared",
        kind: null,
        media_type: null,
        manifest_profile_sha256: `sha256:${"a".repeat(64)}`,
      },
      {
        artifact_id: "artifact-shared",
        kind: null,
        media_type: null,
        manifest_profile_sha256: `sha256:${"b".repeat(64)}`,
      },
    ]);
  });

  it("refuses malformed typed metadata instead of degrading it to an ID-only link", () => {
    const descriptor = getArtifactViewerDescriptor({
      kind: "scientist.preflight_report",
      preview: {
        malformed_kind: {
          artifact_id: "artifact-invalid-kind",
          kind: 42,
          media_type: "application/json",
        },
        malformed_media_type: {
          artifact_id: "artifact-invalid-media",
          kind: "valid.kind",
          media_type: "   ",
        },
      },
    });

    expect(descriptor.relatedRefs).toEqual([]);
  });

  it("falls back to the raw JSON viewer for untyped artifact kinds", () => {
    renderViewer("custom.preview", { foo: "bar" });

    expect(screen.getByTestId("json-preview")).toHaveTextContent(
      '{"foo":"bar"}',
    );
    expect(screen.queryByText("pages.artifacts.title")).not.toBeInTheDocument();
  });

  it("routes metric-validation reports to the simulation viewer", async () => {
    renderViewer("scientist.metric_validation_report", {
      comparisons: [],
      family_adjustment: { method: "holm" },
    });

    expect(
      await screen.findByTestId("simulation-results-viewer"),
    ).toHaveTextContent("scientist.metric_validation_report");
  });

  it("renders the preflight report viewer with diagnostics, hints, notes, and related refs", () => {
    renderViewer("scientist.preflight_report", {
      decision_packet_ref: {
        artifact_id: "artifact-1",
      },
      diagnostics: [
        {
          code: "missing_data",
          message: "Missing source",
          replanning_hints: ["Pin dataset"],
          severity: "warning",
        },
      ],
      notes: ["Review license"],
      ready_to_run: false,
    });

    expect(screen.getByText("pages.artifacts.title")).toBeInTheDocument();
    const decisionPacketUrl = new URL(
      screen
        .getByRole("link", { name: "Decision Packet Ref" })
        .getAttribute("href")!,
      "http://localhost",
    );
    expect(decisionPacketUrl.pathname).toBe("/artifacts/artifact-1");
    expect(decisionPacketUrl.searchParams.get("tab")).toBe("content");
    expect(
      parseEvidenceArtifactRefKey(
        decisionPacketUrl.searchParams.get("artifactRefKey") ?? "",
      ),
    ).toEqual({
      artifact_id: "artifact-1",
      kind: null,
      media_type: null,
      manifest_profile_sha256: null,
    });
    expect(screen.getByText("missing_data")).toBeInTheDocument();
    expect(screen.getByText("Missing source")).toBeInTheDocument();
    expect(screen.getByText("label:warning")).toHaveAttribute(
      "data-kind",
      "neutral",
    );
    expect(
      screen.getByText('pages.artifacts.viewers.hints:{"hints":"Pin dataset"}'),
    ).toBeInTheDocument();
    expect(screen.getByText("- Review license")).toBeInTheDocument();
  });

  it("keeps all three preflight readiness facts in neutral owner-recorded clothing", () => {
    let view = renderViewer("scientist.preflight_report", {
      ready_to_run: true,
    });
    expect(screen.getByText("common.ready")).toHaveAttribute(
      "data-kind",
      "neutral",
    );

    view.unmount();
    view = renderViewer("scientist.preflight_report", {
      ready_to_run: false,
    });
    expect(screen.getByText("common.blocked")).toHaveAttribute(
      "data-kind",
      "neutral",
    );

    view.unmount();
    renderViewer("scientist.preflight_report", {});
    expect(screen.getByText("common.unavailable")).toHaveAttribute(
      "data-kind",
      "neutral",
    );
  });

  it("renders evaluator and reproducibility typed viewers", () => {
    let view = renderViewer("scientist.evaluator_report", {
      diagnostics: [{ code: "guardrail", message: "Needs review" }],
      reasons: ["Policy breach"],
      replanning_hints: ["Try a different source"],
      scores: {
        budget_score: 0.1,
        kpi_score: 0.6,
        total_score: 0.4,
      },
      verdict: "APPROVE",
    });

    expect(screen.getByText("- Policy breach")).toBeInTheDocument();
    expect(screen.getByText("- Try a different source")).toBeInTheDocument();
    expect(screen.getByText("Needs review")).toBeInTheDocument();

    view.unmount();

    view = renderViewer("scientist.reproducibility_manifest", {
      data_snapshot_hash: "snapshot-1",
      determinism_tier: "strict",
      input_bindings_hash: "bindings-1",
      method_catalog_hash: "catalog-1",
      missing_refs: ["artifact-a"],
      plan_hash: "plan-1",
      readiness: "partial",
      registry_hash: "registry-1",
      seed: "1234",
      suggested_next_step: "Retry with pinned sources",
      why_partial: ["Missing snapshot"],
    });

    expect(screen.getByText("- Missing snapshot")).toBeInTheDocument();
    expect(screen.getByText("- artifact-a")).toBeInTheDocument();
    expect(screen.getByText("Retry with pinned sources")).toBeInTheDocument();
  });

  it("renders legal, quality, and causal viewers", () => {
    let view = renderViewer("lex.legal_report", {
      issues: [{ code: "legal-risk", message: "Needs legal review" }],
      jurisdiction: "EU",
      recommendations: ["Escalate to counsel"],
      status: "blocked",
    });

    expect(screen.getByText("legal-risk")).toBeInTheDocument();
    expect(screen.getByText("Needs legal review")).toBeInTheDocument();
    expect(screen.getByText("- Escalate to counsel")).toBeInTheDocument();

    view.unmount();

    view = renderViewer("fabric.quality_report", {
      gates: {
        status: "warn",
      },
      metrics: {
        completeness: 0.71,
        coverage: 0.82,
      },
      quality_score: 0.77,
      violations: ["coverage_gap"],
    });

    expect(
      screen.getByText("pages.artifacts.viewers.gateStatus"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("pages.artifacts.viewers.coverageGaps"),
    ).toBeInTheDocument();
    expect(screen.getByText("completeness, coverage")).toBeInTheDocument();

    view.unmount();

    renderViewer("ir.causal_effect_report", {
      effect_estimate: 0.0314,
      estimand: "ATT",
      method: "Synthetic control",
      standard_error: 0.004,
      status: "ready",
      transport_result: {
        assumptions: ["Ignorability"],
        portability_blockers: ["Dataset mismatch"],
        status: "portable",
      },
    });

    expect(screen.getByText("- Ignorability")).toBeInTheDocument();
    expect(screen.getByText("- Dataset mismatch")).toBeInTheDocument();
  });

  it("renders mocked lazy viewers for decision, simulation, and trinity kinds", async () => {
    let view = renderViewer("scientist.decision_card", {
      title: "Decision",
    });
    expect(await screen.findByTestId("decision-card-view")).toHaveTextContent(
      "scientist.decision_card",
    );

    view.unmount();

    view = renderViewer("foundry.simulation_result", {
      result: "ok",
    });
    expect(
      await screen.findByTestId("simulation-results-viewer"),
    ).toHaveTextContent("foundry.simulation_result");

    view.unmount();

    renderViewer("ir.trinity_bundle", {
      summary: "bundle",
    });
    expect(await screen.findByTestId("trinity-card-view")).toHaveTextContent(
      "trinity",
    );
  });
});
