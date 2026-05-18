import os
from pathlib import Path

def create_opsengine_structure():
    print("🚀 Initializing OpsEngine project structure via Python...")
    
    # Base directory context (assumes running from the desired project root or creates an 'opsengine' folder)
    root = Path.cwd() / "opsengine"
    root.mkdir(exist_ok=True)
    
    # Define the directory matrix
    directories = [
        root / "data",
        root / "src" / "graph",
        root / "src" / "subgraphs" / "confluence",
        root / "src" / "subgraphs" / "jira",
        root / "src" / "subgraphs" / "support",
        root / "src" / "utils",
    ]
    
    # Create directories
    for target_dir in directories:
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"📂 Created directory: {target_dir.relative_to(Path.cwd())}")

    # Define files with their exact initial code content
    files_manifest = {
        root / "langgraph.json": '''{
  "dependencies": ["."],
  "graphs": {
    "opsengine_hub": "./src/hub/graph.py:graph",
    "confluence_agent": "./src/subgraphs/confluence/graph.py:graph"
  },
  "env": ".env"
}''',
        
        root / ".env": '''# --- LLM API Providers (Free Tiers) ---
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# --- Production Observability & Tracing ---
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=opsengine-development''',

        root / "src" / "__init__.py": "",
        root / "src" / "config.py": "# Configuration configurations go here\n",
        
        root / "src" / "state.py": '''from typing import TypedDict, Annotated, Sequence, Dict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class SharedState(TypedDict):
    """
    The global state schema for OpsEngine. 
    Maintains conversation history, routing directions, and temporary tool payloads.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    current_agent: str
    context: Dict[str, Any]
    audit_log: Sequence[str]
''',

        root / "src" / "hub" / "__init__.py": "",
        
        root / "src" / "hub" / "graph.py": '''from langgraph.graph import StateGraph, START, END
from src.state import SharedState
from src.utils.llm_client import get_llm
from langchain_core.messages import AIMessage

builder = StateGraph(SharedState)

def supervisor_router(state: SharedState) -> SharedState:
    llm = get_llm(provider="gemini")
    messages = state["messages"]
    response = llm.invoke(messages)
    
    return {
        "messages": [response],
        "current_agent": "supervisor_hub",
        "audit_log": ["Executed supervisor_router intent evaluation."]
    }

builder.add_node("supervisor_router", supervisor_router)
builder.add_edge(START, "supervisor_router")
builder.add_edge("supervisor_router", END)

graph = builder.compile()
''',
        
        root / "src" / "hub" / "nodes.py": "# Hub specific processing nodes\n",
        root / "src" / "subgraphs" / "__init__.py": "",
        root / "src" / "subgraphs" / "confluence" / "__init__.py": "",
        root / "src" / "subgraphs" / "confluence" / "graph.py": "# Confluence subgraph topolgy\n",
        root / "src" / "subgraphs" / "confluence" / "nodes.py": "# Confluence extraction & search processing logic\n",
        root / "src" / "subgraphs" / "confluence" / "state.py": "# Subgraph isolated schema overrides\n",
        
        root / "src" / "subgraphs" / "jira" / "__init__.py": "",
        root / "src" / "subgraphs" / "jira" / "graph.py": "",
        root / "src" / "subgraphs" / "jira" / "nodes.py": "",
        
        root / "src" / "subgraphs" / "support" / "__init__.py": "",
        root / "src" / "subgraphs" / "support" / "graph.py": "",
        root / "src" / "subgraphs" / "support" / "nodes.py": "",
        
        root / "src" / "utils" / "__init__.py": "",
        root / "src" / "utils" / "db_helper.py": "# SQLite checkpointer wrappers\n",
        
        root / "src" / "utils" / "llm_client.py": '''import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

load_dotenv()

def get_llm(provider: str = "gemini"):
    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or "your_gemini" in api_key:
            raise ValueError("Missing valid GEMINI_API_KEY in your .env configuration.")
        return ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=api_key, temperature=0, streaming=True)
        
    elif provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key or "your_groq" in api_key:
            raise ValueError("Missing valid GROQ_API_KEY in your .env configuration.")
        return ChatGroq(model="llama-3.1-8b-instant", groq_api_key=api_key, temperature=0)
        
    else:
        raise ValueError(f"Target LLM provider '{provider}' is not supported.")
'''
    }

    # Populate files on disk
    for file_path, content in files_manifest.items():
        file_path.write_text(content, encoding="utf-8")
        print(f"📝 Hydrated file: {file_path.relative_to(Path.cwd())}")

    print("\n--------------------------------------------------------")
    print("✅ OpsEngine python scaffolding completed successfully!")
    print(f"📂 Next Step: Navigate to your new workspace via 'cd opsengine'")
    print("--------------------------------------------------------")

if __name__ == "__main__":
    create_opsengine_structure()