import type { ReactNode } from "react";

import {
  useMaybeTrustView,
  type TrustInspectorSubject,
  type TrustViewMode,
} from "./TrustViewBridge";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

import { DisputeBadge } from "./DisputeBadge";
import { HashChip } from "./HashChip";
import { TemporalScopeChip } from "./TemporalScopeChip";
import {
  hasVerificationOwnerContract,
  type VerificationMetadata,
} from "./trust-glyphs";
import { VerificationStatus } from "./VerificationStatus";

type TrustMetadataProps = {
  metadata?: VerificationMetadata | null;
  hash?: string | null;
  label?: string | null;
  subjectId: string;
  subjectKind?: "quantity" | "authored_text" | "artifact" | "lineage" | "chart";
  mode?: Exclude<TrustViewMode, "off">;
  className?: string;
};

export function TrustMetadata({
  metadata,
  hash,
  label,
  subjectId,
  subjectKind = "lineage",
  mode = "compact",
  className,
}: TrustMetadataProps) {
  const { t } = useI18n();
  const ownerMetadata = hasVerificationOwnerContract(metadata)
    ? metadata
    : null;
  const openInspectorPayload: TrustInspectorSubject = {
    hash: ownerMetadata?.hash ?? hash ?? undefined,
    id: subjectId,
    kind: subjectKind,
    label,
    trustMetadata: ownerMetadata,
  };

  if (mode === "compact") {
    return (
      <span className={cn("trust-metadata trust-metadata-compact", className)}>
        <TrustStatusButton subject={openInspectorPayload}>
          <VerificationStatus metadata={ownerMetadata} showLabel={false} />
        </TrustStatusButton>
        <HashChip
          hash={ownerMetadata?.hash ?? hash}
          label={label}
          subjectId={subjectId}
          subjectKind={subjectKind}
          trustMetadata={ownerMetadata}
        />
      </span>
    );
  }

  return (
    <span
      className={cn("trust-metadata trust-metadata-expanded", className)}
      role="group"
      aria-label={t("shared.ui.trustView.label")}
    >
      <span className="flex flex-wrap items-center gap-2">
        <TrustStatusButton subject={openInspectorPayload}>
          <VerificationStatus metadata={ownerMetadata} />
        </TrustStatusButton>
        {ownerMetadata ? (
          <DisputeBadge status={ownerMetadata.dispute_status} />
        ) : null}
        <HashChip
          hash={ownerMetadata?.hash ?? hash}
          label={label}
          subjectId={subjectId}
          subjectKind={subjectKind}
          trustMetadata={ownerMetadata}
        />
      </span>
      <span className="grid gap-x-3 gap-y-1 text-[11px] sm:grid-cols-[max-content_minmax(0,1fr)]">
        <TrustDetail
          label={t("shared.ui.trustView.verifiedBy")}
          value={ownerMetadata?.verified_by ?? t("common.unknown")}
        />
        <TrustDetail
          label={t("shared.ui.trustView.verifiedAt")}
          value={ownerMetadata?.verified_at ?? t("common.unknown")}
        />
        <TrustDetail
          label={t("shared.ui.trustView.method")}
          value={ownerMetadata?.verification_method ?? t("common.unknown")}
        />
        <span className="text-muted-foreground">
          {t("shared.ui.trustView.temporal")}
        </span>
        <span className="min-w-0">
          <TemporalScopeChip scope={ownerMetadata?.temporal_scope} />
        </span>
      </span>
    </span>
  );
}

function TrustDetail({ label, value }: { label: string; value: string }) {
  return (
    <>
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 truncate">{value}</span>
    </>
  );
}

function TrustStatusButton({
  children,
  subject,
}: {
  children: ReactNode;
  subject: TrustInspectorSubject;
}) {
  const trustView = useMaybeTrustView();
  return (
    <button
      type="button"
      className="trust-status-button"
      onClick={() => trustView?.openInspector(subject)}
    >
      {children}
    </button>
  );
}
