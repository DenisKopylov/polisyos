import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import ts from "typescript";

import {
  canonicalizeRuntimeClientSource,
  RuntimeApiClientGenerationError,
} from "./canonicalize-runtime-client.mjs";

const GENERATED_SOURCE = `// GENERATED FILE. DO NOT EDIT.
// Source: schemas/runtime_api_v1.openapi.json

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | { [key: string]: JsonValue }
  | JsonValue[];

export type ArtifactRefInput = { artifact_id: string };

export type AvailableGovernedProjectionPacket = {
  availability: string;
  packet_schema_version?: string;
};

export type ChannelRegistryEntry = { capability_state?: string };

export interface RuntimeApiClientOptions {
  baseUrl: string;
}

export class RuntimeApiClient {}
`;

const COMPONENT_TYPES = `export interface components {
  schemas: {
    "ArtifactRef-Input": { artifact_id: string };
    AvailableGovernedProjectionPacket: {
      availability: string;
      packet_schema_version?: string;
    };
    ChannelRegistryEntry: { capability_state?: string };
    JsonValue: unknown;
  };
}
`;

const COMPONENT_SCHEMA_NAMES = [
  "ArtifactRef-Input",
  "AvailableGovernedProjectionPacket",
  "ChannelRegistryEntry",
  "JsonValue",
];
const NONCOLLIDING_SCHEMA_NAMES = COMPONENT_SCHEMA_NAMES.slice(0, 3);
const SCHEMA_BLOCK_HINT =
  "// OpenAPI component aliases generated from components.schemas.";

function parseClient(source) {
  return ts.createSourceFile("client.ts", source, ts.ScriptTarget.Latest, true);
}

