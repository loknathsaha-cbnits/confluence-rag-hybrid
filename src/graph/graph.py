# graph.py
from typing import List, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from src.graph.state import State
from src.subgraphs.confluence.graph import compiled_subgraph


def query_processing_node(state: State) -> Dict[str, Any]:
    """Cleans or reformats user input before hitting search."""
    raw_query = state["query"]
    print(f"[Parent Node] Processing incoming query: {raw_query}")
    return {"query": raw_query.strip()}

def call_retrieval_subgraph_node(state: State) -> Dict[str, Any]:
    """
    Acts as the entry bridge. Maps parent state keys into the subgraph structure,
    runs the execution flow, and extracts values back to the parent scope.
    """
    print("[Parent Node] Handing off control to Retrieval Subgraph...")
    
    subgraph_input = {
        "query": state["query"],
        "user_id": state["user_id"]
    }
    
    subgraph_output = compiled_subgraph.invoke(subgraph_input)

    return {
        "answer": subgraph_output.get("answer", "No answer generated."),
        "confidence_score": subgraph_output.get("confidence_score")
    }

# Graph
parent_builder = StateGraph(State)

parent_builder.add_node("process_query", query_processing_node)
parent_builder.add_node("retrieval_flow_subgraph", call_retrieval_subgraph_node)

# Map execution path
parent_builder.add_edge(START, "process_query")
parent_builder.add_edge("process_query", "retrieval_flow_subgraph")
parent_builder.add_edge("retrieval_flow_subgraph", END)

main_agent_graph = parent_builder.compile()