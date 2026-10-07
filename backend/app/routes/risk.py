from fastapi import APIRouter
from pydantic import BaseModel
from app.services.risk_scoring import hybrid_score

router = APIRouter()


class RiskInput(BaseModel):
    text: str                      # summary + reasons from the LLM
    llm_risk_level: str            # LOW / MEDIUM / HIGH from the Risk Analysis LLM
    llm_confidence: str = "MEDIUM" # LOW / MEDIUM / HIGH
    source_count: int = 1          # how many sources reported it


@router.post("/score")
def score_risk(data: RiskInput):
    return hybrid_score(
        text=data.text,
        llm_risk_level=data.llm_risk_level,
        llm_confidence=data.llm_confidence,
        source_count=data.source_count,
    )
