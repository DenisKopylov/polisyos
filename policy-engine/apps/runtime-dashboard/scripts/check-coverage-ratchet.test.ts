// @vitest-environment node
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";

const dashboardRoot = fileURLToPath(new URL("..", import.meta.url));
const scratchRoot = path.resolve(
  dashboardRoot,
  "../../_cache/coverage-ratchet-tests",
);
const fixtures: string[] = [];
const metrics = ["lines", "statements", "functions", "branches"] as const;

function fixture(covered = 100, zeroPopulationPercentage?: number) {
  fs.mkdirSync(scratchRoot, { recursive: true });
  const root = fs.mkdtempSync(path.join(scratchRoot, "report-"));
  fixtures.push(root);
  const dashboard = path.join(root, "apps/runtime-dashboard");
  fs.mkdirSync(path.join(dashboard, "scripts"), { recursive: true });
  fs.mkdirSync(path.join(dashboard, "src/api/hooks"), { recursive: true });
  fs.writeFileSync(path.join(dashboard, "package.json"), '{"type":"module"}');
  fs.copyFileSync(
    path.join(dashboardRoot, "scripts/check-coverage-ratchet.mjs"),
    path.join(dashboard, "scripts/check-coverage-ratchet.mjs"),
  );
  fs.copyFileSync(
    path.join(dashboardRoot, "coverage-baseline.json"),
    path.join(dashboard, "coverage-baseline.json"),
  );
  fs.writeFileSync(
    path.join(dashboard, "scripts/coverage-scope.json"),
    JSON.stringify({
      include: ["src/api/hooks/**/*.ts"],
      exclude: ["src/**/*.test.ts"],
    }),
  );
  const source = path.join(dashboard, "src/api/hooks/useExample.ts");
  fs.writeFileSync(source, "export const example = true;\n");
  const entry = Object.fromEntries(
    metrics.map((metric) => [
      metric,
      {
        total: 100,
        covered,
        skipped: 0,
        pct: covered,
      },
    ]),
  );
  const summary: Record<string, typeof entry> = {
    total: structuredClone(entry),
    [source]: entry,
  };
  const zeroSource = path.join(dashboard, "src/api/hooks/empty.ts");
  if (zeroPopulationPercentage !== undefined) {
    fs.writeFileSync(zeroSource, "export type Empty = never;\n");
    summary[zeroSource] = Object.fromEntries(
      metrics.map((metric) => [
        metric,
        { total: 0, covered: 0, skipped: 0, pct: zeroPopulationPercentage },
      ]),
    );
  }
  const summaryPath = path.join(
    root,
    "_build/apps/runtime-dashboard/coverage/coverage-summary.json",
  );
  const write = () => {
    fs.mkdirSync(path.dirname(summaryPath), { recursive: true });
    fs.writeFileSync(summaryPath, JSON.stringify(summary));
  };
  write();
  const run = (tolerance = "0") => {
    const result = spawnSync(
      process.execPath,
      [path.join(dashboard, "scripts/check-coverage-ratchet.mjs")],
      {
        cwd: root,
        encoding: "utf8",
        env: { ...process.env, COVERAGE_RATCHET_TOLERANCE: tolerance },
        timeout: 10_000,
      },
    );
    return {
      status: result.status,
      output: `${result.stdout}${result.stderr}`,
    };
  };
  return { dashboard, source, zeroSource, summary, summaryPath, write, run };
}

afterEach(() => {
  for (const root of fixtures.splice(0))
    fs.rmSync(root, { recursive: true, force: true });
});

