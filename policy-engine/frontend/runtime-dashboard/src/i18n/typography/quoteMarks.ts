import type { Locale } from "../locale";

type QuotePair = readonly [open: string, close: string];
type QuoteMarks = {
  primary: QuotePair;
  secondary: QuotePair;
};

const QUOTE_MARKS: Record<Locale, QuoteMarks> = {
  en: {
    primary: ["“", "”"],
    secondary: ["‘", "’"],
  },
  uk: {
    primary: ["«", "»"],
    secondary: ["„", "“"],
  },
  ru: {
    primary: ["«", "»"],
    secondary: ["„", "“"],
  },
};

function isOpeningQuote(text: string, index: number): boolean {
  const previous = text[index - 1];
  if (!previous) {
    return true;
  }

  return /[\s([{<\u00A0«„“]/u.test(previous);
}

function convertStraightQuotes(text: string, locale: Locale): string {
  const marks = QUOTE_MARKS[locale] ?? QUOTE_MARKS.en;
  let depth = 0;
  let output = "";

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];

    if (character !== '"') {
      output += character;
      continue;
    }

    if (isOpeningQuote(text, index)) {
      const pair =
        depth === 0 || !marks.secondary ? marks.primary : marks.secondary;
      output += pair[0];
      depth += 1;
      continue;
    }

    depth = Math.max(0, depth - 1);
    const pair =
      depth === 0 || !marks.secondary ? marks.primary : marks.secondary;
    output += pair[1];
  }

  return output;
}

export function getLocaleQuoteMarks(locale: Locale): QuoteMarks {
  return QUOTE_MARKS[locale] ?? QUOTE_MARKS.en;
}

export function applyLocaleQuoteMarks(text: string, locale: Locale): string {
  const segments = text.split(/(`[^`]*`)/u);

  return segments
    .map((segment, index) =>
      index % 2 === 1 ? segment : convertStraightQuotes(segment, locale),
    )
    .join("");
}
