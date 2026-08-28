import { expect, test, type Locator, type Page } from "@playwright/test";

import {
  epochProjection,
  epochStalenessAbsenceFixture,
  epochStalenessPositiveFixture,
  epochStalenessSixClassFixture,
  withServerSemanticHash,
} from "../src/test/fixtures/epochStaleness";
import {
  applyRuntimeApiScenario,
  installDashboardTestState,
  readFixtureMetadata,
  waitForDashboardSurface,
} from "./helpers/runtime-dashboard";

type JsonObject = Record<string, unknown>;

const EPOCH_ROUTE = /\/api\/v1\/temporal\/runs\/[^/]+\/epoch-staleness$/u;
const SNAPSHOT_OPTIONS = {
  animations: "disabled",
  caret: "hide",
  maxDiffPixels: 100,
} as const;

function artifactRef(digit: string, kind: string) {
  return {
    artifact_id: `sha256:${digit.repeat(64)}`,
    kind,
    media_type: "application/json",
  };
}

function staleCascadeFixture(): JsonObject {
  const candidate = epochStalenessAbsenceFixture();
  const projection = epochProjection(candidate);
  projection.certificates = [
    {
      authority_purpose: "decision_validity",
      bound_epoch_ref: `sha256:${"1".repeat(64)}`,
      certificate_ref: artifactRef("7", "runtime.epoch_certificate"),
      current_epoch_ref: `sha256:${"2".repeat(64)}`,
      input_certificate_refs: [],
      native_coordinate_refs: [],
      recipe_ref: artifactRef("8", "runtime.derivation_recipe"),
      revalidation_requirements: ["recompute owner evidence"],
      rule_schema_profile_refs: [],
      stale_reasons: ["input revision changed"],
      status: "stale",
      trigger_event_refs: [artifactRef("9", "governance.correction")],
    },
  ];
  projection.dependencies = [
    {
      advisory_event_refs: [artifactRef("9", "governance.correction")],
      authority_purpose: "derived_observation",
      disposition: "invalidate",
      owner_evidence_refs: [],
      recompute: {
        evidence_content_hash: null,
        evidence_ref: null,
        predicate_provenance: "not_established",
        status: "not_established",
      },
      relation: "input revision → dependent derivation",
      source_classes: ["correction"],
      source_ref: artifactRef("3", "runtime.input_revision"),
      target_ref: artifactRef("4", "runtime.derived_observation"),
    },
  ];
  return withServerSemanticHash(candidate);
}

function crossEpochReplayFixture(): JsonObject {
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
  return withServerSemanticHash(candidate);
}

async function openEpochSurface(page: Page, body: JsonObject) {
  const metadata = readFixtureMetadata();
  await installDashboardTestState(page, { theme: "light" });
  await applyRuntimeApiScenario(page, "ok", [
    {
      body,
      matcher: EPOCH_ROUTE,
      method: "GET",
    },
  ]);
  await page.goto(`/runs/${metadata.core_run_id}/overview`);
  await waitForDashboardSurface(page, "run-overview");
  const surface = page.getByTestId("epoch-staleness-view");
  await expect(surface).toBeVisible();
  await page.evaluate(async () => document.fonts.ready);
  return surface;
}

async function openReplay(surface: Locator) {
  await surface.locator("summary").click();
  await expect(
    surface.getByRole("heading", { name: "Epoch lineage" }),
  ).toBeVisible();
}

test("DS18 real declared absence", async ({ page }) => {
  const surface = await openEpochSurface(page, epochStalenessAbsenceFixture());
  await expect(surface.getByText("Authority not appointed")).toHaveCount(2);
  await expect(
    surface.getByText("Engineering capability not wired"),
  ).toBeVisible();
  await expect(surface.getByRole("button", { name: /MACHINE/u })).toBeEnabled();
  await expect(surface).toHaveScreenshot(
    "ds18-declared-absence.png",
    SNAPSHOT_OPTIONS,
  );
});

test("DS18 content-bound positive fixture", async ({ page }) => {
  const surface = await openEpochSurface(page, epochStalenessPositiveFixture());
  await expect(surface).toHaveAttribute("data-epoch-status", "current");
  await expect(surface.getByTestId("epoch-fixture-only")).toContainText(
    "Fixture-only evidence",
  );
  await expect(surface).toHaveScreenshot(
    "ds18-positive-fixture.png",
    SNAPSHOT_OPTIONS,
  );
});

test("DS18 stale certificate and dependency cascade", async ({ page }) => {
  const surface = await openEpochSurface(page, staleCascadeFixture());
  await openReplay(surface);
  await expect(
    surface.getByText("stale — input revision changed"),
  ).toBeVisible();
  await expect(surface.getByText(/recompute not established/u)).toBeVisible();
  await expect(surface).toHaveScreenshot(
    "ds18-stale-cascade.png",
    SNAPSHOT_OPTIONS,
  );
});

test("DS18 six perturbation classes", async ({ page }) => {
  const surface = await openEpochSurface(page, epochStalenessSixClassFixture());
  await openReplay(surface);
  await expect(
    surface.locator('[data-testid^="epoch-perturbation-"]'),
  ).toHaveCount(6);
  await expect(surface.getByTestId("epoch-perturbation-appeal")).toContainText(
    "instance",
  );
  await expect(surface).toHaveScreenshot(
    "ds18-six-perturbation-classes.png",
    SNAPSHOT_OPTIONS,
  );
});

test("DS18 OpenWorldRisk freeze", async ({ page }) => {
  const surface = await openEpochSurface(page, epochStalenessAbsenceFixture());
  const freeze = surface.getByTestId("epoch-open-world-freeze");
  await expect(freeze).toBeVisible();
  await expect(freeze).toHaveScreenshot(
    "ds18-open-world-risk-freeze.png",
    SNAPSHOT_OPTIONS,
  );
});

test("DS18 cross-epoch replay", async ({ page }) => {
  const surface = await openEpochSurface(page, crossEpochReplayFixture());
  await openReplay(surface);
  const boundary = surface.getByTestId("epoch-boundary");
  await boundary.focus();
  await expect(boundary).toBeFocused();
  await expect(boundary).toContainText(`sha256:${"1".repeat(64)}`);
  await expect(boundary).toContainText(`sha256:${"2".repeat(64)}`);
  await expect(surface).toHaveScreenshot(
    "ds18-cross-epoch-replay.png",
    SNAPSHOT_OPTIONS,
  );
});
