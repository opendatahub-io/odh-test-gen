"""Artifact schema definitions, frontmatter read/write/validate for test plan artifacts.

Owns all structured metadata for test plan, test case, and test gap artifacts.
Skills and scripts use this module instead of regex-parsing markdown prose.

Frontmatter is stored as YAML between --- delimiters at the top of markdown files.

Requires:
    pip install pyyaml
"""

import os
import re
import sys

try:
    import yaml
except ImportError:
    print(
        "Error: PyYAML is required but not installed.\n"
        "Install it with: uv pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)


# ─── Schema Definitions ────────────────────────────────────────────────────────

# Each schema is a dict of field_name -> field_spec.
# field_spec keys:
#   type:     "string" | "int" | "bool" | "list"
#   required: bool (default False)
#   enum:     list of allowed values (optional)
#   pattern:  regex pattern the value must match (optional, strings only)
#   default:  default value when not provided (optional)

SCHEMAS = {
    "test-plan": {
        "feature": {
            "type": "string",
            "required": True,
        },
        "strat_key": {
            "type": "string",
            "required": True,
            "pattern": r"^RHAISTRAT-\d+$",
        },
        "version": {
            "type": "string",
            "required": True,
            "pattern": r"^\d+\.\d+\.\d+$",
        },
        "status": {
            "type": "string",
            "required": True,
            "enum": ["Draft", "In Review", "Approved"],
        },
        "last_updated": {
            "type": "string",
            "required": True,
        },
        "author": {
            "type": "string",
            "required": True,
        },
        "additional_docs": {
            "type": "list",
            "required": False,
            "default": [],
        },
        "reviewers": {
            "type": "list",
            "required": False,
            "default": [],
        },
    },
    "test-case": {
        "test_case_id": {
            "type": "string",
            "required": True,
            "pattern": r"^TC-[A-Z]+-\d+$",
        },
        "strat_key": {
            "type": "string",
            "required": True,
            "pattern": r"^RHAISTRAT-\d+$",
        },
        "priority": {
            "type": "string",
            "required": True,
            "enum": ["P0", "P1", "P2"],
        },
        "status": {
            "type": "string",
            "required": True,
            "enum": ["Draft", "Ready", "Automated", "Blocked"],
        },
        "automation_status": {
            "type": "string",
            "required": False,
            "enum": ["Not Started", "In Progress", "Complete", "N/A"],
            "default": "Not Started",
        },
        "last_updated": {
            "type": "string",
            "required": True,
        },
    },
    "test-gaps": {
        "feature": {
            "type": "string",
            "required": True,
        },
        "strat_key": {
            "type": "string",
            "required": True,
            "pattern": r"^RHAISTRAT-\d+$",
        },
        "status": {
            "type": "string",
            "required": True,
            "enum": ["Open", "Partially Resolved", "Resolved"],
        },
        "gap_count": {
            "type": "int",
            "required": True,
        },
        "last_updated": {
            "type": "string",
            "required": True,
        },
    },
}


# ─── Auto-detection ─────────────────────────────────────────────────────────────

def detect_schema_type(path):
    """Detect schema type from file path."""
    basename = os.path.basename(path)
    if basename == "TestPlanGaps.md":
        return "test-gaps"
    if basename.startswith("TC-"):
        return "test-case"
    if basename == "TestPlan.md":
        return "test-plan"
    return None


# ─── Validation ─────────────────────────────────────────────────────────────────

class ValidationError(Exception):
    """Raised when frontmatter fails schema validation."""
    pass


def _validate_field(name, value, spec):
    """Validate a single field against its spec. Returns list of errors."""
    errors = []

    if value is None:
        if spec.get("required", False) and "default" not in spec:
            errors.append(f"Missing required field: {name}")
        return errors

    expected_type = spec.get("type", "string")

    if expected_type == "string":
        if not isinstance(value, str):
            errors.append(
                f"{name}: expected string, got {type(value).__name__}")
            return errors
        if "enum" in spec and value not in spec["enum"]:
            errors.append(
                f"{name}: '{value}' not in {spec['enum']}")
        if "pattern" in spec and not re.match(spec["pattern"], value):
            errors.append(
                f"{name}: '{value}' does not match {spec['pattern']}")

    elif expected_type == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(
                f"{name}: expected int, got {type(value).__name__}")

    elif expected_type == "bool":
        if not isinstance(value, bool):
            errors.append(
                f"{name}: expected bool, got {type(value).__name__}")

    elif expected_type == "list":
        if not isinstance(value, list):
            errors.append(
                f"{name}: expected list, got {type(value).__name__}")

    return errors


def validate(data, schema_type):
    """Validate frontmatter data against a schema.

    Args:
        data: dict of frontmatter fields
        schema_type: one of "test-plan", "test-case", "test-gaps"

    Returns:
        list of error strings (empty if valid)

    Raises:
        ValueError: if schema_type is unknown
    """
    if schema_type not in SCHEMAS:
        raise ValueError(
            f"Unknown schema type: {schema_type}. "
            f"Valid types: {list(SCHEMAS.keys())}")

    schema = SCHEMAS[schema_type]
    errors = []

    for key in data:
        if key not in schema:
            errors.append(f"Unknown field: {key}")

    for field_name, field_spec in schema.items():
        errors.extend(_validate_field(
            field_name, data.get(field_name), field_spec))

    return errors


def apply_defaults(data, schema_type):
    """Apply default values for missing optional fields.

    Modifies data in-place and returns it.
    """
    schema = SCHEMAS[schema_type]
    for field_name, field_spec in schema.items():
        if field_name not in data and "default" in field_spec:
            data[field_name] = field_spec["default"]
    return data


def get_schema_yaml(schema_type):
    """Return the schema definition as a YAML string for display."""
    if schema_type not in SCHEMAS:
        raise ValueError(
            f"Unknown schema type: {schema_type}. "
            f"Valid types: {list(SCHEMAS.keys())}")

    schema = SCHEMAS[schema_type]
    output = {"required": {}, "optional": {}}

    for name, spec in schema.items():
        entry = {"type": spec["type"]}
        if "enum" in spec:
            entry["enum"] = spec["enum"]
        if "pattern" in spec:
            entry["pattern"] = spec["pattern"]
        if "default" in spec:
            entry["default"] = spec["default"]

        if spec.get("required", False):
            output["required"][name] = entry
        else:
            output["optional"][name] = entry

    return yaml.dump(output, default_flow_style=False, sort_keys=False)


# ─── Frontmatter Read/Write ────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(
    r'^---\s*\n(.*?\n)---\s*\n', re.DOTALL)


