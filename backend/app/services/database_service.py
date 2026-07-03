from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.db_models import MarketEventDB, EventEmbeddingDB
from app.models.event import MarketEvent
from datetime import datetime
from typing import List, Optional
import numpy as np

class DatabaseService:
    
    def save_event(self, db: Session, event: MarketEvent) -> MarketEventDB:
        """Save a new market event to the database."""
        db_event = MarketEventDB(
            date=event.date,
            competitors=event.competitors,
            summary=event.summary,
            risk_level=event.risk_level.value,
            confidence=event.confidence.value,
            top_reasons=event.top_reasons,
            recommended_actions=event.recommended_actions,
            impact_areas=event.impact_areas,
            source=event.source or "n8n-pipeline",
            source_count=1,
            received_at=datetime.now()
        )
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        return db_event

    def get_all_events(
        self, 
        db: Session, 
        limit: int = 100,
        risk_level: Optional[str] = None
    ) -> List[MarketEventDB]:
        """Get all events, optionally filtered by risk level."""
        query = db.query(MarketEventDB).order_by(desc(MarketEventDB.created_at))
        if risk_level:
            query = query.filter(MarketEventDB.risk_level == risk_level)
        return query.limit(limit).all()

    def get_latest_event(self, db: Session) -> Optional[MarketEventDB]:
        """Get the most recently created event."""
        return db.query(MarketEventDB)\
                 .order_by(desc(MarketEventDB.created_at))\
                 .first()

    def save_embedding(
        self, 
        db: Session,
        event_text: str,
        enriched_text: str,
        embedding: np.ndarray,
        event_data: dict
    ) -> EventEmbeddingDB:
        """Save an embedding vector to the database for persistence."""
        db_embedding = EventEmbeddingDB(
            event_text=event_text,
            enriched_text=enriched_text,
            embedding=embedding.tolist(),
            source_count=1,
            confidence="LOW",
            event_data=event_data
        )
        db.add(db_embedding)
        db.commit()
        db.refresh(db_embedding)
        return db_embedding

    def get_all_embeddings(self, db: Session) -> List[EventEmbeddingDB]:
        """Load all stored embeddings — used on startup to restore memory."""
        return db.query(EventEmbeddingDB).all()

    def increment_embedding_source_count(
        self, 
        db: Session, 
        embedding_id: int
    ) -> EventEmbeddingDB:
        """When a duplicate is found, increase its source count."""
        embedding = db.query(EventEmbeddingDB)\
                      .filter(EventEmbeddingDB.id == embedding_id)\
                      .first()
        if embedding:
            embedding.source_count += 1
            embedding.confidence = "HIGH"
            db.commit()
            db.refresh(embedding)
        return embedding

    def get_risk_summary(self, db: Session) -> dict:
        """Get count of events by risk level — useful for dashboard."""
        from sqlalchemy import func
        results = db.query(
            MarketEventDB.risk_level,
            func.count(MarketEventDB.id).label('count')
        ).group_by(MarketEventDB.risk_level).all()
        
        return {row.risk_level: row.count for row in results}

# Single instance used across the application
db_service = DatabaseService()