#!/usr/bin/env bash

set -euo pipefail

GH_RETRY_ATTEMPTS_DEFAULT="${GH_RETRY_ATTEMPTS_DEFAULT:-4}"
GH_RETRY_DELAY_SECONDS_DEFAULT="${GH_RETRY_DELAY_SECONDS_DEFAULT:-2}"

require_gh_token() {
  if [[ -z "${GH_TOKEN:-}" ]]; then
    echo "GH_TOKEN is required" >&2
    return 2
  fi
}

gh_retry() {
  local attempts delay attempt output status
  attempts="${GH_RETRY_ATTEMPTS:-$GH_RETRY_ATTEMPTS_DEFAULT}"
  delay="${GH_RETRY_DELAY_SECONDS:-$GH_RETRY_DELAY_SECONDS_DEFAULT}"
  attempt=1

  while (( attempt <= attempts )); do
    if output="$("$@" 2>&1)"; then
      printf "%s" "$output"
      return 0
    fi

    status=$?
    if (( attempt == attempts )); then
      echo "$output" >&2
      return "$status"
    fi

    echo "gh command failed (attempt ${attempt}/${attempts}), retrying in ${delay}s" >&2
    sleep "$delay"
    delay=$((delay * 2))
    attempt=$((attempt + 1))
  done

  return 1
}