def read_frontmatter(path):
    """Read and parse YAML frontmatter from a markdown file.

    Returns:
        (data_dict, body_string) — frontmatter as dict, remainder as string.
        Returns ({}, full_content) if no frontmatter found.
    """
    with open(path, encoding="utf-8") as f:
        content = f.read()

    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content

    yaml_str = match.group(1)
    body = content[match.end():]

    data = yaml.safe_load(yaml_str)
    if not isinstance(data, dict):
        return {}, content

    return data, body


def read_frontmatter_validated(path, schema_type):
    """Read frontmatter and validate against schema.

    Returns:
        (data_dict, body_string)

    Raises:
        ValidationError: if frontmatter fails validation
        FileNotFoundError: if file doesn't exist
    """
    data, body = read_frontmatter(path)
    if not data:
        raise ValidationError(f"No frontmatter found in {path}")

    apply_defaults(data, schema_type)
    errors = validate(data, schema_type)
    if errors:
        raise ValidationError(
            f"Frontmatter validation failed in {path}:\n"
            + "\n".join(f"  - {e}" for e in errors))

    return data, body


def write_frontmatter(path, data, schema_type):
    """Write/update YAML frontmatter on a markdown file.

    Validates data against the schema before writing. Preserves the
    markdown body below the frontmatter. Creates the file if it doesn't
    exist (with empty body).

    Args:
        path: file path
        data: dict of frontmatter fields
        schema_type: one of "test-plan", "test-case", "test-gaps"

    Raises:
        ValidationError: if data fails schema validation
    """
    apply_defaults(data, schema_type)
    errors = validate(data, schema_type)
    if errors:
        raise ValidationError(
            f"Frontmatter validation failed:\n"
            + "\n".join(f"  - {e}" for e in errors))

    body = ""
    if os.path.exists(path):
        _, body = read_frontmatter(path)

    yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False,
                         allow_unicode=True)
    content = f"---\n{yaml_str}---\n{body}"

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def update_frontmatter(path, updates, schema_type):
    """Merge updates into existing frontmatter and rewrite.

    Reads existing frontmatter, merges updates (overwriting on conflict),
    validates, and writes back.

    Args:
        path: file path (must exist)
        updates: dict of fields to add/update
        schema_type: schema to validate against

    Raises:
        ValidationError: if merged data fails validation
        FileNotFoundError: if file doesn't exist
    """
    data, body = read_frontmatter(path)
    for key, value in updates.items():
        data[key] = value

    apply_defaults(data, schema_type)
    errors = validate(data, schema_type)
    if errors:
        raise ValidationError(
            f"Frontmatter validation failed after update in {path}:\n"
            + "\n".join(f"  - {e}" for e in errors))

    yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False,
                         allow_unicode=True)
    content = f"---\n{yaml_str}---\n{body}"

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
