import fs from "node:fs/promises";
import path from "node:path";

import openapiTS, { astToString, COMMENT_HEADER } from "openapi-typescript";
import ts from "typescript";

import { normalizeRecursiveOpenApiTypes } from "./normalize-recursive-openapi-types.mjs";

const SCHEMA_CHILD_KEYS = [
  "$defs",
  "additionalProperties",
  "allOf",
  "anyOf",
  "contains",
  "dependentSchemas",
  "definitions",
  "else",
  "if",
  "items",
  "not",
  "oneOf",
  "patternProperties",
  "prefixItems",
  "properties",
  "propertyNames",
  "then",
  "unevaluatedItems",
  "unevaluatedProperties",
];
const HTTP_METHODS = new Set([
  "delete",
  "get",
  "head",
  "options",
  "patch",
  "post",
  "put",
  "trace",
]);

function escapePointer(segment) {
  return String(segment).replaceAll("~", "~0").replaceAll("/", "~1");
}

function decodePointer(segment) {
  const unescaped = segment.replaceAll("~1", "/").replaceAll("~0", "~");
  try {
    return decodeURIComponent(unescaped);
  } catch {
    return unescaped;
  }
}

function pointerSegments(reference) {
  if (typeof reference !== "string" || !reference.startsWith("#/")) {
    return undefined;
  }
  return reference.slice(2).split("/").map(decodePointer);
}

function pointerFor(segments) {
  return `#/${segments.map(escapePointer).join("/")}`;
}

function resolveLocalReference(document, reference, role) {
  const segments = pointerSegments(reference);
  if (!segments) {
    throw new Error(
      `Unresolved external reference ${JSON.stringify(reference)} in ${role} schema graph`,
    );
  }
  let value = document;
  for (const segment of segments) {
    if (
      value === null ||
      typeof value !== "object" ||
      !Object.hasOwn(value, segment)
    ) {
      throw new Error(
        `Unresolved local reference ${JSON.stringify(reference)} in ${role} schema graph`,
      );
    }
    value = value[segment];
  }
  return { segments, value };
}

function schemaReference(reference) {
  const segments = pointerSegments(reference);
  if (segments?.[0] !== "components" || segments[1] !== "schemas") {
    return undefined;
  }
  if (segments.length < 3) {
    throw new Error(`Invalid components.schemas reference ${reference}`);
  }
  return { name: segments[2], suffix: segments.slice(3) };
}

function resolveDiscriminatorReference(document, reference, role, targets) {
  const localSchema = schemaReference(reference);
  if (localSchema) {
    const resolved = resolveLocalReference(document, reference, role);
    assertReferenceTarget(
      targets,
      "schema",
      resolved.segments,
      reference,
      role,
    );
    return { ...resolved, schema: localSchema };
  }
  if (Object.hasOwn(document.components?.schemas ?? {}, reference)) {
    const name = reference;
    return {
      segments: ["components", "schemas", name],
      value: document.components.schemas[name],
      schema: { name, suffix: [] },
    };
  }
  const resolved = resolveLocalReference(document, reference, role);
  assertReferenceTarget(targets, "schema", resolved.segments, reference, role);
  return resolved;
}

function objectEntries(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? Object.entries(value)
    : [];
}

