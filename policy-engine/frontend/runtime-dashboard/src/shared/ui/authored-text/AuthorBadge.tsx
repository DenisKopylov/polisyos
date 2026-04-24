import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

import { AUTHOR_REGISTRY, type AuthoredTextAuthor } from "./author-registry";

const HUMAN_REVIEWED_LABEL = "Human reviewed";

type AuthorBadgeProps = {
  author: AuthoredTextAuthor;
  sourceRef?: string;
  sourceHref?: string;
  authorAgentVersion?: string;
  reviewedByHuman?: boolean;
  className?: string;
};

export function AuthorBadge({
  author,
  sourceRef,
  sourceHref,
  authorAgentVersion,
  reviewedByHuman = false,
  className,
}: AuthorBadgeProps) {
  const entry = AUTHOR_REGISTRY[author];
  const label =
    author === "citation" && sourceRef
      ? `${entry.badgeLabel} · ${sourceRef}`
      : entry.badgeLabel;
  const detail = reviewedByHuman
    ? HUMAN_REVIEWED_LABEL
    : (authorAgentVersion ?? null);
  const style = {
    "--author-badge-accent": `var(${entry.borderVar})`,
  } as CSSProperties;

  const content = (
    <>
      {entry.glyph ? (
        <span aria-hidden="true" className="font-mono text-[11px]">
          {entry.glyph}
        </span>
      ) : null}
      <span>{label}</span>
      {detail ? (
        <span className="text-[color-mix(in_srgb,var(--ink)_56%,transparent)]">
          {detail}
        </span>
      ) : null}
    </>
  );

  const sharedClassName = cn(
    "inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] uppercase",
    "border-[color:var(--author-badge-accent)]/30 bg-[color-mix(in_srgb,var(--author-badge-accent)_10%,var(--panel))]",
    className,
  );

  if (sourceHref) {
    return (
      <a href={sourceHref} className={sharedClassName} style={style}>
        {content}
      </a>
    );
  }

  return (
    <span className={sharedClassName} style={style}>
      {content}
    </span>
  );
}
