import os
from typing import Any, Dict
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.graph.state import State

class IntentClassifier(BaseModel):
    route: str = Field(
        description="Choose 'rag' if the user is asking a question or looking for information. Choose 'mcp_action' if the user is explicitly telling you to create, edit, update, or publish a page/ticket."
    )

def supervisor_node(state: State) -> Dict[str, Any]:
    print(f"[DEBUG GRAPH] transcript in state: {'YES' if state.get('transcript') else 'NO'}")
    print(f"[DEBUG GRAPH] transcript length: {len(state.get('transcript', ''))}")
    user_query = state.get("query", "")
    print(f"[Node: Supervisor] Classifying incoming query intent: '{user_query}'")
    
    llm = ChatOpenAI(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.0,              # Keeps the output completely deterministic
        max_tokens=5,                 # Stops the model from writing rambling sentences
        base_url="https://api.groq.com/openai/v1"
    )
    
    prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are an operations traffic controller. Classify the user's intent precisely.\n"
        "Respond with exactly ONE word: either 'rag' or 'mcp_action'. Do not include punctuation.\n\n"
        "- Choose 'rag' if the user is asking a question, asking you to summarize text, explain something, or look up information. "
        "Even if they use words like 'write a summary' or 'draft a response' to be shown inside the chat window, choose 'rag'.\n"
        "- Choose 'mcp_action' ONLY if they are explicitly commanding you to interact with the external system—such as "
        "creating a permanent page on Confluence, updating a live wiki document, or publishing data."
    )),
    ("human", "{query}")
])
    
    # Execute as a standard string chain instead of structured schemas to prevent Groq API 400 errors
    chain = prompt | llm
    response = chain.invoke({"query": user_query})
    
    # Sanitize output content text
    decision = response.content.strip().lower()
    
    # Fallback guard to ensure a weird model response doesn't break graph execution
    if "mcp_action" in decision or "action" in decision:
        final_route = "mcp_action"
    else:
        final_route = "rag"
        
    print(f"[Node: Supervisor Decision] Determined routing direction -> '{final_route}'")
    
    return {"router_decision": final_route}