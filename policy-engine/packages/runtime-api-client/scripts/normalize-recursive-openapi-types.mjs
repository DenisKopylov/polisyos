import fs from "node:fs/promises";
import path from "node:path";

import ts from "typescript";

function literalText(node) {
  return ts.isStringLiteral(node) ? node.text : undefined;
}

function schemaReference(node) {
  if (
    !ts.isIndexedAccessTypeNode(node) ||
    !ts.isLiteralTypeNode(node.indexType) ||
    !ts.isIndexedAccessTypeNode(node.objectType) ||
    !ts.isLiteralTypeNode(node.objectType.indexType) ||
    !ts.isTypeReferenceNode(node.objectType.objectType) ||
    !ts.isIdentifier(node.objectType.objectType.typeName) ||
    node.objectType.objectType.typeName.text !== "components" ||
    literalText(node.objectType.indexType.literal) !== "schemas"
  ) {
    return undefined;
  }
  return literalText(node.indexType.literal);
}

function referencesIn(type) {
  const references = [];
  function visit(node, guarded = false) {
    const name = schemaReference(node);
    if (name !== undefined) {
      references.push({ name, node, guarded });
      return;
    }
    const nextGuarded =
      guarded ||
      ts.isArrayTypeNode(node) ||
      ts.isTupleTypeNode(node) ||
      ts.isTypeLiteralNode(node) ||
      ts.isMappedTypeNode(node) ||
      (ts.isTypeReferenceNode(node) &&
        ts.isIdentifier(node.typeName) &&
        ["Array", "ReadonlyArray"].includes(node.typeName.text));
    ts.forEachChild(node, (child) => visit(child, nextGuarded));
  }
  visit(type);
  return references;
}

function recursiveComponents(graph) {
  let nextIndex = 0;
  const indexes = new Map();
  const lows = new Map();
  const stack = [];
  const active = new Set();
  const recursive = [];
  function visit(name) {
    indexes.set(name, nextIndex);
    lows.set(name, nextIndex++);
    stack.push(name);
    active.add(name);
    for (const target of graph.get(name)) {
      if (!indexes.has(target)) {
        visit(target);
        lows.set(name, Math.min(lows.get(name), lows.get(target)));
      } else if (active.has(target)) {
        lows.set(name, Math.min(lows.get(name), indexes.get(target)));
      }
    }
    if (lows.get(name) !== indexes.get(name)) return;
    const component = [];
    let member;
    do {
      member = stack.pop();
      active.delete(member);
      component.push(member);
    } while (member !== name);
    if (component.length > 1 || graph.get(name).has(name)) {
      recursive.push(component);
    }
  }
  for (const name of graph.keys()) {
    if (!indexes.has(name)) visit(name);
  }
  return recursive;
}

function replaceSpans(source, replacements) {
  let end = source.length;
  let result = "";
  for (const replacement of replacements.sort((a, b) => b.start - a.start)) {
    if (replacement.end > end)
      throw new Error("Overlapping schema type replacements");
    result = replacement.text + source.slice(replacement.end, end) + result;
    end = replacement.start;
  }
  return source.slice(0, end) + result;
}

/**
 * Lift guarded recursive schema components into private TypeScript aliases.
 * Nonrecursive component property bytes are preserved without AST reprinting.
 *
 * @param {string} source Actual openapi-typescript output.
 * @returns {string} Compileable recursive aliases and unchanged remaining source.
 */
export function normalizeRecursiveOpenApiTypes(source) {
  const file = ts.createSourceFile(
    "types.ts",
    source,
    ts.ScriptTarget.Latest,
    true,
  );
  if (file.parseDiagnostics.length)
    throw new Error("Cannot normalize invalid TypeScript");
  const components = file.statements.find(
    (node) =>
      ts.isInterfaceDeclaration(node) && node.name.text === "components",
  );
  const schemas = components?.members.find(
    (node) =>
      ts.isPropertySignature(node) &&
      (ts.isIdentifier(node.name) ? node.name.text : literalText(node.name)) ===
        "schemas",
  );
  if (schemas?.type?.kind === ts.SyntaxKind.NeverKeyword) return source;
  if (!schemas?.type || !ts.isTypeLiteralNode(schemas.type)) {
    throw new Error(
      "Generated types are missing the components.schemas type literal",
    );
  }
  const properties = new Map();
  for (const property of schemas.type.members) {
    if (!ts.isPropertySignature(property) || !property.type) {
      throw new Error("Unsupported generated schema member");
    }
    const name = ts.isIdentifier(property.name)
      ? property.name.text
      : literalText(property.name);
    if (name === undefined || properties.has(name))
      throw new Error("Invalid schema component name");
    properties.set(name, {
      type: property.type,
      references: referencesIn(property.type),
    });
  }
  function graphFor(include) {
    return new Map(
      [...properties].map(([name, property]) => [
        name,
        new Set(
          property.references
            .filter(include)
            .map((ref) => ref.name)
            .filter((target) => properties.has(target)),
        ),
      ]),
    );
  }
  const graph = graphFor(() => true);
  const recursive = new Set(recursiveComponents(graph).flat());
  if (!recursive.size) return source;
  const unguarded = recursiveComponents(
    graphFor((reference) => !reference.guarded),
  );
  if (unguarded.length) {
    throw new Error(
      `Recursive schemas require an object or array guard: ${unguarded.flat().sort().join(", ")}`,
    );
  }
  const identifiers = new Set();
  function collectIdentifiers(node) {
    if (ts.isIdentifier(node)) identifiers.add(node.text);
    ts.forEachChild(node, collectIdentifiers);
  }
  collectIdentifiers(file);
  const aliases = new Map();
  for (const name of [...recursive].sort()) {
    const stem = `_RuntimeApiRecursiveSchema_${name.replace(/[^A-Za-z0-9_$]/g, (character) => `_${character.codePointAt(0).toString(16)}_`)}`;
    let candidate = stem;
    let suffix = 1;
    while (identifiers.has(candidate)) candidate = `${stem}_${suffix++}`;
    identifiers.add(candidate);
    aliases.set(name, candidate);
  }
  const replacements = [];
  const declarations = [];
  for (const [name, alias] of aliases) {
    const { type, references } = properties.get(name);
    const start = type.getStart(file);
    const end = type.getEnd();
    const body = replaceSpans(
      source.slice(start, end),
      references
        .filter((reference) => aliases.has(reference.name))
        .map((reference) => ({
          start: reference.node.getStart(file) - start,
          end: reference.node.getEnd() - start,
          text: aliases.get(reference.name),
        })),
    );
    declarations.push(`type ${alias} = ${body};`);
    replacements.push({ start, end, text: alias });
  }
  return `${replaceSpans(source, replacements).trimEnd()}\n\n// Guarded recursive schema aliases; generated from components.schemas.\n${declarations.join("\n\n")}\n`;
}

async function main() {
  const index = process.argv.indexOf("--types");
  const value = index >= 0 ? process.argv[index + 1] : undefined;
  if (!value) throw new Error("Missing required argument --types");
  const filePath = path.resolve(value);
  const source = await fs.readFile(filePath, "utf8");
  const normalized = normalizeRecursiveOpenApiTypes(source);
  if (normalized !== source) await fs.writeFile(filePath, normalized, "utf8");
}

if (
  path.basename(process.argv[1] ?? "") ===
  "normalize-recursive-openapi-types.mjs"
) {
  await main();
}
