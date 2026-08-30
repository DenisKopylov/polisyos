#!/usr/bin/env python3
"""Validate the sound DS5 enforcement core."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from textwrap import dedent
from typing import Any, Literal, NamedTuple

import yaml

ATLAS_DIR = Path(__file__).resolve().parent
STATUS_CHECKER_PATH = ATLAS_DIR / "check_status_retirement_inventory.py"
DISPOSITION_CHECKER_PATH = ATLAS_DIR / "check_frontend_disposition_register.py"
AUTHORITY_SEMANTIC_COPY_REGISTRY_PATH = ATLAS_DIR / "authority-semantic-copy-registry.json"
AUTHORITY_SEMANTIC_COPY_SCHEMA_PATH = ATLAS_DIR / "authority-semantic-copy-registry.schema.json"
QUERY_CACHE_POLICY_REGISTER_PATH = ATLAS_DIR / "query-cache-policy-register.json"
QUERY_CACHE_POLICY_SCHEMA_PATH = ATLAS_DIR / "query-cache-policy-register.schema.json"
SLICE_SCOPE_OBLIGATIONS_PATH = ATLAS_DIR / "slice-scope-obligations.json"
SLICE_SCOPE_OBLIGATIONS_SCHEMA_PATH = ATLAS_DIR / "slice-scope-obligations.schema.json"
AUTHORITY_SEMANTIC_COPY_PATH = (
    "apps/runtime-dashboard/src/shared/ui/AuthoritySemanticCopy.ts"
)
GENERATED_RUNTIME_TYPES_PATH = ATLAS_DIR.parents[1] / "packages/runtime-api-client/types.ts"

_CAPABILITY_DISCOVERY_RENDER_PROBE = r"""
const fs = require("fs");
const nodePath = require("path");
const path = nodePath.posix;
const createRequire = require("module").createRequire;
const dashboardRequire = createRequire(
  nodePath.resolve(process.cwd(), "apps/runtime-dashboard/package.json"),
);
const ts = dashboardRequire("typescript");
const request = JSON.parse(fs.readFileSync(0, "utf8"));
const sources = new Map(Object.entries(request.sources));
const isProductionDashboardSource = sourcePath =>
  sourcePath.startsWith("apps/runtime-dashboard/src/")
  && /\.tsx?$/.test(sourcePath)
  && !/\.d\.ts$/.test(sourcePath)
  && !/(?:^|\/)(?:test|tests|__tests__|__mocks__)(?:\/|$)/.test(sourcePath)
  && !/\.(?:test|spec|stories|story)\.tsx?$/.test(sourcePath);
const resolveRelative = (fromPath, specifier) => {
  if (!specifier.startsWith(".")) return null;
  const base = path.normalize(path.join(path.dirname(fromPath), specifier));
  const candidates = [
    base, `${base}.ts`, `${base}.tsx`, `${base}/index.ts`, `${base}/index.tsx`,
  ];
  for (const candidate of candidates) {
    if (sources.has(candidate)) return candidate;
  }
  return null;
};
const resolveDashboardAlias = specifier => {
  if (!specifier.startsWith("@/")) return null;
  const base = path.normalize(`apps/runtime-dashboard/src/${specifier.slice(2)}`);
  const candidates = [
    base, `${base}.ts`, `${base}.tsx`, `${base}/index.ts`, `${base}/index.tsx`,
  ];
  for (const candidate of candidates) {
    if (sources.has(candidate)) return candidate;
  }
  return null;
};
const sourceFiles = new Map();
for (const [sourcePath, source] of sources) {
  sourceFiles.set(sourcePath, ts.createSourceFile(
    sourcePath, source, ts.ScriptTarget.Latest, true,
    sourcePath.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  ));
}
const staticEdges = (sourcePath, includeDashboardAliases = false) => {
  const edges = [];
  for (const statement of sourceFiles.get(sourcePath)?.statements ?? []) {
    if ((ts.isImportDeclaration(statement) || ts.isExportDeclaration(statement))
      && statement.moduleSpecifier && ts.isStringLiteral(statement.moduleSpecifier)) {
      const specifier = statement.moduleSpecifier.text;
      const resolved = resolveRelative(sourcePath, specifier)
        ?? (includeDashboardAliases ? resolveDashboardAlias(specifier) : null);
      if (resolved) edges.push(resolved);
    }
  }
  return edges;
};
const productionSourcePaths = [...sources.keys()].filter(isProductionDashboardSource);
const ownerRoots = productionSourcePaths.filter(sourcePath =>
  /(?:^|\/)CapabilityDiscovery[^/]*\.tsx?$/.test(sourcePath)
  || sourcePath.includes("/capabilityDiscovery/")
  || sourcePath === "apps/runtime-dashboard/src/api/hooks/useCapabilitySearch.ts"
);
const ownerRootSet = new Set(ownerRoots);
const consumerRoots = productionSourcePaths.filter(sourcePath =>
  staticEdges(sourcePath, true).some(targetPath => ownerRootSet.has(targetPath))
);
const roots = [...new Set([...ownerRoots, ...consumerRoots])];
const reachable = new Set(roots);
const queue = [...roots];
while (queue.length) {
  const sourcePath = queue.shift();
  for (const targetPath of staticEdges(sourcePath)) {
    if (!reachable.has(targetPath)) {
      reachable.add(targetPath);
      queue.push(targetPath);
    }
  }
}
const compilerOptions = {
  target: ts.ScriptTarget.ES2022,
  module: ts.ModuleKind.ESNext,
  moduleResolution: ts.ModuleResolutionKind.Bundler,
  jsx: ts.JsxEmit.ReactJSX,
  skipLibCheck: true,
  noEmit: true,
};
const compilerHost = ts.createCompilerHost(compilerOptions, true);
const defaultGetSourceFile = compilerHost.getSourceFile.bind(compilerHost);
const defaultFileExists = compilerHost.fileExists.bind(compilerHost);
const defaultReadFile = compilerHost.readFile.bind(compilerHost);
const defaultResolveModule = ts.resolveModuleName;
const processRoot = process.cwd().replaceAll("\\", "/");
const sourceKey = fileName => {
  const normalized = path.normalize(fileName.replaceAll("\\", "/"));
  if (sources.has(normalized)) return normalized;
  const relative = path.relative(processRoot, normalized);
  return sources.has(relative) ? relative : null;
};
compilerHost.getSourceFile = (fileName, languageVersion, onError, shouldCreateNew) => {
  const key = sourceKey(fileName);
  return key ? sourceFiles.get(key)
    : defaultGetSourceFile(fileName, languageVersion, onError, shouldCreateNew);
};
compilerHost.fileExists = fileName => Boolean(sourceKey(fileName)) || defaultFileExists(fileName);
compilerHost.readFile = fileName => {
  const key = sourceKey(fileName);
  return key ? sources.get(key) : defaultReadFile(fileName);
};
compilerHost.resolveModuleNames = (moduleNames, containingFile) => {
  const containingKey = sourceKey(containingFile) ?? containingFile.replaceAll("\\", "/");
  return moduleNames.map(specifier => {
    const resolved = resolveRelative(containingKey, specifier)
      ?? resolveDashboardAlias(specifier);
    if (resolved) {
      return {
        resolvedFileName: resolved,
        extension: resolved.endsWith(".tsx") ? ts.Extension.Tsx : ts.Extension.Ts,
        isExternalLibraryImport: false,
      };
    }
    return defaultResolveModule(
      specifier, containingFile, compilerOptions, compilerHost,
    ).resolvedModule;
  });
};
const program = ts.createProgram(
  [...new Set([...reachable, ...productionSourcePaths])].sort(),
  compilerOptions,
  compilerHost,
);
const typeChecker = program.getTypeChecker();
const moduleInfoByPath = new Map();
const hasModifier = (node, modifier) =>
  Boolean(node.modifiers?.some(item => item.kind === modifier));
for (const sourcePath of [...reachable].sort()) {
  const sourceFile = sourceFiles.get(sourcePath);
  const declarations = new Map();
  const declaredNames = new Set();
  const lexicalDeclarations = new Map();
  const imports = new Map();
  const exports = new Map();
  const starExports = [];
  function collect(node) {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
      const named = lexicalDeclarations.get(node.name.text) ?? [];
      named.push(node);
      lexicalDeclarations.set(node.name.text, named);
    }
    ts.forEachChild(node, collect);
  }
  collect(sourceFile);
  for (const statement of sourceFile.statements) {
    if (ts.isVariableStatement(statement)) {
      for (const declaration of statement.declarationList.declarations) {
        if (!ts.isIdentifier(declaration.name)) continue;
        declaredNames.add(declaration.name.text);
        if (declaration.initializer) {
          declarations.set(declaration.name.text, declaration.initializer);
        }
      }
    } else if ((ts.isFunctionDeclaration(statement) || ts.isClassDeclaration(statement))
      && statement.name) {
      declaredNames.add(statement.name.text);
    }
    if (ts.isImportDeclaration(statement) && ts.isStringLiteral(statement.moduleSpecifier)) {
      const resolved = resolveRelative(sourcePath, statement.moduleSpecifier.text);
      const importClause = statement.importClause;
      if (!importClause || importClause.isTypeOnly) continue;
      if (importClause.name) {
        imports.set(importClause.name.text, {
          kind: "binding", targetPath: resolved, exported: "default",
        });
      }
      const bindings = importClause.namedBindings;
      if (bindings && ts.isNamedImports(bindings)) {
        for (const element of bindings.elements) {
          if (element.isTypeOnly) continue;
          imports.set(element.name.text, {
            kind: "binding", targetPath: resolved,
            exported: element.propertyName?.text ?? element.name.text,
          });
        }
      } else if (bindings && ts.isNamespaceImport(bindings)) {
        imports.set(bindings.name.text, { kind: "namespace", targetPath: resolved });
      }
      continue;
    }
    if (ts.isVariableStatement(statement)
      && hasModifier(statement, ts.SyntaxKind.ExportKeyword)) {
      for (const declaration of statement.declarationList.declarations) {
        if (ts.isIdentifier(declaration.name)) {
          exports.set(declaration.name.text, { kind: "local", local: declaration.name.text });
        }
      }
      continue;
    }
    if (ts.isExportAssignment(statement) && !statement.isExportEquals) {
      exports.set("default", { kind: "expression", expression: statement.expression });
      continue;
    }
    if ((ts.isFunctionDeclaration(statement) || ts.isClassDeclaration(statement))
      && hasModifier(statement, ts.SyntaxKind.ExportKeyword)) {
      const exported = hasModifier(statement, ts.SyntaxKind.DefaultKeyword)
        ? "default" : statement.name?.text;
      if (exported) exports.set(exported, { kind: "runtime" });
      continue;
    }
    if (!ts.isExportDeclaration(statement) || statement.isTypeOnly) continue;
    const specifier = statement.moduleSpecifier && ts.isStringLiteral(statement.moduleSpecifier)
      ? statement.moduleSpecifier.text : null;
    const targetPath = specifier === null ? null : resolveRelative(sourcePath, specifier);
    if (!statement.exportClause) {
      starExports.push({ targetPath, specifier });
      continue;
    }
    if (ts.isNamedExports(statement.exportClause)) {
      for (const element of statement.exportClause.elements) {
        if (element.isTypeOnly) continue;
        const exported = element.name.text;
        const imported = element.propertyName?.text ?? element.name.text;
        exports.set(exported, specifier === null
          ? { kind: "local", local: imported }
          : { kind: "reexport", targetPath, exported: imported, specifier });
      }
    } else if (ts.isNamespaceExport(statement.exportClause)) {
      exports.set(statement.exportClause.name.text, { kind: "namespace", targetPath, specifier });
    }
  }
  moduleInfoByPath.set(sourcePath, {
    sourceFile, declarations, declaredNames, lexicalDeclarations, imports, exports, starExports,
  });
}
const outcome = (status, extras = {}) => ({ status, ...extras });
const unresolved = () => outcome("unresolved");
const missing = () => outcome("missing");
const runtime = () => outcome("runtime");
const expressionOutcome = (node, sourcePath) => outcome("expression", { node, sourcePath });
const unwrap = node => {
  while (node && (ts.isParenthesizedExpression(node) || ts.isAsExpression(node)
    || ts.isTypeAssertionExpression(node) || ts.isNonNullExpression(node)
    || ts.isSatisfiesExpression?.(node))) {
    node = node.expression;
  }
  return node;
};
const lexicalScope = node => {
  for (let current = node.parent; current; current = current.parent) {
    if (ts.isFunctionLike(current) || ts.isBlock(current) || ts.isSourceFile(current)) {
      return current;
    }
  }
  return null;
};
const ancestorDistance = (ancestor, node) => {
  let distance = 0;
  for (let current = node; current; current = current.parent) {
    if (current === ancestor) return distance;
    distance += 1;
  }
  return null;
};
const resolveLocal = (sourcePath, local, seen, referenceNode = null) => {
  const info = moduleInfoByPath.get(sourcePath);
  if (!info) return unresolved();
  let declaration = null;
  if (referenceNode) {
    let parameterDistance = Number.POSITIVE_INFINITY;
    let distance = 0;
    for (let current = referenceNode.parent; current; current = current.parent) {
      distance += 1;
      if (ts.isFunctionLike(current)
        && current.parameters.some(parameter => bindingContains(parameter.name, local))) {
        parameterDistance = distance;
        break;
      }
    }
    let bestDistance = Number.POSITIVE_INFINITY;
    for (const candidate of info.lexicalDeclarations.get(local) ?? []) {
      const scope = lexicalScope(candidate);
      const distance = scope ? ancestorDistance(scope, referenceNode) : null;
      if (distance !== null && distance < bestDistance && distance < parameterDistance) {
        declaration = candidate;
        bestDistance = distance;
      }
    }
    if (!declaration && parameterDistance < Number.POSITIVE_INFINITY) return runtime();
  } else if (info.declarations.has(local)) {
    declaration = { initializer: info.declarations.get(local), pos: -1 };
  }
  const token = `local:${sourcePath}:${local}:${declaration?.pos ?? "missing"}`;
  if (seen.has(token)) return unresolved();
  const nextSeen = new Set(seen);
  nextSeen.add(token);
  if (declaration?.initializer) {
    return resolveValue(declaration.initializer, sourcePath, nextSeen);
  }
  return info.declaredNames.has(local) ? runtime() : missing();
};
const resolveExport = (sourcePath, exported, seen) => {
  const token = `export:${sourcePath}:${exported}`;
  if (seen.has(token)) return unresolved();
  const nextSeen = new Set(seen);
  nextSeen.add(token);
  const info = moduleInfoByPath.get(sourcePath);
  if (!info) return unresolved();
  const direct = info.exports.get(exported);
  if (direct) {
    if (direct.kind === "expression") {
      return resolveValue(direct.expression, sourcePath, nextSeen);
    }
    if (direct.kind === "local") {
      const resolved = resolveLocal(sourcePath, direct.local, nextSeen);
      return resolved.status === "missing" ? unresolved() : resolved;
    }
    if (direct.kind === "reexport") {
      if (!direct.targetPath) return unresolved();
      const resolved = resolveExport(direct.targetPath, direct.exported, nextSeen);
      return resolved.status === "missing" ? unresolved() : resolved;
    }
    if (direct.kind === "namespace") {
      return direct.targetPath
        ? outcome("namespace", { targetPath: direct.targetPath }) : unresolved();
    }
    return runtime();
  }
  if (exported === "default") return missing();
  const candidates = [];
  let sawUnresolved = false;
  for (const star of info.starExports) {
    if (!star.targetPath) {
      sawUnresolved = true;
      continue;
    }
    const resolved = resolveExport(star.targetPath, exported, nextSeen);
    if (resolved.status === "unresolved") sawUnresolved = true;
    else if (resolved.status !== "missing") candidates.push(resolved);
  }
  if (candidates.length > 1) return unresolved();
  if (candidates.length === 1) return candidates[0];
  return sawUnresolved ? unresolved() : missing();
};
const bindingContains = (binding, name) => {
  if (ts.isIdentifier(binding)) return binding.text === name;
  if (ts.isObjectBindingPattern(binding) || ts.isArrayBindingPattern(binding)) {
    return binding.elements.some(element =>
      ts.isBindingElement(element) && bindingContains(element.name, name));
  }
  return false;
};
function resolveValue(node, sourcePath, seen = new Set()) {
  node = unwrap(node);
  if (!node) return runtime();
  if (ts.isIdentifier(node)) {
    const local = resolveLocal(sourcePath, node.text, seen, node);
    if (local.status !== "missing") return local;
    const binding = moduleInfoByPath.get(sourcePath)?.imports.get(node.text);
    if (!binding) return runtime();
    if (!binding.targetPath) return unresolved();
    if (binding.kind === "namespace") {
      return outcome("namespace", { targetPath: binding.targetPath });
    }
    const resolved = resolveExport(binding.targetPath, binding.exported, seen);
    return resolved.status === "missing" ? unresolved() : resolved;
  }
  if (ts.isPropertyAccessExpression(node)) {
    const base = resolveValue(node.expression, sourcePath, seen);
    if (base.status === "unresolved") return base;
    if (base.status === "namespace") {
      const resolved = resolveExport(base.targetPath, node.name.text, seen);
      return resolved.status === "missing" ? unresolved() : resolved;
    }
    if (base.status === "expression") {
      const value = unwrap(base.node);
      if (value && ts.isObjectLiteralExpression(value)) {
        for (const property of value.properties) {
          if (!ts.isPropertyAssignment(property)) continue;
          const name = ts.isIdentifier(property.name) || ts.isStringLiteralLike(property.name)
            ? property.name.text : null;
          if (name === node.name.text) {
            return resolveValue(property.initializer, base.sourcePath, seen);
          }
        }
        return unresolved();
      }
    }
    return runtime();
  }
  if (ts.isElementAccessExpression(node)) {
    const key = stringValue(node.argumentExpression, sourcePath, seen);
    if (key.status === "unresolved") return key;
    if (key.status !== "literal") return runtime();
    const base = resolveValue(node.expression, sourcePath, seen);
    if (base.status === "unresolved") return base;
    if (base.status === "namespace") {
      const resolved = resolveExport(base.targetPath, key.value, seen);
      return resolved.status === "missing" ? unresolved() : resolved;
    }
    if (base.status === "expression") {
      const value = unwrap(base.node);
      if (value && ts.isObjectLiteralExpression(value)) {
        for (const property of value.properties) {
          if (!ts.isPropertyAssignment(property)) continue;
          const name = ts.isIdentifier(property.name) || ts.isStringLiteralLike(property.name)
            ? property.name.text : null;
          if (name === key.value) {
            return resolveValue(property.initializer, base.sourcePath, seen);
          }
        }
        return unresolved();
      }
    }
    return runtime();
  }
  return expressionOutcome(node, sourcePath);
}
function stringValue(node, sourcePath, seen = new Set()) {
  const resolved = resolveValue(node, sourcePath, seen);
  if (resolved.status !== "expression") return resolved;
  const value = unwrap(resolved.node);
  if (value && ts.isStringLiteralLike(value)) {
    return outcome("literal", { value: value.text });
  }
  return runtime();
}
const isSemanticPostureField = name =>
  /^(?:discovery|execution|authority)(?:_result|_posture)?$/.test(name);
