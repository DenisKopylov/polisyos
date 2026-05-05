import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ComponentPropsWithoutRef,
} from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  Clock3,
  ShieldQuestion,
} from "lucide-react";

import type { TemporalScope } from "@/app/providers/temporal-scope";
import { useMaybeTrustView } from "@/app/providers/useTrustView";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import {
  TrustMetadata,
  trustMetadataFromLineage,
} from "@/shared/ui/trust-view";

import {
  formatQuantityValue,
  type QuantityFormatOptions,
} from "./quantity-format";
import { ProvenancePopover } from "./ProvenancePopover";
import type {
  QuantityValue,
  TemporalRef,
  VerificationStatus,
} from "./quantity.types";

type QuantityProvenanceStatus = VerificationStatus | "stale";

type QuantityProps = {
  value: QuantityValue;
  format?: QuantityFormatOptions["format"];
  locale?: string;
  precision?: number;
  variant?: "inline" | "table" | "hero" | "dense";
  provenanceMode?: "auto" | "always" | "off";
  temporalScope?: TemporalScope | null;
} & Omit<ComponentPropsWithoutRef<"button">, "children" | "value">;

const STATUS_CLASS: Record<QuantityProvenanceStatus, string> = {
  verified:
    "border-[color-mix(in_srgb,var(--color-status-approved)_28%,transparent)] bg-[color-mix(in_srgb,var(--color-status-approved)_8%,transparent)]",
  pending:
    "border-[color-mix(in_srgb,var(--color-status-pending)_34%,transparent)] bg-[color-mix(in_srgb,var(--color-status-pending)_10%,transparent)]",
  disputed:
    "border-[color-mix(in_srgb,var(--color-status-rejected)_28%,transparent)] bg-[color-mix(in_srgb,var(--color-status-rejected)_8%,transparent)]",
  stale: "border-border bg-[color-mix(in_srgb,var(--muted)_14%,transparent)]",
  untraced: "border-border bg-[color-mix(in_srgb,var(--muted)_8%,transparent)]",
};

const DOT_CLASS: Record<QuantityProvenanceStatus, string> = {
  verified: "text-[var(--color-status-approved)]",
  pending: "text-[var(--color-status-pending)]",
  disputed: "text-[var(--color-status-rejected)]",
  stale: "text-muted-foreground",
  untraced: "text-muted-foreground",
};

const VARIANT_CLASS: Record<NonNullable<QuantityProps["variant"]>, string> = {
  inline: "min-h-6 px-2 py-0.5 text-sm",
  table: "min-h-5 px-1.5 py-0.5 text-xs",
  hero: "min-h-8 px-2.5 py-1 text-lg",
  dense: "min-h-5 px-1.5 py-0 text-xs",
};

const HOVER_OPEN_DELAY_MS = /* policyos-quantity: telemetry */ 150;
const HOVER_CLOSE_DELAY_MS = /* policyos-quantity: telemetry */ 120;

