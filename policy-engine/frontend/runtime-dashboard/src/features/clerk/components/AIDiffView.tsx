import { useState, useMemo } from "react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import { Card, Button, Badge } from "@/shared/ui/primitives";

type DiffSection = {
  before: string;
  after: string;
  sectionLabel?: string;
};

type SectionDecision = "pending" | "accepted" | "rejected" | "edited";

type AIDiffViewProps = {
  sections: DiffSection[];
  onAcceptAll?: () => void;
  onRejectAll?: () => void;
  onDecisionsComplete?: (
    decisions: {
      section: DiffSection;
      decision: SectionDecision;
      editedText?: string;
    }[],
  ) => void;
  className?: string;
};

function computeLineDiff(
  before: string,
  after: string,
): { before: DiffLine[]; after: DiffLine[] } {
  const beforeLines = before.split("\n");
  const afterLines = after.split("\n");

  // Simple LCS-based diff
  const m = beforeLines.length;
  const n = afterLines.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () =>
    Array(n + 1).fill(0),
  );

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (beforeLines[i - 1] === afterLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  const beforeDiff: DiffLine[] = [];
  const afterDiff: DiffLine[] = [];
  let i = m;
  let j = n;

  const beforeTemp: DiffLine[] = [];
  const afterTemp: DiffLine[] = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && beforeLines[i - 1] === afterLines[j - 1]) {
      beforeTemp.push({ text: beforeLines[i - 1], type: "unchanged" });
      afterTemp.push({ text: afterLines[j - 1], type: "unchanged" });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      afterTemp.push({ text: afterLines[j - 1], type: "added" });
      j--;
    } else {
      beforeTemp.push({ text: beforeLines[i - 1], type: "removed" });
      i--;
    }
  }

  beforeDiff.push(...beforeTemp.reverse());
  afterDiff.push(...afterTemp.reverse());

  return { before: beforeDiff, after: afterDiff };
}

type DiffLine = {
  text: string;
  type: "unchanged" | "added" | "removed";
};

function DiffPanel({
  lines,
  side,
}: {
  lines: DiffLine[];
  side: "before" | "after";
}) {
  return (
    <div className="flex-1 overflow-x-auto">
      <pre className="text-xs leading-relaxed">
        {lines.map((line, i) => (
          <div
            key={i}
            className={cn(
              "px-3 py-0.5",
              line.type === "removed" &&
                "bg-[color-mix(in_srgb,var(--color-status-rejected)_10%,transparent)] text-[var(--color-status-rejected)]",
              line.type === "added" &&
                "bg-[color-mix(in_srgb,var(--color-status-approved)_10%,transparent)] text-[var(--color-status-approved)]",
            )}
          >
            <span className="mr-3 inline-block w-4 text-right text-[var(--slate)]">
              {line.type === "removed" && side === "before" ? "-" : ""}
              {line.type === "added" && side === "after" ? "+" : ""}
            </span>
            {line.text}
          </div>
        ))}
      </pre>
    </div>
  );
}

