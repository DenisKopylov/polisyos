import { cn } from "@/lib/utils";

type ClerkSuggestionChipsProps = {
  suggestions: string[];
  onSelect: (question: string) => void;
  className?: string;
};

export function ClerkSuggestionChips({
  suggestions,
  onSelect,
  className,
}: ClerkSuggestionChipsProps) {
  if (suggestions.length === 0) return null;

  return (
    <div
      className={cn("flex flex-wrap gap-2", className)}
      role="group"
      aria-label="Suggested follow-up questions"
    >
      {suggestions.map((suggestion, i) => (
        <button
          key={i}
          type="button"
          onClick={() => onSelect(suggestion)}
          className="rounded-[var(--radius-pill)] border border-[var(--line)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--ink)] transition-colors hover:border-[var(--teal)] hover:bg-[var(--teal-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)]"
        >
          {suggestion}
        </button>
      ))}
    </div>
  );
}
