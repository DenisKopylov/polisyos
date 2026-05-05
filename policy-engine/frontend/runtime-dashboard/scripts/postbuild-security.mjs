import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const dashboardRoot = path.resolve(scriptDir, "..");
const distDir = path.resolve(
  dashboardRoot,
  "../../_build/frontend/runtime-dashboard/dist",
);
const indexHtmlPath = path.join(distDir, "index.html");
const securityDir = path.join(distDir, "security");

function resolveOrigin(rawValue) {
  if (!rawValue) {
    return null;
  }

  try {
    const url = new URL(rawValue, "https://runtime-dashboard.local");
    if (url.origin === "https://runtime-dashboard.local") {
      return "'self'";
    }
    return url.origin;
  } catch {
    return null;
  }
}

function toIntegrity(assetPath) {
  const content = fs.readFileSync(assetPath);
  const hash = crypto.createHash("sha384").update(content).digest("base64");
  return `sha384-${hash}`;
}

function addIntegrityToHtml(html) {
  return html.replace(
    /<(script|link)\b([^>]*?(?:src|href)="([^"]+)"[^>]*)>/g,
    (fullMatch, tagName, attributes, assetHref) => {
      const href = String(assetHref);
      if (
        /^https?:\/\//.test(href) ||
        href.startsWith("data:") ||
        href.startsWith("blob:")
      ) {
        return fullMatch;
      }

      const isSupportedLink =
        tagName === "script" ||
        /rel="stylesheet"/.test(attributes) ||
        /rel="modulepreload"/.test(attributes);
      if (!isSupportedLink) {
        return fullMatch;
      }

      const filePath = path.join(distDir, href.replace(/^\//, ""));
      if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
        return fullMatch;
      }

      const integrity = toIntegrity(filePath);
      const withIntegrity = attributes.includes("integrity=")
        ? attributes.replace(/integrity="[^"]*"/, `integrity="${integrity}"`)
        : `${attributes} integrity="${integrity}"`;
      const withCrossOrigin = withIntegrity.includes("crossorigin=")
        ? withIntegrity.replace(
            /crossorigin="[^"]*"/,
            'crossorigin="anonymous"',
          )
        : `${withIntegrity} crossorigin="anonymous"`;

      return `<${tagName}${withCrossOrigin}>`;
    },
  );
}

function buildCspPolicy() {
  const runtimeApiOrigin = resolveOrigin(process.env.VITE_RUNTIME_API_URL);
  const loginOrigin = resolveOrigin(process.env.VITE_LOGIN_URL);
  const sentryIngestOrigin = resolveOrigin(process.env.VITE_SENTRY_DSN);
  const reportUri = process.env.VITE_CSP_REPORT_URI?.trim();

  const connectSrc = ["'self'"];
  for (const candidate of [runtimeApiOrigin, sentryIngestOrigin]) {
    if (candidate && !connectSrc.includes(candidate)) {
      connectSrc.push(candidate);
    }
  }

  const formAction = ["'self'"];
  if (loginOrigin && !formAction.includes(loginOrigin)) {
    formAction.push(loginOrigin);
  }

  const directives = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src ${connectSrc.join(" ")}`,
    "worker-src 'self'",
    "manifest-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "frame-ancestors 'none'",
    `form-action ${formAction.join(" ")}`,
  ];

  if (reportUri) {
    directives.push(`report-uri ${reportUri}`);
  }

  return directives.join("; ");
}

if (!fs.existsSync(indexHtmlPath)) {
  process.exit(0);
}

const html = fs.readFileSync(indexHtmlPath, "utf8");
const securedHtml = addIntegrityToHtml(html);
fs.writeFileSync(indexHtmlPath, securedHtml, "utf8");

fs.mkdirSync(securityDir, { recursive: true });
const cspPolicy = buildCspPolicy();
fs.writeFileSync(
  path.join(securityDir, "csp-report-only.txt"),
  cspPolicy,
  "utf8",
);
fs.writeFileSync(
  path.join(securityDir, "headers.json"),
  JSON.stringify(
    {
      "content-security-policy-report-only": cspPolicy,
    },
    null,
    2,
  ),
  "utf8",
);
