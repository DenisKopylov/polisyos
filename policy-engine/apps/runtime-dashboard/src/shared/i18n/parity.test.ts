import { createHash } from "node:crypto";

import en from "./locales/en.json";
import ru from "./locales/ru.json";
import uk from "./locales/uk.json";
import { PRIMARY_LOCALE } from "./locale";

function collectPaths(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value == null || Array.isArray(value)) {
    return prefix ? [prefix] : [];
  }

  return Object.entries(value as Record<string, unknown>).flatMap(
    ([key, nested]) => collectPaths(nested, prefix ? `${prefix}.${key}` : key),
  );
}

const COUNT_MESSAGE_ALLOWLIST = new Set([
  "pages.dashboard.narrativeAttentionBody",
  "pages.dashboard.narrativeQueueBody",
  "pages.dashboard.toolbar.addWidget",
  "pages.dashboard.toolbar.views",
  "pages.composer.planSummary",
  "pages.composer.curatedConstraints",
  "pages.composer.capabilitiesVisible",
  "pages.runs.activeRunAnnouncement",
  "pages.runs.pageCount",
  "pages.runs.pageCountWithTotal",
  "pages.runs.missingRefs",
  "pages.runs.blockers",
  "pages.runs.planMatches",
  "pages.evidence.totalProfiles",
  "pages.platform.registeredConnectors",
  "panels.reviewCollaboration.reviewers",
  "panels.dataIntelligence.catalogMatches",
  "panels.dataIntelligence.discoverCandidates",
  "panels.agentPipeline.diagnostics",
  "panels.agentPipeline.iteration",
  "panels.agentPipeline.variants",
  "panels.errors.total",
  "panels.nodeDebug.timelineEvents",
  "shared.ui.quantity.miniGraph.hidden",
  "collaboration.toolbar.onlineCount",
]);

function collectCountMessages(
  value: unknown,
  prefix = "",
): Array<[path: string, message: string]> {
  if (typeof value !== "object" || value == null || Array.isArray(value)) {
    return [];
  }

  return Object.entries(value as Record<string, unknown>).flatMap(
    ([key, nested]) => {
      const path = prefix ? `${prefix}.${key}` : key;

      if (typeof nested === "string") {
        return nested.includes("{count") ? [[path, nested]] : [];
      }

      return collectCountMessages(nested, path);
    },
  );
}

describe("locale catalogs", () => {
  it("keeps the active translation aligned and frozen continuity content locked", () => {
    const productCatalogs = { en, uk } as const;
    const authoredKeys = collectPaths(productCatalogs[PRIMARY_LOCALE]).sort();
    const ukKeys = collectPaths(uk).sort();
    const frozenRuCatalogSha256 = createHash("sha256")
      .update(JSON.stringify(ru))
      .digest("hex");

    expect(PRIMARY_LOCALE).toBe("en");
    expect(ukKeys).toEqual(authoredKeys);
    expect(frozenRuCatalogSha256).toBe(
      "4cb6c3014a14b9aa8a882cd16694ef3f6a9a29f3f971919c83a2e0a473c4449f",
    );
  });

  it.each([
    ["en", en],
    ["uk", uk],
    ["ru", ru],
  ] as const)(
    "marks all count-sensitive %s messages with ICU plural syntax or an explicit allowlist entry",
    (_locale, catalog) => {
      for (const [path, message] of collectCountMessages(catalog)) {
        const isPluralized = message.includes(", plural,");
        const isAllowedMetadata = COUNT_MESSAGE_ALLOWLIST.has(path);

        expect(
          isPluralized || isAllowedMetadata,
          `${path} must use ICU plural syntax or be justified in COUNT_MESSAGE_ALLOWLIST`,
        ).toBe(true);
      }
    },
  );
});
