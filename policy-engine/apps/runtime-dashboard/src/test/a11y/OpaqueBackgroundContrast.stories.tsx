import type { CSSProperties, PropsWithChildren } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";
import type {
  DecisionPacketAuthoredBlock,
  DepthNDomainRunProjection,
  PolicyDesignCaseProjectionBlocker,
  ProjectionFreshness,
} from "@polisyos/runtime-api-client";
import { Badge } from "@polisyos/atlas-ui";
import axe from "axe-core";
import { expect, within } from "storybook/test";

import { CandidateFrame } from "@/shared/ui/compounds/CandidateFrame";
import { NegativeCertificateCard } from "@/shared/ui/compounds/NegativeCertificateCard";
import { WeakestLinkExplainer } from "@/shared/ui/compounds/WeakestLinkExplainer";
import { ProvenanceMiniGraph } from "@/shared/ui/quantity/ProvenanceMiniGraph";
import { ProvenancePopover } from "@/shared/ui/quantity/ProvenancePopover";
import type {
  LineageGraphView,
  QuantityValue,
} from "@/shared/ui/quantity/quantity.types";
import { TimeSemanticsLabel } from "@/shared/ui/temporal/TimeSemanticsLabel";

import {
  classifyOpaqueBackgroundContrast,
  hasOpaqueBackground,
  OPAQUE_BACKGROUND_CONTRAST_SOURCES,
  type AxeContrastPass,
  type OpaqueBackgroundContrastObservation,
  type OpaqueBackgroundContrastSourceId,
} from "./opaqueBackgroundContrast";

const OPAQUE_BACKGROUND_STYLE = {
  backgroundColor: "rgb(255, 255, 255)",
  backgroundImage: "none",
} satisfies CSSProperties;

const candidateBlock = {
  author: "ds6-browser-fixture",
  author_agent_version: "fixture-only",
  confidence: 0.61,
  content:
    "Candidate material remains non-authoritative while this fixture measures its rendered contrast.",
  reviewed_by_human: false,
  sources: [],
  timestamp: "2026-08-11T12:00:00.000Z",
} satisfies DecisionPacketAuthoredBlock;

const blocker = {
  code: "fixture_missing_grounded_effect",
  evidence_ref: "fixture://evidence/missing-grounded-effect",
  message:
    "No producer-signed grounded effect is available in this browser fixture.",
  module_id: "ds6-browser-fixture",
  next_action: "Load producer-signed evidence before promotion.",
  owner: "fixture-only",
  severity: "blocking",
} satisfies PolicyDesignCaseProjectionBlocker;

const weakestLinkUnavailable = {
  acquisition_route: { status: "artifact_missing" },
  design_problem_ref: "fixture://design-problem/ds6-contrast",
  domain_role: "fixture_only",
  evidence_class: "fixture_only",
  evidence_witness: { availability: "artifact_missing" },
  generation_cycle_run_id: "fixture://generation-cycle/ds6-contrast",
  terminal_distribution: { fixture_only: 1 },
  weakest_links: [],
} satisfies DepthNDomainRunProjection;

const freshness = {
  basis: "source_timestamp",
  observed_at: "2026-08-11T12:00:00.000Z",
  source_as_of: null,
  state: "artifact_missing",
} satisfies ProjectionFreshness;

const untracedQuantity = {
  label: "Fixture-only effect estimate",
  lineage: {
    freshness: "unknown",
    id: "untraced",
    reason_code: "fixture_only_ds6_contrast",
    status: "untraced",
  },
  metric_id: "fixture_only_effect_estimate",
  point: null,
  quantity_class: "decision",
  time: {
    tx_at: "2026-08-11T12:00:00.000Z",
    valid_at: "2026-08-11T11:58:00.000Z",
  },
  unit: { code: "1", display: "ratio", system: "ucum" },
} satisfies QuantityValue;

const populatedLineage = {
  compact_summary: [
    { id: "source", kind: "source", label: "Source record" },
    { id: "transform", kind: "transform", label: "Normalized input" },
    { id: "model", kind: "model", label: "Effect model" },
    { id: "result", kind: "result", label: "Effect estimate" },
  ],
  edges: [],
  exports: { openlineage: "", prov: "" },
  freshness: "current",
  id: "fixture://lineage/ds6-contrast",
  nodes: [],
  status: "verified",
} satisfies LineageGraphView;

function OpaqueSource({
  children,
  sourceId,
}: PropsWithChildren<{ sourceId: Exclude<OpaqueBackgroundContrastSourceId, "provenance-popover"> }>) {
  return (
    <section
      className="border-line text-foreground rounded-xl border p-4"
      data-opaque-contrast-source={sourceId}
      style={OPAQUE_BACKGROUND_STYLE}
    >
      {children}
    </section>
  );
}

