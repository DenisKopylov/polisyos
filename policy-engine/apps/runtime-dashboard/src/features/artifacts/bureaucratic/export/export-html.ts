import {
  bureaucraticEpochSemantics,
  flattenBureaucraticBlocks,
  type BureaucraticBlock,
  type BureaucraticDocumentAST,
  type BureaucraticEpistemicKind,
} from "../ast/bureaucratic-document-ast";
import { formatEpochSemanticsSummary } from "@/shared/ui/temporal/TimeSemanticsLabel";
import { computeEpistemicSummary, epistemicLabel } from "../ast/epistemic-map";
import { numberBureaucraticBlocks } from "../ast/numbering";

const EPISTEMIC_ORDER: BureaucraticEpistemicKind[] = [
  "evidence_filled",
  "model_generated",
  "operator_filled",
  "imported",
];

export function exportBureaucraticHtml(
  document: BureaucraticDocumentAST,
): string {
  const numberedBlocks = numberBureaucraticBlocks(document.blocks);
  const numberedAnnexes = numberBureaucraticBlocks(document.annexes);
  const blockIds = flattenBureaucraticBlocks({
    annexes: numberedAnnexes,
    blocks: numberedBlocks,
  })
    .map((block) => block.id)
    .join(",");
  const summary = computeEpistemicSummary({
    annexes: numberedAnnexes,
    blocks: numberedBlocks,
  });
  const epochSemantics = formatEpochSemanticsSummary(
    bureaucraticEpochSemantics(document),
  );
  const epochProjection = bureaucraticEpochSemantics(document);
  return `<!doctype html>
<html lang="${escapeHtml(document.language)}">
<head>
  <meta charset="utf-8">
  <meta name="polisyos:document-id" content="${escapeHtml(document.id)}">
  <meta name="polisyos:packet-id" content="${escapeHtml(document.packet_id)}">
  <meta name="polisyos:packet-hash" content="${escapeHtml(document.packet_hash)}">
  <meta name="polisyos:watermark" content="${escapeHtml(document.watermark)}">
  <meta name="polisyos:template-id" content="${escapeHtml(document.template.id)}">
  <meta name="polisyos:template-version" content="${escapeHtml(document.template.version)}">
  <meta name="polisyos:legal-review-status" content="${escapeHtml(document.template.legal_review_status)}">
  <meta name="polisyos:render-timestamp" content="${escapeHtml(document.render_timestamp)}">
  <meta name="polisyos:epoch-semantics" content="${escapeHtml(epochSemantics)}">
  <meta name="polisyos:epoch-semantic-hash" content="${escapeHtml(epochProjection.projectionSemanticHash ?? "not_established")}">
  <title>${escapeHtml(document.title)}</title>
</head>
<body data-document-id="${escapeHtml(document.id)}" data-template-id="${escapeHtml(document.template.id)}" data-block-ids="${escapeHtml(blockIds)}">
  <article aria-labelledby="document-title">
    <header>
      <p role="note">${escapeHtml(document.watermark)}</p>
      <p>${escapeHtml(document.template.id)} / ${escapeHtml(document.template.version)}</p>
      <dl>
        <dt>Packet</dt><dd>${escapeHtml(document.packet_id)}</dd>
        <dt>Packet hash</dt><dd>${escapeHtml(document.packet_hash)}</dd>
        <dt>Rendered</dt><dd>${escapeHtml(document.render_timestamp)}</dd>
        <dt>Epoch &amp; validity</dt><dd>${escapeHtml(epochSemantics)}</dd>
        <dt>Status</dt><dd>${escapeHtml(document.status)}</dd>
      </dl>
    </header>
    <h1>${escapeHtml(document.title)}</h1>
    ${numberedBlocks.map(renderBlockHtml).join("\n")}
    <section aria-labelledby="epistemic-map" data-block-id="epistemic-map">
      <h2 id="epistemic-map">Epistemic legend</h2>
      <dl>
        ${EPISTEMIC_ORDER.map(
          (origin) =>
            `<dt>${escapeHtml(epistemicLabel(origin))}</dt><dd>${Math.round((summary[origin] ?? 0) * 100)}%</dd>`,
        ).join("\n")}
      </dl>
    </section>
    ${
      numberedAnnexes.length
        ? `<section aria-labelledby="annexes"><h2 id="annexes">Annexes</h2>${numberedAnnexes
            .map(renderBlockHtml)
            .join("\n")}</section>`
        : ""
    }
  </article>
</body>
</html>`;
}

function renderBlockHtml(block: BureaucraticBlock): string {
  const title = block.title
    ? `<h${headingLevel(block.level)}>${renderNumber(block.number)}${escapeHtml(block.title)}</h${headingLevel(block.level)}>`
    : "";
  const text = block.text ? `<p>${escapeHtml(block.text)}</p>` : "";
  const quantity = block.quantity
    ? `<p data-quantity-metric="${escapeHtml(block.quantity.metric_id ?? "")}" data-lineage-id="${escapeHtml(block.quantity.lineage.id)}" data-quantity-class="${escapeHtml(block.quantity.quantity_class ?? "decision")}">${escapeHtml(formatQuantity(block))}</p>`
    : "";
  const items = block.items?.length
    ? `<ul>${block.items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
    : "";
  const provenance = block.provenance?.length
    ? `<p data-provenance-summary="${escapeHtml(
        block.provenance
          .map((item) => `${item.kind}:${item.label}`)
          .join(" | "),
      )}"></p>`
    : "";
  const children = block.children?.length
    ? block.children.map(renderBlockHtml).join("\n")
    : "";
  return `<section data-block-id="${escapeHtml(block.id)}" data-epistemic-origin="${escapeHtml(block.epistemic_origin)}" data-raw-source-refs="${escapeHtml((block.raw_source_refs ?? []).join(" "))}">
    ${title}
    ${text}
    ${quantity}
    ${items}
    ${provenance}
    ${children}
  </section>`;
}

function renderNumber(number?: string | null): string {
  return number ? `<span class="number">${escapeHtml(number)}</span> ` : "";
}

function headingLevel(level: number): number {
  return Math.min(6, Math.max(2, level + 1));
}

function formatQuantity(block: BureaucraticBlock): string {
  const quantity = block.quantity;
  if (!quantity) {
    return "";
  }
  const value = quantity.point === null ? "-" : String(quantity.point);
  const unit = quantity.unit.display ?? quantity.unit.code;
  return `${value} ${unit}`;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
