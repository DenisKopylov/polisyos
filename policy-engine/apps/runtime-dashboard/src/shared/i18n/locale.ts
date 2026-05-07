export const SUPPORTED_LOCALES = ["en", "uk", "ru"] as const;

export type Locale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_STORAGE_KEY = "polisyos.runtime.locale";

const INTL_LOCALE_BY_LOCALE: Record<Locale, string> = {
  en: "en-US",
  uk: "uk-UA",
  ru: "ru-RU",
};

export function isLocale(value: string | null | undefined): value is Locale {
  return (
    value !== null &&
    value !== undefined &&
    SUPPORTED_LOCALES.includes(value as Locale)
  );
}

export function readStoredLocale(): Locale | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  return isLocale(raw) ? raw : null;
}

export function persistLocale(locale: Locale): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
}

export function resolveLocale(explicit?: string | null): Locale {
  if (isLocale(explicit)) {
    return explicit;
  }

  const stored = readStoredLocale();
  if (stored) {
    return stored;
  }

  if (typeof navigator !== "undefined") {
    const preferredLocales = [
      ...(navigator.languages ?? []),
      navigator.language,
    ].filter(Boolean);

    for (const preferred of preferredLocales) {
      const normalized = preferred.toLowerCase();
      if (normalized.startsWith("uk")) {
        return "uk";
      }
      if (normalized.startsWith("ru")) {
        return "ru";
      }
    }
  }

  return DEFAULT_LOCALE;
}

export function toIntlLocale(locale: Locale): string {
  return INTL_LOCALE_BY_LOCALE[locale];
}
