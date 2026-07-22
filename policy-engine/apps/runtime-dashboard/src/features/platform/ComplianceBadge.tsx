import { Shield } from "lucide-react";

import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Tooltip, TooltipContent, TooltipTrigger } from "@polisyos/atlas-ui";

type ComplianceBadgeProps = {
  className?: string;
};

type ComplianceItem = {
  label: string;
  standard: string;
};

const COMPLIANCE_ITEMS: ComplianceItem[] = [
  {
    label: "WCAG 2.2 AA",
    standard: "EU EAA",
  },
  {
    label: "WCAG 2.1 AA",
    standard: "US ADA Title II",
  },
  {
    label: "AC-2, AU-2, IA-2, SC-8",
    standard: "NIST 800-53 Rev.5",
  },
];

/**
 * Applicable accessibility and security standards disclosure for the footer.
 *
 * Lists documentation targets without making a local conformance claim.
 */
export function ComplianceBadge({ className }: ComplianceBadgeProps) {
  const { t } = useI18n();

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className={cn(
            "border-line bg-surface text-foreground inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium",
            className,
          )}
          aria-label={t("compliance.tooltipTitle")}
        >
          <Shield className="h-3 w-3" aria-hidden="true" />
          {t("compliance.tooltipTitle")}
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <p className="mb-2 text-xs font-semibold">
          {t("compliance.tooltipTitle")}
        </p>
        <ul className="space-y-1.5">
          {COMPLIANCE_ITEMS.map((item) => (
            <li key={item.standard} className="flex items-start gap-2">
              <div>
                <p className="text-xs font-medium">
                  {item.standard}: {item.label}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </TooltipContent>
    </Tooltip>
  );
}
