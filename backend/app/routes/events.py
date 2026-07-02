from fastapi import APIRouter, HTTPException
from app.models.event import MarketEvent
from datetime import datetime

router = APIRouter()
# Temporary in-memory storage until database is set up in Phase 3
events_store = []

@router.post("/log")
def log_event(event: MarketEvent):
    # Add timestamp when we receive the event
    event_dict = event.model_dump()
    event_dict["received_at"] = datetime.now().isoformat()
    
    # Store in memory temporarily
    events_store.append(event_dict)
    
    return {
        "status": "success",
        "message": "Event logged successfully",
        "event_id": len(events_store),
        "received_at": event_dict["received_at"]
    }

@router.get("/all")
def get_all_events():
    return {
        "total": len(events_store),
        "events": events_store
    }

@router.get("/latest")
def get_latest_event():
    if not events_store:
        raise HTTPException(
            status_code=404,
            detail="No events logged yet"
        )
    return events_store[-1]
