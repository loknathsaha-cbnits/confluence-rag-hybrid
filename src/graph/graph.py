# graph.py
from typing import List, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

# Import the compiled runner from your subgraph module
from src.subgraphs.confluence.graph import compiled_subgraph

# --- 1. Define Main/Parent State ---
class ParentState(TypedDict):
    query: str
    router_decision: str
    final_answer: str

# --- 2. Define Parent Graph Nodes ---
def query_processing_node(state: ParentState) -> Dict[str, Any]:
    """Cleans or reformats user input before hitting search."""
    raw_query = state["query"]
    print(f"[Parent Node] Processing incoming query: {raw_query}")
    return {"query": raw_query.strip()}

def call_retrieval_subgraph_node(state: ParentState) -> Dict[str, Any]:
    """
    Acts as the entry bridge. Maps parent state keys into the subgraph structure,
    runs the execution flow, and extracts values back to the parent scope.
    """
    print("[Parent Node] Handing off control to Retrieval Subgraph...")
    
    # Map Parent keys -> Subgraph expected keys
    subgraph_input = {
        "sub_query": state["query"]
    }
    
    # Execute the entire compiled subgraph synchronously
    subgraph_output = compiled_subgraph.invoke(subgraph_input)
    
    # Map Subgraph outputs back -> Parent state keys
    return {
        "final_answer": subgraph_output["sub_generation"]
    }

# --- 3. Assemble and Compile Main Graph Architecture ---
parent_builder = StateGraph(ParentState)

# Add standard functional nodes and the subgraph node wrapper
parent_builder.add_node("process_query", query_processing_node)
parent_builder.add_node("retrieval_flow_subgraph", call_retrieval_subgraph_node)

# Map execution path
parent_builder.add_edge(START, "process_query")
parent_builder.add_edge("process_query", "retrieval_flow_subgraph")
parent_builder.add_edge("retrieval_flow_subgraph", END)

# Compile Main Graph
main_agent_graph = parent_builder.compile()

# --- 4. Local Execution Test ---
if __name__ == "__main__":
    test_input = {
        "query": "How can I check connection status for GlobalProtect client on Linux?"
    }
    
    print("\nExecuting Master Orchestrator Graph...")
    result = main_agent_graph.invoke(test_input)
    
    print("\n=== Final Master Output ===")
    print(result["final_answer"])