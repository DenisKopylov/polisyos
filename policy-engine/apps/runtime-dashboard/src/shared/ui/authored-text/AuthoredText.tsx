import {
  type CSSProperties,
  type ComponentPropsWithoutRef,
  type ElementType,
  type ReactNode,
  useEffect,
  useId,
} from "react";

import { cn } from "@/shared/lib/utils";
import {
  TrustMetadata,
  type VerificationMetadata,
} from "@/shared/ui/trust-view";

import { AuthorBadge } from "./AuthorBadge";
import { useAuthorship } from "./AuthorshipProvider";
import {
  extractTextFromNode,
  getAuthorPresentation,
  type AuthoredTextAuthor,
} from "./author-registry";

type AuthoredTextProps<T extends ElementType = "p"> = {
  as?: T;
  author: AuthoredTextAuthor | null;
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
  const { highlightMode, registerBlock, trustDisplayMode, unregisterBlock } =
    useAuthorship();
  const entry = getAuthorPresentation(author);
  const announcedText = entry.announcement(sourceRef);
  const extractedText = extractTextFromNode(children);
  const showBorder =
    entry.isModelCandidate ||
    (highlightMode !== "off" && author === "citation");
  const showGlyph =
    highlightMode !== "off" && author !== "citation" && author !== "human";
  const showBadge = highlightMode === "prominent" || author === "citation";
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
    <>
      <Component
        {...props}
        data-author={author ?? "unrecognized"}
        data-authority-posture={
          entry.isModelCandidate ? "candidate" : "attributed"
        }
        data-highlight-mode={highlightMode}
        data-review-attribution={reviewedByHuman ? "recorded" : "absent"}
        className={cn(
          "block text-[var(--ink)]",
          author === "citation"
            ? "text-[1.02rem] leading-relaxed"
            : "leading-relaxed font-normal",
          entry.isModelCandidate && "border-dashed",
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
      </Component>
      {trustDisplayMode !== "off" && trustMetadata ? (
        <TrustMetadata
          className="mt-2"
          hash={trustMetadata.hash}
          label={entry.badgeLabel}
          metadata={trustMetadata}
          mode={trustDisplayMode}
          subjectId={authoredTextId}
          subjectKind="authored_text"
        />
      ) : null}
    </>
  );
}
