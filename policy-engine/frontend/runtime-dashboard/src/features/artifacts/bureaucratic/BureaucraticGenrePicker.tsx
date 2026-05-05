import { FileText } from "lucide-react";

import { useOptionalI18n } from "@/shared/i18n/LocaleProvider";

import {
  BUREAUCRATIC_GENRES,
  genreLabel,
  type BureaucraticGenre,
} from "./ast/bureaucratic-document-ast";
import { BUREAUCRATIC_TEMPLATE_HELP } from "./renderers/shared/bureaucratic-tokens";

type BureaucraticGenrePickerProps = {
  value: BureaucraticGenre;
  onChange: (genre: BureaucraticGenre) => void;
};

export function BureaucraticGenrePicker({
  value,
  onChange,
}: BureaucraticGenrePickerProps) {
  const { t } = useOptionalI18n();
  return (
    <div
      className="grid gap-2 md:grid-cols-4"
      role="radiogroup"
      aria-label={t("pages.artifacts.bureaucratic.renderAs")}
    >
      {BUREAUCRATIC_GENRES.map((genre) => {
        const selected = genre === value;
        return (
          <button
            key={genre}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(genre)}
            className={
              selected
                ? "border-text bg-text text-canvas flex min-h-16 items-start gap-2 rounded-md border px-3 py-2 text-left text-sm font-semibold"
                : "border-line bg-surface flex min-h-16 items-start gap-2 rounded-md border px-3 py-2 text-left text-sm font-semibold"
            }
          >
            <FileText className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>
              <span className="block">{genreLabel(genre)}</span>
              <span className="block font-mono text-xs opacity-80">
                {BUREAUCRATIC_TEMPLATE_HELP[genre]}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
