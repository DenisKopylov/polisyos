import { cn } from "@/lib/utils";
import { Badge, Card } from "@/shared/ui/primitives";
import { ConfidenceGauge } from "@/shared/charts/ConfidenceGauge";

import type {
  StructuredResponseData,
  KeyFactor,
  SourceCitation,
} from "../state/useChatStore";

type ClerkStructuredResponseProps = {
  data: StructuredResponseData;
  className?: string;
};

const DIRECTION_ICON: Record<KeyFactor["direction"], string> = {
  positive: "\u2191",
  negative: "\u2193",
  neutral: "\u2022",
};

const DIRECTION_COLOR: Record<KeyFactor["direction"], string> = {
  positive: "text-[var(--color-status-approved)]",
  negative: "text-[var(--color-status-rejected)]",
  neutral: "text-[var(--slate)]",
};

const SOURCE_TYPE_LABEL: Record<SourceCitation["type"], string> = {
  dataset: "Data",
  legislation: "Law",
  study: "Study",
  model: "Model",
  governance: "Gov",
};

function KeyFactorRow({ factor }: { factor: KeyFactor }) {
  const barWidth = Math.round(factor.magnitude * 100);
  return (
    <div className="flex items-center gap-3">
      <span
        className={cn("text-sm font-bold", DIRECTION_COLOR[factor.direction])}
        aria-hidden="true"
      >
        {DIRECTION_ICON[factor.direction]}
      </span>
      <span className="min-w-0 flex-1 truncate text-sm">{factor.label}</span>
      <div className="h-1.5 w-20 rounded-full bg-[var(--line)]">
        <div
          className={cn(
            "h-full rounded-full",
            factor.direction === "negative"
              ? "bg-[var(--color-status-rejected)]"
              : factor.direction === "positive"
                ? "bg-[var(--color-status-approved)]"
                : "bg-[var(--slate)]",
          )}
          style={{ width: `${barWidth}%` }}
        />
      </div>
    </div>
  );
}

function SourceCitationChip({ source }: { source: SourceCitation }) {
  const inner = (
    <>
      <Badge kind="outline" className="text-[10px]">
        {SOURCE_TYPE_LABEL[source.type]}
      </Badge>
      <span className="text-xs">{source.label}</span>
    </>
  );

  if (source.url) {
    return (
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--line)] px-2 py-1 transition-colors hover:bg-[var(--surface)]"
      >
        {inner}
      </a>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--line)] px-2 py-1">
      {inner}
    </span>
  );
}

export function ClerkStructuredResponse({
  data,
  className,
}: ClerkStructuredResponseProps) {
  const hasFactors = data.keyFactors && data.keyFactors.length > 0;
  const hasSources = data.sources && data.sources.length > 0;

  return (
    <Card className={cn("space-y-4 p-4", className)}>
      {/* Top row: verdict + confidence */}
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1 space-y-2">
          {data.policyDomain && (
            <Badge kind="info">{data.policyDomain}</Badge>
          )}
          {data.verdict && (
            <p className="text-sm font-semibold leading-relaxed">
              {data.verdict}
            </p>
          )}
          {data.methodology && (
            <p className="text-xs text-[var(--slate)]">
              {data.methodology}
            </p>
          )}
        </div>
        {data.confidence != null && (
          <div className="shrink-0">
            <ConfidenceGauge
              value={data.confidence}
              label={data.confidenceLevel}
              size={80}
            />
          </div>
        )}
      </div>

      {/* Status chips (progressive build) */}
      {data.statusChips && data.statusChips.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {data.statusChips.map((chip, i) => (
            <Badge key={i} kind="neutral">
              {chip}
            </Badge>
          ))}
        </div>
      )}

      {/* Key factors */}
      {hasFactors && (
        <div className="space-y-2">
          <h5 className="text-xs font-semibold uppercase tracking-wider text-[var(--slate)]">
            Key Factors
          </h5>
          <div className="space-y-1.5">
            {data.keyFactors!.map((f, i) => (
              <KeyFactorRow key={i} factor={f} />
            ))}
          </div>
        </div>
      )}

      {/* Source citations */}
      {hasSources && (
        <div className="space-y-2">
          <h5 className="text-xs font-semibold uppercase tracking-wider text-[var(--slate)]">
            Sources
          </h5>
          <div className="flex flex-wrap gap-1.5">
            {data.sources!.map((s) => (
              <SourceCitationChip key={s.id} source={s} />
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