const semanticRowType = (type, seen = new Set()) => {
  if (!type || seen.has(type.id)) return false;
  const nextSeen = new Set(seen);
  nextSeen.add(type.id);
  if (type.isUnionOrIntersection?.()) {
    return type.types.some(member => semanticRowType(member, nextSeen));
  }
  const names = new Set(typeChecker.getPropertiesOfType(type).map(property => property.name));
  return names.has("capability_ref") || names.has("resource_kind")
    || [...names].some(isSemanticPostureField);
};
const nodeHasSemanticRowType = node => {
  try {
    return semanticRowType(typeChecker.getTypeAtLocation(node));
  } catch {
    return false;
  }
};
const capabilityManifestType = (type, seen = new Set()) => {
  if (!type || seen.has(type.id)) return false;
  const nextSeen = new Set(seen);
  nextSeen.add(type.id);
  if (type.isUnionOrIntersection?.()) {
    return type.types.some(member => capabilityManifestType(member, nextSeen));
  }
  let properties;
  try {
    properties = new Set(
      typeChecker.getPropertiesOfType(typeChecker.getApparentType(type))
        .map(property => property.name),
    );
  } catch {
    return false;
  }
  if (!properties.has("features")) return false;
  const ownerMarkers = [
    "constraints", "runtime_api_version", "supported_execution_profiles",
    "default_execution_profile", "worker_backend", "state_store_backend",
  ];
  return ownerMarkers.filter(name => properties.has(name)).length >= 2;
};
const nodeHasCapabilityManifestType = node => {
  try {
    return capabilityManifestType(typeChecker.getTypeAtLocation(node));
  } catch {
    return false;
  }
};
const isTypeOnlyUse = node => {
  for (let current = node.parent; current; current = current.parent) {
    if (ts.isTypeNode(current)) return true;
    if (ts.isStatement(current) || ts.isSourceFile(current)) return false;
  }
  return false;
};
const collectionHasSemanticRows = node => {
  try {
    const collectionType = typeChecker.getTypeAtLocation(node);
    const elementType = typeChecker.getIndexTypeOfType(collectionType, ts.IndexKind.Number);
    return semanticRowType(elementType);
  } catch {
    return false;
  }
};
const symbolDeclaration = node => {
  try {
    const symbol = typeChecker.getSymbolAtLocation(node);
    return symbol?.valueDeclaration ?? symbol?.declarations?.[0] ?? null;
  } catch {
    return null;
  }
};
const resultCollectionOrigin = (node, seen = new Set()) => {
  node = unwrap(node);
  if (!node) return false;
  const token = `collection:${node.getSourceFile().fileName}:${node.pos}:${node.end}`;
  if (seen.has(token)) return false;
  const nextSeen = new Set(seen);
  nextSeen.add(token);
  if (collectionHasSemanticRows(node)) return true;
  if (ts.isPropertyAccessExpression(node) && node.name.text === "results") return true;
  if (ts.isElementAccessExpression(node)
    && ts.isStringLiteralLike(node.argumentExpression)
    && node.argumentExpression.text === "results") return true;
  if (ts.isIdentifier(node)) {
    const declaration = symbolDeclaration(node);
    if (declaration && ts.isVariableDeclaration(declaration) && declaration.initializer) {
      return resultCollectionOrigin(declaration.initializer, nextSeen);
    }
  }
  return false;
};
const callbackParameterHasRowOrigin = parameter => {
  const callback = parameter.parent;
  const call = callback.parent;
  if (!ts.isCallExpression(call) || !call.arguments.includes(callback)) return false;
  const callee = unwrap(call.expression);
  if (!callee || (!ts.isPropertyAccessExpression(callee)
    && !ts.isElementAccessExpression(callee))) return false;
  return resultCollectionOrigin(callee.expression);
};
const bindingPattern = declaration => {
  if (!declaration || !ts.isBindingElement(declaration)) return null;
  let current = declaration.parent;
  while (ts.isBindingElement(current.parent)) current = current.parent.parent;
  return ts.isObjectBindingPattern(current) || ts.isArrayBindingPattern(current)
    ? current : null;
};
const bindingPatternHasRowOrigin = pattern => {
  if (nodeHasSemanticRowType(pattern)) return true;
  const owner = pattern.parent;
  if (ts.isParameter(owner)) return callbackParameterHasRowOrigin(owner);
  if (ts.isVariableDeclaration(owner) && owner.initializer) {
    return semanticRowOrigin(owner.initializer);
  }
  return false;
};
const bindingFieldName = declaration => {
  if (!declaration || !ts.isBindingElement(declaration)) return null;
  if (declaration.propertyName
    && (ts.isIdentifier(declaration.propertyName)
      || ts.isStringLiteralLike(declaration.propertyName))) {
    return declaration.propertyName.text;
  }
  return ts.isIdentifier(declaration.name) ? declaration.name.text : null;
};
function semanticRowOrigin(node, seen = new Set()) {
  node = unwrap(node);
  if (!node) return false;
  const token = `row:${node.getSourceFile().fileName}:${node.pos}:${node.end}`;
  if (seen.has(token)) return false;
  const nextSeen = new Set(seen);
  nextSeen.add(token);
  if (nodeHasSemanticRowType(node)) return true;
  if (ts.isIdentifier(node)) {
    const declaration = symbolDeclaration(node);
    if (declaration && ts.isVariableDeclaration(declaration) && declaration.initializer) {
      return semanticRowOrigin(declaration.initializer, nextSeen);
    }
    if (declaration && ts.isParameter(declaration)) {
      return callbackParameterHasRowOrigin(declaration);
    }
    const pattern = bindingPattern(declaration);
    if (pattern) return bindingPatternHasRowOrigin(pattern);
  }
  return false;
}
const violations = [];
for (const sourcePath of [...reachable].sort()) {
  if (/\/(?:workspaceConfig|surfaceRegistry)\.[^/]+$/i.test(sourcePath)) continue;
  const sourceFile = sourceFiles.get(sourcePath);
  const semanticField = (node, seen = new Set(), fieldPath = sourcePath) => {
    node = unwrap(node);
    if (!node) return outcome("runtime");
    if (ts.isPropertyAccessExpression(node)) {
      return outcome("field", {
        name: node.name.text,
        contextualId: semanticRowOrigin(node.expression),
      });
    }
    if (ts.isElementAccessExpression(node)) {
      const name = stringValue(node.argumentExpression, fieldPath, seen);
      if (name.status !== "literal") return name;
      return outcome("field", {
        name: name.value,
        contextualId: semanticRowOrigin(node.expression),
      });
    }
    if (ts.isIdentifier(node)) {
      const declaration = symbolDeclaration(node);
      const pattern = bindingPattern(declaration);
      const destructuredField = bindingFieldName(declaration);
      if (pattern && destructuredField && bindingPatternHasRowOrigin(pattern)) {
        return outcome("field", {
          name: destructuredField,
          contextualId: destructuredField === "id",
        });
      }
      if (declaration && ts.isVariableDeclaration(declaration) && declaration.initializer) {
        const aliasedField = semanticField(declaration.initializer, seen, fieldPath);
        if (aliasedField.status === "field") return aliasedField;
      }
      const token = `field:${fieldPath}:${node.text}`;
      if (seen.has(token)) return unresolved();
      const nextSeen = new Set(seen);
      nextSeen.add(token);
      const resolved = resolveValue(node, fieldPath, nextSeen);
      if (resolved.status === "expression"
        && (resolved.node !== node || resolved.sourcePath !== fieldPath)) {
        return semanticField(resolved.node, nextSeen, resolved.sourcePath);
      }
    }
    return runtime();
  };
  const propertyName = (property, propertyPath = sourcePath) => {
    if (ts.isIdentifier(property.name) || ts.isStringLiteralLike(property.name)) {
      return outcome("literal", { value: property.name.text });
    }
    if (ts.isComputedPropertyName(property.name)) {
      return stringValue(property.name.expression, propertyPath);
    }
    return runtime();
  };
  const semanticObject = (node, seen = new Set(), objectPath = sourcePath) => {
    const resolved = resolveValue(node, objectPath, seen);
    if (resolved.status !== "expression") {
      return { status: resolved.status, names: new Set() };
    }
    const value = unwrap(resolved.node);
    if (!value || !ts.isObjectLiteralExpression(value)) {
      return { status: "runtime", names: new Set() };
    }
    const names = new Set();
    let status = "expression";
    for (const property of value.properties.filter(ts.isPropertyAssignment)) {
      const name = propertyName(property, resolved.sourcePath);
      if (name.status === "literal") names.add(name.value);
      else if (name.status === "unresolved") status = "unresolved";
    }
    return { status, names };
  };
  const record = (node, kind) => {
    const position = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
    violations.push({ path: sourcePath, line: position.line + 1, kind });
  };
  function inspect(node) {
    if (ts.isObjectLiteralExpression(node)) {
      const properties = node.properties.filter(ts.isPropertyAssignment);
      const nameResults = properties.map(property => propertyName(property));
      const names = new Set(nameResults.filter(item => item.status === "literal")
        .map(item => item.value));
      const rowContext = ["capability_ref", "resource_kind", "candidate_ref", "adapter_id"]
        .some(name => names.has(name));
      for (const property of properties) {
        const name = propertyName(property);
        if (name.status !== "literal") {
          if (name.status === "unresolved" && rowContext) {
            record(property, "unresolved_semantic_value");
          }
          continue;
        }
        const semantic = name.value === "capability_ref" || name.value === "resource_kind"
          || name.value === "adapter_id" || name.value === "candidate_ref"
          || (name.value === "kind" && names.has("capability_ref"))
          || (name.value === "id" && rowContext);
        if (!semantic) continue;
        const value = stringValue(property.initializer, sourcePath);
        if (value.status === "unresolved") {
          record(property, "unresolved_semantic_value");
        } else if (value.status === "literal") {
          if (name.value === "capability_ref" || name.value === "resource_kind") {
            record(property, `authored_${name.value}`);
          } else if (name.value === "kind") {
            record(property, "authored_resource_kind");
          } else {
            record(property, "authored_adapter_id");
          }
        }
      }
    }
    if (ts.isArrayLiteralExpression(node) && node.elements.some(element => {
      const item = semanticObject(element);
      if (item.status === "unresolved") {
        record(node, "unresolved_semantic_value");
        return false;
      }
      return item.names.has("capability_ref") || item.names.has("resource_kind")
        || item.names.has("candidate_ref") || item.names.has("adapter_id");
    })) record(node, "authored_result_array");
    if (ts.isBinaryExpression(node) && [
      ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.EqualsEqualsEqualsToken,
      ts.SyntaxKind.ExclamationEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken,
    ].includes(node.operatorToken.kind)) {
      const pairs = [
        [semanticField(node.left), stringValue(node.right, sourcePath)],
        [semanticField(node.right), stringValue(node.left, sourcePath)],
      ];
      for (const [field, value] of pairs) {
        if (field.status !== "field") continue;
        const semantic = field.name === "capability_ref" || field.name === "resource_kind"
          || (field.name === "kind" && field.contextualId) || field.name === "adapter_id"
          || field.name === "candidate_ref" || (field.name === "id" && field.contextualId);
        if (!semantic) continue;
        if (value.status === "unresolved") {
          record(node, "unresolved_semantic_value");
          break;
        }
        if (value.status === "literal") {
          record(node, "literal_result_branch");
          break;
        }
      }
    }
    if (ts.isCaseClause(node)) {
      const switchStatement = node.parent?.parent;
      const field = switchStatement && ts.isSwitchStatement(switchStatement)
        ? semanticField(switchStatement.expression) : runtime();
      const value = stringValue(node.expression, sourcePath);
      const semantic = field.status === "field" && (
        field.name === "capability_ref" || field.name === "resource_kind"
        || (field.name === "kind" && field.contextualId) || field.name === "adapter_id"
        || field.name === "candidate_ref" || (field.name === "id" && field.contextualId)
      );
      if (semantic && value.status === "unresolved") {
        record(node, "unresolved_semantic_value");
      } else if (semantic && value.status === "literal") {
        record(node, "literal_result_branch");
      }
    }
    ts.forEachChild(node, inspect);
  }
  inspect(sourceFile);
}
for (const sourcePath of [...productionSourcePaths].sort()) {
  const sourceFile = sourceFiles.get(sourcePath);
  const recordLegacyRead = (node, syntax) => {
    const position = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
    violations.push({
      path: sourcePath,
      line: position.line + 1,
      kind: `legacy_manifest_features_read_${syntax}`,
    });
  };
  const bindingFieldName = element => {
    if (element.propertyName
      && (ts.isIdentifier(element.propertyName)
        || ts.isStringLiteralLike(element.propertyName))) {
      return element.propertyName.text;
    }
    return ts.isIdentifier(element.name) ? element.name.text : null;
  };
  const objectPatternReadsFeatures = pattern => pattern.elements.some(element =>
    ts.isBindingElement(element) && bindingFieldName(element) === "features"
  );
  const assignmentPatternReadsFeatures = expression => {
    const pattern = unwrap(expression);
    if (!pattern || !ts.isObjectLiteralExpression(pattern)) return false;
    return pattern.properties.some(property => {
      if (ts.isShorthandPropertyAssignment(property)) {
        return property.name.text === "features";
      }
      if (!ts.isPropertyAssignment(property)) return false;
      return (ts.isIdentifier(property.name) || ts.isStringLiteralLike(property.name))
        && property.name.text === "features";
    });
  };
  const parameterIsExecutable = parameter => Boolean(parameter.parent?.body);
  function inspectLegacyManifestReads(node) {
    if (!isTypeOnlyUse(node) && ts.isPropertyAccessExpression(node)
      && node.name.text === "features"
      && nodeHasCapabilityManifestType(node.expression)) {
      recordLegacyRead(node, "property_access");
    }
    if (!isTypeOnlyUse(node) && ts.isElementAccessExpression(node)
      && ts.isStringLiteralLike(node.argumentExpression)
      && node.argumentExpression.text === "features"
      && nodeHasCapabilityManifestType(node.expression)) {
      recordLegacyRead(node, "element_access");
    }
    if (ts.isVariableDeclaration(node) && ts.isObjectBindingPattern(node.name)
      && node.initializer && objectPatternReadsFeatures(node.name)
      && nodeHasCapabilityManifestType(node.initializer)) {
      recordLegacyRead(node.name, "destructure");
    }
    if (ts.isParameter(node) && parameterIsExecutable(node)
      && ts.isObjectBindingPattern(node.name)
      && objectPatternReadsFeatures(node.name)
      && nodeHasCapabilityManifestType(node)) {
      recordLegacyRead(node.name, "destructure");
    }
    if (ts.isBinaryExpression(node)
      && node.operatorToken.kind === ts.SyntaxKind.EqualsToken
      && assignmentPatternReadsFeatures(node.left)
      && nodeHasCapabilityManifestType(node.right)) {
      recordLegacyRead(node.left, "destructure");
    }
    ts.forEachChild(node, inspectLegacyManifestReads);
  }
  inspectLegacyManifestReads(sourceFile);
}
process.stdout.write(JSON.stringify(violations));
"""

_SEMANTIC_COPY_DECLARATION_PROBE = (
    r"""
const fs = require("fs");
const ts = require("typescript");
const request = JSON.parse(fs.readFileSync(0, "utf8"));
const options = { target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.ESNext,
  moduleResolution: ts.ModuleResolutionKind.Bundler, skipLibCheck: true, noEmit: true };
const overrides = new Map(Object.entries(request.overrides));
const host = ts.createCompilerHost(options, true);
const readFile = host.readFile.bind(host);
const fileExists = host.fileExists.bind(host);
host.readFile = path => overrides.get(path) ?? readFile(path);
host.fileExists = path => overrides.has(path) || fileExists(path);
const program = ts.createProgram([request.issuerPath], options, host);
const checker = program.getTypeChecker();
const issuer = program.getSourceFile(request.issuerPath);
const file = node => node.getSourceFile().fileName;
const sameFile = (node, path) => Boolean(node) && file(node) === path;
""" "const statement = (name, guard) => issuer.statements.find("
"node => guard(node) && node.name?.text === name);" """
const typeAlias = name => statement(name, ts.isTypeAliasDeclaration);
const functionDecl = name => statement(name, ts.isFunctionDeclaration);
const variableDecl = name => {
  for (const statement of issuer.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (ts.isIdentifier(declaration.name) && declaration.name.text === name) return declaration;
    }
  }
};
const moduleSymbol = checker.getSymbolAtLocation(issuer);
""" "const exports = moduleSymbol ? checker.getExportsOfModule(moduleSymbol)"
".map(symbol => symbol.getName()).sort() : [];" """
const brand = variableDecl("authoritySemanticCopyBrand");
const store = variableDecl("issuedAuthoritySemanticCopies");
const issuerFactory = functionDecl("issueAuthoritySemanticCopy");
const factory = functionDecl("presentMayNotUseFor");
const closedFactory = functionDecl("presentSemanticCopy");
const tokenAlias = typeAlias("MayNotUseForOwnerToken");
const returnSymbol = factory?.type && ts.isTypeReferenceNode(factory.type)
  ? checker.getSymbolAtLocation(factory.type.typeName) : undefined;
""" "const parameterSymbol = factory?.parameters[0]?.type && "
"ts.isTypeReferenceNode(factory.parameters[0].type)" """
  ? checker.getSymbolAtLocation(factory.parameters[0].type.typeName) : undefined;
const tokenObject = tokenAlias?.type && ts.isIndexedAccessTypeNode(tokenAlias.type)
""" "  && ts.isIndexedAccessTypeNode(tokenAlias.type.objectType) ? "
"tokenAlias.type.objectType.objectType : undefined;" """
let generatedSymbol = tokenObject && ts.isTypeReferenceNode(tokenObject)
  ? checker.getSymbolAtLocation(tokenObject.typeName) : undefined;
""" "if (generatedSymbol && generatedSymbol.flags & ts.SymbolFlags.Alias) "
"generatedSymbol = checker.getAliasedSymbol(generatedSymbol);" """
const generatedType = tokenObject ? checker.getTypeAtLocation(tokenObject) : undefined;
""" "const field = generatedType ? checker.getPropertyOfType(generatedType, "
"\"may_not_use_for\") : undefined;" """
const storeSymbol = store ? checker.getSymbolAtLocation(store.name) : undefined;
const localDeclaration = (functionNode, name) => {
  let found;
  function visit(node) {
""" "    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && "
"node.name.text === name) found = node;" """
    ts.forEachChild(node, visit);
  }
  if (functionNode) ts.forEachChild(functionNode.body, visit);
  return found;
};
const issued = localDeclaration(issuerFactory, "issued");
const issuedSymbol = issued ? checker.getSymbolAtLocation(issued.name) : undefined;
""" "const sameIssued = node => Boolean(ts.isIdentifier(node) && "
"checker.getSymbolAtLocation(node) === issuedSymbol);" """
const standardMember = (call, expectedName) => {
  if (!ts.isCallExpression(call) || !ts.isPropertyAccessExpression(call.expression)) return false;
  const member = checker.getSymbolAtLocation(call.expression.name);
""" "  return Boolean(member?.getName() === expectedName && "
"member.valueDeclaration && file(member.valueDeclaration).includes("
"\"/typescript/lib/\"));" """
};
const initializedFrozen = Boolean(issued && standardMember(issued.initializer, "freeze"));
let addedIssued = false;
let returnedIssued = false;
let reassignedIssued = false;
let returnCount = 0;
function inspectConstruction(node) {
  if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)) {
    const receiver = checker.getSymbolAtLocation(node.expression.expression);
""" "    if (receiver === storeSymbol && standardMember(node, \"add\") && "
"sameIssued(node.arguments[0])) addedIssued = true;" """
  }
  if (ts.isReturnStatement(node)) {
    returnCount += 1;
    if (sameIssued(node.expression)) returnedIssued = true;
  }
