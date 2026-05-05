import { useEffect, useMemo, useState } from "react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { scheduleA11yAudit } from "@/shared/lib/a11yAudit";

type ContrastWarning = {
  minimum: number;
  ratio: number;
  selector: string;
  text: string;
  type: "contrast" | "exemption";
};

type RgbaColor = {
  a: number;
  b: number;
  g: number;
  r: number;
};

const MINIMUM_NORMAL_TEXT = 4.5;
const MINIMUM_LARGE_TEXT = 3;
const MAX_WARNINGS = 12;
const EXEMPTION_REASON_ATTRIBUTE = "data-a11y-exempt-reason";

const TRANSPARENT: RgbaColor = { a: 0, b: 0, g: 0, r: 0 };
const WHITE: RgbaColor = { a: 1, b: 255, g: 255, r: 255 };

function parseCssColor(value: string): RgbaColor | null {
  const normalized = value.replace(/\s+/g, " ").trim().toLowerCase();

  if (!normalized || normalized === "transparent") {
    return TRANSPARENT;
  }

  const hexMatch = normalized.match(/^#([\da-f]{3,8})$/i);
  if (hexMatch) {
    const hex = hexMatch[1];
    if (hex.length === 3 || hex.length === 4) {
      const expanded = hex
        .split("")
        .map((chunk) => chunk + chunk)
        .join("");
      return parseCssColor(`#${expanded}`);
    }
    if (hex.length === 6 || hex.length === 8) {
      return {
        a: hex.length === 8 ? Number.parseInt(hex.slice(6, 8), 16) / 255 : 1,
        b: Number.parseInt(hex.slice(4, 6), 16),
        g: Number.parseInt(hex.slice(2, 4), 16),
        r: Number.parseInt(hex.slice(0, 2), 16),
      };
    }
  }

  const rgbMatch = normalized.match(
    /^rgba?\(([\d.]+), ([\d.]+), ([\d.]+)(?:, ([\d.]+))?\)$/,
  );
  if (rgbMatch) {
    return {
      a: rgbMatch[4] ? Number.parseFloat(rgbMatch[4]) : 1,
      b: Number.parseFloat(rgbMatch[3]),
      g: Number.parseFloat(rgbMatch[2]),
      r: Number.parseFloat(rgbMatch[1]),
    };
  }

  return null;
}

function blendColors(foreground: RgbaColor, background: RgbaColor): RgbaColor {
  const alpha = foreground.a + background.a * (1 - foreground.a);
  if (alpha <= 0) {
    return TRANSPARENT;
  }

  return {
    a: alpha,
    b:
      (foreground.b * foreground.a +
        background.b * background.a * (1 - foreground.a)) /
      alpha,
    g:
      (foreground.g * foreground.a +
        background.g * background.a * (1 - foreground.a)) /
      alpha,
    r:
      (foreground.r * foreground.a +
        background.r * background.a * (1 - foreground.a)) /
      alpha,
  };
}

function srgbToLinear(channel: number) {
  const normalized = channel / 255;
  if (normalized <= 0.04045) {
    return normalized / 12.92;
  }
  return ((normalized + 0.055) / 1.055) ** 2.4;
}

function relativeLuminance(color: RgbaColor) {
  return (
    srgbToLinear(color.r) * 0.2126 +
    srgbToLinear(color.g) * 0.7152 +
    srgbToLinear(color.b) * 0.0722
  );
}

function contrastRatio(foreground: RgbaColor, background: RgbaColor) {
  const lighter = Math.max(
    relativeLuminance(foreground),
    relativeLuminance(background),
  );
  const darker = Math.min(
    relativeLuminance(foreground),
    relativeLuminance(background),
  );
  return (lighter + 0.05) / (darker + 0.05);
}

function resolveEffectiveBackgroundColor(element: HTMLElement): RgbaColor {
  const ancestry: HTMLElement[] = [];
  let current: HTMLElement | null = element;

  while (current) {
    ancestry.unshift(current);
    current = current.parentElement;
  }

  let effective = WHITE;
  for (const node of ancestry) {
    const background = parseCssColor(
      window.getComputedStyle(node).backgroundColor,
    );
    if (!background || background.a <= 0) {
      continue;
    }
    effective = blendColors(background, effective);
  }

  return effective;
}

function getElementLabel(element: HTMLElement) {
  const ariaLabel = element.getAttribute("aria-label");
  if (ariaLabel) {
    return ariaLabel.trim();
  }

  const title = element.getAttribute("title");
  if (title) {
    return title.trim();
  }

  return element.textContent?.replace(/\s+/g, " ").trim() ?? "";
}

function getElementSelector(element: HTMLElement) {
  if (element.id) {
    return `#${element.id}`;
  }

  const testId = element.getAttribute("data-testid");
  if (testId) {
    return `[data-testid="${testId}"]`;
  }

  const classNames = Array.from(element.classList).slice(0, 2);
  if (classNames.length > 0) {
    return `${element.tagName.toLowerCase()}.${classNames.join(".")}`;
  }

  return element.tagName.toLowerCase();
}

function isLargeText(element: HTMLElement, styles: CSSStyleDeclaration) {
  const fontSize = Number.parseFloat(styles.fontSize);
  const fontWeight = Number.parseFloat(styles.fontWeight);

  if (fontSize >= 24) {
    return true;
  }

  return fontSize >= 18.66 && fontWeight >= 700;
}

function shouldInspectElement(element: HTMLElement) {
  if (element.closest("[data-a11y-overlay]")) {
    return false;
  }
  if (
    element.hasAttribute("hidden") ||
    element.getAttribute("aria-hidden") === "true"
  ) {
    return false;
  }
  if (element.getClientRects().length === 0) {
    return false;
  }
  if (element.closest("script, style, svg defs")) {
    return false;
  }

  const label = getElementLabel(element);
  if (!label) {
    return false;
  }

  return label.length >= 2;
}

function collectContrastWarnings(): ContrastWarning[] {
  const elements = Array.from(document.body.querySelectorAll<HTMLElement>("*"));
  const warnings: ContrastWarning[] = [];
  const seenSelectors = new Set<string>();

  for (const element of elements) {
    if (!shouldInspectElement(element)) {
      continue;
    }

    const exemptContainer = element.closest<HTMLElement>("[data-a11y-exempt]");
    if (exemptContainer) {
      const reason = exemptContainer.getAttribute(EXEMPTION_REASON_ATTRIBUTE);
      if (!reason || !reason.trim()) {
        const selector = getElementSelector(exemptContainer);
        if (!seenSelectors.has(selector)) {
          warnings.push({
            minimum: MINIMUM_NORMAL_TEXT,
            ratio: 0,
            selector,
            text: "data-a11y-exempt is present without a data-a11y-exempt-reason justification.",
            type: "exemption",
          });
          seenSelectors.add(selector);
        }
      }
      continue;
    }

    const styles = window.getComputedStyle(element);
    const foreground = parseCssColor(styles.color);
    if (!foreground) {
      continue;
    }

    const background = resolveEffectiveBackgroundColor(element);
    const solidForeground = blendColors(foreground, background);
    const ratio = contrastRatio(solidForeground, background);
    const minimum = isLargeText(element, styles)
      ? MINIMUM_LARGE_TEXT
      : MINIMUM_NORMAL_TEXT;

    if (ratio >= minimum) {
      continue;
    }

    const selector = getElementSelector(element);
    if (seenSelectors.has(selector)) {
      continue;
    }

    warnings.push({
      minimum,
      ratio,
      selector,
      text: getElementLabel(element),
      type: "contrast",
    });
    seenSelectors.add(selector);
  }

  return warnings
    .sort((left, right) => left.ratio - right.ratio)
    .slice(0, MAX_WARNINGS);
}

export function ContrastEnforcer() {
  const { t } = useI18n();
  const [warnings, setWarnings] = useState<ContrastWarning[]>([]);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!import.meta.env.DEV) {
      return;
    }
    if (typeof window === "undefined" || window.__RUNTIME_DASHBOARD_TEST__) {
      return;
    }

    let timeoutId: number | null = null;
    const scheduleScan = () => {
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }

      timeoutId = window.setTimeout(() => {
        setWarnings(collectContrastWarnings());
        scheduleA11yAudit();
      }, 120);
    };

    const observer = new MutationObserver(scheduleScan);
    observer.observe(document.body, {
      attributes: true,
      childList: true,
      subtree: true,
    });

    window.addEventListener("resize", scheduleScan);
    scheduleScan();

    return () => {
      observer.disconnect();
      window.removeEventListener("resize", scheduleScan);
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
    };
  }, []);

  const summaryLabel = useMemo(() => {
    if (warnings.length === 0) {
      return t("shared.a11y.contrastEnforcer.clean");
    }
    return t("shared.a11y.contrastEnforcer.warnings", {
      count: warnings.length,
    });
  }, [t, warnings.length]);

  if (!import.meta.env.DEV || warnings.length === 0) {
    return null;
  }

  return (
    <aside
      aria-live="polite"
      className="bg-panel text-text border-line shadow-panel fixed right-4 bottom-4 z-[var(--z-toast)] max-w-sm rounded-2xl border p-3 text-xs"
      data-a11y-exempt="true"
      data-a11y-exempt-reason="Developer-only accessibility overlay"
      data-a11y-overlay="true"
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-semibold">{summaryLabel}</p>
          <p className="text-muted mt-1">
            {t("shared.a11y.contrastEnforcer.devOverlayNotice")}
          </p>
        </div>
        <button
          className="border-line bg-surface rounded-full border px-2 py-1 font-semibold"
          onClick={() => setExpanded((current) => !current)}
          type="button"
        >
          {expanded
            ? t("shared.a11y.contrastEnforcer.hide")
            : t("shared.a11y.contrastEnforcer.show")}
        </button>
      </div>

      {expanded ? (
        <ol className="mt-3 space-y-2">
          {warnings.map((warning) => (
            <li key={`${warning.selector}-${warning.text}`}>
              <p className="font-semibold">{warning.selector}</p>
              <p className="text-muted">
                {warning.type === "contrast"
                  ? t("shared.a11y.contrastEnforcer.ratioNeeds", {
                      minimum: warning.minimum.toFixed(1),
                      ratio: warning.ratio.toFixed(2),
                    })
                  : t("shared.a11y.contrastEnforcer.missingExemptionReason")}
              </p>
              <p className="mt-1 line-clamp-2">{warning.text}</p>
            </li>
          ))}
        </ol>
      ) : null}
    </aside>
  );
}
