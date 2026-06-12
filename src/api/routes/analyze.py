"""
Main analysis endpoint.
Accepts document text or signals PDF path, returns full PipelineOutput.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from src.orchestrator.praison import PraisonOrchestrator
from src.core.schemas import PipelineOutput

logger = structlog.get_logger(__name__)
router = APIRouter()

# Lazy-loaded orchestrator (expensive to init)
_orchestrator: PraisonOrchestrator | None = None

def get_orchestrator() -> PraisonOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = PraisonOrchestrator()
    return _orchestrator


class AnalyzeTextRequest(BaseModel):
    request: str
    document_text: str | None = None


@router.post("/analyze/text", response_model=PipelineOutput)
async def analyze_text(body: AnalyzeTextRequest):
    """Analyze a GR/Circular from text input."""
    try:
        orchestrator = get_orchestrator()
        result = await orchestrator.process(
            user_request=body.request,
            document_text=body.document_text,
        )
        return result
    except Exception as exc:
        logger.error("api.analyze_text.error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/analyze/pdf", response_model=PipelineOutput)
async def analyze_pdf(
    request: str = Form(...),
    file: UploadFile = File(...),
):
    """Analyze a GR/Circular from uploaded PDF."""
    import tempfile, os, shutil
    tmp_path = None
    try:
        suffix = os.path.splitext(file.filename or "doc.pdf")[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        orchestrator = get_orchestrator()
        result = await orchestrator.process(
            user_request=request,
            pdf_path=tmp_path,
        )
        return result
    except Exception as exc:
        logger.error("api.analyze_pdf.error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)