import {
  flattenBureaucraticBlocks,
  type BureaucraticDocumentAST,
} from "../ast/bureaucratic-document-ast";

export type BureaucraticParityReport = {
  passed: boolean;
  missingBlockIds: string[];
  watermarkPresent: boolean;
};

export function checkBureaucraticExportParity(
  document: BureaucraticDocumentAST,
  renderedHtml: string,
): BureaucraticParityReport {
  const blockIds = flattenBureaucraticBlocks(document).map((block) => block.id);
  const missingBlockIds = blockIds.filter(
    (blockId) => !renderedHtml.includes(blockId),
  );
  const watermarkPresent = renderedHtml.includes(document.watermark);
  return {
    passed: missingBlockIds.length === 0 && watermarkPresent,
    missingBlockIds,
    watermarkPresent,
  };
}
