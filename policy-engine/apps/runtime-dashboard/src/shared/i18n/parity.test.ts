import crypto from "node:crypto";
import { IntlMessageFormat } from "intl-messageformat";

import { formatIcuMessage, isPluralMessage } from "./messages/icu-messages";
import en from "./locales/en.json";
import ru from "./locales/ru.json";
import uk from "./locales/uk.json";

type Catalog = Record<string, unknown>;

function comparePaths(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

function collectPaths(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value == null || Array.isArray(value)) {
    return prefix ? [prefix] : [];
  }

  return Object.entries(value as Catalog).flatMap(([key, nested]) =>
    collectPaths(nested, prefix ? `${prefix}.${key}` : key),
  );
}

const COUNT_MESSAGE_ALLOWLIST = new Map<string, string>([
  [
    "pages.dashboard.toolbar.addWidget",
    "Parenthesized badge counter; the imperative label does not agree with the count.",
  ],
  [
    "pages.dashboard.toolbar.views",
    "Parenthesized badge counter; `Views` is a fixed toolbar label.",
  ],
  [
    "pages.composer.planSummary",
    "Numeric NL-iteration cap value; it is not a noun-bearing quantity phrase.",
  ],
  [
    "pages.runs.activeRunAnnouncement",
    "Count is the total denominator in “row … of”; it has no agreeing noun.",
  ],
  [
    "pages.runs.pageCount",
    "Machine-readable `name=value` pagination metric.",
  ],
  [
    "pages.runs.pageCountWithTotal",
    "Machine-readable pagination metric paired with a total.",
  ],
  [
    "pages.runs.missingRefs",
    "Postfixed diagnostic tally; fixed technical label rather than a quantified phrase.",
  ],
  [
    "pages.runs.blockers",
    "Postfixed diagnostic tally; fixed technical label rather than a quantified phrase.",
  ],
  [
    "pages.platform.registeredConnectors",
    "Predicative status “registered”; no noun form is selected by count.",
  ],
  [
    "panels.reviewCollaboration.reviewers",
    "Its only tracked caller selects this key only when `participants.length > 1`; singular uses `panels.reviewCollaboration.solo`.",
  ],
  [
    "panels.dataIntelligence.catalogMatches",
    "Colon-delimited result metric; the count is not adjacent to the fixed label.",
  ],
  [
    "panels.dataIntelligence.discoverCandidates",
    "Parenthesized action badge; the action label does not agree with count.",
  ],
  [
    "panels.agentPipeline.diagnostics",
    "Colon-delimited diagnostic metric.",
  ],
  [
    "panels.agentPipeline.iteration",
    "Iteration identifier, not a noun quantity.",
  ],
  [
    "panels.agentPipeline.overBudget",
    "Numeric budget delta with an invariant predicate, not a counted noun.",
  ],
  ["panels.errors.total", "Aggregate total metric with no agreeing noun."],
  [
    "panels.nodeDebug.timelineEvents",
    "Parenthesized badge counter; the timeline label is fixed.",
  ],
  [
    "shared.ui.quantity.miniGraph.hidden",
    "Generic `{kind}` supplies the noun; this template cannot choose its inflection.",
  ],
  [
    "collaboration.toolbar.onlineCount",
    "Online-status predicate, not a noun quantity.",
  ],
  [
    "controlJob.humanReviewUnresolved",
    "Postfixed summary tally for a fixed diagnostic-status label.",
  ],
]);

const LEGACY_CONTINUITY_RU_KEY_COUNT = 2449;
const LEGACY_CONTINUITY_RU_KEY_SET_SHA256 =
  "67b7a921f503f108a9b47e034c31be130911c1fe8b7b9321fa8a163ef8d271a8";
const LEGACY_CONTINUITY_RU_LEAF_VALUE_SHA256 =
  "0426d4ce0397027d25f5a2053bce794b12e31fbe3757d3afefb24de6ba3f45eb";

function collectCountMessages(
  value: unknown,
  prefix = "",
): Array<[path: string, message: string]> {
  if (typeof value !== "object" || value == null || Array.isArray(value)) {
    return [];
  }

  return Object.entries(value as Catalog).flatMap(([key, nested]) => {
    const path = prefix ? `${prefix}.${key}` : key;

    if (typeof nested === "string") {
      return nested.includes("{count") ? [[path, nested]] : [];
    }

    return collectCountMessages(nested, path);
  });
}

