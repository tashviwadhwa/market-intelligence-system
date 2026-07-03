from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Any

# Load the embedding model once when the service starts
# Loading it inside a function would reload it on every call — very slow
model = SentenceTransformer('all-MiniLM-L6-v2')

# In-memory store for embeddings of seen events
# Each entry: {"text": "...", "embedding": [...], "event": {...}}
seen_events: List[Dict[str, Any]] = []
def get_embedding(text: str) -> np.ndarray:
    """Convert text to a numerical embedding vector."""
    return model.encode(text, convert_to_numpy=True)

def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Calculate similarity between two embedding vectors.
    Returns a value between 0 (completely different) and 1 (identical meaning).
    """
    dot_product = np.dot(vec1, vec2)
    magnitude1 = np.linalg.norm(vec1)
    magnitude2 = np.linalg.norm(vec2)
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)

def is_duplicate(new_text: str, threshold: float = 0.85) -> tuple[bool, int]:
    """
    Check if new_text is a duplicate of any previously seen event.
    
    Returns:
        (True, index) if duplicate found at that index
        (False, -1) if not a duplicate
    """
    if not seen_events:
        return False, -1
    
    new_embedding = get_embedding(new_text)
    
    for i, seen in enumerate(seen_events):
        similarity = cosine_similarity(new_embedding, seen["embedding"])
        if similarity >= threshold:
            return True, i
    
    return False, -1

def process_event(event_text: str, event_data: dict) -> dict:
    # Combine multiple fields for richer semantic comparison
    # More context = better duplicate detection
    enriched_text = f"{event_text}. {event_data.get('summary', '')}. Competitors involved: {event_data.get('competitors', '')}"
    is_dup, dup_index = is_duplicate(enriched_text)
    
    if is_dup:
        # It's a duplicate — increase confidence, don't create new event
        seen_events[dup_index]["source_count"] += 1
        seen_events[dup_index]["confidence"] = "HIGH"
        
        return {
            "status": "duplicate",
            "message": "Event already seen, source count increased",
            "source_count": seen_events[dup_index]["source_count"],
            "original_event": seen_events[dup_index]["event"]
        }
    
    # Not a duplicate — store it as a new event
    new_embedding = get_embedding(enriched_text)
    seen_events.append({
        "text": event_text,
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
