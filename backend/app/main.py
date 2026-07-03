from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.routes.events import router as events_router
from app.routes.deduplication import router as deduplication_router
import os
load_dotenv()
app = FastAPI(
    title="Market Intelligence API",
    description="Backend service for Zepto market intelligence and risk monitoring pipeline",
    version="1.0.0"
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
