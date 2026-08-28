import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

import { Resvg } from "@resvg/resvg-js";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import satori from "satori";

import type { PublicShareSummary } from "./email-fixtures";
import {
  formatEpochSemantics,
  formatTemporalScope,
  OGCard,
  sanitizePublicShareSummary,
} from "./OGCard";

const OG_WIDTH = 1200;
const OG_HEIGHT = 630;
const require = createRequire(import.meta.url);

let fontCache: ArrayBuffer | null = null;

export function generateOgHtml(summary: PublicShareSummary) {
  const safeSummary = sanitizePublicShareSummary(summary);
  return [
    "<!doctype html>",
    '<html lang="en">',
    "<head>",
    '<meta charset="utf-8" />',
    '<meta name="viewport" content="width=device-width, initial-scale=1" />',
    `<title>${escapeHtml(safeSummary.title)}</title>`,
    "</head>",
    '<body style="margin:0;background:#fbf8f2">',
    renderToStaticMarkup(React.createElement(OGCard, { summary: safeSummary })),
    "</body>",
    "</html>",
  ].join("");
}

export async function generateOgSvg(summary: PublicShareSummary) {
  const safeSummary = sanitizePublicShareSummary(summary);
  const svg = await satori(ogCardNode(safeSummary), {
    fonts: [
      {
        data: loadOgFont(),
        name: "Manrope",
        style: "normal",
        weight: 800,
      },
    ],
    height: OG_HEIGHT,
    width: OG_WIDTH,
  });
  return withSvgMetadata(svg, safeSummary);
}

export async function generateOgPng(summary: PublicShareSummary) {
  const svg = await generateOgSvg(summary);
  return new Resvg(svg, {
    fitTo: {
      mode: "width",
      value: OG_WIDTH,
    },
  })
    .render()
    .asPng();
}

export function generateOgMetadata(summary: PublicShareSummary) {
  const safeSummary = sanitizePublicShareSummary(summary);
  const payload = stableStringify(safeSummary);
  return {
    contentType: "image/png",
    height: OG_HEIGHT,
    publicOnly: true,
    shareHash: createHash("sha256").update(payload).digest("hex"),
    width: OG_WIDTH,
  };
}

function stableStringify(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.entries(value)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${stableStringify(item)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function withSvgMetadata(svg: string, summary: PublicShareSummary) {
  const metadata = {
    generator: "PolicyOS Runtime",
    epochSemantics: summary.epochSemantics,
    keyQuantity: summary.keyQuantity,
    kind: summary.kind,
    state: summary.state,
    temporalScope: summary.temporalScope,
    title: summary.title,
    trustStatus: summary.trustStatus,
  };
  const metadataNode = `<metadata id="policyos-og-metadata">${escapeHtml(
    stableStringify(metadata),
  )}</metadata>`;
  return svg.replace(/(<svg\b[^>]*>)/u, `$1${metadataNode}`);
}

function ogCardNode(summary: PublicShareSummary) {
  const temporal = formatTemporalScope(summary.temporalScope);
  return React.createElement(
    "div",
    {
      style: {
        backgroundColor: "#fbf8f2",
        color: "#17191d",
        display: "flex",
        flexDirection: "column",
        fontFamily: "Manrope",
        height: "100%",
        justifyContent: "space-between",
        padding: 72,
        width: "100%",
      },
    },
    React.createElement(
      "div",
      {
        style: {
          alignItems: "center",
          display: "flex",
          justifyContent: "space-between",
          width: "100%",
        },
      },
      React.createElement(
        "div",
        { style: { display: "flex", flexDirection: "column", gap: 10 } },
        React.createElement(
          "div",
          {
            style: {
              color: "#40515f",
              display: "flex",
              fontSize: 24,
              fontWeight: 800,
              letterSpacing: 3,
              textTransform: "uppercase",
            },
          },
          "PolicyOS Runtime",
        ),
        React.createElement(
          "div",
          { style: { color: "#40515f", display: "flex", fontSize: 26 } },
          summary.subtitle ?? summary.kind,
        ),
      ),
      React.createElement(
        "div",
        {
          style: {
            border: "2px solid #d9d0bf",
            borderRadius: 999,
            color: "#17191d",
            display: "flex",
            fontSize: 24,
            fontWeight: 800,
            padding: "14px 22px",
          },
        },
        summary.trustStatus,
      ),
    ),
    React.createElement(
      "div",
      { style: { display: "flex", flexDirection: "column", gap: 26 } },
      React.createElement(
        "div",
        {
          style: {
            color: "#40515f",
            display: "flex",
            fontSize: 24,
            fontWeight: 800,
            letterSpacing: 2,
            textTransform: "uppercase",
          },
        },
        summary.kind,
      ),
      React.createElement(
        "div",
        {
          style: {
            display: "flex",
            fontSize: 64,
            fontWeight: 800,
            lineHeight: 1.05,
            maxWidth: 920,
          },
        },
        summary.title,
      ),
      summary.summary
        ? React.createElement(
            "div",
            {
              style: {
                color: "#40515f",
                display: "flex",
                fontSize: 30,
                lineHeight: 1.25,
                maxWidth: 880,
              },
            },
            summary.summary,
          )
        : null,
    ),
    React.createElement(
      "div",
      {
        style: {
          borderTop: "2px solid #d9d0bf",
          display: "flex",
          gap: 36,
          paddingTop: 28,
          width: "100%",
        },
      },
      footerItem(
        summary.keyQuantity.label,
        [summary.keyQuantity.value, summary.keyQuantity.unit]
          .filter(Boolean)
          .join(" "),
      ),
      footerItem("State", summary.state),
      footerItem("Temporal scope", temporal),
      footerItem(
        "Epoch & validity",
        formatEpochSemantics(summary.epochSemantics),
      ),
    ),
  );
}

function footerItem(label: string, value: string) {
  return React.createElement(
    "div",
    {
      style: {
        display: "flex",
        flexDirection: "column",
        gap: 10,
        minWidth: 0,
        width: "25%",
      },
    },
    React.createElement(
      "div",
      {
        style: {
          color: "#40515f",
          display: "flex",
          fontSize: 18,
          fontWeight: 800,
          textTransform: "uppercase",
        },
      },
      label,
    ),
    React.createElement(
      "div",
      {
        style: {
          color: "#17191d",
          display: "flex",
          fontSize: 28,
          fontWeight: 800,
          lineHeight: 1.2,
        },
      },
      value,
    ),
  );
}

function loadOgFont() {
  if (fontCache === null) {
    const fontPath =
      require.resolve("@fontsource/manrope/files/manrope-latin-800-normal.woff");
    const buffer = readFileSync(fontPath);
    fontCache = buffer.buffer.slice(
      buffer.byteOffset,
      buffer.byteOffset + buffer.byteLength,
    ) as ArrayBuffer;
  }
  return fontCache;
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => {
    switch (char) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      default:
        return "&#39;";
    }
  });
}