function createReferenceTargetCatalog(document) {
  const objectKinds = new Map();
  const schemaNodes = new Set();

  function addObject(kind, value, segments) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return;
    const pointer = pointerFor(segments);
    const kinds = objectKinds.get(pointer) ?? new Set();
    kinds.add(kind);
    objectKinds.set(pointer, kinds);
  }

  function addSchema(schema, segments) {
    if (typeof schema === "boolean") {
      schemaNodes.add(pointerFor(segments));
      return;
    }
    if (!schema || typeof schema !== "object" || Array.isArray(schema)) return;
    const pointer = pointerFor(segments);
    if (schemaNodes.has(pointer)) return;
    schemaNodes.add(pointer);
    schemaChildren(schema, (child, relative) =>
      addSchema(child, [...segments, ...relative]),
    );
  }

  function addContentSchemas(value, segments) {
    for (const [mediaType, media] of objectEntries(value?.content)) {
      if (media?.schema !== undefined) {
        addSchema(media.schema, [...segments, "content", mediaType, "schema"]);
      }
    }
  }

  function addParameter(value, segments, kind = "parameter") {
    addObject(kind, value, segments);
    if (value?.schema !== undefined) {
      addSchema(value.schema, [...segments, "schema"]);
    }
    addContentSchemas(value, segments);
  }

  function addHeader(value, segments) {
    addParameter(value, segments, "header");
  }

  function addRequestBody(value, segments) {
    addObject("requestBody", value, segments);
    addContentSchemas(value, segments);
  }

  function addResponse(value, segments) {
    addObject("response", value, segments);
    addContentSchemas(value, segments);
    for (const [name, header] of objectEntries(value?.headers)) {
      addHeader(header, [...segments, "headers", name]);
    }
  }

  function addCallback(value, segments) {
    addObject("callback", value, segments);
    for (const [expression, pathItem] of objectEntries(value)) {
      if (expression !== "$ref") {
        addPathItem(pathItem, [...segments, expression]);
      }
    }
  }

  function addOperation(value, segments) {
    for (const [index, parameter] of (value?.parameters ?? []).entries()) {
      addParameter(parameter, [...segments, "parameters", String(index)]);
    }
    if (value?.requestBody !== undefined) {
      addRequestBody(value.requestBody, [...segments, "requestBody"]);
    }
    for (const [status, response] of objectEntries(value?.responses)) {
      addResponse(response, [...segments, "responses", status]);
    }
    for (const [name, callback] of objectEntries(value?.callbacks)) {
      addCallback(callback, [...segments, "callbacks", name]);
    }
  }

  function addPathItem(value, segments) {
    addObject("pathItem", value, segments);
    for (const [index, parameter] of (value?.parameters ?? []).entries()) {
      addParameter(parameter, [...segments, "parameters", String(index)]);
    }
    for (const [method, operation] of objectEntries(value)) {
      if (HTTP_METHODS.has(method.toLowerCase())) {
        addOperation(operation, [...segments, method]);
      }
    }
  }

  const components = document.components ?? {};
  for (const [name, schema] of objectEntries(components.schemas)) {
    addSchema(schema, ["components", "schemas", name]);
  }
  for (const [name, parameter] of objectEntries(components.parameters)) {
    addParameter(parameter, ["components", "parameters", name]);
  }
  for (const [name, header] of objectEntries(components.headers)) {
    addHeader(header, ["components", "headers", name]);
  }
  for (const [name, body] of objectEntries(components.requestBodies)) {
    addRequestBody(body, ["components", "requestBodies", name]);
  }
  for (const [name, response] of objectEntries(components.responses)) {
    addResponse(response, ["components", "responses", name]);
  }
  for (const [name, pathItem] of objectEntries(components.pathItems)) {
    addPathItem(pathItem, ["components", "pathItems", name]);
  }
  for (const [name, callback] of objectEntries(components.callbacks)) {
    addCallback(callback, ["components", "callbacks", name]);
  }
  for (const [name, pathItem] of objectEntries(document.paths)) {
    addPathItem(pathItem, ["paths", name]);
  }
  for (const [name, pathItem] of objectEntries(document.webhooks)) {
    addPathItem(pathItem, ["webhooks", name]);
  }

  return { objectKinds, schemaNodes };
}

function assertReferenceTarget(
  targets,
  expectedKind,
  segments,
  reference,
  role,
) {
  const pointer = pointerFor(segments);
  const actualKinds = targets.objectKinds.get(pointer) ?? new Set();
  const matches =
    expectedKind === "schema"
      ? targets.schemaNodes.has(pointer)
      : actualKinds.has(expectedKind);
  if (matches) return;
  const found = [
    ...(targets.schemaNodes.has(pointer) ? ["schema"] : []),
    ...actualKinds,
  ];
  const expectedName =
    expectedKind === "schema"
      ? "Schema Object or schema subfragment"
      : {
          parameter: "Parameter Object",
          header: "Header Object",
          requestBody: "Request Body Object",
          response: "Response Object",
          pathItem: "Path Item Object",
          callback: "Callback Object",
        }[expectedKind];
  throw new Error(
    `Invalid ${expectedKind} reference ${JSON.stringify(reference)} in ${role}: target is not an OpenAPI ${expectedName} source slot; ${pointer} has ${found.length ? found.join(", ") : "no recognized OpenAPI object kind"}`,
  );
}

