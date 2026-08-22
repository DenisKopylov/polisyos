import {
  buildRunPaperSemanticRoster,
  type RunPaperPresentation,
  type RunPaperSemanticNode,
} from "@/features/runs/domain/runPaperPresentation";

function elements(root: ParentNode, selector: string): HTMLElement[] {
  return Array.from(root.querySelectorAll(selector)).map((node) => {
    if (!(node instanceof HTMLElement)) {
      throw new TypeError(`Run paper DOM region is not HTML: ${selector}`);
    }
    return node;
  });
}

function singleton(root: ParentNode, selector: string): HTMLElement {
  const matches = elements(root, selector);
  if (matches.length !== 1) {
    throw new Error(
      `Run paper DOM requires exactly one ${selector}; found ${matches.length}`,
    );
  }
  return matches[0] as HTMLElement;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const actual = Object.keys(value).sort();
  const sortedExpected = [...expected].sort();
  return (
    actual.length === sortedExpected.length &&
    actual.every((key, index) => key === sortedExpected[index])
  );
}

function parseNode(element: HTMLElement): RunPaperSemanticNode {
  const raw = element.getAttribute("data-run-paper-raw");
  if (raw === null) {
    throw new Error("Run paper semantic node has no raw fact");
  }
  let value: unknown;
  try {
    value = JSON.parse(raw) as unknown;
  } catch (error) {
    throw new Error("Run paper semantic node contains invalid JSON", {
      cause: error,
    });
  }
  if (
    !isRecord(value) ||
    typeof value.kind !== "string" ||
    typeof value.path !== "string" ||
    element.getAttribute("data-run-paper-path") !== value.path
  ) {
    throw new Error("Run paper semantic node identity is invalid");
  }
  switch (value.kind) {
    case "array":
      if (
        !hasExactKeys(value, ["kind", "length", "path"]) ||
        !Number.isInteger(value.length) ||
        Number(value.length) < 0
      ) {
        throw new Error("Run paper semantic array node is invalid");
      }
      break;
    case "object": {
      if (
        !hasExactKeys(value, ["kind", "members", "path"]) ||
        !Array.isArray(value.members) ||
        value.members.some((member) => typeof member !== "string")
      ) {
        throw new Error("Run paper semantic object node is invalid");
      }
      const members = value.members as string[];
      if (
        new Set(members).size !== members.length ||
        JSON.stringify(members) !== JSON.stringify([...members].sort())
      ) {
        throw new Error("Run paper semantic object members are not canonical");
      }
      break;
    }
    case "null":
      if (!hasExactKeys(value, ["kind", "path"])) {
        throw new Error("Run paper semantic null node is invalid");
      }
      break;
    case "boolean":
    case "number":
    case "string":
      if (
        !hasExactKeys(value, ["kind", "path", "value"]) ||
        typeof value.value !== value.kind ||
        (value.kind === "number" && !Number.isFinite(value.value))
      ) {
        throw new Error("Run paper semantic leaf node is invalid");
      }
      break;
    default:
      throw new Error(
        `Run paper semantic node kind is unsupported: ${value.kind}`,
      );
  }
  const node = value as RunPaperSemanticNode;
  const children = Array.from(element.children);
  const term = children[0];
  const description = children[1];
  if (
    children.length !== 2 ||
    term?.tagName !== "DT" ||
    description?.tagName !== "DD" ||
    term.textContent !== (node.path || "/") ||
    description.textContent !== semanticNodeValue(node)
  ) {
    throw new Error("Run paper semantic raw fact does not match printed text");
  }
  return node;
}

function semanticNodeValue(node: RunPaperSemanticNode): string {
  switch (node.kind) {
    case "array":
      return `[array:${String(node.length)}]`;
    case "object":
      return `[object:${node.members.join(",")}]`;
    case "null":
      return "null";
    case "boolean":
    case "number":
    case "string":
      return String(node.value);
  }
}

function pointerSegment(value: string): string {
  return value.replaceAll("~", "~0").replaceAll("/", "~1");
}

function rebuild(
  path: string,
  nodes: ReadonlyMap<string, RunPaperSemanticNode>,
  visited: Set<string>,
): unknown {
  const node = nodes.get(path);
  if (!node) {
    throw new Error(`Run paper semantic roster is missing ${path || "/"}`);
  }
  visited.add(path);
  switch (node.kind) {
    case "array":
      return Array.from({ length: node.length }, (_unused, index) =>
        rebuild(`${path}/${String(index)}`, nodes, visited),
      );
    case "object":
      return Object.fromEntries(
        node.members.map((member) => [
          member,
          rebuild(`${path}/${pointerSegment(member)}`, nodes, visited),
        ]),
      );
    case "null":
      return null;
    case "boolean":
    case "number":
    case "string":
      return node.value;
  }
}

/** Decode and census the complete run-paper value from its real semantic DOM. */
export function decodeRunPaperDom(
  container: HTMLElement,
): RunPaperPresentation {
  const roster = singleton(container, "[data-run-paper-semantic-roster]");
  const semanticElements = elements(roster, "[data-run-paper-node]");
  if (
    roster.getAttribute("data-run-paper-semantic-roster-size") !==
    String(semanticElements.length)
  ) {
    throw new Error("Run paper semantic roster count is invalid");
  }
  const parsed = semanticElements.map(parseNode);
  const nodeMap = new Map(parsed.map((node) => [node.path, node]));
  if (nodeMap.size !== parsed.length) {
    throw new Error("Run paper semantic roster contains a duplicate path");
  }
  const visited = new Set<string>();
  const decoded = rebuild("", nodeMap, visited);
  if (visited.size !== nodeMap.size) {
    throw new Error("Run paper semantic roster contains an extra path");
  }
  if (!isRecord(decoded)) {
    throw new Error("Run paper semantic roster root is not an object");
  }
  const paper = decoded as unknown as RunPaperPresentation;
  const documentRoot = singleton(container, "[data-run-paper-document]");
  const renderedLinks = elements(documentRoot, "a[href]");
  if (renderedLinks.length !== paper.artifactLinks.length) {
    throw new Error("Run paper DOM contains an unadmitted or missing link");
  }
  paper.artifactLinks.forEach((link, index) => {
    const rendered = renderedLinks[index];
    if (
      rendered?.getAttribute("href") !== link.href ||
      rendered.getAttribute("data-run-paper-artifact-link") !==
        link.artifact_ref.artifact_id
    ) {
      throw new Error(`Run paper DOM artifact link mismatch: ${String(index)}`);
    }
  });
  const canonical = buildRunPaperSemanticRoster(paper);
  if (JSON.stringify(canonical) !== JSON.stringify(parsed)) {
    throw new Error("Run paper semantic roster order is not canonical");
  }
  return paper;
}
