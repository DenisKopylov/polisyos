import type { ComponentType } from "react";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AdmittedEpochStalenessProjection } from "@/features/runs/domain/epochStaleness";
import { TimeSemanticsLabel } from "@/shared/ui/temporal/TimeSemanticsLabel";
import {
  EPOCH_PERTURBATION_CLASSES,
  epochProjection,
  epochStalenessAbsenceFixture,
  epochStalenessPositiveFixture,
  epochStalenessSixClassFixture,
} from "@/test/fixtures/epochStaleness";

import { EpochStalenessView } from "./EpochStalenessView";

function projection(candidate: Record<string, unknown>) {
  return epochProjection(
    candidate,
  ) as unknown as AdmittedEpochStalenessProjection;
}

describe("epoch staleness surface", () => {
  it("changes chrome when the underlying epoch state changes under one shell", () => {
    const Label = TimeSemanticsLabel as ComponentType<{
      epochSemantics: Record<string, unknown>;
    }>;
    const { rerender } = render(
      <Label
        epochSemantics={{
          asOf: "2026-02-11T12:00:00Z",
          asOfReason: null,
          currentEpochRef: `sha256:${"a".repeat(64)}`,
          epochRefs: [`sha256:${"a".repeat(64)}`],
          kind: "admitted",
          projectionSemanticHash: `sha256:${"b".repeat(64)}`,
          revalidationRequired: false,
          status: "current",
          validityStatus: "active",
        }}
      />,
    );

    expect(screen.getByTestId("time-semantics-epoch-status")).toHaveTextContent(
      "current",
    );
    expect(screen.getByTestId("time-semantics-as-of")).toHaveTextContent(
      "2026-02-11",
    );

    rerender(
      <Label
        epochSemantics={{
          asOf: "2026-02-12T12:00:00Z",
          asOfReason: null,
          currentEpochRef: `sha256:${"c".repeat(64)}`,
          epochRefs: [`sha256:${"a".repeat(64)}`, `sha256:${"c".repeat(64)}`],
          kind: "admitted",
          projectionSemanticHash: `sha256:${"d".repeat(64)}`,
          revalidationRequired: true,
          status: "revalidation_required",
          validityStatus: "review_required",
        }}
      />,
    );

    expect(screen.getByTestId("time-semantics-epoch-status")).toHaveTextContent(
      "revalidation required",
    );
    expect(screen.getByTestId("time-semantics-revalidation")).toHaveTextContent(
      "required",
    );
  });

  it("renders institutional and engineering absences as different usable states", () => {
    render(
      <EpochStalenessView
        projection={projection(epochStalenessAbsenceFixture())}
        rawBytes={new TextEncoder().encode('{"exact":"wire"}\n')}
      />,
    );

    const view = screen.getByTestId("epoch-staleness-view");
    expect(within(view).getAllByText("Authority not appointed")).toHaveLength(
      2,
    );
    expect(
      within(view).getByText("Engineering capability not wired"),
    ).toBeInTheDocument();
    expect(
      within(view).getByText("polisyos.runtime.quality.derived_observations"),
    ).toBeInTheDocument();
    expect(
      within(view).getByRole("button", { name: /MACHINE/u }),
    ).toBeEnabled();
    expect(within(view).getByText(/Replay inspection/u)).toBeInTheDocument();
    expect(
      within(view).queryByText(/appoint signer|bypass/u),
    ).not.toBeInTheDocument();
  });

  it("renders six distinct causes and keeps appeal instance-scoped", () => {
    render(
      <EpochStalenessView
        projection={projection(epochStalenessSixClassFixture())}
        rawBytes={new TextEncoder().encode("{}")}
      />,
    );

    for (const sourceClass of EPOCH_PERTURBATION_CLASSES) {
      expect(
        screen.getByTestId(`epoch-perturbation-${sourceClass}`),
      ).toBeInTheDocument();
    }
    expect(screen.getByTestId("epoch-perturbation-appeal")).toHaveTextContent(
      /instance/u,
    );
    expect(
      screen.getByTestId("epoch-perturbation-correction"),
    ).toHaveTextContent(/dependency descendants/u);
  });

  it("renders replay boundaries instead of blending predecessor and successor epochs", () => {
    const candidate = epochStalenessAbsenceFixture();
    epochProjection(candidate).lineage = [
      {
        current_epoch_ref: `sha256:${"2".repeat(64)}`,
        predecessor_packet_ref: null,
        previous_epoch_ref: `sha256:${"1".repeat(64)}`,
        successor_packet_ref: null,
        transition_ref: null,
        trigger_event_refs: [],
      },
    ];
    render(
      <EpochStalenessView
        projection={projection(candidate)}
        rawBytes={new TextEncoder().encode("{}")}
      />,
    );

    const boundary = screen.getByTestId("epoch-boundary");
    expect(boundary).toHaveTextContent(`sha256:${"1".repeat(64)}`);
    expect(boundary).toHaveTextContent(`sha256:${"2".repeat(64)}`);
    expect(boundary).toHaveTextContent(/boundary/u);
  });

  it("changes stale certificate treatment when the owner state changes", () => {
    const candidate = epochStalenessAbsenceFixture();
    const certificateId = `sha256:${"7".repeat(64)}`;
    epochProjection(candidate).certificates = [
      {
        authority_purpose: "decision_validity",
        bound_epoch_ref: `sha256:${"1".repeat(64)}`,
        certificate_ref: {
          artifact_id: certificateId,
          kind: "runtime.epoch_certificate",
          media_type: "application/json",
        },
        current_epoch_ref: `sha256:${"2".repeat(64)}`,
        input_certificate_refs: [],
        native_coordinate_refs: [],
        recipe_ref: {
          artifact_id: `sha256:${"8".repeat(64)}`,
          kind: "runtime.derivation_recipe",
          media_type: "application/json",
        },
        revalidation_requirements: ["recompute owner evidence"],
        rule_schema_profile_refs: [],
        stale_reasons: ["input revision changed"],
        status: "stale",
        trigger_event_refs: [],
      },
    ];
    const { rerender } = render(
      <EpochStalenessView
        projection={projection(candidate)}
        rawBytes={new TextEncoder().encode("{}")}
      />,
    );
    const certificate = screen.getByTestId(
      `epoch-certificate-${certificateId}`,
    );
    expect(certificate).toHaveAttribute("data-certificate-status", "stale");
    expect(certificate).toHaveClass("line-through");

    const current = structuredClone(candidate);
    const currentProjection = epochProjection(current);
    currentProjection.certificates = [
      {
        ...(
          currentProjection.certificates as Array<Record<string, unknown>>
        )[0],
        bound_epoch_ref: `sha256:${"2".repeat(64)}`,
        revalidation_requirements: [],
        stale_reasons: [],
        status: "current",
      },
    ];
    rerender(
      <EpochStalenessView
        projection={projection(current)}
        rawBytes={new TextEncoder().encode("{}")}
      />,
    );
    expect(certificate).toHaveAttribute("data-certificate-status", "current");
    expect(certificate).not.toHaveClass("line-through");
  });

  it("renders and releases the OpenWorldRisk freeze from owner state", () => {
    const absence = epochStalenessAbsenceFixture();
    const { rerender } = render(
      <EpochStalenessView
        projection={projection(absence)}
        rawBytes={new TextEncoder().encode("{}")}
      />,
    );
    expect(screen.getByTestId("epoch-open-world-freeze")).toBeInTheDocument();

    rerender(
      <EpochStalenessView
        projection={projection(epochStalenessPositiveFixture())}
        rawBytes={new TextEncoder().encode("{}")}
      />,
    );
    expect(
      screen.queryByTestId("epoch-open-world-freeze"),
    ).not.toBeInTheDocument();
  });
});