function walkSchema(document, schema, role, uses, visited, targets) {
  if (!schema || typeof schema !== "object" || Array.isArray(schema)) return;

  if (typeof schema.$ref === "string") {
    const { segments, value } = resolveLocalReference(
      document,
      schema.$ref,
      role,
    );
    assertReferenceTarget(targets, "schema", segments, schema.$ref, role);
    const target = schemaReference(schema.$ref);
    if (target && uses[role]) uses[role].add(target.name);
    const refKey = pointerFor(segments);
    const visitKey = `${role}:${refKey}`;
    if (!visited.has(visitKey)) {
      visited.add(visitKey);
      walkSchema(document, value, role, uses, visited, targets);
    }
  }

  for (const [, reference] of objectEntries(schema.discriminator?.mapping)) {
    if (typeof reference !== "string") continue;
    const {
      segments,
      value,
      schema: target,
    } = resolveDiscriminatorReference(document, reference, role, targets);
    if (target && uses[role]) uses[role].add(target.name);
    const visitKey = `${role}:${pointerFor(segments)}`;
    if (!visited.has(visitKey)) {
      visited.add(visitKey);
      walkSchema(document, value, role, uses, visited, targets);
    }
  }

  for (const keyword of SCHEMA_CHILD_KEYS) {
    const child = schema[keyword];
    if (Array.isArray(child)) {
      child.forEach((entry) =>
        walkSchema(document, entry, role, uses, visited, targets),
      );
    } else if (
      keyword === "properties" ||
      keyword === "patternProperties" ||
      keyword === "$defs" ||
      keyword === "definitions" ||
      keyword === "dependentSchemas"
    ) {
      for (const [, entry] of objectEntries(child)) {
        walkSchema(document, entry, role, uses, visited, targets);
      }
    } else if (child && typeof child === "object") {
      walkSchema(document, child, role, uses, visited, targets);
    }
  }
}

function resolveObject(
  document,
  value,
  role,
  expectedKind,
  targets,
  visited,
  visit,
) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return;
  if (typeof value.$ref !== "string") {
    visit(value, visited);
    return;
  }
  const { segments, value: resolved } = resolveLocalReference(
    document,
    value.$ref,
    role,
  );
  assertReferenceTarget(targets, expectedKind, segments, value.$ref, role);
  const key = `${role}:${pointerFor(segments)}`;
  if (visited.has(key)) return;
  const next = new Set(visited);
  next.add(key);
  resolveObject(document, resolved, role, expectedKind, targets, next, visit);
}

function walkParameter(
  document,
  parameter,
  role,
  uses,
  visited,
  targets,
  expectedKind = "parameter",
) {
  resolveObject(
    document,
    parameter,
    role,
    expectedKind,
    targets,
    visited,
    (resolved, next) => {
      if (resolved.schema)
        walkSchema(document, resolved.schema, role, uses, next, targets);
      for (const [, media] of objectEntries(resolved.content)) {
        if (media?.schema)
          walkSchema(document, media.schema, role, uses, next, targets);
      }
    },
  );
}

function walkRequestBody(document, body, uses, visited, targets) {
  resolveObject(
    document,
    body,
    "request",
    "requestBody",
    targets,
    visited,
    (resolved, next) => {
      for (const [, media] of objectEntries(resolved.content)) {
        if (media?.schema)
          walkSchema(document, media.schema, "request", uses, next, targets);
      }
    },
  );
}

function walkHeader(document, header, uses, visited, targets) {
  walkParameter(document, header, "response", uses, visited, targets, "header");
}

function walkResponse(document, response, uses, visited, targets) {
  resolveObject(
    document,
    response,
    "response",
    "response",
    targets,
    visited,
    (resolved, next) => {
      for (const [, media] of objectEntries(resolved.content)) {
        if (media?.schema)
          walkSchema(document, media.schema, "response", uses, next, targets);
      }
      for (const [, header] of objectEntries(resolved.headers)) {
        walkHeader(document, header, uses, next, targets);
      }
    },
  );
}

function walkCallback(document, callback, uses, visited, targets) {
  resolveObject(
    document,
    callback,
    "request/response",
    "callback",
    targets,
    visited,
    (resolved, next) => {
      for (const [expression, pathItem] of objectEntries(resolved)) {
        if (expression !== "$ref")
          walkPathItem(document, pathItem, uses, next, targets);
      }
    },
  );
}

