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

function fixture(covered = 100) {
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
  return { dashboard, source, summary, summaryPath, write, run };
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
});
