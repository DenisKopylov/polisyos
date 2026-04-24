import type { Locale } from "../locale";

const NBSP = "\u00A0";

const SHORT_PREPOSITIONS: Record<Locale, string[]> = {
  en: [],
  uk: [
    "в",
    "у",
    "з",
    "і",
    "й",
    "та",
    "на",
    "до",
    "від",
    "за",
    "під",
    "над",
    "про",
  ],
  ru: ["в", "у", "о", "к", "с", "и", "а", "но"],
};

function buildShortPrepositionPattern(locale: Locale): RegExp | null {
  const words = SHORT_PREPOSITIONS[locale] ?? SHORT_PREPOSITIONS.en;
  if (words.length === 0) {
    return null;
  }

  return new RegExp(
    `(^|[\\s(\\[{"«„“])(${words.join("|")})(?:[ \\t]+)(?=\\S)`,
    "giu",
  );
}

export function insertNonBreakingSpaces(text: string, locale: Locale): string {
  const pattern = buildShortPrepositionPattern(locale);
  if (!pattern) {
    return text;
  }

  return text.replace(pattern, (_match, prefix: string, word: string) => {
    return `${prefix}${word}${NBSP}`;
  });
}

export function hasShortPrepositionSpacingIssue(
  text: string,
  locale: Locale,
): boolean {
  return insertNonBreakingSpaces(text, locale) !== text;
}
