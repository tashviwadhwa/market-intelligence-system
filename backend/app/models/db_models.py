from sqlalchemy import Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import ARRAY, FLOAT, JSONB
from sqlalchemy.sql import func
from app.database import Base

class MarketEventDB(Base):
    __tablename__ = "market_events"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(50), nullable=False)
    competitors = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    risk_level = Column(String(10), nullable=False)
    confidence = Column(String(10), nullable=False)
    top_reasons = Column(Text, nullable=False)
    recommended_actions = Column(Text, nullable=False)
    impact_areas = Column(Text, nullable=False)
    source = Column(String(50), default="n8n-pipeline")
    source_count = Column(Integer, default=1)
    received_at = Column(TIMESTAMP, server_default=func.now())
    created_at = Column(TIMESTAMP, server_default=func.now())

class EventEmbeddingDB(Base):
    __tablename__ = "event_embeddings"
    
    id = Column(Integer, primary_key=True, index=True)
    event_text = Column(Text, nullable=False)
    enriched_text = Column(Text, nullable=False)
    embedding = Column(ARRAY(FLOAT), nullable=False)
    source_count = Column(Integer, default=1)
    confidence = Column(String(10), default="LOW")
    event_data = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())