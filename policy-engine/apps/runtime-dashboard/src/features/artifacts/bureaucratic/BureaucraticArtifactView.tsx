import { useMemo, useState } from "react";
import { Download, FileCheck2, Printer } from "lucide-react";

import { useBureaucraticRender } from "@/api/hooks/useBureaucraticRender";
import { useMaybeTemporalCursor } from "@/app/providers/useTemporalCursor";
import { useOptionalI18n } from "@/shared/i18n/LocaleProvider";
import { Button } from "@polisyos/atlas-ui";

import {
  type BureaucraticDocumentAST,
  type BureaucraticGenre,
} from "./ast/bureaucratic-document-ast";
import { validateBureaucraticDocumentAST } from "./ast/bureaucratic-document-ast";
import { BureaucraticGenrePicker } from "./BureaucraticGenrePicker";
import { buildBureaucraticDocxSource } from "./export/export-docx";
import { exportBureaucraticHtml } from "./export/export-html";
import { exportBureaucraticPdf } from "./export/export-pdf";
import { checkBureaucraticExportParity } from "./export/parity-check";
import { AnalitichnaZapyskaRenderer } from "./renderers/AnalitichnaZapyskaRenderer";
import { ExpertVysnovokRenderer } from "./renderers/ExpertVysnovokRenderer";
import { PostanovaKMURenderer } from "./renderers/PostanovaKMURenderer";
import { ZakonoproektRenderer } from "./renderers/ZakonoproektRenderer";

type BureaucraticArtifactViewProps = {
  artifactId: string;
};

export function BureaucraticArtifactView({
  artifactId,
}: BureaucraticArtifactViewProps) {
  const [genre, setGenre] = useState<BureaucraticGenre>("postanova_kmu");
  const [trustView, setTrustView] = useState(false);
  const { t } = useOptionalI18n();
  const temporal = useMaybeTemporalCursor();
  const query = useBureaucraticRender(artifactId, {
    genre,
    jurisdiction: "ua",
    temporalScope: temporal?.effectiveScope ?? null,
    trustView,
  });
  const document = query.data?.document as BureaucraticDocumentAST | undefined;
  const printTargetId = `bureaucratic-document-${artifactId.replace(/[^a-z0-9_-]+/gi, "-")}`;
  const htmlSource = useMemo(
    () => (document ? exportBureaucraticHtml(document) : ""),
    [document],
  );
  const parity = useMemo(
    () =>
      document
        ? checkBureaucraticExportParity(document, htmlSource)
        : undefined,
    [document, htmlSource],
  );
  const validation = useMemo(
    () => (document ? validateBureaucraticDocumentAST(document) : undefined),
    [document],
  );
  const docxSource = useMemo(
    () =>
      document ? buildBureaucraticDocxSource(document, htmlSource) : undefined,
    [document, htmlSource],
  );

  return (
    <section className="border-line bg-panel space-y-4 rounded-xl border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-muted text-xs uppercase">
            {t("pages.artifacts.bureaucratic.renderAs")}
          </p>
          <h3 className="text-lg font-semibold">
            {t("pages.artifacts.bureaucratic.title")}
          </h3>
        </div>
        <label className="flex items-center gap-2 text-sm font-semibold">
          <input
            type="checkbox"
            checked={trustView}
            onChange={(event) => setTrustView(event.target.checked)}
          />
          {t("pages.artifacts.bureaucratic.trustView")}
        </label>
      </div>

      <BureaucraticGenrePicker value={genre} onChange={setGenre} />

      {query.isLoading ? (
        <p className="text-muted text-sm">
          {t("pages.artifacts.bureaucratic.loading")}
        </p>
      ) : null}
      {query.isError ? (
        <p className="text-danger text-sm">
          {t("pages.artifacts.bureaucratic.error")}
        </p>
      ) : null}

      {document ? (
        <>
          <div className="flex flex-wrap items-center gap-2 print:hidden">
            <Button
              size="sm"
              type="button"
              variant="ghost"
              onClick={() =>
                exportBureaucraticPdf(document, `#${printTargetId}`)
              }
            >
              <Printer className="size-4" aria-hidden="true" />
              {t("pages.artifacts.bureaucratic.printPdf")}
            </Button>
            <Button size="sm" type="button" variant="ghost" disabled>
              <Download className="size-4" aria-hidden="true" />
              {t("pages.artifacts.bureaucratic.docxSourceReady")}
            </Button>
            <span className="text-muted inline-flex items-center gap-1 text-xs">
              <FileCheck2 className="size-4" aria-hidden="true" />
              {t("pages.artifacts.bureaucratic.validationStatus", {
                ast: validation?.valid
                  ? t("pages.artifacts.bureaucratic.valid")
                  : t("pages.artifacts.bureaucratic.needsReview"),
                filename: docxSource?.filename ?? "-",
                parity: parity?.passed
                  ? t("pages.artifacts.bureaucratic.passed")
                  : t("pages.artifacts.bureaucratic.needsReview"),
              })}
            </span>
          </div>
          <div
            id={printTargetId}
            className="overflow-x-auto rounded-md bg-white p-2"
          >
            <RendererForGenre document={document} />
          </div>
        </>
      ) : null}
    </section>
  );
}

function RendererForGenre({ document }: { document: BureaucraticDocumentAST }) {
  if (document.genre === "zakonoproekt") {
    return <ZakonoproektRenderer document={document} />;
  }
  if (document.genre === "expert_vysnovok") {
    return <ExpertVysnovokRenderer document={document} />;
  }
  if (document.genre === "analitichna_zapyska") {
    return <AnalitichnaZapyskaRenderer document={document} />;
  }
  return <PostanovaKMURenderer document={document} />;
}
