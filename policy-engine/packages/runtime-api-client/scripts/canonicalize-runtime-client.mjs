import fs from "node:fs/promises";
import path from "node:path";

import prettier from "prettier";
import ts from "typescript";

const CLIENT_CLASS_NAME = "RuntimeApiClient";
const CLIENT_OPTIONS_NAME = "RuntimeApiClientOptions";
const COMPONENTS_MODULE = "./types.js";
const COMPONENTS_IMPORT_BASE = "RuntimeApiComponents";
const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/;

export class RuntimeApiClientGenerationError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = "RuntimeApiClientGenerationError";
    this.code = code;
    this.details = Object.freeze({ ...details });
  }
}

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

function compareNames(left, right) {
  const leftCodePoints = Array.from(left, (character) =>
    character.codePointAt(0),
  );
  const rightCodePoints = Array.from(right, (character) =>
    character.codePointAt(0),
  );
  for (
    let index = 0;
    index < Math.min(leftCodePoints.length, rightCodePoints.length);
    index += 1
  ) {
    if (leftCodePoints[index] !== rightCodePoints[index]) {
      return leftCodePoints[index] - rightCodePoints[index];
    }
  }
  return leftCodePoints.length - rightCodePoints.length;
}

function schemaNamesByGeneratedAlias(schemaNames) {
  const aliases = new Map();
  for (const schemaName of schemaNames) {
    const alias = generatedTypeName(schemaName);
    const existing = aliases.get(alias);
    if (existing !== undefined) {
      const code =
        existing === schemaName
          ? "duplicate_schema_name"
          : "schema_alias_collision";
      throw new RuntimeApiClientGenerationError(
        code,
        existing === schemaName
          ? `OpenAPI component schema name is repeated: ${schemaName}`
          : `OpenAPI schema aliases collide at ${alias}: ${existing}, ${schemaName}`,
        { alias, schemaNames: [existing, schemaName] },
      );
    }
    aliases.set(alias, schemaName);
  }
  return aliases;
}

