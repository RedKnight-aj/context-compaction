"""
Context Compaction REST API
FastAPI server for context compaction services
"""

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import time
import uuid
from datetime import datetime
from functools import wraps

from src import CompactionEngine, CompactionConfig, CompactionResult
from src.storage import CompactionStorage, CompactionRecord, MockStorage


# =============== Configuration ===============
app = FastAPI(
    title="Context Compaction API",
    description="Token optimization and context management service",
    version="1.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============== Rate Limiting ===============
class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = {}
    
    def check(self, client_id: str) -> bool:
        """Check if client is rate limited"""
        now = time.time()
        minute_ago = now - 60
        
        # Clean old entries
        self.requests[client_id] = [
            t for t in self.requests.get(client_id, [])
            if t > minute_ago
        ]
        
        if len(self.requests[client_id]) >= self.requests_per_minute:
            return False
        
        self.requests[client_id].append(now)
        return True


rate_limiter = RateLimiter(requests_per_minute=60)


def rate_limit(request: Request):
    """Rate limit dependency"""
    client_id = request.client.host if request.client else "unknown"
    if not rate_limiter.check(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


# =============== Models ===============
class MessageInput(BaseModel):
    """Message format for API"""
    role: str = Field(..., description="Message role (system, user, assistant, tool)")
    content: str = Field(..., description="Message content")
    tool_calls: Optional[List[Dict]] = Field(None, description="Tool calls if any")


class CompactRequest(BaseModel):
    """Request to compact messages"""
    messages: List[Dict] = Field(..., description="Messages to compact")
    session_id: Optional[str] = Field(None, description="Session identifier")
    config: Optional[Dict] = Field(None, description="Optional config override")


class EstimateRequest(BaseModel):
    """Request to estimate tokens"""
    messages: List[Dict] = Field(..., description="Messages to analyze")


class ConfigUpdate(BaseModel):
    """Config update request"""
    key: str = Field(..., description="Config key to update")
    value: str = Field(..., description="New value")


# =============== Global State ===============
# Default engine with storage
engine = CompactionEngine()
storage = MockStorage()  # Use MockStorage by default


# =============== API Routes ===============

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Context Compaction API",
        "version": "1.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ----- Compact -----
@app.post("/compact")
async def compact_messages(
    request: CompactRequest,
    rate_limit: bool = Depends(rate_limit)
) -> JSONResponse:
    """
    Compact messages to optimize token usage.
    
    Returns compacted messages and savings report.
    """
    try:
        # Apply custom config if provided
        engine_local = engine
        if request.config:
            config = CompactionConfig(**request.config)
            engine_local = CompactionEngine(config)
        
        # Run compaction
        compacted, result = engine_local.compact(
            messages=request.messages,
            session_id=request.session_id
        )
        
        # Save to storage
        try:
            record = CompactionRecord(
                session_id=result.session_id,
                original_tokens=result.original_tokens,
                compacted_tokens=result.compacted_tokens,
                tokens_saved=result.tokens_saved,
                savings_percentage=result.savings_percentage,
                messages_compacted=result.messages_compacted,
                messages_kept=result.messages_kept,
                timestamp=result.timestamp,
                strategy=result.strategy
            )
            storage.save(record)
        except Exception:
            pass  # Storage is optional
        
        return JSONResponse({
            "success": True,
            "session_id": result.session_id,
            "compacted_messages": compacted,
            "result": {
                "original_tokens": result.original_tokens,
                "compacted_tokens": result.compacted_tokens,
                "tokens_saved": result.tokens_saved,
                "savings_percentage": result.savings_percentage,
                "messages_compacted": result.messages_compacted,
                "messages_kept": result.messages_kept,
                "summary": result.summary,
                "timestamp": result.timestamp
            }
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----- Estimate -----
@app.post("/estimate")
async def estimate_tokens(
    request: EstimateRequest,
    rate_limit: bool = Depends(rate_limit)
) -> JSONResponse:
    """
    Estimate token usage without making changes.
    
    Returns token count and usage analysis.
    """
    try:
        analysis = engine.analyze(request.messages)
        
        return JSONResponse({
            "success": True,
            "tokens": {
                "total": analysis["tokens"].total,
                "system": analysis["tokens"].system,
                "user": analysis["tokens"].user,
                "assistant": analysis["tokens"].assistant,
                "tools": analysis["tokens"].tools,
            },
            "limit": analysis["limit"],
            "usage": analysis["usage"],
            "ranking": analysis["ranking"],
            "needs_compaction": analysis["needs_compaction"]
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----- Stats -----
@app.get("/stats")
async def get_stats(
    rate_limit: bool = Depends(rate_limit)
) -> JSONResponse:
    """
    Get compaction statistics.
    
    Returns aggregate stats from storage.
    """
    try:
        stats = storage.get_stats()
        
        return JSONResponse({
            "success": True,
            "stats": stats
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----- Config -----
@app.get("/config")
async def get_config() -> JSONResponse:
    """Get current configuration"""
    return JSONResponse({
        "success": True,
        "config": {
            "model": engine.config.model,
            "max_context_percentage": engine.config.max_context_percentage,
            "keep_recent": engine.config.keep_recent,
            "keep_user": engine.config.keep_user,
            "keep_tools_recent": engine.config.keep_tools_recent,
            "strategy": engine.config.strategy,
            "enable_summarization": engine.config.enable_summarization,
            "min_savings_percentage": engine.config.min_savings_percentage,
            "summarizer_model": engine.config.summarizer_model,
            "summarizer_provider": engine.config.summarizer_provider,
        }
    })


@app.post("/config")
async def update_config(
    update: ConfigUpdate,
    rate_limit: bool = Depends(rate_limit)
) -> JSONResponse:
    """Update configuration"""
    try:
        key = update.key
        value = update.value
        
        if hasattr(engine.config, key):
            # Type conversion
            if key in ["max_context_percentage", "min_savings_percentage"]:
                setattr(engine.config, key, float(value))
            elif key in ["keep_recent", "keep_tools_recent"]:
                setattr(engine.config, key, int(value))
            elif key in ["keep_user", "enable_summarization"]:
                setattr(engine.config, key, value.lower() in ["true", "1"])
            else:
                setattr(engine.config, key, value)
            
            return JSONResponse({
                "success": True,
                "message": f"Updated {key} = {value}"
            })
        else:
            raise HTTPException(status_code=400, detail=f"Unknown config: {key}")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----- History -----
@app.get("/history")
async def get_history(
    session_id: Optional[str] = None,
    limit: int = 100,
    rate_limit: bool = Depends(rate_limit)
) -> JSONResponse:
    """Get compaction history"""
    try:
        if session_id:
            history = storage.get_session_history(session_id)
        else:
            history = storage.get_all_history(limit)
        
        return JSONResponse({
            "success": True,
            "history": history
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============== Error Handlers ===============

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": str(exc),
            "type": type(exc).__name__
        }
    )


# =============== Run ===============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
