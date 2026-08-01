import fs from "node:fs";
import path from "node:path";
import * as ts from "typescript";

import * as decisionGradePresentation from "./decisionGradePresentation";

const dashboardSourceRoot = path.resolve(import.meta.dirname, "../../..");

function productionSources(directory: string): string[] {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return productionSources(absolutePath);
    }
    if (
      !entry.isFile() ||
      !/\.tsx?$/u.test(entry.name) ||
      /(?:\.test|\.a11y\.test|\.stories)\.tsx?$/u.test(entry.name)
    ) {
      return [];
    }
    return [absolutePath];
  });
}

function dashboardModuleCandidates(
  filename: string,
  moduleSpecifier: string,
): string[] {
  const unresolved = moduleSpecifier.startsWith("@/")
    ? path.normalize(moduleSpecifier.slice(2))
    : moduleSpecifier.startsWith(".")
      ? path.normalize(path.join(path.dirname(filename), moduleSpecifier))
      : null;
  if (!unresolved) return [];
  return [
    unresolved,
    `${unresolved}.ts`,
    `${unresolved}.tsx`,
    path.join(unresolved, "index.ts"),
    path.join(unresolved, "index.tsx"),
  ];
}

function decisionGradeRelevantSources(
  sources: Readonly<Record<string, string>>,
): Record<string, string> {
  const selected = new Set(
    Object.entries(sources)
      .filter(([, source]) =>
        /(?:verdict|decision.?grade|\bgrade\b|evaluatorVerdicts)/iu.test(
          source,
        ),
      )
      .map(([filename]) => filename),
  );
  let changed = true;
  while (changed) {
    changed = false;
    for (const filename of [...selected]) {
      const source = sources[filename];
      if (!source) continue;
      const sourceFile = ts.createSourceFile(
        filename,
        source,
        ts.ScriptTarget.Latest,
        true,
        filename.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
      );
      for (const statement of sourceFile.statements) {
        if (
          (!ts.isImportDeclaration(statement) &&
            !ts.isExportDeclaration(statement)) ||
          !statement.moduleSpecifier ||
          !ts.isStringLiteral(statement.moduleSpecifier)
        ) {
          continue;
        }
        const target = dashboardModuleCandidates(
          filename,
          statement.moduleSpecifier.text,
        ).find((candidate) => Object.hasOwn(sources, candidate));
        if (target && !selected.has(target)) {
          selected.add(target);
          changed = true;
        }
      }
    }
  }
  return Object.fromEntries(
    [...selected].sort().map((filename) => [filename, sources[filename] ?? ""]),
  );
}

type FunctionNode =
  | ts.ArrowFunction
  | ts.FunctionDeclaration
  | ts.FunctionExpression;

type FunctionDefinition = {
  filename: string;
  node: FunctionNode;
};

type ImportBinding = {
  importedName: string;
  targetFilename: string;
};

const equalityOperators = [
  ts.SyntaxKind.EqualsEqualsToken,
  ts.SyntaxKind.EqualsEqualsEqualsToken,
  ts.SyntaxKind.ExclamationEqualsToken,
  ts.SyntaxKind.ExclamationEqualsEqualsToken,
] as const;

const classificationMethods = new Set([
  "endsWith",
  "has",
  "includes",
  "startsWith",
  "toLocaleLowerCase",
  "toLocaleUpperCase",
  "toLowerCase",
  "toUpperCase",
]);

function decisionGradeBypasses(source: string, filename = "inline.ts") {
  return decisionGradeBypassesAcrossSources({ [filename]: source });
}