function isExported(node) {
  return (
    node.modifiers?.some(
      (modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword,
    ) ?? false
  );
}

function declarationName(node) {
  if (
    !ts.isTypeAliasDeclaration(node) &&
    !ts.isInterfaceDeclaration(node) &&
    !ts.isClassDeclaration(node)
  ) {
    return undefined;
  }
  return ts.isIdentifier(node.name) ? node.name.text : undefined;
}

function namedStatementName(node) {
  if (
    ts.isTypeAliasDeclaration(node) ||
    ts.isInterfaceDeclaration(node) ||
    ts.isClassDeclaration(node) ||
    ts.isEnumDeclaration(node) ||
    ts.isFunctionDeclaration(node) ||
    ts.isModuleDeclaration(node)
  ) {
    return ts.isIdentifier(node.name) ? node.name.text : undefined;
  }
  return undefined;
}

function addBindingName(name, names) {
  if (ts.isIdentifier(name)) {
    names.add(name.text);
  } else if (
    ts.isObjectBindingPattern(name) ||
    ts.isArrayBindingPattern(name)
  ) {
    for (const element of name.elements) {
      if (ts.isBindingElement(element)) {
        addBindingName(element.name, names);
      }
    }
  }
}

function topLevelNames(sourceFile, excludedStatements) {
  const names = new Set();
  for (const statement of sourceFile.statements) {
    if (excludedStatements.has(statement)) continue;
    const named = namedStatementName(statement);
    if (named) names.add(named);
    if (ts.isVariableStatement(statement)) {
      for (const declaration of statement.declarationList.declarations) {
        addBindingName(declaration.name, names);
      }
    }
    for (const exported of exportedNames(statement)) names.add(exported);
    if (ts.isImportDeclaration(statement) && statement.importClause) {
      const clause = statement.importClause;
      if (clause.name) names.add(clause.name.text);
      if (clause.namedBindings && ts.isNamespaceImport(clause.namedBindings)) {
        names.add(clause.namedBindings.name.text);
      } else if (
        clause.namedBindings &&
        ts.isNamedImports(clause.namedBindings)
      ) {
        for (const element of clause.namedBindings.elements) {
          names.add(element.name.text);
        }
      }
    }
  }
  return names;
}

function parseSource(source) {
  const sourceFile = ts.createSourceFile(
    "canonicalRuntimeApiClient.ts",
    source,
    ts.ScriptTarget.Latest,
    true,
  );
  if (sourceFile.parseDiagnostics.length > 0) {
    throw new RuntimeApiClientGenerationError(
      "invalid_generated_typescript",
      "Generated client is not valid TypeScript",
    );
  }
  return sourceFile;
}

function findRequiredStatements(sourceFile) {
  const clientDeclarations = sourceFile.statements.filter(
    (node) =>
      ts.isClassDeclaration(node) && node.name?.text === CLIENT_CLASS_NAME,
  );
  if (clientDeclarations.length !== 1 || !isExported(clientDeclarations[0])) {
    throw new RuntimeApiClientGenerationError(
      "client_class_missing",
      `Generated client must contain exactly one exported ${CLIENT_CLASS_NAME} class`,
      { count: clientDeclarations.length },
    );
  }
  const optionDeclarations = sourceFile.statements.filter(
    (node) =>
      ts.isInterfaceDeclaration(node) && node.name.text === CLIENT_OPTIONS_NAME,
  );
  if (optionDeclarations.length !== 1 || !isExported(optionDeclarations[0])) {
    throw new RuntimeApiClientGenerationError(
      "client_options_missing",
      `Generated client must contain exactly one exported ${CLIENT_OPTIONS_NAME} interface`,
      { count: optionDeclarations.length },
    );
  }
  const clientIndex = sourceFile.statements.indexOf(clientDeclarations[0]);
  const optionsIndex = sourceFile.statements.indexOf(optionDeclarations[0]);
  if (clientIndex !== optionsIndex + 1) {
    throw new RuntimeApiClientGenerationError(
      "producer_layout_changed",
      `${CLIENT_OPTIONS_NAME} must immediately precede ${CLIENT_CLASS_NAME}`,
    );
  }
  return { clientIndex, optionsIndex };
}

/**
 * Locate and validate the complete schema-alias run emitted before client options.
 *
 * The raw producer emits every component alias in sorted source-name order directly
 * before RuntimeApiClientOptions. Canonicalization keeps that same complete run,
 * including non-exported bindings used when an existing support alias owns a name.
 *
 * @param {ts.SourceFile} sourceFile Parsed generated client.
 * @param {Map<string, string>} canonicalSchemas Generated alias to source schema name.
 * @param {number} optionsIndex Statement index for RuntimeApiClientOptions.
 * @returns {ts.TypeAliasDeclaration[]} Complete ordered schema alias run.
 */
function findSchemaTypeBlock(sourceFile, canonicalSchemas, optionsIndex) {
  const expectedAliases = [...canonicalSchemas.entries()]
    .sort((left, right) => compareNames(left[1], right[1]))
    .map(([alias]) => alias);
  if (expectedAliases.length === 0) {
    throw new RuntimeApiClientGenerationError(
      "schema_aliases_missing",
      "Generated client has no OpenAPI component schemas",
    );
  }
  const start = optionsIndex - expectedAliases.length;
  const statements = sourceFile.statements.slice(start, optionsIndex);
  if (
    start < 0 ||
    statements.length !== expectedAliases.length ||
    statements.some((statement) => !ts.isTypeAliasDeclaration(statement))
  ) {
    throw new RuntimeApiClientGenerationError(
      "schema_declaration_sequence",
      "Generated client does not contain the complete type-alias run before RuntimeApiClientOptions",
      { expectedAliases },
    );
  }
  return statements;
}

function stringLiteralIndex(typeNode) {
  if (
    !ts.isLiteralTypeNode(typeNode) ||
    !ts.isStringLiteral(typeNode.literal)
  ) {
    return undefined;
  }
  return typeNode.literal.text;
}

function isComponentType(typeNode, localName, schemaName) {
  if (!ts.isIndexedAccessTypeNode(typeNode)) return false;
  if (stringLiteralIndex(typeNode.indexType) !== schemaName) return false;
  const schemasAccess = typeNode.objectType;
  if (
    !ts.isIndexedAccessTypeNode(schemasAccess) ||
    stringLiteralIndex(schemasAccess.indexType) !== "schemas"
  ) {
    return false;
  }
  return (
    ts.isTypeReferenceNode(schemasAccess.objectType) &&
    ts.isIdentifier(schemasAccess.objectType.typeName) &&
    schemasAccess.objectType.typeName.text === localName
  );
}

function componentImport(sourceFile) {
  const matches = [];
  for (const statement of sourceFile.statements) {
    if (
      !ts.isImportDeclaration(statement) ||
      !ts.isStringLiteral(statement.moduleSpecifier) ||
      statement.moduleSpecifier.text !== COMPONENTS_MODULE
    ) {
      continue;
    }
    const bindings = statement.importClause?.namedBindings;
    if (!bindings || !ts.isNamedImports(bindings)) continue;
    for (const element of bindings.elements) {
      const importedName = element.propertyName?.text ?? element.name.text;
      if (importedName === "components") {
        matches.push({
          statement,
          localName: element.name.text,
          isTypeOnly: statement.importClause.isTypeOnly || element.isTypeOnly,
        });
      }
    }
  }
  if (matches.length > 1) {
    throw new RuntimeApiClientGenerationError(
      "components_import_ambiguous",
      "Generated client imports components from ./types.js more than once",
    );
  }
  if (matches.length === 1 && !matches[0].isTypeOnly) {
    throw new RuntimeApiClientGenerationError(
      "components_import_not_type_only",
      "The components binding from ./types.js must be imported as a type",
    );
  }
  return matches[0];
}

function allocateName(base, occupied) {
  let candidate = base;
  let suffix = 2;
  while (occupied.has(candidate)) {
    candidate = `${base}_${suffix}`;
    suffix += 1;
  }
  occupied.add(candidate);
  return candidate;
}

function componentImportName(sourceFile, blockSet, canonicalSchemas, reserved) {
  const existing = componentImport(sourceFile);
  if (existing) {
    const otherNames = topLevelNames(
      sourceFile,
      new Set([...blockSet, existing.statement]),
    );
    if (
      otherNames.has(existing.localName) ||
      canonicalSchemas.has(existing.localName)
    ) {
      throw new RuntimeApiClientGenerationError(
        "components_import_collision",
        `The components import binding ${existing.localName} collides with a client declaration`,
        { alias: existing.localName },
      );
    }
    return { localName: existing.localName, insert: false };
  }
  const occupied = new Set([...reserved, ...canonicalSchemas.keys()]);
  return {
    localName: allocateName(COMPONENTS_IMPORT_BASE, occupied),
    insert: true,
  };
}

function privateSchemaAlias(alias, occupied) {
  return allocateName(`__RuntimeApiSchema_${alias}`, occupied);
}

function importLocalNames(statement) {
  if (!ts.isImportDeclaration(statement) || !statement.importClause) return [];
  const names = [];
  const clause = statement.importClause;
  if (clause.name) names.push(clause.name.text);
  if (clause.namedBindings && ts.isNamespaceImport(clause.namedBindings)) {
    names.push(clause.namedBindings.name.text);
  } else if (clause.namedBindings && ts.isNamedImports(clause.namedBindings)) {
    names.push(
      ...clause.namedBindings.elements.map((element) => element.name.text),
    );
  }
  return names;
}

function exportedNames(statement) {
  if (
    !ts.isExportDeclaration(statement) ||
    !statement.exportClause ||
    !ts.isNamedExports(statement.exportClause)
  ) {
    return [];
  }
  return statement.exportClause.elements.map((element) => element.name.text);
}

function sameNameDeclarations(sourceFile, blockSet, name) {
  return sourceFile.statements.filter((statement) => {
    if (blockSet.has(statement)) return false;
    return (
      namedStatementName(statement) === name ||
      importLocalNames(statement).includes(name) ||
      exportedNames(statement).includes(name)
    );
  });
}

function applyEdits(source, edits) {
  let result = source;
  for (const edit of [...edits].sort(
    (left, right) => right.start - left.start,
  )) {
    result = `${result.slice(0, edit.start)}${edit.text}${result.slice(edit.end)}`;
  }
  return result;
}

/**
 * Replace generated schema DTO bodies with aliases to openapi-typescript output.
 *
 * Existing top-level type aliases keep their package-root meaning when a component
 * schema generates the same TypeScript name. The schema alias remains represented
 * in the complete producer block as a private, exact binding to the public
 * RuntimeApiComponents.schemas member in types.ts. Collisions with other declaration
 * kinds are rejected rather than silently dropping or widening either contract.
 *
 * @param {string} source Raw or previously canonicalized runtime client TypeScript.
 * @param {Iterable<string>} schemaNames OpenAPI component schema names.
 * @returns {string} Canonicalized client TypeScript.
 */
export function canonicalizeRuntimeClientSource(source, schemaNames) {
  const canonicalSchemas = schemaNamesByGeneratedAlias(schemaNames);
  const sourceFile = parseSource(source);
  const { optionsIndex } = findRequiredStatements(sourceFile);
  const schemaDeclarations = findSchemaTypeBlock(
    sourceFile,
    canonicalSchemas,
    optionsIndex,
  );
  const schemaDeclarationSet = new Set(schemaDeclarations);
  const reservedNames = topLevelNames(sourceFile, schemaDeclarationSet);
  const importBinding = componentImportName(
    sourceFile,
    schemaDeclarationSet,
    canonicalSchemas,
    reservedNames,
  );
  const occupiedPrivateNames = new Set([
    ...reservedNames,
    ...canonicalSchemas.keys(),
    importBinding.localName,
  ]);
  const edits = [];

  for (const [index, declaration] of schemaDeclarations.entries()) {
    const [alias, schemaName] = [...canonicalSchemas.entries()].sort(
      (left, right) => compareNames(left[1], right[1]),
    )[index];
    const currentName = declarationName(declaration);
    const existing = sameNameDeclarations(
      sourceFile,
      schemaDeclarationSet,
      alias,
    );
    const existingTypeAliases = existing.filter(ts.isTypeAliasDeclaration);
    const otherKinds = existing.filter(
      (statement) => !ts.isTypeAliasDeclaration(statement),
    );
    if (otherKinds.length > 0) {
      throw new RuntimeApiClientGenerationError(
        "export_namespace_collision",
        `OpenAPI schema alias ${alias} collides with another top-level declaration`,
        {
          alias,
          declarationKinds: otherKinds.map(
            (statement) => ts.SyntaxKind[statement.kind],
          ),
        },
      );
    }
    if (existingTypeAliases.length > 1) {
      throw new RuntimeApiClientGenerationError(
        "support_alias_ambiguous",
        `OpenAPI schema alias ${alias} has multiple existing top-level type aliases`,
        { alias, count: existingTypeAliases.length },
      );
    }
    if (
      currentName !== alias &&
      !currentName?.startsWith(`__RuntimeApiSchema_${alias}`)
    ) {
      throw new RuntimeApiClientGenerationError(
        "schema_declaration_sequence",
        `Schema slot for ${schemaName} has unexpected type alias ${currentName}`,
        { alias, schemaName, actualName: currentName },
      );
    }

    const collidesWithSupport = existingTypeAliases.length === 1;
    if (!collidesWithSupport && currentName !== alias) {
      throw new RuntimeApiClientGenerationError(
        "schema_declaration_sequence",
        `Schema slot for ${schemaName} must retain its generated alias ${alias}`,
        { alias, schemaName, actualName: currentName },
      );
    }
    if (
      collidesWithSupport &&
      currentName !== alias &&
      isExported(declaration)
    ) {
      throw new RuntimeApiClientGenerationError(
        "schema_declaration_sequence",
        `Namespaced schema slot for ${schemaName} must not re-export ${alias}`,
        { alias, schemaName, actualName: currentName },
      );
    }

    let targetName = alias;
    let exportKeyword = "export ";
    if (collidesWithSupport) {
      targetName = privateSchemaAlias(alias, occupiedPrivateNames);
      exportKeyword = "";
      if (currentName !== alias) {
        if (currentName !== targetName || isExported(declaration)) {
          throw new RuntimeApiClientGenerationError(
            "schema_declaration_sequence",
            `Private schema binding for ${schemaName} does not match the complete canonical block`,
            {
              alias,
              schemaName,
              expectedPrivateAlias: targetName,
              actualName: currentName,
            },
          );
        }
        if (
          isComponentType(declaration.type, importBinding.localName, schemaName)
        ) {
          continue;
        }
        throw new RuntimeApiClientGenerationError(
          "schema_binding_changed",
          `Private schema binding for ${schemaName} no longer points to its exact components.schemas member`,
          { alias, schemaName, actualName: currentName },
        );
      }
    } else if (
      isComponentType(declaration.type, importBinding.localName, schemaName)
    ) {
      continue;
    }

    const lintDirective = collidesWithSupport
      ? "/* eslint-disable-next-line @typescript-eslint/no-unused-vars -- preserve the colliding schema binding without changing the package-root support type */\n"
      : "";
    const replacement = `${lintDirective}${exportKeyword}type ${targetName} = ${importBinding.localName}["schemas"][${JSON.stringify(schemaName)}];`;
    edits.push({
      start: declaration.getStart(sourceFile),
      end: declaration.end,
      text: replacement,
    });
  }

  let canonicalized = applyEdits(source, edits);
  if (importBinding.insert) {
    const firstStatement = sourceFile.statements[0];
    if (!firstStatement) {
      throw new RuntimeApiClientGenerationError(
        "generated_header_missing",
        "Generated client has no statement before which to insert the schema type import",
      );
    }
    const importText = `import type { components as ${importBinding.localName} } from "${COMPONENTS_MODULE}";\n\n`;
    const insertionPoint = firstStatement.getStart(sourceFile);
    canonicalized = `${canonicalized.slice(0, insertionPoint)}${importText}${canonicalized.slice(insertionPoint)}`;
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
