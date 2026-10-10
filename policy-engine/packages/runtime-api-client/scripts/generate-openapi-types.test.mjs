import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import openapiTS, { astToString, COMMENT_HEADER } from "openapi-typescript";
import ts from "typescript";

import { generateOpenApiTypes } from "./generate-openapi-types.mjs";
import { normalizeRecursiveOpenApiTypes } from "./normalize-recursive-openapi-types.mjs";

const COMPONENTS = {
  schemas: {
    SharedFilter: {
      allOf: [
        { $ref: "#/components/schemas/FilterBase" },
        {
          type: "object",
          properties: {
            output_dir: { type: "string" },
            query_generation_intent: {
              type: "array",
              items: {
                type: "string",
                enum: ["prod_core_blocking", "observations_backfill"],
              },
              nullable: true,
            },
            target: {
              oneOf: [
                { $ref: "#/components/schemas/CatTarget" },
                { $ref: "#/components/schemas/DogTarget" },
              ],
              discriminator: {
                propertyName: "kind",
                mapping: {
                  cat: "#/components/schemas/CatTarget",
                  dog: "#/components/schemas/DogTarget",
                },
              },
            },
            nodes: {
              type: "array",
              items: { $ref: "#/components/schemas/Node" },
              nullable: true,
            },
          },
          required: ["output_dir"],
        },
      ],
    },
    FilterBase: {
      type: "object",
      properties: {
        query: { type: "string" },
        top_k: { type: "integer", default: 20 },
        nullable_filter: { type: ["string", "null"], default: null },
      },
      required: ["query"],
    },
    Node: {
      type: "object",
      properties: {
        label: { type: "string" },
        children: {
          type: "array",
          items: { $ref: "#/components/schemas/Node" },
        },
      },
      required: ["label"],
    },
    CatTarget: {
      type: "object",
      properties: { kind: { const: "cat" }, name: { type: "string" } },
      required: ["kind", "name"],
    },
    DogTarget: {
      type: "object",
      properties: { kind: { const: "dog" }, age: { type: "integer" } },
      required: ["kind", "age"],
    },
    ResponseOnly: {
      type: "object",
      properties: { computed: { type: "integer", default: 1 } },
    },
    NestedEnvelope: {
      type: "object",
      properties: { payload: { $ref: "#/components/schemas/SharedFilter" } },
      required: ["payload"],
    },
  },
  parameters: {
    Filter: {
      name: "filter",
      in: "query",
      required: false,
      schema: { $ref: "#/components/schemas/SharedFilter" },
    },
  },
};

const DOCUMENT = {
  openapi: "3.1.0",
  info: { title: "Request type fixture", version: "1" },
  paths: {
    "/referenced": {
      get: {
        operationId: "readReferenced",
        parameters: [{ $ref: "#/components/parameters/Filter" }],
        responses: {
          200: {
            description: "The persisted filter view.",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/SharedFilter" },
              },
            },
          },
        },
      },
      post: {
        operationId: "writeReferenced",
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/SharedFilter" },
            },
          },
        },
        responses: {
          200: {
            description: "Accepted.",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/SharedFilter" },
              },
            },
          },
        },
      },
    },
    "/inline": {
      post: {
        operationId: "writeInline",
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: {
                type: "object",
                properties: {
                  query: { type: "string" },
                  top_k: { type: "integer", default: 20 },
                  output_dir: { type: "string" },
                  query_generation_intent: {
                    type: "array",
                    items: {
                      type: "string",
                      enum: ["prod_core_blocking", "observations_backfill"],
                    },
                    nullable: true,
                  },
                },
                required: ["query", "output_dir"],
              },
            },
          },
        },
        responses: {
          200: { description: "Accepted." },
        },
      },
    },
    "/response-only": {
      get: {
        operationId: "readResponseOnly",
        responses: {
          200: {
            description: "Unchanged response projection.",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/ResponseOnly" },
              },
            },
          },
        },
      },
    },
    "/nested-reference": {
      post: {
        operationId: "writeNestedReference",
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: {
                $ref: "#/components/schemas/NestedEnvelope/properties/payload",
              },
            },
          },
        },
        responses: { 200: { description: "Accepted." } },
      },
    },
  },
  components: COMPONENTS,
};

