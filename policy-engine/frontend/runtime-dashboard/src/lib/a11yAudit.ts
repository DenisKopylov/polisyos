/**
 * Runtime accessibility audit utility (dev-only).
 *
 * Runs axe-core against the live DOM and reports violations to the console.
 * Only loaded in development mode via dynamic import.
 */

type A11yViolation = {
  description: string;
  help: string;
  helpUrl: string;
  id: string;
  impact: "critical" | "minor" | "moderate" | "serious" | null;
  nodes: Array<{ html: string; target: string[] }>;
};

type A11yAuditResult = {
  passes: number;
  violations: A11yViolation[];
};

let auditScheduled = false;

/**
 * Schedule an accessibility audit on the current page.
 * Debounced — only runs once per animation frame.
 * Results are logged to the console in dev mode.
 */
export function scheduleA11yAudit(): void {
  if (auditScheduled || !import.meta.env.DEV) return;
  auditScheduled = true;

  requestAnimationFrame(() => {
    void (async () => {
      auditScheduled = false;
      try {
        const result = await runA11yAudit();
        if (result.violations.length === 0) return;

        console.warn(
          `[a11y] ${result.violations.length} violation(s) found across ${result.passes} passes.`,
        );
        for (const violation of result.violations) {
          console.warn(
            [
              `[a11y] ${violation.impact?.toUpperCase() ?? "UNKNOWN"} ${violation.help}`,
              `rule=${violation.id}`,
              `docs=${violation.helpUrl}`,
              ...violation.nodes.slice(0, 5).map(
                (node, index) =>
                  `node${index + 1}=${node.target.join(" > ")} :: ${node.html}`,
              ),
              violation.nodes.length > 5
                ? `additionalNodes=${violation.nodes.length - 5}`
                : null,
            ]
              .filter(Boolean)
              .join("\n"),
          );
        }
      } catch {
        // axe-core not available — skip
      }
    })();
  });
}

async function runA11yAudit(): Promise<A11yAuditResult> {
  const axe = await import("axe-core");
  const results = await axe.default.run(document.body, {
    runOnly: {
      type: "tag",
      values: ["wcag2a", "wcag2aa", "wcag22aa", "best-practice"],
    },
  });
  return {
    passes: results.passes.length,
    violations: results.violations.map((v) => ({
      description: v.description,
      help: v.help,
      helpUrl: v.helpUrl,
      id: v.id,
      impact: v.impact as A11yViolation["impact"],
      nodes: v.nodes.map((n) => ({
        html: n.html,
        target: n.target.map(String),
      })),
    })),
  };
}
