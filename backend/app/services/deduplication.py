from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

# Load the embedding model once when the service starts
model = SentenceTransformer('all-MiniLM-L6-v2')

# In-memory cache of embeddings for fast comparison
# Gets populated from database on startup
seen_events: List[Dict[str, Any]] = []

def get_embedding(text: str) -> np.ndarray:
    """Convert text to a numerical embedding vector."""
    return model.encode(text, convert_to_numpy=True)

def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Calculate similarity between two embedding vectors."""
    dot_product = np.dot(vec1, vec2)
    magnitude1 = np.linalg.norm(vec1)
    magnitude2 = np.linalg.norm(vec2)
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)

def load_embeddings_from_db(db: Session) -> None:
    """
    Load all stored embeddings from database into memory on startup.
    This fixes the 'embeddings disappear on restart' problem.
    """
    from app.models.db_models import EventEmbeddingDB
    
    global seen_events
    seen_events = []
    
    db_embeddings = db.query(EventEmbeddingDB).all()
    
    for emb in db_embeddings:
        seen_events.append({
            "db_id": emb.id,
            "text": emb.event_text,
            "enriched_text": emb.enriched_text,
            "embedding": np.array(emb.embedding),
            "event": emb.event_data,
            "source_count": emb.source_count,
            "confidence": emb.confidence
        })
    
    print(f"Loaded {len(seen_events)} embeddings from database into memory")

def is_duplicate(new_text: str, threshold: float = 0.85) -> tuple[bool, int]:
    """Check if new_text is a duplicate of any previously seen event."""
    if not seen_events:
        return False, -1
    
    new_embedding = get_embedding(new_text)
    
    for i, seen in enumerate(seen_events):
        similarity = cosine_similarity(new_embedding, seen["embedding"])
        if similarity >= threshold:
            return True, i
    
    return False, -1

def process_event(
    event_text: str, 
    event_data: dict,
    db: Optional[Session] = None
) -> dict:
    """
    Main deduplication function.
    Now accepts optional db session for persistence.
    """
    enriched_text = f"{event_text}. {event_data.get('summary', '')}. Competitors involved: {event_data.get('competitors', '')}"
    
    is_dup, dup_index = is_duplicate(enriched_text)
    
    if is_dup:
        seen_events[dup_index]["source_count"] += 1
        seen_events[dup_index]["confidence"] = "HIGH"
        
        if db:
            from app.models.db_models import EventEmbeddingDB
            db_id = seen_events[dup_index].get("db_id")
            if db_id:
                db_embedding = db.query(EventEmbeddingDB)\
                                 .filter(EventEmbeddingDB.id == db_id)\
                                 .first()
                if db_embedding:
                    db_embedding.source_count += 1
                    db_embedding.confidence = "HIGH"
                    db.commit()
        
        return {
            "status": "duplicate",
            "message": "Event already seen, source count increased",
            "source_count": seen_events[dup_index]["source_count"],
            "original_event": seen_events[dup_index]["event"]
        }
    
    new_embedding = get_embedding(enriched_text)
    
    db_id = None
    if db:
        from app.models.db_models import EventEmbeddingDB
        db_embedding = EventEmbeddingDB(
            event_text=event_text,
            enriched_text=enriched_text,
            embedding=new_embedding.tolist(),
            source_count=1,
            confidence="LOW",
            event_data=event_data
        )
        db.add(db_embedding)
        db.commit()
        db.refresh(db_embedding)
        db_id = db_embedding.id
    
    seen_events.append({
        "db_id": db_id,
        "text": event_text,
        "enriched_text": enriched_text,
        "embedding": new_embedding,
        "event": event_data,
        "source_count": 1,
        "confidence": "LOW"
    })
    
    return {
        "status": "new_event",
        "message": "New unique event stored",
        "source_count": 1,
        "total_unique_events": len(seen_events)
    }