function collectLeafPairs(
  value: unknown,
  prefix = "",
): Array<[path: string, value: unknown]> {
  if (typeof value !== "object" || value == null || Array.isArray(value)) {
    return prefix ? [[prefix, value]] : [];
  }

  return Object.entries(value as Catalog).flatMap(([key, nested]) =>
    collectLeafPairs(nested, prefix ? `${prefix}.${key}` : key),
  );
}

function isValidPluralMessage(message: string): boolean {
  if (!isPluralMessage(message)) {
    return false;
  }

  try {
    new IntlMessageFormat(message, "en-US");
    return true;
  } catch {
    return false;
  }
}

function collectUnjustifiedCountMessages(
  catalog: unknown,
  exemptions: ReadonlyMap<string, string> = COUNT_MESSAGE_ALLOWLIST,
): string[] {
  return collectCountMessages(catalog)
    .filter(
      ([path, message]) =>
        isPluralMessage(message)
          ? !isValidPluralMessage(message)
          : !exemptions.get(path)?.trim(),
    )
    .map(([path]) => path)
    .sort(comparePaths);
}

function getMessage(catalog: Catalog, path: string): string {
  const message = path.split(".").reduce<unknown>((value, key) => {
    return typeof value === "object" && value != null && !Array.isArray(value)
      ? (value as Catalog)[key]
      : undefined;
  }, catalog);

  if (typeof message !== "string") {
    throw new Error(`Expected ${path} to resolve to a message.`);
  }

  return message;
}

