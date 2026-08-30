type PropertyDescriptorSnapshot = Readonly<{
  descriptor: PropertyDescriptor | undefined;
  key: PropertyKey;
  target: object;
}>;

function snapshotProperty(
  target: object,
  key: PropertyKey,
): PropertyDescriptorSnapshot {
  return Object.freeze({
    descriptor: Object.getOwnPropertyDescriptor(target, key),
    key,
    target,
  });
}

function restoreProperty(snapshot: PropertyDescriptorSnapshot): void {
  if (snapshot.descriptor === undefined) {
    Reflect.deleteProperty(snapshot.target, snapshot.key);
    return;
  }
  Object.defineProperty(snapshot.target, snapshot.key, snapshot.descriptor);
}

const JSDOM_COMPUTED_DEFAULTS: Readonly<Record<string, string>> = Object.freeze(
  {
    "-webkit-text-fill-color": "currentcolor",
    "-webkit-text-security": "none",
    "-webkit-text-stroke-width": "0px",
    "animation-name": "none",
    "backdrop-filter": "none",
    "background-blend-mode": "normal",
    "box-shadow": "none",
    clip: "auto",
    "clip-path": "none",
    content: "normal",
    "content-visibility": "visible",
    filter: "none",
    isolation: "auto",
    "mask-image": "none",
    "-webkit-mask-image": "none",
    "mix-blend-mode": "normal",
    opacity: "1",
    "paint-order": "normal",
    perspective: "none",
    "pointer-events": "auto",
    rotate: "none",
    scale: "none",
    "text-decoration-line": "none",
    "text-emphasis-style": "none",
    "text-shadow": "none",
    "text-transform": "none",
    transform: "none",
    translate: "none",
    visibility: "visible",
    "will-change": "auto",
  },
);

/**
 * Install a native-shaped layout/paint test double around one JSDOM evaluation.
 *
 * This module is imported only by tests. Production code receives no injectable
 * visibility capability and therefore fails closed when native proof is absent.
 */
