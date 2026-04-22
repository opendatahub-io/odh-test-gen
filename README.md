# Test Plan

Claude Code skills for generating test plans and test cases from RHOAI strategies.

## Skills

### User-invocable

| Skill | Description |
|-------|-------------|
| `/test-plan.create` | Generate a test plan from a strategy (RHAISTRAT), with optional ADR |
| `/test-plan.create-cases` | Generate individual test case files from an existing test plan |
| `/test-plan.case-implement` | Generate executable test automation code from TC specifications with intelligent placement |
| `/test-plan.publish` | Publish test plan artifacts to GitHub — branch, commit, and open a PR |
| `/test-plan.resolve-feedback` | Assess PR review comments, let the user decide what to apply, and push updates |
| `/test-plan.score` | Score an existing test plan using quality rubric (without auto-revision) |

### Sub-agents (forked, non-user-invocable)

| Skill | Description |
|-------|-------------|
| `test-plan.analyze.endpoints` | Extract feature scope, test objectives, and API endpoints/methods |
| `test-plan.analyze.risks` | Determine test levels, types, priorities, and risks |
| `test-plan.analyze.infra` | Identify environment config, test data, infrastructure requirements |
| `test-plan.analyze.placement` | Analyze test cases and recommend placement (component repo vs downstream) |
| `test-plan.review` | Review test plan for completeness, consistency, and quality |
| `test-plan.create.test-function` | Generate test function code from TC specification matching repo conventions |
| `test-plan.score.test-function` | Score generated test function code using 5-criteria quality rubric |

## Installation

### Option 1: Install from Marketplace (Recommended)

Install from the [opendatahub-io/skills-registry](https://github.com/opendatahub-io/skills-registry) marketplace:

```bash
# Add the marketplace (one-time)
claude plugin marketplace add opendatahub-io/skills-registry

# Install test-plan plugin
/plugin install test-plan@opendatahub-skills
```

This clones the repository and makes skills immediately available. Then install Python dependencies:

```bash
cd ~/.claude/plugins/cache/opendatahub-skills/test-plan/<version>
uv pip install -e ".[dev]"
```

Use skills:
```bash
/test-plan.create RHAISTRAT-400
/test-plan.create-cases
/test-plan.publish
```

### Option 2: Manual Clone (For Contributors)

Clone the repository directly:

```bash
git clone https://github.com/fege/test-plan ~/Code/test-plan
cd ~/Code/test-plan
uv pip install -e ".[dev]"
```

Skills are available from `.claude/skills/` directory.

**Note**: Skills use symlinks for shared utilities (`test-plan-common/scripts → ../../../scripts`). Both installation methods clone the full repository, so symlinks resolve correctly.

## Usage

```bash
# Generate a test plan from a Jira strategy
/test-plan.create RHAISTRAT-400

# Generate a test plan with an ADR for extra technical depth
/test-plan.create RHAISTRAT-400 /path/to/adr.pdf

# Generate test cases from an existing test plan
/test-plan.create-cases

# Generate test cases for a specific feature directory
/test-plan.create-cases mcp_catalog

# Publish a test plan to GitHub as a PR
/test-plan.publish tool_calling_metadata

# Publish with reviewers
/test-plan.publish tool_calling_metadata --reviewers alice,bob

# Publish to a different repo
/test-plan.publish tool_calling_metadata --repo org/test-plans-repo

# Resolve PR review feedback
/test-plan.resolve-feedback https://github.com/org/test-plans-repo/pull/42

# Generate executable test code from test cases
/test-plan.case-implement mcp_catalog

# Generate code for specific test cases only
/test-plan.case-implement mcp_catalog --test-cases TC-API-001,TC-API-002

# Score a test plan without triggering auto-revision
/test-plan.score mcp_catalog
```

## Pipeline

```
/test-plan.create RHAISTRAT-400
        │
        ├── test-plan.analyze.endpoints  ─┐
        ├── test-plan.analyze.risks      ─┤  (parallel)
        └── test-plan.analyze.infra      ─┘
                    │
                    ▼
            TestPlan.md + TestPlanGaps.md
                    │
                    ▼
            Gap resolution (HITL)
                    │
                    ▼
            test-plan.review (auto-revision, scoring)
                    │
                    ▼
        /test-plan.create-cases (optional auto-run)
                    │
                    ▼
            TC-*.md + INDEX.md
                    │
                    ├─────────────────────┐
                    │                     │
                    ▼                     ▼
        /test-plan.publish    /test-plan.case-implement
                    │                     │
                    │                     ├── test-plan.analyze.placement
                    │                     ├── test-plan.create.test-function (per TC)
                    │                     └── test-plan.score.test-function (per TC)
                    │                     │
                    ▼                     ▼
            GitHub PR          Generated test code in target repos
                    │
                    ▼
            GitHub PR (with optional reviewers)
                    │
                    ▼
        /test-plan.resolve-feedback (after PR reviews)
                    │
                    ▼
            Updated artifacts + new commit on PR branch
```

## Prerequisites

### Required for All Users
- [Claude Code](https://claude.ai/code) installed
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Git installed
- Python 3.10 or higher

### Required for Specific Features
- **Jira integration**: [Atlassian MCP server](https://support.atlassian.com/atlassian-rovo-mcp-server/docs/getting-started-with-the-atlassian-remote-mcp-server/) configured (for `/test-plan.create`)
- **GitHub publishing**: [GitHub CLI (`gh`)](https://cli.github.com/) installed and authenticated (for `/test-plan.publish` and `/test-plan.resolve-feedback`)
- **Test implementation**: Local or cloned target repositories (for `/test-plan.case-implement`)

## Repository Structure

```
.claude/skills/
├── test-plan.create/
│   ├── SKILL.md
│   └── test-plan-template.md
├── test-plan.analyze.endpoints/
│   └── SKILL.md
├── test-plan.analyze.risks/
│   └── SKILL.md
├── test-plan.analyze.infra/
│   └── SKILL.md
├── test-plan.review/
│   └── SKILL.md
├── test-plan.create-cases/
│   ├── SKILL.md
│   └── test-case-template.md
├── test-plan.publish/
│   └── SKILL.md
└── test-plan.resolve-feedback/
    └── SKILL.md
```

## Development

### Prerequisites

Install the package in development mode with dev dependencies:

```bash
uv pip install -e ".[dev]"
```

This installs:
- The `test-plan` package in editable mode (changes are immediately available)
- `pyyaml` - YAML frontmatter parsing
- `pytest` - Test framework
- `pytest-cov` - Coverage reporting

### Running Tests

Run all tests:
```bash
uv run pytest tests/ -v
```

Run a specific test file:
```bash
uv run pytest tests/test_schema_validation.py -v
```

Run tests with coverage:
```bash
uv run pytest tests/ -v --cov=scripts --cov-report=term-missing
```

Run a specific test:
```bash
uv run pytest tests/test_schema_validation.py::TestPlanSchemaValidation::test_field_validation -v
```

### Test Structure

```
tests/
├── constants.py                      # Shared test data constants
├── unit/                             # Unit tests (fast, isolated)
│   ├── test_schema_validation.py     # Schema validation (test-plan, test-case, test-gaps)
│   ├── test_frontmatter_operations.py # Read, write, update operations
│   └── test_frontmatter_cli_unit.py  # CLI interface tests
└── integration/                      # Integration tests (subprocess, file I/O)
    ├── test_artifact_utils_validation.py # Review schema validation
    ├── test_filter_for_revision.py   # Revision filter (subprocess)
    └── test_preserve_review_state.py # State persistence
```
