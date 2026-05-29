from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from agentassert_typec_core.dsl.process_models import ParseResult, ValidationError
from agentassert_typec_core.dsl.validator import validate_extended
from agentassert_typec_core.models.contract import ContractSpecExtended

_yaml = YAML()
_yaml.preserve_quotes = True


def parse_contract(path: str | Path) -> ParseResult:
    try:
        content = Path(path).read_text(encoding="utf-8")
        data = _yaml.load(content)
    except FileNotFoundError:
        return ParseResult(errors=[ValidationError(
            level="error", path="", message=f"File not found: {path}", code="FILE_NOT_FOUND"
        )])
    except Exception as e:
        return ParseResult(errors=[ValidationError(
            level="error", path="", message=f"YAML parse error: {e}", code="YAML_PARSE_ERROR"
        )])

    if not isinstance(data, dict):
        return ParseResult(errors=[ValidationError(
            level="error", path="", message="Contract YAML must be a mapping", code="NOT_A_MAPPING"
        )])

    dsl_version = data.get("dsl_version", None)
    warnings: list[ValidationError] = []

    if dsl_version is None:
        warnings.append(ValidationError(
            level="warning",
            path="dsl_version",
            message="Missing dsl_version field. Defaulting to '0.3'. Add `dsl_version: '0.4'` to use Type-C operators.",
            code="MISSING_DSL_VERSION",
        ))
        data["dsl_version"] = "0.3"

    errors = validate_extended(data)
    all_issues = warnings + errors

    if any(e.level == "error" for e in all_issues):
        return ParseResult(errors=all_issues)

    try:
        contract = ContractSpecExtended.model_validate(data)
        return ParseResult(contract=contract, errors=all_issues)
    except Exception as e:
        return ParseResult(errors=[ValidationError(
            level="error", path="", message=f"Model validation error: {e}", code="MODEL_VALIDATION_ERROR"
        )])
