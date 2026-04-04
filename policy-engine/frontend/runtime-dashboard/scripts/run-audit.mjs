import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const dashboardRoot = path.resolve(scriptDir, "..");
const allowlistPath = path.join(dashboardRoot, "audit-allowlist.json");
const rawAuditPath = path.join(dashboardRoot, "npm-audit-raw.json");
const outputPath = path.join(dashboardRoot, "npm-audit-report.json");
const summaryPath = path.join(dashboardRoot, "npm-audit-summary.md");

function loadAllowlist() {
  if (!fs.existsSync(allowlistPath)) {
    return [];
  }

  const parsed = JSON.parse(fs.readFileSync(allowlistPath, "utf8"));
  return Array.isArray(parsed.allow) ? parsed.allow : [];
}

function isAllowlisted(vulnerability, allowlist) {
  return allowlist.some((entry) => {
    if (!entry || typeof entry !== "object") {
      return false;
    }
    if (entry.module && entry.module !== vulnerability.name) {
      return false;
    }
    if (entry.source) {
      const matchedSource = vulnerability.via?.some(
        (via) => typeof via === "object" && via.source === entry.source,
      );
      if (!matchedSource) {
        return false;
      }
    }
    if (entry.expiresOn && Date.now() > Date.parse(entry.expiresOn)) {
      return false;
    }
    return true;
  });
}

if (!fs.existsSync(rawAuditPath)) {
  throw new Error(`Missing npm audit input file at ${rawAuditPath}`);
}

const rawAudit = JSON.parse(fs.readFileSync(rawAuditPath, "utf8"));
const allowlist = loadAllowlist();
const vulnerabilities = Object.values(rawAudit.vulnerabilities ?? {});

const filtered = vulnerabilities.filter(
  (vulnerability) => !isAllowlisted(vulnerability, allowlist),
);
const bySeverity = filtered.reduce((accumulator, vulnerability) => {
  const severity = vulnerability.severity ?? "unknown";
  accumulator[severity] = (accumulator[severity] ?? 0) + 1;
  return accumulator;
}, {});

const report = {
  allowlist,
  generatedAt: new Date().toISOString(),
  summary: bySeverity,
  vulnerabilities: filtered,
};

const summaryLines = [
  "## Dependency Audit",
  "",
  `Filtered vulnerabilities: ${filtered.length}`,
  "",
  "| Severity | Count |",
  "| --- | ---: |",
  ...Object.entries(bySeverity).map(
    ([severity, count]) => `| ${severity} | ${count} |`,
  ),
  "",
];

fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), "utf8");
fs.writeFileSync(summaryPath, summaryLines.join("\n"), "utf8");
console.log(summaryLines.join("\n"));
