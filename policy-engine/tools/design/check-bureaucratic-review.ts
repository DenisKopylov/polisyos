import fs from "node:fs";
import path from "node:path";

import { getPolicyEngineRoot } from "./_a11yColor.ts";

const REQUIRED_TEMPLATES = {
  "ua.analitichna_zapyska.v1": "1.0.0",
  "ua.expert_vysnovok.v1": "1.0.0",
  "ua.kmu.postanova.v1": "1.0.0",
  "ua.rada.zakonoproekt.v1": "1.0.0",
} as const;

type ReviewEntry = {
  status?: string;
  reviewer_name?: string;
  reviewer_role?: string;
  review_date?: string;
  reviewed_template_version?: string;
  watermark_disclaimer_approved?: boolean;
  numbering_approved?: boolean;
  signature_seal_placeholders_approved?: boolean;
  evidence_ref?: string;
};

function main() {
  const root = getPolicyEngineRoot();
  const registryPath = path.join(
    root,
    "docs/brand/bureaucratic-template-review.json",
  );
  const registry = JSON.parse(fs.readFileSync(registryPath, "utf8")) as {
    templates?: Record<string, ReviewEntry>;
  };
  const templates = registry.templates ?? {};

  for (const [templateId, version] of Object.entries(REQUIRED_TEMPLATES)) {
    const entry = templates[templateId];
    if (!entry) {
      throw new Error(`Missing bureaucratic template review entry: ${templateId}`);
    }
    if (entry.status !== "approved") {
      throw new Error(`Template ${templateId} is not approved.`);
    }
    if (entry.reviewed_template_version !== version) {
      throw new Error(
        `Template ${templateId} review version ${entry.reviewed_template_version} does not match ${version}.`,
      );
    }
    for (const field of [
      "reviewer_name",
      "reviewer_role",
      "review_date",
      "evidence_ref",
    ] as const) {
      if (!entry[field]) {
        throw new Error(`Template ${templateId} review is missing ${field}.`);
      }
    }
    for (const field of [
      "watermark_disclaimer_approved",
      "numbering_approved",
      "signature_seal_placeholders_approved",
    ] as const) {
      if (entry[field] !== true) {
        throw new Error(`Template ${templateId} review did not approve ${field}.`);
      }
    }
  }

  const serviceSource = fs.readFileSync(
    path.join(
      root,
      "src/polisyos/runtime/http/services/bureaucratic_rendering.py",
    ),
    "utf8",
  );
  for (const templateId of Object.keys(REQUIRED_TEMPLATES)) {
    if (!serviceSource.includes(templateId)) {
      throw new Error(
        `Bureaucratic rendering service catalog is missing ${templateId}.`,
      );
    }
  }

  console.log("Bureaucratic template review checks passed.");
}

main();
