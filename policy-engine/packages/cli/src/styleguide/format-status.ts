import {
  CLI_SEVERITY_TOKENS,
  CLI_PROGRESS_TOKENS,
  CLI_STATUS_DESCRIPTIONS,
  CLI_STATUS_TOKENS,
  type CliProgressState,
  type CliSeverity,
  type CliTrustStatus,
} from "./tokens";

type FormatStatusOptions = {
  includeDescription?: boolean;
  severity?: CliSeverity;
};

export function formatStatus(
  status: CliTrustStatus,
  options: FormatStatusOptions = {},
) {
  const severity = options.severity
    ? `${CLI_SEVERITY_TOKENS[options.severity]} `
    : "";
  const token = `${severity}${CLI_STATUS_TOKENS[status]}`;

  if (!options.includeDescription) {
    return token;
  }

  return `${token} ${CLI_STATUS_DESCRIPTIONS[status]}`;
}

export function formatSeverity(severity: CliSeverity, message: string) {
  return `${CLI_SEVERITY_TOKENS[severity]} ${message}`;
}

export function formatProgress(
  state: CliProgressState,
  label: string,
  options: { current?: number; total?: number } = {},
) {
  const count =
    options.current !== undefined && options.total !== undefined
      ? ` ${options.current}/${options.total}`
      : "";
  return `${CLI_PROGRESS_TOKENS[state]}${count} ${label}`;
}
