import os
from typing import Any, Dict
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.graph.state import State

class GenerationOutput(BaseModel):
    current_answer: str = Field(
        description="A highly comprehensive, well-structured technical explanation (minimum 200 words) matching the markdown rules."
    )
    confidence_score: float = Field(
        description="A float between 0.0 and 1.0 indicating context accuracy."
    )

def generate_node(state: State) -> Dict[str, Any]:
    user_query = state.get("query", "")
    retrieved_results = state.get("retrieved_results", [])
    
    print("[Node: Generate] Building detailed architectural answer with Llama-3.3...")
    
    context_blocks = []
    for doc in retrieved_results:
        title = doc.get("source", {}).get("title", "Unknown Source")
        content = doc.get("text_content", "")
        context_blocks.append(f"Source Document: {title}\nContext Snippet:\n{content}")
    
    context = "\n\n---\n\n".join(context_blocks) if context_blocks else "No context available."
    
    # FIX 1: Set temperature to 0.1 for high instruction compliance and predictable formatting
    llm = ChatOpenAI(
        model="llama-3.1-8b-instant",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.1, 
        base_url="https://api.groq.com/openai/v1"
    )
    
    llm_with_tools = llm.bind_tools([GenerationOutput], tool_choice="any")
    
    # FIX 2: Enhanced prompt enforcing structural length, bulleted details, and deep scope
    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are an expert infrastructure and technical support engineer. Provide an exhaustive, "
            "comprehensive technical overview answering the user prompt. Your response MUST be comprehensive, "
            "detailed, and contain at least 200 words based ONLY on the verified source snippets below.\n\n"
            
            "Mandatory Structural Layout Rules:\n"
            "1. **Executive Summary**: Begin with a crisp sub-paragraph defining the core concept or feature.\n"
            "2. **Core Capabilities / Mechanics**: Use a dedicated `### Core Details` markdown heading. "
            "Explain technical specifications using structured bullet points (`*`). Bold key terms (`**keyword**`).\n"
            "3. **Implementation & Architecture**: Include a `### Architectural Scope` section to break down prerequisites, "
            "commands, or infrastructure mechanics using clean backticks for code blocks or flags (e.g., `GlobalProtect CLI`).\n"
            "4. **Depth Requirement**: Avoid high-level sentences. Provide complete detail using the context chunks provided. Do not use outside facts.\n\n"
            
            "STRICT NOTE: IF ANY QUESTION IS NOT RELATED TO GLOBALPROTECT OR THE QUESTION HAS NO RELATION WITH CONFLUENCE PRD, SAY THAT YOU CANNOT ANSWER THIS QUESTION. YOU ARE A SPECIALIZED AGENT FOR PARTICULAR KNOWLEDGE BASE ONLY"
            "Snippets:\n{context}"
        )),
        ("human", "{query}")
    ])
    
    try:
        rag_chain = prompt | llm_with_tools
        response = rag_chain.invoke({"context": context, "query": user_query})
        
        if response.tool_calls:
            structured_data = response.tool_calls[0]['args']
            return {
                "current_answer": structured_data.get("current_answer"),
                "confidence_score": float(structured_data.get("confidence_score", 0.0))
            }
        else:
            return {
                "current_answer": response.content,
                "confidence_score": 0.0 
            }
            
    except Exception as e:
        # Check if Groq failed specifically due to tool formatting issues
        err_msg = str(e)
        if "failed_generation" in err_msg:
            print("[Node: Generate Warning] Tool call validation failed. Extracting raw generation string fallback...")
            try:
                import re
                # Use regex to isolate the text sitting inside the answer property bounds
                answer_match = re.search(r'"current_answer":\s*"(.*?)"\s*,\s*"confidence_score"', err_msg, re.DOTALL)
                score_match = re.search(r'"confidence_score":\s*([\d\.]+)', err_msg)
                
                fallback_answer = answer_match.group(1).encode().decode('unicode_escape') if answer_match else "Context parsing anomaly."
                fallback_score = float(score_match.group(1)) if score_match else 0.5
                
                # Replace unescaped newline string fragments that break display layouts
                fallback_answer = fallback_answer.replace('\\n', '\n')
                
                return {
                    "current_answer": fallback_answer,
                    "confidence_score": fallback_score
                }
            except Exception as extraction_error:
                print(f"Fallback extraction failed: {extraction_error}")
        
        # If it's a completely different error, raise it up to Chainlit
        raise e