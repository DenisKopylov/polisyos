import {
  type CSSProperties,
  type ComponentPropsWithoutRef,
  type ElementType,
  type ReactNode,
  useEffect,
  useId,
} from "react";

import { cn } from "@/lib/utils";
import { useMaybeTrustView } from "@/app/providers/useTrustView";
import {
  TrustMetadata,
  type VerificationMetadata,
} from "@/shared/ui/trust-view";

import { AuthorBadge } from "./AuthorBadge";
import { useAuthorship } from "./AuthorshipProvider";
import {
  AUTHOR_REGISTRY,
  extractTextFromNode,
  type AuthoredTextAuthor,
} from "./author-registry";

type AuthoredTextProps<T extends ElementType = "p"> = {
  as?: T;
  author: AuthoredTextAuthor;
  authorAgentVersion?: string;
  children: ReactNode;
  className?: string;
  confidence?: number;
  reviewedByHuman?: boolean;
  sourceHref?: string;
  sourceRef?: string;
  timestamp?: string;
  trustMetadata?: VerificationMetadata | null;
} & Omit<ComponentPropsWithoutRef<T>, "as" | "children" | "className">;

export function AuthoredText<T extends ElementType = "p">({
  as,
  author,
  authorAgentVersion,
  children,
  className,
  confidence,
  reviewedByHuman = false,
  sourceHref,
  sourceRef,
  timestamp,
  trustMetadata,
  ...props
}: AuthoredTextProps<T>) {
  const Component = (as ?? "p") as ElementType;
  const authoredTextId = useId();
  const { highlightMode, registerBlock, unregisterBlock } = useAuthorship();
  const trustView = useMaybeTrustView();
  const entry = AUTHOR_REGISTRY[author];
  const announcedText = entry.announcement(sourceRef);
  const extractedText = extractTextFromNode(children);
  const showBorder =
    highlightMode !== "off" && (author === "citation" || author !== "human");
  const showGlyph =
    highlightMode !== "off" && author !== "citation" && author !== "human";
  const showBadge = highlightMode === "prominent" || author === "citation";
  const trustMode =
    trustView?.mode === "expanded"
      ? "expanded"
      : trustView?.mode === "compact"
        ? "compact"
        : "off";
  const resolvedTrustMetadata =
    trustMetadata ??
    buildAuthoredTrustMetadata({
      author,
      authorAgentVersion,
      reviewedByHuman,
      sourceRef,
      timestamp,
    });
  const style = {
    ...(props.style as CSSProperties | undefined),
    ...(showBorder
      ? {
          borderLeftColor: `var(${entry.borderVar})`,
          borderLeftWidth: author === "citation" ? "2px" : "1px",
          paddingLeft: "0.9rem",
        }
      : {}),
    ...(author === "citation"
      ? {
          fontFamily:
            '"Instrument Serif", "Iowan Old Style", "Palatino Linotype", Georgia, serif',
          fontStyle: "italic",
        }
      : {}),
  } satisfies CSSProperties;

  useEffect(() => {
    registerBlock({
      id: authoredTextId,
      author,
      authorAgentVersion,
      confidence,
      reviewedByHuman,
      sourceHref,
      sourceRef,
      text: extractedText,
      timestamp,
    });

    return () => unregisterBlock(authoredTextId);
  }, [
    author,
    authorAgentVersion,
    authoredTextId,
    confidence,
    extractedText,
    registerBlock,
    reviewedByHuman,
    sourceHref,
    sourceRef,
    timestamp,
    unregisterBlock,
  ]);

  return (
    <Component
      {...props}
      data-author={author}
      data-highlight-mode={highlightMode}
      className={cn(
        "block text-[var(--ink)]",
        author === "citation"
          ? "text-[1.02rem] leading-relaxed"
          : "leading-relaxed font-normal",
        className,
      )}
      style={style}
    >
      <span className="sr-only">{`${announcedText}. `}</span>
      {showGlyph && entry.glyph ? (
        <span
          aria-hidden="true"
          className={cn(
            "mr-2 inline-flex align-baseline font-mono text-sm",
            entry.toneClassName,
          )}
        >
          {entry.glyph}
        </span>
      ) : null}
      <span>{children}</span>
      {showBadge ? (
        <span className="mt-2 block">
          <AuthorBadge
            author={author}
            authorAgentVersion={authorAgentVersion}
            reviewedByHuman={reviewedByHuman}
            sourceHref={sourceHref}
            sourceRef={sourceRef}
          />
        </span>
      ) : null}
      {trustMode !== "off" ? (
        <span className="mt-2 block">
          <TrustMetadata
            hash={resolvedTrustMetadata.hash}
            label={entry.badgeLabel}
            metadata={resolvedTrustMetadata}
            mode={trustMode}
            subjectId={authoredTextId}
            subjectKind="authored_text"
          />
        </span>
      ) : null}
    </Component>
  );
}

function buildAuthoredTrustMetadata({
  author,
  authorAgentVersion,
  reviewedByHuman,
  sourceRef,
  timestamp,
}: {
  author: AuthoredTextAuthor;
  authorAgentVersion?: string;
  reviewedByHuman: boolean;
  sourceRef?: string;
  timestamp?: string;
}): VerificationMetadata {
  const hash = sourceRef?.startsWith("sha256:") ? sourceRef : null;
  return {
    dispute_status: "none",
    freshness: "current",
    hash,
    temporal_scope: timestamp ? { valid_at: timestamp } : null,
    verification_method: sourceRef
      ? "authorship_source_ref"
      : "authorship_registry",
    verification_status: reviewedByHuman ? "verified" : "pending",
    verified_at: timestamp ?? null,
    verified_by: reviewedByHuman
      ? author
      : (authorAgentVersion ?? "PolicyOSAuthorshipRegistry"),
  };
}
