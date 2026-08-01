import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, ExternalLink, GitBranch } from "lucide-react";

import type { MessageValues } from "@/shared/i18n/messages/icu-messages";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "@polisyos/atlas-ui";

import { finiteInterval, formatQuantityValue } from "./quantity-format";
import { ProvenanceDeepDiveDialog } from "./ProvenanceDeepDiveDialog";
import { ProvenanceMiniGraph } from "./ProvenanceMiniGraph";
import { useQuantityRuntimeBridge } from "./QuantityRuntimeBridge";
import type {
  LineageFreshness,
  LineageResponsePayload,
  QuantityValue,
  TemporalRef,
  VerificationStatus,
} from "./quantity.types";
import { useLineage } from "./useLineage";

type ProvenancePopoverProps = {
  quantity: QuantityValue;
  children: ReactNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  temporalScope?: TemporalRef | null;
  className?: string;
  onContentMouseEnter?: () => void;
  onContentMouseLeave?: () => void;
};

type LineageQueryState = {
  data?: LineageResponsePayload;
  isLoading: boolean;
  isError: boolean;
};

export function ProvenancePopover(props: ProvenancePopoverProps) {
  if (props.quantity.lineage.id === "untraced") {
    return <UntracedProvenancePopover {...props} />;
  }
  return <TraceableProvenancePopover {...props} />;
}

function TraceableProvenancePopover(props: ProvenancePopoverProps) {
  const runtime = useQuantityRuntimeBridge();
  const scope = props.temporalScope ?? runtime.temporalScope;
  const lineageQuery = useLineage(props.quantity.lineage.id, {
    enabled: props.open,
    temporalScope: scope,
  });

  return (
    <ProvenancePopoverShell
      {...props}
      lineageQuery={lineageQuery}
      scope={scope}
    />
  );
}

function UntracedProvenancePopover(props: ProvenancePopoverProps) {
  const runtime = useQuantityRuntimeBridge();
  const scope = props.temporalScope ?? runtime.temporalScope;
  return (
    <ProvenancePopoverShell {...props} lineageQuery={null} scope={scope} />
  );
}