function walkOperation(document, operation, uses, visited, targets) {
  for (const parameter of operation.parameters ?? []) {
    walkParameter(document, parameter, "request", uses, visited, targets);
  }
  if (operation.requestBody) {
    walkRequestBody(document, operation.requestBody, uses, visited, targets);
  }
  for (const [, response] of objectEntries(operation.responses)) {
    walkResponse(document, response, uses, visited, targets);
  }
  for (const [, callback] of objectEntries(operation.callbacks)) {
    walkCallback(document, callback, uses, visited, targets);
  }
}

function walkPathItem(document, pathItem, uses, visited, targets) {
  resolveObject(
    document,
    pathItem,
    "request/response",
    "pathItem",
    targets,
    visited,
    (resolved, next) => {
      for (const parameter of resolved.parameters ?? []) {
        walkParameter(document, parameter, "request", uses, next, targets);
      }
      for (const [method, operation] of objectEntries(resolved)) {
        if (HTTP_METHODS.has(method.toLowerCase())) {
          walkOperation(document, operation, uses, next, targets);
        }
      }
    },
  );
}

/**
 * Resolve request and response schema roles from every OpenAPI operation and reusable component.
 *
 * @param {object} document Parsed OpenAPI document.
 * @returns {{request: Set<string>, response: Set<string>, requestOnly: Set<string>, shared: Set<string>, responseOnly: Set<string>}}
 */
export function analyzeRequestSchemaDirections(document) {
  const uses = { request: new Set(), response: new Set() };
  const visited = new Set();
  const targets = createReferenceTargetCatalog(document);
  for (const [, pathItem] of objectEntries(document.paths)) {
    walkPathItem(document, pathItem, uses, visited, targets);
  }
  for (const [, pathItem] of objectEntries(document.webhooks)) {
    walkPathItem(document, pathItem, uses, visited, targets);
  }

  const components = document.components ?? {};
  for (const [, parameter] of objectEntries(components.parameters)) {
    walkParameter(document, parameter, "request", uses, visited, targets);
  }
  for (const [, body] of objectEntries(components.requestBodies)) {
    walkRequestBody(document, body, uses, visited, targets);
  }
  for (const [, response] of objectEntries(components.responses)) {
    walkResponse(document, response, uses, visited, targets);
  }
  for (const [, header] of objectEntries(components.headers)) {
    walkHeader(document, header, uses, visited, targets);
  }
  for (const [, pathItem] of objectEntries(components.pathItems)) {
    walkPathItem(document, pathItem, uses, visited, targets);
  }
  for (const [, callback] of objectEntries(components.callbacks)) {
    walkCallback(document, callback, uses, visited, targets);
  }

  // Generated output includes every schema component, including unused ones.
  // Validate their $ref edges too, without assigning them an operation role.
  const schemaGraphUses = { request: new Set(), response: new Set() };
  const schemaGraphVisited = new Set();
  for (const [, schema] of objectEntries(components.schemas)) {
    walkSchema(
      document,
      schema,
      "schema graph",
      schemaGraphUses,
      schemaGraphVisited,
      targets,
    );
  }

  const requestOnly = new Set(
    [...uses.request].filter((name) => !uses.response.has(name)),
  );
  const responseOnly = new Set(
    [...uses.response].filter((name) => !uses.request.has(name)),
  );
  const shared = new Set(
    [...uses.request].filter((name) => uses.response.has(name)),
  );
  return {
    request: uses.request,
    response: uses.response,
    requestOnly,
    responseOnly,
    shared,
  };
}

function collisionSafeSchemaName(originalName, schemas, reserved) {
  const encoded = [...originalName]
    .map((character) => character.codePointAt(0).toString(16))
    .join("_");
  const stem = `__RuntimeApiRequestView_${encoded || "empty"}`;
  let candidate = stem;
  let suffix = 1;
  while (Object.hasOwn(schemas, candidate) || reserved.has(candidate)) {
    candidate = `${stem}_${suffix++}`;
  }
  reserved.add(candidate);
  return candidate;
}

function schemaChildren(schema, visit) {
  if (!schema || typeof schema !== "object" || Array.isArray(schema)) return;
  for (const keyword of SCHEMA_CHILD_KEYS) {
    const child = schema[keyword];
    if (Array.isArray(child)) {
      child.forEach((entry, index) => visit(entry, [keyword, String(index)]));
    } else if (
      keyword === "properties" ||
      keyword === "patternProperties" ||
      keyword === "$defs" ||
      keyword === "definitions" ||
      keyword === "dependentSchemas"
    ) {
      for (const [name, entry] of objectEntries(child)) {
        visit(entry, [keyword, name]);
      }
    } else if (child && typeof child === "object") {
      visit(child, [keyword]);
    }
  }
}

