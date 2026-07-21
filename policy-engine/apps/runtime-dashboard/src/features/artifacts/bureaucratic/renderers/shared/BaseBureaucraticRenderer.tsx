import type { ReactNode } from "react";

import { useOptionalI18n } from "@/shared/i18n/LocaleProvider";
import { Quantity } from "@/shared/ui/quantity";
import { TrustMetadata, useMaybeTrustView } from "@/shared/ui/trust-view";

import type {
  BureaucraticBlock,
  BureaucraticDocumentAST,
} from "../../ast/bureaucratic-document-ast";
import { numberBureaucraticBlocks } from "../../ast/numbering";
import { BureaucraticHeader } from "./BureaucraticHeader";
import { BureaucraticNumbering } from "./BureaucraticNumbering";
import { EpistemicLegend } from "./EpistemicLegend";
import { SignatureBlock } from "./SignatureBlock";

type BaseBureaucraticRendererProps = {
  document: BureaucraticDocumentAST;
  variantTitle: string;
};

export function BaseBureaucraticRenderer({
  document,
  variantTitle,
}: BaseBureaucraticRendererProps) {
  const { t } = useOptionalI18n();
  const numberedBlocks = numberBureaucraticBlocks(document.blocks);
  const numberedAnnexes = numberBureaucraticBlocks(document.annexes);

  return (
    <article
      className="bureaucratic-document mx-auto max-w-[940px] space-y-6 bg-white px-6 py-8 text-black shadow-sm print:max-w-none print:p-0 print:shadow-none"
      data-document-id={document.id}
      data-template-id={document.template.id}
      aria-label={`${variantTitle}: ${document.title}`}
    >
      <BureaucraticHeader document={document} />
      <div className="space-y-5">
        {numberedBlocks.map((block) => (
          <BureaucraticBlockView key={block.id} block={block} />
        ))}
      </div>
      <EpistemicLegend summary={document.epistemic_summary} />
      {numberedAnnexes.length ? (
        <section aria-labelledby="bureaucratic-annexes" className="space-y-4">
          <h2 id="bureaucratic-annexes" className="text-lg font-semibold">
            {t("pages.artifacts.bureaucratic.annexes")}
          </h2>
          {numberedAnnexes.map((block) => (
            <BureaucraticBlockView key={block.id} block={block} />
          ))}
        </section>
      ) : null}
      <SignatureBlock />
    </article>
  );
}

export function BureaucraticBlockView({ block }: { block: BureaucraticBlock }) {
  const trustView = useMaybeTrustView();
  const trustMode =
    trustView?.mode === "expanded"
      ? "expanded"
      : trustView?.mode === "compact"
        ? "compact"
        : "off";
  const metadata = block.quantity?.lineage.trust_metadata ?? null;
  const sourceHash =
    block.raw_source_refs?.find((ref) => ref.startsWith("sha256:")) ?? null;
  const hash = metadata?.hash ?? block.quantity?.lineage.hash ?? sourceHash;
  const heading = block.title ? (
    <Heading level={block.level + 1}>
      <BureaucraticNumbering number={block.number} />
      {block.title}
    </Heading>
  ) : null;
  return (
    <section
      className="break-inside-avoid space-y-2 print:break-inside-avoid"
      data-block-id={block.id}
      data-epistemic-origin={block.epistemic_origin}
    >
      {heading}
      {block.text ? <p className="leading-7">{block.text}</p> : null}
      {block.quantity ? (
        <p>
          <Quantity value={block.quantity} variant="inline" />
        </p>
      ) : null}
      {block.items?.length ? (
        <ul className="list-disc space-y-1 pl-6">
          {block.items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
      {block.provenance?.length ? (
        <p className="text-xs text-zinc-600">
          {block.provenance
            .slice(0, 4)
            .map((item) => `${item.kind}: ${item.label}`)
            .join(" | ")}
        </p>
      ) : null}
      {trustMode !== "off" && !block.quantity ? (
        <TrustMetadata
          hash={hash}
          label={block.title ?? block.id}
          metadata={metadata}
          mode={trustMode}
          subjectId={block.id}
          subjectKind={block.kind === "quantity" ? "quantity" : "artifact"}
        />
      ) : null}
      {block.children?.map((child) => (
        <BureaucraticBlockView key={child.id} block={child} />
      ))}
    </section>
  );
}

function Heading({ children, level }: { children: ReactNode; level: number }) {
  const className = "leading-tight font-semibold";
  if (level <= 2) {
    return <h2 className={`text-xl ${className}`}>{children}</h2>;
  }
  if (level === 3) {
    return <h3 className={`text-lg ${className}`}>{children}</h3>;
  }
  if (level === 4) {
    return <h4 className={`text-base ${className}`}>{children}</h4>;
  }
  return <h5 className={`text-sm ${className}`}>{children}</h5>;
}
