import os
from typing import Any, Dict
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from src.graph.state import State

# --- 1. Define Structured Output Schema ---
class GenerationOutput(BaseModel):
    answer: str = Field(
        description="The professional, detailed answer to the user's query based ONLY on the provided context."
    )
    confidence_score: float = Field(
        description="A float between 0.0 and 1.0 indicating how confident you are that the context fully answers the query. (e.g., 0.95 for high confidence, 0.2 for low confidence)"
    )

def generate_node(state: State) -> Dict[str, Any]:
    # Extract query and results from the new state schema
    user_query = state.get("query", "")
    retrieved_results = state.get("retrieved_results", [])
    
    print("[Node: Generate] Building answer and confidence score with Llama-3.3...")
    
    # --- 2. Build Context from the new DataSource schema ---
    context_blocks = []
    for doc in retrieved_results:
        # Navigate through the nested SourceState to get the title
        title = doc.get("source", {}).get("title", "Unknown Source")
        content = doc.get("text_content", "")
        context_blocks.append(f"Source: {title}\nContext: {content}")
    
    context = "\n\n---\n\n".join(context_blocks) if context_blocks else "No context available."
    
    # --- 3. Initialize LLM ---
    llm = ChatOpenAI(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.2,
        base_url="https://api.groq.com/openai/v1"
    )
    
    # Bind the Pydantic schema to force the LLM to return JSON with answer & confidence_score
    llm_with_tools = llm.bind_tools([GenerationOutput], tool_choice="any")
    
    # --- 4. Build Prompt ---
    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are a professional technical engineer. Answer the user prompt using ONLY the verified source snippets provided below. "
            "Evaluate how well these snippets answer the user's query and provide a confidence_score.\n\n"
            "Snippets:\n{context}"
        )),
        ("human", "{query}")
    ])
    
    # --- 5. Execute Chain ---
    rag_chain = prompt | llm_with_tools
    response = rag_chain.invoke({"context": context, "query": user_query})

    print("======================================")
    print(response)
    print("======================================")

    
    if response.tool_calls:
        structured_data = response.tool_calls[0]['args']
        return {
            "answer": structured_data.get("answer"),
            "confidence_score": float(structured_data.get("confidence_score", 0.0))
        }
    else:
        return {
            "answer": response.content,
            "confidence_score": 0.0 
        }