function exportedTypeAliases(source) {
  return parseClient(source).statements.filter(
    (node) =>
      ts.isTypeAliasDeclaration(node) &&
      node.modifiers?.some(
        (modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword,
      ),
  );
}

function schemaBlock(source, schemaCount) {
  const file = parseClient(source);
  const optionsIndex = file.statements.findIndex(
    (node) =>
      ts.isInterfaceDeclaration(node) &&
      node.name.text === "RuntimeApiClientOptions",
  );
  return file.statements.slice(optionsIndex - schemaCount, optionsIndex);
}

function schemaCollisionSource(supportBody, schemaBody) {
  return `// GENERATED FILE. DO NOT EDIT.
// Source: schemas/runtime_api_v1.openapi.json

export type JsonValue = ${supportBody};

export type ArtifactRefInput = { artifact_id: string };

export type AvailableGovernedProjectionPacket = {
  availability: string;
  packet_schema_version?: string;
};

export type ChannelRegistryEntry = { capability_state?: string };

export type JsonValue = ${schemaBody};

export interface RuntimeApiClientOptions { baseUrl: string; }
export class RuntimeApiClient {}
`;
}

function typeDiagnostics(runtimeSource, typesSource) {
  const runtimePath = path.resolve("virtual-canonical-client.ts");
  const typesPath = path.resolve("types.ts");
  const virtualFiles = new Map([
    [runtimePath, runtimeSource],
    [typesPath, typesSource],
  ]);
  const options = {
    strict: true,
    noEmit: true,
    target: ts.ScriptTarget.ES2023,
    module: ts.ModuleKind.NodeNext,
    moduleResolution: ts.ModuleResolutionKind.NodeNext,
    skipLibCheck: true,
  };
  const host = ts.createCompilerHost(options);
  const originalFileExists = host.fileExists.bind(host);
  const originalReadFile = host.readFile.bind(host);
  const originalGetSourceFile = host.getSourceFile.bind(host);
  host.fileExists = (fileName) =>
    virtualFiles.has(path.resolve(fileName)) || originalFileExists(fileName);
  host.readFile = (fileName) =>
    virtualFiles.get(path.resolve(fileName)) ?? originalReadFile(fileName);
  host.getSourceFile = (
    fileName,
    languageVersion,
    onError,
    shouldCreateNewSourceFile,
  ) => {
    const virtualSource = virtualFiles.get(path.resolve(fileName));
    return virtualSource === undefined
      ? originalGetSourceFile(
          fileName,
          languageVersion,
          onError,
          shouldCreateNewSourceFile,
        )
      : ts.createSourceFile(fileName, virtualSource, languageVersion, true);
  };
  const program = ts.createProgram([runtimePath], options, host);
  return ts.getPreEmitDiagnostics(program).map((diagnostic) => ({
    code: diagnostic.code,
    message: ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n"),
  }));
}

function removeNode(source, node) {
  return `${source.slice(0, node.getStart())}${source.slice(node.end)}`;
}

test("canonicalization binds the complete sorted schema run to types.ts", () => {
  const canonicalized = canonicalizeRuntimeClientSource(
    GENERATED_SOURCE,
    NONCOLLIDING_SCHEMA_NAMES,
  );
  const block = schemaBlock(canonicalized, NONCOLLIDING_SCHEMA_NAMES.length);

  assert.match(
    canonicalized,
    /import type \{ components as RuntimeApiComponents \} from "\.\/types\.js";/,
  );
  assert.deepEqual(
    block.map((node) => node.name.text),
    [
      "ArtifactRefInput",
      "AvailableGovernedProjectionPacket",
      "ChannelRegistryEntry",
    ],
  );
  assert.ok(
    block.every((node, index) => {
      const schemaName = NONCOLLIDING_SCHEMA_NAMES[index];
      return (
        ts.isTypeAliasDeclaration(node) &&
        node.modifiers?.some(
          (modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword,
        ) &&
        node.type.getText() ===
          `RuntimeApiComponents["schemas"][${JSON.stringify(schemaName)}]`
      );
    }),
  );
  assert.match(
    canonicalized,
    /export type JsonValue =\n {2}\| string[\s\S]*\| JsonValue\[\];/,
  );
  assert.deepEqual(typeDiagnostics(canonicalized, COMPONENT_TYPES), []);
});

test("canonicalization is byte-stable when replayed", () => {
  const first = canonicalizeRuntimeClientSource(
    GENERATED_SOURCE,
    NONCOLLIDING_SCHEMA_NAMES,
  );
  assert.equal(
    canonicalizeRuntimeClientSource(first, NONCOLLIDING_SCHEMA_NAMES),
    first,
  );
});

test("an identical support/schema name keeps its exact private binding with a targeted lint exemption", () => {
  const identicalBody = 'RuntimeApiComponents["schemas"]["JsonValue"]';
  const source = schemaCollisionSource(identicalBody, "unknown").replace(
    "export type JsonValue =",
    'import type { components as RuntimeApiComponents } from "./types.js";\n\nexport type JsonValue =',
  );
  const canonicalized = canonicalizeRuntimeClientSource(
    source,
    COMPONENT_SCHEMA_NAMES,
  );
  const publicJsonValues = exportedTypeAliases(canonicalized).filter(
    (node) => node.name.text === "JsonValue",
  );
  const block = schemaBlock(canonicalized, COMPONENT_SCHEMA_NAMES.length);

  assert.equal(publicJsonValues.length, 1);
  assert.equal(publicJsonValues[0].type.getText(), identicalBody);
  assert.equal(block.length, COMPONENT_SCHEMA_NAMES.length);
  assert.equal(block.at(-1).name.text, "__RuntimeApiSchema_JsonValue");
  assert.match(
    canonicalized,
    /\/\* eslint-disable-next-line @typescript-eslint\/no-unused-vars -- preserve the colliding schema binding without changing the package-root support type \*\/\ntype __RuntimeApiSchema_JsonValue = RuntimeApiComponents\["schemas"\]\["JsonValue"\];/,
  );
  assert.equal(
    (
      canonicalized.match(
        /eslint-disable-next-line @typescript-eslint\/no-unused-vars/g,
      ) ?? []
    ).length,
    1,
  );
  assert.deepEqual(typeDiagnostics(canonicalized, COMPONENT_TYPES), []);
});

test("different root and component JsonValue contracts remain separately typed", () => {
  const supportBody = `
  | string
  | number
  | boolean
  | null
  | { [key: string]: JsonValue }
  | JsonValue[]`;
  const source = schemaCollisionSource(supportBody, "unknown");
  const canonicalized = canonicalizeRuntimeClientSource(
    source,
    COMPONENT_SCHEMA_NAMES,
  );
  const publicJsonValues = exportedTypeAliases(canonicalized).filter(
    (node) => node.name.text === "JsonValue",
  );
  const block = schemaBlock(canonicalized, COMPONENT_SCHEMA_NAMES.length);
  const privateJsonValue = block.at(-1);

  assert.equal(publicJsonValues.length, 1);
  assert.match(
    publicJsonValues[0].type.getText(),
    /\| string[\s\S]*\| JsonValue\[\]/,
  );
  assert.equal(privateJsonValue.name.text, "__RuntimeApiSchema_JsonValue");
  assert.match(
    canonicalized,
    /\/\* eslint-disable-next-line @typescript-eslint\/no-unused-vars -- preserve the colliding schema binding without changing the package-root support type \*\/\ntype __RuntimeApiSchema_JsonValue = RuntimeApiComponents\["schemas"\]\["JsonValue"\];/,
  );
  assert.equal(
    privateJsonValue.type.getText(),
    'RuntimeApiComponents["schemas"]["JsonValue"]',
  );
  assert.equal(
    canonicalizeRuntimeClientSource(canonicalized, COMPONENT_SCHEMA_NAMES),
    canonicalized,
  );

  const consumers = `
const validJson: JsonValue = { nested: [null, 3] };
// @ts-expect-error the established package-root JSON type rejects undefined
const invalidJson: JsonValue = undefined;
type SchemaValue = RuntimeApiComponents["schemas"]["JsonValue"];
const namespacedSchemaValue: SchemaValue = undefined;
void validJson;
void invalidJson;
void namespacedSchemaValue;
`;
  assert.deepEqual(
    typeDiagnostics(`${canonicalized}\n${consumers}`, COMPONENT_TYPES),
    [],
  );

  // A comment is only a hint. Keeping it while removing the private binding leaves
  // an incomplete producer block, which AST validation must reject on replay.
  const withoutBinding = removeNode(canonicalized, privateJsonValue);
  const withForgedHint = `${SCHEMA_BLOCK_HINT}\n${withoutBinding}`;
  assert.throws(
    () =>
      canonicalizeRuntimeClientSource(withForgedHint, COMPONENT_SCHEMA_NAMES),
    (error) =>
      error instanceof RuntimeApiClientGenerationError &&
      error.code === "schema_declaration_sequence",
  );

  // The concrete TS compiler also rejects loss of the source-of-truth component
  // while any descriptive comment and generated consumer remain in place.
  const typesWithoutComponent = COMPONENT_TYPES.replace(
    "    JsonValue: unknown;\n",
    "",
  );
  const diagnostics = typeDiagnostics(
    `${SCHEMA_BLOCK_HINT}\n${canonicalized}`,
    typesWithoutComponent,
  );
  assert.ok(
    diagnostics.some(
      (diagnostic) =>
        diagnostic.code === 2339 && /JsonValue/.test(diagnostic.message),
    ),
    "removing the actual component property must fail TypeScript compilation even when a comment remains",
  );
});

test("all colliding schema aliases receive only their own targeted lint exemption", () => {
  const source = `// GENERATED FILE. DO NOT EDIT.
// Source: schemas/runtime_api_v1.openapi.json

export type ArtifactRefInput = { established: true };
export type JsonValue = string | number;
export type ArtifactRefInput = { schema: true };
export type JsonValue = unknown;
export interface RuntimeApiClientOptions { baseUrl: string; }
export class RuntimeApiClient {}
`;
  const canonicalized = canonicalizeRuntimeClientSource(source, [
    "ArtifactRefInput",
    "JsonValue",
  ]);
  const block = schemaBlock(canonicalized, 2);

  assert.deepEqual(
    block.map((node) => node.name.text),
    ["__RuntimeApiSchema_ArtifactRefInput", "__RuntimeApiSchema_JsonValue"],
  );
  assert.equal(
    (
      canonicalized.match(
        /eslint-disable-next-line @typescript-eslint\/no-unused-vars/g,
      ) ?? []
    ).length,
    2,
  );
  assert.equal(
    (canonicalized.match(/eslint-disable-next-line/g) ?? []).length,
    2,
  );
  assert.deepEqual(
    typeDiagnostics(
      `${canonicalized}\ntype SchemaArtifactRef = RuntimeApiComponents["schemas"]["ArtifactRefInput"];\ntype SchemaJson = RuntimeApiComponents["schemas"]["JsonValue"];`,
      `export interface components { schemas: { ArtifactRefInput: { schema: true }; JsonValue: unknown; }; }`,
    ),
    [],
  );
});

test("a namespaced binding with a changed target fails even when a hint comment remains", () => {
  const canonicalized = canonicalizeRuntimeClientSource(
    schemaCollisionSource("string | number", "unknown"),
    COMPONENT_SCHEMA_NAMES,
  );
  const privateJsonValue = schemaBlock(
    canonicalized,
    COMPONENT_SCHEMA_NAMES.length,
  ).at(-1);
  const forged =
    canonicalized.slice(0, privateJsonValue.getStart()) +
    `type ${privateJsonValue.name.text} = unknown;` +
    canonicalized.slice(privateJsonValue.end);
  assert.throws(
    () =>
      canonicalizeRuntimeClientSource(
        `${SCHEMA_BLOCK_HINT}\n${forged}`,
        COMPONENT_SCHEMA_NAMES,
      ),
    (error) =>
      error instanceof RuntimeApiClientGenerationError &&
      error.code === "schema_binding_changed",
  );
});

test("schema names that normalize to one export fail with typed collision details", () => {
  assert.throws(
    () =>
      canonicalizeRuntimeClientSource(GENERATED_SOURCE, [
        "ArtifactRef-Input",
        "ArtifactRefInput",
      ]),
    (error) =>
      error instanceof RuntimeApiClientGenerationError &&
      error.code === "schema_alias_collision" &&
      error.details.alias === "ArtifactRefInput" &&
      error.details.schemaNames.join("|") ===
        "ArtifactRef-Input|ArtifactRefInput",
  );
});

test("generated private names avoid existing declarations and remain replay-stable", () => {
  const source = `// GENERATED FILE. DO NOT EDIT.
// Source: schemas/runtime_api_v1.openapi.json

export type JsonValue = string | number;
export type __RuntimeApiSchema_JsonValue = { retained: true };
export type JsonValue = unknown;
export interface RuntimeApiClientOptions { baseUrl: string; }
export class RuntimeApiClient {}
`;
  const canonicalized = canonicalizeRuntimeClientSource(source, ["JsonValue"]);
  const block = schemaBlock(canonicalized, 1);

  assert.equal(block[0].name.text, "__RuntimeApiSchema_JsonValue_2");
  assert.equal(
    block[0].type.getText(),
    'RuntimeApiComponents["schemas"]["JsonValue"]',
  );
  assert.equal(
    canonicalizeRuntimeClientSource(canonicalized, ["JsonValue"]),
    canonicalized,
  );
});

test("schema aliases that collide with an imported local type name fail closed", () => {
  const source = `// GENERATED FILE. DO NOT EDIT.
// Source: schemas/runtime_api_v1.openapi.json

import type { RemoteShape as JsonValue } from "./remote.js";
export type JsonValue = unknown;
export interface RuntimeApiClientOptions { baseUrl: string; }
export class RuntimeApiClient {}
`;
  assert.throws(
    () => canonicalizeRuntimeClientSource(source, ["JsonValue"]),
    (error) =>
      error instanceof RuntimeApiClientGenerationError &&
      error.code === "export_namespace_collision" &&
      error.details.alias === "JsonValue",
  );
});

test("schema aliases that collide with interface or class declarations fail closed", () => {
  const interfaceCollision = `// GENERATED FILE. DO NOT EDIT.
// Source: schemas/runtime_api_v1.openapi.json

export type RuntimeApiClientOptions = { source: string };
export interface RuntimeApiClientOptions { baseUrl: string; }
export class RuntimeApiClient {}
`;
  assert.throws(
    () =>
      canonicalizeRuntimeClientSource(interfaceCollision, [
        "RuntimeApiClientOptions",
      ]),
    (error) =>
      error instanceof RuntimeApiClientGenerationError &&
      error.code === "export_namespace_collision" &&
      error.details.alias === "RuntimeApiClientOptions",
  );

  const classCollision = `// GENERATED FILE. DO NOT EDIT.
// Source: schemas/runtime_api_v1.openapi.json

export type RuntimeApiClient = { source: string };
export interface RuntimeApiClientOptions { baseUrl: string; }
export class RuntimeApiClient {}
`;
  assert.throws(
    () => canonicalizeRuntimeClientSource(classCollision, ["RuntimeApiClient"]),
    (error) =>
      error instanceof RuntimeApiClientGenerationError &&
      error.code === "export_namespace_collision" &&
      error.details.alias === "RuntimeApiClient",
  );
});