function typeErrors(source) {
  const name = "request-type-probe.ts";
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

const VALID_CONSUMERS = `
type ReferencedBody = paths["/referenced"]["post"]["requestBody"]["content"]["application/json"];
const referencedBody: ReferencedBody = {
  query: "policy",
  output_dir: "artifacts/run",
  query_generation_intent: ["prod_core_blocking"],
  target: { kind: "cat", name: "Miso" },
  nodes: [{ label: "root", children: [{ label: "leaf", children: [] }] }],
};
type InlineBody = paths["/inline"]["post"]["requestBody"]["content"]["application/json"];
const inlineBody: InlineBody = {
  query: "policy",
  output_dir: "artifacts/run",
  query_generation_intent: ["observations_backfill"],
};
type QueryFilter = NonNullable<NonNullable<paths["/referenced"]["get"]["parameters"]["query"]>["filter"]>;
const queryFilter: QueryFilter = {
  query: "policy",
  output_dir: "artifacts/run",
  query_generation_intent: ["prod_core_blocking"],
};
type PersistedFilter = paths["/referenced"]["post"]["responses"]["200"]["content"]["application/json"];
const persisted: PersistedFilter = {
  query: "policy",
  top_k: 20,
  nullable_filter: null,
  output_dir: "artifacts/run",
  query_generation_intent: ["prod_core_blocking"],
  target: { kind: "dog", age: 4 },
  nodes: [{ label: "root", children: [] }],
};
type UnrelatedResponse = components["schemas"]["ResponseOnly"];
const unrelatedResponse: UnrelatedResponse = { computed: 1 };
type NestedBody = paths["/nested-reference"]["post"]["requestBody"]["content"]["application/json"];
const nestedBody: NestedBody = {query: "policy", output_dir: "artifacts/run"};
void [referencedBody, inlineBody, queryFilter, persisted, unrelatedResponse, nestedBody];
`;

const INVALID_CONSUMERS = `
type Request = paths["/referenced"]["post"]["requestBody"]["content"]["application/json"];
// @ts-expect-error query remains required by the OpenAPI required list
const missingQuery: Request = {output_dir: "x"};
// @ts-expect-error output_dir remains required by the OpenAPI required list
const missingOutputDir: Request = {query: "x"};
// @ts-expect-error supplied intent remains constrained to the source enum
const invalidIntent: Request = {query: "x", output_dir: "x", query_generation_intent: ["invalid"]};
// @ts-expect-error response defaults keep their existing required output projection
const missingResponseDefault: Persisted = {query: "x", output_dir: "x"};
// @ts-expect-error response-only default fields keep their existing required projection
const missingResponseOnlyDefault: UnrelatedResponse = {};
`;

test("referenced and inline request bodies accept omitted defaults while output projections stay unchanged", async () => {
  const before = structuredClone(DOCUMENT);
  const generated = await generateOpenApiTypes(DOCUMENT);
  assert.deepEqual(
    DOCUMENT,
    before,
    "generation must not mutate the canonical source object",
  );
  assert.deepEqual(
    typeErrors(`${generated}\n${VALID_CONSUMERS}\n${INVALID_CONSUMERS}`),
    [],
  );
  assert.match(generated, /type _RuntimeApiRequestView_/);
  assert.doesNotMatch(
    generated,
    /components\["schemas"\]\["_RuntimeApiRequestView/,
  );
});

test("the correction is source-bound and the removal control reproduces the required-default defect", async () => {
  const rawNodes = await openapiTS(DOCUMENT);
  const raw = normalizeRecursiveOpenApiTypes(
    `${COMMENT_HEADER}${astToString(rawNodes)}`,
  );
  const requestOnly = `${raw}\n${VALID_CONSUMERS}`;
  const removalDiagnostics = typeErrors(requestOnly);
  assert.ok(
    removalDiagnostics.some((diagnostic) => /top_k/.test(diagnostic.message)),
    "removing the request-direction transform must restore the baseline compile failure",
  );
  assert.deepEqual(
    typeErrors(`${await generateOpenApiTypes(DOCUMENT)}\n${VALID_CONSUMERS}`),
    [],
  );
});

test("an explicit required-list member with a default remains required in the input view", async () => {
  const requiredDefaultDocument = structuredClone(DOCUMENT);
  requiredDefaultDocument.components.schemas.FilterBase.required.push("top_k");
  const consumer = `
type Request = paths["/referenced"]["post"]["requestBody"]["content"]["application/json"];
// @ts-expect-error the source required list, not the property name, controls presence
const missingRequiredDefault: Request = {query: "policy", output_dir: "artifacts/run"};
const suppliedRequiredDefault: Request = {query: "policy", top_k: 20, output_dir: "artifacts/run"};
void suppliedRequiredDefault;
`;
  assert.deepEqual(
    typeErrors(
      `${await generateOpenApiTypes(requiredDefaultDocument)}\n${consumer}`,
    ),
    [],
  );
});

test("private request-view names avoid collisions with source component names", async () => {
  const collisionDocument = structuredClone(DOCUMENT);
  collisionDocument.components.schemas[
    "__RuntimeApiRequestView_53_68_61_72_65_64_46_69_6c_74_65_72"
  ] = {
    type: "object",
    properties: { source_owned: { type: "string" } },
    required: ["source_owned"],
  };
  const generated = await generateOpenApiTypes(collisionDocument);
  assert.deepEqual(typeErrors(`${generated}\n${VALID_CONSUMERS}`), []);
  assert.match(generated, /source_owned: string/);
});

test("unresolved external refs in request or response schema roles fail explicitly", async () => {
  const externalRequest = structuredClone(DOCUMENT);
  externalRequest.paths["/referenced"].post.requestBody.content[
    "application/json"
  ].schema = { $ref: "./external.yaml#/components/schemas/Body" };
  await assert.rejects(
    generateOpenApiTypes(externalRequest),
    /unresolved external reference.*request/i,
  );

  const externalResponse = structuredClone(DOCUMENT);
  externalResponse.paths["/response-only"].get.responses["200"].content[
    "application/json"
  ].schema = { $ref: "./external.yaml#/components/schemas/Reply" };
  await assert.rejects(
    generateOpenApiTypes(externalResponse),
    /unresolved external reference.*response/i,
  );
});

test("the checked-in WorkflowRunRequest intake ref narrows typed refs in TypeScript", async () => {
  const projectRoot = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../../..",
  );
  const sourceDocument = JSON.parse(
    await fs.readFile(
      path.join(projectRoot, "schemas/runtime_api_v1.openapi.json"),
      "utf8",
    ),
  );
  const intakeSchema =
    sourceDocument.components.schemas.WorkflowRunRequest.properties
      .production_case_intake_ref;
  assert.deepEqual(
    intakeSchema.anyOf.slice(1).map((branch) => branch.type),
    ["string", "null"],
  );
  assert.deepEqual(intakeSchema.anyOf[0].allOf[0], {
    $ref: "#/components/schemas/ArtifactRef-Input",
  });
  assert.deepEqual(intakeSchema.anyOf[0].allOf[1], {
    type: "object",
    properties: {
      kind: { const: "gy.loop.proof.root" },
      media_type: { const: "application/json" },
    },
    required: ["kind", "media_type"],
  });

  const validAndInvalidConsumers = `
type Request = components["schemas"]["WorkflowRunRequest"];
const validTyped: Request = {
  data_source: {data_snapshot_ref: "sha256:${"2".repeat(64)}"},
  production_case_intake_ref: {
    artifact_id: "sha256:${"1".repeat(64)}",
    kind: "gy.loop.proof.root",
    media_type: "application/json",
  },
};
const validSelectedProfile: Request = {
  data_source: {data_snapshot_ref: "sha256:${"2".repeat(64)}"},
  production_case_intake_ref: {
    artifact_id: "sha256:${"1".repeat(64)}",
    kind: "gy.loop.proof.root",
    media_type: "application/json",
    manifest_profile_sha256: "sha256:${"a".repeat(64)}",
  },
};
const validLegacy: Request = {
  data_source: {data_snapshot_ref: "sha256:${"2".repeat(64)}"},
  production_case_intake_ref: "sha256:${"1".repeat(64)}",
};
const validNull: Request = {
  data_source: {data_snapshot_ref: "sha256:${"2".repeat(64)}"},
  production_case_intake_ref: null,
};
const wrongKind: Request = {
  data_source: {data_snapshot_ref: "sha256:${"2".repeat(64)}"},
  production_case_intake_ref: {
    artifact_id: "sha256:${"1".repeat(64)}",
    // @ts-expect-error the typed ref branch must retain the source kind predicate
    kind: "fabric.data_snapshot",
    media_type: "application/json",
  },
};
const wrongMediaType: Request = {
  data_source: {data_snapshot_ref: "sha256:${"2".repeat(64)}"},
  production_case_intake_ref: {
    artifact_id: "sha256:${"1".repeat(64)}",
    kind: "gy.loop.proof.root",
    // @ts-expect-error the typed ref branch must retain the source media predicate
    media_type: "text/plain",
  },
};
void [validTyped, validSelectedProfile, validLegacy, validNull, wrongKind, wrongMediaType];
`;
  const generated = await generateOpenApiTypes(sourceDocument);
  assert.deepEqual(typeErrors(`${generated}\n${validAndInvalidConsumers}`), []);

  const withoutTypedPredicate = structuredClone(sourceDocument);
  withoutTypedPredicate.components.schemas.WorkflowRunRequest.properties.production_case_intake_ref.anyOf[0].allOf.pop();
  const wrongKindWithoutPredicate = `
type Request = components["schemas"]["WorkflowRunRequest"];
const admittedWithoutPredicate: Request = {
  data_source: {data_snapshot_ref: "sha256:${"2".repeat(64)}"},
  production_case_intake_ref: {
    artifact_id: "sha256:${"1".repeat(64)}",
    kind: "fabric.data_snapshot",
    media_type: "text/plain",
  },
};
void admittedWithoutPredicate;
`;
  assert.deepEqual(
    typeErrors(
      `${await generateOpenApiTypes(withoutTypedPredicate)}\n${wrongKindWithoutPredicate}`,
    ),
    [],
    "removing the generated typed-ref predicate must make the invalid pair assignable",
  );
});

test("the checked-in LexSearchRequest keeps its required list and optional intent semantics", async () => {
  const projectRoot = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../../..",
  );
  const sourceDocument = JSON.parse(
    await fs.readFile(
      path.join(projectRoot, "schemas/runtime_api_v1.openapi.json"),
      "utf8",
    ),
  );
  const sourceRequest = sourceDocument.components.schemas.LexSearchRequest;
  const actualOperation =
    sourceDocument.paths["/api/v1/control/lex/search"].post;
  assert.deepEqual(
    actualOperation.requestBody.content["application/json"].schema,
    { $ref: "#/components/schemas/LexSearchRequest" },
  );
  assert.ok(sourceRequest.required.includes("query"));
  assert.ok(sourceRequest.required.includes("output_dir"));
  assert.ok(!sourceRequest.required.includes("top_k"));
  assert.ok(!sourceRequest.required.includes("query_generation_intent"));

  const focusedDocument = {
    openapi: sourceDocument.openapi,
    info: sourceDocument.info,
    paths: {
      "/checked-in-lex-search": {
        post: {
          operationId: "checkedInLexSearch",
          requestBody: structuredClone(actualOperation.requestBody),
          responses: { 200: { description: "Focused request type probe." } },
        },
      },
    },
    components: {
      schemas: {
        LexSearchRequest: structuredClone(sourceRequest),
        LegalQueryGenerationIntentV1: structuredClone(
          sourceDocument.components.schemas.LegalQueryGenerationIntentV1,
        ),
      },
    },
  };
  const focusedConsumer = `
type LexRequest = paths["/checked-in-lex-search"]["post"]["requestBody"]["content"]["application/json"];
const omittedDefaultsAndIntent: LexRequest = {query: "policy", output_dir: "data/lex"};
const suppliedIntent: LexRequest = {query: "policy", output_dir: "data/lex", query_generation_intent: [{basis_kind: "legal_lex_facts_embedding", generation_id: "generation-1", inventory_json: "{}"}]};
// @ts-expect-error the source required list still requires query
const missingQuery: LexRequest = {output_dir: "data/lex"};
// @ts-expect-error the source required list still requires output_dir
const missingOutputDir: LexRequest = {query: "policy"};
// @ts-expect-error supplied intent stays constrained by its referenced source schema
const invalidIntent: LexRequest = {query: "policy", output_dir: "data/lex", query_generation_intent: [{basis_kind: "unknown", generation_id: "generation-1", inventory_json: "{}"}]};
void [omittedDefaultsAndIntent, suppliedIntent];
`;
  assert.deepEqual(
    typeErrors(
      `${await generateOpenApiTypes(focusedDocument)}\n${focusedConsumer}`,
    ),
    [],
  );
});

