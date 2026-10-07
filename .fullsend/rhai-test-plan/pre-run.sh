#!/usr/bin/env bash
set -euo pipefail

: "${TARGET_REPO_DIR:?TARGET_REPO_DIR is required}"
: "${FULLSEND_TASK:?FULLSEND_TASK is required}"
: "${FULLSEND_SOURCE_KEY:?FULLSEND_SOURCE_KEY is required}"
: "${FULLSEND_RUN_DIR:?FULLSEND_RUN_DIR is required}"

source_repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
cd -- "$source_repo"
python3 -m scripts.fullsend_harness check-input \
  "$FULLSEND_TASK" "$FULLSEND_SOURCE_KEY" "$FULLSEND_RUN_DIR" "${FULLSEND_FEATURE_DIR:-}"
test -f .fullsend/rhai-test-plan/plugin/.claude-plugin/plugin.json
test -d "$TARGET_REPO_DIR"

if [[ "$FULLSEND_TASK" == create-cases ]]; then
  test -f "$TARGET_REPO_DIR/$FULLSEND_FEATURE_DIR/TestPlanReview.md"
else
  test ! -e "$TARGET_REPO_DIR/$FULLSEND_RUN_DIR/TestPlanReview.md"
fi
