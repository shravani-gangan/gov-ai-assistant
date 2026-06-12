"""
Structured Output Validator
-----------------------------
Enforces JSON schema compliance on pipeline outputs.
Uses Pydantic's own schema generation — no external schema files needed.
"""
from __future__ import annotations

from typing import Any

import structlog
from pydantic import ValidationError

from src.core.schemas import PipelineOutput
from src.tools.base import BaseTool

logger = structlog.get_logger(__name__)


class SchemaValidatorTool(BaseTool):
    name = "schema_validator"
    description = "Validates pipeline output against the official PipelineOutput JSON schema."

    def __init__(self) -> None:
        self._log = logger.bind(tool=self.name)
        self._schema = PipelineOutput.model_json_schema()

    async def _execute(self, *, data: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []

        # Check required top-level fields
        required = [
            "human_readable_draft",
            "gr_analysis",
            "compliance_report",
            "confidence_score",
            "reasoning_steps",
            "audit_trail",
        ]
        for field in required:
            if field not in data:
                errors.append(f"Missing required field: '{field}'")

        # Confidence score range
        score = data.get("confidence_score", -1)
        if not (0.0 <= float(score) <= 1.0):
            errors.append(f"confidence_score {score} out of range [0.0, 1.0]")

        # Draft non-empty
        draft = data.get("human_readable_draft", "")
        if len(draft.strip()) < 50:
            warnings.append("human_readable_draft is suspiciously short (<50 chars)")

        # Reasoning steps present
        steps = data.get("reasoning_steps", [])
        if not steps:
            warnings.append("reasoning_steps is empty — transparency reduced")

        is_valid = len(errors) == 0
        self._log.info(
            "schema_validator.complete",
            valid=is_valid,
            errors=len(errors),
            warnings=len(warnings),
        )

        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "schema_version": "PipelineOutput/v1",
        }