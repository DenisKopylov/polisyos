export const SUPPORTED_LOCALES = ["uk", "en"] as const;

export type ProductLocale = (typeof SUPPORTED_LOCALES)[number];
export type LegacyContinuityLocale = "ru";
export type Locale = ProductLocale | LegacyContinuityLocale;

export const DEFAULT_LOCALE: ProductLocale = "uk";
export const LOCALE_STORAGE_KEY = "polisyos.runtime.locale";

const INTL_LOCALE_BY_LOCALE: Record<Locale, string> = {
  en: "en-US",
  uk: "uk-UA",
  ru: "ru-RU",
};

export function isProductLocale(
  value: string | null | undefined,
): value is ProductLocale {
  return (
    value !== null &&
    value !== undefined &&
    SUPPORTED_LOCALES.includes(value as ProductLocale)
  );
}

function normalizeProductLocale(
  value: string | null | undefined,
): ProductLocale | null {
  if (value === null || value === undefined) {
    return null;
  }

  const match = /^(uk|en)(?:-[a-z]{2})?$/iu.exec(value);
  return match ? (match[1].toLowerCase() as ProductLocale) : null;
}

export function isLocale(value: string | null | undefined): value is Locale {
  return isProductLocale(value) || value === "ru";
}

export function readStoredLocale(): ProductLocale | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  return normalizeProductLocale(raw);
}

export function persistLocale(locale: ProductLocale): void {
  if (typeof window === "undefined" || !isProductLocale(locale)) {
    return;
  }
  window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
}

export function resolveLocale(explicit?: string | null): ProductLocale {
  if (explicit !== null && explicit !== undefined) {
    return normalizeProductLocale(explicit) ?? DEFAULT_LOCALE;
  }

  if (typeof window !== "undefined") {
    const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (stored !== null) {
      return normalizeProductLocale(stored) ?? DEFAULT_LOCALE;
    }
  }

  if (typeof navigator !== "undefined") {
    const preferredLocales = [
      ...(navigator.languages ?? []),
      navigator.language,
    ].filter(Boolean);

    for (const preferred of preferredLocales) {
      const preferredLocale = normalizeProductLocale(preferred);
      if (preferredLocale === "uk") {
        return "uk";
      }
    }
  }

  return DEFAULT_LOCALE;
}

export function toIntlLocale(locale: Locale): string {
  return INTL_LOCALE_BY_LOCALE[locale];
}
