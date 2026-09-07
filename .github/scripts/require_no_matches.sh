#!/usr/bin/env bash
# A policy scan passes only when ripgrep actually establishes no matches.
set -euo pipefail

if ! command -v rg >/dev/null 2>&1; then
  echo "::error::Required scan binary rg (ripgrep) is missing from PATH." >&2
  exit 127
fi

scan_status=0
rg "$@" || scan_status=$?
case "${scan_status}" in
  0)
    echo "::error::Forbidden matches found by ripgrep." >&2
    exit 1
    ;;
  1)
    exit 0
    ;;
  *)
    echo "::error::ripgrep could not complete the scan (status ${scan_status})." >&2
    exit "${scan_status}"
    ;;
esac
