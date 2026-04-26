import { useState } from "react";
import { Copy, ExternalLink } from "lucide-react";

import { useMaybeTrustView } from "@/app/providers/useTrustView";
import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

import { truncateHash, type VerificationMetadata } from "./trust-glyphs";

type HashChipProps = {
  hash?: string | null;
  label?: string | null;
  subjectId: string;
  subjectKind?: "quantity" | "authored_text" | "artifact" | "lineage" | "chart";
  trustMetadata?: VerificationMetadata | null;
  interactive?: boolean;
  className?: string;
};

export function HashChip({
  hash,
  label,
  subjectId,
  subjectKind = "lineage",
  trustMetadata,
  interactive = true,
  className,
}: HashChipProps) {
  const { t } = useI18n();
  const trustView = useMaybeTrustView();
  const [copied, setCopied] = useState(false);
  if (!hash) {
    return null;
  }
  const shortHash = truncateHash(hash);
  const title = t("shared.ui.trustView.hashChipTitle", { hash });

  if (!interactive) {
    return (
      <span
        className={cn("trust-hash-chip", className)}
        title={title}
        data-hash={hash}
      >
        {shortHash}
      </span>
    );
  }

  return (
    <span className={cn("trust-hash-chip-group", className)}>
      <button
        type="button"
        className="trust-hash-chip"
        title={title}
        data-hash={hash}
        onClick={() => {
          trustView?.openInspector({
            hash,
            id: subjectId,
            kind: subjectKind,
            label,
            trustMetadata,
          });
        }}
      >
        {shortHash}
        <ExternalLink className="size-3" aria-hidden="true" />
      </button>
      <button
        type="button"
        className="trust-hash-copy"
        aria-label={t("shared.ui.trustView.copyHash")}
        onClick={async () => {
          await navigator.clipboard?.writeText(hash);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1000);
        }}
      >
        <Copy className="size-3" aria-hidden="true" />
        <span className="sr-only">
          {copied
            ? t("shared.ui.trustView.copied")
            : t("shared.ui.trustView.copyHash")}
        </span>
      </button>
    </span>
  );
}
