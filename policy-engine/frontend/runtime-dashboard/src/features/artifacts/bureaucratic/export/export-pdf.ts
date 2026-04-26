import { triggerPrint } from "@/shared/export/printExport";

import type { BureaucraticDocumentAST } from "../ast/bureaucratic-document-ast";

export function exportBureaucraticPdf(
  document: BureaucraticDocumentAST,
  selector: string,
) {
  triggerPrint({
    contentSelector: selector,
    includeTimestamp: true,
    title: `${document.genre}-${document.packet_hash.slice(0, 12)}`,
  });
}
