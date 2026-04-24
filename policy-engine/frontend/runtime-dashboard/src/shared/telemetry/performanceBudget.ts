/**
 * Performance budget enforcement.
 *
 * Monitors Core Web Vitals and bundle chunk sizes against defined budgets.
 * Reports violations to the telemetry pipeline in production and
 * logs warnings in development.
 */

import { trackTelemetry } from "@/shared/telemetry/pipeline";

export type PerformanceBudget = {
  /** First Contentful Paint (ms). */
  fcp: number;
  /** Largest Contentful Paint (ms). */
  lcp: number;
  /** Time to Interactive (ms). */
  tti: number;
  /** Cumulative Layout Shift. */
  cls: number;
  /** Interaction to Next Paint (ms). */
  inp: number;
  /** Initial bundle size gzipped (KB). */
  initialBundleKB: number;
  /** Total session bundle size gzipped (KB). */
  totalSessionKB: number;
  /** SSE render latency (ms). */
  sseRenderMs: number;
};

export const DEFAULT_BUDGETS: PerformanceBudget = {
  fcp: 1200,
  lcp: 2000,
  tti: 3000,
  cls: 0.05,
  inp: 200,
  initialBundleKB: 250,
  totalSessionKB: 500,
  sseRenderMs: 100,
};

export type BudgetViolation = {
  actual: number;
  budget: number;
  metric: string;
  severity: "critical" | "warning";
};

/**
 * Check a single metric against its budget.
 * Returns a violation if the metric exceeds the budget.
 */
export function checkBudget(
  metric: string,
  actual: number,
  budget: number,
  criticalMultiplier = 1.5,
): BudgetViolation | null {
  if (actual <= budget) return null;

  return {
    actual,
    budget,
    metric,
    severity: actual > budget * criticalMultiplier ? "critical" : "warning",
  };
}

/**
 * Report a performance budget violation to the telemetry pipeline.
 */
export function reportBudgetViolation(violation: BudgetViolation): void {
  if (import.meta.env.DEV) {
    const style =
      violation.severity === "critical"
        ? "color: #e74c3c; font-weight: bold"
        : "color: #e67e22";
    console.warn(
      `%c[perf-budget] ${violation.severity.toUpperCase()}: ${violation.metric} = ${violation.actual} (budget: ${violation.budget})`,
      style,
    );
  }

  trackTelemetry("perf.budget.violation", {
    actual: violation.actual,
    budget: violation.budget,
    metric: violation.metric,
    severity: violation.severity,
  });
}

/**
 * Monitor navigation timing and report budget violations.
 * Call once after the page has finished loading.
 */
export function auditNavigationBudgets(
  budgets: PerformanceBudget = DEFAULT_BUDGETS,
): BudgetViolation[] {
  if (typeof performance === "undefined") return [];

  const navEntry = performance.getEntriesByType("navigation")[0] as
    | PerformanceNavigationTiming
    | undefined;
  if (!navEntry) return [];

  const violations: BudgetViolation[] = [];

  const tti = navEntry.domInteractive;
  const ttiViolation = checkBudget("tti", tti, budgets.tti);
  if (ttiViolation) violations.push(ttiViolation);

  // Check resource transfer sizes for bundle budgets
  const resources = performance.getEntriesByType(
    "resource",
  ) as PerformanceResourceTiming[];
  const jsResources = resources.filter(
    (r) => r.initiatorType === "script" && r.transferSize > 0,
  );
  const totalJsKB =
    jsResources.reduce((sum, r) => sum + r.transferSize, 0) / 1024;
  const bundleViolation = checkBudget(
    "totalSessionKB",
    totalJsKB,
    budgets.totalSessionKB,
  );
  if (bundleViolation) violations.push(bundleViolation);

  for (const v of violations) {
    reportBudgetViolation(v);
  }

  return violations;
}
