import { useOptionalI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";
import { AuthoredText } from "@/shared/ui/authored-text";

import type { ReadingViewMarginNote } from "./reading-view-tokens";

type MarginNotesProps = {
  notes: ReadingViewMarginNote[];
  positions?: Record<string, number>;
  inline?: boolean;
  className?: string;
};

type StackedNote = ReadingViewMarginNote & {
  top: number;
};

const MIN_NOTE_GAP = 84;

function stackNotes(
  notes: ReadingViewMarginNote[],
  positions: Record<string, number>,
): StackedNote[] {
  const ordered = [...notes]
    .map((note) => ({
      ...note,
      top: positions[note.anchorId] ?? 0,
    }))
    .sort((left, right) => left.top - right.top);

  let cursor = 0;
  return ordered.map((note) => {
    const top = Math.max(note.top, cursor);
    cursor = top + MIN_NOTE_GAP;
    return { ...note, top };
  });
}

export function MarginNotes({
  notes,
  positions = {},
  inline = false,
  className,
}: MarginNotesProps) {
  const { t } = useOptionalI18n();

  if (notes.length === 0) {
    return null;
  }

  if (inline) {
    return (
      <div className={cn("mt-5 space-y-3", className)}>
        {notes.map((note, index) => (
          <aside
            key={note.id}
            className="margin-note border-line bg-surface/70 rounded-2xl border px-4 py-3"
            data-testid={`margin-note-${note.id}`}
          >
            <p
              className="text-muted text-[0.68rem] font-semibold tracking-[0.18em] uppercase"
              data-authored-exempt="true"
              data-authored-exempt-reason="Margin-note label is structural chrome, not authored prose."
            >
              {note.label ??
                t("pages.artifacts.readingView.noteLabel", {
                  index: index + 1,
                })}
            </p>
            <AuthoredText
              as="p"
              author="human"
              className="mt-2 text-sm leading-relaxed"
            >
              {note.body}
            </AuthoredText>
          </aside>
        ))}
      </div>
    );
  }

  const stacked = stackNotes(notes, positions);

  return (
    <aside
      aria-label={t("pages.artifacts.readingView.marginNotesAria")}
      className={cn(
        "pointer-events-none absolute inset-y-0 right-0 hidden xl:block",
        className,
      )}
    >
      {stacked.map((note, index) => (
        <div
          key={note.id}
          className="margin-note pointer-events-auto"
          data-testid={`margin-note-${note.id}`}
          style={{ top: `${note.top}px` }}
        >
          <p
            className="text-muted text-[0.68rem] font-semibold tracking-[0.18em] uppercase"
            data-authored-exempt="true"
            data-authored-exempt-reason="Margin-note label is structural chrome, not authored prose."
          >
            {note.label ??
              t("pages.artifacts.readingView.noteLabel", {
                index: index + 1,
              })}
          </p>
          <AuthoredText as="p" author="human" className="mt-2 leading-relaxed">
            {note.body}
          </AuthoredText>
        </div>
      ))}
    </aside>
  );
}
