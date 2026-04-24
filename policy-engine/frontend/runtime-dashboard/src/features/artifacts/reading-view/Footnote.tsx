import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

import type { ReadingViewFootnote } from "./reading-view-tokens";

type FootnoteReferenceProps = {
  noteId: string;
  label?: string;
};

type FootnoteListProps = {
  notes: ReadingViewFootnote[];
  className?: string;
} & Omit<HTMLAttributes<HTMLOListElement>, "children">;

export function FootnoteReference({
  noteId,
  label = noteId,
}: FootnoteReferenceProps) {
  return (
    <a
      href={`#footnote-${noteId}`}
      aria-label={`Footnote ${label}`}
      className="footnote-ref align-super text-[0.72em] font-semibold no-underline"
    >
      [{label}]
    </a>
  );
}

export function FootnoteList({ notes, className, ...rest }: FootnoteListProps) {
  if (notes.length === 0) {
    return null;
  }

  return (
    <ol
      {...rest}
      className={cn(
        "reading-footnotes border-line text-muted mt-8 space-y-3 border-t pt-4 text-sm",
        className,
      )}
    >
      {notes.map((note, index) => (
        <li key={note.id} id={`footnote-${note.id}`}>
          <span className="text-ink font-semibold">
            {note.label ?? index + 1}.
          </span>{" "}
          <span>{note.body}</span>
        </li>
      ))}
    </ol>
  );
}
