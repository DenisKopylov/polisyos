export const SUPPORTED_LOCALES = ["en", "uk"] as const;

export type Locale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_STORAGE_KEY = "polisyos.runtime.locale";

export function isLocale(value: string | null | undefined): value is Locale {
  return value === "en" || value === "uk";
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
    const preferred = navigator.language.toLowerCase();
    if (preferred.startsWith("uk")) {
      return "uk";
    }
  }

  return DEFAULT_LOCALE;
}

export function toIntlLocale(locale: Locale): string {
  return locale === "uk" ? "uk-UA" : "en-US";
}