export function Quantity({
  value,
  format = "decimal",
  locale,
  precision,
  variant = "inline",
  provenanceMode = "auto",
  temporalScope,
  className,
  "aria-label": ariaLabel,
  onBlur,
  onFocus,
  onKeyDown,
  onMouseEnter,
  onMouseLeave,
  ...rest
}: QuantityProps) {
  const { t, locale: activeLocale } = useI18n();
  const trustView = useMaybeTrustView();
  const [open, setOpen] = useState(false);
  const openTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const formatted = formatQuantityValue(value, {
    format,
    locale: locale ?? activeLocale,
    maximumFractionDigits: precision,
  });
  const status = resolveProvenanceStatus(value);
  const resolvedAriaLabel =
    ariaLabel ??
    buildQuantityA11yDescription({
      formattedText: formatted.text,
      quantity: value,
      status,
      t,
    });
  const provenanceEnabled =
    provenanceMode === "always" ||
    (provenanceMode === "auto" &&
      value.quantity_class !== "layout" &&
      value.quantity_class !== "debug");
  const trustMode =
    provenanceEnabled && trustView?.mode !== "off"
      ? trustView?.density === "condensed"
        ? "compact"
        : trustView?.mode
      : "off";
  const trustMetadata = trustMetadataFromLineage({
    fallbackTemporalScope: value.time ?? temporalScopeToRef(temporalScope),
    freshness: value.lineage.freshness,
    hash: value.lineage.hash,
    status: value.lineage.status,
    trustMetadata: value.lineage.trust_metadata,
  });

  const clearTimers = useCallback(() => {
    if (openTimer.current) {
      clearTimeout(openTimer.current);
      openTimer.current = null;
    }
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  }, []);

  const scheduleOpen = useCallback(() => {
    if (!provenanceEnabled) {
      return;
    }
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
    if (!openTimer.current) {
      openTimer.current = setTimeout(() => {
        setOpen(true);
        openTimer.current = null;
      }, HOVER_OPEN_DELAY_MS);
    }
  }, [provenanceEnabled]);

  const scheduleClose = useCallback(() => {
    if (openTimer.current) {
      clearTimeout(openTimer.current);
      openTimer.current = null;
    }
    if (!closeTimer.current) {
      closeTimer.current = setTimeout(() => {
        setOpen(false);
        closeTimer.current = null;
      }, HOVER_CLOSE_DELAY_MS);
    }
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  const content = (
    <>
      <span className="tabular-nums">{formatted.value}</span>
      {formatted.unit ? (
        <span className="text-muted-foreground text-xs font-medium">
          {formatted.unit}
        </span>
      ) : null}
      <StatusCue status={status} />
    </>
  );

  const baseClass = cn(
    "focus-visible:ring-ring inline-flex items-center gap-1.5 rounded-md border align-baseline leading-none font-semibold transition-colors focus-visible:ring-2 focus-visible:outline-none",
    STATUS_CLASS[status],
    VARIANT_CLASS[variant],
    provenanceEnabled && "cursor-help",
    className,
  );

  if (!provenanceEnabled) {
    return (
      <span
        aria-label={resolvedAriaLabel}
        data-lineage-id={value.lineage.id}
        data-lineage-status={value.lineage.status}
        data-lineage-freshness={value.lineage.freshness}
        data-provenance-status={status}
        data-quantity-class={value.quantity_class}
        data-testid="quantity"
        className={baseClass}
      >
        {content}
      </span>
    );
  }

  const trigger = (
    <button
      {...rest}
      type="button"
      aria-label={resolvedAriaLabel}
      aria-expanded={open}
      data-lineage-id={value.lineage.id}
      data-lineage-status={value.lineage.status}
      data-lineage-freshness={value.lineage.freshness}
      data-provenance-status={status}
      data-quantity-class={value.quantity_class}
      data-testid="quantity"
      className={baseClass}
      onBlur={onBlur}
      onFocus={(event) => {
        scheduleOpen();
        onFocus?.(event);
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          setOpen(true);
        }
        if (event.key === "Escape") {
          setOpen(false);
        }
        onKeyDown?.(event);
      }}
      onMouseEnter={(event) => {
        scheduleOpen();
        onMouseEnter?.(event);
      }}
      onMouseLeave={(event) => {
        scheduleClose();
        onMouseLeave?.(event);
      }}
    >
      {content}
    </button>
  );

  const popover = (
    <ProvenancePopover
      quantity={value}
      open={open}
      onOpenChange={setOpen}
      temporalScope={temporalScope}
      onContentMouseEnter={clearTimers}
      onContentMouseLeave={scheduleClose}
    >
      {trigger}
    </ProvenancePopover>
  );

  if (trustMode === "off") {
    return popover;
  }

  return (
    <span
      data-trust-collapse="inspector"
      className={cn(
        "trust-view-quantity",
        trustMode === "expanded" && "trust-view-quantity-expanded",
      )}
    >
      {popover}
      <TrustMetadata
        hash={value.lineage.hash}
        label={value.label ?? value.metric_id}
        metadata={trustMetadata}
        mode={trustMode}
        subjectId={value.lineage.id}
        subjectKind="quantity"
      />
    </span>
  );
}

function StatusCue({ status }: { status: QuantityProvenanceStatus }) {
  const iconClass = cn("size-3.5", DOT_CLASS[status]);
  if (status === "verified") {
    return <CheckCircle2 className={iconClass} aria-hidden="true" />;
  }
  if (status === "pending") {
    return <Clock3 className={iconClass} aria-hidden="true" />;
  }
  if (status === "disputed") {
    return <AlertTriangle className={iconClass} aria-hidden="true" />;
  }
  if (status === "untraced") {
    return <ShieldQuestion className={iconClass} aria-hidden="true" />;
  }
  return <CircleHelp className={iconClass} aria-hidden="true" />;
}

function resolveProvenanceStatus(
  value: QuantityValue,
): QuantityProvenanceStatus {
  if (value.uncertainty?.disputed || value.lineage.status === "disputed") {
    return "disputed";
  }
  if (value.lineage.freshness === "stale") {
    return "stale";
  }
  return value.lineage.status;
}

function buildQuantityA11yDescription({
  formattedText,
  quantity,
  status,
  t,
}: {
  formattedText: string;
  quantity: QuantityValue;
  status: QuantityProvenanceStatus;
  t: (
    path: string,
    vars?: Record<string, string | number | null | undefined>,
  ) => string;
}) {
  const label =
    quantity.label ?? quantity.metric_id ?? t("shared.ui.quantity.valueLabel");
  const interval = quantity.uncertainty?.ci_95;
  if (interval) {
    return t("shared.ui.quantity.aria.withCi95", {
      label,
      value: formattedText,
      lower: interval[0],
      upper: interval[1],
      status: t(`shared.ui.quantity.status.${status}`),
    });
  }
  return t("shared.ui.quantity.aria.withoutCi", {
    label,
    value: formattedText,
    status: t(`shared.ui.quantity.status.${status}`),
  });
}

function temporalScopeToRef(
  scope: TemporalScope | null | undefined,
): TemporalRef | null {
  if (!scope) {
    return null;
  }
  return {
    branch: scope.branch ?? null,
    scenario_id: scope.scenarioId ?? null,
    snapshot_id: scope.snapshotId ?? null,
    tx_at: scope.txAt ?? null,
    valid_at: scope.validAt ?? null,
  };
}
