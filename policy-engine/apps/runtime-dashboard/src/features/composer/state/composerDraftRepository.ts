import { z } from "zod";

import {
  createAuthorityLocalStateEnvelopeFamily,
  type AuthorityLocalScope,
} from "@/app/offline/authorityLocalState";
import {
  deleteComposerDraftRecord,
  loadComposerDraftRecord,
  saveComposerDraftRecord,
} from "@/app/offline/composerDraftDb";
import {
  naturalLanguageLaunchSchema,
  workflowLaunchSchema,
  type NaturalLanguageLaunchFormValues,
  type WorkflowLaunchFormValues,
} from "@/features/composer/domain/forms";

export type ComposerDraftMode = "nl" | "workflow";
export type ComposerDraftValues =
  | NaturalLanguageLaunchFormValues
  | WorkflowLaunchFormValues;
export type ComposerDraftRecord = {
  fromRunId: string | null;
  key: string;
  mode: ComposerDraftMode;
  updatedAt: number;
  values: ComposerDraftValues;
};

type StoredComposerDraft = Readonly<{ envelope: unknown; key: string }>;

export type ComposerDraftDatabasePort = Readonly<{
  delete: (key: string) => Promise<void>;
  get: (key: string) => Promise<unknown>;
  put: (record: StoredComposerDraft) => Promise<void>;
}>;

const COMPOSER_DRAFT_TTL_MS = 24 * 60 * 60 * 1_000;
const COMPOSER_DRAFT_FAMILY = "composer-draft" as const;

const workflowDraftValuesSchema = workflowLaunchSchema
  .extend({ dataSourceRef: z.string() })
  .strict();
const naturalLanguageDraftValuesSchema = naturalLanguageLaunchSchema
  .extend({
    nlRequest: z.string(),
    selectedLlmModels: z.array(
      naturalLanguageLaunchSchema.shape.selectedLlmModels.element,
    ),
  })
  .strict();
const workflowDraftSchema = z
  .object({
    fromRunId: z.string().min(1).nullable(),
    key: z.string().min(1),
    mode: z.literal("workflow"),
    updatedAt: z.number().int().nonnegative(),
    values: workflowDraftValuesSchema,
  })
  .strict();
const naturalLanguageDraftSchema = z
  .object({
    fromRunId: z.string().min(1).nullable(),
    key: z.string().min(1),
    mode: z.literal("nl"),
    updatedAt: z.number().int().nonnegative(),
    values: naturalLanguageDraftValuesSchema,
  })
  .strict();
const composerDraftSchema = z.discriminatedUnion("mode", [
  workflowDraftSchema,
  naturalLanguageDraftSchema,
]);
const storedComposerDraftSchema = z
  .object({ envelope: z.unknown(), key: z.string().min(1) })
  .strict();

function parseComposerDraft(value: unknown): ComposerDraftRecord | null {
  const parsed = composerDraftSchema.safeParse(value);
  if (!parsed.success) {
    return null;
  }
  const draft = parsed.data as ComposerDraftRecord;
  return draft.key === buildComposerDraftKey(draft.mode, draft.fromRunId)
    ? draft
    : null;
}

function composerDraftCodec() {
  return {
    decode(value: unknown): ComposerDraftRecord | null {
      return parseComposerDraft(value);
    },
    encode(value: ComposerDraftRecord): unknown {
      return parseComposerDraft(value);
    },
  };
}

/** Builds the logical composer draft slot used inside the scoped physical key. */
export function buildComposerDraftKey(
  mode: ComposerDraftMode,
  fromRunId: string | null,
) {
  return `${mode}:${fromRunId ?? "new"}`;
}

/**
 * Creates the async IndexedDB adapter for the canonical local-state envelope.
 * The database port owns I/O only; the shared owner owns scope, keys, TTL,
 * clock, version, and codec validation.
 */
export function createComposerDraftRepository(config?: {
  clock?: () => Date;
  database?: ComposerDraftDatabasePort;
}) {
  const database: ComposerDraftDatabasePort = config?.database ?? {
    delete: deleteComposerDraftRecord,
    get: loadComposerDraftRecord,
    put: saveComposerDraftRecord,
  };
  const owner = createAuthorityLocalStateEnvelopeFamily({
    clock: config?.clock ?? (() => new Date()),
    codec: composerDraftCodec(),
    family: COMPOSER_DRAFT_FAMILY,
    ttlMs: COMPOSER_DRAFT_TTL_MS,
    version: 1,
  });

  async function load(
    scope: AuthorityLocalScope | null | undefined,
    key: string,
  ): Promise<ComposerDraftRecord | null> {
    const physicalKey = owner.key({ scope, slot: key });
    if (!physicalKey) {
      return null;
    }
    let stored: unknown;
    try {
      stored = await database.get(physicalKey);
    } catch {
      return null;
    }
    const record = storedComposerDraftSchema.safeParse(stored);
    if (!record.success || record.data.key !== physicalKey) {
      return null;
    }
    const draft = owner.decode({
      envelope: record.data.envelope,
      fallback: null,
      scope,
      slot: key,
    });
    return draft?.key === key ? draft : null;
  }

  async function save(
    scope: AuthorityLocalScope | null | undefined,
    draft: ComposerDraftRecord,
  ): Promise<boolean> {
    let issued: ReturnType<typeof owner.encode>;
    try {
      issued = owner.encode({ scope, slot: draft.key, value: draft });
    } catch {
      return false;
    }
    if (!issued) {
      return false;
    }
    try {
      await database.put({ envelope: issued.envelope, key: issued.key });
      return true;
    } catch {
      return false;
    }
  }

  async function remove(
    scope: AuthorityLocalScope | null | undefined,
    key: string,
  ): Promise<boolean> {
    const physicalKey = owner.key({ scope, slot: key });
    if (!physicalKey) {
      return false;
    }
    try {
      await database.delete(physicalKey);
      return true;
    } catch {
      return false;
    }
  }

  return Object.freeze({ delete: remove, load, save });
}

const composerDraftRepository = createComposerDraftRepository();

export function loadComposerDraft(
  scope: AuthorityLocalScope | null | undefined,
  key: string,
) {
  return composerDraftRepository.load(scope, key);
}

export function saveComposerDraft(
  scope: AuthorityLocalScope | null | undefined,
  draft: ComposerDraftRecord,
) {
  return composerDraftRepository.save(scope, draft);
}

export function deleteComposerDraft(
  scope: AuthorityLocalScope | null | undefined,
  key: string,
) {
  return composerDraftRepository.delete(scope, key);
}
