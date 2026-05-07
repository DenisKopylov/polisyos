import { Shield } from "lucide-react";

import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/shared/ui/primitives";

type ComplianceBadgeProps = {
  className?: string;
};

type ComplianceItem = {
  description: string;
  label: string;
  standard: string;
  status: "compliant" | "partial" | "planned";
};

const COMPLIANCE_ITEMS: ComplianceItem[] = [
  {
    description: "compliance.eaa.description",
    label: "WCAG 2.2 AA",
    standard: "EU EAA",
    status: "compliant",
  },
  {
    description: "compliance.ada.description",
    label: "WCAG 2.1 AA",
    standard: "US ADA Title II",
    status: "compliant",
  },
  {
    description: "compliance.nist.description",
    label: "AC-2, AU-2, IA-2, SC-8",
    standard: "NIST 800-53 Rev.5",
    status: "compliant",
  },
];

const STATUS_STYLES: Record<ComplianceItem["status"], string> = {
  compliant: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  partial: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  planned: "bg-neutral-500/10 text-neutral-600 dark:text-neutral-400",
};

/**
 * EAA/ADA compliance badge for the application footer.
 *
 * Displays a summary of compliance status with tooltip details.
 * Per FRONTEND_SOTA_PLAN Section 20: Legal Compliance.
 */
export function ComplianceBadge({ className }: ComplianceBadgeProps) {
  const { t } = useI18n();

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400",
            className,
          )}
          aria-label={t("compliance.badgeAriaLabel")}
        >
          <Shield className="h-3 w-3" aria-hidden="true" />
          {t("compliance.badgeLabel")}
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <p className="mb-2 text-xs font-semibold">
          {t("compliance.tooltipTitle")}
        </p>
        <ul className="space-y-1.5">
          {COMPLIANCE_ITEMS.map((item) => (
            <li key={item.standard} className="flex items-start gap-2">
              <span
                className={cn(
                  "mt-0.5 inline-block rounded px-1.5 py-0.5 text-[10px] font-bold",
                  STATUS_STYLES[item.status],
                )}
              >
                {item.status.toUpperCase()}
              </span>
              <div>
                <p className="text-xs font-medium">
                  {item.standard}: {item.label}
                </p>
                <p className="text-muted-foreground text-[10px]">
                  {t(item.description)}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </TooltipContent>
    </Tooltip>
  );
}
