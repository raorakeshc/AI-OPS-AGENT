"""FastAPI application for AI-OPS Agent."""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.agent import SupportAgent
from src.config import get_config
from src.schemas import (
    QueryRequest,
    QueryResponse,
    QueryType,
    FeedbackRequest,
    FeedbackResponse,
    HealthCheckResponse,
    ErrorResponse,
    OrderIDRecallRequest,
    OrderIDRecallResponse,
    ClearMemoryRequest,
    ClearMemoryResponse,
)

# Configure logging
logger = logging.getLogger(__name__)

# Global agent instance
agent_instance: Optional[SupportAgent] = None
config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management (startup/shutdown)."""
    global agent_instance
    logger.info("Starting up AI-OPS Agent API")
    try:
        agent_instance = SupportAgent()
        logger.info("Agent initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise
    yield
    logger.info("Shutting down AI-OPS Agent API")


# Create FastAPI app
app = FastAPI(
    title=config.app.name,
    version=config.app.version,
    description="Production-grade AI-powered support agent API",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.app.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_agent() -> SupportAgent:
    """Dependency to get agent instance."""
    if agent_instance is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent not initialized",
        )
    return agent_instance


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Global exception handler."""
    trace_id = str(uuid.uuid4())
    logger.error(f"[{trace_id}] Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="InternalServerError",
            message="An unexpected error occurred",
            trace_id=trace_id,
        ).dict(),
    )


@app.get("/health", response_model=HealthCheckResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns:
        HealthCheckResponse: Health status of the application.
    """
    try:
        agent = get_agent()
        components_status = {
            "agent": "healthy" if agent else "unhealthy",
            "config": "healthy",
        }
        return HealthCheckResponse(
            status="healthy",
            version=config.app.version,
            components=components_status,
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheckResponse(
            status="unhealthy",
            version=config.app.version,
            components={"agent": "unhealthy", "config": "unhealthy"},
        )


@app.post("/query", response_model=QueryResponse, tags=["Agent"])
async def process_query(
    request: QueryRequest,
    agent: SupportAgent = Depends(get_agent),
):
    """
    Process a user query with the support agent.

    Args:
        request: QueryRequest containing user query.
        agent: SupportAgent instance (injected).

    Returns:
        QueryResponse: Agent's response with metadata.

    Raises:
        HTTPException: If query processing fails.
    """
    try:
        # Input validation
        if not request.query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query cannot be empty",
            )

        # Process query
        start_time = time.time()
        response = agent.ask(request.query, thread_id=request.thread_id)
        processing_time = (time.time() - start_time) * 1000

        # Determine query type (simple heuristic)
        query_lower = request.query.lower()
        if any(word in query_lower for word in ["status", "where", "track"]):
            query_type = QueryType.STATUS
        elif any(word in query_lower for word in ["policy", "refund", "return"]):
            query_type = QueryType.KB_QUERY
        elif any(word in query_lower for word in ["what is my", "my order id"]):
            query_type = QueryType.RECALL
        else:
            query_type = QueryType.GENERAL

        return QueryResponse(
            response=response,
            thread_id=request.thread_id,
            query_type=query_type,
            processing_time_ms=processing_time,
            used_tools=[],
            order_id=agent._thread_order_ids.get(request.thread_id),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process query",
        )


@app.post("/feedback", response_model=FeedbackResponse, tags=["Agent"])
async def submit_feedback(
    request: FeedbackRequest,
    agent: SupportAgent = Depends(get_agent),
):
    """
    Submit feedback to adapt agent behavior.

    Args:
        request: FeedbackRequest containing feedback text.
        agent: SupportAgent instance (injected).

    Returns:
        FeedbackResponse: Status of feedback submission.

    Raises:
        HTTPException: If feedback submission fails.
    """
    try:
        if not request.feedback.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feedback cannot be empty",
            )

        agent.feedback_manager.add_feedback(request.feedback)
        logger.info(f"Feedback added for thread {request.thread_id}: {request.feedback}")

        return FeedbackResponse(
            success=True,
            message="Feedback saved successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save feedback",
        )


@app.get("/recall-order-id", response_model=OrderIDRecallResponse, tags=["Agent"])
async def recall_order_id(
    thread_id: str = "default_thread",
    agent: SupportAgent = Depends(get_agent),
):
    """
    Recall the active order ID for a thread.

    Args:
        thread_id: Thread ID to query.
        agent: SupportAgent instance (injected).

    Returns:
        OrderIDRecallResponse: Active order ID if available.
    """
    try:
        order_id = agent._thread_order_ids.get(thread_id)
        return OrderIDRecallResponse(
            order_id=order_id,
            thread_id=thread_id,
        )
    except Exception as e:
        logger.error(f"Error recalling order ID: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to recall order ID",
        )


@app.post("/clear-memory", response_model=ClearMemoryResponse, tags=["Agent"])
async def clear_memory(
    request: ClearMemoryRequest,
    agent: SupportAgent = Depends(get_agent),
):
    """
    Clear conversation memory for a thread or all threads.

    Args:
        request: ClearMemoryRequest with optional thread_id.
        agent: SupportAgent instance (injected).

    Returns:
        ClearMemoryResponse: List of cleared thread IDs.
    """
    try:
        cleared = []

        if request.thread_id:
            if request.thread_id in agent._thread_order_ids:
                del agent._thread_order_ids[request.thread_id]
                cleared.append(request.thread_id)
                logger.info(f"Cleared memory for thread {request.thread_id}")
        else:
            cleared = list(agent._thread_order_ids.keys())
            agent._thread_order_ids.clear()
            logger.info(f"Cleared memory for {len(cleared)} threads")

        return ClearMemoryResponse(
            success=True,
            cleared_threads=cleared,
        )

    except Exception as e:
        logger.error(f"Error clearing memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear memory",
        )


@app.get("/config", tags=["System"])
async def get_current_config():
    """
    Get current application configuration (non-sensitive).

    Returns:
        Dict: Current configuration (API-safe subset).
    """
    return {
        "app": config.app.dict(),
        "agent": {
            "recursion_limit": config.agent.recursion_limit,
            "thread_ttl_seconds": config.agent.thread_ttl_seconds,
        },
        "rag": {
            "chunk_size": config.rag.chunk_size,
            "retriever_k": config.rag.retriever_k,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True,
    )
