import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import {
  DEFAULT_PRODUCER_READS,
  governanceTabPath,
  mintedValueFindings,
  mountGraphCensus,
  panelEmissionMode,
  readinessPanelPath,
  refusalFindings,
  renderedLabelKeys,
  runDetailLayoutPath,
  SANCTIONED_REFUSAL_KEY,
  scientificPanelPath,
  sourceRoot,
} from "@/test/contracts/successorAuthorityAnalyzer";

/**
 * DS16-C02 — the successor containment gate, over the REAL panel files.
 *
 * `DS4-C23` proved "this panel cannot emit anything" by pinning constant
 * emission. This gate proves "this panel cannot emit anything it did not
 * receive", which is what DS16 needs, because C05 must be able to render a
 * producer value and the ancestor forbids rendering anything at all.
 *
 * THE VACUITY TRAP, AND HOW THIS GATE ANSWERS IT
 * ----------------------------------------------
 * Both panels are 11-line stubs. "Emits nothing it did not receive" is
 * trivially true of a panel that emits nothing, so run against today's sources
 * this gate passes FOR THE WRONG REASON. Two things are done about that rather
 * than commenting on it:
 *
 *   1. The gate STATES the reason. `panelEmissionMode` is asserted to be
 *      `contained` for both panels, so the record says the property currently
 *      holds vacuously. When C05 wires the producer the mode becomes `bound`
 *      and that assertion must be updated deliberately — it cannot drift.
 *   2. Every property below is proved RED against a deliberately violating
 *      shape built from the real panel source. A gate that has never failed is
 *      not a gate (`P29`).
 *
 * RELATIONSHIP TO THE ANCESTOR
 * ----------------------------
 * `readinessScientificContainment.test.ts` stays untouched and green. It
 * asserts `calls === 0`, so the moment C05 wires a hook it goes RED; it
 * therefore retires in the SAME change that rewires the panels (C11), not
 * before and not after. Until then the two gates coexist deliberately: the
 * ancestor guards today's stub, this guards the shape C05 will create. The
 * mount-graph walk below duplicates the ancestor's by necessity — the ancestor
 * exports none of its internals and may not be edited — and that duplication
 * ends when the ancestor retires (`P28`: strangle, do not fork).
 */

const readinessSource = fs.readFileSync(readinessPanelPath, "utf8");
const scientificSource = fs.readFileSync(scientificPanelPath, "utf8");
const layoutSource = fs.readFileSync(runDetailLayoutPath, "utf8");

const PANELS = [
  ["PublicSectorReadinessPanel", readinessSource],
  ["ScientificDepthPanel", scientificSource],
] as const;

const siblingWrapperPath = path.join(
  sourceRoot,
  "features/runs/components/ReadinessSiblingWrapper.tsx",
);

