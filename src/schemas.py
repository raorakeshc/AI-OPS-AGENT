"""Data models and schemas for API and internal use."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator, constr
from enum import Enum


class QueryType(str, Enum):
    """Types of user queries."""
    STATUS = "status"
    KB_QUERY = "kb_query"
    RECALL = "recall"
    GENERAL = "general"


class QueryRequest(BaseModel):
    """Request model for user queries."""
    query: constr(min_length=1, max_length=2000) = Field(
        ..., description="User query (1-2000 characters)"
    )
    thread_id: Optional[str] = Field(
        "default_thread",
        description="Conversation thread ID for memory persistence"
    )
    order_id: Optional[str] = Field(
        None,
        description="Optional order ID to include in context"
    )

    @validator("query")
    def strip_query(cls, v: str) -> str:
        """Strip whitespace from query."""
        return v.strip()


class QueryResponse(BaseModel):
    """Response model for query results."""
    response: str = Field(..., description="Agent's response")
    thread_id: str = Field(..., description="Thread ID used for this request")
    query_type: QueryType = Field(..., description="Type of query detected")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    used_tools: List[str] = Field(default_factory=list, description="Tools used")
    order_id: Optional[str] = Field(None, description="Active order ID if any")


class FeedbackRequest(BaseModel):
    """Request model for submitting feedback."""
    feedback: constr(min_length=1, max_length=500) = Field(
        ..., description="Feedback text (1-500 characters)"
    )
    thread_id: Optional[str] = Field(
        "default_thread",
        description="Associated thread ID"
    )

    @validator("feedback")
    def strip_feedback(cls, v: str) -> str:
        """Strip whitespace from feedback."""
        return v.strip()


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""
    success: bool = Field(..., description="Whether feedback was saved")
    message: str = Field(..., description="Status message")


class HealthCheckResponse(BaseModel):
    """Response model for health check."""
    status: str = Field(..., description="Health status: 'healthy' or 'unhealthy'")
    version: str = Field(..., description="Application version")
    components: Dict[str, str] = Field(
        ..., description="Health status of components"
    )


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )
    trace_id: Optional[str] = Field(
        None, description="Request trace ID for debugging"
    )


class OrderIDRecallRequest(BaseModel):
    """Request model for order ID recall."""
    thread_id: str = Field(
        "default_thread",
        description="Thread ID to retrieve order for"
    )


class OrderIDRecallResponse(BaseModel):
    """Response model for order ID recall."""
    order_id: Optional[str] = Field(..., description="Remembered order ID or None")
    thread_id: str = Field(..., description="Thread ID queried")


class ClearMemoryRequest(BaseModel):
    """Request model for clearing conversation memory."""
    thread_id: Optional[str] = Field(
        None,
        description="Specific thread to clear; if None, clears all"
    )


class ClearMemoryResponse(BaseModel):
    """Response model for memory clear."""
    success: bool = Field(..., description="Whether operation succeeded")
    cleared_threads: List[str] = Field(
        ..., description="List of cleared thread IDs"
    )


class ConversationEntry(BaseModel):
    """Single message in conversation history."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(None, description="ISO timestamp")


class ConversationHistoryResponse(BaseModel):
    """Response model for conversation history."""
    thread_id: str = Field(..., description="Thread ID")
    messages: List[ConversationEntry] = Field(
        ..., description="Conversation messages"
    )
    order_id: Optional[str] = Field(None, description="Active order ID if any")
