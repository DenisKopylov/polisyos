import assert from "node:assert/strict";
import test from "node:test";

import ts from "typescript";

import { normalizeRecursiveOpenApiTypes } from "./normalize-recursive-openapi-types.mjs";

function typeErrors(source) {
  const name = "recursive-schema-probe.ts";
  const options = {
    strict: true,
    noEmit: true,
    target: ts.ScriptTarget.ES2023,
    skipLibCheck: true,
  };
  const host = ts.createCompilerHost(options);
  const originalGetSourceFile = host.getSourceFile.bind(host);
  host.getSourceFile = (
    fileName,
    languageVersion,
    onError,
    shouldCreateNewSourceFile,
  ) =>
    fileName === name
      ? ts.createSourceFile(fileName, source, languageVersion, true)
      : originalGetSourceFile(
          fileName,
          languageVersion,
          onError,
          shouldCreateNewSourceFile,
        );
  const program = ts.createProgram([name], options, host);
  return ts.getPreEmitDiagnostics(program).map((diagnostic) => ({
    code: diagnostic.code,
    message: ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n"),
  }));
}

const NONRECURSIVE =
  '    Nonrecursive: { readonly exact: "retained"; /* keep bytes */ };';
const SOURCE = `// Real openapi-typescript components layout; arbitrary sibling schema names.
export interface components {
  schemas: {
    "Tree Node": {
      label: string;
      children: components["schemas"]["Tree-Edges"];
      values: components["schemas"]["History"];
    };
    "Tree-Edges": components["schemas"]["Tree Node"][];
    History: number | components["schemas"]["History"][];
${NONRECURSIVE}
  };
}
// A pre-existing identifier must not be captured by the generated private alias.
type _RuntimeApiRecursiveSchema_History = "already occupied";
`;
const CONSUMER = `
type Tree = components["schemas"]["Tree Node"];
let tree: Tree = {label: "leaf", children: [], values: [1, [2, [3]]]};
for (let depth = 0; depth < 30; depth++) tree = {label: "branch", children: [tree], values: []};
// @ts-expect-error a recursive child must still have a string label
const wrongLabel: Tree = {label: "root", children: [{label: 1, children: [], values: []}], values: 0};
// @ts-expect-error the separate recursive history accepts only numbers and arrays
const wrongHistory: Tree = {label: "root", children: [], values: [1, [() => 2]]};
void [tree, wrongLabel, wrongHistory];
`;

test("recursive graph compiles mutual, self and cross-component edges without widening consumers", () => {
  assert.notDeepEqual(typeErrors(SOURCE + CONSUMER), []);
  const normalized = normalizeRecursiveOpenApiTypes(SOURCE);
  assert.deepEqual(typeErrors(normalized + CONSUMER), []);
  assert.ok(normalized.includes(NONRECURSIVE));
  assert.equal(normalizeRecursiveOpenApiTypes(normalized), normalized);
});

test("unguarded recursive schemas are rejected without inventing a permissive type", () => {
  const source =
    'export interface components { schemas: { A: components["schemas"]["B"]; B: components["schemas"]["A"] } }';
  assert.throws(
    () => normalizeRecursiveOpenApiTypes(source),
    /object or array guard: A, B/,
  );
});
