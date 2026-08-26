import type { CapturedCapabilitySearch } from "@/api/hooks/useCapabilitySearch";
import {
  capabilityDiscoveryResponseSchema,
  type CapabilityDiscoveryPayload,
} from "@/api/validators";

type PacketPathPart = number | string;
type PacketLeafType =
  | "array"
  | "boolean"
  | "null"
  | "number"
  | "object"
  | "string";

export type CapabilityDiscoveryDomTwin = Readonly<CapabilityDiscoveryPayload>;

type PacketLeaf = Readonly<{
  path: readonly PacketPathPart[];
  type: PacketLeafType;
  value: string;
}>;

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

export function capabilityDiscoveryTwin(
  captured: CapturedCapabilitySearch,
): CapabilityDiscoveryDomTwin {
  return Object.freeze(cloneJson(captured.response));
}

function visibleText(root: ParentNode, selector: string, name: string): string {
  const element = root.querySelector<HTMLElement>(selector);
  if (!element) {
    throw new TypeError("capability discovery DOM is missing " + name);
  }
  return element.textContent ?? "";
}

function parsePath(value: string): readonly PacketPathPart[] {
  const parsed = JSON.parse(value) as unknown;
  if (
    !Array.isArray(parsed) ||
    parsed.some(
      (part) =>
        !(
          typeof part === "string" ||
          (typeof part === "number" && Number.isInteger(part) && part >= 0)
        ),
    )
  ) {
    throw new TypeError("capability discovery DOM leaf path is invalid");
  }
  return parsed;
}

function parseLeaf(row: HTMLElement): PacketLeaf {
  const path = parsePath(
    visibleText(row, "[data-capability-leaf-path]", "leaf path"),
  );
  const type = visibleText(row, "[data-capability-leaf-type]", "leaf type");
  if (
    !["array", "boolean", "null", "number", "object", "string"].includes(type)
  ) {
    throw new TypeError("capability discovery DOM leaf type is invalid");
  }
  return Object.freeze({
    path: Object.freeze([...path]),
    type: type as PacketLeafType,
    value: visibleText(row, "[data-capability-leaf-value]", "leaf value"),
  });
}

function parseContainerSize(leaf: PacketLeaf): number {
  const size = Number(leaf.value);
  if (!Number.isInteger(size) || size < 0) {
    throw new TypeError("capability discovery DOM container size is invalid");
  }
  return size;
}

function decodeLeafValue(leaf: PacketLeaf): unknown {
  switch (leaf.type) {
    case "array":
      parseContainerSize(leaf);
      return [];
    case "object":
      parseContainerSize(leaf);
      return {};
    case "boolean":
      if (leaf.value !== "true" && leaf.value !== "false") {
        throw new TypeError("capability discovery DOM boolean leaf is invalid");
      }
      return leaf.value === "true";
    case "null":
      if (leaf.value !== "null") {
        throw new TypeError("capability discovery DOM null leaf is invalid");
      }
      return null;
    case "number": {
      const value = Number(leaf.value);
      if (!Number.isFinite(value)) {
        throw new TypeError("capability discovery DOM number leaf is invalid");
      }
      return value;
    }
    case "string":
      return leaf.value;
  }
}

function resolveParent(
  root: unknown,
  path: readonly PacketPathPart[],
): unknown {
  let cursor = root;
  for (const part of path) {
    if (Array.isArray(cursor)) {
      if (typeof part !== "number" || !(part in cursor)) {
        throw new TypeError(
          "capability discovery DOM array path is incomplete",
        );
      }
      cursor = cursor[part];
      continue;
    }
    if (typeof cursor !== "object" || cursor === null) {
      throw new TypeError("capability discovery DOM object path is incomplete");
    }
    if (
      typeof part !== "string" ||
      ["__proto__", "constructor", "prototype"].includes(part) ||
      !Object.hasOwn(cursor, part)
    ) {
      throw new TypeError("capability discovery DOM object path is incomplete");
    }
    cursor = (cursor as Record<string, unknown>)[part];
  }
  return cursor;
}

function assignLeaf(
  root: unknown,
  path: readonly PacketPathPart[],
  value: unknown,
): void {
  const parent = resolveParent(root, path.slice(0, -1));
  const key = path.at(-1);
  if (Array.isArray(parent)) {
    if (typeof key !== "number" || key > parent.length) {
      throw new TypeError(
        "capability discovery DOM array leaf order is invalid",
      );
    }
    parent[key] = value;
    return;
  }
  if (
    typeof parent !== "object" ||
    parent === null ||
    typeof key !== "string" ||
    ["__proto__", "constructor", "prototype"].includes(key) ||
    Object.hasOwn(parent, key)
  ) {
    throw new TypeError("capability discovery DOM object leaf is duplicated");
  }
  (parent as Record<string, unknown>)[key] = value;
}

function assertContainerSizes(
  root: unknown,
  containers: readonly PacketLeaf[],
): void {
  for (const container of containers) {
    const value = resolveParent(root, container.path);
    const actual = Array.isArray(value)
      ? value.length
      : typeof value === "object" && value !== null
        ? Object.keys(value).length
        : -1;
    if (actual !== parseContainerSize(container)) {
      throw new TypeError("capability discovery DOM container is incomplete");
    }
    if (
      Array.isArray(value) &&
      Array.from({ length: value.length }, (_, index) => index).some(
        (index) => !(index in value),
      )
    ) {
      throw new TypeError("capability discovery DOM array has omitted rows");
    }
  }
}

export function decodeCapabilityDiscoveryDom(
  root: ParentNode,
): CapabilityDiscoveryDomTwin {
  const leaves = [
    ...root.querySelectorAll<HTMLElement>("[data-capability-packet-leaf]"),
  ].map(parseLeaf);
  const rootLeaves = leaves.filter((leaf) => leaf.path.length === 0);
  if (rootLeaves.length !== 1 || rootLeaves[0]?.type !== "object") {
    throw new TypeError(
      "capability discovery DOM packet root is missing or invalid",
    );
  }
  parseContainerSize(rootLeaves[0]);

  const rootValue = decodeLeafValue(rootLeaves[0]);
  const descendants = leaves
    .filter((leaf) => leaf.path.length > 0)
    .sort((left, right) => left.path.length - right.path.length);
  const seen = new Set<string>();
  for (const leaf of descendants) {
    const identity = JSON.stringify(leaf.path);
    if (seen.has(identity)) {
      throw new TypeError("capability discovery DOM leaf is duplicated");
    }
    seen.add(identity);
    assignLeaf(rootValue, leaf.path, decodeLeafValue(leaf));
  }
  assertContainerSizes(
    rootValue,
    leaves.filter((leaf) => leaf.type === "array" || leaf.type === "object"),
  );

  const parsed = capabilityDiscoveryResponseSchema.safeParse(rootValue);
  if (!parsed.success) {
    throw new TypeError("capability discovery DOM response packet is invalid");
  }
  return parsed.data;
}

export function downloadCapabilityDiscoveryMachine(rawBytes: Uint8Array) {
  const exactBytes = rawBytes.slice();
  const blob = new Blob([exactBytes], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "capability-discovery.json";
  anchor.click();
  URL.revokeObjectURL(url);
}
