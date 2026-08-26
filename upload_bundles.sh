#!/usr/bin/env bash
set -euo pipefail

FHIR_URL="${FHIR_URL:-http://localhost:8180/fhir}"
FHIR_USER="${FHIR_USER:-admin}"
FHIR_PASS="${FHIR_PASS:-password}"
OUTPUT_DIR="${OUTPUT_DIR:-$(dirname "$0")/output}"

success=0
failed=0
failed_files=()

total=$(find "$OUTPUT_DIR" -name "*.json" | wc -l)
count=0

for file in "$OUTPUT_DIR"/**/*.json; do
  count=$((count + 1))
  rel="${file#$OUTPUT_DIR/}"
  printf "[%d/%d] Uploading %s ... " "$count" "$total" "$rel"

  http_code=$(curl -s -o /tmp/fhir_response.json -w "%{http_code}" \
    --request POST \
    --url "$FHIR_URL" \
    --user "$FHIR_USER:$FHIR_PASS" \
    --header "Content-Type: application/fhir+json" \
    --data "@$file")

  if [[ "$http_code" =~ ^2 ]]; then
    echo "OK ($http_code)"
    success=$((success + 1))
  else
    echo "FAILED ($http_code)"
    cat /tmp/fhir_response.json
    echo
    failed=$((failed + 1))
    failed_files+=("$rel")
  fi
done

echo
echo "===== Upload complete ====="
echo "  Success: $success"
echo "  Failed:  $failed"

if [[ ${#failed_files[@]} -gt 0 ]]; then
  echo
  echo "Failed files:"
  for f in "${failed_files[@]}"; do
    echo "  - $f"
  done
fi
