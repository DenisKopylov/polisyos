import fs from "node:fs/promises";
import path from "node:path";

import prettier from "prettier";

const CANONICAL_IMPORT = [
  "import",
  'type { components as RuntimeApiComponents } from "./types.js";',
].join(" ");
const DECLARATION_START =
  /^export (type|interface|class) ([A-Za-z_$][A-Za-z0-9_$]*)[ ={]/gm;
const CLIENT_START = "export class RuntimeApiClient";
const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/;

function generatedTypeName(schemaName) {
  if (IDENTIFIER.test(schemaName)) {
    return schemaName;
  }
  const parts = schemaName.split(/[^A-Za-z0-9]+/).filter(Boolean);
  let candidate = parts
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join("");
  if (!candidate) {
    return "AnonymousSchema";
  }
  if (/^[0-9]/.test(candidate)) {
    candidate = `Schema${candidate}`;
  }
  return IDENTIFIER.test(candidate) ? candidate : "AnonymousSchema";
}

function schemaNamesByGeneratedAlias(schemaNames) {
  const aliases = new Map();
  for (const schemaName of schemaNames) {
    const alias = generatedTypeName(schemaName);
    const existing = aliases.get(alias);
    if (existing !== undefined && existing !== schemaName) {
      throw new Error(
        `OpenAPI schema aliases collide at ${alias}: ${existing}, ${schemaName}`,
      );
    }
    aliases.set(alias, schemaName);
  }
  return aliases;
}

/**
 * Replace generated schema DTO bodies with aliases to openapi-typescript output.
 *
 * @param {string} source Raw generated runtime client TypeScript.
 * @param {Iterable<string>} schemaNames OpenAPI component schema names.
 * @returns {string} Canonicalized, byte-stable client TypeScript.
 */
export function canonicalizeRuntimeClientSource(source, schemaNames) {
  const canonicalSchemas = schemaNamesByGeneratedAlias(schemaNames);
  const clientStart = source.indexOf(CLIENT_START);
  if (clientStart < 0) {
    throw new Error(`Generated client is missing ${CLIENT_START}`);
  }

  const declarations = Array.from(source.matchAll(DECLARATION_START));
  const typeDeclarations = declarations.filter(
    (match) =>
      match[1] === "type" && (match.index ?? clientStart) < clientStart,
  );
  if (typeDeclarations.length === 0) {
    throw new Error("Generated client contains no exported DTO aliases");
  }

  let cursor = 0;
  let canonicalizedCount = 0;
  const chunks = [];
  for (const match of typeDeclarations) {
    const start = match.index;
    if (start === undefined) {
      throw new Error("Generated client type match has no source offset");
    }
    const declarationIndex = declarations.indexOf(match);
    const nextStart = declarations[declarationIndex + 1]?.index ?? clientStart;
    const name = match[2];
    const canonicalSchemaName = canonicalSchemas.get(name);
    chunks.push(source.slice(cursor, start));
    if (canonicalSchemaName !== undefined) {
      chunks.push(
        `export type ${name} = RuntimeApiComponents["schemas"][${JSON.stringify(canonicalSchemaName)}];\n\n`,
      );
      canonicalizedCount += 1;
    } else {
      chunks.push(source.slice(start, nextStart));
    }
    cursor = nextStart;
  }
  chunks.push(source.slice(cursor));

  if (canonicalizedCount === 0) {
    throw new Error(
      "Generated client has no aliases matching OpenAPI components",
    );
  }

  let canonicalized = chunks.join("");
  if (!canonicalized.includes(CANONICAL_IMPORT)) {
    const headerEnd = canonicalized.indexOf("\n\n");
    if (headerEnd < 0) {
      throw new Error("Generated client is missing its header boundary");
    }
    const insertionPoint = headerEnd + 2;
    canonicalized = `${canonicalized.slice(0, insertionPoint)}${CANONICAL_IMPORT}\n\n${canonicalized.slice(insertionPoint)}`;
  }
  return canonicalized;
}

function requiredArgument(name) {
  const index = process.argv.indexOf(name);
  const value = index >= 0 ? process.argv[index + 1] : undefined;
  if (!value) {
    throw new Error(`Missing required argument ${name}`);
  }
  return value;
}

async function main() {
  const openapiPath = path.resolve(requiredArgument("--openapi"));
  const clientPath = path.resolve(requiredArgument("--client"));
  const outputTypeScriptPath = path.resolve(requiredArgument("--out-ts"));
  const runtimeJavaScriptPath = path.resolve(requiredArgument("--runtime-js"));
  const outputJavaScriptPath = path.resolve(requiredArgument("--out-js"));
  const [openapiText, source] = await Promise.all([
    fs.readFile(openapiPath, "utf8"),
    fs.readFile(clientPath, "utf8"),
  ]);
  const openapi = JSON.parse(openapiText);
  const schemaNames = Object.keys(openapi.components?.schemas ?? {});
  const canonicalized = canonicalizeRuntimeClientSource(source, schemaNames);
  const runtimeJavaScript = await fs.readFile(runtimeJavaScriptPath, "utf8");
  const [formattedTypeScript, formattedJavaScript] = await Promise.all([
    prettier.format(canonicalized, { parser: "typescript" }),
    prettier.format(runtimeJavaScript, { parser: "babel" }),
  ]);
  await Promise.all([
    fs.writeFile(outputTypeScriptPath, formattedTypeScript, "utf8"),
    fs.writeFile(outputJavaScriptPath, formattedJavaScript, "utf8"),
  ]);
}

if (
  path.basename(process.argv[1] ?? "") === "canonicalize-runtime-client.mjs"
) {
  await main();
}
