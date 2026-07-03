from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class ConfidenceLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class MarketEvent(BaseModel):
    date: str
    competitors: str
    summary: str
    risk_level: RiskLevel
    confidence: ConfidenceLevel
    top_reasons: str
    recommended_actions: str
    impact_areas: str
    source: Optional[str] = "n8n-pipeline"

    class Config:
        use_enum_values = True