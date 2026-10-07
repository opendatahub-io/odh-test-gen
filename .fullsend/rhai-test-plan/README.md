# Fullsend test planner harness

This harness dispatches the existing `test-plan-create` and
`test-plan-create-cases` skills. It uses Fullsend's built-in `coder` role, a
Claude plugin resource, a read-only Jira OpenShell profile, and a host-side
artifact validator. The generated plans remain in the target data workspace.

The source repository has convenience symlinks. Fullsend plugin resources
reject symlinks, and both skills refer to scripts two directories above
`CLAUDE_SKILL_DIR`. Before each run, generate the ignored plugin directory:

```bash
uv run python -m scripts.fullsend_harness prepare . .fullsend/rhai-test-plan/plugin
```

The bundle contains `.claude-plugin/`, `skills/`, `scripts/`, `pyproject.toml`,
and `uv.lock`. The target checkout is separate and receives only validated
feature artifacts in the post script. `prepare` must run before `fullsend run`
because Fullsend resolves plugins before its pre script.

`FULLSEND_TASK` is `create` or `create-cases`; `FULLSEND_SOURCE_KEY`,
`FULLSEND_RUN_DIR`, and `FULLSEND_FEATURE_DIR` identify the one requested
feature. The runner invokes the harness twice with the existing score gate in
between. The post script reads `agent-result.json`, verifies the receipt and
feature tree, then copies that tree into the host checkout. It executes no
agent-written code.

The RFE Creator harness supplies the pinned image, policy, Vertex provider,
Jira provider, and validation-loop pattern. The test planner adds a bundled
plugin and two explicit task invocations because its skills and data live in
different repositories.

The Python package provider attaches a profile that allows only `uv` to read
from the package index hosts required by `uv sync --extra dev`. The plugin uses
its committed lockfile.

The result receipt uses `strategy_issue` for the Jira key. Fullsend sanitizes
JSON fields named `source_key` as credential-like data before the host post
script reads them; the renamed field remains schema-validated and checked
against the host's requested strategy.

This is a comparison harness. The Jira profile denies writes. The caller must
keep host Jira, Pulse, GitLab, and GitHub publication disabled. Production
switching requires evidence from real Fullsend runs and human review.

Generated with Codex.
