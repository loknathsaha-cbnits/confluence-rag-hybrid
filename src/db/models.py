from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class UserRecord:
    """Represents a user in the system."""
    user_id: str
    created_at: datetime
    last_active: datetime


@dataclass
class SessionRecord:
    """Represents a conversation session."""
    session_id: str
    user_id: str
    created_at: datetime
    engine_mode: str
    status: str = "active"


@dataclass
class InteractionRecord:
    """Represents a single query-answer interaction."""
    interaction_id: Optional[int]
    session_id: str
    user_id: str
    query: str
    answer: str
    confidence_score: float
    router_decision: Optional[str]
    execution_status: str
    processing_time_ms: int
    created_at: datetime
    error_message: Optional[str] = None


@dataclass
class SourceRecord:
    """Represents a source document used in an answer."""
    source_id: Optional[int]
    interaction_id: int
    url: str
    title: str
    chunk_id: Optional[str] = None
    relevance_score: Optional[float] = None
    created_at: Optional[datetime] = None
