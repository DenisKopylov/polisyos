import type { BureaucraticDocumentAST } from "../ast/bureaucratic-document-ast";
import { BaseBureaucraticRenderer } from "./shared/BaseBureaucraticRenderer";

export function PostanovaKMURenderer({
  document,
}: {
  document: BureaucraticDocumentAST;
}) {
  return (
    <BaseBureaucraticRenderer
      document={document}
      variantTitle="Постанова КМУ"
    />
  );
}
