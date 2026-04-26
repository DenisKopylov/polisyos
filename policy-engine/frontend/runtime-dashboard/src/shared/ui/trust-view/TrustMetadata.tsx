import type { ReactNode } from "react";

import {
  useMaybeTrustView,
  type TrustInspectorSubject,
} from "@/app/providers/useTrustView";
import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

import { DisputeBadge } from "./DisputeBadge";
import { HashChip } from "./HashChip";
import { TemporalScopeChip } from "./TemporalScopeChip";
import {
  trustMetadataFromLineage,
  trustToneFromMetadata,
  type VerificationMetadata,
} from "./trust-glyphs";
import { VerificationStatus } from "./VerificationStatus";

type TrustMetadataProps = {
  metadata?: VerificationMetadata | null;
  hash?: string | null;
  label?: string | null;
  subjectId: string;
  subjectKind?: "quantity" | "authored_text" | "artifact" | "lineage" | "chart";
  mode?: "compact" | "expanded";
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
  const resolved =
    metadata ??
    trustMetadataFromLineage({
      freshness: "unknown",
      hash,
      status: "untraced",
    });
  const tone = trustToneFromMetadata(resolved);
  const openInspectorPayload: TrustInspectorSubject = {
    hash: resolved.hash ?? hash ?? undefined,
    id: subjectId,
    kind: subjectKind,
    label,
    trustMetadata: resolved,
  };

  if (mode === "compact") {
    return (
      <span className={cn("trust-metadata trust-metadata-compact", className)}>
        <TrustStatusButton subject={openInspectorPayload}>
          <VerificationStatus tone={tone} showLabel={false} />
        </TrustStatusButton>
        <HashChip
          hash={resolved.hash ?? hash}
          label={label}
          subjectId={subjectId}
          subjectKind={subjectKind}
          trustMetadata={resolved}
        />
      </span>
    );
  }

  return (
    <div className={cn("trust-metadata trust-metadata-expanded", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <TrustStatusButton subject={openInspectorPayload}>
          <VerificationStatus tone={tone} />
        </TrustStatusButton>
        <DisputeBadge status={resolved.dispute_status} />
        <HashChip
          hash={resolved.hash ?? hash}
          label={label}
          subjectId={subjectId}
          subjectKind={subjectKind}
          trustMetadata={resolved}
        />
      </div>
      <dl className="grid gap-x-3 gap-y-1 text-[11px] sm:grid-cols-[max-content_minmax(0,1fr)]">
        <dt className="text-muted-foreground">
          {t("shared.ui.trustView.verifiedBy")}
        </dt>
        <dd className="min-w-0 truncate">
          {resolved.verified_by ?? t("common.unknown")}
        </dd>
        <dt className="text-muted-foreground">
          {t("shared.ui.trustView.verifiedAt")}
        </dt>
        <dd className="min-w-0 truncate">
          {resolved.verified_at ?? t("common.unknown")}
        </dd>
        <dt className="text-muted-foreground">
          {t("shared.ui.trustView.method")}
        </dt>
        <dd className="min-w-0 truncate">
          {resolved.verification_method ?? t("common.unknown")}
        </dd>
        <dt className="text-muted-foreground">
          {t("shared.ui.trustView.temporal")}
        </dt>
        <dd className="min-w-0">
          <TemporalScopeChip scope={resolved.temporal_scope} />
        </dd>
      </dl>
    </div>
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
