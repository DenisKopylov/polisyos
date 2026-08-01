import { Glyph } from "@/shared/brand/Glyph";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import {
  Card,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@polisyos/atlas-ui";

export type GovernancePassVocabulary =
  | "preflight_diagnostic"
  | "evaluator_verdict"
  | "reproducibility_readiness"
  | "owner_diagnostic";

/** One owner-labeled diagnostic; each producer vocabulary remains separate. */
export type GovernancePass = {
  id: string;
  label: string;
  status: string | null;
  vocabulary: GovernancePassVocabulary;
  detail?: string;
  durationMs?: number;
};

type GovernancePassGridProps = {
  passes: GovernancePass[];
  title?: string;
  className?: string;
};

export function GovernancePassGrid({
  passes,
  title,
  className,
}: GovernancePassGridProps) {
  const { t } = useI18n();
  const resolvedTitle = title ?? t("shared.ui.governancePassGrid.title");
  const presentations = passes.map((pass) => ({
    pass,
    ownerStatus: pass.status?.trim() || "unknown",
  }));

  return (
    <Card
      className={cn("space-y-3", className)}
      data-governance-source="diagnostic-summary"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">{resolvedTitle}</h3>
        <span className="text-muted text-xs font-medium">
          {t("pages.runs.diagnosticsCount", { count: passes.length })}
        </span>
      </div>

      <p
        className="text-muted font-mono text-xs"
        data-governance-source="diagnostic-summary"
        data-testid="governance-pass-grid-owner-states"
      >
        {presentations.map(({ ownerStatus }) => ownerStatus).join(" · ")}
      </p>

      <TooltipProvider delayDuration={200}>
        <div className="grid grid-cols-5 gap-2 sm:grid-cols-10">
          {presentations.map(({ pass, ownerStatus }) => {
            return (
              <Tooltip key={pass.id}>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="border-line bg-surface/70 focus-visible:ring-ring flex aspect-square items-center justify-center rounded-xl border transition-transform hover:scale-110 focus-visible:ring-2"
                    aria-label={`${pass.label}: ${ownerStatus}`}
                    data-authority-presentation="opaque"
                    data-owner-status={pass.status ?? undefined}
                    data-owner-vocabulary={pass.vocabulary}
                  >
                    <Glyph
                      className="text-muted"
                      decorative
                      name="governance-pass"
                      size={12}
                    />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="top">
                  <p className="font-semibold">{pass.label}</p>
                  <p className="text-muted-foreground text-xs">
                    {pass.durationMs != null
                      ? `${ownerStatus} · ${pass.durationMs}ms`
                      : ownerStatus}
                  </p>
                  <p className="text-muted-foreground text-xs">
                    {pass.vocabulary}
                  </p>
                  {pass.detail ? (
                    <p className="text-muted-foreground mt-1 max-w-48 text-xs">
                      {pass.detail}
                    </p>
                  ) : null}
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      </TooltipProvider>
    </Card>
  );
}