function normalizeRequiredProperties(schema, pointer, visited = new WeakSet()) {
  if (!schema || typeof schema !== "object" || Array.isArray(schema)) return;
  if (visited.has(schema)) return;
  visited.add(schema);

  if (Array.isArray(schema.required) && schema.required.length > 0) {
    const names = schema.required;
    if (names.some((name) => typeof name !== "string")) {
      throw new Error(
        `Malformed required property name in request schema ${pointer}`,
      );
    }
    const existingProperties = objectEntries(schema.properties);
    const existingNames = new Set(existingProperties.map(([name]) => name));
    const missingNames = names.filter((name) => !existingNames.has(name));
    if (missingNames.length > 0) {
      if (schema.additionalProperties === false) {
        throw new Error(
          `Request schema ${pointer} has required property ${JSON.stringify(missingNames[0])} but excludes it with additionalProperties: false`,
        );
      }
      if (
        schema.properties !== undefined &&
        (!schema.properties ||
          typeof schema.properties !== "object" ||
          Array.isArray(schema.properties))
      ) {
        throw new Error(
          `Malformed properties map in request schema ${pointer}`,
        );
      }
      const properties = Object.fromEntries(existingProperties);
      for (const name of missingNames) {
        const additionalSchema = schema.additionalProperties;
        properties[name] =
          additionalSchema &&
          typeof additionalSchema === "object" &&
          !Array.isArray(additionalSchema)
            ? structuredClone(additionalSchema)
            : {};
      }
      schema.properties = properties;
    }
  }

  schemaChildren(schema, (child, relative) => {
    const childPointer = `${pointer}/${relative.map(escapePointer).join("/")}`;
    normalizeRequiredProperties(child, childPointer, visited);
  });
}

function rewriteSchemaReferences(schema, views) {
  if (!schema || typeof schema !== "object" || Array.isArray(schema)) return;
  if (typeof schema.$ref === "string") {
    const target = schemaReference(schema.$ref);
    if (target && views.has(target.name)) {
      schema.$ref = pointerFor([
        "components",
        "schemas",
        views.get(target.name),
        ...target.suffix,
      ]);
    }
  }
  const mapping = schema.discriminator?.mapping;
  if (mapping && typeof mapping === "object") {
    for (const [key, reference] of Object.entries(mapping)) {
      if (typeof reference !== "string") continue;
      const target =
        schemaReference(reference) ??
        (views.has(reference) ? { name: reference, suffix: [] } : undefined);
      if (target && views.has(target.name)) {
        mapping[key] = pointerFor([
          "components",
          "schemas",
          views.get(target.name),
          ...target.suffix,
        ]);
      }
    }
  }
  schemaChildren(schema, (child) => rewriteSchemaReferences(child, views));
}

function rewriteParameterSchemaReferences(parameter, views) {
  if (!parameter || typeof parameter !== "object" || Array.isArray(parameter))
    return;
  if (parameter.$ref) return;
  if (parameter.schema) {
    rewriteSchemaReferences(parameter.schema, views);
    normalizeRequiredProperties(parameter.schema, "request parameter schema");
  }
  for (const [, media] of objectEntries(parameter.content)) {
    if (media?.schema) {
      rewriteSchemaReferences(media.schema, views);
      normalizeRequiredProperties(
        media.schema,
        "request parameter content schema",
      );
    }
  }
}

function rewriteRequestBodySchemaReferences(body, views) {
  if (!body || typeof body !== "object" || Array.isArray(body)) return;
  if (body.$ref) return;
  for (const [, media] of objectEntries(body.content)) {
    if (media?.schema) {
      rewriteSchemaReferences(media.schema, views);
      normalizeRequiredProperties(media.schema, "request body schema");
    }
  }
}