""" "  if (ts.isBinaryExpression(node) && node.operatorToken.kind === "
"ts.SyntaxKind.EqualsToken && sameIssued(node.left)) reassignedIssued = true;" """
  ts.forEachChild(node, inspectConstruction);
}
if (issuerFactory) inspectConstruction(issuerFactory.body);
""" "const canonicalConstruction = initializedFrozen && addedIssued && "
"returnedIssued && returnCount === 1 && !reassignedIssued;" """
""" "const aliasDeclarations = symbol => symbol ? symbol.declarations.map("
"declaration => file(declaration)).sort() : [];" """
process.stdout.write(JSON.stringify({
""" "  compilerDiagnostics: ts.getPreEmitDiagnostics(program).filter("
"diagnostic => diagnostic.file?.fileName === request.issuerPath)"
".map(diagnostic => diagnostic.code)," """
  exports,
""" "  brandPrivateUnique: Boolean(brand && brand.type && "
"ts.isTypeOperatorNode(brand.type) && brand.type.operator === "
"ts.SyntaxKind.UniqueKeyword && !issuer.statements.some(node => node === "
"brand.parent?.parent && ts.getCombinedModifierFlags(node) & "
"ts.ModifierFlags.Export))," """
  brandPath: brand ? file(brand) : null,
""" "  storePrivate: Boolean(store && !issuer.statements.some(node => "
"node === store.parent?.parent && ts.getCombinedModifierFlags(node) & "
"ts.ModifierFlags.Export))," """
  canonicalConstruction,
  factoryReturnDeclarations: aliasDeclarations(returnSymbol),
  factoryParameterDeclarations: aliasDeclarations(parameterSymbol),
  generatedDeclarations: aliasDeclarations(generatedSymbol),
  generatedFieldDeclarations: aliasDeclarations(field),
}));
"""
)

_SPEC = importlib.util.spec_from_file_location("status_retirement_checker", STATUS_CHECKER_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to import status checker from {STATUS_CHECKER_PATH}")
status_checker = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(status_checker)

_DISPOSITION_SPEC = importlib.util.spec_from_file_location(
    "atlas_enforcement_disposition_checker", DISPOSITION_CHECKER_PATH
)
if _DISPOSITION_SPEC is None or _DISPOSITION_SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f"Unable to import disposition checker from {DISPOSITION_CHECKER_PATH}")
disposition_checker = importlib.util.module_from_spec(_DISPOSITION_SPEC)
_DISPOSITION_SPEC.loader.exec_module(disposition_checker)

AuthorityEscapeConstruct = Literal[
    "as_assertion",
    "type_assertion",
    "explicit_any",
    "ts_ignore",
    "ts_expect_error",
    "ts_nocheck",
    "satisfies",
]

C09A_AUTHZ_DECISION_PATHS: tuple[str, ...] = (
    "apps/runtime-dashboard/src/app/layout/Header.tsx",
    "apps/runtime-dashboard/src/app/layout/Sidebar.tsx",
    "apps/runtime-dashboard/src/app/routes/WorkspaceBoundary.tsx",
)

C09A_AUTHZ_DIRECT_SYNTAX_RESIDUAL = (
    "canonical inline calls and one-step local decision aliases, predicate aliases, "
    "or object destructures only; arbitrary assignment, return, closure, callback, "
    "parameter, and interprocedural authorization value-flow remains not_established"
)

# C09b closes the declaration-resolved direct-default remainder. Any later
# canonical decision importer that reintroduces a bounded unsafe default is
# therefore unclassified and fails the generic gate.
C09B_DEFERRED_AUTHZ_DEFAULTS: tuple[tuple[str, str, str], ...] = ()


class AuthorityEscapeExemption(NamedTuple):
    """Exact, owned exception to the bounded authority-path syntax rule."""

    exemption_id: str
    path: str
    line: int
    column: int
    construct: AuthorityEscapeConstruct
    target: str
    site_sha256: str
    owner: str
    reason: str


_ISSUER_ERASURE_REASON = (
    "Runtime-erased generated owner inspection is narrowed only after local "
    "shape or membership checks; the assertion neither targets nor issues a brand."
)
_RUNTIME_NEGATIVE_REASON = (
    "The runtime negative deliberately models a JavaScript value after type erasure; "
    "the exact assertion is confined to rejection or novelty behavior."
)
_STATIC_OWNERSHIP_REASON = (
    "Literal preservation serves the static primitive-ownership census only; "
    "the table neither targets an authority brand nor reaches a presentation sink."
)


def _escape(
    exemption_id: str,
    path: str,
    line: int,
    column: int,
    construct: AuthorityEscapeConstruct,
    target: str,
    site_sha256: str,
    owner: str,
    reason: str,
) -> AuthorityEscapeExemption:
    return AuthorityEscapeExemption(
        exemption_id,
        path,
        line,
        column,
        construct,
        target,
        site_sha256,
        owner,
        reason,
    )


AUTHORITY_ESCAPE_EXEMPTIONS: tuple[AuthorityEscapeExemption, ...] = (
    _escape(
        "issuer-authority-badge-owner-label-array",
        "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
        137,
        7,
        "as_assertion",
        "readonly unknown[] | undefined",
        "sha256:8cb81971c08e14f4faa1bf68d31d3353f7892f41d5f8a1611c0fee5de0a5cd71",
        "DS5",
        _ISSUER_ERASURE_REASON,
    ),
    _escape(
        "issuer-authority-badge-runtime-label",
        "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
        145,
        23,
        "as_assertion",
        "{\n    authority?: unknown;\n    label?: unknown;\n    state?: unknown;\n  }",
        "sha256:2c5ad16863a03dd93cf0dc0a5d4f6a3f0bf9a1d6b86019194e41b721a8e22b13",
        "DS5",
        _ISSUER_ERASURE_REASON,
    ),
    _escape(
        "issuer-authority-badge-exhaustive-index",
        "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
        175,
        26,
        "as_assertion",
        "keyof typeof projectionStateTones",
        "sha256:3bafeebe683860825b3c6900970495e308bfdd096155ced0ad817888dcf015b8",
        "DS5",
        "Object.hasOwn proves the runtime key is present in the compile-time "
        "exhaustive generated-owner tone map; no brand is asserted.",
    ),
    _escape(
        "issuer-governed-purpose-payload-shape",
        "packages/atlas-ui/src/primitives/evidenceTypes.ts",
        90,
        10,
        "as_assertion",
        "{ fixture_authority?: unknown }",
        "sha256:adf83ddb012dfaea816f5dc1d1ad864941d305a85f2722cb4cce4a7d2fe6f003",
        "DS5",
        _ISSUER_ERASURE_REASON,
    ),
    _escape(
        "issuer-governed-purpose-fixture-payload",
        "packages/atlas-ui/src/primitives/evidenceTypes.ts",
        104,
        35,
        "as_assertion",
        "LegacyProvingGroundPayload",
        "sha256:65f9c1172517063f1bc66597fba513ec29661bfdc4d2cd060bb6b7b19a8fbea0",
        "DS5",
        "The discriminator and canonical fixture marker are checked immediately "
        "before the generated payload is passed to the private fixture issuer.",
    ),
    _escape(
        "test-authority-badge-forged-presentation",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        78,
        21,
        "as_assertion",
        "const",
        "sha256:23fa1dbe16420294c9df35fd9277adf24fbfee983aa605360b0e32a864fddadd",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "evidence-link-owned-data-attributes",
        "packages/atlas-ui/src/primitives/EvidenceLink.tsx",
        51,
        18,
        "as_assertion",
        "const",
        "sha256:911d06047264c166eb73a1ae6080b97cd94221abfa62517b76df4b68b775fb7b",
        "team-design",
        "Literal preservation is confined to owned DOM data attributes; it neither "
        "targets an authority brand nor issues authority presentation.",
    ),
    _escape(
        "test-evidence-link-owned-anchor-props",
        "packages/atlas-ui/tests/EvidenceLink.test.tsx",
        61,
        11,
        "ts_expect_error",
        "@ts-expect-error",
        "sha256:571f28ec0ed9f481943dc9e7ac0fbb2a8106e73c7eafc84ae8048e994b42829a",
        "team-design",
        "Compile-only negative proves the evidence primitive rejects an unowned DOM "
        "escape hatch; the directive does not forge a branded authority value.",
    ),
    _escape(
        "test-authority-badge-forged-tone",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        79,
        13,
        "as_assertion",
        "const",
        "sha256:fb976df9fefedeca7c78cf7511d57dfa1a4f4d7e5ea9d23923c1fb5cafee2c81",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-authority-badge-malformed-label-outer",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        81,
        23,
        "as_assertion",
        "RunOperatorProjectionStateLabel",
        "sha256:17a143ca3b81a016acfe638b2cc49458162967811a487f4f4897f16cf9f75a09",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-authority-badge-malformed-label-inner",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        81,
        23,
        "as_assertion",
        "unknown",
        "sha256:698a79719f7d1d67eb994f4cef6eb0356f9c198712c3951242889986d4b88a9d",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-authority-badge-malformed-owner",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        86,
        28,
        "as_assertion",
        "RunOperatorDiagnostic",
        "sha256:3a1847c542b8eff50d7fccda92b5f71ccd15e3fd10bb284ebc3268c4eb886a1a",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-authority-badge-novel-label-outer",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        108,
        23,
        "as_assertion",
        "RunOperatorProjectionStateLabel",
        "sha256:8e2d0d81a51b9bef0a4b149de3b00b00788fb673725d9d363c18b871eab5b18f",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-authority-badge-novel-label-inner",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        108,
        23,
        "as_assertion",
        "unknown",
        "sha256:8603ea50be860be72ad56e4fb4110206b056b57e92b7ac5564b7340aa22b02d5",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-authority-badge-novel-owner",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        113,
        19,
        "as_assertion",
        "RunOperatorDiagnostic",
        "sha256:2645ab1dc363750112b186defbf155508f86c0de0e973c13c93fca018887bfaa",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-envelope-unavailable-outer",
        "packages/atlas-ui/tests/EnvelopeChip.test.tsx",
        30,
        25,
        "as_assertion",
        "typeof GOVERNED_PACKET",
        "sha256:fae74b3a99495e285cd8bd9d3d1419805cf540e9c9705ed2b746c3a3d88fd5b9",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-envelope-unavailable-inner",
        "packages/atlas-ui/tests/EnvelopeChip.test.tsx",
        30,
        25,
        "as_assertion",
        "unknown",
        "sha256:e4c7905ac012964b3dd9b0293a4d0ff820ff4d05aa9abe42877ef64404e83203",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-envelope-malformed-marker-outer",
        "packages/atlas-ui/tests/EnvelopeChip.test.tsx",
        66,
        23,
        "as_assertion",
        "typeof GOVERNED_PACKET",
        "sha256:6e591ce6fc41d1d0e011b6d3aaba24dd4fb91e1bdef0f6808aa926d678e842d9",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-envelope-malformed-marker-inner",
        "packages/atlas-ui/tests/EnvelopeChip.test.tsx",
        66,
        23,
        "as_assertion",
        "unknown",
        "sha256:09b1c9d01c9c298b41e27026ae137a02d9309e8a15d0cd4ae12e1466b9c4b924",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-envelope-missing-marker-outer",
        "packages/atlas-ui/tests/EnvelopeChip.test.tsx",
        78,
        21,
        "as_assertion",
        "typeof GOVERNED_PACKET",
        "sha256:b05306435f50633530db75bd7257f9c5d894c9ab72cbee9f09f2215e45a6987c",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-envelope-missing-marker-inner",
        "packages/atlas-ui/tests/EnvelopeChip.test.tsx",
        78,
        21,
        "as_assertion",
        "unknown",
        "sha256:89e184e190abaa8f2f9cf8c140d3567cfbd88fc3e04de98ede331aa1b8589fea",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-owner-foundation-families",
        "packages/atlas-ui/tests/oneOwner.test.ts",
        9,
        29,
        "as_assertion",
        "const",
        "sha256:7c1fdd6eac1ab7b66321406e476a8b6ab46ffff61b745171a85f466d26388f35",
        "team-design",
        _STATIC_OWNERSHIP_REASON,
    ),
    _escape(
        "test-owner-form-families",
        "packages/atlas-ui/tests/oneOwner.test.ts",
        36,
        23,
        "as_assertion",
        "const",
        "sha256:edaa52d1586a646c932f38fe036624967d30ec66c54df87a35a54e6e2fbf0786",
        "team-design",
        _STATIC_OWNERSHIP_REASON,
    ),
    _escape(
        "test-owner-overlay-families",
        "packages/atlas-ui/tests/oneOwner.test.ts",
        49,
        26,
        "as_assertion",
        "const",
        "sha256:3292124b28dcd885824eab489a8c0be3862b2abeeaeb5e37b451477d01acfb26",
        "team-design",
        _STATIC_OWNERSHIP_REASON,
    ),
    _escape(
        "test-owner-evidence-families",
        "packages/atlas-ui/tests/oneOwner.test.ts",
        77,
        27,
        "as_assertion",
        "const",
        "sha256:49d79202f7f2324f05e9574b0fd402b600dbbcee63df10b95d1632424ad8abb0",
        "team-design",
        _STATIC_OWNERSHIP_REASON,
    ),
    _escape(
        "test-owner-compound-families",
        "packages/atlas-ui/tests/oneOwner.test.ts",
        83,
        27,
        "as_assertion",
        "const",
        "sha256:7902d8d29a84ae1a92c94c4f61af15385d3e13049e545a05a9f5c4dcab060272",
        "team-design",
        _STATIC_OWNERSHIP_REASON,
    ),
    _escape(
        "test-owner-pattern-families",
        "packages/atlas-ui/tests/oneOwner.test.ts",
        89,
        26,
        "as_assertion",
        "const",
        "sha256:4c2be7bde77780431acb01c667fde81f37f24d4c1fba491137a9292e4e8fdb88",
        "team-design",
        _STATIC_OWNERSHIP_REASON,
    ),
    _escape(
        "story-meta-framework-conformance",
        "apps/runtime-dashboard/src/shared/ui/evidence/EvidencePrimitives.stories.tsx",
        163,
        14,
        "satisfies",
        "Meta",
        "sha256:0122b0001de5923a754c73c515d92a65d568632c717db250b70f3f7ab867cba5",
        "team-design",
        "Storybook metadata conformance is unrelated to authority and the target "
        "resolves to no private brand; framework types expose intentional unknown slots.",
    ),
)
AUTHORITY_PATH_EXPECTED_COUNT = 17
CAPABILITY_DISCOVERY_OWNER_PATH = "apps/runtime-dashboard/src/api/hooks/useCapabilities.ts"
CAPABILITY_DISCOVERY_ISSUER_CALLS = 5
QUERY_CACHE_POLICY_TARGET_PATH = (
    "apps/runtime-dashboard/src/api/governedQueryPolicy.ts"
)
QUERY_CACHE_POLICY_DENOMINATORS = {
    "query_key_owners": 43,
    "constructions": 66,
    "producers": 42,
}
QUERY_CACHE_POLICY_GOVERNED_CONSTRUCTION = {
    "path": QUERY_CACHE_POLICY_TARGET_PATH,
    "resolved_callee": "useQuery",
    "options_declaration": None,
    "options_resolution": "referenced",
}
QUERY_CACHE_POLICY_GOVERNED_PRODUCER = {
    "path": "apps/runtime-dashboard/src/features/runs/api/useDepthNCycleBoardProjection.ts",
    "query_key_owner": "governedProjection",
    "options_declaration": {
        "name": "depthNCycleBoardProjectionQueryOptions",
        "path": "apps/runtime-dashboard/src/features/runs/api/useDepthNCycleBoardProjection.ts",
    },
}
COMPOSER_DRAFT_DB_PATH = "apps/runtime-dashboard/src/app/offline/composerDraftDb.ts"
COMPOSER_DRAFT_ADAPTER_PATH = (
    "apps/runtime-dashboard/src/features/composer/state/composerDraftRepository.ts"
)
OFFLINE_QUEUE_PRODUCTION_SOURCE_COUNT = 588
COMPOSER_DRAFT_DB_BINDINGS = [
    "deleteComposerDraftRecord",
    "loadComposerDraftRecord",
    "saveComposerDraftRecord",
]
AUTHORITY_GOVERNANCE_OBJECTS = (
    "EVIDENCE_FAMILIES",
    "EXPECTED_RUNTIME_EXPORTS",
)
AUTHORITY_ISSUER_MODULES = {
    "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
    "packages/atlas-ui/src/primitives/evidenceTypes.ts",
}
AUTHORITY_ISSUER_BRANDS = {
    "authorityPresentationBrand": "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
    "fixtureProvenanceBrand": "packages/atlas-ui/src/primitives/evidenceTypes.ts",
    "governedAuthorityPurposeBrand": "packages/atlas-ui/src/primitives/evidenceTypes.ts",
}
AUTHORITY_GENERATED_TYPES_PATH = "packages/runtime-api-client/types.ts"
AUTHORITY_ISSUER_FACTORIES: dict[str, dict[str, Any]] = {
    "createOpaqueAuthorityPresentation": {
        "path": "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
        "brand": "authorityPresentationBrand",
        "parameters": [
            {
                "name": "authority",
                "type": "string",
                "generated": False,
                "generatedPaths": [],
                "broadString": True,
                "optional": False,
                "rest": False,
            }
        ],
        "returns": [
            {
                "presentation": "unrecognized",
                "source": "opaque_extension",
                "tone": "neutral",
            }
        ],
        "placements": ["top_level"],
    },
    "createOperatorBlockingCausePresentation": {
        "path": "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
        "brand": "authorityPresentationBrand",
        "parameters": [
            {
                "name": "diagnostic",
                "type": "OperatorDiagnosticOwner",
                "generated": True,
                "generatedPaths": [AUTHORITY_GENERATED_TYPES_PATH],
                "broadString": False,
                "optional": False,
                "rest": False,
            }
        ],
        "returns": [
            {
                "presentation": "recognized",
                "source": "operator_blocking_cause",
                "tone": "fail",
            }
        ],
        "placements": ["top_level"],
    },
    "createOperatorProjectionPresentation": {
        "path": "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
        "brand": "authorityPresentationBrand",
        "parameters": [
            {
                "name": "diagnostic",
                "type": "OperatorDiagnosticOwner",
                "generated": True,
                "generatedPaths": [AUTHORITY_GENERATED_TYPES_PATH],
                "broadString": False,
                "optional": False,
                "rest": False,
            },
            {
                "name": "item",
                "type": "OperatorProjectionLabel",
                "generated": True,
                "generatedPaths": [AUTHORITY_GENERATED_TYPES_PATH],
                "broadString": False,
                "optional": False,
                "rest": False,
            },
        ],
        "returns": [
            {
                "presentation": "unrecognized",
                "source": "operator_projection_label",
                "tone": "neutral",
            },
            {
                "presentation": "recognized",
                "source": "operator_projection_label",
                "tone": None,
            },
        ],
        "placements": ["top_level_if", "top_level"],
    },
    "createFixtureProvenance": {
        "path": "packages/atlas-ui/src/primitives/evidenceTypes.ts",
        "brand": "fixtureProvenanceBrand",
        "parameters": [
            {
                "name": "payload",
                "type": "LegacyProvingGroundPayload",
                "generated": True,
                "generatedPaths": [AUTHORITY_GENERATED_TYPES_PATH],
                "broadString": False,
                "optional": False,
                "rest": False,
            }
        ],
        "returns": [{"presentation": None, "source": None, "tone": None}],
        "placements": ["top_level"],
    },
    "createGovernedAuthorityPurpose": {
        "path": "packages/atlas-ui/src/primitives/evidenceTypes.ts",
        "brand": "governedAuthorityPurposeBrand",
        "parameters": [
            {
                "name": "packet",
                "type": "AvailableGovernedProjectionPacket",
                "generated": True,
                "generatedPaths": [AUTHORITY_GENERATED_TYPES_PATH],
                "broadString": False,
                "optional": False,
                "rest": False,
            },
            {
                "name": "authorityPurpose",
                "type": 'AvailableGovernedProjectionPacket["authoritative_for"][number]',
                "generated": True,
                "generatedPaths": [AUTHORITY_GENERATED_TYPES_PATH],
                "broadString": True,
                "optional": False,
                "rest": False,
            },
        ],
        "returns": [{"presentation": None, "source": None, "tone": None}],
        "placements": ["top_level"],
    },
}
AUTHORITY_PRIVATE_CONSTRUCTORS = {
    "createPresentation": {
        "brand": "authorityPresentationBrand",
        "freeze_calls": 1,
        "write": {"store": "authorityPresentationIssuances", "method": "add"},
    },
    "issueFixtureProvenance": {
        "brand": "fixtureProvenanceBrand",
        "freeze_calls": 1,
        "write": {"store": "fixtureProvenanceIssuances", "method": "add"},
    },
    "issueGovernedAuthorityPurpose": {
        "brand": "governedAuthorityPurposeBrand",
        "freeze_calls": 2,
        "write": {
            "store": "governedAuthorityPurposeIssuances",
            "method": "set",
        },
    },
}
AUTHORITY_ISSUANCE_STORES = {
    "authorityPresentationIssuances": {
        "kind": "WeakSet",
        "write": {"function": "createPresentation", "method": "add"},
        "read": {
            "function": "assertAuthorityPresentation",
            "method": "has",
            "argumentParameter": "presentation",
        },
    },
    "fixtureProvenanceIssuances": {
        "kind": "WeakSet",
        "write": {"function": "issueFixtureProvenance", "method": "add"},
        "read": {
            "function": "fixtureAuthorityValue",
            "method": "has",
            "argumentParameter": "provenance",
        },
    },
    "governedAuthorityPurposeIssuances": {
        "kind": "WeakMap",
        "write": {
            "function": "issueGovernedAuthorityPurpose",
            "method": "set",
        },
        "read": {
            "function": "governedAuthorityPurposePresentation",
            "method": "get",
            "argumentParameter": "purpose",
        },
    },
}
AUTHORITY_OWNER_MEMBERSHIPS = {
    (
        "createGovernedAuthorityPurpose",
        "packet",
        "authoritative_for",
        "authorityPurpose",
        True,
        True,
    ),
    (
        "createOperatorProjectionPresentation",
        "diagnostic",
        "projection_labels",
        "item",
        True,
        True,
    ),
}


def _issuer_rows(
    facts: Mapping[str, Any],
    key: str,
    identity: str,
    errors: list[str],
) -> dict[str, Mapping[str, Any]]:
    value = facts.get(key)
    if not isinstance(value, list):
        errors.append(f"authority_issuer_fact_invalid:{key}")
        return {}
    rows: dict[str, Mapping[str, Any]] = {}
    for row in value:
        if not isinstance(row, Mapping) or not isinstance(row.get(identity), str):
            errors.append(f"authority_issuer_fact_invalid:{key}:row")
            continue
        row_id = str(row[identity])
        if row_id in rows:
            errors.append(f"authority_issuer_fact_duplicate:{key}:{row_id}")
        rows[row_id] = row
    return rows


def _issuer_set_drift(
    label: str,
    actual: set[str],
    expected: set[str],
    errors: list[str],
) -> None:
    if actual != expected:
        errors.append(
            f"authority_issuer_{label}_drift:"
            f"expected={','.join(sorted(expected))}:actual={','.join(sorted(actual))}"
        )


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"sha256:[a-f0-9]{64}", value) is not None


def _scope_nodes(node: ast.AST) -> list[ast.AST]:
    """Return nodes in one lexical scope without descending into child scopes."""
    nodes: list[ast.AST] = []

    def visit(current: ast.AST) -> None:
        nodes.append(current)
        for child in ast.iter_child_nodes(current):
            if child is not node and isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
            ):
                continue
            visit(child)

    visit(node)
    return nodes


_PYTHON_CAPABILITY_CONTRACTS = {
    "polisyos.core.contracts.CapabilityFeatureInfo": "feature",
    "polisyos.core.contracts.control.CapabilityFeatureInfo": "feature",
    "polisyos.core.contracts.CapabilityManifestResponse": "manifest",
    "polisyos.core.contracts.control.CapabilityManifestResponse": "manifest",
}


def _python_source_module(path: str) -> str | None:
    """Return the import module represented by one source path."""
    marker = "src/"
    offset = path.find(marker)
    if offset < 0 or not path.endswith(".py"):
        return None
    module = path[offset + len(marker) : -3].replace("/", ".")
    return module.removesuffix(".__init__")


def _python_import_module(
    source_path: str,
    imported: ast.ImportFrom,
    modules_by_path: Mapping[str, str],
) -> str | None:
    """Resolve an absolute or relative import to its module name."""
    if imported.level == 0:
        return imported.module
    source_module = modules_by_path.get(source_path)
    if source_module is None:
        return None
    package_parts = source_module.split(".")
    if not source_path.endswith("/__init__.py"):
        package_parts = package_parts[:-1]
    ascend = imported.level - 1
    if ascend > len(package_parts):
        return None
    base = package_parts[: len(package_parts) - ascend]
    if imported.module:
        base.extend(imported.module.split("."))
    return ".".join(base)


def _python_scope_binding(scope: ast.AST, name: str) -> tuple[str, ast.AST] | None:
    """Find one name's assignment, function, or import inside a lexical scope."""
    for node in reversed(_scope_nodes(scope)):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if node.value is not None and any(
                isinstance(target, ast.Name) and target.id == name for target in targets
            ):
                return "value", node.value
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]
                if local_name == name:
                    return "import", node
    body = getattr(scope, "body", ())
    statements = body if isinstance(body, list) else ()
    for statement in reversed(statements):
        if (
            isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and statement.name == name
        ):
            return "definition", statement
    return None


