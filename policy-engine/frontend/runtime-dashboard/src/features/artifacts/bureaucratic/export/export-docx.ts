import type { BureaucraticDocumentAST } from "../ast/bureaucratic-document-ast";

export type BureaucraticDocxSource = {
  filename: string;
  htmlSource: string;
  metadata: Record<string, string>;
};

export function buildBureaucraticDocxSource(
  document: BureaucraticDocumentAST,
  htmlSource: string,
): BureaucraticDocxSource {
  return {
    filename: `${document.genre}-${document.packet_hash.slice(0, 12)}.docx`,
    htmlSource,
    metadata: {
      documentId: document.id,
      packetHash: document.packet_hash,
      templateId: document.template.id,
      watermark: document.watermark,
    },
  };
}