function rewriteRequestPathReferences(document, views) {
  const components = document.components ?? {};
  for (const [, parameter] of objectEntries(components.parameters)) {
    rewriteParameterSchemaReferences(parameter, views);
  }
  for (const [, body] of objectEntries(components.requestBodies)) {
    rewriteRequestBodySchemaReferences(body, views);
  }

  function rewriteCallback(callback, seen = new Set()) {
    if (!callback || typeof callback !== "object") return;
    if (callback.$ref) {
      const segments = pointerSegments(callback.$ref);
      if (!segments) return;
      const key = pointerFor(segments);
      if (seen.has(key)) return;
      seen.add(key);
      const { value } = resolveLocalReference(
        document,
        callback.$ref,
        "request",
      );
      rewriteCallback(value, seen);
      return;
    }
    for (const [expression, pathItem] of objectEntries(callback)) {
      if (expression !== "$ref") rewritePathItem(pathItem, seen);
    }
  }

  function rewritePathItem(pathItem, seen = new Set()) {
    if (!pathItem || typeof pathItem !== "object") return;
    if (pathItem.$ref) {
      const segments = pointerSegments(pathItem.$ref);
      if (!segments) return;
      const key = pointerFor(segments);
      if (seen.has(key)) return;
      seen.add(key);
      const { value } = resolveLocalReference(
        document,
        pathItem.$ref,
        "request",
      );
      rewritePathItem(value, seen);
      return;
    }
    for (const parameter of pathItem.parameters ?? []) {
      rewriteParameterSchemaReferences(parameter, views);
    }
    for (const [method, operation] of objectEntries(pathItem)) {
      if (!HTTP_METHODS.has(method.toLowerCase())) continue;
      for (const parameter of operation.parameters ?? []) {
        rewriteParameterSchemaReferences(parameter, views);
      }
      rewriteRequestBodySchemaReferences(operation.requestBody, views);
      for (const [, callback] of objectEntries(operation.callbacks)) {
        rewriteCallback(callback, seen);
      }
    }
  }

  for (const [, pathItem] of objectEntries(document.paths)) {
    rewritePathItem(pathItem);
  }
  for (const [, pathItem] of objectEntries(document.webhooks)) {
    rewritePathItem(pathItem);
  }
  for (const [, pathItem] of objectEntries(components.pathItems)) {
    rewritePathItem(pathItem);
  }
  for (const [, callback] of objectEntries(components.callbacks)) {
    rewriteCallback(callback);
  }
}

function addDefaultedOptionalPointers(
  schema,
  pointer,
  optionalPointers,
  inheritedRequired = new Set(),
) {
  if (!schema || typeof schema !== "object" || Array.isArray(schema)) return;
  const required = new Set(inheritedRequired);
  for (const name of schema.required ?? []) required.add(name);
  for (const branch of schema.allOf ?? []) {
    for (const name of branch?.required ?? []) required.add(name);
  }

  for (const [name, child] of objectEntries(schema.properties)) {
    if (
      child &&
      typeof child === "object" &&
      Object.hasOwn(child, "default") &&
      !required.has(name)
    ) {
      optionalPointers.add(`${pointer}/${escapePointer(name)}`);
    }
    addDefaultedOptionalPointers(
      child,
      `${pointer}/${escapePointer(name)}`,
      optionalPointers,
    );
  }

  for (const keyword of SCHEMA_CHILD_KEYS) {
    if (keyword === "properties" || keyword === "allOf") continue;
    const child = schema[keyword];
    if (Array.isArray(child)) {
      child.forEach((entry, index) =>
        addDefaultedOptionalPointers(
          entry,
          `${pointer}/${keyword}/${index}`,
          optionalPointers,
          required,
        ),
      );
    } else if (
      keyword === "patternProperties" ||
      keyword === "$defs" ||
      keyword === "definitions" ||
      keyword === "dependentSchemas"
    ) {
      for (const [name, entry] of objectEntries(child)) {
        addDefaultedOptionalPointers(
          entry,
          `${pointer}/${keyword}/${escapePointer(name)}`,
          optionalPointers,
          required,
        );
      }
    } else if (child && typeof child === "object") {
      addDefaultedOptionalPointers(
        child,
        `${pointer}/${keyword}`,
        optionalPointers,
        required,
      );
    }
  }

  for (const branch of schema.allOf ?? []) {
    addDefaultedOptionalPointers(
      branch,
      `${pointer}/allOf/${schema.allOf.indexOf(branch)}`,
      optionalPointers,
      required,
    );
  }
}

