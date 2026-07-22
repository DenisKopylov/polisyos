import type { LineageCompactSummaryItem } from "@polisyos/runtime-api-client";

import { Glyph } from "@/shared/brand/Glyph";
import { cn } from "@/shared/lib/utils";
import { Badge, Card, EvidenceLink } from "@polisyos/atlas-ui";

type ProvenanceStepPresentation = {
  detail?: string;
  evidenceRef?: string;
  href?: string;
  timestamp?: string;
};

export type RecordedLineageStep = ProvenanceStepPresentation & {
  source: "recorded-lineage";
  lineage: LineageCompactSummaryItem & { id: string };
};

export type DiagnosticProvenanceStep = ProvenanceStepPresentation & {
  source: "diagnostic-summary";
  id: string;
  label: string;
  type: NonNullable<LineageCompactSummaryItem["kind"]>;
  diagnosticLabel?: string | null;
};

export type ProvenanceStep = RecordedLineageStep | DiagnosticProvenanceStep;

type ProvenanceChainProps = {
  steps: ProvenanceStep[];
  title?: string;
  className?: string;
};

function StepEvidence({ step }: { step: ProvenanceStep }) {
  const evidenceRef = step.evidenceRef ?? step.href;
  if (!evidenceRef) {
    return null;
  }
  return step.href ? (
    <EvidenceLink evidenceRef={evidenceRef} href={step.href} label="View" />
  ) : (
    <EvidenceLink evidenceRef={evidenceRef} />
  );
}

function presentStep(step: ProvenanceStep) {
  if (step.source === "recorded-lineage") {
    return {
      diagnosticLabel: null,
      id: step.lineage.id,
      label: step.lineage.label,
      type: step.lineage.kind ?? "unknown",
    };
  }
  return step;
}

export function ProvenanceChain({
  steps,
  title = "Provenance",
  className,
}: ProvenanceChainProps) {
  return (
    <Card
      className={cn("space-y-3", className)}
      data-provenance-collection="mixed"
    >
      <h3 className="text-lg font-semibold">{title}</h3>
      <div className="relative">
        {steps.map((step, index) => {
          const presented = presentStep(step);
          return (
            <div
              key={presented.id}
              className="flex gap-3"
              data-authority-posture={
                step.source === "diagnostic-summary" ? "diagnostic" : undefined
              }
              data-provenance-source={step.source}
            >
              <div className="flex flex-col items-center">
                <div className="border-line bg-surface flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-sm">
                  <Glyph decorative name="provenance" size={16} />
                </div>
                {index < steps.length - 1 ? (
                  <div className="bg-line w-0.5 flex-1" />
                ) : null}
              </div>

              <div className={cn("pb-5", index === steps.length - 1 && "pb-0")}>
                <div className="flex flex-wrap items-center gap-2">
                  <p
                    className="text-sm font-semibold"
                    data-provenance-source={step.source}
                  >
                    {presented.label}
                  </p>
                  {presented.diagnosticLabel ? (
                    <Badge
                      data-authority-presentation="diagnostic"
                      kind="outline"
                    >
                      {presented.diagnosticLabel}
                    </Badge>
                  ) : null}
                  <span className="text-muted text-xs tracking-wide uppercase">
                    {presented.type}
                  </span>
                </div>
                {step.detail ? (
                  <p className="text-muted mt-1 text-sm">{step.detail}</p>
                ) : null}
                <div className="mt-1 flex items-center gap-2">
                  {step.timestamp ? (
                    <span className="text-muted font-mono text-xs">
                      {step.timestamp}
                    </span>
                  ) : null}
                  <StepEvidence step={step} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
