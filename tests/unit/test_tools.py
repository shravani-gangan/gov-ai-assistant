"""
Unit tests for domain-specific tools.
Uses mock LLM responses to isolate tool logic from model inference.
"""
import pytest
from unittest.mock import AsyncMock, patch
from src.tools.gr_analyzer import GRAnalyzerTool
from src.core.schemas import DocumentType


MOCK_GR_TEXT = """
Government of Maharashtra
No. GR/2024/CR-123/DPC
Date: 15 January 2024

GOVERNMENT RESOLUTION
Subject: Implementation of Digital Public Infrastructure in all District Offices

The Government of Maharashtra hereby directs all District Collectors to 
implement the Digital Public Infrastructure platform by 31 March 2024.
All officers must ensure compliance within the stipulated deadline.
Failure to comply will attract penal provisions under Section 4 of the 
Maharashtra Government Administration Act.
"""

MOCK_LLM_RESPONSE = """{
  "document_type": "government_resolution",
  "title": "Implementation of Digital Public Infrastructure",
  "issuing_authority": "Government of Maharashtra",
  "issue_date": "15 January 2024",
  "reference_number": "GR/2024/CR-123/DPC",
  "key_obligations": ["All District Collectors must implement DPI by 31 March 2024"],
  "deadlines": ["31 March 2024"],
  "applicability": ["All District Collectors", "District Offices"],
  "ambiguities": [],
  "clauses": [
    {
      "clause_text": "All District Collectors to implement DPI by 31 March 2024",
      "clause_type": "obligation",
      "authority_referenced": "Government of Maharashtra",
      "deadline": "31 March 2024",
      "applicability_scope": ["District Collectors"],
      "confidence": 0.95
    }
  ]
}"""


@pytest.mark.asyncio
async def test_gr_analyzer_text_input():
    tool = GRAnalyzerTool()
    with patch.object(tool._llm, "generate", new=AsyncMock(return_value=MOCK_LLM_RESPONSE)):
        result = await tool._execute(text=MOCK_GR_TEXT)

    assert result.document_type == DocumentType.GOVERNMENT_RESOLUTION
    assert result.reference_number == "GR/2024/CR-123/DPC"
    assert len(result.clauses) == 1
    assert result.clauses[0].confidence == 0.95
    assert "31 March 2024" in result.deadlines
    assert result.raw_text_hash  # SHA-256 populated


@pytest.mark.asyncio
async def test_gr_analyzer_fallback_on_bad_json():
    """Tool must not raise on LLM JSON parse failure — graceful degradation."""
    tool = GRAnalyzerTool()
    with patch.object(tool._llm, "generate", new=AsyncMock(return_value="NOT VALID JSON")):
        result = await tool._execute(text=MOCK_GR_TEXT)

    # Should still return a valid GRAnalysis, just with empty fields
    assert result is not None
    assert result.clauses == []
    assert result.raw_text_hash  # Hash always computed


@pytest.mark.asyncio
async def test_gr_analyzer_missing_input():
    tool = GRAnalyzerTool()
    with pytest.raises(ValueError, match="Provide either"):
        await tool._execute()