function prepareInputDocument(sourceDocument) {
  const document = structuredClone(sourceDocument);
  const directions = analyzeRequestSchemaDirections(sourceDocument);
  const schemas = document.components?.schemas ?? {};
  const reserved = new Set(Object.keys(schemas));
  const viewNames = new Map();
  for (const name of [...directions.shared].sort()) {
    viewNames.set(name, collisionSafeSchemaName(name, schemas, reserved));
  }

  for (const [sourceName, viewName] of viewNames) {
    schemas[viewName] = structuredClone(schemas[sourceName]);
  }

  const requestSchemaNames = new Set([
    ...directions.requestOnly,
    ...viewNames.values(),
  ]);
  for (const name of directions.requestOnly) {
    rewriteSchemaReferences(schemas[name], viewNames);
  }
  for (const viewName of viewNames.values()) {
    rewriteSchemaReferences(schemas[viewName], viewNames);
  }
  for (const name of requestSchemaNames) {
    if (schemas[name]) {
      normalizeRequiredProperties(
        schemas[name],
        pointerFor(["components", "schemas", name]),
      );
    }
  }
  rewriteRequestPathReferences(document, viewNames);

  const optionalPointers = new Set();
  for (const name of requestSchemaNames) {
    if (schemas[name]) {
      addDefaultedOptionalPointers(
        schemas[name],
        pointerFor(["components", "schemas", name]),
        optionalPointers,
      );
    }
  }
  return { document, directions, viewNames, optionalPointers };
}

function propertyName(node) {
  if (ts.isIdentifier(node)) return node.text;
  if (ts.isStringLiteral(node) || ts.isNumericLiteral(node)) return node.text;
  return undefined;
}

function generatedSchemaReference(node) {
  if (
    !ts.isIndexedAccessTypeNode(node) ||
    !ts.isLiteralTypeNode(node.indexType) ||
    !ts.isIndexedAccessTypeNode(node.objectType) ||
    !ts.isLiteralTypeNode(node.objectType.indexType) ||
    !ts.isTypeReferenceNode(node.objectType.objectType) ||
    !ts.isIdentifier(node.objectType.objectType.typeName) ||
    node.objectType.objectType.typeName.text !== "components"
  ) {
    return undefined;
  }
  if (
    !ts.isStringLiteral(node.objectType.indexType.literal) ||
    node.objectType.indexType.literal.text !== "schemas" ||
    !ts.isStringLiteral(node.indexType.literal)
  ) {
    return undefined;
  }
  return node.indexType.literal.text;
}

function replaceSpans(source, replacements) {
  const ordered = [...replacements].sort(
    (left, right) => right.start - left.start,
  );
  let end = source.length;
  let result = "";
  for (const replacement of ordered) {
    if (replacement.end > end) {
      throw new Error("Overlapping generated TypeScript replacements");
    }
    result = replacement.text + source.slice(replacement.end, end) + result;
    end = replacement.start;
  }
  return source.slice(0, end) + result;
}

function privateAliasNames(source, viewNames) {
  const file = ts.createSourceFile(
    "types.ts",
    source,
    ts.ScriptTarget.Latest,
    true,
  );
  if (file.parseDiagnostics.length) {
    throw new Error("Cannot inspect invalid generated OpenAPI TypeScript");
  }
  const identifiers = new Set();
  function visit(node) {
    if (ts.isIdentifier(node)) identifiers.add(node.text);
    ts.forEachChild(node, visit);
  }
  visit(file);

  const aliases = new Map();
  for (const sourceName of [...viewNames.keys()].sort()) {
    const suffix = [...sourceName]
      .map((character) => character.codePointAt(0).toString(16))
      .join("_");
    const stem = `_RuntimeApiRequestView_${suffix || "empty"}`;
    let candidate = stem;
    let index = 1;
    while (identifiers.has(candidate)) candidate = `${stem}_${index++}`;
    identifiers.add(candidate);
    aliases.set(viewNames.get(sourceName), candidate);
  }
  return { file, aliases };
}

