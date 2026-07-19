import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ComponentPropsWithoutRef,
  type ReactNode,
} from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  Clock3,
  ShieldQuestion,
} from "lucide-react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

import {
  finiteInterval,
  finitePoint,
  formatQuantityValue,
  type QuantityFormatOptions,
} from "./quantity-format";
import { ProvenancePopover } from "./ProvenancePopover";
import { useQuantityRuntimeBridge } from "./QuantityRuntimeBridge";
import type {
  LineageFreshness,
  QuantityValue,
  TemporalRef,
  VerificationStatus,
} from "./quantity.types";

type QuantityBaseProps = {
  value: QuantityValue;
  format?: QuantityFormatOptions["format"];
  locale?: string;
  precision?: number;
  variant?: "inline" | "table" | "hero" | "dense";
  provenanceMode?: "auto" | "always" | "off";
  temporalScope?: TemporalRef | null;
} & Omit<ComponentPropsWithoutRef<"button">, "children" | "value">;

type QuantityProps = QuantityBaseProps &
  (
    | { absentValue?: undefined; absentValueLabel?: never }
    | { absentValue: ReactNode; absentValueLabel: string }
  );

const STATUS_CLASS: Record<VerificationStatus, string> = {
  verified:
    "border-[color-mix(in_srgb,var(--color-status-approved)_28%,transparent)] bg-[color-mix(in_srgb,var(--color-status-approved)_8%,transparent)]",
  pending:
    "border-[color-mix(in_srgb,var(--color-status-pending)_34%,transparent)] bg-[color-mix(in_srgb,var(--color-status-pending)_10%,transparent)]",
  disputed:
    "border-[color-mix(in_srgb,var(--color-status-rejected)_28%,transparent)] bg-[color-mix(in_srgb,var(--color-status-rejected)_8%,transparent)]",
  untraced: "border-border bg-[color-mix(in_srgb,var(--muted)_8%,transparent)]",
};

const DOT_CLASS: Record<VerificationStatus, string> = {
  verified: "text-[var(--color-status-approved)]",
  pending: "text-[var(--color-status-pending)]",
  disputed: "text-[var(--color-status-rejected)]",
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
  absentValue,
  absentValueLabel,
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
  const runtime = useQuantityRuntimeBridge();
  const [open, setOpen] = useState(false);
  const openTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const formatted = formatQuantityValue(value, {
    format,
    locale: locale ?? activeLocale,
    maximumFractionDigits: precision,
  });
  const hasScalarPoint = finitePoint(value.point);
  const hasAbsentPresentation =
    absentValue !== undefined && absentValue !== null;
  const presentation = hasScalarPoint
    ? "scalar"
    : hasAbsentPresentation
      ? "non-scalar"
      : "unknown";
  const formattedText = hasScalarPoint
    ? formatted.text
    : hasAbsentPresentation
      ? absentValueLabel
      : t("common.unknown");
  const resolvedAriaLabel =
    ariaLabel ??
    buildQuantityA11yDescription({
      formattedText,
      quantity: value,
      t,
    });
  const provenanceEnabled =
    provenanceMode === "always" ||
    (provenanceMode === "auto" &&
      value.quantity_class !== "layout" &&
      value.quantity_class !== "debug");
  const trustMode =
    provenanceEnabled && runtime.trustMode !== "off"
      ? runtime.trustMode
      : "off";

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
      <span className="tabular-nums">
        {hasScalarPoint
          ? formatted.value
          : (absentValue ?? t("common.unknown"))}
      </span>
      {hasScalarPoint && formatted.unit ? (
        <span className="text-muted-foreground text-xs font-medium">
          {formatted.unit}
        </span>
      ) : null}
      <StatusCue status={value.lineage.status} />
      <FreshnessCue freshness={value.lineage.freshness} />
      {value.uncertainty?.disputed ? (
        <AlertTriangle
          className="size-3.5 text-[var(--color-status-rejected)]"
          data-testid="quantity-uncertainty-disputed"
          aria-hidden="true"
        />
      ) : null}
    </>
  );

  const baseClass = cn(
    "focus-visible:ring-ring inline-flex items-center gap-1.5 rounded-md border align-baseline leading-none font-semibold transition-colors focus-visible:ring-2 focus-visible:outline-none",
    STATUS_CLASS[value.lineage.status],
    value.uncertainty?.disputed &&
      "ring-1 ring-[color-mix(in_srgb,var(--color-status-rejected)_45%,transparent)]",
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
        data-quantity-class={value.quantity_class}
        data-quantity-metric-id={value.metric_id ?? undefined}
        data-quantity-presentation={presentation}
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
      data-quantity-class={value.quantity_class}
      data-quantity-metric-id={value.metric_id ?? undefined}
      data-quantity-presentation={presentation}
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

  const trustMetadata = runtime.renderTrustMetadata?.(value, trustMode);
  if (!trustMetadata) {
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
      {trustMetadata}
    </span>
  );
}

function StatusCue({ status }: { status: VerificationStatus }) {
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

function FreshnessCue({ freshness }: { freshness: LineageFreshness }) {
  if (freshness === "current") {
    return null;
  }
  return (
    <CircleHelp
      className="text-muted-foreground size-3.5"
      data-lineage-freshness-cue={freshness}
      aria-hidden="true"
    />
  );
}

function buildQuantityA11yDescription({
  formattedText,
  quantity,
  t,
}: {
  formattedText: string;
  quantity: QuantityValue;
  t: (
    path: string,
    vars?: Record<string, string | number | null | undefined>,
  ) => string;
}) {
  const label =
    quantity.label ?? quantity.metric_id ?? t("shared.ui.quantity.valueLabel");
  const interval = finiteInterval(quantity.uncertainty?.ci_95);
  const description = interval
    ? t("shared.ui.quantity.aria.withCi95", {
        label,
        value: formattedText,
        lower: interval[0],
        upper: interval[1],
        status: t(`shared.ui.quantity.status.${quantity.lineage.status}`),
      })
    : t("shared.ui.quantity.aria.withoutCi", {
        label,
        value: formattedText,
        status: t(`shared.ui.quantity.status.${quantity.lineage.status}`),
      });
  const qualifiers: string[] = [];
  if (quantity.lineage.freshness !== "current") {
    const freshness =
      quantity.lineage.freshness === "stale"
        ? t("shared.ui.quantity.status.stale")
        : t("common.unknown");
    qualifiers.push(
      `${t("shared.ui.quantity.deepDive.freshness")} ${freshness}`,
    );
  }
  if (quantity.uncertainty?.disputed) {
    qualifiers.push(t("shared.ui.quantity.status.disputed"));
  }
  return [description, ...qualifiers].join(", ");
}
