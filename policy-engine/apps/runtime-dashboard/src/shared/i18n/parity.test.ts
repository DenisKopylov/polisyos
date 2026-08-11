import crypto from "node:crypto";

import en from "./locales/en.json";
import ru from "./locales/ru.json";
import uk from "./locales/uk.json";

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
  "panels.agentPipeline.overBudget",
  "panels.errors.total",
  "panels.nodeDebug.timelineEvents",
  "shared.ui.quantity.miniGraph.hidden",
  "collaboration.toolbar.onlineCount",
  "controlJob.scientistEvents",
  "controlJob.humanReviewUnresolved",
]);

const LEGACY_CONTINUITY_RU_KEY_COUNT = 2449;
const LEGACY_CONTINUITY_RU_KEY_SET_SHA256 =
  "67b7a921f503f108a9b47e034c31be130911c1fe8b7b9321fa8a163ef8d271a8";

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
  it("keeps the legacy-continuity Russian key set frozen", () => {
    const enKeys = collectPaths(en).sort();
    const ukKeys = collectPaths(uk).sort();
    const ruKeys = collectPaths(ru).sort();

    expect(ukKeys).toEqual(enKeys);
    expect(
      crypto.createHash("sha256").update(JSON.stringify(ruKeys)).digest("hex"),
    ).toBe(LEGACY_CONTINUITY_RU_KEY_SET_SHA256);
    expect(ruKeys).toHaveLength(LEGACY_CONTINUITY_RU_KEY_COUNT);
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
