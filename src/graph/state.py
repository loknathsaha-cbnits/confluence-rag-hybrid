from typing import Optional, TypedDict, Annotated, List
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class SourceState(TypedDict):
    title: str
    url: str
    last_updated: str

class DataSource(TypedDict):
    chunk_id: str
    text_content: str
    score: float
    source: SourceState

class State(TypedDict):
    """
    The global state schema for OpsEngine. 
    Maintains conversation history, routing directions, and temporary tool payloads.
    """
    query: str
    user_id: str

    retrieved_results: Annotated[List[DataSource], add_messages]
    sources: Annotated[List[SourceState], add_messages]

    answer: Optional[str] = None
    confidence_score: float = 0.0
