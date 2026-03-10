import {
  createContext,
  type PropsWithChildren,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { useFeatureFlag } from "@/app/providers/FeatureFlagProvider";

export const SUPPORTED_THEMES = ["light", "dark", "system"] as const;

export type ThemePreference = (typeof SUPPORTED_THEMES)[number];
export type ResolvedTheme = Exclude<ThemePreference, "system">;

const THEME_STORAGE_KEY = "polisyos.runtime.theme";

type ThemeContextValue = {
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: ThemePreference) => void;
  theme: ThemePreference;
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function isThemePreference(
  value: string | null | undefined,
): value is ThemePreference {
  return value === "light" || value === "dark" || value === "system";
}

function readStoredTheme(): ThemePreference | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(THEME_STORAGE_KEY);
  return isThemePreference(raw) ? raw : null;
}

function resolveThemePreference(): ThemePreference {
  return readStoredTheme() ?? "system";
}

function resolveSystemTheme(): ResolvedTheme {
  if (typeof window === "undefined") {
    return "light";
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function resolveTheme(theme: ThemePreference): ResolvedTheme {
  return theme === "system" ? resolveSystemTheme() : theme;
}

export function ThemeProvider({ children }: PropsWithChildren) {
  const darkModeEnabled = useFeatureFlag("enableDarkMode");
  const [theme, setThemeState] = useState<ThemePreference>(() =>
    resolveThemePreference(),
  );
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() =>
    resolveTheme(resolveThemePreference()),
  );

  useEffect(() => {
    if (!darkModeEnabled) {
      setResolvedTheme("light");
      document.documentElement.dataset.theme = "light";
      document.documentElement.style.colorScheme = "light";
      return;
    }

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const applyTheme = (preference: ThemePreference) => {
      const nextResolved = resolveTheme(preference);
      setResolvedTheme(nextResolved);
      document.documentElement.dataset.theme = nextResolved;
      document.documentElement.style.colorScheme = nextResolved;
    };

    applyTheme(theme);

    const handleChange = () => {
      if (theme === "system") {
        applyTheme("system");
      }
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, [darkModeEnabled, theme]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(
      THEME_STORAGE_KEY,
      darkModeEnabled ? theme : "light",
    );
  }, [darkModeEnabled, theme]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      resolvedTheme,
      setTheme: (nextTheme) => setThemeState(nextTheme),
      theme: darkModeEnabled ? theme : "light",
      toggleTheme: () => {
        setThemeState((current) => {
          if (!darkModeEnabled) {
            return "light";
          }
          if (current === "system") {
            return "dark";
          }
          if (current === "dark") {
            return "light";
          }
          return "system";
        });
      },
    }),
    [darkModeEnabled, resolvedTheme, theme],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return context;
}
