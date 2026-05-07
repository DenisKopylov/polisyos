import type { ReactNode } from "react";

import type { PublicShareSummary } from "./email-fixtures";
import { formatTemporalScope, sanitizePublicShareSummary } from "./OGCard";

type EmailSummaryProps = {
  summary: PublicShareSummary;
};

const EMAIL_BRAND_LABEL = "POLICYOS RUNTIME";
const EMAIL_OPEN_LABEL = "Open in PolicyOS";
const EMAIL_PUBLIC_SUMMARY_NOTICE =
  "This email contains a public summary only. Raw evidence and private reviewer notes are not included.";

export function EmailSummary({ summary }: EmailSummaryProps) {
  const safeSummary = sanitizePublicShareSummary(summary);
  return (
    <article
      style={{
        color: "#17191d",
        fontFamily: "Manrope, Arial, sans-serif",
        margin: "0 auto",
        maxWidth: 640,
        padding: 24,
      }}
    >
      <p style={{ fontFamily: "monospace", fontSize: 12, letterSpacing: 2 }}>
        {EMAIL_BRAND_LABEL}
      </p>
      <h1 style={{ fontSize: 28, lineHeight: 1.2, margin: "8px 0 12px" }}>
        {safeSummary.title}
      </h1>
      <p style={{ color: "#40515f", fontSize: 16, lineHeight: 1.5 }}>
        {safeSummary.summary ?? safeSummary.subtitle}
      </p>
      <table
        style={{
          borderCollapse: "collapse",
          marginTop: 20,
          width: "100%",
        }}
      >
        <tbody>
          <EmailRow label={safeSummary.keyQuantity.label}>
            {safeSummary.keyQuantity.value} {safeSummary.keyQuantity.unit}
          </EmailRow>
          <EmailRow label="Trust status">{safeSummary.trustStatus}</EmailRow>
          <EmailRow label="State">{safeSummary.state}</EmailRow>
          <EmailRow label="Temporal scope">
            {formatTemporalScope(safeSummary.temporalScope)}
          </EmailRow>
        </tbody>
      </table>
      <p style={{ marginTop: 24 }}>
        <a href={safeSummary.href}>{EMAIL_OPEN_LABEL}</a>
      </p>
      <p style={{ color: "#40515f", fontSize: 12 }}>
        {EMAIL_PUBLIC_SUMMARY_NOTICE}
      </p>
    </article>
  );
}

export function renderEmailPlainText(summary: PublicShareSummary) {
  const safeSummary = sanitizePublicShareSummary(summary);
  return [
    `PolicyOS Runtime: ${safeSummary.title}`,
    safeSummary.summary ?? safeSummary.subtitle ?? "",
    `${safeSummary.keyQuantity.label}: ${safeSummary.keyQuantity.value} ${safeSummary.keyQuantity.unit ?? ""}`.trim(),
    `Trust status: ${safeSummary.trustStatus}`,
    `State: ${safeSummary.state}`,
    `Temporal scope: ${formatTemporalScope(safeSummary.temporalScope)}`,
    `Open: ${safeSummary.href}`,
    "Public summary only. Raw evidence and private reviewer notes are not included.",
  ]
    .filter(Boolean)
    .join("\n");
}

function EmailRow({ children, label }: { children: ReactNode; label: string }) {
  return (
    <tr>
      <th
        scope="row"
        style={{
          borderTop: "1px solid #d8d2c7",
          color: "#40515f",
          fontSize: 13,
          padding: "10px 8px 10px 0",
          textAlign: "left",
          width: "36%",
        }}
      >
        {label}
      </th>
      <td
        style={{
          borderTop: "1px solid #d8d2c7",
          fontSize: 14,
          padding: "10px 0",
        }}
      >
        {children}
      </td>
    </tr>
  );
}
