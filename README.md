# Test Plan

Claude Code skills for generating test plans and test cases from RHOAI strategies.

## Skills

### User-invocable

| Skill | Description |
|-------|-------------|
| `/test-plan.create` | Generate a test plan from a strategy (RHAISTRAT), with optional ADR |
| `/test-plan.create-cases` | Generate individual test case files from an existing test plan |

### Sub-agents (forked, non-user-invocable)

| Skill | Description |
|-------|-------------|
| `test-plan.analyze.endpoints` | Extract feature scope, test objectives, and API endpoints/methods |
| `test-plan.analyze.risks` | Determine test levels, types, priorities, and risks |
| `test-plan.analyze.infra` | Identify environment config, test data, infrastructure requirements |
| `test-plan.review` | Review test plan for completeness, consistency, and quality |

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
            test-plan.review
                    │
                    ▼
        /test-plan.create-cases (optional auto-run)
                    │
                    ▼
            TC-*.md + INDEX.md
```

## Prerequisites

- Claude Code installed
- Atlassian MCP server configured (for Jira strategy fetching)

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
└── test-plan.create-cases/
    ├── SKILL.md
    └── test-case-template.md
```
