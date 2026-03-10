export const API_BASE_URL = import.meta.env.VITE_RUNTIME_API_URL?.trim() || "";
export const LOGIN_PATH = "/login";
export const LOGIN_URL = import.meta.env.VITE_LOGIN_URL?.trim() || LOGIN_PATH;

export const RUNS_DEFAULT_LIMIT = 50;
export const RUNS_SAMPLE_LIMIT = 24;
export const HEALTH_REFETCH_MS = 15_000;
export const DEFAULT_LEX_OUTPUT_DIR = "data/lex_knowledge";
export const RUNS_SAMPLE_STALE_MS = 60_000;
export const RUN_ACTIVE_STALE_MS = 10_000;
export const RUN_ACTIVE_REFETCH_MS = 10_000;
export const RUN_TERMINAL_STALE_MS = 300_000;
export const RUN_BOOTSTRAP_REFETCH_MS = 2_000;
export const RUNS_LIVE_RETRY_MS = 4_000;
export const RUNS_LIVE_HEARTBEAT_MS = 15_000;
export const RUNS_LIVE_INVALIDATE_DEDUPE_MS = 750;
