import type {
  DecisionPacketAuthoredBlock,
  PolicyDesignCaseProjection,
} from "@polisyos/runtime-api-client";
import { Badge } from "@polisyos/atlas-ui";

import { cn } from "@/shared/lib/utils";
import { AuthoredText } from "@/shared/ui/authored-text";

import { DecisionCard } from "./DecisionCard";

const DECLARED_PURPOSES_LABEL = "Producer-declared authority purposes";
const ABSENT_PURPOSE_LABEL = "Authority purpose absent";
const EXCLUDED_PURPOSES_LABEL = "Producer-declared excluded purposes";

export type CandidateFrameProps = {
  authorityPurpose?: PolicyDesignCaseProjection["authoritative_for"];
  block: DecisionPacketAuthoredBlock;
  className?: string;
  mayNotUseFor?: PolicyDesignCaseProjection["may_not_be_used_for"];
  title: string;
};

/**
 * Frames authored model material without granting it authority presentation.
 *
 * The generated projection fields are displayed opaquely. They describe the
 * producer's declared purpose; they never promote the authored block itself.
 */
export function CandidateFrame({
  authorityPurpose,
  block,
  className,
  mayNotUseFor,
  title,
}: CandidateFrameProps) {
  const declaredPurposes = authorityPurpose ?? [];
  const excludedPurposes = mayNotUseFor ?? [];
  const firstSource = block.sources?.[0];

  return (
    <div
      className={cn(
        "rounded-[var(--radius-panel)] border border-dashed border-[var(--teal)]/50",
        className,
      )}
      data-authority-posture="candidate"
      data-authority-purpose={
        declaredPurposes.length > 0 ? "declared" : "absent"
      }
      data-testid="candidate-frame"
    >
      <DecisionCard title={title} verdict={null}>
        <AuthoredText
          author={block.author ?? null}
          authorAgentVersion={block.author_agent_version ?? undefined}
          confidence={block.confidence ?? undefined}
          reviewedByHuman={Boolean(block.reviewed_by_human)}
          sourceHref={firstSource?.href}
          sourceRef={firstSource?.ref}
          timestamp={block.timestamp ?? undefined}
        >
          {block.content}
        </AuthoredText>

        {declaredPurposes.length > 0 ? (
          <div
            aria-label={DECLARED_PURPOSES_LABEL}
            className="flex flex-wrap gap-2"
          >
            {declaredPurposes.map((purpose) => (
              <Badge key={purpose} kind="neutral">
                {purpose}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-muted text-xs">{ABSENT_PURPOSE_LABEL}</p>
        )}

        {excludedPurposes.length > 0 ? (
          <div aria-label={EXCLUDED_PURPOSES_LABEL}>
            <ul className="text-muted list-disc space-y-1 pl-5 text-xs">
              {excludedPurposes.map((purpose) => (
                <li key={purpose}>{purpose}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </DecisionCard>
    </div>
  );
}
