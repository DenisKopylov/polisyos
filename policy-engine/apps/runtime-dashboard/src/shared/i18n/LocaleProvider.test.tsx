import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";

import { LocaleProvider, useI18n } from "@/shared/i18n/LocaleProvider";
import { LOCALE_STORAGE_KEY } from "@/shared/i18n/locale";

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

  it("resolves Russian locale from navigator preferences", async () => {
    Object.defineProperty(window.navigator, "language", {
      configurable: true,
      value: "ru-RU",
    });

    const { result } = renderHook(() => useI18n(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.locale).toBe("ru"));
    expect(document.documentElement.lang).toBe("ru");
    expect(result.current.t("shell.header.runsInReview", { count: 2 })).toBe(
      "2 runs in review",
    );
  });
});
