"""
GR/Circular Analyzer Tool
--------------------------
Extracts structured information from Government Resolution PDFs or raw text.

Design choice: Two-pass extraction.
  Pass 1 — Rule-based regex for deterministic fields (dates, ref numbers)
  Pass 2 — LLM-based extraction for semantic fields (obligations, applicability)

This hybrid approach gives deterministic precision on structured fields while
leveraging LLM reasoning for unstructured policy language. It also means
partial document inputs (missing pages) gracefully degrade: rule-based fields
fail explicitly while LLM fields still produce best-effort output.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pdfplumber
import structlog

from src.core.config import get_config
from src.core.schemas import (
    DocumentType,
    GRAnalysis,
    PolicyClause,
)
from src.models.ollama_client import OllamaClient
from src.tools.base import BaseTool

logger = structlog.get_logger(__name__)

# ── Regex patterns for deterministic extraction ──────────────────────────────
_REF_NUMBER_PATTERN = re.compile(
    r"(?:No\.|Number|Ref\.?|Reference)\s*[:\-]?\s*([\w\d/\-]+)",
    re.IGNORECASE,
)
_DATE_PATTERN = re.compile(
    r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{1,2}\s+\w+\s+\d{4})\b"
)
_AUTHORITY_PATTERN = re.compile(
    r"(?:Government of|Ministry of|Department of|Office of)\s+[\w\s]+",
    re.IGNORECASE,
)

# ── LLM extraction prompt ─────────────────────────────────────────────────────
# Shorter, faster extraction prompt
_EXTRACTION_PROMPT = """\
Extract structured info from this government document. Return ONLY JSON:
{{
  "document_type": "<government_resolution|circular|office_memorandum|notification|unknown>",
  "title": "<title or null>",
  "issuing_authority": "<authority or null>",
  "issue_date": "<date or null>",
  "reference_number": "<ref or null>",
  "key_obligations": ["<obligation>"],
  "deadlines": ["<deadline>"],
  "applicability": ["<who it applies to>"],
  "ambiguities": ["<unclear clause>"],
  "clauses": [
    {{
      "clause_text": "<clause>",
      "clause_type": "<obligation|deadline|authority|applicability|penalty>",
      "authority_referenced": null,
      "deadline": null,
      "applicability_scope": [],
      "confidence": 0.8
    }}
  ]
}}
DOCUMENT:
{document_text}
"""


class GRAnalyzerTool(BaseTool):
    """
    Two-pass GR/Circular analyzer combining rule-based + LLM extraction.
    Handles PDF and plain text inputs. Deduplicates via SHA-256 hash.
    """

    name = "gr_analyzer"
    description = (
        "Extracts clauses, obligations, deadlines, and authority references "
        "from Government Resolutions and circulars (PDF or text)."
    )

    def __init__(self) -> None:
        self._config = get_config()
        self._llm = OllamaClient(model=self._config.ollama.analyst_model)
        self._log = logger.bind(tool=self.name)

    async def _execute(
        self,
        *,
        text: str | None = None,
        pdf_path: str | Path | None = None,
    ) -> GRAnalysis:
        """
        Args:
            text: Raw document text (mutually exclusive with pdf_path)
            pdf_path: Path to a PDF file

        Returns:
            GRAnalysis: Fully structured document analysis
        """
        if text is None and pdf_path is None:
            raise ValueError("Provide either 'text' or 'pdf_path'.")

        # ── Extract text from PDF if needed ───────────────────────────────────
        raw_text = text or await self._extract_pdf_text(Path(pdf_path))  # type: ignore[arg-type]
        doc_hash = hashlib.sha256(raw_text.encode()).hexdigest()

        self._log.info("gr_analyzer.text_extracted", chars=len(raw_text), hash=doc_hash[:8])

        # ── Pass 1: Deterministic rule-based extraction ────────────────────────
        ref_number  = self._extract_ref_number(raw_text)
        dates       = self._extract_dates(raw_text)
        authorities = self._extract_authorities(raw_text)

        self._log.debug(
            "gr_analyzer.pass1_complete",
            ref=ref_number,
            dates=dates[:3],
            authorities=authorities[:2],
        )

        # ── Pass 2: LLM semantic extraction ───────────────────────────────────
        prompt = _EXTRACTION_PROMPT.format(document_text=raw_text[:8000])  # token guard
        llm_response = await self._llm.generate(prompt=prompt, temperature=0.0)
        parsed = self._parse_llm_json(llm_response)

        self._log.info(
            "gr_analyzer.pass2_complete",
            clauses=len(parsed.get("clauses", [])),
            obligations=len(parsed.get("key_obligations", [])),
        )

        # ── Merge: rule-based takes precedence over LLM for structured fields ─
        clauses = [
            PolicyClause(
                clause_text=c.get("clause_text", ""),
                clause_type=c.get("clause_type", "obligation"),
                authority_referenced=c.get("authority_referenced"),
                deadline=c.get("deadline"),
                applicability_scope=c.get("applicability_scope", []),
                confidence=float(c.get("confidence", 0.7)),
            )
            for c in parsed.get("clauses", [])
        ]

        return GRAnalysis(
            document_type=self._resolve_doc_type(parsed.get("document_type", "unknown")),
            title=parsed.get("title"),
            issuing_authority=parsed.get("issuing_authority") or (authorities[0] if authorities else None),
            issue_date=parsed.get("issue_date") or (dates[0] if dates else None),
            reference_number=parsed.get("reference_number") or ref_number,
            clauses=clauses,
            key_obligations=parsed.get("key_obligations", []),
            deadlines=parsed.get("deadlines", []),
            applicability=parsed.get("applicability", []),
            ambiguities_detected=parsed.get("ambiguities", []),
            raw_text_hash=doc_hash,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _extract_pdf_text(self, path: Path) -> str:
        """Extract text from PDF preserving reading order via pdfplumber."""
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")
        pages: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(x_tolerance=3, y_tolerance=3)
                if page_text:
                    pages.append(page_text)
        if not pages:
            raise ValueError(f"Could not extract text from PDF: {path}")
        return "\n\n".join(pages)

    def _extract_ref_number(self, text: str) -> str | None:
        match = _REF_NUMBER_PATTERN.search(text)
        return match.group(1).strip() if match else None

    def _extract_dates(self, text: str) -> list[str]:
        return list(dict.fromkeys(_DATE_PATTERN.findall(text)))  # deduplicated

    def _extract_authorities(self, text: str) -> list[str]:
        return list(dict.fromkeys(m.group(0) for m in _AUTHORITY_PATTERN.finditer(text)))

    def _resolve_doc_type(self, raw: str) -> DocumentType:
        mapping = {
            "government_resolution": DocumentType.GOVERNMENT_RESOLUTION,
            "circular": DocumentType.CIRCULAR,
            "office_memorandum": DocumentType.OFFICE_MEMORANDUM,
            "notification": DocumentType.NOTIFICATION,
        }
        return mapping.get(raw.lower(), DocumentType.UNKNOWN)

    def _parse_llm_json(self, response: str) -> dict[str, Any]:
        """
        Safely parse LLM JSON output. Strips markdown fences if present.
        Falls back to empty dict on parse failure — never raises.
        """
        import json
        # Strip common LLM artifacts
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            self._log.warning("gr_analyzer.json_parse_failed", error=str(e))
            return {}