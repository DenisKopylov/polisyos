import { useOptionalI18n } from "@/shared/i18n/LocaleProvider";
import { Glyph } from "@/shared/brand/Glyph";
import { cn } from "@/shared/lib/utils";

import {
  sectionGlyphForType,
  sectionLabelForType,
  type ReadingViewSection,
} from "./reading-view-tokens";

type TableOfContentsGlyphedProps = {
  sections: ReadingViewSection[];
  activeSectionId?: string | null;
  className?: string;
};

export function TableOfContentsGlyphed({
  sections,
  activeSectionId,
  className,
}: TableOfContentsGlyphedProps) {
  const { t } = useOptionalI18n();

  if (sections.length === 0) {
    return null;
  }

  return (
    <nav
      aria-label={t("pages.artifacts.readingView.tocAria")}
      className={cn(
        "reading-toc border-line bg-panel/80 rounded-[28px] border p-4",
        className,
      )}
    >
      <p
        className="text-muted text-[0.68rem] font-semibold tracking-[0.2em] uppercase"
        data-authored-exempt="true"
        data-authored-exempt-reason="Table-of-contents heading is structural navigation chrome, not authored prose."
      >
        {t("pages.artifacts.readingView.tocTitle")}
      </p>
      <ol className="mt-4 space-y-2">
        {sections.map((section, index) => {
          const active = section.id === activeSectionId;
          return (
            <li key={section.id}>
              <a
                href={`#${section.id}`}
                className={cn(
                  "flex items-start gap-3 rounded-2xl px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-teal/10 text-ink"
                    : "text-muted hover:bg-surface/70 hover:text-ink",
                )}
              >
                <span className="mt-0.5 flex items-center gap-2 text-xs tracking-[0.16em] uppercase">
                  <Glyph
                    name={sectionGlyphForType(section.sectionType)}
                    size={12}
                    decorative
                  />
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="min-w-0">
                  <span className="block font-semibold">{section.title}</span>
                  <span className="text-muted mt-1 block text-[0.7rem] tracking-[0.16em] uppercase">
                    {sectionLabelForType(section.sectionType)}
                  </span>
                </span>
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
