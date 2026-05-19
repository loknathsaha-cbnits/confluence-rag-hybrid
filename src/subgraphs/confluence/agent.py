import os
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from src.graph.state import State

def generate_node(state: State) -> Dict[str, Any]:
    user_query = state["query"]
    
    # Extract the text attribute from each chunk dictionary saved by the retriever node
    context_blocks = []
    for doc in state["documents"]:
        context_blocks.append(f"Source: {doc['title']} - {doc['section']}\nContext: {doc['text']}")
    
    context = "\n\n---\n\n".join(context_blocks)
    
    print("[Node: Generate] Building answer with Llama-3.3...")
    
    llm = ChatOpenAI(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.2,
        base_url="https://api.groq.com/openai/v1"
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a professional technical engineer. Answer the user prompt using only the verified source snippets provided below.\n\nSnippets:\n{context}"),
        ("human", "{query}")
    ])
    
    rag_chain = prompt | llm
    response = rag_chain.invoke({"context": context, "query": user_query})
    
    return {"generation": response.content}