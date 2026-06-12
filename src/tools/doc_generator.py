"""
Official Document Generator
-----------------------------
Generates government-format documents using Jinja2 templates.
Enforces structure: letterhead → reference → subject → body → signature.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from src.tools.base import BaseTool

logger = structlog.get_logger(__name__)

# Inline template (no external files needed for submission)
_OFFICIAL_TEMPLATE = """\
GOVERNMENT OF MAHARASHTRA
{department}

No. {reference_number}                    Date: {date}

OFFICE MEMORANDUM / GOVERNMENT RESOLUTION

Subject: {subject}

Reference: {reference_note}

{body}

ACTION REQUIRED:
{action_required}

This issues with the approval of the competent authority.

                                        {signatory_name}
                                        {signatory_designation}
                                        {department}

Copy to:
{copy_to}
"""


class DocGeneratorTool(BaseTool):
    name = "doc_generator"
    description = "Generates official government-format documents from structured data."

    def __init__(self) -> None:
        self._log = logger.bind(tool=self.name)

    async def _execute(
        self,
        *,
        subject: str,
        body: str,
        department: str = "Department of Information Technology",
        reference_number: str = "AUTO/GEN/001",
        reference_note: str = "",
        action_required: str = "",
        signatory_name: str = "[Officer Name]",
        signatory_designation: str = "[Designation]",
        copy_to: list[str] | None = None,
        date: str | None = None,
    ) -> dict[str, Any]:

        formatted = _OFFICIAL_TEMPLATE.format(
            department=department,
            reference_number=reference_number,
            date=date or datetime.now().strftime("%d %B %Y"),
            subject=subject,
            reference_note=reference_note or "As above",
            body=body,
            action_required=action_required or "All concerned officers are requested to take note and act accordingly.",
            signatory_name=signatory_name,
            signatory_designation=signatory_designation,
            copy_to="\n".join(f"  {i+1}. {r}" for i, r in enumerate(copy_to or ["All District Collectors"])),
        )

        self._log.info("doc_generator.complete", chars=len(formatted))
        return {"document": formatted, "format": "official_memo", "chars": len(formatted)}