def _python_lookup_binding(
    path: str,
    scope: ast.AST,
    name: str,
    trees: Mapping[str, ast.Module],
) -> tuple[str, ast.AST] | None:
    """Resolve a local binding, falling back to its module scope."""
    binding = _python_scope_binding(scope, name)
    if binding is not None or scope is trees[path]:
        return binding
    return _python_scope_binding(trees[path], name)


def _python_import_binding(
    path: str,
    name: str,
    imported: ast.Import | ast.ImportFrom,
    modules_by_path: Mapping[str, str],
    paths_by_module: Mapping[str, str],
) -> tuple[str, str | None, str]:
    """Return a qualified module plus optional local source and exported symbol."""
    if isinstance(imported, ast.ImportFrom):
        module = _python_import_module(path, imported, modules_by_path)
        for alias in imported.names:
            if (alias.asname or alias.name) == name:
                qualified = f"{module}.{alias.name}" if module else alias.name
                return qualified, paths_by_module.get(module or ""), alias.name
    else:
        for alias in imported.names:
            if (alias.asname or alias.name.split(".")[0]) == name:
                qualified = alias.name if alias.asname else alias.name.split(".")[0]
                return qualified, paths_by_module.get(alias.name), ""
    return name, None, ""


def _python_resolve_callable(
    path: str,
    scope: ast.AST,
    expression: ast.AST,
    *,
    trees: Mapping[str, ast.Module],
    modules_by_path: Mapping[str, str],
    paths_by_module: Mapping[str, str],
    visited: set[tuple[str, int, str]],
) -> str | tuple[str, ast.AST] | None:
    """Resolve contract constructors and local/imported helper functions."""
    token = (path, id(scope), ast.dump(expression, include_attributes=False))
    if token in visited:
        return None
    visited.add(token)
    if isinstance(expression, ast.Name):
        binding = _python_lookup_binding(path, scope, expression.id, trees)
        if binding is None:
            return None
        kind, target = binding
        if kind == "value":
            return _python_resolve_callable(
                path,
                scope,
                target,
                trees=trees,
                modules_by_path=modules_by_path,
                paths_by_module=paths_by_module,
                visited=visited,
            )
        if kind == "definition":
            return path, target
        qualified, target_path, exported = _python_import_binding(
            path, expression.id, target, modules_by_path, paths_by_module
        )
        if qualified in _PYTHON_CAPABILITY_CONTRACTS:
            return _PYTHON_CAPABILITY_CONTRACTS[qualified]
        if target_path and exported:
            return _python_resolve_callable(
                target_path,
                trees[target_path],
                ast.Name(id=exported),
                trees=trees,
                modules_by_path=modules_by_path,
                paths_by_module=paths_by_module,
                visited=visited,
            )
        return None
    if isinstance(expression, ast.Attribute):
        parts: list[str] = [expression.attr]
        current = expression.value
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if not isinstance(current, ast.Name):
            return None
        binding = _python_lookup_binding(path, scope, current.id, trees)
        if binding is None or binding[0] != "import":
            return None
        qualified, target_path, _ = _python_import_binding(
            path, current.id, binding[1], modules_by_path, paths_by_module
        )
        qualified = ".".join((qualified, *reversed(parts)))
        if qualified in _PYTHON_CAPABILITY_CONTRACTS:
            return _PYTHON_CAPABILITY_CONTRACTS[qualified]
        if target_path:
            return _python_resolve_callable(
                target_path,
                trees[target_path],
                ast.Name(id=parts[0]),
                trees=trees,
                modules_by_path=modules_by_path,
                paths_by_module=paths_by_module,
                visited=visited,
            )
    return None


def _python_feature_contributors(
    path: str,
    scope: ast.AST,
    expression: ast.AST,
    *,
    root_ref: str,
    trees: Mapping[str, ast.Module],
    modules_by_path: Mapping[str, str],
    paths_by_module: Mapping[str, str],
    visited: set[tuple[str, int, int]],
) -> set[str]:
    """Trace one manifest features expression to constructors or unresolved imports."""
    token = (path, id(scope), id(expression))
    if token in visited:
        return set()
    visited.add(token)
    contributors: set[str] = set()
    if isinstance(expression, ast.Name):
        binding = _python_lookup_binding(path, scope, expression.id, trees)
        if binding is None:
            return contributors
        kind, target = binding
        if kind == "value":
            contributors.update(
                _python_feature_contributors(
                    path,
                    scope,
                    target,
                    root_ref=root_ref,
                    trees=trees,
                    modules_by_path=modules_by_path,
                    paths_by_module=paths_by_module,
                    visited=visited,
                )
            )
            for node in _scope_nodes(scope):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == expression.id
                    and node.func.attr in {"append", "extend"}
                ):
                    for argument in node.args:
                        contributors.update(
                            _python_feature_contributors(
                                path,
                                scope,
                                argument,
                                root_ref=root_ref,
                                trees=trees,
                                modules_by_path=modules_by_path,
                                paths_by_module=paths_by_module,
                                visited=visited,
                            )
                        )
            return contributors
        if kind == "import":
            qualified, target_path, exported = _python_import_binding(
                path, expression.id, target, modules_by_path, paths_by_module
            )
            if target_path and exported:
                target_scope = trees[target_path]
                if _python_lookup_binding(target_path, target_scope, exported, trees) is None:
                    contributors.add(
                        f"unresolved_manifest_features:{root_ref}:{qualified}"
                    )
                else:
                    contributors.update(
                        _python_feature_contributors(
                            target_path,
                            target_scope,
                            ast.Name(id=exported),
                            root_ref=root_ref,
                            trees=trees,
                            modules_by_path=modules_by_path,
                            paths_by_module=paths_by_module,
                            visited=visited,
                        )
                    )
            elif qualified not in _PYTHON_CAPABILITY_CONTRACTS:
                contributors.add(f"unresolved_manifest_features:{root_ref}:{qualified}")
            return contributors
    if isinstance(expression, ast.Call):
        resolved = _python_resolve_callable(
            path,
            scope,
            expression.func,
            trees=trees,
            modules_by_path=modules_by_path,
            paths_by_module=paths_by_module,
            visited=set(),
        )
        if resolved == "feature":
            return {f"{path}:{expression.lineno}"}
        if isinstance(resolved, tuple):
            helper_path, helper = resolved
            for node in _scope_nodes(helper):
                if isinstance(node, ast.Return) and node.value is not None:
                    contributors.update(
                        _python_feature_contributors(
                            helper_path,
                            helper,
                            node.value,
                            root_ref=root_ref,
                            trees=trees,
                            modules_by_path=modules_by_path,
                            paths_by_module=paths_by_module,
                            visited=visited,
                        )
                    )
            for argument in (*expression.args, *(item.value for item in expression.keywords)):
                contributors.update(
                    _python_feature_contributors(
                        path,
                        scope,
                        argument,
                        root_ref=root_ref,
                        trees=trees,
                        modules_by_path=modules_by_path,
                        paths_by_module=paths_by_module,
                        visited=visited,
                    )
                )
            return contributors
    for child in ast.iter_child_nodes(expression):
        contributors.update(
            _python_feature_contributors(
                path,
                scope,
                child,
                root_ref=root_ref,
                trees=trees,
                modules_by_path=modules_by_path,
                paths_by_module=paths_by_module,
                visited=visited,
            )
        )
    return contributors


