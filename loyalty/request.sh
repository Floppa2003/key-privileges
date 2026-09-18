#!/usr/bin/env bash
# Trusted main-only dispatcher. Never reads instructions or values from scraped pages.
set -euo pipefail

if [[ "${GITHUB_REPOSITORY:-}" != "Floppa2003/key-privileges" || "${GITHUB_REF:-}" != "refs/heads/main" ]]; then
  echo "STOP: requests are allowed only from the configured repository main branch." >&2
  exit 1
fi
if [[ "${LOYALTY_SHEETS_SYNC:-}" != "true" ]]; then
  echo "STOP: LOYALTY_SHEETS_SYNC must be true for a publishing request." >&2
  exit 1
fi
for name in GOOGLE_SERVICE_ACCOUNT GOOGLE_WORKLOAD_IDENTITY_PROVIDER DISCOUNTS_SPREADSHEET_ID GH_TOKEN; do
  if [[ -z "${!name:-}" ]]; then
    printf 'STOP: required configuration is missing: %s\n' "$name" >&2
    exit 1
  fi
done

source_ids="$(python "$(dirname "$0")/source_selection.py" --sources "${LOYALTY_SOURCE_IDS:-}")"
selection=()
if [[ -n "$source_ids" ]]; then
  selection=(-f "sources=$source_ids")
fi

gh workflow run loyalty.yml --repo "$GITHUB_REPOSITORY" --ref main -f limit=500 -f publish=true "${selection[@]}"
printf '%s\n' 'DISPATCH_ACCEPTED: target workflow requested; this is not publication success. Verify its run and Sheets readback.'