function decisionGradeBypassesAcrossSources(
  sources: Readonly<Record<string, string>>,
) {
  const sourceFiles = new Map(
    Object.entries(sources).map(([filename, source]) => [
      filename,
      ts.createSourceFile(
        filename,
        source,
        ts.ScriptTarget.Latest,
        true,
        filename.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
      ),
    ]),
  );
  const functionsByFile = new Map<string, Map<string, FunctionDefinition[]>>();
  const importsByFile = new Map<string, Map<string, ImportBinding>>();
  const namespaceImportsByFile = new Map<string, Map<string, string>>();
  const taintedNamesByFile = new Map<string, Set<string>>();
  const gradeName = (value: string) =>
    /(?:verdict$|decision.?grade|^grade$)/iu.test(value);
  const isAbsenceCheck = (node: ts.Expression) =>
    node.kind === ts.SyntaxKind.NullKeyword ||
    (ts.isIdentifier(node) && node.text === "undefined");

  const resolveRelativeModule = (
    filename: string,
    moduleSpecifier: string,
  ): string | null => {
    return (
      dashboardModuleCandidates(filename, moduleSpecifier).find((candidate) =>
        sourceFiles.has(candidate),
      ) ?? null
    );
  };

  const addFunction = (filename: string, name: string, node: FunctionNode) => {
    const byName = functionsByFile.get(filename) ?? new Map();
    const definitions = byName.get(name) ?? [];
    definitions.push({ filename, node });
    byName.set(name, definitions);
    functionsByFile.set(filename, byName);
  };

  for (const [filename, sourceFile] of sourceFiles) {
    taintedNamesByFile.set(filename, new Set());
    const collect = (node: ts.Node) => {
      if (ts.isFunctionDeclaration(node) && node.name) {
        addFunction(filename, node.name.text, node);
      }
      if (
        ts.isVariableDeclaration(node) &&
        ts.isIdentifier(node.name) &&
        node.initializer &&
        (ts.isArrowFunction(node.initializer) ||
          ts.isFunctionExpression(node.initializer))
      ) {
        addFunction(filename, node.name.text, node.initializer);
      }
      node.forEachChild(collect);
    };
    collect(sourceFile);

    const imports = new Map<string, ImportBinding>();
    const namespaceImports = new Map<string, string>();
    for (const statement of sourceFile.statements) {
      if (
        !ts.isImportDeclaration(statement) ||
        !ts.isStringLiteral(statement.moduleSpecifier)
      ) {
        continue;
      }
      const targetFilename = resolveRelativeModule(
        filename,
        statement.moduleSpecifier.text,
      );
      if (!targetFilename) continue;
      const clause = statement.importClause;
      if (clause?.name) {
        imports.set(clause.name.text, {
          importedName: "default",
          targetFilename,
        });
      }
      if (clause?.namedBindings && ts.isNamedImports(clause.namedBindings)) {
        for (const specifier of clause.namedBindings.elements) {
          imports.set(specifier.name.text, {
            importedName: specifier.propertyName?.text ?? specifier.name.text,
            targetFilename,
          });
        }
      }
      if (clause?.namedBindings && ts.isNamespaceImport(clause.namedBindings)) {
        namespaceImports.set(clause.namedBindings.name.text, targetFilename);
      }
    }
    importsByFile.set(filename, imports);
    namespaceImportsByFile.set(filename, namespaceImports);
  }

  const resolveFunctions = (
    filename: string,
    expression: ts.LeftHandSideExpression,
  ): { definitions: FunctionDefinition[]; imported: boolean } => {
    if (ts.isIdentifier(expression)) {
      const localDefinitions =
        functionsByFile.get(filename)?.get(expression.text) ?? [];
      const binding = importsByFile.get(filename)?.get(expression.text);
      const importedDefinitions = binding
        ? (functionsByFile
            .get(binding.targetFilename)
            ?.get(binding.importedName) ?? [])
        : [];
      return {
        definitions: [...localDefinitions, ...importedDefinitions],
        imported: importedDefinitions.length > 0,
      };
    }
    if (
      ts.isPropertyAccessExpression(expression) &&
      ts.isIdentifier(expression.expression)
    ) {
      const targetFilename = namespaceImportsByFile
        .get(filename)
        ?.get(expression.expression.text);
      if (targetFilename) {
        return {
          definitions:
            functionsByFile.get(targetFilename)?.get(expression.name.text) ??
            [],
          imported: true,
        };
      }
    }
    return { definitions: [], imported: false };
  };

  const expressionCarriesGrade = (
    filename: string,
    node: ts.Node | undefined,
  ): boolean => {
    if (!node) return false;
    if (ts.isIdentifier(node)) {
      return (
        gradeName(node.text) ||
        Boolean(taintedNamesByFile.get(filename)?.has(node.text))
      );
    }
    if (ts.isPropertyAccessExpression(node) && gradeName(node.name.text)) {
      return true;
    }
    if (
      ts.isElementAccessExpression(node) &&
      ts.isStringLiteralLike(node.argumentExpression) &&
      gradeName(node.argumentExpression.text)
    ) {
      return true;
    }
    let carriesGrade = false;
    node.forEachChild((child) => {
      carriesGrade ||= expressionCarriesGrade(filename, child);
    });
    return carriesGrade;
  };

  let changed = true;
  while (changed) {
    changed = false;
    for (const [filename, sourceFile] of sourceFiles) {
      const taintedNames = taintedNamesByFile.get(filename)!;
      const markIdentifier = (identifier: ts.Identifier) => {
        if (!taintedNames.has(identifier.text)) {
          taintedNames.add(identifier.text);
          changed = true;
        }
      };
      const markBinding = (
        binding: ts.BindingName,
        inheritedGrade: boolean,
      ) => {
        if (ts.isIdentifier(binding)) {
          if (inheritedGrade || gradeName(binding.text)) {
            markIdentifier(binding);
          }
          return;
        }
        for (const element of binding.elements) {
          if (ts.isOmittedExpression(element)) continue;
          const propertyName = element.propertyName;
          const propertyCarriesGrade =
            (propertyName &&
              (ts.isIdentifier(propertyName) ||
                ts.isStringLiteralLike(propertyName)) &&
              gradeName(propertyName.text)) ||
            (!propertyName &&
              ts.isIdentifier(element.name) &&
              gradeName(element.name.text));
          markBinding(
            element.name,
            inheritedGrade || Boolean(propertyCarriesGrade),
          );
        }
      };
      const propagate = (node: ts.Node) => {
        if (ts.isVariableDeclaration(node)) {
          markBinding(
            node.name,
            expressionCarriesGrade(filename, node.initializer),
          );
        }
        if (ts.isParameter(node)) {
          markBinding(node.name, false);
        }
        node.forEachChild(propagate);
      };
      propagate(sourceFile);
    }
  }

  const functionClassifiesParameter = (
    definition: FunctionDefinition,
    parameterIndex: number,
    visiting: Set<string>,
  ): boolean => {
    const parameter = definition.node.parameters[parameterIndex];
    if (!parameter || !ts.isIdentifier(parameter.name)) return false;
    const parameterName = parameter.name.text;
    const visitKey = `${definition.filename}:${definition.node.pos}:${parameterIndex}`;
    if (visiting.has(visitKey)) return false;
    const nextVisiting = new Set(visiting).add(visitKey);
    const referencesParameter = (candidate: ts.Node | undefined): boolean => {
      if (!candidate) return false;
      if (ts.isIdentifier(candidate) && candidate.text === parameterName) {
        return true;
      }
      let found = false;
      candidate.forEachChild((child) => {
        found ||= referencesParameter(child);
      });
      return found;
    };
    let classified = false;
    const visit = (candidate: ts.Node) => {
      if (
        ts.isBinaryExpression(candidate) &&
        equalityOperators.includes(
          candidate.operatorToken.kind as (typeof equalityOperators)[number],
        ) &&
        (referencesParameter(candidate.left) ||
          referencesParameter(candidate.right))
      ) {
        const parameterSide = referencesParameter(candidate.left)
          ? candidate.left
          : candidate.right;
        const other =
          parameterSide === candidate.left ? candidate.right : candidate.left;
        classified ||=
          !ts.isTypeOfExpression(parameterSide) && !isAbsenceCheck(other);
      }
      if (
        ts.isElementAccessExpression(candidate) &&
        referencesParameter(candidate.argumentExpression)
      ) {
        classified = true;
      }
      if (
        ts.isCallExpression(candidate) &&
        ts.isPropertyAccessExpression(candidate.expression) &&
        classificationMethods.has(candidate.expression.name.text) &&
        (referencesParameter(candidate.expression.expression) ||
          candidate.arguments.some(referencesParameter))
      ) {
        classified = true;
      }
      if (ts.isCallExpression(candidate)) {
        const resolved = resolveFunctions(
          definition.filename,
          candidate.expression,
        );
        for (const nestedDefinition of resolved.definitions) {
          candidate.arguments.forEach((argument, index) => {
            if (
              referencesParameter(argument) &&
              functionClassifiesParameter(nestedDefinition, index, nextVisiting)
            ) {
              classified = true;
            }
          });
        }
      }
      if (!classified) candidate.forEachChild(visit);
    };
    visit(definition.node);
    return classified;
  };

  const findings: string[] = [];
  const findingKeys = new Set<string>();
  const addFinding = (
    filename: string,
    sourceFile: ts.SourceFile,
    node: ts.Node,
    kind: string,
  ) => {
    const line =
      sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line +
      1;
    const finding = `${filename}:${line}:${kind}`;
    if (!findingKeys.has(finding)) {
      findingKeys.add(finding);
      findings.push(finding);
    }
  };

  for (const [filename, sourceFile] of sourceFiles) {
    const inspect = (node: ts.Node) => {
      if (
        ts.isBinaryExpression(node) &&
        equalityOperators.includes(
          node.operatorToken.kind as (typeof equalityOperators)[number],
        ) &&
        (expressionCarriesGrade(filename, node.left) ||
          expressionCarriesGrade(filename, node.right))
      ) {
        const gradeSide = expressionCarriesGrade(filename, node.left)
          ? node.left
          : node.right;
        const otherSide = gradeSide === node.left ? node.right : node.left;
        if (!ts.isTypeOfExpression(gradeSide) && !isAbsenceCheck(otherSide)) {
          addFinding(filename, sourceFile, node, "literal-or-value comparison");
        }
      }
      if (
        ts.isSwitchStatement(node) &&
        expressionCarriesGrade(filename, node.expression)
      ) {
        addFinding(filename, sourceFile, node, "switch classifier");
      }
      if (
        ts.isElementAccessExpression(node) &&
        expressionCarriesGrade(filename, node.argumentExpression)
      ) {
        addFinding(filename, sourceFile, node, "grade-keyed map");
      }
      if (
        ts.isCallExpression(node) &&
        ts.isPropertyAccessExpression(node.expression)
      ) {
        const method = node.expression.name.text;
        if (
          classificationMethods.has(method) &&
          (expressionCarriesGrade(filename, node.expression.expression) ||
            node.arguments.some((argument) =>
              expressionCarriesGrade(filename, argument),
            ))
        ) {
          addFinding(filename, sourceFile, node, `${method} classifier`);
        }
      }
      if (ts.isCallExpression(node)) {
        const resolved = resolveFunctions(filename, node.expression);
        for (const definition of resolved.definitions) {
          definition.node.parameters.forEach((_parameter, index) => {
            const argument = node.arguments[index];
            if (
              argument &&
              expressionCarriesGrade(filename, argument) &&
              functionClassifiesParameter(definition, index, new Set())
            ) {
              addFinding(
                filename,
                sourceFile,
                node,
                resolved.imported
                  ? "imported helper classifier"
                  : "helper classifier",
              );
            }
          });
        }
      }
      node.forEachChild(inspect);
    };
    inspect(sourceFile);
  }
  return findings;
}

