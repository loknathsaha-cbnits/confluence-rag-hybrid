from typing import Any, Dict
from langgraph.graph import END, START, StateGraph
from src.graph.state import State
from src.subgraphs.confluence.agent import generate_node
from src.subgraphs.confluence.mcp_action import mcp_agent_node
from src.subgraphs.confluence.retriever import retriever_node
from src.subgraphs.confluence.supervisor import supervisor_node

def route_next(state: Dict[str, Any]) -> str:
    return state.get("router_decision", "rag")

workflow = StateGraph(State)

workflow.add_node("supervisor", supervisor_node)
workflow.add_node("retrieve", retriever_node)
workflow.add_node("generate", generate_node)
workflow.add_node("mcp_write_action", mcp_agent_node)

# 2. Establish upfront conditional routing layout
workflow.add_edge(START, "supervisor")

workflow.add_conditional_edges(
    "supervisor",
    route_next,
    {
        "rag": "retrieve",                 # Asking query pathway
        "mcp_action": "mcp_write_action"   # Modifying/Writing pathway
    }
)

# 3. Standard terminal boundaries
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", END)
workflow.add_edge("mcp_write_action", END)

compiled_subgraph = workflow.compile()