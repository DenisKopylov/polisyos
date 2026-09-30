import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const dashboardRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const metadataPath = path.resolve(
  dashboardRoot,
  "../../_build/apps/runtime-dashboard/public-verification/metadata.json",
);

test("real verification service authenticates a report and rejects the same record after signature removal", async ({
  page,
}) => {
  const metadata = JSON.parse(await readFile(metadataPath, "utf8")) as {
    record_id: string;
    title: string;
    fixture_control_url: string;
    fixture_token: string;
  };
  const recordUrl = `/public/decisions/${metadata.record_id}`;
  const realVerdict = () =>
    page
      .waitForEvent("requestfinished", (request) => {
        const url = new URL(request.url());
        return (
          url.pathname === "/api/v1/public-decisions/verification" &&
          url.searchParams.get("record_id") === metadata.record_id
        );
      })
      .then(async (request) => {
        const response = await request.response();
        if (!response) throw new Error("verification_response_missing");
        return response;
      });
  const firstResponse = realVerdict();
  await page.goto(recordUrl);
  const authenticated = await (await firstResponse).json();
  expect(authenticated.report_authentication).toBe("verified");
  expect(authenticated.cryptographic_signature).toBe("valid");
  expect(authenticated.report_key_status).toBe("trusted");
  expect(authenticated.promoted_record).toBeNull();
  await expect(
    page.getByText("Verification record authenticated", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: metadata.title }),
  ).toBeVisible();
  for (const [dimension, value] of Object.entries(authenticated.dimensions)) {
    expect(value).toBe("not_established");
    await expect(
      page.getByTestId(`verification-dimension-${dimension}`),
    ).toContainText("Not established");
  }
  await expect(
    page.getByText("Decision verified", { exact: true }),
  ).toHaveCount(0);
  await expect(page.getByTestId("publication-packet-panel")).toHaveCount(0);

  try {
    // The fixture performs an isolated out-of-band mutation. The browser sees
    // only a scoped control URL and never learns a local CAS path.
    const fixtureHeaders = {
      "x-policyos-fixture-token": metadata.fixture_token,
    };
    const damaged = await page.request.post(
      `${metadata.fixture_control_url}/damage`,
      { headers: fixtureHeaders },
    );
    expect(damaged.ok()).toBeTruthy();
    const damagedResponse = realVerdict();
    await page.reload();
    const rejected = await (await damagedResponse).json();
    expect(rejected.record_id).toBe(metadata.record_id);
    expect(rejected.cryptographic_signature).toBe("invalid");
    expect(rejected.report_authentication).toBe("invalid");
    expect(rejected.reason_codes).toContain("record_signature_invalid");
    expect(rejected.public_document).toBeNull();
    await expect(page.getByTestId("public-decision-unavailable")).toContainText(
      "record_signature_invalid",
    );
    await expect(
      page.getByText("Verification record authenticated", { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("heading", { name: metadata.title }),
    ).toHaveCount(0);
  } finally {
    const restored = await page.request.post(
      `${metadata.fixture_control_url}/restore`,
      { headers: { "x-policyos-fixture-token": metadata.fixture_token } },
    );
    expect(restored.ok()).toBeTruthy();
  }
});