describe("locale catalogs", () => {
  it("keeps the legacy-continuity Russian key set frozen", () => {
    const enKeys = collectPaths(en).sort(comparePaths);
    const ukKeys = collectPaths(uk).sort(comparePaths);
    const ruKeys = collectPaths(ru).sort(comparePaths);
    const ruLeaves = collectLeafPairs(ru).sort(([left], [right]) =>
      comparePaths(left, right),
    );

    expect(ukKeys).toEqual(enKeys);
    expect(
      crypto.createHash("sha256").update(JSON.stringify(ruKeys)).digest("hex"),
    ).toBe(LEGACY_CONTINUITY_RU_KEY_SET_SHA256);
    expect(ruKeys).toHaveLength(LEGACY_CONTINUITY_RU_KEY_COUNT);
    expect(
      crypto.createHash("sha256").update(JSON.stringify(ruLeaves)).digest("hex"),
    ).toBe(LEGACY_CONTINUITY_RU_LEAF_VALUE_SHA256);
  });

  it("justifies exactly every active non-ICU count-message identity", () => {
    const activeNonIcuCountPaths = [...new Set(
      [en, uk]
        .flatMap((catalog) => collectCountMessages(catalog))
        .filter(([, message]) => !isPluralMessage(message))
        .map(([path]) => path),
    )].sort(comparePaths);

    expect([...COUNT_MESSAGE_ALLOWLIST.keys()].sort(comparePaths)).toEqual(
      activeNonIcuCountPaths,
    );
    for (const [path, reason] of COUNT_MESSAGE_ALLOWLIST) {
      expect(reason.trim(), `${path} needs a non-empty exemption reason`).not.toBe("");
    }
  });

  it.each([
    ["en", en],
    ["uk", uk],
  ] as const)(
    "requires every active %s count message to be ICU plural or justified",
    (_locale, catalog) => {
      expect(collectUnjustifiedCountMessages(catalog)).toEqual([]);
    },
  );

  it.each([
    [
      "pages.dashboard.narrativeAttentionBody",
      { blocked: "7" },
      ["1 active run and 7 blocked packets need immediate review posture.", "2 active runs and 7 blocked packets need immediate review posture."],
      ["1 активний запуск і 7 заблокованих packet уже вимагає review posture.", "2 активні запуски і 7 заблокованих packet уже вимагають review posture.", "5 активних запусків і 7 заблокованих packet уже вимагають review posture."],
      {
        grouped: "Активні запуски: 1 001; 7 заблокованих packet уже вимагають review posture.",
        unavailable: "Активні запуски: unavailable; 7 заблокованих packet уже вимагають review posture.",
      },
    ],
    [
      "pages.dashboard.narrativeQueueBody",
      {},
      ["1 decision-bearing run is ready to open from the fleet.", "2 decision-bearing runs are ready to open from the fleet."],
      ["1 decision-bearing запуск уже готовий відкриватися з fleet.", "2 decision-bearing запуски вже готові відкриватися з fleet.", "5 decision-bearing запусків уже готові відкриватися з fleet."],
      {
        grouped: "Decision-bearing запуски, готові до відкриття з fleet: 1 001.",
        unavailable: "Decision-bearing запуски, готові до відкриття з fleet: unavailable.",
      },
    ],
    [
      "pages.runs.planMatches",
      {},
      ["1 matched need", "2 matched needs"],
      ["1 пов'язаний need", "2 пов'язані needs", "5 пов'язаних needs"],
      {
        grouped: "Пов'язані needs: 1 001",
        unavailable: "Пов'язані needs: unavailable",
      },
    ],
    [
      "controlJob.scientistEvents",
      {},
      ["1 event", "2 events"],
      ["1 подія", "2 події", "5 подій"],
      {
        grouped: "Події: 1 001",
        unavailable: "Події: unavailable",
      },
    ],
    [
      "pages.composer.curatedConstraints",
      {},
      ["1 curated constraint", "2 curated constraints"],
      ["1 curated constraint", "2 curated constraints", "5 curated constraints"],
      undefined,
    ],
    [
      "pages.composer.capabilitiesVisible",
      {},
      ["1 runtime capability visible", "2 runtime capabilities visible"],
      ["1 runtime capability видно", "2 runtime capabilities видно", "5 runtime capabilities видно"],
      undefined,
    ],
    [
      "pages.evidence.totalProfiles",
      {},
      ["1 total curated profile", "2 total curated profiles"],
      ["1 curated profile загалом", "2 curated profiles загалом", "5 curated profiles загалом"],
      undefined,
    ],
    [
      "panels.agentPipeline.variants",
      {},
      ["1 variant", "2 variants"],
      ["1 variant", "2 variants", "5 variants"],
      undefined,
    ],
  ] as const)(
    "formats repaired plural message %s with locale-specific count forms",
    (path, values, englishExpected, ukrainianExpected, ukrainianOtherWitness) => {
      expect(
        [1, 2].map((count) =>
          formatIcuMessage(getMessage(en, path), "en", { ...values, count }),
        ),
      ).toEqual(englishExpected);
      expect(
        [1, 2, 5].map((count) =>
          formatIcuMessage(getMessage(uk, path), "uk", { ...values, count }),
        ),
      ).toEqual(ukrainianExpected);

      if (ukrainianOtherWitness) {
        expect(
          formatIcuMessage(getMessage(uk, path), "uk", {
            ...values,
            count: new Intl.NumberFormat("uk-UA").format(1001),
          }),
        ).toBe(ukrainianOtherWitness.grouped);
        expect(
          formatIcuMessage(getMessage(uk, path), "uk", {
            ...values,
            count: "unavailable",
          }),
        ).toBe(ukrainianOtherWitness.unavailable);
      }
    },
  );

  it("rejects omitted and whitespace-only count-message exemption reasons", () => {
    const message = { synthetic: { count: "{count} synthetic records" } };

    expect(collectUnjustifiedCountMessages(message)).toEqual(["synthetic.count"]);
    expect(
      collectUnjustifiedCountMessages(
        message,
        new Map([["synthetic.count", "   "]]),
      ),
    ).toEqual(["synthetic.count"]);
  });

  it("rejects a new active count-message identity until it has a reason", () => {
    const message = { synthetic: { newCount: "{count} new records" } };

    expect(collectUnjustifiedCountMessages(message)).toEqual(["synthetic.newCount"]);
    expect(
      collectUnjustifiedCountMessages(
        message,
        new Map([["synthetic.newCount", "Synthetic metric with an invariant label."]]),
      ),
    ).toEqual([]);
  });

  it("rejects malformed ICU plural syntax despite an exemption reason", () => {
    const message = { synthetic: { malformed: "{count, plural,}" } };
    const exemptions = new Map([
      ["synthetic.malformed", "Synthetic malformed-ICU admission probe."],
    ]);

    expect(collectUnjustifiedCountMessages(message, exemptions)).toEqual([
      "synthetic.malformed",
    ]);
  });
});
