import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dashboardRoot = path.dirname(
  fileURLToPath(new URL("../package.json", import.meta.url)),
);
const summaryPath = path.resolve(
  dashboardRoot,
  "../../_build/apps/runtime-dashboard/coverage/coverage-summary.json",
);
const baselinePath = path.resolve(dashboardRoot, "coverage-baseline.json");
const scopePath = path.resolve(dashboardRoot, "scripts/coverage-scope.json");
const metrics = ["lines", "statements", "functions", "branches"];
const absoluteMinimums = {
  branches: 70,
  functions: 80,
  lines: 85,
  statements: 85,
};

function readJson(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (error) {
    throw new Error(`Cannot measure ${filePath}: ${error.message}`);
  }
}

function percentage(total, covered) {
  return total === 0 ? 100 : Math.floor((10000 * covered) / total) / 100;
}

function validateMetric(value, label) {
  if (
    !value ||
    !Number.isSafeInteger(value.total) ||
    value.total < 0 ||
    !Number.isSafeInteger(value.covered) ||
    value.covered < 0 ||
    value.covered > value.total ||
    !Number.isFinite(value.pct) ||
    value.pct !== percentage(value.total, value.covered)
  ) {
    throw new Error(
      `${label}: missing or inconsistent coverage counts/percentage`,
    );
  }
}

function measuredSummary(summary, scope) {
  if (
    !scope ||
    !Array.isArray(scope.include) ||
    scope.include.length === 0 ||
    !Array.isArray(scope.exclude) ||
    ![...scope.include, ...scope.exclude].every(
      (glob) => typeof glob === "string" && glob.length > 0,
    )
  ) {
    throw new Error("Configured source scope is unavailable or malformed");
  }
  console.log(`Included source globs: ${JSON.stringify(scope.include)}`);
  console.log(`Excluded source globs: ${JSON.stringify(scope.exclude)}`);
  const expected = new Set(
    [
      ...fs.globSync(scope.include, {
        cwd: dashboardRoot,
        exclude: scope.exclude,
      }),
    ]
      .map((file) => path.resolve(dashboardRoot, file))
      .filter((file) => fs.statSync(file).isFile()),
  );
  if (expected.size === 0)
    throw new Error("Configured source scope resolved to no files");
  if (!summary || typeof summary !== "object" || Array.isArray(summary)) {
    throw new Error("Coverage summary is not an object");
  }
  const measured = new Set();
  const totals = Object.fromEntries(
    metrics.map((metric) => [metric, { total: 0, covered: 0 }]),
  );
  const omissions = [];
  for (const [file, record] of Object.entries(summary)) {
    if (file === "total") continue;
    const resolved = path.resolve(dashboardRoot, file);
    if (measured.has(resolved))
      omissions.push(`duplicate source record: ${file}`);
    measured.add(resolved);
    if (!expected.has(resolved))
      omissions.push(`source record outside configured scope: ${file}`);
    for (const metric of metrics) {
      validateMetric(record?.[metric], `${file}.${metric}`);
      totals[metric].total += record[metric].total;
      totals[metric].covered += record[metric].covered;
    }
  }
  for (const file of expected) {
    if (!measured.has(file))
      omissions.push(
        `unmeasured source file: ${path.relative(dashboardRoot, file)}`,
      );
  }
  if (omissions.length > 0) throw new Error(omissions.join("\n- "));
  for (const metric of metrics) {
    const aggregate = summary.total?.[metric];
    validateMetric(aggregate, `total.${metric}`);
    if (
      aggregate.total !== totals[metric].total ||
      aggregate.covered !== totals[metric].covered
    ) {
      throw new Error(
        `total.${metric}: aggregate counts do not reconcile with file records`,
      );
    }
  }
  console.log(
    `Measured file set: ${measured.size}/${expected.size} configured source files reconciled`,
  );
  return summary.total;
}

function main() {
  console.log(
    "Measurement scope: V8 line, statement, function and branch execution in the configured dashboard source scope; a complete verdict requires reconciled artifact counts and current source-file membership.",
  );
  console.log(
    "Not measured: assertion quality, production invocation, source-content freshness of this report, suites not executed by its producer, code outside the configured coverage globs, backend behavior, or hosted CI.",
  );
  try {
    const scope = readJson(scopePath);
    const summary = measuredSummary(readJson(summaryPath), scope);
    const baseline = readJson(baselinePath);
    const tolerance = Number(process.env.COVERAGE_RATCHET_TOLERANCE ?? "0");
    if (!Number.isFinite(tolerance) || tolerance < 0) {
      throw new Error("Coverage tolerance must be a finite nonnegative number");
    }
    const failures = [];
    console.log(
      `Coverage ratchet summary (configured tolerance: ${tolerance})`,
    );
    for (const metric of metrics) {
      const actual = summary[metric].pct;
      const ratchetMinimum = baseline.global?.[metric];
      if (
        !Number.isFinite(ratchetMinimum) ||
        ratchetMinimum < 0 ||
        ratchetMinimum > 100
      ) {
        throw new Error(`Missing or invalid ${metric} coverage baseline`);
      }
      const absoluteMinimum = absoluteMinimums[metric];
      const enforcedMinimum = Math.max(ratchetMinimum, absoluteMinimum);
      console.log(
        `- ${metric}: ${summary[metric].covered}/${summary[metric].total} = ${actual.toFixed(2)}% actual / ${ratchetMinimum.toFixed(2)}% baseline / ${absoluteMinimum.toFixed(2)}% target / ${enforcedMinimum.toFixed(2)}% enforced`,
      );
      if (actual + tolerance < enforcedMinimum) {
        failures.push(
          `${metric} coverage below enforced minimum: ${actual.toFixed(2)}% < ${enforcedMinimum.toFixed(2)}%`,
        );
      }
    }
    if (failures.length > 0) {
      console.error(
        "Coverage ratchet FAILED: complete measured report below enforced minimum",
      );
      for (const failure of failures) console.error(`- ${failure}`);
      return 1;
    }
    console.log("Coverage ratchet passed (named omissions above still apply)");
    return 0;
  } catch (error) {
    console.error("Coverage ratchet UNRUN: no complete verdict");
    console.error(`- ${error.message}`);
    return 2;
  }
}

process.exitCode = main();
