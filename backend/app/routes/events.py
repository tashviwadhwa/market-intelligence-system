from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.models.event import MarketEvent
from app.services.database_service import db_service
from app.database import get_db
from typing import Optional

router = APIRouter()

@router.post("/log")
def log_event(event: MarketEvent, db: Session = Depends(get_db)):
    try:
        db_event = db_service.save_event(db, event)
        return {
            "status": "success",
            "message": "Event logged successfully",
            "event_id": db_event.id,
            "risk_level": db_event.risk_level,
            "llm_risk_level": db_event.llm_risk_level,
            "needs_review": db_event.needs_review,
            "received_at": str(db_event.received_at)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save event: {str(e)}"
        )

@router.get("/all")
def get_all_events(
    risk_level: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    try:
        events = db_service.get_all_events(db, limit=limit, risk_level=risk_level)
        return {
            "total": len(events),
            "events": [
                {
                    "id": e.id,
                    "date": e.date,
                    "competitors": e.competitors,
                    "summary": e.summary,
                    "risk_level": e.risk_level,
                    "confidence": e.confidence,
                    "source_count": e.source_count,
                    "top_reasons": e.top_reasons,
                    "impact_areas": e.impact_areas,
                    "recommended_actions": e.recommended_actions,
                    "llm_risk_level": e.llm_risk_level,
                    "final_score": e.final_score,
                    "rule_points": e.rule_points,
                    "rules_fired": e.rules_fired,
                    "needs_review": e.needs_review,
                    "created_at": str(e.created_at)
                }
                for e in events
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve events: {str(e)}"
        )

@router.get("/latest")
def get_latest_event(db: Session = Depends(get_db)):
    try:
        event = db_service.get_latest_event(db)
        if not event:
            raise HTTPException(
                status_code=404,
                detail="No events found"
            )
        return {
            "id": event.id,
            "date": event.date,
            "competitors": event.competitors,
            "summary": event.summary,
            "risk_level": event.risk_level,
            "confidence": event.confidence,
            "top_reasons": event.top_reasons,
            "recommended_actions": event.recommended_actions,
            "impact_areas": event.impact_areas,
            "source_count": event.source_count,
            "llm_risk_level": event.llm_risk_level,
            "final_score": event.final_score,
            "rule_points": event.rule_points,
            "rules_fired": event.rules_fired,
            "needs_review": event.needs_review,
            "created_at": str(event.created_at)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve latest event: {str(e)}"
        )

@router.get("/summary")
def get_risk_summary(db: Session = Depends(get_db)):
    try:
        summary = db_service.get_risk_summary(db)
        return {
            "risk_distribution": summary,
            "total": sum(summary.values())
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve summary: {str(e)}"
        )