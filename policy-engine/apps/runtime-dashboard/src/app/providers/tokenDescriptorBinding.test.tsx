import { readFileSync } from "node:fs";
import path from "node:path";
import type { PropsWithChildren } from "react";
import { render, waitFor } from "@testing-library/react";

import {
  PREFERENCES_STORAGE_KEY,
  resetPreferencesStore,
} from "@/app/state/usePreferencesStore";

const { tokenDescriptors, useFeatureFlagMock } = vi.hoisted(() => ({
  tokenDescriptors: {
    contrastModeDescriptors: {
      forcedColors: {
        mediaQuery: "(forced-colors: dtcg-active)",
      },
      more: {
        attribute: "more",
        mediaQuery: "(prefers-contrast: dtcg-more)",
      },
    },
    densityModeDescriptors: {
      comfortable: { attribute: "comfortable-dtcg" },
      compact: { attribute: "compact-dtcg" },
      condensed: { attribute: "condensed-dtcg" },
    },
    motionModeDescriptors: {
      reduced: {
        attribute: "reduce",
        mediaQuery: "(prefers-reduced-motion: dtcg-reduce)",
      },
    },
    themeModeDescriptors: {
      dark: {
        attribute: "dark",
        colorScheme: "dark",
        metaThemeColor: "#0d0d0d",
      },
      light: {
        attribute: "light",
        colorScheme: "light",
        metaThemeColor: "#fefefe",
      },
      system: {
        attribute: "system",
        dark: "dark",
        light: "light",
        mediaQuery: "(prefers-color-scheme: dtcg-dark)",
      },
    },
  },
  useFeatureFlagMock: vi.fn(),
}));

vi.mock("@polisyos/atlas-ui", () => tokenDescriptors);

vi.mock("@/app/providers/FeatureFlagProvider", () => ({
  FeatureFlagProvider: ({ children }: PropsWithChildren) => children,
  useFeatureFlag: (...args: unknown[]) => useFeatureFlagMock(...args),
}));

import { DensityProvider } from "@/app/providers/DensityProvider";
import { ThemeProvider } from "@/app/providers/ThemeProvider";
import { HighContrastProvider } from "@/shared/a11y/HighContrastProvider";
import { ReducedMotionProvider } from "@/shared/a11y/ReducedMotionProvider";

function mediaQueryList(query: string): MediaQueryList {
  return {
    addEventListener: vi.fn(),
    addListener: vi.fn(),
    dispatchEvent: vi.fn(),
    matches: query === tokenDescriptors.themeModeDescriptors.system.mediaQuery,
    media: query,
    onchange: null,
    removeEventListener: vi.fn(),
    removeListener: vi.fn(),
  };
}

function readThemeColorMeta() {
  return document.querySelector('meta[name="theme-color"]');
}

describe("living mode owners use generated token descriptors", () => {
  it("keeps the cross-layer parity harness inside the normal TypeScript gate", () => {
    const dashboardRoot = process.cwd();
    const packageJson = JSON.parse(
      readFileSync(path.join(dashboardRoot, "package.json"), "utf8"),
    ) as { scripts: { typecheck: string } };
    const toolsConfig = JSON.parse(
      readFileSync(path.join(dashboardRoot, "tsconfig.tools.json"), "utf8"),
    ) as { include: string[] };

    expect(packageJson.scripts.typecheck).toContain(
      "tsc -p tsconfig.tools.json --noEmit",
    );
    expect(toolsConfig.include).toContain(
      "scripts/tokenProjectionParity.test.ts",
    );
  });

  beforeEach(() => {
    useFeatureFlagMock.mockReset();
    useFeatureFlagMock.mockReturnValue(true);
    vi.spyOn(window, "matchMedia").mockImplementation(mediaQueryList);
    window.localStorage.removeItem("polisyos.runtime.theme");
    window.localStorage.removeItem(PREFERENCES_STORAGE_KEY);
    resetPreferencesStore();
    document.documentElement.removeAttribute("data-density");
    document.documentElement.removeAttribute("data-theme");
  });

  it("uses the generated system query and meta colors in ThemeProvider", async () => {
    render(<ThemeProvider>theme</ThemeProvider>);

    await waitFor(() => {
      expect(window.matchMedia).toHaveBeenCalledWith(
        tokenDescriptors.themeModeDescriptors.system.mediaQuery,
      );
    });
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(readThemeColorMeta()).toHaveAttribute(
      "content",
      tokenDescriptors.themeModeDescriptors.dark.metaThemeColor,
    );
  });

  it("uses the generated density attribute in DensityProvider", async () => {
    render(<DensityProvider>density</DensityProvider>);

    await waitFor(() => {
      expect(document.documentElement.dataset.density).toBe(
        tokenDescriptors.densityModeDescriptors.comfortable.attribute,
      );
    });
  });

  it("uses generated contrast media queries in HighContrastProvider", async () => {
    render(<HighContrastProvider>contrast</HighContrastProvider>);

    await waitFor(() => {
      expect(window.matchMedia).toHaveBeenCalledWith(
        tokenDescriptors.contrastModeDescriptors.more.mediaQuery,
      );
    });
    expect(window.matchMedia).toHaveBeenCalledWith(
      tokenDescriptors.contrastModeDescriptors.forcedColors.mediaQuery,
    );
  });

  it("uses the generated reduced-motion query in ReducedMotionProvider", async () => {
    render(<ReducedMotionProvider>motion</ReducedMotionProvider>);

    await waitFor(() => {
      expect(window.matchMedia).toHaveBeenCalledWith(
        tokenDescriptors.motionModeDescriptors.reduced.mediaQuery,
      );
    });
  });
});
