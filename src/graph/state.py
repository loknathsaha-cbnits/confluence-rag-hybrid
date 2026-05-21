import operator
from typing import NotRequired, Optional, TypedDict, Annotated, List
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

    retrieved_results: NotRequired[Annotated[List[DataSource], operator.add]]
    sources: NotRequired[Annotated[List[SourceState], operator.add]]

    current_answer: NotRequired[str]
    previous_answer: NotRequired[str]
    
    execution_status: NotRequired[str]
    confidence_score: NotRequired[float]

    router_decision: NotRequired[str]