describe("coverage ratchet measurement verdict", () => {
  it("passes a complete reconciled report while naming unmeasured properties", () => {
    const result = fixture().run();
    expect(result.status).toBe(0);
    expect(result.output).toContain("Coverage ratchet passed");
    expect(result.output).toMatch(
      /Not measured:.*assertion quality.*production invocation.*freshness.*hosted CI/,
    );
    expect(result.output).toContain("src/api/hooks/**/*.ts");
  });

  it("fails a complete measured shortfall without calling it unrun", () => {
    const result = fixture(84).run();
    expect(result.status).toBe(1);
    expect(result.output).toContain("Coverage ratchet FAILED");
    expect(result.output).toContain(
      "statements coverage below enforced minimum",
    );
    expect(result.output).not.toContain("Coverage ratchet UNRUN");
  });

  it("reports a missing summary as unrun with no complete verdict", () => {
    const report = fixture();
    fs.unlinkSync(report.summaryPath);
    const result = report.run();
    expect(result.status).toBe(2);
    expect(result.output).toContain(
      "Coverage ratchet UNRUN: no complete verdict",
    );
    expect(result.output).toContain("coverage-summary.json");
  });

  it("rejects a green self-consistent subset that omitted an included source file", () => {
    const report = fixture();
    fs.writeFileSync(
      path.join(report.dashboard, "src/api/hooks/unmeasured.ts"),
      "export const omitted = true;\n",
    );
    const result = report.run();
    expect(result.status).toBe(2);
    expect(result.output).toContain("unmeasured.ts");
    expect(result.output).toContain(
      "Coverage ratchet UNRUN: no complete verdict",
    );
    expect(result.output).not.toContain("Coverage ratchet passed");
  });

  it("rejects malformed JSON without leaking an uncaught parser exception", () => {
    const report = fixture();
    fs.writeFileSync(report.summaryPath, "{invalid");
    const result = report.run();
    expect(result.status).toBe(2);
    expect(result.output).toContain("Coverage ratchet UNRUN");
    expect(result.output).not.toContain("at JSON.parse");
  });

  it("rejects a forged percentage even when it exceeds the floor", () => {
    const report = fixture(84);
    report.summary.total.statements.pct = 100;
    report.write();
    const result = report.run();
    expect(result.status).toBe(2);
    expect(result.output).toContain("total.statements");
  });

  it("rejects aggregate counts that do not reconcile with the file records", () => {
    const report = fixture();
    report.summary.total.lines.total = 200;
    report.summary.total.lines.covered = 200;
    report.write();
    const result = report.run();
    expect(result.status).toBe(2);
    expect(result.output).toMatch(/total.lines.*reconcile/);
  });

  it("rejects an aliased duplicate record instead of double-counting its source", () => {
    const report = fixture();
    report.summary["src/api/hooks/useExample.ts"] = structuredClone(
      report.summary[report.source],
    );
    report.write();
    const result = report.run();
    expect(result.status).toBe(2);
    expect(result.output).toMatch(/duplicate.*useExample.ts/);
  });

  it("reports a missing metric as unmeasured rather than a coverage shortfall", () => {
    const report = fixture();
    delete report.summary[report.source].branches;
    report.write();
    const result = report.run();
    expect(result.status).toBe(2);
    expect(result.output).toContain("branches");
    expect(result.output).toContain("Coverage ratchet UNRUN");
  });

  it("rejects invalid tolerance instead of silently passing a measured shortfall", () => {
    const result = fixture(84).run("not-a-number");
    expect(result.status).toBe(2);
    expect(result.output).toContain("tolerance");
  });

  it.each([0, 100])(
    "accepts zero-population reporter convention %i without treating it as execution",
    (percentage) => {
      const report = fixture(100, percentage);
      const result = report.run();
      expect(result.status).toBe(0);
      expect(result.output).toContain("2/2 configured source files reconciled");
      expect(result.output).toContain(
        "0/0 records carry no execution observations",
      );
      expect(result.output).toContain(
        "0% and 100% are reporter representations",
      );
      expect(result.output).toContain("statements: 100/100 = 100.00%");
    },
  );

  it("rejects omission of a zero-population source record", () => {
    const report = fixture(100, 100);
    delete report.summary[report.zeroSource];
    report.write();
    const result = report.run();
    expect(result.status).toBe(2);
    expect(result.output).toContain(
      "unmeasured source file: src/api/hooks/empty.ts",
    );
    expect(result.output).not.toContain("Coverage ratchet passed");
  });

  it("rejects an arbitrary zero-population percentage", () => {
    const report = fixture(100, 50);
    const result = report.run();
    expect(result.status).toBe(2);
    expect(result.output).toContain("empty.ts.lines");
    expect(result.output).not.toContain("Coverage ratchet passed");
  });

  it("rejects covered items in a zero-population metric", () => {
    const report = fixture(100, 100);
    report.summary[report.zeroSource].statements.covered = 1;
    report.write();
    const result = report.run();
    expect(result.status).toBe(2);
    expect(result.output).toContain("empty.ts.statements");
  });

  it.each([0, 100])(
    "rejects a forged nonzero-population percentage %i",
    (percentage) => {
      const report = fixture(50);
      report.summary[report.source].statements.pct = percentage;
      report.write();
      const result = report.run();
      expect(result.status).toBe(2);
      expect(result.output).toContain("useExample.ts.statements");
    },
  );

  it.each([0, 100])(
    "reports a zero-population aggregate as unrun for %i",
    (percentage) => {
      for (const metric of metrics) {
        const report = fixture();
        report.summary[report.source][metric] = {
          total: 0,
          covered: 0,
          skipped: 0,
          pct: percentage,
        };
        report.summary.total[metric] = structuredClone(
          report.summary[report.source][metric],
        );
        report.write();
        const result = report.run();
        expect(result.status).toBe(2);
        expect(result.output).toContain(
          `total.${metric}: no population for an execution verdict`,
        );
        expect(result.output).not.toContain("Coverage ratchet passed");
      }
    },
  );
});