function ProvenancePopoverShell({
  quantity,
  children,
  open,
  onOpenChange,
  className,
  onContentMouseEnter,
  onContentMouseLeave,
  lineageQuery,
  scope,
}: ProvenancePopoverProps & {
  lineageQuery: LineageQueryState | null;
  scope: TemporalRef | null;
}) {
  const { t, locale } = useI18n();
  const [deepDiveOpen, setDeepDiveOpen] = useState(false);
  const lineage = lineageQuery?.data?.lineage;
  const formatted = formatQuantityValue(quantity, { locale });
  const verificationStatus = lineage?.status ?? quantity.lineage.status;
  const freshness = lineage?.freshness ?? quantity.lineage.freshness;
  const trustMetadata =
    lineage?.trust_metadata ?? quantity.lineage.trust_metadata;
  const temporalLabel = useMemo(
    () => formatTemporalScope(quantity, scope, t),
    [quantity, scope, t],
  );

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key.toLowerCase() !== "d") {
        return;
      }
      event.preventDefault();
      setDeepDiveOpen(true);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  return (
    <>
      <Popover open={open} onOpenChange={onOpenChange}>
        <PopoverTrigger asChild>{children}</PopoverTrigger>
        <PopoverContent
          align="start"
          aria-label={t("shared.ui.quantity.popover.title")}
          className={cn("w-[min(92vw,360px)] p-0", className)}
          onMouseEnter={onContentMouseEnter}
          onMouseLeave={onContentMouseLeave}
          onEscapeKeyDown={() => onOpenChange(false)}
          onKeyDown={(event) => {
            if (event.key.toLowerCase() === "d") {
              event.preventDefault();
              setDeepDiveOpen(true);
            }
          }}
          onOpenAutoFocus={(event) => {
            event.preventDefault();
          }}
        >
          <div className="space-y-3 p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-muted text-xs font-semibold">
                  {t("shared.ui.quantity.popover.title")}
                </p>
                <p className="truncate text-base font-semibold tabular-nums">
                  {quantity.label ?? quantity.metric_id ?? formatted.text}
                </p>
              </div>
              <div className="flex flex-wrap justify-end gap-1">
                <span
                  className={cn(
                    "rounded-full px-2 py-1 text-[11px] font-semibold",
                    verificationStatusClass(verificationStatus),
                  )}
                  data-testid="lineage-verification-status"
                >
                  {t(`shared.ui.quantity.status.${verificationStatus}`)}
                </span>
                <span
                  className={cn(
                    "rounded-full px-2 py-1 text-[11px] font-semibold",
                    freshnessClass(freshness),
                  )}
                  data-testid="lineage-freshness"
                >
                  {freshness}
                </span>
              </div>
            </div>

            <ProvenanceMiniGraph
              lineage={lineage}
              fallback={quantity.lineage}
              maxVisibleNodes={7}
            />

            <dl className="grid grid-cols-[96px_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-xs">
              <dt className="text-muted">
                {t("shared.ui.quantity.popover.value")}
              </dt>
              <dd className="font-medium">{formatted.text}</dd>
              <dt className="text-muted">
                {t("shared.ui.quantity.popover.uncertainty")}
              </dt>
              <dd>{formatUncertainty(quantity, t)}</dd>
              <dt className="text-muted">
                {t("shared.ui.quantity.popover.temporal")}
              </dt>
              <dd className="min-w-0 truncate">{temporalLabel}</dd>
              <dt className="text-muted">
                {t("shared.ui.quantity.popover.lineage")}
              </dt>
              <dd className="min-w-0 truncate">{quantity.lineage.id}</dd>
              {quantity.lineage.hash ? (
                <>
                  <dt className="text-muted">
                    {t("shared.ui.quantity.deepDive.hash")}
                  </dt>
                  <dd className="min-w-0 truncate">{quantity.lineage.hash}</dd>
                </>
              ) : null}
            </dl>

            {trustMetadata ? (
              <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-2 gap-y-1 text-[11px]">
                <dt className="text-muted">
                  {t("shared.ui.quantity.deepDive.verification")}
                </dt>
                <dd data-testid="trust-verification-status">
                  {trustMetadata.verification_status}
                </dd>
                <dt className="text-muted">
                  {t("shared.ui.quantity.deepDive.freshness")}
                </dt>
                <dd data-testid="trust-freshness">{trustMetadata.freshness}</dd>
                <dt className="text-muted" data-testid="trust-dispute-label">
                  {t("shared.ui.trustView.dispute.disputed")}
                </dt>
                <dd data-testid="trust-dispute-status">
                  {trustMetadata.dispute_status
                    ? t(
                        `shared.ui.trustView.dispute.${trustMetadata.dispute_status}`,
                      )
                    : t("common.unknown")}
                </dd>
              </dl>
            ) : null}

            {quantity.lineage.status === "untraced" ? (
              <div className="border-border bg-muted/30 flex gap-2 rounded-md border p-2 text-xs">
                <AlertTriangle
                  className="text-muted-foreground mt-0.5 size-4 shrink-0"
                  aria-hidden="true"
                />
                <div className="min-w-0">
                  <p className="font-medium">
                    {t("shared.ui.quantity.popover.untracedTitle")}
                  </p>
                  <p className="text-muted mt-0.5 break-words">
                    {quantity.lineage.reason_code ?? t("common.unknown")}
                  </p>
                </div>
              </div>
            ) : null}

            {lineageQuery?.isLoading ? (
              <p className="text-muted flex items-center gap-2 text-xs">
                <GitBranch className="size-3.5" aria-hidden="true" />
                {t("shared.ui.quantity.popover.loading")}
              </p>
            ) : null}
            {lineageQuery?.isError ? (
              <p className="text-muted text-xs">
                {t("shared.ui.quantity.popover.loadError")}
              </p>
            ) : null}

            <div className="border-border flex items-center justify-between border-t pt-3">
              <span className="text-muted text-[11px]">
                {t("shared.ui.quantity.popover.shortcut")}
              </span>
              <button
                type="button"
                className="border-border hover:bg-muted/40 focus:ring-ring inline-flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-xs font-semibold focus:ring-2 focus:outline-none"
                onClick={() => setDeepDiveOpen(true)}
              >
                {t("shared.ui.quantity.popover.deepDive")}
                <ExternalLink className="size-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        </PopoverContent>
      </Popover>
      <ProvenanceDeepDiveDialog
        open={deepDiveOpen}
        onOpenChange={setDeepDiveOpen}
        quantity={quantity}
        lineage={lineage}
        temporalScope={scope}
      />
    </>
  );
}

function verificationStatusClass(status: VerificationStatus) {
  if (status === "verified") {
    return "bg-[color-mix(in_srgb,var(--color-status-approved)_14%,transparent)] text-[var(--color-status-approved)]";
  }
  if (status === "pending") {
    return "bg-[color-mix(in_srgb,var(--color-status-pending)_16%,transparent)] text-[var(--color-status-pending)]";
  }
  if (status === "disputed") {
    return "bg-[color-mix(in_srgb,var(--color-status-rejected)_12%,transparent)] text-[var(--color-status-rejected)]";
  }
  return "bg-muted text-muted-foreground";
}

function freshnessClass(freshness: LineageFreshness) {
  return freshness === "current"
    ? "bg-[color-mix(in_srgb,var(--color-status-approved)_10%,transparent)] text-[var(--color-status-approved)]"
    : "bg-muted text-muted-foreground";
}

function formatUncertainty(
  quantity: QuantityValue,
  t: (path: string, vars?: MessageValues) => string,
) {
  const interval = finiteInterval(
    quantity.uncertainty?.ci_95 ?? quantity.uncertainty?.ci_80,
  );
  if (!interval) {
    return t("shared.ui.quantity.popover.noUncertainty");
  }
  return t("shared.ui.quantity.popover.interval", {
    lower: interval[0],
    upper: interval[1],
  });
}

function formatTemporalScope(
  quantity: QuantityValue,
  scope: TemporalRef | null,
  t: (path: string, vars?: MessageValues) => string,
) {
  const validAt = scope?.valid_at ?? quantity.time?.valid_at;
  const txAt = scope?.tx_at ?? quantity.time?.tx_at;
  if (!validAt && !txAt) {
    return t("common.unknown");
  }
  return t("shared.ui.quantity.popover.temporalValue", {
    validAt: validAt ? new Date(validAt).toLocaleString() : t("common.unknown"),
    txAt: txAt ? new Date(txAt).toLocaleString() : t("common.unknown"),
  });
}
