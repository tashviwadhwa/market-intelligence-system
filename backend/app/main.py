from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.routes.events import router as events_router
from app.routes.deduplication import router as deduplication_router
from contextlib import asynccontextmanager
from app.database import get_db
import os
load_dotenv()
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load embeddings from database into memory
    print("Loading embeddings from database...")
    try:
        db = next(get_db())
        from app.services.deduplication import load_embeddings_from_db
        load_embeddings_from_db(db)
        db.close()
    except Exception as e:
        print(f"Could not load embeddings on startup: {e}")
    
    yield  # Server runs here
    
    # Shutdown: cleanup if needed
    print("Shutting down...")

app = FastAPI(
    title="Market Intelligence API",
    description="Backend service for Zepto market intelligence and risk monitoring pipeline",
    version="1.0.0",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5678", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
@app.get("/health")
def health_check():
    return {
        "status": "running",
        "service": "Market Intelligence API",
        "version": "1.0.0"
    }
@app.get("/")
def root():
    return {
        "message": "Zepto Market Intelligence API is running",
        "docs": "http://localhost:8000/docs"
    }
app.include_router(events_router, prefix="/api/events", tags=["Events"])
app.include_router(
    deduplication_router, 
    prefix="/api/deduplication", 
    tags=["Deduplication"]
)
