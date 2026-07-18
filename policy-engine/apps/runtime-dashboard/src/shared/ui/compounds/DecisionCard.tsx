import type { ReactNode } from "react";

import { Badge, Card, type BadgeTone } from "@polisyos/atlas-ui";

export type DecisionCardDiagnostic = {
  kind?: BadgeTone;
  label: string;
};

type DecisionCardProps = {
  title: string;
  subtitle?: ReactNode;
  verdict: ReactNode;
  verdictKind?: BadgeTone;
  confidence?: ReactNode;
  confidenceKind?: BadgeTone;
  summary?: ReactNode;
  diagnostics?: DecisionCardDiagnostic[];
  meta?: Array<{
    label: string;
    value: ReactNode;
  }>;
  eyebrow?: ReactNode;
  sigil?: ReactNode;
  children?: ReactNode;
};

export function DecisionCard({
  children,
  confidence,
  confidenceKind = "neutral",
  diagnostics = [],
  eyebrow,
  meta = [],
  sigil,
  subtitle,
  summary,
  title,
  verdict,
  verdictKind = "neutral",
}: DecisionCardProps) {
  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          {eyebrow ? <div className="mb-1">{eyebrow}</div> : null}
          <h3 className="text-lg font-semibold">{title}</h3>
          {subtitle ? (
            <div className="text-muted text-sm">{subtitle}</div>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {sigil ? <div className="mr-1 shrink-0">{sigil}</div> : null}
          <Badge kind={verdictKind}>{verdict}</Badge>
          {confidence ? (
            <Badge kind={confidenceKind}>{confidence}</Badge>
          ) : null}
        </div>
      </div>

      {summary ? (
        <div className="border-line bg-surface/70 text-muted rounded-2xl border p-3 text-sm">
          {summary}
        </div>
      ) : null}

      {diagnostics.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {diagnostics.map((diagnostic) => (
            <Badge
              key={`${diagnostic.kind ?? "neutral"}-${diagnostic.label}`}
              kind={diagnostic.kind ?? "neutral"}
            >
              {diagnostic.label}
            </Badge>
          ))}
        </div>
      ) : null}

      {meta.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {meta.map((item) => (
            <div
              key={item.label}
              className="border-line bg-canvas/30 rounded-2xl border p-3 text-sm"
            >
              <p className="text-muted text-xs tracking-wide uppercase">
                {item.label}
              </p>
              <div className="mt-2 font-semibold">{item.value}</div>
            </div>
          ))}
        </div>
      ) : null}

      {children}
    </Card>
  );
}
