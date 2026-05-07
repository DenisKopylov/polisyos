import type { BureaucraticDocumentAST } from "../ast/bureaucratic-document-ast";
import { BaseBureaucraticRenderer } from "./shared/BaseBureaucraticRenderer";

export function AnalitichnaZapyskaRenderer({
  document,
}: {
  document: BureaucraticDocumentAST;
}) {
  return (
    <BaseBureaucraticRenderer
      document={document}
      variantTitle="Аналітична записка"
    />
  );
}