function requiredOnlyAllOfDocument(requiredConstraint = {}) {
  return {
    openapi: "3.1.0",
    info: { title: "allOf required property fixture", version: "1" },
    paths: {
      "/value": {
        get: {
          operationId: "readValue",
          responses: {
            200: {
              description: "Persisted value.",
              content: {
                "application/json": {
                  schema: { $ref: "#/components/schemas/ComposedValue" },
                },
              },
            },
          },
        },
        post: {
          operationId: "writeValue",
          requestBody: {
            required: true,
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/ComposedValue" },
              },
            },
          },
          responses: { 204: { description: "Accepted." } },
        },
      },
    },
    components: {
      schemas: {
        DefaultedValue: {
          type: "object",
          properties: { value: { type: "string", default: "fallback" } },
        },
        RequiredValue: {
          type: "object",
          required: ["value"],
          ...requiredConstraint,
        },
        ComposedValue: {
          allOf: [
            { $ref: "#/components/schemas/DefaultedValue" },
            { $ref: "#/components/schemas/RequiredValue" },
          ],
        },
      },
    },
  };
}

test("a required-only allOf ref keeps a defaulted property required and assignable", async () => {
  const document = requiredOnlyAllOfDocument();
  const generated = await generateOpenApiTypes(document);
  const consumer = `
type Input = paths["/value"]["post"]["requestBody"]["content"]["application/json"];
const supplied: Input = {value: "set"};
// @ts-expect-error the referenced allOf sibling requires this defaulted property
const omitted: Input = {};
void [supplied, omitted];
`;
  assert.deepEqual(typeErrors(`${generated}\n${consumer}`), []);

  const baselineNodes = await openapiTS(document);
  const baseline = normalizeRecursiveOpenApiTypes(
    `${COMMENT_HEADER}${astToString(baselineNodes)}`,
  );
  const presentOnly = `
type Input = paths["/value"]["post"]["requestBody"]["content"]["application/json"];
const supplied: Input = {value: "set"};
void supplied;
`;
  const omittedOnly = `
type Input = paths["/value"]["post"]["requestBody"]["content"]["application/json"];
const omitted: Input = {};
void omitted;
`;
  assert.ok(
    typeErrors(`${baseline}\n${presentOnly}`).length > 0,
    "the locked baseline's Record<string, never> branch rejects the valid value",
  );
  assert.ok(
    typeErrors(`${baseline}\n${omittedOnly}`).length > 0,
    "the locked baseline preserves requiredness even though its type is too narrow",
  );

  const typedAdditionalProperties = requiredOnlyAllOfDocument({
    additionalProperties: { type: "integer" },
  });
  typedAdditionalProperties.components.schemas.DefaultedValue.properties.value =
    {
      type: "integer",
      default: 7,
    };
  const typedProjection = await generateOpenApiTypes(typedAdditionalProperties);
  const typedConsumer = `
type Input = paths["/value"]["post"]["requestBody"]["content"]["application/json"];
const supplied: Input = {value: 7};
// @ts-expect-error the required additional property retains its integer schema
const invalidType: Input = {value: "7"};
void [supplied, invalidType];
`;
  assert.deepEqual(typeErrors(`${typedProjection}\n${typedConsumer}`), []);
});