describe("decision-grade presentation", () => {
  it("renders a novel owner label as explicit unrecognized presentation", () => {
    expect(
      decisionGradePresentation.presentDecisionGradeLabel("future-owner-grade"),
    ).toEqual({
      classification: "unrecognized",
      ownerLabel: "future-owner-grade",
    });
  });

  it("exports no value-level vocabulary constants", () => {
    expect(Object.keys(decisionGradePresentation)).toEqual([
      "presentDecisionGradeLabel",
    ]);
  });

  it(
    "forbids sibling decision-grade classifiers and localization maps",
    () => {
      const allProduction = Object.fromEntries(
        productionSources(dashboardSourceRoot)
          .filter(
            (file) =>
              file !==
              path.join(import.meta.dirname, "decisionGradePresentation.ts"),
          )
          .map((file) => [
            path.relative(dashboardSourceRoot, file),
            fs.readFileSync(file, "utf8"),
          ]),
      );
      const production = decisionGradeRelevantSources(allProduction);
      const offenders = [
        ...Object.entries(production).flatMap(([relativePath, source]) =>
          source.includes("evaluatorVerdicts")
            ? [`${relativePath}: decision-grade localization map`]
            : [],
        ),
        ...decisionGradeBypassesAcrossSources(production),
      ];

      expect(offenders).toEqual([]);
    },
    30_000,
  );

  it("catches renamed and destructured aliases, maps, sets, and helper-hidden classifiers", () => {
    const adversarialSource = `
      const KNOWN = new Set(["APPROVE"]);
      const TONES = { APPROVE: "ok" };
      function hidden(value: string) { return KNOWN.has(value); }
      function classify(packet: { verdict: string }) {
        const ownerValue = packet.verdict;
        const grade = ownerValue;
        const { verdict: destructuredOwnerValue } = packet;
        return [
          grade === "APPROVE",
          TONES[ownerValue],
          hidden(ownerValue),
          destructuredOwnerValue === "REJECT",
        ];
      }
    `;

    expect(decisionGradeBypasses(adversarialSource)).toHaveLength(4);
  });

  it("catches decision-grade classification hidden behind an imported helper", () => {
    const findings = decisionGradeBypassesAcrossSources({
      "classify.ts": `
        export function importedClassifier(ownerValue: string) {
          return ownerValue === "APPROVE";
        }
      `,
      "consumer.ts": `
        import { importedClassifier } from "./classify";
        export function render(packet: { verdict: string }) {
          return importedClassifier(packet.verdict);
        }
      `,
    });

    expect(findings).toEqual(["consumer.ts:4:imported helper classifier"]);
  });

  it("catches an imported helper classifier reached through the dashboard alias", () => {
    const sources = {
      "features/consumer.ts": `
        import { importedClassifier } from "@/shared/lib/classify";
        export function render(packet: { verdict: string }) {
          return importedClassifier(packet.verdict);
        }
      `,
      "shared/lib/classify.ts": `
        export function importedClassifier(ownerValue: string) {
          return ownerValue === "APPROVE";
        }
      `,
    };

    expect(
      decisionGradeBypassesAcrossSources(decisionGradeRelevantSources(sources)),
    ).toEqual(["features/consumer.ts:4:imported helper classifier"]);
  });
});
