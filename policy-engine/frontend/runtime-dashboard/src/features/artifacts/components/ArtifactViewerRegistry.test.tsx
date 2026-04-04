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

vi.mock("@/i18n/LocaleProvider", async () => {
  const actual = await vi.importActual<typeof import("@/i18n/LocaleProvider")>(
    "@/i18n/LocaleProvider",
  );
  return {
    ...actual,
    useI18n: () => ({
      label: labelMock,
      t: tMock,
    }),
  };
});

vi.mock("@/shared/ui", () => ({
  Badge: ({ children, kind }: { children: ReactNode; kind: string }) => (
    <span data-kind={kind}>{children}</span>
  ),
  JsonPreview: ({ data }: { data: unknown }) => (
    <pre data-testid="json-preview">{JSON.stringify(data)}</pre>
  ),
}));

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
          },
          report: {
            artifact_id: "artifact-2",
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
      "artifact-2",
    ]);
  });

  it("falls back to the raw JSON viewer for untyped artifact kinds", () => {
    renderViewer("custom.preview", { foo: "bar" });

    expect(screen.getByTestId("json-preview")).toHaveTextContent(
      '{"foo":"bar"}',
    );
    expect(screen.queryByText("pages.artifacts.title")).not.toBeInTheDocument();
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
    expect(
      screen.getByRole("link", { name: "Decision Packet Ref" }),
    ).toHaveAttribute("href", "/artifacts/artifact-1");
    expect(screen.getByText("missing_data")).toBeInTheDocument();
    expect(screen.getByText("Missing source")).toBeInTheDocument();
    expect(
      screen.getByText('pages.artifacts.viewers.hints:{"hints":"Pin dataset"}'),
    ).toBeInTheDocument();
    expect(screen.getByText("- Review license")).toBeInTheDocument();
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