export async function withConfidenceLedgerTestVisibilityPlatform<T>(
  document: Document,
  evaluate: () => Promise<T>,
): Promise<T> {
  const view = document.defaultView;
  if (
    view === null ||
    !view.navigator.userAgent.toLowerCase().includes("jsdom")
  ) {
    throw new TypeError("confidence-ledger test platform requires JSDOM");
  }
  const elementPrototype = view.Element.prototype;
  const rangePrototype = view.Range.prototype;
  const snapshots = [
    snapshotProperty(elementPrototype, "checkVisibility"),
    snapshotProperty(elementPrototype, "getBoundingClientRect"),
    snapshotProperty(elementPrototype, "getClientRects"),
    snapshotProperty(elementPrototype, "scrollIntoView"),
    snapshotProperty(rangePrototype, "getClientRects"),
    snapshotProperty(document, "elementsFromPoint"),
    snapshotProperty(view, "getComputedStyle"),
    snapshotProperty(view, "scrollTo"),
  ];
  let scrolledElement: HTMLElement | null = null;
  let rangeHost: HTMLElement | null = null;
  let nextRectIndex = 0;
  const rectByElement = new WeakMap<Element, DOMRect>();
  const rectFor = (element: Element): DOMRect => {
    const existing = rectByElement.get(element);
    if (existing !== undefined) return existing;
    const rect = new view.DOMRect(16 + nextRectIndex * 200, 16, 160, 20);
    nextRectIndex += 1;
    rectByElement.set(element, rect);
    return rect;
  };
  const nativeGetComputedStyle = view.getComputedStyle.bind(view);
  const pseudoStyleProbe = document.createElement("span");
  const pseudoComputedStyle = new Proxy(
    nativeGetComputedStyle(pseudoStyleProbe),
    {
      get(target, property) {
        if (property === "length") return 0;
        if (property === "item") return () => "";
        if (property === "getPropertyValue") {
          return (name: string) => (name === "content" ? "normal" : "");
        }
        const value = Reflect.get(target, property, target);
        return typeof value === "function" ? value.bind(target) : value;
      },
    },
  );

  const authorRuleDeclaresListNone = (element: HTMLElement): boolean => {
    let found = false;
    const visit = (rules: CSSRuleList): void => {
      for (let index = 0; index < rules.length && !found; index += 1) {
        const rule = rules.item(index);
        if (rule === null) continue;
        const candidate = rule as CSSRule & {
          readonly cssRules?: CSSRuleList;
          readonly selectorText?: string;
          readonly style?: CSSStyleDeclaration;
        };
        if (
          typeof candidate.selectorText === "string" &&
          candidate.style !== undefined
        ) {
          try {
            found =
              element.matches(candidate.selectorText) &&
              candidate.style
                .getPropertyValue("list-style")
                .split(/\s+/u)
                .includes("none");
          } catch {
            found = false;
          }
        }
        if (!found && candidate.cssRules !== undefined) {
          visit(candidate.cssRules);
        }
      }
    };
    for (const sheet of document.styleSheets) {
      try {
        visit(sheet.cssRules);
      } catch {
        return false;
      }
      if (found) return true;
    }
    return false;
  };

  Object.defineProperty(elementPrototype, "checkVisibility", {
    configurable: true,
    value: () => true,
  });
  Object.defineProperty(elementPrototype, "getBoundingClientRect", {
    configurable: true,
    value(this: Element) {
      return rectFor(this);
    },
  });
  Object.defineProperty(elementPrototype, "getClientRects", {
    configurable: true,
    value(this: Element) {
      const rect = rectFor(this);
      return Object.freeze({
        0: rect,
        item: (index: number) => (index === 0 ? rect : null),
        length: 1,
      });
    },
  });
  Object.defineProperty(elementPrototype, "scrollIntoView", {
    configurable: true,
    value(this: HTMLElement) {
      // eslint-disable-next-line @typescript-eslint/no-this-alias -- the double must return the exact method receiver from the hit-test.
      scrolledElement = this;
    },
  });
  Object.defineProperty(rangePrototype, "getClientRects", {
    configurable: true,
    value(this: Range) {
      const start = this.startContainer;
      rangeHost =
        start instanceof view.HTMLElement ? start : start.parentElement;
      const rect =
        rangeHost === null
          ? new view.DOMRect(16, 16, 160, 20)
          : rectFor(rangeHost);
      return Object.freeze({
        0: rect,
        item: (index: number) => (index === 0 ? rect : null),
        length: 1,
      });
    },
  });
  Object.defineProperty(document, "elementsFromPoint", {
    configurable: true,
    value: () => {
      const hit = rangeHost ?? scrolledElement;
      return hit === null ? [] : [hit];
    },
  });
  Object.defineProperty(view, "getComputedStyle", {
    configurable: true,
    value: (element: Element, pseudoElement?: string | null) => {
      // JSDOM ignores the pseudo-element argument. Supplying the host style
      // would falsely transfer host paint into every pseudo census. The test
      // double therefore exposes an empty, unsupported declaration; real
      // pseudo paint remains covered by the persistent native-Chromium lane.
      if (pseudoElement !== null && pseudoElement !== undefined) {
        return pseudoComputedStyle;
      }
      const style = nativeGetComputedStyle(element);
      return new Proxy(style, {
        get(target, property) {
          if (property === "getPropertyValue") {
            return (name: string) => {
              const value = target.getPropertyValue(name);
              if (
                value.trim().length > 0 &&
                value.trim().toLowerCase() !== "initial" &&
                value.trim().toLowerCase() !== "unset"
              ) {
                return value;
              }
              if (name === "-webkit-text-fill-color") {
                return target.getPropertyValue("color") || "rgb(0, 0, 0)";
              }
              if (
                (name === "list-style-image" || name === "list-style-type") &&
                pseudoElement === undefined &&
                element instanceof view.HTMLElement
              ) {
                let listOwner: HTMLElement | null = element;
                while (listOwner !== null) {
                  if (
                    listOwner.style.listStyle.split(/\s+/u).includes("none") ||
                    authorRuleDeclaresListNone(listOwner)
                  ) {
                    return "none";
                  }
                  listOwner = listOwner.parentElement;
                }
              }
              return JSDOM_COMPUTED_DEFAULTS[name] ?? "";
            };
          }
          const value = Reflect.get(target, property, target);
          return typeof value === "function" ? value.bind(target) : value;
        },
      });
    },
  });
  Object.defineProperty(view, "scrollTo", {
    configurable: true,
    value: () => undefined,
  });

  try {
    return await evaluate();
  } finally {
    snapshots.reverse().forEach(restoreProperty);
  }
}