function privatizeRequestViews(source, viewNames) {
  if (!viewNames.size) return source;
  const { file, aliases } = privateAliasNames(source, viewNames);
  const components = file.statements.find(
    (node) =>
      ts.isInterfaceDeclaration(node) && node.name.text === "components",
  );
  const schemas = components?.members.find(
    (node) =>
      ts.isPropertySignature(node) && propertyName(node.name) === "schemas",
  );
  if (!schemas?.type || !ts.isTypeLiteralNode(schemas.type)) {
    throw new Error("Generated types are missing components.schemas");
  }

  const views = new Map();
  for (const member of schemas.type.members) {
    if (!ts.isPropertySignature(member) || !member.type) continue;
    const name = propertyName(member.name);
    if (name && aliases.has(name)) views.set(name, member);
  }
  if (views.size !== aliases.size) {
    const missing = [...aliases.keys()].filter((name) => !views.has(name));
    throw new Error(
      `Generated request views are missing: ${missing.join(", ")}`,
    );
  }

  const referenceEdits = [];
  function replaceReferences(node) {
    const name = generatedSchemaReference(node);
    if (name && aliases.has(name)) {
      referenceEdits.push({
        start: node.getStart(file),
        end: node.getEnd(),
        text: aliases.get(name),
      });
      return;
    }
    ts.forEachChild(node, replaceReferences);
  }
  replaceReferences(file);

  const removals = [...views.values()].map((member) => ({
    start: member.getFullStart(),
    end: member.getEnd(),
    text: "",
  }));
  const removedSource = replaceSpans(source, removals);
  const adjustedReferenceEdits = referenceEdits
    .map((edit) => {
      const removedBefore = removals
        .filter((removal) => removal.end <= edit.start)
        .reduce((total, removal) => total + removal.end - removal.start, 0);
      const insideRemoved = removals.some(
        (removal) => edit.start >= removal.start && edit.end <= removal.end,
      );
      if (insideRemoved) return undefined;
      return {
        start: edit.start - removedBefore,
        end: edit.end - removedBefore,
        text: edit.text,
      };
    })
    .filter(Boolean);
  let result = replaceSpans(removedSource, adjustedReferenceEdits);

  const aliasBodies = [];
  for (const [viewName, member] of views) {
    const alias = aliases.get(viewName);
    const typeNode = member.type;
    const body = source.slice(typeNode.getStart(file), typeNode.getEnd());
    const localReferenceEdits = referenceEdits
      .filter(
        (edit) =>
          edit.start >= typeNode.getStart(file) &&
          edit.end <= typeNode.getEnd(),
      )
      .map((edit) => ({
        start: edit.start - typeNode.getStart(file),
        end: edit.end - typeNode.getStart(file),
        text: edit.text,
      }));
    aliasBodies.push(
      `type ${alias} = ${replaceSpans(body, localReferenceEdits)};`,
    );
  }
  result = `${result.trimEnd()}\n\n// Private request views retain the source response schemas.\n${aliasBodies.join("\n")}\n`;
  return result;
}

/**
 * Generate one TypeScript projection that honors OpenAPI request presence without changing responses.
 *
 * @param {object} sourceDocument Parsed OpenAPI document.
 * @returns {Promise<string>} Generated and normalized TypeScript source.
 */
export async function generateOpenApiTypes(sourceDocument) {
  const { document, viewNames, optionalPointers } =
    prepareInputDocument(sourceDocument);
  const nodes = await openapiTS(document, {
    transformProperty(property, schema, options) {
      const schemaPointer = options.path?.replace(/^\\#/, "#");
      if (
        !Object.hasOwn(schema, "default") ||
        !optionalPointers.has(schemaPointer)
      ) {
        return undefined;
      }
      return ts.factory.updatePropertySignature(
        property,
        property.modifiers,
        property.name,
        ts.factory.createToken(ts.SyntaxKind.QuestionToken),
        property.type,
      );
    },
  });
  let source = `${COMMENT_HEADER}${astToString(nodes)}`;
  source = normalizeRecursiveOpenApiTypes(source);
  source = privatizeRequestViews(source, viewNames);
  return source;
}

async function parseArguments(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument !== "--openapi" && argument !== "--output") {
      throw new Error(`Unknown argument: ${argument}`);
    }
    const value = argv[index + 1];
    if (!value) throw new Error(`${argument} requires a value`);
    options[argument.slice(2)] = value;
    index += 1;
  }
  if (!options.openapi || !options.output) {
    throw new Error(
      "Usage: generate-openapi-types.mjs --openapi FILE --output FILE",
    );
  }
  return options;
}

async function main() {
  const options = await parseArguments(process.argv.slice(2));
  const openapiPath = path.resolve(options.openapi);
  const outputPath = path.resolve(options.output);
  const document = JSON.parse(await fs.readFile(openapiPath, "utf8"));
  const source = await generateOpenApiTypes(document);
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.writeFile(outputPath, source, "utf8");
}

if (path.basename(process.argv[1] ?? "") === "generate-openapi-types.mjs") {
  await main();
}
