from langgraph.graph import END, START, StateGraph

from src.graph.state import State
from src.subgraphs.confluence.agent import generate_node
from src.subgraphs.confluence.retriever import retriever_node


workflow = StateGraph(State)

workflow.add_node("retrieve", retriever_node)
workflow.add_node("generate", generate_node)

workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", END)

compiled_subgraph = workflow.compile()