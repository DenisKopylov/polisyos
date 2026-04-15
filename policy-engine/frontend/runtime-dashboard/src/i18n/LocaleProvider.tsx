import {
  createContext,
  type PropsWithChildren,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import type { Locale } from "./locale";
import { persistLocale, resolveLocale } from "./locale";
import en from "./messages/en";
import uk from "./messages/uk";

const catalogs = { en, uk } as const;

type LabelMapName = keyof typeof en.labels;

type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (path: string, vars?: Record<string, string | number>) => string;
  label: (
    mapName: LabelMapName,
    value: string | null | undefined,
    fallback?: string,
  ) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

function humanize(value: string): string {
  return value
    .replace(/[_.-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function readPathValue(source: unknown, path: string): string | null {
  const segments = path.split(".");
  let current: unknown = source;
  for (const segment of segments) {
    if (!current || typeof current !== "object" || !(segment in current)) {
      return null;
    }
    current = (current as Record<string, unknown>)[segment];
  }
  return typeof current === "string" ? current : null;
}

function interpolate(
  template: string,
  vars?: Record<string, string | number>,
): string {
  if (!vars) {
    return template;
  }
  return Object.entries(vars).reduce(
    (result, [key, value]) => result.split(`{{${key}}}`).join(String(value)),
    template,
  );
}

function createI18nContextValue(
  locale: Locale,
  setLocale: (locale: Locale) => void,
): I18nContextValue {
  const catalog = catalogs[locale];

  return {
    locale,
    setLocale,
    t: (path, vars) => {
      const translated =
        readPathValue(catalog, path) ??
        readPathValue(catalogs.en, path) ??
        path;
      return interpolate(translated, vars);
    },
    label: (mapName, value, fallback) => {
      if (!value) {
        return fallback ?? "-";
      }
      const direct =
        readPathValue(catalog.labels[mapName], value) ??
        readPathValue(catalogs.en.labels[mapName], value);
      if (direct) {
        return direct;
      }
      return fallback ?? humanize(value);
    },
  };
}

export function LocaleProvider({ children }: PropsWithChildren) {
  const [locale, setLocaleState] = useState<Locale>(() => resolveLocale());

  useEffect(() => {
    persistLocale(locale);
    document.documentElement.lang = locale;
  }, [locale]);

  const value = useMemo<I18nContextValue>(
    () => createI18nContextValue(locale, setLocaleState),
    [locale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useOptionalI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  return context ?? createI18nContextValue(resolveLocale(), () => undefined);
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within LocaleProvider");
  }
  return context;
}
