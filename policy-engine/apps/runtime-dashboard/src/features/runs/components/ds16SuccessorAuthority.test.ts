import fs from "node:fs";
import { describe, expect, it } from "vitest";

import {
  mintedValueFindings,
  readinessPanelPath,
  scientificPanelPath,
} from "@/test/contracts/successorAuthorityAnalyzer";

/**
 * DS16-C01 negative 4 (`P05`/`P15`, with `P29` and `P38`) — the successor
 * authority negative: a panel that emits a value the producer did not supply
 * fails, BY CONSTRUCTION and not by inspection.
 *
 * Its ancestor, `readinessScientificContainment.test.ts`, proves CONSTANT
 * emission: `expressions === 0`, `components === 0`, `calls === 0`, zero
 * parameters, zero mount props. `DS4-C23` proved "this panel cannot emit
 * anything". DS16 must prove "this panel cannot emit anything it did not
 * receive", which is strictly harder in the direction that matters and
 * strictly weaker in the direction that DS16 exists to open.
 *
 * NAMED DIVERGENCE FROM THE ANCESTOR (`P38` — say where property and
 * implementation part company, do not assume they coincide):
 *
 *  (a) The successor PERMITS `{composition.readinessScore}` — a value read
 *      straight off a sanctioned producer. The ancestor REJECTS it, because
 *      `expressions === 0` admits nothing but the constant. This divergence is
 *      the entire reason C02 exists; a successor that did not diverge here
 *      would just be the ancestor.
 *  (b) The successor PERMITS a label under a different i18n key. The ancestor
 *      pins the exact key `common.unavailable`, which it can do only while the
 *      panel is constant. A bound panel needs labels, and a label is not a
 *      value. The gate guards the VALUE path.
 *
 * Therefore the successor is NOT a strict superset of the ancestor, and it
 * cannot be: the ancestor's catch-set contains the very producer bindings this
 * slice exists to permit. The honest formulation, verified below, is that the
 * successor catches every ancestor corruption THAT MINTS A VALUE, and adds the
 * case no structural constant-emission gate can see — local computation
 * arriving through an otherwise entirely legitimate producer field.
 *
 * NOT CARRIED HERE: the ancestor's cross-file mount census (reachability, mount
 * counts, zero mount props). That is a mount-graph property, not a value-minting
 * property, and C02 carries it forward unchanged; this analyzer is single-source
 * by design and case 11 below is recorded as out of scope rather than silently
 * dropped.
 */

/**
 * The analyzer itself now lives in `@/test/contracts/successorAuthorityAnalyzer`
 * so that C02's production gate consumes the SAME function rather than a second
 * copy of it (`P27`). It moved verbatim; every expectation below is unchanged
 * from the run that first proved them RED.
 */

const readinessSource = fs.readFileSync(readinessPanelPath, "utf8");
const scientificSource = fs.readFileSync(scientificPanelPath, "utf8");

/** The shape C02 is expected to land: a producer read, rendered untouched. */
const BOUND_PRODUCER_PANEL = `import { useI18n } from "@/shared/i18n/LocaleProvider";
import { useReadinessComposition } from "@/features/runs/producers/useReadinessComposition";

export function PublicSectorReadinessPanel() {
  const { t } = useI18n();
  const { composition } = useReadinessComposition();

  return (
    <section data-testid="public-sector-readiness-panel">
      {composition.readinessScore}
      {composition.refusal}
      {t("readiness.caption")}
    </section>
  );
}
`;

/**
 * THE CRUX. Identical imports, identical sanctioned producer read, identical
 * legitimate fields — and a weighted composite computed on the glass. This is
 * exactly the `DS4-C23` sin (readiness composed from local thresholds and dwell
 * state) surviving inside an otherwise blameless producer binding, and it is
 * the case a constant-emission gate cannot distinguish from the compliant panel
 * once `expressions === 0` is relaxed to let producer values through.
 */
const COMPUTING_PRODUCER_PANEL = `import { useI18n } from "@/shared/i18n/LocaleProvider";
import { useReadinessComposition } from "@/features/runs/producers/useReadinessComposition";

export function PublicSectorReadinessPanel() {
  const { t } = useI18n();
  const { composition } = useReadinessComposition();

  return (
    <section data-testid="public-sector-readiness-panel">
      {composition.coverage * 0.6 + composition.dwell * 0.4}
      {t("readiness.caption")}
    </section>
  );
}
`;

/** The same minting through a threshold rather than arithmetic. */
const THRESHOLD_PRODUCER_PANEL = `import { useI18n } from "@/shared/i18n/LocaleProvider";
import { useReadinessComposition } from "@/features/runs/producers/useReadinessComposition";

export function PublicSectorReadinessPanel() {
  const { t } = useI18n();
  const { composition } = useReadinessComposition();

  return (
    <section data-testid="public-sector-readiness-panel">
      {composition.coverage >= composition.floor ? t("ready") : t("blocked")}
    </section>
  );
}
`;

const BOUND_PRODUCER_READS = ["useI18n", "useReadinessComposition"] as const;