describe("DS16-C02 successor containment gate", () => {
  it("states which reason it is passing for, and it is no longer the vacuous one", () => {
    // THE FLIP. Until C05 both panels were `contained` and this gate passed for the
    // vacuous reason — "emits nothing it did not receive" is trivially true of a panel
    // that emits nothing. Both are now `bound`: they read a producer and render what it
    // served. The property is the same; what changed is that it now has something to say.
    for (const [name, source] of PANELS) {
      expect(panelEmissionMode(source, name), `${name} mode`).toBe("bound");
    }
    expect(DEFAULT_PRODUCER_READS).toEqual(["useI18n", "useRunAuthorityValues"]);
  });

  it("proves no locally minted value on both real panels, and fails on each minting class", () => {
    for (const [name, source] of PANELS) {
      expect(mintedValueFindings(source, name), `${name} clean`).toEqual([]);
    }

    // Each violating shape is built from the REAL readiness source, so the gate
    // is exercised against the file it guards rather than against a fixture.
    const violations: Array<[string, string, readonly string[]]> = [
      [
        "threshold",
        readinessSource.replace(
          '{t("common.unavailable")}',
          "{summary.coverage > summary.floor}",
        ),
        ["local-threshold", "untraceable-render:child"],
      ],
      [
        "arithmetic",
        readinessSource.replace(
          '{t("common.unavailable")}',
          "{summary.coverage * summary.weight}",
        ),
        ["local-arithmetic", "untraceable-render:child"],
      ],
      [
        "regex-over-dwell-state",
        readinessSource.replace(
          "const { t } = useI18n();",
          "const { t } = useI18n();\n  const dwell = /blocked/.test(window.name);",
        ),
        [
          "computed-producer-argument:/blocked/.test",
          "local-regex",
          "unsanctioned-producer-read:/blocked/.test",
        ],
      ],
      [
        "inline-call",
        readinessSource.replace(
          '{t("common.unavailable")}',
          "{composeReadiness(summary)}",
        ),
        [
          "local-call-in-render:composeReadiness",
          "unbound-call:composeReadiness",
        ],
      ],
      [
        "literal-value",
        readinessSource.replace('{t("common.unavailable")}', "{0.87}"),
        ["literal-value-rendered:child"],
      ],
    ];

    for (const [label, corrupted, expected] of violations) {
      const findings = mintedValueFindings(corrupted, "PublicSectorReadinessPanel");
      expect(findings, `${label} must be caught`).not.toEqual([]);
      expect(findings, `${label} findings`).toEqual(expected);
    }
  });

  it("requires a typed refusal and refuses blanks, zeroes and inferences", () => {
    for (const [name, source] of PANELS) {
      expect(refusalFindings(source, name), `${name} refusal`).toEqual([]);
      expect(renderedLabelKeys(source, name)).toContain(SANCTIONED_REFUSAL_KEY);
    }

    // Blanks are refused in every slot, bound or not: null, zero and an empty
    // expression container are each caught where the refusal used to render.
    for (const blank of ["{null}", "{0}", "{}"]) {
      expect(
        refusalFindings(
          readinessSource.replace('{t("common.unavailable")}', blank),
          "PublicSectorReadinessPanel",
        ),
        `blank slot ${blank}`,
      ).toEqual(["blank-emission:child"]);
    }

    // `refusal-missing` is a CONTAINED-mode property and did not disappear when the
    // panels went bound — it is checked here against a contained control, because a
    // bound panel's refusal arrives from the producer at runtime and is carried by
    // the behavioural assertion in ds16BoundPanelBehaviour.test.tsx instead.
    const containedWithoutRefusal = `import { useI18n } from "@/shared/i18n/LocaleProvider";

export function PublicSectorReadinessPanel() {
  const { t } = useI18n();

  return <section data-testid="public-sector-readiness-panel">{t("common.other")}</section>;
}
`;
    expect(panelEmissionMode(containedWithoutRefusal, "PublicSectorReadinessPanel")).toBe(
      "contained",
    );
    expect(
      refusalFindings(containedWithoutRefusal, "PublicSectorReadinessPanel"),
    ).toEqual(["refusal-missing"]);
  });

  it("pins the label-key inventory so a value-bearing key cannot arrive silently", () => {
    // GAP 2's mitigation. Both panels render exactly one key today.
    expect(renderedLabelKeys(readinessSource, "PublicSectorReadinessPanel")).toEqual(
      [SANCTIONED_REFUSAL_KEY],
    );
    expect(renderedLabelKeys(scientificSource, "ScientificDepthPanel")).toEqual([
      SANCTIONED_REFUSAL_KEY,
    ]);

    // A key whose IDENTITY asserts a value changes the inventory, so it cannot
    // enter without editing this expectation — the channel is watched even
    // though it cannot be closed structurally.
    expect(
      renderedLabelKeys(
        readinessSource.replace(
          '{t("common.unavailable")}',
          '{t("common.unavailable")}\n      {t("readiness.high")}',
        ),
        "PublicSectorReadinessPanel",
      ),
    ).toEqual([SANCTIONED_REFUSAL_KEY, "readiness.high"]);
  });

  it("closes label-key SELECTION: a key may not be chosen by local computation", () => {
    // GAP 2's structural half. Every route from a computed predicate to a key
    // is already a minting construct, and each is verified rather than assumed.
    const selections: Array<[string, string, readonly string[]]> = [
      [
        "conditional-key",
        readinessSource.replace(
          '{t("common.unavailable")}',
          '{ready ? t("readiness.high") : t("readiness.low")}',
        ),
        ["local-conditional:child", "unbound-call:t"],
      ],
      [
        "template-key",
        readinessSource.replace(
          '{t("common.unavailable")}',
          "{t(`readiness.${summary.tier}`)}",
        ),
        ["local-call-in-render:t", "unbound-call:t"],
      ],
      [
        "producer-supplied-key",
        readinessSource.replace(
          '{t("common.unavailable")}',
          "{t(summary.readinessKey)}",
        ),
        ["local-call-in-render:t", "unbound-call:t"],
      ],
      [
        "threshold-selected-key",
        readinessSource.replace(
          "const { t } = useI18n();",
          "const { t } = useI18n();\n  const key = summary.score >= summary.floor;",
        ),
        ["local-threshold"],
      ],
    ];

    for (const [label, corrupted, expected] of selections) {
      const findings = mintedValueFindings(corrupted, "PublicSectorReadinessPanel");
      expect(findings, `${label} must be caught`).not.toEqual([]);
      expect(findings, `${label} findings`).toEqual(expected);
    }
  });

  it("censuses the production mount graph and refuses a minted mount prop", () => {
    const census = mountGraphCensus();

    // Re-measured, not inherited: three production mounts, all propless.
    expect(census.findings).toEqual([]);
    expect(census.mounts).toHaveLength(3);
    // C02 generalized the ancestor's "zero mount props" to "no MINTED mount props",
    // and C05 is where that distinction pays: every mount now passes `runId`, which is
    // traceable producer input, while a computed prop is still refused below.
    expect(
      census.mounts.every((mount) => mount.props === 1),
      "every production mount passes exactly runId",
    ).toBe(true);
    expect(
      census.mounts
        .map((mount) => `${mount.file}:${mount.name}`)
        .sort(),
    ).toEqual([
      "features/runs/routes/RunDetailLayout.tsx:PublicSectorReadinessPanel",
      "features/runs/routes/RunDetailLayout.tsx:ScientificDepthPanel",
      "features/runs/routes/tabs/GovernanceTab.tsx:PublicSectorReadinessPanel",
    ]);

    // The harness at src/test/contracts/quantityDecisionProducerHarness.tsx also
    // mounts the readiness panel and is NOT a `*.test.tsx` file. It is excluded
    // by REACHABILITY from the two production roots, not by its name — a census
    // filtering on filename alone would report four mounts and be wrong.
    expect(
      census.mounts.some((mount) => mount.file.startsWith("test/")),
      "the unreachable harness mount must not be counted",
    ).toBe(false);

    // A value minted one file over, at the mount site.
    expect(
      mountGraphCensus({
        [runDetailLayoutPath]: layoutSource.replace(
          "<PublicSectorReadinessPanel runId={runId} />",
          "<PublicSectorReadinessPanel runId={runId} score={summary.coverage * 0.6} />",
        ),
      }).findings,
    ).toEqual([
      "minted-mount-prop:features/runs/routes/RunDetailLayout.tsx:score:arithmetic",
      "minted-mount-prop:features/runs/routes/RunDetailLayout.tsx:score:literal",
    ]);

    // A spread at the mount site hides whatever it carries.
    expect(
      mountGraphCensus({
        [runDetailLayoutPath]: layoutSource.replace(
          "<PublicSectorReadinessPanel runId={runId} />",
          "<PublicSectorReadinessPanel runId={runId} {...composed} />",
        ),
      }).findings,
    ).toEqual([
      "mount-prop-spread:features/runs/routes/RunDetailLayout.tsx:PublicSectorReadinessPanel",
    ]);
  });

  it("catches a fourth mount smuggled in through a reachable wrapper", () => {
    const census = mountGraphCensus({
      [runDetailLayoutPath]: layoutSource
        .replace(
          'import { RunBreadcrumbs } from "@/features/runs/components/RunBreadcrumbs";',
          'import { RunBreadcrumbs } from "@/features/runs/components/RunBreadcrumbs";\nimport { ReadinessSiblingWrapper } from "@/features/runs/components/ReadinessSiblingWrapper";',
        )
        .replace(
          "<ScientificDepthPanel runId={runId} />",
          "<ReadinessSiblingWrapper />\n                <ScientificDepthPanel runId={runId} />",
        ),
      [siblingWrapperPath]: `import { PublicSectorReadinessPanel } from "@/features/runs/components/PublicSectorReadinessPanel";

export function ReadinessSiblingWrapper() {
  return <PublicSectorReadinessPanel score={1 + 1} />;
}
`,
    });

    expect(census.mounts).toHaveLength(4);
    expect(census.findings).toEqual([
      "minted-mount-prop:features/runs/components/ReadinessSiblingWrapper.tsx:score:arithmetic",
      "minted-mount-prop:features/runs/components/ReadinessSiblingWrapper.tsx:score:literal",
    ]);
  });

  it("fails when the property is removed but every marker remains (P29)", () => {
    // Keep the sanctioned import, the sanctioned binding, the section, the
    // testid and the refusal label — remove only the property, by minting a
    // composite beside the refusal that is still rendered.
    const markersIntact = readinessSource.replace(
      '{t("common.unavailable")}',
      '{t("common.unavailable")}\n      {summary.coverage * 0.6 + summary.dwell * 0.4}',
    );

    for (const marker of [
      'import { useI18n } from "@/shared/i18n/LocaleProvider";',
      "const { t } = useI18n();",
      'data-testid="public-sector-readiness-panel"',
      '{t("common.unavailable")}',
    ]) {
      expect(markersIntact, `marker preserved: ${marker}`).toContain(marker);
    }
    // The refusal is still rendered and the label inventory is unchanged — only
    // the property is gone.
    expect(
      renderedLabelKeys(markersIntact, "PublicSectorReadinessPanel"),
    ).toEqual([SANCTIONED_REFUSAL_KEY]);
    expect(refusalFindings(markersIntact, "PublicSectorReadinessPanel")).toEqual(
      [],
    );

    expect(
      mintedValueFindings(markersIntact, "PublicSectorReadinessPanel"),
    ).toEqual(["local-arithmetic", "untraceable-render:child"]);
  });

  it("proves the ancestor is strangled, not merely superseded (P28)", () => {
    // C05 retires `readinessScientificContainment.test.ts` in the same change that
    // rewires the panels — not before, because it was the only gate until now, and not
    // after, because it asserts `calls === 0` and goes RED the moment a hook is wired.
    const ancestor = path.join(
      sourceRoot,
      "features/runs/components/readinessScientificContainment.test.ts",
    );
    expect(fs.existsSync(ancestor), "the retired witness must be gone").toBe(false);

    // A successor closes only when the old owner path is proven strangled. The test is
    // whether anything still REACHES for the witness — imports it, or reads it off disk
    // — not whether its name still appears: the successor's own prose names its ancestor
    // deliberately, and erasing that would lose the lineage rather than prove anything.
    const componentsDir = path.join(sourceRoot, "features/runs/components");
    const reachers = fs
      .readdirSync(componentsDir)
      .filter((file) => file.endsWith(".ts") || file.endsWith(".tsx"))
      .filter((file) =>
        fs
          .readFileSync(path.join(componentsDir, file), "utf8")
          .split("\n")
          .some(
            (line) =>
              line.includes("readinessScientificContainment") &&
              (/\bimport\b/u.test(line) ||
                /\brequire\(/u.test(line) ||
                /readFileSync|existsSync/u.test(line)),
          ),
      );
    expect(reachers, "nothing may still load the retired witness").toEqual([]);

    // And the properties it carried are carried here: the mount census it owned is
    // asserted above, and the emission property it owned is superseded by
    // `mintedValueFindings`, which permits a producer value and refuses a minted one.
    expect(mountGraphCensus().mounts).toHaveLength(3);
    expect(fs.existsSync(governanceTabPath)).toBe(true);
  });
});
