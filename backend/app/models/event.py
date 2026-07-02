from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class MarketEvent(BaseModel):
    date: str
    competitors: str
    summary: str
    risk_level: str
    confidence: str
    top_reasons: str
    recommended_actions: str
    impact_areas: str
    source: Optional[str] = "n8n-pipeline"