def control_capability_manifest_contributors(
    sources: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Enumerate authored manifest contributors through local and imported value flow."""
    if sources is None:
        source_root = status_checker.REPO_ROOT / "src/polisyos"
        sources = {
            path.relative_to(status_checker.REPO_ROOT).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(source_root.rglob("*.py"))
        }
    trees = {
        path: ast.parse(source, filename=path)
        for path, source in sorted(sources.items())
        if path.endswith(".py")
    }
    modules_by_path = {
        path: module for path in trees if (module := _python_source_module(path)) is not None
    }
    paths_by_module = {module: path for path, module in modules_by_path.items()}
    owner_modules = {"polisyos.core.contracts", "polisyos.core.contracts.control"}
    manifest_paths = {
        path
        for path, tree in trees.items()
        if any(
            (
                isinstance(node, ast.ImportFrom)
                and node.module in owner_modules
                and any(alias.name == "CapabilityManifestResponse" for alias in node.names)
            )
            or (
                isinstance(node, ast.Import)
                and any(alias.name in owner_modules for alias in node.names)
            )
            for node in ast.walk(tree)
        )
    }
    changed = True
    while changed:
        changed = False
        for path, tree in trees.items():
            if path in manifest_paths:
                continue
            for imported in (node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)):
                module = _python_import_module(path, imported, modules_by_path)
                if paths_by_module.get(module or "") in manifest_paths:
                    manifest_paths.add(path)
                    changed = True
                    break
    contributors: set[str] = set()
    for path, tree in trees.items():
        if path not in manifest_paths:
            continue
        scopes: list[ast.AST] = [tree]
        scopes.extend(
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda))
        )
        for scope in scopes:
            for node in _scope_nodes(scope):
                if not isinstance(node, ast.Call):
                    continue
                resolved = _python_resolve_callable(
                    path,
                    scope,
                    node.func,
                    trees=trees,
                    modules_by_path=modules_by_path,
                    paths_by_module=paths_by_module,
                    visited=set(),
                )
                if resolved != "manifest":
                    continue
                for keyword in node.keywords:
                    if keyword.arg != "features":
                        continue
                    contributors.update(
                        _python_feature_contributors(
                            path,
                            scope,
                            keyword.value,
                            root_ref=f"{path}:{node.lineno}",
                            trees=trees,
                            modules_by_path=modules_by_path,
                            paths_by_module=paths_by_module,
                            visited=set(),
                        )
                    )
    return tuple(sorted(contributors))


def _capability_discovery_live_sources(
    source_overrides: Mapping[str, str] | None,
) -> tuple[dict[str, str], dict[str, str]]:
    """Derive the Python-owner and dashboard-render source sets for live checks."""
    if source_overrides is not None:
        python_sources = {
            path: source for path, source in source_overrides.items() if path.endswith(".py")
        }
        render_sources = {
            path: source
            for path, source in source_overrides.items()
            if path.endswith((".ts", ".tsx"))
        }
        return python_sources, render_sources

    repo_root = status_checker.REPO_ROOT
    python_root = repo_root / "src/polisyos"
    dashboard_root = repo_root / "apps/runtime-dashboard/src"
    python_sources = {
        path.relative_to(repo_root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(python_root.rglob("*.py"))
    }
    render_sources = {
        path.relative_to(repo_root).as_posix(): path.read_text(encoding="utf-8")
        for suffix in ("*.ts", "*.tsx")
        for path in sorted(dashboard_root.rglob(suffix))
    }
    return python_sources, render_sources


def check_capability_discovery_result_boundary(sources: Mapping[str, str]) -> list[str]:
    """Reject authored capability rows and literal branches in the generic render boundary."""
    node_binary = shutil.which("node")
    if node_binary is None:
        raise RuntimeError("capability discovery render scan requires node")
    completed = subprocess.run(  # noqa: S603 - executable and program are controlled constants.
        [node_binary, "-e", _CAPABILITY_DISCOVERY_RENDER_PROBE],
        cwd=status_checker.REPO_ROOT,
        input=json.dumps({"sources": dict(sorted(sources.items()))}),
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("capability discovery render scan failed: " + completed.stderr.strip())
    violations = json.loads(completed.stdout)
    if not isinstance(violations, list):
        raise RuntimeError("capability discovery render scan returned invalid findings")
    return sorted(
        {
            "hardcoded_discovery_result:"
            + str(violation.get("path", "unknown"))
            + ":"
            + str(violation.get("line", 0))
            + ":"
            + str(violation.get("kind", "unknown"))
            for violation in violations
            if isinstance(violation, Mapping)
        }
    )


def _capability_discovery_errors(
    scan: Mapping[str, Any],
    *,
    enforce_denominator: bool = False,
) -> list[str]:
    """Reject direct discovery construction without modeling value flow.

    The scanner proves only direct canonical-issuer calls and object literals
    contextually resolved to the generated capability-feature declaration.
    """
    facts = scan.get("capabilityDiscoveryFacts")
    if not isinstance(facts, Mapping):
        return ["capability_discovery_facts_missing"]
    production_files = facts.get("productionFiles")
    issuer_calls = facts.get("issuerCalls")
    feature_literals = facts.get("featureLiterals")
    errors: list[str] = []
    if not isinstance(production_files, int) or production_files <= 0:
        errors.append("capability_discovery_production_files_invalid")
    if not isinstance(issuer_calls, list):
        errors.append("capability_discovery_issuer_calls_invalid")
        issuer_calls = []
    if not isinstance(feature_literals, list):
        errors.append("capability_discovery_feature_literals_invalid")
        feature_literals = []
    if enforce_denominator and len(issuer_calls) != CAPABILITY_DISCOVERY_ISSUER_CALLS:
        errors.append(
            "capability_discovery_issuer_denominator_drift:"
            f"expected={CAPABILITY_DISCOVERY_ISSUER_CALLS}:actual={len(issuer_calls)}"
        )

    for call in issuer_calls:
        if not isinstance(call, Mapping):
            errors.append("capability_discovery_issuer_call_invalid")
            continue
        path = call.get("path")
        line = call.get("line")
        if not isinstance(path, str) or not isinstance(line, int) or line <= 0:
            errors.append("capability_discovery_issuer_call_invalid")
            continue
        identity = f"{path}:{line}"
        if path != CAPABILITY_DISCOVERY_OWNER_PATH:
            errors.append(f"capability_discovery_issuer_unowned:{identity}")
        if call.get("argumentKind") != "object_literal":
            errors.append(f"capability_discovery_issuer_argument_invalid:{identity}")
            continue
        state = call.get("state")
        reason = call.get("reason")
        manifest = call.get("manifest")
        if state == "unavailable":
            if (
                reason not in {"error", "loading", "missing_data", "offline"}
                or manifest is not None
            ):
                errors.append(f"capability_discovery_unavailable_shape_invalid:{identity}")
        elif state == "available":
            if (
                reason is not None
                or not isinstance(manifest, Mapping)
                or manifest.get("kind") != "expression"
                or manifest.get("canonical") is not True
                or manifest.get("directQueryData") is not True
                or manifest.get("loadingGuarded") is not False
            ):
                errors.append(f"capability_discovery_available_manifest_invalid:{identity}")
        else:
            errors.append(f"capability_discovery_state_invalid:{identity}")

    for literal in feature_literals:
        if not isinstance(literal, Mapping):
            errors.append("capability_discovery_feature_literal_invalid")
            continue
        path = literal.get("path")
        line = literal.get("line")
        properties = literal.get("properties")
        if (
            not isinstance(path, str)
            or not isinstance(line, int)
            or line <= 0
            or not isinstance(properties, list)
            or any(not isinstance(name, str) for name in properties)
        ):
            errors.append("capability_discovery_feature_literal_invalid")
            continue
        errors.append(f"capability_discovery_feature_literal_authored:{path}:{line}")
    return sorted(set(errors))


def _query_cache_policy_register_from_scan(scan: Mapping[str, Any]) -> dict[str, Any]:
    """Derive the C12a source-bound register from direct local AST facts."""
    facts = scan["queryCachePolicyFacts"]
    constructions = [
        {
            "path": row["path"],
            "line": row["line"],
            "resolved_callee": row["callee"],
            "source_sha256": row["sourceSha256"],
            "options_resolution": row["optionsResolution"],
            "classification": (
                "governed_wrapper"
                if _query_cache_policy_identity_matches(
                    {
                        "path": row["path"],
                        "resolved_callee": row["callee"],
                        "options_declaration": row["optionsDeclaration"],
                        "options_resolution": row["optionsResolution"],
                    },
                    QUERY_CACHE_POLICY_GOVERNED_CONSTRUCTION,
                )
                else "legacy_direct_debt"
            ),
        }
        for row in facts["constructions"]
    ]
    producers = [
        {
            "path": row["path"],
            "line": row["line"],
            "source_sha256": row["sourceSha256"],
            "query_key_owner": row["queryKeyOwner"],
            "dto_contract": row["dtoContract"],
            "required_owner_field": "as_of",
            "owner_slice": "DS5",
            "capability_state": (
                "governed_migration_target"
                if _query_cache_policy_identity_matches(
                    {
                        "path": row["path"],
                        "query_key_owner": row["queryKeyOwner"],
                        "options_declaration": row["optionsDeclaration"],
                    },
                    QUERY_CACHE_POLICY_GOVERNED_PRODUCER,
                )
                else "source_bound_debt"
            ),
            "closure_signal": (
                "C11a-C11b-R1 typed cache-posture consumer"
                if _query_cache_policy_identity_matches(
                    {
                        "path": row["path"],
                        "query_key_owner": row["queryKeyOwner"],
                        "options_declaration": row["optionsDeclaration"],
                    },
                    QUERY_CACHE_POLICY_GOVERNED_PRODUCER,
                )
                else "C12b-R1 independently proves an operational policy contract"
            ),
            "classification": (
                "governed_wrapper"
                if _query_cache_policy_identity_matches(
                    {
                        "path": row["path"],
                        "query_key_owner": row["queryKeyOwner"],
                        "options_declaration": row["optionsDeclaration"],
                    },
                    QUERY_CACHE_POLICY_GOVERNED_PRODUCER,
                )
                else "legacy_direct_debt"
            ),
        }
        for row in facts["producers"]
    ]
    return {
        "$schema": "./query-cache-policy-register.schema.json",
        "schema_version": "1.0",
        "register_id": "atlas-ds5-query-cache-policy",
        "authority": {
            "authoritative_for": [
                "the direct TypeScript construction-site census for DS5 query cache policy debt"
            ],
            "may_not_use_for": [
                "TanStack value-flow analysis",
                "cache-policy runtime behavior",
                "source freshness or observation-time inference",
            ],
        },
        "residual": facts["residual"],
        "denominators": QUERY_CACHE_POLICY_DENOMINATORS,
        "query_key_owners": [
            {"name": row["name"], "path": row["path"], "line": row["line"]}
            for row in facts["queryKeyOwners"]
        ],
        "constructions": constructions,
        "producers": producers,
    }


def _query_cache_policy_identity_matches(
    row: Mapping[str, Any],
    target: Mapping[str, Any],
) -> bool:
    """Return whether one direct-site row is the immutable governed target."""
    def matches(value: Any, expected: Any) -> bool:
        if isinstance(expected, Mapping):
            return isinstance(value, Mapping) and all(
                key in value and matches(value[key], nested_expected)
                for key, nested_expected in expected.items()
            )
        return value == expected

    return all(field in row and matches(row[field], expected) for field, expected in target.items())


def _query_cache_policy_target_identity_errors(
    rows: Sequence[Mapping[str, Any]],
    *,
    identity_rows: Sequence[Mapping[str, Any]],
    target: Mapping[str, Any],
    label: str,
    expected_debt: int,
) -> list[str]:
    """Require exactly one source-bound governed row and all other rows as debt."""
    at_target_path = [row for row in identity_rows if row.get("path") == target["path"]]
    exact = [row for row in identity_rows if _query_cache_policy_identity_matches(row, target)]
    governed = [
        row for row in rows if row.get("classification") == "governed_wrapper"
    ]
    debt = [row for row in rows if row.get("classification") == "legacy_direct_debt"]
    errors: list[str] = []
    if len(at_target_path) != 1 or len(exact) != 1:
        errors.append(f"query_cache_policy_{label}_target_identity_drift")
    if len(governed) != 1 or len(debt) != expected_debt:
        errors.append(
            f"query_cache_policy_{label}_classification_cardinality:"
            f"governed={len(governed)}:debt={len(debt)}"
        )
    return errors


def _query_cache_policy_errors(
    scan: Mapping[str, Any],
    *,
    enforce_denominator: bool = False,
    registry: Mapping[str, Any] | None = None,
) -> list[str]:
    """Require one complete, source-bound table for each C12a construction class."""
    facts = scan.get("queryCachePolicyFacts")
    if not isinstance(facts, Mapping):
        return ["query_cache_policy_facts_missing"]
    try:
        expected = _query_cache_policy_register_from_scan(scan)
    except (KeyError, TypeError):
        return ["query_cache_policy_facts_invalid"]
    actual = dict(registry or status_checker._load_json(QUERY_CACHE_POLICY_REGISTER_PATH))
    errors = status_checker._schema_errors(
        actual,
        QUERY_CACHE_POLICY_SCHEMA_PATH,
        "query-cache-policy-register",
    )
    if enforce_denominator:
        for key, expected_count in QUERY_CACHE_POLICY_DENOMINATORS.items():
            actual_count = len(
                expected[
                    {
                        "query_key_owners": "query_key_owners",
                        "constructions": "constructions",
                        "producers": "producers",
                    }[key]
                ]
            )
            if actual_count != expected_count:
                errors.append(
                    "query_cache_policy_denominator_drift:"
                    f"{key}:expected={expected_count}:actual={actual_count}"
                )
    if actual.get("query_key_owners") != expected["query_key_owners"]:
        errors.append("query_cache_policy_query_key_owner_drift")
    if actual.get("constructions") != expected["constructions"]:
        errors.append("query_cache_policy_construction_drift")
    if actual.get("producers") != expected["producers"]:
        errors.append("query_cache_policy_producer_drift")
    errors.extend(
        _query_cache_policy_target_identity_errors(
            expected["constructions"],
            identity_rows=[
                {
                    "path": row["path"],
                    "resolved_callee": row["callee"],
                    "options_declaration": row["optionsDeclaration"],
                    "options_resolution": row["optionsResolution"],
                }
                for row in facts["constructions"]
            ],
            target=QUERY_CACHE_POLICY_GOVERNED_CONSTRUCTION,
            label="construction",
            expected_debt=65,
        )
    )
    errors.extend(
        _query_cache_policy_target_identity_errors(
            expected["producers"],
            identity_rows=[
                {
                    "path": row["path"],
                    "query_key_owner": row["queryKeyOwner"],
                    "options_declaration": row["optionsDeclaration"],
                }
                for row in facts["producers"]
            ],
            target=QUERY_CACHE_POLICY_GOVERNED_PRODUCER,
            label="producer",
            expected_debt=41,
        )
    )
    return sorted(set(errors))


def _persistence_construction_errors(
    scan: Mapping[str, Any],
    *,
    register: Mapping[str, Any],
) -> list[str]:
    """Join declaration-resolved persistence sites to explicit governed rows."""
    facts = scan.get("persistenceConstructionFacts")
    census = register.get("storage_construction_census")
    if not isinstance(facts, Mapping):
        return ["persistence_construction_facts_missing"]
    if not isinstance(census, Mapping):
        return ["persistence_construction_census_missing"]
    live_sites = facts.get("sites")
    governed_sites = census.get("sites")
    if not isinstance(live_sites, list) or not isinstance(governed_sites, list):
        return ["persistence_construction_census_invalid"]

    errors: list[str] = []
    disposition_checker._validate_storage_construction_census(register, errors)
    if facts.get("productionSourceCount") != census.get("production_source_count"):
        errors.append("persistence_production_source_denominator_drift")
    live_paths = {
        str(row.get("path"))
        for row in live_sites
        if isinstance(row, Mapping) and isinstance(row.get("path"), str)
    }
    if len(live_paths) != census.get("production_file_count"):
        errors.append("persistence_production_file_denominator_drift")
    if len(live_sites) != census.get("site_count"):
        errors.append("persistence_site_denominator_drift")
    if facts.get("apiCounts") != census.get("api_counts"):
        errors.append("persistence_api_denominator_drift")

    def rows_by_id(rows: Sequence[Any], label: str) -> dict[str, Mapping[str, Any]]:
        mapped: dict[str, Mapping[str, Any]] = {}
        for row in rows:
            if not isinstance(row, Mapping) or not isinstance(row.get("site_id"), str):
                errors.append(f"persistence_{label}_row_invalid")
                continue
            site_id = str(row["site_id"])
            if site_id in mapped:
                errors.append(f"persistence_{label}_site_duplicate:{site_id}")
            mapped[site_id] = row
        return mapped

    normalized_live = [
        {
            "site_id": row.get("siteId"),
            "path": row.get("path"),
            "resolved_api_declaration": row.get("resolvedApi"),
            "operation": row.get("operation"),
            "source_fingerprint": row.get("sourceSha256"),
            "site_fingerprint": row.get("siteSha256"),
        }
        for row in live_sites
        if isinstance(row, Mapping)
    ]
    live_by_id = rows_by_id(normalized_live, "live")
    governed_by_id = rows_by_id(governed_sites, "registered")
    authority_factory_calls = facts.get("authorityFactoryCalls")
    if not isinstance(authority_factory_calls, list):
        errors.append("persistence_authority_factory_facts_invalid")
        authority_factory_calls = []
    normalized_factories: list[dict[str, Any]] = []
    for factory_call in authority_factory_calls:
        if not isinstance(factory_call, Mapping):
            errors.append("persistence_authority_factory_fact_invalid")
            continue
        normalized_factories.append(
            {
                "factory_site_id": factory_call.get("factorySiteId"),
                "path": factory_call.get("path"),
                "factory": factory_call.get("factory"),
                "declaration_chain": factory_call.get("declarationChain"),
                "source_fingerprint": factory_call.get("sourceSha256"),
                "site_fingerprint": factory_call.get("siteSha256"),
            }
        )
    live_factory_ids = [
        str(row.get("factory_site_id")) for row in normalized_factories
    ]
    errors.extend(
        f"persistence_authority_factory_duplicate:{factory_id}"
        for factory_id, count in Counter(live_factory_ids).items()
        if count > 1
    )
    live_factories = {
        str(row.get("factory_site_id")): row for row in normalized_factories
    }
    governed_factory_rows = census.get("authority_factory_receipts")
    governed_factories = (
        {
            str(row.get("factory_site_id")): row
            for row in governed_factory_rows
            if isinstance(row, Mapping)
        }
        if isinstance(governed_factory_rows, list)
        else {}
    )
    for factory_id in sorted(live_factories.keys() - governed_factories.keys()):
        errors.append(f"persistence_unregistered_authority_factory:{factory_id}")
    for factory_id in sorted(governed_factories.keys() - live_factories.keys()):
        errors.append(f"persistence_stale_authority_factory:{factory_id}")
    for factory_id in sorted(live_factories.keys() & governed_factories.keys()):
        if live_factories[factory_id] != governed_factories[factory_id]:
            errors.append(f"persistence_authority_factory_drift:{factory_id}")
    for site_id in sorted(live_by_id.keys() - governed_by_id.keys()):
        errors.append(f"persistence_unregistered_site:{site_id}")
    for site_id in sorted(governed_by_id.keys() - live_by_id.keys()):
        errors.append(f"persistence_stale_registered_site:{site_id}")
    comparisons = {
        "path": "path_drift",
        "resolved_api_declaration": "resolved_declaration_drift",
        "operation": "operation_drift",
        "source_fingerprint": "source_fingerprint_drift",
        "site_fingerprint": "site_fingerprint_drift",
    }
    for site_id in sorted(live_by_id.keys() & governed_by_id.keys()):
        live = live_by_id[site_id]
        governed = governed_by_id[site_id]
        for field, label in comparisons.items():
            if live.get(field) != governed.get(field):
                errors.append(f"persistence_{label}:{site_id}")
    return sorted(set(errors))


def _offline_queue_errors(
    scan: Mapping[str, Any], *, enforce_denominator: bool
) -> list[str]:
    """Reject any durable authority-action replay while retaining composer drafts."""
    facts = scan.get("offlineQueueFacts")
    if not isinstance(facts, Mapping):
        return ["offline_queue_facts_missing"]
    required_tables = (
        "authorityActionKinds",
        "composerDbImports",
        "mutationStores",
        "optimisticAuthorityProjections",
        "replayDeclarations",
    )
    if any(not isinstance(facts.get(table), list) for table in required_tables):
        return ["offline_queue_facts_invalid"]

    errors: list[str] = []
    if enforce_denominator and facts.get("productionFiles") != OFFLINE_QUEUE_PRODUCTION_SOURCE_COUNT:
        errors.append("offline_queue_production_source_denominator_drift")
    for table, prefix in (
        ("authorityActionKinds", "offline_queue_authority_action_kind"),
        ("mutationStores", "offline_queue_mutation_store"),
        ("optimisticAuthorityProjections", "offline_queue_optimistic_projection"),
        ("replayDeclarations", "offline_queue_replay_declaration"),
    ):
        for row in facts[table]:
            if not isinstance(row, Mapping) or not isinstance(row.get("path"), str):
                errors.append(f"{prefix}_fact_invalid")
                continue
            errors.append(f"{prefix}:{row['path']}")

    expected_composer_import = {
        "bindings": COMPOSER_DRAFT_DB_BINDINGS,
        "path": COMPOSER_DRAFT_ADAPTER_PATH,
        "targetPath": COMPOSER_DRAFT_DB_PATH,
    }
    if facts["composerDbImports"] != [expected_composer_import]:
        errors.append("composer_draft_db_import_boundary_drift")
    return sorted(set(errors))


def _write_query_cache_policy_register(scan: Mapping[str, Any]) -> None:
    """Prove the committed C12a register is already the byte-preserved derivation."""
    expected = json.dumps(_query_cache_policy_register_from_scan(scan), indent=2) + "\n"
    actual = QUERY_CACHE_POLICY_REGISTER_PATH.read_text(encoding="utf-8")
    if actual != expected:
        raise RuntimeError(
            "query cache policy register drift; writer refuses a non-surgical rewrite"
        )


def _authority_issuer_errors(scan: Mapping[str, Any]) -> list[str]:
    """Validate branded issuer construction sites without modeling value flow."""
    errors: list[str] = []
    facts = scan.get("authorityIssuerFacts")
    if not isinstance(facts, Mapping):
        return ["authority_issuer_facts_missing"]

    modules = _issuer_rows(facts, "modules", "path", errors)
    _issuer_set_drift("modules", set(modules), AUTHORITY_ISSUER_MODULES, errors)
    for path, row in modules.items():
        if not _valid_sha256(row.get("sourceSha256")):
            errors.append(f"authority_issuer_module_receipt_invalid:{path}")

    brands = _issuer_rows(facts, "brands", "name", errors)
    _issuer_set_drift("brands", set(brands), set(AUTHORITY_ISSUER_BRANDS), errors)
    for name, expected_path in AUTHORITY_ISSUER_BRANDS.items():
        row = brands.get(name)
        if row is None:
            continue
        if row.get("path") != expected_path:
            errors.append(f"authority_issuer_brand_path_drift:{name}")
        if row.get("exported") is not False:
            errors.append(f"authority_issuer_brand_exported:{name}")
        if not _valid_sha256(row.get("declarationSha256")):
            errors.append(f"authority_issuer_brand_receipt_invalid:{name}")

    factories = _issuer_rows(facts, "factories", "name", errors)
    _issuer_set_drift("factories", set(factories), set(AUTHORITY_ISSUER_FACTORIES), errors)
    receipt = scan.get("generatedOwnerReceipt", {})
    governed_paths = {
        str(receipt[key])
        for key in ("canonical_path", "types_path")
        if isinstance(receipt, Mapping) and isinstance(receipt.get(key), str)
    }
    for name, expected in AUTHORITY_ISSUER_FACTORIES.items():
        row = factories.get(name)
        if row is None:
            continue
        if row.get("path") != expected["path"]:
            errors.append(f"authority_issuer_factory_path_drift:{name}")
        if row.get("returnBrands") != [expected["brand"]]:
            errors.append(f"authority_issuer_factory_brand_drift:{name}")
        if row.get("overloadCount") != 1:
            errors.append(f"authority_issuer_factory_overload_drift:{name}")
        if not _valid_sha256(row.get("declarationSha256")):
            errors.append(f"authority_issuer_factory_receipt_invalid:{name}")
        parameters = row.get("parameters")
        if not isinstance(parameters, list) or any(
            not isinstance(parameter, Mapping) for parameter in parameters
        ):
            errors.append(f"authority_issuer_factory_parameters_invalid:{name}")
            continue
        if parameters != expected["parameters"]:
            errors.append(f"authority_issuer_factory_parameters_drift:{name}")
        generated = [parameter for parameter in parameters if parameter.get("generated") is True]
        for parameter in generated:
            paths = parameter.get("generatedPaths")
            if (
                not isinstance(paths, list)
                or not paths
                or not governed_paths
                or any(path not in governed_paths for path in paths)
            ):
                errors.append(
                    f"authority_issuer_factory_generated_path_invalid:"
                    f"{name}:{parameter.get('name')}"
                )
        if row.get("issuedReturns") != expected["returns"]:
            errors.append(f"authority_issuer_factory_return_drift:{name}")
        expected_calls = [
            {
                **return_fact,
                "directReturn": True,
                "placement": placement,
            }
            for return_fact, placement in zip(
                expected["returns"], expected["placements"], strict=True
            )
        ]
        if row.get("issuanceCalls") != expected_calls or row.get("returnStatements") != len(
            expected_calls
        ):
            errors.append(f"authority_issuer_factory_call_shape_drift:{name}")

    constructors = _issuer_rows(facts, "privateConstructors", "name", errors)
    _issuer_set_drift(
        "constructors", set(constructors), set(AUTHORITY_PRIVATE_CONSTRUCTORS), errors
    )
    for name, expected in AUTHORITY_PRIVATE_CONSTRUCTORS.items():
        row = constructors.get(name)
        if row is None:
            continue
        brand = str(expected["brand"])
        if row.get("path") != AUTHORITY_ISSUER_BRANDS[brand]:
            errors.append(f"authority_issuer_constructor_path_drift:{name}")
        if row.get("returnBrands") != [brand]:
            errors.append(f"authority_issuer_constructor_brand_drift:{name}")
        if row.get("freezeCalls") != expected["freeze_calls"]:
            errors.append(f"authority_issuer_constructor_freeze_drift:{name}")
        if row.get("returnedValueFrozen") is not True:
            errors.append(f"authority_issuer_constructor_return_not_frozen:{name}")
        if row.get("brandInitializedOnReturnedValue") is not True:
            errors.append(f"authority_issuer_constructor_brand_binding_drift:{name}")
        writes = row.get("issuanceWrites")
        expected_write = expected["write"]
        if not isinstance(writes, list) or writes != [{**expected_write, "issuedValue": True}]:
            errors.append(f"authority_issuer_constructor_issuance_drift:{name}")

    stores = _issuer_rows(facts, "stores", "name", errors)
    _issuer_set_drift("stores", set(stores), set(AUTHORITY_ISSUANCE_STORES), errors)
    for name, expected in AUTHORITY_ISSUANCE_STORES.items():
        row = stores.get(name)
        if row is None:
            continue
        if row.get("kind") != expected["kind"] or row.get("exported") is not False:
            errors.append(f"authority_issuer_store_declaration_drift:{name}")
        for operation_key in ("read", "write"):
            actual = row.get(operation_key + "s")
            if not isinstance(actual, list) or actual != [expected[operation_key]]:
                errors.append(f"authority_issuer_store_{operation_key}_drift:{name}")

    tone_maps = facts.get("exhaustiveToneMaps")
    expected_tone_map = {
        "path": "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
        "target": 'Record<OperatorProjectionLabel["state"], BadgeTone>',
        "consumers": ["createOperatorProjectionPresentation"],
    }
    if (
        not isinstance(tone_maps, list)
        or len(tone_maps) != 1
        or not isinstance(tone_maps[0], Mapping)
        or any(tone_maps[0].get(key) != value for key, value in expected_tone_map.items())
    ):
        errors.append("authority_issuer_exhaustive_tone_map_drift")

    scalars = _issuer_rows(facts, "exactGeneratedScalars", "name", errors)
    if set(scalars) != {"exactFixtureAuthority"}:
        errors.append("authority_issuer_exact_generated_scalar_drift")
    else:
        scalar = scalars["exactFixtureAuthority"]
        if (
            scalar.get("input") != "FixtureAuthority"
            or scalar.get("output") != '"fixture_only"'
            or scalar.get("callers") != ["createFixtureProvenance"]
        ):
            errors.append("authority_issuer_exact_generated_scalar_drift")

    parity = _issuer_rows(facts, "parityBindings", "name", errors)
    parity_row = parity.get("assertProjectionVocabularyParity", {})
    predicate = parity_row.get("predicate")
    if (
        set(parity) != {"assertProjectionVocabularyParity"}
        or parity_row.get("parameters") != 2
        or parity_row.get("totalInvocations") != 1
        or parity_row.get("literalTrueInvocations") != 1
        or parity_row.get("neverFailureParameters") != 2
        or not isinstance(predicate, Mapping)
        or predicate.get("name") != "IsExact"
        or predicate.get("path") != "packages/atlas-ui/src/primitives/AuthorityBadge.tsx"
        or predicate.get("exactTwoWay") is not True
    ):
        errors.append("authority_issuer_projection_parity_drift")

    unrecognized = facts.get("unrecognizedNeutralFactories")
    expected_unrecognized = {
        "createOpaqueAuthorityPresentation",
        "createOperatorProjectionPresentation",
    }
    if (
        not isinstance(unrecognized, list)
        or any(not isinstance(value, str) for value in unrecognized)
        or set(unrecognized) != expected_unrecognized
    ):
        errors.append("authority_issuer_runtime_novelty_drift")

    membership = facts.get("ownerMembershipFactories")
    actual_membership = {
        (
            row.get("factory"),
            row.get("receiverParameter"),
            row.get("receiverProperty"),
            row.get("argumentParameter"),
            row.get("negatedThrow"),
            row.get("precedesIssuance"),
        )
        for row in membership or []
        if isinstance(row, Mapping)
    }
    if not isinstance(membership, list) or actual_membership != AUTHORITY_OWNER_MEMBERSHIPS:
        errors.append("authority_issuer_owner_membership_drift")

    exported_constants = facts.get("exportedValueConstants")
    if not isinstance(exported_constants, list) or exported_constants:
        errors.append("authority_issuer_exported_vocabulary")
    return sorted(set(errors))


def _override_diagnostic_errors(scan: Mapping[str, Any]) -> list[str]:
    """Translate TypeScript diagnostics from synthetic witnesses."""
    return sorted(
        {
            "invalid_source_override:"
            + str(diagnostic.get("path", "unknown"))
            + ":"
            + str(diagnostic.get("line", 0))
            + ":TS"
            + str(diagnostic.get("code", "unknown"))
            for diagnostic in scan.get("overrideDiagnostics", [])
            if isinstance(diagnostic, Mapping)
        }
    )


def _generated_owner_receipt(inventory: Mapping[str, Any]) -> dict[str, str]:
    """Project the content-bound generated-client receipt used by the scan."""
    generated = inventory["sources"]["generated_client"]
    return {
        key: str(generated[key])
        for key in (
            "canonical_path",
            "types_path",
            "canonical_sha256",
            "types_sha256",
        )
    }


def _authority_path_descriptors() -> list[dict[str, str]]:
    """Return the two declaration-anchored branded authority props."""
    return [
        {
            "descriptorId": descriptor_id,
            "component": str(spec["component"]),
            "componentDeclarationPath": str(spec["component_declaration_path"]),
            "prop": str(spec["prop"]),
        }
        for descriptor_id, spec in sorted(
            disposition_checker.AUTHORITY_PROP_CLASSIFICATIONS.items()
        )
        if str(spec["classification"]).startswith("branded:")
    ]


def _enforcement_scan(
    source_overrides: Mapping[str, str] | None,
    *,
    inventory: Mapping[str, Any],
    validate_override_diagnostics: bool,
    include_dashboard_program_roots: bool = False,
) -> dict[str, Any]:
    """Run the shared scanner with the bounded C01a/C01b descriptors."""
    request: dict[str, Any] = {}
    if source_overrides is not None:
        request["sourceOverrides"] = dict(sorted(source_overrides.items()))
        if include_dashboard_program_roots:
            request["includeDashboardProgramRoots"] = True
        if validate_override_diagnostics:
            request["validateOverrideDiagnostics"] = True
    request["authorityPathDescriptors"] = _authority_path_descriptors()
    request["authorityGovernanceObjects"] = list(AUTHORITY_GOVERNANCE_OBJECTS)
    request["authorityPropDescriptors"] = (
        disposition_checker._authority_prop_descriptors() if source_overrides is None else []
    )
    request["protectedDefinitions"] = status_checker._protected_semantic_definitions(inventory)
    generated = inventory["sources"]["generated_client"]
    request["generatedDefinitionPaths"] = sorted(
        {str(generated["canonical_path"]), str(generated["types_path"])}
    )
    scan = status_checker._scan_json(json.dumps(request, sort_keys=True, separators=(",", ":")))
    for key in ("authorityPathFiles", "authorityEscapeSites"):
        if not isinstance(scan.get(key), list):
            raise RuntimeError(f"status TypeScript scan returned invalid {key}")
    if not isinstance(scan.get("authorityIssuerFacts"), Mapping):
        raise RuntimeError("status TypeScript scan returned invalid authorityIssuerFacts")
    if not isinstance(scan.get("offlineQueueFacts"), Mapping):
        raise RuntimeError("status TypeScript scan returned invalid offlineQueueFacts")
    if not isinstance(scan.get("persistenceConstructionFacts"), Mapping):
        raise RuntimeError(
            "status TypeScript scan returned invalid persistenceConstructionFacts"
        )
    if not isinstance(scan.get("authzDecisionFacts"), Mapping):
        raise RuntimeError("status TypeScript scan returned invalid authzDecisionFacts")
    return scan


def _authz_default_allow_errors(scan: Mapping[str, Any]) -> list[str]:
    """Validate the bounded phased N010 direct-default remainder."""
    facts = scan.get("authzDecisionFacts")
    if not isinstance(facts, Mapping):
        return ["authz_decision_facts_missing"]
    hook_calls = facts.get("hookCalls")
    sites = facts.get("defaultAllowSites")
    if not isinstance(hook_calls, list) or not isinstance(sites, list):
        return ["authz_decision_facts_invalid"]

    errors: list[str] = []
    if facts.get("residual") != C09A_AUTHZ_DIRECT_SYNTAX_RESIDUAL:
        errors.append("authz_decision_residual_drift")
    live_hooks = {
        (str(row.get("path")), str(row.get("hook")))
        for row in hook_calls
        if isinstance(row, Mapping)
    }
    for path in C09A_AUTHZ_DECISION_PATHS:
        if (path, "useAuthzDecision") not in live_hooks:
            errors.append(f"authz_decision_api_missing:{path}")

    live = Counter(
        (
            str(row.get("path")),
            str(row.get("kind")),
            str(row.get("siteFingerprint")),
        )
        for row in sites
        if isinstance(row, Mapping)
    )
    expected = Counter(C09B_DEFERRED_AUTHZ_DEFAULTS)
    for identity, count in sorted((live - expected).items()):
        path, kind, fingerprint = identity
        errors.extend(
            f"authz_default_allow_unclassified:{path}:{kind}:{fingerprint}"
            for _ in range(count)
        )
    for identity, count in sorted((expected - live).items()):
        path, kind, fingerprint = identity
        errors.extend(
            f"authz_default_allow_deferred_drift:{path}:{kind}:{fingerprint}"
            for _ in range(count)
        )
    return errors


def _escape_identity(value: Mapping[str, Any] | AuthorityEscapeExemption) -> tuple[Any, ...]:
    getter = (
        (lambda field: getattr(value, field))
        if isinstance(value, AuthorityEscapeExemption)
        else (lambda field: value.get(field))
    )
    return tuple(
        getter(field)
        for field in (
            "path",
            "line",
            "column",
            "construct",
            "target",
            "site_sha256" if isinstance(value, AuthorityEscapeExemption) else "siteSha256",
        )
    )


def _authority_escape_errors(
    scan: Mapping[str, Any],
    *,
    exemptions: Sequence[AuthorityEscapeExemption] = AUTHORITY_ESCAPE_EXEMPTIONS,
    enforce_denominator: bool = True,
) -> list[str]:
    """Validate local escape syntax; this deliberately performs no value flow."""
    errors: list[str] = []
    paths = scan.get("authorityPathFiles", [])
    sites = scan.get("authorityEscapeSites", [])
    if not isinstance(paths, list) or not isinstance(sites, list):
        return ["authority_escape_scan_invalid"]
    path_names = {
        str(row.get("path"))
        for row in paths
        if isinstance(row, Mapping) and isinstance(row.get("path"), str)
    }
    if len(path_names) != len(paths):
        errors.append("authority_escape_path_census_duplicate_or_invalid")
    if enforce_denominator and len(path_names) != AUTHORITY_PATH_EXPECTED_COUNT:
        errors.append(
            "authority_escape_path_denominator_drift:"
            f"expected={AUTHORITY_PATH_EXPECTED_COUNT}:actual={len(path_names)}"
        )

    allowed_constructs = {
        "as_assertion",
        "type_assertion",
        "explicit_any",
        "ts_ignore",
        "ts_expect_error",
        "ts_nocheck",
        "satisfies",
    }
    exemption_by_identity: dict[tuple[Any, ...], AuthorityEscapeExemption] = {}
    exemption_ids: set[str] = set()
    for exemption in exemptions:
        if exemption.exemption_id in exemption_ids:
            errors.append(f"authority_escape_exemption_duplicate:{exemption.exemption_id}")
        exemption_ids.add(exemption.exemption_id)
        if exemption.construct not in allowed_constructs:
            errors.append("authority_escape_exemption_unknown_construct:" + exemption.exemption_id)
        if not re.fullmatch(r"(?:DS\d+[a-z]?|team-[a-z0-9-]+)", exemption.owner):
            errors.append(f"authority_escape_exemption_owner_invalid:{exemption.exemption_id}")
        if len(exemption.reason.strip()) < 20:
            errors.append(f"authority_escape_exemption_reason_missing:{exemption.exemption_id}")
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", exemption.site_sha256):
            errors.append(f"authority_escape_exemption_hash_invalid:{exemption.exemption_id}")
        identity = _escape_identity(exemption)
        if identity in exemption_by_identity:
            errors.append(f"authority_escape_exemption_identity_duplicate:{exemption.exemption_id}")
        exemption_by_identity[identity] = exemption

    live_by_identity = {_escape_identity(site): site for site in sites if isinstance(site, Mapping)}
    required_identities: set[tuple[Any, ...]] = set()
    for identity, site in live_by_identity.items():
        construct = site.get("construct")
        is_unsafe_satisfies = construct == "satisfies" and site.get("safety") in {
            "unsafe_brand",
            "unsafe_exhaustiveness_lookalike",
            "unsafe_widening",
        }
        requires_exemption = construct != "satisfies" or is_unsafe_satisfies
        if not requires_exemption:
            continue
        required_identities.add(identity)
        if identity not in exemption_by_identity:
            errors.append(
                "authority_escape_unregistered:"
                f"{site.get('path')}:{site.get('line')}:{site.get('column')}:"
                f"{construct}:{site.get('target')}"
            )

    for identity, exemption in exemption_by_identity.items():
        if exemption.path not in path_names:
            errors.append(f"authority_escape_exemption_unknown_path:{exemption.exemption_id}")
        if identity not in live_by_identity:
            errors.append(f"authority_escape_exemption_stale:{exemption.exemption_id}")
        elif identity not in required_identities:
            errors.append(f"authority_escape_exemption_not_required:{exemption.exemption_id}")
    return sorted(set(errors))


def _semantic_copy_declaration_facts(
    *, source: str, generated_types: str
) -> tuple[list[str], Mapping[str, Any]]:
    """Run a bounded TypeScript declaration proof over the exact issuer and DTO."""
    issuer_path = status_checker.REPO_ROOT / AUTHORITY_SEMANTIC_COPY_PATH
    try:
        completed = subprocess.run(
            ["node", "-e", _SEMANTIC_COPY_DECLARATION_PROBE],
            cwd=status_checker.REPO_ROOT / "apps/runtime-dashboard",
            input=json.dumps(
                {
                    "issuerPath": str(issuer_path),
                    "overrides": {
                        str(issuer_path): source,
                        str(GENERATED_RUNTIME_TYPES_PATH): generated_types,
                    },
                }
            ),
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
        facts = json.loads(completed.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        return [f"authority_semantic_copy_declaration_probe_failed:{error}"], {}
    if completed.returncode != 0 or not isinstance(facts, Mapping):
        return ["authority_semantic_copy_declaration_probe_invalid"], {}
    return [], facts


def _authority_semantic_copy_errors(
    *,
    registry: Mapping[str, Any],
    source: str,
    generated_types: str,
) -> list[str]:
    """Validate registry integrity and declaration identities, never copy wording."""
    errors = status_checker._schema_errors(
        registry,
        AUTHORITY_SEMANTIC_COPY_SCHEMA_PATH,
        "authority-semantic-copy-registry",
    )
    declaration_errors, facts = _semantic_copy_declaration_facts(
        source=source, generated_types=generated_types
    )
    errors.extend(declaration_errors)
    expected_exports = {
        "AuthoritySemanticCopy",
        "AuthoritySemanticReviewReceipt",
        "ReviewReceiptInput",
        "admitAuthoritySemanticReviewReceipt",
        "assertIssuedAuthoritySemanticCopy",
        "presentMayNotUseFor",
        "presentSemanticCopy",
    }
    issuer_path = str(status_checker.REPO_ROOT / AUTHORITY_SEMANTIC_COPY_PATH)
    generated_alias_path = str(
        status_checker.REPO_ROOT / "packages/runtime-api-client/canonicalRuntimeApiClient.ts"
    )
    generated_field_path = str(GENERATED_RUNTIME_TYPES_PATH)
    if (
        facts.get("compilerDiagnostics")
        or set(facts.get("exports", [])) != expected_exports
        or facts.get("brandPrivateUnique") is not True
        or facts.get("brandPath") != issuer_path
        or facts.get("storePrivate") is not True
        or facts.get("factoryReturnDeclarations") != [issuer_path]
        or facts.get("factoryParameterDeclarations") != [issuer_path]
        or facts.get("generatedDeclarations") != [generated_alias_path]
        or facts.get("generatedFieldDeclarations") != [generated_field_path]
    ):
        errors.append("authority_semantic_copy_declaration_identity_drift")
    if facts.get("canonicalConstruction") is not True:
        errors.append("authority_semantic_copy_issuance_construction_drift")

    copies = registry.get("copies")
    if not isinstance(copies, list):
        return sorted(set([*errors, "authority_semantic_copy_rows_invalid"]))
    if registry.get("capability_state") != "consumer_missing":
        errors.append("authority_semantic_copy_capability_state_drift")

    active_keys: set[tuple[str, str, str]] = set()
    accepted_receipts = 0
    for copy_row in copies:
        if not isinstance(copy_row, Mapping):
            errors.append("authority_semantic_copy_row_invalid")
            continue
        review = copy_row.get("review")
        source_declaration = copy_row.get("source_declaration")
        if not isinstance(review, Mapping) or not isinstance(source_declaration, Mapping):
            errors.append("authority_semantic_copy_receipt_invalid")
            continue
        if source_declaration != {
            "contract_module": "@polisyos/runtime-api-client",
            "schema": "AvailableGovernedProjectionPacket",
            "field": "may_not_use_for",
        }:
            errors.append("authority_semantic_copy_source_declaration_drift")
        if copy_row.get("semantic_class") != "rights_bar":
            errors.append("authority_semantic_copy_class_drift")
        if copy_row.get("strength") != "limited":
            errors.append("authority_semantic_copy_strength_upgrade")
        output = copy_row.get("reviewed_output")
        content_hash = copy_row.get("content_sha256")
        if not isinstance(output, str) or content_hash != "sha256:" + hashlib.sha256(
            output.encode("utf-8")
        ).hexdigest():
            errors.append("authority_semantic_copy_content_hash_drift")
        if copy_row.get("active") is True:
            key = (
                str(copy_row.get("semantic_id")),
                str(copy_row.get("locale")),
                str(copy_row.get("scope")),
            )
            if key in active_keys:
                errors.append("authority_semantic_copy_duplicate_active_tuple")
            active_keys.add(key)
        if review.get("status") == "accepted":
            accepted_receipts += 1
        elif review.get("status") == "verification_missing":
            expected_scope = "authority-copy." + str(copy_row.get("locale")) + "." + str(
                copy_row.get("scope")
            )
            if (
                review.get("reviewer_identity") != "external-reviewer:unreceived"
                or review.get("reviewer_version") != "unreceived"
                or review.get("reviewer_scope") != expected_scope
            ):
                errors.append("authority_semantic_copy_unreceived_reviewer_drift")
    if accepted_receipts != 0:
        errors.append("authority_semantic_copy_accepted_receipt_count_drift")
    return sorted(set(errors))


def _authority_semantic_copy_runtime_errors() -> list[str]:
    """Execute the issuer's real runtime witnesses without modeling value flow."""
    try:
        completed = subprocess.run(
            [
                "corepack",
                "pnpm",
                "exec",
                "vitest",
                "run",
                "src/shared/ui/AuthoritySemanticCopy.test.ts",
                "--maxWorkers=1",
                "--reporter=default",
            ],
            cwd=status_checker.REPO_ROOT / "apps/runtime-dashboard",
            capture_output=True,
            check=False,
            text=True,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return [f"authority_semantic_copy_runtime_harness_failed:{error}"]
    if completed.returncode != 0:
        return ["authority_semantic_copy_runtime_harness_failed"]
    return []


def _authority_local_state_runtime_errors() -> list[str]:
    """Execute the scoped local-state envelope witnesses through the real dashboard runtime."""
    try:
        completed = subprocess.run(
            [
                "corepack",
                "pnpm",
                "exec",
                "vitest",
                "run",
                "src/app/offline/authorityLocalState.test.ts",
                "src/features/runs/domain/operatorCraft.test.ts",
                "--maxWorkers=1",
                "--reporter=default",
            ],
            cwd=status_checker.REPO_ROOT / "apps/runtime-dashboard",
            capture_output=True,
            check=False,
            text=True,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return [f"authority_local_state_runtime_harness_failed:{error}"]
    if completed.returncode != 0:
        return ["authority_local_state_runtime_harness_failed"]
    return []


def _tracked_atlas_plan_paths() -> tuple[Path, ...]:
    """Return every tracked Markdown plan, without using plan filenames as identity."""
    completed = subprocess.run(
        ["git", "ls-files", "-z", "--", "docs/plans"],
        cwd=status_checker.REPO_ROOT,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("slice_scope_obligation_plan_enumeration_failed")
    return tuple(
        status_checker.REPO_ROOT / path
        for path in completed.stdout.decode("utf-8").split("\0")
        if path.endswith(".md")
    )


def _yaml_frontmatter(path: Path) -> Mapping[str, Any] | None:
    """Parse one complete YAML frontmatter block, if the Markdown document has one."""
    source = path.read_text(encoding="utf-8")
    match = re.match(
        r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", source, re.DOTALL
    )
    if match is None:
        return None
    parsed = yaml.safe_load(match.group(1))
    return parsed if isinstance(parsed, Mapping) else None


def validate_slice_scope_obligations(
    *,
    manifest: Mapping[str, Any] | None = None,
    plan_paths: Sequence[Path] | None = None,
) -> list[str]:
    """Require target slice plans to declare the manifest-owned DS8 residual inputs.

    A plan acknowledgement is candidate-only: this validator records scope-setting
    only and never treats the declaration as closure or implementation evidence.
    """
    actual_manifest = dict(
        manifest or status_checker._load_json(SLICE_SCOPE_OBLIGATIONS_PATH)
    )
    errors = status_checker._schema_errors(
        actual_manifest,
        SLICE_SCOPE_OBLIGATIONS_SCHEMA_PATH,
        "slice-scope-obligations",
    )
    if errors:
        return errors
    required_inputs = actual_manifest["atlas_residual_inputs"]
    target_slices = actual_manifest["target_slices"]
    target_plans: dict[str, list[tuple[Path, Mapping[str, Any]]]] = {
        slice_id: [] for slice_id in target_slices
    }
    for path in plan_paths if plan_paths is not None else _tracked_atlas_plan_paths():
        try:
            frontmatter = _yaml_frontmatter(path)
        except (OSError, yaml.YAMLError):
            # A malformed non-slice document cannot establish that one of the
            # target plans exists; target absence deliberately remains open.
            continue
        if frontmatter is None or frontmatter.get("type") != "slice-plan":
            continue
        slice_id = frontmatter.get("slice")
        if slice_id in target_plans:
            target_plans[slice_id].append((path, frontmatter))

    required_set = set(required_inputs)
    for slice_id, plans in target_plans.items():
        if len(plans) > 1:
            errors.append(f"slice_scope_obligation_target_duplicate:{slice_id}")
            continue
        if not plans:
            continue
        path, frontmatter = plans[0]
        inputs = frontmatter.get("atlas_residual_inputs")
        if not isinstance(inputs, list):
            errors.append(f"slice_scope_obligation_inputs_missing:{slice_id}:{path}")
            continue
        if not all(isinstance(input_id, str) for input_id in inputs):
            errors.append(f"slice_scope_obligation_inputs_not_exact:{slice_id}:{path}")
            continue
        if (
            len(inputs) != len(required_set)
            or len(set(inputs)) != len(inputs)
            or set(inputs) != required_set
        ):
            errors.append(f"slice_scope_obligation_inputs_not_exact:{slice_id}:{path}")
    return sorted(set(errors))


def validate_enforcement(
    *,
    source_overrides: Mapping[str, str] | None = None,
    enforce_authority_escapes: bool | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Validate the governed DS4 bridge and declaration-level DS5 census."""
    inventory = status_checker._load_json(status_checker.INVENTORY_PATH)
    debt = status_checker._load_json(status_checker.WAIST_DEBT_PATH)
    typescript_overrides = (
        None
        if source_overrides is None
        else {
            path: source
            for path, source in source_overrides.items()
            if path.endswith((".ts", ".tsx"))
        }
    )
    scan = _enforcement_scan(
        typescript_overrides,
        inventory=inventory,
        validate_override_diagnostics=source_overrides is not None,
    )
    scan["generatedOwnerReceipt"] = _generated_owner_receipt(inventory)
    errors = _override_diagnostic_errors(scan)
    python_sources, render_sources = _capability_discovery_live_sources(source_overrides)
    manifest_contributors = control_capability_manifest_contributors(python_sources)
    render_errors = check_capability_discovery_result_boundary(render_sources)
    scan["capabilityManifestContributors"] = list(manifest_contributors)
    scan["capabilityDiscoveryRenderErrors"] = render_errors
    errors.extend(
        f"authored_capability_manifest_feature:{contributor}"
        for contributor in manifest_contributors
    )
    errors.extend(render_errors)
    should_enforce_escapes = (
        source_overrides is None if enforce_authority_escapes is None else enforce_authority_escapes
    )
    if should_enforce_escapes:
        errors.extend(
            _authority_escape_errors(
                scan,
                exemptions=(AUTHORITY_ESCAPE_EXEMPTIONS if source_overrides is None else ()),
                enforce_denominator=source_overrides is None,
            )
        )
    errors.extend(
        _capability_discovery_errors(
            scan,
            enforce_denominator=source_overrides is None,
        )
    )
    if source_overrides is None:
        scope_obligation_errors = validate_slice_scope_obligations()
        scan["sliceScopeObligationErrors"] = scope_obligation_errors
        errors.extend(scope_obligation_errors)
        errors.extend(_authz_default_allow_errors(scan))
        errors.extend(_query_cache_policy_errors(scan, enforce_denominator=True))
        errors.extend(_offline_queue_errors(scan, enforce_denominator=True))
        errors.extend(
            _persistence_construction_errors(
                scan,
                register=disposition_checker._load_json(disposition_checker.REGISTER_PATH),
            )
        )
    if source_overrides is None:
        errors.extend(_authority_issuer_errors(scan))
        errors.extend(
            _authority_semantic_copy_errors(
                registry=status_checker._load_json(AUTHORITY_SEMANTIC_COPY_REGISTRY_PATH),
                source=(status_checker.REPO_ROOT / AUTHORITY_SEMANTIC_COPY_PATH).read_text(
                    encoding="utf-8"
                ),
                generated_types=GENERATED_RUNTIME_TYPES_PATH.read_text(encoding="utf-8"),
            )
        )
        errors.extend(status_checker.validate_inventory(inventory, debt, live_probes=True))
        disposition = disposition_checker._load_json(disposition_checker.REGISTER_PATH)
        errors.extend(
            disposition_checker._authority_presentation_errors(
                disposition,
                live_probes=True,
                scan=scan,
            )
        )
    return sorted(set(errors)), scan


def _run_architecture_json(
    command: Sequence[str],
    *,
    cwd: Path,
    engine_id: str,
) -> tuple[list[str], dict[str, Any]]:
    """Execute one real architecture engine and parse its structured packet."""
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return [f"architecture_engine_execution_failed:{engine_id}:{error}"], {}
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return [f"architecture_engine_unparseable:{engine_id}"], {}
    if not isinstance(parsed, Mapping):
        return [f"architecture_engine_packet_invalid:{engine_id}"], {}
    return [], {**parsed, "returnCode": completed.returncode}


def _architecture_engine_packets(
    *,
    dashboard_root: Path,
    atlas_source_root: Path,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Run the three bounded module-graph engines over the supplied roots."""
    repo_root = status_checker.REPO_ROOT
    dashboard_script = repo_root / "apps/runtime-dashboard/scripts/check-architecture.mjs"
    dashboard_config = repo_root / "apps/runtime-dashboard/.dependency-cruiser.mjs"
    dependency_binary = repo_root / "apps/runtime-dashboard/node_modules/.bin/depcruise"
    atlas_script = repo_root / "packages/atlas-ui/scripts/check-architecture.mjs"
    commands = {
        "dashboard-custom": (
            ["node", str(dashboard_script), "--format=json"],
            dashboard_root,
        ),
        "dependency-cruiser": (
            [
                str(dependency_binary),
                "--config",
                str(dashboard_config),
                "--output-type",
                "json",
                "src",
            ],
            dashboard_root,
        ),
        "atlas-ui": (
            [
                "node",
                str(atlas_script),
                "--source-root",
                str(atlas_source_root),
                "--format=json",
            ],
            repo_root,
        ),
    }

    packets: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=len(commands)) as executor:
        futures = {
            engine_id: executor.submit(
                _run_architecture_json,
                command,
                cwd=cwd,
                engine_id=engine_id,
            )
            for engine_id, (command, cwd) in commands.items()
        }
        for engine_id, future in futures.items():
            engine_errors, packet = future.result()
            errors.extend(engine_errors)
            packets[engine_id] = packet
    return errors, packets


def _architecture_packet_facts(
    packets: Mapping[str, Mapping[str, Any]],
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Normalize only the decidable facts emitted by the real engines."""
    errors: list[str] = []
    facts: dict[str, dict[str, Any]] = {}

    custom = packets.get("dashboard-custom", {})
    custom_violations = custom.get("violations")
    if (
        custom.get("producer") != "runtime-dashboard-custom-import-boundary"
        or not isinstance(custom_violations, Sequence)
        or isinstance(custom_violations, (str, bytes))
    ):
        errors.append("architecture_engine_packet_invalid:dashboard-custom")
    else:
        custom_rows_valid = all(
            isinstance(row, Mapping)
            and isinstance(row.get("rule_id"), str)
            and bool(row["rule_id"])
            for row in custom_violations
        )
        custom_rules = sorted(
            str(row.get("rule_id"))
            for row in custom_violations
            if isinstance(row, Mapping)
        )
        if not custom_rows_valid:
            errors.append("architecture_engine_violation_invalid:dashboard-custom")
        custom_source_files = custom.get("sourceFiles")
        if (
            type(custom_source_files) is not int
            or custom_source_files <= 0
        ):
            errors.append("architecture_engine_source_count_invalid:dashboard-custom")
        expected_custom_return = 1 if custom_violations else 0
        if (
            type(custom.get("returnCode")) is not int
            or custom.get("returnCode") != expected_custom_return
        ):
            errors.append("architecture_engine_return_code_invalid:dashboard-custom")
        facts["dashboard-custom"] = {
            "return_code": custom.get("returnCode"),
            "source_files": custom_source_files,
            "violation_rules": custom_rules,
        }

    dependency = packets.get("dependency-cruiser", {})
    dependency_summary = dependency.get("summary")
    dependency_modules = dependency.get("modules")
    dependency_violations = (
        dependency_summary.get("violations")
        if isinstance(dependency_summary, Mapping)
        else None
    )
    if (
        not isinstance(dependency_summary, Mapping)
        or not isinstance(dependency_modules, Sequence)
        or isinstance(dependency_modules, (str, bytes))
        or not isinstance(dependency_violations, Sequence)
        or isinstance(dependency_violations, (str, bytes))
    ):
        errors.append("architecture_engine_packet_invalid:dependency-cruiser")
    else:
        dependency_rows_valid = all(
            isinstance(row, Mapping)
            and isinstance((rule := row.get("rule")), Mapping)
            and isinstance(rule.get("name"), str)
            and bool(rule["name"])
            for row in dependency_violations
        )
        dependency_rules = sorted(
            str(rule.get("name"))
            for row in dependency_violations
            if isinstance(row, Mapping)
            and isinstance((rule := row.get("rule")), Mapping)
        )
        if not dependency_rows_valid:
            errors.append("architecture_engine_violation_invalid:dependency-cruiser")
        module_sources = [
            module.get("source")
            for module in dependency_modules
            if isinstance(module, Mapping)
        ]
        dependency_containers_valid = all(
            isinstance(module, Mapping)
            and isinstance(module.get("dependencies"), Sequence)
            and not isinstance(module.get("dependencies"), (str, bytes))
            for module in dependency_modules
        )
        module_identities_valid = (
            len(module_sources) == len(dependency_modules)
            and all(isinstance(source, str) and bool(source) for source in module_sources)
            and len(set(module_sources)) == len(module_sources)
        )
        modules_valid = dependency_containers_valid and module_identities_valid
        if not modules_valid:
            errors.append("architecture_engine_module_invalid:dependency-cruiser")
        dependency_rows = [
            dependency
            for module in dependency_modules
            if isinstance(module, Mapping)
            and isinstance(module.get("dependencies"), Sequence)
            and not isinstance(module.get("dependencies"), (str, bytes))
            for dependency in module["dependencies"]
        ]
        if not all(
            isinstance(dependency, Mapping)
            and isinstance(dependency.get("resolved"), str)
            and bool(dependency["resolved"])
            for dependency in dependency_rows
        ):
            errors.append("architecture_engine_dependency_invalid:dependency-cruiser")
        if len(dependency_modules) <= 0:
            errors.append("architecture_engine_source_count_invalid:dependency-cruiser")
        reported_errors = dependency_summary.get("error")
        if (
            type(reported_errors) is not int
            or reported_errors < 0
            or reported_errors != len(dependency_violations)
        ):
            errors.append(
                "architecture_engine_reported_error_count_invalid:dependency-cruiser"
            )
        if type(dependency.get("returnCode")) is not int or dependency.get(
            "returnCode"
        ) != 0:
            errors.append("architecture_engine_return_code_invalid:dependency-cruiser")
        facts["dependency-cruiser"] = {
            "return_code": dependency.get("returnCode"),
            "reported_errors": reported_errors,
            "source_files": len(dependency_modules),
            "dependency_edges": len(dependency_rows),
            "violation_rules": dependency_rules,
        }

    atlas = packets.get("atlas-ui", {})
    atlas_violations = atlas.get("violations")
    if (
        atlas.get("producer") != "atlas-ui-import-boundary"
        or not isinstance(atlas_violations, Sequence)
        or isinstance(atlas_violations, (str, bytes))
    ):
        errors.append("architecture_engine_packet_invalid:atlas-ui")
    else:
        atlas_rows_valid = all(
            isinstance(row, Mapping)
            and isinstance(row.get("rule_id"), str)
            and bool(row["rule_id"])
            for row in atlas_violations
        )
        atlas_rules = sorted(
            str(row.get("rule_id"))
            for row in atlas_violations
            if isinstance(row, Mapping)
        )
        if not atlas_rows_valid:
            errors.append("architecture_engine_violation_invalid:atlas-ui")
        atlas_source_files = atlas.get("sourceFiles")
        if type(atlas_source_files) is not int or atlas_source_files <= 0:
            errors.append("architecture_engine_source_count_invalid:atlas-ui")
        expected_atlas_return = 1 if atlas_violations else 0
        if (
            type(atlas.get("returnCode")) is not int
            or atlas.get("returnCode") != expected_atlas_return
        ):
            errors.append("architecture_engine_return_code_invalid:atlas-ui")
        facts["atlas-ui"] = {
            "return_code": atlas.get("returnCode"),
            "source_files": atlas_source_files,
            "violation_rules": atlas_rules,
        }

    return errors, facts


def _write_architecture_fixture(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(source).strip() + "\n", encoding="utf-8")


def _populate_architecture_fixture(
    dashboard_root: Path,
    atlas_source_root: Path,
    *,
    illegal: bool,
) -> None:
    """Write the measured bad or benign graph without changing rule markers."""
    write = _write_architecture_fixture
    write(
        dashboard_root / "tsconfig.app.json",
        '{"compilerOptions":{"module":"ESNext","moduleResolution":"Bundler"}}',
    )
    write(
        dashboard_root / "src/app/providers/provider.ts",
        "export const provider = 'provider';",
    )
    write(dashboard_root / "src/shared/peer.ts", "export const peer = 'peer';")
    write(
        dashboard_root / "src/shared/benign.ts",
        """
        import { peer } from "./peer";
        export const errorBudgetWidth = 3;
        export const responsiveColumns = [1, 2, 3] as const;
        export { peer };
        """,
    )
    write(
        dashboard_root / "src/features/example/index.ts",
        "export const publicFeature = 'public';",
    )
    write(
        dashboard_root / "src/features/example/internal.ts",
        "export const privateFeature = 'private';",
    )
    write(
        dashboard_root / "src/app/routes.ts",
        'export { publicFeature } from "../features/example";',
    )
    prefix = "" if illegal else "// retained rule witness: "
    write(
        dashboard_root / "src/app/feature-internal.ts",
        f'{prefix}import {{ privateFeature }} from "../features/example/internal";\n'
        + (
            "export const featureValue = privateFeature;"
            if illegal
            else "export const featureValue = 'public-only';"
        ),
    )
    write(
        dashboard_root / "src/shared/illegal.ts",
        f'{prefix}import {{ provider }} from "../app/providers/provider";\n'
        + (
            "export const sharedValue = provider;"
            if illegal
            else "export const sharedValue = 'shared';"
        ),
    )
    write(
        dashboard_root / "src/app/state/store.ts",
        f'{prefix}import {{ provider }} from "../providers/provider";\n'
        + (
            "export const store = provider;"
            if illegal
            else "export const store = 'store';"
        ),
    )
    write(
        dashboard_root / "src/cycle/a.ts",
        f'{prefix}import {{ b }} from "./b";\n'
        + ('export const a = b;' if illegal else 'export const a = "a";'),
    )
    write(
        dashboard_root / "src/cycle/b.ts",
        f'{prefix}import {{ a }} from "./a";\n'
        + ('export const b = a;' if illegal else 'export const b = "b";'),
    )
    write(
        atlas_source_root / "index.ts",
        'export { safe } from "./primitives/Safe";',
    )
    write(
        atlas_source_root / "primitives/Safe.ts",
        "export const safe = 'safe';",
    )
    write(
        atlas_source_root / "primitives/Illegal.ts",
        (
            'import type { OperatorDiagnostic } from "@polisyos/runtime-api-client";'
            if illegal
            else '// retained rule witness: import type {} from "runtime-api-client";'
        ),
    )


def _architecture_recurrence_errors() -> tuple[list[str], dict[str, Any]]:
    """Recompute live zero and adversarial recurrence from real module graphs."""
    repo_root = status_checker.REPO_ROOT
    live_execution_errors, live_packets = _architecture_engine_packets(
        dashboard_root=repo_root / "apps/runtime-dashboard",
        atlas_source_root=repo_root / "packages/atlas-ui/src",
    )
    live_packet_errors, live = _architecture_packet_facts(live_packets)
    errors = [*live_execution_errors, *live_packet_errors]
    for engine_id, facts in live.items():
        violations = facts.get("violation_rules", facts.get("violations", ()))
        if violations or facts.get("return_code") != 0:
            errors.append(f"architecture_live_graph_red:{engine_id}")
    if live.get("dependency-cruiser", {}).get("reported_errors") != 0:
        errors.append("architecture_live_graph_red:dependency-cruiser-summary")

    with tempfile.TemporaryDirectory(prefix="ds5-c02-") as temporary:
        fixture_root = Path(temporary)
        dashboard_root = fixture_root / "runtime-dashboard"
        atlas_source_root = fixture_root / "atlas-ui/src"
        _populate_architecture_fixture(
            dashboard_root,
            atlas_source_root,
            illegal=True,
        )
        red_execution_errors, red_packets = _architecture_engine_packets(
            dashboard_root=dashboard_root,
            atlas_source_root=atlas_source_root,
        )
        red_packet_errors, red = _architecture_packet_facts(red_packets)
        errors.extend(red_execution_errors)
        errors.extend(red_packet_errors)

        expected_red = {
            "dashboard-custom": {
                "app-no-feature-internals",
                "app-state-no-app-providers",
                "shared-no-app-or-features",
            },
            "dependency-cruiser": {
                "app-no-feature-internals",
                "no-circular",
                "shared-no-app-or-features",
            },
        }
        for engine_id, expected_rules in expected_red.items():
            observed = set(red.get(engine_id, {}).get("violation_rules", ()))
            if observed != expected_rules:
                errors.append(f"architecture_corruption_escaped:{engine_id}")
        atlas_red = red.get("atlas-ui", {})
        if atlas_red.get("violation_rules") != ["atlas-forbidden-import"]:
            errors.append("architecture_corruption_escaped:atlas-ui")
        expected_source_files = {
            "atlas-ui": 3,
            "dashboard-custom": 11,
            "dependency-cruiser": 11,
        }
        if {
            engine_id: facts.get("source_files")
            for engine_id, facts in red.items()
        } != expected_source_files:
            errors.append("architecture_corruption_discovery_drift")
        if red.get("dashboard-custom", {}).get("return_code") != 1:
            errors.append("architecture_corruption_exit_drift:dashboard-custom")
        if atlas_red.get("return_code") != 1:
            errors.append("architecture_corruption_exit_drift:atlas-ui")
        if red.get("dependency-cruiser", {}).get("reported_errors") != 3:
            errors.append("architecture_corruption_summary_drift:dependency-cruiser")

        _populate_architecture_fixture(
            dashboard_root,
            atlas_source_root,
            illegal=False,
        )
        benign_execution_errors, benign_packets = _architecture_engine_packets(
            dashboard_root=dashboard_root,
            atlas_source_root=atlas_source_root,
        )
        benign_packet_errors, benign = _architecture_packet_facts(benign_packets)
        errors.extend(benign_execution_errors)
        errors.extend(benign_packet_errors)
        for engine_id, facts in benign.items():
            violations = facts.get("violation_rules", facts.get("violations", ()))
            if violations or facts.get("return_code") != 0:
                errors.append(f"architecture_benign_graph_red:{engine_id}")
        if benign.get("dependency-cruiser", {}).get("reported_errors") != 0:
            errors.append("architecture_benign_graph_red:dependency-cruiser-summary")

    corruption_rejected = not any(
        error.startswith("architecture_corruption_") for error in errors
    )
    benign_accepted = not any(
        error.startswith("architecture_benign_") for error in errors
    )
    return sorted(set(errors)), {
        "live": live,
        "corruption": red,
        "benign": benign,
        "corruption_witnesses_rejected": corruption_rejected,
        "benign_graphs_accepted": benign_accepted,
    }


def _corruption_probes(
    *,
    architecture_errors: Sequence[str] | None = None,
    architecture_receipt: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return labels for retained-core properties that a corruption escaped."""
    escaped: list[str] = []
    package_path = "packages/atlas-ui/src/index.ts"
    probe_path = "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerCorruptionProbe.tsx"
    angle_probe_path = (
        "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerAngleCorruptionProbe.ts"
    )
    namespace_probe_path = (
        "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerNamespaceCorruptionProbe.tsx"
    )
    nocheck_probe_path = (
        "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerNocheckCorruptionProbe.tsx"
    )
    prose_probe_path = (
        "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerDirectiveProseProbe.tsx"
    )
    type_shapes_path = "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerAuthorityTypes.ts"
    type_shapes = (
        dedent(
            """
            export interface SafeShape { payload: string }
            export interface UnsafeShape { payload: unknown }
            """
        ).strip()
        + "\n"
    )
    exports = (
        dedent(
            """
        export { AuthorityBadge } from "./primitives/AuthorityBadge";
        export type { AuthorityPresentation } from "./primitives/AuthorityBadge";
        export { createOpaqueAuthorityPresentation } from "./primitives/AuthorityBadge";
        export { Button } from "./primitives/Button";
        """
        ).strip()
        + "\n"
    )
    capability_owner_path = status_checker.REPO_ROOT / CAPABILITY_DISCOVERY_OWNER_PATH
    capability_owner_source = capability_owner_path.read_text(encoding="utf-8")
    exported_capability_owner = capability_owner_source.replace(
        "function issueCapabilityDiscovery(", "export function issueCapabilityDiscovery(", 1
    )
    capability_probe_path = (
        "apps/runtime-dashboard/src/shared/lib/domain/capabilityDiscoveryCorruptionProbe.ts"
    )

    _errors, scan = validate_enforcement(
        source_overrides={
            package_path: exports,
            CAPABILITY_DISCOVERY_OWNER_PATH: exported_capability_owner,
            capability_probe_path: dedent(
                """
                import { issueCapabilityDiscovery } from "@/api/hooks/useCapabilities";
                export const discovery = issueCapabilityDiscovery({
                  manifest: { features: [] },
                  state: "available",
                });
                """
            ).strip()
            + "\n",
        }
    )
    capability_errors = _capability_discovery_errors(scan)
    if not any("issuer_unowned" in error for error in capability_errors) or not any(
        "available_manifest_invalid" in error for error in capability_errors
    ):
        escaped.append("capability-discovery-external-issuer")

    feature_probe_path = (
        "apps/runtime-dashboard/src/shared/lib/domain/capabilityFeatureLiteralCorruptionProbe.ts"
    )
    _errors, scan = validate_enforcement(
        source_overrides={
            package_path: exports,
            feature_probe_path: dedent(
                """
                import type { components as Components } from "@/api/types";
                import type * as Api from "@/api/types";
                type FeatureAlias = Components["schemas"]["CapabilityFeatureInfo"];
                const alias: FeatureAlias = {
                  stage: "active", label: "Alias", key: "alias", enabled: true,
                  category: "test", description: "literal",
                };
                const namespaced: Api.components["schemas"]["CapabilityFeatureInfo"] = {
                  key: "namespace", description: "literal", category: "test",
                  enabled: false, label: "Namespace", stage: "planned",
                };
                void alias; void namespaced;
                """
            ).strip()
            + "\n",
        }
    )
    capability_errors = _capability_discovery_errors(scan)
    if len(capability_errors) != 2 or not all(
        "feature_literal_authored" in error for error in capability_errors
    ):
        escaped.append("capability-discovery-feature-literals")

    loading_enabled_owner = capability_owner_source.replace(
        "if (query.isLoading) {",
        "if (Boolean(query.isLoading) && query.data) {\n"
        '    return issueCapabilityDiscovery({ manifest: query.data, state: "available" });\n'
        "  }\n  if (query.isLoading) {",
        1,
    )
    _errors, scan = validate_enforcement(
        source_overrides={
            package_path: exports,
            CAPABILITY_DISCOVERY_OWNER_PATH: loading_enabled_owner,
        }
    )
    if scan.get("overrideDiagnostics") or not any(
        "available_manifest_invalid" in error
        for error in _capability_discovery_errors(scan)
    ):
        escaped.append("capability-discovery-loading-enabled")

    errors, scan = validate_enforcement(
        source_overrides={
            package_path: exports,
            capability_probe_path: dedent(
                """
                import type { CapabilityDiscovery } from "@/api/hooks/useCapabilities";
                declare const runtimeManifest: { features?: unknown[] };
                const fixedChrome = Array.from({ length: 43 }, (_, index) => ({
                  key: `chrome-${index}`, label: "Fixed", enabled: true,
                }));
                const requiredCapabilities = Array.from(
                  { length: 19 }, (_, index) => `gate-${index}`,
                );
                const analyticsFeature = { key: "analytics", label: "Analytics", enabled: true };
                const runtimeFeatures = runtimeManifest.features;
                const lookalike = { state: "available", manifest: { features: [] } };
                const brandedConsumer: CapabilityDiscovery = lookalike;
                void fixedChrome; void requiredCapabilities; void analyticsFeature;
                void runtimeFeatures; void brandedConsumer;
                """
            ).strip()
            + "\n",
        }
    )
    if _capability_discovery_errors(scan) or [
        item.get("code") for item in scan.get("overrideDiagnostics", [])
    ] != [2322] or not any(error.endswith(":TS2322") for error in errors):
        escaped.append("capability-discovery-benign-and-brand")

    python_probe_dir = "src/polisyos/runtime/http/services/control"
    python_rows_path = f"{python_probe_dir}/ds10_corruption_rows.py"
    python_manifest_path = f"{python_probe_dir}/ds10_corruption_manifest.py"
    python_contributors = control_capability_manifest_contributors(
        {
            python_rows_path: dedent(
                """
                from polisyos.core.contracts.control import CapabilityFeatureInfo as Feature
                FeatureAlias = Feature
                marker_only = Feature(
                    key="marker", label="Marker", description="benign", category="probe",
                )
                def rows():
                    return [FeatureAlias(
                        key="generated", label="Generated",
                        description="corruption", category="probe",
                    )]
                """
            ),
            python_manifest_path: dedent(
                """
                from polisyos.core.contracts.control import CapabilityManifestResponse as Manifest
                from .ds10_corruption_rows import rows
                def build(meta):
                    return Manifest(meta=meta, features=rows())
                """
            ),
        }
    )
    if len(python_contributors) != 1 or not python_contributors[0].startswith(
        python_rows_path + ":"
    ):
        escaped.append("capability-discovery-python-manifest-contributor")

    render_dir = "apps/runtime-dashboard/src/features/evidence/components"
    render_root = f"{render_dir}/CapabilityDiscoveryPanel.tsx"
    render_sibling = f"{render_dir}/CapabilityDiscoveryRows.tsx"
    render_values = f"{render_dir}/CapabilityDiscoveryValues.ts"
    fixed_chrome = "apps/runtime-dashboard/src/app/surfaces/workspaceConfig.ts"
    render_errors = check_capability_discovery_result_boundary(
        {
            render_root: (
                'import { selected } from "./CapabilityDiscoveryValues";\n'
                "export function render(result: { resource_kind: string }) {\n"
                "  return result.resource_kind === selected ? null : null;\n"
                "}\n"
            ),
            render_sibling: (
                'const selected = "capability-corruption-probe";\n'
                'const row = { ["capability_ref"]: selected, ["resource_kind"]: "agent" };\n'
                "export const rows = [row];\n"
            ),
            render_values: 'export const selected = "agent";\n',
            fixed_chrome: (
                "type WorkspaceConfig = { route: string; tab: string };\n"
                'export const workspace: WorkspaceConfig = { route: "runs", tab: "overview" };\n'
            ),
        }
    )
    if not render_errors or any(fixed_chrome in error for error in render_errors):
        escaped.append("capability-discovery-generic-render-boundary")

    errors, scan = validate_enforcement(
        source_overrides={
            package_path: exports,
            probe_path: dedent(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const props: { presentation?: Atlas.AuthorityPresentation } = {};
                export const Probe = () => <Atlas.AuthorityBadge {...props} />;
                """
            ).strip()
            + "\n",
        }
    )
    if [item.get("code") for item in scan.get("overrideDiagnostics", [])] != [2322] or not any(
        error.endswith(":TS2322") for error in errors
    ):
        escaped.append("override-diagnostics")

    errors, scan = validate_enforcement(
        source_overrides={
            package_path: exports,
            probe_path: dedent(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                function LocalControl({ disabled: _disabled }: { disabled?: boolean }) {
                  return <div />;
                }
                const presentation = {} as Atlas.AuthorityPresentation;
                export const Probe = () => <>
                  <Atlas.AuthorityBadge presentation={presentation} />
                  <Atlas.Button disabled>Review</Atlas.Button>
                  <LocalControl disabled />
                </>;
                """
            ).strip()
            + "\n",
        }
    )
    pairs = {
        (row.get("componentDeclarationPath"), row.get("prop"))
        for row in scan.get("authoritySinkDeclarations", [])
        if isinstance(row, Mapping)
    }
    if (
        errors
        or (
            "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
            "presentation",
        )
        not in pairs
        or (
            "packages/atlas-ui/src/primitives/Button.tsx",
            "disabled",
        )
        not in pairs
        or any("packageOwnerCorruptionProbe" in str(path) for path, _ in pairs)
    ):
        escaped.append("real-atlas-declaration-census")

    inventory = status_checker._load_json(status_checker.INVENTORY_PATH)
    debt = status_checker._load_json(status_checker.WAIST_DEBT_PATH)
    corrupted = copy.deepcopy(inventory)
    corrupted["sources"]["generated_client"]["canonical_sha256"] = "sha256:" + "0" * 64
    expected = (
        "inventory_source_hash_drift:" + inventory["sources"]["generated_client"]["canonical_path"]
    )
    if expected not in status_checker.validate_inventory(corrupted, debt, live_probes=False):
        escaped.append("generated-owner-content-binding")

    errors, scan = validate_enforcement(
        source_overrides={
            package_path: exports,
            type_shapes_path: type_shapes,
            probe_path: dedent(
                """
                import type { RunOperatorProjectionStateLabel } from "@polisyos/runtime-api-client";
                import * as Atlas from "@polisyos/atlas-ui";
                type BrandAlias = Readonly<Atlas.AuthorityPresentation>;
                type WideningAlias = any;
                declare const widening: unknown;
                declare const safe: { payload: string };
                const issued = Atlas.createOpaqueAuthorityPresentation("owner");
                const asserted = {} as unknown as Atlas.AuthorityPresentation;
                const anyTyped: any = issued;
                // @ts-ignore bounded corruption witness
                const ignored: Atlas.AuthorityPresentation = {};
                // @ts-expect-error bounded corruption witness
                const expected: Atlas.AuthorityPresentation = {};
                const branded = issued satisfies BrandAlias;
                const widened = issued satisfies WideningAlias;
                const queried = "owner" satisfies typeof widening;
                const imported = { payload: "owner" } satisfies
                  import("./packageOwnerAuthorityTypes").UnsafeShape;
                const safeQuery = { payload: "owner" } satisfies typeof safe;
                const safeImport = { payload: "owner" } satisfies
                  import("./packageOwnerAuthorityTypes").SafeShape;
                const generated = {
                  authority: "runtime_authority",
                  label: "owner label",
                  state: "rejected",
                } satisfies RunOperatorProjectionStateLabel;
                export const Probe = () => <Atlas.AuthorityBadge presentation={issued} />;
                void asserted; void anyTyped; void ignored; void expected;
                void branded; void widened; void generated;
                void queried; void imported; void safeQuery; void safeImport;
                """
            ).strip()
            + "\n",
        },
        enforce_authority_escapes=True,
    )
    escape_sites = scan.get("authorityEscapeSites", [])
    observed = {
        str(site.get("construct"))
        for site in escape_sites
        if isinstance(site, Mapping)
        and (
            site.get("construct") != "satisfies"
            or str(site.get("safety", "")).startswith("unsafe_")
        )
    }
    if not {
        "as_assertion",
        "explicit_any",
        "ts_ignore",
        "ts_expect_error",
        "satisfies",
    }.issubset(observed) or not any(
        error.startswith("authority_escape_unregistered:") for error in errors
    ):
        escaped.append("authority-escape-syntax")
    if any(error.startswith("invalid_source_override:") for error in errors):
        escaped.append("authority-escape-witness-diagnostics")
    if not any(
        isinstance(site, Mapping)
        and site.get("construct") == "satisfies"
        and site.get("safety") == "generated_conformance"
        for site in escape_sites
    ):
        escaped.append("authority-escape-benign-generated-conformance")
    resolved_safety = {
        str(site.get("target")): str(site.get("safety"))
        for site in escape_sites
        if isinstance(site, Mapping) and site.get("construct") == "satisfies"
    }
    if resolved_safety.get("typeof widening") != "unsafe_widening" or (
        resolved_safety.get('import("./packageOwnerAuthorityTypes").UnsafeShape')
        != "unsafe_widening"
    ):
        escaped.append("authority-escape-resolved-widening")
    if resolved_safety.get("typeof safe") != "unrelated_conformance" or (
        resolved_safety.get('import("./packageOwnerAuthorityTypes").SafeShape')
        != "unrelated_conformance"
    ):
        escaped.append("authority-escape-resolved-benign")

    errors, scan = validate_enforcement(
        source_overrides={
            package_path: exports,
            angle_probe_path: dedent(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const issued = Atlas.createOpaqueAuthorityPresentation("owner");
                const presentation = <Atlas.AuthorityPresentation>issued;
                void presentation;
                """
            ).strip()
            + "\n",
            namespace_probe_path: dedent(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const Sink = Atlas["AuthorityBadge"];
                const forged: any = {};
                export const Probe = () => <Sink presentation={forged} />;
                """
            ).strip()
            + "\n",
            nocheck_probe_path: dedent(
                """
                // @ts-nocheck bounded corruption witness
                import * as Atlas from "@polisyos/atlas-ui";
                const presentation: Atlas.AuthorityPresentation = {};
                export const Probe = () =>
                  <Atlas.AuthorityBadge presentation={presentation} />;
                """
            ).strip()
            + "\n",
            prose_probe_path: dedent(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                // Documentation says never spell `@ts-ignore` here.
                const presentation =
                  Atlas.createOpaqueAuthorityPresentation("owner");
                export const Probe = () =>
                  <Atlas.AuthorityBadge presentation={presentation} />;
                """
            ).strip()
            + "\n",
        },
        enforce_authority_escapes=True,
    )
    if any(error.startswith("invalid_source_override:") for error in errors):
        escaped.append("authority-escape-local-witness-diagnostics")
    local_sites = [
        site for site in scan.get("authorityEscapeSites", []) if isinstance(site, Mapping)
    ]
    expected_local_constructs = {
        angle_probe_path: "type_assertion",
        namespace_probe_path: "explicit_any",
        nocheck_probe_path: "ts_nocheck",
    }
    if any(
        not any(
            site.get("path") == expected_path and site.get("construct") == expected_construct
            for site in local_sites
        )
        for expected_path, expected_construct in expected_local_constructs.items()
    ) or any(site.get("path") == prose_probe_path for site in local_sites):
        escaped.append("authority-escape-local-syntax")
    authority_paths = {
        str(row.get("path"))
        for row in scan.get("authorityPathFiles", [])
        if isinstance(row, Mapping)
    }
    if namespace_probe_path not in authority_paths:
        escaped.append("authority-escape-namespace-element-import")
    if not any(error.startswith("authority_escape_unregistered:") for error in errors):
        escaped.append("authority-escape-local-rejection")

    _production_errors, production_scan = validate_enforcement(enforce_authority_escapes=False)
    first_exemption = AUTHORITY_ESCAPE_EXEMPTIONS[0]
    moved = first_exemption._replace(line=first_exemption.line + 1)
    moved_errors = _authority_escape_errors(
        production_scan,
        exemptions=(moved, *AUTHORITY_ESCAPE_EXEMPTIONS[1:]),
    )
    if not any(
        error == f"authority_escape_exemption_stale:{first_exemption.exemption_id}"
        for error in moved_errors
    ):
        escaped.append("authority-escape-exemption-binding")

    query_registry = status_checker._load_json(QUERY_CACHE_POLICY_REGISTER_PATH)
    query_corruptions: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    added_source = copy.deepcopy(production_scan)
    added_source["queryCachePolicyFacts"]["constructions"].append(
        copy.deepcopy(added_source["queryCachePolicyFacts"]["constructions"][0])
    )
    query_corruptions.append((added_source, query_registry))
    reordered_register = copy.deepcopy(query_registry)
    reordered_register["constructions"].reverse()
    query_corruptions.append((production_scan, reordered_register))
    retagged_register = copy.deepcopy(query_registry)
    retagged_register["constructions"][0]["resolved_callee"] = (
        "useQuery"
        if retagged_register["constructions"][0]["resolved_callee"] == "queryOptions"
        else "queryOptions"
    )
    query_corruptions.append((production_scan, retagged_register))
    untyped_exemption = copy.deepcopy(query_registry)
    untyped_exemption["exemptions"] = [{"reason": "untyped"}]
    query_corruptions.append((production_scan, untyped_exemption))
    removed_producer = copy.deepcopy(query_registry)
    removed_producer["producers"].pop()
    query_corruptions.append((production_scan, removed_producer))
    if any(
        not _query_cache_policy_errors(
            corrupted_scan,
            enforce_denominator=True,
            registry=corrupted_register,
        )
        for corrupted_scan, corrupted_register in query_corruptions
    ):
        escaped.append("query-cache-policy-register")

    query_target_source = (
        status_checker.REPO_ROOT / QUERY_CACHE_POLICY_TARGET_PATH
    ).read_text(encoding="utf-8")
    query_source_corruptions = (
        query_target_source.replace(
            "  const query = useQuery(options);",
            "  const duplicateQuery = useQuery(options);\n"
            "  const query = useQuery(options);",
            1,
        ),
        query_target_source.replace(
            "useQuery(options)",
            "useQuery({ queryKey: options.queryKey, queryFn: options.queryFn })",
            1,
        ),
    )
    inventory = status_checker._load_json(status_checker.INVENTORY_PATH)
    if any(
        not _query_cache_policy_errors(
            _enforcement_scan(
                {QUERY_CACHE_POLICY_TARGET_PATH: source},
                inventory=inventory,
                validate_override_diagnostics=True,
            ),
            enforce_denominator=True,
            registry=query_registry,
        )
        for source in query_source_corruptions
    ):
        escaped.append("query-cache-policy-source-identity")

    issuer_path = "packages/atlas-ui/src/primitives/AuthorityBadge.tsx"
    issuer_source = (status_checker.REPO_ROOT / issuer_path).read_text(encoding="utf-8")
    corrupted_issuer = issuer_source.replace(
        'satisfies Record<OperatorProjectionLabel["state"], BadgeTone>;',
        'satisfies Partial<Record<OperatorProjectionLabel["state"], BadgeTone>>;',
        1,
    ).replace("return Object.freeze(issued);", "return issued;", 1)
    issuer_override_errors, issuer_scan = validate_enforcement(
        source_overrides={
            package_path: (status_checker.REPO_ROOT / package_path).read_text(encoding="utf-8"),
            issuer_path: corrupted_issuer,
        },
        enforce_authority_escapes=False,
    )
    issuer_fact_errors = set(_authority_issuer_errors(issuer_scan))
    if issuer_override_errors:
        escaped.append("authority-issuer-witness-diagnostics")
    if (
        "authority_issuer_exhaustive_tone_map_drift" not in issuer_fact_errors
        or "authority_issuer_constructor_return_not_frozen:createPresentation"
        not in issuer_fact_errors
    ):
        escaped.append("authority-issuer-construction-sites")

    semantic_registry = status_checker._load_json(AUTHORITY_SEMANTIC_COPY_REGISTRY_PATH)
    semantic_source = (status_checker.REPO_ROOT / AUTHORITY_SEMANTIC_COPY_PATH).read_text(
        encoding="utf-8"
    )
    semantic_generated_types = GENERATED_RUNTIME_TYPES_PATH.read_text(encoding="utf-8")
    semantic_corruptions: dict[str, Mapping[str, Any]] = {}
    class_upgrade = copy.deepcopy(semantic_registry)
    class_upgrade["copies"][0]["strength"] = "strong"
    semantic_corruptions["class-upgrade"] = class_upgrade
    stale_hash = copy.deepcopy(semantic_registry)
    stale_hash["copies"][0]["content_sha256"] = "sha256:" + "0" * 64
    semantic_corruptions["stale-hash"] = stale_hash
    reviewer = copy.deepcopy(semantic_registry)
    reviewer["copies"][0]["review"]["reviewer_identity"] = "external-reviewer:forged"
    semantic_corruptions["reviewer"] = reviewer
    scope = copy.deepcopy(semantic_registry)
    scope["copies"][0]["review"]["reviewer_scope"] = "authority-copy.en.unrelated"
    semantic_corruptions["scope"] = scope
    duplicate = copy.deepcopy(semantic_registry)
    duplicate["copies"].append(copy.deepcopy(duplicate["copies"][0]))
    semantic_corruptions["duplicate"] = duplicate
    semantic_source_corruptions = (
        semantic_source.replace(
            'AvailableGovernedProjectionPacket["may_not_use_for"][number]',
            'string /* AvailableGovernedProjectionPacket["may_not_use_for"][number] */',
            1,
        ),
        semantic_source.replace(
            "issuedAuthoritySemanticCopies.add(issued);",
            "void issuedAuthoritySemanticCopies;",
            1,
        ),
        semantic_source.replace(
            "issuedAuthoritySemanticCopies.add(issued);",
            "issuedAuthoritySemanticCopies.add({});",
            1,
        ),
        semantic_source.replace(
            "const issued: AuthoritySemanticCopy = Object.freeze({",
            "const issued: AuthoritySemanticCopy = {",
            1,
        ).replace(
            "  });\n  issuedAuthoritySemanticCopies.add(issued);",
            "  };\n  Object.freeze({});\n  issuedAuthoritySemanticCopies.add(issued);",
            1,
        ),
        semantic_source
        + "\nexport function issueStrongAuthoritySemanticCopy(): AuthoritySemanticCopy {\n"
        + '  return issueAuthoritySemanticCopy("phase34.harm.risk.limited", "strong");\n}\n',
    )
    if any(
        not _authority_semantic_copy_errors(
            registry=corruption,
            source=semantic_source,
            generated_types=semantic_generated_types,
        )
        for corruption in semantic_corruptions.values()
    ) or any(
        not _authority_semantic_copy_errors(
            registry=semantic_registry,
            source=corruption,
            generated_types=semantic_generated_types,
        )
        for corruption in semantic_source_corruptions
    ):
        escaped.append("authority-semantic-copy-registry")
    if _authority_semantic_copy_runtime_errors():
        escaped.append("authority-semantic-copy-runtime")
    if architecture_errors is None or architecture_receipt is None:
        architecture_errors, architecture_receipt = _architecture_recurrence_errors()
    if architecture_errors:
        escaped.append("architecture-recurrence-execution")
    if not architecture_receipt.get("corruption_witnesses_rejected"):
        escaped.append("architecture-recurrence-corruption")
    if not architecture_receipt.get("benign_graphs_accepted"):
        escaped.append("architecture-recurrence-benign")
    return escaped


def _summary(scan: Mapping[str, Any]) -> dict[str, Any]:
    inventory = status_checker._load_json(status_checker.INVENTORY_PATH)
    debt = status_checker._load_json(status_checker.WAIST_DEBT_PATH)
    status_summary = status_checker._summary(inventory, debt)
    denominators = scan.get("sourceDenominators", {})
    issuer_facts = scan.get("authorityIssuerFacts", {})
    query_cache_facts = scan.get("queryCachePolicyFacts", {})
    offline_queue_facts = scan.get("offlineQueueFacts", {})
    return {
        "atlas_ui_production_sources": denominators.get("atlasUiProduction"),
        "authority_sink_declarations": len(scan.get("authoritySinkDeclarations", [])),
        "authority_badge_sites": len(scan.get("badgeSites", [])),
        "authority_prop_groups": len(scan.get("authorityPropCensus", [])),
        "authority_path_files": len(scan.get("authorityPathFiles", [])),
        "authority_escape_sites": len(scan.get("authorityEscapeSites", [])),
        "authority_issuer_brands": len(issuer_facts.get("brands", [])),
        "authority_issuer_factories": len(issuer_facts.get("factories", [])),
        "authority_issuer_modules": len(issuer_facts.get("modules", [])),
        "authority_issuer_stores": len(issuer_facts.get("stores", [])),
        "capability_discovery_residual": (
            "indirect enclosure identity, including nested same-name functions, is outside "
            "the direct-syntax/construction-site rule"
        ),
        "capability_discovery_production_sources": scan.get("capabilityDiscoveryFacts", {}).get(
            "productionFiles"
        ),
        "capability_discovery_issuer_calls": len(
            scan.get("capabilityDiscoveryFacts", {}).get("issuerCalls", [])
        ),
        "capability_discovery_feature_literals": len(
            scan.get("capabilityDiscoveryFacts", {}).get("featureLiterals", [])
        ),
        "query_cache_query_key_owners": len(query_cache_facts.get("queryKeyOwners", [])),
        "query_cache_constructions": len(query_cache_facts.get("constructions", [])),
        "query_cache_producers": len(query_cache_facts.get("producers", [])),
        "query_cache_residual": query_cache_facts.get("residual"),
        "offline_queue_production_sources": offline_queue_facts.get("productionFiles"),
        "offline_queue_authority_action_kinds": len(
            offline_queue_facts.get("authorityActionKinds", [])
        ),
        "offline_queue_mutation_stores": len(offline_queue_facts.get("mutationStores", [])),
        "offline_queue_replay_declarations": len(
            offline_queue_facts.get("replayDeclarations", [])
        ),
        "current_authored_statuses": status_summary["current_authored"],
        "ds1_status_rows": status_summary["ds1_rows"],
        "semantic_retirement_debt": status_summary["semantic_retirement_debt"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the retained-core checker and optional corruption witnesses."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--corruption-probes", action="store_true")
    parser.add_argument("--write-query-cache-policy-register", action="store_true")
    args = parser.parse_args(argv)
    errors, scan = validate_enforcement()
    if args.write_query_cache_policy_register:
        try:
            _write_query_cache_policy_register(scan)
        except RuntimeError as error:
            errors.append(str(error))
    architecture_errors, architecture_receipt = _architecture_recurrence_errors()
    errors.extend(architecture_errors)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if args.corruption_probes:
        escaped = _corruption_probes(
            architecture_errors=architecture_errors,
            architecture_receipt=architecture_receipt,
        )
        if escaped:
            print("corruption probes escaped: " + ", ".join(escaped), file=sys.stderr)
            return 1
        print("Atlas enforcement corruption probes: PASS")
    summary = _summary(scan)
    summary["architecture_recurrence"] = architecture_receipt
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