describe("DS16-C01 negative 4 — successor authority", () => {
  it("holds on both panels as they stand, and reports the property it proves", () => {
    expect(mintedValueFindings(readinessSource, "PublicSectorReadinessPanel")).toEqual(
      [],
    );
    expect(mintedValueFindings(scientificSource, "ScientificDepthPanel")).toEqual([]);
  });

  it("catches a locally computed value arriving through a legitimate producer field", () => {
    // The compliant bound panel is green ONLY once its producer read is
    // sanctioned — proving the gate is not simply passing everything.
    expect(
      mintedValueFindings(
        BOUND_PRODUCER_PANEL,
        "PublicSectorReadinessPanel",
        BOUND_PRODUCER_READS,
      ),
    ).toEqual([]);

    // Same producer, same sanction, same legitimate fields — and the composite
    // is caught. This is the negative C02's successor gate must satisfy.
    expect(
      mintedValueFindings(
        COMPUTING_PRODUCER_PANEL,
        "PublicSectorReadinessPanel",
        BOUND_PRODUCER_READS,
      ),
    ).toEqual(["local-arithmetic", "untraceable-render:child"]);

    expect(
      mintedValueFindings(
        THRESHOLD_PRODUCER_PANEL,
        "PublicSectorReadinessPanel",
        BOUND_PRODUCER_READS,
      ),
      // The branch labels are swept too: a call inside a rejected conditional
      // is never reached by the label sanction, so it stays accounted for.
    ).toEqual(["local-conditional:child", "local-threshold", "unbound-call:t"]);
  });

  it("keeps the unsanctioned producer read closed", () => {
    // Without the sanction, the very same compliant panel is refused: a panel
    // may not reach for an arbitrary hook and call the result a producer.
    expect(
      mintedValueFindings(BOUND_PRODUCER_PANEL, "PublicSectorReadinessPanel"),
    ).toEqual(["unsanctioned-producer-read:useReadinessComposition"]);
  });

  it("catches every ancestor corruption that mints a value", () => {
    const cases: Array<[string, string, string, readonly string[]]> = [
      [
        "direct-helper",
        readinessSource.replace(
          "const { t } = useI18n();",
          "const { t } = useI18n();\n  const value = helper();",
        ),
        "PublicSectorReadinessPanel",
        ["unsanctioned-producer-read:helper"],
      ],
      [
        "aliased-i18n-import",
        scientificSource.replace("{ useI18n }", "{ useI18n as i18n }"),
        "ScientificDepthPanel",
        ["unimported-producer-read:useI18n"],
      ],
      [
        "component-child",
        scientificSource.replace('{t("common.unavailable")}', "<Unavailable />"),
        "ScientificDepthPanel",
        ["opaque-component-child:Unavailable"],
      ],
      [
        "literal-text",
        scientificSource.replace(
          '{t("common.unavailable")}',
          '{t("common.unavailable")} approved',
        ),
        "ScientificDepthPanel",
        ["literal-text-rendered"],
      ],
      [
        "renamed-binding",
        scientificSource.replace(
          "const { t } = useI18n();",
          "const { arbitrary: t } = useI18n();",
        ),
        "ScientificDepthPanel",
        ["renamed-producer-binding"],
      ],
      [
        "control-flow",
        scientificSource.replace(
          "  return (",
          "  if (window.name) return null;\n\n  return (",
        ),
        "ScientificDepthPanel",
        ["local-control-flow"],
      ],
      [
        "off-jsx-call",
        scientificSource.replace(
          "const { t } = useI18n();",
          'const { t } = useI18n();\n  t("common.unavailable");',
        ),
        "ScientificDepthPanel",
        ["unbound-call:t"],
      ],
      [
        "prop-spread",
        readinessSource.replace("<section", "<section {...props}"),
        "PublicSectorReadinessPanel",
        ["prop-spread"],
      ],
      [
        "conditional-render",
        scientificSource.replace(
          '{t("common.unavailable")}',
          '{ready ? t("common.unavailable") : "waiting"}',
        ),
        "ScientificDepthPanel",
        ["local-conditional:child", "unbound-call:t"],
      ],
    ];

    for (const [name, corrupted, component, expected] of cases) {
      const findings = mintedValueFindings(corrupted, component);
      expect(findings, `${name} must be caught`).not.toEqual([]);
      expect(findings, `${name} findings`).toEqual(expected);
    }
  });

  it("names the two cases where it diverges from the ancestor rather than hiding them", () => {
    // (a) A producer value is PERMITTED here and forbidden by the ancestor.
    expect(
      mintedValueFindings(
        BOUND_PRODUCER_PANEL,
        "PublicSectorReadinessPanel",
        BOUND_PRODUCER_READS,
      ),
    ).toEqual([]);

    // (b) A different i18n key is a label change, not a minted value. The
    // ancestor rejects it because it pins the constant; the successor does not.
    expect(
      mintedValueFindings(
        scientificSource.replace("common.unavailable", "common.unknown"),
        "ScientificDepthPanel",
      ),
    ).toEqual([]);
  });

  it("fails when the property is removed but the markers remain (P29)", () => {
    // The `P29` probe: keep every marker the compliant panel carries — the
    // sanctioned import, the sanctioned binding, the section, the testid, the
    // i18n label — and remove only the property, by minting the value inline.
    const markersIntact = readinessSource.replace(
      '{t("common.unavailable")}',
      '{t("common.unavailable")}\n      {0.87}',
    );

    expect(markersIntact).toContain('import { useI18n } from "@/shared/i18n/LocaleProvider";');
    expect(markersIntact).toContain("const { t } = useI18n();");
    expect(markersIntact).toContain('data-testid="public-sector-readiness-panel"');
    expect(markersIntact).toContain('{t("common.unavailable")}');

    expect(
      mintedValueFindings(markersIntact, "PublicSectorReadinessPanel"),
    ).toEqual(["literal-value-rendered:child"]);
  });
});
