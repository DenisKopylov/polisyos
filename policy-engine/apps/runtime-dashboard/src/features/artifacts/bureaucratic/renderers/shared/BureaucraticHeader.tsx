import { useOptionalI18n } from "@/shared/i18n/LocaleProvider";

import type { BureaucraticDocumentAST } from "../../ast/bureaucratic-document-ast";
import { BureaucraticTemplateBadge } from "../../BureaucraticTemplateBadge";
import { BureaucraticWatermark } from "./BureaucraticWatermark";

type BureaucraticHeaderProps = {
  document: BureaucraticDocumentAST;
};

export function BureaucraticHeader({ document }: BureaucraticHeaderProps) {
  const { t } = useOptionalI18n();
  return (
    <header className="space-y-4 border-b border-black/30 pb-4 print:break-after-avoid">
      <BureaucraticWatermark watermark={document.watermark} />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-muted text-xs uppercase">
            {t("pages.artifacts.bureaucratic.draftArtifact")}
          </p>
          <h1 className="mt-1 max-w-3xl text-2xl leading-tight font-semibold">
            {document.title}
          </h1>
        </div>
        <BureaucraticTemplateBadge template={document.template} />
      </div>
      <dl className="grid gap-2 text-xs md:grid-cols-4">
        <div>
          <dt className="text-muted uppercase">
            {t("pages.artifacts.bureaucratic.packet")}
          </dt>
          <dd className="font-mono break-all">{document.packet_id}</dd>
        </div>
        <div>
          <dt className="text-muted uppercase">
            {t("pages.artifacts.bureaucratic.packetHash")}
          </dt>
          <dd className="font-mono break-all">{document.packet_hash}</dd>
        </div>
        <div>
          <dt className="text-muted uppercase">
            {t("pages.artifacts.bureaucratic.rendered")}
          </dt>
          <dd>{new Date(document.render_timestamp).toLocaleString()}</dd>
        </div>
        <div>
          <dt className="text-muted uppercase">
            {t("pages.artifacts.bureaucratic.status")}
          </dt>
          <dd>{document.status}</dd>
        </div>
      </dl>
    </header>
  );
}