test("nested recursive refs retain allOf requiredness without widening alternatives", async () => {
  const document = {
    openapi: "3.1.0",
    info: { title: "nested recursive required fixture", version: "1" },
    paths: {
      "/nested": {
        post: {
          operationId: "writeNested",
          requestBody: {
            required: true,
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/Envelope" },
              },
            },
          },
          responses: { 204: { description: "Accepted." } },
        },
        get: {
          operationId: "readNested",
          responses: {
            200: {
              description: "Persisted nested value.",
              content: {
                "application/json": {
                  schema: { $ref: "#/components/schemas/Envelope" },
                },
              },
            },
          },
        },
      },
    },
    components: {
      schemas: {
        Envelope: {
          type: "object",
          properties: {
            payload: { $ref: "#/components/schemas/RecursiveValue" },
          },
          required: ["payload"],
        },
        DefaultedValue: {
          type: "object",
          properties: { value: { type: "string", default: "fallback" } },
        },
        RequiredValue: { type: "object", required: ["value"] },
        RecursiveValue: {
          allOf: [
            { $ref: "#/components/schemas/DefaultedValue" },
            { $ref: "#/components/schemas/RequiredValue" },
          ],
          properties: {
            next: { $ref: "#/components/schemas/RecursiveValue" },
          },
        },
        Choice: {
          oneOf: [
            { type: "object", required: ["left"] },
            { type: "object", required: ["right"] },
          ],
        },
      },
    },
  };
  document.paths["/nested"].post.requestBody.content[
    "application/json"
  ].schema = {
    type: "object",
    properties: {
      envelope: { $ref: "#/components/schemas/Envelope" },
      choice: { $ref: "#/components/schemas/Choice" },
    },
    required: ["envelope", "choice"],
  };

  const generated = await generateOpenApiTypes(document);
  const consumer = `
type Input = paths["/nested"]["post"]["requestBody"]["content"]["application/json"];
const supplied: Input = {
  envelope: {payload: {value: "set", next: {value: "next"}}},
  choice: {left: "left"},
};
// @ts-expect-error the nested referenced allOf sibling requires value
const missingNestedValue: Input = {envelope: {payload: {next: {value: "next"}}}, choice: {right: "right"}};
// @ts-expect-error the oneOf alternatives remain branch-required
const missingChoice: Input = {envelope: {payload: {value: "set"}}, choice: {}};
void [supplied, missingNestedValue, missingChoice];
`;
  assert.deepEqual(typeErrors(`${generated}\n${consumer}`), []);
});