function DiffSectionCard({
  section,
  index,
  decision,
  onDecision,
  t,
}: {
  section: DiffSection;
  index: number;
  decision: SectionDecision;
  onDecision: (d: SectionDecision) => void;
  t: ReturnType<typeof useI18n>["t"];
}) {
  const { before, after } = useMemo(
    () => computeLineDiff(section.before, section.after),
    [section.before, section.after],
  );
  const [showEdit, setShowEdit] = useState(false);
  const [editText, setEditText] = useState(section.after);

  const decisionBadge: Record<
    SectionDecision,
    { kind: "ok" | "fail" | "warn" | "neutral"; label: string }
  > = {
    pending: { kind: "neutral", label: t("clerk.diff.pending") },
    accepted: { kind: "ok", label: t("clerk.diff.accepted") },
    rejected: { kind: "fail", label: t("clerk.diff.rejected") },
    edited: { kind: "warn", label: t("clerk.diff.edited") },
  };

  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 border-b border-[var(--line)] px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-[var(--slate)]">
            {t("clerk.diff.section", { index: index + 1 })}
          </span>
          {section.sectionLabel && (
            <span className="text-xs text-[var(--ink)]">
              {section.sectionLabel}
            </span>
          )}
          <Badge kind={decisionBadge[decision].kind}>
            {decisionBadge[decision].label}
          </Badge>
        </div>
        <div className="flex gap-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onDecision("accepted")}
            disabled={decision === "accepted"}
          >
            {t("clerk.diff.accept")}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onDecision("rejected")}
            disabled={decision === "rejected"}
          >
            {t("clerk.diff.reject")}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              setShowEdit(!showEdit);
              if (!showEdit) setEditText(section.after);
            }}
          >
            {t("clerk.diff.edit")}
          </Button>
        </div>
      </div>

      {/* Diff content */}
      {!showEdit ? (
        <div className="flex divide-x divide-[var(--line)]">
          <div className="flex-1">
            <div className="bg-[var(--surface)] px-3 py-1 text-[10px] font-semibold text-[var(--slate)] uppercase">
              {t("clerk.diff.current")}
            </div>
            <DiffPanel lines={before} side="before" />
          </div>
          <div className="flex-1">
            <div className="bg-[var(--surface)] px-3 py-1 text-[10px] font-semibold text-[var(--slate)] uppercase">
              {t("clerk.diff.proposed")}
            </div>
            <DiffPanel lines={after} side="after" />
          </div>
        </div>
      ) : (
        <div className="p-3">
          <textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            className="w-full rounded-lg border border-[var(--line)] bg-[var(--surface)] p-3 font-mono text-xs leading-relaxed focus:border-[var(--teal)] focus:ring-2 focus:ring-[var(--focus-ring)] focus:outline-none"
            rows={10}
          />
          <div className="mt-2 flex justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setShowEdit(false)}
            >
              {t("common.cancel")}
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={() => {
                onDecision("edited");
                setShowEdit(false);
              }}
            >
              {t("clerk.diff.applyEdit")}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

export function AIDiffView({
  sections,
  onAcceptAll,
  onRejectAll,
  onDecisionsComplete,
  className,
}: AIDiffViewProps) {
  const { t } = useI18n();
  const [decisions, setDecisions] = useState<SectionDecision[]>(() =>
    sections.map(() => "pending"),
  );

  const handleDecision = (index: number, decision: SectionDecision) => {
    setDecisions((prev) => {
      const next = [...prev];
      next[index] = decision;
      return next;
    });
  };

  const allDecided = decisions.every((d) => d !== "pending");
  const acceptedCount = decisions.filter(
    (d) => d === "accepted" || d === "edited",
  ).length;

  return (
    <div className={cn("space-y-3", className)}>
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h4 className="text-sm font-semibold">
            {t("clerk.diff.reviewTitle")}
          </h4>
          <Badge kind="info">
            {t("clerk.diff.acceptedSummary", {
              accepted: acceptedCount,
              total: sections.length,
            })}
          </Badge>
        </div>
        <div className="flex gap-2">
          {onAcceptAll && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setDecisions(sections.map(() => "accepted"));
                onAcceptAll();
              }}
            >
              {t("clerk.diff.acceptAll")}
            </Button>
          )}
          {onRejectAll && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setDecisions(sections.map(() => "rejected"));
                onRejectAll();
              }}
            >
              {t("clerk.diff.rejectAll")}
            </Button>
          )}
          {allDecided && onDecisionsComplete && (
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={() =>
                onDecisionsComplete(
                  sections.map((s, i) => ({
                    section: s,
                    decision: decisions[i],
                  })),
                )
              }
            >
              {t("clerk.diff.applyDecisions")}
            </Button>
          )}
        </div>
      </div>

      {/* Diff sections */}
      {sections.map((section, i) => (
        <DiffSectionCard
          key={i}
          section={section}
          index={i}
          decision={decisions[i]}
          t={t}
          onDecision={(d) => handleDecision(i, d)}
        />
      ))}
    </div>
  );
}

export type { DiffSection, SectionDecision };
