import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";

import { LocaleProvider, useI18n } from "@/shared/i18n/LocaleProvider";
import { formatNumber } from "@/shared/i18n/formatters/number";
import { formatIcuMessage } from "@/shared/i18n/messages/icu-messages";
import {
  DEFAULT_LOCALE,
  LEGACY_CONTINUITY_LOCALE,
  LOCALE_STORAGE_KEY,
  PRIMARY_LOCALE,
  SUPPORTED_LOCALES,
  TRANSLATED_LOCALES,
  persistLocale,
  readStoredLocale,
  resolveLocale,
  toIntlLocale,
} from "@/shared/i18n/locale";

function Wrapper({ children }: PropsWithChildren) {
  return <LocaleProvider>{children}</LocaleProvider>;
}

describe("LocaleProvider", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.lang = "";
    Object.defineProperty(window.navigator, "language", {
      configurable: true,
      value: "en-US",
    });
    Object.defineProperty(window.navigator, "languages", {
      configurable: true,
      value: ["en-US"],
    });
  });

  it("hydrates locale state, persists changes, interpolates text, and humanizes missing labels", async () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "uk");

    const { result } = renderHook(() => useI18n(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.locale).toBe("uk"));
    expect(document.documentElement.lang).toBe("uk");
    expect(
      result.current.t("pages.evidence.contextTitle", { runId: "run-7" }),
    ).toBe("Evidence context для запуску run-7");
    expect(result.current.t("shell.header.runsInReview", { count: 1 })).toBe(
      "1 запуск у review",
    );
    expect(result.current.t("shell.header.runsInReview", { count: 2 })).toBe(
      "2 запуски у review",
    );
    expect(result.current.t("shell.header.runsInReview", { count: 5 })).toBe(
      "5 запусків у review",
    );
    expect(
      result.current.t("pages.lex.resultsSummary", {
        count: 2,
        query: "policy",
      }),
    ).toBe("2 результати для «policy»");
    expect(result.current.t("missing.translation.path")).toBe(
      "missing.translation.path",
    );
    expect(
      result.current.label("artifactKinds", "scientist.preflight_report"),
    ).not.toBe("scientist.preflight_report");
    expect(result.current.label("artifactKinds", "custom.preview.kind")).toBe(
      "Custom Preview Kind",
    );
    expect(result.current.label("artifactKinds", undefined)).toBe("-");
    expect(
      result.current.label("artifactKinds", undefined, "Fallback label"),
    ).toBe("Fallback label");

    act(() => {
      result.current.setLocale("en");
    });

    await waitFor(() => expect(result.current.locale).toBe("en"));
    expect(document.documentElement.lang).toBe("en");
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("en");
    expect(
      result.current.t("pages.evidence.contextTitle", { runId: "run-7" }),
    ).toBe("Evidence context for run run-7");
    expect(
      result.current.label("artifactKinds", "scientist.preflight_report"),
    ).toBe("Scientist Preflight Report");
  });

  it("requires useI18n to be used inside LocaleProvider", () => {
    expect(() => renderHook(() => useI18n())).toThrow(
      "useI18n must be used within LocaleProvider",
    );
  });

  it("test_ru_cannot_reenter_active_product_locale", async () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "ru");
    Object.defineProperty(window.navigator, "language", {
      configurable: true,
      value: "ru-RU",
    });

    expect(readStoredLocale()).toBeNull();
    expect(resolveLocale("ru")).toBe("en");

    const { result } = renderHook(() => useI18n(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.locale).toBe("en"));
    expect(document.documentElement.lang).toBe("en");
    expect(result.current.t("shell.header.runsInReview", { count: 2 })).toBe(
      "2 runs in review",
    );

    act(() => {
      result.current.setLocale("ru" as never);
      persistLocale("ru" as never);
    });

    expect(result.current.locale).toBe("en");
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("en");
  });

  it("test_en_is_authored_primary_and_uk_is_its_translation", () => {
    expect(PRIMARY_LOCALE).toBe("en");
    expect(TRANSLATED_LOCALES).toEqual(["uk"]);
    expect(LEGACY_CONTINUITY_LOCALE).toBe("ru");
    expect(SUPPORTED_LOCALES).toEqual(["en", "uk"]);
    expect(DEFAULT_LOCALE).toBe(PRIMARY_LOCALE);
    expect(resolveLocale("en")).toBe("en");
    expect(resolveLocale("unsupported")).toBe("en");
  });

  it("respects ordered browser preferences before the authored default", () => {
    Object.defineProperty(window.navigator, "languages", {
      configurable: true,
      value: ["en-US", "uk-UA"],
    });
    expect(resolveLocale()).toBe("en");

    Object.defineProperty(window.navigator, "languages", {
      configurable: true,
      value: ["uk-UA", "en-US"],
    });
    expect(resolveLocale()).toBe("uk");
  });

  it("fails closed for non-product locale values at resolution, storage, and provider boundaries", async () => {
    const invalidValues = [
      "ru-RU",
      "RU",
      "Ru-rU",
      " ru ",
      " unknown ",
      "uk-UA-extra",
      "en_US",
      "unknown",
    ];

    for (const value of invalidValues) {
      expect(resolveLocale(value)).toBe("en");
      window.localStorage.setItem(LOCALE_STORAGE_KEY, value);
      expect(readStoredLocale()).toBeNull();
    }

    const { result } = renderHook(() => useI18n(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.locale).toBe("en"));

    act(() => {
      result.current.setLocale("ru-RU" as never);
      result.current.setLocale("Ru-rU" as never);
      persistLocale("ru-RU" as never);
    });

    expect(result.current.locale).toBe("en");
    expect(document.documentElement.lang).toBe("en");
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("en");
    expect(result.current.t("shell.header.runsInReview", { count: 2 })).toBe(
      "2 runs in review",
    );
  });

  it("accepts product locale tags during resolution but persists canonical product state", async () => {
    expect(resolveLocale("UK-ua")).toBe("uk");
    expect(resolveLocale("EN-us")).toBe("en");

    window.localStorage.setItem(LOCALE_STORAGE_KEY, "EN-us");
    expect(readStoredLocale()).toBe("en");

    const { result } = renderHook(() => useI18n(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.locale).toBe("en"));
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("en");
    expect(document.documentElement.lang).toBe("en");
  });

  it("test_frozen_ru_formatters_require_explicit_legacy_locale_and_never_become_product_state", () => {
    expect(toIntlLocale(resolveLocale())).toBe("en-US");
    expect(formatNumber(1234.5)).toBe(
      new Intl.NumberFormat("en-US").format(1234.5),
    );
    expect(formatIcuMessage("{count, plural, one {# item} other {# items}}", "ru", { count: 2 })).toBe(
      "2 items",
    );
    expect(toIntlLocale("ru")).toBe("ru-RU");
  });
});
