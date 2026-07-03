from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.services.deduplication import process_event
from app.database import get_db

router = APIRouter()

class DeduplicationRequest(BaseModel):
    text: str
    event_data: dict

@router.post("/check")
def check_duplicate(
    request: DeduplicationRequest,
    db: Session = Depends(get_db)
):
    if not request.text.strip():
        raise HTTPException(
            status_code=400,
            detail="Text cannot be empty"
        )
    
    result = process_event(request.text, request.event_data, db=db)
    return result

@router.get("/stats")
def get_stats():
    from app.services.deduplication import seen_events
    return {
        "total_unique_events": len(seen_events),
        "events": [
            {
                "text": e["text"],
                "source_count": e["source_count"],
                "confidence": e["confidence"],
                "db_id": e.get("db_id")
            }
            for e in seen_events
        ]
    }

@router.post("/similarity")
def check_similarity(request: DeduplicationRequest):
    from app.services.deduplication import get_embedding, cosine_similarity
    
    text1 = request.text
    text2 = request.event_data.get("second_text", "")
    
    if not text2:
        raise HTTPException(
            status_code=400,
            detail="Please provide second_text in event_data"
        )
    
    embedding1 = get_embedding(text1)
    embedding2 = get_embedding(text2)
    similarity = cosine_similarity(embedding1, embedding2)
    
    return {
        "text1": text1,
        "text2": text2,
        "similarity_score": float(similarity),
        "threshold": 0.85,
        "would_be_duplicate": bool(similarity >= 0.85)
    }