test("an allOf required name excluded by additionalProperties is refused", async () => {
  const impossibleDocument = requiredOnlyAllOfDocument({
    additionalProperties: false,
  });
  const before = structuredClone(impossibleDocument);
  await assert.rejects(
    generateOpenApiTypes(impossibleDocument),
    /required property.*additionalProperties.*false/i,
  );
  assert.deepEqual(
    impossibleDocument,
    before,
    "an impossible request schema must be refused without mutating the caller's OpenAPI object",
  );
});

test("schema refs reject OpenAPI objects and allow actual inline schema nodes", async () => {
  const wrongRoleDocument = requiredOnlyAllOfDocument();
  wrongRoleDocument.components.responses = {
    Else: {
      description: "A response object is not a schema.",
      content: {
        "application/json": {
          schema: {
            type: "object",
            properties: { value: { type: "string" } },
          },
        },
      },
    },
  };
  wrongRoleDocument.paths["/value"].post.requestBody.content[
    "application/json"
  ].schema = { $ref: "#/components/responses/Else" };
  await assert.rejects(
    generateOpenApiTypes(wrongRoleDocument),
    /invalid schema reference.*components\/responses\/Else.*not an OpenAPI Schema Object/i,
  );

  const wrongRoleTargets = [
    "#/components/parameters/Else",
    "#/components/requestBodies/Else",
    "#/components/pathItems/Else",
  ];
  for (const target of wrongRoleTargets) {
    const document = requiredOnlyAllOfDocument();
    document.components.parameters = {
      Else: { name: "query", in: "query", schema: { type: "string" } },
    };
    document.components.requestBodies = {
      Else: { content: { "application/json": { schema: { type: "string" } } } },
    };
    document.components.pathItems = {
      Else: { get: { responses: { 200: { description: "A path item." } } } },
    };
    document.paths["/value"].post.requestBody.content[
      "application/json"
    ].schema = { $ref: target };
    await assert.rejects(
      generateOpenApiTypes(document),
      /invalid schema reference.*not an OpenAPI Schema Object/i,
      `a schema edge must reject ${target}`,
    );
  }

  const nestedSchemaDocument = requiredOnlyAllOfDocument();
  nestedSchemaDocument.components.responses = {
    Else: {
      description: "A response containing a reusable schema node.",
      content: {
        "application/json": {
          schema: {
            type: "object",
            properties: { value: { type: "string" } },
          },
        },
      },
    },
  };
  nestedSchemaDocument.paths["/value"].post.requestBody.content[
    "application/json"
  ].schema = {
    $ref: "#/components/responses/Else/content/application~1json/schema",
  };
  await assert.doesNotReject(generateOpenApiTypes(nestedSchemaDocument));
});

