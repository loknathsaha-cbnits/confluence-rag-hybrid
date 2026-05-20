from src.graph.state import State
from src.graph.graph import main_agent_graph

def run_query():
    user_query = input("Ask a question: ")
    id = "loknath_saha_2004"

    user_input: State = {
        "query": user_query,
        "user_id": id
    }
    print("\nExecuting Master Orchestrator Graph...")
    
    # LangGraph will automatically initialize your operator.add lists to [] if they are missing
    result = main_agent_graph.invoke(user_input)
    
    print("\n=== Final Master Output ===")
    print(result.get("answer"))
    print(f"Confidence: {result.get('confidence_score')}")

if __name__ == "__main__":
    run_query()