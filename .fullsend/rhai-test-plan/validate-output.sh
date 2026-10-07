#!/usr/bin/env bash
set -euo pipefail

: "${FULLSEND_OUTPUT_SCHEMA:?FULLSEND_OUTPUT_SCHEMA is required}"
result_file="output/agent-result.json"
test -f "$result_file" || { echo "FAIL: agent-result.json is missing" >&2; exit 1; }
python3 - "$result_file" "$FULLSEND_OUTPUT_SCHEMA" <<'PY'
import json
import sys
from jsonschema import validate

with open(sys.argv[1], encoding="utf-8") as result_file:
    result = json.load(result_file)
with open(sys.argv[2], encoding="utf-8") as schema_file:
    schema = json.load(schema_file)
validate(result, schema)
PY
