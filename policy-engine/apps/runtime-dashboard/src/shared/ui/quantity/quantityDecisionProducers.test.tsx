import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { screen } from "@testing-library/react";

import {
  quantityControlIdentities,
  quantityDecisionProducerProbes,
  readAbsentDecisionScore,
  readKnownConfidenceWithoutScore,
  removedAuthorityGuessIdentities,
  renderAbsentDecisionScoreConsumer,
  renderKnownConfidenceWithoutScoreConsumer,
  renderTypedFixtureAuthorityConsumer,
  renderUntracedNumericScoreConsumer,
  typedFixtureAuthority,
} from "@/test/contracts/quantityDecisionProducerHarness";
import { renderWithProviders } from "@/test/render";

type Diagnostic = {
  column: number;
  line: number;
  message_id: string;
  path: string;
};

type ManifestFile = {
  diagnostics: Diagnostic[];
  path: string;
};

type DebtManifest = {
  lint: {
    files: ManifestFile[];
    immutable_origin?: { files: ManifestFile[] };
    origin?: { files: ManifestFile[] };
    resolutions?: Array<{
      classification?: string;
      cluster_id?: string;
      origin_identity?: Diagnostic;
    }>;
  };
};

const manifest = JSON.parse(
  readFileSync(
    resolve(
      process.cwd(),
      "../../architecture/atlas_surfaces/frontend-baseline-debt-manifest.json",
    ),
    "utf8",
  ),
) as DebtManifest;

function identityKey(identity: Pick<Diagnostic, "column" | "line" | "path">) {
  return `${identity.path}:${identity.line}:${identity.column}`;
}

function c06OriginalDiagnostics(): Diagnostic[] {
  const resolutions = manifest.lint.resolutions ?? [];
  const resolved = resolutions
    .filter(
      (row) =>
        row.cluster_id === "C06" &&
        row.classification === "quantity_enveloped" &&
        row.origin_identity,
    )
    .map((row) => row.origin_identity as Diagnostic);
  if (resolved.length > 0) {
    return resolved;
  }

  const c06Paths = new Set(
    quantityDecisionProducerProbes.map((probe) => probe.path),
  );
  const controls = new Set(quantityControlIdentities.map(identityKey));
  const files =
    manifest.lint.immutable_origin?.files ??
    manifest.lint.origin?.files ??
    manifest.lint.files;
  return files
    .filter((file) => c06Paths.has(file.path))
    .flatMap((file) => file.diagnostics)
    .filter(
      (diagnostic) =>
        diagnostic.message_id === "decision" &&
        !controls.has(identityKey(diagnostic)),
    );
}

function c06RemovedAuthorityGuesses(): Diagnostic[] {
  return (manifest.lint.resolutions ?? [])
    .filter(
      (row) =>
        row.cluster_id === "C06" &&
        row.classification === "authority_guess_removed" &&
        row.origin_identity,
    )
    .map((row) => row.origin_identity as Diagnostic);
}

function expectDecisionQuantity(
  value: unknown,
  expected: { metricId: string; point: number | null },
) {
  expect(value).toEqual(
    expect.objectContaining({
      lineage: expect.objectContaining({
        id: expect.any(String),
        status: "untraced",
      }),
      metric_id: expected.metricId,
      point: expected.point,
      quantity_class: "decision",
      unit: expect.objectContaining({ code: expect.any(String) }),
    }),
  );
}

describe("quantity decision producers", () => {
  it("emits and consumes every manifest-owned decision-bearing value as QuantityValue", () => {
    const diagnostics = c06OriginalDiagnostics();
    expect(diagnostics).toHaveLength(quantityDecisionProducerProbes.length);
    expect(quantityDecisionProducerProbes.map(identityKey).sort()).toEqual(
      diagnostics.map(identityKey).sort(),
    );

    for (const probe of quantityDecisionProducerProbes) {
      expectDecisionQuantity(probe.read(), {
        metricId: probe.expectedMetricId,
        point: probe.expectedPoint,
      });
    }

    for (const probe of quantityDecisionProducerProbes) {
      expect(
        probe.renderConsumer,
        `${identityKey(probe)} needs a live consumer`,
      ).toBeTypeOf("function");
      const view = renderWithProviders(probe.renderConsumer!());
      expect(
        screen
          .getAllByTestId("quantity")
          .some(
            (quantity) =>
              quantity.getAttribute("data-quantity-metric-id") ===
              probe.expectedMetricId,
          ),
        `consumer must render ${probe.expectedMetricId}`,
      ).toBe(true);
      view.unmount();
    }
  });

  it("content-binds every removed authority guess to the manifest", () => {
    const diagnostics = c06RemovedAuthorityGuesses();
    expect(diagnostics).toHaveLength(removedAuthorityGuessIdentities.length);
    expect(removedAuthorityGuessIdentities.map(identityKey).sort()).toEqual(
      diagnostics.map(identityKey).sort(),
    );
  });

  it("marks typed fixture authority without parsing a quantity reason code", () => {
    renderWithProviders(renderTypedFixtureAuthorityConsumer());

    expect(screen.getByTestId("atlas-fixture-authority")).toHaveAttribute(
      "data-fixture-authority",
      typedFixtureAuthority,
    );
  });

  it("keeps an absent decision score unknown and out of numeric evidence charts", () => {
    expectDecisionQuantity(readAbsentDecisionScore(), {
      metricId: "run.decision_score",
      point: null,
    });

    renderWithProviders(renderAbsentDecisionScoreConsumer());

    const score = screen
      .getAllByTestId("quantity")
      .find(
        (quantity) =>
          quantity.getAttribute("data-quantity-metric-id") ===
          "run.decision_score",
      );
    expect(score).toHaveTextContent("Unknown");
    expect(screen.queryByText("Trust calibration")).not.toBeInTheDocument();
    expect(screen.queryByText("Sensitivity analysis")).not.toBeInTheDocument();
  });

  it("does not turn a known confidence label into a score or synthetic evidence", () => {
    expectDecisionQuantity(readKnownConfidenceWithoutScore(), {
      metricId: "run.decision_score",
      point: null,
    });

    renderWithProviders(renderKnownConfidenceWithoutScoreConsumer());

    expect(screen.queryByText("Trust calibration")).not.toBeInTheDocument();
    expect(screen.queryByText("Sensitivity analysis")).not.toBeInTheDocument();
  });

  it("does not promote an untraced numeric score into authority-colored derived charts", () => {
    renderWithProviders(renderUntracedNumericScoreConsumer());

    expect(
      screen.queryByRole("meter", { name: "Confidence gauge: 84%" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Trust calibration")).not.toBeInTheDocument();
    expect(screen.queryByText("Sensitivity analysis")).not.toBeInTheDocument();
  });
});
