#!/usr/bin/env bash
set -euo pipefail

: "${FULLSEND_VALIDATED_ITERATION_DIR:?validated result directory is required}"
: "${REPO_DIR:?downloaded repository is required}"
: "${TARGET_REPO_DIR:?target repository is required}"

source_repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
cd -- "$source_repo"
python3 -m scripts.fullsend_harness copy-back \
  "$FULLSEND_VALIDATED_ITERATION_DIR/agent-result.json" \
  "$REPO_DIR" "$TARGET_REPO_DIR" \
  "$FULLSEND_TASK" "$FULLSEND_SOURCE_KEY" "$FULLSEND_RUN_DIR"
