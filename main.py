import os
import chainlit as cl
from dotenv import load_dotenv
from langchain_core.runnables.config import RunnableConfig

# Import your master orchestrator graph
from src.graph.graph import main_agent_graph

load_dotenv()

@cl.on_chat_start
async def on_chat_start():
    """Runs when a user opens the chat UI session."""
    cl.user_session.set("user_id", "loknath_saha_2004")
    
    # Send a clean welcome greeting
    # await cl.Message(
    #     content="Welcome! Ask me anything about your confluence PRDs"
    # ).send()

    from chainlit.input_widget import Select
    await cl.ChatSettings([
        Select(
            id="engine_mode",
            label="🤖 OpsEngine Active Subgraph",
            values=["Confluence-Hybrid-RAG", "Jira-Sprints", "Support-Automation"],
            initial_index=0
        )
    ]).send()


@cl.on_message
async def on_message(msg: cl.Message):
    """Runs whenever a user sends a message in the UI."""
    
    user_id = cl.user_session.get("user_id")
    thread_id = cl.context.session.id
    config = RunnableConfig(configurable={"thread_id": thread_id})
    
    # 1. Fetch the existing state from the checkpoint memory before triggering a new turn
    past_answer = ""
    try:
        current_graph_state = await main_agent_graph.aget_state(config)
        if current_graph_state and current_graph_state.values:
            # Safely grab the answer generated during the previous turn
            past_answer = current_graph_state.values.get("current_answer", "")

        print("\n--- [DEBUG 1: MAIN.PY CHECKPOINT ENTRY] ---")
        print(f"Loaded past_answer from memory: {repr(past_answer)}")
        print("-------------------------------------------\n")
    except Exception as state_err:
        print(f"[Chainlit Session Warning] Could not fetch checkpoint state: {state_err}")

    # 2. Package the initial state, passing down the historical answer under a protected key
    initial_state = {
        "query": msg.content,
        "user_id": user_id,
        "previous_answer": past_answer  # Handed off safely to your state pipeline
    }
    
    final_answer = cl.Message(content="")
    await final_answer.send()
    
    print(f"\n[Chainlit Session] Processing query: {msg.content}")
    
    try:
        # 3. Run the entire graph execution pipeline
        result = await main_agent_graph.ainvoke(initial_state, config=config)
        
        # Extract values matching your updated schema output
        answer = result.get("current_answer") or result.get("final_answer") or "No response generated."
        confidence = result.get("confidence_score", 0.0)
        raw_sources = result.get("sources", [])
        
        # 4. Build Chainlit text elements for references (Clickable UI Cards)
        cl_elements = []
        seen_urls = set()
        
        for idx, src in enumerate(raw_sources, start=1):
            url = src.get("url", "")
            title = src.get("title", "").replace("+", " ") or f"Reference Doc {idx}"
            
            if url and url not in seen_urls:
                seen_urls.add(url)
                
                # We use cl.Text with a markdown clean link inside the body 
                # This keeps the reference card itself compact and professional
                card_content = f"🔗 **Official Documentation:**\n[{title}]({url})"
                cl_elements.append(
                    cl.Text(name=f"📄 {title}", content=card_content, display="inline")
                )
        
        formatted_response = f"{answer}\n\n---\n💡 *Confidence Score: {float(confidence) * 100:.0f}%*"
        
        final_answer.content = formatted_response
        final_answer.elements = cl_elements
        await final_answer.update()
        
    except Exception as e:
        final_answer.content = f"❌ An error occurred during graph processing: {str(e)}"
        await final_answer.update()