function RenderedContrastFixture() {
  return (
    <div
      className="grid gap-4 lg:grid-cols-2"
      data-opaque-contrast-fixture="true"
      style={OPAQUE_BACKGROUND_STYLE}
    >
      <OpaqueSource sourceId="badge-neutral">
        <Badge kind="neutral">Neutral evidence state</Badge>
      </OpaqueSource>

      <div className="border-line rounded-xl border p-4" style={OPAQUE_BACKGROUND_STYLE}>
        <ProvenancePopover
          className="bg-white"
          onOpenChange={() => undefined}
          open
          quantity={untracedQuantity}
        >
          <button className="underline" type="button">
            Fixture provenance details
          </button>
        </ProvenancePopover>
      </div>

      <OpaqueSource sourceId="provenance-mini-graph">
        <ProvenanceMiniGraph lineage={populatedLineage} />
      </OpaqueSource>

      <OpaqueSource sourceId="time-semantics-label">
        <TimeSemanticsLabel
          cacheAgeLabel="fixture_only"
          freshness={freshness}
          payloadAsOf="2026-08-11T12:00:00.000Z"
          txAt="2026-08-11T12:00:00.000Z"
          validAt="2026-08-11T11:58:00.000Z"
        />
      </OpaqueSource>

      <OpaqueSource sourceId="candidate-frame">
        <CandidateFrame
          block={candidateBlock}
          mayNotUseFor={["approval", "publication"]}
          title="Candidate recommendation"
        />
      </OpaqueSource>

      <OpaqueSource sourceId="negative-certificate-card">
        <NegativeCertificateCard blocker={blocker} />
      </OpaqueSource>

      <OpaqueSource sourceId="weakest-link-explainer">
        <WeakestLinkExplainer projection={weakestLinkUnavailable} />
      </OpaqueSource>
    </div>
  );
}

const meta = {
  title: "DS6/A11y/Opaque Background Contrast",
  parameters: {
    a11y: { test: "error" },
    docs: {
      description: {
        component:
          "Test-only real-browser fixture for the seven DS4 contrast-incomplete source identities.",
      },
    },
  },
  render: () => <RenderedContrastFixture />,
} satisfies Meta;

export default meta;

type Story = StoryObj<typeof meta>;

export const SevenDeclaredSources: Story = {
  play: async ({ canvasElement }) => {
    const document = canvasElement.ownerDocument;
    const controlledHarness = establishOpaqueHarness(document, canvasElement);
    const fixture = document.querySelector<HTMLElement>(
      '[data-opaque-contrast-fixture="true"]',
    );
    if (!fixture) {
      throw new Error("The opaque contrast fixture surface is missing.");
    }
    controlledHarness.push(fixture);
    for (const element of controlledHarness) {
      await expect(hasOpaqueBackground(element)).toBe(true);
    }

    const popover = await within(document.body).findByLabelText("Provenance");
    popover.setAttribute("data-opaque-contrast-source", "provenance-popover");

    const observations: OpaqueBackgroundContrastObservation[] = [];
    for (const source of OPAQUE_BACKGROUND_CONTRAST_SOURCES) {
      const matches = Array.from(document.querySelectorAll(source.selector));
      await expect(matches).toHaveLength(1);
      const element = matches[0];
      if (!(element instanceof HTMLElement)) {
        throw new TypeError(`${source.sourceId} did not resolve to an HTMLElement.`);
      }

      const opaqueBackdrop = hasOpaqueBackground(element);
      await expect(opaqueBackdrop).toBe(true);

      const results = await axe.run(element, {
        elementRef: true,
        resultTypes: ["passes", "violations", "incomplete"],
        runOnly: { type: "rule", values: ["color-contrast"] },
      });
      observations.push({
        sourceId: source.sourceId,
        opaqueBackdrop,
        violationCount: countNodes(results.violations),
        incompleteCount: countNodes(results.incomplete),
        contrastPasses: extractNumericPasses(results),
      });
    }

    const classification = classifyOpaqueBackgroundContrast(observations);
    await expect(classification.failures).toEqual([]);
    await expect(classification.status).toBe("pass");
    await expect(classification.passed).toBe(7);
    await expect(classification.receipts).toHaveLength(7);
  },
};

function establishOpaqueHarness(
  document: Document,
  canvasElement: HTMLElement,
): HTMLElement[] {
  const controlledAncestors: HTMLElement[] = [
    document.documentElement,
    document.body,
  ];
  let current: HTMLElement | null = canvasElement;
  while (current && current !== document.body) {
    controlledAncestors.push(current);
    current = current.parentElement;
  }
  for (const element of controlledAncestors) {
    Object.assign(element.style, OPAQUE_BACKGROUND_STYLE);
  }
  return controlledAncestors;
}

function countNodes(results: axe.Result[]): number {
  return results.reduce((total, result) => total + result.nodes.length, 0);
}

function extractNumericPasses(results: axe.AxeResults): AxeContrastPass[] {
  return results.passes.flatMap((result) =>
    result.nodes.flatMap((node) =>
      [...node.any, ...node.all, ...node.none].flatMap((check) => {
        const data = check.data as Record<string, unknown> | null;
        if (!data || !("contrastRatio" in data)) {
          return [];
        }
        return [
          {
            contrastRatio: parseAxeRatio(data.contrastRatio),
            expectedContrastRatio: parseAxeRatio(data.expectedContrastRatio),
          },
        ];
      }),
    ),
  );
}

function parseAxeRatio(value: unknown): unknown {
  if (typeof value === "number") {
    return value;
  }
  if (typeof value !== "string") {
    return value;
  }
  const match = /^(\d+(?:\.\d+)?):1$/.exec(value);
  return match ? Number(match[1]) : value;
}