test("reusable OpenAPI object refs must target the object kind of their source slot", async () => {
  const wrongParameter = requiredOnlyAllOfDocument();
  wrongParameter.components.responses = {
    Else: { description: "Response, not parameter." },
  };
  wrongParameter.paths["/value"].post.parameters = [
    { $ref: "#/components/responses/Else" },
  ];
  await assert.rejects(
    generateOpenApiTypes(wrongParameter),
    /invalid parameter reference.*not an OpenAPI Parameter Object/i,
  );

  const wrongRequestBody = requiredOnlyAllOfDocument();
  wrongRequestBody.components.responses = {
    Else: { description: "Response, not request body." },
  };
  wrongRequestBody.paths["/value"].post.requestBody = {
    $ref: "#/components/responses/Else",
  };
  await assert.rejects(
    generateOpenApiTypes(wrongRequestBody),
    /invalid requestBody reference.*not an OpenAPI Request Body Object/i,
  );

  const wrongResponse = requiredOnlyAllOfDocument();
  wrongResponse.components.parameters = {
    Else: { name: "query", in: "query", schema: { type: "string" } },
  };
  wrongResponse.paths["/value"].get.responses["200"] = {
    $ref: "#/components/parameters/Else",
  };
  await assert.rejects(
    generateOpenApiTypes(wrongResponse),
    /invalid response reference.*not an OpenAPI Response Object/i,
  );

  const wrongHeader = requiredOnlyAllOfDocument();
  wrongHeader.components.responses = {
    Else: { description: "Response, not header." },
  };
  wrongHeader.paths["/value"].get.responses["200"].headers = {
    "X-Value": { $ref: "#/components/responses/Else" },
  };
  await assert.rejects(
    generateOpenApiTypes(wrongHeader),
    /invalid header reference.*not an OpenAPI Header Object/i,
  );

  const wrongPathItem = requiredOnlyAllOfDocument();
  wrongPathItem.components.responses = {
    Else: { description: "Response, not path item." },
  };
  wrongPathItem.paths["/value"] = {
    $ref: "#/components/responses/Else",
  };
  await assert.rejects(
    generateOpenApiTypes(wrongPathItem),
    /invalid pathItem reference.*not an OpenAPI Path Item Object/i,
  );

  const wrongCallback = requiredOnlyAllOfDocument();
  wrongCallback.components.responses = {
    Else: { description: "Response, not callback." },
  };
  wrongCallback.paths["/value"].post.callbacks = {
    result: { $ref: "#/components/responses/Else" },
  };
  await assert.rejects(
    generateOpenApiTypes(wrongCallback),
    /invalid callback reference.*not an OpenAPI Callback Object/i,
  );
});
