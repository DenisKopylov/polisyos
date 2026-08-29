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
    snapshotProperty(elementPrototype, "scrollIntoView"),
    snapshotProperty(rangePrototype, "getClientRects"),
    snapshotProperty(document, "elementsFromPoint"),
    snapshotProperty(view, "getComputedStyle"),
    snapshotProperty(view, "scrollTo"),
  ];
  let scrolledElement: HTMLElement | null = null;
  let rangeHost: HTMLElement | null = null;
  const nativeGetComputedStyle = view.getComputedStyle.bind(view);

  Object.defineProperty(elementPrototype, "checkVisibility", {
    configurable: true,
    value: () => true,
  });
  Object.defineProperty(elementPrototype, "getBoundingClientRect", {
    configurable: true,
    value: () => new view.DOMRect(16, 16, 160, 20),
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
      const rect = new view.DOMRect(16, 16, 160, 20);
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
      const style = nativeGetComputedStyle(
        element,
        pseudoElement === null || pseudoElement === undefined
          ? pseudoElement
          : undefined,
      );
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
